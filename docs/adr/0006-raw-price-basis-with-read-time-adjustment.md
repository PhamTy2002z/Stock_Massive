# The price store holds raw prices, and adjustment happens at read time

`provider_snapshots` holds **raw** exchange prices for the `market` Capability. A
stored session is never rewritten to reflect a corporate action that happened
after it, and no Adapter adjusts at write time. Adjustment is a read-time
transform inside `prepare_bars()`, computed from a persisted **Corporate Action**
series. Every Snapshot declares its own **Price Basis**, and `prepare_bars()`
serves a window only when that window is entirely `raw`.

## Why raw, and not adjusted

A `MarketSnapshot` is not a price, it is a bundle of one session's measurements,
and an adjustment flag reaches only part of it. `adjusted=True` rescales OHLC;
every traded quantity and every traded-money field comes back byte-identical, and
`ceiling_price`/`floor_price` arrive from a separate
`PriceStatistics.get_ceilingfloor` call that no flag touches at all. Raw is the
only basis under which the whole row is one measurement: `close × volume`
reconciles with `total_value_vnd`, and the close sits on the same tick grid as the
band it is judged against. An adjusted row would pair rescaled OHLC with the raw
band of the same session — inconsistent *inside one row*, not merely across a
seam, which is a worse failure than the one being repaired.

The second reason is what a stored row means. Under an adjusted store, "HPG's
close on 2024-03-01" is a question whose answer changes silently at every later
ex-date, and it is verifiable against no third party. Under a raw store it is the
number the exchange published, permanently.

## Considered Options

- **Adjusted at write time, with a re-fetch of the symbol's whole history on each
  corporate action.** Rejected for the within-row inconsistency above. Cost was
  not the deciding argument — `fetch_market_history` is one call per symbol, a
  hundred or two a year against a 60/min quota — but every row's audit value
  would expire on the next action.
- **Adjusted at write time without re-fetching.** Already removed by `#41`: the
  Collector never rewrites history, so the first ex-date after a symbol is stored
  splits its series, turning one seam into one per symbol per year.
- **Adjusting traded quantities from `exercise_ratio` alongside price.** Rejected
  below: it would break the one within-row invariant that makes a row checkable.

## The convention lives on the row, not in a config flag

`MarketSnapshot` gains a required `price_basis`, written by the Adapter — the
only code that knows which flag it passed — and persisted in the payload under
`schema_version` 2. Required with no default, so an unstamped row fails loudly
instead of being read as `raw`.

`WindowHealth.adjustment` is then derived from the rows loaded rather than from
configuration, which is what `#37` demanded: rows already written do not change
when a flag flips. It reports more than the basis, because on a served window the
basis is always `raw` and would carry no information — it reports whether
adjustment was *applied*, and from how many Corporate Actions.

The basis has to be per-row rather than per-date, because **the seam is not a
date**: `HistoryWindow.crossover()` is `today - backfill_main_source_days`
evaluated on the day a symbol's Backfill runs, so each symbol's seam is set by
when it was loaded. The ten collected symbols share 2021-08-05 only because they
were loaded together, and hard-coding that date anywhere would be wrong for the
eleventh.

## What `prepare_bars()` refuses

Only an all-`raw` window is served, with three refusal reasons standing beside
`insufficient_history`:

- `mixed_price_basis` — the window crosses a seam. This confirms `#41`: a mixed
  window is meaningless rather than degraded, so it is not stamped `unknown` and
  measured.
- `unadjustable_price_basis` — the window lies wholly in the Cover Source's
  `adjusted_at_source` era. Refused not for being mixed but because that basis was
  fixed at `observed_at`, decays with every action since, and cannot be recomputed
  from what is stored.
- `unexplained_price_gap` — a session inside the window moves further than its
  band permits with no Corporate Action accounting for it. This is the same
  ex-date reconciliation `#41` asked for, read in the other direction, and it is
  what catches MBB 2026-08-11 at −16.08%.

The two basis refusals cost nothing. The deepest window in the catalog is `#37`'s
273 sessions (12-2 momentum, window plus skip) — about thirteen months against a
raw era five years deep — and the Cover Source era was never a signal habitat
anyway: `VnstockMarketHistoryProvider` fills neither `total_value_vnd`, nor the
band, nor either flow pair, so most of `#39`'s methods have no inputs there
whatever the basis.

`unexplained_price_gap` is different, and this is what makes the Corporate Action
table a prerequisite rather than a follow-up: until it is loaded, every raw-era
window containing one of the 27 gaps `#41` measured is refused — ACB's are
annual, so for some symbols that is most windows. The table is what converts
those refusals into applied adjustments.

## Traded quantities stay raw, traded money is unaffected

The discontinuity falls exactly on `MarketSnapshot`'s existing naming split. A
share-count change breaks every `*_volume` field — `volume`, `active_buy_volume`,
`active_sell_volume`, `foreign_buy_volume`, `foreign_sell_volume` — because the
unit itself changes. It leaves every `*_value_vnd` field intact, along with
`market_cap_vnd`: a billion dong traded is a billion dong traded on either side
of a split. So an ADTV in money crosses an ex-date and an ADTV in shares does
not, which narrows the constraint usefully.

No quantity is ever rescaled. The price factor cannot be reused — TCB's 2.096
blends a 1:1 bonus with cash dividends rather than being the 2.000 the bonus
implies — `total_value_vnd` is not adjustable either, so rescaling quantities
alone would break the `close × volume` reconciliation that makes a row checkable,
and `#41` found `exright_date` null on the newest `ISS` row, so the trigger date
is not dependable enough to drive arithmetic.

