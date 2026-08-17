from datetime import datetime
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.api.auth import AuthenticatedUser, require_user
from app.db.supabase import get_supabase_client
from app.services.portfolio_import.repository import (
    SupabaseTransactionImportRepository,
)
from app.services.portfolio_ledger import SupabasePortfolioLedgerRepository
from app.services.portfolio_workflow import (
    SupabaseTransactionWorkflowRepository,
    TransactionAlreadyReversed,
    TransactionDraftAlreadyConfirmed,
    TransactionDraftNotFound,
    TransactionNotFound,
)

router = APIRouter()


class ExecutePortfolioRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    shares: float
    cost_basis: float | None = None
    notes: str | None = None


InvestmentAccountType = Literal[
    "BROKERAGE",
    "CRYPTO_EXCHANGE",
    "CRYPTO_WALLET",
    "BANK",
    "CASH",
    "OTHER",
]

TransactionType = Literal[
    "BUY",
    "SELL",
    "DIVIDEND",
    "STAKING",
    "INTEREST",
    "TRANSFER_IN",
    "TRANSFER_OUT",
    "FEE",
    "REVERSAL",
]

ManualTransactionType = Literal[
    "BUY",
    "SELL",
    "DIVIDEND",
    "STAKING",
    "INTEREST",
    "TRANSFER_IN",
    "TRANSFER_OUT",
    "FEE",
]

FeeUnit = Literal["QUOTE_CURRENCY", "ASSET_UNITS"]


class InvestmentAccountCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    name: str = Field(min_length=1, max_length=120)
    account_type: InvestmentAccountType = "BROKERAGE"
    institution_name: str | None = Field(default=None, max_length=120)
    external_identifier: str | None = Field(default=None, max_length=120)
    currency: str = Field(default="THB", min_length=3, max_length=10)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        stripped = value.strip()
        if not stripped:
            raise ValueError("Account name is required")
        return stripped

    @field_validator("institution_name", "external_identifier")
    @classmethod
    def strip_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    @field_validator("currency")
    @classmethod
    def normalize_currency(cls, value: str) -> str:
        return value.strip().upper()


class ReversalDraftCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_at: datetime | None = None
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("notes")
    @classmethod
    def strip_notes(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None


class TransactionDraftCreateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    investment_account_id: UUID
    asset_id: UUID
    transaction_type: ManualTransactionType
    transaction_at: datetime
    quantity: Decimal | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(default=None, gt=0)
    gross_amount: Decimal | None = Field(default=None, gt=0)
    fee_amount: Decimal | None = Field(default=None, ge=0)
    fee_unit: FeeUnit | None = None
    currency: str = Field(min_length=3, max_length=10)
    fx_rate_to_thb: Decimal | None = Field(default=None, gt=0)
    source_identifier: str | None = Field(default=None, max_length=200)
    source_row_number: int | None = Field(default=None, gt=0)
    source_fingerprint: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("currency")
    @classmethod
    def normalize_transaction_currency(cls, value: str) -> str:
        return value.strip().upper()

    @field_validator("source_identifier", "source_fingerprint", "notes")
    @classmethod
    def strip_optional_draft_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    def to_payload(self) -> dict[str, object]:
        _validate_draft_economics(
            transaction_type=self.transaction_type,
            quantity=self.quantity,
            unit_price=self.unit_price,
            gross_amount=self.gross_amount,
        )
        return _json_ready(
            {
                **self.model_dump(),
                "reversal_of_transaction_id": None,
                "source_type": "MANUAL",
                "raw_source_data": {},
                "source_metadata": {"entry_method": "manual"},
            }
        )


class TransactionDraftUpdateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    transaction_at: datetime | None = None
    quantity: Decimal | None = Field(default=None, gt=0)
    unit_price: Decimal | None = Field(default=None, gt=0)
    gross_amount: Decimal | None = Field(default=None, gt=0)
    fee_amount: Decimal | None = Field(default=None, ge=0)
    fee_unit: FeeUnit | None = None
    currency: str | None = Field(default=None, min_length=3, max_length=10)
    fx_rate_to_thb: Decimal | None = Field(default=None, gt=0)
    source_identifier: str | None = Field(default=None, max_length=200)
    source_row_number: int | None = Field(default=None, gt=0)
    source_fingerprint: str | None = Field(default=None, max_length=200)
    notes: str | None = Field(default=None, max_length=500)

    @field_validator("currency")
    @classmethod
    def normalize_optional_currency(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return value.strip().upper()

    @field_validator("source_identifier", "source_fingerprint", "notes")
    @classmethod
    def strip_optional_update_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        stripped = value.strip()
        return stripped or None

    def to_payload(self) -> dict[str, object]:
        return _json_ready(self.model_dump(exclude_unset=True))


def _json_ready(payload: dict[str, object]) -> dict[str, object]:
    converted: dict[str, object] = {}
    for key, value in payload.items():
        if isinstance(value, UUID):
            converted[key] = str(value)
        elif isinstance(value, Decimal):
            converted[key] = format(value, "f")
        elif isinstance(value, datetime):
            converted[key] = value.isoformat()
        else:
            converted[key] = value
    return converted


def _validate_draft_economics(
    *,
    transaction_type: str,
    quantity: Decimal | None,
    unit_price: Decimal | None,
    gross_amount: Decimal | None,
) -> None:
    if transaction_type in {"BUY", "SELL"} and (
        quantity is None or unit_price is None
    ):
        raise ValueError("BUY and SELL drafts require quantity and unit_price")
    if transaction_type in {"DIVIDEND", "INTEREST", "FEE"} and gross_amount is None:
        raise ValueError(f"{transaction_type} drafts require gross_amount")
    if transaction_type in {"TRANSFER_IN", "TRANSFER_OUT"} and quantity is None:
        raise ValueError(f"{transaction_type} drafts require quantity")
    if transaction_type == "STAKING" and quantity is None and gross_amount is None:
        raise ValueError("STAKING drafts require quantity or gross_amount")


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


@router.get("/investment-accounts")
async def list_investment_accounts(
    current_user: AuthenticatedUser = Depends(require_user),
):
    client = get_supabase_client()
    result = (
        client.table("investment_accounts")
        .select(
            "id, user_id, name, account_type, institution_name, "
            "external_identifier, currency, created_at, updated_at"
        )
        .eq("user_id", str(current_user.id))
        .order("name")
        .execute()
    )
    return {"accounts": result.data or [], "count": len(result.data or [])}


@router.post("/investment-accounts")
async def create_investment_account(
    body: InvestmentAccountCreateRequest,
    current_user: AuthenticatedUser = Depends(require_user),
):
    client = get_supabase_client()
    payload = {
        "user_id": str(current_user.id),
        "name": body.name,
        "account_type": body.account_type,
        "institution_name": body.institution_name,
        "external_identifier": body.external_identifier,
        "currency": body.currency,
        "source_metadata": {"entry_method": "manual"},
    }
    result = (
        client.table("investment_accounts")
        .insert(payload)
        .execute()
    )
    return {"account": result.data[0] if result.data else None}


@router.get("/ledger/summary")
async def portfolio_ledger_summary(
    current_user: AuthenticatedUser = Depends(require_user),
):
    repository = SupabasePortfolioLedgerRepository()
    snapshot = repository.build_snapshot(user_id=current_user.id)
    return snapshot.to_report()


@router.post("/ledger/rebuild")
async def rebuild_portfolio_ledger(
    current_user: AuthenticatedUser = Depends(require_user),
):
    repository = SupabasePortfolioLedgerRepository()
    snapshot = repository.rebuild_position_projections(user_id=current_user.id)
    return snapshot.to_report()


@router.get("/transactions")
async def list_confirmed_transactions(
    investment_account_id: UUID | None = None,
    transaction_type: TransactionType | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    current_user: AuthenticatedUser = Depends(require_user),
):
    repository = SupabasePortfolioLedgerRepository()
    transactions = repository.list_confirmed_transactions(
        user_id=current_user.id,
        investment_account_id=investment_account_id,
        transaction_type=transaction_type,
        limit=limit,
    )
    return {"transactions": transactions, "count": len(transactions)}


@router.get("/transactions/{transaction_id}")
async def get_confirmed_transaction(
    transaction_id: UUID,
    current_user: AuthenticatedUser = Depends(require_user),
):
    repository = SupabasePortfolioLedgerRepository()
    transaction = repository.get_confirmed_transaction(
        user_id=current_user.id,
        transaction_id=transaction_id,
    )
    if transaction is None:
        raise HTTPException(status_code=404, detail="Transaction not found")
    return {"transaction": transaction}


@router.post("/transactions/{transaction_id}/reversal-draft")
async def create_reversal_draft(
    transaction_id: UUID,
    body: ReversalDraftCreateRequest | None = None,
    current_user: AuthenticatedUser = Depends(require_user),
):
    repository = SupabaseTransactionWorkflowRepository()
    body = body or ReversalDraftCreateRequest()
    try:
        draft = repository.create_reversal_draft(
            user_id=current_user.id,
            transaction_id=transaction_id,
            transaction_at=body.transaction_at,
            notes=body.notes,
        )
    except TransactionNotFound as exc:
        raise HTTPException(status_code=404, detail="Transaction not found") from exc
    except TransactionAlreadyReversed as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "draft_created", "draft": draft}


@router.post("/transactions/{transaction_id}/correction-draft")
async def create_correction_draft(
    transaction_id: UUID,
    body: TransactionDraftUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_user),
):
    repository = SupabaseTransactionWorkflowRepository()
    try:
        draft = repository.create_correction_draft(
            user_id=current_user.id,
            transaction_id=transaction_id,
            payload=body.to_payload(),
        )
    except TransactionNotFound as exc:
        raise HTTPException(status_code=404, detail="Transaction not found") from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "draft_created", "draft": draft}


