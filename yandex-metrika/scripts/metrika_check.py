#!/usr/bin/env python3
"""Verify Yandex Metrika access + list counters and their goals (Management API).

Run this first if a report errors, or to find goal IDs (needed for
ym:s:goal<ID>reaches metrics in reports).
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _metrika import load_token, request  # noqa: E402


def main() -> None:
    token = load_token()
    d = request("GET", "/management/v1/counters", token,
                params={"per_page": "1000"})
    counters = d.get("counters", [])
    print(f"counters={len(counters)}")
    for c in counters:
        cid = c.get("id")
        print(f"\nCOUNTER {cid}  name={c.get('name')}  site={c.get('site')}  status={c.get('status')}")
        g = request("GET", f"/management/v1/counter/{cid}/goals", token)
        goals = g.get("goals", [])
        if not goals:
            print("  goals: (нет)")
        for goal in goals:
            print(f"  goal id={goal.get('id')}  name={goal.get('name')}  "
                  f"type={goal.get('type')}")


if __name__ == "__main__":
    main()
