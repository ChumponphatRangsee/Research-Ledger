"""Energy scoring configuration emphasizing cash flow and capital discipline."""

from app.services.screening.models import BusinessModel
from app.services.screening.scoring import MetricRule, StrategyDefinition

STRATEGY = StrategyDefinition(
    business_model=BusinessModel.ENERGY,
    category_weights={
        "quality": 0.25,
        "growth": 0.15,
        "financial_strength": 0.20,
        "valuation": 0.15,
        "sector_specific": 0.25,
    },
    rules={
        "quality": (
            MetricRule("roic", "ROIC", "higher", -0.02, 0.20),
            MetricRule("roe", "Return on equity", "higher", 0.0, 0.22),
            MetricRule("fcf_margin", "Free cash flow margin", "higher", -0.05, 0.20),
        ),
        "growth": (
            MetricRule("revenue_growth", "Revenue growth", "higher", -0.25, 0.20),
            MetricRule("earnings_growth", "Earnings growth", "higher", -0.40, 0.30),
        ),
        "financial_strength": (
            MetricRule("debt_to_equity", "Debt to equity", "lower", 1.2, 0.2),
            MetricRule("net_debt_to_ebitda", "Net debt to EBITDA", "lower", 3.5, 0.3),
            MetricRule("interest_coverage", "Interest coverage", "higher", 1.5, 12.0),
        ),
        "valuation": (
            # P/E carries less weight because one commodity year can distort it.
            MetricRule("pe_ratio", "Cyclicality-aware P/E", "range", 0.0, 6.0, 16.0, 40.0, 0.6),
            MetricRule("forward_pe", "Forward P/E", "range", 0.0, 6.0, 16.0, 40.0, 0.6),
            MetricRule("fcf_yield", "Free cash flow yield", "higher", -0.02, 0.12, weight=1.5),
        ),
        "sector_specific": (
            MetricRule("fcf_yield", "Capital discipline / FCF yield", "higher", -0.02, 0.12),
            MetricRule("fcf_margin", "Free cash flow strength", "higher", -0.05, 0.20),
            MetricRule("capex_intensity", "Capital intensity", "lower", 0.45, 0.08),
        ),
    },
    required_categories=("quality", "valuation"),
)
