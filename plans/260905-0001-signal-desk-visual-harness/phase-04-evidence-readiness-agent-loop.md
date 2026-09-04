---
phase: 4
title: "Evidence Readiness Agent Loop"
status: todo
priority: P1
effort: "24h"
dependencies: [3]
---

# Phase 4: Evidence Readiness Agent Loop

## Context Links

- `apps/api/src/agent/loop.py::AgentLoop`
- `apps/api/src/agent/guardrails.py::TurnGuardrails`
- `apps/api/src/agent/lanes.py::DEEP`
- `apps/api/src/agent/executor.py::ToolExecutor`
- `apps/api/src/agent/evidence/pipeline.py`
- `apps/api/src/agent/evidence/ledger.py`
- `apps/api/src/agent/parts.py`
- [Hermes Agent](https://github.com/NousResearch/hermes-agent)
- [OpenCode](https://github.com/anomalyco/opencode)
- [Oh My Pi](https://github.com/can1357/oh-my-pi)

## Overview

Turn the existing deep three-pass pipeline into a result-aware research loop:
the model states what evidence is missing and proposes calls; the host verifies
that each call is legal/useful, measures whether evidence coverage changed and
decides whether the Turn may synthesize. This phase does not add agents or an
LLM-controlled `while true`; it adds one pure readiness controller inside the
current finite `AgentLoop`.

## Requirements

- Functional: planner output carries typed evidence needs and proposed calls;
  needs can be refined but resolved only by evidence IDs already gathered.
- Functional: web is selected for narrative/primary claims; structured market
  needs route to `get_market_data`. Search snippets never satisfy a material
  claim that requires a fetched source or market row.
- Functional: host readiness validates material gap closure, source class,
  multi-source/primary rule, temporal validity, structured-data unit/time and
  required visual fields.
- Functional: final synthesis starts only on `ready_answer` or
  `ready_refusal`; model-authored `ready=true` alone has no effect.
- Functional: readiness state and stop reason survive checkpoints/reconnects in
  existing draft/progress/trajectory payloads; no new mutable DB state machine.
- Functional: every terminal path settles the Turn and outstanding tool calls.
- Safety: untrusted tool text cannot create/resolve needs, change policy or
  request capabilities outside the resolved surface.
- Budget: keep lane `DEEP` hard bounds at 10 tool rounds, 20 external calls,
  1.800 seconds and its existing aggregate LLM/cost ceilings.
- Recovery: one strict-format repair per malformed planner/artifact; no nested
  retry loop; recovery consumes the same Turn envelope.

## Readiness State Machine

```text
PLAN
  → execute admitted calls
  → normalize evidence
  → compare coverage digest
      changed      → CHECK
      unchanged #1 → COURSE_CORRECT
      unchanged #2 → HALT_TO_SYNTHESIS
  → CHECK
      material gaps + viable call → PLAN
      all host gates pass         → READY_ANSWER
      gaps cannot close safely    → READY_REFUSAL
      any hard ceiling            → STOP_WITH_REASON
```

`coverage_digest` is a hash of sorted resolved need IDs, evidence IDs, material
gap IDs and accepted data field identities. It deliberately excludes prose and
timestamps that change without adding knowledge.

## Stop Policy

| Condition | Host action | Terminal/progress reason |
|---|---|---|
| All material gates pass | Stop tools, verify ledger, synthesize | `ready` |
| User cancels | Cancel in-flight work, settle | `cancelled` |
| Wall clock expires | Stop dispatch, settle current evidence | `deadline` |
| 10 tool rounds reached | Final bounded synthesis/refusal | `round_ceiling` |
| 20 external calls reached | Refuse further external dispatch | `external_call_ceiling` |
| Spend/admission refuses | No compensating hidden call | `spend_ceiling` |
| Required capability denied | Try legal alternate once; otherwise refuse | `permission_denied` |
| Provider unavailable | Try declared alternate route only; otherwise refuse | `provider_unavailable` |
| Two unchanged coverage rounds | Halt tool use and synthesize/refuse | `no_progress` |
| Evidence cannot support claim | First-class refusal | `insufficient_evidence` |

## File Inventory

| Action | File | Purpose |
|---|---|---|
| Create | `apps/api/src/agent/evidence/readiness.py` | Pure needs, coverage and readiness decisions. |
| Modify | `apps/api/src/agent/evidence/pipeline.py` | Parse planner needs and pass readiness guidance. |
| Modify | `apps/api/src/agent/loop.py` | Store readiness in `_TurnState`; invoke gate at real round boundaries. |
| Modify | `apps/api/src/agent/guardrails.py` | Reuse exact/result signatures; add successful-repeat reuse and round no-progress halt only if not owned in readiness module. |
| Modify | `apps/api/src/agent/parts.py` | Add allowlisted readiness/stop progress payload fields. |
| Modify | `apps/api/src/agent/turns.py` | Checkpoint optional readiness summary without changing transcript text. |
| Modify | `apps/api/src/agent/schemas.py` | Add backward-compatible `mode: chat | signal_desk` to Turn creation contract. |
| Modify | `apps/api/src/agent/router.py` | Route Signal Desk request to deep lane + market toolset; chat remains existing route. |
| Create | `apps/api/tests/test_agent_readiness.py` | Pure state-machine and adversarial loop tests. |
| Modify | `apps/api/tests/test_agent_guardrails.py` | Duplicate success and coverage no-progress cases. |
| Modify | `apps/api/tests/test_agent_loop.py` | Settlement, budgets, recovery and checkpoint integration. |
| Modify | `apps/api/tests/test_agent_transport.py` | Request default/mode and progress replay contract. |

## Function And Interface Checklist

- [ ] `EvidenceNeed` validates ID, kind, materiality, source/dataset requirements
      and bounded symbol/time range.
- [ ] `ResearchReadiness` is immutable and contains state, gaps, evidence IDs,
      coverage digest and reason code; no chain-of-thought text is stored.
- [ ] `evaluate_readiness(needs, evidence, visual_intent, as_of)` is pure and
      deterministic for the same inputs.
- [ ] `observe_coverage(previous, current)` owns consecutive no-progress count;
      first miss gives guidance, second halts.
- [ ] Tool result reuse is scoped to one Turn and exact canonical arguments;
      reused result keeps original call/evidence identity and costs no dispatch.
- [ ] Tool planning is constrained to the resolved surface; unknown tool names
      remain ordinary executor refusals.
- [ ] `mode` enum is strict; omitted mode means `chat`; no arbitrary client
      string reaches toolset selection.
- [ ] `signal_desk` routes to `DEEP` and includes market toolset; `chat` keeps
      current intent router and exact existing catalog.
- [ ] Progress payload contains codes/counts/need IDs only, never page text,
      hidden reasoning or market rows.
- [ ] Existing verifier still gets a clean context and fail-closes verified
      labels; readiness does not replace claim-ledger validation.

## Implementation Steps

1. Freeze transcripts for chat light/deep behavior and add request schema tests:
   omitted mode is byte-compatible; unknown mode is 422.
2. Write pure tests for evidence needs, source routing and readiness outcomes
   before touching `AgentLoop`.
3. Extend existing research draft schema with needs/readiness proposal; retain
   the current one bounded strict-schema recovery for malformed output.
4. Evaluate readiness after each executor batch and evidence normalization.
   Store only typed summaries in `_TurnState`, checkpoint and trajectory.
5. Add exact successful result reuse using existing call/result signatures; do
   not add a cache service or cross-Turn cache.
6. Add coverage-delta course correction/halt. A blocked/malformed batch counts
   as unchanged coverage, preventing a zero-dispatch round loop.
7. Enforce terminal call reserve inside existing admission arithmetic; verifier,
   format repair and synthesis all consume the same owner budget.
8. Add fault-injection cases for cancellation, deadline, provider error,
   permission denial, malformed planner and every ceiling.
9. Replay existing Phase 6 evidence tests to prove the truth contract and
   three-pass behavior remain intact.

## Test Matrix

| Scenario | Expected dispatch/termination |
|---|---|
| Web narrative gap | Search then fetch; snippet alone remains unresolved. |
| OHLCV/quote/trade gap | Only `get_market_data`; no speculative web replacement for exact rows. |
| Mixed event analysis | Web and market calls may run in parallel if declarations allow; stable result order. |
| Exact successful call repeated | One upstream dispatch; original result reused. |
| Same payload from changed queries | Coverage unchanged; one correction, halt on second unchanged round. |
| Exact failures | Existing warn/block/halt ladder; no external calls after halt. |
| Malformed planner twice | One strict repair only, then typed incomplete/refusal. |
| Permission denied required data | Legal alternative once or `permission_denied`; no retry storm. |
| Round/call/deadline limit | Never exceed 10/20/1.800; final reason persisted. |
| Cancellation during batch | Settled calls remain ordered; undispatched calls cancelled; Turn terminal. |
| Model says ready with unresolved need | Host returns `continue` or `ready_refusal`, never `ready_answer`. |
| Evidence sufficient but model keeps calling | Host stops tools and synthesizes. |

## Verification Commands

```bash
cd apps/api && pytest -q tests/test_agent_readiness.py tests/test_agent_guardrails.py tests/test_agent_loop.py tests/test_agent_evidence_pipeline.py tests/test_agent_transport.py tests/test_agent_turn_lifecycle.py
python -m compileall -q apps/api/src apps/api/tests
git diff --check
```

## Success Criteria

- [ ] Every test Turn terminates with a stable reason; no path can schedule an
      eleventh tool round or twenty-first external call.
- [ ] A no-progress fixture gets exactly one course correction and then halts
      on the second unchanged round.
- [ ] Exact successful repeats dispatch upstream once per Turn.
- [ ] Ready is impossible with unresolved material need, unsupported visual
      data, ambiguous time/unit or invalid ledger evidence.
- [ ] Existing Phase 6 evidence, untrusted-content and cancellation suites pass.

## Risks And Rollback

**Readiness too strict:** answer becomes honest refusal more often. Measure gap
codes; tune only against corpus evidence, never by bypassing a hard gate.

**Readiness too loose:** visual/claim appears without provenance. This is a hard
failure; disable Signal Desk mode and market toolset. Rollback removes the
readiness extension and request mode while preserving the existing AgentLoop.
