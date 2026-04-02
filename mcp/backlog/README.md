# Backlog Usage

Use `mvp_master_plan.json` as the single source of truth.

## Seed into MCP coordinator

From `mcp_sprint_coordinator`:

```cmd
python scripts\seed_backlog.py --input "..\quant-platform-mvp\mcp\backlog\mvp_master_plan.json"
```

## Start work

1. Claude worker claims next item:

```cmd
python scripts\claude_worker.py next --claim
```

2. Claude submits implementation and requests review:

```cmd
python scripts\claude_worker.py submit --item-id <ITEM_ID> --branch-name <BRANCH> --commit-sha <SHA> --summary "<SUMMARY>" --changed-files <FILES...> --test-results "<TEST_OUTPUT>" --request-review
```

3. Reviewer checks queue and posts feedback:

```cmd
python scripts\review_manager.py pending
python scripts\review_manager.py feedback --review-id <REVIEW_ID> --decision changes_requested --summary "<SUMMARY>" --findings-file "..\quant-platform-mvp\mcp\review_templates\blocker_findings.example.json"
```

4. Claude resolves review:

```cmd
python scripts\claude_worker.py resolve --review-id <REVIEW_ID> --new-revision-id <REVISION_ID> --note "<RESOLUTION_NOTE>"
```

5. Reviewer approves and marks done:

```cmd
python scripts\review_manager.py feedback --review-id <REVIEW_ID> --decision approved --summary "Approved" --findings-file "..\quant-platform-mvp\mcp\review_templates\approval_findings.example.json"
python scripts\review_manager.py done --item-id <ITEM_ID> --review-id <REVIEW_ID>
```
