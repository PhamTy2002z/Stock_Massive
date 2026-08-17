"""The Recommendation Validator: groundedness as a runtime block (#82).

``docs/adr/0015`` states the invariant and refuses to let the prompt enforce it.
This module is the enforcement.  **A model assertion never substitutes for a
backend check**, and the model cannot certify that it passed this validator —
there is no field it can set, and no branch below reads one.

## What the model supplies, and what the backend supplies

The model supplies **structured evidence ids and nothing else**.  It never
writes citation prose, a source name, a unit, an ``as_of`` or an interpretation:
each of those is read off the trace and the Signal Registry here, and attached
by the backend.  That is what makes "the model narrates figures; it does not
calculate them" a property rather than an instruction.

The ids are inline markers, closed and small:

- ``[ev:CALL#PATH]`` — the reference for the figure immediately before it;
- ``[rec:SYMBOL@YYYY-MM-DD]`` — this block is a recommendation, for that symbol
  on that Trading Day;
- ``[ref-price:CALL#PATH]`` — the recommendation's explicit reference price;
- ``[zone:LABEL@CALL#PATH]`` — one price zone, which must be a registered field;
- ``[against:CALL#PATH]`` — material evidence pointing the other way;
- ``[user:LABEL]`` — a figure the user supplied, marked ``user_input``.

Brackets rather than braces because the System Prompt Contract's sections may
not contain a brace at all (``prompt/contract.py`` asserts it), and a protocol
the prompt cannot describe is a protocol the model cannot follow.

## Every figure is attributed, and one marker cannot cover two

A numeric literal in a block is grounded when the next marker after it has no
*other* numeric literal in between.  The rule is strict on purpose, and the
exemptions are listed in one place — :data:`_EXEMPT_PATTERNS` — rather than
spread through the scanner: an ISO date is the Trading Day, which the Gate
checks separately, and an ordered-list number is punctuation.

Strictness has a cost, and it is the cost the product chose.  A block the model
cannot attribute is blocked, and the Contract already tells it the same thing in
prose: *a figure you cannot reference is a figure you do not state*.  ADR-0016's
ops query watches exactly this — ``grounding_failed`` above 5% of Turns over 7
days means the Gate is blocking wrongly rather than the model fabricating.

## The failure is the Turn, never a retraction

An invalid block is never displayed and then flagged afterwards.  Validation
raises before :meth:`TurnPublisher.content_block` is reached, the Turn ends
``incomplete`` with the stable reason ``grounding_failed``, and the blocks that
already passed stay checkpointed and displayed — the user keeps the part that
was proven.
"""

from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, replace
from datetime import date
from enum import Enum
from typing import Any

from src.stocks.signals import registered_field

from .context import TranscriptToolCall
from .tools.catalog import refusal_reason
from .tools.fields import sanctioned_interpretation

GROUNDING_FAILED = "grounding_failed"

MARKER_PATTERN = re.compile(r"\[(ev|rec|ref-price|zone|against|user):([^\]\n]{1,200})\]")
NUMBER_PATTERN = re.compile(r"-?\d[\d.,]*")

# The complete exemption list. A number matched by one of these is punctuation
# or a date rather than a material figure, and nothing else is exempt.
_EXEMPT_PATTERNS = (
    # An ISO Trading Day. The Gate validates the day it belongs to separately,
    # against the trusted runtime context rather than against a trace.
    re.compile(r"\d{4}-\d{2}-\d{2}"),
    # The same Trading Day written the way its reader writes one: 14/08, or
    # 14/08/2026. Exempt for exactly the reason the ISO form is — it is a date,
    # not a figure — and it has to be, because the Contract answers in
    # Vietnamese and tells the model to name the session it answered from. Left
    # out, a date read as the two numbers either side of a slash makes the most
    # ordinary sentence in the product unattributable, and the Turn ends rather
    # than the sentence.
    #
    # The day and month ranges are checked so that this stays a date pattern.
    # It still lets a small written fraction — "3/5 phiên" — through the
    # attribution rule, and that is the accepted cost: figures in this system
    # are field values, narrated as decimals, and none of them is a fraction.
    re.compile(r"\b(?:0?[1-9]|[12]\d|3[01])/(?:0?[1-9]|1[0-2])(?:/\d{4})?\b"),
    # An ordered-list marker at the start of a line.
    re.compile(r"(?m)^[ \t]{0,3}\d+[.)](?=\s)"),
)

# What a money or share figure may honestly be rewritten by, and nothing else.
# "3,4 nghìn tỷ" and "3400000000000" are the same fact; a z-score written a
# thousand times too large is not.
_SCALES = (1, 1_000, 1_000_000, 1_000_000_000)
_SCALABLE_UNITS = frozenset({"vnd", "shares"})


