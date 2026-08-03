# Research Ledger Architecture

This document separates the implemented system from intended boundaries. Supabase migrations remain authoritative for exact schema; see [ROADMAP.md](ROADMAP.md) for implementation order.

## System Overview

### Current

```text
User
  |
  v
Next.js frontend
  |  Supabase access token
  v
FastAPI API
  |
  +-> application/research modules -> MarketDataService
  |                                  +-> Supabase snapshot cache
  |                                  +-> YFinanceProvider -> yfinance
  |
  +-> Supabase service-role client -> Postgres

Async:

FastAPI
  |
  v
Celery worker <-> Redis
  |
  +-> sector-aware quantitative screening
  |
  +-> top-N candidates
  |
  v
LangGraph research pipeline
  |
  v
analysis_inbox -> human review -> paper holding
```

The Docker stack includes a Celery beat process, but `beat_schedule` is intentionally empty because a global schedule has no authenticated owner.

## Core Product Flow

### Current and planned

```text
Stock Universe
  -> Market Data
  -> Quantitative Screening
  -> Ranking
  -> Top Candidates
  -> AI Research
  -> Analysis Inbox
  -> Human Review
  -> Paper Portfolio
  -> Thesis Tracking
  -> Re-evaluation
```

The flow is implemented through human review and basic paper-holding creation.
The market-data abstraction and persistent freshness cache are implemented;
substantive sourced AI research, thesis tracking, and re-evaluation are planned.

## Backend Layers

Target dependency direction:

```text
API Routes
    |
    v
Application / Service Layer
    |
    v
Domain Logic
    |
    v
Providers / Persistence
```

Current screening mostly follows this split: routes enqueue work, the screener orchestrates, the screening package classifies/scores, and persistence is handled outside scoring. Maintain these boundaries:

- Routes must not contain financial scoring rules.
- Screening strategies must consume normalized models and must not call external APIs.
- Provider responses must be normalized before domain use.
- Database access must preserve owner scoping and service-role boundaries.
- LangGraph nodes must not become an alternate, ungoverned data-access layer.

## Authentication and Ownership

### Current authentication

```text
Frontend
  -> Supabase session
  -> Bearer access token
  -> FastAPI JWT verification
  -> AuthenticatedUser.id
```

FastAPI verifies Supabase issuer, audience, signature, and subject. JWKS is preferred; a configured legacy HS256 secret is the fallback. Request bodies do not define ownership.

Backend persistence currently uses a backend-only Supabase service-role client. Because that client can bypass RLS, API and worker code explicitly scopes operations to `AuthenticatedUser.id`. RLS provides mandatory defense in depth for authenticated database access.

### Ownership propagation

```text
JWT user
  -> screening_run.user_id
  -> screening_results through screening_run
  -> Celery task user_id
  -> LangGraph state.user_id
  -> analysis_inbox.user_id
  -> portfolios.user_id
```

`screening_run_id` is also checked against the authenticated owner before a user can enqueue research for it. Cross-user access must fail without revealing another user's data.

## Quantitative Screening Architecture

### Current

```text
Ticker
  -> MarketDataService
  -> Fresh Supabase snapshot or YFinanceProvider fallback
  -> Normalized FinancialMetrics
  -> Business Model Classifier
  -> Strategy Registry
  -> Eligibility Checks
  -> Category Scoring
  -> Confidence
  -> Required Categories
  -> Final Pass/Fail
  -> Ranking
  -> Persist all results
  -> Queue top-N passing candidates
```

Screening is sector/business-model-aware rather than a universal P/E/ROE filter. The current registry supports:

- software;
- semiconductor;
- bank;
- consumer/industrial;
- energy;
- default operating company;
- explicit unsupported classification for models such as REITs, utilities, insurance, asset management, and capital markets.

Missing metrics remain null. Available metrics can produce a partial score, while confidence measures expected-data coverage. Passing requires the score threshold, confidence threshold, eligibility checks, and required categories. Unsupported businesses do not receive a misleading specialist score. Bank rules avoid normal-company debt-to-equity and free-cash-flow assumptions, although current yfinance coverage of specialist bank fields is limited.

## Market Data Architecture

### Current

`backend/app/services/market_data/` defines the normalized company snapshot, the
`MarketDataProvider` interface, structured provider exceptions, and
`MarketDataService`. Quantitative screening and the prototype financial-analysis
node both depend on this service. `YFinanceProvider` is the only module that
imports yfinance directly and maps provider responses into the normalized
snapshot. There is no paid-provider integration.

```text
Screener / Research
        |
        v
MarketDataService
    /          \
   v            v
Fresh cache   Cache miss/stale
   ^            |
   |            v
   |      MarketDataProvider
   |            |
   |            v
   +---- normalized snapshot
          from YFinanceProvider
```

