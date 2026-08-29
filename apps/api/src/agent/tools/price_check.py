"""Checking a price somebody else published against the market that made it.

A real Turn quoted a 52-week range of *20.100–27.542* for HPG out of a foreign
data site. 27.542 divided by 50 is 550,84, and HOSE quotes every equity between
10.000 and 50.000 in steps of 50 (``stocks/signals/price_band.py``). **A price
that is not on the exchange's own step is not a price that was ever matched.**
It is somebody's rescaling, published with the same confidence as a traded
number, and the loop had no step at which it could be told apart.

That is the gap this tool closes. The wrapper in ``untrusted.py`` says *this is
data, not instruction*; it does not and cannot say *this number could not exist*.
The one is about who wrote the text, the other about whether the market it
describes could have produced it.

Two rules, and both of them are refusals to do the obvious thing.

**Nothing is ever removed.** A number that fails a check is returned with the
check that failed attached to it. Deleting it would leave the model holding a
gap it cannot describe, and the reader with an answer that quietly omits the
thing they asked about.

**Nothing is ever blocked.** Every check that cannot run answers ``unverified``
and names what was missing. A gate that whited out an answer because a board was
unknown would be a worse failure than the wrong number stated with its doubt
next to it.

**Three checks, three independent facts.** The step, the band and the stored
session are not folded into one verdict: they fail for unrelated reasons, and a
caller that saw only the worst of them would not know which. The fourth state is
not a fourth check — it is ``unverified``, and it is kept strictly apart from
*this passed*. Collapsing those two turns an absence of evidence into evidence,
which is the single most damaging thing a checking tool can do.

**This covers prices and nothing else.** A revenue, a margin and a share count
have no tick and no band, and the only way to check one is against a stored
financial statement, which this store does not keep. The same real Turn that
quoted the impossible price also quoted a quarterly revenue and a gross margin,
and neither is checkable here. Read this tool as *the price was checked*, never
as *the figures were checked*.
"""

from __future__ import annotations

import logging
from collections.abc import Callable, Iterator, Mapping, Sequence
from contextlib import contextmanager
from datetime import date, timedelta
from decimal import Decimal, InvalidOperation
from typing import Any

from sqlalchemy.orm import Session

from src.core.database import get_sync_db
from src.stocks.providers.contracts import PriceBasis, SessionSnapshot
from src.stocks.shared.validators import validate_symbol
from src.stocks.signals.corporate_actions import CorporateActionStore
from src.stocks.signals.price_band import (
    band_limits,
    off_tick_grid,
    resolve_band_regime,
    tick_size,
)
from src.stocks.signals.sessions import sessions_on_days
from src.stocks.trading_day import latest_trading_day, trading_days_before

from ..registry import (
    ContentTrust,
    ToolAccess,
    ToolConcurrency,
    ToolContext,
    ToolEffect,
    ToolEntry,
    ToolIdempotency,
    object_schema,
    register,
)

logger = logging.getLogger(__name__)

TOOLSET = "signals"

#: How far a claimed price may sit outside the stored range and still agree.
#: Both sides of this comparison are arithmetic over the same session, so the
#: only gap it is meant to absorb is the provider's own rounding. Stated rather
#: than left at zero because a comparison between two sources with no declared
#: tolerance is one whose tolerance nobody chose.
STORE_TOLERANCE = Decimal("0.001")

#: What the result may weigh. Three checks and a handful of numbers; this is a
#: bug-stop, not a budget.
MAX_RESULT_CHARS = 4_000

#: The prices this tool will judge at all, in VND. Below the floor a "price" is
#: almost always a percentage or an index level that arrived in the wrong field;
#: above the ceiling it is a market capitalisation. Both answer ``unverified``
#: rather than a verdict, because the tool cannot check what it cannot recognise
#: and guessing which of the two happened would be inventing the caller's intent.
MIN_PLAUSIBLE_PRICE = Decimal(100)
MAX_PLAUSIBLE_PRICE = Decimal(10_000_000)

# The three checks and every verdict they can reach, named once so a caller
# branches on a constant rather than on a string it typed twice.
TICK = "tick"
BAND = "band"
STORE = "store"

OFF_TICK = "off_tick"
ON_TICK = "on_tick"
EXCEEDS_BAND = "exceeds_band"
WITHIN_BAND = "within_band"
STORE_DISAGREES = "store_disagrees"
STORE_AGREES = "store_agrees"
UNVERIFIED = "unverified"

SessionOpener = Callable[[], Any]


