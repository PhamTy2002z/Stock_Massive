"""The port, checked against what the hand-written Studies actually produced.

`fixtures/pre-port/*.json` holds the frames, the headline and the provenance the
four hand-written Studies produced on the **real store** at a pinned as-of,
captured before any of them was ported. This file runs the same four templates
with the same parameters and holds every surviving frame equal to the cell.

**It skips when the store is empty, and that is the honest arrangement.** The
suite's own database is the developer's, which holds only what a test planted;
these fixtures were chased out of the deployment's store, and a comparison
against a synthetic window would be a comparison against a window the fixture
never saw. The hermetic regression is the four per-Study files beside this one:
they plant a window whose answer is known before it runs and assert on it. What
*this* file adds is the thing a synthetic window cannot give — the numbers a real
market produced, before and after, on questions nobody wrote a fixture for.

To run it against the deployment's store:

    DATABASE_URL="postgresql://postgres:postgres@<host>:5432/stockmassive" \\
    UNIVERSE_SYMBOLS="ACB,BID,…,VRE" \\
    make test-one T=tests/studies/test_templates_regression.py

A frame in a fixture that the port no longer produces is **skipped by name**, and
there is exactly one: ``tiles``. Its only consumer was the version-one
``stat_tiles`` block, and the board's KPI strip is what replaced it — every
figure it carried is now a reference the server resolves, which the per-Study
files assert cell by cell.
"""

from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import pytest

from src.core.database import get_sync_db
from src.stocks.universe import build_universe
from src.studies import REGISTRY
from src.studies.contracts import StudyRefused

from .template_run import run_template

FIXTURES = Path(__file__).with_name("fixtures") / "pre-port"

#: The one frame the port drops on purpose. Named rather than inferred, so a
#: second frame going missing is a failure rather than a silence.
REPLACED_BY_THE_KPI_STRIP = "tiles"

#: How close is the same number. Tight enough that a changed order of operations
#: shows up, loose enough that it is not asserting on float bit patterns.
TOLERANCE = 1e-9

#: The one headline figure the port genuinely moved, and by how much it may.
#:
#: ``phaseSummary`` sums the four parts of a session. The hand-written Study
#: summed the shares it had computed and rounded once at the end; the template
#: sums the shares the *picture draws*, which are already rounded to four places,
#: so sixteen buckets carry sixteen roundings — measured at 0,0001 on the
#: fixture (0,2889 → 0,2890). Kept rather than removed: a headline that agrees
#: with the panel under it to the last digit is worth more than one that lands
#: on a tidier total and disagrees with every cell. The allowance is one unit of
#: the last place a cell carries, so a real change still fails here.
PUBLISHED_CELL_PLACES = 5e-4
LOOSER_BY_ROUNDING: frozenset[str] = frozenset({"phaseSummary"})


def cases() -> list[str]:
    return sorted(path.stem for path in FIXTURES.glob("*.json"))


@pytest.fixture(scope="module")
def a_store_with_the_market_in_it():
    """Skip a test unless the configured store is the real one.

    Requested rather than autouse, so the one test below that asks nothing of
    the store still runs on a developer's own database — a fixture naming a
    Study nobody registers should fail everywhere, not only where the market is.
    """
    with get_sync_db() as session:
        universe = build_universe(session).symbols
    if len(universe) < 10:
        pytest.skip(
            "the pre-port fixtures were captured on the deployment's store; "
            "set DATABASE_URL and UNIVERSE_SYMBOLS to run this file"
        )


def same(left: Any, right: Any) -> bool:
    if isinstance(left, bool) or isinstance(right, bool):
        return left == right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        scale = max(1.0, abs(float(left)), abs(float(right)))
        return abs(float(left) - float(right)) <= TOLERANCE * scale
    return left == right


@pytest.mark.parametrize("name", cases())
def test_the_port_reproduces_what_the_hand_written_study_produced(
    name, monkeypatch, a_store_with_the_market_in_it
):
    before = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    with get_sync_db() as session:
        universe = build_universe(session).symbols

    try:
        after = run_template(
            before["study"],
            before["params"],
            universe=universe,
            monkeypatch=monkeypatch,
            as_of=datetime.fromisoformat(before["asOf"]),
        )
    except StudyRefused as refused:  # pragma: no cover - a store that moved
        pytest.skip(
            f"{name} refuses on this store now ({refused.issue.value}); the "
            "fixture was captured when it did not"
        )

    for frame_name, want in before["frames"].items():
        if frame_name == REPLACED_BY_THE_KPI_STRIP:
            continue
        got = after.frames.get(frame_name)
        assert got is not None, f"{name}: the port produces no {frame_name!r}"
        assert list(got.columns) == list(want["columns"]), frame_name
        assert got.unit == want["unit"], frame_name
        assert dict(got.labels) == dict(want["labels"]), frame_name
        assert list(got.point_roles) == list(want["pointRoles"] or []), frame_name
        assert len(got.rows) == len(want["rows"]), frame_name
        for index, (left, right) in enumerate(zip(want["rows"], got.rows)):
            for column, a, b in zip(want["columns"], left, right):
                assert same(a, b), f"{name}.{frame_name} row {index} {column}"


@pytest.mark.parametrize("name", cases())
def test_the_headline_the_model_reads_did_not_move(
    name, monkeypatch, a_store_with_the_market_in_it
):
    """The three hundred tokens a sentence is written from, held equal too.

    Separate from the frames because it fails differently: a frame that moved is
    a calculation that changed, and a headline that moved is what the model will
    say about numbers that did not.
    """
    before = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
    with get_sync_db() as session:
        universe = build_universe(session).symbols

    try:
        after = run_template(
            before["study"],
            before["params"],
            universe=universe,
            monkeypatch=monkeypatch,
            as_of=datetime.fromisoformat(before["asOf"]),
        )
    except StudyRefused as refused:  # pragma: no cover - a store that moved
        pytest.skip(f"{name} refuses on this store now ({refused.issue.value})")

    got = json.loads(json.dumps(after.headline, default=str))
    want = before["headline"]

    assert set(got) == set(want), name
    for key in want:
        tolerance = (
            PUBLISHED_CELL_PLACES if key in LOOSER_BY_ROUNDING else TOLERANCE
        )
        assert _agrees(got[key], want[key], tolerance), f"{name}.{key}"


def _agrees(got: Any, want: Any, tolerance: float) -> bool:
    """The same figure, through whatever nesting a headline puts it in."""
    if isinstance(want, dict):
        return isinstance(got, dict) and set(got) == set(want) and all(
            _agrees(got[key], want[key], tolerance) for key in want
        )
    if isinstance(want, list):
        return (
            isinstance(got, list)
            and len(got) == len(want)
            and all(_agrees(a, b, tolerance) for a, b in zip(got, want))
        )
    if isinstance(want, bool) or isinstance(got, bool):
        return got == want
    if isinstance(want, (int, float)) and isinstance(got, (int, float)):
        scale = max(1.0, abs(float(want)), abs(float(got)))
        return abs(float(got) - float(want)) <= tolerance * scale
    return got == want


def test_every_fixture_names_a_template_that_still_exists():
    """The fixtures are not orphans, checked without touching the store.

    The only test in this file that runs on a developer's own database. A
    fixture naming a Study nobody registers is a fixture nothing compares
    against, and it would otherwise sit here reading as coverage.
    """
    for name in cases():
        before = json.loads((FIXTURES / f"{name}.json").read_text(encoding="utf-8"))
        assert before["study"] in REGISTRY, name
        assert before["frames"], name
