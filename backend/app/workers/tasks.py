from app.agents.graph import run_pipeline
from app.services.screener import run_quantitative_screen
from app.workers.celery_app import celery_app


@celery_app.task(name="app.workers.tasks.run_daily_screener")
def run_daily_screener(user_id: str):
    """User-scoped Celery job: screen stocks and trigger AI pipeline for candidates."""
    result = run_quantitative_screen(user_id)
    triggered = 0
    for candidate in result.get("candidates", []):
        trigger_analysis_pipeline.delay(candidate["symbol"], user_id, result.get("run_id"))
        triggered += 1

    return {
        "run_id": result.get("run_id"),
        "candidates_count": result.get("count", 0),
        "pipelines_triggered": triggered,
    }


@celery_app.task(name="app.workers.tasks.trigger_analysis_pipeline")
def trigger_analysis_pipeline(ticker_symbol: str, user_id: str, screening_run_id: str | None = None):
    """Run the LangGraph multi-agent pipeline for a single ticker."""
    return run_pipeline(ticker_symbol, user_id, screening_run_id)
