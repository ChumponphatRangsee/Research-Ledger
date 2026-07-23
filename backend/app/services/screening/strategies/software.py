"""Software business scoring configuration."""

from app.services.screening.models import BusinessModel
from app.services.screening.scoring import MetricRule, StrategyDefinition

STRATEGY = StrategyDefinition(
    business_model=BusinessModel.SOFTWARE,
    category_weights={
        "quality": 0.25,
        "growth": 0.20,
        "financial_strength": 0.15,
        "valuation": 0.20,
        "sector_specific": 0.20,
    },
    rules={
        "quality": (
            MetricRule("roic", "ROIC", "higher", 0.02, 0.25, weight=1.2),
            MetricRule("fcf_margin", "Free cash flow margin", "higher", 0.0, 0.30, weight=1.1),
            MetricRule("gross_margin", "Gross margin", "higher", 0.30, 0.80),
            MetricRule("operating_margin", "Operating margin", "higher", 0.0, 0.35),
        ),
        "growth": (
            MetricRule("revenue_growth", "Revenue growth", "higher", -0.05, 0.25),
            MetricRule("earnings_growth", "Earnings growth", "higher", -0.10, 0.30),
        ),
        "financial_strength": (
            MetricRule("net_debt_to_ebitda", "Net debt to EBITDA", "lower", 5.0, 0.0),
            MetricRule("interest_coverage", "Interest coverage", "higher", 1.0, 15.0),
        ),
        "valuation": (
            MetricRule("forward_pe", "Forward P/E", "range", 0.0, 15.0, 30.0, 70.0),
            MetricRule("pe_ratio", "Trailing P/E", "range", 0.0, 15.0, 30.0, 75.0),
            MetricRule("fcf_yield", "Free cash flow yield", "higher", -0.01, 0.07),
        ),
        "sector_specific": (
            MetricRule("operating_margin", "Margin scalability", "higher", 0.0, 0.35),
            MetricRule("fcf_margin", "Cash-generative scalability", "higher", 0.0, 0.30),
        ),
    },
)
