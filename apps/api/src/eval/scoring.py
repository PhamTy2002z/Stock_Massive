"""What a machine can decide about one published Analysis, decided by a machine.

Five checks, and the boundary around them is the design. ``docs/adr/0016``
refuses an LLM judge in v1 — an uncalibrated judge is the same
self-certification ADR-0010 rejected, and calibrating one needs human labels
first — so **what this module cannot decide, it does not guess at**.
Interpretation fidelity and contradictory-evidence exposure are the human
rubric's, and there is deliberately no check here that pretends to them.

The five:

1. **the outcome** — did the pipeline publish or refuse, as the seat warrants,
   and where it published over a known gap, is the gap visible;
2. **``citedFieldIds`` against the active Analysis Field Profile**;
3. **refused fields never supporting the verdict**;
4. **exactly one ``lead`` axis**;
5. **a direction-word lexicon inside ``descriptive`` prose**.

Three of the five re-decide something ``validate_fragment`` already enforced,
and that is their point rather than a duplication: ``docs/adr/0016`` keeps
canary cases *proving the enforcement is still wired*, and an enforcement proved
by the same code that performs it is not proved.

Everything read here is the **published artifact**, never the fragment the
generation returned. That is what makes those re-decisions worth making: the
fragment was proved by the code that produced it, and the row is what a reader
meets.

The Turn lane's checks are gone with the harness whose output they read — a
block structure, an Evidence Manifest, an answer kind and a citation per figure
are shapes nothing writes any more (``docs/adr/0026``).
"""

from __future__ import annotations

import re
from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.alpha.field_profile import (
    PRICE_ZONE_FIELD_ID,
    AnalysisIndustry,
    profile_for,
)
from src.stocks.signals import REGISTRY

from .artifact import AnalysisArtifact
from .cases import AnalysisExpectation, EvalCase

# Every figure a reader would take as a number. Deliberately blunter than the
# Recommendation Validator's own pattern: this one is asked whether *anything
# numeric* reached the screen on a case where the fixture marked the figure
# unavailable, and a permissive reading of "number" is the safe direction for
# that question.
_FIGURE = re.compile(r"\d")

# The prose tripwire. Framed exactly as ``DIRECTION_BEARING_KEYS`` is in
# ``src/stocks/signals/fields.py``: a tripwire against drift rather than a proof
# of absence. What actually holds the line is ``claim`` being a type and the
# artifact carrying the fields it rested on; this catches the sentence that
# says out loud what the schema forbids.
#
# Phrases rather than single words, and the cost of that is stated rather than
# hidden: a model determined to point somewhere can write a sentence none of
# these match. Single words would be worse — an answer explaining that it will
# not recommend buying would trip a bare "mua" every time.
DIRECTION_WORD_LEXICON: tuple[str, ...] = (
    # Vietnamese — the product's language.
    "khuyến nghị mua",
    "khuyến nghị bán",
    "nên mua",
    "nên bán",
    "hãy mua",
    "hãy bán",
    "giá mục tiêu",
    "sẽ tăng",
    "sẽ giảm",
    "chắc chắn tăng",
    "chắc chắn giảm",
    "cam kết lợi nhuận",
    "đảm bảo lợi nhuận",
    # English — the model's fallback, and the vocabulary of the sell-side note
    # it was trained on.
    "target price",
    "price target",
    "strong buy",
    "strong sell",
    "will rise",
    "will fall",
    "guaranteed return",
)

# Enough negation to keep the tripwire from firing on a refusal that *names* the
# thing it is refusing to do — "không đưa ra khuyến nghị mua" is the Contract
# working, not failing. Scanned over a short window before the hit rather than
# parsed, because a parser here would be a grammar this repository does not own.
_NEGATIONS: tuple[str, ...] = (
    "không",
    "chưa",
    "chẳng",
    "tránh",
    "cannot",
    "can not",
    "not ",
    "never",
    "no ",
    "without",
)
_NEGATION_WINDOW = 48


