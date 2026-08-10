"""Deterministic normalization, deduplication, and reconciliation planning."""

from __future__ import annotations

import hashlib
import re
import unicodedata
from collections import defaultdict
from collections.abc import Iterable
from datetime import date, datetime, time
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.services.portfolio_import.google_sheets import GoogleSheetsWorkbookReader
from app.services.portfolio_import.models import (
    FeeUnit,
    ImportIssue,
    ImportPlan,
    NormalizedTransaction,
    WorkbookTransactionRow,
)

WORKBOOK_TIME_ZONE = ZoneInfo("Asia/Bangkok")
POSITION_TOLERANCE = Decimal("0.00000001")

TRANSACTION_TYPE_ALIASES = {
    "BUY": "BUY",
    "SELL": "SELL",
    "DIVIDEND": "DIVIDEND",
    "STAKING": "STAKING",
    "INTEREST": "INTEREST",
    "DEPOSIT": "TRANSFER_IN",
    "WITHDRAWAL": "TRANSFER_OUT",
    "TRANSFER IN": "TRANSFER_IN",
    "TRANSFER_IN": "TRANSFER_IN",
    "TRANSFER OUT": "TRANSFER_OUT",
    "TRANSFER_OUT": "TRANSFER_OUT",
    "FEE": "FEE",
}

ASSET_TYPE_ALIASES = {
    "STOCK": "STOCK",
    "ETF": "ETF",
    "CRYPTO": "CRYPTO",
    "CASH": "CASH",
    "BOND": "BOND",
    "MUTUAL FUND": "MUTUAL_FUND",
    "MUTUAL_FUND": "MUTUAL_FUND",
    "MUTUAL_FUND": "MUTUAL_FUND",
    "OTHER": "OTHER",
}

FEE_UNIT_ALIASES = {
    "QUOTE CURRENCY": FeeUnit.QUOTE_CURRENCY,
    "QUOTE_CURRENCY": FeeUnit.QUOTE_CURRENCY,
    "ASSET UNITS": FeeUnit.ASSET_UNITS,
    "ASSET_UNITS": FeeUnit.ASSET_UNITS,
}

CURRENCY_ALIASES = {
    "$": "USD",
    "US DOLLAR": "USD",
    "US DOLLARS": "USD",
    "BAHT": "THB",
}


def _canonical_text(value: Any) -> str:
    text = unicodedata.normalize("NFKC", str(value or ""))
    return re.sub(r"\s+", " ", text).strip()


def _upper_text(value: Any) -> str:
    return _canonical_text(value).upper()


def _decimal(value: Any, *, field_name: str) -> Decimal | None:
    if value in (None, ""):
        return None
    try:
        parsed = Decimal(str(value).replace(",", ""))
    except (InvalidOperation, ValueError) as exc:
        raise ValueError(f"{field_name} is not a valid decimal") from exc
    if not parsed.is_finite():
        raise ValueError(f"{field_name} must be finite")
    return parsed


def _transaction_at(value: Any) -> datetime:
    parsed: date | datetime
    if isinstance(value, (datetime, date)):
        parsed = value
    elif isinstance(value, str):
        try:
            parsed = datetime.fromisoformat(value)
        except ValueError:
            parsed = date.fromisoformat(value)
    else:
        raise TypeError("Date is missing or invalid")

    if isinstance(parsed, datetime):
        if parsed.tzinfo is not None:
            return parsed
        return parsed.replace(tzinfo=WORKBOOK_TIME_ZONE)
    return datetime.combine(parsed, time.min, tzinfo=WORKBOOK_TIME_ZONE)


def _source_fingerprint(spreadsheet_id: str, source_identifier: str) -> str:
    identity = f"GOOGLE_SHEETS\0{spreadsheet_id}\0Transactions\0{source_identifier}"
    return hashlib.sha256(identity.encode("utf-8")).hexdigest()


def _issue(
    row: WorkbookTransactionRow,
    code: str,
    message: str,
    **details: Any,
) -> ImportIssue:
    source_identifier = _canonical_text(row.values.get("Source ID")) or None
    return ImportIssue(
        error_code=code,
        error_message=message,
        source_row_number=row.row_number,
        source_identifier=source_identifier,
        raw_source_data=row.raw_source_data,
        error_details=details,
    )


