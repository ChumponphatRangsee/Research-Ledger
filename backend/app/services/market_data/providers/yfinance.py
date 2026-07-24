"""yfinance adapter for normalized company financial snapshots."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any, NoReturn

import yfinance as yf

from app.services.market_data.exceptions import (
    InvalidProviderResponseError,
    MarketDataProviderError,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    SymbolNotFoundError,
)
from app.services.market_data.models import CompanyFinancialSnapshot
from app.services.market_data.normalization import normalize_company_snapshot

logger = logging.getLogger(__name__)

PROVIDER_NAME = "yfinance"


def _matches_yfinance_exception(exc: Exception, class_name: str) -> bool:
    exception_class = getattr(getattr(yf, "exceptions", None), class_name, None)
    return isinstance(exception_class, type) and isinstance(exc, exception_class)


def _raise_retrieval_error(symbol: str, exc: Exception) -> NoReturn:
    if isinstance(exc, TimeoutError):
        error: MarketDataProviderError = ProviderTimeoutError(
            "yfinance request timed out",
            provider=PROVIDER_NAME,
            symbol=symbol,
        )
    elif _matches_yfinance_exception(exc, "YFRateLimitError"):
        error = ProviderRateLimitError(
            "yfinance rate limit reached",
            provider=PROVIDER_NAME,
            symbol=symbol,
        )
    elif _matches_yfinance_exception(exc, "YFTickerMissingError"):
        error = SymbolNotFoundError(
            "Symbol was not found by yfinance",
            provider=PROVIDER_NAME,
            symbol=symbol,
        )
    else:
        error = ProviderUnavailableError(
            "Unable to retrieve market data",
            provider=PROVIDER_NAME,
            symbol=symbol,
        )
    raise error from exc


def _first_present(mapping: dict[str, Any], *keys: str) -> Any:
    for key in keys:
        if mapping.get(key) is not None:
            return mapping[key]
    return None


def _statement(ticker: Any, attribute: str) -> Any:
    try:
        return getattr(ticker, attribute)
    except Exception as exc:
        logger.debug("Optional yfinance statement %s unavailable: %s", attribute, exc)
        return None


def _statement_value(frame: Any, *row_names: str, column: int = 0) -> Any:
    if frame is None or getattr(frame, "empty", True):
        return None
    for row_name in row_names:
        if row_name in frame.index and len(frame.loc[row_name]) > column:
            value = frame.loc[row_name].iloc[column]
            return value if value == value else None
    return None


def _safe_divide(numerator: Any, denominator: Any) -> float | None:
    try:
        if numerator is None or denominator is None or float(denominator) == 0:
            return None
        return float(numerator) / float(denominator)
    except (TypeError, ValueError, OverflowError):
        return None


def _fetch_raw_snapshot(symbol: str) -> dict[str, Any]:
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
    except Exception as exc:
        _raise_retrieval_error(symbol, exc)

    if not isinstance(info, dict):
        raise InvalidProviderResponseError(
            "yfinance returned invalid quote metadata",
            provider=PROVIDER_NAME,
            symbol=symbol,
        )

    try:
        history = ticker.history(period="5d")
        current_price = (
            float(history["Close"].iloc[-1])
            if not history.empty and "Close" in history
            else _first_present(info, "currentPrice", "regularMarketPrice")
        )
    except Exception as exc:
        logger.warning(
            "%s price history unavailable; using quote metadata: %s",
            symbol,
            exc,
        )
        current_price = _first_present(info, "currentPrice", "regularMarketPrice")

    financials = _statement(ticker, "financials")
    cashflow = _statement(ticker, "cashflow")
    balance_sheet = _statement(ticker, "balance_sheet")

    revenue = _first_present(info, "totalRevenue")
    free_cash_flow = _first_present(info, "freeCashflow")
    operating_cash_flow = _first_present(info, "operatingCashflow")
    market_cap = info.get("marketCap")
    total_debt = info.get("totalDebt")
    total_cash = info.get("totalCash")
    ebitda = info.get("ebitda")
    ebit = _statement_value(financials, "EBIT", "Operating Income")
    interest_expense = _statement_value(
        financials, "Interest Expense", "Interest Expense Non Operating"
    )
    capex = _statement_value(cashflow, "Capital Expenditure", "Capital Expenditures")
    inventory_latest = _statement_value(balance_sheet, "Inventory", column=0)
    inventory_previous = _statement_value(balance_sheet, "Inventory", column=1)
    current_liabilities = _statement_value(balance_sheet, "Current Liabilities")
    total_assets = _statement_value(balance_sheet, "Total Assets")
    tax_rate = info.get("effectiveTaxRate")

    net_debt = None
    if total_debt is not None and total_cash is not None:
        net_debt = float(total_debt) - float(total_cash)

    invested_capital = None
    if total_assets is not None and current_liabilities is not None:
        invested_capital = float(total_assets) - float(current_liabilities)
    nopat = None
    if ebit is not None:
        normalized_tax_rate = float(tax_rate) if tax_rate is not None else 0.21
        nopat = float(ebit) * (1 - max(0.0, min(normalized_tax_rate, 0.50)))

    provider_roic = _first_present(info, "returnOnCapital")
    return {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": market_cap,
        "current_price": current_price,
        "pe_ratio": info.get("trailingPE"),
        "forward_pe": info.get("forwardPE"),
        "price_to_book": info.get("priceToBook"),
        "roe": info.get("returnOnEquity"),
        "roa": info.get("returnOnAssets"),
        "roic": (
            provider_roic
            if provider_roic is not None
            else _safe_divide(nopat, invested_capital)
        ),
        "revenue_growth": info.get("revenueGrowth"),
        "earnings_growth": info.get("earningsGrowth"),
        "gross_margin": info.get("grossMargins"),
        "operating_margin": info.get("operatingMargins"),
        "fcf_margin": _safe_divide(free_cash_flow, revenue),
        "fcf_conversion": _safe_divide(free_cash_flow, operating_cash_flow),
        "revenue": revenue,
        "free_cash_flow": free_cash_flow,
        "operating_cash_flow": operating_cash_flow,
        "fcf_yield": _safe_divide(free_cash_flow, market_cap),
        "debt_to_equity": info.get("debtToEquity"),
        "net_debt_to_ebitda": _safe_divide(net_debt, ebitda),
        "interest_coverage": (
            _safe_divide(ebit, abs(float(interest_expense)))
            if interest_expense is not None
            else None
        ),
        "dividend_yield": info.get("dividendYield"),
        "capex_intensity": (
            _safe_divide(abs(float(capex)), revenue) if capex is not None else None
        ),
        "inventory_growth": (
            _safe_divide(
                float(inventory_latest) - float(inventory_previous),
                inventory_previous,
            )
            if inventory_latest is not None and inventory_previous is not None
            else None
        ),
        "data_as_of": datetime.now(timezone.utc),
    }


class YFinanceProvider:
    """Market data provider backed by yfinance."""

    def get_company_snapshot(self, symbol: str) -> CompanyFinancialSnapshot:
        """Return a normalized company and financial snapshot."""
        raw = self.get_legacy_financial_metrics(symbol)
        try:
            return normalize_company_snapshot(raw)
        except MarketDataProviderError:
            raise
        except Exception as exc:
            raise InvalidProviderResponseError(
                "Unable to normalize yfinance market data",
                provider=PROVIDER_NAME,
                symbol=symbol,
            ) from exc

    def get_legacy_financial_metrics(self, symbol: str) -> dict[str, Any]:
        """Return the former raw mapping for compatibility until Issue 3."""
        try:
            return _fetch_raw_snapshot(symbol)
        except MarketDataProviderError:
            raise
        except (AttributeError, KeyError, TypeError, ValueError, OverflowError) as exc:
            raise InvalidProviderResponseError(
                "yfinance returned invalid financial data",
                provider=PROVIDER_NAME,
                symbol=symbol,
            ) from exc
        except Exception as exc:
            raise ProviderUnavailableError(
                "Unable to retrieve market data",
                provider=PROVIDER_NAME,
                symbol=symbol,
            ) from exc