def summarise_check_price_claim(arguments: Mapping[str, Any]) -> str:
    """The rail row for one price check: which price, for which company.

    The price is the subject, so it is in the row. A reader scanning the rail
    after an answer that quoted an odd number wants to see whether that number
    was the one checked, and a row saying only the ticker cannot tell them.
    """
    symbol = str(arguments.get("symbol") or "").strip().upper()
    raw = arguments.get("price")
    price = _price(raw)
    # Vietnamese thousands separator, because this is a price on a Vietnamese
    # exchange and the reader is comparing it against one they read elsewhere.
    shown = f"{int(price):,}".replace(",", ".") if price is not None else "?"
    return f"Kiểm mức giá: {shown} — {symbol}" if symbol else f"Kiểm mức giá: {shown}"


class PriceCheckTool:
    """One tool: judge one claimed price for one symbol on one session."""

    def __init__(self, *, session_opener: SessionOpener = get_sync_db) -> None:
        self._session_opener = session_opener

    def entries(self) -> tuple[ToolEntry, ...]:
        return (
            ToolEntry(
                name="check_price_claim",
                toolset=TOOLSET,
                description=(
                    "Check a price you read somewhere else against the exchange "
                    "that would have had to produce it: its quoting step, the "
                    "daily band it could have moved inside, and the session this "
                    "system stored. Returns one verdict per check, and says "
                    "unverified where it could not check rather than treating "
                    "that as a pass. It judges prices only — a revenue, a margin "
                    "or a share count has no tick and no band."
                ),
                schema=object_schema(
                    {
                        "symbol": {
                            "type": "string",
                            "minLength": 1,
                            "description": "The ticker the price is claimed for.",
                        },
                        "price": {
                            "type": "number",
                            "exclusiveMinimum": 0,
                            "description": "The claimed price, in VND per share.",
                        },
                        "session_date": {
                            "type": "string",
                            "description": (
                                "The session the price is claimed for, as "
                                "YYYY-MM-DD. Omit it for the most recent closed "
                                "session this system holds."
                            ),
                        },
                    },
                    ("symbol", "price"),
                ),
                handler=self.check_price_claim,
                display_name="Kiểm mức giá",
                summarise=summarise_check_price_claim,
                # It reads this system's own store to judge somebody else's
                # number. The number came from outside; what comes back from here
                # did not.
                effect=ToolEffect.READ,
                idempotency=ToolIdempotency.IDEMPOTENT,
                access=ToolAccess.STORE,
                content_trust=ContentTrust.TRUSTED_STRUCTURED,
                concurrency=ToolConcurrency.SERIALIZED,
                contract_version="1",
                # Three store reads behind a synchronous Session.
                is_async=False,
                max_result_size_chars=MAX_RESULT_CHARS,
            ),
        )

    def check_price_claim(
        self, _context: ToolContext, arguments: Mapping[str, Any]
    ) -> Mapping[str, Any]:
        """The three checks for one claim, and what could not be checked and why.

        ``ToolContext`` is not consulted, and that is the difference between this
        tool and ``get_field``: the subject here is a claim somebody made, not a
        row this caller was opened for. The Analysis lane is checking a number
        the model read; there is no reason it would be about the symbol under
        analysis, and refusing the ones that are not would leave the claim
        unchecked.
        """
        symbol = _symbol(arguments.get("symbol"))
        if symbol is None:
            return _refusal(
                arguments.get("symbol"),
                "That is not a ticker this market uses, so there is no exchange "
                "whose rules the price could be checked against.",
            )
        price = _price(arguments.get("price"))
        if price is None:
            return _refusal(
                symbol,
                "price has to be a number of VND per share.",
            )

        with self._open() as session:
            return _judge(
                session,
                symbol,
                price,
                _session_date(arguments.get("session_date"), session),
            )

    @contextmanager
    def _open(self) -> Iterator[Session]:
        with self._session_opener() as session:
            yield session


