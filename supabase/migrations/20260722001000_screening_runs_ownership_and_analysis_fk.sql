-- Add strict single-user ownership to screening_runs and fix the
-- analysis_inbox.user_id FK action so it cannot SET NULL after user deletion.

ALTER TABLE analysis_inbox
  DROP CONSTRAINT IF EXISTS analysis_inbox_user_id_fkey;

ALTER TABLE analysis_inbox
  ADD CONSTRAINT analysis_inbox_user_id_fkey
  FOREIGN KEY (user_id)
  REFERENCES auth.users (id)
  ON DELETE CASCADE;

ALTER TABLE screening_runs
  ADD COLUMN IF NOT EXISTS user_id UUID REFERENCES auth.users (id) ON DELETE CASCADE;

ALTER TABLE screening_runs
  DROP CONSTRAINT IF EXISTS screening_runs_user_id_fkey;

ALTER TABLE screening_runs
  ADD CONSTRAINT screening_runs_user_id_fkey
  FOREIGN KEY (user_id)
  REFERENCES auth.users (id)
  ON DELETE CASCADE;

DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM screening_runs WHERE user_id IS NULL) THEN
    RAISE EXCEPTION
      'Cannot enforce screening_runs.user_id NOT NULL: existing screening_runs have no owner. Remediate by assigning each run to its initiating auth.users.id or deleting obsolete runs, then rerun this migration.';
  END IF;
END $$;

ALTER TABLE screening_runs
  ALTER COLUMN user_id SET NOT NULL;

CREATE INDEX IF NOT EXISTS idx_screening_runs_user_id ON screening_runs (user_id);

DROP POLICY IF EXISTS "screening_runs_select_authenticated" ON screening_runs;
DROP POLICY IF EXISTS "screening_runs_select_own" ON screening_runs;
DROP POLICY IF EXISTS "screening_runs_insert_own" ON screening_runs;
DROP POLICY IF EXISTS "screening_runs_update_own" ON screening_runs;

CREATE POLICY "screening_runs_select_own"
  ON screening_runs FOR SELECT
  TO authenticated
  USING (user_id = auth.uid());

CREATE POLICY "screening_runs_insert_own"
  ON screening_runs FOR INSERT
  TO authenticated
  WITH CHECK (user_id = auth.uid());

CREATE POLICY "screening_runs_update_own"
  ON screening_runs FOR UPDATE
  TO authenticated
  USING (user_id = auth.uid())
  WITH CHECK (user_id = auth.uid());
