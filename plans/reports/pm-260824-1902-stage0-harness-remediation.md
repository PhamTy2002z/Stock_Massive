# Stage 0 harness remediation — 2026-08-24

| Gate | Result |
|---|---:|
| Focused remediation tests | 42 passed |
| Eval + production-contract blast radius | 277 passed |
| Full API suite | 2,661 passed, 1 skipped, 1 pre-existing failure |
| Offline smoke | 16/16, 0 hard failures |
| Paid diagnostic | 48/48 hard pass |
| Data-provider calls | 0 |
| Dataset digest | `85eb3484ddf286b3` |
| Paid artifact digest | `9f40fe732d9a85b9` |

## Delivered

- Replay uses production Signal Field schemas and frozen-result reachability.
- Hard gate limited to deterministic machine-observable contracts.
- Vietnamese decimal-comma and annualized-unit grading corrected.
- Fixture advertises exact replay-backed tool subset; global state restored.

## Remaining

- Commit the remediation.
- Re-run paid 3 x 16 from the clean commit.
- Review and approve baseline/policy; then close Phase 4 and Stage 0.

## Unresolved questions

- None technical. Baseline approval remains an explicit owner gate.
