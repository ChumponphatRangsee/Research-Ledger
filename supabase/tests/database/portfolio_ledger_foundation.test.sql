BEGIN;

CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SET search_path TO public, extensions;

SELECT plan(105);

-- Schema surface.
SELECT has_table('public', 'assets', 'assets exists');
SELECT has_table('public', 'investment_accounts', 'investment_accounts exists');
SELECT has_table('public', 'transaction_drafts', 'transaction_drafts exists');
SELECT has_table('public', 'transactions', 'transactions exists');
SELECT has_table('public', 'transaction_import_batches', 'transaction_import_batches exists');
SELECT has_table('public', 'transaction_import_errors', 'transaction_import_errors exists');

SELECT has_column('public', 'assets', 'user_id', 'assets.user_id exists');
SELECT has_column('public', 'assets', 'ticker_id', 'assets.ticker_id exists');
SELECT has_column('public', 'assets', 'asset_type', 'assets.asset_type exists');
SELECT has_column('public', 'assets', 'currency', 'assets.currency exists');
SELECT has_column('public', 'investment_accounts', 'account_type', 'account type exists');
SELECT has_column('public', 'transaction_drafts', 'import_batch_id', 'draft batch link exists');
SELECT has_column('public', 'transaction_drafts', 'raw_source_data', 'draft raw data exists');
SELECT has_column('public', 'transactions', 'ledger_sequence', 'ledger sequence exists');
SELECT has_column('public', 'transactions', 'confirmed_from_draft_id', 'confirmed draft link exists');
SELECT has_column('public', 'transactions', 'reversal_of_transaction_id', 'reversal link exists');
SELECT has_column('public', 'transactions', 'source_fingerprint', 'transaction fingerprint exists');
SELECT has_column('public', 'transaction_import_batches', 'status', 'batch status exists');
SELECT has_column('public', 'transaction_import_errors', 'source_row_number', 'error row number exists');
SELECT has_column('public', 'transaction_import_errors', 'error_code', 'structured error code exists');

SELECT fk_ok(
  'public', 'transaction_drafts', ARRAY['investment_account_id', 'user_id'],
  'public', 'investment_accounts', ARRAY['id', 'user_id'],
  'draft account reference is ownership-aware'
);
SELECT fk_ok(
  'public', 'transaction_drafts', ARRAY['asset_id', 'user_id'],
  'public', 'assets', ARRAY['id', 'user_id'],
  'draft asset reference is ownership-aware'
);
SELECT fk_ok(
  'public', 'transaction_drafts', ARRAY['import_batch_id', 'user_id'],
  'public', 'transaction_import_batches', ARRAY['id', 'user_id'],
  'draft batch reference is ownership-aware'
);
SELECT fk_ok(
  'public', 'transactions', ARRAY['investment_account_id', 'user_id'],
  'public', 'investment_accounts', ARRAY['id', 'user_id'],
  'confirmed account reference is ownership-aware'
);
SELECT fk_ok(
  'public', 'transactions', ARRAY['asset_id', 'user_id'],
  'public', 'assets', ARRAY['id', 'user_id'],
  'confirmed asset reference is ownership-aware'
);
SELECT fk_ok(
  'public', 'transactions', ARRAY['confirmed_from_draft_id', 'user_id'],
  'public', 'transaction_drafts', ARRAY['id', 'user_id'],
  'confirmed draft reference is ownership-aware'
);
SELECT fk_ok(
  'public', 'transactions',
  ARRAY[
    'reversal_of_transaction_id', 'user_id',
    'investment_account_id', 'asset_id'
  ],
  'public', 'transactions',
  ARRAY['id', 'user_id', 'investment_account_id', 'asset_id'],
  'reversal reference is ownership/account/asset-aware'
);
SELECT fk_ok(
  'public', 'transaction_import_errors', ARRAY['import_batch_id', 'user_id'],
  'public', 'transaction_import_batches', ARRAY['id', 'user_id'],
  'import error batch reference is ownership-aware'
);
SELECT fk_ok(
  'public', 'transaction_import_errors', ARRAY['transaction_draft_id', 'user_id'],
  'public', 'transaction_drafts', ARRAY['id', 'user_id'],
  'import error draft reference is ownership-aware'
);

