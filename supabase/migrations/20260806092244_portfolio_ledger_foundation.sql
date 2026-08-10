-- PR 1: owner-scoped portfolio-ledger schema and security foundation.
-- Confirmed transactions are backend-inserted, append-only ledger facts.

CREATE TABLE public.assets (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL DEFAULT auth.uid()
    REFERENCES auth.users (id) ON DELETE CASCADE,
  ticker_id UUID REFERENCES public.tickers (id) ON DELETE RESTRICT,
  symbol TEXT NOT NULL,
  name TEXT NOT NULL,
  asset_type TEXT NOT NULL,
  currency TEXT NOT NULL,
  source_identifier TEXT,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT assets_id_user_id_key UNIQUE (id, user_id),
  CONSTRAINT assets_ticker_per_owner_key UNIQUE (user_id, ticker_id),
  CONSTRAINT assets_identity_per_owner_key
    UNIQUE (user_id, asset_type, symbol, currency),
  CONSTRAINT assets_symbol_nonempty
    CHECK (btrim(symbol) <> ''),
  CONSTRAINT assets_symbol_uppercase
    CHECK (symbol = upper(symbol)),
  CONSTRAINT assets_name_nonempty
    CHECK (btrim(name) <> ''),
  CONSTRAINT assets_asset_type_valid
    CHECK (
      asset_type IN (
        'STOCK',
        'ETF',
        'CRYPTO',
        'CASH',
        'BOND',
        'MUTUAL_FUND',
        'OTHER'
      )
    ),
  CONSTRAINT assets_currency_valid
    CHECK (currency ~ '^[A-Z][A-Z0-9]{2,9}$'),
  CONSTRAINT assets_ticker_stock_only
    CHECK (ticker_id IS NULL OR asset_type = 'STOCK'),
  CONSTRAINT assets_source_identifier_nonempty
    CHECK (source_identifier IS NULL OR btrim(source_identifier) <> ''),
  CONSTRAINT assets_source_metadata_object
    CHECK (jsonb_typeof(source_metadata) = 'object'),
  CONSTRAINT assets_timestamps_valid
    CHECK (
      isfinite(created_at)
      AND isfinite(updated_at)
      AND updated_at >= created_at
    )
);

COMMENT ON TABLE public.assets IS
  'Owner-scoped universal portfolio assets; tickers remains the shared stock-screener identity model.';
COMMENT ON COLUMN public.assets.currency IS
  'Uppercase 3-10 character native currency code, including fiat or crypto quote codes. Portfolio base currency is THB.';
COMMENT ON COLUMN public.assets.ticker_id IS
  'Optional stock-only link, unique per owner so different users may reference the same shared ticker.';

CREATE TABLE public.investment_accounts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL DEFAULT auth.uid()
    REFERENCES auth.users (id) ON DELETE CASCADE,
  name TEXT NOT NULL,
  account_type TEXT NOT NULL,
  institution_name TEXT,
  external_identifier TEXT,
  currency TEXT NOT NULL DEFAULT 'THB',
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT investment_accounts_id_user_id_key UNIQUE (id, user_id),
  CONSTRAINT investment_accounts_name_per_owner_key UNIQUE (user_id, name),
  CONSTRAINT investment_accounts_name_nonempty
    CHECK (btrim(name) <> ''),
  CONSTRAINT investment_accounts_type_valid
    CHECK (
      account_type IN (
        'BROKERAGE',
        'CRYPTO_EXCHANGE',
        'CRYPTO_WALLET',
        'BANK',
        'CASH',
        'OTHER'
      )
    ),
  CONSTRAINT investment_accounts_institution_nonempty
    CHECK (institution_name IS NULL OR btrim(institution_name) <> ''),
  CONSTRAINT investment_accounts_external_identifier_nonempty
    CHECK (external_identifier IS NULL OR btrim(external_identifier) <> ''),
  CONSTRAINT investment_accounts_currency_valid
    CHECK (currency ~ '^[A-Z][A-Z0-9]{2,9}$'),
  CONSTRAINT investment_accounts_source_metadata_object
    CHECK (jsonb_typeof(source_metadata) = 'object'),
  CONSTRAINT investment_accounts_timestamps_valid
    CHECK (
      isfinite(created_at)
      AND isfinite(updated_at)
      AND updated_at >= created_at
    )
);