class EvidenceSource(str, Enum):
    """Where a cited number came from, which decides what it may support."""

    # Computed in code and declared in the Signal Registry.
    REGISTERED_FIELD = "registered_field"
    # Read straight from a stored provider row through the Tool Catalog.
    STORED = "stored"
    # Found only in news. Unverified, and never a basis on its own.
    SOURCE_CLAIM = "source_claim"
    # Retrieved from an open web source, MCP server, or the Knowledge Store.
    # Persistence does not promote it: the source remains external and
    # unsuitable as the sole basis for a recommendation or price zone.
    EXTERNAL_CLAIM = "external_claim"
    # Produced by the isolated executor. It is reproducible arithmetic, but it
    # did not pass the Signal Registry's calibration and suitability bar.
    DERIVED = "derived"
    # Supplied by the user in this conversation.
    USER_INPUT = "user_input"


class BlockKind(str, Enum):
    PROSE = "prose"
    RECOMMENDATION = "recommendation"


#: The Gate conditions a recommendation fails when the *evidence* for it was
#: not there — as opposed to the conditions it fails when the block says
#: something its evidence does not.
#:
#: The distinction decides what the reader gets. Both classes keep the block off
#: the screen; only this one lets the Turn carry on and say why, because "no
#: registered price zone could be computed for this symbol today" is an answer,
#: and a blank Turn is not. A figure that contradicts its own citation is not in
#: here and never will be: that is the confident false number the whole design
#: exists to stop, and it ends the Turn.
DEGRADABLE_GATE_CODES = frozenset(
    {
        "missing_reference_price",
        "missing_price_zone",
        "unregistered_price_zone",
        "window_health_refusal",
        "no_supporting_field",
        "no_contradictory_evidence",
        "news_only_basis",
        "unreferenced_figure",
    }
)

#: What the reader is told in place of the recommendation that was dropped.
#:
#: Backend-authored and versioned for the same reason the Risk Notice is: a
#: sentence the model writes is a sentence the model can be talked out of. It
#: carries no figure by construction, so it needs no citation and cannot itself
#: fail the Gate.
DEGRADED_RECOMMENDATION_NOTICE = (
    "Tôi chưa đưa ra khuyến nghị vùng giá cho câu hỏi này: bằng chứng bắt buộc "
    "cho một khuyến nghị chưa đủ ({reason}). Phần nhận định ở trên là những gì "
    "dữ liệu hiện có chứng minh được."
)

#: One Vietnamese clause per degradable condition, so the sentence above names
#: what was missing instead of gesturing at it.
DEGRADED_REASON_TEXT = {
    "missing_reference_price": "chưa có giá tham chiếu nào được tính trong mã nguồn",
    "missing_price_zone": "chưa có vùng giá nào được tính trong mã nguồn",
    "unregistered_price_zone": "vùng giá được nêu không phải một chỉ số đã đăng ký",
    "window_health_refusal": "cửa sổ dữ liệu của bằng chứng bị từ chối",
    "no_supporting_field": "chưa có chỉ số đã đăng ký nào ủng hộ nhận định",
    "no_contradictory_evidence": "chưa nêu được bằng chứng ngược chiều",
    "news_only_basis": "vùng giá chỉ dựa trên nguồn tin, không phải số liệu tính được",
    "unreferenced_figure": "có con số chưa gắn được với bằng chứng nào",
}


class GroundingFailure(Exception):
    """One block that cannot be proven, and why.

    ``code`` is stable and branchable; ``detail`` is the operator's sentence.
    The Turn's terminal reason is always :data:`GROUNDING_FAILED` — the code
    here says which condition failed, and it belongs in the Evidence Manifest
    rather than in the user's answer.
    """

    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.reason = GROUNDING_FAILED

    @property
    def degradable(self) -> bool:
        """Whether the Turn may carry on and say what was missing.

        Read by the loop, never by the model: there is no field it can set to
        make a failure degradable, exactly as there is none to make a block
        pass.
        """
        return self.code in DEGRADABLE_GATE_CODES

    def notice(self) -> str:
        """The reader's sentence for this failure, or the empty string."""
        reason = DEGRADED_REASON_TEXT.get(self.code)
        if reason is None:
            return ""
        return DEGRADED_RECOMMENDATION_NOTICE.format(reason=reason)


@dataclass(frozen=True)
class EvidenceRef:
    """One ``tool_call_id + field_path`` pair, exactly as the model wrote it."""

    call_id: str
    field_path: str

    @classmethod
    def parse(cls, body: str) -> "EvidenceRef":
        call_id, separator, field_path = body.partition("#")
        if not separator or not call_id.strip() or not field_path.strip():
            raise GroundingFailure(
                "malformed_reference",
                f"{body!r} is not a tool call id and a field path separated by '#'",
            )
        return cls(call_id=call_id.strip(), field_path=field_path.strip())


