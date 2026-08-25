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

import hashlib
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
from .cross_sectional import (
    FACTOR_LOOKBACK_SESSIONS,
    FACTOR_MIN_SESSIONS,
    MOMENTUM_FORMATION_SESSIONS,
    MOMENTUM_MIN_SESSIONS,
    MOMENTUM_SKIP_SESSIONS,
    RELATIVE_STRENGTH_MIN_SESSIONS,
    TREND_MIN_SESSIONS,
    TREND_YEAR_SESSIONS,
    book_yield_ranked,
    earnings_yield_ranked,
    momentum_ranked,
    relative_strength_reading,
    roe_ranked,
    size_ranked,
    trend_reading,
)
from .foreign_flow import (
    FOREIGN_FLOW_MIN_SESSIONS,
    FOREIGN_FLOW_SESSIONS,
    FOREIGN_PERSISTENCE_MIN_SESSIONS,
    FOREIGN_PERSISTENCE_SESSIONS,
    FOREIGN_ROOM_MIN_SESSIONS,
    PERSISTENCE_RUN_THRESHOLD,
    foreign_room_pct_reading,
    net_value_over_adtv_reading,
    net_volume_over_adtv_reading,
    persistence_run_days,
    persistence_run_days_reading,
)
from .indicators import (
    BOLLINGER_MIN_SESSIONS,
    INDICATOR_WARMUP_SESSIONS,
    MACD_MIN_SESSIONS,
    RSI_MIN_SESSIONS,
    bollinger_percent_b_reading,
    macd_reading,
    rsi_reading,
)
from .market_behavior import (
    BAND_PRESSURE_MIN_SESSIONS,
    BAND_PRESSURE_SESSIONS,
    LIQUIDITY_MIN_SESSIONS,
    LIQUIDITY_SESSIONS,
    MEAN_REVERSION_MIN_SESSIONS,
    MEAN_REVERSION_SESSIONS,
    SETTLEMENT_FLOOR_SESSIONS,
    adtv_money_reading,
    adtv_percentile_reading,
    adtv_shares_reading,
    amihud_illiquidity_reading,
    band_pressure_reading,
    mean_reversion_half_life_reading,
    mean_reversion_z_reading,
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


# --- The market-behaviour cluster ----------------------------------------
#
# Nothing below fires. The volatility-regime z above is the cluster's one
# ``signal`` field and it was calibrated when it was registered; the four
# questions added here — how much money trades, how illiquid that makes the
# symbol, how often it reaches its band, how stretched it is against its own
# mean — are all descriptive, and each carries the uncertainty its kind demands
# instead of a threshold. A "thin" or "stretched" flag would be one narration
# away from a claim about what the price does next, and the research behind this
# cluster could verify no such claim for this market.

ADTV_MONEY = SignalField(
    name="liquidity_profile.adtv_vnd",
    unit=Unit.VND,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "Average money traded in this symbol per session over the last "
        f"{LIQUIDITY_SESSIONS} sessions, in dong. It is denominated in **money**, "
        "which is the figure that survives a corporate action: a share count "
        "changes at an ex-date and the dong traded do not. It says how much of "
        "this symbol can be bought or sold on an ordinary day and nothing about "
        "what its price will do."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=LIQUIDITY_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=(
        "standard_error",
        "adtv_basis",
        "sessions",
        "limit_lock_days",
    ),
    reading=adtv_money_reading,
)

ADTV_SHARES = SignalField(
    name="liquidity_profile.adtv_shares",
    unit=Unit.SHARES,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "Average number of shares traded in this symbol per session over the "
        f"last {LIQUIDITY_SESSIONS} sessions. It is denominated in **shares**, so "
        "a window crossing a stock dividend, bonus issue or split holds two "
        "different units and the answer says so through its degradation. Where "
        "a figure has to be compared across such a window, the money ADTV is "
        "the one that can be."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=LIQUIDITY_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=(
        "standard_error",
        "adtv_basis",
        "sessions",
        "quantities_comparable",
    ),
    reading=adtv_shares_reading,
)

AMIHUD_ILLIQUIDITY = SignalField(
    name="liquidity_profile.amihud_illiq",
    unit=Unit.PERCENT_PER_BILLION_VND,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "Amihud's illiquidity: how far this symbol's price moves, in percent, "
        "per billion dong traded, averaged over the last "
        f"{LIQUIDITY_SESSIONS} sessions. **Higher means more illiquid** — the "
        "same money moves the price further. Sessions in which nothing traded "
        "are counted beside it rather than averaged in, because a price move "
        "divided by no traded money is not a measurement."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=LIQUIDITY_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=(
        "standard_error",
        "measured_sessions",
        "zero_volume_days",
        "limit_lock_days",
        "sessions",
    ),
    reading=amihud_illiquidity_reading,
)

ADTV_PERCENTILE = SignalField(
    name="liquidity_profile.adtv_percentile",
    unit=Unit.PERCENTILE,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "Where this symbol's average daily traded money sits among the Universe "
        f"over the same {LIQUIDITY_SESSIONS} sessions, as a percentile from 0 to "
        "100. Higher means more of the Universe trades less than this symbol "
        "does. It is a position within a named sample on a named date, both of "
        "which travel with it, and it is not comparable with a percentile taken "
        "over a different sample."
    ),
    kind=FieldKind.PERCENTILE,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=LIQUIDITY_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=("n", "as_of", "adtv_vnd", "adtv_basis", "sessions"),
    reading=adtv_percentile_reading,
)

