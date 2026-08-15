"""The one call to the model, and everything that has to be true of what returns.

The evidence envelope goes out exactly once per attempt and comes back either as
a fragment the backend has *proved* valid or as a failure with a name from the
pipeline's closed taxonomy. There is no third outcome, and in particular there is
no outcome where the backend repaired something.

**One fixed call.** A fixed system prompt with its own ``promptVersion``, the
configured route, temperature 0, strict structured output, no tools, no loop and
no prompt built by branching on what happened to be in the envelope. Determinism
here means fixed inputs, fixed control flow and bounded validation — not
bit-identical prose out of a probabilistic model.

**The model sees the refusals too.** Every figure the profile named reaches it,
including the ones that are ``refused`` and the codes saying why, so it can
choose emphasis honestly rather than narrating around a hole it cannot see. It
may cite only what is usable.

**Provider-level strict validation is not enough.** A gateway silently dropping
``response_format`` was measured, which is why ``JsonSchemaFormat.strict``
exists and why the six semantic rules below run afterwards anyway. Text that is
not the schema is caught here rather than trusted.

**One regeneration, never a patch.** A first invalid fragment is answered with
machine-readable validation errors and asked for again, once, and only if the
remaining per-Analysis budget can fund it. A second invalid fragment fails the
attempt with ``invalid_model_output``. The backend never edits model output into
validity: a fragment the backend fixed is a fragment nobody can audit, and the
durable three-attempt ceiling per ``(symbol, trading_day)`` belongs to the
lifecycle rather than to this module.

**Nothing reaches the provider without a committed reservation.** The call goes
through ``ReservedLLMClient``, which refuses outright if handed no
``SpendRequest``, so the admission transaction is structurally unavoidable
rather than remembered.
"""

from __future__ import annotations

import json
import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from enum import Enum
from typing import Any

from src.core.llm import (
    AuthUnavailable,
    BudgetLane,
    BudgetRefusal,
    CallOwner,
    Completion,
    CompletionRequest,
    JsonSchemaFormat,
    LLMClient,
    LLMError,
    Message,
    ModelRefusal,
    OwnerType,
    Role,
    SpendRequest,
    Workload,
)
from src.core.llm.admission import ANALYSIS_INPUT_PER_CALL, ANALYSIS_OUTPUT_PER_CALL

from .envelope import EvidenceEnvelope
from .field_profile import AXIS_ORDER, Axis
from .producer import ProductionFailure, sanitized_reason

# The behavioural core of this call. Bumped whenever the system prompt or the
# output schema changes, because both are the cacheable prefix and both are what
# an Analysis was generated against — a fragment cannot be compared with one
# produced under different instructions.
PROMPT_VERSION = "v1"

# What one fragment may cost in output. Well under the per-call ceiling on
# purpose: the fragment is a verdict word, one line, a short thesis and four
# short reads, and reserving the ceiling would spend the whole per-Analysis
# allowance on the first generation and leave the sanctioned regeneration
# unfundable by construction.
MAX_OUTPUT_TOKENS = 700

# Characters per token, for the reservation only. A rough, deliberately
# pessimistic ratio: the envelope is JSON, which tokenizes worse than prose, and
# the ledger is made true by reconciliation against the provider's own counters
# immediately after the call rather than by this estimate.
CHARS_PER_TOKEN = 3.5

# Every generation is one attempt plus at most one regeneration.
MAX_GENERATIONS_PER_ATTEMPT = 2

if MAX_OUTPUT_TOKENS * MAX_GENERATIONS_PER_ATTEMPT > ANALYSIS_OUTPUT_PER_CALL:
    # Checked at import rather than left to a reviewer, because the failure it
    # guards against is silent: raise the output bound past half the per-call
    # ceiling and the regeneration this module is built around stops being
    # fundable, without a single test going red.
    raise ValueError(
        f"an output bound of {MAX_OUTPUT_TOKENS} leaves no room for the "
        f"{MAX_GENERATIONS_PER_ATTEMPT} generations one attempt may make inside "
        f"the {ANALYSIS_OUTPUT_PER_CALL}-token per-call ceiling"
    )