Sharper than the question asks: only a **share-count-changing** action is a
quantity discontinuity. A cash dividend moves the price and leaves the share
count alone — precisely the distinction `exercise_ratio` carries and
`DividendItem` does not. Fields reading a quantity across such an action are
`degraded` with reason `volume_basis_break`, not refused: a Volume Spike over an
ex-date is a real observation that simply is not comparable. This constrains
`#39`'s foreign-flow pressure versus ADTV only where that ratio is taken in
shares, and the 20-Trading-Day Volume Spike baseline always.

## Corporate Actions are persisted, and their ex-dates are confirmed

The table is required, not optional: read-time adjustment has no other input.
Roughly `(symbol, exright_date, event_code, exercise_ratio, value_per_share)`
from `Company(source='VCI').events()` on a slow Collector cadence.

`#41`'s caveat becomes a mechanism rather than a note. The **Adjustment Factor** is
computed from the declared `exercise_ratio` and `value_per_share`; the raw price
gap only *confirms the ex-date*, and never supplies the factor. The direction
matters: an ex-date's gap is the entitlement and that session's ordinary move
together, so measuring the factor from it would fold a day of news into the
adjustment permanently — and it would be circular, since an unexplained gap is
the signal that an action is missing. A row whose `exright_date` is null, or that
no gap corroborates, is `unconfirmed`, may not drive arithmetic, and leaves its
window `degraded` with reason `unconfirmed_corporate_action`.

## Band checks and limit-lock detection read raw prices

Confirmed, as `#41` argued: the raw close is a required input to `prepare_bars()`
rather than an alternative to the adjusted one. Adjusted closes are unrounded
floats off the tick grid, and the ±7/±10/±15 bands are defined against the
exchange's reference price.

Two caveats found while deciding, both pointing the same way. First,
`MarketSnapshot.reference_price` is **not** the exchange's reference price: both
Adapters set it to the previous session's close from the same frame, so on an
ex-date it is not the number the band is defined against. Second,
`ceiling_price`/`floor_price` are `None` on every history bar, because
`_fetch_history` passes `band=None` deliberately rather than stamp today's band
onto a 2019 session. So neither stored field can serve as the band, and both the
reverse guard above and limit-lock detection have to take the band from the
symbol's exchange regime for that session — which `#39` already fixed, including
the HNX→HOSE migrations that change the regime mid-history. How the detector is
written stays with `#37`'s hazard list; this ADR only settles that it reads raw.

## Measured while implementing this, and where it changed the shape

Three things the live `Company(source='VCI').events()` feed turned out to be, none
of them visible when the decision above was written. Recorded here rather than in
a new decision because none of them reverses anything; they narrow it.

- **`(symbol, exright_date, event_code)` is not a key.** MBB's 2026-08-11 ex-date
  carries two `ISS` rows — a 15% stock dividend and a 10% rights issue — so the
  stored identity adds the *kind* of the issue. The cost is that identity now
  depends on wording the provider controls: a reworded title that reclassifies a
  row forks a duplicate rather than updating the row it is a re-read of. Accepted
  over the alternative, which loses half of an adjustment that has to be computed
  from both rows at once.
- **A rights issue is confirmable and not adjustable.** Its reference adds the
  money subscribers pay in — MBB's was `(24,250 + 0.10 × 10,000) ÷ 1.25` — and no
  column in the feed carries that subscription price. It is stored, confirmed by
  its gap like any other action, and then refuses a factor with a sixth Signal
  Issue, `corporate_action_terms_incomplete`, which is beside
  `unconfirmed_corporate_action` rather than a spelling of it: nothing is in
  doubt about *whether* the action happened. So one of the four action types this
  ADR names stays unadjustable until a source for the subscription price exists.
- **`exercise_ratio` means two different things.** On an `ISS` row it is the
  share ratio; on a `DIV` row it is the payment as a fraction of the 10,000 VND
  par, so TCB's 700 VND dividend arrives as 0.07. Read by column name rather than
  by kind, every cash dividend becomes a share-count change.

The ex-date gap also has to point **downward**. An entitlement is taken out of
the share, so a session that broke above its ceiling is a wrong anchor of some
other kind; confirming on any out-of-band move would let a rally corroborate a
dividend.

## Consequences

The repair of the existing seam needs **no provider calls and no truncation**.
Each FiinQuant call has carried `adjusted=False` since the day it was written —
the daily read in `cf969d4`, `_fetch_history` in `5c43a24` — and `adjusted=True`
appears nowhere in the repository's history, so every Main Source row already *is*
raw, while the vnstock Cover Source has no raw option and is already
`adjusted_at_source`. What is missing is only that the rows do not say so.
Stamping is an in-place payload `UPDATE`, not a re-collection: `schema_version` is
part of `uq_provider_snapshot_identity`, so re-fetching under 2 would write a
second row beside the first rather than replace it.

`prepare_bars()` now owns a transform, not only a set of guards, so `#37`'s
gateway is where the Corporate Action series is read and applied. The Signal Issue
vocabulary grows `mixed_price_basis`, `unadjustable_price_basis`,
`unexplained_price_gap`, `volume_basis_break` and `unconfirmed_corporate_action`.

`/{symbol}/series/market` keeps serving both eras, each session carrying its own
basis to the wire as ADR-0002 requires. A long-range chart is the one reader for
which the `adjusted_at_source` era is the *better* series — its job is a decade of
shape — so that endpoint is not to be narrowed to one convention.

ADR-0002's sentence that the seam is recorded through `Snapshot.metadata.source`
still stands, but source alone no longer carries the basis. It happens to
determine it for every row written so far, which is what makes the one-time stamp
possible, and it stops determining it the moment either provider's flag changes.

Revisit if the FiinQuant tier deepens past `backfill_depth_days`, in which case
the Cover Source era could be re-loaded raw and the second basis retired
entirely, or if vnstock exposes a raw parameter.
