from __future__ import annotations

from datetime import UTC, datetime
from decimal import Decimal

import pytest

from app.services.portfolio_ledger import (
    LedgerReplayError,
    SupabasePortfolioLedgerRepository,
    TransactionRecord,
    build_ledger_snapshot,
)


ACCOUNT_ID = "11111111-1111-4111-8111-111111111111"
ASSET_ID = "22222222-2222-4222-8222-222222222222"
SECOND_ASSET_ID = "33333333-3333-4333-8333-333333333333"


def tx(
    tx_id: str,
    transaction_type: str,
    sequence: int,
    *,
    quantity: str | None = None,
    gross_amount: str | None = None,
    fee_amount: str | None = None,
    fee_unit: str | None = None,
    fx_rate_to_thb: str = "35",
    reversal_of_transaction_id: str | None = None,
    asset_id: str = ASSET_ID,
) -> TransactionRecord:
    return TransactionRecord(
        id=tx_id,
        investment_account_id=ACCOUNT_ID,
        investment_account_name="Best",
        asset_id=asset_id,
        asset_symbol="MSFT" if asset_id == ASSET_ID else "NVDA",
        asset_type="STOCK",
        asset_currency="USD",
        transaction_type=transaction_type,
        transaction_at=datetime(2026, 1, sequence, tzinfo=UTC),
        ledger_sequence=sequence,
        quantity=Decimal(quantity) if quantity is not None else None,
        gross_amount=Decimal(gross_amount) if gross_amount is not None else None,
        fee_amount=Decimal(fee_amount) if fee_amount is not None else None,
        fee_unit=fee_unit,
        currency="USD",
        fx_rate_to_thb=Decimal(fx_rate_to_thb),
        reversal_of_transaction_id=reversal_of_transaction_id,
    )


def only_position(transactions: list[TransactionRecord]):
    snapshot = build_ledger_snapshot(transactions)
    return snapshot.positions[(ACCOUNT_ID, ASSET_ID)]


def test_replays_buy_sell_with_weighted_average_cost_and_realized_pnl():
    position = only_position(
        [
            tx("buy-1", "BUY", 1, quantity="10", gross_amount="100", fee_amount="1", fee_unit="QUOTE_CURRENCY"),
            tx("buy-2", "BUY", 2, quantity="10", gross_amount="300", fee_amount="3", fee_unit="QUOTE_CURRENCY"),
            tx("sell-1", "SELL", 3, quantity="5", gross_amount="125", fee_amount="1", fee_unit="QUOTE_CURRENCY"),
        ]
    )

    assert position.quantity == Decimal("15")
    assert position.cost_basis_thb == Decimal("10605.00")
    assert position.weighted_average_cost_thb == Decimal("707.00")
    assert position.realized_pnl_thb == Decimal("805.00")
    assert position.fees_thb == Decimal("175")
    assert position.cash_flow_thb == Decimal("-9800")


def test_asset_unit_buy_fee_reduces_acquired_quantity_without_cash_fee():
    position = only_position(
        [
            tx("buy-1", "BUY", 1, quantity="1", gross_amount="1000", fee_amount="0.01", fee_unit="ASSET_UNITS"),
        ]
    )

    assert position.quantity == Decimal("0.99")
    assert position.cost_basis_thb == Decimal("35000")
    assert position.weighted_average_cost_thb == Decimal("35000") / Decimal("0.99")
    assert position.fees_thb == Decimal("0")


def test_buy_cost_basis_uses_quantity_times_unit_price_when_gross_amount_missing():
    position = only_position(
        [
            TransactionRecord(
                id="buy-1",
                investment_account_id=ACCOUNT_ID,
                asset_id=ASSET_ID,
                transaction_type="BUY",
                transaction_at=datetime(2026, 1, 1, tzinfo=UTC),
                ledger_sequence=1,
                quantity=Decimal("2"),
                unit_price=Decimal("10"),
                gross_amount=None,
                fee_amount=Decimal("1"),
                fee_unit="QUOTE_CURRENCY",
                currency="USD",
                fx_rate_to_thb=Decimal("35"),
            )
        ]
    )

    assert position.quantity == Decimal("2")
    assert position.cost_basis_thb == Decimal("735")
    assert position.cash_flow_thb == Decimal("-735")


def test_tiny_fractional_residue_is_normalized_to_zero():
    position = only_position(
        [
            tx("buy-1", "BUY", 1, quantity="1.0000001", gross_amount="10"),
            tx("sell-1", "SELL", 2, quantity="1", gross_amount="10"),
        ]
    )

    assert position.quantity == Decimal("0")
    assert position.cost_basis_thb == Decimal("0")


