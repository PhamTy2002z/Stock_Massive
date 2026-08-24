# Stage 0 harness remediation — 2026-08-24

| Gate | Result |
|---|---:|
| Focused remediation tests | 42 passed |
| Eval + production-contract blast radius | 277 passed |
| Full API suite | 2,661 passed, 1 skipped, 1 pre-existing failure |
| Offline smoke | 16/16, 0 hard failures |
| Paid diagnostic | 48/48 hard pass |
| Clean approved baseline | 48/48 hard pass |
| Data-provider calls | 0 |
| Dataset digest | `85eb3484ddf286b3` |
| Approved artifact digest | `36bc44f7c00966cd` |

## Delivered

- Replay uses production Signal Field schemas and frozen-result reachability.
- Hard gate limited to deterministic machine-observable contracts.
- Vietnamese decimal-comma and annualized-unit grading corrected.
- Fixture advertises exact replay-backed tool subset; global state restored.

## Closure

- Remediation committed through `b6ea20e`.
- Clean 3 x 16 run completed from that commit with 48/48 hard passes.
- Repository owner approved policy `2.0.0` and baseline digest
  `36bc44f7c00966cd`; numeric trade-off thresholds remain intentionally unset.
- Phase 4 and Stage 0 complete: 73/73 checklist items.

## Unresolved questions

- None.
