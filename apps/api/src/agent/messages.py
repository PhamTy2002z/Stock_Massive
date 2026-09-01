"""One Turn's transcript, and the context constructed from it.

A pure function of a transcript and a budget, with no I/O, no clock and no LLM.
Trimming is the part of an agent harness most likely to be wrong in a way nobody
notices — it silently changes what the model saw, and a bug in it looks exactly
like the model being stupid — so every trimming decision here is a unit test
rather than a live experiment.

Its own module rather than a section of the loop because two callers meet here.
The loop constructs the context it sends; the transport reads a Thread out of the
store and hands it over as :class:`TranscriptTurn`. A type both of them name is a
shared boundary, and putting it inside the loop would make the transport import
the loop to describe a row it read from a table.
"""

from __future__ import annotations

import json
import uuid
from collections.abc import Iterator, Mapping, Sequence
from dataclasses import dataclass, field, replace
from enum import Enum
from typing import Any
from urllib.parse import parse_qsl, urlsplit

from src.core.llm import ContentSegment, ImageContent, Message, Role, ToolCall
from src.core.llm.admission import TURN_CONTEXT_PER_CALL

from . import registry
from .untrusted import wrap_attachment, wrap_result

#: What a tool call went and read, as the surface is told it. Two values, and the
#: distinction is the one the evidence boundary is built on: a figure out of this
#: system's store has a date and a health and reads the same tomorrow, and a page
#: has none of those. A surface that drew them alike would be undoing in pixels
#: what ``untrusted.py`` does in the message.
EXTERNAL_KIND = "external"
STORE_KIND = "store"


#: The two things a piece of a Turn's prose can be.
#:
#: ``answer`` is the reply. ``thought`` is a sentence written on the way to it,
#: in a round that went on to call tools — it belongs to the timeline of what
#: happened rather than to what was concluded.
#:
#: Here rather than in the transport, for the reason ``ToolCallStatus`` is here:
#: the loop produces these and the transport streams them, and the loop names
#: the shape of the transport rather than importing its module.
ANSWER = "answer"
THOUGHT = "thought"


class ToolCallStatus(str, Enum):
    """The five states the interactive surface renders a tool call in.

    ``pending`` is a call that has been *written down* before its effect runs:
    the harness checkpoints the intent of a batch that changes durable state, so
    a crash between dispatch and result leaves a record saying the effect may
    have happened. ``running`` is stronger — it means the call is on its way to
    the tool — and the difference is the whole reason both exist.

    ``denied`` is a call the declaration's permission rule refused. It never
    reached a tool and never will, which is a different fact from ``error``: a
    tool that broke is worth asking again and a closed route is not. The
    ``error`` code travels beside it in the transcript, but not on the rendered
    channel (``events.TOOL_CALL_FIELDS`` carries no ``error``), so the status is
    where a surface learns this.

    The Tool Call Trace keeps its own four-value vocabulary
    (``alpha/models.py``): these are the states of a call as a *screen* and a
    checkpoint see it, and a projection is not a trace.
    """

    PENDING = "pending"
    RUNNING = "running"
    OK = "ok"
    ERROR = "error"
    DENIED = "denied"


#: The states a call is in while it is still somebody's responsibility.
#:
#: Named once, because three readers ask the same question: the context
#: constructor leaves an unsettled call out of the transcript entirely, the loop
#: settles what is left of them when a Turn ends, and the lifecycle settles the
#: same thing in a checkpoint it is about to freeze.
UNSETTLED_STATUSES = frozenset({ToolCallStatus.PENDING, ToolCallStatus.RUNNING})

#: What a call that never got to settle is recorded as.
#:
#: The honest reading of an interrupted call rather than a claim about the tool:
#: something ended the Turn — a restart, a deadline, a shutdown — while this call
#: was outstanding, and whether its effect landed is unknown. ``dispatched`` is
#: kept as it was, because that is the only fact anybody has about it.
CALL_INTERRUPTED = "interrupted"


#: How each tool is described on screen, and which one of its arguments may
#: appear beside the description.
#:
#: An allowlist of both halves rather than a rendering of the argument object,
#: for two reasons. The sentence is what the reader sees, and the interactive
#: surface renders it verbatim rather than composing one — so it has to read as
#: Vietnamese prose here or nowhere. And an argument nobody named is an argument
#: nobody reviewed for a screen: a tool added later shows its name and nothing
#: else until somebody decides what of it is fit to show.
MAX_SUMMARY_CHARS = 120

#: The hard ceiling on a whole rail row, for the tools that compose their own.
#: A row is one line in a narrow panel; past this it is truncated by the layout
#: anyway, and the cap is here so that is decided once rather than by whichever
#: tool wrote the longest sentence.
MAX_SUMMARY_ROW_CHARS = 200

# A deterministic approximation, and deliberately a pessimistic one. Vietnamese
# prose with diacritics tokenizes worse than English, and the ceiling this feeds
# is also enforced by admission, where the penalty for undercounting is a
# refused call in the middle of a Turn.
CHARS_PER_TOKEN = 3
# What the wire format costs per message beyond its text: role, delimiters, and
# the ids on a tool block.
MESSAGE_OVERHEAD_TOKENS = 4

SUMMARY_LABEL = "Summary of the earlier turns in this conversation:"

#: The eight things a constructed context is made of.
#:
#: Named rather than derived from the message list, because the question C2 asks
#: is *where did the tokens go*, and a role is not an answer to it: four of these
#: layers travel as ``system`` and three as ``user``. Each name is a thing
#: somebody can decide to spend less on.
#:
#: ``system_core`` is the prompt every Turn carries — the cacheable prefix.
#: ``domain_body`` is the active pack's playbook, whether it travels inside the
#: constructed context or is reserved for a message appended after it.
#: ``system_dynamic`` is everything else the harness says: the rendered date and
#: name, and the per-call notes the loop appends.
#: ``history`` is older Turns, and the summary standing in for the ones dropped.
#: ``user_intent`` is the newest question, in the reader's own words.
#: ``attachments`` is what they attached to it, text and pixels.
#: ``tool_results`` is this Turn's tool exchange.
SYSTEM_CORE = "system_core"
DOMAIN_BODY = "domain_body"
SYSTEM_DYNAMIC = "system_dynamic"
HISTORY = "history"
USER_INTENT = "user_intent"
ATTACHMENTS = "attachments"
TOOL_RESULTS = "tool_results"

CONTEXT_LAYERS = (
    SYSTEM_CORE,
    DOMAIN_BODY,
    SYSTEM_DYNAMIC,
    HISTORY,
    USER_INTENT,
    ATTACHMENTS,
    TOOL_RESULTS,
)


