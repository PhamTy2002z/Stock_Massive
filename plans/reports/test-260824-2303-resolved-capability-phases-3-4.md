---
title: "Test Report: Resolved Capability Contract v1 Phases 3-4"
date: 2026-08-24
scope: "Conversation/Analysis consumer migration and eval identity/graduation gate"
status: passed-with-unrelated-failure
---

# Test Report: Resolved Capability Contract v1 Phases 3-4

## Summary

Focused Phase 3 and eval suites pass: 409 passed, 0 failed, 0 skipped, 74
warnings across four commands. The two former blockers also pass: 26/26 turn
lifecycle tests complete without a hang, and the exact eval CLI import test
opens no network connection. All 77 currently touched Python files compile.

`make test` completes in 99.63s with 2,828 passed, 1 failed, 1 skipped, and 56
deselected. Its only failure is the unchanged, out-of-slice missing
`docs/streaming-topology.md`; no Phase 3-4 failure remains.

No paid eval, provider call, or intentional network call was run. No production
or test file was edited.

## Environment

- macOS Darwin; branch `develop`; CWD `/Users/typham/Dev/Stock_Massive`.
- Required shared venv activated: `/Users/typham/.venv`, Python 3.12.3.
- `make test` internally selected `apps/api/.venv/bin/pytest` per the checked-in
  Makefile despite the shared venv activation; both report Python 3.12.3.
- Concurrent realtime/DNSE changes were present throughout and were not edited
  or reverted.

## Results

| Gate | Result | Passed | Failed | Skipped | Deselected | Warnings | Duration |
|---|---:|---:|---:|---:|---:|---:|---:|
| In-memory syntax compile of all modified/untracked `.py` files | PASS | 77 files | 0 | — | — | 0 | 0.5s command |
| Exact eval CLI no-network import regression | PASS | 1 | 0 | 0 | 0 | 4 | 0.74s |
| Entire agent turn lifecycle | PASS | 26 | 0 | 0 | 0 | 4 | 0.79s |
| Capability contract/registry/definitions | PASS | 37 | 0 | 0 | 0 | 4 | 0.37s |
| Executor/budget/Conversation/Analysis | PASS | 148 | 0 | 0 | 0 | 4 | 0.69s |
| Transport/signals/untrusted/ops | PASS | 120 | 0 | 0 | 0 | 62 | 14.58s |
| Eval contracts/runner/harness/report | PASS | 104 | 0 | 0 | 0 | 4 | 18.15s |
| `make test` | FAIL: unrelated missing doc | 2,828 | 1 | 1 | 56 | 231 | 99.63s |

Focused four-group total: **409 passed, 0 failed, 0 skipped, 74 warnings**.
Former-blocker checks add 27 passes and 8 warnings, but are not combined with
the broad total because their cases overlap.

## Commands

All Python/pytest commands began with
`source /Users/typham/.venv/bin/activate`.

```text
python - <<'PY'
# git diff + untracked .py paths; compile(file_bytes, path, "exec")
PY

cd apps/api
pytest tests/test_eval_battery.py::test_cli_import_opens_no_network_connection -q
pytest tests/test_agent_turn_lifecycle.py -q
pytest tests/test_agent_capability_contract.py tests/test_agent_tool_registry.py tests/test_agent_tool_definitions.py -q
pytest tests/test_agent_tool_executor.py tests/test_agent_tool_budget.py tests/test_agent_loop.py tests/test_analysis_loop.py -q
pytest tests/test_agent_transport.py tests/test_agent_signal_tools.py tests/test_agent_untrusted_results.py tests/test_agent_ops_query.py -q
pytest tests/test_eval_contracts.py tests/test_eval_runner.py tests/test_eval_harness.py tests/test_eval_report.py -q
make test
rg -n "PARALLEL_SAFE_TOOLS" apps/api/src apps/api/tests
```

The syntax command compiled all 77 modified or untracked Python paths from
`git diff --name-only --diff-filter=ACMR` plus
`git ls-files --others --exclude-standard`; it emitted no bytecode.

## Repaired Regression Checks

### 1. Phase 3 lifecycle suite completes

The lifecycle fixture now adds its test-only `slow` and `sleepy` tools to the
selected `memory` toolset and restores the table/memo afterward. All 26 tests
pass in 0.79s. `make test` passes the same full file at 15% and continues to
completion, proving the former wait/hang is gone without reopening the
lane-unselected dispatch boundary.

### 2. Phase 4 CLI import remains offline

`tests/test_eval_battery.py::test_cli_import_opens_no_network_connection`
passes alone and in `make test`. `src.eval.cli` now defers the `world` import
inside `_identity`, so plain CLI import no longer crosses into stocks/runtime
provider dependencies before offline guards exist. The sentinel patches
`socket.socket.connect` and records zero attempts.

No paid comparison, provider call, or live eval was run.

## Non-Phase Failures and Warnings

- `tests/test_deployment_topology.py::TestTheOuterProxy::test_the_topology_is_written_down_where_the_next_reader_will_look`
  is the only broad failure. `docs/streaming-topology.md` is absent;
  `git ls-tree HEAD` also shows no such tracked file, and this path is outside
  the Phase 3-4 diff.
- One broad-suite skip was reported; verbose output was truncated before its
  node/reason was retained in the final summary.
- Warnings: FastAPI/httpx TestClient deprecation; vnstock/vnai update notices;
  Pydantic class-based config deprecation; repeated short HMAC test keys;
  pandas `to_pydatetime` deprecation. No warning was hidden.

## Scope and Contract Checks

- `rg -n "PARALLEL_SAFE_TOOLS" apps/api/src apps/api/tests`: zero matches.
- The Phase 3-4 capability file slice changes agent/Analysis/eval owners and
  their tests; it contains no provider adapter, Alembic migration, endpoint,
  SSE event model, or public route file.
- Exact transport group passes 120/120 as part of the second Phase 3 group,
  including transcript/SSE assertions.
- The dirty workspace does contain concurrent out-of-slice changes:
  `src/stocks/providers/vnstock_provider.py` has a comment-only request-count
  correction, and `alembic/versions/e2c4a7d19b63_add_reconciliation_audit.py`
  is an untracked realtime reconciliation migration. Neither is attributable
  to this capability slice.
- No test/make process started by this verification remains running.

## Recommendation

1. Accept the Phase 3-4 test slice: its focused, lifecycle, no-network, and
   broad-integration coverage is green.
2. Resolve the unrelated missing topology document separately before claiming
   a wholly green repository gate.
3. Keep paid eval/provider execution outside this verification; run only under
   the repository's approved owner, route, ceiling, and baseline process.

## Unresolved Questions

- Was `docs/streaming-topology.md` intentionally removed in another session, or
  is the deployment-topology test exposing a pre-existing missing artifact?
