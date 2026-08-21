# A round of tool results has a context ceiling, and a repeated call has a ladder before it

Two bounds are added to the agent loop, both decided by pure functions outside it.

**A round's results are measured together.** Each tool already bounds its own
output at `MAX_TOOL_RESULT_BYTES`, and that is the only bound there was. A round
whose results together claim more than a quarter of the constructed-context budget
now has its largest result replaced by a **preview**: the envelope, the citable
fields and the first rows, plus a reference stating what was left out and how much
of it there was. The whole result stays in `agent_tool_call`, addressable by the
call id the model cites it under.

**A call the Turn already made and had answered walks a ladder** — allow, warn,
block, halt — instead of being dispatched again and again. A halt ends the *tool*
loop and not the Turn: the next call is the answering one, made with
`tool_choice="none"` over the evidence already gathered.

Neither bound is a retry policy. `core.llm.errors.ToolAttempts` owns retries — two
attempts on a tool that *failed*, spent before dispatch by `admit_round` — and it
is untouched. A failed call is deliberately not shown to the ladder at all, so the
second attempt the retry policy exists to allow cannot be refused by a guardrail
counting the same event twice.

## What the numbers are, and why they are not the ones we borrowed

The pattern comes from a survey of `nousresearch/hermes-agent`
(`plans/reports/hermes-synthesis-260821-0030.md`), which warns after two identical
failures and halts after eight. Copying eight would have produced a guardrail that
never fires: `MAX_TOOL_ROUNDS` here is **4**, so a Turn cannot show eight
repetitions, and a rung placed past the budget is decoration. The thresholds are
therefore a function of the round budget, passed in as `max_rounds` — which is
also why a test can ask what the ladder looks like at two rounds and at eight.

At four rounds the ladder reads: the second identical call is warned and still
dispatched, the third is refused before dispatch, and a fourth halts the tool
loop. An effect-capable tool skips the first rung — reading the same rows twice is
a wasted round, writing the same fact twice has a consequence.

**Only a repetition halts, and a halt keeps its round.** Two boundaries were drawn
after the first version of this got both wrong, and each is a way a guardrail can
cost more than the failure it prevents:

- A tool that keeps coming back **empty** is warned and never halted. Emptiness is
  read from a Structured Refusal, and refusals arrive in ordinary bunches — three
  symbols outside the Universe, three searches while the open web is down, three
  windows too short for the field. Counted per tool and ignoring arguments, a halt
  there ended the tool loop over a question the Turn had not yet asked.
- The call that earns a halt is refused; **its siblings still run**. A round is
  emitted whole, so the calls beside a repetition may be the first time this Turn
  asked for what they ask for. The halt takes the loop — the next call is the
  answering one — rather than the round.

**A copy inside one round is blocked outright**, whatever rung the ladder would
have reached. The rungs are about a model asking again after reading an answer, and
inside one round nobody has read anything: a round is emitted whole, so every call
in it was decided before any of them ran. The first call runs and the copies are
answered by it. The one exception is a repetition the Turn's own history already
halts on, which is not the round's doing.

**An unknown tool is a write.** Anything not named in `IDEMPOTENT_TOOLS` — every
MCP tool, every plugin, anything added later and not classified — is treated as
effect-capable. Guessing "harmless" about an unknown write is the only guess here
with a consequence.

The spillover thresholds are measured rather than chosen. Over sixty days of
stored traces the largest result any tool produced was **2,267 bytes** against a
per-tool cap of 4,096, the mean was about 1,200, and the fattest Turn on record
produced 61 KB across 62 calls and four rounds. So:

- the per-tool threshold defaults to three quarters of the cap, which is above
  every result in that history. It fires on the two cases that are *not* in it: a
  tool whose payload grew, and an MCP tool whose shape nothing here has seen;
- the round ceiling is a quarter of the constructed-context budget, which that
  history does not reach either. Rung three is for the round that fans out further
  than any round yet, not a tax on the ones that do not;
- **six tools declare the full cap and so never spill**, because for them the
  bulk *is* the answer: `web_search` and `fetch_url` (a second clipping of an
  already-clipped page, at a boundary nobody read), `screen_universe` (a screen is
  asked for its tail), `search_news`, `get_analysis` (clipped prose reads as
  finished prose), and `get_financials` — whose periods list is both the answer to
  the question this tool was widened for and the binding a
  `quarterly_financials` Widget resolves.