def _compact(payload: Mapping[str, Any]) -> str:
    """One deterministic encoding, so the same inputs give the same bytes."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )


def charged_text(message: Message) -> str:
    """Exactly the string :func:`estimate_tokens` charges this message for.

    Its own function because two readers need the same answer and only one of
    them is the estimate. The composition below attributes a message's tokens to
    the layers its text came from, and it can only do that if it is slicing the
    identical string — a second, nearly-identical concatenation here would make
    the layer breakdown add up to a number no request was ever charged.
    """
    text = message.content or ""
    for call in message.tool_calls:
        text += call.name + _compact(call.arguments)
    if message.tool_call_id:
        text += message.tool_call_id
    return text


def estimate_tokens(message: Message) -> int:
    """What one message is charged, deterministically.

    An image is charged what it declares, on top of the placeholder naming it in
    ``content``. The placeholder is how the string still narrates the whole
    prompt; it is not what the image costs. Left at the placeholder's length an
    image reads as about eleven tokens, and then everything that decides what
    fits — the climb-down in :func:`build_messages`, the pre-call ceilings, and
    the recovery ladder asking whether anything was given up — decides it on a
    number that is off by two orders of magnitude.

    A message carrying no images is charged exactly what it was charged before.
    """
    images = sum(image.estimated_tokens for image in message.images)
    return MESSAGE_OVERHEAD_TOKENS + _text_tokens(charged_text(message)) + images


def _text_tokens(text: str) -> int:
    """Characters to tokens, the one rounding rule this module has."""
    return -(-len(text) // CHARS_PER_TOKEN)


@dataclass(frozen=True)
class ContextComposition:
    """Where a request's input tokens went, by layer.

    Eight counters and a total, and the property that makes them worth having is
    that the total is not a ninth number: it is the sum, and it equals the
    estimate the request was reserved against. A breakdown that could disagree
    with the bill would be a diagnosis of a system nobody is running.

    Built by attribution rather than by re-measurement. Each message of the
    constructed context is charged once, and its charge is split between the
    layers its own text came from — see :func:`_attribute`. The split is exact
    by construction: the parts of a message's charged text are contiguous and
    cover all of it, and the rounding is applied to running prefixes so the
    pieces sum to the whole rather than to the whole plus two.
    """

    system_core: int = 0
    domain_body: int = 0
    system_dynamic: int = 0
    history: int = 0
    user_intent: int = 0
    attachments: int = 0
    tool_results: int = 0

    @property
    def total(self) -> int:
        return sum(getattr(self, layer) for layer in CONTEXT_LAYERS)

    def plus(self, **layers: int) -> ContextComposition:
        """The same composition with more tokens on the named layers.

        The loop appends messages after the context is constructed and reserves
        room for them; both halves land here, so the arithmetic that funds the
        call and the arithmetic that explains it are the same arithmetic.
        """
        unknown = set(layers) - set(CONTEXT_LAYERS)
        if unknown:
            raise ValueError(f"no such context layer: {sorted(unknown)}")
        return replace(
            self, **{name: getattr(self, name) + value for name, value in layers.items()}
        )

    def as_dict(self) -> dict[str, int]:
        """The breakdown as an ordered mapping, for an artifact or a report."""
        return {layer: getattr(self, layer) for layer in CONTEXT_LAYERS}


#: One message, and which layers its charge belongs to.
#:
#: ``parts`` are ``(layer, characters)`` in the order they appear in
#: :func:`charged_text`, and their lengths sum to that string's length. The
#: per-message overhead is charged to the first part, and any image tokens to
#: ``image_layer``.
@dataclass(frozen=True)
class _Tagged:
    message: Message
    parts: tuple[tuple[str, int], ...]
    image_layer: str = ATTACHMENTS


def _attribute(tagged: Sequence[_Tagged]) -> ContextComposition:
    """Split every message's charge across the layers its text came from."""
    totals: dict[str, int] = {layer: 0 for layer in CONTEXT_LAYERS}
    for piece in tagged:
        text = charged_text(piece.message)
        covered = sum(length for _, length in piece.parts)
        if covered != len(text):
            raise ValueError(
                "a tagged message's parts must cover its charged text exactly; "
                f"{covered} characters were tagged and {len(text)} were charged"
            )
        consumed = 0
        running = 0
        for layer, length in piece.parts:
            running += length
            upto = -(-running // CHARS_PER_TOKEN)
            totals[layer] += upto - consumed
            consumed = upto
        totals[piece.parts[0][0]] += MESSAGE_OVERHEAD_TOKENS
        images = sum(image.estimated_tokens for image in piece.message.images)
        if images:
            totals[piece.image_layer] += images
    return ContextComposition(**totals)



@dataclass(frozen=True)
class TurnToolCall:
    """One tool call of a Turn: what the model asked, and what came back.

    One type rather than two, and the reason is that a second one would drift.
    The same record answers three readers: the transcript the next round is
    constructed from, the ``tool.call`` payload the interactive surface renders,
    and the Tool Call Trace row. Splitting them means three places that can
    disagree about whether a call succeeded.

    ``result_text`` is the *whole* result as the tool returned it. What the model
    is shown is derived from it at construction time, because the per-Turn output
    budget can ask a result gathered three rounds ago to give ground now
    (``budget.py`` rung three) — so the trimmed form is never stored here.
    """

    id: str
    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    status: ToolCallStatus = ToolCallStatus.RUNNING
    result_text: str | None = None
    #: The same result, projected for the model, or ``None`` where the two are
    #: the same string.
    #:
    #: A second field rather than a narrower ``result_text``, because the two
    #: answer to different readers and only one of them may ever shrink. The
    #: Tool Call Trace is the audit record of what an answer rested on, and the
    #: invariant on it is that it holds exactly what the tool returned; the
    #: model's copy is what a Turn can afford to show, and by the end of a
    #: web-first Turn the same page has often already been shown by an earlier
    #: call. Trimming ``result_text`` to fit would edit the audit record to make
    #: the context cheaper, which is the trade this field exists to refuse.
    #:
    #: **It never goes on the wire.** :meth:`as_wire` does not carry it, and it
    #: is not a second public shape of a result: a surface reads ``results``,
    #: a reader reads the answer, and this is only what the next model call is
    #: given. ``None`` means "no projection was made", and every reader falls
    #: back to ``result_text`` — which is what every caller written before this
    #: field gets, unchanged.
    context_text: str | None = None
    #: A short user-facing line: the tool and the one argument worth naming.
    #: Never the result body, and never the reason it failed — that is ``error``,
    #: which travels beside it so a surface can say *why* without the summary
    #: having to be rewritten into an apology.
    summary: str = ""
    error: str | None = None
    #: The guardrail ladder's warning about this call, when it warned. Carried
    #: to the model *outside* the untrusted wrapper, because it is the harness
    #: talking and must not read as part of a page.
    guidance: str | None = None
    duration_ms: int = 0
    dispatched: bool = True
    #: Which round of the tool loop asked for this call, counting from zero.
    #:
    #: Carried so the surface can group a round's calls under one line — the
    #: model asks for several searches at once, and five rows that all appeared
    #: in the same instant read as five separate decisions rather than as the
    #: one decision it was. Grouping by arrival time would guess at that; the
    #: round is the fact.
    round: int = 0
    #: The part of this call's result that is fit to put on a screen.
    #:
    #: Distinct from ``result_text``, which is the whole result and belongs to
    #: the model and the trace. This is a short, already-flattened projection —
    #: title, link, source, one snippet — built by :func:`display_results` from
    #: text the web tools ran through ``visible_text`` and therefore stripped of
    #: markup. Empty for every tool that has nothing worth showing.
    results: tuple[Mapping[str, Any], ...] = ()
    #: The route's own opaque token for the reasoning behind this call, when the
    #: route issued one. Held for the length of the Turn and no longer: a route
    #: that demands it back demands it for the rounds of the Turn it is
    #: answering, and a closed Turn in the history is accepted without it.
    signature: str | None = None
    #: What the advisory threat scan made of this call's result.
    #:
    #: ``{"risk": ..., "findings": [...]}`` for a call that read outside content,
    #: ``None`` for everything else. Three risks, and the third one matters: a
    #: scan that could not finish says ``unknown`` rather than ``low``, because
    #: "we looked and found nothing" and "we did not look" are different facts.
    #:
    #: **It travels to the screen and never to the model.** A warning inside the
    #: text is a sentence the model has to interpret, and interpreting sentences
    #: from a page is the surface the attack is aimed at — so :func:`shown_result`
    #: does not read this and there is no path from here into a message. It is
    #: for the person, on the channel the person's browser reads, and it is
    #: carried in ``as_wire`` so a Thread reopened tomorrow still shows it.
    scan: Mapping[str, Any] | None = None
    #: Task-local declaration snapshot. It is deliberately absent from
    #: :meth:`as_wire`; reconnects have only the persisted public call and use
    #: the conservative registry fallback until typed lifecycle identity lands.
    resolved_tool: registry.ResolvedTool | None = field(
        default=None, repr=False, compare=False
    )

    @property
    def finished(self) -> bool:
        """Whether this call has a state nobody is waiting on any more.

        Read against :data:`UNSETTLED_STATUSES` rather than against ``running``
        alone: a ``pending`` call is an intent that has been written down and not
        yet answered, so a transcript built from it would hand the model half a
        tool exchange — the very thing ``completed_calls`` exists to prevent.
        """
        return self.status not in UNSETTLED_STATUSES

    @property
    def model_text(self) -> str:
        """What the model reads for this call: the projection, or the result.

        One accessor rather than the same ``or`` at four call sites, because a
        site that forgot it would quietly send the model the untrimmed result
        and the budget would be measuring a string nobody was given.
        """
        if self.context_text is not None:
            return self.context_text
        return self.result_text or ""

    @property
    def reads_external(self) -> bool:
        """Classify current calls from their snapshot, legacy calls conservatively."""
        if self.resolved_tool is not None:
            return self.resolved_tool.access is registry.ToolAccess.NETWORK
        return registry.accesses_network(self.name)

    def as_wire(self) -> dict[str, Any]:
        """The ``tool.call`` payload of the SSE contract, and nothing else.

        ``error`` is here because ``status`` alone cannot answer the question a
        reader actually has. Three of the reasons a call ends in ``error`` are
        not failures at all — the Turn spent its external-call allowance, the
        round asked for more calls than it may dispatch, the tool loop was
        halted — and every one of those was refused by this deployment before
        anything was dispatched. Sending only ``error`` as a status draws them
        exactly like a tool that broke, and only one of the two is worth
        retrying.

        The reason is a stable code, not a sentence: the surface owns the words,
        the same way it already owns the words for ``terminal_reason``.
        """
        return {
            "id": self.id,
            "name": self.name,
            "status": self.status.value,
            "summary": self.summary,
            "error": self.error,
            "round": self.round,
            "results": [dict(item) for item in self.results],
            "result_count": len(self.results),
            # Which kind of evidence this call went and got. Read off the same
            # declaration the untrusted wrapper reads, so a surface cannot draw a
            # read of this system's own store the way it draws a stranger's page
            # — the distinction the whole evidence boundary rests on. A name the
            # registry does not hold reads as external, conservatively, exactly
            # as it does for the wrapper.
            "kind": EXTERNAL_KIND if self.reads_external else STORE_KIND,
            # The advisory scan's verdict, on the payload that is persisted with
            # the Turn rather than in a column of its own. That choice is the
            # whole storage decision: this dictionary is already written to
            # ``agent_message.content`` when the answer commits, so the verdict
            # survives a reopened Thread and can be counted over a corpus
            # without a migration, without a second column on the hot trace
            # table, and without putting an advisory signal inside the trace's
            # own invariant — that ``result`` holds exactly what the model saw.
            "scan": dict(self.scan) if self.scan else None,
        }


def summarise_call(
    name: str,
    arguments: Mapping[str, Any],
    *,
    resolved: registry.ResolvedTool | None = None,
) -> str:
    """The one line a reader is shown about a tool call.

    The whole sentence, in the reader's language, because the interactive
    surface renders it verbatim: a client that described a call would be
    guessing at what it was for, and the guess is what the reader would
    believe.

    It says what was *asked*, and it never changes once the call has been
    announced. What came back is the call's status, which the surface shows
    beside it, and a failure code belongs in the trace rather than in a sentence
    somebody reads.

    **Built from the registration, not from a table here.** Every tool declares
    the phrase a person reads (``ToolEntry.display_name``) beside the name the
    model calls, and ``register`` refuses a blank one. This function used to keep
    its own mapping of five tool names, which is why the three tools added after
    it was written showed a reader a raw function name — the same defect, in the same
    shape, that ``untrusted.py`` had with its frozenset of two.

    A name the registry does not hold falls back to itself. That is a tool
    nobody registered, so there is no declared phrase to use and inventing one
    would be this function guessing; it happens in a process whose tool surface
    has not been installed, and a raw name there is a symptom worth seeing.
    """
    entry = resolved if resolved is not None else registry.get(name)
    if entry is None:
        return name
    if entry.summarise is not None:
        # A tool whose row cannot be built from one argument builds its own.
        return entry.summarise(arguments)[:MAX_SUMMARY_ROW_CHARS]
    if entry.summary_detail_arg is None:
        return entry.display_name
    value = arguments.get(entry.summary_detail_arg)
    detail = value.strip() if isinstance(value, str) else ""
    if not detail:
        return entry.display_name
    return f"{entry.display_name}: {detail[:MAX_SUMMARY_CHARS]}"


#: How much of one result's snippet is sent to a screen.
#:
#: Shorter than the ``MAX_SNIPPET_CHARS`` the model reads, because the two are
#: doing different jobs: the model reads a snippet to decide whether the page is
#: worth fetching, and the reader reads it to recognise a source they already
#: half-know. A card is two lines tall either way, so the rest of it would be
#: bytes on the wire that no layout has room for.
DISPLAY_SNIPPET_CHARS = 280

#: The most results one call may put on screen, whatever the tool returned.
#:
#: A ceiling on this side as well as on the tool's, so raising ``MAX_RESULTS``
#: to widen what the *model* reads cannot silently make every Turn's event
#: stream several times larger.
MAX_DISPLAY_RESULTS = 10


#: Query parameters that name a campaign rather than a page.
#:
#: Measured rather than guessed at: these are the keys a search provider hands
#: back attached to links whose page is identical without them. The list is
#: deliberately short and closed — a parameter this does not recognise is left
#: alone, because dropping one that *does* select content would merge two real
#: pages into one and silently hide evidence.
_TRACKING_PARAMS = frozenset(
    {
        "fbclid",
        "gclid",
        "igshid",
        "mc_cid",
        "mc_eid",
        "msclkid",
        "ref",
        "ref_src",
        "utm_campaign",
        "utm_content",
        "utm_id",
        "utm_medium",
        "utm_source",
        "utm_term",
        "yclid",
    }
)


def dedup_key(url: str, *, host: str = "") -> str:
    """What makes two links the same page, for comparison and nothing else.

    **The normalised form is never what gets fetched or shown.** It exists to
    answer one question — are these two results the same page — and a link is
    stored and clicked exactly as the provider gave it. That is a design
    constraint rather than a thing to discover later: stripping a parameter some
    site happens to route on would turn a working link into a 404 for the
    reader, and this function has no way to know which sites those are.

    Four reductions, each one a case where two strings name one page: the
    fragment is a position inside a document rather than a document; ``www.`` is
    a host prefix that resolves to the same server; a trailing slash on a path is
    the same path; and the parameters in :data:`_TRACKING_PARAMS` say where a
    visitor came from rather than what they are looking at. The scheme is
    dropped for the same reason — ``http`` and ``https`` are one page served two
    ways, and a provider returning both would otherwise read as two sources.

    A string that is not a link at all comes back empty, and the caller treats
    an empty key as no key: two results with no link are two results, because
    the alternative is one unusable key merging everything that lacks one.

    ``host`` is the hostname the backend already built — ``results[].source``,
    which ``tools/web.py`` derives once when it assembles the item. It is passed
    in rather than parsed again here so there is one derivation of a hostname in
    this system and not two that can come to disagree. Parsing is the fallback
    for a payload that carries no such field.
    """
    try:
        parts = urlsplit(url.strip())
    except ValueError:
        return ""
    host = (host.strip() or parts.hostname or "").lower().removeprefix("www.")
    if not host:
        return ""
    query = "&".join(
        sorted(
            f"{key}={value}"
            for key, value in parse_qsl(parts.query, keep_blank_values=True)
            if key.lower() not in _TRACKING_PARAMS
        )
    )
    port = f":{parts.port}" if parts.port not in (None, 80, 443) else ""
    path = parts.path.rstrip("/")
    return f"{host}{port}{path}?{query}" if query else f"{host}{port}{path}"


def _better(candidate: Mapping[str, Any], incumbent: Mapping[str, Any]) -> bool:
    """Whether ``candidate`` is the copy of a page worth keeping.

    The provider's own position first, because that is the one ordering it
    committed to; the publication date only breaks a tie. Both fields come off
    the search item the web tool builds, and a result carrying neither loses to
    one that arrived earlier — first seen is the stable answer when there is
    nothing to prefer.
    """
    ranks = (_rank_of(candidate), _rank_of(incumbent))
    if ranks[0] != ranks[1]:
        return ranks[0] < ranks[1]
    return str(candidate.get("published_at") or "") > str(
        incumbent.get("published_at") or ""
    )


def _rank_of(item: Mapping[str, Any]) -> int:
    value = item.get("rank")
    return int(value) if isinstance(value, int) and value > 0 else 1_000


def display_results(
    name: str, payload: Any, *, seen: set[str] | None = None
) -> tuple[Mapping[str, Any], ...]:
    """The part of one tool's result that may be put on a screen.

    Separate from ``result_text`` on purpose. ``result_text`` is the whole
    result: it belongs to the model, which is told to treat it as data, and to
    the Tool Call Trace, which nobody renders. What comes back from here is a
    short projection with four named fields and no body — the fields a reader
    needs to recognise a source and click it.

    Four properties make that projection safe to render, and all four are
    already true of what the web tools return rather than being asserted here:

    * the text has been through ``visible_text``, so it is the *visible* text of
      an HTML document with tags and scripts discarded, not markup;
    * every field is a string, flattened here, so no nested object from a
      provider reaches a component that would have to walk it;
    * the snippet is cut to :data:`DISPLAY_SNIPPET_CHARS` and the list to
      :data:`MAX_DISPLAY_RESULTS`, so one enormous answer cannot become one
      enormous frame;
    * the surface labels the whole block as outside content, which is where that
      label belongs — a wrapper *inside* the payload would be a string a page
      could forge.

    A tool with nothing worth showing returns nothing, which is the default: a
    tool added later shows a row and no results until somebody decides what of
    it is fit for a screen.

    **``seen`` makes the projection Turn-wide rather than call-wide**, and the
    scope is the whole reason it is a parameter. Two searches issued in one
    round routinely land on the same page — measured over a recorded run, 21 of
    223 links came back to more than one query — and without a set carried
    across the calls each of them draws that page again. Within a single
    provider response there is nothing to merge: the same run had **no** call
    return one link twice, so a deduplication scoped to one payload would be
    code that never runs, which is the one thing this plan refuses to ship.

    The caller owns the set because the Turn is what the set is about. Passing
    ``None`` asks the old question — what is in *this* payload — and is what a
    test or a one-off render wants.

    What is compared is :func:`dedup_key` and never the link itself. The link
    stored and clicked is the provider's, untouched.
    """
    if not isinstance(payload, Mapping):
        return ()
    if name == "web_search":
        raw = payload.get("results")
        if not isinstance(raw, Sequence) or isinstance(raw, str):
            return ()
        return _distinct(
            [item for item in raw if isinstance(item, Mapping)], seen=seen
        )
    if name == "fetch_url":
        # A page read is one result, and it is only worth a row once it has a
        # page: a refusal carries a ``reason`` and no title, and a card with an
        # empty heading tells the reader less than no card at all.
        if not payload.get("title") and not payload.get("url"):
            return ()
        return _distinct([payload], seen=seen)
    return ()


def _distinct(
    items: Sequence[Mapping[str, Any]], *, seen: set[str] | None
) -> tuple[Mapping[str, Any], ...]:
    """The results worth drawing, in the order they arrived, each page once.

    Two passes, and they are not the same question. The first collapses copies
    *inside* this payload, where the better copy wins — a page returned at rank
    two and again at rank five is one page, and the reader should be shown the
    provider's better placement of it. The second drops what the Turn has drawn
    already, where the *earlier* copy wins by having been drawn: retracting a
    source from a row that is already on screen would be a row rewriting itself.

    A result with no usable link keeps its place. It cannot be compared, and
    treating "no key" as a key would merge every such result into one.
    """
    best: dict[str, Mapping[str, Any]] = {}
    order: list[str | int] = []
    loose: dict[int, Mapping[str, Any]] = {}
    for position, item in enumerate(items):
        key = dedup_key(
            str(item.get("url") or ""), host=str(item.get("source") or "")
        )
        if not key:
            loose[position] = item
            order.append(position)
            continue
        if key not in best:
            best[key] = item
            order.append(key)
        elif _better(item, best[key]):
            best[key] = item

    kept: list[Mapping[str, Any]] = []
    for slot in order:
        # The ceiling is checked before the set is written, not after. Marking a
        # link as drawn and then dropping it for want of room would hide it from
        # every later call of the Turn as well, which is the one way this can
        # lose a source outright.
        if len(kept) >= MAX_DISPLAY_RESULTS:
            break
        if isinstance(slot, int):
            kept.append(_display_item(loose[slot]))
            continue
        if seen is not None:
            if slot in seen:
                continue
            seen.add(slot)
        kept.append(_display_item(best[slot]))
    return tuple(kept)


def _display_item(item: Mapping[str, Any]) -> Mapping[str, Any]:
    """One result flattened to the four strings a card is built from."""
    return {
        "title": _display_text(item.get("title"), 240),
        "url": _display_text(item.get("url"), 2048),
        "source": _display_text(item.get("source"), 120),
        "snippet": _display_text(item.get("snippet"), DISPLAY_SNIPPET_CHARS),
    }


def _display_text(value: Any, limit: int) -> str:
    """A single-line string of at most ``limit`` characters.

    Newlines collapse rather than survive: these strings are put in a card that
    is two lines tall, and a snippet carrying its own line breaks would either
    blow the card open or be silently clipped mid-paragraph.
    """
    if not isinstance(value, str):
        return ""
    return " ".join(value.split())[:limit]


#: How many of a collapsed call's links survive the collapse.
#:
#: A ceiling because rung two of the ladder fires precisely when the context is
#: already over its budget, and a fix that hands back an unbounded number of
#: tokens at that moment is not a fix. Five is the width of one search
#: (``tools/web.py``'s ``MAX_RESULTS``), so an ordinary search keeps all of its
#: links and only a page that returned more than a search does gives any up.
COLLAPSED_RESULT_URLS = 5


def context_projection(
    name: str, payload: Any, text: str, *, seen: set[str] | None = None
) -> str:
    """The result as the *model* reads it, with what it has already read removed.

    Built from the structured payload the executor is still holding rather than
    by parsing ``text`` back into objects. A second parse would be a second
    chance to read a provider's JSON differently from the first, and the two
    readings would diverge on exactly the payload nobody tested.

    One tool is projected and the rest pass through unchanged, and the asymmetry
    is measured rather than tidy:

    ``web_search`` returns a list of pages, and over a recorded run **21 of 223**
    links came back to more than one query while **no single call** returned a
    link twice. So the duplication is *between* calls, which is why ``seen`` is
    a Turn-wide set the caller owns — a deduplication scoped to one payload
    would be code that never runs.

    ``fetch_url`` is **not** deduplicated by URL, and that is the load-bearing
    exception. The same page fetched twice with two different ``looking_for``
    values returns two different passages, because the tool selects the passages
    that answer the question it was given. Dropping the second as a duplicate
    would throw away the evidence the second call was made to get, and the
    Turn's answer would be missing the half it went back for.

    What survives is the *identity* of what was dropped: the link is still in
    the earlier call's own result, and in the ``results`` projection the rail
    draws. Nothing that was ever cited stops being reachable.
    """
    if seen is None or name != "web_search" or not isinstance(payload, Mapping):
        return text
    raw = payload.get("results")
    if not isinstance(raw, Sequence) or isinstance(raw, str):
        return text

    kept: list[Any] = []
    dropped = 0
    for item in raw:
        if not isinstance(item, Mapping):
            kept.append(item)
            continue
        key = dedup_key(
            str(item.get("url") or ""), host=str(item.get("source") or "")
        )
        # No key is no comparison. A result with no usable link keeps its place,
        # because treating "no key" as a key would merge every such result into
        # one and hide all but the first.
        if not key:
            kept.append(item)
            continue
        if key in seen:
            dropped += 1
            continue
        seen.add(key)
        kept.append(item)

    if not dropped:
        # Nothing to say, and nothing to re-encode. Returning ``text`` keeps the
        # exact bytes the executor produced for the common case, so a projection
        # that changes nothing cannot change anything.
        return text
    return _compact({**payload, "results": kept})


#: What a collapsed call is called in the message the model reads.
#:
#: The words are chosen to say two true things and no third. The result *was*
#: recorded — the Tool Call Trace holds it in full, and an auditor reading the
#: Turn tomorrow can see what this call returned. And it is **not** something
#: the model can ask for back: there is no retrieval tool in this deployment,
#: and a sentence implying one would send the model looking for a call it cannot
#: make, spending a round to learn that.
TRACE_HANDLE_PREFIX = "earlier call, recorded in full and not repeated here:"


def _collapsed_result(call: TurnToolCall) -> str:
    """One collapsed call, as the model reads it after rung two of the ladder.

    What the collapse throws away is a whole page of prose, which is the point.
    What it must not throw away is the *identity* of what the call found, and
    that identity was in two places, only one of which survived.

    The arguments survived and always did: ``fetch_url``'s ``url`` and
    ``web_search``'s ``query`` are in the encoded argument object, so a model
    reading a collapsed line still knows what was asked. Rebuilding those here
    would be paying twice for one fact.

    The links the search *found* did not survive, and they are what an answer
    points at. A Turn whose early rounds have collapsed could still name a
    figure it read and no longer had any way to say where it came from — which
    is the one property this plan is about. So the links come back, and the
    titles and snippets do not: a link is what a claim is anchored to, and the
    prose is what the collapse was called to shed.

    What the line says about itself is :data:`TRACE_HANDLE_PREFIX`: the result
    was recorded and is not repeated. Said explicitly rather than left as a bare
    ``called ...``, because a model reading a line that only names a call has to
    guess whether the call failed, returned nothing, or returned something it is
    not being shown — and one of those three guesses turns a collapse into an
    answer that says the lookup did not work.
    """
    line = (
        f"{TRACE_HANDLE_PREFIX} {call.name} with arguments "
        f"{_compact(call.arguments)}"
    )
    links = [
        str(item.get("url") or "")
        for item in call.results[:COLLAPSED_RESULT_URLS]
        if str(item.get("url") or "")
    ]
    return f"{line}; results: {' '.join(links)}" if links else line


def shown_result(call: TurnToolCall) -> str:
    """What the model reads for one finished call, in the one place it is built.

    Two decisions live here rather than at the three call sites that would
    otherwise each need them. Outside content is wrapped and its delimiter
    defanged (``untrusted.py``) — at the message layer, because a prompt cannot
    enforce a wrapper and an attacker can forge a closing tag. And the
    guardrail's warning is appended *after* the wrapper closes, so a page cannot
    be mistaken for the harness or the harness for a page.
    """
    body = wrap_result(
        call.name,
        call.model_text,
        source=_source_of(call),
        resolved=call.resolved_tool,
    )
    if call.guidance:
        return f"{body}\n\n{call.guidance}" if body else call.guidance
    return body


def _source_of(call: TurnToolCall) -> str:
    """The label the untrusted wrapper names as the origin of this content."""
    for key in ("url", "query"):
        value = call.arguments.get(key)
        if isinstance(value, str) and value.strip():
            return value.strip()
    return call.name


#: How much uploaded file text one Turn may put in front of the model.
#:
#: Deliberately the same value as ``turns.MAX_USER_INPUT_BYTES``, and written
#: again rather than imported because ``turns`` imports ``loop`` which imports
#: this module — the cycle is the only reason there are two names. A test pins
#: them equal so they cannot drift apart into two different policies.
#:
#: The value is the same because the question is the same one: how much prose a
#: single Turn may set in front of the model as the reader's own words. A file
#: the reader chose is their words as much as the message they typed, so it gets
#: the same allowance and not a larger one derived from the image budget — that
#: budget is measured in pixels and has nothing to say about how much text a
#: model should read before answering.
MAX_ATTACHMENT_TEXT_BYTES = 8 * 1024

#: What a truncated file says about itself, inside its own wrapper. A file cut
#: silently is a file the model reads as complete, and a conclusion drawn from
#: the half it saw would be stated with the confidence of the whole.
TRUNCATION_NOTE = "… [tệp bị cắt ở đây vì vượt trần nội dung của một lượt]"


@dataclass(frozen=True)
class TurnAttachment:
    """One thing a reader attached, as the context constructor sees it.

    Metadata always; payload only sometimes. That split is the whole shape of
    this type: a Turn read back out of the store carries what is needed to
    *name* the attachment — so the placeholder in the message still narrates the
    prompt and the surface can draw a chip — while the bytes are loaded for the
    newest Turn alone. Carrying every earlier Turn's pixels would send n images
    on the n-th question of a Thread.
    """

    id: uuid.UUID
    filename: str
    media_type: str
    byte_size: int
    #: An image's own token cost, from ``attachments.image_tokens_for``. ``None``
    #: for a text file, whose cost is the characters it contributes to
    #: ``content`` and is therefore already counted by :func:`estimate_tokens`.
    estimated_tokens: int | None = None
    #: Base64 image data, when this Turn is the newest one. ``None`` otherwise.
    data: str | None = None
    #: Decoded file text, when this Turn is the newest one. ``None`` otherwise.
    text: str | None = None

    @classmethod
    def from_payload(cls, entry: Mapping[str, Any]) -> TurnAttachment:
        """Rebuild the metadata half from what the request committed.

        Metadata only, by construction: there is no field here for bytes, so a
        Turn read back out of the store cannot accidentally resend an image.
        That is the ceiling holding, not an omission — see ``history_of``.
        """
        return cls(
            id=uuid.UUID(str(entry["id"])),
            filename=str(entry.get("filename") or ""),
            media_type=str(entry.get("media_type") or ""),
            byte_size=int(entry.get("byte_size") or 0),
            estimated_tokens=(
                int(entry["estimated_tokens"])
                if entry.get("estimated_tokens")
                else None
            ),
        )

    def as_metadata(self) -> dict[str, Any]:
        """What gets committed beside the question. Never the payload."""
        entry: dict[str, Any] = {
            "id": str(self.id),
            "filename": self.filename,
            "media_type": self.media_type,
            "byte_size": self.byte_size,
        }
        if self.estimated_tokens:
            entry["estimated_tokens"] = self.estimated_tokens
        return entry

    @property
    def is_image(self) -> bool:
        return self.media_type.startswith("image/")

    @property
    def placeholder(self) -> str:
        """The text standing for this attachment inside the message.

        Present for every Turn, newest or not, because it is what makes the
        string a ledger measures describe the whole prompt the route reads — and
        because a model that can no longer see an earlier image must at least
        know that there was one rather than answer as though nothing was sent.
        """
        kind = "ảnh" if self.is_image else "tệp"
        return f"[{kind}: {self.filename}]"


@dataclass(frozen=True)
class TranscriptTurn:
    """One user message and everything that answered it."""

    user_text: str
    tool_calls: tuple[TurnToolCall, ...] = ()
    assistant_text: str | None = None
    #: What the reader attached to this question. Frozen, so a tuple.
    attachments: tuple[TurnAttachment, ...] = ()
    #: The names of the tools this Turn called, and nothing else about them.
    #:
    #: A second field rather than a thinner ``tool_calls``, because the two are
    #: read by different things for different reasons. ``tool_calls`` is the
    #: exchange the model is shown again, and a Turn reconstructed from the
    #: store never has it: the constructor trims older Turns to their prose, so
    #: rehydrating a full call — arguments, result, status — would put every
    #: earlier tool result back into every later request. What survives in the
    #: transcript row is the list of names, and a *name* is enough to answer the
    #: one question a later Turn asks of an earlier one: did this thread already
    #: reach for the domain.
    #:
    #: Nothing in :func:`build_messages` reads this. That is the point, and a
    #: test holds it: a field the constructor consulted would be a field that
    #: changed what the model sees, which is exactly what leaving ``tool_calls``
    #: empty was protecting.
    tool_names: tuple[str, ...] = ()

    @property
    def completed_calls(self) -> tuple[TurnToolCall, ...]:
        """Only the finished ones.

        A call still running is left out of the constructed context entirely —
        both halves of it — because half a tool exchange is a transcript the
        model has to guess at, and most routes reject it outright.
        """
        return tuple(call for call in self.tool_calls if call.finished)


@dataclass(frozen=True)
class Transcript:
    """Everything the constructor is allowed to see.

    A snapshot, already read from the store by the caller. Reading it here would
    put a database session inside the one function whose value is having none.
    """

    system_prompt: str
    #: Where the stable part of ``system_prompt`` ends, when the caller knows.
    #: Only a caller holding ``prompt.prefix()`` can say which part is which, so
    #: the boundary arrives here rather than being guessed at by string surgery.
    #: ``None`` means the whole prompt travels as one block.
    system_prefix: str | None = None
    #: The active domain pack's playbook, when this Turn has earned it.
    #:
    #: It travels *inside* the system message, between the core and the values
    #: rendered for this Turn, and that position is the whole point. A pack body
    #: appended at the tail is read after every tool result and is paid for in
    #: full on every call; the same prose here sits in the cacheable head, so a
    #: route with an automatic prefix cache reads it back from the second call
    #: of the Turn onward instead of re-sending it.
    #:
    #: Two blocks and not one string, because they go stale on different clocks:
    #: the core changes when the prompt is edited, and the body changes when the
    #: domain is swapped. A cache keyed on their concatenation would void the
    #: core every time a pack moved.
    #:
    #: ``None`` is the ordinary case — most Turns never touch the domain — and
    #: it produces byte-for-byte the message this built before packs existed.
    system_body: str | None = None
    turns: tuple[TranscriptTurn, ...] = ()
    #: Whether the route this context is being built for can read images.
    #:
    #: A snapshot fact, arriving with the snapshot, for the same reason
    #: ``system_prefix`` does: only the caller holds the ``LLMRoute``, and
    #: :func:`build_messages` reading configuration would make its purity a
    #: claim about the environment rather than about the function. ``False`` by
    #: default, so every caller written before images existed builds exactly the
    #: context it built before — and so a route that was never measured for
    #: vision does not get sent pixels on the strength of a default.
    vision: bool = False
    # The cached summary, and how many leading Turns it covers. Both come from
    # persistence together; a summary whose span is unknown could only be
    # applied by guessing.
    summary: str | None = None
    summarised_turns: int = 0


@dataclass(frozen=True)
class ContextBudget:
    """The ceiling the constructor exists to meet, and how it gives ground."""

    max_tokens: int = TURN_CONTEXT_PER_CALL
    # Never dropped, and their tool results collapse last.
    keep_intact_turns: int = 2
    # Past this many live Turns, a summary is worth its call.
    summary_threshold_turns: int = 8


@dataclass(frozen=True)
class ConstructedContext:
    """The message list, and what it cost to fit.

    The counters are returned rather than logged because the caller has to act
    on one of them: ``summary_needed`` is the rung-3 trigger, and a function
    that stayed pure by hiding it would just move the decision somewhere
    untestable.
    """

    messages: tuple[Message, ...]
    estimated_tokens: int
    summary_used: bool = False
    summary_needed: bool = False
    turns_dropped: int = 0
    results_collapsed: int = 0
    #: Where those tokens went. ``composition.total`` is ``estimated_tokens``,
    #: and the equality is not a coincidence to be checked but the definition:
    #: the estimate is the sum of the layers. A test pins it for every rung of
    #: the ladder, because a breakdown that drifts from the bill is a diagnosis
    #: of a system nobody is running.
    composition: ContextComposition = field(default_factory=ContextComposition)


class ConstructedContextTooLarge(ValueError):
    """Even the protected Turns, fully collapsed, break the ceiling.

    Raised rather than trimmed past the ladder's last rung. Returning an
    over-budget context would hand admission a call it must refuse mid-Turn, and
    returning a silently mangled one is the failure this constructor exists to
    prevent.
    """

    def __init__(self, estimated_tokens: int, budget: int) -> None:
        super().__init__(
            f"the smallest constructible context is {estimated_tokens} tokens "
            f"against a ceiling of {budget}"
        )
        self.estimated_tokens = estimated_tokens
        self.budget = budget


#: What separates two blocks of the system message. The same blank line the
#: prompt already puts between its own sections, so a reader — and a model —
#: sees one document rather than three concatenated ones.
_BLOCK_SEPARATOR = "\n\n"


def _system_message(transcript: Transcript) -> _Tagged:
    """The system message: core, then the pack's body, then this Turn's values.

    Three blocks in one message, in the order of how often each changes. The
    core is identical for every Turn of every reader. The body is identical for
    every Turn under one pack. The rendered values change daily. A route with a
    prefix cache reads back everything up to the first byte that differs, so
    that order is the difference between caching five thousand tokens and
    caching none.

    The segments describe the same string the message already holds —
    ``Message`` refuses any other arrangement — so a route that does not speak
    ``cache_control`` sees exactly one prompt, and the token estimate is the
    same either way.

    The boundary between blocks is the caller's, never this function's.
    ``system_prefix`` is where the core ends because only a caller holding
    ``prompt.prefix()`` can say so; a boundary found here by string surgery
    would move the moment somebody edited the prompt's last section.

    With no declared boundary the whole prompt is the core and a body follows
    it, which is what every caller written before packs existed already gets.
    """
    prompt = transcript.system_prompt
    stable = transcript.system_prefix
    body = transcript.system_body
    declared = bool(stable) and prompt.startswith(stable or "") and len(
        stable or ""
    ) < len(prompt)

    core = stable if declared else prompt
    runtime = prompt[len(core) :] if declared else ""

    blocks: list[tuple[str, str, bool]] = [(SYSTEM_CORE, core, True)]
    if body:
        blocks.append((DOMAIN_BODY, _BLOCK_SEPARATOR + body, True))
    if runtime:
        blocks.append((SYSTEM_DYNAMIC, runtime, False))

    content = "".join(text for _, text, _ in blocks)
    if len(blocks) == 1:
        # One block is not a boundary. Left without segments, so a message with
        # nothing to say about caching is byte-identical to what it always was.
        return _Tagged(
            Message(role=Role.SYSTEM, content=content),
            ((SYSTEM_CORE, len(content)),),
        )
    return _Tagged(
        Message(
            role=Role.SYSTEM,
            content=content,
            segments=tuple(
                ContentSegment(text, cache_breakpoint=breakpoint)
                for _, text, breakpoint in blocks
            ),
        ),
        tuple((layer, len(text)) for layer, text, _ in blocks),
    )


def _attachment_block(
    attachments: Sequence[TurnAttachment], *, latest: bool, vision: bool
) -> tuple[str, tuple[ImageContent, ...]]:
    """The text an attachment contributes, and the image parts it becomes.

    Two rules, and both are properties of *this* Turn's place in the snapshot
    rather than of anything read at call time.

    A placeholder for every attachment of every Turn: that is what keeps the
    message's own string a description of the whole prompt.

    Payload for the newest Turn only. An image becomes a content part here and
    nowhere else; a file's text is wrapped by
    :func:`untrusted.wrap_attachment` here and nowhere else, which is what makes
    that wrapper impossible to bypass — there is one place uploaded content
    enters a message, and it is this function.
    """
    lines: list[str] = []
    images: list[ImageContent] = []
    remaining = MAX_ATTACHMENT_TEXT_BYTES
    for attachment in attachments:
        lines.append(attachment.placeholder)
        if not latest:
            continue
        if attachment.is_image:
            # The placeholder above went out regardless, and on a route that
            # cannot read images that placeholder is the whole of what travels:
            # the model is told a picture was attached and can say it cannot see
            # it, which is the honest answer. Sending the bytes to a route
            # measured not to read them would spend the tokens for nothing.
            if vision and attachment.data is not None:
                images.append(
                    ImageContent(
                        media_type=attachment.media_type,
                        data=attachment.data,
                        placeholder=attachment.placeholder,
                        **(
                            {"estimated_tokens": attachment.estimated_tokens}
                            if attachment.estimated_tokens
                            else {}
                        ),
                    )
                )
            continue
        if attachment.text is None or remaining <= 0:
            continue
        body = attachment.text
        encoded = body.encode("utf-8")
        if len(encoded) > remaining:
            # Cut on a character boundary, then say so. ``errors="ignore"``
            # drops the partial sequence a byte slice can end in.
            body = encoded[:remaining].decode("utf-8", errors="ignore") + TRUNCATION_NOTE
        # What was actually spent, so the budget reads as a budget. The note
        # itself is not charged against it: it is the harness's own sentence
        # about the file, not any of the file's content.
        remaining -= min(len(encoded), remaining)
        lines.append(wrap_attachment(body, filename=attachment.filename))
    return "\n".join(lines), tuple(images)


def _user_message(
    turn: TranscriptTurn, *, latest: bool, vision: bool, intent_layer: str
) -> _Tagged:
    """The reader's own words, and whatever they attached to them.

    ``intent_layer`` is where the words themselves are charged — the newest
    question is :data:`USER_INTENT` and an older one is :data:`HISTORY` — while
    the attachment block is always :data:`ATTACHMENTS`, in either Turn. Passed
    in for the reason ``latest`` is: a message cannot see its own place in the
    tuple it came from, and reading it here would make this function's answer
    depend on something other than its arguments.
    """
    if not turn.attachments:
        return _Tagged(
            Message(role=Role.USER, content=turn.user_text),
            ((intent_layer, len(turn.user_text)),),
        )
    block, images = _attachment_block(turn.attachments, latest=latest, vision=vision)
    content = f"{turn.user_text}\n\n{block}" if block else turn.user_text
    return _Tagged(
        Message(role=Role.USER, content=content, images=images),
        (
            (intent_layer, len(turn.user_text)),
            (ATTACHMENTS, len(content) - len(turn.user_text)),
        ),
    )


def _result_layer(call: TurnToolCall) -> str:
    """Charge every current tool result to the tool-result layer."""
    return TOOL_RESULTS


def _turn_messages(
    turn: TranscriptTurn,
    collapsed: frozenset[str],
    *,
    latest: bool = False,
    vision: bool = False,
) -> tuple[_Tagged, ...]:
    """One whole Turn, with its call/result pairs kept together.

    ``latest`` says whether this is the newest Turn of the snapshot it came
    from. It is passed in rather than read anywhere, which is what keeps
    :func:`build_messages` pure: the same transcript still gives the same list,
    because "newest" is a fact about the tuple and not about the clock.

    It also decides which layer this Turn's prose is charged to. The newest
    Turn is the question being answered; every older one is history, and so is
    the answer this Turn eventually gives — an assistant message is only ever
    read again by a later Turn.
    """
    intent_layer = USER_INTENT if latest else HISTORY
    messages: list[_Tagged] = [
        _user_message(turn, latest=latest, vision=vision, intent_layer=intent_layer)
    ]
    calls = turn.completed_calls
    if calls:
        ask = Message(
            role=Role.ASSISTANT,
            tool_calls=tuple(
                ToolCall(
                    id=call.id,
                    name=call.name,
                    arguments=dict(call.arguments),
                    output_index=index,
                    signature=call.signature,
                )
                for index, call in enumerate(calls)
            ),
        )
        # The request for the calls is charged call by call, where each call's
        # own result is charged. An older Turn's exchange is history whatever
        # tool made it: the layer answers "can this be pruned", and a finished
        # Turn's results can be, while this Turn's are the evidence the answer
        # is standing on. Per call rather than per message because a round that
        # mixed external and local calls would otherwise put every ask on the
        # page layer, and the layer names would stop meaning what they say.
        messages.append(
            _Tagged(
                ask,
                tuple(
                    (
                        _result_layer(call) if latest else HISTORY,
                        len(inner.name) + len(_compact(inner.arguments)),
                    )
                    for call, inner in zip(calls, ask.tool_calls, strict=True)
                ),
            )
        )
        for call in calls:
            if call.id in collapsed:
                body = _collapsed_result(call)
            else:
                body = shown_result(call)
            result = Message(
                role=Role.TOOL,
                content=body,
                tool_call_id=call.id,
                name=call.name,
            )
            layer = _result_layer(call) if latest else HISTORY
            messages.append(
                _Tagged(result, ((layer, len(charged_text(result))),))
            )
    if turn.assistant_text:
        answered = Message(role=Role.ASSISTANT, content=turn.assistant_text)
        messages.append(_Tagged(answered, ((HISTORY, len(turn.assistant_text)),)))
    return tuple(messages)


def _render_messages(
    transcript: Transcript,
    turns: Sequence[TranscriptTurn],
    dropped: int,
    collapsed: frozenset[str],
) -> tuple[_Tagged, ...]:
    """Assemble one candidate context.

    The system prompt is one message and the summary is another. Folding the
    summary into the prompt would put conversation content inside the artifact
    whose whole property is that conversation content cannot enter it — and it
    would move the cacheable prefix once per Turn.

    The summary travels as a ``system`` message and is charged to
    :data:`HISTORY`, because a role is not a layer: it is the Turns it replaced,
    rewritten, and it is spent on for exactly the reason they were.
    """
    messages: list[_Tagged] = [_system_message(transcript)]
    if transcript.summary:
        summarised = Message(
            role=Role.SYSTEM,
            content=f"{SUMMARY_LABEL}\n{transcript.summary}",
        )
        messages.append(
            _Tagged(summarised, ((HISTORY, len(charged_text(summarised))),))
        )
    shown = turns[dropped:]
    last = len(shown) - 1
    for index, turn in enumerate(shown):
        messages.extend(
            _turn_messages(
                turn, collapsed, latest=index == last, vision=transcript.vision
            )
        )
    return tuple(messages)


#: Tools whose result is a way of *choosing* what to read, not the reading.
#:
#: One name, and the prompt already says why it is this one. §5 of the system
#: prompt tells the model in as many words that a search snippet is an indicator
#: of which page is worth opening and **not** evidence — so once the Turn has
#: moved on, the snippets have done the only job they had, and what is worth
#: keeping is which pages the search found. That is exactly what the handle
#: keeps: the query, and up to :data:`COLLAPSED_RESULT_URLS` links.
#:
#: ``fetch_url`` is deliberately absent. A fetched passage *is* the evidence,
#: and it stays in full for :data:`RESULT_CALLS`.
_SELECTION_TOOLS = frozenset({"web_search"})

#: For how many model calls a selection result stays in the context in full.
#:
#: Counted from the call that *reads* it, which is the only counting that makes
#: sense here: a result returned in round *r* is first read by the call that
#: closes round *r*, and that call is age one. So one means "read once" and
#: never means "collapsed before anybody looked" — the distinction is the whole
#: correctness of this rung, and a test holds it.
#:
#: One, because the call that reads a page of search results is the call that
#: decides what to fetch. By the next call that decision has been made, acted
#: on, and the pages are in the context in full.
SELECTION_CALLS = 1

#: For how many model calls any other result stays in the context in full.
#:
#: Two, on the same clock. A page fetched in round one is read by the call that
#: closes round one and by the call after it; a Turn still quoting it three
#: calls later is answering from something it has not looked at in a while, and
#: the handle still names the page it came from.
#:
#: Both numbers were read off a measured distribution rather than picked, and
#: the distribution says something the plan they came from did not know. Over
#: the twenty-case golden corpus this pair takes constructed tokens down
#: **13.8%** with **no source URL lost**. The most aggressive honest policy —
#: every result a handle after the single call that read it — reaches **17.8%**,
#: and that is the ceiling: the system prompt is **53.3%** of a context and no
#: amount of pruning touches it, so a 20% total cut would need 46% of every tool
#: result to go, which is more than there is. Deduplication alone, which loses
#: nothing whatsoever, is **1.1%**.
RESULT_CALLS = 2


def aged_results(turn: TranscriptTurn) -> frozenset[str]:
    """The calls of one Turn whose full text has outlived its usefulness.

    Deterministic, and computed before anything is measured — this is not a rung
    of the recovery ladder but the state the ladder starts from. A context that
    fits is still built without prose the answer stopped reading two calls ago,
    because the alternative is paying for it on every remaining call of the Turn
    and only noticing at the ceiling.

    Which call the Turn is on is read off the Turn rather than passed in: the
    constructor is shown exactly the calls of rounds before the current one, so
    the highest round present plus one *is* the call being built. That keeps
    :func:`build_messages` a pure function of its transcript, and it means a
    caller cannot get the ageing wrong by miscounting.

    Only this Turn's calls. An older Turn's results are older than any of these,
    but their round numbers count from that Turn's own zero — comparing them
    would be comparing two clocks — and the ladder already drops whole older
    Turns before it reaches anything here.
    """
    calls = turn.completed_calls
    if not calls:
        return frozenset()
    now = max(call.round for call in calls) + 1
    return frozenset(
        call.id
        for call in calls
        if (now - call.round)
        > (SELECTION_CALLS if call.name in _SELECTION_TOOLS else RESULT_CALLS)
    )


def _reductions(
    turns: Sequence[TranscriptTurn], budget: ContextBudget
) -> Iterator[tuple[int, frozenset[str]]]:
    """The ladder, as an ordered sequence of ``(turns dropped, collapsed)``.

    Rungs two and three interleave in one place the description does not spell
    out. A single Turn can outgrow the ceiling on its own — four rounds of
    parallel calls, each result up to its own cap — so the collapse is ordered
    by tool call, oldest first, and reaches inside the most recent Turn only
    after every older Turn has already been dropped. Ordering it by Turn instead
    would leave the one case that actually blows the budget with nothing left to
    give.
    """
    protected = max(1, budget.keep_intact_turns)
    older = turns[: max(0, len(turns) - protected)]
    recent = turns[len(older) :]

    older_ids = [call.id for turn in older for call in turn.completed_calls]
    recent_ids = [call.id for turn in recent for call in turn.completed_calls]

    # 1. Everything intact.
    yield 0, frozenset()

    # 2. Old tool results collapse to one line, oldest first.
    for taken in range(1, len(older_ids) + 1):
        yield 0, frozenset(older_ids[:taken])

    all_older = frozenset(older_ids)

    # 3. Whole Turns leave, oldest first; the protected ones never do.
    for dropped in range(1, len(older) + 1):
        yield dropped, all_older

    # 4. Last resort: the protected Turns' own results collapse, oldest first.
    for taken in range(1, len(recent_ids) + 1):
        yield len(older), all_older | frozenset(recent_ids[:taken])


def build_messages(
    transcript: Transcript, budget: ContextBudget | None = None
) -> ConstructedContext:
    """Construct one call's messages under the constructed-context ceiling.

    Pure: the same transcript and the same budget give the same list, every
    time. The ceiling is met here and nowhere else, which is why the ladder is
    exhaustive rather than best-effort.
    """
    budget = budget or ContextBudget()
    # A summary without a span could only be applied by guessing which Turns it
    # replaced, so an unaccompanied span is ignored rather than trusted.
    covered = transcript.summarised_turns if transcript.summary else 0
    live = tuple(transcript.turns[covered:])

    # What the newest Turn has stopped reading. Applied to every rung rather
    # than being one of them: it is not a concession made under pressure, it is
    # the shape of a context that has not been paying for the same page four
    # times.
    aged = aged_results(live[-1]) if live else frozenset()

    smallest = 0
    for dropped, collapsed in _reductions(live, budget):
        collapsed = collapsed | aged
        tagged = _render_messages(transcript, live, dropped, collapsed)
        messages = tuple(piece.message for piece in tagged)
        tokens = sum(estimate_tokens(message) for message in messages)
        smallest = tokens
        if tokens <= budget.max_tokens:
            return ConstructedContext(
                messages=messages,
                estimated_tokens=tokens,
                summary_used=transcript.summary is not None,
                summary_needed=(
                    dropped > 0 or len(live) > budget.summary_threshold_turns
                ),
                turns_dropped=dropped,
                results_collapsed=len(collapsed),
                composition=_attribute(tagged),
            )

    raise ConstructedContextTooLarge(smallest, budget.max_tokens)


__all__ = [
    "ANSWER",
    "ATTACHMENTS",
    "CALL_INTERRUPTED",
    "CHARS_PER_TOKEN",
    "COLLAPSED_RESULT_URLS",
    "CONTEXT_LAYERS",
    "DOMAIN_BODY",
    "HISTORY",
    "SYSTEM_CORE",
    "SYSTEM_DYNAMIC",
    "TOOL_RESULTS",
    "USER_INTENT",
    "ContextComposition",
    "charged_text",
    "DISPLAY_SNIPPET_CHARS",
    "MAX_DISPLAY_RESULTS",
    "MAX_SUMMARY_CHARS",
    "MESSAGE_OVERHEAD_TOKENS",
    "SUMMARY_LABEL",
    "THOUGHT",
    "UNSETTLED_STATUSES",
    "ConstructedContext",
    "ConstructedContextTooLarge",
    "ContextBudget",
    "ToolCallStatus",
    "Transcript",
    "TranscriptTurn",
    "TurnAttachment",
    "TurnToolCall",
    "RESULT_CALLS",
    "SELECTION_CALLS",
    "TRACE_HANDLE_PREFIX",
    "aged_results",
    "build_messages",
    "context_projection",
    "dedup_key",
    "display_results",
    "estimate_tokens",
    "shown_result",
    "summarise_call",
]
