"""LangGraph multi-agent research pipeline with human-in-the-loop breakpoint."""

from langgraph.graph import END, StateGraph

from app.agents.nodes.decision import decision_maker_node
from app.agents.nodes.financial import financial_analyst_node
from app.agents.nodes.researcher import researcher_node
from app.agents.nodes.valuator import valuator_node
from app.agents.state import ResearchState
from app.db.supabase import get_supabase_client


def _save_to_inbox(state: ResearchState) -> ResearchState:
    """Breakpoint: persist completed analysis to inbox for human approval."""
    client = get_supabase_client()
    symbol = state["ticker_symbol"]
    user_id = state["user_id"]

    ticker = client.table("tickers").select("id").eq("symbol", symbol).single().execute()
    if not ticker.data:
        ticker = client.table("tickers").insert({"symbol": symbol}).execute()
        ticker_id = ticker.data[0]["id"]
    else:
        ticker_id = ticker.data["id"]

    metrics = state.get("financial_metrics", {})
    inbox = client.table("analysis_inbox").insert(
        {
            "ticker_id": ticker_id,
            "user_id": user_id,
            "screening_run_id": state.get("screening_run_id"),
            "status": "pending_review",
            "pipeline_stage": "complete",
            "current_price": metrics.get("current_price"),
            "fair_value": state.get("fair_value"),
            "upside_pct": state.get("upside_pct"),
            "recommendation": state.get("recommendation"),
            "researcher_output": {
                "news_summary": state.get("news_summary"),
                "qualitative_signals": state.get("qualitative_signals"),
            },
            "financial_output": {
                "metrics": metrics,
                "analysis": state.get("financial_analysis"),
            },
            "valuation_output": {
                "fair_value": state.get("fair_value"),
                "method": state.get("valuation_method"),
                "upside_pct": state.get("upside_pct"),
            },
            "decision_output": {"recommendation": state.get("recommendation")},
            "investment_memo": state.get("investment_memo"),
            "memo_summary": state.get("memo_summary"),
        }
    ).execute()

    return {**state, "inbox_id": inbox.data[0]["id"] if inbox.data else None}


def build_research_graph():
    graph = StateGraph(ResearchState)

    graph.add_node("researcher", researcher_node)
    graph.add_node("financial", financial_analyst_node)
    graph.add_node("valuator", valuator_node)
    graph.add_node("decision", decision_maker_node)
    graph.add_node("save_inbox", _save_to_inbox)

    graph.set_entry_point("researcher")
    graph.add_edge("researcher", "financial")
    graph.add_edge("financial", "valuator")
    graph.add_edge("valuator", "decision")
    graph.add_edge("decision", "save_inbox")
    graph.add_edge("save_inbox", END)

    return graph.compile()


research_graph = build_research_graph()


def run_pipeline(ticker_symbol: str, user_id: str, screening_run_id: str | None = None) -> dict:
    result = research_graph.invoke(
        {
            "ticker_symbol": ticker_symbol,
            # Ownership enters the graph at invocation and is persisted at the human-review breakpoint.
            "user_id": user_id,
            "screening_run_id": screening_run_id,
            "pipeline_stage": "researcher",
        }
    )
    return dict(result)
