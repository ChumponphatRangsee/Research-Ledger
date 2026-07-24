"""Typed inputs and explainable outputs for quantitative screening."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from app.services.market_data.models import CompanyFinancialSnapshot


class BusinessModel(str, Enum):
    SOFTWARE = "software"
    SEMICONDUCTOR = "semiconductor"
    BANK = "bank"
    CONSUMER_INDUSTRIAL = "consumer_industrial"
    ENERGY = "energy"
    DEFAULT = "default"
    UNSUPPORTED = "unsupported"


# Preserve the established screening import while making market_data the
# canonical owner of the provider-neutral input model.
FinancialMetrics = CompanyFinancialSnapshot


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

