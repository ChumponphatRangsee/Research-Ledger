from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from app.api.auth import AuthenticatedUser, require_user
from app.db.supabase import get_supabase_client
from app.workers.tasks import run_daily_screener, trigger_analysis_pipeline

router = APIRouter()


class TriggerPipelineRequest(BaseModel):
    ticker_symbol: str
    screening_run_id: UUID | None = None


def _assert_screening_run_owner(screening_run_id: UUID, user_id: UUID) -> None:
    result = (
        get_supabase_client()
        .table("screening_runs")
        .select("id")
        .eq("id", str(screening_run_id))
        .eq("user_id", str(user_id))
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Screening run not found")


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
    if body.screening_run_id:
        _assert_screening_run_owner(body.screening_run_id, current_user.id)

    task = trigger_analysis_pipeline.delay(
        body.ticker_symbol,
        str(current_user.id),
        str(body.screening_run_id) if body.screening_run_id else None,
    )
    return {"task_id": task.id, "ticker": body.ticker_symbol, "status": "queued"}
