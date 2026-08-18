"""The published Analysis, read back the way a reader would meet it.

The Analysis lane scores the **row**, not the fragment the generation returned.
That is the whole difference between this lane and re-running
``validate_fragment``: the fragment was proved on the way in by the code that
produces it, and ``docs/adr/0016`` keeps canary cases precisely because *an
enforcement proved by the same code that performs it is not proved*. What
reaches this module is ``analysis.payload`` — the immutable artifact — and every
question is asked of that.

So this type holds no model objects and imports nothing that can generate one.
It is a reader over one JSON payload, plus the two facts a failed production
leaves instead of a payload: the code and the sentence.

**A run that produced nothing is not an empty artifact.** :meth:`unpublished`
exists so the difference is in the type rather than in a ``None`` every caller
has to remember to branch on, and so a battery of failed runs cannot report a
clean sheet on the checks that need a payload to have an opinion.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import date
from typing import Any

from src.alpha.field_profile import AnalysisIndustry

# The health value a figure carries when the backend could not read it. A
# refused figure stays in the artifact as evidence of what the system could not
# see, and that is the whole of its role (spec 0003 §8.3).
REFUSED_HEALTH = "refused"

# What the model owns in the payload, and the order a reader meets it in. Named
# rather than walked ad hoc, because the prose embedded in the Eval Report is
# what the human rubric scores and a quietly dropped sentence is a rubric
# judging half an artifact.
_JUDGMENT_PROSE_KEYS = ("verdictLine", "thesis")


@dataclass(frozen=True)
class AxisJudgmentRead:
    """One axis as the artifact stores it, with no enum promoted from a string.

    ``axis`` and ``emphasis`` stay strings on purpose. This is a reader over a
    stored row, and a row written by an older ``schemaVersion`` may carry a word
    this build's enums do not have; coercing it here would turn a checkable
    mismatch into a ``ValueError`` from inside a scoring pass.
    """

    axis: str
    emphasis: str
    emphasis_reason: str
    read: str

    @property
    def leads(self) -> bool:
        return self.emphasis == "lead"


@dataclass(frozen=True)
class AnalysisArtifact:
    """What one production attempt over the fixture left behind.

    Either a published payload or a named failure, never both and never neither.
    """

    symbol: str
    trading_day: date
    verdict: str | None = None
    payload: Mapping[str, Any] | None = None
    error_code: str | None = None
    error_message: str | None = None

    @classmethod
    def published(
        cls,
        *,
        symbol: str,
        trading_day: date,
        verdict: str,
        payload: Mapping[str, Any],
    ) -> "AnalysisArtifact":
        return cls(
            symbol=symbol,
            trading_day=trading_day,
            verdict=verdict,
            payload=payload,
        )

    @classmethod
    def unpublished(
        cls,
        *,
        symbol: str,
        trading_day: date,
        error_code: str | None,
        error_message: str | None,
    ) -> "AnalysisArtifact":
        return cls(
            symbol=symbol,
            trading_day=trading_day,
            error_code=error_code,
            error_message=error_message,
        )

    @property
    def exists(self) -> bool:
        """Whether there is an artifact to ask questions of at all."""
        return self.payload is not None

    @property
    def evidence(self) -> Mapping[str, Any]:
        """The envelope verbatim, which is where every displayed number lives."""
        return dict(self._section("evidence"))

    @property
    def judgment(self) -> Mapping[str, Any]:
        return dict(self._section("judgment"))

    @property
    def industry(self) -> AnalysisIndustry:
        """Which industry's Field Profile this artifact was built against.

        Read off the artifact rather than off the store. The profile that was
        active when the Analysis was produced is the one its citations have to
        be a subset of, and a symbol reclassified since would otherwise be
        scored against a list nobody generated it from.
        """
        try:
            return AnalysisIndustry(str(self.evidence.get("industry", "")))
        except ValueError:
            return AnalysisIndustry.UNCLASSIFIED

    @property
    def cited_field_ids(self) -> tuple[str, ...]:
        if self.payload is None:
            return ()
        cited = self.payload.get("citedFieldIds") or ()
        return tuple(str(item) for item in cited)

    @property
    def figures(self) -> Mapping[str, Mapping[str, Any]]:
        """Every figure in the artifact by id, price zone included.

        Built once per access from the payload rather than cached: the artifact
        is read a handful of times per run and a cache here would be state on a
        type whose whole value is that it has none.
        """
        if self.payload is None:
            return {}
        found: dict[str, Mapping[str, Any]] = {}
        zone = self.evidence.get("priceZone")
        if isinstance(zone, Mapping):
            found[str(zone.get("fieldId"))] = zone
        for section in self._sections():
            for figure in section.get("figures", ()):
                if isinstance(figure, Mapping):
                    found[str(figure.get("fieldId"))] = figure
        return found

    @property
    def refused_field_ids(self) -> frozenset[str]:
        """Every figure the backend could not read, and said so."""
        return frozenset(
            field_id
            for field_id, figure in self.figures.items()
            if figure.get("health") == REFUSED_HEALTH
        )

    @property
    def axes(self) -> tuple[AxisJudgmentRead, ...]:
        judgment = self.judgment.get("axes") or ()
        return tuple(
            AxisJudgmentRead(
                axis=str(item.get("axis", "")),
                emphasis=str(item.get("emphasis", "")),
                emphasis_reason=str(item.get("emphasisReason", "")),
                read=str(item.get("read", "")),
            )
            for item in judgment
            if isinstance(item, Mapping)
        )

    @property
    def lead_axis(self) -> str:
        """The axis the payload's extracted ``leadAxis`` names.

        Extracted rather than derived, so it is a second spelling of one fact —
        which is why the lane checks that the two agree rather than trusting
        either.
        """
        return str(self.judgment.get("leadAxis", ""))

    @property
    def leading_axes(self) -> tuple[str, ...]:
        return tuple(item.axis for item in self.axes if item.leads)

    @property
    def prose(self) -> str:
        """Every sentence the model wrote, in the order the artifact carries it.

        This is what the Eval Report embeds and what the blind human rubric
        scores, so it is deliberately everything: the verdict line, the thesis,
        and both narrations of all four axes. An axis whose section is refused
        says what is missing, and *that* sentence is the one category E is
        about — dropping it because it names no figure would hide the answer
        being judged.

        A run that produced nothing says so here rather than returning an empty
        string. The report shows this text where an answer would be, and a blank
        is indistinguishable from a model that said nothing.
        """
        if self.payload is None:
            code = self.error_code or "unknown"
            reason = self.error_message or "no reason was recorded"
            return f"({code}) {reason}"
        judgment = self.judgment
        lines = [
            str(judgment.get(key, "")).strip() for key in _JUDGMENT_PROSE_KEYS
        ]
        for item in self.axes:
            lines.append(f"[{item.axis}] {item.emphasis_reason}".strip())
            lines.append(f"[{item.axis}] {item.read}".strip())
        return "\n\n".join(line for line in lines if line)

    def _sections(self) -> Sequence[Mapping[str, Any]]:
        sections = self.evidence.get("sections") or ()
        return [item for item in sections if isinstance(item, Mapping)]

    def _section(self, name: str) -> Mapping[str, Any]:
        if self.payload is None:
            return {}
        value = self.payload.get(name)
        return value if isinstance(value, Mapping) else {}


__all__ = [
    "REFUSED_HEALTH",
    "AnalysisArtifact",
    "AxisJudgmentRead",
]
