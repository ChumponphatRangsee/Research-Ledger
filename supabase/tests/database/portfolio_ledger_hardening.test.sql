BEGIN;

CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SET search_path TO public, extensions;

SELECT plan(40);

SELECT ok(
  to_regprocedure('public.prevent_confirmed_transaction_draft_update()') IS NOT NULL,
  'confirmed-draft immutability trigger function exists'
);

SELECT is(
  (
    SELECT CASE WHEN prosecdef THEN 'definer' ELSE 'invoker' END
    FROM pg_proc
    WHERE oid = 'public.prevent_confirmed_transaction_draft_update()'::regprocedure
  ),
  'invoker',
  'confirmed-draft immutability function is SECURITY INVOKER'
);

SELECT ok(
  NOT has_function_privilege(
    'PUBLIC',
    'public.prevent_confirmed_transaction_draft_update()',
    'EXECUTE'
  ),
  'confirmed-draft immutability function is not public executable'
);

SELECT ok(
  NOT has_function_privilege(
    'anon',
    'public.prevent_confirmed_transaction_draft_update()',
    'EXECUTE'
  ),
  'anon cannot execute confirmed-draft immutability function'
);
SELECT ok(
  NOT has_function_privilege(
    'authenticated',
    'public.prevent_confirmed_transaction_draft_update()',
    'EXECUTE'
  ),
  'authenticated cannot execute confirmed-draft immutability function'
);
SELECT ok(
  NOT has_function_privilege(
    'service_role',
    'public.prevent_confirmed_transaction_draft_update()',
    'EXECUTE'
  ),
  'service role cannot execute confirmed-draft immutability function directly'
);

SELECT ok(
  NOT has_function_privilege(
    'anon',
    'public.validate_transaction_reversal()',
    'EXECUTE'
  ),
  'anon cannot execute reversal trigger function'
);
SELECT ok(
  NOT has_function_privilege(
    'authenticated',
    'public.validate_transaction_reversal()',
    'EXECUTE'
  ),
  'authenticated cannot execute reversal trigger function'
);
SELECT ok(
  NOT has_function_privilege(
    'service_role',
    'public.validate_transaction_reversal()',
    'EXECUTE'
  ),
  'service role cannot execute reversal trigger function directly'
);

SELECT ok(
  NOT has_function_privilege(
    'anon',
    'public.prevent_confirmed_transaction_mutation()',
    'EXECUTE'
  ),
  'anon cannot execute confirmed transaction immutability function'
);
SELECT ok(
  NOT has_function_privilege(
    'authenticated',
    'public.prevent_confirmed_transaction_mutation()',
    'EXECUTE'
  ),
  'authenticated cannot execute confirmed transaction immutability function'
);
SELECT ok(
  NOT has_function_privilege(
    'service_role',
    'public.prevent_confirmed_transaction_mutation()',
    'EXECUTE'
  ),
  'service role cannot execute confirmed transaction immutability function directly'
);

SELECT ok(
  NOT has_function_privilege('anon', 'public.set_updated_at()', 'EXECUTE'),
  'anon cannot execute updated-at trigger function'
);
SELECT ok(
  NOT has_function_privilege(
    'authenticated',
    'public.set_updated_at()',
    'EXECUTE'
  ),
  'authenticated cannot execute updated-at trigger function'
);
SELECT ok(
  NOT has_function_privilege(
    'service_role',
    'public.set_updated_at()',
    'EXECUTE'
  ),
  'service role cannot execute updated-at trigger function directly'
);

SELECT ok(
  EXISTS (
    SELECT 1
    FROM pg_trigger
    WHERE tgname = 'trg_transaction_drafts_prevent_confirmed_update'
      AND tgrelid = 'public.transaction_drafts'::regclass
      AND NOT tgisinternal
  ),
  'confirmed-draft immutability trigger exists'
);

SELECT ok(
  EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'transaction_drafts_id_user_id_import_batch_key'
      AND conrelid = 'public.transaction_drafts'::regclass
      AND contype = 'u'
  ),
  'transaction_drafts has unique owner/batch support key'
);

