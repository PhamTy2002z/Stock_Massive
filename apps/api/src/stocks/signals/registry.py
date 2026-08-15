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
from .volatility import (
    VOLATILITY_REGIME_BASELINE_DAYS,
    VOLATILITY_REGIME_MIN_SESSIONS,
    volatility_regime_z,
)

# The seed and path count the frozen numbers below were measured at. Recorded so
# the derivation can be repeated exactly rather than approximately: a threshold
# nobody can reproduce is a threshold nobody can argue with.
NULL_DERIVATION_SEED = 20260815
NULL_DERIVATION_PATHS = 16_000

VOLATILITY_REGIME_Z = SignalField(
    name="volatility_regime.robust_z_gk",
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
        "baseline_sessions",
        "limit_lock_days",
    ),
    statistic=volatility_regime_z,
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


REGISTRY: Mapping[str, SignalField] = _index(VOLATILITY_REGIME_Z)


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
