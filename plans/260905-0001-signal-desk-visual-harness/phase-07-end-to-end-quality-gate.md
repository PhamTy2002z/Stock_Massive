---
phase: 7
title: "End To End Quality Gate"
status: todo
priority: P1
effort: "16h"
dependencies: [6]
---

# Phase 7: End To End Quality Gate

## Context Links

- `apps/api/golden/README.md`
- `apps/api/golden/`
- `plans/260902-0026-phase-06-evidence-engine/plan.md`
- `docs/roadmap.md` truth contract and Phase 6 gate
- All Phase 2–6 reports and fixtures in this plan

## Overview

Graduate the complete path, not isolated components: prompt → durable Turn →
bounded web/Vnstock research → readiness → verified claim ledger → persisted
visual part → official Flint compile → right-pane render. This phase absorbs the
remaining paid Phase 6 evidence run so one corpus measures answer quality,
evidence truth, tool discipline and visual validity together.

## Requirements

- Functional: extend the existing release corpus with bounded Signal Desk cases
  covering OHLCV, event explanation, quote/trades, source conflict, no-data,
  stale data, chat mode and insufficient evidence.
- Functional: artifacts record mode, lane ceilings, stop reason, tool-call
  fingerprints, need-to-call mapping, readiness history, evidence ledger,
  visual part and Flint compile verdict; no generated option is recorded.
- Functional: grading is offline after the paid run and uses the persisted claim
  ledger/visual part, never reverse-parsed answer prose.
- Budget: paid command requires explicit `CEILING_USD`; no default, no automatic
  rerun and no live Vnstock call outside the internal profile/rate budget.
- Quality: preserve all current truth-contract hard gates and existing Phase 6
  rubric threshold; no threshold is lowered to make the new path pass.
- Safety: fault injection proves cancellation, restart, malformed model output,
  duplicate calls, provider failure, permission denial and every finite ceiling.

## Release Corpus

Keep the existing 40-case evidence corpus as denominator. Add a focused visual
slice (minimum 12 cases) without replacing existing jobs:

| Family | Minimum cases | Required sources/output |
|---|---:|---|
| Price/volume history | 3 | Vnstock OHLCV + evidence-bound Flint chart |
| Event explanation | 3 | Primary/web narrative + OHLCV/quote/trades as needed |
| Multi-symbol comparison | 2 | Same unit/time basis; Flint comparison or honest refusal |
| Source/provider conflict | 1 | Both identities shown; no silent winner |
| No-data/stale/ambiguous | 2 | Text refusal/unavailable visual |
| Chat-mode control | 1 | Text/evidence only; zero visual work |

Live values are frozen into the paid artifact/tape for repeatable grading. Tests
use these recorded real outputs; they do not fabricate market responses merely
to satisfy gates.

## Hard Gates

| Dimension | Gate |
|---|---|
| Terminality | 100% Turns settle with typed status and stop reason. |
| Absolute bounds | 0 Turns exceed lane limit: 10 tool rounds, 20 external calls, 1.800 seconds; per-round executor cap also holds. |
| Call intent | 100% dispatched external calls map to an unresolved evidence need at admission time. |
| Duplicate dispatch | 0 successful exact call fingerprints dispatched upstream twice in one Turn. |
| No progress | 100% unchanged-coverage fixtures receive at most one correction and halt on the second consecutive unchanged round. |
| Truth contract | Existing fabrication/disclosure/temporal/multi-source hard dimensions remain at their locked values (fabrication 0%). |
| Visual grounding | 100% persisted visual numbers map to accepted tool-call field + evidence ID + unit + `as_of`. |
| Flint validity | 100% `status=ready` visuals pass official pinned Flint validation/compile offline. |
| Flint integrity | 0 modified/vendored Flint source files; 0 persisted or post-processed generated ECharts options. |
| Mode isolation | 100% chat controls have no visual key, Flint compile or market toolset selected only because of UI state. |
| Internal-only data | 100% non-internal profile cases hide/refuse Vnstock capability. |
| Replay | Same persisted artifact produces the same visual input/hash after refresh/restart with 0 model/tool calls. |

