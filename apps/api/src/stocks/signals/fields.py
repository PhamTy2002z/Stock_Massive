"""What a model-visible number has to declare before it is one.

A **Signal Field** is one number and the unit the statistical bar applies to —
not the tool that returns it, because one tool returns fields of different kinds
(``docs/adr/0010``). ``risk_metrics`` holds a realized-volatility estimator with
no threshold and nothing to fire beside a drawdown judged against a benchmark,
which does fire. Applied per tool, the bar would either force meaningless null
runs on the estimator or exempt the whole cluster because one of its fields is
descriptive.

So the bar is declared here, per field, and it bites in three places rather than
in a prompt:

**At declaration.** ``SignalField`` has no defaults. A field that forgets to say
what its unit is, or what reading of it is sanctioned, is a ``TypeError`` at
import rather than a gap a reviewer has to notice. A ``signal`` without a
threshold and a measured null, an ``estimator`` that never ships uncertainty, a
``descriptive`` field declaring a direction-bearing key — each is refused where
it is written.

**At return.** ``FieldValue`` checks that what came back matches what the kind
promised: an estimator carrying its standard error or interval, a percentile
carrying its ``n`` and its cutoff date, and no descriptive field carrying a key
that points anywhere.

**At serialization.** The tool layer serializes registered fields only, which is
why an unregistered computation needs no prohibition — it simply has no route to
a model.

## Why ``claim`` is a type and not a label

In v1 every field is ``descriptive``, and ``descriptive`` is a schema constraint:
a descriptive field may not return a direction-bearing key at all — no
``direction``, no ``signal: buy | sell``, no ``expected_return``. Requiring a
measured net-of-cost forward-return harness before catalog entry would have shipped
an empty catalog, so the claim became a contract field instead, and ``predictive``
unlocks only behind that harness.

The bar does not police language, and is not trying to: a model reading a number
will narrate it whatever the schema omits. What it does is make the violation
detectable, and hand three things onward so the statistics are not re-litigated
downstream — ``interpretation`` as the only sanctioned reading, the ``claim``
flag, and the list of fields an answer rested on.
"""

from __future__ import annotations

import math
from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, Any

from .issues import SignalIssue


class BarProjection(str, Enum):
    """Which stored measurement makes a session usable for a computation.

    Declared on the field rather than chosen by whoever serves it. The two
    projections differ in what they refuse: the price one admits a session with
    a close and enforces the price-basis and band contract over the window; the
    volume one admits a session with a traded quantity and does not refuse a
    count for a condition about prices.

    It lives here, beside the declarations, and not in ``bars`` where the
    gateway reads it, because ``bars`` imports this module. That direction is
    the right way round: a field says what it needs, and the gateway obeys.
    """

    PRICE = "price"
    VOLUME = "volume"


if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to a checker
    from .bars import BarFrame, WindowHealth
    from .earnings import QuarterlyStatements
    from .fundamentals import FundamentalStanding
    from .reference import ForeignRoomStanding

# The catalog-wide ceiling on how often a `signal` field may fire on data that
# contains no signal. Fixed here rather than declared per tool: a self-declared
# rate is exactly the failure mode measured in the external library this system
# rejected, and it only ever drifts upward when an author wants theirs shipped.
CATALOG_NULL_FPR_CEILING = 0.01

# The share of a window that may be limit-locked or otherwise unreadable before
# the answer is degraded rather than normal (``docs/adr/0010``). A locked session
# has no range at all, so past this the estimate is measuring the band rather
# than the market.
DEGRADED_LIMIT_LOCK_SHARE = 0.20

# How much of a sample has to survive exclusion before a percentile taken over
# it means anything (``docs/adr/0010``). A share of the sample plus an absolute
# floor, and both halves are load-bearing:
#
# * A **share** rather than a count, because the count that matters is relative.
#   A Universe of thirty answering with twenty-seven is a ranking over almost
#   everything; a Universe of three hundred answering with twenty-seven is a
#   ranking over a ninth of it wearing the same clothes.
# * A **floor**, because no share rescues a small sample. Sixty percent of ten is
#   six, and a position among six names is a rank, not a distribution.
#
# It was a constant 30, and against a Universe of exactly 30 that left no
# tolerance at all: one newly listed symbol without the history a field needs
# refused the field for every symbol, including the twenty-nine that had it. The
# sample size and the exclusions already travel with every percentile
# (``FieldValue.extras``), so a reader can see a thinner sample rather than
# having to be protected from one by a blank.
PERCENTILE_MIN_SAMPLE_SHARE = 0.6
PERCENTILE_ABSOLUTE_FLOOR = 15


