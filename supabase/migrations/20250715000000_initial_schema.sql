-- InvestFlow-AI: Initial schema
-- Tables: tickers, screening_runs, analysis_inbox, portfolios

-- ── Extensions ──────────────────────────────────────────────────────────────
CREATE EXTENSION IF NOT EXISTS "pgcrypto";

-- ── Local dev compat (Supabase provides auth.users in hosted/local CLI) ───────
CREATE SCHEMA IF NOT EXISTS auth;
CREATE TABLE IF NOT EXISTS auth.users (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  email TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

-- ── Enums ─────────────────────────────────────────────────────────────────────
DO $$ BEGIN
  CREATE TYPE inbox_status AS ENUM (
    'pending_review',
    'approved',
    'discarded',
    'expired'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE pipeline_stage AS ENUM (
    'researcher',
    'financial',
    'valuator',
    'decision',
    'complete',
    'failed'
  );
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE portfolio_status AS ENUM ('active', 'closed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

DO $$ BEGIN
  CREATE TYPE screening_run_status AS ENUM ('running', 'completed', 'failed');
EXCEPTION WHEN duplicate_object THEN NULL;
END $$;

-- ── tickers ───────────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS tickers (
  id            UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  symbol        TEXT NOT NULL UNIQUE,
  name          TEXT,
  sector        TEXT,
  industry      TEXT,
  exchange      TEXT,
  market_cap    BIGINT,
  currency      TEXT DEFAULT 'USD',
  last_screened_at TIMESTAMPTZ,
  metadata      JSONB DEFAULT '{}'::jsonb,
  created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_tickers_symbol ON tickers (symbol);
CREATE INDEX IF NOT EXISTS idx_tickers_last_screened ON tickers (last_screened_at DESC);

-- ── screening_runs ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS screening_runs (
  id               UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  run_date         DATE NOT NULL DEFAULT CURRENT_DATE,
  status           screening_run_status NOT NULL DEFAULT 'running',
  criteria         JSONB NOT NULL DEFAULT '{}'::jsonb,
  candidates_count INTEGER NOT NULL DEFAULT 0,
  triggered_count  INTEGER NOT NULL DEFAULT 0,
  error_message    TEXT,
  started_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
  completed_at     TIMESTAMPTZ,
  created_at       TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_screening_runs_run_date ON screening_runs (run_date DESC);

-- ── analysis_inbox ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS analysis_inbox (
  id                  UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ticker_id           UUID NOT NULL REFERENCES tickers (id) ON DELETE CASCADE,
  user_id             UUID REFERENCES auth.users (id) ON DELETE SET NULL,
  screening_run_id    UUID REFERENCES screening_runs (id) ON DELETE SET NULL,
  status              inbox_status NOT NULL DEFAULT 'pending_review',
  pipeline_stage      pipeline_stage NOT NULL DEFAULT 'researcher',
  quantitative_score  NUMERIC(8, 4),
  current_price       NUMERIC(14, 4),
  fair_value          NUMERIC(14, 4),
  upside_pct          NUMERIC(8, 4),
  recommendation      TEXT,
  researcher_output   JSONB DEFAULT '{}'::jsonb,
  financial_output    JSONB DEFAULT '{}'::jsonb,
  valuation_output    JSONB DEFAULT '{}'::jsonb,
  decision_output     JSONB DEFAULT '{}'::jsonb,
  investment_memo     TEXT,
  memo_summary        TEXT,
  error_message       TEXT,
  reviewed_at         TIMESTAMPTZ,
  created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS idx_analysis_inbox_status ON analysis_inbox (status);
CREATE INDEX IF NOT EXISTS idx_analysis_inbox_user_id ON analysis_inbox (user_id);
CREATE INDEX IF NOT EXISTS idx_analysis_inbox_ticker_id ON analysis_inbox (ticker_id);
CREATE INDEX IF NOT EXISTS idx_analysis_inbox_created_at ON analysis_inbox (created_at DESC);

-- ── portfolios ──────────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolios (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               UUID NOT NULL REFERENCES auth.users (id) ON DELETE CASCADE,
  ticker_id             UUID NOT NULL REFERENCES tickers (id) ON DELETE RESTRICT,
  approved_from_inbox_id UUID REFERENCES analysis_inbox (id) ON DELETE SET NULL,
  shares                NUMERIC(18, 6) NOT NULL DEFAULT 0,
  cost_basis            NUMERIC(14, 4),
  avg_cost_per_share    NUMERIC(14, 4),
  status                portfolio_status NOT NULL DEFAULT 'active',
  notes                 TEXT,
  opened_at             TIMESTAMPTZ NOT NULL DEFAULT now(),
  closed_at             TIMESTAMPTZ,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (user_id, ticker_id, status)
);

CREATE INDEX IF NOT EXISTS idx_portfolios_user_id ON portfolios (user_id);
CREATE INDEX IF NOT EXISTS idx_portfolios_ticker_id ON portfolios (ticker_id);

-- ── updated_at trigger ────────────────────────────────────────────────────────
CREATE OR REPLACE FUNCTION set_updated_at()
RETURNS TRIGGER AS $$
BEGIN
  NEW.updated_at = now();
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_tickers_updated_at ON tickers;
CREATE TRIGGER trg_tickers_updated_at
  BEFORE UPDATE ON tickers
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_analysis_inbox_updated_at ON analysis_inbox;
CREATE TRIGGER trg_analysis_inbox_updated_at
  BEFORE UPDATE ON analysis_inbox
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

DROP TRIGGER IF EXISTS trg_portfolios_updated_at ON portfolios;
CREATE TRIGGER trg_portfolios_updated_at
  BEFORE UPDATE ON portfolios
  FOR EACH ROW EXECUTE FUNCTION set_updated_at();

-- ── Row Level Security ────────────────────────────────────────────────────────
ALTER TABLE tickers ENABLE ROW LEVEL SECURITY;
ALTER TABLE screening_runs ENABLE ROW LEVEL SECURITY;
ALTER TABLE analysis_inbox ENABLE ROW LEVEL SECURITY;
ALTER TABLE portfolios ENABLE ROW LEVEL SECURITY;

-- tickers: readable by authenticated users; writes via service role only
CREATE POLICY "tickers_select_authenticated"
  ON tickers FOR SELECT
  TO authenticated
  USING (true);

-- screening_runs: readable by authenticated users
CREATE POLICY "screening_runs_select_authenticated"
  ON screening_runs FOR SELECT
  TO authenticated
  USING (true);

-- analysis_inbox: users see their own items + unassigned pending items
CREATE POLICY "analysis_inbox_select_own_or_unassigned"
  ON analysis_inbox FOR SELECT
  TO authenticated
  USING (user_id IS NULL OR user_id = auth.uid());

CREATE POLICY "analysis_inbox_update_own"
  ON analysis_inbox FOR UPDATE
  TO authenticated
  USING (user_id IS NULL OR user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

-- portfolios: users manage only their own holdings
CREATE POLICY "portfolios_select_own"
  ON portfolios FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "portfolios_insert_own"
  ON portfolios FOR INSERT
  TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "portfolios_update_own"
  ON portfolios FOR UPDATE
  TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "portfolios_delete_own"
  ON portfolios FOR DELETE
  TO authenticated
  USING (user_id = auth.uid());