Soft metrics—useful call rate, latency, cost, number of evidence gaps and visual
selection quality—are reported as distributions first. They may get thresholds
only after this baseline; they never override the hard ceilings above.

## File Inventory

| Action | File | Purpose |
|---|---|---|
| Modify | `apps/api/golden/corpus.json` or current corpus owner | Add Signal Desk cases without replacing existing evidence cases. |
| Modify | `apps/api/golden/run.py` | Record mode/readiness/visual fields and honor lane/provider ceilings. |
| Modify | `apps/api/golden/grade.py` | Aggregate mechanical visual/tool-discipline dimensions. |
| Modify | `apps/api/golden/gate.py` or current gate owner | Add hard gates using persisted structured fields. |
| Create | `apps/api/golden/visual_grade.py` | Only if Flint compile verdict cannot live in existing grader without mixing Python/Node concerns. |
| Modify | `apps/api/Makefile` | One combined release command only if current `golden-release` cannot select Signal Desk slice. |
| Modify | `apps/api/tests/golden/test_release_corpus.py` | Corpus source/ground-truth/mode validation. |
| Modify | `apps/api/tests/golden/test_grade.py` | Hard dimension fixtures. |
| Modify | `apps/api/tests/golden/test_gate.py` | Fail-closed gate and missing-field behavior. |
| Create | `apps/web/src/lib/flint/grade-visuals.ts` | Offline official Flint compile check, if needed by combined command. |
| Create | `plans/260905-0001-signal-desk-visual-harness/reports/graduation-report.md` | Commands, versions, distributions, verdict and known limits. |
| Modify after pass | `docs/roadmap.md`, `CLAUDE.md` | Mark capability current and record measured gates only. |

The implementation must first attempt to extend existing `golden-release`; a
separate visual grader/module is created only if invoking the TypeScript Flint
compiler cannot fit its current runner cleanly.

## Function And Interface Checklist

- [ ] Release artifact schema versions optional visual/readiness fields and
      rejects unknown future shapes fail-closed for hard dimensions.
- [ ] `run` records actual lane ceilings selected per case, not module constants.
- [ ] Call-intent grader joins planned call ID → need ID → pre-call unresolved
      state; prose similarity is not accepted as proof.
- [ ] Duplicate grader canonicalizes arguments through production
      `call_signature`, not a second implementation.
- [ ] No-progress grader reads production coverage digests/reasons.
- [ ] Visual grounding grader walks assembly data and proves exact membership in
      normalized tool result/evidence; string labels are not treated as numbers.
- [ ] Flint compile grader uses the exact pinned package and assembly input, then
      discards compile output.
- [ ] Missing market data/license/provider is a scored refusal, not a skipped
      case that shrinks denominator.
- [ ] Paid runner cancels/awaits every started Turn before releasing its slot;
      no unfinished Turn leaks into later cases.
- [ ] Release command refuses missing ceiling and records actual spend.

## Implementation Steps

1. Add offline corpus validation first: source rights marker, mode, expected
   visual/refusal and bounded symbol/time range for every new case.
2. Extend structured run artifact with readiness/call-intent/visual fields;
   preserve backward parsing for earlier artifacts where dimensions are `N/A`,
   never falsely passing.
3. Add adversarial offline fixtures for exact duplicate success, changed-query
   same-result, repeated failure, malformed planner, permission denial, deadline,
   restart and corrupt visual.
4. Implement grounding and official Flint compile graders; verify they fail when
   one value/evidence ID is deliberately changed.
5. Run all free focused tests, then API suite, compileall and web gates. Fix
   product defects; never weaken a gate or exclude a failing case.
6. Run one internal read-only canary to ensure Vnstock provider/version/profile
   is available and within explicit request budget.
