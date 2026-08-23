"""The wire contracts of the Evaluation lane, and nothing else.

Every artifact the harness reads or writes is one of the frozen models here:
a dataset manifest, a case, an evidence snapshot, a trial outcome, a
trajectory event, a grade, or a run manifest. Each carries a ``schema`` tag
naming its kind *and* generation, so an artifact written by a different
generation is refused at load rather than misread in place — the fail-loud
version-mismatch pattern the deleted battery got right.

Three properties hold across all of them:

**Strict.** Unknown fields are refused, never dropped. A fixture that grew a
field nobody declared is either a schema change or a typo, and both deserve a
human. This mirrors ``stocks.providers.contracts.InternalSnapshot``.

**Frozen.** Every model is immutable after validation; artifacts are records,
not working state.

**Canonical.** :func:`canonical_json` sorts object keys, uses compact
separators, and leaves array order alone (order is meaningful). Digests are
taken over canonical form only, so indentation on disk can never move an
identity.
"""

from __future__ import annotations

import hashlib
import json
import re
from datetime import date, datetime
from enum import Enum
from typing import Any, Literal, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

DATASET_SCHEMA = "eval.dataset@1"
CASE_SCHEMA = "eval.case@1"
SNAPSHOT_SCHEMA = "eval.snapshot@1"
TRIAL_SCHEMA = "eval.trial@1"
TRAJECTORY_EVENT_SCHEMA = "eval.trajectory-event@1"
GRADE_SCHEMA = "eval.grade@1"
RUN_MANIFEST_SCHEMA = "eval.run-manifest@1"

#: How long a content digest is carried. Sixteen hex characters is 64 bits of
#: identity for artifacts measured in kilobytes; collision odds at this scale
#: are nil, and short digests are digests people actually read aloud.
DIGEST_LENGTH = 16


def canonical_json(value: Any) -> str:
    """The one serialization digests are taken over."""
    return json.dumps(value, ensure_ascii=True, separators=(",", ":"), sort_keys=True)


def content_digest(value: Any) -> str:
    """A short content-addressed identity over :func:`canonical_json`."""
    encoded = canonical_json(value).encode("utf-8")
    return hashlib.sha256(encoded).hexdigest()[:DIGEST_LENGTH]


_SECRET_PATTERNS: tuple[re.Pattern[str], ...] = tuple(
    re.compile(pattern, re.IGNORECASE)
    for pattern in (
        r"\bsk-(?:proj-)?[A-Za-z0-9_-]{20,}\b",  # OpenAI-shaped keys
        r"\bsk-ant-[A-Za-z0-9_-]{20,}\b",  # Anthropic-shaped keys
        r"\bgh[pousr]_[A-Za-z0-9]{20,}\b",  # GitHub tokens
        r"\bgithub_pat_[A-Za-z0-9_]{20,}\b",
        r"\bxox[baprs]-[A-Za-z0-9-]{15,}\b",  # Slack tokens
        r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b",  # AWS access key ids
        r"\bAIza[A-Za-z0-9_-]{30,}\b",  # Google API keys
        r"-----BEGIN [A-Z ]*PRIVATE KEY-----",
        r"\bBearer\s+[A-Za-z0-9._-]{10,}",
    )
)


def find_secret_shapes(value: Any) -> tuple[str, ...]:
    """Every string inside ``value`` shaped like a credential.

    Applied to whole documents at load: a committed dataset containing a live
    credential is an incident regardless of which field it hid in. Shape-based
    on purpose — long random strings that merely look secret-ish are fine;
    known provider prefixes are not.
    """
    found: list[str] = []

    def visit(node: Any) -> None:
        if isinstance(node, str):
            if any(pattern.search(node) for pattern in _SECRET_PATTERNS):
                found.append(node)
        elif isinstance(node, Mapping):
            for item in node.values():
                visit(item)
        elif isinstance(node, (list, tuple)):
            for item in node:
                visit(item)

    visit(value)
    return tuple(found)


