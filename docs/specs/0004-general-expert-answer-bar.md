# Product specification — the General-Expert Answer Bar

Why the agent's answers today lose to pasting the same question into ChatGPT, and
what has to change so they win. This spec records the decisions closed in the
2026-08-17 grilling session with the product owner, defines the acceptance bar for
answer quality, and orders the work.

Read with:

- [`0003-intelligent-quant-architecture.md`](0003-intelligent-quant-architecture.md) —
  the architecture this spec adjusts, not replaces. Store-only tools, the Signal
  Registry, the Recommendation Gate and the Eval Battery all stand; this spec feeds
  them and re-tiers one of them.
- `CONTEXT.md` — every **bold** term, including the three added by this spec:
  **Hydration**, **Answer Tier**, **Golden Question Set**.
- `docs/eval/2026-08-17-1.4.0.json` — the measured evidence behind §1.

## 1. The problem, measured

Two real user questions failed on 2026-08-17:

1. *"Tình hình báo cáo tài chính Masan các quý gần nhất"* → "one reporting period,
   detailed line items unavailable." Root cause: `get_financials` serves two figures
   per period (TTM net income, parent equity) from a store that holds **one**
   fundamental Snapshot per symbol, and hard-codes the statement line items as
   `unavailable` on every call (`src/agent/tools/data.py:523`). A full
   `FinancialService` (revenue, margins, ROE/ROA, CFO/CFI/CFF, FCF, 8 quarters)
   exists but is REST-only and unreachable from the agent by the store-only wall.
2. *"Cho tôi xu hướng STB"* → one hedged sentence. Root cause: `trend_signal` and
   `momentum_rank` need ~253 stored sessions; Backfill is off and Warm-up loads 25,
   so every cross-sectional field refuses and the Contract correctly forbids the
   model to fill the gap.

The Eval Battery already measures this as systemic, not anecdotal
(`docs/eval/2026-08-17-1.4.0.json`):

- Category B (false refusal): **0/30**, bar ≥90%. 28/30 runs ended
  `incomplete/grounding_failed`.
- `answer_kinds: {analysis: 0, education: 4, none: 7, refusal: 0}` — nothing that
  reached the screen was a tool-backed analysis.
- The `grounding_failed` over-blocking tripwire the validator names (>5% of Turns)
  is blown by an order of magnitude on recommendation-shaped questions.

Conclusion of the session: the disciplined core (store-only tools, Signal Registry,
Recommendation Gate, Evidence Manifest) is the long-term moat and is kept intact.
It is currently **starved of data** and **tiered wrong**, and the product around it
under-presents what it does compute.

## 2. Decisions closed in the session

| # | Decision | Choice |
| --- | --- | --- |
| D1 | Target user | The owner and a small group now; the north-star persona is a retail investor on HOSE/HNX/UPCOM. Every answer must beat pasting the question into a general chatbot. |
| D2 | Moat | (a) Normalized VN market data with real history, (b) answers presented as data — tables, charts, widgets on the board — with (c) validated trust as the layer above. Realtime is explicitly **out**: EOD/offline done well is the v1 bar. |
| D3 | Quality axes | All three — data completeness, answer depth, UX smoothness — fixed in that order. |
| D4 | Fundamentals path | Keep store-only. Widen the `fundamental` Capability payload to full statement line items per quarter, fill it by **Hydration** on demand plus a scheduled backfill for VN30 + Watchlist symbols. No agent tool ever calls a Provider Source directly. |
| D5 | Price history | Enable Backfill for VN30 + Watchlist first (~50 symbols), measure real quota burn on the free vnstock tier, then widen. Other symbols go through Hydration. |
| D6 | Data budget | Stay on the free vnstock tier (20 req/min). Correct processing before paid quota; upgrade only after the owner validates quality. |
| D7 | Gate tiering | Introduce **Answer Tiers**: the full seven-condition Recommendation Gate applies to buy/sell recommendation blocks with price zones; stance/trend/overview questions are served at the analysis tier — every figure attributed, no zone required. |
| D8 | Missing data behaviour | An unanswerable question returns what the store has, names the gap precisely, and enqueues Hydration — never a bare refusal and never a blank `grounding_failed` Turn. |
| D9 | General-expert scope | Enable the web lane (`web_tools_enabled=True`). Company-fact, leadership, and market-context questions are in scope, answered as **External Claims** with visible sources. |
| D10 | Progress visibility | The stream shows real steps — the actual search queries issued, sources found, data being read — replacing the four generic phases. Raw prompts, reasoning, and tool internals stay hidden. |
| D11 | Visual answers | Up to 3 Widgets per answer (was 1). Add a quarterly-financials table widget type to the registry. Follow-up suggestion chips after every answer. |
| D12 | Quality measurement | The **Golden Question Set** (§4) enters the Eval Battery through the confirmed-flagged-message door and category B's bar is enforced once the data foundation (D4/D5) lands. |