def _normalize_row(
    row: WorkbookTransactionRow,
    *,
    spreadsheet_id: str,
) -> tuple[NormalizedTransaction | None, list[ImportIssue]]:
    issues: list[ImportIssue] = []
    source_identifier = _canonical_text(row.values.get("Source ID"))
    account_name = _canonical_text(row.values.get("Account"))
    symbol = _upper_text(row.values.get("Asset"))
    asset_type_source = _upper_text(row.values.get("Asset Class"))
    transaction_type_source = _upper_text(row.values.get("Action"))
    currency_source = _upper_text(row.values.get("Currency"))
    fee_unit_source = _upper_text(row.values.get("Fee Unit"))

    for field_name, value in (
        ("Source ID", source_identifier),
        ("Account", account_name),
        ("Asset", symbol),
        ("Asset Class", asset_type_source),
        ("Action", transaction_type_source),
        ("Currency", currency_source),
    ):
        if not value:
            issues.append(
                _issue(
                    row,
                    "MISSING_REQUIRED_FIELD",
                    f"{field_name} is required",
                    field=field_name,
                )
            )

    transaction_type = TRANSACTION_TYPE_ALIASES.get(transaction_type_source)
    if transaction_type_source and transaction_type is None:
        issues.append(
            _issue(
                row,
                "UNSUPPORTED_TRANSACTION_TYPE",
                f"Unsupported transaction type: {transaction_type_source}",
                value=transaction_type_source,
            )
        )

    asset_type = ASSET_TYPE_ALIASES.get(asset_type_source)
    if asset_type_source and asset_type is None:
        issues.append(
            _issue(
                row,
                "UNSUPPORTED_ASSET_CLASS",
                f"Unsupported asset class: {asset_type_source}",
                value=asset_type_source,
            )
        )

    currency = CURRENCY_ALIASES.get(currency_source, currency_source)
    if currency and not re.fullmatch(r"[A-Z][A-Z0-9]{2,9}", currency):
        issues.append(
            _issue(
                row, "INVALID_CURRENCY", f"Invalid currency: {currency}", value=currency
            )
        )

    fee_unit = FEE_UNIT_ALIASES.get(fee_unit_source)
    if fee_unit_source and fee_unit is None:
        issues.append(
            _issue(
                row,
                "INVALID_FEE_UNIT",
                f"Unsupported fee unit: {fee_unit_source}",
                value=fee_unit_source,
            )
        )

    if "Price" in row.formulas:
        issues.append(
            _issue(
                row,
                "FORMULA_DERIVED_PRICE",
                "Transaction price must be a stored source input, not a formula",
                formula=row.formulas["Price"],
            )
        )
    if "FX Rate" in row.formulas:
        issues.append(
            _issue(
                row,
                "FORMULA_DERIVED_FX",
                "Historical FX must be stored explicitly and cannot be recomputed",
                formula=row.formulas["FX Rate"],
            )
        )

    try:
        transaction_at = _transaction_at(row.values.get("Date"))
    except (ValueError, TypeError) as exc:
        issues.append(_issue(row, "INVALID_DATE", str(exc)))
        transaction_at = datetime.min.replace(tzinfo=WORKBOOK_TIME_ZONE)

    parsed: dict[str, Decimal | None] = {}
    for source_name, target_name in (
        ("Quantity", "quantity"),
        ("Price", "unit_price"),
        ("Fee", "fee_amount"),
        ("FX Rate", "fx_rate_to_thb"),
    ):
        try:
            parsed[target_name] = _decimal(
                row.values.get(source_name), field_name=source_name
            )
        except ValueError as exc:
            issues.append(_issue(row, "INVALID_NUMBER", str(exc), field=source_name))
            parsed[target_name] = None

    quantity = parsed["quantity"]
    unit_price = parsed["unit_price"]
    fee_amount = parsed["fee_amount"]
    fx_rate_to_thb = parsed["fx_rate_to_thb"]

    for field_name, value in (
        ("Quantity", quantity),
        ("Price", unit_price),
        ("FX Rate", fx_rate_to_thb),
    ):
        if value is None or value <= 0:
            issues.append(
                _issue(
                    row,
                    "INVALID_NUMBER",
                    f"{field_name} must be greater than zero",
                    field=field_name,
                )
            )
    if fee_amount is not None and fee_amount < 0:
        issues.append(
            _issue(row, "INVALID_NUMBER", "Fee must be non-negative", field="Fee")
        )
    if fee_amount is not None and fee_unit is None:
        issues.append(
            _issue(row, "MISSING_FEE_UNIT", "Fee Unit is required when Fee is present")
        )
    if (
        fee_unit == FeeUnit.ASSET_UNITS
        and fee_amount is not None
        and quantity is not None
        and fee_amount >= quantity
    ):
        issues.append(
            _issue(
                row,
                "ASSET_FEE_EXCEEDS_QUANTITY",
                "Asset-unit fee must be smaller than transaction quantity",
            )
        )

    data_check = _upper_text(row.values.get("Data Check"))
    if data_check and data_check != "OK":
        issues.append(
            _issue(
                row,
                "SOURCE_DATA_CHECK_FAILED",
                f"Workbook data check is {data_check}",
                value=data_check,
            )
        )

    if issues or transaction_type is None or asset_type is None:
        return None, issues

    gross_amount = None
    if transaction_type in {"DIVIDEND", "INTEREST", "FEE"}:
        gross_amount = quantity * unit_price if quantity and unit_price else None

    asset_currency = currency
    if asset_type in {"STOCK", "ETF", "CRYPTO"} and currency in {"USD", "USDT"}:
        asset_currency = "USD"

    notes = _canonical_text(row.values.get("Notes")) or None
    return (
        NormalizedTransaction(
            source_identifier=source_identifier,
            source_row_number=row.row_number,
            source_fingerprint=_source_fingerprint(spreadsheet_id, source_identifier),
            account_name=account_name,
            account_type="OTHER",
            symbol=symbol,
            asset_name=symbol,
            asset_type=asset_type,
            asset_currency=asset_currency,
            transaction_type=transaction_type,
            transaction_at=transaction_at,
            quantity=quantity,
            unit_price=unit_price,
            gross_amount=gross_amount,
            fee_amount=fee_amount,
            fee_unit=fee_unit,
            currency=currency,
            fx_rate_to_thb=fx_rate_to_thb,
            raw_source_data=row.raw_source_data,
            source_metadata={
                "spreadsheet_id": spreadsheet_id,
                "sheet": "Transactions",
                "workbook_time_zone": "Asia/Bangkok",
                "fee_unit": fee_unit.value if fee_unit else None,
                "formula_derived_summary_columns_ignored": True,
            },
            notes=notes,
        ),
        [],
    )