BAND_PRESSURE = SignalField(
    # The id the Analysis Field Profile already names (spec 0003 §8.4).
    name="band_pressure.limit_days_in_window",
    unit=Unit.SESSIONS,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "How many of the last "
        f"{BAND_PRESSURE_SESSIONS} sessions this symbol spent locked at a price "
        "limit, with its own base rate and the distance from its latest close to "
        "that session's ceiling and floor beside it. The distances share one "
        "sign convention: **positive means the limit sits above the close**, so "
        "the ceiling distance is the room the price still had and the floor "
        "distance is negative. A session locked at a limit is one that never "
        "traded away from it, which is not the same as one that closed there."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=BAND_PRESSURE_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=(
        "standard_error",
        "base_rate_pct",
        "closes_at_ceiling",
        "closes_at_floor",
        "distance_to_ceiling_pct",
        "distance_to_floor_pct",
        "anchor_basis",
        "decided_days",
        "undecided_days",
        "sessions",
    ),
    reading=band_pressure_reading,
)

_MEAN_REVERSION_KEYS = (
    "confidence_interval",
    "half_life_sessions",
    "half_life_reaches_window",
    "ar1_phi",
    "settlement_floor_sessions",
    "half_life_under_settlement_floor",
    "bootstrap_paths_without_reversion",
    "baseline_sessions",
    "sessions",
    "limit_lock_days",
)

