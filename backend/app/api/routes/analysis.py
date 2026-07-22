from datetime import datetime, timezone
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException

from app.api.auth import AuthenticatedUser, require_user
from app.db.supabase import get_supabase_client

router = APIRouter()


def _owner_filter(user_id: UUID) -> str:
    return f"user_id.is.null,user_id.eq.{user_id}"


def _reviewed_at() -> str:
    return datetime.now(timezone.utc).isoformat()


@router.get("/inbox")
async def list_inbox(
    status: str = "pending_review",
    limit: int = 50,
    current_user: AuthenticatedUser = Depends(require_user),
):
    """List analysis inbox items awaiting human review."""
    client = get_supabase_client()
    query = (
        client.table("analysis_inbox")
        .select("*, tickers(symbol, name, sector)")
        .eq("status", status)
        .or_(_owner_filter(current_user.id))
        .order("created_at", desc=True)
        .limit(limit)
    )
    result = query.execute()
    return {"items": result.data, "count": len(result.data)}


@router.get("/inbox/{inbox_id}")
async def get_inbox_item(
    inbox_id: UUID,
    current_user: AuthenticatedUser = Depends(require_user),
):
    client = get_supabase_client()
    result = (
        client.table("analysis_inbox")
        .select("*, tickers(symbol, name, sector, industry)")
        .eq("id", str(inbox_id))
        .or_(_owner_filter(current_user.id))
        .limit(1)
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    return result.data[0]


@router.post("/inbox/{inbox_id}/approve")
async def approve_inbox_item(
    inbox_id: UUID,
    current_user: AuthenticatedUser = Depends(require_user),
):
    """Human-in-the-loop gate: approve and stage for portfolio execution."""
    client = get_supabase_client()
    result = (
        client.table("analysis_inbox")
        .update(
            {
                "status": "approved",
                "user_id": str(current_user.id),
                "reviewed_at": _reviewed_at(),
            }
        )
        .eq("id", str(inbox_id))
        .or_(_owner_filter(current_user.id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    return {"status": "approved", "item": result.data[0]}


@router.post("/inbox/{inbox_id}/discard")
async def discard_inbox_item(
    inbox_id: UUID,
    current_user: AuthenticatedUser = Depends(require_user),
):
    """Human-in-the-loop gate: discard the AI recommendation."""
    client = get_supabase_client()
    result = (
        client.table("analysis_inbox")
        .update(
            {
                "status": "discarded",
                "user_id": str(current_user.id),
                "reviewed_at": _reviewed_at(),
            }
        )
        .eq("id", str(inbox_id))
        .or_(_owner_filter(current_user.id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    return {"status": "discarded", "item": result.data[0]}
