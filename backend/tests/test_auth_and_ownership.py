import os
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

os.environ["DEBUG"] = "false"

from app.agents import graph
from app.api.auth import AuthenticatedUser, require_user
from app.api.routes import analysis, portfolio, screener
from app.main import create_app
from app.services import screener as screener_service
from app.workers import tasks


USER_A = UUID("00000000-0000-0000-0000-00000000000a")
USER_B = UUID("00000000-0000-0000-0000-00000000000b")
INBOX_ID = UUID("11111111-1111-1111-1111-111111111111")
TICKER_ID = UUID("22222222-2222-2222-2222-222222222222")
RUN_ID = UUID("33333333-3333-3333-3333-333333333333")


class FakeQuery:
    def __init__(self, data=None):
        self.data = data if data is not None else []
        self.calls = []
        self.update_payload = None
        self.insert_payload = None
        self.upsert_payload = None

    def select(self, value):
        self.calls.append(("select", value))
        return self

    def eq(self, field, value):
        self.calls.append(("eq", field, value))
        return self

    def or_(self, value):
        self.calls.append(("or", value))
        return self

    def order(self, field, desc=False):
        self.calls.append(("order", field, desc))
        return self

    def limit(self, value):
        self.calls.append(("limit", value))
        return self

    def gte(self, field, value):
        self.calls.append(("gte", field, value))
        return self

    def single(self):
        self.calls.append(("single",))
        return self

    def update(self, payload):
        self.calls.append(("update", payload))
        self.update_payload = payload
        return self

    def insert(self, payload):
        self.calls.append(("insert", payload))
        self.insert_payload = payload
        return self

    def upsert(self, payload, on_conflict=None):
        self.calls.append(("upsert", payload, on_conflict))
        self.upsert_payload = payload
        return self

    def execute(self):
        return SimpleNamespace(data=self.data)


class FakeSupabaseClient:
    def __init__(self, queries):
        self.queries = list(queries)
        self.tables = []

    def table(self, name):
        self.tables.append(name)
        return self.queries.pop(0)


class FakeTaskResult:
    id = "task-123"


class FakeCeleryTask:
    def __init__(self):
        self.delay_calls = []

    def delay(self, *args):
        self.delay_calls.append(args)
        return FakeTaskResult()


def make_client(user_id=USER_A):
    app = create_app()

    async def fake_require_user():
        return AuthenticatedUser(id=user_id, role="authenticated", claims={"sub": str(user_id)})

    app.dependency_overrides[require_user] = fake_require_user
    return TestClient(app), app


def test_missing_bearer_token_is_unauthorized():
    client = TestClient(create_app())

    response = client.get("/api/analysis/inbox")

    assert response.status_code == 401


def test_invalid_bearer_token_is_unauthorized():
    client = TestClient(create_app())

    response = client.get("/api/analysis/inbox", headers={"Authorization": "Bearer not-a-jwt"})

    assert response.status_code == 401


def test_unauthenticated_users_cannot_run_screener_endpoints():
    client = TestClient(create_app())

    run_response = client.post("/api/screener/run")
    pipeline_response = client.post("/api/screener/pipeline", json={"ticker_symbol": "AAPL"})

    assert run_response.status_code == 401
    assert pipeline_response.status_code == 401


