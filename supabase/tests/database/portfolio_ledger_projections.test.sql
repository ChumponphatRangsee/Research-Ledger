BEGIN;

CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SET search_path TO public, extensions;

SELECT plan(36);

SELECT has_table(
  'public',
  'portfolio_position_projections',
  'portfolio position projection table exists'
);
SELECT has_view('public', 'portfolio_positions', 'portfolio positions view exists');
SELECT has_view('public', 'portfolio_summary', 'portfolio summary view exists');

SELECT ok(
  to_regprocedure('public.replace_portfolio_position_projections(uuid, jsonb)') IS NOT NULL,
  'projection replacement RPC exists'
);

SELECT ok(
  (
    SELECT relrowsecurity
    FROM pg_class
    WHERE oid = 'public.portfolio_position_projections'::regclass
  ),
  'projection table has RLS enabled'
);

SELECT is(
  (
    SELECT CASE WHEN prosecdef THEN 'definer' ELSE 'invoker' END
    FROM pg_proc
    WHERE oid = 'public.replace_portfolio_position_projections(uuid, jsonb)'::regprocedure
  ),
  'invoker',
  'projection replacement RPC is SECURITY INVOKER'
);

SELECT ok(
  NOT has_function_privilege(
    'PUBLIC',
    'public.replace_portfolio_position_projections(uuid, jsonb)',
    'EXECUTE'
  ),
  'projection replacement RPC is not public executable'
);
SELECT ok(
  NOT has_function_privilege(
    'anon',
    'public.replace_portfolio_position_projections(uuid, jsonb)',
    'EXECUTE'
  ),
  'anon cannot execute projection replacement RPC'
);
SELECT ok(
  NOT has_function_privilege(
    'authenticated',
    'public.replace_portfolio_position_projections(uuid, jsonb)',
    'EXECUTE'
  ),
  'authenticated clients cannot execute projection replacement RPC'
);
SELECT ok(
  has_function_privilege(
    'service_role',
    'public.replace_portfolio_position_projections(uuid, jsonb)',
    'EXECUTE'
  ),
  'service role can execute projection replacement RPC'
);

SELECT ok(
  has_table_privilege(
    'authenticated',
    'public.portfolio_position_projections',
    'SELECT'
  ),
  'authenticated users can select own projection rows'
);
SELECT ok(
  NOT has_table_privilege(
    'authenticated',
    'public.portfolio_position_projections',
    'INSERT'
  ),
  'authenticated users cannot insert projection rows'
);
SELECT ok(
  has_table_privilege(
    'service_role',
    'public.portfolio_position_projections',
    'INSERT'
  ),
  'service role can replace projection rows'
);
SELECT ok(
  NOT has_table_privilege('anon', 'public.portfolio_positions', 'SELECT'),
  'anon cannot select portfolio positions view'
);
SELECT ok(
  has_table_privilege('authenticated', 'public.portfolio_positions', 'SELECT'),
  'authenticated users can select portfolio positions view'
);
SELECT ok(
  EXISTS (
    SELECT 1
    FROM pg_class
    WHERE oid = 'public.portfolio_positions'::regclass
      AND reloptions @> ARRAY['security_invoker=true']
  ),
  'portfolio positions view is security_invoker'
);
SELECT ok(
  EXISTS (
    SELECT 1
    FROM pg_class
    WHERE oid = 'public.portfolio_summary'::regclass
      AND reloptions @> ARRAY['security_invoker=true']
  ),
  'portfolio summary view is security_invoker'
);

SELECT fk_ok(
  'public',
  'portfolio_position_projections',
  ARRAY['investment_account_id', 'user_id'],
  'public',
  'investment_accounts',
  ARRAY['id', 'user_id'],
  'projection account reference is ownership-aware'
);
SELECT fk_ok(
  'public',
  'portfolio_position_projections',
  ARRAY['asset_id', 'user_id'],
  'public',
  'assets',
  ARRAY['id', 'user_id'],
  'projection asset reference is ownership-aware'
);

