"""The baseline a gate run is read against, and the drift the thresholds miss.

``docs/adr/0016``: the baseline is the **most recent passing gate run**, read
from ``eval_run`` — *in SQL, not by eye*, which is one of the two reasons that
table exists at all. Two rules sit on top of it:

**Drift is reported even when the category is still above threshold.** A drop of
two case-equivalents or more does not block the merge and **must be explained in
prose in the pull request**. Absolute thresholds catch collapse and miss decay,
so silence is not an option.

**A moved ``fixture_version`` voids the baseline.** The first run on a new
fixture is marked ``baseline_reset`` and its pull request may not claim "no
regression", because comparing scores across two fixtures compares two different
exams. A run with **no** history is a different thing and is not marked: it
establishes the baseline, and nothing regressed because there was nothing to
regress from.

**What "passing" means here, stated rather than implied.** These are the
deterministic totals — the ones a machine decided. The blind human rubric scores
interpretation fidelity and contradictory-evidence exposure on top of them
(``docs/adr/0016``), and those scores enter the same thresholds and the same
hard-fail rule *in the pull request*, not in this table. So a baseline resolved
here is the most recent gate run that passed **the machine's half**, and the
report says so where a reader could otherwise assume more.
"""

from __future__ import annotations

import uuid
from collections.abc import Mapping
from dataclasses import dataclass
from datetime import datetime
from fractions import Fraction
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from src.alpha.models import EvalRun

from .cases import EvalCategory
from .verdict import THRESHOLDS

#: How large a fall has to be before the pull request owes an explanation. Two
#: **case-equivalents**: not two runs, and not two percentage points. A category
#: of eight cases that loses two of them has lost a quarter of what it measures,
#: and that is the unit the ADR states the rule in.
CASE_EQUIVALENT_DRIFT = 2


@dataclass(frozen=True)
class CategoryScore:
    """One category's counts, and the only place the rate is derived.

    Counts are what the table stores, deliberately: the thresholds differ by
    category and the hard fail on a backwards sign overrides every rate, so a
    stored percentage would be a number two later readers would disagree about
    the meaning of.
    """

    category: str
    cases: int
    runs: int
    passed: int

    @property
    def rate(self) -> float:
        """Passes over runs, and zero where nothing ran.

        Zero rather than ``None`` or one. A category with no runs has not been
        proved and must not read as proved, and every caller here compares
        against a threshold — where a ``None`` would have to be branched on and
        eventually would not be.
        """
        return self.passed / self.runs if self.runs else 0.0

    @property
    def threshold(self) -> float:
        """The category's own bar, taken from ``verdict`` and never restated.

        One table of thresholds in this package, because the report, the
        verdict and the baseline all read it — and a second copy would be the
        one that did not move when a bar did.
        """
        try:
            return THRESHOLDS[EvalCategory(self.category)]
        except ValueError:  # pragma: no cover - a letter this build lacks
            return 1.0

    @property
    def meets_threshold(self) -> bool:
        """Whether the machine's half of this category passed.

        A category nobody ran does not meet it. ``cases == 0`` is a battery that
        lost its cases rather than one that answered them all correctly, and the
        two must never read the same.

        The safety categories take no rate at all: ``passed == runs``, because
        a rate of exactly 1.0 is satisfied by rounding and one leak is a leak.
        """
        if not self.cases or not self.runs:
            return False
        try:
            if EvalCategory(self.category).is_safety:
                return self.passed == self.runs
        except ValueError:  # pragma: no cover - a letter this build lacks
            return False
        return self.rate >= self.threshold


@dataclass(frozen=True)
class SurfaceScore:
    """One lane's counts, with no threshold to meet.

    Its own type rather than a :class:`CategoryScore` holding ``"turn"``.
    ``docs/adr/0016`` sets thresholds per **category**, not per surface — asked
    of a lane, ``threshold`` has no answer, and a shared type would have to
    invent one. This one cannot be asked.
    """

    surface: str
    cases: int
    runs: int
    passed: int

    @property
    def rate(self) -> float:
        return self.passed / self.runs if self.runs else 0.0


@dataclass(frozen=True)
class Baseline:
    """The gate run this one is compared against."""

    run_id: uuid.UUID
    started_at: datetime
    prompt_version: str
    fixture_version: str
    category_totals: Mapping[str, Any]
    report_path: str | None

    def score(self, category: str) -> CategoryScore:
        return _score_of(self.category_totals, category)