SELECT has_index('public', 'assets', 'idx_assets_user_id', 'assets ownership index exists');
SELECT has_index(
  'public', 'investment_accounts', 'idx_investment_accounts_user_id',
  'account ownership index exists'
);
SELECT has_index(
  'public', 'transaction_drafts', 'idx_transaction_drafts_user_id',
  'draft ownership index exists'
);
SELECT has_index(
  'public', 'transactions', 'idx_transactions_user_id',
  'transaction ownership index exists'
);
SELECT has_index(
  'public', 'transaction_import_batches', 'idx_transaction_import_batches_user_id',
  'batch ownership index exists'
);
SELECT has_index(
  'public', 'transaction_import_errors', 'idx_transaction_import_errors_user_id',
  'error ownership index exists'
);
SELECT has_index(
  'public', 'transactions', 'idx_transactions_source_fingerprint_owner',
  'confirmed fingerprint uniqueness index exists'
);
SELECT has_index(
  'public', 'transactions', 'idx_transactions_original_reversed_once',
  'single reversal index exists'
);

-- Financial values remain exact numeric values, never floating point.
SELECT col_type_is('public', 'transaction_drafts', 'quantity', 'numeric(38,18)', 'draft quantity is numeric');
SELECT col_type_is('public', 'transaction_drafts', 'unit_price', 'numeric(38,18)', 'draft price is numeric');
SELECT col_type_is('public', 'transaction_drafts', 'gross_amount', 'numeric(38,18)', 'draft amount is numeric');
SELECT col_type_is('public', 'transaction_drafts', 'fee_amount', 'numeric(38,18)', 'draft fee is numeric');
SELECT col_type_is('public', 'transaction_drafts', 'fx_rate_to_thb', 'numeric(38,18)', 'draft FX is numeric');
SELECT col_type_is('public', 'transactions', 'quantity', 'numeric(38,18)', 'transaction quantity is numeric');
SELECT col_type_is('public', 'transactions', 'unit_price', 'numeric(38,18)', 'transaction price is numeric');
SELECT col_type_is('public', 'transactions', 'gross_amount', 'numeric(38,18)', 'transaction amount is numeric');
SELECT col_type_is('public', 'transactions', 'fee_amount', 'numeric(38,18)', 'transaction fee is numeric');
SELECT col_type_is('public', 'transactions', 'fx_rate_to_thb', 'numeric(38,18)', 'transaction FX is numeric');

-- RLS and privilege boundaries.
SELECT results_eq(
  $$
    SELECT relname
    FROM pg_class
    WHERE oid IN (
      'public.assets'::regclass,
      'public.investment_accounts'::regclass,
      'public.transaction_drafts'::regclass,
      'public.transactions'::regclass,
      'public.transaction_import_batches'::regclass,
      'public.transaction_import_errors'::regclass
    )
      AND relrowsecurity
    ORDER BY relname
  $$,
  $$
    VALUES
      ('assets'::name),
      ('investment_accounts'::name),
      ('transaction_drafts'::name),
      ('transaction_import_batches'::name),
      ('transaction_import_errors'::name),
      ('transactions'::name)
  $$,
  'RLS is enabled on every new table'
);