MEAN_REVERSION_Z = SignalField(
    name="mean_reversion.trailing_z",
    unit=Unit.Z_SCORE,
    sign=Sign.SIGNED,
    interpretation=(
        "How far this symbol's latest close sits from its own mean over the "
        f"trailing {MEAN_REVERSION_SESSIONS} sessions, in standard deviations of "
        "that stretch. Positive is above its own recent mean and negative below. "
        "It is **descriptive**: it says where the price is relative to its own "
        "history and carries no view on where it goes next. Where the fitted "
        "half-life beside it reaches the window length the z is withheld "
        "entirely, because there it measures the window rather than the market."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=MEAN_REVERSION_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=_MEAN_REVERSION_KEYS,
    reading=mean_reversion_z_reading,
)

MEAN_REVERSION_HALF_LIFE = SignalField(
    name="mean_reversion.half_life_sessions",
    unit=Unit.SESSIONS,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "How many sessions a deviation from this symbol's own trailing mean has "
        "taken to decay by half, from an AR(1) fit over the last "
        f"{MEAN_REVERSION_SESSIONS} sessions, with a block-bootstrap interval. "
        f"Under about {SETTLEMENT_FLOOR_SESSIONS} sessions the reading is not "
        "round-trip actionable at all: Vietnamese settlement is T+2, so the "
        "shares are not deliverable until the move has already half-decayed. The "
        "field states that floor rather than leaving it to be discovered."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=MEAN_REVERSION_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=_MEAN_REVERSION_KEYS,
    reading=mean_reversion_half_life_reading,
)

# The cluster as one list, so a test can assert something of all of it and a
# later field cannot be added without joining what is asserted.
MARKET_BEHAVIOR_FIELDS: tuple[SignalField, ...] = (
    VOLATILITY_REGIME_Z,
    ADTV_MONEY,
    ADTV_SHARES,
    AMIHUD_ILLIQUIDITY,
    ADTV_PERCENTILE,
    BAND_PRESSURE,
    MEAN_REVERSION_Z,
    MEAN_REVERSION_HALF_LIFE,
)


# --- The cross-sectional cluster -----------------------------------------
#
# Four positions within the Universe rather than against a symbol's own past,
# and two of them are honest about what this system does not hold: relative
# strength has no stored benchmark to regress against, so it is registered and
# refuses; the factor percentiles rest on quarterly statements and carry the age
# of the quarter behind every figure.

MOMENTUM_RANK = SignalField(
    # The id the Analysis Field Profile already names (spec 0003 §8.4). "12-2"
    # names the formation by its month endpoints — twelve months back to two
    # months back — which is the same window ``252 + 21`` describes by the length
    # of its skip. Both spellings, one window (see ``cross_sectional``).
    name="momentum_rank.percentile_12_2",
    unit=Unit.PERCENTILE,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "Where this symbol's return over the "
        f"{MOMENTUM_FORMATION_SESSIONS} sessions ending "
        f"{MOMENTUM_SKIP_SESSIONS} sessions ago sits within the Universe, as a "
        "percentile from 0 to 100 with the raw return beside it. Higher means it "
        "outran more of the Universe over that stretch. The most recent month is "
        "skipped deliberately, to step around the short-horizon reversal that "
        "contaminates a formation running up to today. **It is never a valid "
        "read over one day**: the price band spreads a single shock across "
        "consecutive limit sessions, so a short formation ranks a move that has "
        "not finished arriving."
    ),
    kind=FieldKind.PERCENTILE,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    # Window plus skip, and this is the field the rule was written for.
    min_sessions=MOMENTUM_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=(
        "n",
        "as_of",
        "excluded_symbols",
        "formation_return_pct",
        "formation_sessions",
        "skipped_sessions",
        "sessions",
        "limit_lock_days",
    ),
    ranked=momentum_ranked,
)