@dataclass(frozen=True)
class CategoryDiff:
    """One category, then and now, in the unit the ADR states the rule in."""

    category: str
    current: CategoryScore
    baseline: CategoryScore

    @property
    def exact_case_equivalents(self) -> Fraction:
        """The signed change, in whole cases, computed without floating point.

        Scaled by the number of cases rather than compared run-for-run, so the
        rule survives a battery that grew: eight cases at 85% and ten cases at
        85% are the same standard, and a raw count of passes would call the
        second an improvement.

        Where a category has stopped running entirely, the baseline's own case
        count is the scale. Zero times any fall is zero, and a category that
        vanished is the one drop nobody would notice on their own.

        A ``Fraction`` because the rule is an equality at the boundary and the
        boundary is where it will be argued about: ten cases falling from 30/30
        to 24/30 is exactly two case-equivalents, and in binary floating point
        it is 1.9999999999999996 — which is to say, in floating point the ADR's
        rule would quietly not fire on the example it was written for.
        """
        scale = self.current.cases or self.baseline.cases
        return (_exact_rate(self.current) - _exact_rate(self.baseline)) * scale

    @property
    def case_equivalents(self) -> float:
        """The same number, for display and for readers who want a float."""
        return float(self.exact_case_equivalents)

    @property
    def drifted(self) -> bool:
        """A fall of two case-equivalents or more, threshold or no threshold."""
        return self.exact_case_equivalents <= -Fraction(CASE_EQUIVALENT_DRIFT)


@dataclass(frozen=True)
class BaselineComparison:
    """What this run is worth beside the last passing one, or why it is not.

    Three states, and the third is why ``baseline_reset`` is not simply "there
    is no diff":

    - a comparison, with ``diffs`` and no reset;
    - **``baseline_reset``** — a baseline exists and the fixture moved under it,
      so the numbers are not comparable and this pull request may not claim *no
      regression*;
    - **no baseline at all** — the first gate run, which *establishes* the
      baseline. Nothing regressed because there is nothing to have regressed
      from, and calling that a reset would put a warning about a void comparison
      on a run that never had one.

    ``diffs`` is empty in both of the last two, because showing numbers is how a
    pull request comes to claim no regression against a different exam.
    """

    baseline: Baseline | None
    baseline_reset: bool
    diffs: tuple[CategoryDiff, ...] = ()

    @property
    def drifted(self) -> tuple[CategoryDiff, ...]:
        return tuple(diff for diff in self.diffs if diff.drifted)

    def as_wire(self) -> dict[str, Any]:
        return {
            "baseline_run_id": (
                None if self.baseline is None else str(self.baseline.run_id)
            ),
            "baseline_fixture_version": (
                None if self.baseline is None else self.baseline.fixture_version
            ),
            "baseline_reset": self.baseline_reset,
            "drifted_categories": [diff.category for diff in self.drifted],
        }


def run_passes(category_totals: Mapping[str, Any]) -> bool:
    """Whether these totals clear every category's bar, deterministically.

    An incomplete run never passes and has no score at all: a battery that
    truncates itself and publishes a total is a battery that lies, so the
    counts it did produce are not a smaller score — they are not a score.

    **One recorded hard fail is enough to fail the run**, whatever the rates
    say. Narrating a registered field backwards in sign or direction is a hard
    fail at 1/3 (``docs/adr/0016``) — that is the exact defect that disqualified
    the assessed external library, and letting it dissolve into an average is
    the failure this rule exists against.
    """
    if not category_totals.get("complete", False):
        return False
    if category_totals.get("hard_fails"):
        return False
    by_category = category_totals.get("by_category") or {}
    if not by_category:
        return False
    return all(
        _score_of(category_totals, category.value).meets_threshold
        for category in EvalCategory
    )


def resolve_baseline(
    session: Session, *, exclude: uuid.UUID | None = None
) -> Baseline | None:
    """The most recent passing gate run, or ``None`` where there is not one.

    The query does what a query can: gate mode only, finished only, newest
    first, and never the run asking the question. A **smoke** run is excluded in
    SQL rather than filtered later, because it is the one exclusion that must
    not depend on anybody remembering it — a smoke run does not exercise the
    production model, so a report compared against one compares against nothing.

    The session is the caller's: it opened it and it closes it, as everywhere
    else in this package. A callee that closed a handle it was lent is a callee
    the caller cannot use twice.

    The pass mark itself is applied in Python over the rows that come back.
    Expressing per-category rate arithmetic over a JSONB column in SQL would put
    a second copy of ``CATEGORY_THRESHOLDS`` in a dialect nobody tests, and the
    two would disagree the first time a threshold moved.
    """
    query = (
        select(EvalRun)
        .where(
            EvalRun.mode == "gate",
            EvalRun.finished_at.is_not(None),
        )
        .order_by(EvalRun.started_at.desc(), EvalRun.id.desc())
    )
    if exclude is not None:
        query = query.where(EvalRun.id != exclude)

    for row in session.execute(query).scalars():
        totals = dict(row.category_totals or {})
        if run_passes(totals):
            return Baseline(
                run_id=row.id,
                started_at=row.started_at,
                prompt_version=row.prompt_version,
                fixture_version=row.fixture_version,
                category_totals=totals,
                report_path=row.report_path,
            )
    return None