COMMENT ON TABLE public.investment_accounts IS
  'Owner-scoped brokerage, exchange, wallet, bank, cash, and other investment accounts.';

CREATE TABLE public.transaction_import_batches (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL DEFAULT auth.uid()
    REFERENCES auth.users (id) ON DELETE CASCADE,
  source_type TEXT NOT NULL,
  source_identifier TEXT,
  source_filename TEXT,
  source_fingerprint TEXT,
  status TEXT NOT NULL DEFAULT 'PENDING',
  raw_source_data JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  started_at TIMESTAMPTZ,
  completed_at TIMESTAMPTZ,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT transaction_import_batches_id_user_id_key UNIQUE (id, user_id),
  CONSTRAINT transaction_import_batches_source_type_valid
    CHECK (source_type ~ '^[A-Z][A-Z0-9_]*$'),
  CONSTRAINT transaction_import_batches_source_identifier_nonempty
    CHECK (source_identifier IS NULL OR btrim(source_identifier) <> ''),
  CONSTRAINT transaction_import_batches_source_filename_nonempty
    CHECK (source_filename IS NULL OR btrim(source_filename) <> ''),
  CONSTRAINT transaction_import_batches_source_fingerprint_nonempty
    CHECK (source_fingerprint IS NULL OR btrim(source_fingerprint) <> ''),
  CONSTRAINT transaction_import_batches_status_valid
    CHECK (
      status IN (
        'PENDING',
        'PROCESSING',
        'COMPLETED',
        'COMPLETED_WITH_ERRORS',
        'FAILED'
      )
    ),
  CONSTRAINT transaction_import_batches_raw_source_data_object
    CHECK (jsonb_typeof(raw_source_data) = 'object'),
  CONSTRAINT transaction_import_batches_source_metadata_object
    CHECK (jsonb_typeof(source_metadata) = 'object'),
  CONSTRAINT transaction_import_batches_timestamps_valid
    CHECK (
      isfinite(created_at)
      AND isfinite(updated_at)
      AND updated_at >= created_at
      AND (started_at IS NULL OR isfinite(started_at))
      AND (completed_at IS NULL OR isfinite(completed_at))
      AND (completed_at IS NULL OR started_at IS NOT NULL)
      AND (completed_at IS NULL OR completed_at >= started_at)
    )
);

COMMENT ON TABLE public.transaction_import_batches IS
  'Owner-scoped import-run metadata only; PR 1 does not stage or import spreadsheet rows.';

