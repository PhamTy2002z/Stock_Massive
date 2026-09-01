# Phase 3 · Task 4 — cancellation reaches the model call and the read tools

Plan: `plans/260901-1154-phase-03-durable-loop-lane/plan.md` (Thiết kế §5).
Branch `feat/phase-03-durable-loop-lane`, one commit `92d0edc`
(`feat(agent): tear down in-flight work when a turn is cancelled`).
Worktree clean at start (HEAD `576b88a`), `git diff --check` clean.

## What changed

**Cancel event plumbing.** `RunningTurn.cancel_event` (`turns.py:151`,
`asyncio.Event` per Turn); `TurnService.cancel` sets it beside
`cancel_requested` (`turns.py:733`), `shutdown` sets it for every running Turn
(`turns.py:753`); `cancelled()` predicate untouched and still the round-boundary
authority. `_execute` passes it into the loop (`turns.py:554`).
`AgentLoop.run(..., *, cancel_event=None)` (`loop.py:1121`) → `_run` → carried on
`_TurnState.cancel_event` (`loop.py:1019`) rather than through six signatures,
because both racers (`_complete`, the executor) already hold the state or are
built in `_run`.

**Model call.** `_complete` builds the client coroutine, then races it inside the
unchanged `wait_for(self._call_timeout)` (`loop.py:1591`); `_asked`
(`loop.py:1593`) is the race: `asyncio.wait({call, stopped}, FIRST_COMPLETED)`,
completion wins ties, otherwise the call task is cancelled, awaited quietly and
`TurnCancelled` (`loop.py:686`) is raised. `_run` settles it as
`CANCELLED / cancelled_by_user` with the partial text kept (`loop.py:1248`) and
emits the existing `model_attempt {status: cancelled}` part. A `wait_for` timeout
still tears the inner call down (`except asyncio.CancelledError: call.cancel()`),
so the pre-existing `llm_call_timeout` path is unchanged. Ledger untouched: the
abandoned reservation reconciles through `usage_unknown`, stated in the
`_complete` docstring.

**Tool round.** `ToolExecutor.cancel_event` (`executor.py:238`) plus
`CANCELLED_CALL = "cancelled"` (`executor.py:118`). Boundary check settles every
remaining call `ok=False, dispatched=False` (`executor.py:312-319`). `_parallel`
(`executor.py:358`) races the read segment against the event, cancels the
still-pending dispatches and settles them `CANCELLED_CALL, dispatched=True`;
finished siblings keep their real results. A single-call parallel segment takes
the same path when an event exists — cancellability must not depend on batch
size. A sequential barrier already running is never cancelled: the write
finishes, and the boundary check settles what follows. One result per call on
every path; module docstring rule list extended (`executor.py:19-40`).

**Round-timeout truthfulness (task 3 follow-up).** `loop.py:2092` —
`dispatched=call.id in sent`, `sent` being the runnable batch, so a call that was
sent stays `dispatched=True` when the round gives up on it.

## Evidence

- Loop: `test_a_stop_during_the_model_call_does_not_wait_the_route_out`
  (`tests/test_agent_loop.py:892`) — a client that stalls 5 s on its second ask;
  Turn settles `cancelled/cancelled_by_user` in under 2.5 s, `answered == 0`
  (the ask was torn down), round 1's text and `ok` call kept, attempt statuses
  `running, completed, running, cancelled`, no unsettled call in the outcome or
  in the last draft.
- Loop: `test_a_call_the_round_gave_up_on_is_still_recorded_as_sent`
  (`tests/test_agent_loop.py:2443`) — both timed-out calls keep `dispatched=True`.
- Executor (`tests/test_agent_tool_executor.py:341-445`): reads in flight
  cancelled with `dispatched=True` while the finished sibling keeps its result and
  the issued order holds; a write barrier crossing the stop runs to its end
  exactly once (`surface.order == ["web_search", "remember_fact"]`) and the read
  behind it settles `cancelled, dispatched=False`; a batch meeting an already-set
  stop dispatches nothing and answers every call.
- Lifecycle: `test_a_cancel_reaches_the_work_in_flight_and_not_only_the_next_boundary`
  (`tests/test_agent_turn_lifecycle.py:545`) and
  `test_shutdown_stops_every_running_turn_the_way_a_reader_would`
  (`tests/test_agent_turn_lifecycle.py:1050`).
- `tests/test_agent_transport.py:113` — the `ScriptedLoop` double now accepts the
  keyword the service passes (contract change, no assertion weakened).

Commands (host): `pytest tests/test_agent_loop.py tests/test_agent_tool_executor.py
tests/test_agent_turn_lifecycle.py -q` → 234 passed (also clean under
`-W error::RuntimeWarning`); `pytest -q` → **1232 passed, 3 deselected**
(baseline 1225 + 7 new); `compileall -q src tests golden` clean.

## Notes / unresolved

1. A call cancelled in flight writes **no Tool Call Trace row** — `_dispatch` is
   torn down before `_record`, the same as the existing `_skipped` path. The wire
   and message record it (status `error`, error `cancelled`, honest `dispatched`),
   the DB trace does not. The trace `status` vocabulary has only four values, so
   giving it one would be a schema decision; flagging for P5/P9 rather than
   deciding here.
2. Wire status for a cancelled call is `error` via `_settled_status`, and
   `trace_status` would group it under `tool_error` if a row were ever written.
   No new wire status was added (out of task scope; task 3 owns that vocabulary).
3. Fault-injection matrix rows "Cancel giữa model call" / "Cancel giữa tool
   round" are covered by the tests above but not yet in
   `tests/test_agent_fault_injection.py`, which task 7 owns.

Status: DONE
Summary: A stop now tears down the in-flight model call and in-flight read
segments, lets a running write finish exactly once, settles every call with an
honest `dispatched`, and the round-timeout settle no longer claims a sent call
was never dispatched.
Concerns/Blockers: none blocking; the missing trace row for a cancelled call
(note 1) is a deliberate, documented gap.
