"""Owner-scoped persistence for draft review and confirmation workflow."""

from __future__ import annotations

from datetime import UTC, datetime
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


class TransactionDraftAlreadyConfirmed(ValueError):
    pass


class TransactionNotFound(LookupError):
    pass


class TransactionAlreadyReversed(ValueError):
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

    def create_draft(
        self,
        *,
        user_id: UUID,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        response = (
            self._get_client()
            .table("transaction_drafts")
            .insert(
                {
                    **payload,
                    "user_id": str(user_id),
                    "source_type": payload.get("source_type") or "MANUAL",
                    "raw_source_data": payload.get("raw_source_data") or {},
                    "source_metadata": payload.get("source_metadata") or {
                        "entry_method": "manual"
                    },
                }
            )
            .execute()
        )
        data = response.data or []
        if not data:
            raise RuntimeError("Supabase did not return a transaction draft")
        return data[0]

    def update_draft(
        self,
        *,
        user_id: UUID,
        draft_id: UUID,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        existing = self._get_draft(user_id=user_id, draft_id=draft_id)
        if existing is None:
            raise TransactionDraftNotFound
        if self._confirmed_transactions_by_draft(
            user_id=user_id,
            draft_ids=[str(draft_id)],
        ):
            raise TransactionDraftAlreadyConfirmed(
                "Confirmed transaction drafts cannot be edited"
            )

        protected = {
            "id",
            "user_id",
            "import_batch_id",
            "created_at",
            "updated_at",
            "confirmed_transaction_id",
            "status",
        }
        update_payload = {
            key: value
            for key, value in payload.items()
            if key not in protected and value is not _UNSET
        }
        if not update_payload:
            return {
                **existing,
                "status": "pending",
                "confirmed_transaction_id": None,
            }

        response = (
            self._get_client()
            .table("transaction_drafts")
            .update(update_payload)
            .eq("user_id", str(user_id))
            .eq("id", str(draft_id))
            .execute()
        )
        data = response.data or []
        if not data:
            raise TransactionDraftNotFound
        return {
            **data[0],
            "status": "pending",
            "confirmed_transaction_id": None,
        }

    def create_correction_draft(
        self,
        *,
        user_id: UUID,
        transaction_id: UUID,
        payload: dict[str, Any],
    ) -> dict[str, Any]:
        original = self._get_confirmed_transaction(
            user_id=user_id,
            transaction_id=transaction_id,
        )
        if original is None:
            raise TransactionNotFound

        base_payload = {
            "investment_account_id": original["investment_account_id"],
            "asset_id": original["asset_id"],
            "reversal_of_transaction_id": None,
            "transaction_type": original["transaction_type"],
            "transaction_at": original["transaction_at"],
            "quantity": original.get("quantity"),
            "unit_price": original.get("unit_price"),
            "gross_amount": original.get("gross_amount"),
            "fee_amount": original.get("fee_amount"),
            "fee_unit": original.get("fee_unit"),
            "currency": original["currency"],
            "fx_rate_to_thb": original.get("fx_rate_to_thb"),
            "source_type": "MANUAL",
            "source_identifier": f"correction:{original['id']}",
            "raw_source_data": {"correction_of_transaction_id": original["id"]},
            "source_metadata": {
                "entry_method": "manual_correction",
                "correction_of_transaction_id": original["id"],
            },
            "notes": None,
        }
        return self.create_draft(
            user_id=user_id,
            payload={**base_payload, **payload},
        )

    def create_reversal_draft(
        self,
        *,
        user_id: UUID,
        transaction_id: UUID,
        transaction_at: datetime | None = None,
        notes: str | None = None,
    ) -> dict[str, Any]:
        client = self._get_client()
        original = self._get_confirmed_transaction(
            user_id=user_id,
            transaction_id=transaction_id,
        )
        if original is None:
            raise TransactionNotFound
        if original.get("transaction_type") == "REVERSAL":
            raise TransactionAlreadyReversed("A reversal cannot reverse another reversal")
        if self._confirmed_reversal_exists(
            user_id=user_id,
            transaction_id=transaction_id,
        ):
            raise TransactionAlreadyReversed(
                "Transaction already has a confirmed reversal"
            )

        existing_draft = self._existing_reversal_draft(
            user_id=user_id,
            transaction_id=transaction_id,
        )
        if existing_draft is not None:
            return existing_draft

        reversal_at = _utc_datetime(transaction_at or datetime.now(tz=UTC))
        if reversal_at < _parse_datetime(original["transaction_at"]):
            raise ValueError("Reversal date cannot precede the original transaction")

        payload = {
            "user_id": str(user_id),
            "investment_account_id": original["investment_account_id"],
            "asset_id": original["asset_id"],
            "reversal_of_transaction_id": original["id"],
            "transaction_type": "REVERSAL",
            "transaction_at": reversal_at.isoformat(),
            "quantity": original.get("quantity"),
            "unit_price": original.get("unit_price"),
            "gross_amount": original.get("gross_amount"),
            "fee_amount": original.get("fee_amount"),
            "fee_unit": original.get("fee_unit"),
            "currency": original["currency"],
            "fx_rate_to_thb": original.get("fx_rate_to_thb"),
            "source_type": "MANUAL",
            "source_identifier": f"reversal:{original['id']}",
            "raw_source_data": {"reversal_of_transaction_id": original["id"]},
            "source_metadata": {
                "entry_method": "manual_reversal",
                "reversal_of_transaction_id": original["id"],
            },
            "notes": notes,
        }
        response = (
            client.table("transaction_drafts")
            .insert(payload)
            .execute()
        )
        data = response.data or []
        if not data:
            raise RuntimeError("Supabase did not return a reversal draft")
        return data[0]

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

    def _get_draft(
        self,
        *,
        user_id: UUID,
        draft_id: UUID,
    ) -> dict[str, Any] | None:
        response = (
            self._get_client()
            .table("transaction_drafts")
            .select(DRAFT_SELECT)
            .eq("user_id", str(user_id))
            .eq("id", str(draft_id))
            .limit(1)
            .execute()
        )
        data = response.data or []
        return data[0] if data else None

    def _get_confirmed_transaction(
        self,
        *,
        user_id: UUID,
        transaction_id: UUID,
    ) -> dict[str, Any] | None:
        response = (
            self._get_client()
            .table("transactions")
            .select(
                "id, user_id, investment_account_id, asset_id, "
                "reversal_of_transaction_id, transaction_type, transaction_at, "
                "quantity, unit_price, gross_amount, fee_amount, fee_unit, "
                "currency, fx_rate_to_thb"
            )
            .eq("user_id", str(user_id))
            .eq("id", str(transaction_id))
            .limit(1)
            .execute()
        )
        data = response.data or []
        return data[0] if data else None

    def _confirmed_reversal_exists(
        self,
        *,
        user_id: UUID,
        transaction_id: UUID,
    ) -> bool:
        response = (
            self._get_client()
            .table("transactions")
            .select("id")
            .eq("user_id", str(user_id))
            .eq("reversal_of_transaction_id", str(transaction_id))
            .limit(1)
            .execute()
        )
        return bool(response.data)

    def _existing_reversal_draft(
        self,
        *,
        user_id: UUID,
        transaction_id: UUID,
    ) -> dict[str, Any] | None:
        response = (
            self._get_client()
            .table("transaction_drafts")
            .select(DRAFT_SELECT)
            .eq("user_id", str(user_id))
            .eq("reversal_of_transaction_id", str(transaction_id))
            .limit(1)
            .execute()
        )
        data = response.data or []
        return data[0] if data else None


def _parse_datetime(value: Any) -> datetime:
    if isinstance(value, datetime):
        return _utc_datetime(value)
    return _utc_datetime(datetime.fromisoformat(str(value).replace("Z", "+00:00")))


def _utc_datetime(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


class _Unset:
    pass


_UNSET = _Unset()
