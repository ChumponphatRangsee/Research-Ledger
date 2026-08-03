import ast
from pathlib import Path

from app.agents.nodes import financial
from app.services.market_data import CompanyFinancialSnapshot


def test_yfinance_is_imported_only_by_provider_adapter():
    app_root = Path(__file__).parents[1] / "app"
    direct_imports: list[Path] = []

    for python_file in app_root.rglob("*.py"):
        tree = ast.parse(python_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import) and any(
                alias.name == "yfinance"
                or alias.name.startswith("yfinance.")
                for alias in node.names
            ):
                direct_imports.append(python_file.relative_to(app_root))
            if (
                isinstance(node, ast.ImportFrom)
                and node.module is not None
                and (
                    node.module == "yfinance"
                    or node.module.startswith("yfinance.")
                )
            ):
                direct_imports.append(python_file.relative_to(app_root))

    assert direct_imports == [
        Path("services/market_data/providers/yfinance.py")
    ]


def test_application_has_no_legacy_yfinance_client_dependency():
    app_root = Path(__file__).parents[1] / "app"
    application_source = "\n".join(
        python_file.read_text(encoding="utf-8")
        for python_file in app_root.rglob("*.py")
    )

    assert "yfinance_client" not in application_source
    assert "fetch_financial_metrics" not in application_source
    non_market_data_source = "\n".join(
        python_file.read_text(encoding="utf-8")
        for python_file in app_root.rglob("*.py")
        if "market_data" not in python_file.parts
    )
    assert "YFinanceProvider" not in non_market_data_source


def test_financial_node_uses_normalized_market_data_without_live_call(monkeypatch):
    requested_symbols: list[str] = []

    class FakeMarketDataService:
        def get_company_snapshot(self, symbol: str) -> CompanyFinancialSnapshot:
            requested_symbols.append(symbol)
            return CompanyFinancialSnapshot(
                symbol="AAPL",
                pe_ratio=25,
                roe=None,
                revenue_growth=0.12,
            )

    monkeypatch.setattr(
        financial,
        "MarketDataService",
        FakeMarketDataService,
    )

    result = financial.financial_analyst_node({"ticker_symbol": "AAPL"})

    assert requested_symbols == ["AAPL"]
    assert result["financial_metrics"]["roe"] is None
    assert result["financial_metrics"]["pe_ratio"] == 25
    assert "P/E: 25.0" in result["financial_analysis"]
