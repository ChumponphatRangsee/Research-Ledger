from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace

import pytest

from app.services.market_data import (
    CompanyFinancialSnapshot,
    InvalidProviderResponseError,
    SupabaseMarketDataSnapshotCache,
)
from app.services.market_data.cache import (
    CACHE_TABLE,
    COMPANY_SNAPSHOT_DATA_TYPE,
    LOOKUP_CONFLICT_COLUMNS,
)


class RecordingQuery:
    def __init__(self, data):
        self.data = data
        self.selected: str | None = None
        self.equal_filters: list[tuple[str, str]] = []
        self.greater_than_filters: list[tuple[str, str]] = []
        self.limit_count: int | None = None
        self.upsert_payload: dict | None = None
        self.on_conflict: str | None = None

    def select(self, columns: str):
        self.selected = columns
        return self

    def eq(self, column: str, value: str):
        self.equal_filters.append((column, value))
        return self

    def gt(self, column: str, value: str):
        self.greater_than_filters.append((column, value))
        return self

    def limit(self, count: int):
        self.limit_count = count
        return self

    def upsert(self, payload: dict, *, on_conflict: str):
        self.upsert_payload = payload
        self.on_conflict = on_conflict
        return self

    def execute(self):
        return SimpleNamespace(data=self.data)


class RecordingClient:
    def __init__(self, data=None):
        self.query = RecordingQuery([] if data is None else data)
        self.tables: list[str] = []

    def table(self, table: str):
        self.tables.append(table)
        return self.query


NOW = datetime(2026, 7, 24, 9, 30, tzinfo=timezone.utc)


def test_cache_builds_fresh_company_snapshot_lookup_query():
    payload = CompanyFinancialSnapshot(
        symbol="MSFT",
        current_price=None,
        data_as_of=NOW - timedelta(minutes=5),
    ).model_dump(mode="json")
    client = RecordingClient([{"payload": payload}])
    cache = SupabaseMarketDataSnapshotCache(client)

    snapshot = cache.get_fresh_company_snapshot(
        " msft ",
        "yfinance",
        now=NOW,
    )

    assert snapshot == CompanyFinancialSnapshot.model_validate(payload)
    assert snapshot.current_price is None
    assert client.tables == [CACHE_TABLE]
    assert client.query.selected == "payload"
    assert client.query.equal_filters == [
        ("symbol", "MSFT"),
        ("provider", "yfinance"),
        ("data_type", COMPANY_SNAPSHOT_DATA_TYPE),
    ]
    assert client.query.greater_than_filters == [
        ("expires_at", NOW.isoformat())
    ]
    assert client.query.limit_count == 1


def test_cache_returns_none_for_empty_result():
    cache = SupabaseMarketDataSnapshotCache(RecordingClient([]))

    assert (
        cache.get_fresh_company_snapshot("AAPL", "yfinance", now=NOW)
        is None
    )


@pytest.mark.parametrize(
    "row",
    [
        {"payload": "not-an-object"},
        {"payload": {"symbol": "AAPL", "market_cap": "invalid"}},
        {"payload": {"symbol": "MSFT"}},
    ],
)
def test_cache_rejects_malformed_company_snapshot_payload(row):
    cache = SupabaseMarketDataSnapshotCache(RecordingClient([row]))

    with pytest.raises(InvalidProviderResponseError) as caught:
        cache.get_fresh_company_snapshot("AAPL", "yfinance", now=NOW)

    assert caught.value.provider == "yfinance"
    assert caught.value.symbol == "AAPL"


def test_cache_upserts_by_unique_key_and_preserves_null_metrics():
    observed_at = NOW - timedelta(hours=1)
    snapshot = CompanyFinancialSnapshot(
        symbol="aapl",
        current_price=None,
        roe=None,
        data_as_of=observed_at,
    )
    client = RecordingClient()
    cache = SupabaseMarketDataSnapshotCache(client)

    cache.upsert_company_snapshot(
        snapshot,
        "yfinance",
        fetched_at=NOW,
        expires_at=NOW + timedelta(hours=24),
    )

    assert client.tables == [CACHE_TABLE]
    assert client.query.on_conflict == LOOKUP_CONFLICT_COLUMNS
    assert client.query.upsert_payload == {
        "symbol": "AAPL",
        "provider": "yfinance",
        "data_type": COMPANY_SNAPSHOT_DATA_TYPE,
        "payload": {
            **snapshot.model_copy(update={"symbol": "AAPL"}).model_dump(mode="json"),
        },
        "data_as_of": observed_at.isoformat(),
        "fetched_at": NOW.isoformat(),
        "expires_at": (NOW + timedelta(hours=24)).isoformat(),
    }
    assert client.query.upsert_payload["payload"]["current_price"] is None
    assert client.query.upsert_payload["payload"]["roe"] is None


def test_market_data_snapshot_migration_is_backend_only_and_indexed():
    migrations = Path(__file__).parents[2] / "supabase" / "migrations"
    migration = next(migrations.glob("*_market_data_snapshots.sql"))
    sql = migration.read_text(encoding="utf-8").lower()

    assert "unique (symbol, provider, data_type)" in sql
    assert "check (symbol = upper(symbol))" in sql
    assert "idx_market_data_snapshots_expires_at" in sql
    assert "enable row level security" in sql
    assert "revoke all on table public.market_data_snapshots from anon, authenticated" in sql
    assert "to service_role" in sql
