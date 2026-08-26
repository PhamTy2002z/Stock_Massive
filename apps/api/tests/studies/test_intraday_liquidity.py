"""The study, against a window whose answer is known before it runs.

The fixture builds thirty synthetic sessions with a spike planted at ``14:15`` in
exactly twenty-one of them. Everything asserted below is a fact about that
construction, so a change in the arithmetic shows up as a wrong answer to a
question with a right one — not as a number that merely looks plausible.
"""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlalchemy import delete

from src.core.database import Base, get_sync_db, sync_engine
from src.stocks.intraday import session_window
from src.stocks.models import BarIntraday15m
from src.stocks.providers.normalize import VN_TZ
from src.stocks.signals.issues import SignalIssue
from src.studies import registry, runner
from src.studies.contracts import StudyRefused
from src.studies.intraday_liquidity import MIN_SESSIONS, NAME

from . import artifact_fixture as fixture

SYMBOL = fixture.SYMBOL  # declared Universe, so the membership check passes
OUTSIDE = "NOTINUNIV"
LAST_SESSION = fixture.LAST_SESSION
SPIKE_BUCKET = fixture.SPIKE_BUCKET
SPIKE_SESSIONS = fixture.SPIKE_SESSIONS
TOTAL_SESSIONS = fixture.TOTAL_SESSIONS
BASE_VOLUME = fixture.BASE_VOLUME
SPIKE_VOLUME = fixture.SPIKE_VOLUME
HOSE_BUCKETS = fixture.HOSE_BUCKETS


@pytest.fixture(scope="module", autouse=True)
def schema():
    Base.metadata.create_all(sync_engine, checkfirst=True)


@pytest.fixture
def window():
    """Thirty stored sessions for STB, removed again afterwards."""
    with get_sync_db() as session:
        fixture.load_window(session)
        session.commit()

    yield fixture.sessions()

    with get_sync_db() as session:
        session.execute(delete(BarIntraday15m).where(BarIntraday15m.symbol == SYMBOL))
        session.commit()


def at(day: date, hour: int = 16) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=VN_TZ)


def run(params: dict, monkeypatch):
    """The whole run path, with the Universe declared here.

    ``UNIVERSE_SYMBOLS`` is empty in the suite's settings — a declared Universe
    is operator configuration, not a test fixture — so the membership the study
    checks is stated locally rather than inherited from whatever the developer
    has in their environment.
    """
    monkeypatch.setattr(
        runner, "build_universe", lambda session: _AUniverseOf((SYMBOL,))
    )
    with get_sync_db() as session:
        stored = runner.run(NAME, params, session=session)
        session.rollback()
        return stored


class _AUniverseOf:
    def __init__(self, symbols: tuple[str, ...]) -> None:
        self.symbols = symbols


def compute(params: dict, when: datetime):
    """The study's own compute, with as-of pinned so the window is deterministic."""
    from src.studies.contracts import StudyContext
    from src.studies.intraday_liquidity import LiquidityParams, compute as _compute

    with get_sync_db() as session:
        return _compute(
            StudyContext(
                params=LiquidityParams.model_validate(params),
                session=session,
                as_of=when,
                universe=(SYMBOL,),
            )
        )


def test_the_planted_spike_is_the_peak_window_at_the_frequency_planted(window):
    result = compute({"symbol": SYMBOL}, at(LAST_SESSION))

    assert result.headline["peakWindow"] == SPIKE_BUCKET
    assert result.headline["peakOccurrence"] == f"{SPIKE_SESSIONS}/{TOTAL_SESSIONS}"
    assert result.headline["sessionsUsed"] == TOTAL_SESSIONS
    assert result.headline["peakAvgAmount"] == pytest.approx(
        (SPIKE_VOLUME * SPIKE_SESSIONS + BASE_VOLUME * (TOTAL_SESSIONS - SPIKE_SESSIONS))
        / TOTAL_SESSIONS,
        rel=1e-6,
    )


