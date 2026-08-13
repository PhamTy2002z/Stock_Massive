# The agent loop is hand-rolled in `apps/api`, over the `LLMClient` boundary

The loop lives in `apps/api` (Python), in a new `src/agent/` package, written by
hand over an `LLMClient` protocol in `src/core/`. No agent framework is adopted:
not LangGraph, not pydantic-ai, not the OpenAI Agents SDK, not the Anthropic SDK's
`tool_runner`. A **Turn** is the unit of every ceiling in the system.

## Why `apps/api` and not Next.js

Everything the loop needs is already there: the store, the Provider Source
adapters, the quota logic, the Universe, the scheduler, and the sync
`SnapshotStore`. `apps/web` gains one route plus a Next Route Handler proxy
(ADR-0013) and nothing else.

## Why hand-rolled

1. The route is a config flip by design (ADR-0014), and every framework marries
   one client abstraction — precisely where the `LLMClient` boundary already
   exists for three other reasons: the boot-time **Capability Probe**, the
   JSON-parse invariant on tool arguments, and `auth_unavailable` as a
   first-class error class.
2. The failures on this channel class are **silent**. A gateway was measured
   keying streamed tool calls on a counter instead of the upstream
   `output_index`, concatenating two calls' arguments into invalid JSON under the
   wrong id — while returning 200. A framework hides exactly the seam that needs
   an assertion.
3. There is no graph to orchestrate. The twelve tools of ADR-0009 are plain
   functions over the service layer.
4. `requirements.txt` already pins `vnstock>=4,<5` because a dependency changed
   behaviour silently. A framework with its own provider opinions invites the
   same class of risk into the newest, least-understood part of the system.

**The cost, stated plainly:** a few hundred lines of dispatch, retry, trimming,
and streaming that we write and own, and correctness is ours.

## Considered Options

- **LangGraph / pydantic-ai / Agents SDK / `tool_runner`.** Each buys dispatch,
  retry, and streaming we would otherwise write, and each costs the seam in
  reason 2. The trade is not "less code versus more code"; it is "less code
  versus an assertion we can place".
- **Hand-rolled in TypeScript inside `apps/web`.** Rejected: it puts the loop on
  the far side of the store, the quota arbiter, and `prepare_bars()`, so every
  tool becomes an HTTP hop and the Universe check moves further from the data
  that decides it.

## What the loop guarantees

- **`build_messages(thread, budget) -> list[Message]` is a pure function outside
  the loop**, so all trimming is testable with no LLM involved.
- **Parallel calls dispatch through `asyncio.gather(..., return_exceptions=True)`**
  so one failing tool does not kill the round, and **every result is asserted
  against its own `tool_call_id`** before it goes back to the model. That single
  assertion is what turns reason 2's silent corruption into a loud failure.
- **Eight tool-call rounds per Turn**, counted by round rather than by call.
  On the ceiling, one further call with `tool_choice="none"` lets the model answer
  from what it has, and the transcript states that all eight lookup steps were
  used — information, not an error. An answer built on incomplete data beats a
  blank one, provided its incompleteness is visible.
- **Cancellation stops after the in-flight tool call completes.** Every tool is
  read-only, so there is nothing to roll back, and a half-cancel path costs more
  than the call it would save. The partial assistant message persists as
  `cancelled` with the traces of what ran.
- **Five error classes with distinct behaviour**, and `malformed_arguments`
  raises immediately rather than handing garbage back for the model to guess at.
- **No auto-disable of a route.** `malformed_arguments` is counted and logged
  loudly; the operator flips `alpha_desk_enabled` by hand. A cutoff that fires on
  two errors is a mechanism that can cause its own outage, and with a handful of
  internal users whoever notices is also whoever can fix it.

## What the prompt may carry

The system prompt injects **only what no tool can supply**: user identity (out of
band), the current **Trading Day** under its data-defined meaning, market state as
a short string, and the active symbol if there is one. The Watchlist is *not*
injected — it is fetched through `get_watchlist()`, because injecting it creates
two sources of truth for the same data inside one Turn. **No figure is ever
injected**: that is the whole point of the summary-with-declared-units contract.

Market state is injected deliberately. Without it the model calls yesterday's EOD
close "the current price", and no tool can catch that sentence.

## Consequences

- The **Capability Probe** runs inside `lifespan`, immediately after
  `get_universe()` and before the scheduler starts. With `alpha_desk_enabled`
  true, a failing probe refuses startup. This reuses an existing precedent whose
  own comment already argues the case — *the operator should meet the failure here
  rather than hours later inside a run nobody is watching*.
- Concurrency is an in-process `asyncio.Semaphore` of **3 sessions**, correct
  because uvicorn runs a single worker; the 4th Turn is refused `503` and never
  queued. Queueing behind a 60-second Turn puts the user in front of a spinner
  with no estimable end.
- Context trimming drops **old tool results first** — zero audit loss, since they
  are stored whole in `agent_tool_call` — then caches one summary as an
  `agent_message` with `role = 'summary'`, needing no schema beyond the
  persistence model.
- Models split **by workload, never inside the loop** (`llm_model_session` /
  `llm_model_batch`). An in-loop cheap-router split adds a decision point whose
  quality cannot be measured until the Eval Battery exists, and it cuts into
  exactly the reasoning that produces the value.
- Revisit when the API needs more than one worker: the semaphore becomes a
  distributed lease, and the process-local Turn registry of ADR-0013 becomes a
  shared one. Both are consequences of the same change and should move together.
