# PR 2 Google Sheets staging dry-run

Date: 2026-08-07  
Workbook: [Investment Portfolio Tracker - Chumponphat](https://docs.google.com/spreadsheets/d/1MUZD_nevvmH3yx972Ep6o8pCRmsdd_IgzSzjD6TPCjw)  
Workbook time zone: Asia/Bangkok  
Source status: writable during migration and dual-run

## Source identity

Drive metadata and spreadsheet metadata identify this as the current workbook:

- 15 tabs, in the expected order;
- `Transactions` is the source transaction tab;
- `Holdings` and `Checks` are reconciliation inputs only; and
- the separate 7-tab `Investment tracking` workbook is not an approved source.

The export was downloaded as a local XLSX on 2026-08-10 and validated with the
staging CLI. No source workbook or private access token is stored in Git.

## Live source preflight

Bounded reads of `Transactions!A4:V204`, `Holdings!A4:D18`, `Checks!A4:G15`,
and the relevant price/formula cells produced this redacted report:

| Check | Result | Evidence |
| --- | --- | --- |
| Transaction input rows | Pass | 25 source rows; 23 BUY and 2 SELL |
| Workbook data checks | Pass | Every populated transaction row reports `OK` |
| Asset classes | Pass | 10 Stock rows and 15 Crypto rows |
| Accounts | Pass | Best 17, Loan Money 6, Mom 2 |
| Transaction currencies | Pass | USD 16 and USDT 9; stored values are preserved |
| Historical FX | Pass | All 25 rows contain literal positive FX-to-THB inputs |
| Formula-derived prices | Pass | Transaction `Price` inputs are literal; derived transaction/summary columns are ignored |
| Crypto fee units | Pass | 5 positive asset-unit fee rows; exact effective values remain source evidence |
| CRWD history | Pass | 1 buy and 2 partial sells replay to zero units |
| MSFT history | Pass | 2 buys replay to 1.230852 units |
| Negative positions | Pass | Workbook `Checks` reports 0 negative holdings |
| Holdings reconciliation | Pass | Live formula-derived Holdings quantities match the transaction replay baseline |

The five positive asset-unit fees are retained at full effective precision:
`0.0000023 BTC`, `0.00000229 BTC`, `0.0444 XRP`, `0.0000312 ETH`, and
`0.0226 XRP`. Their displayed currency formatting is not used for parsing.

## XLSX dry-run result

The canonical CLI run completed successfully against the exported workbook:

```bash
python -m app.services.portfolio_import.cli \
  "C:\Research-Ledger\data\Investment Portfolio Tracker - Chumponphat.xlsx" \
  --spreadsheet-id 1MUZD_nevvmH3yx972Ep6o8pCRmsdd_IgzSzjD6TPCjw \
  --output ..\docs\migration\google-sheets-pr2-live-dry-run-report.json
```

Result summary:

- status: `READY`
- rows read: 25
- rows ready for human review: 25
- rows with errors: 0
- checks passed: current 15-tab export, stored historical FX, literal transaction
  prices, crypto fee units, CRWD partial sell history, MSFT purchase history,
  non-negative positions, and Holdings reconciliation
- source fingerprint:
  `ca46029d6325b49bc0a0b9c9166bde3a809e00ef230fb61004e63b43433c4296`

The replay treats tiny fractional-share residue up to `0.000001` units as zero
for reconciliation. This handles the closed CRWD position where the source
transactions sum to a `0.0000001` unit residue while the workbook Holdings tab
correctly records zero.

## Supabase staging result

The approved XLSX export was staged to Supabase Cloud on 2026-08-11 using the
development-only owner bypass. The bypass used the backend service role only to
resolve the existing Supabase Auth user by email; row ownership was still stored
as the resolved `auth.users.id`.

```bash
python -m app.services.portfolio_import.cli \
  "C:\Research-Ledger\data\Investment Portfolio Tracker - Chumponphat.xlsx" \
  --spreadsheet-id 1MUZD_nevvmH3yx972Ep6o8pCRmsdd_IgzSzjD6TPCjw \
  --persist-staging \
  --output ..\docs\migration\google-sheets-pr2-live-staging-report.json
```

Remote verification:

- import batch: `9588e840-4d46-4661-ae1c-f91f36e626be`
- `transaction_import_batches`: 1 row for the batch
- `transaction_drafts`: 25 rows for the batch
- `transaction_import_errors`: 0 rows for the batch
- confirmed `transactions` from the batch drafts: 0 rows

## Confirmed ledger promotion result

After the PR 4 confirmation workflow was deployed, the staged batch was
explicitly approved and confirmed on 2026-08-11. Confirmation used the
backend-only `confirm_transaction_draft` RPC, which returns the same confirmed
transaction if called repeatedly for the same draft.

Remote verification after confirmation:

- pending drafts for batch `9588e840-4d46-4661-ae1c-f91f36e626be`: 0
- confirmed drafts for the batch: 25
- confirmed transactions linked to the batch drafts: 25
- total confirmed transactions for the owner: 25
- idempotency spot check: repeating confirmation for an already confirmed draft
  returned the same transaction and kept one transaction for that draft

Deterministic ledger replay after confirmation:

- positions: 14 account/asset positions
- total THB cost basis: `309749.48879218389783534`
- total realized P&L: `6198.063816362974`
- total income: `0`
- CRWD replay quantity: `0` after tiny fractional residue normalization

## Staging behavior

The importer:

1. rejects any workbook that is not the exact approved 15-tab shape;
2. preserves source row number plus entered/effective cell values in
   `raw_source_data`;
3. normalizes action, account, symbol, asset class, currency, fee unit, and
   Bangkok-local transaction date;
4. computes a stable SHA-256 fingerprint from source system, spreadsheet ID,
   tab, and source transaction ID;
5. rejects duplicate fingerprints and formula-derived transaction price/FX;
6. replays quantities with asset-unit fees and rejects negative positions;
7. compares replayed quantities with `Holdings` as a reconciliation input;
8. writes valid rows only to `transaction_drafts` and ambiguous rows only to
   `transaction_import_errors`; and
9. writes zero confirmed `transactions`.

Before staging against Supabase, download the current XLSX and run from
`backend/`:

```bash
python -m app.services.portfolio_import.cli <current-15-tab-export.xlsx> \
  --spreadsheet-id 1MUZD_nevvmH3yx972Ep6o8pCRmsdd_IgzSzjD6TPCjw \
  --output <dry-run-report.json>
```

Only after reviewing that report should an authenticated operator set
`SUPABASE_ACCESS_TOKEN` and add `--persist-staging`. The token is verified and
its `sub` claim supplies row ownership; the command accepts no `user_id`.

For local development only, the CLI also supports:

```bash
ALLOW_DEV_OWNER_BYPASS=true
DEV_IMPORT_USER_EMAIL=<existing Supabase Auth user email>
```

This bypass does not disable ownership. It uses the backend service role to
resolve an existing Supabase Auth user and then stages rows under that user's
`auth.users.id`.