def _judge(
    session: Session, symbol: str, price: Decimal, day: date | None
) -> Mapping[str, Any]:
    """Every check for one claim, each answering only for itself.

    ``day`` may be absent, and the checks then part company rather than all
    refusing together. The step a board quotes in is a property of the board, so
    the tick check still answers; the band and the stored session are both
    statements about one session and cannot. Failing all three for the want of a
    date the first one never needed would hide the check that can prove a price
    impossible on its own.
    """
    # The board question is asked as of the session where there is one and as of
    # today otherwise, because the dated migration register is what the day is
    # for and a symbol's board today is the best answer available without one.
    regime = resolve_band_regime(session, symbol, day or date.today())
    exchange = regime.exchange

    if day is None:
        anchor_day: date | None = None
        bars: Mapping[date, SessionSnapshot] = {}
    else:
        anchor_days = trading_days_before(session, day, 1)
        anchor_day = anchor_days[0] if anchor_days else None
        wanted = [d for d in (day, anchor_day) if d is not None]
        bars = sessions_on_days(session, (symbol,), wanted).get(symbol, {})

    no_session = "no session was named and the store holds none to fall back on"
    checks = [
        _tick_check(exchange, price),
        _band_check(
            exchange,
            price,
            bars.get(anchor_day),
            anchor_day,
            _rescaled_since(session, symbol, anchor_day) if anchor_day else (),
        )
        if day is not None
        else _unverified(BAND, no_session),
        _store_check(price, bars.get(day), day, _rescaled_since(session, symbol, day))
        if day is not None
        else _unverified(STORE, no_session),
    ]
    return {
        "symbol": symbol,
        "price": float(price),
        "sessionDate": None if day is None else day.isoformat(),
        "exchange": None if exchange is None else exchange.value,
        # Where the board came from, because on a bar inside the HNX→HOSE
        # transfer programme it is an assumption rather than a record, and the
        # band the assumption picks is the whole of the band check.
        "exchangeAsOf": regime.exchange_as_of.value,
        "checks": checks,
        "flags": [
            check["verdict"]
            for check in checks
            if check["verdict"] in {OFF_TICK, EXCEEDS_BAND, STORE_DISAGREES, UNVERIFIED}
        ],
    }


def _tick_check(exchange: Any, price: Decimal) -> dict[str, Any]:
    """Whether this price sits on the step the exchange quotes in.

    The one check with no store read behind it, and the one that can prove a
    price impossible on its own: a step is a rule about which numbers the
    exchange will accept at all, so a price off the step was never matched
    there, whatever any session held.
    """
    if exchange is None:
        return _unverified(TICK, "no board is known for this symbol on this session")
    if not MIN_PLAUSIBLE_PRICE <= price <= MAX_PLAUSIBLE_PRICE:
        return _unverified(
            TICK,
            "the number is outside the range of a share price in VND, so it is "
            "probably not a price and no step applies to it",
        )
    step = tick_size(exchange, price)
    remainder = price % step
    if remainder == 0:
        return {
            "check": TICK,
            "verdict": ON_TICK,
            "tickSize": float(step),
            "detail": (
                f"{price} is a multiple of the {step} VND step {exchange.value} "
                "quotes at this price level."
            ),
        }
    return {
        "check": TICK,
        "verdict": OFF_TICK,
        "tickSize": float(step),
        "detail": (
            f"{exchange.value} quotes this price level in steps of {step} VND, and "
            f"{price} is not a multiple of it. A price off the exchange's own step "
            "was never a matched price — it is a figure somebody rescaled."
        ),
    }


def _rescaled_since(session: Session, symbol: str, day: date) -> tuple[date, ...]:
    """The ex-dates that stand between this session and the newest stored one.

    Each is a moment the provider restated the whole series at, so each is a
    reason the stored prices for ``day`` are no longer the prices the exchange
    printed. Empty is the ordinary answer and the one that lets the stored check
    speak: most sessions have no entitlement behind them.

    Undated actions are deliberately not in this answer — ``for_symbol`` cannot
    return them, because an action with no date is in every window and none. An
    undated action is a gap in this control, and it is the same gap the window
    gateway already reports as ``unconfirmed_corporate_action``.
    """
    newest = latest_trading_day(session)
    if newest is None or newest <= day:
        return ()
    actions = CorporateActionStore(session).for_symbol(
        symbol, start=day + timedelta(days=1), end=newest
    )
    return tuple(
        sorted({action.ex_date for action in actions if action.ex_date is not None})
    )


