from typing import Any, TypedDict


class ResearchState(TypedDict, total=False):
    ticker_symbol: str
    screening_run_id: str | None
    inbox_id: str | None

    # Agent outputs
    news_summary: str
    qualitative_signals: list[str]
    financial_metrics: dict[str, Any]
    financial_analysis: str
    fair_value: float
    valuation_method: str
    upside_pct: float
    investment_memo: str
    recommendation: str
    memo_summary: str

    # Pipeline control
    pipeline_stage: str
    error: str | None
