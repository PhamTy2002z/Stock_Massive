"""What the backend attaches to every assistant message (#83).

The **Evidence Manifest**, the **Risk Notice** and ``answer_kind`` exist for one
reason between them.  Enforcing any of the three through the prompt makes
compliance a model behaviour measured after the fact; attaching them makes it a
system property.  So none of the three has a route the model can reach: the
manifest is built from typed values the harness already holds, the notice is a
versioned constant, and ``answer_kind`` is classified by
``prompt.classify_answer_kind`` from counters the loop kept.

## The Manifest is what survives a dispute

It is immutable, it lives with the message **indefinitely**, and full Tool Call
Traces keep their 90-day window — so an answer stays disputable long after the
trace behind it is gone.  That is only true because the manifest copies the
resolved citations rather than pointing at them: a manifest holding trace ids
would become unreadable on day 91, which is the day someone finally asks.

A7 replays against this. **Replay means re-reading the Manifest, not reproducing
the answer** — the model is non-deterministic above temperature 0 and the store
moves nightly, so a reproduction would be a different answer wearing the same
name.

## What it must never contain

No credential, no token, no hidden reasoning, and no database copy of the prompt
— a version and a hash, not the text.  :func:`build_manifest` takes typed
arguments and there is no free-form field among them, which is the same
technique ``prompt/contract.py`` uses to prove nothing can be interpolated into
the system prompt: the hole is not guarded, it does not exist.
:func:`assert_discloses_nothing` is the belt to that braces, run in tests over a
real manifest.
"""

from __future__ import annotations

import json
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

from src.stocks.signals import registry_version

from .grounding import Citation, EvidenceSource
from .prompt import PROMPT_HASH, PROMPT_VERSION, AnswerKind

# The manifest's own shape. Bumped when a reader would have to parse it
# differently, never when a field is added that an old reader can ignore.
MANIFEST_SCHEMA_VERSION = 1

RISK_NOTICE_VERSION = "1.0.0"

CANONICAL_RISK_NOTICE = (
    "Nội dung này phục vụ phân tích và tham khảo, không phải tư vấn đầu tư cá "
    "nhân hay cam kết lợi nhuận. Dữ liệu có thể chậm, thiếu hoặc thay đổi; bạn "
    "tự chịu trách nhiệm cho quyết định của mình."
)


class RiskMeaning(str, Enum):
    """The four meanings a Risk Notice must retain in any language.

    An enum rather than a prose note, because the acceptance criterion is that a
    *translation* is checked against them. Checking prose against prose needs a
    reader; checking a declared set against a required set needs neither a
    reader nor a model.
    """

    ANALYTICAL_PURPOSE = "analytical_purpose"
    NO_PERSONAL_ADVICE = "no_personal_advice"
    NO_PROMISED_OUTCOME = "no_promised_outcome"
    LIMITED_DATA_USER_RESPONSIBLE = "limited_data_user_responsible"


ALL_RISK_MEANINGS = frozenset(RiskMeaning)


@dataclass(frozen=True)
class RiskNotice:
    """One rendering of the notice, refused unless it retains all four meanings."""

    version: str
    locale: str
    text: str
    meanings: frozenset[RiskMeaning] = field(default_factory=lambda: ALL_RISK_MEANINGS)

    def __post_init__(self) -> None:
        missing = ALL_RISK_MEANINGS - self.meanings
        if missing:
            raise ValueError(
                "a Risk Notice must retain all four meanings; this one drops "
                + ", ".join(sorted(meaning.value for meaning in missing))
            )
        if not self.text.strip():
            raise ValueError("a Risk Notice with no text satisfies nothing")

    def as_wire(self) -> dict[str, Any]:
        return {
            "version": self.version,
            "locale": self.locale,
            "text": self.text,
            "meanings": sorted(meaning.value for meaning in self.meanings),
        }


VIETNAMESE_RISK_NOTICE = RiskNotice(
    version=RISK_NOTICE_VERSION,
    locale="vi",
    text=CANONICAL_RISK_NOTICE,
)

DEFAULT_LOCALE = "vi"

# One locale ships in v1, and this is a registry rather than a constant because
# the way a translation arrives is the thing worth fixing now: it is registered
# here, as a :class:`RiskNotice`, and the constructor refuses one that drops a
# meaning. A renderer that translated the string somewhere else would have no
# such check in front of it.
RISK_NOTICES: Mapping[str, RiskNotice] = {
    VIETNAMESE_RISK_NOTICE.locale: VIETNAMESE_RISK_NOTICE,
}


