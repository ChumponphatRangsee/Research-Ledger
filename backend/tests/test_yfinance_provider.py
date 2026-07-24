import math

import pandas as pd
import pytest

from app.services.market_data import (
    CompanyFinancialSnapshot,
    InvalidProviderResponseError,
    MarketDataProvider,
    ProviderRateLimitError,
    ProviderTimeoutError,
    ProviderUnavailableError,
    SymbolNotFoundError,
)
from app.services.market_data.providers import YFinanceProvider
from app.services.market_data.providers import yfinance as yfinance_module
from app.services.screening.normalization import normalize_financial_metrics
from app.services.yfinance_client import fetch_financial_metrics


class FakeTicker:
    def __init__(
        self,
        info: dict,
        *,
        history: pd.DataFrame | None = None,
        history_error: Exception | None = None,
        financials: pd.DataFrame | None = None,
        cashflow: pd.DataFrame | None = None,
        balance_sheet: pd.DataFrame | None = None,
    ) -> None:
        self.info = info
        self._history = pd.DataFrame() if history is None else history
        self._history_error = history_error
        self.financials = pd.DataFrame() if financials is None else financials
        self.cashflow = pd.DataFrame() if cashflow is None else cashflow
        self.balance_sheet = (
            pd.DataFrame() if balance_sheet is None else balance_sheet
        )

    def history(self, *, period: str) -> pd.DataFrame:
        assert period == "5d"
        if self._history_error is not None:
            raise self._history_error
        return self._history


def test_yfinance_provider_returns_normalized_snapshot(monkeypatch):
    ticker = FakeTicker(
        {
            "longName": "Example Corp",
            "sector": "Technology",
            "industry": "Software",
            "marketCap": 2_000,
            "totalRevenue": 1_000,
            "freeCashflow": 100,
            "operatingCashflow": 200,
            "totalDebt": 300,
            "totalCash": 100,
            "ebitda": 100,
            "effectiveTaxRate": 0.20,
            "debtToEquity": 150,
            "trailingPE": math.nan,
        },
        history=pd.DataFrame({"Close": [99.0, 101.0]}),
        financials=pd.DataFrame(
            {0: [100.0, -5.0]},
            index=["EBIT", "Interest Expense"],
        ),
        cashflow=pd.DataFrame(
            {0: [-50.0]},
            index=["Capital Expenditure"],
        ),
        balance_sheet=pd.DataFrame(
            {
                0: [120.0, 200.0, 1_000.0],
                1: [100.0, 190.0, 900.0],
            },
            index=["Inventory", "Current Liabilities", "Total Assets"],
        ),
    )
    monkeypatch.setattr(yfinance_module.yf, "Ticker", lambda _symbol: ticker)

    provider = YFinanceProvider()
    snapshot = provider.get_company_snapshot("example")

    assert isinstance(provider, MarketDataProvider)
    assert isinstance(snapshot, CompanyFinancialSnapshot)
    assert snapshot.symbol == "EXAMPLE"
    assert snapshot.current_price == 101.0
    assert snapshot.debt_to_equity == 1.5
    assert snapshot.pe_ratio is None
    assert snapshot.roic == pytest.approx(0.10)
    assert snapshot.fcf_margin == pytest.approx(0.10)
    assert snapshot.fcf_conversion == pytest.approx(0.50)
    assert snapshot.fcf_yield == pytest.approx(0.05)
    assert snapshot.net_debt_to_ebitda == pytest.approx(2.0)
    assert snapshot.interest_coverage == pytest.approx(20.0)
    assert snapshot.capex_intensity == pytest.approx(0.05)
    assert snapshot.inventory_growth == pytest.approx(0.20)
    assert snapshot.data_as_of is not None
    assert snapshot.data_as_of.tzinfo is not None


def test_history_failure_falls_back_to_quote_metadata(monkeypatch):
    ticker = FakeTicker(
        {"regularMarketPrice": 42.5},
        history_error=RuntimeError("history unavailable"),
    )
    monkeypatch.setattr(yfinance_module.yf, "Ticker", lambda _symbol: ticker)

    snapshot = YFinanceProvider().get_company_snapshot("FALLBACK")

    assert snapshot.current_price == 42.5
    assert snapshot.market_cap is None


def test_provider_converts_timeout_to_structured_error(monkeypatch):
    def raise_timeout(_symbol):
        raise TimeoutError("provider timed out")

    monkeypatch.setattr(yfinance_module.yf, "Ticker", raise_timeout)

    with pytest.raises(ProviderTimeoutError) as caught:
        YFinanceProvider().get_company_snapshot("FAIL")

    assert isinstance(caught.value, ProviderUnavailableError)
    assert caught.value.provider == "yfinance"
    assert caught.value.symbol == "FAIL"
    assert isinstance(caught.value.__cause__, TimeoutError)


@pytest.mark.parametrize(
    ("provider_error", "expected_error"),
    [
        (yfinance_module.yf.exceptions.YFRateLimitError(), ProviderRateLimitError),
        (
            yfinance_module.yf.exceptions.YFTickerMissingError("MISS", "missing"),
            SymbolNotFoundError,
        ),
    ],
)
def test_provider_converts_known_yfinance_errors(
    monkeypatch,
    provider_error,
    expected_error,
):
    def raise_provider_error(_symbol):
        raise provider_error

    monkeypatch.setattr(yfinance_module.yf, "Ticker", raise_provider_error)

    with pytest.raises(expected_error) as caught:
        YFinanceProvider().get_company_snapshot("MISS")

    assert caught.value.provider == "yfinance"
    assert caught.value.symbol == "MISS"


def test_provider_converts_malformed_financial_data_to_invalid_response(monkeypatch):
    ticker = FakeTicker(
        {"totalDebt": "not-a-number", "totalCash": 10},
    )
    monkeypatch.setattr(yfinance_module.yf, "Ticker", lambda _symbol: ticker)

    with pytest.raises(InvalidProviderResponseError) as caught:
        YFinanceProvider().get_company_snapshot("BAD")

    assert caught.value.provider == "yfinance"
    assert caught.value.symbol == "BAD"


def test_legacy_client_delegates_without_double_normalizing_ratios(monkeypatch):
    ticker = FakeTicker({"debtToEquity": 1_500})
    monkeypatch.setattr(yfinance_module.yf, "Ticker", lambda _symbol: ticker)

    raw = fetch_financial_metrics("LEVERED")
    normalized = normalize_financial_metrics(raw)

    assert raw["debt_to_equity"] == 1_500
    assert normalized.debt_to_equity == 15.0