@dataclass(frozen=True)
class Citation:
    """One resolved reference, as the backend describes it to everyone.

    This is the shape the visible answer takes its unit and ``as_of`` from, the
    shape the *Sources & methods* surface renders, and the shape the Evidence
    Manifest keeps forever. One shape rather than three, because three would let
    the answer and the record disagree about what was cited.
    """

    call_id: str
    tool_name: str
    field_path: str
    value: Any
    unit: str | None
    interpretation: str | None
    claim: str | None
    provenance: str
    as_of: str | None
    stale: bool
    source: EvidenceSource
    window_health: Mapping[str, Any] | None = None
    contradictory: bool = False
    zone_label: str | None = None
    reference_price: bool = False
    # The Signal Registry declaration this citation resolved through, when it
    # resolved through one. ``field_path`` cannot be reduced back to it: a
    # registered field's own name is dotted, so the path does not split into a
    # name and a remainder without consulting what the call actually served.
    # ADR-0012's Widget descriptor needs the bare name to reconstruct the same
    # slice a year later, so the resolution that already worked it out keeps it
    # rather than making a second reader guess.
    field_name: str | None = None

    @property
    def window_health_refusal(self) -> str | None:
        if not self.window_health:
            return None
        refusal = self.window_health.get("refusal")
        return str(refusal) if refusal else None

    def as_wire(self) -> dict[str, Any]:
        return {
            "tool_call_id": self.call_id,
            "tool_name": self.tool_name,
            "field_path": self.field_path,
            "value": self.value,
            "unit": self.unit,
            "interpretation": self.interpretation,
            "claim": self.claim,
            "provenance": self.provenance,
            "as_of": self.as_of,
            "stale": self.stale,
            "source": self.source.value,
            "window_health": (
                dict(self.window_health) if self.window_health is not None else None
            ),
            "contradictory": self.contradictory,
            "zone_label": self.zone_label,
            "reference_price": self.reference_price,
            "field_name": self.field_name,
        }


@dataclass(frozen=True)
class ReleasedBlock:
    """A block that passed, and everything the backend attached to it."""

    text: str
    kind: BlockKind
    citations: tuple[Citation, ...]
    symbol: str | None = None
    trading_day: str | None = None
    #: Figures stated in this block that no reference in the Turn attributes.
    #: Always empty on a recommendation — that kind refuses rather than labels.
    #: The literals as written, because the renderer's label names them and a
    #: reader has to be able to find them in the sentence they are reading.
    unverified_figures: tuple[str, ...] = ()

    def as_wire(self) -> dict[str, Any]:
        return {
            "kind": self.kind.value,
            "text": self.text,
            "symbol": self.symbol,
            "trading_day": self.trading_day,
            "citations": [citation.as_wire() for citation in self.citations],
            "unverified_figures": list(self.unverified_figures),
        }


@dataclass(frozen=True)
class _Marker:
    kind: str
    body: str
    start: int
    end: int


def _markers(text: str) -> tuple[_Marker, ...]:
    return tuple(
        _Marker(kind=match.group(1), body=match.group(2).strip(), start=match.start(), end=match.end())
        for match in MARKER_PATTERN.finditer(text)
    )


def _exempt_spans(text: str) -> tuple[tuple[int, int], ...]:
    spans = [(marker.start, marker.end) for marker in _markers(text)]
    for pattern in _EXEMPT_PATTERNS:
        spans.extend(match.span() for match in pattern.finditer(text))
    return tuple(spans)


def _material_numbers(text: str) -> tuple[tuple[int, int, str], ...]:
    """Every numeric literal a block has to attribute, with its position."""
    exempt = _exempt_spans(text)
    found: list[tuple[int, int, str]] = []
    for match in NUMBER_PATTERN.finditer(text):
        start, end = match.span()
        if any(low <= start < high for low, high in exempt):
            continue
        # The permissive scanner includes sentence punctuation so it can read
        # both Vietnamese and machine separator conventions. Punctuation is
        # not part of the literal shown in an unverified-figure label.
        found.append((start, end, match.group().rstrip(".,")))
    return tuple(found)


def display_text(text: str) -> str:
    """The block as the user sees it, with every marker removed.

    A marker sits between the figure it attributes and whatever follows, so
    removing it leaves either a doubled space or a space stranded in front of
    the sentence's own punctuation. Both are repaired here rather than by asking
    the model to place markers considerately, because a rendering defect is not
    something a prompt should be responsible for.
    """
    stripped = MARKER_PATTERN.sub("", text)
    stripped = re.sub(r"[ \t]{2,}", " ", stripped)
    stripped = re.sub(r"[ \t]+([.,;:!?)\]])", r"\1", stripped)
    return "\n".join(line.rstrip() for line in stripped.splitlines()).strip()


