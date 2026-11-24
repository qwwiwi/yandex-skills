#!/usr/bin/env python3
"""Yandex Webmaster API v4 wrapper – SEO data of your sites.

Auth: OAuth token in YANDEX_OAUTH_TOKEN (environment or env file, see YANDEX_ENV_FILE).
Header: Authorization: OAuth <token>. user_id and host_id are resolved automatically.
The site is passed with --host (a domain such as example.com, a URL, or a full host_id
like https:example.com:443) or taken from WEBMASTER_HOST.

Subcommands:
  hosts                         list sites + verification status
  summary   [--host ...]        summary (SQI, number of problems)
  queries   [--host ...]        TOP search queries (shows/clicks/position) – the main SEO report
  q-history [--host ...]        history of the sum over all queries (dynamics)
  indexing  [--host ...]        pages in search + history
  sitemaps  [--host ...]        sitemaps (list); add one: --add <url>
  diagnostics [--host ...]      site problems (severity/state)
  recrawl   [--host ...] --url  send a URL for recrawl (+ shows the quota)
  links     [--host ...]        external links (history)
  raw --method GET --path /...  arbitrary API call

Examples:
  webmaster.py hosts
  webmaster.py queries --host example.com --indicator TOTAL_SHOWS --indicator TOTAL_CLICKS --indicator AVG_SHOW_POSITION --days 28 --limit 50
  webmaster.py diagnostics --host example.com
  webmaster.py recrawl --host example.com --url https://example.com/page/
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta
from pathlib import Path

BASE = "https://api.webmaster.yandex.net/v4"


def _read_env_file() -> dict[str, str]:
    """Parse a KEY=VALUE file (YANDEX_ENV_FILE, default ./.env); {} if missing."""
    path = Path(os.environ.get("YANDEX_ENV_FILE", ".env"))
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def get_setting(name: str) -> str:
    """Return a setting from the environment, falling back to the env file."""
    return os.environ.get(name) or _read_env_file().get(name, "")


def token() -> str:
    """Return the OAuth token or exit with a clear message."""
    value = get_setting("YANDEX_OAUTH_TOKEN")
    if not value:
        sys.exit("YANDEX_OAUTH_TOKEN is not set (export it or put it into the env file; see README.md)")
    return value


def api(path: str, method: str = "GET", body: dict | None = None) -> dict:
    """Call the Webmaster API; HTTP errors are returned as a dict with `_http`."""
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(BASE + path, data=data, method=method,
                                 headers={"Authorization": f"OAuth {token()}",
                                          "Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(req, timeout=30) as r:
            txt = r.read().decode("utf-8", "replace")
            return json.loads(txt) if txt.strip() else {}
    except urllib.error.HTTPError as e:
        payload = e.read().decode("utf-8", "replace")
        try:
            j = json.loads(payload)
        except ValueError:
            j = {"error_message": payload[:300]}
        j["_http"] = e.code
        return j


_UID: str | None = None


def user_id() -> str:
    """Return (and cache) the numeric Webmaster user id of the token owner."""
    global _UID
    if _UID is None:
        _UID = str(api("/user/").get("user_id", ""))
    return _UID


_HOSTS: list[dict] | None = None


def hosts() -> list[dict]:
    """Return (and cache) the sites of the account."""
    global _HOSTS
    if _HOSTS is None:
        _HOSTS = api(f"/user/{user_id()}/hosts").get("hosts", [])
    return _HOSTS


def normalize_domain(value: str) -> str:
    """Reduce 'https://Example.com/path' to 'example.com'."""
    value = value.strip().lower()
    if "://" in value:
        value = value.split("://", 1)[1]
    return value.split("/", 1)[0]


def host_id(site: str | None) -> str:
    """Resolve a domain/URL (or a ready host_id like https:example.com:443) to host_id."""
    if not site:
        sys.exit("host is not set: pass --host <domain> or set WEBMASTER_HOST (run `hosts` to list sites)")
    if site.count(":") == 2 and "/" not in site:  # already a host_id: protocol:host:port
        return site
    dom = normalize_domain(site)
    for h in hosts():
        url = h.get("unicode_host_url", "") or h.get("ascii_host_url", "")
        if f"//{dom}/" in url or f"//www.{dom}/" in url:  # exact host, not substring
            return h["host_id"]
    sys.exit(f"host '{site}' not found among the sites of this account (run `hosts`)")


def hpath(site: str | None, tail: str) -> str:
    """Build /user/<uid>/hosts/<host_id><tail> with the host_id URL-encoded."""
    hid = host_id(site)  # validate the host first: fails fast without a network call
    return f"/user/{user_id()}/hosts/{urllib.parse.quote(hid, safe='')}{tail}"


def loading_guard(res: dict) -> bool:
    """Print a readable status and return True if the response is not usable data."""
    if res.get("error_code") == "HOST_NOT_LOADED":
        print("Сайт ещё загружается в Вебмастер (только подключён). "
              "Данные по запросам/индексации появятся через несколько часов–сутки. "
              "Сейчас доступны: sitemaps, diagnostics, recrawl, links.")
        return True
    if "_http" in res and res.get("_http") not in (200, 201):
        print(f"API {res.get('_http')}: {res.get('error_code','')} {res.get('error_message','')}")
        return True
    return False


def days_range(n: int) -> tuple[str, str]:
    """Return (today - n days, today) as ISO dates."""
    return (date.today() - timedelta(days=n)).isoformat(), date.today().isoformat()


# ---- commands ----
def cmd_hosts(a):
    for h in hosts():
        print(f"{h.get('unicode_host_url'):<32} verified={h.get('verified')}  id={h.get('host_id')}")


def cmd_summary(a):
    res = api(hpath(a.site, "/summary"))
    if loading_guard(res):
        return
    print(json.dumps(res, ensure_ascii=False, indent=2))


def cmd_queries(a):
    d1, d2 = days_range(a.days)
    params = [("order_by", a.order_by), ("date_from", d1), ("date_to", d2),
              ("device_type_indicator", a.device), ("limit", str(a.limit)), ("offset", str(a.offset))]
    for ind in a.indicator:
        params.append(("query_indicator", ind))
    res = api(hpath(a.site, "/search-queries/popular?" + urllib.parse.urlencode(params)))
    if loading_guard(res):
        return
    qs = res.get("queries", [])
    print(f"ТОП {len(qs)} запросов @{normalize_domain(a.site)} ({d1}..{d2}), сортировка {a.order_by}:")
    for q in qs:
        ind = q.get("indicators", {})
        cells = "  ".join(f"{k}={ind[k]}" for k in ind)
        print(f"  {q.get('query_text','?'):<45} {cells}")


def cmd_q_history(a):
    d1, d2 = days_range(a.days)
    params = [("date_from", d1), ("date_to", d2)]
    for ind in a.indicator:
        params.append(("query_indicator", ind))
    res = api(hpath(a.site, "/search-queries/all/history?" + urllib.parse.urlencode(params)))
    if loading_guard(res):
        return
    print(json.dumps(res, ensure_ascii=False, indent=2)[:4000])


def cmd_indexing(a):
    res = api(hpath(a.site, "/search-urls/in-search/history"))
    if loading_guard(res):
        return
    print(json.dumps(res, ensure_ascii=False, indent=2)[:4000])


def cmd_sitemaps(a):
    if a.add:
        res = api(hpath(a.site, "/user-added-sitemaps"), method="POST", body={"url": a.add})
        print("added:", json.dumps(res, ensure_ascii=False))
        return
    res = api(hpath(a.site, "/sitemaps"))
    ua = api(hpath(a.site, "/user-added-sitemaps"))
    print("sitemaps:", json.dumps(res.get("sitemaps", res), ensure_ascii=False))
    print("user-added:", json.dumps(ua.get("sitemaps", ua), ensure_ascii=False))


def cmd_diagnostics(a):
    res = api(hpath(a.site, "/diagnostics"))
    if loading_guard(res):
        return
    probs = res.get("problems", {})
    present = {k: v for k, v in probs.items() if v.get("state") not in ("ABSENT", None)}
    print(f"Диагностика @{normalize_domain(a.site)}: {len(probs)} проверок, активных проблем {len(present)}")
    for k, v in (present or probs).items():
        print(f"  {k:<28} severity={v.get('severity')}  state={v.get('state')}")


def cmd_recrawl(a):
    quota = api(hpath(a.site, "/recrawl/quota"))
    print(f"квота переобхода: {quota.get('quota_remainder')}/{quota.get('daily_quota')} в день")
    if a.url:
        res = api(hpath(a.site, "/recrawl/queue"), method="POST", body={"url": a.url})
        print("отправлено на переобход:", json.dumps(res, ensure_ascii=False))


def cmd_links(a):
    # external/history requires the `indicator` query param
    res = api(hpath(a.site, "/links/external/history?indicator=LINKS_TOTAL_COUNT"))
    print("external:", json.dumps(res.get("indicators", res), ensure_ascii=False)[:1500])
    samp = api(hpath(a.site, "/links/external/samples?limit=20"))
    print("samples:", json.dumps(samp.get("links", samp), ensure_ascii=False)[:1500])


def cmd_raw(a):
    res = api(a.path, method=a.method, body=json.loads(a.body) if a.body else None)
    print(json.dumps(res, ensure_ascii=False, indent=2)[:6000])


def main():
    p = argparse.ArgumentParser(description="Yandex Webmaster API v4")
    sub = p.add_subparsers(dest="cmd", required=True)
    default_host = get_setting("WEBMASTER_HOST") or None

    def site_arg(sp):
        sp.add_argument("--host", dest="site", default=default_host,
                        help="domain, URL or host_id; default: WEBMASTER_HOST")

    sub.add_parser("hosts", help="list sites and verification status").set_defaults(fn=cmd_hosts)
    sp = sub.add_parser("summary", help="SQI and problem counters")
    site_arg(sp)
    sp.set_defaults(fn=cmd_summary)

    sp = sub.add_parser("queries", help="top search queries")
    site_arg(sp)
    sp.add_argument("--order-by", dest="order_by", default="TOTAL_SHOWS",
                    choices=["TOTAL_SHOWS", "TOTAL_CLICKS"])
    sp.add_argument("--indicator", action="append",
                    default=None, help="TOTAL_SHOWS/TOTAL_CLICKS/AVG_SHOW_POSITION/AVG_CLICK_POSITION (repeatable)")
    sp.add_argument("--device", default="ALL", choices=["ALL", "DESKTOP", "MOBILE", "TABLET"])
    sp.add_argument("--days", type=int, default=28)
    sp.add_argument("--limit", type=int, default=50)
    sp.add_argument("--offset", type=int, default=0)
    sp.set_defaults(fn=cmd_queries)

    sp = sub.add_parser("q-history", help="dynamics of all queries")
    site_arg(sp)
    sp.add_argument("--indicator", action="append", default=None)
    sp.add_argument("--days", type=int, default=28)
    sp.set_defaults(fn=cmd_q_history)

    sp = sub.add_parser("indexing", help="pages in search, history")
    site_arg(sp)
    sp.set_defaults(fn=cmd_indexing)

    sp = sub.add_parser("sitemaps", help="list sitemaps or add one")
    site_arg(sp)
    sp.add_argument("--add", default=None, help="sitemap URL to add")
    sp.set_defaults(fn=cmd_sitemaps)

    sp = sub.add_parser("diagnostics", help="site problems")
    site_arg(sp)
    sp.set_defaults(fn=cmd_diagnostics)

    sp = sub.add_parser("recrawl", help="recrawl quota; send a URL for recrawl")
    site_arg(sp)
    sp.add_argument("--url", default=None, help="URL to send for recrawl")
    sp.set_defaults(fn=cmd_recrawl)

    sp = sub.add_parser("links", help="external links")
    site_arg(sp)
    sp.set_defaults(fn=cmd_links)

    sp = sub.add_parser("raw", help="arbitrary API call")
    sp.add_argument("--method", default="GET")
    sp.add_argument("--path", required=True, help="path after /v4, e.g. /user/")
    sp.add_argument("--body", default=None, help="JSON body")
    sp.set_defaults(fn=cmd_raw)

    a = p.parse_args()
    if getattr(a, "indicator", "x") is None:
        a.indicator = ["TOTAL_SHOWS", "TOTAL_CLICKS", "AVG_SHOW_POSITION"]
    a.fn(a)


if __name__ == "__main__":
    main()
