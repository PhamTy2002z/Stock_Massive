"""Rebuild, from a finished run's trace, every context that run constructed.

The measurement C2 is graded on is a *token* measurement, and a token
measurement made by running the corpus again is three measurements added
together: the code changed, the Internet changed, and the model sampled
differently. Only the first of those is C2's. So this module takes the trace of
one real run — the questions the model was asked, the tools it chose, the
arguments it passed, the bytes that came back — and replays it through the same
public context builder the loop uses, with no network, no model and no clock.

Two commands, and the split is the whole design.

``export`` reads the store once and writes a corpus file. It is the only half
that touches a database, and it is run when a Golden artifact is produced.

``replay`` reads that corpus and constructs contexts. It is pure: the same
corpus gives byte-identical output on any machine, today or in a month, which
is what lets a number from before a change be compared with a number from after
it. A replay that needed the store would be a replay whose denominator moves.

What it deliberately does **not** do is decide anything. It does not judge a
context, it does not enforce a threshold and it does not know what "better"
means; it prints where the tokens went. The gate that reads these numbers is
phase 05, and it lives in a file that cannot also produce them.
"""

from __future__ import annotations

import argparse
import json
import logging
from collections.abc import Mapping, Sequence
from dataclasses import replace
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

logger = logging.getLogger("golden.context_replay")

#: The corpus this module writes, and the report it writes from one.
#:
#: Two versions rather than one, because they go stale for different reasons: a
#: corpus is a recording of a run and only changes when a run is re-exported,
#: while the report's shape changes whenever a layer is added.
CORPUS_SCHEMA = "golden.context-replay@1"
REPORT_SCHEMA = "golden.context-replay-report@1"

#: The date the replayed prompt is rendered for.
#:
#: Pinned rather than read from the clock, and that is the difference between a
#: replay and a re-run. ``RuntimeContext`` puts the date in the prompt, so a
#: replay reading ``date.today()`` would produce a different system message
#: every morning — and the token delta phase 05 grades would move on its own.
REPLAY_DATE = date(2026, 8, 29)

#: The reader the replayed prompt greets. The synthetic runner's own name and
#: nobody else's: it is already written down in ``golden/run.py``, it changes
#: the prompt's bytes, and it belongs to an account that exists to be measured.
REPLAY_USER_NAME = "Golden Runner"


# -- export: the one half that reads a store -------------------------------


def _artifact_cases(artifact: Mapping[str, Any]) -> tuple[Mapping[str, Any], ...]:
    return tuple(
        case
        for case in artifact.get("cases") or ()
        if isinstance(case, Mapping) and (case.get("turn") or {}).get("request_message_id")
    )


