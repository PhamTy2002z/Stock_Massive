"""The single place a model-visible number is declared.

Nothing here prohibits an unregistered computation, and nothing needs to: every
model-facing surface — the tool layer and the nightly Analysis alike —
serializes **registered fields only**, so a computation that is not in this file
has no route to a model. That is why the registry sits at domain level rather
than under the agent: the artifact people read every day cites through the same
declarations the agent does, and a registry under the agent would leave the
nightly one unguarded.

Each entry declares the nine attributes of ADR-0010 and is validated where it is
written (``fields.py``). A field that omits one does not ship a gap for a
reviewer to notice — it fails at import.

## Thresholds are frozen here and derived elsewhere

Every threshold in this file is a constant produced by running the null harness
**offline** and writing the answer down. Never calibrated at runtime: a threshold
computed from today's data loosens itself in a quiet market, which is exactly
when a detector should be hardest to trip. Where the literature has a convention,
the stricter of convention and derived value wins, and ``Threshold.origin``
records which — that being precisely the line a reviewer will want to argue with.

## What ``null_fpr`` is and is not

It is the measured rate at which a field fires on data containing no signal, the
maximum of the two nulls, and it rides in the **tool schema description** rather
than in a payload: the model reads it once before deciding to call, at no
per-call cost against the response budget. The numbers below were measured by
``src.stocks.signals.nulls`` at the seed and path count each records, and
``tests/test_null_harness.py`` re-measures them on every run — at fewer paths, so
it re-derives nothing and only fails when a field drifts past the ceiling.
"""

from __future__ import annotations

from collections.abc import Mapping
from types import MappingProxyType

from .fields import (
    Claim,
    FieldKind,
    FieldSource,
    NullCalibration,
    SignalField,
    Sign,
    Threshold,
    ThresholdOrigin,
    Unit,
)
from .risk import (
    DRAWDOWN_MIN_SESSIONS,
    current_drawdown_reading,
    days_underwater_reading,
    drawdown_versus_benchmark_reading,
    max_drawdown_reading,
    price_zone_reading,
    realized_volatility_reading,
    sharpe_reading,
    sortino_reading,
    DRAWDOWN_SESSIONS,
    MIN_DOWNSIDE_OBSERVATIONS,
    PRICE_ZONE_MIN_SESSIONS,
    PRICE_ZONE_SESSIONS,
    REALIZED_VOLATILITY_MIN_SESSIONS,
    REALIZED_VOLATILITY_SESSIONS,
    RISK_ADJUSTED_MIN_SESSIONS,
    RISK_ADJUSTED_SESSIONS,
    drawdown_ratio,
)
from .volatility import (
    VOLATILITY_REGIME_BASELINE_DAYS,
    VOLATILITY_REGIME_MIN_SESSIONS,
    volatility_regime_reading,
    volatility_regime_z,
)

# The seed and path count the frozen numbers below were measured at. Recorded so
# the derivation can be repeated exactly rather than approximately: a threshold
# nobody can reproduce is a threshold nobody can argue with.
NULL_DERIVATION_SEED = 20260815
NULL_DERIVATION_PATHS = 16_000