CREATE TABLE public.transaction_drafts (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL DEFAULT auth.uid()
    REFERENCES auth.users (id) ON DELETE CASCADE,
  investment_account_id UUID NOT NULL,
  asset_id UUID NOT NULL,
  import_batch_id UUID,
  reversal_of_transaction_id UUID,
  transaction_type TEXT NOT NULL,
  transaction_at TIMESTAMPTZ NOT NULL,
  quantity NUMERIC(38, 18),
  unit_price NUMERIC(38, 18),
  gross_amount NUMERIC(38, 18),
  fee_amount NUMERIC(38, 18),
  currency TEXT NOT NULL,
  fx_rate_to_thb NUMERIC(38, 18),
  source_type TEXT NOT NULL,
  source_identifier TEXT,
  source_row_number BIGINT,
  source_fingerprint TEXT,
  raw_source_data JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT transaction_drafts_id_user_id_key UNIQUE (id, user_id),
  CONSTRAINT transaction_drafts_account_owner_fkey
    FOREIGN KEY (investment_account_id, user_id)
    REFERENCES public.investment_accounts (id, user_id)
    ON DELETE RESTRICT,
  CONSTRAINT transaction_drafts_asset_owner_fkey
    FOREIGN KEY (asset_id, user_id)
    REFERENCES public.assets (id, user_id)
    ON DELETE RESTRICT,
  CONSTRAINT transaction_drafts_batch_owner_fkey
    FOREIGN KEY (import_batch_id, user_id)
    REFERENCES public.transaction_import_batches (id, user_id)
    ON DELETE RESTRICT,
  CONSTRAINT transaction_drafts_type_valid
    CHECK (
      transaction_type IN (
        'BUY',
        'SELL',
        'DIVIDEND',
        'STAKING',
        'INTEREST',
        'TRANSFER_IN',
        'TRANSFER_OUT',
        'FEE',
        'REVERSAL'
      )
    ),
  CONSTRAINT transaction_drafts_reversal_shape_valid
    CHECK (
      (transaction_type = 'REVERSAL' AND reversal_of_transaction_id IS NOT NULL)
      OR
      (transaction_type <> 'REVERSAL' AND reversal_of_transaction_id IS NULL)
    ),
  CONSTRAINT transaction_drafts_transaction_at_valid
    CHECK (isfinite(transaction_at)),
  CONSTRAINT transaction_drafts_quantity_positive
    CHECK (quantity IS NULL OR quantity > 0),
  CONSTRAINT transaction_drafts_unit_price_positive
    CHECK (unit_price IS NULL OR unit_price > 0),
  CONSTRAINT transaction_drafts_gross_amount_positive
    CHECK (gross_amount IS NULL OR gross_amount > 0),
  CONSTRAINT transaction_drafts_fee_amount_nonnegative
    CHECK (fee_amount IS NULL OR fee_amount >= 0),
  CONSTRAINT transaction_drafts_fx_rate_positive
    CHECK (fx_rate_to_thb IS NULL OR fx_rate_to_thb > 0),
  CONSTRAINT transaction_drafts_currency_valid
    CHECK (currency ~ '^[A-Z][A-Z0-9]{2,9}$'),
  CONSTRAINT transaction_drafts_source_type_valid
    CHECK (source_type ~ '^[A-Z][A-Z0-9_]*$'),
  CONSTRAINT transaction_drafts_source_identifier_nonempty
    CHECK (source_identifier IS NULL OR btrim(source_identifier) <> ''),
  CONSTRAINT transaction_drafts_source_row_number_positive
    CHECK (source_row_number IS NULL OR source_row_number > 0),
  CONSTRAINT transaction_drafts_source_fingerprint_nonempty
    CHECK (source_fingerprint IS NULL OR btrim(source_fingerprint) <> ''),
  CONSTRAINT transaction_drafts_raw_source_data_object
    CHECK (jsonb_typeof(raw_source_data) = 'object'),
  CONSTRAINT transaction_drafts_source_metadata_object
    CHECK (jsonb_typeof(source_metadata) = 'object'),
  CONSTRAINT transaction_drafts_timestamps_valid
    CHECK (
      isfinite(created_at)
      AND isfinite(updated_at)
      AND updated_at >= created_at
    )
);

COMMENT ON TABLE public.transaction_drafts IS
  'Mutable owner-scoped transaction proposals that require later human confirmation.';
COMMENT ON COLUMN public.transaction_drafts.source_fingerprint IS
  'Nullable source deduplication candidate; drafts intentionally permit duplicates until human review.';

