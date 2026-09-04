---
phase: 3
title: "Vnstock Market Data Capability"
status: todo
priority: P1
effort: "20h"
dependencies: [1]
---

# Phase 3: Vnstock Market Data Capability

## Context Links

- `plans/reports/research-260904-2254-vnstock-personal-to-saas-production.md`
- `apps/api/src/agent/registry.py`
- `apps/api/src/agent/toolsets.py`
- `apps/api/src/agent/executor.py`
- `apps/api/src/agent/evidence/contracts.py`
- `apps/api/src/agent/evidence/pipeline.py`
- `apps/api/src/core/config.py`
- `apps/api/requirements.txt`

## Overview

Add the smallest structured-data surface that closes web search's real gap:
one read-only `get_market_data` tool backed by pinned Vnstock Community for
personal internal use. The model chooses symbol, dataset and bounds; the host
chooses provider route, validates semantics, normalizes units/time and converts
the result to durable `STORE_FIGURE` evidence.

This is not a market terminal or local analytics engine. No bulk ingestion,
cache, scheduler or derived indicator is created.

## Requirements

- Functional: datasets are exactly `ohlcv`, `quote`, `trades`; one normalized
  HOSE/HNX/UPCOM symbol per call; no arbitrary provider/URL/method argument.
- Functional: `ohlcv` requires bounded start/end and supports only the interval
  proven by contract tests; `quote` is one snapshot; `trades` has a hard row cap.
- Functional: reject reversed dates, unsupported interval, ambiguous unit,
  stale/absent observation time and provider output outside requested bounds.
- Functional: return source, package/version, provider, requested/actual bounds,
  retrieved/observed/as-of times, timezone, currency, unit/scale, adjustment,
  row count, quality state and raw/normalized SHA-256.
- Functional: preserve raw provider field names for hashing/audit, but expose
  only normalized allowlisted fields to the model and visual layer.
- Functional: transform accepted rows into evidence IDs; numeric claims and
  visual series cite those IDs rather than Vnstock documentation.
- Security: key/credential is backend-only and never appears in tool schema,
  model context, result, trace, browser or logs.
- Deployment: capability availability is true only when explicit profile is
  `personal_internal`, provider flag is on and package/version check passes.
- Licensing: production/staging/shared SaaS profiles fail closed even if a key
  exists; enabling them requires a later written-rights deviation.
- Budget: declaration is network/read/idempotent, external-call counted,
  finite timeout, bounded result size and no hidden `get_all`/pagination loop.

## Tool Contract

```json
{
  "name": "get_market_data",
  "arguments": {
    "symbol": "FPT",
    "dataset": "ohlcv | quote | trades",
    "start": "YYYY-MM-DD (ohlcv only)",
    "end": "YYYY-MM-DD (ohlcv only)",
    "limit": "bounded integer (trades only)"
  }
}
```

The response has one host-authored envelope and dataset-specific rows. Provider
messages/errors are mapped to codes (`invalid_request`, `no_data`,
`provider_unavailable`, `rate_limited`, `schema_drift`, `ambiguous_time`,
`ambiguous_unit`) and never passed through as trusted prose.

## File Inventory

| Action | File | Purpose |
|---|---|---|
| Create | `apps/api/src/agent/tools/market_data.py` | Vnstock adapter, validation, normalization and registration. |
| Modify | `apps/api/src/agent/tools/__init__.py` | Import registration using existing pattern. |
| Modify | `apps/api/src/agent/toolsets.py` | Add a `market_data` bundle selected only for Signal Desk deep Turns. |
| Modify | `apps/api/src/agent/registry.py` | Only if existing declarations cannot express the verified availability check; no new dispatch path. |
| Modify | `apps/api/src/agent/evidence/contracts.py` | Use/clarify `STORE_FIGURE` locator semantics without weakening web evidence. |
| Modify | `apps/api/src/agent/evidence/pipeline.py` | Convert successful market calls into evidence refs. |
| Modify | `apps/api/src/core/config.py` | Explicit internal profile/provider gate. |
| Modify | `apps/api/requirements.txt` | Pin the exact Community version proven in preflight. |
| Create | `apps/api/tests/test_agent_market_data.py` | Contract, normalization, availability and error tests. |
| Modify | `apps/api/tests/test_agent_toolsets.py` | Prove chat does not inherit market capability. |
| Modify | `apps/api/tests/test_agent_evidence_contract.py` | Prove structured row provenance and hashes. |

No migration is expected: full tool results already persist in
`agent_tool_call`, and claim ledgers already persist `EvidenceRef`. If preflight
finds either payload cannot replay a bounded result, stop and amend this plan
before adding a table.

