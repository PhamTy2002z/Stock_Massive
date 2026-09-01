---
report: fullstack-260901-1154-phase-03-task7-fault-gate
plan: 260901-1154-phase-03-durable-loop-lane
task: 7 — fault-injection gate suite
branch: feat/phase-03-durable-loop-lane
commit: 01b0b59
date: 2026-09-01
---

# Task 7 — fault-injection gate suite

One new file, no production change: `apps/api/tests/test_agent_fault_injection.py`
(14 tests). Every matrix row is exercised through `TurnService` — the highest
honest level: the fault is injected into the scripted route or the tool world,
and the assertions are made on what a reader can actually reach afterwards (the
`agent_turn` row, its `draft_content`, the canonical assistant message, the
snapshot `snapshot_from_draft` rebuilds, the publisher's own snapshot, and the
`agent_question` state merged into `read_thread`).

## Matrix row → test → result

| # | Fault | Test | Result |
|---|---|---|---|
| 1 | LLM call timeout | `test_a_route_that_stops_answering_ends_on_our_own_call_ceiling` | pass — `incomplete/llm_call_timeout`, partial prose kept, last `model_attempt` part = `error/llm_call_timeout`, the stalled ask torn down (`client.answered == 0`) |
| 2 | Route rate limit | `test_a_rate_limited_route_ends_the_turn_under_the_routes_own_reason` | pass — `incomplete/route_rate_limited`; nothing said, so no message is written and the reason lives on the Turn |
| 3a | Duplicate tool-call ids | `test_a_route_that_repeats_a_call_id_fails_and_leaves_nothing_running` | pass — `incomplete/turn_failed`; the round was also made to answer one call short, so the settle on that path is real: message, `draft_content` and the rebuilt snapshot all read `["ok", "error"]` with `error == "interrupted"` |
| 3b | Malformed JSON arguments | `test_arguments_that_are_not_json_settle_one_call_and_spare_its_sibling` | pass — typed `invalid_arguments` on the garbled call, `ok` on the sibling, Turn `complete` and answered in 2 calls |
| 4 | Empty completion after tools | `test_a_round_of_tools_with_no_reply_is_nudged_once_and_then_admits_it` | pass — exactly one `recovery/empty_nudge` (attempt 1, bound 1), 3 route calls, then `incomplete/empty_answer`; narration and the round's evidence kept |
| 5 | Context overflow past both compressions | `test_a_transcript_that_never_fits_ends_after_the_compressions_it_ran` | pass — `incomplete/context_overflow`, 3 calls, two `recovery/compress` parts (attempts 1 and 2, bound 2) on the checkpointed trail, prompt characters strictly decreasing, output ceiling untouched |
| 6 | Output cap past both reductions | `test_an_output_ceiling_that_never_fits_ends_after_the_reductions_it_ran` | pass — `incomplete/output_cap_exceeded`, two `recovery/lower_output_cap` parts, ceilings strictly decreasing, transcript identical across the three attempts |
| 7 | Tool past its declared bound | `test_a_tool_past_its_declared_bound_is_one_result_and_the_turn_answers` | pass — typed `tool_call_timeout` on that one call, Turn `complete` with its answer, `dispatched is True` on the timed-out call |
| 8 | Cancel mid model call | `test_a_stop_mid_model_call_settles_promptly_and_keeps_what_was_said` | pass — `cancelled/cancelled_by_user` in **< 2.5 s against a 5 s stall**, partial text kept, `model_attempt cancelled/cancelled_by_user` in the trail, zero unsettled calls in the final draft |
| 9a | Cancel mid tool round (reads) | `test_a_stop_mid_round_gives_up_the_reads_that_were_in_flight` | pass — both in-flight reads settle `error/cancelled` with `dispatched is True`; no further route call bought |
| 9b | Write barrier crossing the stop | `test_a_write_crossing_the_stop_happens_once_and_a_second_stop_adds_nothing` | pass — counting handler ran **exactly once**, the read queued behind it settles `error/cancelled` with `dispatched is False`, and a second `cancel` returns the same `cancel_requested_at` with no second effect |
| 10 | Disconnect / replay | `test_a_dropped_tab_rebuilds_the_whole_turn_from_a_fresh_snapshot` | pass — the 2-deep tab is dropped at seq 3 while the Turn runs on; a mid-Turn resubscribe restates exactly the events published up to its `through_seq` (text/thoughts/tool_calls/progress); after the terminal the publisher's snapshot text == the concatenation of every answer delta == `message["answer"]`, and the checkpoint-based subscriber is closed, carries `through_seq == last published seq == record.last_event_seq`, and shows no `running\|pending` call |
| 11 | Shutdown / sweep | `test_a_turn_a_restart_caught_mid_write_is_frozen_with_nothing_running` | pass — the intent is `pending` in the checkpoint before the effect runs; the task is killed mid-write; a fresh service's `sweep()` freezes it `incomplete/interrupted_restart` with `error/interrupted` on the call, the prose kept and the trail byte-identical to what the dead build had written |
| 12 | Question, three states | `test_a_card_survives_the_publisher_the_terminal_and_a_reopened_thread` | pass — event order is `part.question` then `turn.completed`; a late subscriber's snapshot still shows the card `pending`; the checkpoint snapshot carries `question: null` (the amended row); `answered` (+ `selected_option_ids`), `skipped` and `superseded` (fired by creating the next Turn) each read back through `read_thread` with the card itself unchanged |

