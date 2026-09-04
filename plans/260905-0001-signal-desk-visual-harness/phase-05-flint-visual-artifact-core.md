---
phase: 5
title: "Flint Visual Artifact Core"
status: todo
priority: P1
effort: "20h"
dependencies: [2, 4]
---

# Phase 5: Flint Visual Artifact Core

## Context Links

- Phase 2 Flint MCP report and fixtures
- `apps/api/src/agent/loop.py::TurnOutcome`
- `apps/api/src/agent/turns.py::assistant_message`
- `apps/api/src/agent/persistence.py::finish_turn`
- `apps/api/src/agent/evidence/contracts.py`
- `apps/web/src/lib/alpha-desk/types.ts`
- `apps/web/package.json`

## Overview

Create one versioned visual part that is durable with the assistant message.
The model proposes chart intent and evidence references, never literal market
data. The host resolves those references to validated market rows and assembles
official `ChartAssemblyInput`. The browser validates/compiles it through the
pinned Flint package and renders with ECharts.

No legacy artifact table, artifact endpoint, Board DSL, widget catalog or
server-side chart compiler is reintroduced.

## Requirements

- Functional: visual exists only for `signal_desk` Turns whose host readiness
  is `ready_answer` and whose required structured evidence passed validation.
- Functional: model visual draft contains chart kind, field mappings, labels
  and evidence references; any literal series values from the model are refused.
- Functional: host hydrates every row/value from accepted tool results and
  stores exact evidence IDs, source call IDs, `as_of`, units and content hash.
- Functional: persisted payload is the official `ChartAssemblyInput` plus a
  small host envelope; reopening a Thread does not call model/tools again.
- Functional: frontend calls official Flint validate/compile on each render;
  compiled ECharts option remains memory-only.
- Functional: invalid draft gets at most one tool-free strict repair if budget
  remains; after that text settles with visual status `unavailable`.
- Non-functional: pin exact `flint-chart` and compatible ECharts versions from
  Phase 2; package source and templates remain byte-unmodified.
- Non-functional: default Flint chart/theme behavior is retained. Host CSS may
  size/pad the surrounding panel but cannot traverse or rewrite compiled option.
- Security: assembly row/series caps, string length caps and allowlisted chart
  types prevent a model payload from exhausting the browser.

## Visual Part Contract

```json
{
  "version": 1,
  "renderer": "flint-echarts",
  "flintVersion": "<pinned>",
  "status": "ready | unavailable",
  "asOf": "<timezone-aware ISO-8601>",
  "assembly": "<official ChartAssemblyInput when ready>",
  "evidenceIds": ["..."],
  "sourceCallIds": ["..."],
  "contentSha256": "<hash of canonical envelope inputs>",
  "reason": "<stable code only when unavailable>"
}
```

`assembly` is absent when unavailable. The transcript's `text`/`answer` remains
the text response; `visual` is a sibling part and is excluded from model history.

## Data Ownership

```text
model: chart intent + evidence/field references
host:  resolve references + exact rows + caps + provenance + canonical hash
Flint: validate + compile chart assembly
ECharts: render compiled output
```

The host may construct Flint input; it may not edit what Flint compiled. The
only lawful data mutation after normalization is deterministic field selection
and row ordering needed by the documented Flint input contract.

## File Inventory

| Action | File | Purpose |
|---|---|---|
| Create | `apps/api/src/agent/visual.py` | Visual draft validation, evidence binding and durable envelope. |
| Modify | `apps/api/src/agent/loop.py` | Build visual after readiness/ledger; carry it on draft/outcome. |
| Modify | `apps/api/src/agent/turns.py` | Checkpoint and persist optional `visual` sibling part. |
| Modify | `apps/api/src/agent/persistence.py` | Pass visual through existing terminal transaction only if current signature requires it. |
| Modify | `apps/api/src/agent/evidence/pipeline.py` | Expose accepted market rows/field identities to visual binding. |
| Create | `apps/api/tests/test_agent_visual.py` | No-literal-data, binding, caps, hashing and replay tests. |
| Modify | `apps/api/tests/test_agent_turn_lifecycle.py` | Terminal/checkpoint/restart persistence. |
| Modify | `apps/web/package.json` and `apps/web/pnpm-lock.yaml` | Pin official Flint and ECharts packages. |
| Create | `apps/web/src/lib/flint/compile-visual.ts` | Thin validate/compile call; no option rewriting. |
| Create | `apps/web/src/lib/flint/compile-visual.test.ts` | Compile Phase 2 fixtures and reject malformed payloads. |
| Modify | `apps/web/src/lib/alpha-desk/types.ts` | Add `VisualPart` to assistant content type. |
| Modify | `apps/web/src/lib/alpha-desk/read-content.ts` | Parse bounded visual envelope independently of chat text. |

