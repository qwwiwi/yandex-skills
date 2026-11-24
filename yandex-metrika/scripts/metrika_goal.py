#!/usr/bin/env python3
"""Create a goal in a Yandex Metrika counter (Management API, needs metrika:write).

Two goal types are wired:
  url    – visitor reaches a page path. --match exact|contain|start|regexp
  action – a JS event fired via ym(id,'reachGoal','<event_id>'). --url = event id

Examples:
    # URL goal: signup thank-you page
    python metrika_goal.py --counter 12345678 --name "Signup" \
        --type url --match contain --url /thank-you --price 4990

    # Action goal: CTA click event fired via ym(<id>, 'reachGoal', 'cta_click')
    python metrika_goal.py --counter 12345678 --name "CTA click" \
        --type action --url cta_click

The counter defaults to METRIKA_COUNTER_ID (must be a single id here).

DRY-RUN by default – prints the payload and does NOT create. Add --commit to actually POST.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from _metrika import counters_for, load_token, request  # noqa: E402


def build_goal(args) -> dict:
    goal: dict = {"name": args.name, "type": args.type}
    if args.price is not None:
        goal["default_price"] = args.price
    if args.favorite:
        goal["is_favorite"] = True
    if args.type == "url":
        goal["conditions"] = [{"type": args.match, "url": args.url}]
    elif args.type == "action":
        # JS reachGoal event goal: condition type is "exact" (NOT "action"),
        # url = the reachGoal event id. The API answers 400 on "action".
        goal["conditions"] = [{"type": "exact", "url": args.url}]
    else:
        raise SystemExit("Only --type url|action are wired in this script.")
    return {"goal": goal}


def main() -> None:
    p = argparse.ArgumentParser(description="Create a Metrika goal.")
    p.add_argument("--counter", default=None,
                   help="single counter id; default: METRIKA_COUNTER_ID")
    p.add_argument("--name", required=True)
    p.add_argument("--type", required=True, choices=["url", "action"])
    p.add_argument("--url", required=True,
                   help="url: page path pattern; action: JS reachGoal event id")
    p.add_argument("--match", default="contain",
                   choices=["exact", "contain", "start", "regexp"],
                   help="for --type url only")
    p.add_argument("--price", type=float, default=None, help="goal value in counter currency")
    p.add_argument("--favorite", action="store_true")
    p.add_argument("--commit", action="store_true", help="actually create (default: dry-run)")
    args = p.parse_args()

    cid = counters_for(args.counter)
    if "," in cid:
        raise SystemExit("metrika_goal.py works with exactly one counter id.")
    body = build_goal(args)
    print(f"counter={cid}")
    print("payload:", json.dumps(body, ensure_ascii=False))
    if not args.commit:
        print("\nDRY-RUN – добавьте --commit, чтобы реально создать цель.")
        return
    d = request("POST", f"/management/v1/counter/{cid}/goals", load_token(), body=body)
    g = d.get("goal", {})
    print(f"\nCREATED goal id={g.get('id')} name={g.get('name')} type={g.get('type')}")


if __name__ == "__main__":
    main()
