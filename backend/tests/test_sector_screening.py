import math
from types import SimpleNamespace

import pytest

from app.services import screener
from app.services.screening.classifier import classify_business_model
from app.services.screening.engine import ScreeningEngine
from app.services.screening.models import BusinessModel, FinancialMetrics
from app.services.screening.normalization import normalize_financial_metrics


def metrics(symbol: str, sector: str, industry: str, **overrides) -> FinancialMetrics:
    values = {
        "symbol": symbol,
        "name": f"{symbol} Corp",
        "sector": sector,
        "industry": industry,
        "current_price": 100,
        "market_cap": 100_000_000_000,
    }
    values.update(overrides)
    return FinancialMetrics(**values)


@pytest.mark.parametrize(
    ("company", "expected"),
    [
        (metrics("MSFT", "Technology", "Software - Infrastructure"), BusinessModel.SOFTWARE),
        (metrics("NVDA", "Technology", "Semiconductors"), BusinessModel.SEMICONDUCTOR),
        (metrics("JPM", "Financial Services", "Banks - Diversified"), BusinessModel.BANK),
        (metrics("XOM", "Energy", "Oil & Gas Integrated"), BusinessModel.ENERGY),
    ],
)
def test_business_model_classification(company, expected):
    assert classify_business_model(company) == expected


def test_strong_software_company_scores_with_high_confidence():
    company = metrics(
        "MSFT",
        "Technology",
        "Software - Infrastructure",
        roic=0.28,
        fcf_margin=0.31,
        gross_margin=0.72,
        operating_margin=0.42,
        revenue_growth=0.18,
        earnings_growth=0.24,
        net_debt_to_ebitda=-0.5,
        interest_coverage=25,
        forward_pe=28,
        pe_ratio=32,
        fcf_yield=0.04,
    )

    result = ScreeningEngine(1_000_000_000).screen(company)

    assert result.passed
    assert result.score is not None and result.score >= 75
    assert result.confidence == 100
    assert result.category_scores["quality"] >= 85


def test_expensive_high_quality_software_is_scored_not_hard_rejected():
    company = metrics(
        "CRM",
        "Technology",
        "Software - Application",
        roic=0.22,
        fcf_margin=0.30,
        gross_margin=0.75,
        operating_margin=0.32,
        revenue_growth=0.20,
        earnings_growth=0.25,
        net_debt_to_ebitda=0.1,
        interest_coverage=20,
        forward_pe=55,
        pe_ratio=70,
        fcf_yield=0.025,
    )

    result = ScreeningEngine(1_000_000_000).screen(company)

    assert result.score is not None
    assert result.category_scores["valuation"] < result.category_scores["quality"]
    assert not any("P/E" in reason for reason in result.failure_reasons)


def test_weak_industrial_company_fails_score_threshold():
    company = metrics(
        "WEAK",
        "Industrials",
        "Farm & Heavy Construction Machinery",
        roic=-0.05,
        operating_margin=-0.03,
        fcf_margin=-0.10,
        revenue_growth=-0.12,
        earnings_growth=-0.30,
        debt_to_equity=3.0,
        net_debt_to_ebitda=6.0,
        interest_coverage=0.5,
        forward_pe=48,
        pe_ratio=55,
        fcf_yield=-0.03,
        fcf_conversion=-0.2,
    )

    result = ScreeningEngine(1_000_000_000).screen(company)

    assert not result.passed
    assert result.score is not None and result.score < 55
    assert result.failure_reasons


def test_bank_uses_bank_metrics_and_not_corporate_debt_logic():
    bank = metrics(
        "JPM",
        "Financial Services",
        "Banks - Diversified",
        roe=0.17,
        roa=0.014,
        earnings_growth=0.12,
        revenue_growth=0.08,
        price_to_book=1.6,
        pe_ratio=12,
        forward_pe=11,
        cet1_ratio=0.14,
        efficiency_ratio=0.52,
        charge_off_ratio=0.009,
        debt_to_equity=8.0,
        net_debt_to_ebitda=20.0,
        fcf_margin=-1.0,
    )

    result = ScreeningEngine(1_000_000_000).screen(bank)
    serialized_breakdown = str(result.score_breakdown)

    assert result.passed
    assert "profitability" in result.category_scores
    assert "quality" not in result.category_scores
    assert "debt_to_equity" not in serialized_breakdown
    assert "net_debt_to_ebitda" not in serialized_breakdown
    assert "fcf_margin" not in serialized_breakdown


