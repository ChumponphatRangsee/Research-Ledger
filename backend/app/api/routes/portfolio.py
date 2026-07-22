from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict

from app.api.auth import AuthenticatedUser, require_user
from app.db.supabase import get_supabase_client

router = APIRouter()


class ExecutePortfolioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shares: float
    cost_basis: float | None = None
    notes: str | None = None


@router.get("/")
async def list_portfolios(current_user: AuthenticatedUser = Depends(require_user)):
    client = get_supabase_client()
    result = (
        client.table("portfolios")
        .select("*, tickers(symbol, name, sector)")
        .eq("user_id", str(current_user.id))
        .eq("status", "active")
        .order("created_at", desc=True)
        .execute()
    )
    return {"holdings": result.data, "count": len(result.data)}


@router.post("/execute/{inbox_id}")
async def execute_from_inbox(
    inbox_id: UUID,
    body: ExecutePortfolioRequest,
    current_user: AuthenticatedUser = Depends(require_user),
):
    """Create a portfolio position from an approved inbox item."""
    client = get_supabase_client()

    inbox = (
        client.table("analysis_inbox")
        .select("id, ticker_id, status, fair_value, user_id")
        .eq("id", str(inbox_id))
        .eq("user_id", str(current_user.id))
        .limit(1)
        .execute()
    )
    if not inbox.data:
        raise HTTPException(status_code=404, detail="Inbox item not found")
    inbox_item = inbox.data[0]
    if str(inbox_item.get("user_id")) != str(current_user.id):
        raise HTTPException(status_code=404, detail="Inbox item not found")
    if inbox_item["status"] != "approved":
        raise HTTPException(status_code=400, detail="Inbox item must be approved first")

    avg_cost = body.cost_basis / body.shares if body.cost_basis and body.shares else None
    portfolio = (
        client.table("portfolios")
        .insert(
            {
                "user_id": str(current_user.id),
                "ticker_id": inbox_item["ticker_id"],
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
