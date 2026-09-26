# Signal Desk Visual Harness — graduation report

- Date: 2026-09-05
- Branch: `develop`
- Phases delivered: 5 (Flint visual artifact core), 6 (Signal Desk right panel),
  7 (end-to-end quality gate) — **free half only**; the paid release run has not
  been made.
- Verdict: **not graduated**. Every free gate passes. Two gates are armed and
  have no data, and one requires a spend ceiling only the product owner can set.

## What now exists

**Backend.** `apps/api/src/agent/visual.py` assembles one optional visual part
from the successful `get_market_data` calls of a Turn, after
`validate_claim_ledger` has admitted the figures. One call becomes a candlestick
over a volume bar chart (two assemblies, because the pinned Flint candlestick
template has no volume channel); two to four comparable calls become one
multi-series line; anything else becomes no part at all. The model contributes
no number and no shape.

The part rides the existing checkpoint / outcome / message path
(`loop.py` → `turns.py`) under the absent-not-null rule the `question` key
already follows, so a message written before charts existed stays byte-identical.
No migration, no artifact table, no endpoint.

**Frontend.** `lib/flint/compile-visual.ts` is the one place a persisted part
becomes an ECharts option; `lib/alpha-desk/read-content.ts::readVisual` is the
one place it is read off the wire; `lib/alpha-desk/desk-visual.ts` decides which
chart the pane is about. `components/signal-desk/signal-desk-panel.tsx` draws the
four states and reaches ECharts and the compiler through dynamic `import()`, so
a chat-only reader downloads neither.

**Harness.** Three hard dimensions (`visual_grounding`, `visual_replay`,
`mode_isolation`), twelve new corpus cases across six new families, a
`source_rights` marker, and a browser-side Flint-validity gate. `gate.py`,
`Makefile` and `thresholds.json` are untouched, as the phase required.

## Two defects the phase found, and the fix for each

Both were latent in Phase 4 and would have failed **every** Signal Desk Turn.
Neither was visible from the unit tests that existed; both surfaced the first
time a Turn was driven end to end through the deep pipeline with the market
surface resolved.

**1. The planning gate refused the batch its own note asked for.**
`MARKET_PLANNER_NOTE` asks for three searches plus one `get_market_data` in one
batch. `AgentLoop._valid_planner_calls` required four calls *all* named
`web_search`, so a compliant Turn settled
`planner_did_not_produce_four_independent_searches` before reading anything.
Fixed at the gate: the batch shape is now decided by whether the market read is
on the resolved surface, the distinctness rule stays on the searches, and the
terminal reason is renamed to `planner_did_not_produce_the_batch_the_note_asked_for`.
Regression: `tests/test_agent_evidence_pipeline.py::test_the_planning_gate_accepts_the_batch_the_market_note_asks_for`.

**2. The ledger renderer crashed on evidence with no URL.**
`render_claim_ledger` called `canonical_url` unconditionally on every cited
source. A market row's locator is `vnstock:kbs/<symbol>/<interval>`, which is not
an http address, so the call raised `ValueError` inside the verification pass —
costing the reader the whole answer, prose and chart alike, for the sake of a
link that never existed. Fixed with `_public_locator`: a non-http locator renders
as no locator, which also keeps a connector slug out of a reader-facing citation.
The publisher, the title and the bar close already say what was read and when it
became knowable.

## Gates

### Passing, offline, reproducible

```bash
cd apps/api && pytest -q                       # 1554 passed, 3 deselected
python -m compileall -q apps/api/src apps/api/golden apps/api/tests
pnpm --dir apps/web lint
pnpm --dir apps/web type-check
pnpm --dir apps/web test                       # 511 passed, 2 skipped
E2E_NEXT_DIST_DIR=.next-verify pnpm --dir apps/web build
git diff --check
rg -n 'src\.(stocks|studies)|Study DSL|Board DSL|widget catalog|global watchlist' apps/api/src apps/web/src   # no matches
rg -n 'echarts.*option|compiledOption|setOption' apps/api apps/web/src                                        # one call site
```

The `setOption` scan returns exactly one call —
`signal-desk-panel.tsx::Canvas` — plus three comment or type references. No
ECharts option is stored, serialised or post-processed anywhere.

| Hard gate | State | Evidence |
|---|---|---|
| Terminality | pass | existing `settlement` dimension; `tests/test_agent_fault_injection.py` |
| Absolute bounds | pass | `tests/test_agent_loop.py` round and external-call ceilings per lane; `grade_budget` now reads the recorded lane, so a deep Turn is not held to the light cap |
| Duplicate dispatch / no progress | pass | `tests/test_agent_guardrails.py` (ladder, `call_signature`, `result_signature`) |
| Truth contract | pass | `tests/test_agent_evidence_*`, unchanged thresholds |
| Visual grounding | pass offline | `tests/golden/test_graders.py` proves the grader **fails** when one price is edited, when an evidence id is invented, and when a call id names another trial |
| Visual replay | pass offline | same file: a chart whose rows are reordered is still perfectly grounded and fails replay |
| Mode isolation | pass offline | same file, both directions; `rl-cc-001` is the live control |
| Flint integrity | pass | package unmodified, pinned `flint-chart@0.5.1` and `echarts@6.1.0`, exact; `test_agent_visual.py` reads the pin from `apps/web/package.json` so a bump cannot land on one side only |
| Internal-only data | pass | `tests/test_agent_market_data.py` profile gate; corpus test refuses a chat case marked `market_internal` |

