"""Keep computations behind the package's one gateway to stored sessions."""

import ast
from pathlib import Path


SIGNALS_PACKAGE = Path(__file__).parents[1] / "src" / "stocks" / "signals"

# These modules implement the gateway or the primitives it owns. Every current
# and future computation module is outside this small set and therefore cannot
# import a raw session reader without making this test fail.
SESSION_INFRASTRUCTURE = {
    "bars.py",
    "corporate_actions.py",
    "price_band.py",
    "sessions.py",
}


def _forbidden_session_imports(path: Path) -> set[str]:
    forbidden: set[str] = set()
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if not isinstance(node, ast.ImportFrom):
            continue
        module = node.module or ""
        names = {alias.name for alias in node.names}
        if module.endswith("sessions"):
            forbidden.add(f"{module}: {', '.join(sorted(names))}")
        for name in names & {"ProviderSnapshot", "SnapshotStore"}:
            forbidden.add(f"{module}: {name}")
    return forbidden


def test_no_computation_module_opens_a_second_path_to_session_data():
    violations = {
        path.name: sorted(imports)
        for path in SIGNALS_PACKAGE.glob("*.py")
        if path.name not in SESSION_INFRASTRUCTURE
        and (imports := _forbidden_session_imports(path))
    }

    assert violations == {}