SELECT fk_ok(
  'public',
  'transaction_import_errors',
  ARRAY['transaction_draft_id', 'user_id', 'import_batch_id'],
  'public',
  'transaction_drafts',
  ARRAY['id', 'user_id', 'import_batch_id'],
  'import error draft reference is batch-aware'
);

SELECT has_index(
  'public', 'transaction_drafts', 'idx_transaction_drafts_account_owner_fk',
  'draft account FK covering index exists'
);
SELECT has_index(
  'public', 'transaction_drafts', 'idx_transaction_drafts_asset_owner_fk',
  'draft asset FK covering index exists'
);
SELECT has_index(
  'public', 'transaction_drafts', 'idx_transaction_drafts_batch_owner_fk',
  'draft batch FK covering index exists'
);
SELECT has_index(
  'public', 'transaction_drafts', 'idx_transaction_drafts_reversal_owner_fk',
  'draft reversal FK covering index exists'
);
SELECT has_index(
  'public', 'transactions', 'idx_transactions_account_owner_fk',
  'transaction account FK covering index exists'
);
SELECT has_index(
  'public', 'transactions', 'idx_transactions_asset_owner_fk',
  'transaction asset FK covering index exists'
);
SELECT has_index(
  'public', 'transactions', 'idx_transactions_confirmed_draft_owner_fk',
  'transaction confirmed-draft FK covering index exists'
);
SELECT has_index(
  'public', 'transactions', 'idx_transactions_reversal_owner_account_asset_fk',
  'transaction reversal FK covering index exists'
);
SELECT has_index(
  'public', 'transaction_import_errors',
  'idx_transaction_import_errors_batch_owner_fk',
  'import error batch FK covering index exists'
);
SELECT has_index(
  'public', 'transaction_import_errors',
  'idx_transaction_import_errors_draft_batch_owner_fk',
  'import error draft/batch FK covering index exists'
);

SELECT ok(
  (
    SELECT relrowsecurity
    FROM pg_class
    WHERE oid = 'public.market_data_snapshots'::regclass
  ),
  'market_data_snapshots keeps RLS enabled'
);

SELECT ok(
  EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'market_data_snapshots'
      AND policyname = 'market_data_snapshots_service_role_manage'
      AND cmd = 'ALL'
  ),
  'market_data_snapshots has explicit backend service-role policy'
);

SELECT ok(
  NOT has_table_privilege('anon', 'public.market_data_snapshots', 'SELECT'),
  'anon cannot select market data snapshots'
);
SELECT ok(
  NOT has_table_privilege('authenticated', 'public.market_data_snapshots', 'SELECT'),
  'authenticated cannot select market data snapshots'
);
SELECT ok(
  has_table_privilege('service_role', 'public.market_data_snapshots', 'SELECT'),
  'service role can select market data snapshots'
);
SELECT ok(
  has_table_privilege('service_role', 'public.market_data_snapshots', 'INSERT'),
  'service role can insert market data snapshots'
);
SELECT ok(
  has_table_privilege('service_role', 'public.market_data_snapshots', 'UPDATE'),
  'service role can update market data snapshots'
);
SELECT ok(
  has_table_privilege('service_role', 'public.market_data_snapshots', 'DELETE'),
  'service role can delete market data snapshots'
);

INSERT INTO auth.users (id)
VALUES
  ('30000000-0000-0000-0000-000000000001'),
  ('30000000-0000-0000-0000-000000000002');

INSERT INTO public.investment_accounts (id, user_id, name, account_type, currency)
VALUES (
  '31000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',
  'Hardening Brokerage',
  'BROKERAGE',
  'USD'
);

INSERT INTO public.assets (id, user_id, symbol, name, asset_type, currency)
VALUES (
  '32000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',
  'AAPL',
  'Apple',
  'STOCK',
  'USD'
);

INSERT INTO public.transaction_import_batches (
  id, user_id, source_type, source_filename, status
)
VALUES
  (
    '33000000-0000-0000-0000-000000000001',
    '30000000-0000-0000-0000-000000000001',
    'GOOGLE_SHEETS',
    'hardening-a.xlsx',
    'PENDING'
  ),
  (
    '33000000-0000-0000-0000-000000000002',
    '30000000-0000-0000-0000-000000000001',
    'GOOGLE_SHEETS',
    'hardening-b.xlsx',
    'PENDING'
  );