def test_screener_routes_use_jwt_user_instead_of_request_data(monkeypatch):
    run_task = FakeCeleryTask()
    pipeline_task = FakeCeleryTask()
    screening_run_query = FakeQuery(data=[{"id": str(RUN_ID), "user_id": str(USER_A)}])
    fake_supabase = FakeSupabaseClient([screening_run_query])
    monkeypatch.setattr(screener, "run_daily_screener", run_task)
    monkeypatch.setattr(screener, "trigger_analysis_pipeline", pipeline_task)
    monkeypatch.setattr(screener, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    run_response = client.post("/api/screener/run", json={"user_id": str(USER_B)})
    pipeline_response = client.post(
        "/api/screener/pipeline",
        json={
            "ticker_symbol": "MSFT",
            "screening_run_id": str(RUN_ID),
            "user_id": str(USER_B),
        },
    )

    assert run_response.status_code == 200
    assert pipeline_response.status_code == 200
    assert run_task.delay_calls == [(str(USER_A),)]
    assert pipeline_task.delay_calls == [("MSFT", str(USER_A), str(RUN_ID))]
    assert ("eq", "user_id", str(USER_A)) in screening_run_query.calls
    app.dependency_overrides.clear()


def test_pipeline_route_rejects_another_users_screening_run(monkeypatch):
    pipeline_task = FakeCeleryTask()
    screening_run_query = FakeQuery(data=[])
    fake_supabase = FakeSupabaseClient([screening_run_query])
    monkeypatch.setattr(screener, "trigger_analysis_pipeline", pipeline_task)
    monkeypatch.setattr(screener, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.post(
        "/api/screener/pipeline",
        json={"ticker_symbol": "MSFT", "screening_run_id": str(RUN_ID)},
    )

    assert response.status_code == 404
    assert pipeline_task.delay_calls == []
    assert ("eq", "id", str(RUN_ID)) in screening_run_query.calls
    assert ("eq", "user_id", str(USER_A)) in screening_run_query.calls
    app.dependency_overrides.clear()


def test_screening_results_are_owner_scoped_and_filterable(monkeypatch):
    owner_query = FakeQuery(data=[{"id": str(RUN_ID), "user_id": str(USER_A)}])
    results_query = FakeQuery(
        data=[
            {
                "id": "result-1",
                "screening_run_id": str(RUN_ID),
                "passed": True,
                "business_model": "software",
                "total_score": 88,
            }
        ]
    )
    fake_supabase = FakeSupabaseClient([owner_query, results_query])
    monkeypatch.setattr(screener, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.get(
        f"/api/screener/runs/{RUN_ID}/results"
        "?passed=true&business_model=software&min_score=70&limit=20"
    )

    assert response.status_code == 200
    assert ("eq", "user_id", str(USER_A)) in owner_query.calls
    assert ("eq", "screening_run_id", str(RUN_ID)) in results_query.calls
    assert ("eq", "passed", True) in results_query.calls
    assert ("eq", "business_model", "software") in results_query.calls
    assert ("gte", "total_score", 70.0) in results_query.calls
    assert ("order", "total_score", True) in results_query.calls
    app.dependency_overrides.clear()


def test_list_inbox_filters_to_current_user_only(monkeypatch):
    query = FakeQuery(data=[{"id": str(INBOX_ID), "user_id": str(USER_A)}])
    fake_supabase = FakeSupabaseClient([query])
    monkeypatch.setattr(analysis, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.get("/api/analysis/inbox")

    assert response.status_code == 200
    assert ("eq", "user_id", str(USER_A)) in query.calls
    assert not any(call[0] == "or" for call in query.calls)
    app.dependency_overrides.clear()


def test_user_cannot_view_another_users_analysis(monkeypatch):
    query = FakeQuery(data=[])
    fake_supabase = FakeSupabaseClient([query])
    monkeypatch.setattr(analysis, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.get(f"/api/analysis/inbox/{INBOX_ID}")

    assert response.status_code == 404
    assert ("eq", "id", str(INBOX_ID)) in query.calls
    assert ("eq", "user_id", str(USER_A)) in query.calls
    app.dependency_overrides.clear()


def test_null_owned_analysis_is_inaccessible(monkeypatch):
    query = FakeQuery(data=[])
    fake_supabase = FakeSupabaseClient([query])
    monkeypatch.setattr(analysis, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.get(f"/api/analysis/inbox/{INBOX_ID}")

    assert response.status_code == 404
    assert ("eq", "user_id", str(USER_A)) in query.calls
    app.dependency_overrides.clear()


def test_only_pending_review_analysis_can_be_approved(monkeypatch):
    query = FakeQuery(data=[{"id": str(INBOX_ID), "user_id": str(USER_A), "status": "approved"}])
    fake_supabase = FakeSupabaseClient([query])
    monkeypatch.setattr(analysis, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.post(
        f"/api/analysis/inbox/{INBOX_ID}/approve",
        json={"user_id": str(USER_B)},
    )

    assert response.status_code == 200
    assert query.update_payload["status"] == "approved"
    assert "user_id" not in query.update_payload
    assert "reviewed_at" in query.update_payload
    assert ("eq", "user_id", str(USER_A)) in query.calls
    assert ("eq", "status", "pending_review") in query.calls
    app.dependency_overrides.clear()


def test_non_pending_or_inaccessible_analysis_cannot_be_approved(monkeypatch):
    query = FakeQuery(data=[])
    fake_supabase = FakeSupabaseClient([query])
    monkeypatch.setattr(analysis, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.post(f"/api/analysis/inbox/{INBOX_ID}/approve")

    assert response.status_code == 404
    assert query.update_payload["status"] == "approved"
    assert ("eq", "user_id", str(USER_A)) in query.calls
    assert ("eq", "status", "pending_review") in query.calls
    app.dependency_overrides.clear()


def test_non_pending_or_inaccessible_analysis_cannot_be_discarded(monkeypatch):
    query = FakeQuery(data=[])
    fake_supabase = FakeSupabaseClient([query])
    monkeypatch.setattr(analysis, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.post(f"/api/analysis/inbox/{INBOX_ID}/discard")

    assert response.status_code == 404
    assert query.update_payload["status"] == "discarded"
    assert "user_id" not in query.update_payload
    assert ("eq", "user_id", str(USER_A)) in query.calls
    assert ("eq", "status", "pending_review") in query.calls
    app.dependency_overrides.clear()


def test_user_cannot_execute_another_users_analysis(monkeypatch):
    inbox_query = FakeQuery(data=[])
    fake_supabase = FakeSupabaseClient([inbox_query])
    monkeypatch.setattr(portfolio, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.post(f"/api/portfolio/execute/{INBOX_ID}", json={"shares": 1})

    assert response.status_code == 404
    assert ("eq", "id", str(INBOX_ID)) in inbox_query.calls
    assert ("eq", "user_id", str(USER_A)) in inbox_query.calls
    assert fake_supabase.tables == ["analysis_inbox"]
    app.dependency_overrides.clear()


def test_only_approved_user_owned_analysis_can_enter_portfolio(monkeypatch):
    inbox_query = FakeQuery(
        data=[
            {
                "id": str(INBOX_ID),
                "ticker_id": str(TICKER_ID),
                "status": "pending_review",
                "user_id": str(USER_A),
            }
        ]
    )
    fake_supabase = FakeSupabaseClient([inbox_query])
    monkeypatch.setattr(portfolio, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.post(f"/api/portfolio/execute/{INBOX_ID}", json={"shares": 1})

    assert response.status_code == 400
    app.dependency_overrides.clear()


def test_execute_inserts_current_user_and_rejects_spoofed_user_id(monkeypatch):
    inbox_query = FakeQuery(
        data=[
            {
                "id": str(INBOX_ID),
                "ticker_id": str(TICKER_ID),
                "status": "approved",
                "user_id": str(USER_A),
            }
        ]
    )
    duplicate_check_query = FakeQuery(data=[])
    insert_query = FakeQuery(data=[{"id": "holding-1", "user_id": str(USER_A)}])
    fake_supabase = FakeSupabaseClient([inbox_query, duplicate_check_query, insert_query])
    monkeypatch.setattr(portfolio, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.post(
        f"/api/portfolio/execute/{INBOX_ID}",
        json={"shares": 2, "cost_basis": 100, "notes": "starter position"},
    )

    assert response.status_code == 200
    assert insert_query.insert_payload["user_id"] == str(USER_A)

    spoof_response = client.post(
        f"/api/portfolio/execute/{INBOX_ID}",
        json={"user_id": str(USER_B), "shares": 2},
    )

    assert spoof_response.status_code == 422
    app.dependency_overrides.clear()


def test_repeated_portfolio_execution_does_not_create_duplicate(monkeypatch):
    inbox_query = FakeQuery(
        data=[
            {
                "id": str(INBOX_ID),
                "ticker_id": str(TICKER_ID),
                "status": "approved",
                "user_id": str(USER_A),
            }
        ]
    )
    duplicate_check_query = FakeQuery(data=[{"id": "existing-holding"}])
    fake_supabase = FakeSupabaseClient([inbox_query, duplicate_check_query])
    monkeypatch.setattr(portfolio, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.post(f"/api/portfolio/execute/{INBOX_ID}", json={"shares": 1})

    assert response.status_code == 409
    assert fake_supabase.tables == ["analysis_inbox", "portfolios"]
    app.dependency_overrides.clear()


def test_portfolio_list_filters_to_current_user(monkeypatch):
    query = FakeQuery(data=[{"id": "holding-1", "user_id": str(USER_A)}])
    fake_supabase = FakeSupabaseClient([query])
    monkeypatch.setattr(portfolio, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.get(f"/api/portfolio/?user_id={USER_B}")

    assert response.status_code == 200
    assert ("eq", "user_id", str(USER_A)) in query.calls
    assert ("eq", "user_id", str(USER_B)) not in query.calls
    app.dependency_overrides.clear()


def test_portfolio_ledger_summary_uses_current_user(monkeypatch):
    calls = []

    class FakeSnapshot:
        @staticmethod
        def to_report():
            return {"positions": [], "total_cost_basis_thb": "0"}

    class FakeLedgerRepository:
        def build_snapshot(self, *, user_id):
            calls.append(user_id)
            return FakeSnapshot()

    monkeypatch.setattr(
        portfolio,
        "SupabasePortfolioLedgerRepository",
        lambda: FakeLedgerRepository(),
    )
    client, app = make_client(USER_A)

    response = client.get(f"/api/portfolio/ledger/summary?user_id={USER_B}")

    assert response.status_code == 200
    assert response.json()["positions"] == []
    assert calls == [USER_A]
    app.dependency_overrides.clear()


def test_transaction_draft_list_uses_current_user(monkeypatch):
    calls = []

    class FakeWorkflowRepository:
        def list_drafts(self, *, user_id, status, import_batch_id):
            calls.append((user_id, status, import_batch_id))
            return [{"id": str(INBOX_ID), "status": "pending"}]

    monkeypatch.setattr(
        portfolio,
        "SupabaseTransactionWorkflowRepository",
        lambda: FakeWorkflowRepository(),
    )
    client, app = make_client(USER_A)

    response = client.get(f"/api/portfolio/transaction-drafts?user_id={USER_B}")

    assert response.status_code == 200
    assert response.json()["count"] == 1
    assert calls == [(USER_A, "pending", None)]
    app.dependency_overrides.clear()


def test_transaction_draft_confirm_uses_current_user(monkeypatch):
    calls = []

    class FakeWorkflowRepository:
        def confirm_draft(self, *, user_id, draft_id):
            calls.append((user_id, draft_id))
            return {"id": "transaction-id"}

    monkeypatch.setattr(
        portfolio,
        "SupabaseTransactionWorkflowRepository",
        lambda: FakeWorkflowRepository(),
    )
    client, app = make_client(USER_A)

    response = client.post(
        f"/api/portfolio/transaction-drafts/{INBOX_ID}/confirm?user_id={USER_B}"
    )

    assert response.status_code == 200
    assert response.json()["transaction"]["id"] == "transaction-id"
    assert calls == [(USER_A, INBOX_ID)]
    app.dependency_overrides.clear()


def test_transaction_draft_confirm_hides_other_users_drafts(monkeypatch):
    class FakeWorkflowRepository:
        def confirm_draft(self, *, user_id, draft_id):
            raise portfolio.TransactionDraftNotFound

    monkeypatch.setattr(
        portfolio,
        "SupabaseTransactionWorkflowRepository",
        lambda: FakeWorkflowRepository(),
    )
    client, app = make_client(USER_A)

    response = client.post(f"/api/portfolio/transaction-drafts/{INBOX_ID}/confirm")

    assert response.status_code == 404
    app.dependency_overrides.clear()


def test_screener_task_passes_authenticated_user_to_pipeline(monkeypatch):
    delayed_pipeline_calls = []
    triggered_count_calls = []

    class FakePipelineTask:
        @staticmethod
        def delay(*args):
            delayed_pipeline_calls.append(args)

    monkeypatch.setattr(
        tasks,
        "run_quantitative_screen",
        lambda user_id: {
            "run_id": str(RUN_ID),
            "candidates": [{"symbol": "AAPL"}],
            "count": 1,
            "selected_for_ai": 1,
        },
    )
    monkeypatch.setattr(tasks, "trigger_analysis_pipeline", FakePipelineTask)
    monkeypatch.setattr(
        tasks,
        "record_triggered_count",
        lambda *args: triggered_count_calls.append(args),
    )

    result = tasks.run_daily_screener.run(str(USER_A))

    assert result["pipelines_triggered"] == 1
    assert delayed_pipeline_calls == [("AAPL", str(USER_A), str(RUN_ID))]
    assert triggered_count_calls == [(str(USER_A), str(RUN_ID), 1)]


def test_screener_task_records_only_successfully_queued_pipelines(monkeypatch):
    triggered_count_calls = []

    class PartiallyFailingPipelineTask:
        @staticmethod
        def delay(symbol, *_args):
            if symbol == "FAIL":
                raise RuntimeError("broker rejected task")

    monkeypatch.setattr(
        tasks,
        "run_quantitative_screen",
        lambda user_id: {
            "run_id": str(RUN_ID),
            "candidates": [{"symbol": "AAPL"}, {"symbol": "FAIL"}],
            "count": 2,
            "selected_for_ai": 2,
        },
    )
    monkeypatch.setattr(
        tasks,
        "trigger_analysis_pipeline",
        PartiallyFailingPipelineTask,
    )
    monkeypatch.setattr(
        tasks,
        "record_triggered_count",
        lambda *args: triggered_count_calls.append(args),
    )

    result = tasks.run_daily_screener.run(str(USER_A))

    assert result["pipelines_triggered"] == 1
    assert result["pipeline_queue_failures"] == 1
    assert triggered_count_calls == [(str(USER_A), str(RUN_ID), 1)]


def test_quantitative_screen_persists_screening_run_owner(monkeypatch):
    insert_run_query = FakeQuery(data=[{"id": str(RUN_ID)}])
    update_run_query = FakeQuery(data=[{"id": str(RUN_ID)}])
    fake_supabase = FakeSupabaseClient([insert_run_query, update_run_query])
    monkeypatch.setattr(screener_service, "get_supabase_client", lambda: fake_supabase)

    result = screener_service.run_quantitative_screen(
        str(USER_A),
        universe=[],
        market_data_service=SimpleNamespace(),
    )

    assert result["run_id"] == str(RUN_ID)
    assert insert_run_query.insert_payload["user_id"] == str(USER_A)
    assert insert_run_query.insert_payload["status"] == "running"
    assert ("eq", "id", str(RUN_ID)) in update_run_query.calls
    assert ("eq", "user_id", str(USER_A)) in update_run_query.calls


def test_record_triggered_count_is_run_and_user_scoped(monkeypatch):
    update_query = FakeQuery(data=[{"id": str(RUN_ID), "triggered_count": 7}])
    fake_supabase = FakeSupabaseClient([update_query])
    monkeypatch.setattr(
        screener_service,
        "get_supabase_client",
        lambda: fake_supabase,
    )

    screener_service.record_triggered_count(str(USER_A), str(RUN_ID), 7)

    assert update_query.update_payload == {"triggered_count": 7}
    assert ("eq", "id", str(RUN_ID)) in update_query.calls
    assert ("eq", "user_id", str(USER_A)) in update_query.calls


def test_pipeline_task_passes_ownership_into_langgraph(monkeypatch):
    calls = []

    def fake_run_pipeline(ticker_symbol, user_id, screening_run_id=None):
        calls.append((ticker_symbol, user_id, screening_run_id))
        return {"ticker_symbol": ticker_symbol, "user_id": user_id, "screening_run_id": screening_run_id}

    monkeypatch.setattr(tasks, "run_pipeline", fake_run_pipeline)

    result = tasks.trigger_analysis_pipeline.run("AAPL", str(USER_A), str(RUN_ID))

    assert result["user_id"] == str(USER_A)
    assert calls == [("AAPL", str(USER_A), str(RUN_ID))]


def test_langgraph_invocation_includes_user_id(monkeypatch):
    invoked_states = []

    class FakeResearchGraph:
        @staticmethod
        def invoke(state):
            invoked_states.append(state)
            return {**state, "inbox_id": str(INBOX_ID)}

    monkeypatch.setattr(graph, "research_graph", FakeResearchGraph)

    result = graph.run_pipeline("AAPL", str(USER_A), str(RUN_ID))

    assert result["user_id"] == str(USER_A)
    assert invoked_states[0]["user_id"] == str(USER_A)


def test_langgraph_persists_correct_user_id(monkeypatch):
    ticker_query = FakeQuery(data={"id": str(TICKER_ID)})
    inbox_query = FakeQuery(data=[{"id": str(INBOX_ID)}])
    fake_supabase = FakeSupabaseClient([ticker_query, inbox_query])
    monkeypatch.setattr(graph, "get_supabase_client", lambda: fake_supabase)

    result = graph._save_to_inbox(
        {
            "ticker_symbol": "AAPL",
            "user_id": str(USER_A),
            "screening_run_id": str(RUN_ID),
            "financial_metrics": {"current_price": 150},
            "recommendation": "BUY",
        }
    )

    assert result["inbox_id"] == str(INBOX_ID)
    assert inbox_query.insert_payload["user_id"] == str(USER_A)
    assert inbox_query.insert_payload["status"] == "pending_review"
