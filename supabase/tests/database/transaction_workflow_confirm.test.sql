BEGIN;

CREATE EXTENSION IF NOT EXISTS pgtap WITH SCHEMA extensions;
SET search_path TO public, extensions;

SELECT plan(8);

SELECT ok(
  to_regprocedure('public.confirm_transaction_draft(uuid, uuid)') IS NOT NULL,
  'confirm transaction draft RPC exists'
);

SELECT is(
  (
    SELECT CASE WHEN prosecdef THEN 'definer' ELSE 'invoker' END
    FROM pg_proc
    WHERE oid = 'public.confirm_transaction_draft(uuid, uuid)'::regprocedure
  ),
  'definer',
  'confirm transaction draft RPC is SECURITY DEFINER for atomic backend confirmation'
);

SELECT ok(
  NOT has_function_privilege(
    'PUBLIC',
    'public.confirm_transaction_draft(uuid, uuid)',
    'EXECUTE'
  ),
  'confirm transaction draft RPC is not public executable'
);

SELECT ok(
  NOT has_function_privilege(
    'anon',
    'public.confirm_transaction_draft(uuid, uuid)',
    'EXECUTE'
  ),
  'anon cannot confirm transaction drafts'
);

SELECT ok(
  NOT has_function_privilege(
    'authenticated',
    'public.confirm_transaction_draft(uuid, uuid)',
    'EXECUTE'
  ),
  'authenticated clients cannot directly confirm transaction drafts'
);

SELECT ok(
  has_function_privilege(
    'service_role',
    'public.confirm_transaction_draft(uuid, uuid)',
    'EXECUTE'
  ),
  'service role can execute backend-only confirmation RPC'
);

SELECT isnt_empty(
  $$
    SELECT pg_get_functiondef('public.confirm_transaction_draft(uuid, uuid)'::regprocedure)
    WHERE pg_get_functiondef('public.confirm_transaction_draft(uuid, uuid)'::regprocedure)
      LIKE '%FOR UPDATE%'
  $$,
  'confirmation RPC locks the draft row during idempotent insert'
);

SELECT isnt_empty(
  $$
    SELECT description
    FROM pg_description
    WHERE objoid = 'public.confirm_transaction_draft(uuid, uuid)'::regprocedure
  $$,
  'confirmation RPC is documented'
);

SELECT * FROM finish();
ROLLBACK;
