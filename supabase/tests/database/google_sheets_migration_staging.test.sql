BEGIN;

CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;

SELECT plan(12);

SELECT has_column(
  'public', 'transaction_drafts', 'fee_unit',
  'staged drafts preserve fee units'
);
SELECT has_column(
  'public', 'transactions', 'fee_unit',
  'confirmed transactions preserve reviewed fee units'
);
SELECT col_type_is(
  'public', 'transaction_drafts', 'fee_unit', 'text',
  'draft fee unit is text'
);
SELECT col_type_is(
  'public', 'transactions', 'fee_unit', 'text',
  'transaction fee unit is text'
);
SELECT has_check(
  'public', 'transaction_drafts', 'transaction_drafts_fee_unit_valid',
  'draft fee unit values are constrained'
);
SELECT has_check(
  'public', 'transactions', 'transactions_fee_unit_valid',
  'transaction fee unit values are constrained'
);
SELECT has_index(
  'public', 'transaction_drafts',
  'idx_transaction_drafts_import_source_fingerprint_owner',
  'imported draft fingerprint index exists'
);
SELECT index_is_unique(
  'public', 'transaction_drafts',
  'idx_transaction_drafts_import_source_fingerprint_owner',
  'imported draft fingerprints are unique per owner'
);
SELECT ok(
  NOT has_table_privilege('anon', 'public.transaction_drafts', 'SELECT'),
  'anon cannot read staged drafts'
);
SELECT ok(
  NOT has_table_privilege('anon', 'public.transaction_import_errors', 'SELECT'),
  'anon cannot read staging errors'
);
SELECT ok(
  NOT has_table_privilege('authenticated', 'public.transactions', 'UPDATE'),
  'authenticated users cannot update confirmed transactions'
);
SELECT ok(
  NOT has_table_privilege('authenticated', 'public.transactions', 'DELETE'),
  'authenticated users cannot delete confirmed transactions'
);

SELECT * FROM finish();
ROLLBACK;
