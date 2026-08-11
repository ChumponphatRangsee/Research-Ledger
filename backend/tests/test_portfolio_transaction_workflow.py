from __future__ import annotations

from types import SimpleNamespace
from uuid import UUID

import pytest

from app.services.portfolio_workflow import (
    SupabaseTransactionWorkflowRepository,
    TransactionDraftNotFound,
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
