#!/usr/bin/env python3
"""Claude worker CLI — claim items, submit artifacts, request reviews.

Usage:
    python scripts/claude_worker.py health
    python scripts/claude_worker.py status
    python scripts/claude_worker.py next
    python scripts/claude_worker.py claim P10-08
    python scripts/claude_worker.py submit P10-08 --summary "Implemented feature"
    python scripts/claude_worker.py review P10-08 --revision-id 55
    python scripts/claude_worker.py resolve --review-id 55 --new-revision-id 56
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


def cmd_health(client: MCPClient, args: argparse.Namespace) -> int:
    _pp(client.health())
    return 0


def cmd_status(client: MCPClient, args: argparse.Namespace) -> int:
    s = client.status_summary()
    print(f"Sprint: {s['by_status'].get('done', 0)}/{s['total']} done")
    for status, count in sorted(s["by_status"].items()):
        print(f"  {status}: {count}")
    if s["next_item"]:
        print(f"  Next: {s['next_item']['id']} — {s['next_item'].get('title', '')}")
    return 0


def cmd_next(client: MCPClient, args: argparse.Namespace) -> int:
    s = client.status_summary()
    if s["next_item"]:
        _pp(s["next_item"])
    else:
        print("No todo items remaining.")
    return 0


def cmd_claim(client: MCPClient, args: argparse.Namespace) -> int:
    result = client.claim_item(args.item_id, args.branch)
    _pp(result)
    return 0


def cmd_submit(client: MCPClient, args: argparse.Namespace) -> int:
    result = client.submit_artifact(
        args.item_id, args.summary,
        files_changed=args.files,
        branch=args.branch,
    )
    _pp(result)
    rev_id = result.get("result", {}).get("revision_id")
    if args.request_review and rev_id:
        review = client.request_review(args.item_id, rev_id)
        _pp(review)
    return 0


def cmd_review(client: MCPClient, args: argparse.Namespace) -> int:
    result = client.request_review(args.item_id, args.revision_id)
    _pp(result)
    return 0


def cmd_resolve(client: MCPClient, args: argparse.Namespace) -> int:
    result = client.resolve_review(args.review_id, args.new_revision_id, args.note)
    _pp(result)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Claude worker CLI for MCP sprint coordinator")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("health", help="Check MCP server health")
    sub.add_parser("status", help="Print sprint status summary")
    sub.add_parser("next", help="Show next todo item")

    p_claim = sub.add_parser("claim", help="Claim a sprint item")
    p_claim.add_argument("item_id")
    p_claim.add_argument("--branch", default="")

    p_submit = sub.add_parser("submit", help="Submit artifact for review")
    p_submit.add_argument("item_id")
    p_submit.add_argument("--summary", required=True)
    p_submit.add_argument("--files", nargs="*", default=[])
    p_submit.add_argument("--branch", default="")
    p_submit.add_argument("--request-review", action="store_true")

    p_review = sub.add_parser("review", help="Request review for an item")
    p_review.add_argument("item_id")
    p_review.add_argument("--revision-id", required=True, type=int)

    p_resolve = sub.add_parser("resolve", help="Resolve review with new revision")
    p_resolve.add_argument("--review-id", required=True, type=int)
    p_resolve.add_argument("--new-revision-id", required=True, type=int)
    p_resolve.add_argument("--note", default="Fixes applied.")

    args = parser.parse_args()
    client = MCPClient()
    dispatch = {
        "health": cmd_health, "status": cmd_status, "next": cmd_next,
        "claim": cmd_claim, "submit": cmd_submit, "review": cmd_review,
        "resolve": cmd_resolve,
    }
    try:
        return dispatch[args.command](client, args)
    except MCPError as exc:
        print(f"MCP error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
