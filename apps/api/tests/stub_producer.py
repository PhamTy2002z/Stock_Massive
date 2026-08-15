"""The placeholder producer, kept where nothing shipped can reach it.

It stood in ``src/alpha/producer.py`` while the **Analysis Run** lifecycle was
built, so every state could be driven before generation existed. Once a real
producer landed it moved here, and the move is the point: a stub importable from
``src`` is one wrong default away from publishing a placeholder to a user, and
the payload's ``stub: True`` marker only helps somebody who already suspects.

Still marked, for the same reason it always was. A test that finds this payload
in the database is a test that proved the wiring, and one that finds it anywhere
else has found a bug.
"""

from datetime import date

from src.alpha.producer import AnalysisDraft


def stub_producer(symbol: str, trading_day: date) -> AnalysisDraft:
    """A STUB. It produces no Analysis and must never run outside these tests."""
    return AnalysisDraft(
        verdict="watch",
        payload={
            "stub": True,
            "symbol": symbol,
            "trading_day": trading_day.isoformat(),
            "note": "Placeholder used by the Analysis Run lifecycle tests.",
        },
    )
