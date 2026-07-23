"""Centralized sector/industry classification rules."""

from __future__ import annotations

from dataclasses import dataclass

from app.services.screening.models import BusinessModel, FinancialMetrics


@dataclass(frozen=True)
class ClassificationRule:
    business_model: BusinessModel
    sectors: tuple[str, ...] = ()
    industry_keywords: tuple[str, ...] = ()

    def matches(self, sector: str, industry: str) -> bool:
        sector_match = not self.sectors or sector in self.sectors
        industry_match = not self.industry_keywords or any(
            keyword in industry for keyword in self.industry_keywords
        )
        return sector_match and industry_match


CLASSIFICATION_RULES = (
    ClassificationRule(
        BusinessModel.SEMICONDUCTOR,
        industry_keywords=("semiconductor", "integrated circuit"),
    ),
    ClassificationRule(
        BusinessModel.SOFTWARE,
        industry_keywords=("software", "cloud", "internet content"),
    ),
    ClassificationRule(
        BusinessModel.BANK,
        sectors=("financial services",),
        industry_keywords=("bank",),
    ),
    ClassificationRule(
        BusinessModel.ENERGY,
        sectors=("energy",),
    ),
    ClassificationRule(
        BusinessModel.CONSUMER_INDUSTRIAL,
        sectors=(
            "industrials",
            "consumer cyclical",
            "consumer defensive",
            "basic materials",
        ),
    ),
)

UNSUPPORTED_SECTORS = {"real estate", "utilities"}
UNSUPPORTED_INDUSTRY_KEYWORDS = {
    "reit",
    "insurance",
    "asset management",
    "capital markets",
    "shell companies",
}


def classify_business_model(metrics: FinancialMetrics) -> BusinessModel:
    sector = (metrics.sector or "").strip().lower()
    industry = (metrics.industry or "").strip().lower()

    if sector in UNSUPPORTED_SECTORS or any(
        keyword in industry for keyword in UNSUPPORTED_INDUSTRY_KEYWORDS
    ):
        return BusinessModel.UNSUPPORTED

    for rule in CLASSIFICATION_RULES:
        if rule.matches(sector, industry):
            return rule.business_model

    return BusinessModel.DEFAULT
