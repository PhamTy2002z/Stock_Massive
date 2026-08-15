"""How often each registered signal fires on data that contains no signal.

This is the gate ADR-0010 puts in front of the catalog, and it is a test rather
than a document because a bar that cannot be run is a checklist. It is
parametrised over the registry, so a field added there is a field measured here
without anybody remembering to add it — and a field that drifts past the ceiling
fails the suite rather than shipping with a stale number beside it.

Three measurements per field, all at a fixed seed:

- **matched-volatility GBM**, across the range of daily volatilities this
  system's symbols actually span;
- **the same, truncated at ±7%**, which is the only one of the three that
  produces limit-locked sessions — the zero-variance bars every robust baseline
  here is built to exclude;
- **a stationary block bootstrap** over bar histories carrying fat tails and
  volatility clustering, which GBM has neither of.

The published rate is the maximum of them, and the ceiling is a flat 1% for the
whole catalog rather than a number each field declares for itself. A
self-declared rate is exactly the failure measured in the external library this
system rejected: it only ever drifts upward, and always when somebody wants
their field shipped.

The harness runs at fewer paths than the derivation that froze the thresholds —
enough to catch a field that has drifted, not enough to re-derive a threshold,
which is deliberate. Nothing here is allowed to change a shipped constant.
"""

from __future__ import annotations

from dataclasses import replace

import numpy as np
import pytest

from src.stocks.signals.fields import (
    CATALOG_NULL_FPR_CEILING,
    FieldKind,
    SignalField,
    Threshold,
    ThresholdOrigin,
)
from src.stocks.signals.nulls import (
    MATCHED_DAILY_VOLATILITIES,
    REFERENCE_HISTORIES,
    block_bootstrap_shapes,
    false_positive_rate,
    frames_from,
    gbm_shapes,
    null_quantile,
    reference_bar_history,
)
from src.stocks.signals.registry import (
    NULL_DERIVATION_SEED,
    REGISTRY,
    VOLATILITY_REGIME_Z,
    signal_fields,
)

# ADR-0010's floor is a thousand paths per null. The two GBM nulls run a little
# over it; the bootstrap runs well over, because it is the only one whose true
# rate is near enough to the ceiling for sampling noise to matter — at a rate of
# roughly half a percent, a thousand paths would fail this suite by luck about
# once in three hundred runs.
GBM_PATHS_PER_VOLATILITY = 400
BOOTSTRAP_PATHS_PER_HISTORY = 375

# How far the harness's measurement may sit above the rate the registry
# publishes before the registry is understating it. Generous on purpose: this is
# a sanity bound against a number written from a different statistic, not a
# second calibration, and at these path counts the measurement's own noise is a
# large fraction of the rate.
REGISTRY_DRIFT_FACTOR = 3.0


def _gbm_rates(field: SignalField, truncated: bool) -> tuple[float, int]:
    """The worst false-positive rate across the volatilities this field ships for.

    Worst rather than average: a field is shipped for every symbol at once, so
    the rate a reader is owed is the one it fires at on the symbol it behaves
    worst on.
    """
    rng = np.random.default_rng(NULL_DERIVATION_SEED)
    rates: list[float] = []
    paths = 0
    for sigma in MATCHED_DAILY_VOLATILITIES:
        shapes = gbm_shapes(
            rng,
            paths=GBM_PATHS_PER_VOLATILITY,
            sessions=field.min_sessions,
            daily_volatility=sigma,
            truncated=truncated,
        )
        rates.append(false_positive_rate(field, frames_from(shapes)))
        paths += GBM_PATHS_PER_VOLATILITY
    return max(rates), paths


def _bootstrap_rate(field: SignalField) -> tuple[float, int]:
    """The rate across several independent bar histories, pooled.

    Pooled rather than worst-of, because each history is one symbol's luck and
    the threshold is frozen for all of them. Taking the worst history would
    calibrate the catalog against whichever draw happened to be wildest.
    """
    rng = np.random.default_rng(NULL_DERIVATION_SEED)
    fired = 0
    measured = 0
    for _ in range(REFERENCE_HISTORIES):
        history = reference_bar_history(rng)
        shapes = block_bootstrap_shapes(
            rng,
            history,
            paths=BOOTSTRAP_PATHS_PER_HISTORY,
            sessions=field.min_sessions,
        )
        frames = frames_from(shapes)
        rate = false_positive_rate(field, frames)
        fired += rate * len(frames)
        measured += len(frames)
    return fired / measured, measured


@pytest.fixture(scope="module")
def measured() -> dict[str, dict[str, tuple[float, int]]]:
    """Every signal field run against all three nulls, once for the module.

    Module-scoped because the nulls are the expensive part and the assertions
    below are all reading the same measurement: a per-test fixture would run
    fifteen thousand paths three times over to answer three questions about one
    number.
    """
    results: dict[str, dict[str, tuple[float, int]]] = {}
    for field in signal_fields():
        results[field.name] = {
            "gbm": _gbm_rates(field, truncated=False),
            "gbm_truncated": _gbm_rates(field, truncated=True),
            "block_bootstrap": _bootstrap_rate(field),
        }
    return results


def _names() -> list[str]:
    return [field.name for field in signal_fields()]