INSERT INTO public.transaction_drafts (
  id, user_id, investment_account_id, asset_id, import_batch_id,
  transaction_type, transaction_at, quantity, unit_price, currency,
  source_type, source_row_number
)
VALUES
  (
    '34000000-0000-0000-0000-000000000001',
    '30000000-0000-0000-0000-000000000001',
    '31000000-0000-0000-0000-000000000001',
    '32000000-0000-0000-0000-000000000001',
    '33000000-0000-0000-0000-000000000001',
    'BUY',
    '2026-02-01 10:00:00+00',
    2,
    100,
    'USD',
    'GOOGLE_SHEETS',
    1
  ),
  (
    '34000000-0000-0000-0000-000000000002',
    '30000000-0000-0000-0000-000000000001',
    '31000000-0000-0000-0000-000000000001',
    '32000000-0000-0000-0000-000000000001',
    '33000000-0000-0000-0000-000000000002',
    'BUY',
    '2026-02-02 10:00:00+00',
    1,
    101,
    'USD',
    'GOOGLE_SHEETS',
    1
  ),
  (
    '34000000-0000-0000-0000-000000000003',
    '30000000-0000-0000-0000-000000000001',
    '31000000-0000-0000-0000-000000000001',
    '32000000-0000-0000-0000-000000000001',
    '33000000-0000-0000-0000-000000000002',
    'BUY',
    '2026-02-03 10:00:00+00',
    1,
    102,
    'USD',
    'GOOGLE_SHEETS',
    2
  );

SELECT lives_ok(
  $$
    INSERT INTO public.transaction_import_errors (
      user_id, import_batch_id, transaction_draft_id,
      error_code, error_message
    )
    VALUES (
      '30000000-0000-0000-0000-000000000001',
      '33000000-0000-0000-0000-000000000001',
      '34000000-0000-0000-0000-000000000001',
      'INVALID_ROW',
      'Same-batch draft error'
    )
  $$,
  'import error may reference a same-owner, same-batch draft'
);

SELECT throws_ok(
  $$
    INSERT INTO public.transaction_import_errors (
      user_id, import_batch_id, transaction_draft_id,
      error_code, error_message
    )
    VALUES (
      '30000000-0000-0000-0000-000000000001',
      '33000000-0000-0000-0000-000000000002',
      '34000000-0000-0000-0000-000000000001',
      'INVALID_ROW',
      'Cross-batch draft error'
    )
  $$,
  '23503',
  NULL,
  'import error cannot reference a draft from another batch'
);

INSERT INTO public.transactions (
  id, user_id, investment_account_id, asset_id, confirmed_from_draft_id,
  transaction_type, transaction_at, quantity, unit_price, currency,
  source_type, source_fingerprint
)
VALUES (
  '35000000-0000-0000-0000-000000000001',
  '30000000-0000-0000-0000-000000000001',
  '31000000-0000-0000-0000-000000000001',
  '32000000-0000-0000-0000-000000000001',
  '34000000-0000-0000-0000-000000000001',
  'BUY',
  '2026-02-01 10:00:00+00',
  2,
  100,
  'USD',
  'GOOGLE_SHEETS',
  'hardening-confirmed-draft'
);

SELECT throws_ok(
  $$
    UPDATE public.transaction_drafts
    SET notes = 'mutated after confirmation'
    WHERE id = '34000000-0000-0000-0000-000000000001'
  $$,
  '55000',
  'Confirmed transaction drafts are immutable; append a correcting draft instead',
  'confirmed draft updates are blocked'
);

SELECT lives_ok(
  $$
    UPDATE public.transaction_drafts
    SET notes = 'still mutable'
    WHERE id = '34000000-0000-0000-0000-000000000003'
  $$,
  'unconfirmed drafts remain mutable'
);

SELECT * FROM finish();

ROLLBACK;
