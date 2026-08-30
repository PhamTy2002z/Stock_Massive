"""The artifact payload both apps develop against, built from the golden window.

``contracts/fixtures/artifact-intraday-liquidity.json`` is what the browser's own
suite renders against, so it has to be a real study run rather than something
handwritten: a handwritten fixture agrees with the code until the day the code
changes, and then the widgets are proven against a shape the server no longer
sends.

Generated (with the widget catalog) by ``make contracts`` from ``apps/api``, and
held equal to this builder by ``test_intraday_liquidity.py``. Deterministic: the
window is synthetic and the as-of is pinned, so regenerating it without a code
change produces the same bytes.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from src.stocks.intraday import ingest, session_window
from src.stocks.providers.normalize import VN_TZ

SYMBOL = "STB"
LAST_SESSION = date(2026, 8, 21)
SPIKE_BUCKET = "14:15"
SPIKE_SESSIONS = 21
TOTAL_SESSIONS = 30
BASE_VOLUME = 100_000
SPIKE_VOLUME = 500_000

#: The as-of the fixture is frozen at. Any instant after the last session's close
#: gives the same window; pinning it keeps the file byte-stable.
AS_OF = datetime(2026, 8, 21, 16, 0, tzinfo=VN_TZ)

GRID = tuple(
    (datetime.min + timedelta(minutes=15 * step)).time() for step in range(96)
)
#: HOSE has no 09:00 bucket — its opening auction lands in 09:15.
HOSE_BUCKETS = tuple(
    label for label in session_window.SESSION_BUCKET_LABELS if label != "09:00"
)

FIXTURE_PATH = (
    Path(__file__).resolve().parents[4]
    / "contracts"
    / "fixtures"
    / "artifact-intraday-liquidity.json"
)


def sessions() -> list[date]:
    return [
        LAST_SESSION - timedelta(days=offset)
        for offset in range(TOTAL_SESSIONS - 1, -1, -1)
    ]


def provider_frame(days: list[date]) -> pd.DataFrame:
    """The provider's 96-bucket grid, with a spike planted in the last 21 days."""
    spiking = set(days[-SPIKE_SESSIONS:])
    records = []
    for day in days:
        for moment in GRID:
            label = session_window.label_of(moment)
            if label not in HOSE_BUCKETS:
                records.append(
                    {
                        "time": datetime.combine(day, moment),
                        "open": float("nan"),
                        "high": float("nan"),
                        "low": float("nan"),
                        "close": float("nan"),
                        "volume": 0,
                    }
                )
                continue
            volume = (
                SPIKE_VOLUME
                if label == SPIKE_BUCKET and day in spiking
                else BASE_VOLUME
            )
            records.append(
                {
                    "time": datetime.combine(day, moment),
                    "open": 74.5,
                    "high": 74.9,
                    "low": 74.2,
                    "close": 75.0,
                    "volume": volume,
                }
            )
    return pd.DataFrame.from_records(records)


def load_window(session) -> None:
    """Put the synthetic window in the store for this symbol."""
    from sqlalchemy import delete

    from src.stocks.models import BarIntraday15m

    days = sessions()
    session.execute(delete(BarIntraday15m).where(BarIntraday15m.symbol == SYMBOL))
    ingest.ensure_bars(
        session,
        SYMBOL,
        sessions=TOTAL_SESSIONS,
        fetch=lambda *_: provider_frame(days),
        today=LAST_SESSION,
    )


def payload(session) -> dict:
    """The artifact as the browser fetches it: the board, its frames, provenance.

    The whole template runs — reader, sandbox, composer — so what the browser
    develops against is what a live question produces rather than a hand-built
    approximation of it. ``as_of`` is passed rather than taken from the clock,
    which is what keeps regenerating this file a no-op when nothing changed.
    """
    from sqlalchemy import select

    from src.agent.tools.query import read_source
    from src.alpha.models import AgentArtifact
    from src.studies import runner
    from src.studies.templates.intraday_liquidity import NAME, VERSION
    from src.studies.templates.params import LiquidityParams

    params = LiquidityParams.model_validate({"symbol": SYMBOL, "sessions": 30})
    universe = _AUniverseOf((SYMBOL,))
    original = runner.build_universe
    runner.build_universe = lambda _session: universe
    try:
        artifact = runner.run(
            NAME,
            params.model_dump(mode="json"),
            session=session,
            read=read_source,
            as_of=AS_OF,
        )
    finally:
        runner.build_universe = original

    row = session.execute(
        select(AgentArtifact).where(AgentArtifact.id == artifact.id)
    ).scalar_one()
    return {
        "studyName": NAME,
        "studyVersion": VERSION,
        "params": params.model_dump(mode="json"),
        "headline": dict(artifact.headline),
        "signal_deskSpec": dict(row.signal_desk_spec),
        "frames": {key: dict(value) for key, value in (row.frames or {}).items()},
        "provenance": dict(row.provenance or {}),
    }


class _AUniverseOf:
    """The declared Universe, stated here rather than read from the environment."""

    def __init__(self, symbols: tuple[str, ...]) -> None:
        self.symbols = symbols


def main() -> None:
    from src.core.database import get_sync_db

    with get_sync_db() as session:
        load_window(session)
        session.flush()
        print(json.dumps(payload(session), ensure_ascii=False, indent=2))
        session.rollback()


if __name__ == "__main__":
    main()
