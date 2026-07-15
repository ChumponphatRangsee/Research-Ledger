from uuid import UUID

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.db.supabase import get_supabase_client

router = APIRouter()


class ExecutePortfolioRequest(BaseModel):
    user_id: UUID
    shares: float
    cost_basis: float | None = None
    notes: str | None = None


@router.get("/")
async def list_portfolios(user_id: UUID):
    client = get_supabase_client()
    result = (
        client.table("portfolios")
        .select("*, tickers(symbol, name, sector)")
        .eq("user_id", str(user_id))
        .eq("status", "active")
        .order("created_at", desc=True)
        .execute()
    )
    return {"holdings": result.data, "count": len(result.data)}


@router.post("/execute/{inbox_id}")
async def execute_from_inbox(inbox_id: UUID, body: ExecutePortfolioRequest):
    """Create a portfolio position from an approved inbox item."""
    client = get_supabase_client()

    inbox = (
        client.table("analysis_inbox")
        .select("id, ticker_id, status, fair_value")
        .eq("id", str(inbox_id))
        .single()
        .execute()
    )
    if not inbox.data:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    if inbox.data["status"] != "approved":
        raise HTTPException(status_code=400, detail="Inbox item must be approved first")

    avg_cost = body.cost_basis / body.shares if body.cost_basis and body.shares else None
    portfolio = (
        client.table("portfolios")
        .insert(
            {
                "user_id": str(body.user_id),
                "ticker_id": inbox.data["ticker_id"],
                "approved_from_inbox_id": str(inbox_id),
                "shares": body.shares,
                "cost_basis": body.cost_basis,
                "avg_cost_per_share": avg_cost,
                "notes": body.notes,
                "status": "active",
            }
        )
        .execute()
    )
    return {"status": "executed", "holding": portfolio.data[0] if portfolio.data else None}
