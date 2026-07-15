"""Agent 3: Calculate fair value."""

from app.agents.state import ResearchState


def valuator_node(state: ResearchState) -> ResearchState:
    metrics = state.get("financial_metrics", {})
    current_price = metrics.get("current_price") or 0
    pe = metrics.get("pe_ratio") or 20
    # Simplified DCF / relative valuation placeholder
    fair_value = round(current_price * (18 / pe), 2) if pe and current_price else 0
    upside = round(((fair_value - current_price) / current_price) * 100, 2) if current_price else 0

    return {
        **state,
        "fair_value": fair_value,
        "valuation_method": "relative_pe_normalized",
        "upside_pct": upside,
        "pipeline_stage": "decision",
    }