TREND_SIGNAL = SignalField(
    name="trend_signal.total_return_12m_pct",
    unit=Unit.PERCENT,
    sign=Sign.SIGNED,
    interpretation=(
        "This symbol's own total return over the last "
        f"{TREND_YEAR_SESSIONS} sessions in percent, with the sign and magnitude "
        "over three and six months beside it. Positive is a rise over the window "
        "and negative a fall; the three windows disagreeing is itself the "
        "reading. **The evidence for reading a past return's sign at all is from "
        "liquid futures** (Moskowitz-Ooi-Pedersen 2012, all 58 instruments), and "
        "applying it to a single Vietnamese equity is an extrapolation rather "
        "than a published result."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=TREND_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=(
        "standard_error",
        "return_3m_pct",
        "sign_3m",
        "return_6m_pct",
        "sign_6m",
        "return_12m_pct",
        "sign_12m",
        "evidence_basis",
        "sessions",
        "limit_lock_days",
    ),
    reading=trend_reading,
)

RELATIVE_STRENGTH = SignalField(
    name="relative_strength.beta_vs_market_index",
    unit=Unit.RATIO,
    sign=Sign.SIGNED,
    interpretation=(
        "Rolling beta and correlation against the market index. **Unavailable**: "
        "the benchmark's session series is now stored durably and is served by "
        "the same bar gateway a symbol's window comes from, but the rolling "
        "regression over it is not implemented — so what is missing is the "
        "estimator rather than the data. The index alias inside the live price "
        "path is deliberately not read in its place. The field is registered so "
        "the Analysis Field Profile stays honest about what it is missing, and "
        "it will report beta and correlation under Ledoit-Wolf shrinkage — with "
        "the shrinkage intensity beside them, an intensity approaching one "
        "meaning the data was insufficient."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=RELATIVE_STRENGTH_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=("missing_input", "benchmark", "shrinkage"),
    reading=relative_strength_reading,
)

_FACTOR_KEYS = (
    "n",
    "as_of",
    "excluded_symbols",
    "period_end",
    "period_age_days",
    # The session the market side of the ratio was read from, and the session the
    # window ends on. Two keys because the Main Source writes a capitalisation on
    # some sessions and not others: where they differ the figure is degraded
    # under ``stale_market_cap``, and a reader can only see that if both are here.
    "price_session",
    "window_session",
)

EARNINGS_YIELD_PERCENTILE = SignalField(
    name="factor_percentiles.earnings_yield_percentile",
    unit=Unit.PERCENTILE,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "Where this symbol's trailing twelve-month earnings over its market "
        "capitalisation sits within the Universe, as a percentile from 0 to 100. "
        "Higher means cheaper on earnings. The Vietnamese evidence prefers "
        "earnings-to-price over book-to-market as the value measure "
        "(Huang-Liu-Shu 2023). The quarter the earnings come from is stamped "
        "beside it, and the percentile is a positioning fact rather than a "
        "timing one — the premia behind it are measured at annual horizons."
    ),
    kind=FieldKind.PERCENTILE,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.STORED,
    min_sessions=FACTOR_MIN_SESSIONS,
    lookback_sessions=FACTOR_LOOKBACK_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=_FACTOR_KEYS,
    ranked=earnings_yield_ranked,
)

BOOK_YIELD_PERCENTILE = SignalField(
    name="factor_percentiles.book_yield_percentile",
    unit=Unit.PERCENTILE,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "Where this symbol's parent-company equity over its market "
        "capitalisation sits within the Universe, as a percentile from 0 to 100. "
        "Higher means cheaper on book value. The quarter the equity comes from "
        "is stamped beside it."
    ),
    kind=FieldKind.PERCENTILE,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.STORED,
    min_sessions=FACTOR_MIN_SESSIONS,
    lookback_sessions=FACTOR_LOOKBACK_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=_FACTOR_KEYS,
    ranked=book_yield_ranked,
)

ROE_PERCENTILE = SignalField(
    name="factor_percentiles.roe_percentile",
    unit=Unit.PERCENTILE,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "Where this symbol's trailing twelve-month return on parent-company "
        "equity sits within the Universe, as a percentile from 0 to 100. Higher "
        "means more profitable on the equity it holds. The quarter both figures "
        "come from is stamped beside it."
    ),
    kind=FieldKind.PERCENTILE,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.STORED,
    min_sessions=FACTOR_MIN_SESSIONS,
    lookback_sessions=FACTOR_LOOKBACK_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=_FACTOR_KEYS,
    ranked=roe_ranked,
)

SIZE_PERCENTILE = SignalField(
    name="factor_percentiles.size_percentile",
    unit=Unit.PERCENTILE,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "Where this symbol's market capitalisation sits within the Universe, as "
        "a percentile from 0 to 100. **Higher means larger.** The research this "
        "field comes from declares its direction the other way round, as "
        "+ = smaller, which folds the small-cap premium into the sign of the "
        "number; a premium is a claim about returns, and a descriptive field does "
        "not make one. The session the capitalisation was read from is stamped "
        "beside it."
    ),
    kind=FieldKind.PERCENTILE,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.STORED,
    min_sessions=FACTOR_MIN_SESSIONS,
    lookback_sessions=FACTOR_LOOKBACK_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=_FACTOR_KEYS,
    ranked=size_ranked,
)

