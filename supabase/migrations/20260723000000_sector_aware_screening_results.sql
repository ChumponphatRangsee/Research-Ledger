-- Persist explainable sector-aware quantitative screening results.

ALTER TABLE screening_runs
  ADD COLUMN IF NOT EXISTS requested_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS processed_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS failed_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS passed_count INTEGER NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS selected_count INTEGER NOT NULL DEFAULT 0;

CREATE TABLE IF NOT EXISTS screening_results (
  id                       UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  screening_run_id         UUID NOT NULL REFERENCES screening_runs (id) ON DELETE CASCADE,
  ticker_id                UUID NOT NULL REFERENCES tickers (id) ON DELETE CASCADE,
  business_model           TEXT NOT NULL,
  passed                   BOOLEAN NOT NULL DEFAULT false,
  total_score              NUMERIC(6, 2),
  confidence_score         NUMERIC(6, 2) NOT NULL DEFAULT 0,
  quality_score            NUMERIC(6, 2),
  growth_score             NUMERIC(6, 2),
  financial_strength_score NUMERIC(6, 2),
  valuation_score          NUMERIC(6, 2),
  sector_specific_score    NUMERIC(6, 2),
  metrics                  JSONB NOT NULL DEFAULT '{}'::jsonb,
  score_breakdown          JSONB NOT NULL DEFAULT '{}'::jsonb,
  strengths                JSONB NOT NULL DEFAULT '[]'::jsonb,
  warnings                 JSONB NOT NULL DEFAULT '[]'::jsonb,
  failure_reasons          JSONB NOT NULL DEFAULT '[]'::jsonb,
  data_as_of               TIMESTAMPTZ,
  created_at               TIMESTAMPTZ NOT NULL DEFAULT now(),
  UNIQUE (screening_run_id, ticker_id),
  CONSTRAINT screening_results_total_score_range
    CHECK (total_score IS NULL OR total_score BETWEEN 0 AND 100),
  CONSTRAINT screening_results_confidence_range
    CHECK (confidence_score BETWEEN 0 AND 100)
);

CREATE INDEX IF NOT EXISTS idx_screening_results_run
  ON screening_results (screening_run_id);
CREATE INDEX IF NOT EXISTS idx_screening_results_ticker
  ON screening_results (ticker_id);
CREATE INDEX IF NOT EXISTS idx_screening_results_total_score
  ON screening_results (total_score DESC NULLS LAST);
CREATE INDEX IF NOT EXISTS idx_screening_results_passed
  ON screening_results (passed);
CREATE INDEX IF NOT EXISTS idx_screening_results_business_model
  ON screening_results (business_model);
CREATE INDEX IF NOT EXISTS idx_screening_results_run_rank
  ON screening_results (screening_run_id, passed, total_score DESC NULLS LAST);

ALTER TABLE screening_results ENABLE ROW LEVEL SECURITY;

DROP POLICY IF EXISTS "screening_results_select_own" ON screening_results;
CREATE POLICY "screening_results_select_own"
  ON screening_results FOR SELECT
  TO authenticated
  USING (
    EXISTS (
      SELECT 1
      FROM screening_runs
      WHERE screening_runs.id = screening_results.screening_run_id
        AND screening_runs.user_id = (SELECT auth.uid())
    )
  );

-- Inserts and updates remain service-role-only, matching the existing ticker and
-- analysis pipeline persistence convention.
