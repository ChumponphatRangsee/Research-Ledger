"""Validated models for spreadsheet staging and dry-run reporting."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal
from enum import StrEnum
from typing import Any


class FeeUnit(StrEnum):
    QUOTE_CURRENCY = "QUOTE_CURRENCY"
    ASSET_UNITS = "ASSET_UNITS"


@dataclass(frozen=True)
class WorkbookTransactionRow:
    row_number: int
    values: dict[str, Any]
    formulas: dict[str, str]
    raw_source_data: dict[str, Any]


@dataclass(frozen=True)
class WorkbookSnapshot:
    source_filename: str
    source_fingerprint: str
    sheet_titles: tuple[str, ...]
    transaction_rows: tuple[WorkbookTransactionRow, ...]
    holdings: dict[tuple[str, str], Decimal]


@dataclass(frozen=True)
class ImportIssue:
    error_code: str
    error_message: str
    source_row_number: int | None = None
    source_identifier: str | None = None
    raw_source_data: dict[str, Any] = field(default_factory=dict)
    error_details: dict[str, Any] = field(default_factory=dict)

    def to_error_payload(self, *, user_id: str, import_batch_id: str) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "import_batch_id": import_batch_id,
            "source_identifier": self.source_identifier,
            "source_row_number": self.source_row_number,
            "raw_source_data": self.raw_source_data,
            "error_code": self.error_code,
            "error_message": self.error_message,
            "error_details": self.error_details,
        }


@dataclass(frozen=True)
class NormalizedTransaction:
    source_identifier: str
    source_row_number: int
    source_fingerprint: str
    account_name: str
    account_type: str
    symbol: str
    asset_name: str
    asset_type: str
    asset_currency: str
    transaction_type: str
    transaction_at: datetime
    quantity: Decimal | None
    unit_price: Decimal | None
    gross_amount: Decimal | None
    fee_amount: Decimal | None
    fee_unit: FeeUnit | None
    currency: str
    fx_rate_to_thb: Decimal | None
    raw_source_data: dict[str, Any]
    source_metadata: dict[str, Any]
    notes: str | None = None

    def signed_quantity(self) -> Decimal:
        quantity = self.quantity or Decimal(0)
        asset_fee = (
            self.fee_amount or Decimal(0)
            if self.fee_unit == FeeUnit.ASSET_UNITS
            else Decimal(0)
        )
        if self.transaction_type in {"BUY", "TRANSFER_IN", "STAKING"}:
            return quantity - asset_fee
        if self.transaction_type in {"SELL", "TRANSFER_OUT"}:
            return -(quantity + asset_fee)
        return Decimal(0)

    def account_payload(self, *, user_id: str) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "name": self.account_name,
            "account_type": self.account_type,
            "currency": "THB",
            "source_metadata": {"source": "GOOGLE_SHEETS"},
        }

    def asset_payload(self, *, user_id: str) -> dict[str, Any]:
        return {
            "user_id": user_id,
            "symbol": self.symbol,
            "name": self.asset_name,
            "asset_type": self.asset_type,
            "currency": self.asset_currency,
            "source_identifier": self.symbol,
            "source_metadata": {"source": "GOOGLE_SHEETS"},
        }

    def draft_payload(
        self,
        *,
        user_id: str,
        import_batch_id: str,
        investment_account_id: str,
        asset_id: str,
    ) -> dict[str, Any]:
        def decimal_string(value: Decimal | None) -> str | None:
            return None if value is None else format(value, "f")

        return {
            "user_id": user_id,
            "investment_account_id": investment_account_id,
            "asset_id": asset_id,
            "import_batch_id": import_batch_id,
            "transaction_type": self.transaction_type,
            "transaction_at": self.transaction_at.isoformat(),
            "quantity": decimal_string(self.quantity),
            "unit_price": decimal_string(self.unit_price),
            "gross_amount": decimal_string(self.gross_amount),
            "fee_amount": decimal_string(self.fee_amount),
            "fee_unit": self.fee_unit.value if self.fee_unit else None,
            "currency": self.currency,
            "fx_rate_to_thb": decimal_string(self.fx_rate_to_thb),
            "source_type": "GOOGLE_SHEETS",
            "source_identifier": self.source_identifier,
            "source_row_number": self.source_row_number,
            "source_fingerprint": self.source_fingerprint,
            "raw_source_data": self.raw_source_data,
            "source_metadata": self.source_metadata,
            "notes": self.notes,
        }


@dataclass
class ImportPlan:
    spreadsheet_id: str
    source_filename: str
    source_fingerprint: str
    sheet_titles: tuple[str, ...]
    rows_read: int
    transactions: list[NormalizedTransaction]
    issues: list[ImportIssue]
    positions: dict[tuple[str, str], Decimal]
    expected_holdings: dict[tuple[str, str], Decimal]
    checks: dict[str, dict[str, Any]]
    import_batch_id: str | None = None

    def report(self) -> dict[str, Any]:
        transaction_types = Counter(row.transaction_type for row in self.transactions)
        asset_types = Counter(row.asset_type for row in self.transactions)
        accounts = Counter(row.account_name for row in self.transactions)
        currencies = Counter(row.currency for row in self.transactions)
        error_codes = Counter(issue.error_code for issue in self.issues)
        asset_fee_rows = [
            row
            for row in self.transactions
            if row.fee_unit == FeeUnit.ASSET_UNITS
            and (row.fee_amount or Decimal(0)) > 0
        ]
        return {
            "status": "READY" if not self.issues else "READY_WITH_ERRORS",
            "spreadsheet_id": self.spreadsheet_id,
            "source_filename": self.source_filename,
            "source_fingerprint": self.source_fingerprint,
            "sheet_count": len(self.sheet_titles),
            "sheet_titles": list(self.sheet_titles),
            "rows_read": self.rows_read,
            "rows_ready_for_human_review": len(self.transactions),
            "rows_with_errors": len(self.issues),
            "import_batch_id": self.import_batch_id,
            "counts": {
                "transaction_types": dict(sorted(transaction_types.items())),
                "asset_types": dict(sorted(asset_types.items())),
                "accounts": dict(sorted(accounts.items())),
                "currencies": dict(sorted(currencies.items())),
                "error_codes": dict(sorted(error_codes.items())),
                "asset_unit_fee_rows": len(asset_fee_rows),
            },
            "positions": {
                f"{account}::{symbol}": format(quantity, "f")
                for (account, symbol), quantity in sorted(self.positions.items())
            },
            "checks": self.checks,
            "errors": [
                {
                    "error_code": issue.error_code,
                    "error_message": issue.error_message,
                    "source_row_number": issue.source_row_number,
                    "source_identifier": issue.source_identifier,
                    "error_details": issue.error_details,
                }
                for issue in self.issues
            ],
        }
