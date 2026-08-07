-- Hardening follow-up for the portfolio ledger foundation after Cloud advisor
-- review. Keep this separate from the already-pushed foundation migration so
-- remote migration history remains append-only.

CREATE FUNCTION public.prevent_confirmed_transaction_draft_update()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path TO pg_catalog
AS $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM public.transactions
    WHERE confirmed_from_draft_id = OLD.id
      AND user_id = OLD.user_id
  ) THEN
    RAISE EXCEPTION 'Confirmed transaction drafts are immutable; append a correcting draft instead'
      USING ERRCODE = '55000';
  END IF;

  RETURN NEW;
END;
$$;

CREATE TRIGGER trg_transaction_drafts_prevent_confirmed_update
  BEFORE UPDATE ON public.transaction_drafts
  FOR EACH ROW EXECUTE FUNCTION public.prevent_confirmed_transaction_draft_update();

REVOKE ALL ON FUNCTION public.prevent_confirmed_transaction_draft_update()
  FROM PUBLIC;

ALTER TABLE public.transaction_drafts
  ADD CONSTRAINT transaction_drafts_id_user_id_import_batch_key
  UNIQUE (id, user_id, import_batch_id);

ALTER TABLE public.transaction_import_errors
  DROP CONSTRAINT transaction_import_errors_draft_owner_fkey;

ALTER TABLE public.transaction_import_errors
  ADD CONSTRAINT transaction_import_errors_draft_batch_owner_fkey
  FOREIGN KEY (transaction_draft_id, user_id, import_batch_id)
  REFERENCES public.transaction_drafts (id, user_id, import_batch_id)
  ON DELETE RESTRICT;

CREATE INDEX idx_transaction_drafts_account_owner_fk
  ON public.transaction_drafts (investment_account_id, user_id);
CREATE INDEX idx_transaction_drafts_asset_owner_fk
  ON public.transaction_drafts (asset_id, user_id);
CREATE INDEX idx_transaction_drafts_batch_owner_fk
  ON public.transaction_drafts (import_batch_id, user_id)
  WHERE import_batch_id IS NOT NULL;
CREATE INDEX idx_transaction_drafts_reversal_owner_fk
  ON public.transaction_drafts (reversal_of_transaction_id, user_id)
  WHERE reversal_of_transaction_id IS NOT NULL;

CREATE INDEX idx_transactions_account_owner_fk
  ON public.transactions (investment_account_id, user_id);
CREATE INDEX idx_transactions_asset_owner_fk
  ON public.transactions (asset_id, user_id);
CREATE INDEX idx_transactions_confirmed_draft_owner_fk
  ON public.transactions (confirmed_from_draft_id, user_id)
  WHERE confirmed_from_draft_id IS NOT NULL;
CREATE INDEX idx_transactions_reversal_owner_account_asset_fk
  ON public.transactions (
    reversal_of_transaction_id,
    user_id,
    investment_account_id,
    asset_id
  )
  WHERE reversal_of_transaction_id IS NOT NULL;

CREATE INDEX idx_transaction_import_errors_batch_owner_fk
  ON public.transaction_import_errors (import_batch_id, user_id);
CREATE INDEX idx_transaction_import_errors_draft_batch_owner_fk
  ON public.transaction_import_errors (
    transaction_draft_id,
    user_id,
    import_batch_id
  )
  WHERE transaction_draft_id IS NOT NULL;

COMMENT ON FUNCTION public.prevent_confirmed_transaction_draft_update() IS
  'Blocks updates to draft evidence after a confirmed transaction references the draft.';
COMMENT ON CONSTRAINT transaction_drafts_id_user_id_import_batch_key
  ON public.transaction_drafts IS
  'Supports import-error references that must match the draft owner and import batch.';
COMMENT ON CONSTRAINT transaction_import_errors_draft_batch_owner_fkey
  ON public.transaction_import_errors IS
  'Requires an import error linked to a draft to use a draft from the same owner and batch.';

REVOKE ALL ON TABLE public.market_data_snapshots
  FROM PUBLIC, anon, authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE
  ON TABLE public.market_data_snapshots
  TO service_role;

CREATE POLICY market_data_snapshots_service_role_manage
  ON public.market_data_snapshots FOR ALL
  TO service_role
  USING (true)
  WITH CHECK (true);

COMMENT ON POLICY market_data_snapshots_service_role_manage
  ON public.market_data_snapshots IS
  'Backend cache policy; anon and authenticated roles have no table grants.';
