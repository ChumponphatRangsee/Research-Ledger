"""Persistence and orchestration for sector-aware quantitative screening."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any

from app.config import get_settings
from app.db.supabase import get_supabase_client
from app.services.market_data.service import MarketDataService
from app.services.screening import BusinessModel, ScreeningEngine, ScreeningResult

logger = logging.getLogger(__name__)

# Starter universe — replace with index constituents or a user-defined universe.
DEFAULT_UNIVERSE = [
    "AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "BRK-B", "JPM",
    "V", "UNH", "XOM", "JNJ", "WMT", "PG", "MA", "HD", "CVX", "MRK",
    "ABBV", "KO", "PEP", "COST", "AVGO", "TMO", "MCD", "CSCO", "ACN",
    "LIN", "ABT", "DHR", "TXN", "NEE", "PM", "UNP", "RTX", "HON", "LOW",
    "UPS", "ORCL", "IBM", "AMAT", "INTC", "QCOM", "AMD", "CRM", "NFLX",
]


def _upsert_ticker(client: Any, result: ScreeningResult) -> str:
    payload = {
        "symbol": result.symbol,
        "last_screened_at": datetime.now(timezone.utc).isoformat(),
    }
    optional_values = {
        "name": result.name,
        "sector": result.sector,
        "industry": result.industry,
        "market_cap": result.metrics.get("market_cap"),
    }
    payload.update({key: value for key, value in optional_values.items() if value is not None})
    response = client.table("tickers").upsert(payload, on_conflict="symbol").execute()
    if response.data:
        row = response.data[0] if isinstance(response.data, list) else response.data
        if row.get("id"):
            return row["id"]

    lookup = (
        client.table("tickers")
        .select("id")
        .eq("symbol", result.symbol)
        .single()
        .execute()
    )
    if not lookup.data:
        raise RuntimeError(f"Ticker upsert did not return an id for {result.symbol}")
    return lookup.data["id"]


def _generic_category(result: ScreeningResult, name: str) -> float | None:
    return result.category_scores.get(name)


def _persist_result(
    client: Any,
    run_id: str,
    ticker_id: str,
    result: ScreeningResult,
    error: Exception | None = None,
) -> None:
    breakdown: dict[str, Any] = {
        key: value.model_dump(mode="json")
        for key, value in result.score_breakdown.items()
    }
    if error is not None:
        breakdown["error"] = {
            "type": type(error).__name__,
            "message": str(error),
        }

    client.table("screening_results").insert(
        {
            "screening_run_id": run_id,
            "ticker_id": ticker_id,
            "business_model": result.business_model.value,
            "passed": result.passed,
            "total_score": result.score,
            "confidence_score": result.confidence,
            "quality_score": _generic_category(result, "quality"),
            "growth_score": _generic_category(result, "growth"),
            "financial_strength_score": _generic_category(result, "financial_strength"),
            "valuation_score": _generic_category(result, "valuation"),
            "sector_specific_score": _generic_category(result, "sector_specific"),
            "metrics": result.metrics,
            "score_breakdown": breakdown,
            "strengths": result.strengths,
            "warnings": result.warnings,
            "failure_reasons": result.failure_reasons,
            "data_as_of": (
                result.data_as_of.isoformat() if result.data_as_of is not None else None
            ),
        }
    ).execute()


def _provider_failure(symbol: str, exc: Exception) -> ScreeningResult:
    return ScreeningResult(
        symbol=symbol,
        business_model=BusinessModel.UNSUPPORTED,
        passed=False,
        confidence=0.0,
        metrics={"symbol": symbol},
        warnings=[f"Provider error: {type(exc).__name__}"],
        failure_reasons=[f"Financial data retrieval failed: {exc}"],
        data_as_of=datetime.now(timezone.utc),
    )


def record_triggered_count(user_id: str, run_id: str, count: int) -> None:
    """Record how many selected candidates were successfully queued by Celery."""
    (
        get_supabase_client()
        .table("screening_runs")
        .update({"triggered_count": count})
        .eq("id", run_id)
        .eq("user_id", user_id)
        .execute()
    )


def run_quantitative_screen(
    user_id: str,
    universe: list[str] | None = None,
    top_n_candidates: int | None = None,
    market_data_service: MarketDataService | None = None,
) -> dict[str, Any]:
    """Run, persist, rank, and return only the top AI research candidates."""
    settings = get_settings()
    client = get_supabase_client()
    data_service = (
        market_data_service
        if market_data_service is not None
        else MarketDataService()
    )
    symbols = list(DEFAULT_UNIVERSE if universe is None else universe)
    top_n = (
        settings.screener_top_n_candidates
        if top_n_candidates is None
        else max(0, top_n_candidates)
    )
    criteria = {
        "min_market_cap": settings.screener_min_market_cap,
        "min_score": settings.screener_min_score,
        "min_confidence": settings.screener_min_confidence,
        "top_n_candidates": top_n,
        "strategy_version": 1,
    }

    run = (
        client.table("screening_runs")
        .insert(
            {
                "user_id": user_id,
                "criteria": criteria,
                "status": "running",
                "requested_count": len(symbols),
            }
        )
        .execute()
    )
    if not run.data:
        raise RuntimeError("Unable to create screening run")
    run_id = run.data[0]["id"]

    engine = ScreeningEngine(
        min_market_cap=settings.screener_min_market_cap,
        min_score=settings.screener_min_score,
        min_confidence=settings.screener_min_confidence,
    )
    persisted_results: list[ScreeningResult] = []
    data_errors = 0
    processed = 0

    for raw_symbol in symbols:
        symbol = raw_symbol.strip().upper()
        provider_error: Exception | None = None
        try:
            metrics = data_service.get_company_snapshot(symbol)
            result = engine.screen(metrics)
            processed += 1
        except Exception as exc:
            provider_error = exc
            data_errors += 1
            result = _provider_failure(symbol, exc)
            logger.exception(
                "Screening data failure for %s in run %s (%s): %s",
                symbol,
                run_id,
                type(exc).__name__,
                exc,
            )

        try:
            ticker_id = _upsert_ticker(client, result)
            _persist_result(client, run_id, ticker_id, result, provider_error)
            persisted_results.append(result)
        except Exception as persistence_error:
            logger.exception(
                "Could not persist screening result for %s in run %s: %s",
                symbol,
                run_id,
                persistence_error,
            )
            if provider_error is None:
                data_errors += 1

    passing = sorted(
        (
            result
            for result in persisted_results
            if result.passed and result.score is not None
        ),
        key=lambda result: (result.score or 0, result.confidence),
        reverse=True,
    )
    selected = passing[:top_n]
    candidates = [
        {
            **result.metrics,
            "symbol": result.symbol,
            "business_model": result.business_model.value,
            "score": result.score,
            "confidence": result.confidence,
        }
        for result in selected
    ]
    summary = {
        "requested": len(symbols),
        "processed": processed,
        "failed": data_errors,
        "passed": len(passing),
        "selected_for_ai": len(selected),
    }

    (
        client.table("screening_runs")
        .update(
            {
                "status": "completed",
                "candidates_count": len(passing),
                "processed_count": processed,
                "failed_count": data_errors,
                "passed_count": len(passing),
                "selected_count": len(selected),
                "completed_at": datetime.now(timezone.utc).isoformat(),
            }
        )
        .eq("id", run_id)
        .eq("user_id", user_id)
        .execute()
    )

    return {
        "run_id": run_id,
        "candidates": candidates,
        "count": len(candidates),
        **summary,
    }
