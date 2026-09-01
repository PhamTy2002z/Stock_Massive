# Task 5 — question part: schema, table, terminal seam, endpoints, three states

Branch `feat/phase-03-durable-loop-lane`, one commit `eeb7f2f`. Worktree was
clean at `522cf04` before starting. Backend only; no `apps/web` change.

## What landed

### 1. Part (`apps/api/src/agent/parts.py`)

- `QuestionOption` (`parts.py:330`) and `QuestionPart` (`parts.py:357`), both
  frozen. `question_id` is validated as a UUID (it is the row's PK), prompt and
  labels are non-empty and capped, options are coerced to a tuple, counted
  2–4 and their ids must be distinct. `multi_select` defaults False,
  `skip_label` defaults to `DEFAULT_SKIP_LABEL` = "Bỏ qua — dùng giả định mặc
  định" (roadmap §1.4).
- **Validation raises here, unlike progress which drops** (`parts.py:52-72`
  docstring): a malformed progress part must never end a Turn, a malformed
  question has no safe reduced form — a card with no answerable option is a dead
  end.
- States are module constants, not part fields: `QUESTION_PENDING|ANSWERED|
  SKIPPED|SUPERSEDED` + `QUESTION_STATES` (`parts.py:255-283`).
- `QUESTION_WIRE_FIELDS` (`parts.py:309`) is the one declaration of the wire
  shape; `question_option_ids(payload)` (`parts.py:415`) is the one reader of a
  stored question's options, used by the store to validate an answer.

### 2. Table (`apps/api/src/alpha/models.py:367` `AgentQuestion`)

`id Uuid PK` (= the part's `question_id`), `thread_id`/`turn_id` FK CASCADE,
`message_id` BigInteger FK **SET NULL**, `user_id` FK CASCADE, `payload` JSONB,
`state` String(16), `selected_option_ids` JSONB nullable, `created_at`,
`resolved_at`, `Index(thread_id, state)`. Docstring gives the reason it is its
own table (same split `agent_turn` exists for) and why `user_id` is a column
rather than a join (these rows are reached by question id alone, with no Thread
in the path).

### 3. Migration

`apps/api/alembic/versions/d3f6a1c82b47_record_a_question_and_what_became_of_it.py`
— revision `d3f6a1c82b47`, `down_revision = c4e8a1f70b62` (the verified head:
`alembic heads` → `c4e8a1f70b62 (head)`). Additive; downgrade drops index +
table. `alembic/env.py` gained `AgentQuestion` in its explicit ORM import list.

Verified on a **throwaway database** (`CREATE DATABASE stockmassive_qmig_*` on
the same server, dropped afterwards), never against the configured shared URL:
`upgrade head` → table + index + 4 FKs exactly as declared → `downgrade -1` →
`information_schema` count 0, `alembic current` back to `c4e8a1f70b62` →
`upgrade head` again → clean.

### 4. Persistence (`apps/api/src/agent/persistence.py`)

- `finish_turn(..., question=…)` (`persistence.py:1265`) → the row is inserted
  in the **same** terminal transaction as the assistant message
  (`persistence.py:1327`, helper `_pending_question` at `:507`, which resolves
  the owner from the Thread rather than taking it as an argument). A question
  without a message raises. First-terminal-wins unchanged, question included
  (test pins it).
- `answer_question` (`:1358`) / `skip_question` (`:1384`) / `read_question`
  (`:1343`) → owner-scoped by `_owned_question` (`:1398`), transitions only from
  `pending`, same outcome repeated returns the row untouched (stamp does not
  move), conflicting change raises `QuestionAlreadyResolved` (409),
  bad/empty/too-many ids raise `QuestionOptionInvalid` (422). Skip stores NULL
  and not `[]` — "chose nothing" is what a skip is.
- Supersede runs inside `_create_turn`'s existing transaction
  (`persistence.py:1145-1160`), scoped to the Thread, only for `pending` rows so
  a settled card keeps its stamp.
- **Merge point (one, pinned):** `read_thread` (`:579`). One indexed query per
  Thread open builds a `question_id → row` map and `_message_record(row, states)`
  merges `state` + `selected_option_ids` **inside** the content's `question`
  object (`_with_question_state` at `:362`). The DB row keeps what was written.
  A card whose row is gone is left exactly as written (no invented `pending`).

### 5. Draft-settler seam — chose **relocation**, not a callback

`settle_orphan_calls` moved to `messages.py:105` (re-exported from `turns.py:74`,
so `turns.settle_orphan_calls` and its existing test still resolve). `_freeze`
now also rewrites the checkpoint via `_settled_draft` (`persistence.py:477`),
and only when something is actually unsettled, so an ordinary interrupted Turn's
column stays byte-identical.

Why relocation over `freeze_interrupted_turns(message_builder, draft_settler=…)`:
the function is pure and reads `UNSETTLED_STATUSES` / `CALL_INTERRUPTED` /
`ToolCallStatus`, all of which live in `messages.py`; `persistence` already
imports sibling agent modules (`.loop` for `CHAT_MODE`), so nothing about the
layering changes. A settler passed in as an optional callback is a parameter a
future caller can forget — which is precisely the bug being fixed (task 3's
report note 1).

### 6. TurnService seam (`apps/api/src/agent/turns.py:665`)

`settle_with_question(running, *, text, question_part)` → `assistant_message`
gains a `question` key (written **only** when there is one, so a questionless
message is byte-identical to before, `turns.py:296-320`), `finish_turn(status=
complete, terminal_reason=None, question=…)`, then `publisher.question(...)`,
then the terminal event. `last_event_seq` is persisted as `next_seq + 1` because
two events follow the commit. The loop's last checkpoint is left untouched. The
docstring states plainly that no production path calls this in this phase.

### 7. SSE (`events.py`) — additive only

`EventType.PART_QUESTION = "part.question"`, `TurnPublisher.question(part_wire,
state=pending)` (allowlisted by `QUESTION_WIRE_FIELDS` + `state` +
`selected_option_ids`), `_remember` keeps it, the subscribe snapshot gains
`"question"` (None when the Turn answered instead). `snapshot_from_draft` gains
the same key, always `None`, with the reason in a comment. `ENVELOPE_VERSION`
unchanged; the other event shapes untouched.

### 8. HTTP (`router.py`, `schemas.py`) — additive only

`POST /api/v1/questions/{question_id}/answer` `{selected_option_ids:[…]}` and
`POST /api/v1/questions/{question_id}/skip` (no body), both `CurrentUser`,
owner-scoped, 200 `QuestionResponse{id,state,selected_option_ids,resolved_at}`,
404 unknown/foreign, 409 conflicting change (`question_already_resolved`), 422
option not offered (`option_not_offered`) or empty list (schema). Existing
endpoints untouched.

## Tests (+36; the whole delta is new tests)

- `test_agent_parts.py` (+10): outcome vocabulary, `multi_select` default, skip
  label, wire shape = `QUESTION_WIRE_FIELDS`, 1/5 options refused, duplicate ids
  refused, empty/over-long prompt-label-detail refused, non-UUID id refused,
  list→tuple + frozen, `question_option_ids` read defensively.
- `test_agent_persistence_paths.py` (+14): message+row in one transaction
  (message_id/turn_id/user_id/pending); a Turn that answered carries no
  `question` key at all; question without message refused; answer idempotent
  (stamp does not move); conflicting change 409-shaped, row unchanged; skip is
  NULL not `[]`; option validation matrix incl. multi-select; owner scoping (a
  second account, and an unknown id); supersede fires inside `create_turn`,
  Thread-scoped, and does not re-settle a resolved card; all three states via
  `read_thread`; missing row leaves the card as written; **freeze settles the
  checkpoint** (regression for task 3 note 1) and does not rewrite a clean one;
  first-terminal-wins with a question.
- `test_agent_turn_lifecycle.py` (+5): `settle_with_question` settles
  `complete`/None with the part in the transcript; `part.question` **then**
  `turn.completed` on the stream with the persisted seq = the terminal's;
  post-terminal snapshot carries the card; a Turn that asked nothing has
  `question: None` on both snapshot producers; each of the three outcomes read
  back off a reopened Thread with the card itself unchanged.
- `test_agent_transport.py` (+7, `TestQuestions`): answer happy path +
  idempotency, multi-select belongs to the question (422 vs 200), unknown/empty
  option 422, skip idempotent, 409 on change, another reader's question 404 (and
  unknown id 404), and the reopened Thread drawing answered vs superseded (the
  supersede driven through the real `POST /threads/{id}/turns`).
  `alpha_schema` fixture now creates `AgentQuestion.__table__`.

## Verification (host)

```
pytest tests/test_agent_parts.py tests/test_agent_persistence_paths.py \
  tests/test_agent_turn_lifecycle.py tests/test_agent_transport.py \
  tests/test_agent_turn_events.py -q        → 161 passed
pytest -q                                   → 1268 passed, 3 deselected
python3 -m compileall -q src golden tests alembic → clean
git diff --check                            → clean
alembic upgrade head / downgrade -1 / upgrade head on a throwaway DB → clean
```

Baseline was 1232 passed / 3 deselected; +36 is exactly the new tests. No
existing test was changed except adding the new table to one schema fixture and
splitting the `owner` fixture in the persistence file into `_account()` so a
second reader (`stranger`) exists.

## Unresolved questions

1. **The plan's gate wording says "sống qua snapshot-from-draft và GET thread"
   (§7 matrix); I implemented durable replay through GET thread only, and
   `snapshot_from_draft` carries `question: None` by design.** A checkpoint
   cannot own this state honestly: the outcome changes *after* the Turn is
   terminal, so a draft-borne state would be the one view able to show a state
   the reader has already left. Making it work would mean either a store read
   inside `TurnService.subscribe` or writing the state into the draft on every
   transition. Which does Phase 3 want for task 7's matrix row — accept "GET
   thread is the replay surface" (my reading of plan §3, which says exactly
   that), or open the subscribe path?
