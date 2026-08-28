# Turn `mode` — the Signal Desk switch as a backend promise

Backend only. No `apps/web/**`, no `src/studies/**`, no `src/stocks/**`, no
migration, no new table, no change to `CHAT_TOOLSETS`.

## What was built

**1. `mode` on the request.** `CreateTurnRequest.mode: TurnMode = "chat"`.
`TurnMode = Literal["chat", "signal_desk"]` is declared once, in
`src/agent/loop.py`, and imported by the schema — the loop is what behaves
differently, so it owns the vocabulary and the wire shape restates it rather
than spelling the two values a second time.

Persisted on the **user message content** (`agent_message.content`), beside
`text` and `symbols`, which is where the Turn's other request-shaped facts
already live. `agent_turn` has no column for it and none was added. Written only
when it is not `chat`, exactly as `symbols` is omitted when empty: the payload is
the idempotency key, so an always-present key would make the same question asked
before this existed compare unequal to itself. Consequence, tested: the same
`turn_id` asked once from chat and once from the desk is a **409**.

**2. What `signal_desk` changes.**

- Every model call of the Turn carries one extra system message
  (`loop.SIGNAL_DESK_NOTE`), priced at the existing `SYSTEM_NOTE_TOKENS`
  reservation and reserved in `_construct` so the trimming ceiling and the
  request agree. Per call rather than once, unlike `state.note`: a mode holds for
  the whole Turn.
- `tool_choice` stays `"auto"`. Nothing is forced.
- `TurnOutcome.canvas_absence: str | None` is computed in `AgentLoop._ended` —
  the one funnel every terminal path runs through, including deadline,
  cancellation and route failure — as `canvas_absence(state.calls)` whenever the
  mode is `signal_desk` and no canvas was announced. `None` for every `chat`
  Turn and for any Turn that drew something.

**3. Where the reason surfaces.** Two paths, one code:

- terminal SSE event: `data.canvas_absence` (only when there is one);
- canonical assistant message: `content.canvas_absence` (only when there is one),
  so a reopened Thread renders it without the stream.

**4. Reason vocabulary.** `messages.canvas_absence()` reads the `outcome` the
loop already computed per call (`outcome_of`), so the completion and the Tool
Call Trace cannot disagree. The last canvas-producing call decides.

| situation | code |
|---|---|
| Study refused for data reasons | `no_value:<signal issue>` (e.g. `no_value:insufficient_sessions`) — existing |
| Study/`render_canvas` declined the question | `cannot_read` — existing |
| the call never ran or broke | the executor's own error code: `tool_failed`, `tool_timeout`, `unknown_tool`, `blocked_call`, `external_budget_exhausted`, … — existing |
| the model reached for no canvas-producing tool at all | **`no_canvas_tool_called`** — the one new code |

`src/alpha/reasons.py` was **read and not extended**. The one new code is not a
Signal Issue and could not honestly be made one: it is a fact about the round,
not about the store, and inventing an issue for it would put a claim about data
on a Turn that never asked the store anything.

**5. Prompt.** One paragraph added to section 4 of `prompt/sections.py` (the
Signal Desk rule; framing rules explicitly unchanged), `PROMPT_VERSION`
2.7.0 → **2.8.0**.

## Files modified

| file | note |
|---|---|
| `apps/api/src/agent/loop.py` | +~75: `TurnMode`/`CHAT_MODE`/`SIGNAL_DESK_MODE`, `SIGNAL_DESK_NOTE`, `TurnRequest.mode`, `_TurnState.mode`, note + reservation, `TurnOutcome.canvas_absence` |
| `apps/api/src/agent/messages.py` | +~50: `NO_CANVAS_TOOL_CALLED`, `canvas_absence()` |
| `apps/api/src/agent/schemas.py` | +12: `CreateTurnRequest.mode` |
| `apps/api/src/agent/router.py` | +5: carries `payload.mode` through |
| `apps/api/src/agent/prompt/sections.py` | +7 prose, version bump |
| `apps/api/src/agent/turns.py` | **outside the stated ownership list** — `create(mode=…)`, `assistant_message(canvas_absence=…)`, terminal event data |
| `apps/api/src/agent/persistence.py` | **outside the stated ownership list** — `create_turn(mode=…)`, one key on the request payload |

