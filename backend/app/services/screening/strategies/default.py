"""Fallback configuration for ordinary non-specialized operating companies."""

from app.services.screening.models import BusinessModel
from app.services.screening.scoring import MetricRule, StrategyDefinition

STRATEGY = StrategyDefinition(
    business_model=BusinessModel.DEFAULT,
    category_weights={
        "quality": 0.25,
        "growth": 0.20,
        "financial_strength": 0.15,
        "valuation": 0.20,
        "sector_specific": 0.20,
    },
    rules={
        "quality": (
            MetricRule("roic", "ROIC", "higher", 0.0, 0.20),
            MetricRule("roe", "Return on equity", "higher", 0.0, 0.20),
            MetricRule("operating_margin", "Operating margin", "higher", 0.0, 0.22),
            MetricRule("fcf_margin", "Free cash flow margin", "higher", -0.03, 0.15),
        ),
        "growth": (
            MetricRule("revenue_growth", "Revenue growth", "higher", -0.10, 0.18),
            MetricRule("earnings_growth", "Earnings growth", "higher", -0.20, 0.25),
        ),
        "financial_strength": (
            MetricRule("debt_to_equity", "Debt to equity", "lower", 2.0, 0.3),
            MetricRule("net_debt_to_ebitda", "Net debt to EBITDA", "lower", 4.5, 0.5),
            MetricRule("interest_coverage", "Interest coverage", "higher", 1.5, 12.0),
        ),
        "valuation": (
            MetricRule("forward_pe", "Forward P/E", "range", 0.0, 10.0, 25.0, 55.0),
            MetricRule("pe_ratio", "Trailing P/E", "range", 0.0, 10.0, 25.0, 60.0),
            MetricRule("fcf_yield", "Free cash flow yield", "higher", -0.01, 0.08),
        ),
        "sector_specific": (
            MetricRule("fcf_conversion", "Free cash flow conversion", "higher", 0.20, 0.90),
            MetricRule("gross_margin", "Gross margin", "higher", 0.10, 0.55),
        ),
    },
)
