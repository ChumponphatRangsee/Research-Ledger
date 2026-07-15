from typing import Any

import yfinance as yf


def fetch_financial_metrics(symbol: str) -> dict[str, Any]:
    ticker = yf.Ticker(symbol)
    info = ticker.info or {}
    hist = ticker.history(period="5d")
    current_price = float(hist["Close"].iloc[-1]) if not hist.empty else info.get("currentPrice", 0)

    return {
        "symbol": symbol,
        "name": info.get("longName") or info.get("shortName"),
        "sector": info.get("sector"),
        "industry": info.get("industry"),
        "market_cap": info.get("marketCap"),
        "current_price": current_price,
        "pe_ratio": info.get("trailingPE") or info.get("forwardPE"),
        "roe": info.get("returnOnEquity"),
        "revenue_growth": info.get("revenueGrowth"),
        "profit_margin": info.get("profitMargins"),
        "debt_to_equity": info.get("debtToEquity"),
    }
