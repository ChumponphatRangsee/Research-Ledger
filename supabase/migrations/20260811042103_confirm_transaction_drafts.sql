-- PR 4: atomic, idempotent confirmation of reviewed transaction drafts.
-- Backend calls this with p_user_id derived from a verified Supabase JWT.

CREATE FUNCTION public.confirm_transaction_draft(
  p_draft_id UUID,
  p_user_id UUID
)
RETURNS public.transactions
LANGUAGE plpgsql
SECURITY DEFINER
SET search_path TO pg_catalog, public
AS $$
DECLARE
  draft public.transaction_drafts%ROWTYPE;
  confirmed public.transactions%ROWTYPE;
BEGIN
  IF p_draft_id IS NULL OR p_user_id IS NULL THEN
    RAISE EXCEPTION 'Draft id and user id are required'
      USING ERRCODE = '22023';
  END IF;

  SELECT *
  INTO confirmed
  FROM public.transactions
  WHERE confirmed_from_draft_id = p_draft_id
    AND user_id = p_user_id;

  IF FOUND THEN
    RETURN confirmed;
  END IF;

  SELECT *
  INTO draft
  FROM public.transaction_drafts
  WHERE id = p_draft_id
    AND user_id = p_user_id
  FOR UPDATE;

  IF NOT FOUND THEN
    RAISE EXCEPTION 'Transaction draft not found'
      USING ERRCODE = 'P0002';
  END IF;

  SELECT *
  INTO confirmed
  FROM public.transactions
  WHERE confirmed_from_draft_id = p_draft_id
    AND user_id = p_user_id;

  IF FOUND THEN
    RETURN confirmed;
  END IF;

  INSERT INTO public.transactions (
    user_id,
    investment_account_id,
    asset_id,
    confirmed_from_draft_id,
    reversal_of_transaction_id,
    transaction_type,
    transaction_at,
    quantity,
    unit_price,
    gross_amount,
    fee_amount,
    currency,
    fx_rate_to_thb,
    source_type,
    source_identifier,
    source_row_number,
    source_fingerprint,
    raw_source_data,
    source_metadata,
    notes,
    fee_unit
  )
  VALUES (
    draft.user_id,
    draft.investment_account_id,
    draft.asset_id,
    draft.id,
    draft.reversal_of_transaction_id,
    draft.transaction_type,
    draft.transaction_at,
    draft.quantity,
    draft.unit_price,
    draft.gross_amount,
    draft.fee_amount,
    draft.currency,
    draft.fx_rate_to_thb,
    draft.source_type,
    draft.source_identifier,
    draft.source_row_number,
    draft.source_fingerprint,
    draft.raw_source_data,
    draft.source_metadata || jsonb_build_object(
      'confirmed_from_draft_id', draft.id,
      'confirmed_at', now()
    ),
    draft.notes,
    draft.fee_unit
  )
  RETURNING *
  INTO confirmed;

  RETURN confirmed;
END;
$$;

COMMENT ON FUNCTION public.confirm_transaction_draft(UUID, UUID) IS
  'Atomically confirms one reviewed draft for a backend-verified owner; idempotently returns the existing transaction if already confirmed.';

REVOKE ALL ON FUNCTION public.confirm_transaction_draft(UUID, UUID)
  FROM PUBLIC, anon, authenticated, service_role;
GRANT EXECUTE ON FUNCTION public.confirm_transaction_draft(UUID, UUID)
  TO service_role;