## 3. The reference bar

The acceptance reference is the behaviour the owner captured from a competing
product (rebo.ai.vn — which, per its own footer, runs on the same free vnstock
source; the gap is processing and presentation, not data access):

1. **Progress is legible.** The user watches a timeline: thinking → the actual
   search queries → "found 15 results" with a source list → done. Never a spinner
   with a generic label.
2. **Answers are cited and structured.** A factual question ("who chairs Masan?")
   gets a bolded direct answer, bullet evidence, per-claim source chips, and
   follow-up suggestions.
3. **Analysis carries data.** A market/trend question gets sections, figures with
   dates, and at least one structured block (table or chart), not a lone hedged
   sentence.

An answer meets the bar when a reader gains something they could not get by
pasting the question into a general chatbot: real store figures with as-of dates,
a rendered data block, or a validated, cited claim.

## 4. Golden Question Set (seed)

The set the system must answer well, each mapped to the lane that serves it.
The first two are the owner's flagged answers from 2026-08-17.

| # | Question (shape) | Lane | Minimum passing answer |
| --- | --- | --- | --- |
| G1 | Financial results of {symbol}, recent quarters | store: fundamentals | ≥4 quarters of revenue, net profit, margins with reporting dates + quarterly table widget |
| G2 | Trend of {symbol} | store: signals | 3m/6m/12m returns, momentum/RS readings with values + price/trend widget |
| G3 | Who chairs / leads {company}? | web lane | Direct cited answer, source chips |
| G4 | How is the market today? | store + web | Index moves with figures, breadth, driver names, sources |
| G5 | Compare {A} vs {B} | store: cross-sectional | Side-by-side registered fields + comparison widget |
| G6 | Debt / cash flow health of {symbol} | store: fundamentals | Leverage and CFO/FCF figures across quarters |
| G7 | Which {industry} symbols look strongest? | store: screen | Ranked list with the fields that ranked them |
| G8 | Foreign flow in {symbol} | store: foreign_flow | Net-flow readings with dates (once money flow is wired) |
| G9 | Should I buy {symbol}? | recommendation tier | Full Recommendation Gate, or a precise statement of what evidence is missing plus what *can* be said at the analysis tier |
| G10 | {symbol} not in Universe | structured refusal | Same-industry alternatives + Hydration offer, never a dead end |
| G11 | Out-of-domain question | general | Honest general answer or scoped refusal — never a blank Turn |
| G12 | Question that needs data currently absent | Hydration | Partial answer + named gap + "loading now" with a working retry |

## 5. Workstreams, ordered

### W1 — Fundamentals depth (unblocks G1, G6)

- Extend the `fundamental` Capability payload from 3 fields to the statement line
  items `FinancialService` already normalizes (income statement, balance sheet,
  cash flow, ratios), one Snapshot per `(symbol, period_end)`.
- Persist history: a fundamentals backfill for VN30 + Watchlist (8–12 quarters);
  Hydration for the rest.
- Delete the hard-coded `unavailable` list in `get_financials`; serve N periods
  with per-figure staleness stamps. Respect `MAX_TOOL_RESULT_BYTES` by serving the
  trend-metric summary shape, with a `data_ref` for full line items.

### W2 — Price history (unblocks G2, G5, G7)

- Enable Backfill scoped to VN30 + Watchlist; measure quota burn; widen only after
  measured headroom on the free tier.
- Wire the Corporate Action prerequisite per spec 0003 §"Prerequisites" — trailing
  windows are not trustworthy without it.

### W3 — Hydration (unblocks G10, G12; ADR planned)

- A user question may enqueue a bounded Hydration request; the Collector executes
  it. The Collector invariant — user requests never touch a Provider Source —
  stands.
- The agent's structured refusals gain a `hydration_queued` state the UI renders
  as "loading, retry in ~a minute".

