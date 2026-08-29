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
from dataclasses import dataclass, field
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
    """The three states the interactive surface renders a tool call in."""

    RUNNING = "running"
    OK = "ok"
    ERROR = "error"


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


def _compact(payload: Mapping[str, Any]) -> str:
    """One deterministic encoding, so the same inputs give the same bytes."""
    return json.dumps(
        payload,
        ensure_ascii=False,
        separators=(",", ":"),
        sort_keys=True,
        default=str,
    )


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
    #: What this call actually yielded, for the calls where "it ran" and "it
    #: answered" are different facts.
    #:
    #: ``status`` cannot carry this. A store read that comes back saying the
    #: store has nothing to say is a successful call — the tool worked, the
    #: question was well formed, and the answer is that there is no figure — so
    #: it is ``ok``, and it was drawn and recorded exactly like a call that
    #: returned a number. Measured over the trace: of 151 ``get_field`` calls,
    #: 94 carried a figure, 42 carried a refusal and 15 said the symbol was
    #: outside the Universe, and all 151 were stored as ``ok``. That is a third
    #: of the evidence path invisible to anyone reading either the rail or the
    #: table.
    #:
    #: ``None`` for every tool with nothing to classify, which is the default: a
    #: tool added later says nothing here until somebody decides what its
    #: outcomes are.
    outcome: str | None = None
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
        return self.status is not ToolCallStatus.RUNNING

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
            "outcome": self.outcome,
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
    it was written showed a reader ``get_field`` — the same defect, in the same
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


#: What a call yielded, where that is a different question from whether it ran.
#:
#: Three values, and the middle one is the one this exists for. Kept short and
#: stable because they are stored in a column and grouped by in a query, and
#: because a surface holds one sentence per value the way it already does for a
#: **Signal Issue**.
OUTCOME_VALUE = "value"
OUTCOME_NO_VALUE = "no_value"
OUTCOME_CANNOT_READ = "cannot_read"

#: Every tool whose result carries a figure that may be absent. Named rather
#: than sniffed from the payload shape: a tool answering with a ``value`` key
#: that is legitimately null would otherwise be reported as having refused.
_FIGURE_TOOLS = frozenset({"get_field"})

#: Every tool that answers with a whole picture rather than one figure.
#:
#: Named for the same reason and classified apart, because the two say "nothing
#: this time" differently: a figure is a ``value`` that came back null, and a
#: Study is a refusal carrying the input that was short. Folding them together
#: would mean sniffing for whichever key happened to be present, which is the
#: guess this table exists to avoid.
_STUDY_TOOLS = frozenset({"run_study", "render_signal_desk"})


def outcome_of(name: str, payload: Any) -> str | None:
    """What one call yielded, or ``None`` where the question does not apply.

    Read off the structured payload rather than the result text, for the reason
    :func:`display_results` is: the executor is holding the object, and a second
    parse is a second chance to read it differently from the first.

    A Study answers the same three ways for the same reasons: an ``artifactId``
    is a picture that exists, an ``issue`` is the input that was too short, and
    an ``error`` is the question itself being declined.

    A refusal keeps the **Signal Issue** that caused it, not a flat "nothing".
    The whole value of separating these is that ``insufficient_cross_section``
    and ``market_cap_absent`` are different operational facts with different
    fixes, and folding them into one word rebuilds the blind spot one level up.
    """
    if not isinstance(payload, Mapping):
        return None
    if name in _STUDY_TOOLS:
        if payload.get("error"):
            return OUTCOME_CANNOT_READ
        if payload.get("artifactId"):
            return OUTCOME_VALUE
        issue = payload.get("issue")
        return f"{OUTCOME_NO_VALUE}:{issue}" if issue else OUTCOME_NO_VALUE
    if name not in _FIGURE_TOOLS:
        return None
    if payload.get("error"):
        # The tool declined the question itself — a symbol outside the Universe,
        # a call opened for another one. It never reached the store.
        return OUTCOME_CANNOT_READ
    if "value" not in payload:
        return None
    if payload.get("value") is not None:
        return OUTCOME_VALUE
    code = payload.get("reasonCode")
    return f"{OUTCOME_NO_VALUE}:{code}" if code else OUTCOME_NO_VALUE


#: The one thing a Signal Desk absence can be that nothing already names.
#:
#: Every other reason a Turn drew nothing is a code that exists: the Signal
#: Issue a Study refused under (:data:`OUTCOME_NO_VALUE` and the issue),
#: :data:`OUTCOME_CANNOT_READ` for a Study that declined the question, and the
#: executor's own error code for a call that never ran. This one has no home
#: among them because it is not a fact about the data at all — the model simply
#: never reached for a picture — and inventing a Signal Issue to say so would
#: put a claim about the store on a Turn that never asked it anything.
NO_SIGNAL_DESK_TOOL_CALLED = "no_signal_desk_tool_called"