SELECT ok(NOT has_table_privilege('anon', 'public.assets', 'SELECT'), 'anon cannot select assets');
SELECT ok(NOT has_table_privilege('anon', 'public.investment_accounts', 'SELECT'), 'anon cannot select accounts');
SELECT ok(NOT has_table_privilege('anon', 'public.transaction_drafts', 'SELECT'), 'anon cannot select drafts');
SELECT ok(NOT has_table_privilege('anon', 'public.transactions', 'SELECT'), 'anon cannot select transactions');
SELECT ok(NOT has_table_privilege('anon', 'public.transaction_import_batches', 'SELECT'), 'anon cannot select batches');
SELECT ok(NOT has_table_privilege('anon', 'public.transaction_import_errors', 'SELECT'), 'anon cannot select errors');
SELECT ok(has_table_privilege('authenticated', 'public.transaction_drafts', 'UPDATE'), 'authenticated may update drafts');
SELECT ok(has_table_privilege('authenticated', 'public.transaction_drafts', 'DELETE'), 'authenticated may delete drafts');
SELECT ok(NOT has_table_privilege('authenticated', 'public.transactions', 'INSERT'), 'authenticated cannot confirm directly');
SELECT ok(NOT has_table_privilege('authenticated', 'public.transactions', 'UPDATE'), 'authenticated cannot update confirmed rows');
SELECT ok(NOT has_table_privilege('authenticated', 'public.transactions', 'DELETE'), 'authenticated cannot delete confirmed rows');
SELECT ok(has_table_privilege('service_role', 'public.transactions', 'INSERT'), 'service role may confirm in a future backend workflow');
SELECT ok(NOT has_table_privilege('service_role', 'public.transactions', 'UPDATE'), 'service role cannot update confirmed rows');
SELECT ok(NOT has_table_privilege('service_role', 'public.transactions', 'DELETE'), 'service role cannot delete confirmed rows');

SELECT is(
  (
    SELECT count(*)::INTEGER
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'transactions'
      AND cmd IN ('UPDATE', 'DELETE')
  ),
  0,
  'transactions has no update or delete RLS policy'
);

-- Preserve the existing screener and paper-holding objects exactly.
SELECT has_table('public', 'tickers', 'legacy tickers remains present');
SELECT has_table('public', 'portfolios', 'legacy portfolios remains present');
SELECT columns_are(
  'public',
  'tickers',
  ARRAY[
    'id', 'symbol', 'name', 'sector', 'industry', 'exchange', 'market_cap',
    'currency', 'last_screened_at', 'metadata', 'created_at', 'updated_at'
  ],
  'tickers columns remain unchanged'
);
SELECT columns_are(
  'public',
  'portfolios',
  ARRAY[
    'id', 'user_id', 'ticker_id', 'approved_from_inbox_id', 'shares',
    'cost_basis', 'avg_cost_per_share', 'status', 'notes', 'opened_at',
    'closed_at', 'created_at', 'updated_at'
  ],
  'portfolios columns remain unchanged'
);

-- Fixed users and owner-scoped parent rows used by the behavioral tests.
RESET ROLE;
INSERT INTO auth.users (id)
VALUES
  ('10000000-0000-0000-0000-000000000001'),
  ('20000000-0000-0000-0000-000000000002');

INSERT INTO public.investment_accounts (id, user_id, name, account_type, currency)
VALUES
  (
    '11000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    'User A Brokerage',
    'BROKERAGE',
    'USD'
  ),
  (
    '22000000-0000-0000-0000-000000000002',
    '20000000-0000-0000-0000-000000000002',
    'User B Exchange',
    'CRYPTO_EXCHANGE',
    'USD'
  );

INSERT INTO public.assets (id, user_id, symbol, name, asset_type, currency)
VALUES
  (
    '12000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    'MSFT',
    'Microsoft',
    'STOCK',
    'USD'
  ),
  (
    '23000000-0000-0000-0000-000000000002',
    '20000000-0000-0000-0000-000000000002',
    'BTC',
    'Bitcoin',
    'CRYPTO',
    'USD'
  );

INSERT INTO public.transaction_import_batches (
  id, user_id, source_type, source_filename, status
)
VALUES
  (
    '13000000-0000-0000-0000-000000000001',
    '10000000-0000-0000-0000-000000000001',
    'GOOGLE_SHEETS',
    'user-a.xlsx',
    'PENDING'
  ),
  (
    '24000000-0000-0000-0000-000000000002',
    '20000000-0000-0000-0000-000000000002',
    'GOOGLE_SHEETS',
    'user-b.xlsx',
    'PENDING'
  );

