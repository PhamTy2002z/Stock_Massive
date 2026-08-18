"""The Analysis lane's cases: ten seats, three runs each, scored by D and E.

``docs/adr/0016`` gives this lane roughly ten cases inside the same budget
ceiling and the same ``eval_run`` as the Turn lane, scored by the two quality
categories the nightly artifact can fail at: **interpretation fidelity** (D) and
**data-gap behaviour** (E).

**Why D runs across four industries.** Emphasis and field membership differ by
industry — the banks profile adds three fundamentals no other profile has, and
the News axis is refused for everybody — so one representative symbol would
prove that the pipeline works for one shape of envelope and nothing more.

**Why three cases share a seat with another.** There are eight seats and the
ADR asks for ten cases, and the three that double up assert something the
first case about that seat does not: that the industry block's unavailable
metrics reach the artifact as refused evidence rather than being quietly
dropped. A case is a question, not a symbol, and two questions about one symbol
are two cases.

**What is deliberately not asserted here.** Whether the reading is *within* the
field's sanctioned interpretation, and whether material contradictory evidence
was omitted. Those are the blind human rubric's (``docs/adr/0016``), and an
expectation field for them would be this module guessing at what only a person
can decide.
"""

from __future__ import annotations

from src.alpha.field_profile import (
    INDUSTRY_FUNDAMENTAL_FIELDS,
    NEWS_FIELDS,
    AnalysisIndustry,
)

from .cases import (
    AnalysisExpectation,
    EvalCase,
    EvalCategory,
    EvalSurface,
    Expectation,
    register,
)
from .roles import FixtureRole

#: The two approved-source news counts. No durable store stands behind either in
#: v1, so every profile carries the whole News axis refused — which makes it the
#: one data gap present on every seat.
NEWS_GAP: tuple[str, ...] = tuple(entry.field_id for entry in NEWS_FIELDS)


def _industry_gap(industry: AnalysisIndustry) -> tuple[str, ...]:
    """The per-industry fundamentals that have no store behind them in v1.

    Read off the profile rather than listed here. A hand-written list is the
    thing that stops being true: the day one of these gets a durable store, the
    field stops being refused and a case naming it would fail for the best
    possible reason, having been written down twice.
    """
    return tuple(
        entry.field_id for entry in INDUSTRY_FUNDAMENTAL_FIELDS.get(industry, ())
    )


def _case(
    identifier: str,
    *,
    category: EvalCategory,
    role: FixtureRole,
    intent: str,
    publishes: bool = True,
    failure_code: str | None = None,
    exposes_refused: tuple[str, ...] = (),
) -> EvalCase:
    return EvalCase(
        id=identifier,
        category=category,
        surface=EvalSurface.ANALYSIS,
        # An Analysis case has no prompt. Its input is the seat and the nightly
        # pipeline, which is the whole reason the surface is a separate lane.
        prompt="",
        role=role,
        expectation=Expectation(
            analysis=AnalysisExpectation(
                publishes=publishes,
                failure_code=failure_code,
                exposes_refused=exposes_refused,
            )
        ),
        intent=intent,
    )


ANALYSIS_CASES: tuple[EvalCase, ...] = register(
    # --- D: interpretation fidelity, across the four field profiles ---------
    _case(
        "analysis-d-bank",
        category=EvalCategory.INTERPRETATION,
        role=FixtureRole.BANK,
        intent=(
            "A bank's profile adds three fundamentals no other profile has. The "
            "verdict has to rest on figures that profile names, and the reading "
            "has to stay inside each field's sanctioned interpretation."
        ),
    ),
    _case(
        "analysis-d-real-estate",
        category=EvalCategory.INTERPRETATION,
        role=FixtureRole.REAL_ESTATE,
        intent=(
            "The same artifact for a developer, whose fundamental block is two "
            "fields rather than three. Emphasis differs by industry and one "
            "representative symbol proves nothing about the others."
        ),
    ),
    _case(
        "analysis-d-retail",
        category=EvalCategory.INTERPRETATION,
        role=FixtureRole.RETAIL,
        intent=(
            "A retailer, whose industry block is the third of the three the "
            "Analysis Field Profile has metrics for."
        ),
    ),
    _case(
        "analysis-d-ordinary",
        category=EvalCategory.INTERPRETATION,
        role=FixtureRole.ORDINARY,
        intent=(
            "A classified symbol in none of the three industries: the shared "
            "fundamentals and nothing added. The baseline the other three are "
            "read against."
        ),
    ),
    # --- E: data-gap behaviour, on the fixture's deliberate bad cases -------
    _case(
        "analysis-e-short-history",
        category=EvalCategory.DATA_GAP,
        role=FixtureRole.BELOW_MIN_SESSIONS,
        publishes=False,
        failure_code="insufficient_core_evidence",
        intent=(
            "Below the price-zone field's own floor, so the artifact's core "
            "evidence cannot be read. The pipeline must refuse the pair by name "
            "rather than publish an Analysis built around a figure it does not "
            "have."
        ),
    ),
    _case(
        "analysis-e-price-basis-seam",
        category=EvalCategory.DATA_GAP,
        role=FixtureRole.PRICE_BASIS_SEAM,
        exposes_refused=("momentum_rank.percentile_12_2",),
        intent=(
            "The window a twelve-month momentum percentile needs crosses the "
            "ADR-0006 price-basis seam while the twenty-one-session price zone "
            "does not. So the Analysis is published and the long-window field "
            "arrives refused: the gap is exposed rather than filled, and the "
            "prose has to say so instead of narrating around it."
        ),
    ),
    _case(
        "analysis-e-limit-lock",
        category=EvalCategory.DATA_GAP,
        role=FixtureRole.LIMIT_LOCK_DENSE,
        intent=(
            "At least a fifth of the served window is limit-locked, which is the "
            "registry's own degradation share. The figures are usable and "
            "degraded, so the artifact stands and the limitation has to be "
            "visible in the reading rather than read as if the window were whole."
        ),
    ),
    _case(
        "analysis-e-news-refused",
        category=EvalCategory.DATA_GAP,
        role=FixtureRole.ORDINARY,
        exposes_refused=NEWS_GAP,
        intent=(
            "Approved-source news is not persisted in v1, so the whole News axis "
            "is refused for every symbol. The axis still needs an emphasis and a "
            "read — saying what is missing — and neither count may support the "
            "verdict."
        ),
    ),
    _case(
        "analysis-e-bank-metrics",
        category=EvalCategory.DATA_GAP,
        role=FixtureRole.BANK,
        exposes_refused=_industry_gap(AnalysisIndustry.BANKS),
        intent=(
            "The bank block's three metrics are named by the profile and have no "
            "durable store behind them. They must reach the artifact refused, "
            "with a reason: an Analysis that dropped them would make two rows "
            "carrying the same fieldProfileVersion mean different things."
        ),
    ),
    _case(
        "analysis-e-retail-metrics",
        category=EvalCategory.DATA_GAP,
        role=FixtureRole.RETAIL,
        exposes_refused=_industry_gap(AnalysisIndustry.RETAIL),
        intent=(
            "The same question for the retail block, whose three metrics are the "
            "largest industry addition the profile makes."
        ),
    ),
)


__all__ = ["ANALYSIS_CASES", "NEWS_GAP"]
