from __future__ import annotations

import ast
from pathlib import Path


APP_ROOT = Path(__file__).parents[1] / "app"


def test_application_never_inserts_confirmed_transactions_directly():
    direct_inserts: list[Path] = []

    for python_file in APP_ROOT.rglob("*.py"):
        tree = ast.parse(python_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "insert"
                and _contains_table_call(node.func.value, "transactions")
            ):
                direct_inserts.append(python_file.relative_to(APP_ROOT))

    assert direct_inserts == []


def test_confirm_transaction_rpc_is_centralized_in_workflow_repository():
    rpc_callers: list[Path] = []

    for python_file in APP_ROOT.rglob("*.py"):
        tree = ast.parse(python_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr == "rpc"
                and node.args
                and isinstance(node.args[0], ast.Constant)
                and node.args[0].value == "confirm_transaction_draft"
            ):
                rpc_callers.append(python_file.relative_to(APP_ROOT))

    assert rpc_callers == [Path("services/portfolio_workflow/repository.py")]


def test_research_graph_stops_at_human_review_inbox():
    graph_source = (APP_ROOT / "agents" / "graph.py").read_text(encoding="utf-8")

    assert 'table("analysis_inbox").insert' in graph_source
    assert 'table("transaction_drafts")' not in graph_source
    assert 'table("transactions")' not in graph_source


def _contains_table_call(node: ast.AST, table_name: str) -> bool:
    if isinstance(node, ast.Call):
        if (
            isinstance(node.func, ast.Attribute)
            and node.func.attr == "table"
            and node.args
            and isinstance(node.args[0], ast.Constant)
            and node.args[0].value == table_name
        ):
            return True
        return _contains_table_call(node.func, table_name)
    if isinstance(node, ast.Attribute):
        return _contains_table_call(node.value, table_name)
    return False