class Verdict(str, Enum):
    """The one scalar the rail reads as an extracted column.

    One word for ten symbols is the whole reason it is a scalar rather than a
    structure. The prototype's artifact-level ``claim`` is deliberately absent:
    claim semantics belong to each registered field, and a verdict is model
    judgment rather than a descriptive measurement.
    """

    ACCUMULATE = "accumulate"
    HOLD = "hold"
    REDUCE = "reduce"
    AVOID = "avoid"
    WATCH = "watch"


class Emphasis(str, Enum):
    """How much weight one axis carries in this Analysis.

    Exactly one axis is ``lead``. Not a boolean on each axis, because a boolean
    admits zero leads and four leads, and both are artifacts nobody can lay out.
    """

    LEAD = "lead"
    SUPPORT = "support"
    CONTEXT = "context"


AXIS_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "axis": {"type": "string", "enum": [axis.value for axis in AXIS_ORDER]},
        "emphasis": {"type": "string", "enum": [item.value for item in Emphasis]},
        "emphasisReason": {"type": "string"},
        "read": {"type": "string"},
    },
    "required": ["axis", "emphasis", "emphasisReason", "read"],
    "additionalProperties": False,
}

# The five model-owned things and nothing else. `additionalProperties: false`
# everywhere, so a route that honours the schema cannot return a sixth — and the
# semantic pass below catches the route that does not honour it.
FRAGMENT_SCHEMA: Mapping[str, Any] = {
    "type": "object",
    "properties": {
        "verdict": {"type": "string", "enum": [item.value for item in Verdict]},
        "verdictLine": {"type": "string"},
        "thesis": {"type": "string"},
        "citedFieldIds": {
            "type": "array",
            "items": {"type": "string"},
            "minItems": 1,
        },
        "axes": {
            "type": "array",
            "items": AXIS_SCHEMA,
            "minItems": len(AXIS_ORDER),
            "maxItems": len(AXIS_ORDER),
        },
    },
    "required": ["verdict", "verdictLine", "thesis", "citedFieldIds", "axes"],
    "additionalProperties": False,
}

FRAGMENT_FORMAT = JsonSchemaFormat(name="analysis_fragment", schema=FRAGMENT_SCHEMA)

# Fixed prose. It is a module constant and never a template: a prompt assembled
# by branching on what happened to be in one envelope is a prompt that cannot be
# reviewed, cached or compared across two Analyses.
SYSTEM_PROMPT = """\
You write the judgment layer of a Vietnamese equities Analysis.

The user message is the complete evidence envelope for one symbol on one Trading
Day. Every number, unit, date and health state in it is owned by the backend and
is already correct. You do not compute, restate as your own, correct or invent
any figure.

You return exactly five things and nothing else:

- verdict: one of accumulate, hold, reduce, avoid, watch.
- verdictLine: one sentence a reader sees beside the verdict.
- thesis: a short paragraph saying what the evidence supports and what it does
  not.
- citedFieldIds: the fieldId of every figure your verdict rests on.
- axes: the four axes technical, fundamental, money_flow, news, in that order,
  each with an emphasis, an emphasisReason and a read.

Rules that are checked after you answer, and that fail the whole Analysis when
broken:

- Cite only figures whose health is ok or degraded. A figure whose health is
  refused carries a reasonCode explaining why it is missing; you may mention
  that the evidence is missing, and it can never support your verdict.
- Cite at least one figure, and cite only fieldIds that appear in the envelope.
- Return the four axes in the given order, all four, and no others.
- Exactly one axis is lead. The other three are support or context.
- Where you cite a degraded figure, make its age or its limitation visible in
  the prose rather than reading it as if it were whole.
- Every axis needs an emphasisReason and a read, including an axis whose section
  is refused — there, say what is missing rather than leaving it blank.

You choose emphasis, the lead axis, the reading and the words. You do not choose
section order, section membership, layout, or any displayed number.
"""


