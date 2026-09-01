# Task 3 — tool-call lifecycle: `pending`/`denied` on the wire, persist-intent-before-effect, 0 orphan at terminal

Branch `feat/phase-03-durable-loop-lane`, commit `bc4b963`. Worktree was clean at
`2b0808b` before starting; clean after the commit.

## Which pending-shape, and why

**The full shape** from plan §4, not the simplified one: the intent checkpoint
writes the calls as `PENDING`, and they are published `RUNNING` at the moment
they are about to be dispatched.

Reasons it was not materially simpler to reuse `RUNNING`:

- the flip is two three-line loops over one `range` that already existed
  (`loop.py:1842-1873`), against one loop for the simple shape — no new type, no
  new call site, no new state machine;
- the two states answer different questions of a *recovered* draft, which is the
  only reader that ever sees `PENDING`: a `pending` call is an intent nobody acted
  on yet, a `running` call is an intent somebody acted on. With `RUNNING` reused,
  a recovered draft cannot tell "we wrote it down and then the process died"
  from "we dispatched it and then the process died" — and that distinction is
  exactly what persist-intent-before-effect exists to record;
- the plan's Non-goals already fix the DB vocabulary at four values, so the extra
  wire state costs nothing downstream (`alpha/models.py` untouched).

`PENDING` never reaches the live SSE stream by design (the publish point is
after the flip back), so nothing on the wire changes for a healthy Turn. It
reaches a reader only through a *draft* projection — the checkpoint, and the
snapshot rebuilt from it — which is where the fact belongs.

## What changed

`apps/api/src/agent/messages.py`
- `ToolCallStatus` +`PENDING` +`DENIED`, docstring says what each of the five
  means and that the trace vocabulary is a different thing (`messages.py:54-79`).
- `UNSETTLED_STATUSES` (`pending|running`) and `CALL_INTERRUPTED = "interrupted"`
  named once (`messages.py:82-98`).
- `TurnToolCall.finished` now reads against `UNSETTLED_STATUSES`
  (`messages.py:393-402`). This is load-bearing: without it a `pending` call would
  enter `completed_calls` and hand the model half a tool exchange.

`apps/api/src/agent/loop.py`
- `_settled_status(result)` maps `executor.PERMISSION_DENIED` → `DENIED`, keeps
  OK/ERROR otherwise (`loop.py:842-857`, used at `loop.py:1911`). `dispatched=False`
  and the `permission_denied` code are preserved; executor semantics untouched.
- `_changes_durable_state(calls)` reads `effect is ToolEffect.WRITE` off the
  per-call resolved declaration (`loop.py:860-878`).
- Intent checkpoint in `_round`: write batch → set planned records `PENDING`,
  `await self._save(state, boundary=True)`, flip back to `RUNNING`, then publish
  and dispatch (`loop.py:1842-1873`). Read-only batches keep the old path.
- The publish loop and the timeout settle now read `state.calls[position]` rather
  than the stale `planned` list, and the timeout settle widened to
  `UNSETTLED_STATUSES` (`loop.py:1875-1885`, `1961-1972`).
- `_settle_orphans(state, status)` called first in `_ended`
  (`loop.py:2160-2196`, `2246`): anything left `pending|running` becomes
  `ERROR` with `cancelled_by_user` on the cancel path and `interrupted`
  otherwise, `dispatched` and any existing error code untouched, and the settled
  state is published so stream and checkpoint agree.

`apps/api/src/agent/turns.py`
- `settle_orphan_calls(calls, error)` — pure, wire-dict level, beside
  `draft_content` (`turns.py:250-287`). Only `status` changes; `error` only when
  the record carries none; every other key copied through, `dispatched` included.
- Applied in `frozen_message` (`turns.py:357-366`) and in `_finish_bare`
  (`turns.py:618-632`), and `_finish_bare` now also writes a settled `draft=`
  (`turns.py:650-665`) — without it the row a later subscriber is answered from
  would keep drawing what the canonical message no longer says.
- `events.py`, `executor.py`, `alpha/models.py`, `persistence.py`, `router.py`,
  `lanes.py`, `parts.py`, `apps/web` untouched.

