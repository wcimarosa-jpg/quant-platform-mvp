# Demo Walkthrough — Quant Platform MVP

End-to-end smoke-tested demo path. Verified against `docker compose` on 2026-04-08.

## Prerequisites

- Docker Desktop installed and running (engine status: green)
- Git clone of this repo
- About 3 GB free disk for the first build (Python + Node base images, scientific Python wheels)

## One-time setup

```bash
cp .env.example .env
docker compose build         # ~5 minutes the first time, ~30 seconds on subsequent runs
docker compose up -d         # starts api (port 8010) and frontend (port 8510)
docker compose exec api python scripts/seed_users.py
```

You should see:
- `Container quant-platform-mvp-api-1 ... Healthy`
- `Created: admin@egg.local (admin)`
- `Created: researcher@egg.local (researcher)`
- `Created: reviewer@egg.local (reviewer)`

## Verify the stack is up

```bash
curl http://localhost:8010/health           # backend direct
# {"ok":true,"service":"quant-platform-api","version":"0.1.0"}

curl http://localhost:8510/health           # via nginx proxy
# Same response

docker compose ps                            # both containers should be "Up"
```

## Demo script (researcher walkthrough)

**Browser:** open http://localhost:8510

### 1. Login (~30 seconds)
- You'll be redirected to `/login`
- Email: `researcher@egg.local`
- Password: `password`
- Click Sign In → land on Home page

### 2. Create a project (~1 minute)
- Click `+ Create Project` (top-right of Home)
- Name: "Q4 Brand Health Study" (or similar)
- Methodology: Segmentation
- *(Optional)* Drag a SOW file (`.docx`, `.pdf`, or `.md`) into the SOW dropzone
- Click "Create Project & Continue"

### 3. Brief review (~3 minutes)
- If you didn't drop a file in step 2, drag a research brief into the dropzone now
- The parser extracts what it can; missing fields show with red badges
- Click any field tab (Objectives / Audience / Category / Geography / Constraints) to edit
- Click **Save** after each edit
- Click **Run Analyzer** to see suggested assumptions for missing fields
- The checkpoint at the bottom turns green ("Ready") once `is_complete` OR all assumptions are resolved
- Click the green checkpoint to continue

### 4. Survey builder (~2 minutes)
- Methodology dropdown is pre-populated from the API (matches your project's methodology)
- Click "Create Draft" — the backend returns a pre-selected list of sections for your methodology
- Toggle sections on/off by clicking them (required sections are locked)
- Click the green checkpoint to continue

### 5. Data mapping (~3 minutes)
- Drag `data/demo_survey.csv` (500 rows, mixed numeric/text) into the dropzone
- The Data Profile card shows: 500 rows, 8 columns, 6 tabulatable, 2 skipped (text or empty)
- The Column Profile table shows each column's kind:
  - `Q1_brand_aware`, `Q2_satisfaction`, `Q3_nps`, `gender`, `segment` → categorical
  - `age` → continuous
  - `ResponseId`, `open_end` → text (skipped)
- Click "Generate Tables (6 cols)"
- Wait ~2 seconds → green checkpoint with the run_id appears
- Click the checkpoint to continue (run_id is passed via query param)

### 6. Analysis (~1 minute)
- The page reads `?run_id=tblrun-XXXXXXXX` from the URL
- Click "Run QA Checks"
- QA report shows: "PASSED, 0 errors, 0 warnings, 12 tables"
- Click the green checkpoint to continue

### 7. Reporting (~1 minute)
- Strategic summary draft is shown (placeholder text — real LLM-generated summary requires P12-04)
- Cost cards show $0.00 (real LLM cost tracking requires P12-04)
- Export buttons are stubbed (P12-04)
- Click around to verify nothing crashes

**Total walkthrough time: ~10 minutes**

## Stop / clean up

```bash
docker compose down            # stop containers (preserves the db-data volume)
docker compose down -v         # also delete the persisted database
```

## Known limitations (transparent to demo audience)

| Area | Limitation | Why |
|---|---|---|
| LLM features | All assistant responses are stubbed | P12-04 (Anthropic SDK integration) deferred |
| Cost tracking | `/ops/cost` shows $0.00 / 0 tokens | No LLM calls happen yet |
| SLO dashboard | All actuals show 0.0 | No FastAPI middleware records `record_request()` yet |
| Brief / draft / table persistence | **Wiped on container restart** | These stores are in-memory; P12-03 will migrate to DB |
| Project persistence | Survives container restart ✓ | DB-backed via SQLAlchemy + named volume |
| Brief parser quality | Only extracts loose fragments from a clean markdown brief | Heuristic regex parser, not LLM-powered |
| Export functionality | DOCX / Excel / CSV export buttons disabled | P12-04 (depends on LLM for narrative content) |
| User management UI | None | Use `seed_users.py` to add accounts |

## Troubleshooting

**`docker compose up` complains `env file .env not found`**
→ Run `cp .env.example .env` first.

**Build hangs at `pip install --no-cache-dir .` for ~5 minutes**
→ Normal. scipy and scikit-learn compile native wheels on first build. Subsequent builds are fast (cached).

**Login returns 401**
→ Run `docker compose exec api python scripts/seed_users.py` to seed default accounts.

**Brief disappeared after `docker compose restart api`**
→ Expected. Briefs are in-memory until P12-03. Re-upload to continue.

**Frontend shows blank page**
→ Hard-refresh (Ctrl+Shift+R). Check browser console — likely a stale service worker or cached bundle from a previous Vite dev server.

**Port 8510 or 8010 already in use**
→ Edit `.env` to override `WEB_PORT` and `API_PORT`, then `docker compose down && docker compose up -d`.

## Sample CSV included

`data/demo_survey.csv` is a 500-row synthetic survey with these column kinds:

| Column | Kind | Notes |
|---|---|---|
| `ResponseId` | text | Leading-zero IDs (`R_0001`), skipped by profiler |
| `Q1_brand_aware` | categorical (binary) | 0/1 |
| `Q2_satisfaction` | categorical (Likert 5) | 1–5 |
| `Q3_nps` | categorical (NPS 11) | 0–10 |
| `age` | continuous | 18–75, ~58 unique values |
| `gender` | categorical (binary) | 1/2 |
| `segment` | categorical (4-way) | 1–4 |
| `open_end` | text | Embedded commas, escaped `""` quotes, multi-line responses, BOM in header |

This file deliberately stress-tests the RFC 4180 parser and the column profiler. It is the smoke test's gold standard input.
