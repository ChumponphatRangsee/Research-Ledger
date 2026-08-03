# Research Ledger Roadmap

This roadmap reflects the implemented repository through the market-data
provider, service, and Supabase snapshot-cache work.

Status:

- `[x]` implemented in the repository;
- `[ ]` not implemented or not yet complete;
- **Current/next** is the recommended immediate work;
- **Deferred** is intentionally outside the near-term product.

## Product Strategy

Research Ledger is an AI-assisted investment research workspace, not a financial data terminal or an autonomous trading bot. It should help an authenticated user move from quantitative discovery to sourced AI research, human review, paper-portfolio tracking, and thesis re-evaluation.

The near-term experience should prioritize decision quality over breadth: clear screening evidence, structured research memos, citations and freshness, explicit bull/base/bear thinking, documented risks, thesis invalidation criteria, and human approval before any paper holding is created.

## Next Recommended Task

**Repeatable Screener Calibration With Recorded Data**

Run repeatable calibration against the starter universe, inspect ranking quality
by business model, and record false positives, false negatives, and missing-data
patterns before changing thresholds or expanding the universe.

## Phase 1 - Foundation & Security

- [x] FastAPI backend, Next.js frontend, Redis/Celery, and Supabase/Postgres foundation
- [x] Supabase browser/server clients and bearer-token API calls
- [x] FastAPI JWT verification through Supabase JWKS with configured legacy-secret fallback
- [x] Authenticated ownership derived from JWT identity rather than request `user_id`
- [x] Owner-scoped screening runs, analysis inbox items, and paper holdings
- [x] RLS and ownership migrations for `screening_runs`, `analysis_inbox`, `portfolios`, and `screening_results`
- [x] Ownership propagation through FastAPI, Celery, LangGraph, and inbox persistence
- [x] Auth and ownership regression tests for routes, tasks, and graph persistence
- [x] Disable unowned global Celery beat screening
- [ ] Add a complete frontend sign-in/sign-out and session-refresh experience
- [ ] Add database-backed cross-user, RLS, and migration integration tests

## Phase 2 - Quantitative Stock Discovery

- [x] Define a starter stock universe
- [x] Add centralized sector/business-model classification
- [x] Add software strategy
- [x] Add semiconductor strategy
- [x] Add bank strategy without inappropriate corporate debt/FCF rules
- [x] Add consumer/industrial strategy
- [x] Add energy strategy
- [x] Add default operating-company strategy and explicit unsupported classification
- [x] Produce deterministic scores on a 0-100 scale
- [x] Calculate a separate 0-100 data-confidence score
- [x] Enforce minimum confidence and required-category handling
- [x] Preserve missing values and provider failures explicitly
- [x] Persist owner-scoped `screening_results` with explanations and run counters
- [x] Rank passing candidates and send only top N to AI research
- [x] Add authenticated screener run/result APIs
- [x] Add screener dashboard with score, confidence, breakdown, strengths, and warnings
- [x] Add screening unit and mocked persistence/orchestration tests
- [ ] Calibrate thresholds and ranking quality with recorded real-data runs
- [ ] Add live-provider integration fixtures or replay tests

## Phase 3 - Market Data Architecture

- [x] Introduce `MarketDataProvider` abstraction
- [x] Move yfinance behind `YFinanceProvider`
- [x] Add `MarketDataService`
- [x] Add normalized market-data models shared by consumers
- [x] Add structured provider exceptions
- [x] Add Supabase screening/fundamental snapshot cache
- [x] Add cache TTL and freshness behavior
- [x] Remove direct yfinance calls outside the provider layer
- [x] Add provider, normalization, failure, cache, and TTL tests

Later in this phase:

- [ ] Evaluate a production fundamentals provider
- [ ] Add an FMP provider if selected
- [ ] Add a dedicated quote/history provider if needed
- [ ] Add a separate SEC EDGAR filings integration

Paid-provider integration remains deferred. Calibrate the existing normalized
data path and screening results before selecting or adding another provider.

## Phase 4 - Screener Calibration & Expansion (Current/Next)

- [ ] Run repeatable calibration against the starter universe
- [ ] Inspect ranking quality by business model
- [ ] Calibrate eligibility, score, confidence, and category thresholds
- [ ] Record false positives, false negatives, and missing-data patterns
- [ ] Validate whether bank-specific data coverage is adequate
- [ ] Expand the universe to the S&P 500
- [ ] Add peer-group classification
- [ ] Add peer-relative percentile scoring after sector strategies are calibrated

## Phase 5 - Guided AI Research + Investment Memo

- [x] Create a LangGraph pipeline skeleton: Researcher -> Financial Analyst -> Valuator -> Decision Maker
- [x] Persist basic prototype outputs to the owner-scoped analysis inbox
- [ ] Add a detailed research page centered on a readable investment memo
- [ ] Define validated structured schemas for every agent output
- [ ] Replace the placeholder researcher with sourced qualitative and filing research
- [ ] Build a substantive financial-analysis stage on normalized data
- [ ] Replace prototype P/E valuation with explicit, deterministic valuation methods
- [ ] Produce structured decision output instead of only a simple recommendation/memo
- [ ] Preserve source citations and evidence
- [ ] Show source and market-data freshness
- [ ] Report research confidence separately from quantitative score
- [ ] Add bull, base, and bear cases
- [ ] Add risks and catalysts
- [ ] Add thesis invalidation criteria
- [ ] Add analysis history and versioning

## Phase 6 - Investment Workflow

- [x] Provide an owner-scoped analysis inbox
- [x] Provide pending-only approve and reject/discard actions
- [x] Create a basic user-owned database holding from an approved analysis
- [ ] Rename legacy `execute` language to an explicit paper-portfolio action
- [ ] Add watchlists and a watchlist review action
- [ ] Add saved screening strategies
- [ ] Add a complete approve/reject/watchlist frontend flow
- [ ] Model paper transactions and positions explicitly
- [ ] Add thesis journal entries
- [ ] Add thesis revisions and links to analysis versions
- [ ] Add paper-portfolio performance tracking
- [ ] Add thesis re-evaluation triggers and review history

The current `portfolios` rows are paper holdings only. They are not evidence of brokerage execution.

## Phase 7 - Reliability & Evaluation

- [ ] Centralize and test deterministic financial calculations
- [ ] Add an AI/model evaluation suite
- [ ] Add factual-consistency tests
- [ ] Measure citation coverage
- [ ] Enforce structured-output/JSON validity
- [ ] Monitor provider failures and stale-cache usage
- [ ] Add bounded retries and failure classification
- [ ] Add structured, correlation-aware logging for API, Celery, and LangGraph
- [ ] Track model token use and cost
- [ ] Add end-to-end screening-to-review database integration tests
- [ ] Make worker failures and partial screening failures visible in the UI

## Deferred

- [ ] Real brokerage execution
- [ ] Automatic live trading
- [ ] International markets
- [ ] Complex team/workspace permissions
- [ ] A large set of specialized sector models before core strategies are calibrated
- [ ] Speculative microservice decomposition
