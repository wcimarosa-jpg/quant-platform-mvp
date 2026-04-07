# Sprint Command Reference

All MCP sprint operations use local Python scripts — no ad-hoc curl needed.

## Prerequisites

1. MCP server running on localhost:8765
2. `.env` file with `MCP_BASE_URL`, `MCP_WORKER_TOKEN`, `MCP_REVIEW_TOKEN`

## One-Command Runner

```bash
python scripts/run_sprint_loop.py          # status only
python scripts/run_sprint_loop.py --claim  # claim next todo item
# PowerShell:
.\scripts\run_sprint_loop.ps1
.\scripts\run_sprint_loop.ps1 -claim
```

## Worker Commands (`claude_worker.py`)

| Command | Description |
|---------|-------------|
| `python scripts/claude_worker.py health` | Check MCP server health |
| `python scripts/claude_worker.py status` | Print sprint progress summary |
| `python scripts/claude_worker.py next` | Show next todo item |
| `python scripts/claude_worker.py claim P10-08` | Claim a specific item |
| `python scripts/claude_worker.py submit P10-08 --summary "Done" --request-review` | Submit artifact + request review |
| `python scripts/claude_worker.py review P10-08 --revision-id 55` | Request review for a revision |
| `python scripts/claude_worker.py resolve --review-id 55 --new-revision-id 56` | Resolve review with fixes |

## Reviewer Commands (`review_manager.py`)

| Command | Description |
|---------|-------------|
| `python scripts/review_manager.py pending` | List pending reviews |
| `python scripts/review_manager.py approve --review-id 55 --summary "LGTM"` | Approve a review |
| `python scripts/review_manager.py reject --review-id 55 --summary "Needs fixes"` | Request changes |
| `python scripts/review_manager.py done --item-id P10-08 --review-id 55` | Mark item done |
| `python scripts/review_manager.py items` | List all sprint items |
| `python scripts/review_manager.py items --status todo` | Filter by status |

## Typical Sprint Workflow

```bash
# 1. Check status and claim next item
python scripts/claude_worker.py status
python scripts/claude_worker.py claim P10-08

# 2. Implement the feature...

# 3. Submit and request review
python scripts/claude_worker.py submit P10-08 \
    --summary "Implemented feature X" \
    --files pkg/foo.py tests/test_foo.py \
    --request-review

# 4. After Codex review — approve and close
python scripts/review_manager.py approve --review-id 55 --summary "All findings fixed"
python scripts/review_manager.py done --item-id P10-08 --review-id 55
```

## Recommended Allowlist Prefixes

For automated/CI environments, allowlist these command prefixes to minimize
interactive approval prompts. All commands are **local-only** (localhost:8765):

```
python scripts/claude_worker.py
python scripts/review_manager.py
python scripts/run_sprint_loop.py
```

Optional (for manual debugging):
```
curl -s -X POST http://localhost:8765/api/v1/tools/
curl -s http://localhost:8765/health
```

### Safety Properties

- All commands target `localhost:8765` only — no external network calls
- Tokens are read from `.env` at runtime — never hardcoded
- No destructive operations (no `rm`, `git reset --hard`, `git push --force`)
- Read-only commands (`health`, `status`, `next`, `pending`, `items`) have no side effects
- Write commands (`claim`, `submit`, `approve`, `done`) are idempotent or guarded
