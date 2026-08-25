"""Provider ownership and executable inventory without importing provider code."""

from __future__ import annotations

import ast
from pathlib import Path


API_ROOT = Path(__file__).parents[1]
CONTRACTS_SOURCE = API_ROOT / "src" / "stocks" / "providers" / "contracts.py"
VNSTOCK_SOURCE = API_ROOT / "src" / "stocks" / "providers" / "vnstock_provider.py"


def _tree(path: Path) -> ast.Module:
    return ast.parse(path.read_text(encoding="utf-8"))


def _class_methods(tree: ast.Module) -> dict[str, set[str]]:
    return {
        node.name: {
            child.name
            for child in node.body
            if isinstance(child, (ast.AsyncFunctionDef, ast.FunctionDef))
        }
        for node in tree.body
        if isinstance(node, ast.ClassDef)
    }


def _enum_members(tree: ast.Module, class_name: str) -> set[str]:
    target = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == class_name
    )
    return {
        node.targets[0].id
        for node in target.body
        if isinstance(node, ast.Assign)
        and len(node.targets) == 1
        and isinstance(node.targets[0], ast.Name)
    }


def _ownership(tree: ast.Module) -> dict[str, dict[str, str]]:
    declaration = next(
        node
        for node in tree.body
        if isinstance(node, ast.AnnAssign)
        and isinstance(node.target, ast.Name)
        and node.target.id == "SOURCE_OWNERSHIP_BY_CAPABILITY"
    )
    assert isinstance(declaration.value, ast.Call)
    table = declaration.value.args[0]
    assert isinstance(table, ast.Dict)
    result: dict[str, dict[str, str]] = {}
    for key, value in zip(table.keys, table.values, strict=True):
        assert isinstance(key, ast.Attribute)
        assert isinstance(value, ast.Call)
        result[key.attr] = {
            keyword.arg: keyword.value.attr
            for keyword in value.keywords
            if keyword.arg is not None and isinstance(keyword.value, ast.Attribute)
        }
    return result


def test_provider_boundary_suite_has_no_project_or_provider_import():
    imports = [
        node
        for node in ast.walk(_tree(Path(__file__)))
        if isinstance(node, (ast.Import, ast.ImportFrom))
    ]

    assert all(
        not (
            isinstance(node, ast.ImportFrom)
            and node.module
            and node.module.startswith("src")
        )
        for node in imports
    )
    assert all(
        not (
            isinstance(node, ast.Import)
            and any(alias.name.startswith(("src", "vnstock")) for alias in node.names)
        )
        for node in imports
    )


def test_declared_valuation_cover_does_not_invent_an_executable_adapter():
    ownership = _ownership(_tree(CONTRACTS_SOURCE))
    classes = _class_methods(_tree(VNSTOCK_SOURCE))

    assert ownership["VALUATION"] == {"main": "FIINQUANT", "cover": "VNSTOCK"}
    assert "VnstockValuationProvider" not in classes
    assert "fetch_valuation" not in classes["VnstockProviderBase"]


def test_executable_corporate_actions_do_not_invent_snapshot_ownership():
    contracts = _tree(CONTRACTS_SOURCE)
    classes = _class_methods(_tree(VNSTOCK_SOURCE))

    assert "fetch_corporate_actions" in classes["VnstockCorporateActionProvider"]
    assert "CORPORATE_ACTION" not in _enum_members(contracts, "Capability")


def test_vnstock_history_does_not_imply_current_or_index_execution():
    classes = _class_methods(_tree(VNSTOCK_SOURCE))

    assert "fetch_market_history" in classes["VnstockMarketHistoryProvider"]
    assert "fetch_market" not in classes["VnstockMarketHistoryProvider"]
    assert "VnstockMarketIndexProvider" not in classes


def test_fundamental_module_documents_its_actual_three_call_shape():
    prose = ast.get_docstring(_tree(VNSTOCK_SOURCE), clean=False) or ""

    assert "three requests per symbol" in prose
    assert "income,\nbalance, and cash flow" in prose