7. Run `golden-release` once with owner-provided `CEILING_USD` and trial count.
   The first trial records web/market tape; later trials replay external data.
8. Grade offline repeatedly until byte/dimension deterministic. If quality fails,
   fix and request a new paid-run decision rather than silently spending again.
9. Write graduation report with all hard gates, soft distributions, package/data
   versions and unresolved production-license boundary.
10. Only when every hard gate passes, update roadmap status and close the old
    Signal Desk compiler plan as superseded.

## Test Scenario Matrix

| Scenario | Assertions |
|---|---|
| FPT historical trend | Vnstock need, bounded OHLCV, source/time/unit, valid Flint chart. |
| Sudden three-session drop | Web primary narrative plus relevant market data; claims distinguish fact/inference. |
| Quote vs recent trades | Observation semantics explicit; no false “live” timestamp. |
| Two-symbol comparison | Common unit/range or refusal; no mixed scale. |
| KBS/VCI conflict | Conflict disclosed in ledger and visual metadata. |
| Invalid symbol/weekend | No retry storm; no-data refusal and unavailable visual. |
| Web sufficient, no structured need | No Vnstock call merely because capability exists. |
| Structured need, web insufficient | Vnstock called; agent does not invent or stop early. |
| Exact successful repeat | One provider dispatch, reused result, finite Turn. |
| Endless changed searches, same evidence | One correction, then `no_progress`. |
| 21 proposed external calls | First 20 maximum; tail refused/settled; reason recorded. |
| 11th proposed tool round | Never dispatched. |
| Simulated 1.800-second expiry | Deadline settlement with outstanding calls resolved. |
| Cancel during parallel batch | No orphan process/call; stable order and terminal cancel. |
| Invalid chart draft twice | One repair maximum; text survives, visual unavailable. |
| Refresh/restart | Same message/visual hash, zero duplicate work. |
| Chat mode control | No market bundle due to mode, no visual, existing text quality. |

## Verification Commands

```bash
cd apps/api && pytest -q tests/test_agent_guardrails.py tests/test_agent_readiness.py tests/test_agent_market_data.py tests/test_agent_visual.py tests/test_agent_fault_injection.py tests/golden
cd apps/api && pytest -q tests/
python -m compileall -q apps/api/src apps/api/golden apps/api/tests
pnpm --dir apps/web lint
pnpm --dir apps/web type-check
pnpm --dir apps/web test
pnpm --dir apps/web build
git diff --check
rg -n 'src\.(stocks|studies)|Study DSL|Board DSL|widget catalog|global watchlist' apps/api/src apps/web/src
```

Paid gate, run only with explicit owner ceiling:

```bash
make -C apps/api golden-release CEILING_USD=<amount> TRIALS=<n>
```

## Success Criteria

- [ ] Every hard gate passes on one complete combined artifact; no case is
      skipped to improve denominator.
- [ ] Existing Phase 6 paid quality requirement is satisfied by this artifact
      and is not left as a second pending run.
- [ ] Tool count distributions show bounded, need-linked calls; duplicate and
      no-progress adversarial cases terminate exactly as specified.
- [ ] Every ready visual compiles with official Flint and is grounded in market
      evidence; Chat controls have no visual work.
- [ ] Full API/web/build/security/replay checks pass and graduation report is
      sufficient to reproduce the verdict without another paid call.
- [ ] Roadmap remains explicit that SaaS/production Vnstock is disabled pending
      written software and upstream-data rights.

## Risks And Rollback

**Live corpus cost or unfinished Turns:** runner refuses without ceiling and
awaits/cancels every Turn. Stop after the first systemic failure; do not burn the
rest of the budget collecting known-bad evidence.

**Gate reveals quality regression:** keep plan open and Signal Desk behind its
internal flag. Rollback order is UI panel → visual part → market toolset; the
existing text/evidence engine remains deployable throughout.
