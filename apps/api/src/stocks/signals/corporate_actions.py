"""What a declared corporate action means, and whether it may be believed.

A raw price store is only comparable across a split, a bonus or a dividend if the
series of actions is held durably and read at the seam (``docs/adr/0006``). This
module is the reading half: it turns the provider's event rows into a kind, an
**Adjustment Factor**, and a verdict on whether the action's ex-date is real.

Three rules carry the weight, and each of them exists because the obvious
shortcut produces a confident wrong number.

**The factor comes from the declared terms, never from the gap.** An ex-date's
raw price gap is the entitlement and that session's ordinary move together, so a
factor measured from it folds one day of news into the adjustment permanently.
It is also circular: an unexplained gap is the very signal that an action is
missing, so using the gap to size the action would make every missing action
explain itself.

**The gap only confirms the date.** An action with no ex-date, or one the prices
contradict, is ``unconfirmed``: it may not drive arithmetic, and it leaves a
window that contains it degraded rather than adjusted. This is a live case, not a
defensive one — TCB's 2026 bonus issue at ratio 0.6 arrives with a public date
and no ex-date at all.

**A ratio is not a ratio everywhere.** The feed puts a cash dividend's payment
into ``exercise_ratio`` as a fraction of the 10,000 VND par — 700 VND arrives as
0.07 — beside share issues where the same column really is shares per share.
Read by name rather than by kind, a 700-dong dividend becomes a 7% bonus issue.

## What the arithmetic is

For one ex-date, with every action on it taken together:

    reference = (previous_close − cash_per_share + Σ rightsᵢ × subscriptionᵢ)
                ÷ (1 + Σ ratio_of_every_entitling_issue)
    factor    = reference ÷ previous_close

Blending is the point rather than a detail. ACB's 2025-05-23 ex-date is a 15%
stock dividend *and* a 1,000 VND cash dividend, and the two together give a
factor of 0.8356 where the stock dividend alone implies 0.8696 — a 4% error, on
every price before that date, in the direction that looks plausible.

## What it refuses

A rights issue is priced at a subscription the feed does not carry, and the par
value it is usually set at is a convention rather than a fact about the row. So a
rights issue is stored, confirmed like any other action, and then refuses to
produce a factor: MBB's 2026-08-11 ex-date is measurably (24,250 + 0.10 × 10,000)
÷ 1.25, and that 10,000 is knowledge from outside the feed.
"""

from __future__ import annotations

import logging
import re
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from enum import Enum

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.stocks.models import CorporateAction

from ..providers import CorporateActionEvent, ProviderSource
from .issues import SignalIssue
from .price_band import detect_limit_lock

logger = logging.getLogger(__name__)


class ActionKind(str, Enum):
    """What a declared action does to a shareholder's holding.

    The feed's ``event_code`` does not answer this: ``ISS`` covers a stock
    dividend, a bonus issue, a rights issue, an ESOP grant and a private
    placement alike, and only the free-text title tells them apart. So the kind
    is parsed once, at write time, and stored — a reader deciding it again would
    be re-deriving the one field every downstream rule turns on.
    """

    # Money out of the company, share count untouched.
    CASH_DIVIDEND = "cash_dividend"

    # Free shares to existing holders. The two names are the feed's, for the same
    # arithmetic; both are kept because relabelling a row would make the stored
    # title and the stored kind disagree.
    STOCK_DIVIDEND = "stock_dividend"
    BONUS_ISSUE = "bonus_issue"
    STOCK_SPLIT = "stock_split"

    # Shares offered to existing holders at a subscription price the feed does
    # not carry. Entitling, and therefore a share-count change; not priceable.
    RIGHTS_ISSUE = "rights_issue"

    # Shares issued to somebody other than the existing holders. Dilutive over
    # time, but not a rescaling of anyone's holding and not an ex-date: the feed
    # leaves these without one, as measured on TCB and MBB.
    ESOP = "esop"
    PRIVATE_PLACEMENT = "private_placement"

    # A row whose wording this system does not recognise. Never guessed into one
    # of the above: a share issue read as a cash dividend rescales nothing and a
    # cash dividend read as a bonus rescales everything.
    UNKNOWN = "unknown"


