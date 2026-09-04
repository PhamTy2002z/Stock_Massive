---
phase: 2
title: "Official Flint MCP Demo"
status: todo
priority: P1
effort: "8h"
dependencies: [1]
---

# Phase 2: Official Flint MCP Demo

## Context Links

- [microsoft/flint-chart](https://github.com/microsoft/flint-chart)
- Flint packages and MCP tools at the exact release pinned during preflight
- `apps/web/package.json`
- `apps/web/src/components/signal-desk/signal-desk-empty.tsx`

## Overview

Prove the visual choice before touching the product path. Run the official
`flint-chart-mcp` locally, with local file references disabled, and produce one
ECharts candlestick/volume view plus one comparison chart from bounded inline
data. This phase validates Flint's public contract and original visual output;
it does not add MCP to the application runtime.

## Requirements

- Functional: use official tools only: `create_chart_view`, `validate_chart`,
  `compile_chart`/`render_chart` as exposed by the pinned release.
- Functional: demonstrate native candlestick/OHLC support and one multi-series
  comparison using explicit `ChartAssemblyInput`.
- Functional: capture input, validation result, package/version and screenshot;
  generated ECharts option is ephemeral and must not be committed.
- Security: start MCP with `--disable-file-reference`; provide inline synthetic
  fixture only; no repo file, secret, Vnstock key or live account data is sent.
- Non-functional: no patch/fork/template override; no CSS applied inside Flint
  output; no application API, DB or SSE change.

## Architecture Boundary

```text
synthetic bounded rows
  → official Flint MCP create/validate
  → official Flint compile (ECharts)
  → official renderer screenshot
  → report + reusable ChartAssemblyInput fixture
```

The fixture proves the contract later used by the web package. MCP itself is a
throwaway adapter for the demo, not the product's compiler service.

## File Inventory

| Action | File | Purpose |
|---|---|---|
| Create | `apps/web/src/components/signal-desk/__fixtures__/flint-candlestick-input.json` | Bounded official assembly fixture, no generated option. |
| Create | `apps/web/src/components/signal-desk/__fixtures__/flint-comparison-input.json` | Multi-series contract fixture. |
| Create | `plans/260905-0001-signal-desk-visual-harness/reports/phase-02-flint-mcp-demo.md` | Version, commands, validation and screenshots/links. |
| Verify only | `apps/web/package.json` | No runtime dependency yet. |

## Interface Checklist

- [ ] Verify package names, release version, CLI flags and public exports from
      the installed release; do not infer them from memory.
- [ ] Fixture is valid `ChartAssemblyInput`, not an ECharts option object.
- [ ] Every data field has an explicit type and deterministic row order.
- [ ] Candlestick uses Flint's native ECharts path; no custom series renderer.
- [ ] Validation failure returns a typed/structured error suitable for Phase 5.
- [ ] Demo process is tracked and terminated at the end of the phase.

## Implementation Steps

1. Verify official package metadata, license, package integrity and docs at the
   pinned release (observed candidate `0.5.1`; pin only after registry check).
2. Run CLI `--help`; record exact stdio/HTTP and file-reference flags before
   starting a process. Bind any HTTP demo to loopback and one deterministic port.
3. Build two small synthetic inputs: OHLCV candlestick+volume and two-symbol
   normalized comparison. No live financial claim belongs in this spike.
4. Call list/validate/create/compile/render in that order; save only assembly
   inputs and report evidence.
5. Run one negative case with malformed field mapping and one attempted file
   reference; both must be refused without reading disk.
6. Visually inspect screenshots for labels, axes, tooltip, legend and resize;
   record observed behavior without changing Flint defaults.
7. Stop the MCP process, confirm its port/process is gone and leave no generated
   ECharts option or downloaded source tree in the repository.

## Test Matrix

| Scenario | Expected |
|---|---|
| Valid OHLCV | Native candlestick and volume render successfully. |
| Valid comparison | Both series, legend and time axis compile successfully. |
| Missing required field | Official validator returns failure; no render. |
| Local file reference | Refused under `--disable-file-reference`. |
| Repeated compile | Same input compiles deterministically enough for semantic snapshot; input remains unchanged. |
| Resize | Official renderer remains legible at desktop right-pane dimensions. |

## Verification Commands

The report records the exact verified CLI invocation. Free repository checks:

```bash
pnpm --dir apps/web exec prettier --check src/components/signal-desk/__fixtures__/*.json
git diff --check
git status --short
```

## Success Criteria

- [ ] Both positive fixtures pass official validation and compile/render.
- [ ] Both negative fixtures fail at the official boundary.
- [ ] Visual output is Flint's unmodified output.
- [ ] No MCP process, generated option, source fork or runtime dependency remains.
- [ ] Report gives Phase 5 exact imports, types and failure behavior to use.

## Risks And Rollback

**Package surface differs from inspected source:** stop and update this phase
from release docs; do not build a compatibility wrapper around guessed APIs.

**Candlestick cannot meet baseline:** mark the plan blocked and reconsider the
library choice via a new deviation. Rollback is deletion of two synthetic
fixtures and the demo report; production remains untouched.