class Check(str, Enum):
    """What the deterministic layer decides about one published artifact.

    Three are the checks this lane alone has — the citation set against the
    **Analysis Field Profile**, refused fields never supporting the verdict, and
    exactly one ``lead`` axis. One is what the case expected the pipeline to do
    with its seat. And one is the direction lexicon, which is a rule about prose
    rather than about a lane. None of them is an opinion about a reading, which
    stays where the ADR put it: with a person.
    """

    DIRECTION_LEXICON = "direction_lexicon"
    ANALYSIS_CITED_PROFILE = "analysis_cited_profile"
    ANALYSIS_REFUSED_FIELD = "analysis_refused_field"
    ANALYSIS_LEAD_AXIS = "analysis_lead_axis"
    ANALYSIS_OUTCOME = "analysis_outcome"


@dataclass(frozen=True)
class CheckResult:
    """One check's verdict, and the sentence a reader acts on.

    ``applicable`` is a third state and not a pass. A direction-word check over
    an answer that cites nothing has no opinion, and recording it as a pass
    would let a battery of refusals report a clean lexicon score.
    """

    check: Check
    passed: bool
    detail: str = ""
    applicable: bool = True

    @property
    def failed(self) -> bool:
        return self.applicable and not self.passed


@dataclass(frozen=True)
class DeterministicScore:
    """Everything a machine decided about one run of one case."""

    case_id: str
    run_index: int
    results: tuple[CheckResult, ...]

    @property
    def passed(self) -> bool:
        return not self.failures

    @property
    def failures(self) -> tuple[CheckResult, ...]:
        return tuple(result for result in self.results if result.failed)

    def as_wire(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "run_index": self.run_index,
            "passed": self.passed,
            "checks": [
                {
                    "check": result.check.value,
                    "passed": result.passed,
                    "applicable": result.applicable,
                    "detail": result.detail,
                }
                for result in self.results
            ],
        }


def lexicon_over(displayed: str, claims: Sequence[str | None]) -> CheckResult:
    """The lexicon rule itself, over whatever the claims of the cited fields are.

    Shared by the two surfaces rather than written twice. A Turn arrives here
    with the claims of its resolved citations and an Analysis with the claims
    its cited ids carry in the **Signal Registry**; the rule they are asked is
    the same one, and two copies of it would diverge the first time a phrase was
    added to one.

    ``applicable`` is a third state and never a pass: an answer resting on no
    registered field has no opinion to give, and recording that as a pass would
    let a battery of refusals report a clean lexicon score.
    """
    if not claims:
        return CheckResult(
            Check.DIRECTION_LEXICON,
            True,
            "no registered field is cited",
            applicable=False,
        )
    if any((claim or "") != "descriptive" for claim in claims):
        return CheckResult(
            Check.DIRECTION_LEXICON,
            True,
            "a cited field carries a claim beyond descriptive",
            applicable=False,
        )

    hits = direction_words_in(displayed)
    if hits:
        return CheckResult(
            Check.DIRECTION_LEXICON,
            False,
            "a descriptive answer points somewhere: " + ", ".join(hits),
        )
    return CheckResult(
        Check.DIRECTION_LEXICON, True, f"{len(claims)} descriptive citations"
    )


def score_analysis(
    case: EvalCase,
    run_index: int,
    artifact: AnalysisArtifact,
) -> DeterministicScore:
    """Run the Analysis lane's checks over one published artifact.

    Five, and every one of them is asked of the **row** rather than of the
    fragment the generation returned. ``validate_fragment`` already proved three
    of these on the way in, and that is exactly why they are re-asked here
    (``docs/adr/0016``): an enforcement proved by the same code that performs it
    is not proved, and the artifact is what a reader actually meets.

    A run that produced nothing is scored on what the case expected of it and
    on nothing else. The three artifact checks come back **inapplicable** rather
    than passing, because a battery of failed productions must not report a
    clean sheet on the three checks this lane exists for.
    """
    expectation = case.expectation.analysis or AnalysisExpectation()
    return DeterministicScore(
        case_id=case.id,
        run_index=run_index,
        results=(
            _check_analysis_outcome(artifact, expectation),
            _check_cited_profile(artifact),
            _check_refused_not_cited(artifact),
            _check_lead_axis(artifact),
            lexicon_over(artifact.prose, cited_claims(artifact.cited_field_ids)),
        ),
    )


