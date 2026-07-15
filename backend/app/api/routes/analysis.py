from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.supabase import get_supabase_client

router = APIRouter()


class InboxActionRequest(BaseModel):
    user_id: UUID


@router.get("/inbox")
async def list_inbox(status: str = "pending_review", limit: int = 50):
    """List analysis inbox items awaiting human review."""
    client = get_supabase_client()
    query = (
        client.table("analysis_inbox")
        .select("*, tickers(symbol, name, sector)")
        .eq("status", status)
        .order("created_at", desc=True)
        .limit(limit)
    )
    result = query.execute()
    return {"items": result.data, "count": len(result.data)}


@router.get("/inbox/{inbox_id}")
async def get_inbox_item(inbox_id: UUID):
    client = get_supabase_client()
    result = (
        client.table("analysis_inbox")
        .select("*, tickers(symbol, name, sector, industry)")
        .eq("id", str(inbox_id))
        .single()
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    return result.data


@router.post("/inbox/{inbox_id}/approve")
async def approve_inbox_item(inbox_id: UUID, body: InboxActionRequest):
    """Human-in-the-loop gate: approve and stage for portfolio execution."""
    client = get_supabase_client()
    result = (
        client.table("analysis_inbox")
        .update({"status": "approved", "user_id": str(body.user_id)})
        .eq("id", str(inbox_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    return {"status": "approved", "item": result.data[0]}


@router.post("/inbox/{inbox_id}/discard")
async def discard_inbox_item(inbox_id: UUID, body: InboxActionRequest):
    """Human-in-the-loop gate: discard the AI recommendation."""
    client = get_supabase_client()
    result = (
        client.table("analysis_inbox")
        .update({"status": "discarded", "user_id": str(body.user_id)})
        .eq("id", str(inbox_id))
        .execute()
    )
    if not result.data:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    return {"status": "discarded", "item": result.data[0]}