def min_sample_for(sample_size: int) -> int:
    """How many members must answer before a percentile over them is served.

    Taken from the sample that was *asked for*, not from the survivors: a floor
    derived from what survived would be satisfied by definition.

    Deliberately not clamped down to ``sample_size``. A sample smaller than the
    absolute floor can never answer, and clamping would quietly turn a
    three-symbol request into a three-symbol percentile.
    """
    return max(
        math.ceil(PERCENTILE_MIN_SAMPLE_SHARE * max(0, sample_size)),
        PERCENTILE_ABSOLUTE_FLOOR,
    )

# Keys a `descriptive` field may not return, whatever it calls itself. Matched on
# the **whole key**, so `expected_return` is refused and `return_window_days` is
# not — a substring rule would refuse half the honest metadata in this package.
# The cost of that choice is real and is accepted rather than hidden: a field
# determined to point somewhere can spell it `direction_of_travel` and pass. The
# list is the ADR's three plus the wordings a field would reach for next once
# those three are taken, and it is a tripwire against drift rather than a proof
# of its absence — what actually holds the line is `claim` being a type and the
# nightly artifact carrying the fields it rested on.
DIRECTION_BEARING_KEYS = frozenset(
    {
        "action",
        "bias",
        "buy",
        "call",
        "direction",
        "expected_return",
        "forecast",
        "outlook",
        "position",
        "prediction",
        "recommendation",
        "sell",
        "signal",
        "stance",
        "target_price",
        "verdict",
        "view",
    }
)


class FieldKind(str, Enum):
    """What sort of number this is, which decides the bar it must clear."""

    # A point estimate with a sampling distribution behind it. Must ship a
    # standard error or a confidence interval: a realized volatility printed
    # without one invites a comparison between two numbers that are the same
    # number.
    ESTIMATOR = "estimator"

    # A cross-sectional position. Must ship the ``n`` it was ranked among and the
    # date the ranking was cut at — a percentile over eleven names is a rank
    # dressed up as a distribution.
    PERCENTILE = "percentile"

    # A number with a threshold, which can therefore fire. Must ship the full
    # null: two calibrations, the published rate the maximum of them, and a
    # threshold frozen from the null rather than calibrated at runtime.
    SIGNAL = "signal"

    # A number that is exact for what it describes, so there is no sampling
    # distribution behind it to report. Two shapes qualify and both are here for
    # the same reason. A deterministic transform of the window admits a caller
    # and a model to the market's shared vocabulary without turning its
    # conventional cutoffs into a statistical claim; a figure read straight from
    # a stored provider row — a foreign ownership room against its cap — is
    # exact for the date it was read, and the honest caveat on it is its age
    # rather than an error bar. Neither carries a threshold, and neither asserts
    # any predictive value at all.
    VOCABULARY = "vocabulary"


class Claim(str, Enum):
    """What this field asserts about the future, which in v1 is nothing."""

    DESCRIPTIVE = "descriptive"
    PREDICTIVE = "predictive"


class FieldSource(str, Enum):
    """Where the number comes from, which decides what it is exempt from.

    A ``stored`` provider figure has no threshold and therefore no false-positive
    rate to measure, so it is exempt from the null — and from nothing else. It
    still declares its unit, its sign and its interpretation, and it additionally
    carries a staleness stamp, because a five-month-old quarterly figure narrated
    as current is a false positive by another mechanism.
    """

    COMPUTED = "computed"
    STORED = "stored"


class Sign(str, Enum):
    """The sign convention, which no figure may be published without.

    Its own declaration rather than a note in the interpretation, because the
    failure it guards against is a reader taking a magnitude for a direction: a
    drawdown is negative by convention and a volatility never is, and a field
    that does not say which is being read as both.
    """

    SIGNED = "signed"
    NON_NEGATIVE = "non_negative"
    NON_POSITIVE = "non_positive"