def _numeric(literal: str) -> float | None:
    """Read a figure the way a Vietnamese answer writes one.

    Both separator conventions appear in the same product — a tool result is
    machine-formatted and a Vietnamese sentence is not — so the shape is decided
    per literal rather than by a locale setting nothing sets.
    """
    text = literal.strip().rstrip(".")
    if not text:
        return None
    if "," in text and "." in text:
        # The rightmost separator is the decimal one; the other groups digits.
        if text.rfind(",") > text.rfind("."):
            text = text.replace(".", "").replace(",", ".")
        else:
            text = text.replace(",", "")
    elif "," in text:
        whole, _, fraction = text.rpartition(",")
        text = f"{whole}.{fraction}" if len(fraction) != 3 else text.replace(",", "")
    elif "." in text:
        # The convention this product is read in: a dot groups thousands and a
        # comma is the decimal separator, so "71.800" is seventy-one thousand
        # eight hundred and not seventy-one point eight. Judged by the same
        # three-digit test the comma branch above uses rather than by a locale
        # setting nothing sets — and it has to be judged, because `float()`
        # reads the dot as a decimal point and turns a share price into a
        # `figure_mismatch` the writer cannot see anything wrong with.
        #
        # `_decimals` already applies this test to both separators, so a figure
        # written this way was being compared to zero places and parsed to one:
        # the two halves of the same comparison disagreed.
        whole, _, fraction = text.rpartition(".")
        if whole and len(fraction) == 3:
            text = text.replace(".", "")
    try:
        return float(text)
    except ValueError:
        return None


def _decimals(literal: str) -> int:
    tail = literal.strip().rstrip(".")
    for separator in (".", ","):
        head, found, fraction = tail.rpartition(separator)
        if found and head and len(fraction) != 3:
            return len(fraction)
    return 0


def figures_agree(stated: str, actual: Any, *, unit: str | None) -> bool:
    """Whether the figure written in the block is the figure in the trace.

    Compared at the precision the answer was written to, because "12.5" and
    12.4997 are the same number told to a reader and a mismatch told to a float.

    Money and share counts additionally match at a thousand, a million or a
    billion, since "3,4 nghìn tỷ đồng" and the raw dong figure are the same
    fact. Nothing else scales: a z-score or a percentage written a thousand
    times too large is wrong, and silently accepting it is the failure this
    function exists to catch.
    """
    if not isinstance(actual, (int, float)) or isinstance(actual, bool):
        return False
    wanted = _numeric(stated)
    if wanted is None:
        return False
    places = _decimals(stated)
    scales = _SCALES if (unit or "").lower() in _SCALABLE_UNITS else (1,)
    for scale in scales:
        if round(float(actual) / scale, places) == round(wanted, places):
            return True
    return False