def signal_desk_absence(calls: Sequence[TurnToolCall]) -> str:
    """Why this Turn drew nothing, in the vocabulary its calls already wrote.

    Read off :attr:`TurnToolCall.outcome`, which the loop already computed with
    :func:`outcome_of` at the moment the payload was in hand. Deriving it a
    second time from the result text would be a second chance to read the same
    call differently, and the whole value of a named reason is that the surface
    and the trace agree about it.

    The *last* signal_desk-producing call decides, because a Turn that tried twice
    gave up on the second one: reporting the first would tell the reader about
    an attempt the model had already moved past.

    Never ``None``. This is called only where a Turn owes an account of itself,
    and a caller handed nothing would have to invent a sentence — which is the
    silence the account exists to prevent.
    """
    attempts = [call for call in calls if call.name in _STUDY_TOOLS]
    if not attempts:
        return NO_SIGNAL_DESK_TOOL_CALLED
    last = attempts[-1]
    if last.outcome:
        # ``no_value:<signal issue>`` or ``cannot_read``. ``value`` cannot reach
        # here: a call that carried an ``artifactId`` produced a signal_desk.
        return last.outcome
    if last.error:
        # The call never got as far as an outcome — it was blocked, it timed
        # out, the budget refused it, or the tool broke. The executor already
        # named that, in codes the surface holds a sentence for because it draws
        # them beside the call itself, so the name is carried rather than
        # restated.
        return last.error
    # A call that finished, reported no error, and answered with something no
    # signal_desk could be read out of. Rare enough to have no code of its own, and
    # this is what that code would mean.
    return OUTCOME_CANNOT_READ


def signal_desk_of(name: str, payload: Any) -> Mapping[str, Any] | None:
    """The Signal Desk one call produced, or ``None`` where it produced none.

    Read off the structured payload for the reason :func:`outcome_of` is, and
    projected rather than passed through: what the stream may carry about a
    signal_desk is the id to fetch it by and enough to draw a skeleton of the right
    height. The numbers stay in the row, which is the whole arrangement.
    """
    if name not in _STUDY_TOOLS or not isinstance(payload, Mapping):
        return None
    artifact_id = payload.get("artifactId")
    if not artifact_id:
        return None
    headline = payload.get("headline")
    provenance = payload.get("provenance")
    return {
        "artifactId": str(artifact_id),
        "studyName": str(payload.get("studyName") or ""),
        # The Vietnamese name of the recipe, which is the only one a reader may
        # be shown. Resolved here because the registry is the one place that
        # knows it, and a browser given only the slug would either print the
        # slug or keep a second copy of the catalogue.
        "studyDisplayName": _study_display_name(payload.get("studyName")),
        "title": str(payload.get("title") or ""),
        "blockCount": (
            payload["blockCount"] if isinstance(payload.get("blockCount"), int) else 0
        ),
        # Which company the picture is about, so a reader with twenty boards can
        # type a ticker to find one again. Read off the headline the model was
        # handed rather than fetched: it is already in this payload, and a
        # Study about no single company honestly has none.
        "symbol": _headline_symbol(headline),
        # When the numbers were frozen. Off the provenance for the same reason.
        "asOf": (
            str(provenance.get("asOf") or "") if isinstance(provenance, Mapping) else ""
        ),
    }


def _headline_symbol(headline: Any) -> str:
    """The ticker one run is about, or ``""`` where it is about no single one."""
    if not isinstance(headline, Mapping):
        return ""
    symbol = headline.get("symbol")
    return str(symbol).strip().upper() if isinstance(symbol, str) else ""


