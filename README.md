# Quant Platform MVP

Greenfield codebase for survey generation and quantitative analysis.

## Scope

- AI-assisted questionnaire generation by methodology
- In-app questionnaire review/editing
- Export to DOCX and Decipher-ready structured output
- Raw data upload and editable questionnaire/data mapping
- Table generation and advanced quant analysis (including MaxDiff and TURF)
- Project-based folder isolation for client data separation

## Structure

- `docs/`: product, methodology, architecture, and decision records
- `apps/`: API and web app surfaces
- `packages/`: reusable domain logic
- `services/`: background job workers
- `mcp/`: sprint coordination and backlog payloads
- `legacy_reference/`: imported legacy docs for reuse

## How We Work

1. Pull a ticket from `mcp/backlog/sprint_01.json`.
2. Claude implements the ticket.
3. Review manager runs MCP review loop.
4. Only approved items are marked done.