2. **The shared dev DB now has `agent_question` created by `create_all`, without
   an alembic stamp** (it sits at `a4c71d9e5b28`, already many revisions behind
   head, so its schema is maintained by `create_all` in practice). If anyone runs
   `alembic upgrade head` against it, this revision will fail on "relation
   already exists". It holds 0 rows, so the remediation is one command
   (`DROP TABLE agent_question` before upgrading, or `alembic stamp`). I did not
   touch that database.
3. **`elapsed_ms` on a question message** comes from `running.publisher.elapsed_ms`,
   i.e. the wall clock of the process holding the Turn. Correct for a Turn the
   loop was running; for a P6 caller that builds a `RunningTurn` itself it will
   read as near-zero. Worth a look when the planner is wired to this seam.
4. **No `question` key in the draft/checkpoint**, so a question is not part of
   `draft_content`. If Phase 6 wants a Turn to be able to *re-publish* a card
   after a process restart, that would need the part in the checkpoint — a
   decision that belongs with whoever owns the ask policy.

Status: DONE
Summary: The question contract is complete and durable — typed immutable part,
its own table plus an additive migration verified up and down on a throwaway DB,
one terminal transaction that writes message and row together, owner-scoped
idempotent answer/skip endpoints with 404/409/422, thread-scoped supersede inside
the create transaction, and all three outcomes merged back into the transcript at
one pinned point; suite 1268 passed / 3 deselected.
Concerns: the plan's gate line mentions snapshot-from-draft replay, which I
deliberately did not implement (question 1); and the shared dev DB now holds the
new table without an alembic stamp (question 2).