`MarketDataService` normalizes requested symbols to uppercase and keys company
snapshots by symbol, provider, and `company_snapshot`. A row is fresh only while
`expires_at` is later than the lookup time. Fresh rows are validated back into
`CompanyFinancialSnapshot`; a miss or stale row calls the provider and upserts
the normalized payload with a 24-hour default TTL. Provider failures propagate
unchanged and are not cached. Cache read or write failures are logged and
bypassed so a cache outage or malformed row does not block a healthy provider
or a successful provider response. Missing metrics remain JSON null.

`market_data_snapshots` is shared backend cache data rather than user-owned
application data. RLS is enabled, anon/authenticated table access is revoked,
and only the backend service-role client manages rows. The cache records the
provider, observation time (`data_as_of`), retrieval time (`fetched_at`), and
freshness cutoff (`expires_at`). Service-role credentials remain backend-only.

Consumers depend on normalized internal models, never provider response shapes.

Filings are a separate concern:

```text
Research pipeline
      |
      v
FilingsService
      |
      v
SEC EDGAR
```

Filings should retain document identity and citations rather than being treated as interchangeable quote data.

## AI Research Architecture

### Current

```text
Researcher
  -> Financial Analyst
  -> Valuator
  -> Decision Maker
  -> Persist to analysis_inbox
  -> Human review
```

LangGraph and the persistence breakpoint are implemented. Ownership and optional screening-run lineage travel through graph state.

The research quality is prototype-only:

- the Researcher returns placeholder qualitative text and no sources;
- the Financial Analyst formats a small normalized market-data subset;
- the Valuator applies a simplified normalized-P/E calculation;
- the Decision Maker derives BUY/HOLD/PASS from calculated upside and emits a basic memo.

No node currently calls a configured LLM. Structured sourced research, explicit assumptions, evidence, confidence, and analysis versioning are planned. Quantitative screening should continue to limit expensive research to top-ranked candidates, and human review remains mandatory.

## Persistence

### Current tables

- `tickers`: shared ticker metadata and last-screened timestamp;
- `market_data_snapshots`: shared backend-managed normalized snapshot cache with
  provider, observation, retrieval, and expiry timestamps;
- `screening_runs`: user-owned run criteria, status, counters, and timing;
- `screening_results`: per-run scores, confidence, normalized metrics, explanations, warnings, and failures;
- `analysis_inbox`: user-owned prototype research output and human-review status;
- `portfolios`: user-owned paper holdings created from approved inbox items.

Important relationships:

```text
auth.users
  +-> screening_runs -> screening_results -> tickers
  +-> analysis_inbox ---------------------> tickers
  +-> portfolios -> approved analysis ----> tickers
```

Migrations enforce ownership foreign keys, RLS, indexes, a unique result per run/ticker, and at-most-once paper-holding creation from an approved inbox item. Supabase migrations are the authoritative source for exact schema.

## Background Jobs

### Current

- Authenticated `POST /api/screener/run` enqueues a user-scoped Celery screening task.
- The task screens the starter universe, persists every result, ranks passing results, and queues AI research only for the configured top N.
- Each AI task receives `user_id` and `screening_run_id`; the graph persists both.
- Per-symbol provider failures are recorded as failed results and processing continues.
- Successful research-task queue counts are recorded on the owner-scoped run.

Worker failures are logged, but end-to-end observability, retries, correlation IDs, and UI-visible failure details remain planned. Scheduled/global screening must not be enabled until it has an explicit ownership and delivery model.

## Frontend

### Current

- `/`: static dashboard and navigation;
- `/screener`: authenticated run controls, polling, ranked results, and explanations;
- `/inbox`: owner-scoped pending analyses with approve/discard actions;
- `/portfolio`: owner-scoped basic holdings list.

The frontend obtains an existing Supabase browser session and attaches its access token to API calls. A complete sign-in/sign-out UI is not present. The analysis inbox has no detailed research page, and the paper-portfolio workflow has only basic display/API support.

Any remaining “execute trade” language is legacy terminology. It means inserting a paper holding, not contacting a broker.

## Architectural Constraints: Do Not

- Do not accept ownership from client-supplied user IDs.
- Do not expose the Supabase service-role key or other secrets to the frontend.
- Do not weaken RLS or omit explicit owner filters when using the service role.
- Do not call financial-data vendors directly from screening strategies.
- Do not let provider-specific response shapes leak into domain logic.
- Do not silently treat missing data as zero.
- Do not conflate score with confidence.
- Do not use standard corporate leverage/FCF rules for banks.
- Do not use AI for arithmetic or deterministic rules that normal code can perform.
- Do not fabricate research facts or sources.
- Do not describe paper holdings as live trade execution.
- Do not bypass top-N screening to send the entire universe through expensive AI research.

## Future Architecture

Near-term evolution should stay inside the existing monorepo:

1. market-data cache observability and deliberate production-provider evaluation;
2. calibrated sector and later peer-relative scoring;
3. structured research outputs with evidence and citations;
4. analysis history/versioning;
5. paper transactions, thesis tracking, and re-evaluation.

Do not introduce speculative microservices before these boundaries and workflows are proven.
