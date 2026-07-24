"""Normalized, provider-neutral market data models."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class CompanyFinancialSnapshot(BaseModel):
    """Company and financial data required by quantitative screening.

    All financial fields are optional so an unavailable provider value remains
    explicit as ``None``. Provider adapters are responsible for mapping their
    response shapes and units into this model.
    """

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

    # Specialist bank fields remain optional until a provider can supply them.
    rotce: float | None = None
    cet1_ratio: float | None = None
    net_interest_margin: float | None = None
    efficiency_ratio: float | None = None
    charge_off_ratio: float | None = None
    tangible_book_growth: float | None = None

    data_as_of: datetime | None = None