def risk_notice(locale: str = DEFAULT_LOCALE) -> RiskNotice:
    """The notice the backend attaches, whatever the model wrote.

    An unregistered locale falls back to the canonical Vietnamese rather than
    raising: the notice must be present on every useful answer, so a missing
    translation may cost the reader their language but never the notice.
    """
    return RISK_NOTICES.get(locale, VIETNAMESE_RISK_NOTICE)


@dataclass(frozen=True)
class GateOutcome:
    """The three validator outcomes the Manifest records.

    Recorded as outcomes rather than as a pass/fail, because ``not_applicable``
    is the honest answer for a Turn that produced no recommendation and
    ``blocked`` is the answer that has to be countable in the ops query
    (``docs/adr/0016``).
    """

    scope: str = "in_scope"
    grounding: str = "passed"
    recommendation: str = "not_applicable"
    failure_code: str | None = None
    #: Every condition that downgraded a block this Turn answered around, in the
    #: order they happened.
    #:
    #: ``failure_code`` reports one, which was enough while eight conditions
    #: could downgrade and only a recommendation could be the block. Twenty can
    #: now, on any block, so an answer routinely has several — and the record
    #: that decides whether inverting the Gate's default let a false figure
    #: through is the record that lists all of them. Additive: an old reader that
    #: knows only ``failure_code`` reads this Manifest unchanged.
    downgrades: tuple[str, ...] = ()

    def as_wire(self) -> dict[str, Any]:
        return {
            "scope": self.scope,
            "grounding": self.grounding,
            "recommendation": self.recommendation,
            "failure_code": self.failure_code,
            "downgrades": list(self.downgrades),
        }


@dataclass(frozen=True)
class EvidenceManifest:
    """The immutable record stored with one assistant message, kept forever."""

    schema_version: int
    prompt_version: str
    prompt_hash: str
    git_sha: str
    model: str
    route: str
    provider_request_id: str | None
    tool_catalog_version: str
    mcp_servers_version: str
    registry_version: str
    risk_notice_version: str
    answer_kind: AnswerKind
    status: str
    terminal_reason: str | None
    outcomes: GateOutcome
    cited_fields: tuple[Citation, ...] = ()

    def as_wire(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "prompt_version": self.prompt_version,
            "prompt_hash": self.prompt_hash,
            "git_sha": self.git_sha,
            "model": self.model,
            "route": self.route,
            "provider_request_id": self.provider_request_id,
            "tool_catalog_version": self.tool_catalog_version,
            "mcp_servers_version": self.mcp_servers_version,
            "registry_version": self.registry_version,
            "risk_notice_version": self.risk_notice_version,
            "answer_kind": self.answer_kind.value,
            "status": self.status,
            "terminal_reason": self.terminal_reason,
            "outcomes": self.outcomes.as_wire(),
            "cited_fields": [citation.as_wire() for citation in self.cited_fields],
        }


def build_manifest(
    *,
    git_sha: str,
    model: str,
    route: str,
    provider_request_id: str | None,
    tool_catalog_version: str,
    mcp_servers_version: str = "disabled",
    answer_kind: AnswerKind,
    status: str,
    terminal_reason: str | None,
    citations: Sequence[Citation] = (),
    outcomes: GateOutcome | None = None,
) -> EvidenceManifest:
    """Assemble the Manifest from typed values, and from nothing else.

    Every argument is a version, an identifier, an enum or a resolved citation.
    There is no free-form string among them for a prompt, a credential or a
    piece of reasoning to arrive in — which is the whole guarantee, stated as a
    signature rather than as a promise.
    """
    return EvidenceManifest(
        schema_version=MANIFEST_SCHEMA_VERSION,
        prompt_version=PROMPT_VERSION,
        prompt_hash=PROMPT_HASH,
        git_sha=git_sha,
        model=model,
        route=route,
        provider_request_id=provider_request_id,
        tool_catalog_version=tool_catalog_version,
        mcp_servers_version=mcp_servers_version,
        registry_version=registry_version(),
        risk_notice_version=RISK_NOTICE_VERSION,
        answer_kind=answer_kind,
        status=status,
        terminal_reason=terminal_reason,
        outcomes=outcomes or GateOutcome(),
        cited_fields=tuple(citations),
    )


