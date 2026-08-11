"""Supabase reads for confirmed portfolio ledger facts."""

from __future__ import annotations

from uuid import UUID

from supabase import Client

from app.db.supabase import get_supabase_client
from app.services.portfolio_ledger.calculator import (
    LedgerSnapshot,
    TransactionRecord,
    build_ledger_snapshot,
)


TRANSACTION_SELECT = """
id,
investment_account_id,
asset_id,
transaction_type,
transaction_at,
ledger_sequence,
quantity,
unit_price,
gross_amount,
fee_amount,
fee_unit,
currency,
fx_rate_to_thb,
reversal_of_transaction_id,
investment_accounts(name),
assets(symbol, asset_type, currency)
"""


class SupabasePortfolioLedgerRepository:
    def __init__(self, client: Client | None = None) -> None:
        self._client = client

    def _get_client(self) -> Client:
        return self._client if self._client is not None else get_supabase_client()

    def fetch_confirmed_transactions(self, *, user_id: UUID) -> list[TransactionRecord]:
        response = (
            self._get_client()
            .table("transactions")
            .select(TRANSACTION_SELECT)
            .eq("user_id", str(user_id))
            .order("transaction_at")
            .order("ledger_sequence")
            .execute()
        )
        return [
            TransactionRecord.from_supabase_row(row)
            for row in response.data or []
        ]

    def build_snapshot(self, *, user_id: UUID) -> LedgerSnapshot:
        return build_ledger_snapshot(
            self.fetch_confirmed_transactions(user_id=user_id)
        )