SELECT col_type_is(
  'public',
  'portfolio_position_projections',
  'quantity',
  'numeric(38,18)',
  'projection quantity is exact numeric'
);
SELECT col_type_is(
  'public',
  'portfolio_position_projections',
  'cost_basis_thb',
  'numeric(38,18)',
  'projection cost basis is exact numeric'
);
SELECT col_type_is(
  'public',
  'portfolio_position_projections',
  'realized_pnl_thb',
  'numeric(38,18)',
  'projection realized P&L is exact numeric'
);

INSERT INTO auth.users (id)
VALUES
  ('40000000-0000-0000-0000-000000000001'),
  ('40000000-0000-0000-0000-000000000002');

INSERT INTO public.investment_accounts (id, user_id, name, account_type, currency)
VALUES
  (
    '41000000-0000-0000-0000-000000000001',
    '40000000-0000-0000-0000-000000000001',
    'Projection Brokerage A',
    'BROKERAGE',
    'USD'
  ),
  (
    '41000000-0000-0000-0000-000000000002',
    '40000000-0000-0000-0000-000000000002',
    'Projection Brokerage B',
    'BROKERAGE',
    'USD'
  );

INSERT INTO public.assets (id, user_id, symbol, name, asset_type, currency)
VALUES
  (
    '42000000-0000-0000-0000-000000000001',
    '40000000-0000-0000-0000-000000000001',
    'MSFT',
    'Microsoft',
    'STOCK',
    'USD'
  ),
  (
    '42000000-0000-0000-0000-000000000002',
    '40000000-0000-0000-0000-000000000002',
    'NVDA',
    'Nvidia',
    'STOCK',
    'USD'
  );

SET LOCAL ROLE service_role;

SELECT lives_ok(
  $$
    SELECT public.replace_portfolio_position_projections(
      '40000000-0000-0000-0000-000000000001',
      '[
        {
          "investment_account_id": "41000000-0000-0000-0000-000000000001",
          "asset_id": "42000000-0000-0000-0000-000000000001",
          "as_of_transaction_at": "2026-01-02T12:34:56Z",
          "as_of_ledger_sequence": "42",
          "source_transaction_count": "3",
          "source_metadata": {
            "calculation": "weighted_average_cost_replay",
            "source": "confirmed_transactions"
          },
          "quantity": "2",
          "cost_basis_thb": "7035",
          "weighted_average_cost_thb": "3517.5",
          "realized_pnl_thb": "150",
          "income_thb": "25",
          "fees_thb": "35",
          "cash_flow_thb": "-6885",
          "market_value_thb": "9000",
          "unrealized_pnl_thb": "1965",
          "allocation_pct": "100"
        }
      ]'::jsonb
    )
  $$,
  'service role can replace User A projection rows'
);

SELECT lives_ok(
  $$
    SELECT public.replace_portfolio_position_projections(
      '40000000-0000-0000-0000-000000000002',
      '[
        {
          "investment_account_id": "41000000-0000-0000-0000-000000000002",
          "asset_id": "42000000-0000-0000-0000-000000000002",
          "quantity": "1",
          "cost_basis_thb": "3500",
          "weighted_average_cost_thb": "3500",
          "realized_pnl_thb": "0",
          "income_thb": "0",
          "fees_thb": "0",
          "cash_flow_thb": "-3500",
          "market_value_thb": "4000",
          "unrealized_pnl_thb": "500",
          "allocation_pct": "100"
        }
      ]'::jsonb
    )
  $$,
  'service role can replace User B projection rows'
);

RESET ROLE;

SELECT is(
  (
    SELECT count(*)::INTEGER
    FROM public.portfolio_position_projections
    WHERE user_id = '40000000-0000-0000-0000-000000000001'
  ),
  1,
  'projection replacement stores User A rows'
);

SELECT results_eq(
  $$
    SELECT
      as_of_transaction_at,
      as_of_ledger_sequence,
      source_transaction_count,
      source_metadata
    FROM public.portfolio_position_projections
    WHERE user_id = '40000000-0000-0000-0000-000000000001'
  $$,
  $$
    VALUES (
      '2026-01-02T12:34:56Z'::TIMESTAMPTZ,
      42::BIGINT,
      3::BIGINT,
      jsonb_build_object(
        'calculation',
        'weighted_average_cost_replay',
        'source',
        'confirmed_transactions'
      )
    )
  $$,
  'projection replacement persists deterministic replay metadata'
);