CROSS_SECTIONAL_FIELDS: tuple[SignalField, ...] = (
    MOMENTUM_RANK,
    TREND_SIGNAL,
    RELATIVE_STRENGTH,
    EARNINGS_YIELD_PERCENTILE,
    BOOK_YIELD_PERCENTILE,
    ROE_PERCENTILE,
    SIZE_PERCENTILE,
)


# --- The foreign-flow cluster --------------------------------------------
#
# The distinctive dataset, and the one whose contract carries the most. Its
# predictive claim is unverified for Vietnam, so both served fields are
# descriptive and say so in their own interpretation; the share-denominated twin
# has no stored inputs and is registered refused rather than filled with the
# money figure.

FOREIGN_FLOW_PRESSURE = SignalField(
    # The id the Analysis Field Profile already names (spec 0003 §8.4).
    name="foreign_flow_pressure.net_value_over_adtv",
    unit=Unit.RATIO,
    sign=Sign.SIGNED,
    interpretation=(
        "Net foreign buying over the last "
        f"{FOREIGN_FLOW_SESSIONS} sessions divided by this symbol's average "
        "daily traded value over the same sessions — **both in money** — so the "
        "number is in days of ordinary turnover. **Positive means net foreign "
        "buying.** It describes what foreign investors did and nothing about "
        "what the price will do: no verified published result shows that HOSE "
        "foreign net buying forecasts subsequent returns, and this field makes "
        "no such claim. A foreign ownership room that is full stops buying "
        "mechanically rather than by anyone's choice, so the room state travels "
        "beside the number and an exhausted room degrades it."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=FOREIGN_FLOW_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=(
        "standard_error",
        "standard_error_basis",
        "standard_error_lags",
        "net_value_vnd",
        "adtv_vnd",
        "numerator_basis",
        "denominator_basis",
        "sessions",
        "foreign_room_state",
        "foreign_room_available_share",
        "foreign_room_as_of",
    ),
    reading=net_value_over_adtv_reading,
)

FOREIGN_FLOW_PERSISTENCE = SignalField(
    name="foreign_flow_pressure.persistence_run_days",
    unit=Unit.SESSIONS,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "How many consecutive sessions this symbol's net foreign flow has held "
        f"one sign, looked for over the last {FOREIGN_PERSISTENCE_SESSIONS} "
        "sessions. The direction of the streak is beside it — a long run of "
        "selling and a long run of buying are the same length and not the same "
        "fact. It says how long the flow has held a side and nothing about how "
        "long it will: the Vietnamese predictiveness of foreign flow is "
        "unverified. A session of exactly zero net flow ends a run rather than "
        "extending it."
    ),
    kind=FieldKind.SIGNAL,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=FOREIGN_PERSISTENCE_MIN_SESSIONS,
    threshold=Threshold(
        value=PERSISTENCE_RUN_THRESHOLD,
        origin=ThresholdOrigin.DERIVED,
        # No published convention says how long a foreign-flow streak has to be
        # before it is remarkable, which is part of why this field needed a
        # null rather than a number somebody liked.
        convention=None,
        derived=PERSISTENCE_RUN_THRESHOLD,
        note=(
            "The two nulls disagree by nearly a factor of two, and the "
            "disagreement is the whole argument for running the block "
            "permutation. Under independently drawn flows — the GBM nulls, "
            "truncated or not — the 99th percentile of the run length is 7 "
            "sessions, which is a coin landing the same way seven times. Under "
            "the stationary block bootstrap over a flow series carrying the "
            "session-to-session persistence foreign flows actually have, it is "
            "12. A field calibrated on the independent null alone would fire on "
            "about 9% of null windows. "
            "The smallest length clearing the 1% ceiling on all three is 13, "
            "where the bootstrap sits at 0.95% — close enough to the ceiling "
            "that a rerun could cross it. The shipped 15 is a margin over that "
            "measurement rather than a second derivation: it puts the worst "
            "null at 0.43%, under half the ceiling, and a rerun landing a "
            "session either way does not move the constant."
        ),
    ),
    null_fpr=NullCalibration(
        gbm=0.0001,
        gbm_truncated=0.0001,
        block_bootstrap=0.0043,
        paths=NULL_DERIVATION_PATHS,
        seed=NULL_DERIVATION_SEED,
    ),
    output_keys=(
        "run_sign",
        "run_net_value_vnd",
        "sessions",
        "foreign_room_state",
        "foreign_room_available_share",
        "foreign_room_as_of",
    ),
    reading=persistence_run_days_reading,
    statistic=persistence_run_days,
)