Tests: new `apps/api/tests/test_agent_signal_desk.py` (12); extended
`test_agent_turn_lifecycle.py` (+5), `test_agent_transport.py` (+3),
`test_agent_prompt.py` (+2), `test_agent_study_tools.py` (+1),
`test_agent_loop.py` (note-reservation loop now covers `SIGNAL_DESK_NOTE`).

`tests/test_agent_capability_contract.py` needed **no** change: the tool schemas
did not move, and its hash lock still passes. (Another agent has that file open
concurrently for unrelated widget/study work.)

## Tests

- `cd apps/api && make test` → **1283 passed** (baseline 1260 + 23 new). 36s.
- `make lint` → clean.
- Coverage of the acceptance list: default `mode` unchanged (no note in the
  request, no `canvas_absence`, no `mode` key in the stored payload, repeat POST
  still 200/`created: false`); a desk Turn that drew a canvas; one that drew none
  and reports `no_canvas_tool_called`; one whose Study refused with
  `insufficient_sessions` reaching the completion; `cannot_read`; a failed call;
  a Turn whose tools timed out; the last-attempt rule; and the frames law
  extended to a whole `signal_desk` Turn driven through the loop against the
  real `run_study` registration.

## Deviations and findings

1. **File ownership.** `turns.py` and `persistence.py` were not in the given
   list, but "persist it with the turn" and "the loop must know the mode" cannot
   be done without them — `TurnService.create` is what builds `TurnRequest` and
   what calls `create_turn`. Neither file is touched by the parallel `apps/web`
   task. Changes there are additive and defaulted.

2. **One new code**, `no_canvas_tool_called` — justified above. The frontend will
   need a sentence for it plus the existing `no_value:<issue>` / `cannot_read` /
   executor-error vocabularies it already renders beside tool calls.

3. **`_finish_bare` carries no `canvas_absence`.** A Turn killed by the wall
   clock, a shutdown, or an unexpected exception never hands back a
   `TurnOutcome`; the account it gives is its `terminal_reason`
   (`turn_deadline`, `shutdown`, `turn_failed`) plus whatever the last checkpoint
   held. Inventing a canvas reason there would mean guessing at a Turn that never
   finished. The same applies to `frozen_message` after a restart.

4. **Pre-existing leak path found while testing (not fixed — outside my files).**
   When the artifact insert fails, the SQLAlchemy exception text becomes the
   tool's `result_text`, and that text embeds the bound parameters — including
   the whole `frames` JSON. My first draft of the transcript guard hit exactly
   this by using unstored owner ids (FK violation), and the frames appeared in
   the messages the route was sent. In production both ids are committed before
   execution, so this needs a database failure to trigger, but the rule "frames
   never enter a message" is currently only true while the write succeeds. The
   fix belongs in `src/agent/tools/studies.py` or in the executor's error text
   (`executor.py`, `except Exception … f"{call.name} failed: {exc}"`), neither of
   which I own. Worth a follow-up.

## Unresolved questions

- The task asked for the contract-hash test to be "updated deliberately". No test
  pins the prompt hash literal — `tests/test_agent_prompt.py` hashes the prose
  and asserts only that the hash moves. I added
  `test_the_version_names_the_prose_this_build_actually_ships`, which pins
  `PROMPT_VERSION == "2.8.0"` with a comment saying what 2.8.0 changed, so a
  future bump is a decision rather than a silent edit. Say the word if a
  different lock was meant.
- `canvas_absence` is not carried on the **checkpoint** (`TurnDraft`), only on the
  terminal event and the final message, because it is only known at the end. A
  browser reconnecting mid-Turn learns it from the terminal event it will still
  receive.

Status: DONE_WITH_CONCERNS
Summary: `mode` now travels request → committed payload → loop → completion, and a `signal_desk` Turn either announces a canvas or names why it could not; `make test` 1283 passed, `make lint` clean.
Concerns/Blockers: two files outside the stated ownership list were needed (`turns.py`, `persistence.py`); one new reason code (`no_canvas_tool_called`) that the web app must render; and a pre-existing frames-in-error-text leak path found while testing, reported rather than fixed because it lives in files I do not own.