VOLATILITY_REGIME_Z = SignalField(
    # The id the Analysis Field Profile already names (spec 0003 §8.4). Kept
    # letter for letter even though the z is taken on the logarithm of the
    # variance rather than on the variance: the profile is the contract, and a
    # field the nightly pipeline cannot find by name is a field it emits as
    # refused.
    name="volatility_regime.gk_variance_robust_z",
    unit=Unit.Z_SCORE,
    sign=Sign.SIGNED,
    interpretation=(
        "How wide this session's price range was against the same symbol's own "
        "recent range, in robust standard deviations of its trailing "
        f"{VOLATILITY_REGIME_BASELINE_DAYS}-session baseline. Positive means a "
        "wider range than usual for this symbol and negative a narrower one. It "
        "says nothing about which way the price moved or is going to move."
    ),
    kind=FieldKind.SIGNAL,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    # Window plus skip, and this field skips nothing.
    min_sessions=VOLATILITY_REGIME_MIN_SESSIONS,
    threshold=Threshold(
        value=3.0,
        origin=ThresholdOrigin.DERIVED,
        # The conventional z of the literature, and the one a reader will expect.
        convention=2.0,
        derived=3.0,
        note=(
            "The two nulls disagree, and the disagreement is the argument for "
            "running both. Matched-volatility GBM puts the 99th percentile of "
            "this z at 2.28 and the ±7%-truncated variant at 2.32; the "
            "stationary block bootstrap, which alone carries fat tails and "
            "volatility clustering, puts it at 2.86. The maximum, 2.86, is "
            "rounded up to a flat 3.0 — a margin over the measurement rather "
            "than a second derivation, so a rerun landing a few hundredths "
            "higher does not move the shipped constant. Convention's z = 2 is "
            "the looser of the two and loses. "
            "Measured while deriving this and recorded because it decided the "
            "statistic's shape: taken on the raw Garman-Klass variance rather "
            "than on its logarithm, the same bootstrap demands z of about 25, "
            "because a variance under realistic tails is power-law rather than "
            "location-scale and a z over it measures the tail instead of the "
            "regime."
        ),
    ),
    null_fpr=NullCalibration(
        gbm=0.0010,
        gbm_truncated=0.0011,
        block_bootstrap=0.0047,
        paths=NULL_DERIVATION_PATHS,
        seed=NULL_DERIVATION_SEED,
    ),
    output_keys=(
        "garman_klass_variance",
        "sessions",
        "baseline_sessions",
        "limit_lock_days",
    ),
    reading=volatility_regime_reading,
    statistic=volatility_regime_z,
)


# --- The risk cluster -----------------------------------------------------

REALIZED_VOLATILITY = SignalField(
    name="realized_volatility.yang_zhang_annualized_pct",
    unit=Unit.PERCENT_ANNUALIZED,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "How much this symbol's price has moved over the last "
        f"{REALIZED_VOLATILITY_SESSIONS} sessions, as an annualized standard "
        "deviation in percent, estimated by Yang-Zhang from each session's open, "
        "high, low and close. It measures the size of past moves and not their "
        "direction. Limit-locked and zero-range sessions have no range to read, "
        "so where the counts beside it are material the estimate is biased low."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=REALIZED_VOLATILITY_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=(
        "standard_error",
        "components_annualized_pct",
        "sessions",
        "estimator_sessions",
        "limit_lock_days",
        "zero_range_days",
    ),
    reading=realized_volatility_reading,
)

# The price-zone field the nightly artifact treats as core evidence. Named here
# because the spec left it unnamed, and recorded in spec 0003 §8.4 so the
# Analysis Field Profile reads the same string. It does not consume a Technical
# slot.
PRICE_ZONE = SignalField(
    name="price_zone.ordinary_range_pct",
    unit=Unit.PERCENT,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "This symbol's ordinary daily range: one realized standard deviation of "
        f"a session's move, from Yang-Zhang over {PRICE_ZONE_SESSIONS} sessions, "
        "as a percentage of the reference price. The prices beside it are that "
        "band drawn around the reference price. It describes how far this symbol "
        "usually travels in a day and carries no view on where it will travel."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=PRICE_ZONE_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=(
        "anchor_close",
        "lower_price",
        "upper_price",
        "anchor_session",
        "standard_error",
        "sessions",
        "estimator_sessions",
        "limit_lock_days",
    ),
    reading=price_zone_reading,
)

_DRAWDOWN_KEYS = (
    "standard_error",
    "expected_max_drawdown_pct",
    "max_drawdown_pct",
    "current_drawdown_pct",
    "days_underwater",
    "peak_session",
    "trough_session",
    "sessions",
    "estimator_sessions",
    "limit_lock_days",
)