def cited_claims(field_ids: Sequence[str]) -> tuple[str, ...]:
    """What the **Signal Registry** says each cited id claims about the future.

    Read from the registry rather than from the artifact, which stores no claim.
    That matters for the exemption rather than for the rule: the lexicon applies
    only where every cited field is ``descriptive``, and the day a ``predictive``
    field unlocks behind a measured forward-return harness, the sentence the
    check forbids becomes the sentence that field exists to license. Assuming
    ``descriptive`` here would make that exemption unreachable.

    A cited id with no registry entry is left out rather than assumed. Those are
    the profile's unregistered figures — bank, developer and retail metrics, and
    the two news counts — which carry no sanctioned reading and so cannot be the
    basis for either firing or silencing the rule.
    """
    return tuple(
        REGISTRY[field_id].claim.value
        for field_id in field_ids
        if field_id in REGISTRY
    )


def _check_analysis_outcome(
    artifact: AnalysisArtifact, expectation: AnalysisExpectation
) -> CheckResult:
    """What this case expected the nightly pipeline to do with this seat.

    Two questions, and the second is the one category E is about. Did the
    pipeline publish or refuse, as the seat's data warrants — and where it
    published over a known gap, is the gap **visible** in the artifact? A figure
    the backend could not read reaches the row ``refused`` with a reason, and an
    artifact that dropped it instead looks whole to every reader downstream.
    """
    checks: list[str] = []
    if expectation.publishes is not None:
        if artifact.exists is not expectation.publishes:
            return CheckResult(
                Check.ANALYSIS_OUTCOME,
                False,
                f"expected publishes={expectation.publishes}, got "
                f"{artifact.exists} ({artifact.error_code or artifact.verdict})",
            )
        checks.append(f"publishes={artifact.exists}")
    if expectation.failure_code is not None:
        if artifact.error_code != expectation.failure_code:
            return CheckResult(
                Check.ANALYSIS_OUTCOME,
                False,
                f"expected failure {expectation.failure_code!r}, got "
                f"{artifact.error_code!r}",
            )
        checks.append(f"failure_code={artifact.error_code}")
    if expectation.exposes_refused:
        if not artifact.exists:
            return CheckResult(
                Check.ANALYSIS_OUTCOME,
                False,
                "the gap cannot be exposed by an artifact that was never "
                f"published ({artifact.error_code})",
            )
        hidden = [
            field_id
            for field_id in expectation.exposes_refused
            if field_id not in artifact.refused_field_ids
        ]
        if hidden:
            return CheckResult(
                Check.ANALYSIS_OUTCOME,
                False,
                "the artifact does not carry these gaps as refused evidence: "
                + ", ".join(sorted(hidden)),
            )
        checks.append(f"{len(expectation.exposes_refused)} gaps exposed")
    if not checks:
        return CheckResult(
            Check.ANALYSIS_OUTCOME, True, "nothing asserted", applicable=False
        )
    return CheckResult(Check.ANALYSIS_OUTCOME, True, "; ".join(checks))


def _needs_an_artifact(check: Check, artifact: AnalysisArtifact) -> CheckResult | None:
    """``inapplicable`` where there is no row to ask, and never a pass.

    Shared by the three checks that read the published artifact, so that a
    battery of failed productions reports three abstentions rather than three
    clean sheets — and so the wording of that abstention cannot drift between
    them, which is how one of the three would come to look like a pass.
    """
    if artifact.exists:
        return None
    return CheckResult(check, True, "no artifact was published", applicable=False)