def sources_and_methods(citations: Sequence[Citation]) -> tuple[dict[str, Any], ...]:
    """The expandable provenance surface, built by the backend.

    The second of the two provenance layers ``docs/adr/0015`` names: units and
    ``as_of`` sit beside the figures in the answer itself, and this is what
    opens underneath. Every entry is derived from a resolved citation, so no
    source name or citation sentence here originated with the model.
    """
    surface: list[dict[str, Any]] = []
    for citation in citations:
        surface.append(
            {
                "provider_source": citation.provenance,
                "tool_call_id": citation.call_id,
                "tool_name": citation.tool_name,
                "registered_field": (
                    citation.field_path
                    if citation.source is EvidenceSource.REGISTERED_FIELD
                    else None
                ),
                "value": citation.value,
                "unit": citation.unit,
                "interpretation": citation.interpretation,
                "freshness": {"as_of": citation.as_of, "stale": citation.stale},
                "window_health": (
                    dict(citation.window_health)
                    if citation.window_health is not None
                    else None
                ),
                "contradictory": citation.contradictory,
                "claim_class": citation.source.value,
            }
        )
    return tuple(surface)


def assemble_message(
    *,
    blocks: Sequence[Mapping[str, Any]],
    text: str,
    answer_kind: AnswerKind,
    manifest: EvidenceManifest,
    citations: Sequence[Citation] = (),
    notice: RiskNotice | None = None,
    widgets: Sequence[Mapping[str, Any]] = (),
    widget_refusals: Sequence[Mapping[str, Any]] = (),
    search_progress: Sequence[Mapping[str, Any]] = (),
    suggestions: Sequence[str] = (),
) -> dict[str, Any]:
    """The canonical assistant message content, Notice and Manifest included.

    Built here rather than at the call site so that there is exactly one shape:
    a message assembled anywhere else could omit the Risk Notice, and an
    omission is precisely what attaching it in the backend is supposed to make
    impossible.

    ``widgets`` holds validated Widget *specs* — fixed-date retrieval
    descriptors, never the series (``docs/adr/0012``), and there is no
    ``widgets`` table for them to live in instead. ``widget_refusals`` holds only
    the refusals that have somewhere better to send the reader — a chart Stock
    360 already owns, and the deep link to it. Every other rejection is silent,
    because a broken box teaches a reader nothing about a picture they never
    asked for.

    ``search_progress`` and ``suggestions`` are ``docs/adr/0020``'s two additive
    keys: what the open-web lane disclosed while the Turn ran, and the follow-up
    questions offered under it. Both are stored on the message rather than left
    to the stream, because a Thread reopened tomorrow should show the same thing
    the reader watched today. A message written before that decision simply has
    neither, which is why both default to empty rather than being required.
    """
    return {
        "text": text,
        "blocks": [dict(block) for block in blocks],
        "answer_kind": answer_kind.value,
        "risk_notice": (notice or risk_notice()).as_wire(),
        "evidence_manifest": manifest.as_wire(),
        "sources_and_methods": list(sources_and_methods(citations)),
        "widgets": [dict(widget) for widget in widgets],
        "widget_refusals": [dict(refusal) for refusal in widget_refusals],
        "search_progress": [dict(step) for step in search_progress],
        "suggestions": list(suggestions),
    }


def assert_discloses_nothing(manifest: EvidenceManifest, *secrets: str) -> None:
    """Refuse a Manifest that carries anything it must never carry.

    Called from tests over a real manifest rather than on the write path: this
    is a proof about the shape, and a runtime scan of every message would be a
    cost paid forever for a property the type system already gives.
    """
    encoded = json.dumps(manifest.as_wire(), ensure_ascii=False)
    for secret in secrets:
        if secret and secret in encoded:
            raise AssertionError(
                "the Evidence Manifest discloses a value it must never carry"
            )


__all__ = [
    "ALL_RISK_MEANINGS",
    "CANONICAL_RISK_NOTICE",
    "DEFAULT_LOCALE",
    "RISK_NOTICES",
    "MANIFEST_SCHEMA_VERSION",
    "RISK_NOTICE_VERSION",
    "VIETNAMESE_RISK_NOTICE",
    "EvidenceManifest",
    "GateOutcome",
    "RiskMeaning",
    "RiskNotice",
    "assemble_message",
    "assert_discloses_nothing",
    "build_manifest",
    "risk_notice",
    "sources_and_methods",
]
