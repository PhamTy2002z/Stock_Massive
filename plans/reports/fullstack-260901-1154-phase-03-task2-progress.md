# Phase 3 · Task 2 — typed progress parts (real loop audit trail)

Plan: `plans/260901-1154-phase-03-durable-loop-lane/plan.md` §Thiết kế 2.
Branch `feat/phase-03-durable-loop-lane`, one commit `caf8c28`.
Worktree clean at start (`b62f7dd`), `git diff --check` clean.

## What landed

**New `apps/api/src/agent/parts.py`** (238 lines)
- `ProgressKind` closed set (parts.py:50-79): `lane_selected`, `model_attempt`,
  `tool_round`, `recovery`, `tools_halted`, `rounds_exhausted`, `deadline`.
- `PROGRESS_FIELDS` per-kind key allowlist (parts.py:108-121) + closed
  vocabularies `ATTEMPT_STATUSES` / `RECOVERY_ACTIONS` (parts.py:82-105).
- `progress_payload(kind, **fields)` (parts.py:165-197): unknown *kind* →
  `ValueError`; unknown *key* → dropped + `logger.warning` (a part must never be
  the thing that ends a Turn). Value discipline `_admissible` (parts.py:133-162):
  codes/numbers/flags or a list of codes only — a mapping or a >120-char string
  is dropped, so prose cannot ride in on an allowed key.
- `ProgressPart` frozen (parts.py:200-231): `seq` (per-Turn ordinal), `kind`,
  `round`, `payload`, `at` (loop clock, UTC ISO), `as_wire()`;
  `PROGRESS_WIRE_FIELDS` is the five-key wire shape both the transport and the
  checkpoint read.

**`events.py`** — additive only
- `EventType.PART_PROGRESS = "part.progress"` (events.py:96); the seven existing
  types and `ENVELOPE_VERSION` unchanged.
- `TurnPublisher.progress(part_wire)` (events.py:393-405) publishes with a
  by-name field take, like `tool_call`. `_remember` appends to the ordered
  `self._progress` (events.py:486-487, field at events.py:267); read side is the
  property `progress_parts` — renamed from `progress` because the method would
  have shadowed it (events.py:330-336).
- `subscribe` snapshot gains `"progress"` (events.py:457);
  `snapshot_from_draft` reads `draft.get("progress")` and defaults to `[]`
  (events.py:541-561). No awaits added → subscribe/publish still atomic.

**`loop.py`** — emission at the real events, via `_progress` (loop.py:2014-2043)
which appends to `_TurnState.progress` with the next ordinal and publishes in the
same step. Synchronous, so the recovery helpers can emit.
- `lane_selected` once at the top of `_run` (loop.py:1092-1099). The reason is
  plumbed as `TurnRequest.lane_reason` (loop.py:707-715, default
  `lanes.DEFAULT_REASON`) — chosen over a constructor kwarg because it needed no
  change to the four `loop_factory(*, checkpoint, publisher, lane)` signatures
  task 1 settled (`service.py:120`, two test factories, `tests/e2e/server.py`).
- `model_attempt`: `running` before `_call` (loop.py:1138); `completed` after it
  returns (loop.py:1185); `error` + terminal_reason on the timeout, budget and
  `LLMError` paths (loop.py:1152, 1164, 1182); `cancelled` + `cancelled_by_user`
  at both cancel exits (loop.py:1103, 1262 via `_cancelled_attempt`,
  loop.py:2064-2073). `ModelRefusal` reports `completed` with
  `terminal_reason=model_refusal` (loop.py:1178): the attempt returned words that
  were paid for. `MalformedArguments` re-raises unchanged and emits nothing (see
  questions).
- `recovery` exactly where each recovery commits: `_compress` after the two
  roll-back branches (loop.py:1582-1592), `_lower_output_cap` (loop.py:1637-1644),
  `_nudge_empty` (loop.py:1697-1704) — `attempt` = the new count, `bound` = the max.
- `tool_round` right after `state.calls.extend(planned)` (loop.py:1781-1793):
  `calls`, `external_used`, `call_ids`; no queries or domains duplicated.
- `tools_halted` where `state.tools_halted` is set, carrying the ladder's code and
  not its prose guidance (loop.py:1901-1909); `rounds_exhausted` once per Turn
  where `exhausted` is decided (loop.py:1128-1136); `deadline` where `_expired`
  ends the Turn (loop.py:1113).
- `TurnDraft.progress` / `TurnOutcome.progress` in wire form (loop.py:738-742,
  768-772), `_TurnState.draft()` (loop.py:969) and `_ended` (loop.py:2137) carry it.

