"""Supabase-backed cache for normalized company financial snapshots."""

from datetime import datetime, timezone
from typing import Protocol

from pydantic import ValidationError
from supabase import Client

from app.db.supabase import get_supabase_client
from app.services.market_data.exceptions import InvalidProviderResponseError
from app.services.market_data.models import CompanyFinancialSnapshot

CACHE_TABLE = "market_data_snapshots"
COMPANY_SNAPSHOT_DATA_TYPE = "company_snapshot"
LOOKUP_CONFLICT_COLUMNS = "symbol,provider,data_type"


class CompanySnapshotCache(Protocol):
    """Cache operations required by ``MarketDataService``."""

    def get_fresh_company_snapshot(
        self,
        symbol: str,
        provider: str,
        *,
        now: datetime,
    ) -> CompanyFinancialSnapshot | None:
        """Return a fresh cached snapshot, or ``None`` on a cache miss."""

        ...

    def upsert_company_snapshot(
        self,
        snapshot: CompanyFinancialSnapshot,
        provider: str,
        *,
        fetched_at: datetime,
        expires_at: datetime,
    ) -> None:
        """Store a normalized company snapshot and its freshness window."""

        ...


class SupabaseMarketDataSnapshotCache:
    """Persist normalized company snapshots through the backend Supabase client."""

    def __init__(self, client: Client | None = None) -> None:
        self._client = client if client is not None else get_supabase_client()

    def get_fresh_company_snapshot(
        self,
        symbol: str,
        provider: str,
        *,
        now: datetime | None = None,
    ) -> CompanyFinancialSnapshot | None:
        """Return a cache row whose expiry is later than ``now``."""
        normalized_symbol = symbol.strip().upper()
        cutoff = now if now is not None else datetime.now(timezone.utc)
        response = (
            self._client.table(CACHE_TABLE)
            .select("payload")
            .eq("symbol", normalized_symbol)
            .eq("provider", provider)
            .eq("data_type", COMPANY_SNAPSHOT_DATA_TYPE)
            .gt("expires_at", cutoff.isoformat())
            .limit(1)
            .execute()
        )

        if not response.data:
            return None
        if not isinstance(response.data, list) or not isinstance(
            response.data[0],
            dict,
        ):
            raise InvalidProviderResponseError(
                "Market data cache returned an invalid row",
                provider=provider,
                symbol=normalized_symbol,
            )

        payload = response.data[0].get("payload")
        if not isinstance(payload, dict):
            raise InvalidProviderResponseError(
                "Market data cache returned an invalid company snapshot payload",
                provider=provider,
                symbol=normalized_symbol,
            )

        try:
            snapshot = CompanyFinancialSnapshot.model_validate(payload)
        except ValidationError as exc:
            raise InvalidProviderResponseError(
                "Market data cache returned an invalid company snapshot payload",
                provider=provider,
                symbol=normalized_symbol,
            ) from exc
        if snapshot.symbol.strip().upper() != normalized_symbol:
            raise InvalidProviderResponseError(
                "Market data cache returned a snapshot for a different symbol",
                provider=provider,
                symbol=normalized_symbol,
            )
        if snapshot.symbol != normalized_symbol:
            snapshot = snapshot.model_copy(update={"symbol": normalized_symbol})
        return snapshot

    def upsert_company_snapshot(
        self,
        snapshot: CompanyFinancialSnapshot,
        provider: str,
        *,
        fetched_at: datetime,
        expires_at: datetime,
    ) -> None:
        """Upsert by the table's symbol/provider/data-type cache key."""
        normalized_symbol = snapshot.symbol.strip().upper()
        normalized_snapshot = (
            snapshot
            if snapshot.symbol == normalized_symbol
            else snapshot.model_copy(update={"symbol": normalized_symbol})
        )
        payload = {
            "symbol": normalized_symbol,
            "provider": provider,
            "data_type": COMPANY_SNAPSHOT_DATA_TYPE,
            "payload": normalized_snapshot.model_dump(mode="json"),
            "data_as_of": (
                normalized_snapshot.data_as_of.isoformat()
                if normalized_snapshot.data_as_of is not None
                else None
            ),
            "fetched_at": fetched_at.isoformat(),
            "expires_at": expires_at.isoformat(),
        }
        (
            self._client.table(CACHE_TABLE)
            .upsert(payload, on_conflict=LOOKUP_CONFLICT_COLUMNS)
            .execute()
        )