@dataclass(frozen=True)
class AxisJudgment:
    """What the model said about one axis."""

    axis: Axis
    emphasis: Emphasis
    emphasis_reason: str
    read: str

    def as_wire(self) -> dict[str, Any]:
        return {
            "axis": self.axis.value,
            "emphasis": self.emphasis.value,
            "emphasisReason": self.emphasis_reason,
            "read": self.read,
        }


@dataclass(frozen=True)
class AnalysisFragment:
    """The validated model-owned half of an Analysis.

    Constructed only by ``validate_fragment``. There is no path from raw model
    output to this type that skips the six rules, which is what makes holding one
    mean the rules passed.
    """

    verdict: Verdict
    verdict_line: str
    thesis: str
    cited_field_ids: tuple[str, ...]
    axes: tuple[AxisJudgment, ...]

    @property
    def lead_axis(self) -> Axis:
        return next(
            item.axis for item in self.axes if item.emphasis is Emphasis.LEAD
        )

    def as_wire(self) -> dict[str, Any]:
        return {
            "verdict": self.verdict.value,
            "verdictLine": self.verdict_line,
            "thesis": self.thesis,
            "citedFieldIds": list(self.cited_field_ids),
            "axes": [item.as_wire() for item in self.axes],
        }


@dataclass(frozen=True)
class FragmentError:
    """One thing wrong with a fragment, in a shape a model can act on.

    ``path`` and ``code`` are machine-readable and are what the regeneration is
    handed; ``message`` is the sentence beside them. Prose alone would leave the
    model guessing which of four axes the complaint was about.
    """

    path: str
    code: str
    message: str

    def as_wire(self) -> dict[str, str]:
        return {"path": self.path, "code": self.code, "message": self.message}


class FragmentRejected(Exception):
    """A fragment that failed the semantic pass, with every reason it failed.

    Every rule is evaluated rather than the first failure raised: a regeneration
    told about one problem at a time is a loop, and this module allows exactly
    one more call.
    """

    def __init__(self, errors: Sequence[FragmentError]) -> None:
        self.errors = tuple(errors)
        super().__init__(
            "; ".join(f"{error.path}: {error.code}" for error in self.errors)
        )

    def as_feedback(self) -> str:
        return json.dumps(
            {"validationErrors": [error.as_wire() for error in self.errors]},
            ensure_ascii=False,
        )


def validate_fragment(payload: Any, envelope: EvidenceEnvelope) -> AnalysisFragment:
    """Prove one fragment against the envelope it was generated from, or reject it.

    Six rules, and the reason each of them is here rather than left to the
    provider's schema:

    1. ``citedFieldIds`` is non-empty and every id exists **in this envelope** —
       a schema can say "an array of strings" and cannot say "of these strings".
    2. Only ``ok`` or ``degraded`` figures are cited. A refused figure is in the
       artifact as honesty evidence and can never support the verdict.
    3. The axes are the invariant four, in their order and no others. Section
       order and membership are not the model's to choose.
    4. Exactly one axis is ``lead``.
    5. Enum values are in range, which a dropped ``response_format`` would let
       through.
    6. The required narration is present, including on a refused section, where
       saying what is missing is the whole point.
    """
    errors: list[FragmentError] = []

    if not isinstance(payload, Mapping):
        raise FragmentRejected(
            [
                FragmentError(
                    path="$",
                    code="not_an_object",
                    message=(
                        "The response is not a JSON object matching the fragment "
                        "schema."
                    ),
                )
            ]
        )

    unexpected = sorted(set(payload) - set(FRAGMENT_SCHEMA["properties"]))
    if unexpected:
        errors.append(
            FragmentError(
                path="$",
                code="unexpected_field",
                message=(
                    "The fragment carries fields the schema does not define: "
                    f"{', '.join(unexpected)}."
                ),
            )
        )

    verdict = _enum_or_error(
        Verdict, payload.get("verdict"), "$.verdict", "verdict", errors
    )
    verdict_line = _narration(payload.get("verdictLine"), "$.verdictLine", errors)
    thesis = _narration(payload.get("thesis"), "$.thesis", errors)
    cited = _citations(payload.get("citedFieldIds"), envelope, errors)
    axes = _axes(payload.get("axes"), errors)

    if errors:
        raise FragmentRejected(errors)

    assert verdict is not None  # every branch above appended an error instead
    return AnalysisFragment(
        verdict=verdict,
        verdict_line=verdict_line,
        thesis=thesis,
        cited_field_ids=cited,
        axes=axes,
    )


