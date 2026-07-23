from app.agents.graph import run_pipeline
from app.services.screener import record_triggered_count, run_quantitative_screen
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.run_daily_screener")
def run_daily_screener(user_id: str, top_n_candidates: int | None = None):
    """Screen stocks and enqueue AI work only for deterministic top-ranked names."""
    result = (
        run_quantitative_screen(user_id)
        if top_n_candidates is None
        else run_quantitative_screen(user_id, top_n_candidates=top_n_candidates)
    )
    triggered = 0
    for candidate in result.get("candidates", []):
        trigger_analysis_pipeline.delay(candidate["symbol"], user_id, result.get("run_id"))
        triggered += 1
    if result.get("run_id") and "selected_for_ai" in result:
        record_triggered_count(user_id, result["run_id"], triggered)

    return {
        "run_id": result.get("run_id"),
        "candidates_count": result.get("passed", result.get("count", 0)),
        "pipelines_triggered": triggered,
        "requested": result.get("requested", 0),
        "processed": result.get("processed", 0),
        "failed": result.get("failed", 0),
        "passed": result.get("passed", 0),
        "selected_for_ai": result.get("selected_for_ai", triggered),
    }


@celery_app.task(name="app.workers.tasks.trigger_analysis_pipeline")
def trigger_analysis_pipeline(ticker_symbol: str, user_id: str, screening_run_id: str | None = None):
    """Run the LangGraph multi-agent pipeline for a single ticker."""
    return run_pipeline(ticker_symbol, user_id, screening_run_id)