def export(artifact_path: Path, out_path: Path) -> dict[str, Any]:
    """Turn one Golden artifact plus its traces into a replayable corpus.

    The artifact alone is not enough and never was: it records what each call
    *found* — a source list, a character count — because that is what a grader
    reads. Rebuilding a context needs what each call *returned*, in full, and
    the arguments it was called with. Both are in ``agent_tool_call``, keyed by
    the same ``request_message_id`` the artifact already carries.

    Nothing personal travels. The rows are the synthetic runner's, the account
    is named by a constant in this directory rather than read from the user
    table, and no owner id, address or route configuration is written out.
    """
    from sqlalchemy import select

    from src.agent.definitions import resolve_tool_surface
    from src.agent.domain import active_pack
    from src.agent.prompt import PROMPT_HASH, PROMPT_VERSION
    from src.agent.toolsets import CHAT_TOOLSETS
    from src.alpha.models import AgentMessage, AgentToolCall
    from src.core.database import sync_session_factory

    artifact = json.loads(artifact_path.read_text(encoding="utf-8"))
    cases = _artifact_cases(artifact)
    if not cases:
        raise SystemExit(f"{artifact_path} carries no case with a request message")

    wanted = [int(case["turn"]["request_message_id"]) for case in cases]
    with sync_session_factory() as session:
        rows = list(
            session.execute(
                select(AgentToolCall)
                .where(AgentToolCall.request_message_id.in_(wanted))
                .order_by(AgentToolCall.request_message_id, AgentToolCall.id)
            ).scalars()
        )
        # The result lists the model's context carries, read from the message
        # they were persisted on rather than from the artifact. The artifact's
        # per-call rows deliberately drop them — a grader reads the flat
        # ``sources`` list, which is deduplicated across the whole case — and a
        # corpus built from that would have already done, by accident, the
        # deduplication phase 02 exists to measure.
        shown = list(
            session.execute(
                select(AgentMessage.thread_id, AgentMessage.content)
                .where(
                    AgentMessage.thread_id.in_(
                        [case["turn"]["thread_id"] for case in cases]
                    ),
                    AgentMessage.role == "assistant",
                )
                .order_by(AgentMessage.id)
            )
        )

    traced: dict[int, dict[str, Any]] = {}
    for row in rows:
        result = row.result or {}
        traced.setdefault(int(row.request_message_id), {})[
            str(row.tool_call_id or "")
        ] = {
            "arguments": dict(row.arguments or {}),
            "result_text": str(result.get("text") or ""),
            "status": str(row.status or ""),
        }

    results_by_call: dict[str, list[dict[str, Any]]] = {}
    for _, content in shown:
        for payload in (content or {}).get("tool_calls") or ():
            if not isinstance(payload, Mapping):
                continue
            results_by_call[str(payload.get("id") or "")] = [
                dict(item)
                for item in (payload.get("results") or ())
                if isinstance(item, Mapping)
            ]

    surface = resolve_tool_surface(CHAT_TOOLSETS)
    pack = active_pack()

    exported: list[dict[str, Any]] = []
    missing: list[str] = []
    for case in cases:
        message_id = int(case["turn"]["request_message_id"])
        rows_for_case = traced.get(message_id, {})
        calls: list[dict[str, Any]] = []
        for payload in case.get("tool_calls") or ():
            call_id = str(payload.get("id") or "")
            trace = rows_for_case.get(call_id)
            refused = trace is None
            if refused and int(payload.get("result_chars") or 0) > 0:
                # A call that produced text and left no trace row is a hole in
                # the record, and a corpus with a hole in it has a smaller
                # denominator than the run it claims to replay — which is
                # exactly the shape a token saving takes.
                missing.append(f"{case.get('id')}:{call_id}")
                continue
            calls.append(
                {
                    "id": call_id,
                    "name": str(payload.get("name") or ""),
                    "round": int(payload.get("round") or 0),
                    "status": str(payload.get("status") or ""),
                    "outcome": payload.get("outcome"),
                    "kind": str(payload.get("kind") or "external"),
                    "arguments": {} if refused else trace["arguments"],
                    "result_text": "" if refused else trace["result_text"],
                    # A call the harness refused before dispatching it. It never
                    # reached a tool, so it never wrote a trace row — and it is
                    # still part of the context, because the model asked for it
                    # and is shown that it did not run.
                    #
                    # What cannot be recovered is the guardrail's sentence about
                    # it: ``guidance`` travels in the message and is not
                    # persisted anywhere. It is a fixed constant per reason, so
                    # it is the same missing amount in every replay of every
                    # corpus and cancels in a delta — but it is counted in the
                    # report rather than left to be discovered.
                    "refused": refused,
                    "results": results_by_call.get(call_id, []),
                }
            )
        exported.append(
            {
                "id": case.get("id"),
                "question": case.get("question"),
                "family": case.get("family"),
                "calls": calls,
            }
        )

    if missing:
        # A corpus short of a call is a corpus whose denominator is smaller than
        # the run it claims to replay, and a smaller denominator is exactly the
        # shape a token saving takes. Refused rather than reported, because the
        # number this produces is the number a gate reads.
        raise SystemExit(
            "the trace is missing "
            f"{len(missing)} call(s) the artifact records: {missing[:5]}"
        )

    corpus = {
        "schema": CORPUS_SCHEMA,
        "exported_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source_artifact": artifact_path.name,
        "identity": {
            "prompt_version": PROMPT_VERSION,
            "prompt_hash": PROMPT_HASH,
            "pack": f"{pack.name}@{pack.version}",
            "pack_identity": pack.identity,
            "toolsets": list(CHAT_TOOLSETS),
            "tool_surface": surface.identity_digest,
            "model": (artifact.get("run") or {})
            .get("runtime_constants", {})
            .get("model"),
        },
        "runtime": {
            "today": REPLAY_DATE.isoformat(),
            "user_name": REPLAY_USER_NAME,
        },
        "cases": exported,
    }
    _write(out_path, corpus)
    logger.info(
        "exported %d case(s) and %d call(s) to %s",
        len(exported),
        sum(len(case["calls"]) for case in exported),
        out_path,
    )
    return corpus