def build_request(
    envelope: EvidenceEnvelope,
    model: str,
    *,
    previous: str | None = None,
    rejection: FragmentRejected | None = None,
) -> CompletionRequest:
    """The one request shape, with or without the regeneration's feedback.

    The system prompt is message zero and is byte-identical for every symbol and
    every Trading Day. That is the whole of prompt caching in this lane: the
    cacheable prefix is the system prompt and the output schema, keyed by model
    and ``promptVersion``, and everything that varies comes after it. Caching
    never changes correctness or control flow here — it changes what the prefix
    costs.

    A regeneration appends the rejected fragment and the machine-readable errors
    rather than rewriting the prompt. Re-phrasing the instructions on a second
    attempt would be the dynamic branching this call does not do.
    """
    messages = [
        Message(role=Role.SYSTEM, content=SYSTEM_PROMPT),
        Message(
            role=Role.USER,
            content=json.dumps(envelope.as_wire(), ensure_ascii=False),
        ),
    ]
    if rejection is not None:
        messages.append(Message(role=Role.ASSISTANT, content=previous or ""))
        messages.append(Message(role=Role.USER, content=rejection.as_feedback()))

    return CompletionRequest(
        model=model,
        messages=tuple(messages),
        # No tools, so no loop is expressible. `tool_choice` is stated anyway:
        # a route that invented a tool call from an empty catalog is a route
        # violating its contract, and the explicit "none" is what says so.
        tools=(),
        tool_choice="none",
        response_format=FRAGMENT_FORMAT,
        max_output_tokens=MAX_OUTPUT_TOKENS,
        temperature=0.0,
        # One whole response rather than a stream. Nothing in the nightly lane
        # consumes tokens as they arrive, and a whole response carries its usage
        # without a stream option that a gateway could drop.
        stream=False,
    )


def spend_for(request: CompletionRequest, run_id: int | str) -> SpendRequest:
    """The worst case one generation asks admission to fund.

    Owned by the **Analysis Run** rather than by the attempt, which is what makes
    the per-Analysis ceiling hold across all three attempts for the pair: a
    second attempt is charged into the same owner and refused once the pair has
    spent its allowance.
    """
    return SpendRequest(
        owner=CallOwner(type=OwnerType.ANALYSIS_RUN, id=str(run_id)),
        lane=BudgetLane.ANALYSIS,
        workload=Workload.BATCH,
        input_tokens=_estimated_input_tokens(request),
        output_tokens=request.max_output_tokens or MAX_OUTPUT_TOKENS,
    )


async def generate_fragment(
    client: LLMClient,
    envelope: EvidenceEnvelope,
    *,
    model: str,
    run_id: int | str,
) -> AnalysisFragment:
    """Generate and prove one fragment, or fail the attempt by name.

    At most two provider calls: the generation, and — only where the fragment
    came back invalid and admission will still fund one — the single sanctioned
    regeneration. Whether the budget can fund it is asked of admission rather
    than recomputed here, because admission is where the ceiling lives and a
    second copy of it would be a second answer to the same question. A
    reservation is not a generation, so a refused reservation is a regeneration
    that was never attempted.
    """
    rejection: FragmentRejected | None = None
    previous: str | None = None

    for generation in range(MAX_GENERATIONS_PER_ATTEMPT):
        request = build_request(
            envelope, model, previous=previous, rejection=rejection
        )
        try:
            completion = await client.complete(request, spend_for(request, run_id))
        except BudgetRefusal as refusal:
            raise _budget_failure(refusal, rejection) from refusal
        except AuthUnavailable as exc:
            raise ProductionFailure(
                "auth_unavailable",
                "Tuyến LLM từ chối thông tin xác thực: "
                f"{sanitized_reason(str(exc))}",
            ) from exc
        except ModelRefusal as exc:
            # The model declined rather than the route failing. Its own words are
            # the answer and are never re-prompted around, so this ends the
            # attempt instead of consuming the regeneration.
            raise ProductionFailure(
                "invalid_model_output",
                f"Model từ chối sinh Analysis: {sanitized_reason(str(exc))}",
            ) from exc
        except LLMError as exc:
            raise ProductionFailure(
                "llm_transport_error",
                "Tuyến LLM không trả lời được: "
                f"{sanitized_reason(str(exc))}",
            ) from exc

        previous = completion.text or ""
        try:
            return validate_fragment(_parsed(completion), envelope)
        except FragmentRejected as rejected:
            rejection = rejected

    assert rejection is not None  # the loop only exits here through a rejection
    raise ProductionFailure(
        "invalid_model_output",
        "Fragment vẫn không hợp lệ sau một lần sinh lại: "
        f"{sanitized_reason(str(rejection))}",
    )