def compare_to_baseline(
    category_totals: Mapping[str, Any],
    fixture_version: str,
    baseline: Baseline | None,
) -> BaselineComparison:
    """This run against the last passing one, or a stated reason there is none.

    ``baseline_reset`` is reserved for the case ``docs/adr/0016`` gives it: *when
    ``fixture_version`` changes the previous baseline is void.* A first-ever gate
    run is not that — it establishes the baseline — and marking it reset would
    warn a pull request off a claim it was never in a position to make.
    """
    if baseline is None:
        return BaselineComparison(baseline=None, baseline_reset=False)
    if baseline.fixture_version != fixture_version:
        return BaselineComparison(baseline=baseline, baseline_reset=True)
    return BaselineComparison(
        baseline=baseline,
        baseline_reset=False,
        diffs=tuple(
            CategoryDiff(
                category=category.value,
                current=_score_of(category_totals, category.value),
                baseline=baseline.score(category.value),
            )
            for category in EvalCategory
        ),
    )


def category_scores(category_totals: Mapping[str, Any]) -> tuple[CategoryScore, ...]:
    """Every category as a score, in the letters' own order."""
    return tuple(
        _score_of(category_totals, category.value) for category in EvalCategory
    )


def surface_scores(category_totals: Mapping[str, Any]) -> tuple[SurfaceScore, ...]:
    """The two lanes as scores, so a reader can take the run apart by surface."""
    buckets = category_totals.get("by_surface") or {}
    return tuple(
        SurfaceScore(
            surface=name,
            cases=int((buckets.get(name) or {}).get("cases", 0) or 0),
            runs=int((buckets.get(name) or {}).get("runs", 0) or 0),
            passed=int((buckets.get(name) or {}).get("passed", 0) or 0),
        )
        for name in sorted(buckets)
    )


def category_scores_by_surface(
    category_totals: Mapping[str, Any],
) -> tuple[tuple[str, tuple[SurfaceScore, ...]], ...]:
    """Each category split by the lane it was measured on, where both ran it.

    The two lanes share D and E, and a category total covering both is where a
    regression in the nightly artifact hides behind a healthy Turn lane. Only
    categories a second lane actually touched are returned: a row saying
    ``analysis 0/0`` beside every safety category would be four lines of noise
    about a surface those categories are not asked of.
    """
    split = category_totals.get("by_category_surface") or {}
    return tuple(
        (
            category,
            tuple(
                SurfaceScore(
                    surface=surface,
                    cases=int((bucket or {}).get("cases", 0) or 0),
                    runs=int((bucket or {}).get("runs", 0) or 0),
                    passed=int((bucket or {}).get("passed", 0) or 0),
                )
                for surface, bucket in sorted(lanes.items())
                if (bucket or {}).get("cases")
            ),
        )
        for category, lanes in sorted(split.items())
        if sum(1 for bucket in lanes.values() if (bucket or {}).get("cases")) > 1
    )


def _score_of(category_totals: Mapping[str, Any], category: str) -> CategoryScore:
    buckets = category_totals.get("by_category") or {}
    return _bucket_score(category, buckets.get(category) or {})


def _exact_rate(score: CategoryScore) -> Fraction:
    """The pass rate as a fraction, so a comparison at the boundary is exact."""
    return Fraction(score.passed, score.runs) if score.runs else Fraction(0)


def _bucket_score(name: str, bucket: Mapping[str, Any]) -> CategoryScore:
    return CategoryScore(
        category=name,
        cases=int(bucket.get("cases", 0) or 0),
        runs=int(bucket.get("runs", 0) or 0),
        passed=int(bucket.get("passed", 0) or 0),
    )


__all__ = [
    "CASE_EQUIVALENT_DRIFT",
    "Baseline",
    "BaselineComparison",
    "CategoryDiff",
    "CategoryScore",
    "SurfaceScore",
    "category_scores",
    "category_scores_by_surface",
    "compare_to_baseline",
    "resolve_baseline",
    "run_passes",
    "surface_scores",
]
