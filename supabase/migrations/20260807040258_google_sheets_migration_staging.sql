-- PR 2: preserve spreadsheet fee semantics and make imported-draft
-- deduplication enforceable at the database boundary.

ALTER TABLE public.transaction_drafts
  ADD COLUMN fee_unit TEXT;

ALTER TABLE public.transactions
  ADD COLUMN fee_unit TEXT;

ALTER TABLE public.transaction_drafts
  ADD CONSTRAINT transaction_drafts_fee_unit_valid
  CHECK (fee_unit IS NULL OR fee_unit IN ('QUOTE_CURRENCY', 'ASSET_UNITS'));

ALTER TABLE public.transactions
  ADD CONSTRAINT transactions_fee_unit_valid
  CHECK (fee_unit IS NULL OR fee_unit IN ('QUOTE_CURRENCY', 'ASSET_UNITS'));

COMMENT ON COLUMN public.transaction_drafts.fee_unit IS
  'Unit of fee_amount. Spreadsheet staging writes QUOTE_CURRENCY or ASSET_UNITS; null remains allowed for legacy/manual drafts.';
COMMENT ON COLUMN public.transactions.fee_unit IS
  'Unit of fee_amount copied from a reviewed draft so deterministic calculations can distinguish cash fees from asset quantity fees.';

CREATE UNIQUE INDEX idx_transaction_drafts_import_source_fingerprint_owner
  ON public.transaction_drafts (user_id, source_fingerprint)
  WHERE import_batch_id IS NOT NULL AND source_fingerprint IS NOT NULL;

COMMENT ON INDEX public.idx_transaction_drafts_import_source_fingerprint_owner IS
  'Race-safe deduplication for spreadsheet-staged drafts; manual drafts without an import batch remain unaffected.';

CREATE OR REPLACE FUNCTION public.validate_transaction_reversal()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path TO pg_catalog
AS $$
DECLARE
  original public.transactions%ROWTYPE;
BEGIN
  IF NEW.transaction_type <> 'REVERSAL' THEN
    RETURN NEW;
  END IF;

  SELECT *
  INTO original
  FROM public.transactions
  WHERE id = NEW.reversal_of_transaction_id
    AND user_id = NEW.user_id
    AND investment_account_id = NEW.investment_account_id
    AND asset_id = NEW.asset_id;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Reversal must reference a same-owner, same-account, same-asset transaction'
      USING ERRCODE = '23514';
  END IF;

  IF original.transaction_type = 'REVERSAL' THEN
    RAISE EXCEPTION 'A reversal cannot reverse another reversal'
      USING ERRCODE = '23514';
  END IF;

  IF NEW.transaction_at < original.transaction_at THEN
    RAISE EXCEPTION 'A reversal cannot precede its original transaction'
      USING ERRCODE = '23514';
  END IF;

  IF NOT (
    NEW.quantity IS NOT DISTINCT FROM original.quantity
    AND NEW.unit_price IS NOT DISTINCT FROM original.unit_price
    AND NEW.gross_amount IS NOT DISTINCT FROM original.gross_amount
    AND NEW.fee_amount IS NOT DISTINCT FROM original.fee_amount
    AND NEW.fee_unit IS NOT DISTINCT FROM original.fee_unit
    AND NEW.currency IS NOT DISTINCT FROM original.currency
    AND NEW.fx_rate_to_thb IS NOT DISTINCT FROM original.fx_rate_to_thb
  ) THEN
    RAISE EXCEPTION 'A reversal must copy the original transaction financial values'
      USING ERRCODE = '23514';
  END IF;

  RETURN NEW;
END;
$$;

REVOKE ALL ON FUNCTION public.validate_transaction_reversal() FROM PUBLIC;