def _budget_failure(
    refusal: BudgetRefusal,
    rejection: FragmentRejected | None,
) -> ProductionFailure:
    """What a refused reservation means, which depends on which call it was.

    A first generation admission would not fund is a spend failure and says so.
    A *regeneration* it would not fund is not: the attempt failed because the
    fragment was invalid, and the budget is why nothing could be done about it —
    reporting it as a spend failure would hide a model that produced garbage
    behind a number in a ledger.

    The message carries admission's own reason rather than asserting one, because
    the refusals it can raise are not all about money: a prompt over the per-call
    input ceiling arrives here as ``analysis_input_per_call``, and calling that
    "out of budget" would send an operator to the ledger instead of to the
    envelope that grew.
    """
    if rejection is None:
        return ProductionFailure(
            "budget_exhausted",
            "Lượt sinh Analysis bị từ chối ở khâu cấp ngân sách: "
            f"{sanitized_reason(refusal.reason)}",
        )
    return ProductionFailure(
        "invalid_model_output",
        "Fragment không hợp lệ và ngân sách còn lại không đủ để sinh "
        f"lại ({sanitized_reason(refusal.reason)}): "
        f"{sanitized_reason(str(rejection))}",
    )


def _parsed(completion: Completion) -> Any:
    """The fragment as an object, or the rejection a non-JSON answer earns.

    A gateway that silently drops ``response_format`` answers with prose, and
    prose is caught here rather than trusted: it becomes an ordinary validation
    failure, gets the one regeneration every other invalid fragment gets, and
    fails the attempt as ``invalid_model_output`` if it happens twice.
    """
    try:
        return json.loads(completion.text or "")
    except ValueError:
        raise FragmentRejected(
            [
                FragmentError(
                    path="$",
                    code="not_json",
                    message=(
                        "The response is not JSON. Return only the fragment "
                        "object described by the schema."
                    ),
                )
            ]
        ) from None


def _estimated_input_tokens(request: CompletionRequest) -> int:
    """What this prompt is worth, stated honestly however large it is.

    **Deliberately unclamped.** Admission refuses a generation whose reserved
    input exceeds ``ANALYSIS_INPUT_PER_CALL``, so clamping the estimate to that
    ceiling would make the ceiling unenforceable: an oversized envelope would be
    admitted on an understated reservation and the ≤6,000-token rule
    (``docs/adr/0014``, spec 0003 §11) would never fire. A prompt too big for one
    generation is a defect in what the backend assembled, and the only way it
    surfaces is by being reserved at its real size and refused.
    """
    characters = sum(len(message.content or "") for message in request.messages)
    characters += len(json.dumps(FRAGMENT_SCHEMA))
    return max(math.ceil(characters / CHARS_PER_TOKEN), 1)


def _enum_or_error(
    enum: type[Enum],
    value: Any,
    path: str,
    code: str,
    errors: list[FragmentError],
) -> Any:
    try:
        return enum(value)
    except ValueError:
        errors.append(
            FragmentError(
                path=path,
                code=f"{code}_out_of_range",
                message=(
                    f"{value!r} is not one of "
                    f"{', '.join(item.value for item in enum)}."
                ),
            )
        )
        return None


