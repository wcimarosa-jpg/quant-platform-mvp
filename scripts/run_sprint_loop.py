#!/usr/bin/env python3
"""One-command local sprint runner.

Checks MCP health, shows sprint status, and optionally claims the next item.

Usage:
    python scripts/run_sprint_loop.py              # status only
    python scripts/run_sprint_loop.py --claim      # claim next todo item
    python scripts/run_sprint_loop.py --full       # claim + submit placeholder + request review
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.mcp_client import MCPClient, MCPError


def main() -> int:
    parser = argparse.ArgumentParser(description="Sprint loop runner")
    parser.add_argument("--claim", action="store_true", help="Claim the next todo item")
    args = parser.parse_args()

    client = MCPClient()

    # 1. Health check
    print("=" * 50)
    print("MCP Sprint Runner")
    print("=" * 50)
    try:
        h = client.health()
        print(f"  Server: {h.get('service', 'unknown')} v{h.get('version', '?')} — OK")
    except MCPError as exc:
        print(f"  Server: UNREACHABLE — {exc}")
        print("\n  Start the MCP server first:")
        print("    cd ../mcp_sprint_coordinator")
        print("    .venv/Scripts/uvicorn sprint_coordinator.server:app --reload --app-dir src --port 8765")
        return 1

    # 2. Sprint status
    print()
    try:
        s = client.status_summary()
        done = s["by_status"].get("done", 0)
        total = s["total"]
        print(f"  Progress: {done}/{total} items done")
        for status, count in sorted(s["by_status"].items()):
            print(f"    {status}: {count}")
        if s["next_item"]:
            nxt = s["next_item"]
            print(f"\n  Next item: {nxt['id']} — {nxt.get('title', '')}")
        else:
            print("\n  All items complete!")
            return 0
    except MCPError as exc:
        print(f"  Status error: {exc}")
        return 1

    # 3. Optionally claim
    if args.claim and s["next_item"]:
        item_id = s["next_item"]["id"]
        print(f"\n  Claiming {item_id}...")
        try:
            result = client.claim_item(item_id)
            print(f"  Claimed: {result.get('result', {}).get('item_id', item_id)} — in_progress")
        except MCPError as exc:
            print(f"  Claim failed: {exc}")
            return 1

    print()
    print("Commands:")
    print("  python scripts/claude_worker.py claim <ITEM_ID>")
    print("  python scripts/claude_worker.py submit <ITEM_ID> --summary '...' --request-review")
    print("  python scripts/review_manager.py pending")
    print("  python scripts/review_manager.py approve --review-id N --summary '...'")
    print("  python scripts/review_manager.py done --item-id <ID> --review-id N")
    print("=" * 50)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
