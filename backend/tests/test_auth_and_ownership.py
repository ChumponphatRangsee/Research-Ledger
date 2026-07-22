import os
from types import SimpleNamespace
from uuid import UUID

from fastapi.testclient import TestClient

os.environ["DEBUG"] = "false"

from app.api.auth import AuthenticatedUser, require_user
from app.api.routes import analysis, portfolio
from app.main import create_app


USER_A = UUID("00000000-0000-0000-0000-00000000000a")
USER_B = UUID("00000000-0000-0000-0000-00000000000b")
INBOX_ID = UUID("11111111-1111-1111-1111-111111111111")
TICKER_ID = UUID("22222222-2222-2222-2222-222222222222")


class FakeQuery:
    def __init__(self, data=None):
        self.data = data if data is not None else []
        self.calls = []
        self.update_payload = None
        self.insert_payload = None

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

    def update(self, payload):
        self.calls.append(("update", payload))
        self.update_payload = payload
        return self

    def insert(self, payload):
        self.calls.append(("insert", payload))
        self.insert_payload = payload
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


def test_list_inbox_filters_to_current_user_or_unassigned(monkeypatch):
    query = FakeQuery(data=[{"id": str(INBOX_ID), "user_id": None}])
    fake_supabase = FakeSupabaseClient([query])
    monkeypatch.setattr(analysis, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.get("/api/analysis/inbox")

    assert response.status_code == 200
    assert ("or", f"user_id.is.null,user_id.eq.{USER_A}") in query.calls
    app.dependency_overrides.clear()


def test_get_inbox_item_uses_owner_filter(monkeypatch):
    query = FakeQuery(data=[{"id": str(INBOX_ID), "user_id": str(USER_A)}])
    fake_supabase = FakeSupabaseClient([query])
    monkeypatch.setattr(analysis, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.get(f"/api/analysis/inbox/{INBOX_ID}")

    assert response.status_code == 200
    assert ("eq", "id", str(INBOX_ID)) in query.calls
    assert ("or", f"user_id.is.null,user_id.eq.{USER_A}") in query.calls
    app.dependency_overrides.clear()


def test_user_cannot_fetch_another_users_analysis(monkeypatch):
    query = FakeQuery(data=[])
    fake_supabase = FakeSupabaseClient([query])
    monkeypatch.setattr(analysis, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.get(f"/api/analysis/inbox/{INBOX_ID}")

    assert response.status_code == 404
    assert ("or", f"user_id.is.null,user_id.eq.{USER_A}") in query.calls
    app.dependency_overrides.clear()


def test_approve_unassigned_analysis_claims_current_user(monkeypatch):
    query = FakeQuery(data=[{"id": str(INBOX_ID), "user_id": str(USER_A), "status": "approved"}])
    fake_supabase = FakeSupabaseClient([query])
    monkeypatch.setattr(analysis, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.post(
        f"/api/analysis/inbox/{INBOX_ID}/approve",
        json={"user_id": str(USER_B)},
    )

    assert response.status_code == 200
    assert query.update_payload["user_id"] == str(USER_A)
    assert query.update_payload["status"] == "approved"
    assert "reviewed_at" in query.update_payload
    assert ("or", f"user_id.is.null,user_id.eq.{USER_A}") in query.calls
    app.dependency_overrides.clear()


def test_user_cannot_discard_another_users_claimed_analysis(monkeypatch):
    query = FakeQuery(data=[])
    fake_supabase = FakeSupabaseClient([query])
    monkeypatch.setattr(analysis, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_B)

    response = client.post(f"/api/analysis/inbox/{INBOX_ID}/discard")

    assert response.status_code == 404
    assert query.update_payload["user_id"] == str(USER_B)
    assert ("or", f"user_id.is.null,user_id.eq.{USER_B}") in query.calls
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


def test_execute_rejects_another_users_analysis(monkeypatch):
    inbox_query = FakeQuery(
        data=[
            {
                "id": str(INBOX_ID),
                "ticker_id": str(TICKER_ID),
                "status": "approved",
                "user_id": str(USER_B),
            }
        ]
    )
    fake_supabase = FakeSupabaseClient([inbox_query])
    monkeypatch.setattr(portfolio, "get_supabase_client", lambda: fake_supabase)
    client, app = make_client(USER_A)

    response = client.post(f"/api/portfolio/execute/{INBOX_ID}", json={"shares": 1})

    assert response.status_code == 404
    assert fake_supabase.tables == ["analysis_inbox"]
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
    insert_query = FakeQuery(data=[{"id": "holding-1", "user_id": str(USER_A)}])
    fake_supabase = FakeSupabaseClient([inbox_query, insert_query])
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