def _narration(value: Any, path: str, errors: list[FragmentError]) -> str:
    if isinstance(value, str) and value.strip():
        return value.strip()
    errors.append(
        FragmentError(
            path=path,
            code="narration_missing",
            message="This field is required and may not be blank.",
        )
    )
    return ""


def _citations(
    value: Any,
    envelope: EvidenceEnvelope,
    errors: list[FragmentError],
) -> tuple[str, ...]:
    if not isinstance(value, list) or not value:
        errors.append(
            FragmentError(
                path="$.citedFieldIds",
                code="no_citation",
                message="At least one usable figure has to support the verdict.",
            )
        )
        return ()

    # Both sets are read once. They are properties over the whole envelope, so
    # asking inside the comprehensions would rebuild the figures tuple per cited
    # id — and a fragment is allowed to cite every figure there is.
    known = envelope.field_ids
    usable = envelope.citable_field_ids

    cited = tuple(str(item) for item in value)
    unknown = [item for item in cited if item not in known]
    if unknown:
        errors.append(
            FragmentError(
                path="$.citedFieldIds",
                code="unknown_field",
                message=(
                    "These ids are not in the supplied envelope: "
                    f"{', '.join(sorted(set(unknown)))}."
                ),
            )
        )

    unusable = [item for item in cited if item in known and item not in usable]
    if unusable:
        errors.append(
            FragmentError(
                path="$.citedFieldIds",
                code="refused_field_cited",
                message=(
                    "A refused figure can never support the verdict: "
                    f"{', '.join(sorted(set(unusable)))}."
                ),
            )
        )
    return cited


def _axes(value: Any, errors: list[FragmentError]) -> tuple[AxisJudgment, ...]:
    if not isinstance(value, list):
        errors.append(
            FragmentError(
                path="$.axes",
                code="axes_missing",
                message="The four axes are required, in their fixed order.",
            )
        )
        return ()

    named = [item.get("axis") if isinstance(item, Mapping) else None for item in value]
    if named != [axis.value for axis in AXIS_ORDER]:
        errors.append(
            FragmentError(
                path="$.axes",
                code="axis_order",
                message=(
                    "The axes have to be exactly "
                    f"{', '.join(axis.value for axis in AXIS_ORDER)}, in that "
                    "order, with no others."
                ),
            )
        )
        return ()

    judgments: list[AxisJudgment] = []
    for index, item in enumerate(value):
        axis = Axis(named[index])
        emphasis = _enum_or_error(
            Emphasis,
            item.get("emphasis"),
            f"$.axes[{index}].emphasis",
            "emphasis",
            errors,
        )
        judgments.append(
            AxisJudgment(
                axis=axis,
                emphasis=emphasis or Emphasis.CONTEXT,
                emphasis_reason=_narration(
                    item.get("emphasisReason"),
                    f"$.axes[{index}].emphasisReason",
                    errors,
                ),
                read=_narration(item.get("read"), f"$.axes[{index}].read", errors),
            )
        )

    leads = [item for item in judgments if item.emphasis is Emphasis.LEAD]
    if len(leads) != 1:
        errors.append(
            FragmentError(
                path="$.axes",
                code="lead_axis",
                message=(
                    f"Exactly one axis is lead; this fragment named {len(leads)}."
                ),
            )
        )
    return tuple(judgments)


__all__ = [
    "AXIS_SCHEMA",
    "CHARS_PER_TOKEN",
    "FRAGMENT_FORMAT",
    "FRAGMENT_SCHEMA",
    "MAX_GENERATIONS_PER_ATTEMPT",
    "MAX_OUTPUT_TOKENS",
    "PROMPT_VERSION",
    "SYSTEM_PROMPT",
    "AnalysisFragment",
    "AxisJudgment",
    "Emphasis",
    "FragmentError",
    "FragmentRejected",
    "Verdict",
    "build_request",
    "generate_fragment",
    "spend_for",
    "validate_fragment",
]
