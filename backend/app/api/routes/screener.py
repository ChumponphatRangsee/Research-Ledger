from uuid import UUID

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field

from app.api.auth import AuthenticatedUser, require_user
from app.db.supabase import get_supabase_client
from app.workers.tasks import run_daily_screener, trigger_analysis_pipeline

router = APIRouter()


class TriggerPipelineRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    ticker_symbol: str
    screening_run_id: UUID | None = None


class RunScreenerRequest(BaseModel):
    # Ignore legacy/spoofed fields such as user_id while ownership always comes
    # from the verified JWT.
    model_config = ConfigDict(extra="ignore")

    top_n_candidates: int | None = Field(default=None, ge=1, le=100)


def _owned_screening_run(screening_run_id: UUID, user_id: UUID) -> dict:
    result = (
        get_supabase_client()
        .table("screening_runs")
        .select("*")
        .eq("id", str(screening_run_id))
        .eq("user_id", str(user_id))
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Screening run not found")
    return result.data[0]


def _assert_screening_run_owner(screening_run_id: UUID, user_id: UUID) -> None:
    _owned_screening_run(screening_run_id, user_id)


@router.post("/run")
async def run_screener(
    body: RunScreenerRequest | None = None,
    current_user: AuthenticatedUser = Depends(require_user),
):
    """Manually trigger the daily quantitative screener."""
    top_n = body.top_n_candidates if body else None
    if top_n is None:
        task = run_daily_screener.delay(str(current_user.id))
    else:
        task = run_daily_screener.delay(str(current_user.id), top_n)
    return {"task_id": task.id, "status": "queued"}


@router.get("/runs/latest")
async def get_latest_screening_run(
    current_user: AuthenticatedUser = Depends(require_user),
):
    result = (
        get_supabase_client()
        .table("screening_runs")
        .select("*")
        .eq("user_id", str(current_user.id))
        .order("started_at", desc=True)
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="No screening runs found")
    return result.data[0]


@router.get("/runs/{run_id}")
async def get_screening_run(
    run_id: UUID,
    current_user: AuthenticatedUser = Depends(require_user),
):
    return _owned_screening_run(run_id, current_user.id)


@router.get("/runs/{run_id}/results")
async def get_screening_results(
    run_id: UUID,
    passed: bool | None = None,
    business_model: str | None = None,
    min_score: float | None = Query(default=None, ge=0, le=100),
    limit: int = Query(default=100, ge=1, le=500),
    sort: Literal[
        "total_score_desc",
        "total_score_asc",
        "confidence_desc",
        "created_desc",
    ] = "total_score_desc",
    current_user: AuthenticatedUser = Depends(require_user),
):
    """Return owner-scoped explainable results with deterministic sorting."""
    _assert_screening_run_owner(run_id, current_user.id)
    sort_field, descending = {
        "total_score_desc": ("total_score", True),
        "total_score_asc": ("total_score", False),
        "confidence_desc": ("confidence_score", True),
        "created_desc": ("created_at", True),
    }[sort]
    query = (
        get_supabase_client()
        .table("screening_results")
        .select("*,tickers(symbol,name,sector,industry)")
        .eq("screening_run_id", str(run_id))
    )
    if passed is not None:
        query = query.eq("passed", passed)
    if business_model:
        query = query.eq("business_model", business_model)
    if min_score is not None:
        query = query.gte("total_score", min_score)
    result = query.order(sort_field, desc=descending).limit(limit).execute()
    return {"run_id": str(run_id), "items": result.data or []}


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