-- Authenticated User A can manage only their own draft rows.
SET LOCAL ROLE authenticated;
SELECT set_config(
  'request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000001","role":"authenticated"}',
  true
);

SELECT lives_ok(
  $$
    INSERT INTO public.transaction_drafts (
      id, investment_account_id, asset_id, import_batch_id,
      transaction_type, transaction_at, quantity, unit_price, currency,
      fx_rate_to_thb, source_type, source_row_number
    )
    VALUES (
      '14000000-0000-0000-0000-000000000001',
      '11000000-0000-0000-0000-000000000001',
      '12000000-0000-0000-0000-000000000001',
      '13000000-0000-0000-0000-000000000001',
      'BUY',
      '2026-01-02 10:00:00+00',
      1.250000000000000001,
      400.123456789012345678,
      'USD',
      35.500000000000000000,
      'MANUAL',
      1
    )
  $$,
  'User A can create an own draft with auth-derived ownership'
);

SELECT is(
  (
    SELECT user_id
    FROM public.transaction_drafts
    WHERE id = '14000000-0000-0000-0000-000000000001'
  ),
  '10000000-0000-0000-0000-000000000001'::UUID,
  'draft ownership defaults from auth.uid()'
);

SELECT lives_ok(
  $$ UPDATE public.transaction_drafts
     SET notes = 'reviewed'
     WHERE id = '14000000-0000-0000-0000-000000000001' $$,
  'User A can update an own draft'
);

SELECT is(
  (
    SELECT notes
    FROM public.transaction_drafts
    WHERE id = '14000000-0000-0000-0000-000000000001'
  ),
  'reviewed',
  'own draft update persists'
);

SELECT lives_ok(
  $$
    INSERT INTO public.transaction_drafts (
      id, investment_account_id, asset_id, transaction_type,
      transaction_at, quantity, unit_price, currency, source_type
    )
    VALUES (
      '15000000-0000-0000-0000-000000000001',
      '11000000-0000-0000-0000-000000000001',
      '12000000-0000-0000-0000-000000000001',
      'BUY',
      '2026-01-03 10:00:00+00',
      1,
      401,
      'USD',
      'MANUAL'
    )
  $$,
  'User A can create a deletable own draft'
);

SELECT lives_ok(
  $$ DELETE FROM public.transaction_drafts
     WHERE id = '15000000-0000-0000-0000-000000000001' $$,
  'User A can delete an own unconfirmed draft'
);

SELECT is(
  (
    SELECT count(*)::INTEGER
    FROM public.transaction_drafts
    WHERE id = '15000000-0000-0000-0000-000000000001'
  ),
  0,
  'deleted own draft is gone'
);

SELECT throws_ok(
  $$
    INSERT INTO public.transaction_drafts (
      user_id, investment_account_id, asset_id, transaction_type,
      transaction_at, quantity, unit_price, currency, source_type
    )
    VALUES (
      '20000000-0000-0000-0000-000000000002',
      '22000000-0000-0000-0000-000000000002',
      '23000000-0000-0000-0000-000000000002',
      'BUY',
      '2026-01-02 10:00:00+00',
      1,
      1,
      'USD',
      'MANUAL'
    )
  $$,
  '42501',
  NULL,
  'User A cannot spoof User B ownership'
);

SELECT is(
  (
    SELECT count(*)::INTEGER
    FROM public.investment_accounts
    WHERE user_id = '20000000-0000-0000-0000-000000000002'
  ),
  0,
  'User A cannot read User B accounts'
);

SELECT is(
  (
    SELECT count(*)::INTEGER
    FROM public.transaction_import_batches
    WHERE user_id = '20000000-0000-0000-0000-000000000002'
  ),
  0,
  'User A cannot read User B batches'
);