@router.get("/transaction-import-batches")
async def list_transaction_import_batches(
    limit: int = Query(default=50, ge=1, le=200),
    current_user: AuthenticatedUser = Depends(require_user),
):
    repository = SupabaseTransactionImportRepository()
    batches = repository.list_batches(user_id=current_user.id, limit=limit)
    return {"batches": batches, "count": len(batches)}


@router.get("/transaction-import-errors")
async def list_transaction_import_errors(
    import_batch_id: UUID | None = None,
    limit: int = Query(default=200, ge=1, le=500),
    current_user: AuthenticatedUser = Depends(require_user),
):
    repository = SupabaseTransactionImportRepository()
    errors = repository.list_errors(
        user_id=current_user.id,
        import_batch_id=import_batch_id,
        limit=limit,
    )
    return {"errors": errors, "count": len(errors)}


@router.get("/transaction-drafts")
async def list_transaction_drafts(
    status: Literal["pending", "confirmed", "all"] = "pending",
    import_batch_id: UUID | None = None,
    current_user: AuthenticatedUser = Depends(require_user),
):
    repository = SupabaseTransactionWorkflowRepository()
    drafts = repository.list_drafts(
        user_id=current_user.id,
        status=status,
        import_batch_id=import_batch_id,
    )
    return {"drafts": drafts, "count": len(drafts)}


@router.post("/transaction-drafts")
async def create_transaction_draft(
    body: TransactionDraftCreateRequest,
    current_user: AuthenticatedUser = Depends(require_user),
):
    repository = SupabaseTransactionWorkflowRepository()
    try:
        draft = repository.create_draft(
            user_id=current_user.id,
            payload=body.to_payload(),
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"status": "draft_created", "draft": draft}


@router.patch("/transaction-drafts/{draft_id}")
async def update_transaction_draft(
    draft_id: UUID,
    body: TransactionDraftUpdateRequest,
    current_user: AuthenticatedUser = Depends(require_user),
):
    repository = SupabaseTransactionWorkflowRepository()
    try:
        draft = repository.update_draft(
            user_id=current_user.id,
            draft_id=draft_id,
            payload=body.to_payload(),
        )
    except TransactionDraftNotFound as exc:
        raise HTTPException(status_code=404, detail="Transaction draft not found") from exc
    except TransactionDraftAlreadyConfirmed as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    return {"status": "draft_updated", "draft": draft}


@router.post("/transaction-drafts/{draft_id}/confirm")
async def confirm_transaction_draft(
    draft_id: UUID,
    current_user: AuthenticatedUser = Depends(require_user),
):
    repository = SupabaseTransactionWorkflowRepository()
    try:
        transaction = repository.confirm_draft(
            user_id=current_user.id,
            draft_id=draft_id,
        )
    except TransactionDraftNotFound as exc:
        raise HTTPException(status_code=404, detail="Transaction draft not found") from exc
    return {"status": "confirmed", "transaction": transaction}


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

    existing = (
        client.table("portfolios")
        .select("id")
        .eq("user_id", str(current_user.id))
        .eq("approved_from_inbox_id", str(inbox_id))
        .limit(1)
        .execute()
    )
    if existing.data:
        raise HTTPException(status_code=409, detail="Inbox item has already been executed")

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
