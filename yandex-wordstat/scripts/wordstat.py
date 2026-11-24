#!/usr/bin/env python3
"""Yandex Cloud Search API – Wordstat client.

Endpoint: https://searchapi.api.cloud.yandex.net/v2/wordstat/{topRequests,dynamics,regions}
Auth: header `Authorization: Api-Key <key>`; body REQUIRES `folderId`.

Credentials (environment variables, or an env file via --env / YANDEX_ENV_FILE / ./.env):
  YANDEX_WORDSTAT_API_KEY=...     API key of a Yandex Cloud service account
  YANDEX_WORDSTAT_FOLDER_ID=...   Yandex Cloud folder id

Usage:
  wordstat.py top "claude code" "скиллы для claude" [...]   # show + top similar requests
  wordstat.py top --region 225 "claude code"                 # 225=Russia, 213=Moscow
  wordstat.py dynamics "claude code" --from 2026-01-01 --to 2026-05-31
  wordstat.py raw top '{"phrase":"claude code","numPhrases":20}'   # debug: dump raw JSON

Gotchas (per docs): counts come as JSON strings (int64) -> cast int; PERIOD_MONTHLY toDate
must be last day of month; operators ! + [] not supported in phrase.
"""
from __future__ import annotations

import argparse
import json
import os
import ssl
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

BASE = "https://searchapi.api.cloud.yandex.net/v2/wordstat"


def load_creds(env_path: Path | None) -> tuple[str, str]:
    """Read API key + folder id from the environment, then from the optional env file."""
    vals: dict[str, str] = {}
    if env_path is not None and env_path.is_file():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            k, v = line.split("=", 1)
            vals[k.strip()] = v.strip().strip('"').strip("'")
    key = os.environ.get("YANDEX_WORDSTAT_API_KEY") or vals.get("YANDEX_WORDSTAT_API_KEY", "")
    folder = os.environ.get("YANDEX_WORDSTAT_FOLDER_ID") or vals.get("YANDEX_WORDSTAT_FOLDER_ID", "")
    if not key or not folder:
        sys.exit("YANDEX_WORDSTAT_API_KEY and YANDEX_WORDSTAT_FOLDER_ID must be set "
                 "(environment variables or an env file; see README.md)")
    return key, folder


def _ctx() -> ssl.SSLContext:
    try:
        import certifi  # noqa: PLC0415

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


def call(method: str, body: dict, key: str, folder: str) -> dict:
    """POST one Wordstat method, return parsed JSON (raises on HTTP error with body)."""
    body = {**body, "folderId": folder}
    req = urllib.request.Request(
        f"{BASE}/{method}",
        data=json.dumps(body).encode(),
        headers={"Authorization": f"Api-Key {key}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=30, context=_ctx()) as r:
            return json.loads(r.read())
    except urllib.error.HTTPError as e:
        sys.exit(f"HTTP {e.code} on {method}: {e.read().decode()[:600]}")


def _as_int(x) -> int:
    try:
        return int(x)
    except (TypeError, ValueError):
        return 0


def cmd_top(args, key, folder):
    regions = [args.region] if args.region else []
    rows = []
    for phrase in args.phrases:
        body = {"phrase": phrase, "numPhrases": args.num}
        if regions:
            body["regions"] = regions
        resp = call("topRequests", body, key, folder)
        # response shape may vary; surface count + top similar best-effort
        # API shape: {"results":[{phrase,count}, ...], "associations":[...], "totalCount":"N"}
        # results[0] is the phrase itself, the rest are similar requests.
        results = resp.get("results") or []
        total = _as_int(resp.get("totalCount") or resp.get("count") or resp.get("shows"))
        if not total and results:
            total = _as_int(results[0].get("count"))
        tops = [r for r in results if (r.get("phrase") or "").strip() != phrase.strip()]
        assoc = resp.get("associations") or []
        rows.append((phrase, total, len(tops), len(assoc), resp))
        print(f"\n=== {phrase!r}  показов/мес: {total or '?'} ===")
        for it in (tops if isinstance(tops, list) else [])[: args.show]:
            if isinstance(it, dict):
                ph = it.get("phrase") or it.get("text") or ""
                c = _as_int(it.get("count") or it.get("shows"))
                print(f"  {c:>10}  {ph}")
        for it in (assoc if isinstance(assoc, list) else [])[:5]:
            if isinstance(it, dict):
                ph = it.get("phrase") or ""
                c = _as_int(it.get("count"))
                print(f"  {c:>10}  ~ {ph}")
        time.sleep(0.2)  # ~5-10 rps limit
    print("\n--- сводка показов/мес ---")
    for phrase, total, nt, na, _ in rows:
        print(f"  {total or '?':>10}  {phrase}")
    if args.json:
        print("\nRAW:", json.dumps([r[4] for r in rows], ensure_ascii=False, indent=2))


def cmd_dynamics(args, key, folder):
    body = {
        "phrase": args.phrase,
        "period": args.period,
        "fromDate": f"{args.from_date}T00:00:00Z",
        "toDate": f"{args.to_date}T23:59:59Z",
    }
    resp = call("dynamics", body, key, folder)
    print(json.dumps(resp, ensure_ascii=False, indent=2))


def cmd_raw(args, key, folder):
    body = json.loads(args.body)
    resp = call(args.method, body, key, folder)
    print(json.dumps(resp, ensure_ascii=False, indent=2))


def main():
    ap = argparse.ArgumentParser(description="Yandex Wordstat (Cloud Search API) client")
    ap.add_argument("--env", default=os.environ.get("YANDEX_ENV_FILE", ".env"),
                    help="optional KEY=VALUE env file (default: YANDEX_ENV_FILE or ./.env)")
    sub = ap.add_subparsers(dest="cmd", required=True)

    t = sub.add_parser("top", help="topRequests for one or more phrases")
    t.add_argument("phrases", nargs="+")
    t.add_argument("--num", type=int, default=20, help="numPhrases 1-2000 (default 20)")
    t.add_argument("--region", help="region id (225=Russia, 213=Moscow)")
    t.add_argument("--show", type=int, default=15, help="how many similar to print")
    t.add_argument("--json", action="store_true")
    t.set_defaults(func=cmd_top)

    d = sub.add_parser("dynamics", help="frequency over time")
    d.add_argument("phrase")
    d.add_argument("--period", default="PERIOD_MONTHLY")
    d.add_argument("--from", dest="from_date", required=True)
    d.add_argument("--to", dest="to_date", required=True, help="last day of month for MONTHLY")
    d.set_defaults(func=cmd_dynamics)

    r = sub.add_parser("raw", help="debug: post raw JSON to a method")
    r.add_argument("method")
    r.add_argument("body")
    r.set_defaults(func=cmd_raw)

    args = ap.parse_args()
    key, folder = load_creds(Path(args.env))
    args.func(args, key, folder)


if __name__ == "__main__":
    main()
