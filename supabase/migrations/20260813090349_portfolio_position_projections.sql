-- PR 3: rebuildable portfolio calculation projections.
-- Confirmed transactions remain the source of truth; these rows are disposable
-- read models rebuilt from deterministic weighted-average ledger replay.

CREATE TABLE public.portfolio_position_projections (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL
    REFERENCES auth.users (id) ON DELETE CASCADE,
  investment_account_id UUID NOT NULL,
  asset_id UUID NOT NULL,
  as_of_transaction_at TIMESTAMPTZ,
  as_of_ledger_sequence BIGINT,
  source_transaction_count BIGINT NOT NULL DEFAULT 0,
  quantity NUMERIC(38, 18) NOT NULL DEFAULT 0,
  cost_basis_thb NUMERIC(38, 18) NOT NULL DEFAULT 0,
  weighted_average_cost_thb NUMERIC(38, 18),
  realized_pnl_thb NUMERIC(38, 18) NOT NULL DEFAULT 0,
  income_thb NUMERIC(38, 18) NOT NULL DEFAULT 0,
  fees_thb NUMERIC(38, 18) NOT NULL DEFAULT 0,
  cash_flow_thb NUMERIC(38, 18) NOT NULL DEFAULT 0,
  market_value_thb NUMERIC(38, 18),
  unrealized_pnl_thb NUMERIC(38, 18),
  allocation_pct NUMERIC(38, 18),
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  calculated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT portfolio_position_projections_id_user_id_key
    UNIQUE (id, user_id),
  CONSTRAINT portfolio_position_projections_owner_position_key
    UNIQUE (user_id, investment_account_id, asset_id),
  CONSTRAINT portfolio_position_projections_account_owner_fkey
    FOREIGN KEY (investment_account_id, user_id)
    REFERENCES public.investment_accounts (id, user_id)
    ON DELETE CASCADE,
  CONSTRAINT portfolio_position_projections_asset_owner_fkey
    FOREIGN KEY (asset_id, user_id)
    REFERENCES public.assets (id, user_id)
    ON DELETE CASCADE,
  CONSTRAINT portfolio_position_projections_as_of_valid
    CHECK (as_of_transaction_at IS NULL OR isfinite(as_of_transaction_at)),
  CONSTRAINT portfolio_position_projections_sequence_nonnegative
    CHECK (as_of_ledger_sequence IS NULL OR as_of_ledger_sequence >= 0),
  CONSTRAINT portfolio_position_projections_source_count_nonnegative
    CHECK (source_transaction_count >= 0),
  CONSTRAINT portfolio_position_projections_quantity_nonnegative
    CHECK (quantity >= 0),
  CONSTRAINT portfolio_position_projections_cost_basis_nonnegative
    CHECK (cost_basis_thb >= 0),
  CONSTRAINT portfolio_position_projections_average_cost_nonnegative
    CHECK (weighted_average_cost_thb IS NULL OR weighted_average_cost_thb >= 0),
  CONSTRAINT portfolio_position_projections_fees_nonnegative
    CHECK (fees_thb >= 0),
  CONSTRAINT portfolio_position_projections_market_value_nonnegative
    CHECK (market_value_thb IS NULL OR market_value_thb >= 0),
  CONSTRAINT portfolio_position_projections_allocation_pct_valid
    CHECK (
      allocation_pct IS NULL
      OR (allocation_pct >= 0 AND allocation_pct <= 100)
    ),
  CONSTRAINT portfolio_position_projections_source_metadata_object
    CHECK (jsonb_typeof(source_metadata) = 'object'),
  CONSTRAINT portfolio_position_projections_timestamps_valid
    CHECK (
      isfinite(calculated_at)
      AND isfinite(updated_at)
      AND updated_at >= calculated_at
    )
);

COMMENT ON TABLE public.portfolio_position_projections IS
  'Rebuildable owner-scoped position read model derived from immutable confirmed transactions.';
COMMENT ON COLUMN public.portfolio_position_projections.cost_basis_thb IS
  'Remaining weighted-average THB cost basis replayed from confirmed transaction rows.';
COMMENT ON COLUMN public.portfolio_position_projections.realized_pnl_thb IS
  'Realized THB profit and loss replayed from SELL and linked REVERSAL rows.';
COMMENT ON COLUMN public.portfolio_position_projections.cash_flow_thb IS
  'Signed THB cash movement implied by confirmed transactions; buys and fees are negative.';
COMMENT ON COLUMN public.portfolio_position_projections.market_value_thb IS
  'Optional marked THB value. PR 5 introduces authoritative price and FX snapshots.';