class Unit(str, Enum):
    """What the number is measured in.

    ``VND`` and ``SHARES`` are the money/quantity split the market contracts
    already make, and keeping it here rather than in prose is what lets the
    serving layer act on it: a share-denominated figure changes unit partway
    through a window that crosses a share-count-changing action and a
    money-denominated one does not, so the unit is what decides whether a window
    degrades a field (``docs/adr/0006``).
    """

    Z_SCORE = "z_score"
    PERCENT = "percent"
    PERCENT_ANNUALIZED = "percent_annualized"
    RATIO = "ratio"
    SESSIONS = "sessions"
    VND = "vnd"
    SHARES = "shares"
    # Amihud's illiquidity: percent of price moved per billion dong traded. Its
    # own unit rather than a ratio, because the number is meaningless without
    # both denominations and a ``ratio`` label would invite a comparison with
    # every other dimensionless figure in the catalog.
    PERCENT_PER_BILLION_VND = "percent_per_billion_vnd"
    PERCENTILE = "percentile"
    INDEX_0_100 = "index_0_100"


class Denomination(str, Enum):
    """Whether a traded figure counts money or shares.

    A closed set rather than the two words spelled inline, because this is the
    one distinction in the package that a wrong answer looks entirely reasonable
    under: money crosses an ex-date unchanged and shares do not, so a figure
    labelled with the wrong one of these is off by a corporate action while
    reading perfectly. Two fields that report their basis have to report it in
    the same vocabulary for a reader to compare them at all.
    """

    MONEY = "money"
    SHARES = "shares"


class ThresholdOrigin(str, Enum):
    """Which of convention and the derived value the shipped threshold is."""

    # The literature's number was the stricter one, so it won.
    CONVENTION = "convention"

    # The null demanded more than convention does, so the derived number won.
    DERIVED = "derived"


@dataclass(frozen=True)
class Threshold:
    """The frozen number a signal field fires at, and how it was arrived at.

    Both candidates are recorded, not only the winner. Where the literature has a
    conventional threshold the **stricter** of convention and derived value wins
    — and which won is precisely the line a reviewer will want to argue with, so
    it is on the record rather than reconstructible from a commit message.

    Frozen as a constant, never calibrated at runtime: a threshold computed from
    today's data is a threshold that loosens itself in a quiet market, which is
    exactly when a detector should be hardest to trip.
    """

    value: float
    origin: ThresholdOrigin
    convention: float | None
    derived: float
    note: str

    def __post_init__(self) -> None:
        candidates = [self.derived] + (
            [] if self.convention is None else [self.convention]
        )
        strictest = max(candidates)
        if self.value != strictest:
            raise ValueError(
                f"a threshold ships the stricter of convention and derived: "
                f"{strictest} rather than {self.value}"
            )
        expected = (
            ThresholdOrigin.DERIVED
            if self.convention is None or self.derived >= self.convention
            else ThresholdOrigin.CONVENTION
        )
        if self.origin is not expected:
            raise ValueError(
                f"threshold {self.value} came from {expected.value}, "
                f"not {self.origin.value}"
            )


@dataclass(frozen=True)
class NullCalibration:
    """How often this field fires on data that contains no signal.

    Two nulls rather than one, ≥1000 paths each. Matched-volatility geometric
    Brownian motion has neither fat tails nor serial dependence, so a detector
    silent on GBM can still fire constantly on a real quiet series; the
    stationary block bootstrap on a real return history is what catches that. The
    ±7% truncated GBM variant is the third measurement, because a band that
    clamps a session changes the range every one of these fields is computed
    from.

    ``published`` is the **maximum** of them. A field that cannot reach the
    catalog ceiling gets a stricter threshold or does not enter the catalog.
    """

    gbm: float
    gbm_truncated: float
    block_bootstrap: float
    paths: int
    seed: int

    def __post_init__(self) -> None:
        if self.paths < 1000:
            raise ValueError("a null calibration runs at least 1000 paths per null")
        if self.published > CATALOG_NULL_FPR_CEILING:
            raise ValueError(
                f"a published false-positive rate of {self.published} exceeds the "
                f"catalog ceiling of {CATALOG_NULL_FPR_CEILING}"
            )

    @property
    def published(self) -> float:
        return max(self.gbm, self.gbm_truncated, self.block_bootstrap)