class TraceIndex:
    """This Turn's Tool Call Traces, and the only thing a reference resolves in.

    Built from the calls the Turn itself made. That is what makes "a reference
    to another Turn's trace fails validation" a property of the data structure
    rather than a check someone has to remember to write: another Turn's calls
    are not in here.
    """

    def __init__(self, calls: Sequence[TranscriptToolCall] = ()) -> None:
        self._calls = {call.call_id: call for call in calls}

    @property
    def call_ids(self) -> tuple[str, ...]:
        return tuple(self._calls)

    def call(self, call_id: str) -> TranscriptToolCall | None:
        """One of this Turn's calls, by the id the model referred to it by.

        ``None`` rather than a failure, because the callers that want the call
        itself — rather than a figure out of it — are asking a question that has
        a legitimate negative answer: which symbol did this call answer about,
        and is this call one of the ones already drawn elsewhere.
        """
        return self._calls.get(call_id)

    def admitted_symbols(self) -> frozenset[str]:
        """Every symbol a tool answered about without a Universe refusal.

        Universe membership stays deterministic in the tool layer; this reads
        the tool layer's answer rather than asking the Universe a second
        question, so a symbol the tools served and the Gate refuses cannot
        disagree.
        """
        admitted: set[str] = set()
        for call in self._calls.values():
            result = call.result
            if not isinstance(result, Mapping) or refusal_reason(result) is not None:
                continue
            symbol = result.get("symbol")
            if isinstance(symbol, str) and symbol:
                admitted.add(symbol.upper())
        return frozenset(admitted)

    def resolve_descriptor(self, ref: EvidenceRef) -> tuple[TranscriptToolCall, Any]:
        """The raw leaf a reference points at, with no citation semantics.

        A Widget binds to two different kinds of thing (``docs/adr/0012``). One
        is a *figure*, and it goes through :meth:`resolve` because a figure has
        to arrive with the unit and the sanctioned reading the Recommendation
        Validator would attach to it. The other is a *retrieval descriptor* —
        a Data Reference, or the arguments a screen was run with — which
        carries no unit and no interpretation and is not a citation at all.
        Pushing the second through :meth:`resolve` would make it fail on the
        ``as_of`` a descriptor legitimately does not have, so it resolves here
        instead: same index, same Turn, same "another Turn's calls are not in
        here" property, and no invented citation.
        """
        call = self._require(ref)
        result = call.result
        leaf, _container = _walk(result, [part for part in ref.field_path.split(".") if part], ref)
        return call, leaf

    def resolve(self, ref: EvidenceRef) -> Citation:
        call = self._require(ref)
        return self._citation(call, call.result, ref)

    def _require(self, ref: EvidenceRef) -> TranscriptToolCall:
        """The call a reference names, or the reason it cannot be cited."""
        call = self._calls.get(ref.call_id)
        if call is None:
            raise GroundingFailure(
                "unknown_tool_call",
                f"no tool call {ref.call_id!r} was made in this Turn",
            )
        result = call.result
        if not isinstance(result, Mapping):
            raise GroundingFailure(
                "unfinished_tool_call",
                f"tool call {ref.call_id!r} has no result to cite",
            )
        refused = refusal_reason(result)
        if refused is not None:
            raise GroundingFailure(
                "refused_tool_call",
                f"tool call {ref.call_id!r} answered {refused!r} and carries no figure",
            )
        return call

    def _citation(
        self,
        call: TranscriptToolCall,
        result: Mapping[str, Any],
        ref: EvidenceRef,
    ) -> Citation:
        parts = [part for part in ref.field_path.split(".") if part]
        if parts and parts[0] == "registered_fields":
            return self._registered(call, result, ref, parts)
        leaf, container = _walk(result, parts, ref)
        stamped = _claim_container(result, parts)
        if stamped is None:
            stamped = leaf if isinstance(leaf, Mapping) else container
        claim_class = stamped.get("claim_class") if isinstance(stamped, Mapping) else None
        if "untrusted_evidence" in parts or claim_class in {
            EvidenceSource.SOURCE_CLAIM.value,
            EvidenceSource.EXTERNAL_CLAIM.value,
            EvidenceSource.DERIVED.value,
        }:
            return self._untrusted_claim(call, ref, leaf, stamped)
        return self._stored(call, result, ref, leaf, container)

    def _registered(
        self,
        call: TranscriptToolCall,
        result: Mapping[str, Any],
        ref: EvidenceRef,
        parts: Sequence[str],
    ) -> Citation:
        # A registered field's name is itself dotted — ``indicator_pack.rsi_14``
        # — so the path cannot be split on dots and then indexed. The longest
        # matching key wins, which is the only rule that stays right if two
        # field names ever share a prefix.
        served = result.get("registered_fields")
        remainder = ".".join(parts[1:])
        name = None
        if isinstance(served, Mapping):
            name = next(
                (
                    key
                    for key in sorted(served, key=len, reverse=True)
                    if remainder == key or remainder.startswith(f"{key}.")
                ),
                None,
            )
        if name is None:
            raise GroundingFailure(
                "unknown_field_path",
                f"tool call {ref.call_id!r} returned no registered field for "
                f"{ref.field_path!r}",
            )
        serialized = served[name]
        if not isinstance(serialized, Mapping):
            raise GroundingFailure(
                "unknown_field_path",
                f"tool call {ref.call_id!r} returned no registered field {name!r}",
            )
        inside = [part for part in remainder[len(name) :].split(".") if part]
        leaf = serialized if not inside else _walk(serialized, inside, ref)[0]
        try:
            declared = registered_field(name)
        except (KeyError, ValueError) as exc:
            raise GroundingFailure(
                "field_not_registered",
                f"{name!r} is not a Signal Registry declaration",
            ) from exc

        # The registry is the authority; a serialized result that disagrees with
        # it is a tampered or stale projection, and either way the figure cannot
        # be narrated under a reading the registry never sanctioned.
        for key, expected in (
            ("unit", declared.unit.value),
            ("claim", declared.claim.value),
            ("source", declared.source.value),
            ("interpretation", sanctioned_interpretation(declared)),
        ):
            if serialized.get(key) != expected:
                raise GroundingFailure(
                    f"{key}_mismatch",
                    f"{name}.{key} came back as {serialized.get(key)!r} but the Signal "
                    f"Registry declares {expected!r}",
                )
        if serialized.get("refusal"):
            raise GroundingFailure(
                "refused_field",
                f"{name} was refused ({serialized['refusal']}) and carries no value",
            )

        health = serialized.get("window_health") or result.get("window_health")
        as_of = result.get("as_of") or _last_session(health)
        if not as_of:
            raise GroundingFailure(
                "missing_as_of", f"{name} carries no date it was computed for"
            )
        value = leaf if not isinstance(leaf, Mapping) else leaf.get("value")
        if value is None and parts[-1] == "value":
            raise GroundingFailure(
                "missing_value", f"{name} has no value to narrate"
            )
        return Citation(
            call_id=ref.call_id,
            tool_name=call.name,
            field_path=ref.field_path,
            value=value,
            unit=str(serialized["unit"]),
            interpretation=str(serialized["interpretation"]),
            claim=str(serialized["claim"]),
            provenance=f"{call.name}:{name}",
            as_of=str(as_of),
            stale=bool(serialized.get("degraded_reason")),
            source=EvidenceSource.REGISTERED_FIELD,
            window_health=health if isinstance(health, Mapping) else None,
            field_name=name,
        )

    @staticmethod
    def _untrusted_claim(
        call: TranscriptToolCall,
        ref: EvidenceRef,
        leaf: Any,
        container: Mapping[str, Any] | None,
    ) -> Citation:
        item = container if isinstance(container, Mapping) else {}
        try:
            source = EvidenceSource(str(item.get("claim_class")))
        except ValueError as exc:
            # Reached only if the news tool's own envelope changed shape. It is
            # a failure rather than a default, because defaulting here would
            # quietly promote an untrusted claim to a stored figure.
            raise GroundingFailure(
                "unclassified_claim",
                f"{ref.field_path!r} is inside untrusted evidence that declares no "
                "claim class",
            ) from exc
        if source not in {
            EvidenceSource.SOURCE_CLAIM,
            EvidenceSource.EXTERNAL_CLAIM,
            EvidenceSource.DERIVED,
        }:
            raise GroundingFailure(
                "unclassified_claim",
                f"{ref.field_path!r} declares unsupported claim class {source.value!r}",
            )
        return Citation(
            call_id=ref.call_id,
            tool_name=call.name,
            field_path=ref.field_path,
            value=leaf,
            unit=None,
            interpretation=None,
            claim=None,
            provenance=str(item.get("source") or item.get("source_name") or call.name),
            as_of=str(
                item.get("published_at")
                or item.get("retrieved_at")
                or item.get("as_of")
                or ""
            )
            or None,
            stale=False,
            source=source,
        )

    @staticmethod
    def _stored(
        call: TranscriptToolCall,
        result: Mapping[str, Any],
        ref: EvidenceRef,
        leaf: Any,
        container: Mapping[str, Any] | None,
    ) -> Citation:
        stamped = leaf if isinstance(leaf, Mapping) else container
        stamped = stamped if isinstance(stamped, Mapping) else {}
        value = leaf.get("value") if isinstance(leaf, Mapping) else leaf
        as_of = stamped.get("as_of") or result.get("as_of") or result.get("trading_day")
        if not as_of:
            raise GroundingFailure(
                "missing_as_of",
                f"{ref.field_path!r} carries no date, so its staleness cannot be shown",
            )
        return Citation(
            call_id=ref.call_id,
            tool_name=call.name,
            field_path=ref.field_path,
            value=value,
            unit=stamped.get("unit"),
            interpretation=None,
            claim=None,
            provenance=call.name,
            as_of=str(as_of),
            stale=bool(stamped.get("stale")),
            source=EvidenceSource.STORED,
            window_health=(
                result["window_health"]
                if isinstance(result.get("window_health"), Mapping)
                else None
            ),
        )