SELECT is(
  (
    WITH changed AS (
      UPDATE public.investment_accounts
      SET name = 'Compromised'
      WHERE id = '22000000-0000-0000-0000-000000000002'
      RETURNING 1
    )
    SELECT count(*)::INTEGER FROM changed
  ),
  0,
  'User A cannot mutate User B accounts'
);

RESET ROLE;

-- Composite foreign keys reject cross-owner references even when RLS is bypassed.
SELECT throws_ok(
  $$
    INSERT INTO public.transaction_drafts (
      user_id, investment_account_id, asset_id, transaction_type,
      transaction_at, quantity, unit_price, currency, source_type
    )
    VALUES (
      '10000000-0000-0000-0000-000000000001',
      '22000000-0000-0000-0000-000000000002',
      '12000000-0000-0000-0000-000000000001',
      'BUY', now(), 1, 1, 'USD', 'MANUAL'
    )
  $$,
  '23503',
  NULL,
  'cross-owner draft account reference fails'
);

SELECT throws_ok(
  $$
    INSERT INTO public.transaction_drafts (
      user_id, investment_account_id, asset_id, transaction_type,
      transaction_at, quantity, unit_price, currency, source_type
    )
    VALUES (
      '10000000-0000-0000-0000-000000000001',
      '11000000-0000-0000-0000-000000000001',
      '23000000-0000-0000-0000-000000000002',
      'BUY', now(), 1, 1, 'USD', 'MANUAL'
    )
  $$,
  '23503',
  NULL,
  'cross-owner draft asset reference fails'
);

SELECT throws_ok(
  $$
    INSERT INTO public.transaction_drafts (
      user_id, investment_account_id, asset_id, import_batch_id,
      transaction_type, transaction_at, quantity, unit_price, currency, source_type
    )
    VALUES (
      '10000000-0000-0000-0000-000000000001',
      '11000000-0000-0000-0000-000000000001',
      '12000000-0000-0000-0000-000000000001',
      '24000000-0000-0000-0000-000000000002',
      'BUY', now(), 1, 1, 'USD', 'MANUAL'
    )
  $$,
  '23503',
  NULL,
  'cross-owner draft batch reference fails'
);

SELECT throws_ok(
  $$
    INSERT INTO public.transaction_import_errors (
      user_id, import_batch_id, transaction_draft_id,
      error_code, error_message
    )
    VALUES (
      '20000000-0000-0000-0000-000000000002',
      '24000000-0000-0000-0000-000000000002',
      '14000000-0000-0000-0000-000000000001',
      'INVALID_ROW',
      'Cross-owner draft'
    )
  $$,
  '23503',
  NULL,
  'cross-owner import-error draft reference fails'
);

-- Type and value checks.
SELECT throws_ok(
  $$
    INSERT INTO public.assets (user_id, symbol, name, asset_type, currency)
    VALUES (
      '10000000-0000-0000-0000-000000000001',
      'INVALID',
      'Invalid',
      'OPTION',
      'USD'
    )
  $$,
  '23514',
  NULL,
  'invalid asset type fails'
);

SELECT lives_ok(
  $$
    INSERT INTO public.assets (user_id, symbol, name, asset_type, currency)
    VALUES (
      '10000000-0000-0000-0000-000000000001',
      'USDT',
      'Tether',
      'CRYPTO',
      'USDT'
    )
  $$,
  'normalized crypto currency codes longer than three characters are supported'
);

SELECT throws_ok(
  $$
    INSERT INTO public.assets (user_id, symbol, name, asset_type, currency)
    VALUES (
      '10000000-0000-0000-0000-000000000001',
      'LOWER',
      'Lowercase currency',
      'OTHER',
      'usd'
    )
  $$,
  '23514',
  NULL,
  'lowercase currency codes fail'
);

SELECT throws_ok(
  $$
    INSERT INTO public.transactions (
      user_id, investment_account_id, asset_id, transaction_type,
      transaction_at, quantity, unit_price, currency, source_type
    )
    VALUES (
      '10000000-0000-0000-0000-000000000001',
      '11000000-0000-0000-0000-000000000001',
      '12000000-0000-0000-0000-000000000001',
      'SPLIT', now(), 1, 1, 'USD', 'MANUAL'
    )
  $$,
  '23514',
  NULL,
  'invalid transaction type fails'
);

