-- Trigger functions are implementation details, not RPC endpoints. Supabase
-- may have explicit default grants for anon/authenticated/service_role, so
-- revoke from those roles directly in addition to PUBLIC.

REVOKE ALL ON FUNCTION public.set_updated_at()
FROM PUBLIC, ANON, AUTHENTICATED, SERVICE_ROLE;

REVOKE ALL ON FUNCTION public.validate_transaction_reversal()
FROM PUBLIC, ANON, AUTHENTICATED, SERVICE_ROLE;

REVOKE ALL ON FUNCTION public.prevent_confirmed_transaction_mutation()
FROM PUBLIC, ANON, AUTHENTICATED, SERVICE_ROLE;

REVOKE ALL ON FUNCTION public.prevent_confirmed_transaction_draft_update()
FROM PUBLIC, ANON, AUTHENTICATED, SERVICE_ROLE;
