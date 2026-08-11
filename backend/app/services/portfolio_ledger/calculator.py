"""Deterministic confirmed-transaction replay for portfolio state.

The ledger database stores immutable facts. This module rebuilds portfolio
state from those facts rather than trusting spreadsheet summary formulas or
mutable projections.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from typing import Any


ZERO = Decimal("0")
POSITION_ZERO_TOLERANCE = Decimal("0.000001")


class LedgerReplayError(ValueError):
    """Raised when confirmed transactions cannot be replayed deterministically."""


@dataclass(frozen=True)
class TransactionRecord:
    id: str
    investment_account_id: str
    asset_id: str
    transaction_type: str
    transaction_at: datetime
    ledger_sequence: int
    quantity: Decimal | None = None
    unit_price: Decimal | None = None
    gross_amount: Decimal | None = None
    fee_amount: Decimal | None = None
    fee_unit: str | None = None
    currency: str = "THB"
    fx_rate_to_thb: Decimal | None = None
    reversal_of_transaction_id: str | None = None
    investment_account_name: str | None = None
    asset_symbol: str | None = None
    asset_type: str | None = None
    asset_currency: str | None = None

    @classmethod
    def from_supabase_row(cls, row: dict[str, Any]) -> TransactionRecord:
        account = row.get("investment_accounts") or {}
        asset = row.get("assets") or {}
        transaction_at = row["transaction_at"]
        if isinstance(transaction_at, str):
            transaction_at = datetime.fromisoformat(
                transaction_at.replace("Z", "+00:00")
            )
        return cls(
            id=str(row["id"]),
            investment_account_id=str(row["investment_account_id"]),
            asset_id=str(row["asset_id"]),
            transaction_type=str(row["transaction_type"]),
            transaction_at=transaction_at,
            ledger_sequence=int(row["ledger_sequence"]),
            quantity=_decimal_or_none(row.get("quantity")),
            unit_price=_decimal_or_none(row.get("unit_price")),
            gross_amount=_decimal_or_none(row.get("gross_amount")),
            fee_amount=_decimal_or_none(row.get("fee_amount")),
            fee_unit=row.get("fee_unit"),
            currency=str(row.get("currency") or "THB"),
            fx_rate_to_thb=_decimal_or_none(row.get("fx_rate_to_thb")),
            reversal_of_transaction_id=(
                str(row["reversal_of_transaction_id"])
                if row.get("reversal_of_transaction_id")
                else None
            ),
            investment_account_name=account.get("name") if isinstance(account, dict) else None,
            asset_symbol=asset.get("symbol") if isinstance(asset, dict) else None,
            asset_type=asset.get("asset_type") if isinstance(asset, dict) else None,
            asset_currency=asset.get("currency") if isinstance(asset, dict) else None,
        )

    @property
    def position_key(self) -> tuple[str, str]:
        return (self.investment_account_id, self.asset_id)


@dataclass(frozen=True)
class LedgerEffect:
    quantity_delta: Decimal = ZERO
    cost_basis_delta_thb: Decimal = ZERO
    realized_pnl_delta_thb: Decimal = ZERO
    income_delta_thb: Decimal = ZERO
    fee_delta_thb: Decimal = ZERO
    cash_flow_delta_thb: Decimal = ZERO

    def inverse(self) -> LedgerEffect:
        return LedgerEffect(
            quantity_delta=-self.quantity_delta,
            cost_basis_delta_thb=-self.cost_basis_delta_thb,
            realized_pnl_delta_thb=-self.realized_pnl_delta_thb,
            income_delta_thb=-self.income_delta_thb,
            fee_delta_thb=-self.fee_delta_thb,
            cash_flow_delta_thb=-self.cash_flow_delta_thb,
        )


@dataclass
class PortfolioPosition:
    investment_account_id: str
    asset_id: str
    investment_account_name: str | None = None
    asset_symbol: str | None = None
    asset_type: str | None = None
    asset_currency: str | None = None
    quantity: Decimal = ZERO
    cost_basis_thb: Decimal = ZERO
    realized_pnl_thb: Decimal = ZERO
    income_thb: Decimal = ZERO
    fees_thb: Decimal = ZERO
    cash_flow_thb: Decimal = ZERO
    market_value_thb: Decimal | None = None
    unrealized_pnl_thb: Decimal | None = None
    allocation_pct: Decimal | None = None

    @property
    def weighted_average_cost_thb(self) -> Decimal | None:
        if self.quantity <= ZERO:
            return None
        return self.cost_basis_thb / self.quantity

    def apply(self, effect: LedgerEffect, *, transaction_id: str) -> None:
        self.quantity += effect.quantity_delta
        self.cost_basis_thb += effect.cost_basis_delta_thb
        self.realized_pnl_thb += effect.realized_pnl_delta_thb
        self.income_thb += effect.income_delta_thb
        self.fees_thb += effect.fee_delta_thb
        self.cash_flow_thb += effect.cash_flow_delta_thb
        if abs(self.quantity) <= POSITION_ZERO_TOLERANCE:
            self.quantity = ZERO
        if self.quantity < ZERO:
            raise LedgerReplayError(
                f"Transaction {transaction_id} creates a negative position"
            )
        if self.quantity == ZERO:
            self.cost_basis_thb = ZERO

    def to_report(self) -> dict[str, Any]:
        return {
            "investment_account_id": self.investment_account_id,
            "investment_account_name": self.investment_account_name,
            "asset_id": self.asset_id,
            "asset_symbol": self.asset_symbol,
            "asset_type": self.asset_type,
            "asset_currency": self.asset_currency,
            "quantity": _decimal_string(self.quantity),
            "cost_basis_thb": _decimal_string(self.cost_basis_thb),
            "weighted_average_cost_thb": _decimal_string(
                self.weighted_average_cost_thb
            ),
            "realized_pnl_thb": _decimal_string(self.realized_pnl_thb),
            "income_thb": _decimal_string(self.income_thb),
            "fees_thb": _decimal_string(self.fees_thb),
            "cash_flow_thb": _decimal_string(self.cash_flow_thb),
            "market_value_thb": _decimal_string(self.market_value_thb),
            "unrealized_pnl_thb": _decimal_string(self.unrealized_pnl_thb),
            "allocation_pct": _decimal_string(self.allocation_pct),
        }


@dataclass
class LedgerSnapshot:
    positions: dict[tuple[str, str], PortfolioPosition] = field(default_factory=dict)

    @property
    def total_market_value_thb(self) -> Decimal | None:
        marked_values = [
            position.market_value_thb
            for position in self.positions.values()
            if position.market_value_thb is not None
        ]
        if not marked_values:
            return None
        return sum(marked_values, ZERO)

    @property
    def total_cost_basis_thb(self) -> Decimal:
        return sum((position.cost_basis_thb for position in self.positions.values()), ZERO)

    @property
    def total_realized_pnl_thb(self) -> Decimal:
        return sum((position.realized_pnl_thb for position in self.positions.values()), ZERO)

    @property
    def total_income_thb(self) -> Decimal:
        return sum((position.income_thb for position in self.positions.values()), ZERO)

    def to_report(self) -> dict[str, Any]:
        return {
            "total_cost_basis_thb": _decimal_string(self.total_cost_basis_thb),
            "total_realized_pnl_thb": _decimal_string(self.total_realized_pnl_thb),
            "total_income_thb": _decimal_string(self.total_income_thb),
            "total_market_value_thb": _decimal_string(self.total_market_value_thb),
            "positions": [
                position.to_report()
                for _, position in sorted(self.positions.items())
            ],
        }


def build_ledger_snapshot(
    transactions: list[TransactionRecord],
    *,
    mark_prices_thb: dict[str, Decimal] | None = None,
) -> LedgerSnapshot:
    """Replay confirmed transactions in `(transaction_at, ledger_sequence)` order."""

    positions: dict[tuple[str, str], PortfolioPosition] = {}
    effects_by_transaction_id: dict[str, LedgerEffect] = {}

    for record in sorted(transactions, key=lambda row: (row.transaction_at, row.ledger_sequence)):
        position = positions.setdefault(
            record.position_key,
            PortfolioPosition(
                investment_account_id=record.investment_account_id,
                asset_id=record.asset_id,
                investment_account_name=record.investment_account_name,
                asset_symbol=record.asset_symbol,
                asset_type=record.asset_type,
                asset_currency=record.asset_currency,
            ),
        )
        effect = _transaction_effect(
            record,
            position=position,
            effects_by_transaction_id=effects_by_transaction_id,
        )
        position.apply(effect, transaction_id=record.id)
        effects_by_transaction_id[record.id] = effect

    snapshot = LedgerSnapshot(positions=positions)
    _apply_marks(snapshot, mark_prices_thb or {})
    return snapshot


def _transaction_effect(
    record: TransactionRecord,
    *,
    position: PortfolioPosition,
    effects_by_transaction_id: dict[str, LedgerEffect],
) -> LedgerEffect:
    if record.transaction_type == "REVERSAL":
        if not record.reversal_of_transaction_id:
            raise LedgerReplayError("REVERSAL transaction is missing original id")
        try:
            return effects_by_transaction_id[record.reversal_of_transaction_id].inverse()
        except KeyError as exc:
            raise LedgerReplayError(
                f"REVERSAL {record.id} references an unreplayed transaction"
            ) from exc

    quantity = record.quantity or ZERO
    gross_thb = _gross_amount_thb(record)
    quote_fee_thb = (
        _money_thb(record.fee_amount, record.fx_rate_to_thb)
        if record.fee_unit == "QUOTE_CURRENCY"
        else ZERO
    )
    asset_fee_quantity = (
        record.fee_amount
        if record.fee_unit == "ASSET_UNITS" and record.fee_amount is not None
        else ZERO
    )

    match record.transaction_type:
        case "BUY":
            acquired_quantity = quantity - asset_fee_quantity
            if acquired_quantity <= ZERO:
                raise LedgerReplayError(f"BUY {record.id} has no acquired quantity")
            total_cost = gross_thb + quote_fee_thb
            return LedgerEffect(
                quantity_delta=acquired_quantity,
                cost_basis_delta_thb=total_cost,
                fee_delta_thb=quote_fee_thb,
                cash_flow_delta_thb=-total_cost,
            )
        case "SELL":
            removed_quantity = quantity + asset_fee_quantity
            cost_removed = _cost_removed(position, removed_quantity, record.id)
            proceeds = gross_thb - quote_fee_thb
            return LedgerEffect(
                quantity_delta=-removed_quantity,
                cost_basis_delta_thb=-cost_removed,
                realized_pnl_delta_thb=proceeds - cost_removed,
                fee_delta_thb=quote_fee_thb,
                cash_flow_delta_thb=proceeds,
            )
        case "TRANSFER_IN":
            return LedgerEffect(quantity_delta=quantity)
        case "TRANSFER_OUT":
            cost_removed = _cost_removed(position, quantity, record.id)
            return LedgerEffect(
                quantity_delta=-quantity,
                cost_basis_delta_thb=-cost_removed,
            )
        case "DIVIDEND" | "INTEREST":
            net_income = gross_thb - quote_fee_thb
            return LedgerEffect(
                income_delta_thb=net_income,
                fee_delta_thb=quote_fee_thb,
                cash_flow_delta_thb=net_income,
            )
        case "STAKING":
            net_quantity = quantity - asset_fee_quantity
            return LedgerEffect(
                quantity_delta=net_quantity,
                income_delta_thb=gross_thb,
                fee_delta_thb=quote_fee_thb,
                cash_flow_delta_thb=gross_thb - quote_fee_thb,
            )
        case "FEE":
            return LedgerEffect(
                fee_delta_thb=gross_thb,
                cash_flow_delta_thb=-gross_thb,
            )
        case _:
            raise LedgerReplayError(
                f"Unsupported transaction type {record.transaction_type}"
            )


def _cost_removed(
    position: PortfolioPosition,
    quantity: Decimal,
    transaction_id: str,
) -> Decimal:
    if quantity < ZERO:
        raise LedgerReplayError(f"Transaction {transaction_id} has negative quantity")
    if quantity > position.quantity:
        raise LedgerReplayError(
            f"Transaction {transaction_id} removes more units than available"
        )
    average_cost = position.weighted_average_cost_thb or ZERO
    return average_cost * quantity


def _apply_marks(
    snapshot: LedgerSnapshot,
    mark_prices_thb: dict[str, Decimal],
) -> None:
    for position in snapshot.positions.values():
        mark = mark_prices_thb.get(position.asset_id)
        if mark is None:
            continue
        position.market_value_thb = position.quantity * mark
        position.unrealized_pnl_thb = position.market_value_thb - position.cost_basis_thb

    total = snapshot.total_market_value_thb
    if total is None or total <= ZERO:
        return
    for position in snapshot.positions.values():
        if position.market_value_thb is not None:
            position.allocation_pct = position.market_value_thb / total * Decimal("100")


def _money_thb(amount: Decimal | None, fx_rate_to_thb: Decimal | None) -> Decimal:
    if amount is None:
        return ZERO
    return amount * (fx_rate_to_thb or Decimal("1"))


def _gross_amount_thb(record: TransactionRecord) -> Decimal:
    if record.gross_amount is not None:
        return _money_thb(record.gross_amount, record.fx_rate_to_thb)
    if record.quantity is not None and record.unit_price is not None:
        return _money_thb(record.quantity * record.unit_price, record.fx_rate_to_thb)
    return ZERO


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    return Decimal(str(value))


def _decimal_string(value: Decimal | None) -> str | None:
    return None if value is None else format(value, "f")