CREATE INDEX idx_portfolio_position_projections_user_id
  ON public.portfolio_position_projections (user_id);
CREATE INDEX idx_portfolio_position_projections_account_owner_fk
  ON public.portfolio_position_projections (investment_account_id, user_id);
CREATE INDEX idx_portfolio_position_projections_asset_owner_fk
  ON public.portfolio_position_projections (asset_id, user_id);
CREATE INDEX idx_portfolio_position_projections_owner_value
  ON public.portfolio_position_projections (user_id, market_value_thb)
  WHERE market_value_thb IS NOT NULL;

CREATE TRIGGER trg_portfolio_position_projections_updated_at
  BEFORE UPDATE ON public.portfolio_position_projections
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.portfolio_position_projections
  ENABLE ROW LEVEL SECURITY;

CREATE POLICY portfolio_position_projections_select_own
  ON public.portfolio_position_projections FOR SELECT
  TO authenticated
  USING ((SELECT auth.uid()) = user_id);

CREATE POLICY portfolio_position_projections_service_role_manage
  ON public.portfolio_position_projections FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

REVOKE ALL ON TABLE public.portfolio_position_projections
  FROM PUBLIC, anon, authenticated, service_role;

GRANT SELECT
  ON TABLE public.portfolio_position_projections
  TO authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE
  ON TABLE public.portfolio_position_projections
  TO service_role;

CREATE VIEW public.portfolio_position_projection_view
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
  projection.as_of_transaction_at,
  projection.as_of_ledger_sequence,
  projection.source_transaction_count,
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
  projection.calculated_at,
  projection.updated_at
FROM public.portfolio_position_projections AS projection
JOIN public.investment_accounts AS account
  ON account.id = projection.investment_account_id
  AND account.user_id = projection.user_id
JOIN public.assets AS asset
  ON asset.id = projection.asset_id
  AND asset.user_id = projection.user_id;

CREATE VIEW public.portfolio_account_projection_view
WITH (security_invoker = true)
AS
WITH account_totals AS (
  SELECT
    projection.user_id,
    projection.investment_account_id,
    account.name AS investment_account_name,
    account.account_type AS investment_account_type,
    count(*)::BIGINT AS position_count,
    count(*) FILTER (WHERE projection.quantity > 0)::BIGINT
      AS open_position_count,
    max(projection.as_of_transaction_at) AS as_of_transaction_at,
    max(projection.as_of_ledger_sequence) AS as_of_ledger_sequence,
    max(projection.source_transaction_count) AS source_transaction_count,
    sum(projection.cost_basis_thb) AS cost_basis_thb,
    sum(projection.realized_pnl_thb) AS realized_pnl_thb,
    sum(projection.income_thb) AS income_thb,
    sum(projection.fees_thb) AS fees_thb,
    sum(projection.cash_flow_thb) AS cash_flow_thb,
    sum(projection.market_value_thb) AS market_value_thb,
    sum(projection.unrealized_pnl_thb) AS unrealized_pnl_thb,
    max(projection.calculated_at) AS calculated_at,
    max(projection.updated_at) AS updated_at
  FROM public.portfolio_position_projections AS projection
  JOIN public.investment_accounts AS account
    ON account.id = projection.investment_account_id
    AND account.user_id = projection.user_id
  GROUP BY
    projection.user_id,
    projection.investment_account_id,
    account.name,
    account.account_type
)
SELECT
  account_totals.*,
  CASE
    WHEN sum(account_totals.market_value_thb)
      OVER (PARTITION BY account_totals.user_id) > 0
    THEN account_totals.market_value_thb
      / sum(account_totals.market_value_thb)
        OVER (PARTITION BY account_totals.user_id)
      * 100
    ELSE NULL
  END AS allocation_pct
FROM account_totals;

COMMENT ON VIEW public.portfolio_position_projection_view IS
  'Security-invoker view exposing owner-scoped rebuilt position projections with account and asset labels.';
COMMENT ON VIEW public.portfolio_account_projection_view IS
  'Security-invoker view aggregating rebuilt position projections by investment account.';

REVOKE ALL ON TABLE public.portfolio_position_projection_view
  FROM PUBLIC, anon, authenticated, service_role;
REVOKE ALL ON TABLE public.portfolio_account_projection_view
  FROM PUBLIC, anon, authenticated, service_role;

GRANT SELECT
  ON TABLE
    public.portfolio_position_projection_view,
    public.portfolio_account_projection_view
  TO authenticated, service_role;;
