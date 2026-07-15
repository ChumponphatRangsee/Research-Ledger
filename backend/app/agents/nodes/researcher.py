"""Agent 1: Gather news and qualitative data."""

from app.agents.state import ResearchState


def researcher_node(state: ResearchState) -> ResearchState:
    symbol = state["ticker_symbol"]
    # TODO: integrate news APIs, SEC filings, web search
    return {
        **state,
        "news_summary": f"Qualitative research placeholder for {symbol}.",
        "qualitative_signals": ["Strong brand", "Growing TAM"],
        "pipeline_stage": "financial",
    }
