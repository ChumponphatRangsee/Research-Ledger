"""Semiconductor scoring configuration with cyclicality-aware valuation."""

from app.services.screening.models import BusinessModel
from app.services.screening.scoring import MetricRule, StrategyDefinition

STRATEGY = StrategyDefinition(
    business_model=BusinessModel.SEMICONDUCTOR,
    category_weights={
        "quality": 0.25,
        "growth": 0.20,
        "financial_strength": 0.15,
        "valuation": 0.20,
        "sector_specific": 0.20,
    },
    rules={
        "quality": (
            MetricRule("roic", "ROIC", "higher", 0.0, 0.25),
            MetricRule("gross_margin", "Gross margin", "higher", 0.20, 0.65),
            MetricRule("operating_margin", "Operating margin", "higher", -0.05, 0.35),
            MetricRule("fcf_margin", "Free cash flow margin", "higher", -0.05, 0.25),
        ),
        "growth": (
            MetricRule("revenue_growth", "Revenue growth", "higher", -0.15, 0.30),
            MetricRule("earnings_growth", "Earnings growth", "higher", -0.25, 0.40),
        ),
        "financial_strength": (
            MetricRule("debt_to_equity", "Debt to equity", "lower", 1.5, 0.2),
            MetricRule("net_debt_to_ebitda", "Net debt to EBITDA", "lower", 4.0, 0.0),
            MetricRule("fcf_margin", "Cash generation", "higher", -0.05, 0.25),
        ),
        "valuation": (
            MetricRule("forward_pe", "Forward P/E", "range", 0.0, 12.0, 28.0, 65.0),
            MetricRule("pe_ratio", "Cyclicality-adjusted P/E", "range", 0.0, 10.0, 25.0, 65.0),
            MetricRule("fcf_yield", "Free cash flow yield", "higher", -0.02, 0.08),
        ),
        "sector_specific": (
            MetricRule("gross_margin", "Gross-margin strength", "higher", 0.20, 0.65, weight=1.4),
            MetricRule("capex_intensity", "Capital intensity", "lower", 0.30, 0.05),
            MetricRule("inventory_growth", "Inventory trend", "range", -0.35, -0.05, 0.10, 0.50),
        ),
    },
)
