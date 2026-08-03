-- Shared backend-managed cache for normalized market-data snapshots.
-- Cache rows are not user-owned product data and are intentionally unavailable
-- to anon/authenticated clients. The backend service-role client manages them.

CREATE TABLE public.market_data_snapshots (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol TEXT NOT NULL,
  provider TEXT NOT NULL,
  data_type TEXT NOT NULL,
  payload JSONB NOT NULL,
  data_as_of TIMESTAMPTZ,
  fetched_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  expires_at TIMESTAMPTZ NOT NULL,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT market_data_snapshots_symbol_uppercase
    CHECK (symbol = upper(symbol)),
  CONSTRAINT market_data_snapshots_nonempty_cache_key
    CHECK (
      btrim(symbol) <> ''
      AND btrim(provider) <> ''
      AND btrim(data_type) <> ''
    ),
  CONSTRAINT market_data_snapshots_valid_freshness_window
    CHECK (expires_at > fetched_at),
  CONSTRAINT market_data_snapshots_lookup_key
    UNIQUE (symbol, provider, data_type)
);

COMMENT ON TABLE public.market_data_snapshots IS
  'Shared backend-managed cache of normalized market-data snapshots; not user-owned application data.';
COMMENT ON COLUMN public.market_data_snapshots.payload IS
  'Provider-neutral normalized snapshot JSON. Missing metrics remain JSON null.';
COMMENT ON COLUMN public.market_data_snapshots.data_as_of IS
  'When the underlying market data was observed, when supplied by the provider.';
COMMENT ON COLUMN public.market_data_snapshots.fetched_at IS
  'When the backend retrieved the snapshot from the provider.';
COMMENT ON COLUMN public.market_data_snapshots.expires_at IS
  'Freshness cutoff used by MarketDataService cache lookups.';
COMMENT ON CONSTRAINT market_data_snapshots_lookup_key
  ON public.market_data_snapshots IS
  'Unique cache lookup index for symbol, provider, and normalized data type.';

CREATE INDEX idx_market_data_snapshots_expires_at
  ON public.market_data_snapshots (expires_at);

-- public.set_updated_at() is created by 20250715000000_initial_schema.sql and
-- its search_path is hardened by 20260722002000_rls_index_function_hardening.sql.
CREATE TRIGGER trg_market_data_snapshots_updated_at
  BEFORE UPDATE ON public.market_data_snapshots
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

ALTER TABLE public.market_data_snapshots ENABLE ROW LEVEL SECURITY;

REVOKE ALL ON TABLE public.market_data_snapshots FROM anon, authenticated;
GRANT SELECT, INSERT, UPDATE, DELETE
  ON TABLE public.market_data_snapshots
  TO service_role;
