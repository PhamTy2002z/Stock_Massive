"""How much room foreign investors still have in a symbol, and when it was read.

A Vietnamese equity has a statutory ceiling on foreign ownership, and the room
under it is a **reference** fact rather than a session one: it changes over
months, it is collected with the price board rather than derived from it, and it
has nothing to do with any window of bars.

It is here because a foreign-flow reading is not readable without it. A flow that
flattens because the room filled is not a change of view, and a field that cannot
tell the two apart must not imply it can — so the flow field reports the room
state beside its number, and degrades where the room is exhausted rather than
presenting a mechanically-capped flow as an ordinary one.

Nothing here reaches a Provider Source. A symbol whose room this system has not
collected reports its room as unknown, which is a fact about the store rather
than a reason to make a live call.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.models import ProviderSnapshot

from ..providers.contracts import Capability, ReferenceSnapshot, main_source
from ..providers.normalize import VN_TZ

# The share of the foreign cap that has to remain before a flow is read as an
# ordinary one. One percent rather than zero: a room down to its last fraction
# stops buying as mechanically as a room at zero does, because the remaining
# shares cannot absorb an ordinary session's foreign demand.
#
# A domain choice and not a null derivation, and the difference matters: a null
# can say how often a statistic trips on noise, and it has no opinion on where a
# regulatory ceiling starts to bind.
FOREIGN_ROOM_EXHAUSTED_SHARE = 0.01

# How old a reference reading may be before a figure drawn from it is degraded.
# Ninety days: the room moves when foreigners trade and when the cap is
# re-issued, so a reading from last quarter describes a different book, and the
# reference Capability is collected on every ordinary cycle — a reading three
# months old is a collector that stopped rather than a room that never moved.
#
# Declared here because this is the registry contract for the reference
# Capability, and the nightly pipeline's freshness rule reads the threshold off
# the contract rather than holding one of its own (spec 0003 §8.3). Like
# ``FUNDAMENTAL_STALE_DAYS`` it is a domain choice and not a null derivation: a
# null can say how often a statistic trips on noise, and has no opinion on how
# long a collected fact stays current.
REFERENCE_STALE_DAYS = 90

_REFERENCE = Capability.REFERENCE.value


class ForeignRoomState(str, Enum):
    """The room in one word, for a payload that must always say something.

    Three states rather than two, because "nobody has collected this symbol's
    room" and "the room is open" are different facts, and a field that reported
    them the same way would be asserting the second on the evidence of the
    first. A closed set for the same reason every other vocabulary in this
    package is one: the web app holds one Vietnamese sentence per value.
    """

    OPEN = "open"
    EXHAUSTED = "exhausted"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class ForeignRoomStanding:
    """The foreign room this system last saw for a symbol, and on what date.

    ``current_room`` is the number of shares foreigners may still buy and
    ``total_room`` the cap those shares sit under, both as the price board
    publishes them. Either may be absent: the board carries them for most
    symbols and not for all, and an absent room is unknown rather than full.
    """

    symbol: str
    current_room: int | None
    total_room: int | None
    as_of: date
    # How far the date being answered for is past the reading, in days. Carried
    # rather than recomputed by each reader, for the reason
    # ``FundamentalStanding`` carries its own: the age is a property of the
    # question and the row together, and a reader holding only the row would
    # have to be handed the cutoff again to work it out.
    age_days: int

    @property
    def stale(self) -> bool:
        """Whether narrating this reading as current would be wrong."""
        return self.age_days > REFERENCE_STALE_DAYS

    @property
    def available_share(self) -> float | None:
        """What fraction of the foreign cap is still open, where both are known."""
        if (
            self.current_room is None
            or self.total_room is None
            or self.total_room <= 0
        ):
            return None
        return self.current_room / self.total_room

    @property
    def exhausted(self) -> bool:
        """Whether the room is full enough to stop buying by itself."""
        share = self.available_share
        return share is not None and share <= FOREIGN_ROOM_EXHAUSTED_SHARE

    @property
    def state(self) -> ForeignRoomState:
        """Which of the three this reading is."""
        if self.available_share is None:
            return ForeignRoomState.UNKNOWN
        return (
            ForeignRoomState.EXHAUSTED
            if self.exhausted
            else ForeignRoomState.OPEN
        )

    def as_extras(self) -> dict[str, object]:
        """What a foreign-flow answer says about the room beside its number."""
        return {
            "foreign_room_state": self.state.value,
            "foreign_room_available_share": self.available_share,
            "foreign_room_as_of": self.as_of.isoformat(),
        }


def foreign_room_on_or_before(
    session: Session,
    symbol: str,
    day: date,
) -> ForeignRoomStanding | None:
    """The newest reference reading of this symbol's room at or before a date.

    ``None`` where the store holds none. Dated by the session the board was read
    in, which is how the Adapter writes it — the room carries no period of its
    own — so a cutoff in the past gets the room as it was then rather than the
    room as it is now.
    """
    cutoff = datetime.combine(day + timedelta(days=1), time.min, tzinfo=VN_TZ)
    row = session.execute(
        select(ProviderSnapshot)
        .where(
            ProviderSnapshot.capability == _REFERENCE,
            ProviderSnapshot.symbol == symbol.upper(),
            ProviderSnapshot.source == main_source(Capability.REFERENCE).value,
            ProviderSnapshot.effective_at < cutoff,
        )
        .order_by(
            ProviderSnapshot.effective_at.desc(),
            ProviderSnapshot.observed_at.desc(),
        )
        .limit(1)
    ).scalar_one_or_none()
    if row is None:
        return None

    snapshot = ReferenceSnapshot.model_validate(row.payload)
    read_on = row.effective_at.astimezone(VN_TZ).date()
    return ForeignRoomStanding(
        symbol=row.symbol,
        current_room=snapshot.current_foreign_room,
        total_room=snapshot.total_foreign_room,
        as_of=read_on,
        age_days=(day - read_on).days,
    )