SELECT throws_ok(
  $$
    INSERT INTO public.transactions (
      user_id, investment_account_id, asset_id, transaction_type,
      transaction_at, quantity, unit_price, fee_amount, currency,
      fx_rate_to_thb, source_type
    )
    VALUES (
      '10000000-0000-0000-0000-000000000001',
      '11000000-0000-0000-0000-000000000001',
      '12000000-0000-0000-0000-000000000001',
      'BUY', now(), 1, 1, -0.01, 'USD', 35, 'MANUAL'
    )
  $$,
  '23514',
  NULL,
  'negative confirmed fee fails'
);

SELECT throws_ok(
  $$
    INSERT INTO public.transactions (
      user_id, investment_account_id, asset_id, transaction_type,
      transaction_at, quantity, unit_price, currency, fx_rate_to_thb, source_type
    )
    VALUES (
      '10000000-0000-0000-0000-000000000001',
      '11000000-0000-0000-0000-000000000001',
      '12000000-0000-0000-0000-000000000001',
      'BUY', now(), 1, 1, 'USD', 0, 'MANUAL'
    )
  $$,
  '23514',
  NULL,
  'non-positive FX fails'
);

SELECT throws_ok(
  $$
    INSERT INTO public.transactions (
      user_id, investment_account_id, asset_id, transaction_type,
      transaction_at, currency, source_type
    )
    VALUES (
      '10000000-0000-0000-0000-000000000001',
      '11000000-0000-0000-0000-000000000001',
      '12000000-0000-0000-0000-000000000001',
      'BUY', now(), 'USD', 'MANUAL'
    )
  $$,
  '23514',
  NULL,
  'confirmed BUY requires quantity and unit price'
);

-- Confirmed-source deduplication and immutability.
INSERT INTO public.transactions (
  id, user_id, investment_account_id, asset_id, confirmed_from_draft_id,
  transaction_type, transaction_at, quantity, unit_price, fee_amount,
  currency, fx_rate_to_thb, source_type, source_fingerprint
)
VALUES (
  '16000000-0000-0000-0000-000000000001',
  '10000000-0000-0000-0000-000000000001',
  '11000000-0000-0000-0000-000000000001',
  '12000000-0000-0000-0000-000000000001',
  '14000000-0000-0000-0000-000000000001',
  'BUY',
  '2026-01-02 10:00:00+00',
  1.250000000000000001,
  400.123456789012345678,
  0.500000000000000000,
  'USD',
  35.500000000000000000,
  'GOOGLE_SHEETS',
  'owner-a-row-1'
);

SELECT throws_ok(
  $$
    INSERT INTO public.transactions (
      user_id, investment_account_id, asset_id, transaction_type,
      transaction_at, quantity, unit_price, currency, source_type,
      source_fingerprint
    )
    VALUES (
      '10000000-0000-0000-0000-000000000001',
      '11000000-0000-0000-0000-000000000001',
      '12000000-0000-0000-0000-000000000001',
      'BUY', now(), 1, 1, 'USD', 'MANUAL', 'owner-a-row-1'
    )
  $$,
  '23505',
  NULL,
  'duplicate confirmed fingerprint for one owner fails'
);

SELECT lives_ok(
  $$
    INSERT INTO public.transactions (
      user_id, investment_account_id, asset_id, transaction_type,
      transaction_at, quantity, unit_price, currency, source_type,
      source_fingerprint
    )
    VALUES (
      '20000000-0000-0000-0000-000000000002',
      '22000000-0000-0000-0000-000000000002',
      '23000000-0000-0000-0000-000000000002',
      'BUY', '2026-01-02 10:00:00+00', 1, 100000, 'USD', 'MANUAL',
      'owner-a-row-1'
    )
  $$,
  'the same fingerprint is allowed for a different owner'
);

