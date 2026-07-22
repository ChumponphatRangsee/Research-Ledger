-- Phase-one MVP ownership hardening:
-- every analysis and portfolio row belongs to exactly one authenticated user.

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM analysis_inbox WHERE user_id IS NULL) THEN
    RAISE EXCEPTION
      'Cannot enforce analysis_inbox.user_id NOT NULL: null-owned rows exist. Remediate by deleting obsolete unowned analyses or assigning each row to its actual initiating auth.users.id, then rerun this migration.';
  END IF;
END $$;

DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM portfolios
    WHERE approved_from_inbox_id IS NOT NULL
    GROUP BY approved_from_inbox_id
    HAVING COUNT(*) > 1
  ) THEN
    RAISE EXCEPTION
      'Cannot enforce unique portfolio execution: duplicate approved_from_inbox_id values exist in portfolios. Remediate duplicates before rerunning this migration.';
  END IF;
END $$;

ALTER TABLE analysis_inbox
  ALTER COLUMN user_id SET NOT NULL;

DROP POLICY IF EXISTS "analysis_inbox_select_own_or_unassigned" ON analysis_inbox;
DROP POLICY IF EXISTS "analysis_inbox_select_own" ON analysis_inbox;
DROP POLICY IF EXISTS "analysis_inbox_insert_own" ON analysis_inbox;
DROP POLICY IF EXISTS "analysis_inbox_update_own" ON analysis_inbox;

CREATE POLICY "analysis_inbox_select_own"
  ON analysis_inbox FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "analysis_inbox_update_own"
  ON analysis_inbox FOR UPDATE
  TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());

DROP POLICY IF EXISTS "portfolios_select_own" ON portfolios;
DROP POLICY IF EXISTS "portfolios_insert_own" ON portfolios;
DROP POLICY IF EXISTS "portfolios_update_own" ON portfolios;
DROP POLICY IF EXISTS "portfolios_delete_own" ON portfolios;

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

CREATE UNIQUE INDEX IF NOT EXISTS idx_portfolios_approved_from_inbox_once
  ON portfolios (approved_from_inbox_id)
  WHERE approved_from_inbox_id IS NOT NULL;