CREATE TABLE public.transactions (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  ledger_sequence BIGINT GENERATED ALWAYS AS IDENTITY
    (SEQUENCE NAME public.transactions_ledger_sequence_seq),
  user_id UUID NOT NULL,
  investment_account_id UUID NOT NULL,
  asset_id UUID NOT NULL,
  confirmed_from_draft_id UUID,
  reversal_of_transaction_id UUID,
  transaction_type TEXT NOT NULL,
  transaction_at TIMESTAMPTZ NOT NULL,
  quantity NUMERIC(38, 18),
  unit_price NUMERIC(38, 18),
  gross_amount NUMERIC(38, 18),
  fee_amount NUMERIC(38, 18),
  currency TEXT NOT NULL,
  fx_rate_to_thb NUMERIC(38, 18),
  source_type TEXT NOT NULL,
  source_identifier TEXT,
  source_row_number BIGINT,
  source_fingerprint TEXT,
  raw_source_data JSONB NOT NULL DEFAULT '{}'::jsonb,
  source_metadata JSONB NOT NULL DEFAULT '{}'::jsonb,
  notes TEXT,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT transactions_ledger_sequence_key UNIQUE (ledger_sequence),
  CONSTRAINT transactions_id_user_id_key UNIQUE (id, user_id),
  CONSTRAINT transactions_reversal_reference_key
    UNIQUE (id, user_id, investment_account_id, asset_id),
  CONSTRAINT transactions_user_id_fkey
    FOREIGN KEY (user_id)
    REFERENCES auth.users (id)
    ON DELETE RESTRICT,
  CONSTRAINT transactions_account_owner_fkey
    FOREIGN KEY (investment_account_id, user_id)
    REFERENCES public.investment_accounts (id, user_id)
    ON DELETE RESTRICT,
  CONSTRAINT transactions_asset_owner_fkey
    FOREIGN KEY (asset_id, user_id)
    REFERENCES public.assets (id, user_id)
    ON DELETE RESTRICT,
  CONSTRAINT transactions_confirmed_draft_owner_fkey
    FOREIGN KEY (confirmed_from_draft_id, user_id)
    REFERENCES public.transaction_drafts (id, user_id)
    ON DELETE RESTRICT,
  CONSTRAINT transactions_type_valid
    CHECK (
      transaction_type IN (
        'BUY',
        'SELL',
        'DIVIDEND',
        'STAKING',
        'INTEREST',
        'TRANSFER_IN',
        'TRANSFER_OUT',
        'FEE',
        'REVERSAL'
      )
    ),
  CONSTRAINT transactions_reversal_shape_valid
    CHECK (
      (transaction_type = 'REVERSAL' AND reversal_of_transaction_id IS NOT NULL)
      OR
      (transaction_type <> 'REVERSAL' AND reversal_of_transaction_id IS NULL)
    ),
  CONSTRAINT transactions_economic_fields_valid
    CHECK (
      CASE transaction_type
        WHEN 'BUY' THEN quantity IS NOT NULL AND unit_price IS NOT NULL
        WHEN 'SELL' THEN quantity IS NOT NULL AND unit_price IS NOT NULL
        WHEN 'DIVIDEND' THEN gross_amount IS NOT NULL
        WHEN 'STAKING' THEN quantity IS NOT NULL OR gross_amount IS NOT NULL
        WHEN 'INTEREST' THEN gross_amount IS NOT NULL
        WHEN 'TRANSFER_IN' THEN quantity IS NOT NULL
        WHEN 'TRANSFER_OUT' THEN quantity IS NOT NULL
        WHEN 'FEE' THEN gross_amount IS NOT NULL
        WHEN 'REVERSAL' THEN true
        ELSE false
      END
    ),
  CONSTRAINT transactions_transaction_at_valid
    CHECK (isfinite(transaction_at)),
  CONSTRAINT transactions_quantity_positive
    CHECK (quantity IS NULL OR quantity > 0),
  CONSTRAINT transactions_unit_price_positive
    CHECK (unit_price IS NULL OR unit_price > 0),
  CONSTRAINT transactions_gross_amount_positive
    CHECK (gross_amount IS NULL OR gross_amount > 0),
  CONSTRAINT transactions_fee_amount_nonnegative
    CHECK (fee_amount IS NULL OR fee_amount >= 0),
  CONSTRAINT transactions_fx_rate_positive
    CHECK (fx_rate_to_thb IS NULL OR fx_rate_to_thb > 0),
  CONSTRAINT transactions_currency_valid
    CHECK (currency ~ '^[A-Z][A-Z0-9]{2,9}$'),
  CONSTRAINT transactions_source_type_valid
    CHECK (source_type ~ '^[A-Z][A-Z0-9_]*$'),
  CONSTRAINT transactions_source_identifier_nonempty
    CHECK (source_identifier IS NULL OR btrim(source_identifier) <> ''),
  CONSTRAINT transactions_source_row_number_positive
    CHECK (source_row_number IS NULL OR source_row_number > 0),
  CONSTRAINT transactions_source_fingerprint_nonempty
    CHECK (source_fingerprint IS NULL OR btrim(source_fingerprint) <> ''),
  CONSTRAINT transactions_raw_source_data_object
    CHECK (jsonb_typeof(raw_source_data) = 'object'),
  CONSTRAINT transactions_source_metadata_object
    CHECK (jsonb_typeof(source_metadata) = 'object'),
  CONSTRAINT transactions_created_at_valid
    CHECK (isfinite(created_at))
);

