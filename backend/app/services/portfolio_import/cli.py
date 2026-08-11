"""Command-line dry run and optional staging for an approved workbook export."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
from typing import Any
from uuid import UUID

from dotenv import load_dotenv

from app.api.auth import verify_supabase_jwt
from app.db.supabase import get_supabase_client
from app.services.portfolio_import.planner import (
    apply_existing_fingerprint_deduplication,
    build_import_plan,
)
from app.services.portfolio_import.repository import (
    SupabaseTransactionImportRepository,
)


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description=(
            "Validate the current 15-tab Google Sheets XLSX export. By default "
            "this is read-only and prints a dry-run JSON report."
        )
    )
    parser.add_argument("workbook", type=Path)
    parser.add_argument("--spreadsheet-id", required=True)
    parser.add_argument(
        "--persist-staging",
        action="store_true",
        help=(
            "Create an import batch, drafts, and errors. Never creates confirmed "
            "transactions. Requires SUPABASE_ACCESS_TOKEN, or the explicit "
            "development-only ALLOW_DEV_OWNER_BYPASS + DEV_IMPORT_USER_EMAIL "
            "environment variables."
        ),
    )
    parser.add_argument("--output", type=Path)
    return parser


def _load_cli_env() -> None:
    load_dotenv(override=False)
    load_dotenv(Path(__file__).resolve().parents[4] / ".env", override=False)
    debug_value = os.environ.get("DEBUG", "")
    if debug_value and debug_value.strip().lower() not in {
        "0",
        "1",
        "true",
        "false",
        "yes",
        "no",
        "on",
        "off",
    }:
        os.environ.pop("DEBUG")


def _is_enabled(value: str | None) -> bool:
    return value is not None and value.strip().lower() in {"1", "true", "yes", "on"}


def _user_email(user: Any) -> str | None:
    if isinstance(user, dict):
        email = user.get("email")
    else:
        email = getattr(user, "email", None)
    return email.lower() if isinstance(email, str) else None


def _user_id(user: Any) -> UUID:
    raw_id = user.get("id") if isinstance(user, dict) else getattr(user, "id", None)
    return UUID(str(raw_id))


def _lookup_dev_owner_user_id(email: str, *, client: Any | None = None) -> UUID:
    """Resolve a Supabase Auth user for the dev-only owner bypass.

    This path intentionally still derives ownership from an existing Supabase
    Auth user. It only bypasses the need to obtain a short-lived user JWT from
    the browser or password flow while running a local migration utility.
    """

    normalized_email = email.strip().lower()
    if not normalized_email:
        raise SystemExit("DEV_IMPORT_USER_EMAIL is required for dev owner bypass")

    auth_client = client if client is not None else get_supabase_client()
    page = 1
    per_page = 1000
    while True:
        users = auth_client.auth.admin.list_users(page=page, per_page=per_page)
        if not users:
            break
        for user in users:
            if _user_email(user) == normalized_email:
                return _user_id(user)
        if len(users) < per_page:
            break
        page += 1

    raise SystemExit(
        "DEV_IMPORT_USER_EMAIL did not match any Supabase Auth user"
    )


def _resolve_staging_user_id() -> UUID:
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "").strip()
    if token:
        return verify_supabase_jwt(token).id

    if not _is_enabled(os.environ.get("ALLOW_DEV_OWNER_BYPASS")):
        raise SystemExit(
            "SUPABASE_ACCESS_TOKEN is required for owner-derived staging. "
            "For local development only, set ALLOW_DEV_OWNER_BYPASS=true and "
            "DEV_IMPORT_USER_EMAIL to resolve an existing Supabase Auth user "
            "with the backend service role."
        )

    return _lookup_dev_owner_user_id(os.environ.get("DEV_IMPORT_USER_EMAIL", ""))


def main() -> int:
    _load_cli_env()
    args = _parser().parse_args()
    plan = build_import_plan(
        args.workbook,
        spreadsheet_id=args.spreadsheet_id,
    )

    if args.persist_staging:
        user_id = _resolve_staging_user_id()
        repository = SupabaseTransactionImportRepository()
        fingerprints = {row.source_fingerprint for row in plan.transactions}
        existing = repository.existing_source_fingerprints(
            user_id=user_id,
            source_fingerprints=fingerprints,
        )
        apply_existing_fingerprint_deduplication(plan, existing)
        repository.stage(plan, user_id=user_id)

    rendered = json.dumps(plan.report(), indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if not plan.issues else 2


if __name__ == "__main__":
    raise SystemExit(main())
