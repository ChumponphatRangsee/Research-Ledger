from uuid import UUID

from fastapi import APIRouter, Depends
from pydantic import BaseModel

from app.api.auth import AuthenticatedUser, require_user
from app.workers.tasks import run_daily_screener, trigger_analysis_pipeline

router = APIRouter()


class TriggerPipelineRequest(BaseModel):
    ticker_symbol: str
    screening_run_id: UUID | None = None


@router.post("/run")
async def run_screener(current_user: AuthenticatedUser = Depends(require_user)):
    """Manually trigger the daily quantitative screener."""
    task = run_daily_screener.delay(str(current_user.id))
    return {"task_id": task.id, "status": "queued"}


@router.post("/pipeline")
async def trigger_pipeline(
    body: TriggerPipelineRequest,
    current_user: AuthenticatedUser = Depends(require_user),
):
    """Trigger the LangGraph multi-agent pipeline for a single ticker."""
    task = trigger_analysis_pipeline.delay(
        body.ticker_symbol,
        str(current_user.id),
        str(body.screening_run_id) if body.screening_run_id else None,
    )
    return {"task_id": task.id, "ticker": body.ticker_symbol, "status": "queued"}