# -- replay: pure -----------------------------------------------------------


def _payload_of(entry: Mapping[str, Any]) -> Any:
    """The structured result, back from the text the executor serialised.

    The one place this replay parses rather than being handed an object, and it
    is unavoidable: the executor holds the payload for the length of a call and
    nothing persists it. Parsing here is safe in the way parsing in the runtime
    would not be — this is a measurement of a recording, and a payload that will
    not parse simply projects to itself, which is what the runtime does for
    every tool that is not a search anyway.
    """
    text = str(entry.get("result_text") or "")
    if not text.startswith("{"):
        return None
    try:
        return json.loads(text)
    except ValueError:
        return None


def _call_of(entry: Mapping[str, Any], *, seen: set[str]) -> Any:
    from src.agent.messages import ToolCallStatus, TurnToolCall, context_projection

    status = entry.get("status")
    text = str(entry.get("result_text") or "")
    name = str(entry.get("name") or "")
    return TurnToolCall(
        id=str(entry.get("id") or ""),
        name=name,
        arguments=dict(entry.get("arguments") or {}),
        status=(
            ToolCallStatus(status)
            if status in {item.value for item in ToolCallStatus}
            else ToolCallStatus.OK
        ),
        result_text=text,
        # The same projection the loop applies at the same seam, against a set
        # that is per-case here for the reason it is per-Turn there.
        context_text=context_projection(
            name, _payload_of(entry), text, seen=seen
        ),
        round=int(entry.get("round") or 0),
        results=tuple(
            dict(item) for item in (entry.get("results") or ()) if isinstance(item, Mapping)
        ),
        outcome=entry.get("outcome"),
    )


def _urls_of(calls: Sequence[Any]) -> tuple[str, ...]:
    """Every source URL the model could point at, in first-seen order."""
    seen: list[str] = []
    for call in calls:
        for item in call.results:
            url = str(item.get("url") or "")
            if url and url not in seen:
                seen.append(url)
    return tuple(seen)


