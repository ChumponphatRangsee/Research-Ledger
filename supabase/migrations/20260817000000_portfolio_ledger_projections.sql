-- PR 3 follow-up: backend rebuild RPC and user-facing projection views.
-- The projection table itself is created by remote migration 20260813090349.

CREATE INDEX IF NOT EXISTS idx_portfolio_position_projections_account_owner_fk
  ON public.portfolio_position_projections (investment_account_id, user_id);

CREATE INDEX IF NOT EXISTS idx_portfolio_position_projections_asset_owner_fk
  ON public.portfolio_position_projections (asset_id, user_id);

ALTER TABLE public.portfolio_position_projections
  ENABLE ROW LEVEL SECURITY;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'portfolio_position_projections'
      AND policyname = 'portfolio_position_projections_select_own'
  ) THEN
    CREATE POLICY portfolio_position_projections_select_own
      ON public.portfolio_position_projections FOR SELECT
      TO authenticated
      USING ((SELECT auth.uid()) = user_id);
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM pg_policies
    WHERE schemaname = 'public'
      AND tablename = 'portfolio_position_projections'
      AND policyname = 'portfolio_position_projections_service_role_manage'
  ) THEN
    CREATE POLICY portfolio_position_projections_service_role_manage
      ON public.portfolio_position_projections FOR ALL
      TO service_role
      USING (true)
      WITH CHECK (true);
  END IF;
END $$;

REVOKE ALL ON TABLE public.portfolio_position_projections
  FROM PUBLIC, anon, authenticated, service_role;

GRANT SELECT
  ON TABLE public.portfolio_position_projections
  TO authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE
  ON TABLE public.portfolio_position_projections
  TO service_role;

CREATE OR REPLACE FUNCTION public.replace_portfolio_position_projections(
  p_user_id UUID,
  p_rows JSONB
)
RETURNS VOID
LANGUAGE plpgsql
SECURITY INVOKER
SET search_path TO pg_catalog, public
AS $$
DECLARE
  v_calculated_at TIMESTAMPTZ := now();
BEGIN
  IF p_user_id IS NULL THEN
    RAISE EXCEPTION 'User id is required'
      USING ERRCODE = '22023';
  END IF;

  IF p_rows IS NULL OR jsonb_typeof(p_rows) <> 'array' THEN
    RAISE EXCEPTION 'Projection rows must be a JSON array'
      USING ERRCODE = '22023';
  END IF;

  IF EXISTS (
    SELECT 1
    FROM jsonb_array_elements(p_rows) AS item(row_data)
    WHERE jsonb_typeof(item.row_data) <> 'object'
  ) THEN
    RAISE EXCEPTION 'Every projection row must be a JSON object'
      USING ERRCODE = '22023';
  END IF;

  DELETE FROM public.portfolio_position_projections
  WHERE user_id = p_user_id;

  INSERT INTO public.portfolio_position_projections (
    user_id,
    investment_account_id,
    asset_id,
    quantity,
    cost_basis_thb,
    weighted_average_cost_thb,
    realized_pnl_thb,
    income_thb,
    fees_thb,
    cash_flow_thb,
    market_value_thb,
    unrealized_pnl_thb,
    allocation_pct,
    calculated_at
  )
  SELECT
    p_user_id,
    (item.row_data ->> 'investment_account_id')::UUID,
    (item.row_data ->> 'asset_id')::UUID,
    (item.row_data ->> 'quantity')::NUMERIC,
    (item.row_data ->> 'cost_basis_thb')::NUMERIC,
    NULLIF(item.row_data ->> 'weighted_average_cost_thb', '')::NUMERIC,
    (item.row_data ->> 'realized_pnl_thb')::NUMERIC,
    (item.row_data ->> 'income_thb')::NUMERIC,
    (item.row_data ->> 'fees_thb')::NUMERIC,
    (item.row_data ->> 'cash_flow_thb')::NUMERIC,
    NULLIF(item.row_data ->> 'market_value_thb', '')::NUMERIC,
    NULLIF(item.row_data ->> 'unrealized_pnl_thb', '')::NUMERIC,
    NULLIF(item.row_data ->> 'allocation_pct', '')::NUMERIC,
    v_calculated_at
  FROM jsonb_array_elements(p_rows) AS item(row_data);
END;
$$;

COMMENT ON FUNCTION public.replace_portfolio_position_projections(UUID, JSONB) IS
  'Backend-only replacement of rebuildable owner-scoped portfolio projection rows.';

REVOKE ALL ON FUNCTION public.replace_portfolio_position_projections(UUID, JSONB)
  FROM PUBLIC, anon, authenticated, service_role;

GRANT EXECUTE ON FUNCTION public.replace_portfolio_position_projections(UUID, JSONB)
  TO service_role;

CREATE OR REPLACE VIEW public.portfolio_positions
WITH (security_invoker = true)
AS
SELECT
  projection.user_id,
  projection.investment_account_id,
  account.name AS investment_account_name,
  account.account_type AS investment_account_type,
  projection.asset_id,
  asset.symbol AS asset_symbol,
  asset.name AS asset_name,
  asset.asset_type,
  asset.currency AS asset_currency,
  projection.quantity,
  projection.cost_basis_thb,
  projection.weighted_average_cost_thb,
  projection.realized_pnl_thb,
  projection.income_thb,
  projection.fees_thb,
  projection.cash_flow_thb,
  projection.market_value_thb,
  projection.unrealized_pnl_thb,
  projection.allocation_pct,
  projection.calculated_at
FROM public.portfolio_position_projections AS projection
JOIN public.investment_accounts AS account
  ON account.id = projection.investment_account_id
 AND account.user_id = projection.user_id
JOIN public.assets AS asset
  ON asset.id = projection.asset_id
 AND asset.user_id = projection.user_id;

CREATE OR REPLACE VIEW public.portfolio_summary
WITH (security_invoker = true)
AS
SELECT
  user_id,
  sum(cost_basis_thb) AS total_cost_basis_thb,
  sum(realized_pnl_thb) AS total_realized_pnl_thb,
  sum(income_thb) AS total_income_thb,
  CASE
    WHEN count(*) FILTER (WHERE market_value_thb IS NOT NULL) = 0
      THEN NULL::NUMERIC
    ELSE sum(market_value_thb) FILTER (WHERE market_value_thb IS NOT NULL)
  END AS total_market_value_thb,
  max(calculated_at) AS calculated_at
FROM public.portfolio_position_projections
GROUP BY user_id;

COMMENT ON VIEW public.portfolio_positions IS
  'Security-invoker user-facing portfolio position projection view; underlying projection RLS remains effective.';

COMMENT ON VIEW public.portfolio_summary IS
  'Security-invoker user-facing portfolio summary projection view; underlying projection RLS remains effective.';

REVOKE ALL ON TABLE public.portfolio_positions, public.portfolio_summary
  FROM PUBLIC, anon, authenticated, service_role;

GRANT SELECT
  ON TABLE public.portfolio_positions, public.portfolio_summary
  TO authenticated, service_role;