ALTER TABLE public.transactions
  ADD CONSTRAINT transactions_reversal_owner_account_asset_fkey
  FOREIGN KEY (
    reversal_of_transaction_id,
    user_id,
    investment_account_id,
    asset_id
  )
  REFERENCES public.transactions (
    id,
    user_id,
    investment_account_id,
    asset_id
  )
  ON DELETE RESTRICT;

ALTER TABLE public.transaction_drafts
  ADD CONSTRAINT transaction_drafts_reversal_owner_fkey
  FOREIGN KEY (reversal_of_transaction_id, user_id)
  REFERENCES public.transactions (id, user_id)
  ON DELETE RESTRICT;

COMMENT ON TABLE public.transactions IS
  'Immutable confirmed portfolio ledger facts. Corrections are new linked REVERSAL rows.';
COMMENT ON COLUMN public.transactions.ledger_sequence IS
  'Stable tie-breaker after transaction_at for deterministic ledger replay.';
COMMENT ON COLUMN public.transactions.source_fingerprint IS
  'Nullable idempotency key unique per owner across confirmed sources; manual rows may leave it null.';
COMMENT ON COLUMN public.transactions.reversal_of_transaction_id IS
  'For REVERSAL rows, the same-owner, same-account, same-asset original transaction.';

CREATE TABLE public.transaction_import_errors (
  id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id UUID NOT NULL DEFAULT auth.uid()
    REFERENCES auth.users (id) ON DELETE CASCADE,
  import_batch_id UUID NOT NULL,
  transaction_draft_id UUID,
  source_identifier TEXT,
  source_row_number BIGINT,
  raw_source_data JSONB NOT NULL DEFAULT '{}'::jsonb,
  error_code TEXT NOT NULL,
  error_message TEXT NOT NULL,
  error_details JSONB NOT NULL DEFAULT '{}'::jsonb,
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  updated_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  CONSTRAINT transaction_import_errors_id_user_id_key UNIQUE (id, user_id),
  CONSTRAINT transaction_import_errors_batch_owner_fkey
    FOREIGN KEY (import_batch_id, user_id)
    REFERENCES public.transaction_import_batches (id, user_id)
    ON DELETE RESTRICT,
  CONSTRAINT transaction_import_errors_draft_owner_fkey
    FOREIGN KEY (transaction_draft_id, user_id)
    REFERENCES public.transaction_drafts (id, user_id)
    ON DELETE RESTRICT,
  CONSTRAINT transaction_import_errors_source_identifier_nonempty
    CHECK (source_identifier IS NULL OR btrim(source_identifier) <> ''),
  CONSTRAINT transaction_import_errors_source_row_number_positive
    CHECK (source_row_number IS NULL OR source_row_number > 0),
  CONSTRAINT transaction_import_errors_raw_source_data_object
    CHECK (jsonb_typeof(raw_source_data) = 'object'),
  CONSTRAINT transaction_import_errors_error_code_valid
    CHECK (error_code ~ '^[A-Z][A-Z0-9_]*$'),
  CONSTRAINT transaction_import_errors_error_message_nonempty
    CHECK (btrim(error_message) <> ''),
  CONSTRAINT transaction_import_errors_error_details_object
    CHECK (jsonb_typeof(error_details) = 'object'),
  CONSTRAINT transaction_import_errors_timestamps_valid
    CHECK (
      isfinite(created_at)
      AND isfinite(updated_at)
      AND updated_at >= created_at
    )
);

COMMENT ON TABLE public.transaction_import_errors IS
  'Owner-scoped structured import diagnostics retaining original source-row evidence.';

