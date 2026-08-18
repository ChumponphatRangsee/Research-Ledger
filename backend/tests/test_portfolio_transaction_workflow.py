from __future__ import annotations

from datetime import UTC, datetime
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.services.portfolio_workflow import (
    SupabaseTransactionWorkflowRepository,
    TransactionAlreadyReversed,
    TransactionDraftAlreadyConfirmed,
    TransactionDraftNotFound,
    TransactionNotFound,
)


USER_ID = UUID("11111111-1111-4111-8111-111111111111")
DRAFT_ID = UUID("22222222-2222-4222-8222-222222222222")
BATCH_ID = UUID("33333333-3333-4333-8333-333333333333")


class RecordingQuery:
    def __init__(self, client, table: str, data=None):
        self.client = client
        self.table = table
        self.calls = []
        self.data = data if data is not None else []

    def select(self, columns):
        self.calls.append(("select", columns))
        return self

    def eq(self, column, value):
        self.calls.append(("eq", column, value))
        return self

    def in_(self, column, values):
        self.calls.append(("in", column, tuple(values)))
        return self

    def order(self, column):
        self.calls.append(("order", column))
        return self

    def limit(self, value):
        self.calls.append(("limit", value))
        return self

    def insert(self, payload):
        self.calls.append(("insert", payload))
        self.data = [payload]
        return self

    def update(self, payload):
        self.calls.append(("update", payload))
        self.data = [payload]
        return self

    def execute(self):
        self.client.executed.append(self)
        return SimpleNamespace(data=self.data)


class RecordingRpc:
    def __init__(self, client, name: str, params: dict, data=None, error: Exception | None = None):
        self.client = client
        self.name = name
        self.params = params
        self.data = data
        self.error = error

    def execute(self):
        self.client.rpcs.append(self)
        if self.error:
            raise self.error
        return SimpleNamespace(data=self.data)


class RecordingClient:
    def __init__(self):
        self.queries_by_table: dict[str, list[RecordingQuery]] = {}
        self.executed: list[RecordingQuery] = []
        self.rpcs: list[RecordingRpc] = []
        self.rpc_result = {"id": "transaction-id"}
        self.rpc_error: Exception | None = None

    def queue_table(self, table: str, data):
        self.queries_by_table.setdefault(table, []).append(
            RecordingQuery(self, table, data)
        )

    def table(self, table: str):
        return self.queries_by_table[table].pop(0)

    def rpc(self, name: str, params: dict):
        return RecordingRpc(
            self,
            name,
            params,
            data=self.rpc_result,
            error=self.rpc_error,
        )


def test_list_drafts_filters_to_owner_and_pending_status():
    client = RecordingClient()
    client.queue_table(
        "transaction_drafts",
        [
            {"id": str(DRAFT_ID), "transaction_type": "BUY"},
            {"id": "already-confirmed", "transaction_type": "SELL"},
        ],
    )
    client.queue_table(
        "transactions",
        [{"id": "tx-existing", "confirmed_from_draft_id": "already-confirmed"}],
    )

    drafts = SupabaseTransactionWorkflowRepository(client).list_drafts(
        user_id=USER_ID,
        status="pending",
        import_batch_id=BATCH_ID,
    )

    assert [draft["id"] for draft in drafts] == [str(DRAFT_ID)]
    draft_query, confirmed_query = client.executed
    assert ("eq", "user_id", str(USER_ID)) in draft_query.calls
    assert ("eq", "import_batch_id", str(BATCH_ID)) in draft_query.calls
    assert ("eq", "user_id", str(USER_ID)) in confirmed_query.calls
    assert (
        "in",
        "confirmed_from_draft_id",
        (str(DRAFT_ID), "already-confirmed"),
    ) in confirmed_query.calls


def test_confirm_draft_calls_atomic_rpc_with_verified_owner():
    client = RecordingClient()

    transaction = SupabaseTransactionWorkflowRepository(client).confirm_draft(
        user_id=USER_ID,
        draft_id=DRAFT_ID,
    )

    assert transaction == {"id": "transaction-id"}
    assert len(client.rpcs) == 1
    assert client.rpcs[0].name == "confirm_transaction_draft"
    assert client.rpcs[0].params == {
        "p_draft_id": str(DRAFT_ID),
        "p_user_id": str(USER_ID),
    }