FOREIGN_FLOW_SHARE_PRESSURE = SignalField(
    name="foreign_flow_pressure.net_volume_over_adtv",
    unit=Unit.RATIO,
    sign=Sign.SIGNED,
    interpretation=(
        "Net foreign buying in **shares** over this symbol's average daily "
        "traded share count. The numerator comes from stored DNSE G1 cumulative "
        "foreign buy/sell share counts and is served only when every session in "
        "the window is present. It never substitutes the money-denominated "
        "ratio beside it."
    ),
    kind=FieldKind.ESTIMATOR,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=FOREIGN_FLOW_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    requires_foreign_share_flow=True,
    output_keys=(
        "standard_error",
        "standard_error_basis",
        "standard_error_lags",
        "net_volume_shares",
        "adtv_shares",
        "numerator_basis",
        "denominator_basis",
        "sessions",
        "missing_input",
        "foreign_room_state",
        "foreign_room_available_share",
        "foreign_room_as_of",
    ),
    reading=net_volume_over_adtv_reading,
)

FOREIGN_ROOM_PCT = SignalField(
    # The id the Analysis Field Profile already names on the Money-flow axis
    # (spec 0003 §8.4). It belongs to the company profile by name and to this
    # cluster by inputs: it is the fact that says whether a flow beside it was
    # freely chosen or mechanically capped.
    name="company_profile.foreign_room_pct",
    unit=Unit.PERCENT,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "How much of this symbol's statutory foreign ownership cap is still "
        "open, as a percentage of the cap. Zero means foreigners cannot buy at "
        "all, which stops a foreign flow mechanically rather than by anyone's "
        "choice. It is read from the newest reference snapshot at or before the "
        "session being answered for, and the date of that reading travels with "
        "it — the room changes over months, so a stale one is not today's."
    ),
    # Exact for the date it was read rather than estimated from a sample, so
    # there is no sampling error to ship beside it and the caveat that does
    # matter — how old the reading is — travels as its own key.
    kind=FieldKind.VOCABULARY,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.STORED,
    min_sessions=FOREIGN_ROOM_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    output_keys=(
        "current_room_shares",
        "total_room_shares",
        "foreign_room_state",
        "foreign_room_available_share",
        "foreign_room_as_of",
    ),
    reading=foreign_room_pct_reading,
)

FOREIGN_FLOW_FIELDS: tuple[SignalField, ...] = (
    FOREIGN_FLOW_PRESSURE,
    FOREIGN_FLOW_PERSISTENCE,
    FOREIGN_FLOW_SHARE_PRESSURE,
    FOREIGN_ROOM_PCT,
)


# --- Descriptive indicator vocabulary ------------------------------------

_NO_INDICATOR_EDGE = (
    "This is descriptive market vocabulary only: no out-of-sample edge is "
    "claimed after accounting for data snooping."
)

RSI = SignalField(
    name="indicator_pack.rsi_14",
    unit=Unit.INDEX_0_100,
    sign=Sign.NON_NEGATIVE,
    interpretation=(
        "Wilder's smoothed 14-session relative-strength index on the prepared "
        "closing prices, from 0 to 100, after "
        f"{INDICATOR_WARMUP_SESSIONS} sessions of warm-up. {_NO_INDICATOR_EDGE}"
    ),
    kind=FieldKind.VOCABULARY,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=RSI_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    reading=rsi_reading,
)