# The wording each kind arrives under, in the order it is tested. Ordered rather
# than a mapping because the phrases overlap — "Stock dividend" and "Bonus Issue"
# would both match a looser rule for the other — and because the specific cases
# have to be tried before the general one.
#
# Measured against the live feed for TCB, MBB and ACB in 2024-2026; every phrase
# below is one this system has actually seen, not one it expects.
_TITLE_PATTERNS: tuple[tuple[re.Pattern[str], ActionKind], ...] = (
    (re.compile(r"\bcash dividend\b", re.I), ActionKind.CASH_DIVIDEND),
    (re.compile(r"\bstock dividend\b", re.I), ActionKind.STOCK_DIVIDEND),
    (re.compile(r"\bbonus\b", re.I), ActionKind.BONUS_ISSUE),
    (re.compile(r"\brights? issue\b", re.I), ActionKind.RIGHTS_ISSUE),
    (re.compile(r"\besop\b", re.I), ActionKind.ESOP),
    (re.compile(r"\bprivate placement", re.I), ActionKind.PRIVATE_PLACEMENT),
    (re.compile(r"\bsplit\b", re.I), ActionKind.STOCK_SPLIT),
)

# The event codes this system reasons about. ``DIV`` is a cash payment and
# ``ISS`` is a share issue of some kind; everything else in the feed's dividend
# category is left ``UNKNOWN`` rather than assigned the arithmetic of a
# neighbouring code.
EVENT_CODE_CASH = "DIV"
EVENT_CODE_SHARE_ISSUE = "ISS"

# The kinds that multiply a holding: one share becomes 1 + ratio shares. This is
# the distinction ADR-0006 makes a downstream field depend on — a share-count
# change breaks every ``*_volume`` field and leaves every ``*_value_vnd`` field
# alone — so it is a property of the kind rather than of the event code.
_ENTITLING_KINDS = frozenset(
    {
        ActionKind.STOCK_DIVIDEND,
        ActionKind.BONUS_ISSUE,
        ActionKind.STOCK_SPLIT,
        ActionKind.RIGHTS_ISSUE,
    }
)


class Confirmation(str, Enum):
    """Whether this action's ex-date is corroborated by the prices around it."""

    CONFIRMED = "confirmed"
    UNCONFIRMED = "unconfirmed"


class ConfirmationReason(str, Enum):
    """Why an action is still unconfirmed, which is not one question but four.

    Kept apart because the fixes differ. A missing ex-date waits on the feed; a
    session the store does not hold waits on a Warm-up; an effect too small to
    show against the band will never be corroborable by a gap at all and is not
    a defect; and a session that moved inside its band when the terms say it
    should not have is the one case that says the row itself is wrong.
    """

    # No ex-date to test. The feed left it null.
    NO_EX_DATE = "no_ex_date"

    # The band regime could not decide the session — an unstored anchor, a
    # non-raw pair, an UPCOM anchor that is not reconstructible. The Signal Issue
    # that says which travels in the log, not in this column: it is the band's
    # vocabulary and this is the action's.
    SESSION_UNDECIDED = "session_undecided"

    # The action's declared terms move the reference by less than the band
    # permits, so no gap could distinguish it from an ordinary session. A 700 VND
    # dividend on a 25,000 VND share is 2.8% against a ±7% band.
    EFFECT_WITHIN_BAND = "effect_within_band"

    # The session did not move the way an action of these terms would have made
    # it move. The date is contradicted rather than merely unproven.
    NO_CORROBORATING_GAP = "no_corroborating_gap"


@dataclass(frozen=True)
class ActionTerms:
    """One action reduced to what the arithmetic reads, and nothing else."""

    kind: ActionKind
    ratio: Decimal | None
    cash_per_share: Decimal | None

    @property
    def changes_share_count(self) -> bool:
        return self.kind in _ENTITLING_KINDS


