"""Agent 2: Analyze financial statements."""

from app.agents.state import ResearchState
from app.services.yfinance_client import fetch_financial_metrics


def financial_analyst_node(state: ResearchState) -> ResearchState:
    symbol = state["ticker_symbol"]
    metrics = fetch_financial_metrics(symbol)
    return {
        **state,
        "financial_metrics": metrics,
        "financial_analysis": (
            f"P/E: {metrics.get('pe_ratio', 'N/A')}, "
            f"ROE: {metrics.get('roe', 'N/A')}, "
            f"Revenue growth: {metrics.get('revenue_growth', 'N/A')}"
        ),
        "pipeline_stage": "valuator",
    }