@dataclass(frozen=True)
class FieldReading:
    """What one computation produced, before it is dressed as a ``FieldValue``.

    The seam between a pure function over a window and a served answer: a reading
    knows the number and what came with it, and knows nothing about the field
    that declared it. That is what lets a computation be tested, and run against
    a null, without a store behind it.

    ``degraded_reason`` is the computation's **own** verdict on its answer, and
    it exists because some degradations are not properties of the window. A
    window is too limit-locked for any range estimator in the package at once,
    and that lives on Window Health; a band distance measured on UPCOM is
    degraded for this field alone, because that board's anchor is not stored and
    no other field asks for it (``docs/adr/0006``).
    """

    value: float | None
    extras: Mapping[str, Any] = field(default_factory=dict)
    refusal: SignalIssue | None = None
    degraded_reason: SignalIssue | None = None


@dataclass(frozen=True)
class FieldWindow:
    """Everything a registered field may read, and the only thing it is handed.

    One argument rather than a bar frame, because "the window" is more than the
    bars for some fields and the alternative to saying so once is saying it
    differently in each of them. A field asking for a session's traded money
    reads a bar; a field asking how thin this symbol is against its peers reads
    the cross-sectional standing the gateway measured while serving the window;
    a field asking whether a flow was mechanically capped reads a foreign room
    that is not a session fact at all. All three arrive here, and a field that
    reached past this object for any of them would be the second path to data
    that ``prepare_bars()`` exists to make impossible.

    Built in ``serving`` alone. ``health`` is the gateway's own account of the
    window and is echoed beside whatever was computed from it, so a field never
    recounts what the gateway already counted.

    ``fundamental`` is present only where a field's own declaration asked for a
    cross-section, because that is the only serving path that loads statements —
    one query for every symbol rather than one per symbol. A field reading it
    finds either the newest quarter at or before the window's cutoff, with the
    age of that quarter on it, or ``None`` where the store holds no statement
    for this symbol at all.

    ``foreign_room`` is the same shape of fact from the reference Capability: the
    ceiling on foreign ownership, which is not a session and is not derivable
    from one. It is here because a foreign-flow number cannot be read without it
    — a flow that flattened because the room filled is not a change of view.

    ``quarterly`` is the filings themselves — several quarters of one symbol's
    income statement — and it is present only where a field declared that it
    needs them, because loading them costs one read per quarter. A results field
    finds either the quarters whose end is at or before the window's cutoff, or
    ``None`` where the store holds no statement for this symbol at all.
    """

    frame: "BarFrame"
    health: "WindowHealth"
    fundamental: "FundamentalStanding | None" = None
    foreign_room: "ForeignRoomStanding | None" = None
    foreign_net_volume_by_session: Mapping[date, int] | None = None
    quarterly: "QuarterlyStatements | None" = None


