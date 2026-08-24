---
title: Phase 2 replay lane and trajectory capture
date: 2026-08-23
summary: Implemented and verified case-isolated Conversation and Analysis replay with redacted trajectories and bounded cleanup.
---

# Phase 2 replay lane and trajectory capture

## What happened

Implemented Phase 2 of the investment-intelligence eval harness in `apps/api/src/eval`: a typed runner over the real Conversation and Analysis lifecycles, compact fixture world, case-local admission, scripted/offline and explicitly authorized live clients, and redacted model/tool trajectories.

Independent testing first exposed an Analysis thread surviving deadline teardown. Debugging then found three related boundary gaps: live admission ownership was not case-bound, Analysis accepted duplicate tool-call IDs, and normalized observable content could retain credential-shaped output. Independent review added external task cancellation, Analysis tool-error redaction, fixture-call deadline, missing-ID, and smoke/live refusal cases.

## Decision

Keep production orchestrators unchanged. Enforce evaluation-only safety in the new adapters: shield and await Analysis workers before fixture teardown, bind live config and session-factory identity, reject ambiguous tool IDs before dispatch, redact normalized artifacts and interleaved traces, reject non-cancellable synchronous fixture callables, and propagate the Analysis stop signal into async fixture work.

## Evidence

- Focused Phase 2: 37 passed.
- Combined Phase 1+2: 106 passed.
- Lifecycle/admission/provider blast radius: 277 passed.
- Independent reviewer: no remaining findings.
- Development LLM usage ledger unchanged; no throwaway databases or eval processes remained.

## Next steps

Phase 3 owns deterministic graders and the 16-case golden battery. No evergreen docs update was needed because Phase 2 adds an internal eval-only lane without changing setup, commands, or production public contracts.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
