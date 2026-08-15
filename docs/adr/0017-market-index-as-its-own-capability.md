# The market index is its own Capability, not a reserved symbol in `market`

The benchmark's session series is persisted under a fifth Capability,
`market_index`, with the index code as its symbol. It is written by one source
and no cover, read through the same session reader every symbol's sessions come
through, and served by `prepare_bars(series=BarSeries.MARKET_INDEX)` — which
measures no band on it, reads no Corporate Action series for it, and gives it no
liquidity standing.

## Why the series exists at all

`relative_strength.beta_vs_market_index` is registered and refuses. Until this
landed it refused because **this system stored no market-index session series**:
the VN-Index existed only as an alias inside the live price path
(`src/stocks/price/service.py`, `MARKET_INDICES`), and reading it from there is
exactly the substitution `docs/specs/0003` §13 forbids — a legacy live read used
to make a registered field look available. The field was honest and useless at
the same time, and this is the precursor that removes the second half of that
without touching the first: no serving path gained a provider read.

## The decision that had to be made, and the failure that made it

An index is not a tradeable symbol. It could have been stored under the existing
`market` Capability with a reserved symbol — `VNINDEX` is a legal symbol under
the ordinary pattern — and that option is rejected for one measurable reason
and three supporting ones.

**A Trading Day is derived from the `market` Capability.**
`src/stocks/trading_day.py` answers `latest_trading_day` with
`date(max(effective_at))` over `capability = 'market'`, and `trading_days_before`
walks the distinct `effective_at` values of the same rows. This system has no
holiday calendar; the store *is* the calendar. An index session stored under
`market` would therefore not merely sit beside the equities — it would help
**define** the market-wide window every equity is measured against.

That is not a theoretical hazard. The index and the Universe are loaded by
different jobs on different clocks. One index row landing for a session the
Universe has not been collected for moves `latest_trading_day` forward by a day,
and every symbol's trailing window is then one session short of what its field
declares: a hundred `insufficient_history` refusals produced by a benchmark
arriving early. Backfilling the index deeper than the equities would do the same
thing to every historical window.

The three supporting reasons:

- **Cross-sectional reads would have to exclude it by name.** `sessions_on_days`,
  the liquidity percentile in the gateway and every ranked field read the
  `market` Capability for a list of symbols. Under a reserved symbol the only
  thing keeping an index out of a percentile of listed companies is a string
  comparison somebody remembers to write. ADR-0010's whole argument is that a
  rule enforced by memory fails at the sixth reader.
- **The Universe is a hundred tradeable names.** An index is in no Universe, is
  not collected by the per-symbol cycle, and is not batched with symbols.
- **Ownership and staleness are per Capability.** The index has one owning source
  and the `market` Capability has two; expressing that under one Capability is
  not expressible at all.

## What the Capability declares

**One source, no cover.** `market_index` is owned by FiinQuant alone. The Cover
Source's quote history is `adjusted_at_source` with no raw option (ADR-0006), but
an index is adjusted for nothing — so a vnstock-filled index series would carry a
basis asserting a rescaling nobody performed, and a window mixing the two would
be refused as `mixed_price_basis` for a seam that does not exist in the market.

**Its own snapshot contract.** `MarketIndexSnapshot` and `MarketSnapshot` share a
`SessionSnapshot` base holding what any priced instrument's session has — OHLC,
traded quantity, traded money, and the Price Basis. The equity-only figures
(`ceiling_price`, `floor_price`, the foreign split, `market_cap_vnd`) are on
`MarketSnapshot` and are **absent** from the index contract rather than
present-and-null on it. "An index has no ceiling price" is then a fact of the
type, instead of a `None` indistinguishable from one nobody collected.

Splitting the equity contract is more than the ticket asked for and is what
criterion three costs: an index payload reusing `MarketSnapshot` would store a
band, a foreign split and a market capitalisation as nulls on every row, and no
reader could tell "this instrument has none" from "nobody collected it". The
base answers `company_figures` with `(None, None)` and `MarketSnapshot`
overrides it, so the gateway reads the distinction off the contract rather than
testing the type — one mechanism, which cannot disagree with itself.

**The same Price Basis rule.** Not relaxed. An index level says what it means
like every other stored session does, and `prepare_bars()` refuses a mixed-basis
index window exactly as it refuses a mixed-basis equity one.

## What the gateway does with the absent band and the absent actions

Both are **stated decisions on `BarSeries`**, not consequences of fields that
happen to be null.

- **No band is measured, on any session.** The band is a percentage of a board's
  reference price and the index sits on no board. `BandRegimeResolver` is never
  constructed for an index window; every index bar carries
  `band_undecided_reason = band_not_applicable` — a new Signal Issue, distinct
  from `exchange_unknown` (a board exists and nothing named it) and from
  `band_not_measured` (a band exists and this window did not ask) — and
  `limit_lock = not_applicable`, a new `LimitLock` member kept apart from
  `indeterminate` for the same reason: that one is the store admitting it could
  not judge a session which *does* have a band, and reusing it here would leave
  an equity's word on the one bar that most needs not to carry one. The window
  carries no `band_regime`, and `band_undecided_days` is zero: nothing was left
  undecided, because there was nothing to decide.
