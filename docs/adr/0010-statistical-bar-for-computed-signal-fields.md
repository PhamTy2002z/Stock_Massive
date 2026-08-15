# Statistical bar for computed signal fields

Every model-visible number is a **Signal Field** registered in a **Signal
Registry**, and the bar it must clear is a property of the *field*, not of the
tool that returns it. The tool layer serializes registered fields only, so an
unregistered computation has no route to the model.

Each field declares `unit`, `sign`, `interpretation`, `kind`, `claim`, `source`,
`min_sessions`, `threshold`, and `null_fpr`.

| `kind` | What it is | Bar |
| --- | --- | --- |
| `estimator` | a point estimate with a sampling distribution | must carry SE or CI |
| `percentile` | a cross-sectional position | must carry `n` and the cutoff date |
| `signal` | has a threshold, can fire | the full bar below |

## Why the field and not the tool

The five computation clusters of ADR-0009 each mix kinds. `risk_metrics` holds
Yang-Zhang realized volatility — an estimator with no threshold and nothing to
fire — beside drawdown against the E[MDD] ≈ 1.25σ√T benchmark, which fires.
Applying the bar per tool would either force meaningless null runs on estimators
or exempt a whole cluster because one of its fields is descriptive.

## Null Calibration

Every `signal` field ships against **two** nulls, ≥1000 paths each:

1. **Matched-volatility GBM**, with and without ±7% truncation.
2. **A stationary block bootstrap on the symbol's own return history** — GBM has
   neither fat tails nor serial dependence, so a detector silent on GBM can still
   fire constantly on a real quiet series.

The published rate is the **maximum** of the two, and **FPR ≤ 1% is fixed
catalog-wide**, not declared per tool. A self-declared rate is exactly what the
rejected external library did, and it only ever drifts upward when an author wants
their tool shipped. A field that cannot reach 1% gets a stricter threshold or does
not enter the catalog.

**Thresholds are derived from the null**, offline, and frozen as constants in the
registry — never calibrated at runtime, which would make the threshold a function
of today's data. Where the literature has a conventional threshold (RSI 70, z = 2,
1.25σ√T), the **stricter** of convention and derived value wins, and the registry
records which won: that is precisely the line a reviewer will want to argue with.

`null_fpr` rides in the **tool schema description**, not in the payload. The model
reads it once before deciding to call, at zero per-call cost against the 4KB
budget.

## Windows, history, and confidence

Trailing-only is absolute — **no full-sample statistic, ever**, not even as an
internal baseline. That is the measured lookahead bias: the same event scored
z = +151.5 on a Jan–Feb run and z = +135.6 on a Jan–May run.

`min_sessions` must cover **window plus skip**: the cross-sectional momentum rank is
252 + 21 = **273**, not 252. Below it, an `insufficient_history` refusal — never a
silently shortened window. Above it, three states:

- **normal** — full window, healthy;
- **degraded** — with a **non-null** `degraded_reason` (for example more than 20%
  of sessions limit-locked or non-trading);
- **refusal** — below `min_sessions`.

For a cross-sectional field a symbol short of history is **dropped, not hidden**:
the return carries `n_ranked` and `excluded: [{symbol, reason}]`. The whole call
refuses only when the surviving sample falls under **n < 30**, applied *after*
exclusion, where a percentile stops meaning anything.

## The hazards are enforced by construction

The Vietnamese-market hazard list — bands ±7/±10/±15 dated per bar through the
HNX→HOSE migrations to 31/12/2026, limit-lock days where `H=L=O=C`, ATO/ATC, the
lunch break, UPCOM bands anchored to prior-day VWAP, thin liquidity, and
corporate-action adjustment — is too long for five tools to each remember, and a
review checklist fails at the sixth tool.

So there is one gateway: **`prepare_bars(symbol, window_days) -> (frame,
WindowHealth)`** is the only path a computation may take to bars. **Window
Health** — `sessions_used`, `limit_lock_days`, `band_regime`, `adjustment`,
`adtv_percentile` — is echoed in every return. Limit-lock days are excluded from
robust baselines, because a run of zero Garman-Klass variance deflates MAD and
manufactures z elsewhere, and they are reported rather than quietly dropped.