def test_reversal_inverts_original_transaction_effect():
    position = only_position(
        [
            tx("buy-1", "BUY", 1, quantity="10", gross_amount="100", fee_amount="1", fee_unit="QUOTE_CURRENCY"),
            tx("reverse-buy-1", "REVERSAL", 2, reversal_of_transaction_id="buy-1"),
        ]
    )

    assert position.quantity == Decimal("0")
    assert position.cost_basis_thb == Decimal("0")
    assert position.fees_thb == Decimal("0")
    assert position.cash_flow_thb == Decimal("0")


def test_rejects_negative_positions_during_replay():
    with pytest.raises(LedgerReplayError, match="removes more units than available"):
        only_position(
            [
                tx("buy-1", "BUY", 1, quantity="1", gross_amount="10"),
                tx("sell-1", "SELL", 2, quantity="2", gross_amount="20"),
            ]
        )


def test_marks_unrealized_pnl_and_allocation_with_supplied_prices():
    snapshot = build_ledger_snapshot(
        [
            tx("buy-1", "BUY", 1, quantity="2", gross_amount="20"),
            tx("buy-2", "BUY", 2, quantity="1", gross_amount="30", asset_id=SECOND_ASSET_ID),
        ],
        mark_prices_thb={
            ASSET_ID: Decimal("400"),
            SECOND_ASSET_ID: Decimal("1400"),
        },
    )

    first = snapshot.positions[(ACCOUNT_ID, ASSET_ID)]
    second = snapshot.positions[(ACCOUNT_ID, SECOND_ASSET_ID)]
    assert first.market_value_thb == Decimal("800")
    assert first.unrealized_pnl_thb == Decimal("100")
    assert first.allocation_pct == Decimal("800") / Decimal("2200") * Decimal("100")
    assert second.market_value_thb == Decimal("1400")
    assert snapshot.total_market_value_thb == Decimal("2200")


def test_from_supabase_row_preserves_joined_account_and_asset_metadata():
    record = TransactionRecord.from_supabase_row(
        {
            "id": "tx-1",
            "investment_account_id": ACCOUNT_ID,
            "asset_id": ASSET_ID,
            "transaction_type": "BUY",
            "transaction_at": "2026-01-01T00:00:00Z",
            "ledger_sequence": 1,
            "quantity": "1.25",
            "gross_amount": "100.50",
            "currency": "USD",
            "fx_rate_to_thb": "35.5",
            "investment_accounts": {"name": "Best"},
            "assets": {"symbol": "MSFT", "asset_type": "STOCK", "currency": "USD"},
        }
    )

    assert record.quantity == Decimal("1.25")
    assert record.gross_amount == Decimal("100.50")
    assert record.investment_account_name == "Best"
    assert record.asset_symbol == "MSFT"
    assert record.transaction_at == datetime(2026, 1, 1, tzinfo=UTC)


class RecordingQuery:
    def __init__(self, data):
        self.data = data
        self.calls = []

    def select(self, columns):
        self.calls.append(("select", columns))
        return self

    def eq(self, column, value):
        self.calls.append(("eq", column, value))
        return self

    def order(self, column):
        self.calls.append(("order", column))
        return self

    def execute(self):
        return type("Response", (), {"data": self.data})()


class RecordingClient:
    def __init__(self, data):
        self.query = RecordingQuery(data)
        self.tables = []

    def table(self, table):
        self.tables.append(table)
        return self.query


def test_repository_fetches_confirmed_transactions_for_verified_owner_only():
    client = RecordingClient(
        [
            {
                "id": "tx-1",
                "investment_account_id": ACCOUNT_ID,
                "asset_id": ASSET_ID,
                "transaction_type": "BUY",
                "transaction_at": "2026-01-01T00:00:00Z",
                "ledger_sequence": 1,
                "quantity": "1",
                "gross_amount": "100",
                "currency": "USD",
                "fx_rate_to_thb": "35",
                "investment_accounts": {"name": "Best"},
                "assets": {"symbol": "MSFT", "asset_type": "STOCK", "currency": "USD"},
            }
        ]
    )

    records = SupabasePortfolioLedgerRepository(client).fetch_confirmed_transactions(
        user_id=ACCOUNT_ID
    )

    assert len(records) == 1
    assert client.tables == ["transactions"]
    assert ("eq", "user_id", ACCOUNT_ID) in client.query.calls
    assert ("order", "transaction_at") in client.query.calls
    assert ("order", "ledger_sequence") in client.query.calls
