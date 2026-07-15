"""Quantitative stock screener using yfinance."""

from datetime import datetime, timezone

from typing import Any

from app.config import get_settings
from app.db.supabase import get_supabase_client
from app.services.yfinance_client import fetch_financial_metrics

# Starter universe — replace with index constituents or custom list
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "BRK-B", "JPM",
    "V", "UNH", "XOM", "JNJ", "WMT", "PG", "MA", "HD", "CVX", "MRK",
    "ABBV", "KO", "PEP", "COST", "AVGO", "TMO", "MCD", "CSCO", "ACN",
    "LIN", "ABT", "DHR", "TXN", "NEE", "PM", "UNP", "RTX", "HON", "LOW",
    "UPS", "ORCL", "IBM", "AMAT", "INTC", "QCOM", "AMD", "CRM", "NFLX",
]


def passes_criteria(metrics: dict[str, Any], criteria: dict[str, Any]) -> bool:
    market_cap = metrics.get("market_cap") or 0
    pe = metrics.get("pe_ratio")
    roe = metrics.get("roe") or 0

    if market_cap < criteria.get("min_market_cap", 0):
        return False
    if pe is None or pe <= 0 or pe > criteria.get("max_pe", 999):
        return False
    if roe < criteria.get("min_roe", 0):
        return False
    return True


def run_quantitative_screen(universe: list[str] | None = None) -> dict[str, Any]:
    settings = get_settings()
    client = get_supabase_client()

    criteria = {
        "min_market_cap": settings.screener_min_market_cap,
        "max_pe": settings.screener_max_pe,
        "min_roe": settings.screener_min_roe,
    }

    run = client.table("screening_runs").insert({"criteria": criteria, "status": "running"}).execute()
    run_id = run.data[0]["id"] if run.data else None

    symbols = universe or DEFAULT_UNIVERSE
    candidates: list[dict[str, Any]] = []

    for symbol in symbols:
        try:
            metrics = fetch_financial_metrics(symbol)
            if passes_criteria(metrics, criteria):
                candidates.append(metrics)
                client.table("tickers").upsert(
                    {
                        "symbol": symbol,
                        "name": metrics.get("name"),
                        "sector": metrics.get("sector"),
                        "industry": metrics.get("industry"),
                        "market_cap": metrics.get("market_cap"),
                        "last_screened_at": datetime.now(timezone.utc).isoformat(),
                    },
                    on_conflict="symbol",
                ).execute()
        except Exception:
            continue

    if run_id:
        client.table("screening_runs").update(
            {
                "status": "completed",
                "candidates_count": len(candidates),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        ).eq("id", run_id).execute()

    return {"run_id": run_id, "candidates": candidates, "count": len(candidates)}