SET LOCAL ROLE authenticated;
SELECT set_config(
  'request.jwt.claims',
  '{"sub":"40000000-0000-0000-0000-000000000001","role":"authenticated"}',
  true
);

SELECT results_eq(
  $$
    SELECT asset_symbol, quantity, cost_basis_thb, weighted_average_cost_thb
    FROM public.portfolio_positions
    ORDER BY asset_symbol
  $$,
  $$
    VALUES (
      'MSFT'::TEXT,
      2.000000000000000000::NUMERIC,
      7035.000000000000000000::NUMERIC,
      3517.500000000000000000::NUMERIC
    )
  $$,
  'User A reads only own projected position through security-invoker view'
);

SELECT is(
  (
    SELECT count(*)::INTEGER
    FROM public.portfolio_positions
    WHERE asset_symbol = 'NVDA'
  ),
  0,
  'User A cannot read User B projected position through view'
);

SELECT results_eq(
  $$
    SELECT
      total_cost_basis_thb,
      total_realized_pnl_thb,
      total_income_thb,
      total_market_value_thb
    FROM public.portfolio_summary
  $$,
  $$
    VALUES (
      7035.000000000000000000::NUMERIC,
      150.000000000000000000::NUMERIC,
      25.000000000000000000::NUMERIC,
      9000.000000000000000000::NUMERIC
    )
  $$,
  'User A reads own projected summary through security-invoker view'
);

SELECT is(
  (
    SELECT count(*)::INTEGER
    FROM public.portfolio_position_projections
    WHERE user_id = '40000000-0000-0000-0000-000000000002'
  ),
  0,
  'User A cannot read User B projection table rows directly'
);

SELECT is(
  (
    SELECT count(*)::INTEGER
    FROM public.portfolio_summary
  ),
  1,
  'User A sees one owner-scoped summary row'
);

SELECT ok(
  (
    SELECT calculated_at
    FROM public.portfolio_positions
    WHERE asset_symbol = 'MSFT'
  ) IS NOT NULL,
  'projected position exposes rebuild timestamp'
);

SELECT throws_ok(
  $$
    SELECT public.replace_portfolio_position_projections(
      '40000000-0000-0000-0000-000000000001',
      '[]'::jsonb
    )
  $$,
  '42501',
  NULL,
  'authenticated owner cannot execute projection replacement RPC'
);

SELECT throws_ok(
  $$
    INSERT INTO public.portfolio_position_projections (
      user_id, investment_account_id, asset_id, quantity, cost_basis_thb,
      realized_pnl_thb, income_thb, fees_thb, cash_flow_thb
    )
    VALUES (
      '40000000-0000-0000-0000-000000000001',
      '41000000-0000-0000-0000-000000000001',
      '42000000-0000-0000-0000-000000000001',
      1, 1, 0, 0, 0, 0
    )
  $$,
  '42501',
  NULL,
  'authenticated owner cannot insert projection rows'
);

RESET ROLE;

SELECT throws_ok(
  $$
    SELECT public.replace_portfolio_position_projections(
      '40000000-0000-0000-0000-000000000001',
      '{}'::jsonb
    )
  $$,
  '22023',
  'Projection rows must be a JSON array',
  'projection replacement rejects non-array JSON'
);

SELECT throws_ok(
  $$
    SELECT public.replace_portfolio_position_projections(
      '40000000-0000-0000-0000-000000000001',
      '[
        {
          "investment_account_id": "41000000-0000-0000-0000-000000000001",
          "asset_id": "42000000-0000-0000-0000-000000000001",
          "source_metadata": {"source": "client_supplied"},
          "quantity": "1",
          "cost_basis_thb": "1",
          "realized_pnl_thb": "0",
          "income_thb": "0",
          "fees_thb": "0",
          "cash_flow_thb": "0"
        }
      ]'::jsonb
    )
  $$,
  '22023',
  'Projection source metadata must be canonical',
  'projection replacement rejects arbitrary source metadata'
);

SELECT * FROM finish();

ROLLBACK;