CREATE UNIQUE INDEX idx_transactions_confirmed_draft_once
  ON public.transactions (user_id, confirmed_from_draft_id)
  WHERE confirmed_from_draft_id IS NOT NULL;

CREATE UNIQUE INDEX idx_transactions_source_fingerprint_owner
  ON public.transactions (user_id, source_fingerprint)
  WHERE source_fingerprint IS NOT NULL;

CREATE UNIQUE INDEX idx_transactions_original_reversed_once
  ON public.transactions (reversal_of_transaction_id)
  WHERE reversal_of_transaction_id IS NOT NULL;

CREATE INDEX idx_assets_user_id
  ON public.assets (user_id);
CREATE INDEX idx_assets_ticker_id
  ON public.assets (ticker_id)
  WHERE ticker_id IS NOT NULL;
CREATE INDEX idx_investment_accounts_user_id
  ON public.investment_accounts (user_id);
CREATE INDEX idx_transaction_import_batches_user_id
  ON public.transaction_import_batches (user_id);
CREATE INDEX idx_transaction_drafts_user_id
  ON public.transaction_drafts (user_id);
CREATE INDEX idx_transaction_drafts_owner_account_asset
  ON public.transaction_drafts (user_id, investment_account_id, asset_id);
CREATE INDEX idx_transaction_drafts_import_batch
  ON public.transaction_drafts (user_id, import_batch_id)
  WHERE import_batch_id IS NOT NULL;
CREATE INDEX idx_transactions_user_id
  ON public.transactions (user_id);
CREATE INDEX idx_transactions_owner_timestamp_order
  ON public.transactions (user_id, transaction_at, ledger_sequence);
CREATE INDEX idx_transactions_owner_account_asset_order
  ON public.transactions (
    user_id,
    investment_account_id,
    asset_id,
    transaction_at,
    ledger_sequence
  );
CREATE INDEX idx_transaction_import_errors_user_id
  ON public.transaction_import_errors (user_id);
CREATE INDEX idx_transaction_import_errors_batch
  ON public.transaction_import_errors (user_id, import_batch_id);

CREATE FUNCTION public.validate_transaction_reversal()
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
    AND NEW.currency IS NOT DISTINCT FROM original.currency
    AND NEW.fx_rate_to_thb IS NOT DISTINCT FROM original.fx_rate_to_thb
  ) THEN
    RAISE EXCEPTION 'A reversal must copy the original transaction financial values'
      USING ERRCODE = '23514';
  END IF;

  RETURN NEW;
END;
$$;

CREATE FUNCTION public.prevent_confirmed_transaction_mutation()
RETURNS TRIGGER
LANGUAGE plpgsql
SET search_path TO pg_catalog
AS $$
BEGIN
  RAISE EXCEPTION 'Confirmed transactions are immutable; append a linked reversal instead'
    USING ERRCODE = '55000';
END;
$$;

CREATE TRIGGER trg_transactions_validate_reversal
  BEFORE INSERT ON public.transactions
  FOR EACH ROW EXECUTE FUNCTION public.validate_transaction_reversal();

CREATE TRIGGER trg_transactions_immutable
  BEFORE UPDATE OR DELETE ON public.transactions
  FOR EACH ROW EXECUTE FUNCTION public.prevent_confirmed_transaction_mutation();

CREATE TRIGGER trg_assets_updated_at
  BEFORE UPDATE ON public.assets
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_investment_accounts_updated_at
  BEFORE UPDATE ON public.investment_accounts
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_transaction_import_batches_updated_at
  BEFORE UPDATE ON public.transaction_import_batches
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_transaction_drafts_updated_at
  BEFORE UPDATE ON public.transaction_drafts
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();
CREATE TRIGGER trg_transaction_import_errors_updated_at
  BEFORE UPDATE ON public.transaction_import_errors
  FOR EACH ROW EXECUTE FUNCTION public.set_updated_at();

REVOKE ALL ON FUNCTION public.validate_transaction_reversal() FROM PUBLIC;
REVOKE ALL ON FUNCTION public.prevent_confirmed_transaction_mutation() FROM PUBLIC;