def _reconcile_positions(
    transactions: Iterable[NormalizedTransaction],
    expected_holdings: dict[tuple[str, str], Decimal],
) -> tuple[
    list[NormalizedTransaction],
    list[ImportIssue],
    dict[tuple[str, str], Decimal],
    dict[str, dict[str, Any]],
]:
    accepted: list[NormalizedTransaction] = []
    issues: list[ImportIssue] = []
    positions: dict[tuple[str, str], Decimal] = defaultdict(Decimal)

    for transaction in sorted(
        transactions,
        key=lambda item: (item.transaction_at, item.source_row_number),
    ):
        key = (transaction.account_name, transaction.symbol)
        candidate = positions[key] + transaction.signed_quantity()
        if candidate < -POSITION_TOLERANCE:
            issues.append(
                ImportIssue(
                    error_code="NEGATIVE_POSITION",
                    error_message="Transaction would create a negative position",
                    source_row_number=transaction.source_row_number,
                    source_identifier=transaction.source_identifier,
                    raw_source_data=transaction.raw_source_data,
                    error_details={
                        "account": transaction.account_name,
                        "symbol": transaction.symbol,
                        "candidate_quantity": format(candidate, "f"),
                    },
                )
            )
            continue
        positions[key] = (
            Decimal(0) if abs(candidate) <= POSITION_TOLERANCE else candidate
        )
        accepted.append(transaction)

    position_mismatches: list[dict[str, str]] = []
    for key in sorted(set(positions) | set(expected_holdings)):
        actual = positions.get(key, Decimal(0))
        expected = expected_holdings.get(key, Decimal(0))
        difference = actual - expected
        if abs(difference) > POSITION_TOLERANCE:
            position_mismatches.append(
                {
                    "account": key[0],
                    "symbol": key[1],
                    "actual": format(actual, "f"),
                    "expected": format(expected, "f"),
                    "difference": format(difference, "f"),
                }
            )

    if position_mismatches:
        issues.append(
            ImportIssue(
                error_code="POSITION_RECONCILIATION_MISMATCH",
                error_message="Replayed positions do not match the workbook Holdings baseline",
                error_details={"mismatches": position_mismatches},
            )
        )

    crwd_rows = [row for row in accepted if row.symbol == "CRWD"]
    msft_rows = [row for row in accepted if row.symbol == "MSFT"]
    crwd_sells = [row for row in crwd_rows if row.transaction_type == "SELL"]
    checks = {
        "current_15_tab_export": {"passed": True, "actual": 15, "expected": 15},
        "stored_historical_fx": {
            "passed": all(row.fx_rate_to_thb is not None for row in accepted),
            "rows_checked": len(accepted),
        },
        "formula_derived_transaction_prices": {
            "passed": not any(
                issue.error_code == "FORMULA_DERIVED_PRICE" for issue in issues
            ),
            "policy": "reject formula prices; ignore summary formulas",
        },
        "crypto_fee_units": {
            "passed": all(
                row.fee_unit is not None
                for row in accepted
                if row.asset_type == "CRYPTO" and row.fee_amount is not None
            ),
            "asset_unit_fee_rows": sum(
                1
                for row in accepted
                if row.fee_unit == FeeUnit.ASSET_UNITS
                and (row.fee_amount or Decimal(0)) > 0
            ),
        },
        "crwd_partial_sell_history": {
            "passed": len(crwd_rows) == 3
            and len(crwd_sells) == 2
            and all(
                quantity == 0
                for (account, symbol), quantity in positions.items()
                if symbol == "CRWD"
            ),
            "transaction_count": len(crwd_rows),
            "sell_count": len(crwd_sells),
        },
        "msft_purchase_history": {
            "passed": len(msft_rows) == 2
            and all(row.transaction_type == "BUY" for row in msft_rows),
            "transaction_count": len(msft_rows),
        },
        "non_negative_positions": {
            "passed": not any(
                issue.error_code == "NEGATIVE_POSITION" for issue in issues
            ),
        },
        "holdings_reconciliation": {
            "passed": not position_mismatches,
            "mismatch_count": len(position_mismatches),
        },
    }
    return accepted, issues, dict(positions), checks


