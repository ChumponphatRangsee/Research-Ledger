"""Agent 4: Produce final investment memo."""

from app.agents.state import ResearchState


def decision_maker_node(state: ResearchState) -> ResearchState:
    symbol = state["ticker_symbol"]
    upside = state.get("upside_pct", 0)
    recommendation = "BUY" if upside > 10 else "HOLD" if upside > 0 else "PASS"

    memo = (
        f"# Investment Memo: {symbol}\n\n"
        f"**Recommendation:** {recommendation}\n\n"
        f"## Qualitative\n{state.get('news_summary', '')}\n\n"
        f"## Financial\n{state.get('financial_analysis', '')}\n\n"
        f"## Valuation\n"
        f"Fair value: ${state.get('fair_value', 0):.2f} "
        f"({upside:+.1f}% upside)\n"
    )

    return {
        **state,
        "recommendation": recommendation,
        "investment_memo": memo,
        "memo_summary": f"{recommendation} — {upside:+.1f}% upside vs fair value",
        "pipeline_stage": "complete",
    }