class TestEverySignalFieldClearsTheCatalogCeiling:
    def test_the_registry_has_a_signal_field_to_measure(self):
        """An empty parametrisation passes every test in this file silently."""
        assert signal_fields(), "the registry declares no field that can fire"

    @pytest.mark.parametrize("name", _names())
    def test_the_published_rate_is_under_one_percent(self, name, measured):
        """The maximum of the two nulls, against a flat catalog-wide ceiling.

        A field that cannot reach 1% gets a stricter threshold or does not enter
        the catalog. It does not get a ceiling of its own.
        """
        rates = {label: rate for label, (rate, _) in measured[name].items()}
        published = max(rates.values())

        assert published <= CATALOG_NULL_FPR_CEILING, (
            f"{name} fires on {published:.3%} of null windows "
            f"(ceiling {CATALOG_NULL_FPR_CEILING:.1%}); by null: {rates}"
        )

    @pytest.mark.parametrize("name", _names())
    def test_both_nulls_ran_at_least_a_thousand_paths(self, name, measured):
        """The floor ADR-0010 sets, asserted rather than assumed."""
        for label, (_, paths) in measured[name].items():
            assert paths >= 1000, f"{name}'s {label} null ran {paths} paths"

    @pytest.mark.parametrize("name", _names())
    def test_the_bootstrap_is_measured_and_not_only_the_gbm(self, name, measured):
        """GBM alone is not the bar, and the two do not agree.

        A detector silent on Brownian motion can still fire constantly on a real
        quiet series, because GBM has neither fat tails nor serial dependence.
        This asserts the second null is actually exercised — that it ran, and
        that it is the harder of the two rather than a formality.
        """
        gbm, _ = measured[name]["gbm"]
        bootstrap, _ = measured[name]["block_bootstrap"]

        assert bootstrap > 0.0
        assert bootstrap >= gbm

    @pytest.mark.parametrize("name", _names())
    def test_the_registry_does_not_understate_what_was_measured(self, name, measured):
        """The frozen number and the running one have to be about the same field.

        Not a second calibration — the harness runs far fewer paths than the
        derivation did, deliberately, so that nothing here can move a shipped
        constant. What it catches is a registry number written for a different
        statistic, or left behind when one changed.
        """
        published = max(rate for rate, _ in measured[name].values())
        declared = REGISTRY[name].null_fpr
        assert declared is not None

        assert published <= declared.published * REGISTRY_DRIFT_FACTOR, (
            f"{name} measures {published:.3%} against a registered "
            f"{declared.published:.3%}"
        )


class TestTheDerivationTheFrozenThresholdCameFrom:
    def test_the_null_demands_more_than_convention_does(self):
        """Which is the whole claim ``ThresholdOrigin.DERIVED`` makes.

        Re-run here at a fraction of the derivation's paths, so this checks that
        the statistic still has the shape the frozen constant was measured
        against — not that the constant is right to two decimal places. The
        bounds are wide on purpose: a rerun that lands a tenth either side must
        not move a shipped threshold, and nothing in ``make test`` is allowed to.
        """
        field = VOLATILITY_REGIME_Z
        assert field.threshold is not None
        assert field.statistic is not None

        rng = np.random.default_rng(NULL_DERIVATION_SEED)
        history = reference_bar_history(rng)
        shapes = block_bootstrap_shapes(
            rng, history, paths=2000, sessions=field.min_sessions
        )

        demanded = null_quantile(
            field.statistic, frames_from(shapes), CATALOG_NULL_FPR_CEILING
        )

        assert field.threshold.convention is not None
        assert demanded > field.threshold.convention
        assert 0.5 * field.threshold.value <= demanded <= 1.5 * field.threshold.value


class TestTheGateActuallyBites:
    def test_the_conventional_threshold_would_fail_this_gate(self):
        """Which is why the derived value won, and why the harness exists at all.

        At the literature's z = 2 the volatility-regime field fires on several
        percent of bootstrapped null windows — several times the catalog ceiling.
        Convention is the looser of the two candidates here, and shipping it
        would have shipped a detector that is wrong once a month on a symbol
        nothing is happening to.
        """
        loose = replace(
            VOLATILITY_REGIME_Z,
            threshold=Threshold(
                value=2.0,
                origin=ThresholdOrigin.CONVENTION,
                convention=2.0,
                derived=1.0,
                note="convention alone, for this test",
            ),
        )
        rng = np.random.default_rng(NULL_DERIVATION_SEED)
        history = reference_bar_history(rng)
        shapes = block_bootstrap_shapes(
            rng, history, paths=1000, sessions=loose.min_sessions
        )

        rate = false_positive_rate(loose, frames_from(shapes))

        assert rate > CATALOG_NULL_FPR_CEILING


class TestTheMetadataTheNullRunRequires:
    @pytest.mark.parametrize("name", _names())
    def test_a_signal_field_carries_a_frozen_threshold_and_a_measured_null(self, name):
        """Missing metadata fails the suite, which is the other half of the gate."""
        field = REGISTRY[name]

        assert field.kind is FieldKind.SIGNAL
        assert field.threshold is not None
        assert field.null_fpr is not None
        assert field.null_fpr.paths >= 1000
        assert field.statistic is not None

    @pytest.mark.parametrize("name", _names())
    def test_the_recorded_calibration_names_its_seed(self, name):
        """A derivation nobody can repeat is one nobody can argue with."""
        field = REGISTRY[name]
        assert field.null_fpr is not None
        assert field.null_fpr.seed == NULL_DERIVATION_SEED
