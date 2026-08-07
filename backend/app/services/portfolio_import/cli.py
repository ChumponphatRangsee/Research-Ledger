"""Command-line dry run and optional staging for an approved workbook export."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path

from app.api.auth import verify_supabase_jwt
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
            "transactions. Requires SUPABASE_ACCESS_TOKEN."
        ),
    )
    parser.add_argument("--output", type=Path)
    return parser


def main() -> int:
    args = _parser().parse_args()
    plan = build_import_plan(
        args.workbook,
        spreadsheet_id=args.spreadsheet_id,
    )

    if args.persist_staging:
        token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
        if not token:
            raise SystemExit(
                "SUPABASE_ACCESS_TOKEN is required for owner-derived staging"
            )
        user = verify_supabase_jwt(token)
        repository = SupabaseTransactionImportRepository()
        fingerprints = {row.source_fingerprint for row in plan.transactions}
        existing = repository.existing_source_fingerprints(
            user_id=user.id,
            source_fingerprints=fingerprints,
        )
        apply_existing_fingerprint_deduplication(plan, existing)
        repository.stage(plan, user_id=user.id)

    rendered = json.dumps(plan.report(), indent=2, sort_keys=True)
    if args.output:
        args.output.write_text(rendered + "\n", encoding="utf-8")
    else:
        print(rendered)
    return 0 if not plan.issues else 2


if __name__ == "__main__":
    raise SystemExit(main())
