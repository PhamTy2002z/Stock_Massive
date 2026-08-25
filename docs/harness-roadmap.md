# Harness roadmap

This roadmap owns the evolution of Stock_Massive from an evidence-backed AI
assistant into an Investment Intelligence runtime. It covers evaluation,
capability resolution, evidence reasoning, user and thesis state, proactive
intelligence, and specialist orchestration. Provider ingestion, storage,
market-data APIs, product projections, and operations belong to the
[system roadmap](system-roadmap.md).

The [Investment Intelligence contract](Harness/investment-intelligence-contract.md),
[target architecture](Harness/target-architecture.md), and
[quality, safety, and operations contract](Harness/quality-safety-and-operations.md)
remain binding. Code and tests prove current behavior. This checklist owns
dependency order and graduation decisions.

## Roadmap status model

Checklist state has a narrow meaning so future work is not mistaken for shipped
capability.

- `[x]` means the repository contains executable evidence for the item.
- `[ ]` means the item is pending, conditional, or not yet accepted.
- A phase graduates only when every required exit-gate item is complete.
- Later phases may be prototyped, but they must not become the default before
  their dependencies graduate.

## Architecture conformance contract

Every phase must preserve the Stock_Massive architecture synthesized from
Hermes and OpenCode. The canonical adopt, adapt, and reject decisions live in
[Target architecture: Adopt, adapt and
reject](Harness/target-architecture.md#adopt-adapt-and-reject).
The research corpus under [`docs/hermes`](hermes/README.md) and
[`docs/opencode`](opencode/README.md) provides evidence, but it does not override
the Stock_Massive target architecture.

The Harness adopts or adapts these standards:

- **From OpenCode:** server/session separation, durable typed state, one
  resolved capability plane, typed tool lifecycle, provider seams, isolated
  child-session semantics, and progressive context selection.
- **From Hermes:** typed recovery taxonomy, bounded retries, stable/context/
  volatile prompt discipline, output spill plus aggregate turn budget,
  guardrail ladder, content-light observability, and operational recovery.
- **Stock_Massive specialization:** one capability/policy/evidence path for all
  lanes, deterministic financial calculations, point-in-time evidence, typed
  user context, and read-only financial autonomy by default.

The Harness explicitly rejects these inheritance mistakes:

- copying either reference architecture wholesale;
- introducing a second runtime, executor, policy plane, or evidence path;
- importing OpenCode's host shell, coding tools, broad plugin/MCP surface, or
  coding-agent threat model;
- adopting Hermes's in-process, non-durable subagent tree as the target;
- putting privileged free-text memory, provider policy, or financial arithmetic
  in prompts as the only owner;
- using a general graph framework before a concrete evidence requirement proves
  the need.

Every phase exit review must complete this checklist:

- [ ] The change uses the shared runtime, resolved capability, policy, evidence,
  budget, and observer seams defined by the target architecture.
- [ ] Tool/task state is typed, durable to the degree required by its lane, and
  settles once across retry, cancellation, and reconnect.
- [ ] Recovery maps a typed cause to a bounded action and preserves the task's
  financial semantics.
- [ ] Context separates stable contracts, scoped task/evidence context, and
  volatile runtime state without promoting untrusted content.
- [ ] No alternate path bypasses authorization, evidence identity, budget,
  guardrails, or trace.
- [ ] Any departure from the adopted Hermes/OpenCode pattern is recorded in
  `Harness/target-architecture.md` before the phase graduates.

## DNSE impact on the Harness

DNSE changes the evidence available to the Harness, not the Harness's authority.
The empirical basis is the
[DNSE market-data audit](research/dnse-lightspeed-market-data-audit.md).

- Live trades, book snapshots, foreign flow, auction state, session events,
  indices, and futures make a dedicated live-market intelligence phase viable.
- Board-specific units, duplicate snapshots, silent-empty REST responses, and
  reconnect uncertainty require deterministic validation before model access.
- DNSE historical prices remain supporting evidence, not canonical EOD truth,
  until price basis and data-quality gaps are resolved.
- Realtime data does not justify skipping evaluation, evidence identity,
  point-in-time rules, user context, materiality, or autonomy gates.
- Trading, broker account sync, and order execution remain outside the current
  Harness contract.

## Dependency path

The Harness advances from measurement to trustworthy perception, then to deeper
reasoning and controlled autonomy.

```text
H0 Measurement authority
  -> H1 Unified capability and evidence contracts
  -> H2 Live market intelligence
  -> H3 Deep multi-axis research
  -> H4 User, thesis, and portfolio intelligence
  -> H5 Proactive intelligence

H3 + H4 -> H6 Specialist orchestration
H5 + H6 -> H7 Controlled ecosystem and actions
```

System dependencies use phase identifiers from the
[system roadmap](system-roadmap.md). A Harness phase cannot graduate when its
required data contract is still experimental.

## Phase H0 — Restore measurement authority

This phase makes every material prompt, model, tool, context, and loop change
measurable before release. The executable owner is the evaluation lane under
`apps/api/src/eval`, with policy under `apps/api/eval` and commands in
`apps/api/Makefile`. Progress and approval evidence live in the
[Eval and Replay Harness plan](../plans/260823-1744-investment-intelligence-eval-replay-harness/plan.md).

**Delivery checklist:**

- [x] Define compact, frozen, point-in-time fixtures for Conversation and
  Symbol Analysis.
- [x] Run the real runtime entry points instead of a lookalike evaluation loop.
- [x] Grade figures, units, as-of time, evidence references, refusals, terminal
  settlement, and policy deterministically.
- [x] Grade synthesis, counterargument, uncertainty, and utility separately
  from hard financial facts.
- [x] Record model, prompt, tool, config, data, code, cost, latency, and trial
  identity in canonical artifacts.
- [x] Compare candidate and baseline without letting a candidate weaken policy.
- [x] Prove that evaluation consumes no live market-provider quota.
- [x] Reproduce the paid 3-by-16 baseline from a clean commit.
- [x] Approve the baseline digest and lock repository-owned thresholds.

**Exit gate:**

- [x] A maintainer can run the repository-owned command from a clean commit and
  reproduce an approved report with all hard dimensions passing.
- [x] Stage policy fails closed when the baseline, digest, trial set, or
  threshold approval is absent.
- [x] The architecture conformance checklist passes for both runtime lanes.

**Do not open yet:** general specialists, proactive monitoring, or broad context
redesign must not become default behavior before this gate closes.

## Phase H1 — Unify capability and evidence contracts

This phase implements the OpenCode-derived resolved capability and typed
lifecycle boundaries on Stock_Massive's existing runtime. It deepens shared
seams rather than merging Conversation and Analysis into a monolith. The
[Resolved Capability Contract plan](../plans/260823-2104-resolved-capability-contract-v1/plan.md)
delivers the first capability-declaration slice; it does not graduate every H1
item by itself.

**Delivery checklist:**

- [ ] Make one resolved capability declaration own schema, availability,
  provenance, mutability, trust, concurrency, budget, trace, and display.
- [ ] Require intentional lane selection before a globally registered tool can
  execute.
- [ ] Establish stable root-task, attempt, call, and evidence identities across
  state, SSE, operations, and evaluation.
- [ ] Use one evidence-reference contract across Conversation and Analysis.
- [ ] Add typed capability probes that verify semantic data availability, not
  connectivity alone.
- [ ] Add Hermes-style typed recovery decisions and bounded retry budgets at
  the shared runtime seam.
- [ ] Add context telemetry for stable/scoped/volatile selection, cache,
  pruning, evidence handles, and protected citations.
- [ ] Settle every terminal tool/task path as completed, blocked, interrupted,
  refused, or failed.
- [ ] Remove duplicate policy/name owners after their final consumers migrate.

**Exit gate:**

- [ ] A new read-only financial capability needs one registration plus explicit
  lane selection, with no parallel policy or display table.
- [ ] Conversation and Analysis preserve the same evidence identity and
  terminal state across disconnect, retry, and replay.
- [ ] The approved H0 baseline shows no hard-dimension regression.
- [ ] The architecture conformance checklist passes with no alternate runtime
  or capability path.

**Dependency:** H0 must graduate before this phase becomes the default contract.

## Phase H2 — Deliver live market intelligence

This phase turns normalized DNSE events into decision-grade market evidence.
It owns AI-facing meanings, deterministic calculations, evidence binding, and
evaluation. The System owns connections, normalization, storage, and serving.

**Delivery checklist:**

- [ ] Register trusted tools for session state, trades, closed bars, foreign
  flow, book depth, auction state, indices, and data health.
- [ ] Bind source, symbol, exchange, board, trading day, event time, observed
  time, units, schema version, and quality state to every observation.
- [ ] Add deterministic methods for VWAP, signed flow, volume acceleration,
  spread, depth imbalance, liquidity shock, auction dislocation, breadth, and
  index-relative movement.
- [ ] Keep venue depth limits, board quantity rules, and market-session rules
  out of model arithmetic.
- [x] Unblock `foreign_flow_pressure.net_volume_over_adtv` only after the
  normalized share-volume contract is proven.
- [ ] Add the “explain a material move” slice across price, volume, regime,
  liquidity, foreign flow, auction, and known events.
- [ ] Expose stale, duplicate, gap, reconnect, partial-depth, and conflicting
  evidence as typed health, never as fluent success.
- [ ] Add live-market golden cases and fault injection for wrong units,
  duplicate snapshots, out-of-order events, silent-empty responses, and session
  transitions.
- [ ] Compare event-derived bars with provider daily data without erasing
  source provenance.

**Exit gate:**

- [ ] The Harness explains a frozen and a live market move with traceable
  evidence, correct board/unit semantics, and explicit data limitations.
- [ ] Deterministic calculations reconcile with accepted fixtures and reject
  malformed or incomplete inputs.
- [ ] Live-market runs stay inside accepted latency, cost, and context envelopes
  without increasing unsupported claims.
- [ ] Architecture conformance proves that DNSE tools use the shared OpenCode-
  derived capability plane and Hermes-derived recovery/budget discipline.

**Dependencies:** H1 and System phases S0–S3 must graduate. Order-book and
auction items additionally depend on S4.

## Phase H3 — Deepen multi-axis research

This phase combines live market evidence with fundamentals, valuation, events,
peers, and deterministic scenarios. It expands research depth without making
the model the owner of calculations or source selection.

**Delivery checklist:**

- [ ] Plan evidence acquisition by question and horizon instead of calling the
  full tool catalog.
- [ ] Represent observations, derived metrics, documents, claims, conflicts,
  hypotheses, scenarios, and judgments with lineage.
- [ ] Add point-in-time-safe fundamental, valuation, flow, event, peer, risk,
  and technical domain packs.
- [ ] Normalize news and filings by entity, publication time, effective time,
  event type, materiality evidence, and duplicate cluster.
- [ ] Bind material claims to evidence and extract counterevidence and
  falsifiers.
- [ ] Generate bull, base, and bear scenarios with explicit assumptions and
  sensitivity, without invented probabilities.
- [ ] Produce research memo, comparison, and evidence-appendix artifacts.
- [ ] Preserve cited evidence and unresolved commitments under context
  reduction; recover full artifacts through handles.
- [ ] Evaluate thesis review, opportunity comparison, and valuation/quality
  slices against fixed-envelope baselines.

**Exit gate:**

- [ ] Planner-based research improves task success and evidence coverage beyond
  the accepted baseline without temporal, safety, or unsupported-claim
  regression.
- [ ] Every material figure resolves from point-in-time evidence with method
  and source identity.
- [ ] Missing fundamentals, corporate actions, news, or historical membership
  remain named blockers rather than DNSE-derived guesses.
- [ ] Context selection follows the adopted Hermes discipline and OpenCode
  progressive disclosure without privileged untrusted memory.

**Dependencies:** H2 plus System S4 for broad live-market context. Canonical EOD,
corporate-action, fundamental, and news owners remain independent dependencies.

## Phase H4 — Add user, thesis, and portfolio intelligence

This phase makes intelligence continuous and context-aware without increasing
action authority. User-provided or future read-only portfolio data must remain
typed, scoped, fresh, and reviewable.

**Delivery checklist:**

- [ ] Define typed objective, horizon, constraint, liquidity need, and
  communication preferences.
- [ ] Version portfolio snapshots with source, ownership, freshness, and
  quality.
- [ ] Version thesis claims, assumptions, evidence, falsifiers, horizon, and
  status instead of rewriting history.
- [ ] Compute concentration, liquidity, factor, cross-position exposure, and
  correlation uncertainty deterministically.
- [ ] Run deterministic portfolio scenarios and stress tests.
- [ ] Connect judgments to evidence, as-of time, user context, and later
  outcomes in a decision journal.
- [ ] Provide memory proposal, review, correction, and deletion controls.
- [ ] Refuse personalization when required context is missing instead of
  inferring sensitive preferences.

**Exit gate:**

- [ ] Frozen user/portfolio contexts produce appropriately different
  implications from the same evidence without cross-user leakage.
- [ ] Portfolio arithmetic and temporal joins pass deterministic tests.
- [ ] The Harness does not present a personalized action when suitability
  context is insufficient.
- [ ] Memory follows typed Stock_Massive lifecycle rules rather than copying
  mutable privileged memory from either reference harness.

**Dependency:** H3 must establish the evidence and scenario contracts first.

## Phase H5 — Open proactive intelligence

This phase turns reliable market events into user-owned monitoring. It opens
read-only autonomy level A2 only after materiality, checkpoint, and delivery
contracts are measurable.

**Delivery checklist:**

- [ ] Let users create, inspect, pause, expire, and delete typed monitors for
  thesis falsifiers, material events, flow, liquidity, auction, and risk.
- [ ] Evaluate only evidence newer than a durable checkpoint.
- [ ] Separate source outage, reconnect gap, stale projection, and data-quality
  failure from genuine market change.
- [ ] Apply deterministic deduplication, cooldown, quiet hours, and delivery
  state before notification.
- [ ] Produce scheduled briefs from new evidence and unresolved items only.
- [ ] Bound each goal by scope, expiry, data, model, cost, and delivery budget.
- [ ] Preserve trigger-to-evidence-to-judgment trace and useful/dismissed/noisy
  feedback.
- [ ] Run shadow mode before any user-visible alert becomes default.

**Exit gate:**

- [ ] Shadow evaluation meets owner-approved materiality, delay, duplicate,
  noise, crash-recovery, and monthly-cost thresholds.
- [ ] Stale, conflicted, refused, or incomplete DNSE evidence cannot create a
  market alert.
- [ ] A monitor cannot expand its own scope or escalate into a broker action.
- [ ] Durable task recovery adapts Hermes operational lessons without using a
  long-lived HTTP turn or non-resumable background agent.

**Dependencies:** H4 plus System S5–S7. Proactive market alerts also require
live-market completeness gates from S4.

## Phase H6 — Add specialist orchestration conditionally

This conditional phase adds specialists only where evaluation proves that an
independent subtask improves the outcome after cost, latency, and redo are
counted. Specialist roles are profiles on the shared runtime, not a second
execution system.

**Delivery checklist:**

- [ ] Identify a measured single-agent bottleneck by task family.
- [ ] Define fresh scoped context, explicit as-of time, capability allowlist,
  typed output, and evidence-reference contract for each specialist.
- [ ] Use OpenCode-style child-session identity and monotonic permissions,
  adapted to durable Stock_Massive task state.
- [ ] Enforce child/depth/token/cost/deadline limits and cancellation across the
  task tree.
- [ ] Persist child status and settle joins deterministically.
- [ ] Keep full child trace auditable while returning only structured findings
  and evidence handles to the parent.
- [ ] Compare candidate financial roles only when their task family warrants
  independent work.
- [ ] Reject a specialist when deterministic, inline, or stronger direct-model
  execution produces the same uplift more simply.

**Exit gate:**

- [ ] Each retained specialist beats the direct baseline with sufficient
  confidence and no permission, settlement, or evidence regression.
- [ ] Parent redo, join failure, and total task cost remain inside accepted
  thresholds.
- [ ] The implementation does not adopt Hermes's non-durable in-process tree or
  bypass the OpenCode-derived capability and child-session boundaries.

**Dependencies:** H3 and H4. H0 remains the authority for every uplift claim.

## Phase H7 — Control ecosystem and actions

This conditional phase admits narrowly reviewed external capabilities or action
proposals. It does not authorize autonomous trading, portfolio mutation, or a
generic plugin marketplace.

**Delivery checklist:**

- [ ] Admit external adapters only through narrow contracts, least-privilege
  credentials, capability probes, conformance tests, and revoke controls.
- [ ] Add sandboxed computation or document workspaces only with explicit data
  scope and artifact policy.
- [ ] Permit research exports or proposed action tickets only after preview and
  explicit user approval contracts exist.
- [ ] Require idempotency, reconciliation, immutable receipts, and incident
  runbooks before any write action.
- [ ] Keep broker order execution rejected until a new product, legal, threat
  model, and human-approval decision explicitly changes autonomy level A4.

**Exit gate:**

- [ ] Every external capability passes security, privacy, evidence, reliability,
  and disable-path review.
- [ ] No provider annotation, remote prompt, package manifest, or model output
  can grant authority.
- [ ] OpenCode plugin/MCP breadth and Hermes host-execution breadth remain
  rejected unless a new target-architecture decision explicitly admits a
  narrow capability.

**Dependencies:** H5 or H6 only when a concrete product outcome requires this
phase. The roadmap can end at read-only decision support.

## Priority and maintenance rules

Use these rules whenever multiple checklist items compete for implementation.

1. Fix a hard truth, safety, temporal, or settlement failure first.
2. Close the current phase's graduation gate before widening capability.
3. Open missing evidence for a high-value task before adding model complexity.
4. Improve measured task success before increasing autonomy or extensibility.
5. Keep System delivery work in `system-roadmap.md`; keep Harness intelligence
   and evaluation work here.
6. Update a checkbox only with a linkable executable owner, test, trace, or
   approved evaluation artifact.
7. Treat Hermes/OpenCode as architecture evidence; treat
   `Harness/target-architecture.md` as the binding Stock_Massive decision.

## Next execution slice

H0 graduated on clean artifact `36bc44f7c00966cd`: 48/48 hard passes and zero
live data-provider calls under policy `2.0.0`. The immediate Harness slice is
the resolved capability contract in H1. DNSE contract work can proceed in
parallel on the System roadmap, but DNSE tools must not become default Harness
capabilities before H1 and the relevant System gates graduate.