def test_every_sessions_shares_sum_to_one_over_the_buckets_it_has(window):
    result = compute({"symbol": SYMBOL}, at(LAST_SESSION))
    heatmap = result.frames["heatmap"]

    for row in heatmap.rows:
        cells = [cell for cell in row[1:] if cell is not None]
        assert len(cells) == len(HOSE_BUCKETS)
        assert sum(cells) == pytest.approx(1.0, abs=5e-4)


def test_a_bucket_this_symbol_never_trades_in_is_a_hole_not_a_zero(window):
    result = compute({"symbol": SYMBOL}, at(LAST_SESSION))
    heatmap = result.frames["heatmap"]
    ato_column = heatmap.columns.index("09:00")

    assert all(row[ato_column] is None for row in heatmap.rows)
    assert "09:00" not in {row[0] for row in result.frames["profile"].rows}


def test_the_phase_summary_accounts_for_the_whole_session(window):
    result = compute({"symbol": SYMBOL}, at(LAST_SESSION))
    summary = result.headline["phaseSummary"]

    assert summary["ato"] == 0.0  # a HOSE symbol has no 09:00 bucket
    assert sum(summary.values()) == pytest.approx(1.0, abs=5e-4)
    # Per bucket rather than per phase: the morning has nine buckets against the
    # afternoon's six, so the raw phase totals favour the morning even though the
    # planted spike is an afternoon bucket.
    assert summary["pm"] / 6 > summary["am"] / 9


def test_the_value_metric_reads_money_rather_than_shares(window):
    volume = compute({"symbol": SYMBOL, "metric": "volume"}, at(LAST_SESSION))
    value = compute({"symbol": SYMBOL, "metric": "value"}, at(LAST_SESSION))

    assert value.frames["profile"].unit == "VND"
    assert volume.frames["profile"].unit == "shares"
    # One price across the fixture, so shares and money rank the buckets alike.
    assert value.headline["peakWindow"] == volume.headline["peakWindow"]
    assert value.headline["peakAvgAmount"] == pytest.approx(
        volume.headline["peakAvgAmount"] * 75_000, rel=1e-6
    )


def test_a_bucket_missing_from_most_sessions_is_averaged_over_the_whole_window():
    """A quiet quarter hour is quiet, not absent.

    Dividing by the sessions a bucket *appeared* in makes a bucket that traded
    once in thirty look like the busiest of the day, and makes the four phases
    sum to more than one. The sessions it is missing from are sessions it was
    worth nothing in.
    """
    from src.studies.intraday_liquidity import _bucket_statistics, _phase_summary

    by_session = {
        "d1": {"09:15": 50.0, "14:45": 50.0},
        "d2": {"14:45": 100.0},
        "d3": {"14:45": 100.0},
        "d4": {"14:45": 100.0},
    }

    buckets = {bucket.label: bucket for bucket in _bucket_statistics(by_session)}

    # Present in one session of four, at half of it: a share of an eighth.
    assert buckets["09:15"].avg_share == pytest.approx(0.125)
    assert buckets["09:15"].avg_amount == pytest.approx(50.0 / 4)
    # And the whole picture still adds to one session's worth.
    assert sum(_phase_summary(list(buckets.values())).values()) == pytest.approx(1.0)


def test_a_spike_is_measured_rather_than_broken_by_the_clock():
    """Being in the top two has to mean something to be worth counting.

    Taking the first two of a sorted list breaks ties by the order the buckets
    arrived in, which is the clock — so on a session where everything traded the
    same amount, the two earliest quarter hours collected a spike apiece and the
    frequency became a fact about sorting.
    """
    from src.studies.intraday_liquidity import _bucket_statistics

    flat = {label: 100.0 for label in ("09:15", "09:30", "09:45", "10:00")}
    spiked = {"09:15": 100.0, "09:30": 100.0, "09:45": 100.0, "14:45": 900.0}

    buckets = {
        bucket.label: bucket
        for bucket in _bucket_statistics({"d1": flat, "d2": spiked})
    }

    # Nobody is distinguished on the flat session, and only the real spike is on
    # the other — the second slot is a three-way tie that spans the cut.
    assert buckets["14:45"].spike_sessions == 1
    assert buckets["09:15"].spike_sessions == 0
    assert buckets["09:30"].spike_sessions == 0


