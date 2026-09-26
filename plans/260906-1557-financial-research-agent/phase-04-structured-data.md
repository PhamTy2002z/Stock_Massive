---
phase: 4
title: "Nguồn structured và quyền sử dụng"
status: pending
priority: P1
effort: "8–12 engineer-days"
dependencies: [3]
---

# Phase 4: Nguồn structured và quyền sử dụng

Context: [Plan](./plan.md) · [Decision register](./decisions-and-dependencies.md) · [Validation](./validation-strategy.md)

## Overview

Cung cấp nguồn giá/benchmark/corporate action và BCTC structured khi có quyền, đủ để phục vụ nghiên cứu và phản ứng thị trường ở cả hai mode sau D2/D3.

## Requirements

- Không bật Vnstock community ở production; provider hiện tại giữ internal gate.
- Vendor selection dựa coverage, semantics và rights, không chọn từ tên SDK.
- Dataset schema bounded, units/time/adjustment/version explicit; unknown không giả thành 0.
- Không ingestion toàn thị trường, scheduler, stock store hoặc expose toàn SDK.

## Architecture

Question intent → resolved capability + entitlement → bounded dataset adapter → normalized observation/evidence → ledger.
Reuse registry/executor and market_data owner; provider-specific code stays ở adapter boundary. Nguồn public document vẫn là đường chuẩn cho thuyết minh và thông tin ngách.

## Related Code Files

| Action | Files |
|---|---|
| Modify | `apps/api/src/agent/tools/market_data.py`, `toolsets.py`, `registry.py`, `service.py`, `turns.py` |
| Modify | `apps/api/src/core/config.py`, `evidence/pipeline.py`, `evidence/source_policy.py` |
| Configuration after approval | `.env.example`, deployment compose files: nonsecret flags/capability settings only |
| Tests | `test_agent_market_data.py`, `test_agent_signal_desk_notes.py`, `test_agent_turn_lifecycle.py`, `test_llm_config.py` |
| Create conditionally | One actual chosen provider adapter next to market_data.py, no speculative provider hierarchy |

## Implementation Steps

1. Build source matrix for OHLCV, benchmark/index, adjustment/corporate actions, financial statements and public filings. Coverage includes listed/unlisted historical symbol status, HOSE/HNX/UPCOM, suspended/delisted names where rights permit.
2. For shortlisted sources obtain written terms for software use, upstream data access, display/redistribution, derived values, caching, retention and SaaS scope. Price quote alone is not entitlement.
3. Probe normal/empty/rate-limited/schema-drift cases and requested-vs-returned date ranges; unit/tz/bar-close/corporate-action conventions. Store sanitized manifests and samples under allowed retention.
4. Implement only approved datasets backed by real samples. Separate price raw/adjusted, absolute/index return, event available_at and data effective time.
5. Gate by deployment + dataset entitlement + request owner policy; mode does not grant rights. Authorized Chat may read data but never produces visual part.
6. Return bounded data reference, summary and targeted excerpts to model; full validated rows live in Turn evidence storage for host visualization. Avoid repeating 250 OHLCV rows in every prompt.
7. Add cache/single-flight at existing lane/seam when appropriate with source/date/basis/rights/version key. Do not mix tenants with different data rights.
8. Fallback only to entitled semantically compatible source; reveal real source and discrepancy. Unknown adjustment/time is explicit partial/unavailable.
9. Add source kill switch, retry-after handling within Turn bounds, provider health trace and denial/revocation cases.
10. Run canary and all source-rights gates before production flag opens; if no eligible source, customer data capability stays disabled and plan phase remains blocked for that dataset.

## Dataset acceptance

| Dataset | Required fields / special cases |
|---|---|
| Price/volume | requested/actual range, session, tz, adjustment, unit, gaps/suspension |
| Benchmark | index identity and methodology/basis, compatible timestamps, no silent equity substitution |
| Corporate action | event type, announcement/ex/record/payment dates when known, factors/version |
| Financial statement | entity, metric, period, consolidation, audit/restatement and source filing linkage |
| Sector/operating data | source report/period/unit; niche public reading supported even without API |

## Success Criteria

- [ ] Every enabled dataset has rights + owner + real canary + normalizer fixtures.
- [ ] 0 wrong-scale/time/basis acceptance on mutations; incomplete series disclosed.
- [ ] Chat/Signal read permission matches; only Signal renders chart; internal Vnstock remains denied in production.
- [ ] Revoked/expired entitlement cannot be bypassed by cache or stored visual replay.

## Validation

Focused market_data, config and lifecycle tests, then mode/source-rights golden and live source canary. No invented provider endpoint until vendor is selected.

## Risk Assessment

License or source discontinuation → disable affected capability and show precise gap; do not route covertly to scraped feed. Lack of commercial data is a delivery dependency, not a harness defect.

## Rollback / handoff

Per-provider/dataset kill switch; schema backwards reader retained. Preserve audit metadata consistent with rights; purge/restrict raw where contract requires. Handoff source manifest, probe artifact, operational quota and entitlement evidence.
