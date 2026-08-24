# Investment Intelligence Eval & Replay Harness — Phase 3/4 Progress

Date: 2026-08-23

## Status

| Scope | Status | Progress | Next action |
|---|---|---:|---|
| Plan | In progress | 68/70 (97%) | Approve paid baseline route, ceiling, and thresholds |
| Phase 3: deterministic graders and golden battery | Done | 14/14 (100%) | None |
| Phase 4: multi-trial reports, baseline, release gate | In progress | 17/19 (89%) | Owner-reviewed paid baseline |
| Harness Stage 0 | Target | Approval gate open | Do not graduate before approved baseline/policy |

## Implementation highlights

- Generic hard-grader registry and structured findings cover 9 deterministic
  dimensions; blinded rubric remains subordinate to hard outcomes.
- Golden battery contains 16 reviewed cases across four families and both
  Conversation and Symbol Analysis surfaces, backed by 3 compact snapshots.
- Multi-trial scheduling, run ceiling, completeness refusal, canonical JSON,
  deterministic Markdown, immutable comparison, repository gate policy, CLI,
  and Make targets are implemented.
- Evaluation remains isolated: zero provider calls, no eval database, no
  production lifecycle hook, and no leftover eval process.

## Verification

| Check | Evidence |
|---|---|
| Full eval suite | 162 passed across Phases 1-4 |
| Dataset validation | 16 cases; 3 snapshots; 9 hard graders; digest `8e829faa380d64f2` |
| Offline smoke 1 | 16/16 complete; `hard_failures=0`; `rubric.available=16`; `data_provider_calls=0` |
| Offline smoke 2 | Same metrics; canonical content identical after excluding run identity and artifact digest |
| Syntax/import boundary | `py_compile` clean; CLI-import network capture clean |
| Review | Independent code review DONE; no concerns |
| Teardown | No leftover eval database or process |
| Cancellation regression | Invalid cold-race test sentinel corrected; full 162-test suite green |
| Plan tooling | `ak plan validate` valid; `ak plan status` 3/4 phases done, 68/70 tasks; local plan store reindexed |

## Remaining approval gate

- [ ] Obtain explicit owner approval for the paid model route, run-level spend
  ceiling, reviewed baseline distribution, and numeric trade-off thresholds.
- [ ] After approval, commit the approved baseline/policy and change Stage 0
  from Target to its verified completed state.

No paid run or approval was fabricated. Phase 4 and the overall plan remain
`in-progress` until both items are complete.

## Docs impact

No additional docs update from this reconciliation. Stage 0 documentation must
remain Target until the approved paid baseline and threshold policy exist.

## Unresolved questions

1. Which paid model route and maximum spend ceiling does the owner approve?
2. After reviewing the paid distribution, which quality, cost, and latency
   thresholds should become repository policy?