## The two cross-cutting properties

Both are asserted for **every** row above, in one helper each row calls
(`settled_turn`):

- **Typed terminal.** `record.status` ∈ `{complete, incomplete, cancelled}` and
  `record.terminal_reason` is `None` or a member of a vocabulary assembled from
  the modules that write it (`loop` reasons, `ADMISSION_STATUS` keys,
  `shutdown`/`turn_failed`/`interrupted_restart`) — not a hand-copied list, so a
  reason invented at a call site fails the gate and a reason added to `loop.py`
  does not require editing the test.
- **No orphan tool state.** No `running`/`pending` call in `draft_content`, in the
  canonical message content, or in the snapshot `snapshot_from_draft` rebuilds
  from the persisted row.

## Defects found

**None.** No production file was touched; `git status` after the commit is clean
apart from this report.

## Evidence the gate is not vacuous (mutation probes, all reverted)

| Mutation in `src/` | Caught by |
|---|---|
| `messages.settle_orphan_calls` returns its input unchanged | `…repeats_a_call_id…`, `…restart_caught_mid_write…` (2 failed) |
| `loop.AgentLoop._settle_orphans` returns immediately | *not* caught by this file — caught by the existing `test_agent_loop.py::test_a_turn_that_ends_leaves_no_call_waiting` and `::test_a_cancelled_turn_settles_what_it_was_waiting_on_as_the_cancel` (that path is only reachable through the one-result-short injection those two own) |
| `executor.run` routes a started sequential barrier through the cancellable path | `…write_crossing_the_stop…` |
| `loop._complete` ignores `cancel_event` | `…stop_mid_model_call…` (and the file's runtime rose from 0.7 s to 5.8 s, which is the latency assert doing its job) |

Two asserts were found vacuous during writing and fixed rather than kept:
the mid-Turn snapshot's answer text (answer deltas only exist immediately before
the terminal, so the claim is now made on the post-terminal publisher snapshot as
well), and "compression gave ground" (message *count* is unchanged at this
ceiling — the ladder collapses results rather than dropping turns — so the assert
is on prompt characters).

## Verification (host, this branch)

```
pytest tests/test_agent_fault_injection.py -q            → 14 passed (3 consecutive runs, no flake)
pytest <phase gate: fault_injection lanes parts loop turn_lifecycle turn_events turn_sse> -q
                                                        → 296 passed
pytest -q                                                → 1283 passed, 3 deselected  (baseline 1269 + 14)
python3 -m compileall -q apps/api/{src,tests,golden}      → clean
git diff --check                                         → clean
```

## Notes for whoever reads this next

- The suite reuses the fixtures and fakes it needs by importing them
  (`FakeClient`, `StallingClient`, `entry`/`install`, `long_history`,
  `_answers_one_call_short` from the loop tests; `owner`, `schema`, `_tools`,
  `service`, `store`, `thread_for`, `messages_of`, `narrating`, `answer`, `card`,
  `committed_turn` from the lifecycle tests). Nothing was extracted into a new
  shared module: three local helpers (`narrated_batch`, `gated_tool`, `restated`)
  are all the file added.
- `dispatched` is deliberately absent from `TurnToolCall.as_wire()`, so the two
  rows that assert it (7 and 9) read it off the loop's own last draft
  (`RunningTurn.draft.tool_calls`) rather than off a wire payload that does not
  carry it.
- One private touch, commented and `noqa`'d: the replay row sets the publisher's
  `_queue_size` to 2 before subscribing the tab that stops reading. Filling the
  real 256-deep queue would be measuring the constant instead of the drop.

## Unresolved questions

1. **`dispatched` never reaches a reader.** The wire payload and therefore the
   transcript and the replay snapshot omit it, while the Tool Call Trace keeps it
   inside `result`. For a cancelled or interrupted write, "was this effect
   possibly applied?" is exactly the question a reader (or an operator) asks of a
   recovered Turn, and today it is answerable only from the trace table. Whether
   that is a gap belongs to whoever owns the surface for interrupted writes
   (Phase 7 renders, Phase 9 operates) — flagged, not changed.
2. **A Turn that says nothing writes no message.** Rows 2, 5 and 6 settle typed
   with a reason but leave no assistant row, so their trail survives only in
   `draft_content`. That is the existing rule (`text` empty → no message), and
   the gate accepts it; if a reason-only bubble is wanted, it is a UX decision
   for Phase 7 rather than a lifecycle bug.
3. **The startup sweep is deployment-wide.** `sweep()` freezes every active Turn
   in the database, so the row-11 test would also freeze another process's
   in-flight Turn if one existed against the same dev database. Harmless in the
   suite (the pre-existing lifecycle tests already do this), worth knowing before
   anyone runs the suite against a shared database.
