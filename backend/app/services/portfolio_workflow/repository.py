"""Owner-scoped persistence for draft review and confirmation workflow."""

from __future__ import annotations

from typing import Any, Literal
from uuid import UUID

from supabase import Client

from app.db.supabase import get_supabase_client


DraftStatus = Literal["pending", "confirmed", "all"]


DRAFT_SELECT = """
id,
user_id,
investment_account_id,
asset_id,
import_batch_id,
reversal_of_transaction_id,
transaction_type,
transaction_at,
quantity,
unit_price,
gross_amount,
fee_amount,
fee_unit,
currency,
fx_rate_to_thb,
source_type,
source_identifier,
source_row_number,
source_fingerprint,
raw_source_data,
source_metadata,
notes,
created_at,
updated_at,
investment_accounts(name, account_type),
assets(symbol, name, asset_type, currency)
"""


class TransactionDraftNotFound(LookupError):
    pass


class SupabaseTransactionWorkflowRepository:
    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    def _get_client(self) -> Client:
        return self._client if self._client is not None else get_supabase_client()

    def list_drafts(
        self,
        *,
        user_id: UUID,
        status: DraftStatus = "pending",
        import_batch_id: UUID | None = None,
    ) -> list[dict[str, Any]]:
        query = (
            self._get_client()
            .table("transaction_drafts")
            .select(DRAFT_SELECT)
            .eq("user_id", str(user_id))
            .order("transaction_at")
            .order("created_at")
        )
        if import_batch_id is not None:
            query = query.eq("import_batch_id", str(import_batch_id))
        drafts = query.execute().data or []
        draft_ids = [row["id"] for row in drafts]
        confirmed_by_draft = self._confirmed_transactions_by_draft(
            user_id=user_id,
            draft_ids=draft_ids,
        )

        hydrated: list[dict[str, Any]] = []
        for row in drafts:
            confirmed = confirmed_by_draft.get(row["id"])
            row_status = "confirmed" if confirmed else "pending"
            if status != "all" and status != row_status:
                continue
            hydrated.append(
                {
                    **row,
                    "status": row_status,
                    "confirmed_transaction_id": (
                        confirmed["id"] if confirmed is not None else None
                    ),
                }
            )
        return hydrated

    def confirm_draft(self, *, user_id: UUID, draft_id: UUID) -> dict[str, Any]:
        try:
            response = (
                self._get_client()
                .rpc(
                    "confirm_transaction_draft",
                    {
                        "p_draft_id": str(draft_id),
                        "p_user_id": str(user_id),
                    },
                )
                .execute()
            )
        except Exception as exc:
            if "Transaction draft not found" in str(exc):
                raise TransactionDraftNotFound from exc
            raise

        data = response.data
        if isinstance(data, list):
            if not data:
                raise TransactionDraftNotFound
            return data[0]
        if isinstance(data, dict):
            return data
        raise RuntimeError("Supabase did not return a confirmed transaction")

    def _confirmed_transactions_by_draft(
        self,
        *,
        user_id: UUID,
        draft_ids: list[str],
    ) -> dict[str, dict[str, Any]]:
        if not draft_ids:
            return {}
        response = (
            self._get_client()
            .table("transactions")
            .select("id, confirmed_from_draft_id")
            .eq("user_id", str(user_id))
            .in_("confirmed_from_draft_id", draft_ids)
            .execute()
        )
        return {
            row["confirmed_from_draft_id"]: row
            for row in response.data or []
            if row.get("confirmed_from_draft_id")
        }