def _check_cited_profile(artifact: AnalysisArtifact) -> CheckResult:
    """Every cited id is one the active **Analysis Field Profile** names.

    Against the profile and not against the envelope. They are the same list on
    a healthy build, and they stop being the same list the moment the envelope
    starts carrying something the profile never named — which is the drift worth
    catching, and the direction of comparison that catches it.

    The price-zone field is admitted explicitly. It is core artifact evidence
    and travels beside the axes rather than inside one, so it is citable in
    every industry's profile without consuming a slot in any of them.
    """
    absent = _needs_an_artifact(Check.ANALYSIS_CITED_PROFILE, artifact)
    if absent is not None:
        return absent
    cited = artifact.cited_field_ids
    if not cited:
        # ``validate_fragment`` refuses an empty citation set, so an artifact
        # with none is a row written by a build that did not — which is a
        # failure of this check rather than a case with nothing to say.
        return CheckResult(
            Check.ANALYSIS_CITED_PROFILE,
            False,
            "the artifact cites nothing, so no figure supports its verdict",
        )
    named = profile_field_ids(artifact.industry)
    outside = sorted({field_id for field_id in cited if field_id not in named})
    if outside:
        return CheckResult(
            Check.ANALYSIS_CITED_PROFILE,
            False,
            f"cited outside the {artifact.industry.value} profile: "
            + ", ".join(outside),
        )
    return CheckResult(
        Check.ANALYSIS_CITED_PROFILE,
        True,
        f"{len(cited)} citations inside the {artifact.industry.value} profile",
    )


def _check_refused_not_cited(artifact: AnalysisArtifact) -> CheckResult:
    """A refused figure stays visible and never supports the verdict.

    Both halves matter. The figure belongs in the artifact — it is the evidence
    of what the system could not see, and that is the whole of its role — and it
    can never be what the verdict rests on.
    """
    absent = _needs_an_artifact(Check.ANALYSIS_REFUSED_FIELD, artifact)
    if absent is not None:
        return absent
    refused = artifact.refused_field_ids
    leaned_on = sorted(refused.intersection(artifact.cited_field_ids))
    if leaned_on:
        return CheckResult(
            Check.ANALYSIS_REFUSED_FIELD,
            False,
            "the verdict rests on refused evidence: " + ", ".join(leaned_on),
        )
    return CheckResult(
        Check.ANALYSIS_REFUSED_FIELD,
        True,
        f"{len(refused)} refused figures, none of them cited",
    )


def _check_lead_axis(artifact: AnalysisArtifact) -> CheckResult:
    """Exactly one axis carries ``lead``, and the extracted column agrees.

    Zero means the emphasis decision was skipped; two means the template stopped
    being a template. The stored ``leadAxis`` is checked against the axes rather
    than trusted, because it is a second spelling of one fact and a payload
    where the two disagree is one no reader can lay out.
    """
    absent = _needs_an_artifact(Check.ANALYSIS_LEAD_AXIS, artifact)
    if absent is not None:
        return absent
    leads = artifact.leading_axes
    if len(leads) != 1:
        return CheckResult(
            Check.ANALYSIS_LEAD_AXIS,
            False,
            f"{len(leads)} axes carry lead: {', '.join(leads) or 'none'}",
        )
    if artifact.lead_axis != leads[0]:
        return CheckResult(
            Check.ANALYSIS_LEAD_AXIS,
            False,
            f"the payload names {artifact.lead_axis!r} as lead and the axes "
            f"carry {leads[0]!r}",
        )
    return CheckResult(Check.ANALYSIS_LEAD_AXIS, True, f"lead is {leads[0]}")


def profile_field_ids(industry: AnalysisIndustry) -> frozenset[str]:
    """Every field id this industry's Analysis may cite, price zone included."""
    return frozenset(
        [PRICE_ZONE_FIELD_ID]
        + [
            entry.field_id
            for fields in profile_for(industry).values()
            for entry in fields
        ]
    )


def direction_words_in(text: str) -> tuple[str, ...]:
    """Which lexicon phrases appear un-negated, in the order they were written."""
    lowered = text.lower()
    hits: list[str] = []
    for phrase in DIRECTION_WORD_LEXICON:
        start = lowered.find(phrase)
        while start != -1:
            if not _negated_before(lowered, start):
                hits.append(phrase)
                break
            start = lowered.find(phrase, start + 1)
    return tuple(hits)


def _negated_before(lowered: str, index: int) -> bool:
    window = lowered[max(0, index - _NEGATION_WINDOW) : index]
    return any(marker in window for marker in _NEGATIONS)


__all__ = [
    "DIRECTION_WORD_LEXICON",
    "Check",
    "CheckResult",
    "DeterministicScore",
    "cited_claims",
    "direction_words_in",
    "lexicon_over",
    "profile_field_ids",
    "score_analysis",
]
