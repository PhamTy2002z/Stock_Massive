"""One read: what the Analysis lane's loop bought, in raw numbers.

Same refusal as ``agent/ops.py``, for the same reason: **one developer, no
on-call rotation.** No dashboard, no alert, no threshold, and no new table. The
endpoint returns counts and the rates derived from them, and a person reads it
when somebody asks whether the loop is doing anything.

**No threshold, deliberately.** There is no healthy/unhealthy boolean here and
none should be added. A substitution rate is a fact about recovery from missing
evidence, not a quality score, and the sentence saying so travels inside the
response (``analysis_reads.SUBSTITUTION_CAVEAT``) rather than living in a plan
nobody reads beside the number.

**Admin only.** Not because the numbers are sensitive but because they are
meaningless to a reader who came to look at a stock, and an endpoint anybody can
call is an endpoint somebody builds a widget on.

**Its own router.** Not a path under ``/analyses``, whose ``/{symbol}`` and
``/{symbol}/{trading_day}`` routes would make this a name that has to be
registered before them and stay there — an ordering constraint nothing in the
file would explain to whoever reorders it.
"""

from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from fastapi import APIRouter, Query

from src.auth.dependencies import AdminUser
from src.core.database import in_sync_session

from .analysis_reads import cited_figure_rate, round_yield, substitution_rate

router = APIRouter(prefix="/ops", tags=["ops"])

#: How many Trading Days back the window reaches when the caller names no dates.
#: Roughly a month of sessions, which is the shortest span over which a rate
#: built from one Analysis per symbol per session means anything.
DEFAULT_WINDOW_DAYS = 21


@router.get("/analysis-loop")
async def get_analysis_loop_measurement(
    _admin: AdminUser,
    since: date | None = Query(
        None, description="First Trading Day in the window, inclusive."
    ),
    until: date | None = Query(
        None, description="Last Trading Day in the window, inclusive."
    ),
) -> dict[str, Any]:
    """The three loop numbers over a range of Trading Days. Reads only.

    Inclusive at both ends, because the window is a range of *sessions* and a
    caller naming two dates means the Analyses on both of them.

    The three are returned together and never folded into one score. They answer
    different questions and one of them can fall while the others rise: a loop
    that fetches more evidence and cites less of it is buying data it does not
    use, and a single number would hide exactly that.
    """
    end = until or date.today()
    start = since or end - timedelta(days=DEFAULT_WINDOW_DAYS)
    if start > end:
        start, end = end, start

    def read(session: Any) -> dict[str, Any]:
        return {
            "since": start.isoformat(),
            "until": end.isoformat(),
            "substitution": substitution_rate(session, start, end).as_wire(),
            "roundYield": round_yield(session, start, end).as_wire(),
            "citedFigures": cited_figure_rate(session, start, end).as_wire(),
        }

    return await in_sync_session(read)


__all__ = ["DEFAULT_WINDOW_DAYS", "router"]