- **It follows that `unexplained_price_gap` cannot fire on an index.** That
  refusal reads a break of the band as evidence of a wrong anchor. With no band
  there is no break to read, so a 9% index session is served: it is the market
  moving, and the store has nothing to say against it. This is a real loss of a
  check and it is accepted, because the check has no meaning for a composite —
  an index does not go ex-anything.
- **No Corporate Action series is read.** The exchange absorbs member
  entitlements and reconstitutions into the index divisor, so the published
  series is already continuous. The window reports `applied=False` over *zero*
  actions in window, which is a measurement rather than a default. An action
  stored against the index's code — which nothing writes — does not rebase it,
  and `volume_basis_break` is unreachable.
- **No liquidity standing.** `adtv` is `None`. There is no peer set an index
  trades among; ranking its turnover would rank a composite against its own
  members.

**The window is still cut from the market's own Trading Days.** That is the whole
reason a beta will be computable: the benchmark is read on exactly the sessions
the symbol was, so the two series line up by construction rather than by a join
done afterwards. An index row on a day no equity traded is outside the window
rather than an extra bar in it.

## The load, and its depth

`src/stocks/market_index.py` is neither a Warm-up nor a Backfill and is named for
itself. It borrows a property from each: repeatable and Main Source only like a
**Warm-up** (ADR-0005), so the run that first fills the series is the run that
tops it up daily and repairs a week that was missed; and deep like a
**Backfill**, a year of sessions rather than the recent signal window. It matches
neither because it loads one instrument that is in no Universe, under a
Capability of its own. Calling it a Warm-up would have contradicted `CONTEXT.md`,
which defines that term as recent `market` history making a *Universe member*
evaluable.

`RELATIVE_STRENGTH_MIN_SESSIONS` is 250 and `prepare_bars()` refuses a window
short of what the field declares, so a benchmark stored 249 sessions deep would
leave that field refusing under `insufficient_history` — the same unavailability
wearing a reason that points at the wrong fix. The default depth is written as
the field's own floor plus a margin of 25 sessions.

**Writing it as that expression is not what enforces it.** Production reads the
depth from configuration, so a constant nothing checks would be a comment:
`build_market_index_loader` compares the *configured* window against the field's
floor and refuses to wire a loader below it, naming both numbers. Shortening the
load past what its only reader needs is then a refusal an operator sees at wiring
time, rather than a field that starts refusing weeks later for a reason that
points at collection.

The margin is how far behind the daily run may fall — a long holiday, a broken
week — while still leaving the field its full 250 on the next successful run.

The arithmetic that turns a session count into the calendar span a provider is
asked for, and the trim that keeps "bounded" a property of what is *written*,
live in `src/stocks/session_window.py` and are shared with the equity Warm-up.
Two loaders answering the same mechanical question two ways would be one of them
wrong, and the drift is not hypothetical: the holiday allowance was briefly
declared twice with the same value and two different reasons.

## Considered options

- **A reserved symbol under `market`.** Rejected above; the Trading Day
  contamination is the deciding argument and it is not repairable by an
  exclusion list, because the list would have to be remembered by every future
  reader of the Capability.
- **Reusing `MarketSnapshot` for index payloads.** Rejected: it would store a
  ceiling price, a foreign split and a market capitalisation as `None` on every
  index row, and nothing downstream could tell "this instrument has none" from
  "nobody collected it".
- **A reader of its own beside `signals/sessions.py`.** Rejected: the resolution
  rule — which of two stored copies of a session is *the* session — is the same
  rule either way, and a second spelling of it would be a second answer to that
  question. The reader takes the Capability as a parameter and refuses any
  Capability that is not a session series.
- **Collecting the index in the daily cycle.** Rejected: the cycle is a batched
  per-symbol read over the Universe, and the index is in no Universe and needs a
  year of history rather than one session. It is its own scheduled job, after the
  market catch-up, so the index and the Universe stop on the same Trading Day.

## What is still refused, and why that is not a regression

`relative_strength.beta_vs_market_index` still returns `unavailable`. What
changed is what the refusal says: the benchmark is stored and reachable, and the
**rolling regression over it is not implemented**. Ledoit-Wolf shrinkage is
mandatory for that estimator when it lands, with the shrinkage intensity reported
beside the beta as the honesty signal — an intensity approaching one means the
data was insufficient (`docs/research/quant-methods-eod-vn.md`, shortlist #11).

A field whose refusal still claimed the store held no benchmark would be lying
about its own dependency and pointing whoever read it at a data load that is
already done, which is the same failure as a silently dropped field wearing
better clothes.