ADR-0006 makes `prepare_bars()` own a transform as well as the guards: it reads
the persisted **Corporate Action** series, applies the **Adjustment Factor**, and
refuses `mixed_price_basis`, `unadjustable_price_basis`, and
`unexplained_price_gap`.

## Forward-return validation is not an entry gate

Requiring a measured net-of-cost forward-return harness before catalog entry would
block all fourteen shortlisted methods from v1, and the research found **no
verified result** showing that HOSE foreign net-buy predicts returns. Instead it
becomes a contract field: every field declares
`claim: "descriptive" | "predictive"`, and **in v1 every field is
`descriptive`**. `predictive` unlocks only behind a measured harness.

`descriptive` is not a label, it **constrains the schema**: a descriptive field may
not return a direction-bearing key at all — no `direction`, no
`signal: buy | sell`, no `expected_return`. The bar is a property of the tool, so
it has to bite at the type rather than at the prompt.

## Vocabulary is exact arithmetic, not an estimator

RSI, MACD, and Bollinger %B are admitted only as named market vocabulary. Their
values are deterministic transforms of a prepared window, so classifying them
as `estimator` would require a meaningless SE or CI; classifying them as
`signal` would turn practitioner cutoffs into claims that the out-of-sample
evidence does not support. The `vocabulary` kind therefore carries no threshold,
null, or sampling uncertainty, while `claim: "descriptive"` and each field's
sanctioned `interpretation` keep the absence of predictive edge explicit.

## The price-zone tension, resolved

The product commits to direct price-zone recommendations while this ADR forbids
any field carrying direction. Both survive by separating **the number** from **the
judgment**:

- The zone is a number, so it is a **registered field computed in code** and
  genuinely descriptive — a ±1 realized-σ band (Yang-Zhang, 20 sessions) around
  the reference price, whose `interpretation` reads *"this symbol's ordinary daily
  range"*, never *"buy here"*.
- The verdict is the model's, and it **may rest only on registered fields, with
  the artifact carrying the list it rested on**. A wrong verdict is then traceable
  to a source instead of dissolving into prose.

## `stored` fields are exempt from the null, not from the contract

`source: computed | stored` draws the last boundary. A stored provider figure has
no threshold and therefore no FPR to measure, but it still carries `unit`, `sign`,
and `interpretation`, and it additionally carries a **staleness stamp**: a
five-month-old quarterly figure narrated as current is a false positive by another
mechanism. The rule is clean — **a threshold requires a null, whatever the
number's origin.**

## Considered Options

- **A review checklist.** Rejected: it holds for five tools and fails at the
  sixth, and it cannot be run.
- **Per-tool declared FPR.** Rejected as above — this is the failure mode
  measured in the assessed external library.
- **Runtime threshold calibration.** Rejected: it makes the threshold a function
  of today's data, so a quiet market silently loosens every signal.
- **Forward-return validation as the entry gate.** Rejected because it would ship
  an empty catalog. Recorded as the unlock for `claim: "predictive"` instead.

## Consequences

- Placement: `src/stocks/signals/` holds the computations, `prepare_bars()`, the
  registry, and the null harness — *what is true*. `src/agent/tools/` is a thin
  adapter — *what the model may see*. The package is shared with the Volume Spike
  signal, which already lives there.
- Enforcement is a runtime contract plus a **pytest parametrised over the
  registry** at a fixed seed, running both nulls and failing when FPR > 1% or a
  metadata field is missing. It is offline and free, so it belongs in `make test`
  rather than in the paid `make eval` lane.
- **The bar binds the nightly Analysis too.** Its template cites registered fields
  only, through the same registry. This is the real reason the registry sits at
  domain level rather than under the agent.
- The bar does not police language. A model reading `rsi_14 = 72` will narrate
  "overbought" whatever the schema omits. What the bar does is make the violation
  **detectable**, and it hands three things onward so the statistics are not
  re-litigated: `interpretation` as the only sanctioned reading, the `claim` flag,
  and the cited-field list. ADR-0015 turns the first into a prompt rule; ADR-0016
  turns it into a machine-checkable target, with a backwards narration a hard fail.
- Adding a computation is a registry change with a null run attached, so a
  sixth cluster is a bounded amount of work rather than an open question.
