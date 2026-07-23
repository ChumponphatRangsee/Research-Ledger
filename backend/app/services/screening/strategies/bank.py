"""Bank scoring configuration that excludes corporate debt and FCF ratios."""

from app.services.screening.models import BusinessModel
from app.services.screening.scoring import MetricRule, StrategyDefinition

STRATEGY = StrategyDefinition(
    business_model=BusinessModel.BANK,
    category_weights={
        "profitability": 0.30,
        "capital_credit": 0.25,
        "efficiency": 0.15,
        "growth": 0.10,
        "valuation": 0.20,
    },
    rules={
        "profitability": (
            MetricRule("roe", "Return on equity", "higher", 0.04, 0.18),
            MetricRule("roa", "Return on assets", "higher", 0.003, 0.018),
            MetricRule("rotce", "Return on tangible common equity", "higher", 0.05, 0.20),
            MetricRule("net_interest_margin", "Net interest margin", "higher", 0.015, 0.045),
        ),
        "capital_credit": (
            MetricRule("cet1_ratio", "CET1 ratio", "higher", 0.08, 0.15),
            MetricRule("charge_off_ratio", "Charge-off ratio", "lower", 0.04, 0.005),
        ),
        "efficiency": (
            MetricRule("efficiency_ratio", "Efficiency ratio", "lower", 0.80, 0.45),
        ),
        "growth": (
            MetricRule("earnings_growth", "Earnings growth", "higher", -0.15, 0.20),
            MetricRule("revenue_growth", "Revenue growth", "higher", -0.10, 0.15),
            MetricRule("tangible_book_growth", "Tangible book growth", "higher", -0.05, 0.15),
        ),
        "valuation": (
            MetricRule("price_to_book", "Price to book", "range", 0.2, 0.8, 1.8, 4.0, 1.3),
            MetricRule("pe_ratio", "Trailing P/E", "range", 0.0, 7.0, 15.0, 35.0),
            MetricRule("forward_pe", "Forward P/E", "range", 0.0, 7.0, 15.0, 35.0),
        ),
    },
    minimum_available_metrics=3,
    required_categories=("profitability", "valuation"),
    required_category_groups=(("capital_credit", "efficiency"),),
    incomplete_data_reason="Insufficient bank-specific financial data",
)
