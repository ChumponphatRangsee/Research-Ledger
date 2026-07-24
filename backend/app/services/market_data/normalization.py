"""Provider-neutral normalization for company financial snapshots."""

from __future__ import annotations

import math
from datetime import datetime, timezone
from numbers import Real
from typing import Any

from app.services.market_data.models import CompanyFinancialSnapshot


def finite_float(value: Any) -> float | None:
    """Return a finite float, preserving unavailable/invalid data as ``None``."""
    if value is None or isinstance(value, bool):
        return None
    if not isinstance(value, Real):
        try:
            value = float(value)
        except (TypeError, ValueError):
            return None
    result = float(value)
    return result if math.isfinite(result) else None


def ratio_from_percent(value: Any) -> float | None:
    """Normalize ratios that providers sometimes express as percentages."""
    result = finite_float(value)
    if result is None:
        return None
    return result / 100.0 if abs(result) > 10 else result


def normalize_company_snapshot(raw: dict[str, Any]) -> CompanyFinancialSnapshot:
    """Validate provider output and remove NaN/infinite values."""
    text_fields = {"symbol", "name", "sector", "industry"}
    ratio_percent_fields = {"debt_to_equity"}
    datetime_fields = {"data_as_of"}
    normalized: dict[str, Any] = {}

    for field_name in CompanyFinancialSnapshot.model_fields:
        value = raw.get(field_name)
        if field_name in text_fields or field_name in datetime_fields:
            normalized[field_name] = value
        elif field_name in ratio_percent_fields:
            normalized[field_name] = ratio_from_percent(value)
        else:
            normalized[field_name] = finite_float(value)

    normalized["symbol"] = str(raw.get("symbol") or "").strip().upper()
    normalized["data_as_of"] = raw.get("data_as_of") or datetime.now(timezone.utc)
    return CompanyFinancialSnapshot.model_validate(normalized)