ALTER TABLE public.assets ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.investment_accounts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transaction_import_batches ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transaction_drafts ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transactions ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.transaction_import_errors ENABLE ROW LEVEL SECURITY;

CREATE POLICY assets_select_own
  ON public.assets FOR SELECT
  TO authenticated
  USING ((SELECT auth.uid()) = user_id);
CREATE POLICY assets_insert_own
  ON public.assets FOR INSERT
  TO authenticated
  WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY assets_update_own
  ON public.assets FOR UPDATE
  TO authenticated
  USING ((SELECT auth.uid()) = user_id)
  WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY assets_delete_own
  ON public.assets FOR DELETE
  TO authenticated
  USING ((SELECT auth.uid()) = user_id);

CREATE POLICY investment_accounts_select_own
  ON public.investment_accounts FOR SELECT
  TO authenticated
  USING ((SELECT auth.uid()) = user_id);
CREATE POLICY investment_accounts_insert_own
  ON public.investment_accounts FOR INSERT
  TO authenticated
  WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY investment_accounts_update_own
  ON public.investment_accounts FOR UPDATE
  TO authenticated
  USING ((SELECT auth.uid()) = user_id)
  WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY investment_accounts_delete_own
  ON public.investment_accounts FOR DELETE
  TO authenticated
  USING ((SELECT auth.uid()) = user_id);

CREATE POLICY transaction_import_batches_select_own
  ON public.transaction_import_batches FOR SELECT
  TO authenticated
  USING ((SELECT auth.uid()) = user_id);

CREATE POLICY transaction_drafts_select_own
  ON public.transaction_drafts FOR SELECT
  TO authenticated
  USING ((SELECT auth.uid()) = user_id);
CREATE POLICY transaction_drafts_insert_own
  ON public.transaction_drafts FOR INSERT
  TO authenticated
  WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY transaction_drafts_update_own
  ON public.transaction_drafts FOR UPDATE
  TO authenticated
  USING ((SELECT auth.uid()) = user_id)
  WITH CHECK ((SELECT auth.uid()) = user_id);
CREATE POLICY transaction_drafts_delete_own
  ON public.transaction_drafts FOR DELETE
  TO authenticated
  USING ((SELECT auth.uid()) = user_id);

CREATE POLICY transactions_select_own
  ON public.transactions FOR SELECT
  TO authenticated
  USING ((SELECT auth.uid()) = user_id);

CREATE POLICY transaction_import_errors_select_own
  ON public.transaction_import_errors FOR SELECT
  TO authenticated
  USING ((SELECT auth.uid()) = user_id);

REVOKE ALL ON TABLE public.assets FROM anon, authenticated, service_role;
REVOKE ALL ON TABLE public.investment_accounts FROM anon, authenticated, service_role;
REVOKE ALL ON TABLE public.transaction_import_batches FROM anon, authenticated, service_role;
REVOKE ALL ON TABLE public.transaction_drafts FROM anon, authenticated, service_role;
REVOKE ALL ON TABLE public.transactions FROM anon, authenticated, service_role;
REVOKE ALL ON TABLE public.transaction_import_errors FROM anon, authenticated, service_role;
REVOKE ALL ON SEQUENCE public.transactions_ledger_sequence_seq
  FROM anon, authenticated, service_role;

GRANT SELECT, INSERT, UPDATE, DELETE
  ON TABLE public.assets, public.investment_accounts, public.transaction_drafts
  TO authenticated;
GRANT SELECT
  ON TABLE
    public.transaction_import_batches,
    public.transactions,
    public.transaction_import_errors
  TO authenticated;

GRANT SELECT, INSERT, UPDATE, DELETE
  ON TABLE
    public.assets,
    public.investment_accounts,
    public.transaction_import_batches,
    public.transaction_drafts,
    public.transaction_import_errors
  TO service_role;
GRANT SELECT, INSERT
  ON TABLE public.transactions
  TO service_role;
GRANT USAGE, SELECT
  ON SEQUENCE public.transactions_ledger_sequence_seq
  TO service_role;