def _band_check(
    exchange: Any,
    price: Decimal,
    anchor_bar: SessionSnapshot | None,
    anchor_day: date | None,
    rescaled_since: Sequence[date] = (),
) -> dict[str, Any]:
    """Whether the claim is inside the move the session was permitted.

    Anchored on the previous session's close out of the store, which is what
    HOSE and HNX compute the band from. UPCOM computes it from the prior day's
    volume-weighted average instead and the store does not hold one, so a UPCOM
    claim answers ``unverified`` rather than being judged against the wrong
    anchor.

    **The anchor has to be a price the exchange printed, and that is asked of the
    price rather than of its basis.** This check used to require
    ``price_basis == raw``, which was right about the reason and wrong about the
    test: once sessions moved to the daily spine no stored row carried that
    basis, so this branch answered ``unverified`` for every claim ever made — a
    security control switched off as a side effect, and silently, because
    ``unverified`` is an ordinary answer here.

    Two gates replace it, and both fail to ``unverified``:

    * **On the tick grid** (``price_band.off_tick_grid``). Every limit price sits
      on a tick because the exchange would not accept an order anywhere else, so
      an anchor off the grid has been multiplied since it was published and the
      band computed from it would be wrong rather than missing. Necessary and not
      sufficient — a rebased price can land back on the grid by coincidence.
    * **No entitlement in between.** The ex-dates between the anchor session and
      the one being checked, which the store check beside this one already loads.
      Not used alone: the action series covers a fraction of the market, so "no
      row" reads as "no ex-date" and would wave through the very cases the first
      gate is guessing at. Used together, each covers what the other misses.
    """
    if exchange is None:
        return _unverified(BAND, "no board is known for this symbol on this session")
    if anchor_day is None or anchor_bar is None:
        return _unverified(
            BAND, "the store holds no session before this one to anchor the band on"
        )
    if rescaled_since:
        named = ", ".join(item.isoformat() for item in rescaled_since)
        return _unverified(
            BAND,
            "a corporate action fell between the anchor session and this one "
            f"({named}), so the stored close is not the reference price the "
            "exchange set the band from",
        )
    close = anchor_bar.last_price
    if close is None:
        return _unverified(BAND, "the previous session in the store has no close")

    anchor = Decimal(str(close))
    if not MIN_PLAUSIBLE_PRICE <= anchor <= MAX_PLAUSIBLE_PRICE:
        return _unverified(BAND, "the previous session's close is not a usable anchor")

    if off_tick_grid(exchange, anchor):
        return _unverified(
            BAND,
            "the previous session's stored close is not on this board's quoting "
            "steps, so it has been rescaled since it was published and is not "
            "the reference price the band was set from",
        )

    limits = band_limits(exchange, anchor)
    inside = limits.floor <= price <= limits.ceiling
    detail = (
        f"{exchange.value} allowed this session to trade between {limits.floor} and "
        f"{limits.ceiling}, anchored on the {anchor_day.isoformat()} close of "
        f"{anchor}."
    )
    if inside:
        return {
            "check": BAND,
            "verdict": WITHIN_BAND,
            "anchor": float(anchor),
            "anchorDate": anchor_day.isoformat(),
            "ceiling": float(limits.ceiling),
            "floor": float(limits.floor),
            "detail": detail,
        }
    return {
        "check": BAND,
        "verdict": EXCEEDS_BAND,
        "anchor": float(anchor),
        "anchorDate": anchor_day.isoformat(),
        "ceiling": float(limits.ceiling),
        "floor": float(limits.floor),
        "detail": (
            f"{detail} {price} is outside that, so no order at this price could "
            "have been accepted on that session."
        ),
    }


def _store_check(
    price: Decimal,
    bar: SessionSnapshot | None,
    day: date,
    rescaled_since: Sequence[date] = (),
) -> dict[str, Any]:
    """Whether the session this system stored could contain this price.

    The traded range rather than the close, because the claim is untyped: a
    number said to be *the price on that day* may be the close, the open, an
    intraday high or a 52-week extreme, and only the range answers all four
    without guessing which was meant. Inside the range this check says
    ``store_agrees``, which is a narrower claim than *this is the right number* —
    it is *this session could have produced it*.

    Both figures travel, and the store's ``asOf``, because a disagreement the
    reader cannot see both sides of is an assertion rather than a check.

    **On an ``adjusted_at_source`` session the comparison is still made, under
    one condition.** The provider restates the whole series to the moment it
    answered, so a session with no entitlement between it and the newest stored
    one has been rescaled by nothing: its stored prices *are* the prices the
    exchange printed. ``rescaled_since`` carries the ex-dates that fall in
    between, and one of them is enough to withhold the verdict — the stored
    prices are then a real measurement of a different quantity, and no factor
    this system holds can be trusted to undo the provider's own.

    This check is a security control: the price it is handed came out of web
    content nobody vouches for. Losing it to a source change would have left the
    tick grid as the only thing standing between a fabricated but plausible price
    and an answer, so the condition above is written out rather than assumed.
    """
    if bar is None:
        return _unverified(STORE, f"this system holds no session for {day.isoformat()}")
    high = bar.high_price
    low = bar.low_price
    if high is None or low is None:
        return _unverified(
            STORE, "the stored session has no traded range to compare against"
        )
    stored = {
        "low": low,
        "high": high,
        "close": bar.last_price,
        "priceBasis": bar.price_basis.value,
    }
    if bar.price_basis is not PriceBasis.RAW and rescaled_since:
        named = ", ".join(item.isoformat() for item in rescaled_since)
        return _unverified(
            STORE,
            "the stored session is adjusted at source and the provider has "
            f"rescaled it since — {named} — so its prices and a published price "
            "are not the same quantity",
            extra={
                "stored": stored,
                "asOf": day.isoformat(),
                "rescaledSince": [item.isoformat() for item in rescaled_since],
            },
        )

    # What the provider's own rounding can move a price by. Equity history
    # arrives in thousands of dong and is scaled once at ingest, so today this
    # absorbs nothing; it is here because the check is a comparison between two
    # sources' arithmetic and a comparison with no stated tolerance is one whose
    # tolerance is nobody's decision.
    slack = Decimal(str(high)) * STORE_TOLERANCE
    inside = Decimal(str(low)) - slack <= price <= Decimal(str(high)) + slack
    return {
        "check": STORE,
        "verdict": STORE_AGREES if inside else STORE_DISAGREES,
        "claimed": float(price),
        "stored": stored,
        "tolerancePct": float(STORE_TOLERANCE * 100),
        "asOf": day.isoformat(),
        "detail": (
            f"This system stored {day.isoformat()} as trading between {low} and "
            f"{high}."
            if inside
            else (
                f"This system stored {day.isoformat()} as trading between {low} and "
                f"{high}, which does not contain {price}. Where the two differ the "
                "stored session is the one that was normalised and dated."
            )
        ),
    }