def test_confirm_draft_maps_not_found_rpc_error():
    client = RecordingClient()
    client.rpc_error = RuntimeError("Transaction draft not found")

    with pytest.raises(TransactionDraftNotFound):
        SupabaseTransactionWorkflowRepository(client).confirm_draft(
            user_id=USER_ID,
            draft_id=DRAFT_ID,
        )


def test_create_draft_inserts_verified_owner_and_manual_defaults():
    client = RecordingClient()
    client.queue_table("transaction_drafts", [])

    draft = SupabaseTransactionWorkflowRepository(client).create_draft(
        user_id=USER_ID,
        payload={
            "investment_account_id": "account-id",
            "asset_id": "asset-id",
            "transaction_type": "BUY",
            "transaction_at": "2026-01-02T00:00:00+00:00",
            "quantity": "1",
            "unit_price": "10",
            "currency": "USD",
        },
    )

    query = client.executed[0]
    assert query.table == "transaction_drafts"
    assert ("insert", draft) in query.calls
    assert draft["user_id"] == str(USER_ID)
    assert draft["source_type"] == "MANUAL"
    assert draft["raw_source_data"] == {}
    assert draft["source_metadata"] == {"entry_method": "manual"}


def test_update_draft_rejects_confirmed_draft_and_scopes_update():
    client = RecordingClient()
    client.queue_table("transaction_drafts", [{"id": str(DRAFT_ID), "notes": "old"}])
    client.queue_table("transactions", [])
    client.queue_table("transaction_drafts", [])

    draft = SupabaseTransactionWorkflowRepository(client).update_draft(
        user_id=USER_ID,
        draft_id=DRAFT_ID,
        payload={"notes": "new", "user_id": "spoof"},
    )

    get_query, confirmed_query, update_query = client.executed
    assert ("eq", "user_id", str(USER_ID)) in get_query.calls
    assert ("eq", "id", str(DRAFT_ID)) in get_query.calls
    assert ("in", "confirmed_from_draft_id", (str(DRAFT_ID),)) in confirmed_query.calls
    assert ("eq", "user_id", str(USER_ID)) in update_query.calls
    assert ("eq", "id", str(DRAFT_ID)) in update_query.calls
    assert ("update", {"notes": "new"}) in update_query.calls
    assert draft["status"] == "pending"
    assert draft["confirmed_transaction_id"] is None

    client = RecordingClient()
    client.queue_table("transaction_drafts", [{"id": str(DRAFT_ID)}])
    client.queue_table(
        "transactions",
        [{"id": "transaction-id", "confirmed_from_draft_id": str(DRAFT_ID)}],
    )

    with pytest.raises(TransactionDraftAlreadyConfirmed):
        SupabaseTransactionWorkflowRepository(client).update_draft(
            user_id=USER_ID,
            draft_id=DRAFT_ID,
            payload={"notes": "new"},
        )


def test_create_correction_draft_copies_original_and_marks_metadata():
    client = RecordingClient()
    client.queue_table(
        "transactions",
        [
            {
                "id": str(DRAFT_ID),
                "investment_account_id": "account-id",
                "asset_id": "asset-id",
                "transaction_type": "BUY",
                "transaction_at": "2026-01-02T00:00:00+00:00",
                "quantity": "2",
                "unit_price": "10",
                "gross_amount": "20",
                "fee_amount": "1",
                "fee_unit": "QUOTE_CURRENCY",
                "currency": "USD",
                "fx_rate_to_thb": "35",
            }
        ],
    )
    client.queue_table("transaction_drafts", [])

    draft = SupabaseTransactionWorkflowRepository(client).create_correction_draft(
        user_id=USER_ID,
        transaction_id=DRAFT_ID,
        payload={"quantity": "3", "notes": "correct quantity"},
    )

    assert draft["user_id"] == str(USER_ID)
    assert draft["transaction_type"] == "BUY"
    assert draft["quantity"] == "3"
    assert draft["unit_price"] == "10"
    assert draft["reversal_of_transaction_id"] is None
    assert draft["source_identifier"] == f"correction:{DRAFT_ID}"
    assert draft["source_metadata"] == {
        "entry_method": "manual_correction",
        "correction_of_transaction_id": str(DRAFT_ID),
    }
    assert draft["notes"] == "correct quantity"