MACD = SignalField(
    name="indicator_pack.macd_12_26_vnd",
    unit=Unit.VND,
    sign=Sign.SIGNED,
    interpretation=(
        "The 12-session exponential moving average of the prepared closing "
        "prices minus the 26-session exponential moving average, in VND, after "
        f"{INDICATOR_WARMUP_SESSIONS} sessions of warm-up. "
        f"{_NO_INDICATOR_EDGE}"
    ),
    kind=FieldKind.VOCABULARY,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=MACD_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    reading=macd_reading,
)

BOLLINGER_PERCENT_B = SignalField(
    name="indicator_pack.bollinger_percent_b_20",
    unit=Unit.RATIO,
    sign=Sign.SIGNED,
    interpretation=(
        "The prepared close's position in its 20-session Bollinger envelope, "
        "as the unitless fraction from the lower band to the upper band; it "
        "may lie outside zero to one. "
        f"{_NO_INDICATOR_EDGE}"
    ),
    kind=FieldKind.VOCABULARY,
    claim=Claim.DESCRIPTIVE,
    source=FieldSource.COMPUTED,
    min_sessions=BOLLINGER_MIN_SESSIONS,
    threshold=None,
    null_fpr=None,
    reading=bollinger_percent_b_reading,
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
    ADTV_MONEY,
    ADTV_SHARES,
    AMIHUD_ILLIQUIDITY,
    ADTV_PERCENTILE,
    BAND_PRESSURE,
    MEAN_REVERSION_Z,
    MEAN_REVERSION_HALF_LIFE,
    REALIZED_VOLATILITY,
    PRICE_ZONE,
    MAX_DRAWDOWN,
    CURRENT_DRAWDOWN,
    DAYS_UNDERWATER,
    DRAWDOWN_VERSUS_BENCHMARK,
    SHARPE,
    SORTINO,
    MOMENTUM_RANK,
    TREND_SIGNAL,
    RELATIVE_STRENGTH,
    EARNINGS_YIELD_PERCENTILE,
    BOOK_YIELD_PERCENTILE,
    ROE_PERCENTILE,
    SIZE_PERCENTILE,
    FOREIGN_FLOW_PRESSURE,
    FOREIGN_FLOW_PERSISTENCE,
    FOREIGN_FLOW_SHARE_PRESSURE,
    FOREIGN_ROOM_PCT,
    RSI,
    MACD,
    BOLLINGER_PERCENT_B,
)


def registered_field(name: str) -> SignalField:
    """The declaration for one field, or a refusal to guess at one.

    ``KeyError`` rather than ``None``: a caller asking for a field by name has
    the name in its own source, so a missing one is a typo or a deletion rather
    than a condition to handle.
    """
    return REGISTRY[name]


def registry_version() -> str:
    """A stable identity for the declarations this build serves.

    Derived from the declarations themselves rather than bumped by hand, for the
    same reason ``contract_hash`` is taken over the prose: a version somebody
    has to remember to bump is a version that eventually names the wrong
    registry, and this one ends up in the Evidence Manifest, where being wrong
    is silent.

    Only the six declarations a reader acts on are hashed — name, unit, sign,
    claim, source and the sanctioned interpretation. A threshold or a null
    calibration moving does change the numbers, but it is the *reading* of a
    field that an answer is disputed against.
    """
    digest = hashlib.sha256()
    for name in sorted(REGISTRY):
        entry = REGISTRY[name]
        digest.update(
            "\x00".join(
                (
                    entry.name,
                    entry.unit.value,
                    entry.sign.value,
                    entry.claim.value,
                    entry.source.value,
                    entry.interpretation,
                )
            ).encode("utf-8")
        )
        digest.update(b"\x01")
    return digest.hexdigest()[:16]


def signal_fields() -> tuple[SignalField, ...]:
    """Every registered field that can fire, in declaration order.

    What the null harness is parametrised over. A field added to the registry is
    therefore a field the harness runs, without anybody remembering to add it
    anywhere — which is the difference between a gate and a convention.
    """
    return tuple(entry for entry in REGISTRY.values() if entry.fires)


def fields_of_kind(kind: FieldKind) -> tuple[SignalField, ...]:
    return tuple(entry for entry in REGISTRY.values() if entry.kind is kind)