def replay_case(case: Mapping[str, Any], runtime: Mapping[str, Any]) -> dict[str, Any]:
    """Every context one Turn constructed, in the order it constructed them.

    A Turn calls the model once before its first tool and once after each round,
    so a Turn with two rounds of tools constructed three contexts and paid for
    three. The rounds are rebuilt from the recorded round index rather than from
    arrival order, because the index is the fact the runtime wrote down.
    """
    from src.agent.budget import TurnBudget, thresholds_for_context
    from src.agent.domain import active_pack
    from src.agent.loop import MAX_TOOL_ROUNDS, SYSTEM_NOTE_TOKENS, domain_tool_names
    from src.agent.messages import (
        SYSTEM_DYNAMIC,
        ContextBudget,
        Transcript,
        TranscriptTurn,
        build_messages,
    )
    from src.agent.prompt import RuntimeContext, prefix as prompt_prefix, render

    # First-seen order across the whole Turn, which is the order the loop sees
    # them in: the corpus preserves the round index and the arrival order within
    # it, so building the projections in one pass here is the same pass.
    context_sources: set[str] = set()
    calls = [
        _call_of(entry, seen=context_sources) for entry in case.get("calls") or ()
    ]
    rounds = max((call.round for call in calls), default=-1) + 1
    domain_tools = domain_tool_names()
    pack = active_pack()

    prompt = render(
        RuntimeContext(
            today=date.fromisoformat(str(runtime["today"])),
            user_name=runtime.get("user_name") or None,
        )
    )
    budget = ContextBudget()
    thresholds = thresholds_for_context(budget.max_tokens)

    turn_budget = TurnBudget(thresholds)
    constructed: list[dict[str, Any]] = []
    body_on = False
    for index in range(rounds + 1):
        earlier = [call for call in calls if call.round < index]
        # The output budget is a fact about the Turn, not about a round: a
        # result gathered three rounds ago can be asked to give ground now, so
        # the trimmed set is recomputed here exactly as ``_shown_calls`` does.
        trimmed = {result.call_id: result.text for result in turn_budget.rebalance()}
        shown = tuple(
            call
            if call.id not in trimmed
            else replace(call, context_text=trimmed[call.id])
            for call in earlier
        )
        exhausted = index == MAX_TOOL_ROUNDS
        # Only the notes are reserved now. The pack body travels inside the
        # system message and is measured there, like every other block of the
        # prompt — reserving it here as well would price it twice.
        reserved: list[tuple[str, int]] = []
        if exhausted:
            reserved.append((SYSTEM_DYNAMIC, SYSTEM_NOTE_TOKENS))

        held = sum(tokens for _, tokens in reserved)
        trimmed_budget = (
            replace(budget, max_tokens=budget.max_tokens - held) if held else budget
        )

        context = build_messages(
            Transcript(
                system_prompt=prompt,
                system_prefix=prompt_prefix(),
                system_body=pack.body_text if body_on else None,
                turns=(
                    TranscriptTurn(
                        user_text=str(case.get("question") or ""),
                        tool_calls=shown,
                    ),
                ),
            ),
            trimmed_budget,
        )
        composition = context.composition
        for layer, tokens in reserved:
            composition = composition.plus(**{layer: tokens})

        # Retention is asserted on the *text the model is given*, not on the
        # display projection beside it. A handle that kept a link in ``results``
        # and dropped it from the message would pass a check on the former and
        # be exactly the failure this phase is about.
        body = "\n".join(message.content or "" for message in context.messages)
        reachable = [url for url in _urls_of(shown) if url in body]
        constructed.append(
            {
                "call": index,
                "messages": len(context.messages),
                "estimated_tokens": composition.total,
                "turns_dropped": context.turns_dropped,
                "results_collapsed": context.results_collapsed,
                "composition": composition.as_dict(),
                "source_urls": list(_urls_of(shown)),
                "source_urls_in_context": reachable,
                # The reader's own question, still in the message the model
                # reads. It is protected by ``keep_intact_turns`` and by the
                # ladder never dropping the newest Turn — this is the assertion
                # that the protection held rather than the belief that it did.
                "intent_in_context": str(case.get("question") or "") in body,
            }
        )

        # What this round asked for decides whether the *next* call carries the
        # pack body — the loop reads the request before dispatching it, so the
        # playbook is in place for the call that has to read the results.
        if any(call.name in domain_tools for call in calls if call.round == index):
            body_on = True
        for call in calls:
            if call.round == index:
                turn_budget.add(call.id, call.name, call.model_text)

    return {
        "id": case.get("id"),
        "family": case.get("family"),
        "rounds": rounds,
        "calls": len(calls),
        "refused_calls": sum(
            1 for entry in case.get("calls") or () if entry.get("refused")
        ),
        "constructed": constructed,
        "constructed_tokens": sum(item["estimated_tokens"] for item in constructed),
        "source_urls": list(_urls_of(calls)),
        "urls_offered": sum(len(item["source_urls"]) for item in constructed),
        "urls_reachable": sum(
            len(item["source_urls_in_context"]) for item in constructed
        ),
        "intent_kept": all(item["intent_in_context"] for item in constructed),
    }


def _median(values: Sequence[int]) -> float:
    ordered = sorted(values)
    if not ordered:
        return 0.0
    middle = len(ordered) // 2
    if len(ordered) % 2:
        return float(ordered[middle])
    return (ordered[middle - 1] + ordered[middle]) / 2