def test_missing_data_is_explicit_and_never_nan():
    company = metrics(
        "MISS",
        "Technology",
        "Software - Application",
        roic=0.20,
        pe_ratio=25,
    )
    result = ScreeningEngine(1_000_000_000).screen(company)

    assert not result.passed
    assert result.score is None
    assert "Insufficient financial data" in result.failure_reasons
    assert 0 <= result.confidence <= 100

    normalized = normalize_financial_metrics(
        {
            "symbol": "NAN",
            "current_price": math.inf,
            "market_cap": math.nan,
            "roe": "not-a-number",
        }
    )
    assert normalized.current_price is None
    assert normalized.market_cap is None
    assert normalized.roe is None


def test_unsupported_industry_does_not_receive_specialized_score():
    company = metrics(
        "REIT",
        "Real Estate",
        "REIT - Retail",
        roe=0.20,
        pe_ratio=15,
        revenue_growth=0.10,
    )
    result = ScreeningEngine(1_000_000_000).screen(company)

    assert result.business_model == BusinessModel.UNSUPPORTED
    assert not result.passed
    assert result.score is None
    assert "Unsupported business model" in result.failure_reasons


@pytest.mark.parametrize(
    "company",
    [
        metrics(
            "SOFT",
            "Technology",
            "Software - Application",
            roic=0.1,
            gross_margin=0.6,
            revenue_growth=0.1,
            forward_pe=30,
        ),
        metrics(
            "BANK",
            "Financial Services",
            "Banks - Regional",
            roe=0.1,
            roa=0.01,
            price_to_book=1.0,
        ),
        metrics(
            "ENER",
            "Energy",
            "Oil & Gas E&P",
            roe=0.1,
            fcf_margin=0.1,
            debt_to_equity=0.5,
        ),
    ],
)
def test_score_and_confidence_invariants(company):
    result = ScreeningEngine(1_000_000_000).screen(company)
    assert 0 <= result.confidence <= 100
    if result.score is not None:
        assert math.isfinite(result.score)
        assert 0 <= result.score <= 100


class RecordingQuery:
    def __init__(self, client, table):
        self.client = client
        self.table = table
        self.operation = None
        self.payload = None

    def insert(self, payload):
        self.operation = "insert"
        self.payload = payload
        return self

    def upsert(self, payload, on_conflict=None):
        self.operation = "upsert"
        self.payload = payload
        return self

    def update(self, payload):
        self.operation = "update"
        self.payload = payload
        return self

    def eq(self, *_args):
        return self

    def execute(self):
        self.client.operations.append((self.table, self.operation, self.payload))
        if self.table == "screening_runs" and self.operation == "insert":
            return SimpleNamespace(data=[{"id": "run-1"}])
        if self.table == "tickers" and self.operation == "upsert":
            return SimpleNamespace(data=[{"id": "ticker-1"}])
        return SimpleNamespace(data=[self.payload] if self.payload else [])


class RecordingClient:
    def __init__(self):
        self.operations = []

    def table(self, table):
        return RecordingQuery(self, table)


def test_screening_integration_persists_ranks_and_selects_top_candidates(monkeypatch):
    client = RecordingClient()
    settings = SimpleNamespace(
        screener_min_market_cap=1_000_000_000,
        screener_min_score=55.0,
        screener_top_n_candidates=1,
    )
    raw = {
        "symbol": "MSFT",
        "name": "Microsoft",
        "sector": "Technology",
        "industry": "Software - Infrastructure",
        "current_price": 400,
        "market_cap": 3_000_000_000_000,
        "roic": 0.30,
        "fcf_margin": 0.30,
        "gross_margin": 0.70,
        "operating_margin": 0.40,
        "revenue_growth": 0.18,
        "earnings_growth": 0.22,
        "net_debt_to_ebitda": -0.5,
        "interest_coverage": 30,
        "forward_pe": 28,
        "pe_ratio": 32,
        "fcf_yield": 0.04,
    }
    monkeypatch.setattr(screener, "get_supabase_client", lambda: client)
    monkeypatch.setattr(screener, "get_settings", lambda: settings)
    monkeypatch.setattr(screener, "fetch_financial_metrics", lambda _symbol: raw)

    output = screener.run_quantitative_screen("user-1", universe=["MSFT"])

    result_inserts = [
        payload
        for table, operation, payload in client.operations
        if table == "screening_results" and operation == "insert"
    ]
    assert output["run_id"] == "run-1"
    assert output["requested"] == 1
    assert output["processed"] == 1
    assert output["failed"] == 0
    assert output["passed"] == 1
    assert output["selected_for_ai"] == 1
    assert output["candidates"][0]["symbol"] == "MSFT"
    assert len(result_inserts) == 1
    assert result_inserts[0]["business_model"] == "software"
    assert 0 <= result_inserts[0]["total_score"] <= 100
    assert result_inserts[0]["score_breakdown"]