### Armed, with no data yet

| Gate | Why it is empty |
|---|---|
| Flint validity over persisted artifacts | `grade-artifact.test.ts` finds no artifact carrying a `visual` key, because no run has produced one. It skips rather than passes, and will decide as soon as one exists. |
| Visual grounding / replay / mode isolation on live data | The graders are proven against fixtures. They have not yet seen a Turn that spent money. |

### Not run

**The paid release run.** It needs a ceiling the product owner sets:

```bash
make -C apps/api golden-release CEILING_USD=<amount> TRIALS=<n>
make -C apps/api golden-release CEILING_USD=1 RELEASE_ARGS="--grade-only golden/artifacts/<file>.json"
```

**The internal Vnstock canary.** Read-only, one call, to confirm the provider,
the package version and the profile still work before spending the ceiling.

**Phase 6 step 7** — a real Signal Desk Turn with a refresh mid-flight and a
Thread switch, with screenshots. It needs the same live stack as the paid run,
and it is the one acceptance criterion in Phase 6 that no offline test can
stand in for.

## Deviations from the phase plans, and why

**`assembly` became `assemblies` (a list).** Phase 5's contract sketch shows one
`assembly` key. Its own shape table then asks a single market call to produce
"candlestick + volume — exactly the Phase 2 fixture", and the Phase 2 contract
test proves the pinned candlestick template has **no volume channel**. Price and
volume are therefore two chart inputs and two compiled options. The alternative —
merging them after compilation — is editing Flint's output, which the plan
forbids outright. The list is what the phase's own findings require.

**`"part.visual"` was not added to the client event union.** Phase 5's file
inventory names it, but nothing publishes such an event: the chart is written at
the terminal transaction and read from the persisted message, exactly like the
question card's stored half. A union member no transport emits would be dead
code, and `types.ts` says a client only ever sees events it subscribed to. The
`VisualPart` type and the `AssistantContent.visual` field were added.

**One golden hard gate stayed cut.** Phase 7 already removed "call intent" as
unmeasurable (`gaps` exist only after a research pass; calls happen before it).
Nothing here revived it.

**`live-turn.ts` was not modified.** Phase 6's inventory expected the visual to
travel through the live reducer. It does not need to: the chart exists only at
the terminal, the terminal already triggers a Thread refetch, and
`selectDeskView` reads it from the Thread's own messages. That is also what makes
"a running Turn shows no old chart" a property of one pure function rather than a
rule spread across a reducer and a component.

**Fault injection was not extended.** Phase 7 lists cancel, deadline, provider
failure, permission denied and every ceiling. All of them are already covered —
cancel, deadline, restart and route failure in `test_agent_fault_injection.py`;
round and external-call ceilings and permission denial in `test_agent_loop.py`;
duplicate and no-progress in `test_agent_guardrails.py`. What was genuinely
missing was the deep pipeline driven end to end with the market surface on, and
that is what `test_agent_evidence_pipeline.py` now has — which is how both
defects above were found.

## Known limits

- **`source_rights` is a corpus declaration, not a runtime gate.** The runtime
  gate is the profile check in `tools/market_data.py`, which is unchanged and
  tested. The marker exists so a case cannot be run somewhere its data licence
  does not reach; a corpus test refuses a chat case that claims the internal
  feed.
- **The empty-versus-no-chart distinction is approximate.** The pane shows the
  opening board when the Thread has no assistant message at all, and "this answer
  has no chart" otherwise. A reader who switches the desk on over a chat-only
  history sees the second line. It is true — that answer has no chart — but it is
  not the invitation the first line is. Making it exact would mean persisting the
  Turn's mode on the message, which is a schema change nothing else needs yet.
- **Production Vnstock stays disabled.** The community licence is personal and
  non-commercial. Nothing in this work changes that, and nothing should be read
  as clearing it: production remains fail-closed until the software licence and
  the upstream data right exist in writing.

## Before this can be called graduated

1. Owner sets `CEILING_USD` and `TRIALS`.
2. Internal read-only canary against the live provider.
3. One `golden-release` run; trial one records the tape, later trials replay it.
4. Grade offline until deterministic; fix product defects, never the gate.
5. Re-run `grade-artifact.test.ts` — it will stop skipping.
6. Only then update `docs/roadmap.md` and `CLAUDE.md` to record the capability as
   current, and close the superseded Signal Desk compiler plan.