def _study_display_name(name: Any) -> str:
    """The registered Vietnamese name for a Study, or ``""`` for an unknown one.

    Imported where it is used rather than at module scope: ``studies`` reaches
    the database layer, and this module is imported by the context builder,
    which has no business dragging the store in behind it. The package import
    is also what registers the Studies, so it is the package and not the
    registry module that is asked.
    """
    if not isinstance(name, str) or not name:
        return ""
    from src import studies

    definition = studies.REGISTRY.get(name)
    return definition.display_name if definition is not None else ""


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
    """
    line = f"called {call.name} with arguments {_compact(call.arguments)}"
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
        call.result_text or "",
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
    text = message.content or ""
    for call in message.tool_calls:
        text += call.name + _compact(call.arguments)
    if message.tool_call_id:
        text += message.tool_call_id
    images = sum(image.estimated_tokens for image in message.images)
    return MESSAGE_OVERHEAD_TOKENS + -(-len(text) // CHARS_PER_TOKEN) + images


def _system_message(transcript: Transcript) -> Message:
    """The system prompt, carrying its cache boundary when one is known.

    The segments describe the same string the message already holds —
    ``Message`` refuses any other arrangement — so a route that does not speak
    ``cache_control`` sees exactly the prompt it saw before, and the token
    estimate is unchanged either way.
    """
    prompt = transcript.system_prompt
    stable = transcript.system_prefix
    if not stable or not prompt.startswith(stable) or len(stable) == len(prompt):
        return Message(role=Role.SYSTEM, content=prompt)
    return Message(
        role=Role.SYSTEM,
        content=prompt,
        segments=(
            ContentSegment(stable, cache_breakpoint=True),
            ContentSegment(prompt[len(stable) :]),
        ),
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


def _user_message(turn: TranscriptTurn, *, latest: bool, vision: bool) -> Message:
    """The reader's own words, and whatever they attached to them."""
    if not turn.attachments:
        return Message(role=Role.USER, content=turn.user_text)
    block, images = _attachment_block(turn.attachments, latest=latest, vision=vision)
    return Message(
        role=Role.USER,
        content=f"{turn.user_text}\n\n{block}" if block else turn.user_text,
        images=images,
    )


def _turn_messages(
    turn: TranscriptTurn,
    collapsed: frozenset[str],
    *,
    latest: bool = False,
    vision: bool = False,
) -> tuple[Message, ...]:
    """One whole Turn, with its call/result pairs kept together.

    ``latest`` says whether this is the newest Turn of the snapshot it came
    from. It is passed in rather than read anywhere, which is what keeps
    :func:`build_messages` pure: the same transcript still gives the same list,
    because "newest" is a fact about the tuple and not about the clock.
    """
    messages: list[Message] = [_user_message(turn, latest=latest, vision=vision)]
    calls = turn.completed_calls
    if calls:
        messages.append(
            Message(
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
        )
        for call in calls:
            if call.id in collapsed:
                body = _collapsed_result(call)
            else:
                body = shown_result(call)
            messages.append(
                Message(
                    role=Role.TOOL,
                    content=body,
                    tool_call_id=call.id,
                    name=call.name,
                )
            )
    if turn.assistant_text:
        messages.append(Message(role=Role.ASSISTANT, content=turn.assistant_text))
    return tuple(messages)


def _render_messages(
    transcript: Transcript,
    turns: Sequence[TranscriptTurn],
    dropped: int,
    collapsed: frozenset[str],
) -> tuple[Message, ...]:
    """Assemble one candidate context.

    The system prompt is one message and the summary is another. Folding the
    summary into the prompt would put conversation content inside the artifact
    whose whole property is that conversation content cannot enter it — and it
    would move the cacheable prefix once per Turn.
    """
    messages: list[Message] = [_system_message(transcript)]
    if transcript.summary:
        messages.append(
            Message(
                role=Role.SYSTEM,
                content=f"{SUMMARY_LABEL}\n{transcript.summary}",
            )
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

    smallest = 0
    for dropped, collapsed in _reductions(live, budget):
        messages = _render_messages(transcript, live, dropped, collapsed)
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
            )

    raise ConstructedContextTooLarge(smallest, budget.max_tokens)


__all__ = [
    "ANSWER",
    "CHARS_PER_TOKEN",
    "COLLAPSED_RESULT_URLS",
    "DISPLAY_SNIPPET_CHARS",
    "MAX_DISPLAY_RESULTS",
    "MAX_SUMMARY_CHARS",
    "MESSAGE_OVERHEAD_TOKENS",
    "NO_SIGNAL_DESK_TOOL_CALLED",
    "signal_desk_absence",
    "signal_desk_of",
    "OUTCOME_CANNOT_READ",
    "OUTCOME_NO_VALUE",
    "OUTCOME_VALUE",
    "SUMMARY_LABEL",
    "THOUGHT",
    "ConstructedContext",
    "ConstructedContextTooLarge",
    "ContextBudget",
    "ToolCallStatus",
    "Transcript",
    "TranscriptTurn",
    "TurnAttachment",
    "TurnToolCall",
    "build_messages",
    "dedup_key",
    "display_results",
    "estimate_tokens",
    "outcome_of",
    "shown_result",
    "summarise_call",
]