@dataclass(frozen=True)
class FactorReading:
    """The Adjustment Factor for one ex-date, or the reason there is none.

    ``share_count_ratio`` travels beside the factor rather than being derived
    from it, because the two are different numbers and confusing them is the
    error ADR-0006 spends a section on: ACB's 2025 ex-date multiplies the share
    count by 1.15 while multiplying past prices by 0.8356. A quantity rescaled by
    the price factor would be wrong by exactly the cash dividend.
    """

    ex_date: date
    factor: Decimal | None
    share_count_ratio: Decimal | None
    refusal: SignalIssue | None

    @property
    def usable(self) -> bool:
        return self.factor is not None


def classify(event_code: str, title: str) -> ActionKind:
    """Read the kind of an action out of its code and its wording.

    The code narrows and the title decides. A ``DIV`` row is a cash dividend
    whatever its wording, because that code carries a payment and nothing else;
    an ``ISS`` row needs the title, and one whose title says nothing this system
    recognises stays ``UNKNOWN`` rather than defaulting to the commonest kind.
    """
    code = event_code.strip().upper()
    for pattern, kind in _TITLE_PATTERNS:
        if pattern.search(title):
            if code == EVENT_CODE_CASH and kind is not ActionKind.CASH_DIVIDEND:
                # A payment row whose title reads like a share issue is a row
                # this system has not seen and cannot price. Refusing is the
                # whole point: taking the title would apply a share ratio to a
                # cash payment.
                return ActionKind.UNKNOWN
            return kind
    if code == EVENT_CODE_CASH:
        return ActionKind.CASH_DIVIDEND
    return ActionKind.UNKNOWN


def terms_of(action: CorporateAction) -> ActionTerms:
    """What a stored row declares, read by kind rather than by column name.

    This is where the feed's overloaded ``exercise_ratio`` is disarmed. On a cash
    dividend that column holds the payment as a fraction of par, so it is ignored
    entirely and the payment is taken from ``value_per_share``; on a share issue
    it is the share ratio and ``value_per_share`` is empty.
    """
    kind = ActionKind(action.kind)
    if kind is ActionKind.CASH_DIVIDEND:
        return ActionTerms(
            kind=kind,
            ratio=None,
            cash_per_share=_decimal(action.value_per_share),
        )
    return ActionTerms(
        kind=kind,
        ratio=_decimal(action.exercise_ratio),
        cash_per_share=None,
    )


def adjustment_factor(
    actions: Sequence[CorporateAction],
    previous_close: Decimal,
) -> FactorReading:
    """The factor that makes prices before this ex-date comparable with prices after.

    Every action sharing the ex-date is applied at once, which is what makes the
    answer right: an ex-date carrying a stock dividend and a cash dividend is one
    reference-price calculation, not two factors multiplied together.

    Refuses rather than approximates. One unconfirmed action on the date, one
    kind this system cannot read, one set of terms with a number missing, and the
    whole date is refused — a factor computed from the actions that happened to
    be complete would silently under-adjust, and under-adjustment is
    indistinguishable from a real price move.
    """
    if not actions:
        raise ValueError("an adjustment factor needs at least one action")
    if previous_close <= 0:
        raise ValueError("an adjustment factor needs a positive previous close")

    ex_dates = {action.ex_date for action in actions}
    if len(ex_dates) != 1 or None in ex_dates:
        raise ValueError(
            "an adjustment factor is computed for one ex-date, and every action "
            "on it must carry that date"
        )
    ex_date = ex_dates.pop()
    assert ex_date is not None  # narrowed by the check above

    def refuse(reason: SignalIssue) -> FactorReading:
        return FactorReading(
            ex_date=ex_date,
            factor=None,
            share_count_ratio=None,
            refusal=reason,
        )

    if any(action.confirmation != Confirmation.CONFIRMED.value for action in actions):
        return refuse(SignalIssue.UNCONFIRMED_CORPORATE_ACTION)

    issued = Decimal(0)
    cash = Decimal(0)
    for action in actions:
        terms = terms_of(action)
        if terms.kind is ActionKind.UNKNOWN:
            return refuse(SignalIssue.CORPORATE_ACTION_TERMS_INCOMPLETE)
        if terms.kind is ActionKind.RIGHTS_ISSUE:
            # The subscription price is not in the feed, and the par value it is
            # conventionally set at is knowledge from outside this row. Guessing
            # it would put a plausible number on an entitlement whose whole size
            # depends on it.
            return refuse(SignalIssue.CORPORATE_ACTION_TERMS_INCOMPLETE)
        if terms.kind is ActionKind.CASH_DIVIDEND:
            if terms.cash_per_share is None:
                return refuse(SignalIssue.CORPORATE_ACTION_TERMS_INCOMPLETE)
            cash += terms.cash_per_share
            continue
        if terms.kind in (ActionKind.ESOP, ActionKind.PRIVATE_PLACEMENT):
            # Neither entitles an existing holder to anything, so neither moves
            # the exchange's reference price. Skipped explicitly rather than
            # falling through to the ratio arithmetic below, where their ratio
            # would rescale a history that nothing rescaled.
            continue
        if terms.ratio is None:
            return refuse(SignalIssue.CORPORATE_ACTION_TERMS_INCOMPLETE)
        issued += terms.ratio

    reference = (previous_close - cash) / (Decimal(1) + issued)
    if reference <= 0:
        # A dividend larger than the share price is not an adjustment, it is a
        # row read wrong — a payment in the wrong unit is the usual way.
        return refuse(SignalIssue.CORPORATE_ACTION_TERMS_INCOMPLETE)

    return FactorReading(
        ex_date=ex_date,
        factor=reference / previous_close,
        share_count_ratio=Decimal(1) + issued,
        refusal=None,
    )