SELECT lives_ok(
  $$
    INSERT INTO public.transactions (
      user_id, investment_account_id, asset_id, transaction_type,
      transaction_at, quantity, unit_price, currency, source_type
    )
    VALUES
      (
        '10000000-0000-0000-0000-000000000001',
        '11000000-0000-0000-0000-000000000001',
        '12000000-0000-0000-0000-000000000001',
        'BUY', '2026-01-04 10:00:00+00', 1, 410, 'USD', 'MANUAL'
      ),
      (
        '10000000-0000-0000-0000-000000000001',
        '11000000-0000-0000-0000-000000000001',
        '12000000-0000-0000-0000-000000000001',
        'BUY', '2026-01-05 10:00:00+00', 1, 420, 'USD', 'MANUAL'
      )
  $$,
  'multiple manual confirmed rows may have null fingerprints'
);

SELECT throws_ok(
  $$ UPDATE public.transactions
     SET notes = 'forbidden'
     WHERE id = '16000000-0000-0000-0000-000000000001' $$,
  '55000',
  'Confirmed transactions are immutable; append a linked reversal instead',
  'database trigger rejects confirmed updates even for migration owner'
);

SELECT throws_ok(
  $$ DELETE FROM public.transactions
     WHERE id = '16000000-0000-0000-0000-000000000001' $$,
  '55000',
  'Confirmed transactions are immutable; append a linked reversal instead',
  'database trigger rejects confirmed deletes even for migration owner'
);

-- Reversal relationships and copied financial payload.
SELECT lives_ok(
  $$
    INSERT INTO public.transactions (
      id, user_id, investment_account_id, asset_id, reversal_of_transaction_id,
      transaction_type, transaction_at, quantity, unit_price, fee_amount,
      currency, fx_rate_to_thb, source_type, source_fingerprint
    )
    VALUES (
      '17000000-0000-0000-0000-000000000001',
      '10000000-0000-0000-0000-000000000001',
      '11000000-0000-0000-0000-000000000001',
      '12000000-0000-0000-0000-000000000001',
      '16000000-0000-0000-0000-000000000001',
      'REVERSAL',
      '2026-01-03 10:00:00+00',
      1.250000000000000001,
      400.123456789012345678,
      0.500000000000000000,
      'USD',
      35.500000000000000000,
      'MANUAL',
      'owner-a-row-1-reversal'
    )
  $$,
  'valid same-owner reversal succeeds'
);

SELECT throws_ok(
  $$
    INSERT INTO public.transactions (
      user_id, investment_account_id, asset_id, reversal_of_transaction_id,
      transaction_type, transaction_at, quantity, unit_price, fee_amount,
      currency, fx_rate_to_thb, source_type
    )
    VALUES (
      '10000000-0000-0000-0000-000000000001',
      '11000000-0000-0000-0000-000000000001',
      '12000000-0000-0000-0000-000000000001',
      '16000000-0000-0000-0000-000000000001',
      'REVERSAL', now(),
      1.250000000000000001, 400.123456789012345678,
      0.500000000000000000, 'USD', 35.500000000000000000, 'MANUAL'
    )
  $$,
  '23505',
  NULL,
  'a second reversal of one original fails'
);

SELECT throws_ok(
  $$
    INSERT INTO public.transactions (
      user_id, investment_account_id, asset_id, reversal_of_transaction_id,
      transaction_type, transaction_at, quantity, unit_price, fee_amount,
      currency, fx_rate_to_thb, source_type
    )
    VALUES (
      '20000000-0000-0000-0000-000000000002',
      '22000000-0000-0000-0000-000000000002',
      '23000000-0000-0000-0000-000000000002',
      '16000000-0000-0000-0000-000000000001',
      'REVERSAL', now(),
      1.250000000000000001, 400.123456789012345678,
      0.500000000000000000, 'USD', 35.500000000000000000, 'MANUAL'
    )
  $$,
  '23514',
  'Reversal must reference a same-owner, same-account, same-asset transaction',
  'cross-owner reversal fails'
);

