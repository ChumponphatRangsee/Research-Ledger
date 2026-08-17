# Research Ledger Roadmap

This roadmap reflects the implemented repository through the market-data
provider, service, and Supabase snapshot-cache work, plus the accepted
portfolio migration contract in
[ADR 0001](docs/adr/0001-supabase-portfolio-migration-contract.md).

Status:

- `[x]` implemented in the repository;
- `[ ]` not implemented or not yet complete;
- **Current/next** is the recommended immediate work;
- **Deferred** is intentionally outside the near-term product.

## Product Strategy

Research Ledger is an AI-assisted investment research workspace, not a financial data terminal or an autonomous trading bot. It should help an authenticated user move from quantitative discovery to sourced AI research, human review, paper-portfolio tracking, and thesis re-evaluation.

The near-term experience should prioritize decision quality over breadth: an auditable transaction ledger, deterministic portfolio context, clear screening evidence, structured research memos, citations and freshness, explicit bull/base/bear thinking, documented risks, thesis invalidation criteria, and human approval before any portfolio action.

## Next Recommended Task

**PR 4 - Transaction Workflow**

Add draft create/read/update APIs, transaction list and linked
reversal/correction APIs, and the review UI needed to confirm or correct
transactions without bypassing human approval.

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

## Phase 4 - Portfolio Migration (Current/Next)

The migration is delivered as one focused branch and pull request per item.
Google Sheets remains writable through staging and dual-run, then becomes a
read-only archive only after reconciliation succeeds.

### PR 0 - Architecture Contract

- [x] Record Supabase as the target source of truth and THB as base currency
- [x] Retain weighted-average cost by account and asset
- [x] Define confirmed transactions as immutable and corrections as linked reversals
- [x] Require Draft -> Human review -> Confirm for screenshots and AI extraction
- [x] Preserve `portfolios` as legacy paper holdings and `tickers` as the screener model
- [x] Define universal `assets` and keep its ticker relationship optional
- [x] Separate quantitative, research, and opportunity scores
- [x] Record security, reconciliation, delivery, and cutover gates in ADR 0001

### PR 1 - Portfolio Ledger Foundation

- [x] Add `assets` for Stock, ETF, Crypto, Cash, Bond, Mutual fund, and Other
- [x] Add `investment_accounts`
- [x] Add owner-scoped `transaction_drafts` that freeze after confirmation
- [x] Add immutable `transactions` with BUY, SELL, DIVIDEND, STAKING, INTEREST, TRANSFER_IN, TRANSFER_OUT, FEE, and REVERSAL
- [x] Add `transaction_import_batches` and batch-consistent `transaction_import_errors`
- [x] Use PostgreSQL `numeric` for ledger quantity, price, fee, amount, and FX values; derived cost basis and P&L remain PR 3
- [x] Add source identifiers, raw source data, and unique confirmed-transaction source fingerprints
- [x] Add RLS, ownership indexes, least-privilege explicit grants, and cross-user pgTAP tests
- [x] Preserve the legacy `portfolios` table

### PR 2 - Google Sheets Migration Staging

- [x] Re-export the current 15-tab Google Sheet; do not import the old 7-tab workbook as production truth
- [x] Stage rows with original row number and raw data preserved
- [x] Normalize transaction types, symbols, currencies, asset classes, and account names
- [x] Deduplicate by `source_fingerprint`
- [x] Isolate ambiguous rows in `transaction_import_errors`
- [x] Produce a dry-run report before promoting any transaction
- [x] Verify crypto fee units, stored historical FX, formula-derived prices, CRWD/MSFT history, and non-negative positions

### PR 3 - Deterministic Portfolio Calculation Engine

- [x] Replay confirmed transactions chronologically by account and asset
- [x] Calculate quantity, weighted-average cost, THB cost basis, realized P&L, unrealized P&L, income, cash flows, and allocations
- [x] Add rebuildable projections and `security_invoker = true` views
- [x] Recalculate from ledger rows rather than importing formula-derived summary tabs

### PR 4 - Transaction Workflow

- [ ] Add draft create/read/update and atomic idempotent confirmation APIs
- [ ] Add transaction list and linked reversal/correction APIs
- [ ] Add Transactions, Draft Review, Transaction Detail, Correction/Reversal, and Import Errors pages
- [ ] Prevent AI or screenshot extraction from bypassing human confirmation

### PR 5 - Prices, FX, and Performance (Portfolio Migration MVP)

- [ ] Add asset price, FX rate, portfolio valuation, and benchmark snapshots
- [ ] Extend `MarketDataService` for stock, ETF, crypto, FX to THB, historical prices, and SPY benchmark data
- [ ] Rebuild performance from transactions and historical valuations
- [ ] Complete MVP reconciliation and dual-run readiness checks

### PR 6 - Allocation, DCA, and Risk

- [ ] Add versioned investor context, target allocations, DCA plans, risk limits, and risk snapshots
- [ ] Add allocation-gap, concentration, theme-exposure, DCA, and model-check views
- [ ] Read portfolio context from Supabase before asking the user for missing or stale inputs

### PR 7 - Stock Screener Migration

- [ ] Migrate sector KPI definitions, discovery runs/candidates, watchlists, valuation scenarios, and buy zones
- [ ] Keep quantitative, research, and opportunity scores independent
- [ ] Resume repeatable screener calibration before expanding the universe

### PR 8 - Structured AI Research and Thesis

- [ ] Add versioned scorecards, sources, analyses, theses, revisions, recommendations, and AI runs
- [ ] Persist facts, assumptions, estimates, judgment, citations, freshness, scenarios, sizing rationale, and thesis invalidation
- [ ] Preserve the portfolio-context snapshot and prompt/model version used for every analysis

### PR 9 - Scheduling and Cutover

- [ ] Add owner-aware scheduled jobs, monitoring, and failure reporting
- [ ] Pass every reconciliation, idempotency, RLS, security-advisor, pgTAP, and application integration gate
- [ ] Complete dual-run before making Google Sheets a read-only archive

## Phase 5 - Screener Calibration & Expansion

- [ ] Run repeatable calibration against the starter universe
- [ ] Inspect ranking quality by business model
- [ ] Calibrate eligibility, score, confidence, and category thresholds
- [ ] Record false positives, false negatives, and missing-data patterns
- [ ] Validate whether bank-specific data coverage is adequate
- [ ] Expand the universe to the S&P 500
- [ ] Add peer-group classification
- [ ] Add peer-relative percentile scoring after sector strategies are calibrated

## Phase 6 - Guided AI Research + Investment Memo

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

## Phase 7 - Investment Workflow

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

## Phase 8 - Reliability & Evaluation

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