@dataclass(frozen=True)
class ConfirmationVerdict:
    """One ex-date judged against the prices around it."""

    confirmation: Confirmation
    reason: ConfirmationReason | None


def confirm_ex_date(
    session: Session,
    symbol: str,
    ex_date: date,
    actions: Sequence[CorporateAction],
) -> ConfirmationVerdict:
    """Decide whether the prices around this date corroborate an action on it.

    The band regime for that session is what makes the question answerable: a
    session may move ±7% on HOSE and ±15% on UPCOM for no reason at all, so a
    move inside its band is never evidence of anything, and a move outside it
    cannot be an ordinary session. That is the whole test, and it is deliberately
    the only thing the prices are asked — the terms supply the factor, and the
    prices supply the date.

    Two cases are separated that a looser test would merge. An action whose
    declared terms move the reference by *less* than the band permits could never
    show up as a gap, so it is left unconfirmed with ``EFFECT_WITHIN_BAND``
    rather than reported as contradicted: nothing is wrong with the row, the
    instrument simply does not reach. An action whose terms say the session
    should have gapped, on a session that did not, is contradicted.
    """
    reading = detect_limit_lock(session, symbol, ex_date)
    if reading.degraded_reason is SignalIssue.PRICE_MOVE_EXCEEDS_BAND:
        return ConfirmationVerdict(Confirmation.CONFIRMED, None)

    if reading.degraded_reason is not None or reading.limits is None:
        # The session could not be measured at all: no stored anchor, a mixed
        # price basis, an UPCOM band whose anchor is not in the store. Logged
        # with the band's own vocabulary, because that is the reason a reader
        # would need to act on.
        logger.info(
            "Cannot confirm %s on %s yet: the band reading is %s",
            symbol,
            ex_date,
            reading.degraded_reason.value if reading.degraded_reason else "unusable",
        )
        return ConfirmationVerdict(
            Confirmation.UNCONFIRMED, ConfirmationReason.SESSION_UNDECIDED
        )

    if reading.anchor is None:
        return ConfirmationVerdict(
            Confirmation.UNCONFIRMED, ConfirmationReason.SESSION_UNDECIDED
        )

    reference = _reference_from_terms(actions, reading.anchor)
    if reference is None:
        # Terms this system cannot price cannot say what the session should have
        # done, so the session cannot contradict them either.
        return ConfirmationVerdict(
            Confirmation.UNCONFIRMED, ConfirmationReason.EFFECT_WITHIN_BAND
        )

    if reference >= reading.limits.floor:
        return ConfirmationVerdict(
            Confirmation.UNCONFIRMED, ConfirmationReason.EFFECT_WITHIN_BAND
        )
    return ConfirmationVerdict(
        Confirmation.UNCONFIRMED, ConfirmationReason.NO_CORROBORATING_GAP
    )


