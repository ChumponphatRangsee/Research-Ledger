# Research Ledger

Research Ledger is an AI-assisted investment research workspace combining sector-aware quantitative screening, multi-agent AI analysis, human review, and paper-portfolio thesis tracking.

Research Ledger is not a financial data terminal, autonomous trading bot, or brokerage execution system. Its intended flow is:

```text
Discover -> Quantitative Screen -> AI Research -> Human Review
         -> Paper Portfolio -> Thesis Tracking -> Re-evaluation
```

## Architecture

```text
+--------------------------------------------------------------------------+
|                    Research Ledger Monorepo                              |
+------------------------------+-------------------------------------------+
| frontend/ (Next.js 15)       | backend/ (FastAPI)                        |
| - Dashboard (Tremor)         | - REST API                                 |
| - Analysis Inbox             | - LangGraph agent pipeline                 |
| - Portfolio view             | - Celery workers + beat scheduler          |
| - Supabase Auth client       | - sector-aware screener                    |
+------------------------------+-------------------------------------------+
| supabase/ - PostgreSQL schema, RLS policies, and ownership migrations     |
+--------------------------------------------------------------------------+
| docker-compose - Postgres, Redis, FastAPI, Celery, Next.js                |
+--------------------------------------------------------------------------+
```

### Data Flow

1. **Celery Beat** is currently disabled for unowned global screening; authenticated users can trigger screening through the API/UI.
2. **Screener** fetches market data through the current yfinance-backed service, classifies each ticker by sector/business model, applies strategy-specific quantitative rules, and produces score, confidence, explanations, and warnings.
3. Top-ranked passing candidates are sent to **LangGraph**, which currently runs a prototype pipeline:
   - Researcher -> Financial Analyst -> Valuator -> Decision Maker
4. Results land in **analysis_inbox** with `status = pending_review` as the human review breakpoint.
5. User reviews on the **Inbox** page and can approve or discard the analysis.
6. Approved items can create a user-owned **paper holding** in the portfolio. The legacy backend route name uses `execute`, but this is not broker execution or a live trade.

## Portfolio Migration Contract

[ADR 0001](docs/adr/0001-supabase-portfolio-migration-contract.md) establishes Supabase Postgres as the target source of truth for portfolio data. The target ledger uses THB as its base currency, weighted-average cost by account and asset, and a universal asset model covering stocks, crypto, and later asset classes.

Transactions follow Draft -> Human review -> Confirm. Confirmed transactions are immutable, and the source draft becomes audit-stable once referenced; mistakes are handled with linked reversal or correcting transactions. Every exposed user-owned database object requires both owner-scoped RLS and explicit least-privilege grants.

Google Sheets remains writable during migration and dual-run. It becomes a read-only archive only after the contract's reconciliation, idempotency, calculation, and security gates pass. Portfolio Migration precedes Screener Expansion in the [roadmap](ROADMAP.md).

PR 2 adds strict staging for the current 15-tab Google Sheets workbook. The
importer preserves entered and effective cell evidence, normalizes rows into
owner-scoped drafts, isolates errors, deduplicates source fingerprints, and
produces a reconciliation report. It never creates confirmed transactions.
The current `portfolios` paper-holding implementation remains unchanged.

## Quick Start

### 1. Environment

```bash
cp .env.example .env
# Fill in Supabase keys and AI provider API keys
```

### 2. Docker (full stack)

```bash
docker compose up --build
```

| Service | URL |
| --- | --- |
| Frontend | http://localhost:3000 |
| Backend API | http://localhost:8000 |
| API docs | http://localhost:8000/docs |
| PostgreSQL | localhost:5432 |
| Redis | localhost:6379 |

### 3. Local development (without Docker)

**Backend:**

```bash
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
pip install -r requirements.txt
uvicorn app.main:app --reload
```

**Celery (separate terminals):**

```bash
celery -A app.workers.celery_app worker --loglevel=info
celery -A app.workers.celery_app beat --loglevel=info
```

**Frontend:**

```bash
cd frontend
npm install
npm run dev
```

### 4. Supabase

Apply migrations to a hosted Supabase project:

```bash
supabase db push
```

Or use a reviewed Supabase Cloud migration workflow. Do not apply unreviewed
migrations directly to a production project.

Database tests use pgTAP and live under `supabase/tests/database/`. With a
disposable test database containing all migrations, run:

```bash
supabase test db
```

ADR 0001 remains the migration contract. Run a local dry report from
`backend/` before enabling staging persistence:

```bash
python -m app.services.portfolio_import.cli portfolio-export.xlsx \
  --spreadsheet-id YOUR_GOOGLE_SHEET_ID
```

`--persist-staging` requires `SUPABASE_ACCESS_TOKEN`; ownership is derived from
that verified JWT. Persistence writes only import batches, assets/accounts,
transaction drafts, and import errors. It never promotes a draft or inserts a
confirmed transaction.

## Project Structure

```text
InvestFlow-AI/  # repository name retained pending a future GitHub rename
|-- docker-compose.yml
|-- .env.example
|-- docs/adr/               # accepted architecture decision records
|-- frontend/
|   |-- src/app/              # Next.js App Router pages
|   |-- src/components/       # shadcn/ui + domain components
|   `-- src/lib/              # Supabase client, API helpers
|-- backend/
|   `-- app/
|       |-- agents/           # LangGraph pipeline + agent nodes
|       |-- api/routes/       # FastAPI endpoints
|       |-- services/         # Screener, current yfinance-backed market data
|       |-- workers/          # Celery app + tasks
|       `-- db/               # Supabase client
`-- supabase/
    |-- migrations/           # PostgreSQL schema + RLS policies
    `-- tests/database/       # pgTAP schema, ownership, RLS, and integrity tests
```

## API Endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/health` | Health check |
| POST | `/api/screener/run` | Trigger authenticated screening manually |
| POST | `/api/screener/pipeline` | Run AI pipeline for one ticker |
| GET | `/api/analysis/inbox` | List authenticated user's analyses |
| POST | `/api/analysis/inbox/{id}/approve` | Human approval |
| POST | `/api/analysis/inbox/{id}/discard` | Human discard |
| GET | `/api/portfolio/` | List user paper holdings |
| POST | `/api/portfolio/execute/{inbox_id}` | Create a paper holding from an approved analysis; `execute` is legacy route language |

## Legacy

The root `src/` folder contains the previous React/Vite prototype and is superseded by `frontend/`.