@dataclass(frozen=True)
class SignalField:
    """One model-visible number, and everything that has to be true of it.

    Nine declarations, none of them optional at the type level: ``unit``,
    ``sign``, ``interpretation``, ``kind``, ``claim``, ``source``,
    ``min_sessions``, ``threshold`` and ``null_fpr``. A field that omits one
    fails at import rather than shipping — which is the difference between a bar
    and a checklist.

    ``reading`` and ``statistic`` are the mechanism rather than two more
    declarations. ``reading`` is the pure function from a ``FieldWindow`` to this
    field's answer, and it lives on the field so that the pairing is recorded
    where the field is: passed alongside a field instead, a caller could serve
    the Sharpe declaration with the Sortino computation and get a
    perfectly-valid-looking answer. ``statistic`` is the narrower one the null
    harness runs — just the number the threshold is compared against, over the
    bars alone — and a ``signal`` field must have it, because the harness runs
    the real field over synthetic windows and there is no other way to run it.
    """

    name: str
    unit: Unit
    sign: Sign
    interpretation: str
    kind: FieldKind
    claim: Claim
    source: FieldSource
    # Window **plus skip**, always. A field that skips a month before a
    # twelve-month window needs 273 sessions and not 252, and a window quietly
    # shortened to what happened to be stored is a different baseline rather
    # than a weaker one.
    min_sessions: int
    threshold: Threshold | None
    null_fpr: NullCalibration | None
    # Which stored measurement this field's arithmetic actually reads, and so
    # which contract the gateway enforces over its window. Required, with no
    # default, for the reason the nine above are: the gateway's default is the
    # price projection, and a field that never touches a price was silently
    # inheriting the price-basis and band refusals that go with it. Left
    # optional, "which projection" becomes a thing a reader has to work out
    # from the computation, which is exactly the checklist this package refuses
    # to keep.
    projection: BarProjection
    # How many trailing sessions the window *spans*, when that is more than the
    # floor above. Two numbers rather than one because they answer two
    # questions: ``min_sessions`` is how much history the computation refuses
    # below, and this is how far back the window may look for an input the
    # provider writes on some sessions and not others.
    #
    # They were one number, and that made a fallback unreachable: a factor
    # declaring ``min_sessions = 1`` got a one-bar window, so the loop in
    # ``cross_sectional._market_cap`` that walks back for the newest session
    # carrying a market capitalisation had nothing to walk. It read as a
    # tolerance and was dead code.
    #
    # Left unset it *is* ``min_sessions``, which is what every field wanting one
    # window means. A window shorter than the floor is refused at import: it
    # would ask the gateway for fewer sessions than the field then demands, and
    # the refusal would name the history rather than the declaration that caused
    # it.
    lookback_sessions: int | None = None
    requires_foreign_share_flow: bool = False
    # Whether the serving path loads this field's quarterly statements onto the
    # window. Declared rather than loaded for everyone, because the read is one
    # query per quarter of one symbol: paid for every field, it would put five
    # statement reads behind a question about a moving average.
    requires_quarterly_statements: bool = False
    output_keys: tuple[str, ...] = ()
    reading: Callable[[FieldWindow], FieldReading] | None = None
    # The cross-sectional half of the same mechanism: the per-symbol quantity a
    # percentile ranks, over the same ``FieldWindow`` a reading gets. Declared
    # instead of ``reading`` rather than beside it, because a cross-sectional
    # field has no single-symbol answer at all — its number is a position within
    # a sample, and a caller holding one symbol has no sample.
    ranked: Callable[[FieldWindow], FieldReading] | None = None
    statistic: Callable[["BarFrame"], float | None] | None = None

    def __post_init__(self) -> None:
        if not self.interpretation.strip():
            raise ValueError(f"{self.name} must say how it is to be read")
        if self.min_sessions < 1:
            raise ValueError(f"{self.name} must declare the history it needs")
        if self.lookback_sessions is not None and (
            self.lookback_sessions < self.min_sessions
        ):
            raise ValueError(
                f"{self.name} looks back over {self.lookback_sessions} sessions "
                f"and refuses below {self.min_sessions}: a window shorter than "
                "the floor it is measured against can only refuse"
            )

        if self.claim is Claim.DESCRIPTIVE:
            pointing = sorted(DIRECTION_BEARING_KEYS.intersection(self.output_keys))
            if pointing:
                raise ValueError(
                    f"{self.name} is descriptive and may not return "
                    f"{', '.join(pointing)}: a claim about direction unlocks only "
                    "behind a measured forward-return harness"
                )

        if (self.reading is None) == (self.ranked is None):
            raise ValueError(
                f"{self.name} declares exactly one of a reading and a ranked "
                "quantity: the computation that answers for a field belongs on "
                "the declaration rather than beside it, and whether it is "
                "answered for one symbol or within a sample is not a caller's "
                "choice to make"
            )
        if self.requires_quarterly_statements and self.ranked is not None:
            raise ValueError(
                f"{self.name} is ranked across a cross-section, which loads one "
                "quarter for a whole sample rather than several quarters for one "
                "symbol: declared here, it would refuse for every member of "
                "every ranking and the refusal would name the store"
            )
        if self.ranked is not None and self.kind is not FieldKind.PERCENTILE:
            raise ValueError(
                f"{self.name} is ranked across a cross-section, so what it "
                f"answers with is a percentile rather than a {self.kind.value}"
            )

        if self.kind is FieldKind.SIGNAL:
            if self.threshold is None or self.null_fpr is None:
                raise ValueError(
                    f"{self.name} can fire, so it ships a frozen threshold and a "
                    "measured null"
                )
            if self.statistic is None:
                raise ValueError(
                    f"{self.name} can fire, so the null harness has to be able to "
                    "run it"
                )
        elif self.threshold is not None or self.null_fpr is not None:
            raise ValueError(
                f"{self.name} is a {self.kind.value} and cannot fire, so a "
                "threshold or a null on it would describe nothing"
            )

    @property
    def fires(self) -> bool:
        return self.kind is FieldKind.SIGNAL

    @property
    def window_sessions(self) -> int:
        """How many trailing sessions the gateway is asked for.

        The declared lookback where there is one, and the floor otherwise. Every
        caller asks for this rather than reading ``min_sessions`` as a window:
        the two agree for most fields, and the ones they do not agree for are
        exactly the ones where reading the wrong number is silent.
        """
        return self.lookback_sessions or self.min_sessions


