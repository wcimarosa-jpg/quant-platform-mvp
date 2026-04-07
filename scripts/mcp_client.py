"""Lightweight MCP sprint coordinator client.

Self-contained HTTP client for the local MCP server — no dependency on
the mcp_sprint_coordinator repo. Reads tokens from .env or environment.

Usage from other scripts:
    from scripts.mcp_client import MCPClient
    client = MCPClient()
    client.health()
    client.call_tool("sprint.claim_item", {...})
"""

from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any


def _load_dotenv() -> None:
    """Minimal .env loader — no dependency on python-dotenv."""
    env_path = Path(__file__).resolve().parents[1] / ".env"
    if not env_path.is_file():
        return
    for line in env_path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.strip())


_load_dotenv()

MCP_BASE_URL = os.environ.get("MCP_BASE_URL", "http://127.0.0.1:8765")
MCP_WORKER_TOKEN = os.environ.get("MCP_WORKER_TOKEN", "replace_me_claude_token")
MCP_REVIEW_TOKEN = os.environ.get("MCP_REVIEW_TOKEN", "replace_me_reviewer_token")


class MCPError(RuntimeError):
    """Raised on MCP API failures."""


class MCPClient:
    """HTTP client for the local MCP sprint coordinator."""

    def __init__(
        self,
        base_url: str = MCP_BASE_URL,
        worker_token: str = MCP_WORKER_TOKEN,
        review_token: str = MCP_REVIEW_TOKEN,
    ) -> None:
        self.base_url = base_url.rstrip("/")
        self.worker_token = worker_token
        self.review_token = review_token

    # -- low-level --------------------------------------------------------

    def _request(self, method: str, url: str, token: str, body: dict | None = None) -> dict:
        data = None
        headers = {"Authorization": f"Bearer {token}"}
        if body is not None:
            data = json.dumps(body).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url=url, method=method, data=data, headers=headers)
        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                payload = resp.read().decode("utf-8")
                return json.loads(payload) if payload else {}
        except urllib.error.HTTPError as exc:
            try:
                detail = exc.read().decode("utf-8")
            except Exception:
                detail = str(exc)
            raise MCPError(f"HTTP {exc.code}: {detail}") from exc
        except urllib.error.URLError as exc:
            raise MCPError(f"Connection error: {exc}") from exc

    def call_tool(self, tool_name: str, tool_input: dict, *, role: str = "worker") -> dict:
        token = self.worker_token if role == "worker" else self.review_token
        url = f"{self.base_url}/api/v1/tools/{tool_name}"
        return self._request("POST", url, token, body={"input": tool_input})

    # -- health -----------------------------------------------------------

    def health(self) -> dict:
        url = f"{self.base_url}/health"
        req = urllib.request.Request(url)
        with urllib.request.urlopen(req, timeout=5) as resp:
            return json.loads(resp.read().decode("utf-8"))

    # -- worker actions ---------------------------------------------------

    def claim_item(self, item_id: str, branch: str = "") -> dict:
        branch = branch or f"feat/{item_id.lower()}"
        return self.call_tool("sprint.claim_item", {
            "item_id": item_id,
            "assignee": "claude_worker",
            "branch_name": branch,
        })

    def submit_artifact(
        self,
        item_id: str,
        summary: str,
        files_changed: list[str] | None = None,
        branch: str = "",
        commit_sha: str = "HEAD",
    ) -> dict:
        branch = branch or f"feat/{item_id.lower()}"
        return self.call_tool("artifact.submit_diff", {
            "item_id": item_id,
            "assignee": "claude_worker",
            "branch_name": branch,
            "commit_sha": commit_sha,
            "summary": summary,
            "diff_summary": summary,
            "files_changed": files_changed or [],
        })

    def request_review(self, item_id: str, revision_id: int) -> dict:
        return self.call_tool("review.request", {
            "item_id": item_id,
            "revision_id": revision_id,
            "requested_by": "claude_worker",
            "summary": "Ready for review.",
        })

    def resolve_review(self, review_id: int, new_revision_id: int, note: str = "") -> dict:
        return self.call_tool("review.resolve", {
            "review_id": review_id,
            "resolver": "claude_worker",
            "resolution_note": note or "Fixes applied.",
            "new_revision_id": new_revision_id,
        })

    # -- reviewer actions -------------------------------------------------

    def get_pending_reviews(self, limit: int = 50) -> dict:
        return self.call_tool("review.get_pending", {
            "assignee": "review_manager",
            "limit": limit,
        }, role="reviewer")

    def post_feedback(
        self,
        review_id: int,
        decision: str,
        summary: str,
        findings: list[dict] | None = None,
    ) -> dict:
        return self.call_tool("review.post_feedback", {
            "review_id": review_id,
            "reviewer": "codex_reviewer",
            "decision": decision,
            "summary": summary,
            "findings": findings or [],
        }, role="reviewer")

    def mark_done(self, item_id: str, review_id: int, summary: str = "") -> dict:
        return self.call_tool("sprint.mark_done", {
            "item_id": item_id,
            "review_id": review_id,
            "by": "claude_worker",
            "summary": summary or "Done.",
        }, role="reviewer")

    # -- query ------------------------------------------------------------

    def list_items(self, status: str | None = None) -> list[dict]:
        params: dict[str, str] = {"limit": "50"}
        if status:
            params["status"] = status
        qs = urllib.parse.urlencode(params)
        url = f"{self.base_url}/api/v1/sprint/items?{qs}"
        resp = self._request("GET", url, self.review_token)
        return resp if isinstance(resp, list) else resp.get("items", [])

    def status_summary(self) -> dict[str, Any]:
        """Return a compact sprint status summary."""
        items = self.list_items()
        by_status: dict[str, int] = {}
        for item in items:
            s = item.get("status", "unknown")
            by_status[s] = by_status.get(s, 0) + 1
        todo = [i for i in items if i.get("status") == "todo"]
        next_item = todo[0] if todo else None
        return {
            "total": len(items),
            "by_status": by_status,
            "next_item": next_item,
        }
