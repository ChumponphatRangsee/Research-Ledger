"""Typed inputs and explainable outputs for quantitative screening."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


class BusinessModel(str, Enum):
    SOFTWARE = "software"
    SEMICONDUCTOR = "semiconductor"
    BANK = "bank"
    CONSUMER_INDUSTRIAL = "consumer_industrial"
    ENERGY = "energy"
    DEFAULT = "default"
    UNSUPPORTED = "unsupported"


class FinancialMetrics(BaseModel):
    """Normalized provider data. Missing values remain ``None``."""

    model_config = ConfigDict(extra="ignore")

    symbol: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None

    current_price: float | None = None
    market_cap: float | None = None

    pe_ratio: float | None = None
    forward_pe: float | None = None
    price_to_book: float | None = None
    fcf_yield: float | None = None

    roe: float | None = None
    roa: float | None = None
    roic: float | None = None

    revenue_growth: float | None = None
    earnings_growth: float | None = None

    gross_margin: float | None = None
    operating_margin: float | None = None
    fcf_margin: float | None = None
    fcf_conversion: float | None = None

    revenue: float | None = None
    free_cash_flow: float | None = None
    operating_cash_flow: float | None = None

    debt_to_equity: float | None = None
    net_debt_to_ebitda: float | None = None
    interest_coverage: float | None = None

    dividend_yield: float | None = None
    capex_intensity: float | None = None
    inventory_growth: float | None = None

    # Bank-specific extension points. The current yfinance adapter usually
    # cannot populate these, so they intentionally remain optional.
    rotce: float | None = None
    cet1_ratio: float | None = None
    net_interest_margin: float | None = None
    efficiency_ratio: float | None = None
    charge_off_ratio: float | None = None
    tangible_book_growth: float | None = None

    data_as_of: datetime | None = None


class MetricScore(BaseModel):
    score: float | None
    available: bool
    value: float | None
    reason: str


class CategoryScore(BaseModel):
    score: float | None
    weight: float
    metrics: dict[str, MetricScore] = Field(default_factory=dict)


class ScreeningResult(BaseModel):
    symbol: str
    name: str | None = None
    sector: str | None = None
    industry: str | None = None
    business_model: BusinessModel
    passed: bool
    score: float | None = None
    confidence: float
    category_scores: dict[str, float | None] = Field(default_factory=dict)
    score_breakdown: dict[str, CategoryScore] = Field(default_factory=dict)
    strengths: list[str] = Field(default_factory=list)
    warnings: list[str] = Field(default_factory=list)
    failure_reasons: list[str] = Field(default_factory=list)
    metrics: dict[str, Any] = Field(default_factory=dict)
    data_as_of: datetime | None = None

