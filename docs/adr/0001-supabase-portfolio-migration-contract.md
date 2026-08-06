# ADR 0001: Supabase Portfolio Migration Contract

- Status: Accepted
- Date: 2026-08-06
- Owners: Research Ledger maintainers
- Scope: Portfolio migration, transaction ledger, and dependent research workflows

## Context

Research Ledger currently stores quantitative screening and prototype research data in Supabase. Its `portfolios` table represents legacy paper holdings created from approved analyses; it is not a transaction ledger and must not be reused as one.

The current investment tracker is maintained in Google Sheets. The target system needs one auditable source of truth for stocks, ETFs, crypto, cash, bonds, mutual funds, and other assets without breaking the existing stock screener, which is keyed by `tickers`.

The available workbook export is an older 7-tab snapshot while the current Google Sheet has 15 tabs. It cannot be used for the production import. A new export is required before migration staging begins.

## Decision

### Source of truth and cutover

- Supabase Postgres becomes the source of truth for portfolio transactions, positions, cost basis, cash flows, valuations, allocation, and portfolio context.
- Google Sheets remains writable during migration and dual-run, then becomes a read-only archive only after every reconciliation gate passes.
- The portfolio base currency is THB.
- The migration stays inside the existing FastAPI, Next.js, and Supabase monorepo.
- `portfolios` remains a legacy paper-holding table during the migration. It is not imported into or treated as the confirmed transaction ledger.

### Asset model

- New portfolio records use a universal `assets` model supporting Stock, ETF, Crypto, Cash, Bond, Mutual fund, and Other.
- Existing `tickers` remains the stock-screener identity model.
- A US-listed stock asset may reference one ticker through an optional one-to-one relationship. Non-stock assets do not require a ticker.

### Ledger and calculation rules

- Confirmed transactions are immutable.
- Corrections are represented by linked reversal/correction transactions; confirmed rows are never edited or deleted in place.
- Cost basis uses the weighted-average method, partitioned by investment account and asset.
- Quantity, price, fee, FX, cost-basis, and P&L values use PostgreSQL `numeric`, never floating-point types.
- Positions, realized P&L, unrealized P&L, allocation, balances, and cash flows are deterministic projections rebuilt from ordered confirmed transactions.
- Formula-derived summary tabs in Google Sheets are reconciliation inputs, not migration truth.
- Historical FX values already used by the tracker are preserved during import. They must not be silently recomputed.

### Transaction workflow

- Manual entry, imported rows, AI extraction, and screenshot extraction create drafts first.
- The required workflow is Draft -> Human review -> Confirm -> Ledger projection.
- Confirmation must be atomic and idempotent.
- AI may read portfolio context and propose drafts, research, risk analysis, and recommendations. It may not confirm transactions or place real trades.
- A correction must link to the transaction it reverses.

### Research and scoring boundaries

- Quantitative score, research score, and opportunity score are separate concepts and must be persisted separately.
- Portfolio context may influence opportunity score and position-sizing rationale, but it must not rewrite quantitative business-quality evidence.
- AI analysis must preserve facts, assumptions, estimates, judgment, sources, freshness, scenarios, thesis invalidation, portfolio-context snapshot, and prompt/model version.

### Ownership and database security

- User ownership is derived from the verified Supabase JWT. A client-supplied `user_id` is never trusted.
- Every user-owned table in an exposed schema has RLS enabled, an indexed ownership column, and owner-scoped policies.
- Confirmed transactions expose no authenticated update or delete path. Drafts may be updated or deleted only by their owner before confirmation.
- Data API privileges are explicitly granted per table and operation; grants and RLS are treated as separate controls.
- User-facing views use `security_invoker = true` so underlying RLS remains effective.
- Backend service-role credentials remain backend-only. Service-role use does not remove the requirement for explicit owner filters.

## Delivery sequence

Each item uses one branch and one pull request. Do not automatically begin the next item after completing the current one.

1. PR 0: architecture contract and roadmap update
2. PR 1: portfolio ledger foundation
3. PR 2: Google Sheets staging import and dry-run report
4. PR 3: deterministic portfolio calculation engine
5. PR 4: transaction draft, confirmation, correction, and review UI
6. PR 5: asset prices, FX, valuation snapshots, and performance
7. PR 6: allocation, DCA, and risk controls
8. PR 7: stock-screener migration
9. PR 8: structured AI research and thesis history
10. PR 9: scheduling, monitoring, dual-run, and cutover

The usable Portfolio Migration MVP ends after PR 5. Screener migration and AI research expansion remain later phases.

## Reconciliation gates

Google Sheets cannot become read-only until all of the following pass:

- transaction row counts match the approved import set;
- no duplicate `source_fingerprint` exists;
- quantity by account and asset matches;
- weighted-average cost and realized P&L match the accepted baseline;
- the CRWD partial sells and MSFT purchase history reconcile;
- no sell creates a negative position unless a future, explicit short-selling model is approved;
- total portfolio value is within a documented tolerance;
- allocation totals 100% within rounding tolerance;
- repeated import creates no additional confirmed rows;
- reversal/correction and cross-user RLS tests pass;
- database security advisors show no unresolved material finding; and
- pgTAP and application integration tests pass.

## Consequences

- Portfolio migration takes priority over screener expansion until the ledger and reconciliation path are reliable.
- Google Sheets remains necessary during staging and dual-run, so the system temporarily has two representations but only one approved migration direction.
- The transaction ledger remains small and auditable; derived portfolio state can be rebuilt instead of manually repaired.
- Existing screener functionality continues during PRs 1-6 because `tickers` and legacy `portfolios` are preserved.
- A fresh 15-tab Google Sheets export is a blocking input for PR 2 production data work, but not for PR 1 schema implementation.

## References

- [Supabase: Row Level Security](https://supabase.com/docs/guides/database/postgres/row-level-security)
- [Supabase breaking change: tables are not automatically exposed to the Data and GraphQL APIs](https://supabase.com/changelog/45329-breaking-change-tables-not-exposed-to-data-and-graphql-api-automatically)
- [Supabase: Import data](https://supabase.com/docs/guides/database/import-data)
- [Supabase: Database testing](https://supabase.com/docs/guides/local-development/testing/overview)
