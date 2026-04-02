# System Design (Draft)

Architecture target:

- `apps/api`: orchestration + endpoints
- `apps/web`: UI
- `packages/*`: reusable business logic
- `services/worker`: background analysis runs
- `projects/`: isolated per-project data roots

All analysis runs persist provenance: input file version, mapping version, questionnaire version, timestamp, and user.