### W4 — Answer Tiers (unblocks G2, G9; fixes category B) — **done**

The diagnosis this workstream was written against turned out to be wrong, and
the real cause is narrower and worse. Category B did not fail because the Gate
was mis-tiered. It failed because **the Gate's condition 3 had no route to
satisfy**: the only registered price-zone field, `price_zone.ordinary_range_pct`,
was declared in the Signal Registry, computed correctly in code, treated as core
evidence by the nightly Analysis — and served by **no tool in the catalog**. No
recommendation could name a zone computed in code, so every recommendation the
model wrote was refused, and category B was 0/30 by construction rather than by
data or by model quality.

Landed:

- A `price_zone` tool serves that field. Its details carry the anchor close a
  recommendation cites as its reference price (Gate condition 2) and the band it
  cites as its price zone (condition 3). Served alone rather than inside
  `risk_metrics`, because a cluster reports its widest field's Window Health and
  a 21-session zone would otherwise inherit a 250-session field's refusal —
  condition 4 blocking a recommendation over a window that never fed it.
- The System Prompt Contract's Gate section names where the zone and reference
  price come from. `PROMPT_VERSION` 1.4.0 → 1.5.0.
- Gate failures are split into two classes. An *availability* failure (the
  evidence for a recommendation was not there) drops the block and lets the Turn
  answer around it, carrying a backend-authored, figure-free sentence naming the
  condition that was not met. An *integrity* failure — above all a figure that
  contradicts its own citation — still ends the Turn. The Evidence Manifest
  records a degrade as a blocked recommendation either way.

Not landed, and no longer believed necessary: a separate analysis-tier
validator. Prose already releases under the lighter bar (ADR-0018), so the tier
distinction the spec asked for exists in the code; what was missing was the
route, not the tier.

### W5 — General-expert lane (unblocks G3, G4, G11)

- `web_tools_enabled=True`; `search_news` and `fetch_url` results stay External
  Claims and can never establish zones or reference prices (unchanged).
- Activity events carry real step content: issued queries, source domains, counts.
  Prompts, reasoning, and raw tool payloads remain out of the stream.

### W6 — Presentation (the visible moat)

- Widget ceiling 1 → 3; add `quarterly_financials` table widget to the typed
  registry.
- Follow-up suggestion chips generated per answer.
- Citation chips on claims sourced from the web lane.

### Gate status of the W1 + W4 merge

W1 and W4 reached `develop` **without** the Eval Report
[`docs/agents/eval-battery.md`](../agents/eval-battery.md) requires of anything
touching the System Prompt Contract, the tool catalog or the Recommendation
Validator — all three of which they touch. Merged on the owner's explicit
instruction, and recorded here rather than left to be discovered.

What stands in its place: the fixture was re-frozen against the new tool
catalog, `apps/api` passes 2,376 tests, `apps/web` passes type-check, lint, 431
tests and a production build, and both flagged answers were re-run end to end
against the deployed loop (§1) and now return the figures they could not
before.

What is still owed: one passing gate run. It could not be produced because the
LLM route is a free tier allowing roughly fifty model calls a day, while a gate
run needs several hundred. The first paid or higher-quota route should run it
before any further change to these surfaces.

### W7 — Measurement

- Add the Golden Question Set to the Eval Battery via the flagged-message door;
  freeze a new Eval Fixture once W1/W2 data exists in the eval store.
- Definition of done for this spec: a gate run where B ≥ 90%, A/C/F at their
  bars, and every Golden Question class passes its minimum answer.

Order: W1 → W2 → W4 → W3 → W5 → W6, with W7 capturing fixtures as each lands.
W1 and W2 first because no prompt or gate change can cite data the store has
never held.

## 6. Scale path

1. **Now** — single owner + small group; Universe cap 100; VN30 + Watchlist get
   full history; free vnstock tier.
2. **Validated** — owner judges the Golden Set quality acceptable; upgrade the
   vnstock tier; widen Backfill to HOSE.
3. **Later** — public users; realtime lanes; predictive Claims behind the
   measured forward-return harness (per Signal Registry rules). Explicitly out of
   scope for this spec.

## 7. Open decisions

1. Whether the analysis tier needs its own eval category or re-uses B/D with new
   cases.
2. The exact `quarterly_financials` widget schema (columns, period count).
3. Whether follow-up suggestions are model-generated per Turn or templated per
   question class.
