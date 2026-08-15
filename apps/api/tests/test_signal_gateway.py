"""Keep computations behind the package's one gateway to stored sessions."""

import ast
from pathlib import Path


SIGNALS_PACKAGE = Path(__file__).parents[1] / "src" / "stocks" / "signals"

# Only the existing infrastructure seam may touch each raw reader. Naming the
# capability rather than exempting the whole file means adding a second raw path
# inside one of these modules still needs an explicit architectural decision.
RAW_ACCESS_ALLOWLIST = {
    "bars.py": {"sessions"},
    "corporate_actions.py": {"SnapshotStore"},
    "price_band.py": {"sessions"},
    "sessions.py": {"ProviderSnapshot"},
}


def _forbidden_session_imports(path: Path) -> set[str]:
    forbidden: set[str] = set()
    tree = ast.parse(path.read_text(), filename=str(path))
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.endswith(".sessions"):
                    forbidden.add("sessions")
        elif isinstance(node, ast.ImportFrom):
            module = node.module or ""
            names = {alias.name for alias in node.names}
            if module.endswith("sessions") or "sessions" in names:
                forbidden.add("sessions")
            forbidden.update(names & {"ProviderSnapshot", "SnapshotStore"})
    return forbidden


def test_no_computation_module_opens_a_second_path_to_session_data():
    violations = {
        path.name: sorted(unexpected)
        for path in SIGNALS_PACKAGE.glob("*.py")
        if (
            unexpected := _forbidden_session_imports(path)
            - RAW_ACCESS_ALLOWLIST.get(path.name, set())
        )
    }

    assert violations == {}


def test_the_guard_recognises_ordinary_module_import_forms(tmp_path: Path):
    examples = (
        "import src.stocks.signals.sessions as sessions",
        "from src.stocks.signals import sessions",
        "from . import sessions",
    )
    for index, source in enumerate(examples):
        candidate = tmp_path / f"candidate_{index}.py"
        candidate.write_text(source)
        assert _forbidden_session_imports(candidate), source
