# A chart is a typed, versioned Widget from a server-owned registry — never a model-authored spec

The agent produces a visual by naming a **Widget** from a registry and binding it to
registered fields returned during the same Turn. It may not emit a chart grammar,
run code to produce an image, invent values, change units, or control colours and
layout.

The model chooses: a stable Widget name, the tool-produced data binding, which
registered fields to display, and a short title. The server chooses: the pinned
Widget version and every presentation default.

## Why a registry and not a chart grammar

A free-form spec (Vega-Lite-shaped) hands the model the axis, the encoding, and the
scale — which is another way of saying it hands over the units and the sign. That
reopens exactly what ADR-0010 closed: a field whose `interpretation` is the only
sanctioned reading cannot survive a model choosing to plot it inverted or against a
truncated axis. A registry keeps the reading with the field.

The second reason is degradation. An unknown Widget version or a malformed spec must
leave a readable answer behind, and a named-and-versioned tuple can be looked up and
missed cleanly. A grammar fails at render time, inside the transcript.

## Where validation happens

Twice, on both sides of persistence.

1. `apps/api` validates the selection against the Widget-specific schema **before**
   persisting: the data binding came from the current authorized Turn, every
   requested field is registered, `unit` and `as_of` are intact, and the
   combination is supported. A `widget.ready` event is emitted only after the spec
   is validated and checkpointed.
2. `apps/web` validates the persisted spec again before looking up
   `(name, version)` in its component registry. An unknown version, malformed spec,
   or missing component degrades to the text answer and never crashes the
   transcript.

## The initial registry

| Registry name | Purpose | Source |
| --- | --- | --- |
| `metric_comparison` | one registered field across symbols | a registry-owned horizontal comparison leaf, adapted from the generic shape of the existing sector comparison chart |
| `ranked_symbols` | ordered Universe screening results | new, mobile-first ranked list; bars only where their length carries meaning |
| `metric_trend` | a registered analytical field over a fixed historical window | a registry-owned generic trend leaf extracted from the existing Recharts patterns |
| `relative_position` | where a value sits against its own history or the Universe | a new accessible range/percentile strip informed by the existing range-card primitive |
| `quarterly_financials` | stored statement figures across the reporting periods a lookup returned | added by ADR-0023; a table rather than a picture, drawn with the same `WidgetTable` every other entry carries as its accessible equivalent |

`Sparkline` may be reused as an internal primitive but is not model-selectable. Pie,
radar, candlestick, 3D, arbitrary specs, and image generation are outside the v1
registry. When a supported request has too little data for a useful visual, the
renderer uses concise bullets or a small table.

The registry must be built from **leaf charts, not cards**. Of roughly thirty
existing components only `Sparkline` and `StockIndexCard` are genuinely generic and
`SectorHistoricalChart` is one export away; ten more are generic-shaped but
response-typed, and thirteen take `symbol` and fetch their own data. Each of those
needs the same mechanical split, because each opens by flattening a domain object
into exactly the series a generic chart would take.

## What a Widget may not redraw

Alpha Desk never redraws a chart Stock 360 already owns: OHLCV, candlesticks,
volume, valuation history, price ranges, peer valuation. Those requests deep-link to
`/analytics/deep-dive?symbol=`. One number lives in one place, and a second drawing
of it is a second thing to keep correct.

The fixed Analysis artifact remains the only owner of the registered price-zone
band, which is its one inline graphic.

## A Widget is optional evidence, not the answer

- The answer starts with a clear conclusion in two to four concise bullets.
- A Widget appears only when a visual makes a comparison, ranking, trend, or
  relative position easier to understand than text. A single value stays text.
- The default ceiling is **three Widgets per answer**; a fourth requires an
  explicit user request. This is the anti-spam rule, and it is a protocol
  constraint rather than a style preference. It was **one** here originally, and
  `docs/specs/0004` D11 raised it: one picture per answer cannot serve a question
  about several things at once, which is most of the questions this product is
  for. ADR-0023 records the change and the measurement behind it. The user's own
  words remain the only thing that raises it further (`user_requested_multiple`),
  and `WIDGET_CEILING` in `apps/api/src/agent/widgets.py` is the authority.
- Formulae, method names, sources, and implementation detail live under **View
  details**.

## Historical semantics

A reopened Thread is a historical record. Every Widget visibly carries its data
date, reopening re-renders **the same fixed historical slice**, and `latest` is never
silently re-evaluated. *Update with new data* starts a new Turn rather than mutating
the old one.

The persisted spec therefore stores a **fixed-date retrieval descriptor, not the
series**. The 24-hour Redis `data_ref` is a hot cache only; after expiry the same
historical slice is reconstructed from the store, which is sound because EOD data is
settled. Embedding the data would copy the same price array into the database once
per chart, forever. If the slice or the renderer can no longer be reconstructed, the
text answer stays readable and the Widget shows a compact unavailable state.

## Considered Options

- **A free-form chart specification the web renders.** Rejected above: it hands the
  model the units and fails at render time.
- **A sandbox producing an image.** Still rejected after ADR-0019: `run_python`
  returns bounded JSON only. A rendered artifact would have no required data table,
  keyboard operation, or screen-reader path.
- **Reusing the existing dashboard cards directly as widgets.** Rejected: they are
  response-typed and fetch their own data, so a widget built on one would re-query
  today's numbers inside a historical answer — the exact staleness bug this ADR
  closes.

## Consequences

- Text streams first, and a Widget gets a stable placeholder so the transcript does
  not jump while data loads.
- **Expand** opens the same fixed data full-screen with a readable data table, its
  data date, and a **View calculation** disclosure. There is no BI-style chart editor
  in v1.
- On narrow screens a Widget uses the available width and may switch to a list or
  table rather than forcing horizontal scrolling.
- An agent-added optional Widget that fails disappears without noise; a
  user-requested one leaves the text answer plus a short *Unable to display this
  visual* state with **Retry**.
- Every Widget has a textual summary, keyboard operation, screen-reader labelling,
  reduced-motion support, and a data-table equivalent in the expanded view. Colour
  never carries meaning alone.
- The registry owns an accessible semantic palette and does **not** inherit the two
  defects measured in the existing charts: eight charts paint series pure white
  while the app is `forcedTheme="light"`, and `--stock-up` / `--stock-down` are
  referenced but never defined. Inheriting a shared chart layer would inherit both.