def _walk(
    result: Mapping[str, Any],
    parts: Sequence[str],
    ref: EvidenceRef,
) -> tuple[Any, Mapping[str, Any] | None]:
    """Follow a dotted field path, returning the leaf and its container."""
    if not parts:
        raise GroundingFailure("malformed_reference", "an empty field path resolves nothing")
    current: Any = result
    container: Mapping[str, Any] | None = None
    for part in parts:
        if isinstance(current, Mapping) and part in current:
            container = current
            current = current[part]
            continue
        if isinstance(current, Sequence) and not isinstance(current, (str, bytes)):
            try:
                index = int(part)
            except ValueError:
                index = -1
            if 0 <= index < len(current):
                current = current[index]
                continue
        raise GroundingFailure(
            "unknown_field_path",
            f"{ref.field_path!r} does not exist in the result of tool call "
            f"{ref.call_id!r}",
        )
    return current, container


def _claim_container(
    result: Mapping[str, Any], parts: Sequence[str]
) -> Mapping[str, Any] | None:
    """The nearest ancestor that declares a claim class, if one exists."""
    current: Any = result
    found: Mapping[str, Any] | None = (
        result if result.get("claim_class") is not None else None
    )
    for part in parts:
        if isinstance(current, Mapping) and part in current:
            current = current[part]
        elif isinstance(current, Sequence) and not isinstance(current, (str, bytes)):
            try:
                current = current[int(part)]
            except (ValueError, IndexError):
                return found
        else:
            return found
        if isinstance(current, Mapping) and current.get("claim_class") is not None:
            found = current
    return found


def _last_session(health: Any) -> str | None:
    if isinstance(health, Mapping):
        last = health.get("last_session")
        return str(last) if last else None
    return None