def test_a_session_with_no_more_buckets_than_the_cut_distinguishes_nothing():
    from src.studies.intraday_liquidity import _bucket_statistics

    buckets = {
        bucket.label: bucket
        for bucket in _bucket_statistics({"d1": {"09:15": 10.0, "09:30": 90.0}})
    }

    assert buckets["09:15"].spike_sessions == 0
    assert buckets["09:30"].spike_sessions == 0


def test_a_window_shorter_than_the_minimum_refuses_with_the_matching_code(window):
    with get_sync_db() as session:
        session.execute(
            delete(BarIntraday15m).where(
                BarIntraday15m.symbol == SYMBOL,
                BarIntraday15m.trading_day > window[MIN_SESSIONS - 2],
            )
        )
        session.commit()

    with pytest.raises(StudyRefused) as refusal:
        compute({"symbol": SYMBOL}, at(LAST_SESSION))

    assert refusal.value.issue is SignalIssue.INSUFFICIENT_SESSIONS


def test_a_symbol_outside_the_universe_is_refused_before_any_read():
    from src.studies.contracts import StudyContext
    from src.studies.intraday_liquidity import LiquidityParams, compute as _compute

    with get_sync_db() as session:
        with pytest.raises(StudyRefused) as refusal:
            _compute(
                StudyContext(
                    params=LiquidityParams.model_validate({"symbol": OUTSIDE}),
                    session=session,
                    as_of=at(LAST_SESSION),
                    universe=(SYMBOL,),
                )
            )

    assert refusal.value.issue is SignalIssue.MISSING_TARGET_SESSION


def test_a_session_count_out_of_range_is_clamped_rather_than_refused():
    from src.studies.intraday_liquidity import LiquidityParams

    assert LiquidityParams.model_validate({"symbol": "stb", "sessions": 900}).sessions == 60
    assert LiquidityParams.model_validate({"symbol": "stb", "sessions": 1}).sessions == 10
    assert LiquidityParams.model_validate({"symbol": "stb"}).symbol == "STB"


def test_the_headline_stays_inside_the_budget_the_model_pays_for(window):
    import json

    result = compute({"symbol": SYMBOL}, at(LAST_SESSION))
    serialized = json.dumps(result.headline, ensure_ascii=False)

    assert len(serialized) < 1_500, serialized


def test_the_canvas_draws_four_blocks_over_frames_the_study_produced(window):
    definition = registry.study(NAME)
    result = compute({"symbol": SYMBOL}, at(LAST_SESSION))
    spec = definition.view(result)

    assert [block.widget for block in spec.blocks] == [
        "stat_tiles",
        "bar_series",
        "session_heatmap",
        "ranked_bars",
    ]
    assert all(block.frame in result.frames for block in spec.blocks)
    assert set(result.frames) == set(definition.frames)
    assert SYMBOL in spec.title


def test_a_run_through_the_runner_persists_the_frames_and_not_the_headline(
    window, monkeypatch
):
    stored = run({"symbol": SYMBOL, "sessions": 30}, monkeypatch)

    assert stored.study_name == NAME
    assert stored.headline["peakWindow"] == SPIKE_BUCKET
    assert stored.canvas_spec.blocks[2].widget == "session_heatmap"


def test_the_published_artifact_fixture_is_what_this_study_produces(window):
    """The browser's fixture and the server's output, held equal.

    ``apps/web`` renders its widgets against
    ``contracts/fixtures/artifact-intraday-liquidity.json``. Regenerate it with
    ``make contracts`` when this fails for a deliberate reason; a handwritten
    edit is the failure mode this test exists to catch.
    """
    import json

    with get_sync_db() as session:
        produced = fixture.payload(session)
        session.rollback()

    published = json.loads(fixture.FIXTURE_PATH.read_text(encoding="utf-8"))

    assert published == produced
