-- Harden single-user ownership policies and add missing supporting indexes.

CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolios_approved_from_inbox_once
  ON portfolios (approved_from_inbox_id)
  WHERE approved_from_inbox_id IS NOT NULL;

CREATE INDEX IF NOT EXISTS idx_analysis_inbox_screening_run_id
  ON analysis_inbox (screening_run_id);

ALTER FUNCTION public.set_updated_at()
  SET search_path TO public, pg_temp;

DROP POLICY IF EXISTS "analysis_inbox_select_own_or_unassigned" ON analysis_inbox;
DROP POLICY IF EXISTS "analysis_inbox_select_own" ON analysis_inbox;
DROP POLICY IF EXISTS "analysis_inbox_insert_own" ON analysis_inbox;
DROP POLICY IF EXISTS "analysis_inbox_update_own" ON analysis_inbox;

CREATE POLICY "analysis_inbox_select_own"
  ON analysis_inbox FOR SELECT
  TO authenticated
  USING (user_id = (SELECT auth.uid()));

CREATE POLICY "analysis_inbox_update_own"
  ON analysis_inbox FOR UPDATE
  TO authenticated
  USING (user_id = (SELECT auth.uid()))
  WITH CHECK (user_id = (SELECT auth.uid()));

DROP POLICY IF EXISTS "screening_runs_select_authenticated" ON screening_runs;
DROP POLICY IF EXISTS "screening_runs_select_own" ON screening_runs;
DROP POLICY IF EXISTS "screening_runs_insert_own" ON screening_runs;
DROP POLICY IF EXISTS "screening_runs_update_own" ON screening_runs;

CREATE POLICY "screening_runs_select_own"
  ON screening_runs FOR SELECT
  TO authenticated
  USING (user_id = (SELECT auth.uid()));

CREATE POLICY "screening_runs_insert_own"
  ON screening_runs FOR INSERT
  TO authenticated
  WITH CHECK (user_id = (SELECT auth.uid()));

CREATE POLICY "screening_runs_update_own"
  ON screening_runs FOR UPDATE
  TO authenticated
  USING (user_id = (SELECT auth.uid()))
  WITH CHECK (user_id = (SELECT auth.uid()));

DROP POLICY IF EXISTS "portfolios_select_own" ON portfolios;
DROP POLICY IF EXISTS "portfolios_insert_own" ON portfolios;
DROP POLICY IF EXISTS "portfolios_update_own" ON portfolios;
DROP POLICY IF EXISTS "portfolios_delete_own" ON portfolios;

CREATE POLICY "portfolios_select_own"
  ON portfolios FOR SELECT
  TO authenticated
  USING (user_id = (SELECT auth.uid()));

CREATE POLICY "portfolios_insert_own"
  ON portfolios FOR INSERT
  TO authenticated
  WITH CHECK (user_id = (SELECT auth.uid()));

CREATE POLICY "portfolios_update_own"
  ON portfolios FOR UPDATE
  TO authenticated
  USING (user_id = (SELECT auth.uid()))
  WITH CHECK (user_id = (SELECT auth.uid()));

CREATE POLICY "portfolios_delete_own"
  ON portfolios FOR DELETE
  TO authenticated
  USING (user_id = (SELECT auth.uid()));
