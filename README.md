# InvestFlow-AI

A semi-automated financial research platform combining quantitative screening, multi-agent AI analysis, and human-in-the-loop investment decisions.

## Architecture

```
┌─────────────────────────────────────────────────────────────────────────┐
│                         InvestFlow-AI Monorepo                          │
├──────────────────────────────┬──────────────────────────────────────────┤
│  frontend/ (Next.js 15)      │  backend/ (FastAPI)                     │
│  • Dashboard (Tremor)        │  • REST API                              │
│  • Analysis Inbox            │  • LangGraph agent pipeline              │
│  • Portfolio view            │  • Celery workers + beat scheduler       │
│  • Supabase Auth client      │  • yfinance data layer                   │
├──────────────────────────────┴──────────────────────────────────────────┤
│  supabase/ — PostgreSQL schema (tickers, analysis_inbox, portfolios)      │
├───────────────────────────────────────────────────────────────────────────┤
│  docker-compose — Postgres, Redis, FastAPI, Celery, Next.js               │
└─────────────────────────────────────────────────────────────────────────┘
```

### Data Flow

1. **Celery Beat** triggers the daily screener at a configured time.
2. **Screener** fetches market data via yfinance, filters by P/E, ROE, market cap.
3. For each candidate, **LangGraph** runs four agents:
   - Researcher → Financial Analyst → Valuator → Decision Maker
4. Results land in **analysis_inbox** with `status = pending_review` (human breakpoint).
5. User reviews on the **Inbox** page → Approve or Discard.
6. Approved items can be **executed** into the user's portfolio.

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

| Service        | URL                    |
|----------------|------------------------|
| Frontend       | http://localhost:3000  |
| Backend API    | http://localhost:8000  |
| API docs       | http://localhost:8000/docs |
| PostgreSQL     | localhost:5432         |
| Redis          | localhost:6379         |

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

Or use the local Postgres container (migrations auto-apply on first boot).

## Project Structure

```
InvestFlow-AI/
├── docker-compose.yml
├── .env.example
├── frontend/
│   ├── src/app/              # Next.js App Router pages
│   ├── src/components/       # shadcn/ui + domain components
│   └── src/lib/              # Supabase client, API helpers
├── backend/
│   └── app/
│       ├── agents/           # LangGraph pipeline + agent nodes
│       ├── api/routes/       # FastAPI endpoints
│       ├── services/         # Screener, yfinance
│       ├── workers/          # Celery app + tasks
│       └── db/               # Supabase client
└── supabase/
    └── migrations/           # PostgreSQL schema + RLS policies
```

## API Endpoints

| Method | Path | Description |
|--------|------|-------------|
| GET | `/health` | Health check |
| POST | `/api/screener/run` | Trigger screener manually |
| POST | `/api/screener/pipeline` | Run AI pipeline for one ticker |
| GET | `/api/analysis/inbox` | List pending analyses |
| POST | `/api/analysis/inbox/{id}/approve` | Human approval |
| POST | `/api/analysis/inbox/{id}/discard` | Human discard |
| GET | `/api/portfolio/` | List user holdings |
| POST | `/api/portfolio/execute/{inbox_id}` | Execute approved trade |

## Legacy

The root `src/` folder contains the previous React/Vite prototype and is superseded by `frontend/`.
