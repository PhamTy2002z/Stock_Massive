"""The one lane that may mint an Analysis outside the nightly pass.

Adding a symbol to a Watchlist is the only thing that creates an on-demand
**Analysis Run**. Everything else — asking the agent about a Universe symbol,
opening someone's Analysis, browsing history — reads what already exists.

**It always targets the latest Trading Day that already has a Snapshot.** That
is not a rule this module checks; it is the shape of `request_on_demand_analysis`,
which takes a user and a symbol and nothing else. There is no parameter through
which a session that has not closed could arrive, which is the only version of
that guarantee worth having: an argument would be a code path, and a code path
gets used. Adding a symbol at 10:00 therefore yields an Analysis for the last
session that closed — clearly labelled, diffable against the official one the
next evening.

**Three new on-demand Analyses per user per Trading Day.** Two things follow
from the artifact being keyed by ``(symbol, trading_day)`` and shared
system-wide rather than owned by a Watchlist:

*Joining costs nothing.* A symbol already analysed, or already queued by anyone,
creates no run and consumes no allowance. A second watcher is a read.

*The overflow refuses the Analysis, never the addition.* Above the allowance the
symbol still goes on the Watchlist and its Analysis waits for the next nightly
cohort. A production budget is not a reason to stop a user curating the list
they came here to curate.

The count keys on the Trading Day rather than on a wall clock, so it resets when
the session does — by construction, with nothing to schedule and no midnight to
get wrong in a timezone.

What this module deliberately does not own: production. It creates a `pending`
run and stops. The nightly cohort, the queue ordering and the retry backoff are
the pipeline milestone's, and a lane that produced inline would be a second
place where an Analysis gets written.
"""

import logging
from dataclasses import dataclass
from datetime import date
from enum import Enum

from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.core.database import in_sync_write
from src.stocks.shared import validate_symbol
from src.stocks.trading_day import latest_trading_day

from .analysis_run import RunOrigin, RunStatus, published_analysis, stored_run
from .models import AnalysisRun
from .naming import session_label

logger = logging.getLogger(__name__)

# Three new Analyses per user per Trading Day. Small because each one is a real
# generation against a real budget, and large enough that a user seating a fresh
# Watchlist in one evening still sees most of it filled that night.
ON_DEMAND_ANALYSES_PER_DAY = 3


class OnDemandOutcome(str, Enum):
    """What an addition did to the on-demand lane.

    Five values rather than a boolean, because the three that create nothing are
    not the same event. `already_analysed` and `already_queued` are free and
    expected; `allowance_exhausted` is a refusal the user should be told about;
    `no_snapshotted_session` is the system having nothing to analyse yet.
    """

    CREATED = "created"
    ALREADY_ANALYSED = "already_analysed"
    ALREADY_QUEUED = "already_queued"
    ALLOWANCE_EXHAUSTED = "allowance_exhausted"
    NO_SNAPSHOTTED_SESSION = "no_snapshotted_session"


@dataclass(frozen=True)
class OnDemandResult:
    """What the lane did, and what the user has left.

    ``remaining`` is carried on every outcome, including the free ones, so the
    interface can show the allowance without a second request — the same reason
    every Watchlist mutation returns the whole view.

    ``message`` is a sentence a person reads and is present only where nothing
    was created for a reason they would otherwise have to guess at. A free join
    needs no explanation: the rail already shows the symbol's state.
    """

    outcome: OnDemandOutcome
    trading_day: date | None
    remaining: int
    allowance: int = ON_DEMAND_ANALYSES_PER_DAY
    message: str | None = None


def on_demand_analyses_used(session: Session, user_id: int, trading_day: date) -> int:
    """How many on-demand runs this user has caused for this session.

    A count rather than a stored tally, so there is no second thing to keep in
    step with the runs themselves — and no way for a run to exist that the
    allowance forgot about.
    """
    return session.execute(
        select(func.count())
        .select_from(AnalysisRun)
        .where(
            AnalysisRun.trading_day == trading_day,
            AnalysisRun.origin == RunOrigin.ON_DEMAND.value,
            AnalysisRun.requested_by_user_id == user_id,
        )
    ).scalar_one()


def request_on_demand_analysis(
    session: Session,
    user_id: int,
    symbol: str,
) -> OnDemandResult:
    """Open the on-demand lane for one addition, and say what it did.

    Deliberately three parameters. The Trading Day is resolved here, from the
    store, and cannot be supplied — see this module's docstring for why that is
    the whole guarantee rather than a detail of the signature.

    Nothing is produced. The run is created `pending`; whoever drains the queue
    is the pipeline's business.
    """
    symbol = validate_symbol(symbol)
    trading_day = latest_trading_day(session)

    if trading_day is None:
        return OnDemandResult(
            outcome=OnDemandOutcome.NO_SNAPSHOTTED_SESSION,
            trading_day=None,
            remaining=ON_DEMAND_ANALYSES_PER_DAY,
            message=(
                "Chưa có phiên nào được chốt dữ liệu nên chưa dựng được Analysis. "
                "Mã vẫn nằm trên Watchlist."
            ),
        )

    used = on_demand_analyses_used(session, user_id, trading_day)
    remaining = max(0, ON_DEMAND_ANALYSES_PER_DAY - used)

    if published_analysis(session, symbol, trading_day) is not None:
        return OnDemandResult(
            outcome=OnDemandOutcome.ALREADY_ANALYSED,
            trading_day=trading_day,
            remaining=remaining,
        )

    if stored_run(session, symbol, trading_day) is not None:
        return OnDemandResult(
            outcome=OnDemandOutcome.ALREADY_QUEUED,
            trading_day=trading_day,
            remaining=remaining,
        )

    if remaining == 0:
        return OnDemandResult(
            outcome=OnDemandOutcome.ALLOWANCE_EXHAUSTED,
            trading_day=trading_day,
            remaining=0,
            message=(
                f"Bạn đã dùng hết {ON_DEMAND_ANALYSES_PER_DAY} lượt dựng Analysis "
                f"theo yêu cầu cho {session_label(trading_day)}. Mã vẫn nằm "
                "trên Watchlist và sẽ có Analysis trong đợt chạy đêm kế tiếp."
            ),
        )

    session.add(
        AnalysisRun(
            symbol=symbol,
            trading_day=trading_day,
            status=RunStatus.PENDING.value,
            origin=RunOrigin.ON_DEMAND.value,
            attempts=0,
            requested_by_user_id=user_id,
        )
    )
    try:
        session.commit()
    except IntegrityError:
        # Two people added the same symbol at once. ``UNIQUE(symbol, trading_day)``
        # settled it, and the loser joins for free rather than retrying: the row
        # identifies the pair, not the requester.
        session.rollback()
        logger.info(
            "On-demand run for %s %s was created concurrently; joining it",
            symbol,
            trading_day,
        )
        return OnDemandResult(
            outcome=OnDemandOutcome.ALREADY_QUEUED,
            trading_day=trading_day,
            remaining=remaining,
        )

    return OnDemandResult(
        outcome=OnDemandOutcome.CREATED,
        trading_day=trading_day,
        remaining=remaining - 1,
    )


async def open_on_demand_lane(user_id: int, symbol: str) -> OnDemandResult:
    """Reach the lane from an async request handler.

    Through `in_sync_write` because this writes and commits, and the addition it
    follows has to stand whatever the lane decides — the seat is committed
    before this runs, so a failure here leaves a Watchlist entry rather than
    rolling one back.
    """
    return await in_sync_write(
        lambda session: request_on_demand_analysis(session, user_id, symbol)
    )