def _reference_from_terms(
    actions: Sequence[CorporateAction],
    previous_close: Decimal,
) -> Decimal | None:
    """The reference these terms imply, ignoring whether they are confirmed yet.

    Confirmation is what this is being computed *for*, so reading it back here
    would make every action's first pass refuse itself.
    """
    priced = [
        action
        for action in actions
        if ActionKind(action.kind)
        not in (
            ActionKind.UNKNOWN,
            ActionKind.RIGHTS_ISSUE,
            ActionKind.ESOP,
            ActionKind.PRIVATE_PLACEMENT,
        )
    ]
    if not priced or len(priced) != len(actions):
        # A date carrying one unpriceable action is unpriceable as a whole: the
        # missing term is part of the same reference calculation.
        return None

    issued = Decimal(0)
    cash = Decimal(0)
    for action in priced:
        terms = terms_of(action)
        if terms.kind is ActionKind.CASH_DIVIDEND:
            if terms.cash_per_share is None:
                return None
            cash += terms.cash_per_share
            continue
        if terms.ratio is None:
            return None
        issued += terms.ratio

    if issued == 0 and cash == 0:
        return None
    reference = (previous_close - cash) / (Decimal(1) + issued)
    return reference if reference > 0 else None


class CorporateActionStore:
    """Read and write the durable action series for one symbol at a time."""

    def __init__(self, session: Session) -> None:
        self.session = session

    def save(
        self,
        event: CorporateActionEvent,
        source: ProviderSource,
        observed_at: datetime,
    ) -> CorporateAction:
        """Write one declared action, replacing the row it is a re-read of.

        Idempotent on the identity the table enforces, so a collector that walks
        a company's whole event history every run leaves one row per action
        rather than one row per run. A re-read updates the terms in place: the
        feed does fill in an ex-date that was null, and the row that gains one
        has to become the same row that was already there, not a second one
        beside it.

        Confirmation is deliberately not touched here. An action is confirmed
        against price history that arrives later than the announcement, and a
        re-read that reset the verdict would un-confirm every action every run.
        """
        kind = classify(event.event_code, event.title)
        existing = self._existing(event, kind)

        if existing is None:
            row = CorporateAction(
                symbol=event.symbol,
                ex_date=event.ex_date,
                event_code=event.event_code,
                title=event.title,
                record_date=event.record_date,
                public_date=event.public_date,
                kind=kind.value,
                exercise_ratio=event.exercise_ratio,
                value_per_share=event.value_per_share,
                changes_share_count=kind in _ENTITLING_KINDS,
                confirmation=Confirmation.UNCONFIRMED.value,
                confirmation_reason=(
                    ConfirmationReason.NO_EX_DATE.value
                    if event.ex_date is None
                    else None
                ),
                source=source.value,
                observed_at=observed_at,
            )
            self.session.add(row)
            self.session.flush()
            return row

        gained_ex_date = existing.ex_date is None and event.ex_date is not None
        existing.ex_date = event.ex_date
        existing.title = event.title
        existing.record_date = event.record_date
        existing.public_date = event.public_date
        existing.exercise_ratio = event.exercise_ratio
        existing.value_per_share = event.value_per_share
        existing.changes_share_count = kind in _ENTITLING_KINDS
        existing.source = source.value
        existing.observed_at = observed_at
        if gained_ex_date and existing.confirmation != Confirmation.CONFIRMED.value:
            # The one reason to clear a stored reason: it said "no ex-date", and
            # now there is one. Left alone it would outlive the condition it
            # describes.
            existing.confirmation_reason = None
        self.session.flush()
        return existing

    def _existing(
        self,
        event: CorporateActionEvent,
        kind: ActionKind,
    ) -> CorporateAction | None:
        """Find the row this event is a re-read of, under either identity.

        An undated row is matched on its public date, and it is matched *before*
        the dated lookup would fail, so an action that has since gained an
        ex-date updates the row it was announced as rather than forking into two.
        """
        conditions = [
            CorporateAction.symbol == event.symbol,
            CorporateAction.event_code == event.event_code,
            CorporateAction.kind == kind.value,
        ]
        if event.ex_date is not None:
            dated = self.session.execute(
                select(CorporateAction).where(
                    *conditions, CorporateAction.ex_date == event.ex_date
                )
            ).scalar_one_or_none()
            if dated is not None:
                return dated

        if event.public_date is None:
            return None
        return self.session.execute(
            select(CorporateAction).where(
                *conditions,
                CorporateAction.ex_date.is_(None),
                CorporateAction.public_date == event.public_date,
            )
        ).scalar_one_or_none()

    def for_symbol(
        self,
        symbol: str,
        start: date | None = None,
        end: date | None = None,
    ) -> tuple[CorporateAction, ...]:
        """This symbol's dated actions across a window, oldest first.

        Undated actions are not in this answer and cannot be: a window is a range
        of dates, and an action with no date is in every window and none. They
        are reached through ``undated`` instead, which is what a caller asking
        "is anything about this symbol unaccounted for" needs.
        """
        conditions = [
            CorporateAction.symbol == symbol.upper(),
            CorporateAction.ex_date.is_not(None),
        ]
        if start is not None:
            conditions.append(CorporateAction.ex_date >= start)
        if end is not None:
            conditions.append(CorporateAction.ex_date <= end)
        rows = self.session.execute(
            select(CorporateAction)
            .where(*conditions)
            .order_by(CorporateAction.ex_date.asc(), CorporateAction.id.asc())
        ).scalars()
        return tuple(rows)

    def undated(self, symbol: str) -> tuple[CorporateAction, ...]:
        """The actions held for this symbol that carry no ex-date at all."""
        rows = self.session.execute(
            select(CorporateAction)
            .where(
                CorporateAction.symbol == symbol.upper(),
                CorporateAction.ex_date.is_(None),
            )
            .order_by(CorporateAction.public_date.asc(), CorporateAction.id.asc())
        ).scalars()
        return tuple(rows)

    def confirm_pending(self, symbol: str) -> int:
        """Judge every dated action of this symbol that is not confirmed yet.

        Grouped by ex-date rather than run per row, because the test is about the
        session and the session was moved by everything on that date at once. A
        confirmed action is never re-judged: the verdict was made against the raw
        prices of that session, and those do not change.
        """
        pending = [
            action
            for action in self.for_symbol(symbol)
            if action.confirmation != Confirmation.CONFIRMED.value
        ]
        if not pending:
            return 0

        by_date: dict[date, list[CorporateAction]] = {}
        for action in pending:
            assert action.ex_date is not None  # for_symbol excludes the undated
            by_date.setdefault(action.ex_date, []).append(action)

        confirmed = 0
        for ex_date in sorted(by_date):
            # Every action on the date, not only the pending ones: the reference
            # a session moved to was set by all of them together.
            on_date = [
                action
                for action in self.for_symbol(symbol, start=ex_date, end=ex_date)
            ]
            verdict = confirm_ex_date(self.session, symbol, ex_date, on_date)
            for action in by_date[ex_date]:
                action.confirmation = verdict.confirmation.value
                action.confirmation_reason = (
                    verdict.reason.value if verdict.reason is not None else None
                )
                if verdict.confirmation is Confirmation.CONFIRMED:
                    confirmed += 1
        self.session.flush()
        return confirmed


def previous_close(session: Session, symbol: str, ex_date: date) -> Decimal | None:
    """The raw close the exchange's reference for this ex-date was measured from.

    Reads the same stored series the band regime does, and refuses the same
    things: a non-raw session is not an anchor, because an ``adjusted_at_source``
    close has already had this very action folded into it and anchoring to it
    would adjust the same event twice.
    """
    reading = detect_limit_lock(session, symbol, ex_date)
    if reading.anchor is not None:
        return reading.anchor
    return None


def _decimal(value: object) -> Decimal | None:
    """A stored number as an exact decimal, or nothing.

    Through ``str`` deliberately: SQLite hands a ``Numeric`` column back as a
    float, and ``Decimal(0.15)`` is not 0.15. Going via the repr keeps the number
    the one that was written.
    """
    if value is None:
        return None
    return Decimal(str(value))