**`turns.py`** — `draft_content` includes `"progress"` (turns.py:244);
`assistant_message` gains `progress` and writes it on the content (turns.py:256,
291); `_finish` passes `outcome.progress` to both message and draft
(turns.py:529, 546); `_finish_bare` (turns.py:585) and `frozen_message`
(turns.py:324) carry the checkpointed trail through unchanged;
`create` passes `lane_reason` into the request (turns.py:463).

## Evidence for the two load-bearing invariants

1. **1-1 with real events, no fake stages.** Every emission site is inside the
   branch that performs the act. Pinned by
   `test_a_recovery_that_was_declined_is_not_in_the_trail`
   (test_agent_loop.py:1365) — a `ContextOverflow` with nothing to give up
   produces *no* recovery part — and by
   `test_a_halted_tool_loop_says_so_with_the_ladders_own_code`
   (test_agent_loop.py:1439), where the halt does not fake a
   `rounds_exhausted`.
2. **Progress never reaches the model.** `messages.Transcript`/`TranscriptTurn`
   have no field a part could arrive through, and `router.history_of`
   (router.py:195-260) reads only `text`, `attachments`, `tool_calls`.
   Pinned twice: `test_no_part_of_the_trail_reaches_the_model`
   (test_agent_loop.py:1508) asserts no kind or recovery action appears in
   anything sent to the route on a Turn that produced lane/recovery/tool_round
   parts, and `test_an_extra_key_on_a_stored_message_cannot_change_what_the_model_sees`
   (test_agent_loop.py:1548) asserts `history_of` and the constructed messages
   are identical for a stored message with and without the trail.

## Tests

- New `tests/test_agent_parts.py` (12): allowlist by key, by value type, by
  length; unknown kind refused, declared kind as a bare string resolved; wire
  shape = `PROGRESS_WIRE_FIELDS`; `None` terminal_reason kept; ordinal ordering;
  frozen part.
- `test_agent_loop.py` new section "the progress trail" (14 tests): ordered kinds
  for a two-round Turn (`lane_selected`, running/completed, `tool_round`,
  running/completed) with seq 1..6 and per-round attribution; `tool_round`
  call_ids joined against the rail's ids; compression / lower-cap / empty-nudge
  recoveries with their bounds and the fact that a recovery does not open a second
  attempt; the ceiling with the lane's own number; the halt code; the deadline;
  the cancel; trail equal on checkpoint, outcome and stream.
  One existing assertion adapted, not weakened: the event-order pin at
  test_agent_loop.py:423 now filters progress out of the same list so it still
  pins narration → tool → tool → reply.
- `test_agent_turn_events.py` (+6): ordered remembering, five-field wire take
  (an extra `guidance` key dropped), snapshot restates exactly what was
  published and still consumes no sequence, `snapshot_from_draft` round-trip,
  a pre-parts checkpoint reads as `[]`, a part reaches a live subscriber and the
  terminal still closes it.
- `test_agent_turn_lifecycle.py` (+3): checkpoint + replayed snapshot carry the
  trail; the canonical message says which lane answered and why
  (`{"lane": "deep", "reason": "keyword:memo"}` end-to-end through the router);
  a swept Turn keeps its checkpointed trail, and an older-build checkpoint reads
  as `[]`.

Commands (host):
- `pytest tests/test_agent_parts.py tests/test_agent_turn_events.py tests/test_agent_loop.py tests/test_agent_turn_lifecycle.py tests/test_turn_sse.py -q` → **228 passed**
- `pytest -q` → **1216 passed, 3 deselected** (baseline 1181 + 35 new)
- `python3 -m compileall -q apps/api/src apps/api/golden apps/api/tests` → clean

Web untouched: `use-live-turn.ts:41-49` listens only for the seven named types,
so `part.progress` never dispatches to a client, and `MessageResponse.content` is
an open mapping (schemas.py:108) so the new content key needs no schema change.
Task 6 owns the projection.

## Unresolved questions

1. `MalformedArguments` (including `ToolCallIdMismatch`) re-raises out of `_run`
   and emits no `model_attempt` part — the Turn is settled `turn_failed` by
   `turns.py`, and a part published there would never be checkpointed. The task
   did not list it; if the fault-injection matrix (task 7) wants the trail to
   name this, it is one line at loop.py:1141.
2. `model_attempt {status: cancelled}` currently means "the Turn will ask the
   model nothing further" — cancellation is still only polled at round
   boundaries, so no attempt is ever in flight when it fires. Task 4 makes the
   in-flight case real; the payload does not need to change, but the docstring at
   loop.py:2058 should be revisited then.
3. The publisher's read side is `progress_parts`, not `progress`, because the
   emit method owns the shorter name. If the web or ops later wants a symmetric
   name for the three restated collections, that rename belongs with task 6.

Status: DONE
Summary: Typed progress parts now emit from the seven real loop events, ride an
additive `part.progress` SSE type plus the snapshot, checkpoint and canonical
message, and are pinned as content-light and invisible to the model; whole
backend suite green at 1216.