def replay(corpus: Mapping[str, Any]) -> dict[str, Any]:
    """Every case of a corpus, and the totals a gate reads."""
    from src.agent.definitions import resolve_tool_surface
    from src.agent.domain import active_pack
    from src.agent.messages import CONTEXT_LAYERS
    from src.agent.prompt import PROMPT_HASH, PROMPT_VERSION
    from src.agent.toolsets import CHAT_TOOLSETS

    if corpus.get("schema") != CORPUS_SCHEMA:
        raise SystemExit(f"not a {CORPUS_SCHEMA} corpus: {corpus.get('schema')!r}")

    runtime = corpus.get("runtime") or {}
    cases = [replay_case(case, runtime) for case in corpus.get("cases") or ()]

    layers = {layer: 0 for layer in CONTEXT_LAYERS}
    for case in cases:
        for item in case["constructed"]:
            for layer, tokens in item["composition"].items():
                layers[layer] += tokens

    pack = active_pack()
    return {
        "schema": REPORT_SCHEMA,
        "corpus": {
            "source_artifact": corpus.get("source_artifact"),
            "exported_at": corpus.get("exported_at"),
            "identity": corpus.get("identity"),
        },
        # The identity the *replay* ran under, beside the one the run was
        # recorded under. Two fields rather than one because a mismatch is the
        # information: a prompt edited since the export explains a token delta
        # that has nothing to do with prune.
        "replayed_under": {
            "prompt_version": PROMPT_VERSION,
            "prompt_hash": PROMPT_HASH,
            "pack": f"{pack.name}@{pack.version}",
            "pack_identity": pack.identity,
            "tool_surface": resolve_tool_surface(CHAT_TOOLSETS).identity_digest,
        },
        "totals": {
            "cases": len(cases),
            "calls": sum(case["calls"] for case in cases),
            # Calls the harness refused before dispatch. Their guardrail
            # sentence is the one thing a replayed context is missing, so the
            # count is printed rather than buried: it is the size of the gap.
            "refused_calls": sum(case["refused_calls"] for case in cases),
            "model_calls": sum(len(case["constructed"]) for case in cases),
            "constructed_tokens": sum(case["constructed_tokens"] for case in cases),
            "tokens_per_turn_median": _median(
                [case["constructed_tokens"] for case in cases]
            ),
            "distinct_source_urls": len(
                {url for case in cases for url in case["source_urls"]}
            ),
            # Out of every (call, url) pair the Turn could point at, how many
            # the model could still see. The denominator is per model call, not
            # per URL: a link that survives round one and is gone by round three
            # is not retained, and a set would hide that.
            "urls_offered": sum(case["urls_offered"] for case in cases),
            "urls_reachable": sum(case["urls_reachable"] for case in cases),
            "intent_kept": all(case["intent_kept"] for case in cases),
            "layers": layers,
        },
        "cases": cases,
    }


# -- command line -----------------------------------------------------------


def _write(path: Path, payload: Mapping[str, Any]) -> None:
    """One serialisation, so two runs of the same input are the same bytes."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=False) + "\n",
        encoding="utf-8",
    )


def main(argv: Sequence[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    parser = argparse.ArgumentParser(prog="golden.context_replay", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    exporter = sub.add_parser("export", help="read a run's traces into a corpus")
    exporter.add_argument("--artifact", required=True, type=Path)
    exporter.add_argument(
        "--out", type=Path, default=Path("golden/artifacts/context-replay-v1.json")
    )

    player = sub.add_parser("replay", help="construct every context of a corpus")
    player.add_argument(
        "--corpus", type=Path, default=Path("golden/artifacts/context-replay-v1.json")
    )
    player.add_argument("--out", type=Path, required=True)

    args = parser.parse_args(argv)
    if args.command == "export":
        export(args.artifact, args.out)
        return 0

    corpus = json.loads(args.corpus.read_text(encoding="utf-8"))
    report = replay(corpus)
    _write(args.out, report)
    totals = report["totals"]
    logger.info(
        "%d case(s), %d model call(s), %d constructed token(s), median %.0f/Turn",
        totals["cases"],
        totals["model_calls"],
        totals["constructed_tokens"],
        totals["tokens_per_turn_median"],
    )
    return 0


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