## Function And Interface Checklist

- [ ] `normalize_market_request(arguments)` validates dataset-specific fields
      before any package call.
- [ ] `get_market_data(context, arguments)` is the only registered handler.
- [ ] Blocking Vnstock work is declared `is_async=False` so executor moves it
      off the event loop.
- [ ] `market_data_available()` checks profile, flag and exact import/version;
      failures hide the tool rather than crash the catalog.
- [ ] `normalize_ohlcv`, `normalize_quote`, `normalize_trades` return one typed,
      deterministic JSON shape and reject unknown required-field drift.
- [ ] Dates are post-filtered because VCI was observed ignoring `start`.
- [ ] Price scale differences are explicit: OHLCV/trades thousand-VND versus
      quote full VND are normalized to VND and retain original scale metadata.
- [ ] Naive timestamps are assigned only by a documented Asia/Ho_Chi_Minh rule;
      no timestamp is invented for quote rows that do not provide one.
- [ ] Retry wrappers are unwrapped; validation/no-data never retry as outage.
- [ ] Handler issues no `get_all`, multi-symbol request or unbounded page loop.
- [ ] Registry trust is `TRUSTED_STRUCTURED` only after provider strings are
      removed/allowlisted and all numbers pass validation.
- [ ] Permission resource is a normalized symbol/dataset, not model-supplied URL.

## Implementation Steps

1. In the project venv, verify current Vnstock Community API with package-native
   discovery/docs; pin the tested version (research baseline `4.0.5`) only if
   the exact calls still match. Do not guess renamed methods.
2. Add failing tests with saved **shape metadata**, not fake market values, for
   KBS/VCI observations in the research report: scale mismatch, ignored start,
   `limit`/`page_size`, `va` alias and wrapped no-data errors.
3. Add internal profile settings and fail-closed availability tests first.
4. Implement request validation and one direct package operation per dataset;
   record provider operation count and refuse any path requiring pagination.
5. Normalize values, time and units; cap rows/serialized chars before returning.
6. Register through the current declaration and permission plane, then expose
   the tool only in the Signal Desk-selected toolset.
7. Build `STORE_FIGURE` evidence from normalized payload + call ID + hashes;
   preserve multi-source conflicts instead of silently selecting a value.
8. Run live read-only canary against one liquid and one illiquid symbol, with
   explicit rate ceilings from the internal entitlement; redact all credentials.

## Test Matrix

| Dataset/case | Expected |
|---|---|
| OHLCV valid range | Rows sorted, bounded, post-filtered, VND-normalized, timezone explicit. |
| Quote valid | Snapshot fields typed; absent observation timestamp yields degraded/unavailable, never “live now”. |
| Trades valid limit | Returned rows never exceed host cap even if provider ignores `limit`. |
| Invalid symbol/reversed dates/weekend | Stable input/no-data code; no retry storm. |
| KBS vs VCI conflict | Both identities preserved; quality is conflict/degraded. |
| Schema drift/missing field | Fail closed with `schema_drift`; raw hash retained in trace. |
| Tool called in chat mode | Not in resolved surface / unknown tool, no dispatch. |
| Non-internal profile | Tool unavailable even with credentials installed. |
| Result too large | Deterministic cap/refusal before model context. |
| Secret scanner | No key in schema, result, trace, SSE or logs. |

## Verification Commands

```bash
cd apps/api && pytest -q tests/test_agent_market_data.py tests/test_agent_toolsets.py tests/test_agent_tool_registry.py tests/test_agent_evidence_contract.py tests/test_agent_untrusted_results.py
python -m compileall -q apps/api/src apps/api/tests
git diff --check
```

Live canary is manual, read-only and budgeted; its exact command belongs in the
phase report and must refuse to start without `personal_internal` profile.

## Success Criteria

- [ ] All three datasets pass deterministic contract tests and bounded live
      canary, or unsupported providers/datasets remain disabled explicitly.
- [ ] One market call equals one admitted provider operation; no hidden fan-out.
- [ ] Every accepted number has unit, time, source and two hashes.
- [ ] Existing web/memory tools and chat tool surface are unchanged.
- [ ] Production cannot expose the package or tool by configuration accident.

## Risks And Rollback

**Schema/provider drift:** capability returns `schema_drift` and stops; it never
coerces unknown fields. Roll back by removing the `market_data` bundle and
dependency; web evidence remains functional.

**License scope changes:** immediately disable the internal availability flag.
Tool traces/ledger remain historical evidence under the retention policy; any
required deletion is a separate reviewed data decision.
