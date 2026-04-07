#!/usr/bin/env python3
"""Review manager CLI — pending reviews, feedback, mark done.

Usage:
    python scripts/review_manager.py pending
    python scripts/review_manager.py approve --review-id 55 --summary "All good"
    python scripts/review_manager.py reject --review-id 55 --summary "Needs fixes"
    python scripts/review_manager.py done --item-id P10-08 --review-id 55
    python scripts/review_manager.py items
    python scripts/review_manager.py items --status todo
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.mcp_client import MCPClient, MCPError


def _pp(obj: dict | list) -> None:
    print(json.dumps(obj, indent=2))


def cmd_pending(client: MCPClient, args: argparse.Namespace) -> int:
    result = client.get_pending_reviews(limit=args.limit)
    reviews = result.get("result", {}).get("reviews", [])
    if not reviews:
        print("No pending reviews.")
        return 0
    for r in reviews:
        print(f"  review={r['id']}  item={r['item_id']}  rev={r['revision_id']}  {(r.get('summary') or '')[:60]}")
    return 0


def cmd_approve(client: MCPClient, args: argparse.Namespace) -> int:
    result = client.post_feedback(args.review_id, "approved", args.summary)
    _pp(result)
    return 0


def cmd_reject(client: MCPClient, args: argparse.Namespace) -> int:
    result = client.post_feedback(args.review_id, "changes_requested", args.summary)
    _pp(result)
    return 0


def cmd_done(client: MCPClient, args: argparse.Namespace) -> int:
    result = client.mark_done(args.item_id, args.review_id, args.summary)
    _pp(result)
    return 0


def cmd_items(client: MCPClient, args: argparse.Namespace) -> int:
    items = client.list_items(status=args.status)
    if not items:
        print("No items.")
        return 0
    for item in items:
        print(f"  {item['id']}: {item['status']:15s} {item.get('title', '')[:60]}")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Review manager CLI for MCP sprint coordinator")
    sub = parser.add_subparsers(dest="command", required=True)

    p_pending = sub.add_parser("pending", help="List pending reviews")
    p_pending.add_argument("--limit", type=int, default=50)

    p_approve = sub.add_parser("approve", help="Approve a review")
    p_approve.add_argument("--review-id", required=True, type=int)
    p_approve.add_argument("--summary", required=True)

    p_reject = sub.add_parser("reject", help="Request changes on a review")
    p_reject.add_argument("--review-id", required=True, type=int)
    p_reject.add_argument("--summary", required=True)

    p_done = sub.add_parser("done", help="Mark item as done")
    p_done.add_argument("--item-id", required=True)
    p_done.add_argument("--review-id", required=True, type=int)
    p_done.add_argument("--summary", default="Done.")

    p_items = sub.add_parser("items", help="List sprint items")
    p_items.add_argument("--status", default=None)

    args = parser.parse_args()
    client = MCPClient()
    dispatch = {
        "pending": cmd_pending, "approve": cmd_approve, "reject": cmd_reject,
        "done": cmd_done, "items": cmd_items,
    }
    try:
        return dispatch[args.command](client, args)
    except MCPError as exc:
        print(f"MCP error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
