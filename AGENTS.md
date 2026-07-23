# InvestFlow AI Agent Guide

## Project Mission

InvestFlow AI is an AI-assisted investment research platform. It helps authenticated users discover, quantitatively screen, research, review, and track investment ideas.

The intended flow is:

```text
Discover -> Quantitative Screen -> AI Research -> Human Review
         -> Paper Portfolio -> Thesis Tracking -> Re-evaluation
```

It is not a live brokerage or automated trading system. The current portfolio endpoint creates a database-backed paper holding; its legacy `execute` name must not be described as real trade execution. Human review remains a required decision point.

## Sources of Truth

Use this order:

1. GitHub code and Supabase migrations define what currently exists.
2. [ROADMAP.md](ROADMAP.md) defines intended implementation order.
3. [ARCHITECTURE.md](ARCHITECTURE.md) defines architectural constraints.
4. [README.md](README.md) provides setup and a high-level overview.

The README contains some stale descriptions. If code, migrations, tests, and documentation disagree, inspect the implementation and recent relevant commits or pull requests, then reconcile the documentation before coding.

## Current Boundaries

- `frontend/` is the active Next.js application. The root package metadata is legacy.
- `backend/` contains FastAPI routes, screening services, the LangGraph pipeline, and Celery tasks.
- `supabase/migrations/` is authoritative for the database schema and RLS.
- Sector-aware screening, persistent results, top-N selection, and the screener dashboard exist.
- Authentication and explicit single-user ownership exist across API routes, Celery, LangGraph state, and persistence.
- Market data still comes directly from `backend/app/services/yfinance_client.py`; the provider/service/cache architecture is planned.
- The LangGraph flow exists, but its researcher is a placeholder and its valuation/decision logic is only a prototype. Do not present it as production-grade AI research.

## Before Coding

1. Confirm the branch and compare it with current `main`.
2. Read the relevant routes, services, models, migrations, and tests.
3. Inspect recent relevant commits or pull requests when they clarify intent.
4. Identify the smallest logical feature or fix and its ownership/security impact.
5. Avoid unrelated refactors, speculative abstractions, and cleanup outside scope.

## Development Workflow

```text
one focused feature/fix
-> feature branch
-> implementation
-> tests
-> self-review
-> pull request
```

Do not implement directly on `main`. Finish and report the current task without automatically starting the next roadmap item.

## Security Rules

These are hard constraints:

- Derive authenticated ownership from verified Supabase JWT identity.
- Never trust a client-supplied `user_id`.
- Preserve Supabase RLS as defense in depth.
- Preserve service-role boundaries. Service-role credentials are backend-only and must never reach the frontend.
- Pass ownership explicitly through API, Celery task arguments, LangGraph state, and persisted rows.
- Scope reads and mutations to the authenticated owner, including `screening_runs`, `analysis_inbox`, and `portfolios`.
- User A must never read, mutate, approve, discard, or create paper holdings from User B's data.
- A scheduled/global job must not bypass the ownership model. The current Celery beat schedule is intentionally empty.

Never weaken JWT verification, ownership checks, RLS, or migration safeguards to simplify development or tests.

## Financial Data Rules

- Missing values remain `None`/`null`; never silently convert them to zero.
- Score and confidence are separate. A high partial score with insufficient confidence is not a trusted pass.
- Enforce required-category availability separately from partial scoring.
- Use sector/business-model-specific metrics. Banks must not use ordinary corporate leverage or free-cash-flow rules.
- Mark unsupported business models explicitly instead of guessing a specialist score.
- Prefer deterministic code for calculations, normalization, ranking, and eligibility.
- Keep provider-specific field names and raw response shapes out of domain logic.

## Market Data Rules

The target dependency direction is:

```text
Application/domain code
-> MarketDataService
-> MarketDataProvider interface
-> provider implementation
```

Providers must return normalized internal models and structured failures. Once the abstraction exists, direct `yfinance` imports are allowed only in `YFinanceProvider`. Do not hardcode provider keys, credentials, or secrets. Keep SEC filing retrieval behind a separate filings service rather than treating filings as quote/fundamental data.

## AI Research Rules

- Prefer validated structured outputs over free-form strings.
- Preserve sources, evidence, retrieval timestamps, and data freshness.
- Never fabricate missing facts; `insufficient data` is a valid result.
- Make valuation method and assumptions explicit.
- Keep deterministic arithmetic outside the LLM.
- Preserve the human-review breakpoint before any paper-portfolio action.

## Database Rules

- Make schema changes through ordered Supabase migrations.
- Treat migrations as authoritative for exact tables, columns, constraints, indexes, foreign keys, and RLS.
- Preserve ownership foreign keys and RLS policies.
- Add supporting indexes when access patterns require them.
- Do not make manual production schema edits when a migration is appropriate.

## Testing Expectations

Add or update tests proportional to the change, especially for:

- JWT authentication, ownership isolation, and spoofed `user_id` rejection;
- RLS assumptions and database-backed cross-user behavior;
- sector classification, scoring, confidence, required categories, and ranking;
- missing or malformed financial data;
- provider failures, normalization, caching, and TTL behavior;
- Celery and LangGraph ownership propagation;
- migrations and database integration.

Run the narrow tests first, then the relevant backend/frontend suite. Do not claim tests passed if dependencies or infrastructure prevented execution.

## Definition of Completion

Every implementation handoff must report:

- files created or modified;
- migrations added or changed;
- tests run and results;
- architectural or security impact;
- known limitations;
- one recommended next [ROADMAP.md](ROADMAP.md) task.

Recommend the next task, but do not implement it automatically.
