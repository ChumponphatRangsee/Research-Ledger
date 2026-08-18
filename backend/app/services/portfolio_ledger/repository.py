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

    def rebuild_position_projections(self, *, user_id: UUID) -> LedgerSnapshot:
        snapshot = self.build_snapshot(user_id=user_id)
        rows = [
            _projection_row(position.to_report(), snapshot=snapshot)
            for position in snapshot.positions.values()
        ]
        (
            self._get_client()
            .rpc(
                "replace_portfolio_position_projections",
                {
                    "p_user_id": str(user_id),
                    "p_rows": rows,
                },
            )
            .execute()
        )
        return snapshot


def _projection_row(
    report: dict[str, object],
    *,
    snapshot: LedgerSnapshot,
) -> dict[str, object]:
    return {
        "investment_account_id": report["investment_account_id"],
        "asset_id": report["asset_id"],
        "as_of_transaction_at": (
            snapshot.as_of_transaction_at.isoformat()
            if snapshot.as_of_transaction_at is not None
            else None
        ),
        "as_of_ledger_sequence": snapshot.as_of_ledger_sequence,
        "source_transaction_count": snapshot.source_transaction_count,
        "source_metadata": dict(snapshot.source_metadata),
        "quantity": report["quantity"],
        "cost_basis_thb": report["cost_basis_thb"],
        "weighted_average_cost_thb": report["weighted_average_cost_thb"],
        "realized_pnl_thb": report["realized_pnl_thb"],
        "income_thb": report["income_thb"],
        "fees_thb": report["fees_thb"],
        "cash_flow_thb": report["cash_flow_thb"],
        "market_value_thb": report["market_value_thb"],
        "unrealized_pnl_thb": report["unrealized_pnl_thb"],
        "allocation_pct": report["allocation_pct"],
    }
