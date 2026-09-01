# Phase 2 — Unified Capability Plane, implementation

Branch `feat/phase-02-capability-plane`, worktree left dirty (no commit).

## Files touched

| File | What |
|---|---|
| `apps/api/src/agent/registry.py` | `ToolPermission` enum; `ToolEntry.permission` (unset = `None`, refused by `register()`), `ToolEntry.timeout_seconds` + `DEFAULT_TOOL_TIMEOUT_SECONDS = 20.0`; `__post_init__` coerces the enum and refuses a non-finite/non-positive timeout; both axes materialized on `ResolvedTool`; `__all__` |
| `apps/api/src/agent/definitions.py` | identity payload gains `permission` + `timeout_seconds`; `resolver_version` → `resolved-tool-surface@2` |
| `apps/api/src/agent/executor.py` | `PERMISSION_DENIED`, `TOOL_CALL_TIMEOUT`; permission enforced in `_dispatch` after availability and before argument parsing; handler await wrapped in `asyncio.wait_for(entry.timeout_seconds)`; `_permission_refusal` helper; `__all__` |
| `apps/api/src/agent/tools/web.py` | `web_search` allow/20s, `fetch_url` allow/25s |
| `apps/api/src/agent/tools/memory.py` | three tools allow/`STORE_TIMEOUT_SECONDS = 10.0` |
| `apps/api/tests/agent_tool_world.py` | `stub_entry` declares `permission=ALLOW` |
| `apps/api/tests/test_agent_capability_contract.py` | catalog columns; extended flow-through test; typed-settle, stable-order, registration-refusal tests |
| `apps/api/tests/test_agent_tool_executor.py` | `Surface.add` takes `permission` / `timeout_seconds` |
| `apps/api/tests/test_agent_loop.py`, `tests/test_agent_untrusted_results.py` | fixtures declare `permission` |

12 `ToolEntry(` construction sites accounted for: 5 shipped, 2 factories, 3 direct in tests, 1 re-registration through `entry.__dict__` (carries the field automatically), 1 deliberately-invalid entry in the display-name refusal test (still refused on `display_name`, which is checked first).

## Test output

```
$ pytest tests/test_agent_capability_contract.py tests/test_agent_tool_executor.py \
    tests/test_agent_tool_registry.py tests/test_agent_tool_definitions.py -q
83 passed in 0.52s

$ pytest -q
1143 passed, 3 deselected, 155 warnings in 34.55s      # baseline before the change: 1136 passed

$ python -m compileall -q apps/api/src apps/api/golden apps/api/tests
COMPILE_OK

$ git diff --check
DIFF_CLEAN
```

No pre-existing failures: the pre-change tree was run first and was green at 1136.

## Decisions taken inside the spec's bounds

- **`None` permission is refused, not projected.** `ResolvedTool.from_entry` passes the entry's value through unchanged rather than defaulting an undeclared one to `DENY`; the type annotation is `ToolPermission` because `register()` guarantees it for anything the registry can resolve, and `_permission_refusal` refuses a literal `None` (only reachable from a declaration built outside the registry) with its own honest text. No default permission exists anywhere.
- **The timeout wraps `_invoke` at its call site in `_dispatch`**, so one `wait_for` covers both the async path and the `to_thread` path. `TimeoutError` is caught before the generic handler; the existing `after_call` / `_record` / `duration_ms` path is reused unchanged, so the repetition ladder and the trace see the failure without new code.
- **`STORE_TIMEOUT_SECONDS` named once in `memory.py`** instead of repeating `10.0` three times.
- **One extra locked invariant** in the catalog test: every shipped bound is `> 0` and `< loop.TOOL_TIMEOUT_SECONDS`, so a per-call bound can never only fire by ending the Turn.
- The golden release harness was not re-run: shipped runtime behavior is unchanged (all `allow`, bounds above each handler's internal limits); only the surface identity digest moves, which is a prompt-prefix cache key.

## Unresolved questions

1. A `DENY`/`ASK` tool is still offered to the model in its schema list — the surface only filters on availability. Refusing at dispatch is what this phase specified; whether a non-`allow` tool should also be withheld from `offered_schemas` is a policy question the permission phase owns.
2. `fetch_url` and `web_search` declare `is_async=True` but run their work in `asyncio.to_thread` internally, so a timeout there returns control to the round while the worker thread runs on until its own 8s wire bound. Documented in `_invoke`; no measurement exists yet of how often the 25s/20s bounds fire on real Vietnamese network paths.