@dataclass(frozen=True)
class FieldValue:
    """What one field answered for one symbol, or the reason it did not.

    **Window Health travels with every one of these**, refusals included. A
    number drawn from twelve sessions and one drawn from two hundred look
    identical until the answer says which it is, and the reason a field could not
    answer is exactly what a surface has to say in place of a number.

    The kind's own bar is checked here rather than trusted: an estimator without
    its uncertainty, a percentile without the sample it was ranked in, a
    descriptive field carrying a key that points somewhere — each raises where it
    is constructed, so a field cannot ship the violation and be caught later by a
    reviewer reading the payload.
    """

    field: SignalField
    value: float | None
    health: "WindowHealth"
    extras: Mapping[str, Any] = field(default_factory=dict)
    refusal: SignalIssue | None = None
    degraded_reason: SignalIssue | None = None

    def __post_init__(self) -> None:
        pointing = sorted(DIRECTION_BEARING_KEYS.intersection(self.extras))
        if self.field.claim is Claim.DESCRIPTIVE and pointing:
            raise ValueError(
                f"{self.field.name} is descriptive and returned "
                f"{', '.join(pointing)}"
            )

        if self.refusal is not None:
            if self.value is not None:
                raise ValueError(
                    f"{self.field.name} refused with {self.refusal.value} and "
                    "returned a number anyway"
                )
            return

        if self.value is None:
            raise ValueError(
                f"{self.field.name} returned no value and no reason for it"
            )

        # Presence is not the test, and a key holding ``None`` is the way an
        # estimator ships no uncertainty while looking as though it does. Either
        # a field can say how much its number would move, or it refuses.
        if self.field.kind is FieldKind.ESTIMATOR and not (
            self.extras.get("standard_error") is not None
            or self.extras.get("confidence_interval") is not None
        ):
            raise ValueError(
                f"{self.field.name} is an estimator, so it ships a standard error "
                "or a confidence interval, and neither may be null"
            )
        if self.field.kind is FieldKind.PERCENTILE and not (
            self.extras.get("n") is not None and self.extras.get("as_of") is not None
        ):
            raise ValueError(
                f"{self.field.name} is a percentile, so it ships the n it was "
                "ranked among and the date it was cut at"
            )

    @property
    def fired(self) -> bool:
        """Whether the number cleared its frozen threshold.

        False for anything that cannot fire, which is not the same as a signal
        that did not: an estimator has no threshold to clear and asking whether
        it fired is asking the wrong question of it.
        """
        if self.value is None or self.field.threshold is None:
            return False
        return self.value >= self.field.threshold.value


def schema_description(field: SignalField) -> str:
    """The one sentence a model reads about this field before deciding to call.

    This is where ``null_fpr`` lives, and the reason it lives here rather than in
    a payload: read once from the schema, it costs nothing against the response
    budget on any call, while a rate repeated in every payload would be paid for
    on all of them and read on none.

    The interpretation leads, because it is the only sanctioned reading of the
    number. The unit and sign follow it, since ADR-0010 admits no figure without
    both. The false-positive rate comes last and only where there is one — an
    estimator has no threshold, so it has no rate, and printing a zero would read
    as a perfect detector rather than as a field that never claims an event.
    """
    parts = [
        field.interpretation,
        f"Unit: {field.unit.value}. Sign: {field.sign.value}. "
        f"Claim: {field.claim.value}.",
        f"Needs {field.min_sessions} sessions.",
    ]
    if field.threshold is not None and field.null_fpr is not None:
        parts.append(
            f"Fires at {field.threshold.value:g} "
            f"({field.threshold.origin.value}); measured false-positive rate "
            f"{field.null_fpr.published:.2%} against a "
            f"{CATALOG_NULL_FPR_CEILING:.0%} ceiling."
        )
    return " ".join(parts)
