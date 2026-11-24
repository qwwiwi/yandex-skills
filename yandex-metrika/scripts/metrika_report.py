#!/usr/bin/env python3
"""Pull a Yandex Metrika report (Stat/Reporting API) via the OAuth token.

Agent-native, no UI. The counter comes from --counter or METRIKA_COUNTER_ID.

Examples:
    # Last 7 days, counter from METRIKA_COUNTER_ID, default metrics
    python metrika_report.py

    # Traffic sources for one counter, last 30 days
    # NOTE: use --sort=-... (equals form) when sorting desc – the leading '-'
    # otherwise looks like a flag to argparse.
    python metrika_report.py --counter 12345678 --dimensions ym:s:trafficSource \
        --metrics ym:s:visits,ym:s:bounceRate --date1 30daysAgo --sort=-ym:s:visits

    # UTM campaigns
    python metrika_report.py --dimensions ym:s:UTMCampaign,ym:s:UTMSource \
        --metrics ym:s:visits --sort=-ym:s:visits --limit 50

    # Daily dynamics, JSON out
    python metrika_report.py --dimensions ym:s:date --metrics ym:s:visits,ym:s:users --json
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _metrika import counters_for, load_token, request  # noqa: E402


def render(d: dict) -> None:
    q = d.get("query", {})
    dims = q.get("dimensions", [])
    mets = q.get("metrics", [])
    rows = d.get("data", [])
    if d.get("sampled"):
        print(f"[sampled: share={d.get('sample_share')}] ", end="")
    print(f"total_rows={d.get('total_rows', len(rows))}")
    if not rows:
        print("(нет данных – вероятно, счётчик ещё не собирает визиты или нет трафика за период)")
        return
    headers = [x.split(":")[-1] for x in dims] + [x.split(":")[-1] for x in mets]
    table = [headers]
    for row in rows:
        dvals = [ (v.get("name") or "-") for v in row.get("dimensions", []) ]
        mvals = [ _fmt(v) for v in row.get("metrics", []) ]
        table.append(dvals + mvals)
    widths = [max(len(str(r[i])) for r in table) for i in range(len(headers))]
    for i, r in enumerate(table):
        print("  ".join(str(c).ljust(widths[j]) for j, c in enumerate(r)))
        if i == 0:
            print("  ".join("-" * w for w in widths))
    tot = d.get("totals")
    if tot:
        print("TOTALS:", "  ".join(_fmt(x) for x in tot))


def _fmt(x) -> str:
    if isinstance(x, float):
        return f"{x:.2f}".rstrip("0").rstrip(".")
    return str(x)


def main() -> None:
    p = argparse.ArgumentParser(description="Yandex Metrika report (Stat API).")
    p.add_argument("--counter", default=None,
                   help="counter id (or several, comma-separated); default: METRIKA_COUNTER_ID")
    p.add_argument("--metrics", default="ym:s:visits,ym:s:users,ym:s:pageviews,ym:s:bounceRate")
    p.add_argument("--dimensions", default="")
    p.add_argument("--date1", default="7daysAgo")
    p.add_argument("--date2", default="today")
    p.add_argument("--filters", default="")
    p.add_argument("--sort", default="")
    p.add_argument("--limit", default="100")
    p.add_argument("--accuracy", default="full")
    p.add_argument("--json", action="store_true")
    args = p.parse_args()

    params = {
        "ids": counters_for(args.counter),
        "metrics": args.metrics,
        "date1": args.date1,
        "date2": args.date2,
        "limit": args.limit,
        "accuracy": args.accuracy,
    }
    if args.dimensions:
        params["dimensions"] = args.dimensions
    if args.filters:
        params["filters"] = args.filters
    if args.sort:
        params["sort"] = args.sort

    d = request("GET", "/stat/v1/data", load_token(), params=params)
    if args.json:
        print(json.dumps(d, ensure_ascii=False, indent=2))
    else:
        render(d)


if __name__ == "__main__":
    main()