No migration: `agent_message.content` and `agent_turn.draft_content` are the
existing versioned JSON persistence path for typed parts. The retired
`agent_artifact` schema is not mapped or reused.

## Function And Interface Checklist

- [ ] `VisualDraft` accepts only an allowlisted chart type and evidence-backed
      field references; no `data`, `series.values`, HTML, JS or formatter code.
- [ ] `build_visual_part(draft, evidence, calls, as_of)` is deterministic and
      fails closed on missing call/evidence/field/unit/time.
- [ ] Canonical hash uses stable JSON ordering and includes exact selected rows,
      evidence identities, assembly input and pinned Flint version.
- [ ] Maximum series, rows, points, labels and serialized bytes are declared
      once and tested at boundary/over-boundary.
- [ ] `TurnDraft`/`TurnOutcome` carry optional visual through every checkpoint,
      complete, incomplete, cancelled and restart path without orphaning calls.
- [ ] `assistant_message(..., visual=None)` writes no key for legacy/chat Turns.
- [ ] `parseVisualPart` validates version/status/hash shape before compile.
- [ ] `compileVisual` calls only official Flint public API and returns either
      official compile output or a stable error; it never mutates input/output.
- [ ] No generated ECharts option appears in API payload, DB fixture, snapshot,
      trace, log or committed artifact.
- [ ] Package-lock diff contains only exact dependencies required by Flint.

## Implementation Steps

1. Import exact public types/API learned in Phase 2 and pin package versions;
   first compile the two existing fixtures in a web unit test.
2. Write backend tests proving model literal data is rejected and every allowed
   visual value round-trips from a named market tool field.
3. Implement `VisualDraft` and deterministic host hydration. Start with only
   chart types proven by Phase 2; do not expose Flint's whole catalog speculatively.
4. Add optional visual to checkpoint/outcome/message builders and all terminal
   replay paths. Keep it out of transcript construction sent back to the model.
5. Add frontend runtime parsing plus a one-function Flint compile wrapper.
6. Test invalid version, hash, missing evidence, too many points, unsupported
   chart and corrupted persisted payload. All degrade to unavailable, not crash.
7. Run a fixture through backend assembly → persisted JSON → web parser → Flint
   compile and compare semantic fields to the Phase 2 MCP output.
8. Search the repository for ECharts option persistence/post-processing and for
   changes under installed Flint source; both must be zero.

## Test Matrix

| Scenario | Expected |
|---|---|
| Valid OHLCV evidence | Host builds assembly; official Flint compile succeeds. |
| Valid two-series evidence | Deterministic series order and source mapping. |
| Model supplies literal data | Backend refuses draft; no visual assembly. |
| Evidence ID/call ID missing | `unavailable: missing_visual_evidence`. |
| Unit/time ambiguous | No chart; text truth contract remains. |
| Row/byte cap exceeded | Deterministic refusal before persistence/browser. |
| Invalid Flint assembly | One bounded repair at most, then unavailable. |
| Refresh/restart | Same content hash and assembly; no tool/model call. |
| Chat mode | No `visual` key at any lifecycle stage. |
| Corrupt historical visual | Parser isolates failure; transcript still renders. |

## Verification Commands

```bash
cd apps/api && pytest -q tests/test_agent_visual.py tests/test_agent_turn_lifecycle.py tests/test_agent_persistence_paths.py tests/test_agent_evidence_renderer.py
pnpm --dir apps/web test -- src/lib/flint/compile-visual.test.ts src/lib/alpha-desk
pnpm --dir apps/web type-check
python -m compileall -q apps/api/src apps/api/tests
rg -n 'echarts.*option|compiledOption|setOption' apps/api apps/web/src
git diff --check
```

The `setOption` search may find the one official render invocation; any store,
serializer or mutation of that object fails the phase.

## Success Criteria

- [ ] Backend-to-browser fixture compiles with official Flint and preserves
      exact evidence-backed values.
- [ ] Zero model-authored numeric series points reach persisted assembly.
- [ ] Zero generated ECharts options are persisted or post-processed.
- [ ] Refresh/restart replay is deterministic and adds no network/model work.
- [ ] Chat/evidence behavior survives an invalid or absent visual.

## Risks And Rollback

**Flint input changes:** pinned compile test fails before deploy; upgrade requires
a fixture migration decision, not a fallback compiler.

**Message payload too large:** lower bounded row cap or aggregate server-side
from explicit evidence only; do not add an artifact service without measured
need. Rollback removes optional visual fields and web dependencies while leaving
all text/evidence data intact.