SELECT throws_ok(
  $$
    INSERT INTO public.transactions (
      user_id, investment_account_id, asset_id, reversal_of_transaction_id,
      transaction_type, transaction_at, quantity, unit_price, fee_amount,
      currency, fx_rate_to_thb, source_type
    )
    VALUES (
      '10000000-0000-0000-0000-000000000001',
      '11000000-0000-0000-0000-000000000001',
      '12000000-0000-0000-0000-000000000001',
      '17000000-0000-0000-0000-000000000001',
      'REVERSAL', now(),
      1.250000000000000001, 400.123456789012345678,
      0.500000000000000000, 'USD', 35.500000000000000000, 'MANUAL'
    )
  $$,
  '23514',
  'A reversal cannot reverse another reversal',
  'reversing a reversal fails'
);

SELECT throws_ok(
  $$
    INSERT INTO public.transactions (
      user_id, investment_account_id, asset_id, reversal_of_transaction_id,
      transaction_type, transaction_at, quantity, unit_price, fee_amount,
      currency, fx_rate_to_thb, source_type
    )
    VALUES (
      '10000000-0000-0000-0000-000000000001',
      '11000000-0000-0000-0000-000000000001',
      '12000000-0000-0000-0000-000000000001',
      '16000000-0000-0000-0000-000000000001',
      'REVERSAL', '2026-01-01 10:00:00+00',
      1.250000000000000001, 400.123456789012345678,
      0.500000000000000000, 'USD', 35.500000000000000000, 'MANUAL'
    )
  $$,
  '23514',
  'A reversal cannot precede its original transaction',
  'reversal timestamp must follow the original'
);

SELECT throws_ok(
  $$
    INSERT INTO public.transactions (
      user_id, investment_account_id, asset_id, reversal_of_transaction_id,
      transaction_type, transaction_at, quantity, unit_price, fee_amount,
      currency, fx_rate_to_thb, source_type
    )
    VALUES (
      '10000000-0000-0000-0000-000000000001',
      '11000000-0000-0000-0000-000000000001',
      '12000000-0000-0000-0000-000000000001',
      '16000000-0000-0000-0000-000000000001',
      'REVERSAL', now(),
      2, 400.123456789012345678,
      0.500000000000000000, 'USD', 35.500000000000000000, 'MANUAL'
    )
  $$,
  '23514',
  'A reversal must copy the original transaction financial values',
  'reversal with mismatched financial values fails'
);

-- RLS on confirmed rows, including no authenticated mutation path.
SET LOCAL ROLE authenticated;
SELECT set_config(
  'request.jwt.claims',
  '{"sub":"10000000-0000-0000-0000-000000000001","role":"authenticated"}',
  true
);

SELECT is(
  (
    SELECT count(*)::INTEGER
    FROM public.transactions
    WHERE user_id = '10000000-0000-0000-0000-000000000001'
  ),
  4,
  'User A reads only their confirmed rows'
);

SELECT is(
  (
    SELECT count(*)::INTEGER
    FROM public.transactions
    WHERE user_id = '20000000-0000-0000-0000-000000000002'
  ),
  0,
  'User A cannot read User B confirmed rows'
);

SELECT throws_ok(
  $$ UPDATE public.transactions SET notes = 'forbidden' $$,
  '42501',
  NULL,
  'authenticated owner has no confirmed UPDATE privilege'
);

SELECT throws_ok(
  $$ DELETE FROM public.transactions $$,
  '42501',
  NULL,
  'authenticated owner has no confirmed DELETE privilege'
);

RESET ROLE;
SET LOCAL ROLE anon;
SELECT throws_ok(
  $$ SELECT count(*) FROM public.assets $$,
  '42501',
  NULL,
  'anonymous table access is denied'
);

RESET ROLE;
SELECT * FROM finish();
ROLLBACK;