def test_create_reversal_draft_copies_original_financial_payload():
    client = RecordingClient()
    client.queue_table(
        "transactions",
        [
            {
                "id": str(DRAFT_ID),
                "user_id": str(USER_ID),
                "investment_account_id": "account-id",
                "asset_id": "asset-id",
                "reversal_of_transaction_id": None,
                "transaction_type": "BUY",
                "transaction_at": "2026-01-02T00:00:00+00:00",
                "quantity": "2",
                "unit_price": "10",
                "gross_amount": "20",
                "fee_amount": "1",
                "fee_unit": "QUOTE_CURRENCY",
                "currency": "USD",
                "fx_rate_to_thb": "35",
            }
        ],
    )
    client.queue_table("transactions", [])
    client.queue_table("transaction_drafts", [])
    client.queue_table("transaction_drafts", [])

    draft = SupabaseTransactionWorkflowRepository(client).create_reversal_draft(
        user_id=USER_ID,
        transaction_id=DRAFT_ID,
        transaction_at=datetime(2026, 1, 3, tzinfo=UTC),
        notes="wrong import",
    )

    original_query, reversal_query, existing_draft_query, insert_query = client.executed
    assert ("eq", "user_id", str(USER_ID)) in original_query.calls
    assert ("eq", "id", str(DRAFT_ID)) in original_query.calls
    assert ("eq", "reversal_of_transaction_id", str(DRAFT_ID)) in reversal_query.calls
    assert ("eq", "reversal_of_transaction_id", str(DRAFT_ID)) in existing_draft_query.calls
    assert draft["user_id"] == str(USER_ID)
    assert draft["transaction_type"] == "REVERSAL"
    assert draft["investment_account_id"] == "account-id"
    assert draft["asset_id"] == "asset-id"
    assert draft["reversal_of_transaction_id"] == str(DRAFT_ID)
    assert draft["quantity"] == "2"
    assert draft["unit_price"] == "10"
    assert draft["gross_amount"] == "20"
    assert draft["fee_amount"] == "1"
    assert draft["fee_unit"] == "QUOTE_CURRENCY"
    assert draft["currency"] == "USD"
    assert draft["fx_rate_to_thb"] == "35"
    assert draft["source_type"] == "MANUAL"
    assert draft["source_identifier"] == f"reversal:{DRAFT_ID}"
    assert draft["notes"] == "wrong import"
    assert ("insert", draft) in insert_query.calls


def test_create_reversal_draft_returns_existing_pending_draft():
    existing = {"id": "existing-draft", "transaction_type": "REVERSAL"}
    client = RecordingClient()
    client.queue_table(
        "transactions",
        [
            {
                "id": str(DRAFT_ID),
                "transaction_type": "BUY",
                "transaction_at": "2026-01-02T00:00:00+00:00",
                "investment_account_id": "account-id",
                "asset_id": "asset-id",
                "currency": "USD",
            }
        ],
    )
    client.queue_table("transactions", [])
    client.queue_table("transaction_drafts", [existing])

    draft = SupabaseTransactionWorkflowRepository(client).create_reversal_draft(
        user_id=USER_ID,
        transaction_id=DRAFT_ID,
    )

    assert draft == existing
    assert [query.table for query in client.executed] == [
        "transactions",
        "transactions",
        "transaction_drafts",
    ]


def test_create_reversal_draft_rejects_missing_or_already_reversed_transaction():
    client = RecordingClient()
    client.queue_table("transactions", [])

    with pytest.raises(TransactionNotFound):
        SupabaseTransactionWorkflowRepository(client).create_reversal_draft(
            user_id=USER_ID,
            transaction_id=DRAFT_ID,
        )

    client = RecordingClient()
    client.queue_table(
        "transactions",
        [
            {
                "id": "reversal-id",
                "transaction_type": "REVERSAL",
                "transaction_at": "2026-01-02T00:00:00+00:00",
            }
        ],
    )

    with pytest.raises(TransactionAlreadyReversed):
        SupabaseTransactionWorkflowRepository(client).create_reversal_draft(
            user_id=USER_ID,
            transaction_id=DRAFT_ID,
        )
