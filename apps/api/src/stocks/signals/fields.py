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

from collections.abc import Callable, Mapping
from dataclasses import dataclass, field
from datetime import date
from enum import Enum
from typing import TYPE_CHECKING, Any

from .issues import SignalIssue

if TYPE_CHECKING:  # pragma: no cover - import cycle only matters to a checker
    from .bars import BarFrame, WindowHealth

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

# Keys a `descriptive` field may not return, whatever it calls itself. Matched on
# the whole key rather than as a substring: `direction` is refused and
# `direction_of_travel` with it, while `expected_return` is refused and
# `return_window_days` is not. The list is the ADR's three plus the wordings a
# field would reach for next once those three are taken.
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
    """What the number is measured in."""

    Z_SCORE = "z_score"
    PERCENT = "percent"
    PERCENT_ANNUALIZED = "percent_annualized"
    RATIO = "ratio"
    SESSIONS = "sessions"
    VND = "vnd"
    PERCENTILE = "percentile"


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
class SignalField:
    """One model-visible number, and everything that has to be true of it.

    Nine declarations, none of them optional at the type level: ``unit``,
    ``sign``, ``interpretation``, ``kind``, ``claim``, ``source``,
    ``min_sessions``, ``threshold`` and ``null_fpr``. A field that omits one
    fails at import rather than shipping — which is the difference between a bar
    and a checklist.

    ``statistic`` is the mechanism rather than a tenth declaration: the pure
    function from a window of bars to the number the threshold is compared
    against. A ``signal`` field must have one, because the null harness runs the
    real field over synthetic windows and there is no other way to run it.
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
    output_keys: tuple[str, ...] = ()
    statistic: Callable[["BarFrame"], float | None] | None = None

    def __post_init__(self) -> None:
        if not self.interpretation.strip():
            raise ValueError(f"{self.name} must say how it is to be read")
        if self.min_sessions < 1:
            raise ValueError(f"{self.name} must declare the history it needs")

        if self.claim is Claim.DESCRIPTIVE:
            pointing = sorted(DIRECTION_BEARING_KEYS.intersection(self.output_keys))
            if pointing:
                raise ValueError(
                    f"{self.name} is descriptive and may not return "
                    f"{', '.join(pointing)}: a claim about direction unlocks only "
                    "behind a measured forward-return harness"
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

        if self.field.kind is FieldKind.ESTIMATOR and not (
            "standard_error" in self.extras or "confidence_interval" in self.extras
        ):
            raise ValueError(
                f"{self.field.name} is an estimator, so it ships a standard error "
                "or a confidence interval"
            )
        if self.field.kind is FieldKind.PERCENTILE and not (
            "n" in self.extras and "as_of" in self.extras
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


def as_of_stamp(value: date) -> str:
    """A cutoff date in the one form a percentile's ``as_of`` is written in."""
    return value.isoformat()


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