def _unverified(
    check: str, reason: str, *, extra: Mapping[str, Any] | None = None
) -> dict[str, Any]:
    """A check that did not run, said so, and is not a pass.

    Its own verdict rather than a null, so a reader cannot fold it into the
    checks that did run. Every branch that reaches this has lost an input the
    verdict is made of, and none of them has learned anything about the price.
    """
    result: dict[str, Any] = {
        "check": check,
        "verdict": UNVERIFIED,
        "reason": reason,
        "detail": f"Not checked: {reason}. This is not a pass.",
    }
    if extra:
        result.update(extra)
    return result


def _refusal(raw: Any, sentence: str) -> dict[str, Any]:
    """An argument the tool cannot work from, answered so the model can read it.

    A returned value rather than a raise: the model asked a well-formed question
    about a badly-formed subject, and what it needs back is the reason, not a
    tool failure it will read as the tool being broken.
    """
    return {
        "symbol": None if raw is None else str(raw)[:32],
        "price": None,
        "sessionDate": None,
        "exchange": None,
        "checks": [],
        "flags": [UNVERIFIED],
        "detail": sentence,
    }


def _symbol(raw: Any) -> str | None:
    if not isinstance(raw, str) or not raw.strip():
        return None
    try:
        return validate_symbol(raw)
    except Exception:  # noqa: BLE001 - a malformed ticker is an answer, not a fault
        return None


def _price(raw: Any) -> Decimal | None:
    if isinstance(raw, bool) or raw is None:
        return None
    try:
        value = Decimal(str(raw))
    except (InvalidOperation, ValueError):
        return None
    return value if value > 0 else None


def _session_date(raw: Any, session: Session) -> date | None:
    """The session the claim is about: the one named, or the newest one closed.

    A named date is taken as given. An omitted one resolves to the latest
    session the store holds rather than to today, because today may not have
    closed and a claim checked against a session still trading would be checked
    against a moving band.
    """
    if isinstance(raw, str) and raw.strip():
        try:
            return date.fromisoformat(raw.strip()[:10])
        except ValueError:
            logger.debug("check_price_claim was given %r as a session date", raw)
            return None
    return latest_trading_day(session)


def register_price_check_tool(**kwargs: Any) -> tuple[ToolEntry, ...]:
    """Register the price check and hand the registration back to the caller."""
    tool = PriceCheckTool(**kwargs)
    return tuple(register(entry) for entry in tool.entries())


__all__ = [
    "BAND",
    "EXCEEDS_BAND",
    "MAX_PLAUSIBLE_PRICE",
    "MAX_RESULT_CHARS",
    "MIN_PLAUSIBLE_PRICE",
    "OFF_TICK",
    "ON_TICK",
    "STORE",
    "STORE_AGREES",
    "STORE_DISAGREES",
    "TICK",
    "TOOLSET",
    "UNVERIFIED",
    "WITHIN_BAND",
    "PriceCheckTool",
    "register_price_check_tool",
    "summarise_check_price_claim",
]
