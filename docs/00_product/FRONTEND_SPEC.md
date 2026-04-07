# Frontend Specification — Prototype-to-React Mapping

Baseline: HTML prototypes `apps/web/prototypes/00-07`.

## Route Map

| Prototype | React Route | Page Component | Key API Endpoints |
|-----------|-------------|----------------|-------------------|
| 01_home_dashboard | `/` | HomePage | GET /projects, GET /ops/cost, GET /ops/metrics |
| 02_project_setup_wizard | `/projects/new` | ProjectSetupPage | POST /projects, POST /briefs/upload, GET /drafts/methodologies |
| 03_brief_ingest_review | `/projects/:id/brief` | BriefReviewPage | POST /briefs/upload, GET /briefs/:id, PATCH /briefs/:id, POST /briefs/:id/analyze |
| 04_survey_builder | `/projects/:id/survey` | SurveyBuilderPage | GET /drafts/:id, PATCH /drafts/:id/sections, GET /drafts/:id/generation-config |
| 05_mapping_data_upload | `/projects/:id/mapping` | MappingPage | POST /tables/generate |
| 06_analysis_run_results | `/projects/:id/analysis` | AnalysisPage | POST /tables/:id/qa, POST /tables/:id/qa-copilot |
| 07_reporting_exports | `/projects/:id/report` | ReportingPage | GET /ops/cost |

## Shared Components

| Component | Source Prototype | Props |
|-----------|-----------------|-------|
| `AppShell` | 00_nav_shell | children, currentStage |
| `LeftNav` | 00_nav_shell | stages[], activeStage, projectId |
| `AssistantPanel` | All screens | contextChips[], actions[], chatHistory[] |
| `ContextChip` | All screens | label, value, variant |
| `SectionNavigator` | 03, 04 | sections[], activeId, onSelect |
| `FileDropzone` | 02, 03, 05 | accept, maxSize, onDrop |
| `CheckpointBlock` | 03, 04, 05, 07 | title, status, onApprove |
| `StatusBadge` | 01, 06 | status: draft/running/completed/failed |
| `KPICard` | 01, 07 | label, value, trend? |
| `DataTable` | 01, 05, 06 | columns[], rows[], actions? |

## Known Deltas (Prototype vs Production)

| Area | Prototype Behavior | Production Behavior |
|------|-------------------|---------------------|
| AI Assistant | Static suggestions | Real LLM calls (P12-04, deferred) |
| File upload | Visual only | Actual upload + parsing |
| Data persistence | None (HTML) | API-backed with DB |
| Auth | None shown | JWT login + RBAC |
| Error states | Not shown | Loading/error/retry UX |
| Mobile | Viewport meta only | Responsive breakpoints |
