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

The export action completed through authenticated Google Drive on 2026-08-07.
The connector returned a protected file reference rather than a workspace-local
binary, so the staging CLI must still be run against the downloaded XLSX before
any database persistence. No source workbook or private access token is stored
in Git.

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