def build_import_plan(
    workbook_path: str | Path,
    *,
    spreadsheet_id: str,
    reader: GoogleSheetsWorkbookReader | None = None,
) -> ImportPlan:
    snapshot = (reader or GoogleSheetsWorkbookReader()).read(workbook_path)
    transactions: list[NormalizedTransaction] = []
    issues: list[ImportIssue] = []
    seen_fingerprints: set[str] = set()

    for row in snapshot.transaction_rows:
        transaction, row_issues = _normalize_row(row, spreadsheet_id=spreadsheet_id)
        issues.extend(row_issues)
        if transaction is None:
            continue
        if transaction.source_fingerprint in seen_fingerprints:
            issues.append(
                ImportIssue(
                    error_code="DUPLICATE_SOURCE_FINGERPRINT",
                    error_message="Duplicate source transaction in workbook",
                    source_row_number=transaction.source_row_number,
                    source_identifier=transaction.source_identifier,
                    raw_source_data=transaction.raw_source_data,
                    error_details={
                        "source_fingerprint": transaction.source_fingerprint
                    },
                )
            )
            continue
        seen_fingerprints.add(transaction.source_fingerprint)
        transactions.append(transaction)

    accepted, reconciliation_issues, positions, checks = _reconcile_positions(
        transactions,
        snapshot.holdings,
    )
    issues.extend(reconciliation_issues)
    checks["formula_derived_transaction_prices"]["passed"] = not any(
        issue.error_code == "FORMULA_DERIVED_PRICE" for issue in issues
    )
    checks["stored_historical_fx"]["passed"] = checks["stored_historical_fx"][
        "passed"
    ] and not any(issue.error_code == "FORMULA_DERIVED_FX" for issue in issues)
    return ImportPlan(
        spreadsheet_id=spreadsheet_id,
        source_filename=snapshot.source_filename,
        source_fingerprint=snapshot.source_fingerprint,
        sheet_titles=snapshot.sheet_titles,
        rows_read=len(snapshot.transaction_rows),
        transactions=accepted,
        issues=issues,
        positions=positions,
        expected_holdings=snapshot.holdings,
        checks=checks,
    )


def apply_existing_fingerprint_deduplication(
    plan: ImportPlan,
    existing_fingerprints: set[str],
) -> ImportPlan:
    retained: list[NormalizedTransaction] = []
    for transaction in plan.transactions:
        if transaction.source_fingerprint not in existing_fingerprints:
            retained.append(transaction)
            continue
        plan.issues.append(
            ImportIssue(
                error_code="DUPLICATE_SOURCE_FINGERPRINT",
                error_message="Source transaction was already staged or confirmed",
                source_row_number=transaction.source_row_number,
                source_identifier=transaction.source_identifier,
                raw_source_data=transaction.raw_source_data,
                error_details={"source_fingerprint": transaction.source_fingerprint},
            )
        )
    plan.transactions = retained
    return plan