MAX_DRAWDOWN = SignalField(
    name="drawdown_stats.max_drawdown_pct",
    unit=Unit.PERCENT,
    sign=Sign.NON_POSITIVE,
    interpretation=(
        "The deepest fall from a running high over the last "
        f"{DRAWDOWN_SESSIONS} sessions, in percent and negative by convention. "
        "Read it against the expected maximum drawdown beside it, which is what "
        "a driftless random walk at this symbol's volatility would have produced "
        "over the same length: a fall near that number is ordinary rather than "
        "alarming. The standard error is wide because a realized drawdown is one "
        "draw from a broad distribution, not an exact property of the symbol."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=DRAWDOWN_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=_DRAWDOWN_KEYS,
    reading=max_drawdown_reading,
)

CURRENT_DRAWDOWN = SignalField(
    name="drawdown_stats.current_drawdown_pct",
    unit=Unit.PERCENT,
    sign=Sign.NON_POSITIVE,
    interpretation=(
        "How far below its running high over the last "
        f"{DRAWDOWN_SESSIONS} sessions this symbol closed, in percent and "
        "negative by convention; zero means it closed at a new high. It says "
        "where the price sits relative to its own recent peak and nothing about "
        "where it goes next."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=DRAWDOWN_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=_DRAWDOWN_KEYS,
    reading=current_drawdown_reading,
)

DAYS_UNDERWATER = SignalField(
    name="drawdown_stats.days_underwater",
    unit=Unit.SESSIONS,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "How many sessions have passed since this symbol last closed at a high "
        f"of its trailing {DRAWDOWN_SESSIONS}-session window. Under a driftless "
        "random walk this number is spread almost evenly across the window, so a "
        "large one is ordinary rather than a finding — which is what the wide "
        "standard error beside it says."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=DRAWDOWN_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=_DRAWDOWN_KEYS,
    reading=days_underwater_reading,
)

DRAWDOWN_VERSUS_BENCHMARK = SignalField(
    name="drawdown_stats.mdd_over_expected",
    unit=Unit.RATIO,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "The deepest fall over the last "
        f"{DRAWDOWN_SESSIONS} sessions divided by the fall a driftless random "
        "walk at this symbol's own volatility would have produced over the same "
        "length (Magdon-Ismail's E[MDD] = 1.2533·σ√T). One means an ordinary "
        "fall for a symbol this volatile; the threshold is where the fall is "
        "deeper than a random walk plausibly explains."
    ),
    kind=FieldKind.SIGNAL,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=DRAWDOWN_MIN_SESSIONS,
    threshold=Threshold(
        value=2.75,
        origin=ThresholdOrigin.DERIVED,
        # Firing at the benchmark itself is the reading a naive user of
        # E[MDD] would take: "deeper than expected". Half of all random walks
        # are deeper than their own expectation, so it is by far the looser
        # candidate and loses.
        convention=1.0,
        derived=2.75,
        note=(
            "The two nulls agree here, unlike the volatility-regime z: the "
            "worst matched-volatility GBM group puts the 99th percentile of "
            "this ratio at 2.47, the ±7%-truncated variant at 2.51, and the "
            "stationary block bootstrap at 2.19 — a drawdown ratio is far less "
            "sensitive to fat tails than a variance z, because it is already "
            "normalised by the volatility those tails inflate. The maximum, "
            "2.51, is rounded up to 2.75, a margin over the measurement wide "
            "enough that the tightest of the three still clears the ceiling "
            "by a factor of two. "
            "Convention's 1.0 — the benchmark read as a threshold — would fire "
            "on about half of all random walks."
        ),
    ),
    null_fpr=NullCalibration(
        gbm=0.0030,
        gbm_truncated=0.0050,
        block_bootstrap=0.0014,
        paths=NULL_DERIVATION_PATHS,
        seed=NULL_DERIVATION_SEED,
    ),
    output_keys=(
        "expected_max_drawdown_log",
        "sessions",
        "estimator_sessions",
        "limit_lock_days",
    ),
    reading=drawdown_versus_benchmark_reading,
    statistic=drawdown_ratio,
)

SHARPE = SignalField(
    name="risk_adjusted.sharpe_annualized",
    unit=Unit.RATIO,
    sign=Sign.SIGNED,
    interpretation=(
        "Annualized return per unit of return volatility over the last "
        f"{RISK_ADJUSTED_SESSIONS} sessions, measured against a zero benchmark "
        "because this system holds no risk-free series. Read the confidence "
        "interval and not the ratio: on a sample this length the interval "
        "usually contains zero, which means the ratio is not distinguishable "
        "from no risk-adjusted return at all. Where the returns are "
        "autocorrelated the annualization is Lo's corrected factor rather than "
        "√252, and the answer says which was used."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=RISK_ADJUSTED_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=(
        "standard_error",
        "confidence_interval",
        "indistinguishable_from_zero",
        "annualization",
        "annualization_lags",
        "first_autocorrelation",
        "benchmark",
        "sessions",
        "estimator_sessions",
        "limit_lock_days",
    ),
    reading=sharpe_reading,
)

SORTINO = SignalField(
    name="risk_adjusted.sortino_annualized",
    unit=Unit.RATIO,
    sign=Sign.SIGNED,
    interpretation=(
        "Annualized return per unit of **downside** volatility over the last "
        f"{RISK_ADJUSTED_SESSIONS} sessions, against a zero benchmark. The "
        "downside deviation divides by every observation rather than only by "
        "those below the benchmark, so it is not understated on a symbol that "
        "mostly rose. Judge it by the downside-observation count beside it; "
        f"below {MIN_DOWNSIDE_OBSERVATIONS} of them the ratio is withheld."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=RISK_ADJUSTED_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=(
        "standard_error",
        "standard_error_basis",
        "confidence_interval",
        "downside_obs_count",
        "downside_deviation_pct",
        "annualization",
        "annualization_lags",
        "benchmark",
        "sessions",
        "estimator_sessions",
        "limit_lock_days",
    ),
    reading=sortino_reading,
)


def _index(*fields: SignalField) -> Mapping[str, SignalField]:
    """Key the declarations by name, refusing two fields with one name.

    A duplicate would not be a merge conflict anybody notices: the later
    declaration would simply win, and one surface would be citing a field
    another surface believes it is citing.
    """
    indexed: dict[str, SignalField] = {}
    for entry in fields:
        if entry.name in indexed:
            raise ValueError(f"{entry.name} is declared twice")
        indexed[entry.name] = entry
    return MappingProxyType(indexed)


REGISTRY: Mapping[str, SignalField] = _index(
    VOLATILITY_REGIME_Z,
    REALIZED_VOLATILITY,
    PRICE_ZONE,
    MAX_DRAWDOWN,
    CURRENT_DRAWDOWN,
    DAYS_UNDERWATER,
    DRAWDOWN_VERSUS_BENCHMARK,
    SHARPE,
    SORTINO,
)


def registered_field(name: str) -> SignalField:
    """The declaration for one field, or a refusal to guess at one.

    ``KeyError`` rather than ``None``: a caller asking for a field by name has
    the name in its own source, so a missing one is a typo or a deletion rather
    than a condition to handle.
    """
    return REGISTRY[name]


def signal_fields() -> tuple[SignalField, ...]:
    """Every registered field that can fire, in declaration order.

    What the null harness is parametrised over. A field added to the registry is
    therefore a field the harness runs, without anybody remembering to add it
    anywhere — which is the difference between a gate and a convention.
    """
    return tuple(entry for entry in REGISTRY.values() if entry.fires)


def fields_of_kind(kind: FieldKind) -> tuple[SignalField, ...]:
    return tuple(entry for entry in REGISTRY.values() if entry.kind is kind)
