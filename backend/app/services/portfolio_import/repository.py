"""Owner-scoped Supabase persistence for import batches, drafts, and errors."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import UUID

from supabase import Client

from app.db.supabase import get_supabase_client
from app.services.portfolio_import.models import ImportPlan, NormalizedTransaction


IMPORT_BATCH_SELECT = """
id,
user_id,
source_type,
source_identifier,
source_filename,
source_fingerprint,
status,
raw_source_data,
source_metadata,
started_at,
completed_at,
created_at,
updated_at
"""

IMPORT_ERROR_SELECT = """
id,
user_id,
import_batch_id,
transaction_draft_id,
source_identifier,
source_row_number,
raw_source_data,
error_code,
error_message,
error_details,
created_at,
updated_at,
transaction_import_batches(source_type, source_filename, status, created_at)
"""


class SupabaseTransactionImportRepository:
    """Stage spreadsheet output without ever inserting confirmed transactions."""

    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    def _get_client(self) -> Client:
        return self._client if self._client is not None else get_supabase_client()

    def existing_source_fingerprints(
        self,
        *,
        user_id: UUID,
        source_fingerprints: set[str],
    ) -> set[str]:
        if not source_fingerprints:
            return set()

        existing: set[str] = set()
        values = sorted(source_fingerprints)
        for table in ("transaction_drafts", "transactions"):
            response = (
                self._get_client()
                .table(table)
                .select("source_fingerprint")
                .eq("user_id", str(user_id))
                .in_("source_fingerprint", values)
                .execute()
            )
            for row in response.data or []:
                fingerprint = row.get("source_fingerprint")
                if isinstance(fingerprint, str):
                    existing.add(fingerprint)
        return existing

    def list_batches(
        self,
        *,
        user_id: UUID,
        limit: int = 50,
    ) -> list[dict[str, Any]]:
        response = (
            self._get_client()
            .table("transaction_import_batches")
            .select(IMPORT_BATCH_SELECT)
            .eq("user_id", str(user_id))
            .order("created_at", desc=True)
            .limit(limit)
            .execute()
        )
        return response.data or []

    def list_errors(
        self,
        *,
        user_id: UUID,
        import_batch_id: UUID | None = None,
        limit: int = 200,
    ) -> list[dict[str, Any]]:
        query = (
            self._get_client()
            .table("transaction_import_errors")
            .select(IMPORT_ERROR_SELECT)
            .eq("user_id", str(user_id))
            .order("created_at", desc=True)
            .limit(limit)
        )
        if import_batch_id is not None:
            query = query.eq("import_batch_id", str(import_batch_id))
        response = query.execute()
        return response.data or []

    def stage(self, plan: ImportPlan, *, user_id: UUID) -> ImportPlan:
        client = self._get_client()
        owner_id = str(user_id)
        now = datetime.now(timezone.utc).isoformat()
        batch_payload = {
            "user_id": owner_id,
            "source_type": "GOOGLE_SHEETS",
            "source_identifier": plan.spreadsheet_id,
            "source_filename": plan.source_filename,
            "source_fingerprint": plan.source_fingerprint,
            "status": "PROCESSING",
            "raw_source_data": {
                "spreadsheet_id": plan.spreadsheet_id,
                "sheet_titles": list(plan.sheet_titles),
            },
            "source_metadata": {
                "mode": "STAGING_ONLY",
                "rows_read": plan.rows_read,
                "confirmed_transactions_written": 0,
            },
            "started_at": now,
        }
        response = (
            client.table("transaction_import_batches").insert(batch_payload).execute()
        )
        if not response.data or not isinstance(response.data, list):
            raise RuntimeError("Supabase did not return the created import batch")
        batch_id = str(response.data[0]["id"])
        plan.import_batch_id = batch_id

        try:
            account_ids = self._upsert_accounts(
                plan.transactions,
                user_id=owner_id,
            )
            asset_ids = self._upsert_assets(
                plan.transactions,
                user_id=owner_id,
            )
            draft_payloads = [
                transaction.draft_payload(
                    user_id=owner_id,
                    import_batch_id=batch_id,
                    investment_account_id=account_ids[transaction.account_name],
                    asset_id=asset_ids[
                        (
                            transaction.asset_type,
                            transaction.symbol,
                            transaction.asset_currency,
                        )
                    ],
                )
                for transaction in plan.transactions
            ]
            if draft_payloads:
                client.table("transaction_drafts").insert(draft_payloads).execute()

            error_payloads = [
                issue.to_error_payload(user_id=owner_id, import_batch_id=batch_id)
                for issue in plan.issues
            ]
            if error_payloads:
                client.table("transaction_import_errors").insert(
                    error_payloads
                ).execute()

            completed_at = datetime.now(timezone.utc).isoformat()
            status = "COMPLETED_WITH_ERRORS" if plan.issues else "COMPLETED"
            (
                client.table("transaction_import_batches")
                .update(
                    {
                        "status": status,
                        "completed_at": completed_at,
                        "source_metadata": {
                            "mode": "STAGING_ONLY",
                            "rows_read": plan.rows_read,
                            "drafts_created": len(plan.transactions),
                            "errors_created": len(plan.issues),
                            "confirmed_transactions_written": 0,
                        },
                    }
                )
                .eq("id", batch_id)
                .eq("user_id", owner_id)
                .execute()
            )
        except Exception:
            (
                client.table("transaction_import_batches")
                .update(
                    {
                        "status": "FAILED",
                        "completed_at": datetime.now(timezone.utc).isoformat(),
                    }
                )
                .eq("id", batch_id)
                .eq("user_id", owner_id)
                .execute()
            )
            raise
        return plan

    def _upsert_accounts(
        self,
        transactions: list[NormalizedTransaction],
        *,
        user_id: str,
    ) -> dict[str, str]:
        unique = {row.account_name: row for row in transactions}
        account_ids: dict[str, str] = {}
        for name, transaction in sorted(unique.items()):
            existing = (
                self._get_client()
                .table("investment_accounts")
                .select("id")
                .eq("user_id", user_id)
                .eq("name", name)
                .limit(1)
                .execute()
            )
            if existing.data:
                account_ids[name] = self._single_id(existing.data, "investment account")
                continue
            created = (
                self._get_client()
                .table("investment_accounts")
                .insert(transaction.account_payload(user_id=user_id))
                .execute()
            )
            account_ids[name] = self._single_id(created.data, "investment account")
        return account_ids

    def _upsert_assets(
        self,
        transactions: list[NormalizedTransaction],
        *,
        user_id: str,
    ) -> dict[tuple[str, str, str], str]:
        unique = {
            (row.asset_type, row.symbol, row.asset_currency): row
            for row in transactions
        }
        asset_ids: dict[tuple[str, str, str], str] = {}
        for key, transaction in sorted(unique.items()):
            existing = (
                self._get_client()
                .table("assets")
                .select("id")
                .eq("user_id", user_id)
                .eq("asset_type", transaction.asset_type)
                .eq("symbol", transaction.symbol)
                .eq("currency", transaction.asset_currency)
                .limit(1)
                .execute()
            )
            if existing.data:
                asset_ids[key] = self._single_id(existing.data, "asset")
                continue
            created = (
                self._get_client()
                .table("assets")
                .insert(transaction.asset_payload(user_id=user_id))
                .execute()
            )
            asset_ids[key] = self._single_id(created.data, "asset")
        return asset_ids

    @staticmethod
    def _single_id(data: Any, object_name: str) -> str:
        if not isinstance(data, list) or not data or "id" not in data[0]:
            raise RuntimeError(f"Supabase did not return the staged {object_name}")
        return str(data[0]["id"])