A **declaration** is honoured at both rungs, and that is a correction worth
recording rather than a detail. Rung three asks a result for the bytes the round
is over by, and it sorts largest-first — so the tools declaring the full cap are
exactly the ones it reaches for. Left unfloored, a fat round would have answered a
question about eight quarters with three and pinned the Widget's descriptor to
those three forever. The floor is the *declaration* and never the resolved
threshold: after rung two every result already sits at or under its threshold, so
flooring at that would leave rung three nothing to give. A round that still does
not fit is reported as `over_ceiling` instead of being shrunk past what its
results are for.

`context_overflow` has been **zero** in the measured window. That is stated here
rather than hidden, because it is the honest reading of what these two rungs are:
a guard armed above measured traffic, not a fix for an observed failure. The plan
this work comes from names the alternative explicitly — if the count stays at zero
and nothing spills, the mechanism cost a page of pure functions and no behaviour.

## Where the declarations live

A tool's result budget is declared on its registration
(`ToolSpec.result_budget_bytes`) and read back as a table
(`ToolCatalog.result_budgets`). It is a property of the shape a tool returns, so it
belongs beside the schema where a reviewer meets it, and a second table inside the
spillover module would be a second place for the two to disagree. Resolution order
is `pinned > config > registry > default`: a caller may pin one call's threshold,
the loop builds the table from the catalog, and anything undeclared takes the
default.

## What a preview may never drop

Three groups of keys are preserved whatever it costs, and each is a failure the
preview would otherwise cause somewhere else:

| Preserved | Why |
| --- | --- |
| `registered_fields` | the Recommendation Validator resolves citations into it; a clipped one costs the Turn a figure through `unknown_field_path` |
| `data_ref` | the Widget Validator resolves it; a spill descriptor written into that key would turn every widget bound to a spilled series into `wrong_binding` — which is why the spill reference is `spilled_ref` |
| `reason`, `error`, `available`, `unavailable`, `unavailable_reason`, `symbol`, `as_of`, `window_health`, `tool`, `tool_call_id` | the envelope every caller branches on, and the identity a figure is cited by |

The preview is also **not** the collapse the context ladder already performs.
That one replaces an *old* tool result with the line *called X with arguments Y*,
which is right for a result the model has already reasoned over and wrong for one
it has not seen yet. A spilled result belongs to the round just finishing, so its
preview has to carry enough shape for the model to plan the next move.

**The trail is projected before the spill, never after.** `progress.sources_of`
reads the tool result, so previewing first would shorten the source list under an
answer by however much a context budget the reader cannot see happened to remove.

## Recovery hints

A refused tool hands the model a code and a shape. The code is honest and inert:
nothing in it says what to do instead, and the measured behaviour is a Turn that
calls the same tool again with the same arguments and is refused again on the same
code. Each refusal code the tools actually produce now carries **one sentence
naming the next action**, from a closed table in `tools/catalog.py`.

Four rules keep it from becoming a second prompt: only on a refusal, at most one,
an action rather than a diagnosis, and written in the table rather than assembled
per call so two Turns refused the same way read the same. A tool that wrote its
own hint keeps it, and a hint that would push a result past its budget is dropped
— the refusal is the product, the hint is the garnish.

Window-health refusals get their own table. Those arrive on a result that
*answered*, with one field inside it that could not be computed, so the action is
about the field: ask for one computed from a shorter window, or say the history is
too short.

## Consequences

- Two nullable columns on `agent_tool_call`: `tool_call_id`, which finally lets a
  citation be joined to the row holding the result it names, and `spilled_bytes`,
  which is how a threshold becomes tunable against measurement. Migration
  `a4c71d9e5b28`, additive, no backfill and no index.
- `ToolCatalog.dispatch` takes the route's `call_id`. Tool schemas are untouched,
  so **`tool_catalog_version` does not move** and the Eval Fixture is not
  re-frozen. The `hint` key is additive on refusal envelopes and nothing branches
  on it.
- The loop reserves `GUARDRAIL_NOTE_TOKENS` when a nudge is pending, and truncates
  the note to that reservation. The budget that funds a call and the message that
  goes out cannot disagree, which is the property `REPAIR_NOTE_TOKENS` already
  holds.
- Guardrail decisions are recorded in the structured log and **not** in the ops
  query. The plan's own signal that this ADR stopped working is a halt count that
  stays at zero forever, and counting halts needs a per-Turn record the schema does
  not have — a Turn that halted still completes normally. Adding one is a change to
  ADR-0016's fixed query and is deliberately left for the phase that reads it.
- The agent loop changed, so a pull request carrying this owes an Eval Report
  (`CLAUDE.md`).