class _Artifact(BaseModel):
    """Common shape of every eval wire artifact.

    ``populate_by_name`` exists for the artifacts whose wire key is
    ``schema``: the field is named ``schema_tag`` in Python (a field called
    ``schema`` shadows a BaseModel attribute) and travels as ``schema`` on
    the wire.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, populate_by_name=True)


class ProviderSourceName(str, Enum):
    """Mirror of ``ProviderSource``, spelled out so fixtures stay data-only.

    Importing the runtime enum would couple artifact parsing to it; spelling
    the same two values keeps a fixture readable without an interpreter.
    Validation against the runtime enum happens where the replay lane hands
    evidence to adapters, not here.
    """

    FIINQUANT = "fiinquant"
    VNSTOCK = "vnstock"


class FigureHealth(str, Enum):
    """The condition a figure was in when it was frozen."""

    OK = "ok"
    STALE = "stale"
    DEGRADED = "degraded"
    ABSENT = "absent"


class EvidenceRecord(_Artifact):
    """One point-in-time fact a case may be graded against.

    Four times, because finance replay distinguishes all of them: the
    *effective* time the fact is about, the *publication* time it became public,
    the *ingestion* time it entered this system's store, and the case's own
    task ``as_of`` (carried by the case, not by rows). A grader that cannot
    tell these apart cannot detect lookahead.
    """

    source: ProviderSourceName
    capability: str = Field(min_length=3, max_length=32)
    entity: str = Field(min_length=1, max_length=32)
    unit: str | None = None
    value: float | int | str | None = None
    health: FigureHealth = FigureHealth.OK
    effective_at: datetime
    published_at: datetime | None = None
    ingested_at: datetime | None = None
    #: Where this row says it came from, as the provider named it.
    provenance: str = Field(min_length=1, max_length=512)
    price_basis: Literal["raw", "adjusted_at_source"] | None = None
    #: Set **only** on evidence deliberately frozen past the case's ``as_of``
    #: to test that the model declines to use it. The loader refuses unmarked
    #: post-``as_of`` knowledge outright.
    available_after_as_of: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("effective_at", "published_at", "ingested_at")
    @classmethod
    def require_timezone(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.utcoffset() is None:
            raise ValueError("evidence timestamps must be timezone-aware")
        return value

    @model_validator(mode="after")
    def ingestion_follows_publication(self) -> "EvidenceRecord":
        if (
            self.published_at is not None
            and self.ingested_at is not None
            and self.ingested_at < self.published_at
        ):
            raise ValueError("ingested_at cannot precede published_at")
        return self


class SnapshotFile(_Artifact):
    """The reachable slice of the world one or more cases are graded over."""

    schema_tag: Literal["eval.snapshot@1"] = Field(alias="schema")
    snapshot_id: str = Field(min_length=2, max_length=64)
    description: str = ""
    evidence: tuple[EvidenceRecord, ...] = Field(min_length=1)

    @field_validator("snapshot_id")
    @classmethod
    def identifier_shape(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", value):
            raise ValueError(
                f"snapshot id {value!r} must be lowercase kebab-case"
            )
        return value


class SnapshotRef(_Artifact):
    """One snapshot a case reads, pinned by content digest."""

    snapshot_id: str = Field(min_length=2, max_length=64)
    digest: str = Field(min_length=DIGEST_LENGTH, max_length=DIGEST_LENGTH)


class UserContext(_Artifact):
    """Who the simulated user is — synthetic, always.

    Production user ids are integers; requiring the ``synthetic-`` prefix makes
    a real id impossible to paste in by accident, which is most of the way to
    keeping private data out of committed fixtures.
    """

    synthetic_user_id: str = Field(min_length=10, max_length=64)
    display_name: str | None = Field(default=None, max_length=64)

    @field_validator("synthetic_user_id")
    @classmethod
    def must_be_synthetic(cls, value: str) -> str:
        if not value.startswith("synthetic-"):
            raise ValueError(
                f"user context {value!r} must use a 'synthetic-' prefixed id; "
                "committed cases never carry real users"
            )
        return value


class CaseInput(_Artifact):
    """What the lane would have been given, per surface.

    A conversation case carries a prompt and no symbol scope; an analysis case
    is keyed by ``(symbol, trading_day)`` exactly as the production lane is.
    The validator keeps each surface honest rather than letting every field be
    optional everywhere.
    """

    prompt: str | None = Field(default=None, min_length=1, max_length=8_000)
    symbol: str | None = Field(default=None, min_length=3, max_length=10)
    trading_day: date | None = None


class Expectation(_Artifact):
    """One outcome property a case accepts, generically described.

    The dataset describes *what must hold* (a figure matches frozen evidence
    within tolerance, a refusal names its reason); the graders of a later phase
    own *how it is checked*. Keeping the vocabulary generic and open here is
    deliberate: cases may enter the battery before their grader exists, but a
    case with no executable expectation never graduates — that gate lives in
    Phase 3, not in this schema.
    """

    kind: str = Field(min_length=3, max_length=64)
    params: dict[str, Any] = Field(default_factory=dict)


class CaseFile(_Artifact):
    """One evaluation case: intent, scope, expectations, traps, evidence pins."""

    schema_tag: Literal["eval.case@1"] = Field(alias="schema")
    case_id: str = Field(min_length=2, max_length=64)
    surface: Literal["conversation", "analysis"]
    family: str = Field(min_length=3, max_length=64)
    title: str = Field(min_length=2, max_length=200)
    #: The task's as-of date. Evidence knowable strictly after it is refused
    #: unless explicitly marked as an unavailable trap.
    as_of: date
    input: CaseInput
    user_context: UserContext | None = None
    expectations: tuple[Expectation, ...] = Field(min_length=1)
    traps: tuple[str, ...] = ()
    snapshots: tuple[SnapshotRef, ...] = ()

    @field_validator("case_id")
    @classmethod
    def identifier_shape(cls, value: str) -> str:
        if not re.fullmatch(r"[a-z0-9][a-z0-9-]{1,63}", value):
            raise ValueError(f"case id {value!r} must be lowercase kebab-case")
        return value

    @model_validator(mode="after")
    def input_matches_surface(self) -> "CaseFile":
        if self.surface == "conversation":
            if not self.input.prompt:
                raise ValueError(
                    f"conversation case {self.case_id!r} needs a prompt"
                )
            if self.input.symbol or self.input.trading_day:
                raise ValueError(
                    f"conversation case {self.case_id!r} cannot pin a symbol "
                    "scope; that is the analysis lane's keying"
                )
        else:
            if not (self.input.symbol and self.input.trading_day):
                raise ValueError(
                    f"analysis case {self.case_id!r} needs a symbol and a trading day"
                )
            if self.input.prompt:
                raise ValueError(
                    f"analysis case {self.case_id!r} cannot carry a chat prompt; "
                    "its input is keyed by symbol and trading day"
                )
        return self


class SizeBudget(_Artifact):
    """Reviewed ceilings that keep a fixture from becoming a million-line dump.

    Every limit must be positive; a zero anywhere means "nobody reviewed this".
    Byte counts are taken over canonical form, so pretty-printing on disk can
    neither evade nor trip them.
    """

    max_snapshot_bytes: int = Field(gt=0)
    max_snapshot_rows: int = Field(gt=0)
    max_total_bytes: int = Field(gt=0)
    max_total_rows: int = Field(gt=0)


class ManifestCaseRef(_Artifact):
    case_id: str = Field(min_length=2, max_length=64)
    file: str = Field(min_length=1)
    digest: str = Field(min_length=DIGEST_LENGTH, max_length=DIGEST_LENGTH)


class ManifestSnapshotRef(_Artifact):
    snapshot_id: str = Field(min_length=2, max_length=64)
    file: str = Field(min_length=1)
    digest: str = Field(min_length=DIGEST_LENGTH, max_length=DIGEST_LENGTH)


class DatasetManifest(_Artifact):
    """The dataset contract: what exists, where, under which digests and budgets.

    Cases are listed after Phase 3 defines their executable expectations; the
    empty dataset is a valid shell until then, and loading it is how the shell
    proves itself.
    """

    schema_tag: Literal["eval.dataset@1"] = Field(alias="schema")
    dataset_id: str = Field(min_length=2, max_length=64)
    created: date
    description: str = ""
    cases: tuple[ManifestCaseRef, ...] = ()
    snapshots: tuple[ManifestSnapshotRef, ...] = ()
    budget: SizeBudget


# ---------------------------------------------------------------------------
# Artifacts the replay and grading phases write. Defined now so every producer
# and consumer shares one vocabulary from the start.


class TrialOutcome(_Artifact):
    """One run of one case in one trial, as the persisted record of it."""

    schema_tag: Literal["eval.trial@1"] = Field(alias="schema")
    run_id: str = Field(min_length=5, max_length=64)
    case_id: str = Field(min_length=2, max_length=64)
    trial_index: int = Field(ge=0)
    started_at: datetime
    finished_at: datetime
    #: Terminal settlement, using the runtime's own lifecycle vocabulary.
    terminal: Literal[
        "completed", "incomplete", "refused", "cancelled", "failed"
    ]
    usage_tokens: int = Field(ge=0, default=0)
    usage_known: bool = True
    cost_usd: float | None = None
    latency_ms: int = Field(ge=0, default=0)
    tool_calls: int = Field(ge=0, default=0)

    @model_validator(mode="after")
    def finish_follows_start(self) -> "TrialOutcome":
        if self.finished_at < self.started_at:
            raise ValueError("finished_at cannot precede started_at")
        return self


class TrajectoryEvent(_Artifact):
    """One ordered step of what a run did, redacted before persistence."""

    schema_tag: Literal["eval.trajectory-event@1"] = Field(alias="schema")
    seq: int = Field(ge=0)
    kind: Literal[
        "model_attempt",
        "tool_call",
        "tool_result",
        "guardrail",
        "terminal",
    ]
    at: datetime
    payload: dict[str, Any] = Field(default_factory=dict)


class Grade(_Artifact):
    """One grader's verdict on one trial. Hard dimensions never blend with
    trade-off dimensions into a single number."""

    schema_tag: Literal["eval.grade@1"] = Field(alias="schema")
    run_id: str = Field(min_length=5, max_length=64)
    case_id: str = Field(min_length=2, max_length=64)
    trial_index: int = Field(ge=0)
    grader: str = Field(min_length=3, max_length=64)
    dimension: Literal["hard", "tradeoff"]
    passed: bool
    detail: str = ""


class CodeStampWire(_Artifact):
    git_sha: str = Field(min_length=40, max_length=40)
    dirty: bool


class PromptIdentityWire(_Artifact):
    version: str
    contract_sha: str
    loop_version: str
    generation_version: str


class ToolCatalogWire(_Artifact):
    digest: str = Field(min_length=DIGEST_LENGTH, max_length=DIGEST_LENGTH)
    names: tuple[str, ...]
    unavailable: tuple[str, ...]


class PriceBlock(_Artifact):
    input: float
    cached_input: float
    cache_write: float
    output: float


class ModelIdentityWire(_Artifact):
    session_model: str
    batch_model: str
    route_base_url: str
    streaming: bool
    reasoning_history: bool
    prompt_cache_control: bool
    pricing_version: str
    pricing_effective_from: str | None
    session_prices: PriceBlock
    batch_prices: PriceBlock
    request_timeout_seconds: float
    route_breaker_enabled: bool


class RunManifest(_Artifact):
    """Everything needed to reproduce a run, stamped onto every artifact set.

    Written by the reporting phase; the schema exists now because contracts
    are the part later phases must agree on before any code does.
    """

    schema_tag: Literal["eval.run-manifest@1"] = Field(alias="schema")
    run_id: str = Field(min_length=5, max_length=64)
    mode: Literal["smoke", "multi-trial"]
    code: CodeStampWire
    dataset_id: str = Field(min_length=2, max_length=64)
    dataset_digest: str = Field(min_length=DIGEST_LENGTH, max_length=DIGEST_LENGTH)
    case_contract_digest: str = Field(min_length=DIGEST_LENGTH, max_length=DIGEST_LENGTH)
    prompts: PromptIdentityWire
    tools: ToolCatalogWire
    model: ModelIdentityWire
    provider_capabilities: dict[str, Any]
    graders: dict[str, str] = Field(default_factory=dict)
    rubric_version: str | None = None
    policy_version: str
    trials: int = Field(ge=1)


__all__ = [
    "CASE_SCHEMA",
    "DATASET_SCHEMA",
    "DIGEST_LENGTH",
    "GRADE_SCHEMA",
    "RUN_MANIFEST_SCHEMA",
    "SNAPSHOT_SCHEMA",
    "TRAJECTORY_EVENT_SCHEMA",
    "TRIAL_SCHEMA",
    "CaseFile",
    "CaseInput",
    "CodeStampWire",
    "DatasetManifest",
    "EvidenceRecord",
    "Expectation",
    "FigureHealth",
    "Grade",
    "ManifestCaseRef",
    "ManifestSnapshotRef",
    "ModelIdentityWire",
    "PriceBlock",
    "PromptIdentityWire",
    "ProviderSourceName",
    "RunManifest",
    "SizeBudget",
    "SnapshotFile",
    "SnapshotRef",
    "ToolCatalogWire",
    "TrajectoryEvent",
    "TrialOutcome",
    "UserContext",
    "canonical_json",
    "content_digest",
    "find_secret_shapes",
]
