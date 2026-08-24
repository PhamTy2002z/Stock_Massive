# Resolved Capability Contract v1 — capability architecture inventory

## Scope and conclusion

The current harness already has a strong registration nucleus, but it does not yet
have one resolved capability object consumed end-to-end. `ToolEntry` owns model
schema, handler, availability inputs, display metadata, external-content
classification, sync/async dispatch, and per-result size
(`apps/api/src/agent/registry.py:116-174`). `definitions.get_tool_definitions()`
then resolves only the model-facing `ToolSchema` tuple
(`apps/api/src/agent/definitions.py:44-64`). Downstream consumers subsequently
re-read the mutable global registry or consult tool-name tables for execution,
concurrency, budgeting, display, trust, and telemetry.

This is exactly the H1 gap identified by the architecture documents: a
resolved declaration should unify schema, availability, provenance, mutability,
concurrency, budget, policy, and display, and consumers should migrate one at a
time without changing current observable behavior
([Harness roadmap](../../../docs/harness-roadmap.md#phase-h1--unify-capability-and-evidence-contracts);
[target architecture](../../../docs/Harness/target-architecture.md#capability-plane)).
The minimal v1 should deepen this seam only. It must not add MCP, plugins,
subagents, lifecycle persistence, new tools, or new product authority.

## Current owners and consumers

| Surface | Current owner / symbol | Consumers and present behavior | Evidence |
|---|---|---|---|
| Registration identity | `registry.ToolEntry`, `_ENTRIES`, `register()` | Tool modules register eight current names; registry refuses blank names/descriptions/display names and cross-toolset shadowing. | `registry.py:116-189`, `203-233`; `toolsets.py:39-64`; registrations at `agent/tools/web.py:299-356`, `memory.py:68-151`, `signals.py:270-342`, `price_check.py:119-159` |
| Trusted call scope | `registry.ToolContext` | Chat supplies user/thread/time; Analysis supplies symbol/trading day/time. Model arguments cannot select these trusted values. | `registry.py:84-113`; `loop.py:801-809`; `analysis_loop.py:259-267` |
| Lane allowlist | `toolsets.TOOLSETS`, `CHAT_TOOLSETS`, `resolve_toolset()` | Chat explicitly selects web, memory, and signals. Analysis selects only the signals bundle. Unknown toolsets and cycles fail closed. | `toolsets.py:25-64`, `67-110`, `110-159`, `180-198`; `loop.py:743-765`; `analysis_loop.py:461-478` |
| Availability | `ToolEntry.requires_env`, `check_fn`; `registry.is_available()` | A failed/missing probe hides a tool. Verdicts are cached for 30 seconds and dispatch checks availability again. | `registry.py:152-170`, `276-305`; `executor.py:292-319` |
| Model schema resolution | `definitions.get_tool_definitions()` | Expands toolsets, filters availability, preserves requested order, and caches a `ToolSchema` tuple by registry generation and selected toolsets. Chat resolves once at turn start; Analysis resolves once at run start. | `definitions.py:39-64`; `loop.py:794-810`; `analysis_loop.py:267-268`, `461-478` |
| Dispatch | `ToolExecutor.lookup`, `availability`, `_dispatch()`, `_invoke()` | Looks up a `ToolEntry` by name again, parses arguments, applies guardrails, invokes sync/async handler, and returns one settled `ToolResult` per call. | `executor.py:184-220`, `236-290`, `292-424` |
| Concurrency / ordering | `executor.PARALLEL_SAFE_TOOLS`, `plan_segments()` | Four hard-coded read names may overlap; every other and unknown name is a sequential barrier. Issued result order is preserved. | `executor.py:70-84`, `167-181`, `236-290` |
| External/store budget class | `ToolEntry.reads_external` plus global/injected lookups | Executor uses its injected lookup for per-round external/store ceilings; chat re-reads global registry for the per-turn external ceiling. Unknown is conservatively external. | `registry.py:159-170`, `338-347`; `executor.py:196-234`; `loop.py:279-292`, `1347-1373` |
| Result budget | `ToolEntry.max_result_size_chars`; registry accessor maps | Chat snapshots all declared caps into `TurnBudget`; Analysis re-reads the registry for each result. | `registry.py:174`, `332-373`; `loop.py:796-800`, `1429-1438`; `analysis_loop.py:338-345` |
| Human display | `ToolEntry.display_name`, `summary_detail_arg`, `summarise`; `messages.summarise_call()` | Call rows use registration metadata, but result cards and figure outcome remain name-specific projections. Wire `kind` is derived from the current registry at serialization time. | `registry.py:127-151`; `messages.py:200-248`, `268-313`, `326-355`; `loop.py:1347-1355`, `1405-1427` |
| Untrusted-content boundary | `untrusted.is_untrusted()`, `wrap_result()` | Message construction asks global registry whether a result is external; unknown names are wrapped conservatively and delimiters are defanged. | `untrusted.py:1-34`, `57-100`; `messages.py:380-402` |
| Trace / observer | Executor `_record()`, loop `_trace_writer()`, Analysis `_record_round()`, ops readers | Execution records names, results, failure codes, duration, and derived outcome. Ops derives the current external-name set from the registry, but one price-compliance rule names its tool explicitly. | `executor.py:476-514`; `loop.py:1473-1526`; `analysis_loop.py:202-216`, `590-619`; `ops.py:74-81`, `201-210`, `299-363` |

The two orchestrators intentionally remain separate. Chat owns thread,
publication, transcript, aggregate budgets, and turn lifecycle, while Analysis
has no user/thread/stream and reuses only the lower executor/guardrail/schema
seams (`analysis_loop.py:17-45`). v1 should share the resolved capability seam,
not parameterize or merge the loops.

## Duplicate name/policy tables and contract gaps

### Duplicates to remove through the resolved contract

1. **Concurrency allowlist:** `PARALLEL_SAFE_TOOLS` repeats four registered names
   (`executor.py:70-84`). It is already known to be a property distinct from
   toolset membership, but the property belongs on the declaration. This is the
   clearest current policy table that forces executor edits when a capability is
   added.
2. **Display/result projection names:** `messages.display_results()` branches on
   `web_search` and `fetch_url`, while `_FIGURE_TOOLS` separately names
   `get_field` (`messages.py:268-313`, `326-355`). Registration already owns row
   display metadata, so v1 should also own an optional safe display/outcome
   projector rather than growing more name branches.
3. **Repeated mutable-registry classification:** schema resolution, executor
   lookup, chat external budgeting, result wrapping, wire `kind`, Analysis result
   limits, and ops classification are independent reads. They are not literal
   duplicate tables, but they can observe different registrations during one
   turn (`definitions.py:53-64`; `executor.py:193-220`; `loop.py:1356-1367`;
   `untrusted.py:57-65`; `analysis_loop.py:338-345`; `ops.py:201-210`). A frozen
   resolved view is the missing owner.

### Name references that should remain explicit

- `TOOLSETS` and `CHAT_TOOLSETS` are intentional lane allowlists, not duplicated
  capability facts. Defaulting chat to every registered tool would broaden
  authority (`toolsets.py:67-79`).
- `ops.PRICE_CHECK_TOOL` is a domain-specific compliance metric, not a generic
  classification table (`ops.py:74-76`, `299-354`). It may reference a shared
  exported capability identifier, but should not become generic policy.
- Analysis `_STATUS_BY_ERROR` maps executor errors into a closed persistence
  vocabulary (`analysis_loop.py:202-211`). That is a trace projection boundary,
  not capability metadata.

### Missing contract fields

The current entry can express only a boolean external provenance, implicit
mutability via the executor allowlist, and an output-size cap. It cannot directly
declare:

- read/write/unknown effect and idempotency;
- parallel-read versus serialized/unknown ordering;
- internal/external/mixed provenance as a typed value;
- budget/policy class distinct from provenance;
- required trusted context / authorization scope and data sensitivity;
- inherited versus capability-specific deadline;
- approval and artifact policy;
- safe result display/outcome projection;
- stable handler identity and capability contract version.

These are the minimum target dimensions called out by
`target-architecture.md:156-167`. v1 should populate only values corresponding to
current behavior. Existing capabilities retain current approval, authorization,
deadline, and inline-result behavior; the contract must not silently grant new
authority or enforce a new refusal.

### Resolution gap

`get_tool_definitions()` returns schemas, not resolved capabilities. As a result:

- the model can be shown one registration while dispatch later uses a replaced
  handler or policy;
- a toolset-only mutation has no revision in the definitions cache key;
  `toolsets.clear_memo()` does not invalidate `definitions._CACHE`
  (`toolsets.py:107-164`; `definitions.py:39-63`);
- availability may change between offer and dispatch. Rechecking at dispatch is
  security-positive, but today all other properties can change with it;
- display and wrapping of a completed call can change if the global registry
  changes before the next message construction.

## Minimal v1 contract and invariants

Use two frozen concepts inside the existing registry/definitions boundary:

- **Declared capability:** the author-owned registration, extending `ToolEntry`
  with typed current policy (`effect`, `idempotency`, `provenance`,
  `concurrency`, budget/policy classification, display/outcome projector,
  handler identity, contract version). New fields need conservative defaults so
  existing direct constructors remain source-compatible during migration.
- **Resolved capability set:** an ordered, immutable per-lane/per-turn result with
  registry generation, toolset selection/revision, expiry, a tuple of available
  resolved entries, and a by-name lookup. Each resolved entry includes its
  `ToolSchema`, handler, and resolved current policy.

Load-bearing invariants:

1. Stable order and exact model-facing names/schema remain unchanged.
2. Unknown or incomplete metadata means external, serialized, unknown effect,
   no retry, and no elevated authority.
3. The executor dispatches only names in the resolved set and uses the same
   handler/policy snapshot the model was offered.
4. Availability is still revalidated immediately before dispatch so credential
   or feature revocation fails closed; revalidation may withhold a resolved tool
   but may not swap in a different handler mid-turn.
5. `ToolContext` remains the only source of trusted user/thread/symbol/day facts.
6. One call still produces one ordered result; existing error strings, timeout,
   fanout, guardrail, trace, and SSE semantics do not change.
7. External content remains wrapped at message construction. The classification
   used for the completed call is captured from its resolved entry; missing or
   legacy transcript metadata falls back to external.
8. No database, event version, endpoint, prompt, tool name, or toolset name
   changes in v1.

## Minimal implementation phases, files, and tests

### Phase 1 — Pin and introduce the contract

Files:

- `apps/api/src/agent/registry.py`
- `apps/api/src/agent/toolsets.py`
- `apps/api/tests/test_agent_tool_registry.py`
- add focused resolver tests beside `test_agent_tool_definitions.py` rather than
  a broad new test hierarchy.

Work:

- Add typed enums/value objects and frozen resolved types with conservative
  defaults.
- Add a toolset catalogue revision only if runtime mutation remains supported;
  otherwise explicitly keep the catalogue static and test that resolution owns
  the expanded ordered names.
- Characterize every real registration: web reads are external/read/parallel;
  signal and memory reads are internal/read/parallel; `remember_fact` is
  internal/write/serialized with unknown idempotency; unknown stays
  external/unknown/serialized.
- Preserve `ToolEntry`, `registry.get()`, `definitions()`,
  `reads_external()`, result-size accessors, and generation behavior as
  compatibility surfaces until all consumers move.

Tests:

- exact real-surface classification and safe-default matrix;
- stable name/schema/order and shadow/refusal behavior;
- no required-field break for direct `ToolEntry(...)` callers;
- toolset selection/cycle/unknown behavior and catalogue revision if added.

### Phase 2 — Make definitions the resolver/cache owner

Files:

- `apps/api/src/agent/definitions.py`
- `apps/api/tests/test_agent_tool_definitions.py`

Work:

- Add `resolve_capabilities(toolsets, now=...)` returning the immutable set.
- Cache the resolved set, not a separate schema-only reconstruction. Keep
  `get_tool_definitions()` as a thin projection for backward compatibility.
- Preserve the bounded LRU, registry-generation invalidation, 30-second monotonic
  availability expiry, requested order, and current `None => all known toolsets`
  behavior.

Tests:

- existing cache suite unchanged;
- same snapshot feeds schema, handler, classification, budget, and display;
- registration/re-registration/removal and TTL expiry invalidate correctly;
- toolset-only change cannot serve stale membership;
- resolution cache is not keyed by principal because v1 adds no principal-aware
  capability visibility. If that ever changes, principal/policy inputs must be
  explicit cache dimensions before rollout.

### Phase 3 — Migrate executor policy and remove the name allowlist

Files:

- `apps/api/src/agent/executor.py`
- `apps/api/tests/test_agent_tool_executor.py`
- real registrations in `apps/api/src/agent/tools/{web,memory,signals,price_check}.py`

Work:

- Inject the resolved by-name view into `ToolExecutor`.
- Plan segments from declared concurrency/effect and admit from declared budget
  class/provenance.
- Remove `PARALLEL_SAFE_TOOLS` only after all current tools are classified and
  characterization tests pass.
- Keep legacy `lookup`/`availability` injection temporarily as a compatibility
  adapter for focused tests, then remove only if no caller remains.

Tests:

- retain every existing overlap, barrier, ordering, fanout, unknown,
  unavailable, error-code, trace-degrade-open, and one-result assertion;
- add offered-handler atomicity across re-registration;
- add live availability revocation after resolution;
- prove missing metadata is serialized and charged to the external ceiling.

### Phase 4 — Migrate both lanes and projections

Files:

- `apps/api/src/agent/loop.py`
- `apps/api/src/alpha/analysis_loop.py`
- `apps/api/src/agent/messages.py`
- `apps/api/src/agent/untrusted.py`
- `apps/api/src/agent/ops.py`
- `apps/api/tests/test_analysis_loop.py`
- `apps/api/tests/test_agent_transport.py`
- focused message/untrusted/ops tests already owning those modules.

Work:

- Resolve once at chat turn / Analysis run start and derive model schemas,
  executor lookup, external counters, result limits, display/outcome projection,
  wrapping classification, and content-light trace metadata from that set.
- Capture only internal capability metadata needed by current-turn message
  construction; do not add fields to public SSE or durable records in v1.
- Keep Analysis signals-only, exact tool messages, trace vocabulary, and fail-open
  trace-store behavior.
- Let ops enumerate generic classes from declarations. Keep the price-check
  compliance metric explicitly tied to its shared identifier.

Tests:

- exact chat/Analysis offered tool names and order;
- unchanged exact transcript/SSE payload and version;
- unchanged Analysis envelope widening, refusal, duplicate, round, and trace
  behavior;
- external result wrapping and delimiter defanging from the captured resolved
  class, including unknown/legacy fallback;
- UI row summary/cards/outcomes equal current projections;
- ops external classification and price-check counts unchanged.

### Phase 5 — Cleanup and broad regression

Remove compatibility accessors only when `rg` shows no production consumer.
Run the narrow suites first:

```text
test_agent_tool_registry.py
test_agent_tool_definitions.py
test_agent_tool_executor.py
test_agent_tool_budget.py
test_analysis_loop.py
test_agent_transport.py
```

Then run the owning message/untrusted/ops tests and the broader API agent suite.
No migration, event-version bump, or UI change is an acceptance criterion.

## Compatibility and risk register

### Backward compatibility

- Tests and Analysis helpers construct `ToolEntry` directly
  (`test_agent_tool_registry.py:140-156`; `test_agent_tool_executor.py:52-61`;
  `test_analysis_loop.py:181-237`). New required constructor arguments would be
  breaking; defaults plus real-registration conformance tests are required.
- Prompt cache quality depends on stable registration/request order
  (`registry.py:184-186`; `definitions.py:67-78`). Sorting, renaming, or emitting
  a new schema shape is out of scope.
- `get_tool_definitions`, cache inspection helpers, registry accessors, exact
  executor failure codes, `TurnToolCall.as_wire()`, and SSE version 2 are pinned
  consumers. Keep them stable throughout the migration.
- `test_analysis_loop.py:370-380` expects exactly `list_fields` and `get_field`
  in its model surface; no capability broadening is allowed.

### Caching

- Keep caches process-local and bounded; never serialize handler callables.
- Cache keys currently omit toolset revision and any principal/policy context.
  v1 must fix only catalogue staleness. It must not introduce user-dependent
  resolution into this global cache.
- Registry generation invalidates registration changes; TTL invalidates
  availability changes. Both semantics are test-pinned
  (`test_agent_tool_definitions.py:34-107`).
- A frozen snapshot improves correspondence, but dispatch availability must be a
  separate live fail-closed check rather than a handler/policy re-resolution.

### Concurrency

- The current module globals (`_ENTRIES`, `_CHECKS`, `_CACHE`, `_MEMO`) have no
  synchronization. Their synchronous paths do not yield on the main event loop,
  but registration/probing from worker threads can race and every process has an
  independent view. Prefer startup-only registration; if runtime mutation is a
  supported contract, guard mutation/resolution with a narrow lock and test it.
- Availability probes are synchronous and can block the event loop. v1 should
  not turn them into new network lifecycle behavior; semantic/remote probes need
  a later bounded design.
- Continue parallelizing only declared read-safe calls, serializing writes and
  unknowns, and preserving issued result order
  (`executor.py:1-18`, `236-290`).

### Security

- Preserve conservative defaults: unknown is external and serial; unavailable
  is not dispatched; failed probes hide only their tool
  (`registry.py:276-347`; `executor.py:292-319`).
- Do not key authorization on model arguments. Trusted identity remains in
  `ToolContext` (`registry.py:84-113`). v1 metadata must not claim central
  authorization enforcement where handlers still own it.
- External wrapping is a security boundary, including delimiter defanging
  (`untrusted.py:1-34`, `68-100`). A missing resolved entry or legacy transcript
  must wrap, never trust.
- Transport user ownership and subscription isolation are already pinned by
  `test_agent_transport.py:517-555`, `687-745`; the contract refactor must not
  touch these paths.

### Rollback

- Migrate consumer-by-consumer behind compatibility projections rather than a
  runtime feature flag. Each phase is revertible without a database rollback.
- Keep the legacy schema/accessor functions until the last consumer migrates,
  allowing a code revert to restore the previous consumer path.
- Do not dual-dispatch tools. Shadow comparison may compare resolved metadata to
  legacy projections in tests, but executing both paths would duplicate reads or
  writes.
- Rollback acceptance is the same observable contract: tool names/order/schema,
  handler result, error codes, trace rows, budgets, UI projection, and SSE payload
  remain identical.

## Existing test coverage and missing proofs

The current tests strongly pin registry shadowing/generation/availability and
display requirements (`test_agent_tool_registry.py:18-172`), definition cache
behavior (`test_agent_tool_definitions.py:34-117`), budget precedence and
rebalancing (`test_agent_tool_budget.py:12-136`), executor barriers/order/errors
and ceilings (`test_agent_tool_executor.py:76-524`), Analysis behavior and trace
(`test_analysis_loop.py:281-783`), and transport ownership/replay/wire shape
(`test_agent_transport.py:517-919`).

The missing proofs are: one atomic resolved snapshot across offer and dispatch;
catalogue-only cache invalidation; metadata completeness over the real surface;
captured classification across registry mutation; availability revocation after
resolution; and equality of schema/executor/budget/display/trust/trace projections
from one declaration.

## Unresolved questions for the implementation plan

1. Is runtime toolset mutation a supported production operation, or only a test
   convenience? This decides whether toolsets need an explicit generation or can
   be immutable after startup.
2. Should safe display/outcome projection callables live directly on
   `ToolEntry`, or in a small typed display projection object nested in it? Either
   is behavior-preserving; choose the smaller shape that keeps registration
   readable.
3. Which current handler-owned authorization requirements are trustworthy enough
   to declare as metadata without moving enforcement in v1? Metadata must not
   overstate the actual security boundary.