## Tests (9 new, none weakened)

`tests/test_agent_loop.py`
- permission-denied call renders `denied` on the wire, keeps
  `error="permission_denied"`, `dispatched=False`, Turn stays `COMPLETE`;
- a write batch produces exactly one draft holding the call `PENDING`, at a
  `boundary`, with no `result_text`, and its index precedes the first draft that
  carries any result;
- a read-only batch produces no `PENDING` draft at all and the write batch costs
  exactly one checkpoint more than the read batch (`len(writes) == len(reads)+1`);
- Turn ending with an unsettled call: `outcome.tool_calls` has nothing
  unfinished, the orphan is `error/interrupted` with `dispatched is True`, and
  the surface was told. The fault is injected by monkeypatching
  `ToolExecutor.run` to answer one result short — one-call-one-result makes the
  terminal gate unreachable otherwise, so injecting it is the only way to test
  the gate rather than assume it;
- the cancel variant of the same, settling as `cancelled_by_user`;
- a `pending` call is left out of the constructed context like a `running` one.

`tests/test_agent_turn_lifecycle.py`
- `settle_orphan_calls` unit: pending/running settle, `ok` untouched, an existing
  `tool_call_timeout` reason survives, `dispatched` (True/False/absent) copied
  verbatim, input list not mutated;
- deadline path end-to-end: a hanging `remember_fact` (WRITE) killed by a 0.05s
  deadline leaves `interrupted` in the persisted draft, in the canonical message
  and in the replayed snapshot — which also proves the intent checkpoint landed,
  since without it the draft holds no call at all;
- startup sweep: a checkpoint holding `ok` + `running` + `pending` freezes to
  `ok` + two `error/interrupted`.

## Verification (host)

```
pytest tests/test_agent_loop.py tests/test_agent_turn_lifecycle.py \
  tests/test_agent_turn_events.py tests/test_agent_tool_executor.py -q  → 251 passed
pytest -q                                                              → 1225 passed, 3 deselected
python -m compileall -q src tests                                      → clean
git diff --check                                                       → clean
```

Baseline was 1216 passed / 3 deselected; +9 is exactly the new tests.

## Residuals and unresolved questions

1. **The sweep does not rewrite `draft_content`.** `persistence._freeze` writes
   the frozen *message* and leaves the checkpoint column as it was, so a swept
   Turn's replayed snapshot (`turns.subscribe` → `snapshot_from_draft`) can still
   project `running`/`pending` calls. Rewriting it means touching
   `persistence.py`, which this task was told not to do, and `events.py`, which
   the task said needs no change. This pre-exists for `running`; `pending` joins
   it. If the phase gate "0 call `running|pending` in *any* persisted view" is
   measured on that snapshot, it needs either a settle inside `_freeze`'s
   transaction or a settle in `snapshot_from_draft`. Which one do you want, and
   in whose task?
2. **`TOOL_CALL_FIELDS` carries no `error`.** So `denied` vs `error` is the only
   signal the browser gets about a refused call; the reason code lives only in
   the transcript and the trace. That is why the status mapping matters, but if
   the web work in task 6 wants to say *why*, the allowlist would have to widen —
   an SSE contract question, not mine to open.
3. **The tool-timeout path still records `dispatched=False`** (`loop.py:1961-1972`,
   pre-existing). For a write batch that hung, that is not truthful — the call was
   sent and may have landed. I left the behaviour alone rather than change a
   settled path outside this task's scope; it is the one place a recovered write
   intent is contradicted by the record beside it.

Status: DONE
Summary: Tool-call lifecycle landed on the full pending-shape — write batches
checkpoint their intent as `pending` before dispatch, permission refusals render
as `denied`, and every unsettled call is settled at the loop's terminal gate and
in the checkpoint the lifecycle freezes; suite 1225 passed / 3 deselected.
Concerns: the startup sweep leaves the raw checkpoint in `draft_content`, so a
swept Turn's replayed snapshot can still project an unsettled call — fixing that
needs `persistence.py` or `events.py`, both excluded here.