class RecommendationValidator:
    """The seven Gate conditions, each enforced on its own.

    Independent checks rather than one composite score: the Gate is a runtime
    block, and a block that fails on Window Health alone must be refused for
    that reason alone. Each condition below is reachable by a test that breaks
    only it.
    """

    def __init__(self, *, trading_day: date) -> None:
        self._trading_day = trading_day

    def validate(self, text: str, traces: TraceIndex) -> ReleasedBlock:
        """Prove one block, label what it could not prove, or refuse it.

        Prose is never refused for a figure it failed to attribute: the figure
        travels on the block as ``unverified_figures`` and the renderer says so
        (``docs/adr/0018``). A recommendation still is — an action carrying a
        number nobody can check is the one output where the label is not enough.
        """
        markers = _markers(text)
        cited: dict[int, Citation] = {}
        for index, marker in enumerate(markers):
            if marker.kind != "rec":
                cited[index] = self._cite(marker, traces)
        unverified = self._match_figures(text, markers, cited)
        citations = tuple(cited[index] for index in sorted(cited))

        recommendation = next((m for m in markers if m.kind == "rec"), None)
        if recommendation is None:
            return ReleasedBlock(
                text=display_text(text),
                kind=BlockKind.PROSE,
                citations=citations,
                unverified_figures=unverified,
            )
        if unverified:
            raise GroundingFailure(
                "unreferenced_figure",
                f"a recommendation states {unverified[0]!r} with no evidence "
                "reference attributing it",
            )
        symbol, trading_day = self._declaration(recommendation.body)
        self._gate(symbol, citations, traces)
        return ReleasedBlock(
            text=display_text(text),
            kind=BlockKind.RECOMMENDATION,
            citations=citations,
            symbol=symbol,
            trading_day=trading_day.isoformat(),
        )

    def _cite(self, marker: _Marker, traces: TraceIndex) -> Citation:
        if marker.kind == "user":
            return _user_citation(marker.body)
        body = marker.body
        label: str | None = None
        if marker.kind == "zone":
            label, separator, body = body.partition("@")
            if not separator:
                raise GroundingFailure(
                    "malformed_reference",
                    f"{marker.body!r} is not a zone label and a reference separated "
                    "by '@'",
                )
            label = label.strip()
        citation = traces.resolve(EvidenceRef.parse(body))
        if marker.kind == "against":
            return replace(citation, contradictory=True)
        if marker.kind == "zone":
            return replace(citation, zone_label=label)
        if marker.kind == "ref-price":
            return replace(citation, reference_price=True)
        return citation

    @staticmethod
    def _match_figures(
        text: str,
        markers: Sequence[_Marker],
        cited: Mapping[int, Citation],
    ) -> tuple[str, ...]:
        """Attribute every material figure, and check it against its trace.

        Two failures are found here and they are different failures, which is
        why only one of them raises.

        A figure whose reference resolves to a different number was attributed
        to evidence that does not say what the sentence says. That is the
        confident false figure the whole design exists to prevent, and the one
        case a prompt cannot catch — it raises, always, in prose as much as in
        a recommendation.

        A figure with **no** reference after it was never attributed at all.
        That is a weaker claim: the sentence may be right, and the model simply
        had nothing in the Turn to point at. It is returned rather than raised,
        and the caller decides — prose carries it to the reader under a label,
        a recommendation still refuses it.
        """
        positions = sorted((marker.start, index) for index, marker in enumerate(markers))
        numbers = _material_numbers(text)
        unattributed: list[str] = []
        for order, (_start, end, literal) in enumerate(numbers):
            attributed = next(
                ((start, index) for start, index in positions if start >= end), None
            )
            if attributed is None:
                # Stated with no evidence reference after it.
                unattributed.append(literal)
                continue
            start, index = attributed
            following = numbers[order + 1][0] if order + 1 < len(numbers) else None
            if following is not None and following < start:
                # Followed by another figure before any reference, so the one
                # reference that exists cannot be said to belong to this one.
                unattributed.append(literal)
                continue
            citation = cited.get(index)
            if citation is None:
                # The nearest marker is the recommendation declaration, which
                # names a symbol and a Trading Day rather than evidence.
                unattributed.append(literal)
                continue
            if citation.source is EvidenceSource.USER_INPUT:
                # The user's own number needs no trace; it is marked instead, so
                # nothing downstream can mistake it for something the system
                # computed.
                continue
            if not figures_agree(literal, citation.value, unit=citation.unit):
                raise GroundingFailure(
                    "figure_mismatch",
                    f"the block states {literal!r} but {citation.field_path} in tool "
                    f"call {citation.call_id!r} holds {citation.value!r}",
                )
        return tuple(unattributed)

    def _declaration(self, body: str) -> tuple[str, date]:
        symbol, separator, day = body.partition("@")
        if not separator:
            raise GroundingFailure(
                "missing_trading_day",
                f"{body!r} names no Trading Day for the recommendation",
            )
        try:
            declared = date.fromisoformat(day.strip())
        except ValueError as exc:
            raise GroundingFailure(
                "missing_trading_day", f"{day.strip()!r} is not a Trading Day"
            ) from exc
        if declared != self._trading_day:
            raise GroundingFailure(
                "trading_day_mismatch",
                f"the block declares {declared.isoformat()} but this Turn is dated "
                f"{self._trading_day.isoformat()}",
            )
        return symbol.strip().upper(), declared

    def _gate(
        self,
        symbol: str,
        citations: Sequence[Citation],
        traces: TraceIndex,
    ) -> None:
        # 1. The symbol belongs to the Universe.
        if symbol not in traces.admitted_symbols():
            raise GroundingFailure(
                "symbol_not_in_universe",
                f"no tool in this Turn served {symbol} without a Universe refusal",
            )

        # 2. Its Trading Day and reference price are explicit. The day is
        #    proven by ``_declaration``; the price gets a marker of its own,
        #    because "the price it is trading around" is the one figure a
        #    recommendation cannot leave to the reader to infer.
        if not any(citation.reference_price for citation in citations):
            raise GroundingFailure(
                "missing_reference_price",
                "the recommendation states no reference price backed by a tool call",
            )

        # 3. Every price zone is a registered field computed in code.
        zones = [citation for citation in citations if citation.zone_label is not None]
        if not zones:
            raise GroundingFailure(
                "missing_price_zone",
                "the recommendation names no price zone",
            )
        for zone in zones:
            if zone.source in {
                EvidenceSource.SOURCE_CLAIM,
                EvidenceSource.EXTERNAL_CLAIM,
                EvidenceSource.DERIVED,
            }:
                # Left to condition 7, which is the precise diagnosis: this is
                # news carrying a price zone, not a computation that failed to
                # be registered.
                continue
            if zone.source is not EvidenceSource.REGISTERED_FIELD:
                raise GroundingFailure(
                    "unregistered_price_zone",
                    f"the price zone {zone.zone_label!r} is not a registered field "
                    "computed in code",
                )

        # 4. Window Health is not a refusal.
        for citation in citations:
            refusal = citation.window_health_refusal
            if refusal:
                raise GroundingFailure(
                    "window_health_refusal",
                    f"{citation.field_path} rests on a window that refused: {refusal}",
                )

        # 5. The verdict cites at least one suitable registered field and
        #    exposes material contradictory evidence.
        #
        #    The zone and the reference price are excluded from what counts as
        #    support, and that exclusion is what keeps this condition worth
        #    having: both are already required by 2 and 3, so counting them
        #    would make this check pass by construction and test nothing. A
        #    recommendation has to cite a field that argues *for* the verdict,
        #    over and above the levels it names.
        supporting = [
            citation
            for citation in citations
            if citation.source is EvidenceSource.REGISTERED_FIELD
            and not citation.contradictory
            and citation.zone_label is None
            and not citation.reference_price
        ]
        if not supporting:
            raise GroundingFailure(
                "no_supporting_field",
                "the verdict names levels but cites no registered field arguing for it",
            )
        if not any(citation.contradictory for citation in citations):
            raise GroundingFailure(
                "no_contradictory_evidence",
                "the verdict exposes no material evidence pointing the other way",
            )

        # 6. Every cited field carries value, unit, sanctioned interpretation,
        #    provenance and staleness.
        #
        #    *Field* is read the way the rest of this codebase reads it — a
        #    Signal Registry declaration — because that is where a unit and a
        #    sanctioned interpretation exist to be carried. A stored reference
        #    price is a price rather than a field, and is held to what it can
        #    actually supply: provenance and a date. A source claim and the
        #    user's own number are held to neither, and both are already barred
        #    from supporting the verdict by 5 and 7.
        for citation in citations:
            if citation.source is EvidenceSource.USER_INPUT:
                continue
            required: tuple[tuple[str, bool], ...] = (
                ("value", citation.value is not None),
                ("provenance", bool(citation.provenance)),
                ("staleness", citation.as_of is not None),
            )
            if citation.source is EvidenceSource.REGISTERED_FIELD:
                required += (
                    ("unit", bool(citation.unit)),
                    ("interpretation", bool(citation.interpretation)),
                )
            missing = [name for name, present in required if not present]
            if missing:
                raise GroundingFailure(
                    "incomplete_citation",
                    f"{citation.field_path} is cited without {', '.join(missing)}",
                )

        # 7. Unregistered evidence is not a directional basis. Conditions 2
        #    and 3 hand an untrusted claim down to here rather than refusing it,
        #    because "the price zone is not registered" is the wrong sentence
        #    for a number that came out of a news article: the failure is the
        #    source, and this is the condition that says so.
        for citation in citations:
            if citation.source not in {
                EvidenceSource.SOURCE_CLAIM,
                EvidenceSource.EXTERNAL_CLAIM,
                EvidenceSource.DERIVED,
            }:
                continue
            if citation.reference_price or citation.zone_label is not None:
                raise GroundingFailure(
                    "news_only_basis",
                    "a price zone or reference price rests on unregistered evidence "
                    "alone",
                )


def _user_citation(label: str) -> Citation:
    """A figure the user supplied, marked and never promoted.

    It resolves against no trace because there is none: the user said it. Marked
    ``user_input`` so the Gate's completeness check and the Evidence Manifest
    both see a number the system did not produce.
    """
    return Citation(
        call_id="",
        tool_name="",
        field_path=f"user_input:{label}",
        value=label,
        unit=None,
        interpretation=None,
        claim=None,
        provenance="user_input",
        as_of=None,
        stale=False,
        source=EvidenceSource.USER_INPUT,
    )


__all__ = [
    "GROUNDING_FAILED",
    "BlockKind",
    "Citation",
    "EvidenceRef",
    "EvidenceSource",
    "GroundingFailure",
    "RecommendationValidator",
    "ReleasedBlock",
    "TraceIndex",
    "display_text",
    "figures_agree",
]
