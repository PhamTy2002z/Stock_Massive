# DNSE OpenAPI market-data capability audit

Status: empirical research snapshot, **2026-08-24**. This report records what
was documented and what a live DNSE credential actually returned on that date.
It is evidence for an integration decision, not an evergreen API reference.

## Decision

Use DNSE as Stock_Massive's internal **realtime and market-microstructure data
source**, behind a dedicated ingestion boundary. Do not make it the canonical
historical EOD source yet.

This split follows the evidence:

- DNSE exposes authenticated REST and WebSocket market data for trades, order
  book snapshots, auction expected price, foreign flow, market sessions,
  indices, cash instruments, and futures.
- A single FPT session reconciled exactly across trades, one-minute bars, and
  the daily bar after applying the board-specific quantity units documented
  below.
- The historical surface has silent-empty failure modes, 45 invalid daily bars
  in the current 30-symbol Universe, two timestamp eras, and no explicit raw
  versus adjusted price basis.
- The official SDK is useful as protocol documentation but is not safe to adopt
  unchanged because of TLS, parser, subscription, and replay limitations.

The intended product remains research and monitoring. Trading, portfolio sync,
account data, and order execution are outside this audit and were not called.

## How to read the evidence

Claims use three evidence labels:

- **Documented**: stated by DNSE's current developer documentation or official
  SDK.
- **Observed**: returned by the production API during read-only tests on
  2026-08-24.
- **Inferred**: derived from reconciliation or multiple observed fields; the
  derivation is stated.

The live checks loaded `API_KEY` and the repository's existing
`API_SECRECT` spelling from `.env` without printing them. No credential or
response containing account information is recorded here. No trading, account,
OTP, or portfolio endpoint was called.

## Capability surface

### REST market data

The REST base is `https://openapi.dnse.com.vn`. DNSE's
[market-data reference](https://developers.dnse.com.vn/docs/dnse/market-data/)
and the authenticated production surface expose:

| Endpoint | Purpose | Important behavior |
|---|---|---|
| `GET /price/ohlc` | Historical bars | Resolutions `1`, `3`, `5`, `15`, `30`, `1H`, `1D`, `1W` |
| `GET /price/{symbol}/secdef` | Security definition | Board, ISIN, price bands, statuses, dates |
| `GET /instruments` | Instrument catalog | Works in production |
| `GET /market/instruments` | Instrument catalog alias | Also works despite docs/SDK drift |
| `GET /price/{symbol}/trades` | Trades for one day | Token pagination, maximum page size 1,000 |
| `GET /price/{symbol}/trades/latest` | Latest trades | Current/latest event window |
| `GET /price/{symbol}/quotes` | Book snapshots for one day | Board-dependent depth |
| `GET /price/{symbol}/quotes/latest` | Latest book snapshot | May retain depth after close |
| `GET /price/{symbol}/foreign-trading` | Foreign activity for one day | Volume, value, and room fields |
| `GET /market/trading-session` | Current session state | Market, board, product group, session/event IDs |
| `GET /price/{symbol}/expected-price` | Auction expected price for one day | ATO/ATC path, duplicates possible |
| `GET /price/{symbol}/close` | Closing data | Suitable for reconciliation, not source mixing |
| `GET /market/working-dates` | Future working calendar | Returned future dates, not historical sessions |

Historical trades, quotes, foreign activity, and expected prices accept at most
one trading day per request. Pagination uses an opaque `nextPageToken`; two
consecutive five-row trade pages were descending, non-overlapping, and stable in
the live check.

The empirical page-size ceiling is exactly 1,000. A larger limit returns HTTP
400. Applications should not infer success only from HTTP status: invalid
symbols, invalid resolution spelling, and reversed date ranges can return HTTP
200 with an empty list or null OHLC arrays.

### REST rate budget

DNSE's [published rate-limit table](https://developers.dnse.com.vn/docs/guide/ratelimits)
groups endpoints into materially different budgets:

| Endpoint family | Hourly limit | Daily limit |
|---|---:|---:|
| OHLC | 50,000 | 100,000 |
| Trades, quotes, and latest variants | 10,000 | 100,000 |
| Instrument catalog | 10,000 | 100,000 |
| Security definition, close, and working dates | 1,000 | 10,000 |

Rate-limit response headers were present in the live checks. Expected price,
foreign trading, and current session were not listed in the published table;
their effective budgets must be learned from headers without deliberately
exhausting the allowance. REST should handle bootstrap and reconciliation, not
simulate streaming through polling.

### WebSocket market data

The current WebSocket endpoint is:

```text
wss://ws-openapi.dnse.com.vn/v1/stream?encoding=json
```

Authentication completed with `auth_success` using a verified TLS chain. The
server also sent its application-level ping. Because the test occurred after
market close, actual quote/trade payload rate and reconnect-gap behavior remain
unverified.

The documented channel families are:

| Channel pattern | Event family |
|---|---|
| `security_definition.{board}.{encoding}` | Instrument/reference updates |
| `tick.{board}.{encoding}` | Matched trades |
| `tick_extra.{board}.{encoding}` | Additional trade fields |
| `top_price.{board}.{encoding}` | Order-book snapshots |
| `ohlc.{resolution}.{encoding}` | Updating bars |
| `ohlc_closed.{resolution}.{encoding}` | Closed bars |
| `expected_price.{board}.{encoding}` | Auction expected price and quantity |
| `market_index.{index}.{encoding}` | Index ticks |
| `foreign.{board}.{encoding}` | Foreign trading/room updates |
| `estimated_market_index.{index}.{encoding}` | Estimated index values |
| `session.{product_group}.{board}.{encoding}` | Session transitions |

JSON and MessagePack are documented encodings. The
[connection guide](https://developers.dnse.com.vn/docs/guide/market-data/connect)
sets an eight-hour maximum connection lifetime, a server ping every three
minutes, and a required pong within one minute. No public limit was found for
symbols per subscription, channels per connection, event throughput, replay
depth, or concurrent connections. No sequence/replay guarantee was found.

## Instrument and market coverage

### Catalog snapshot

The unfiltered catalog returned 3,254 records and 3,252 unique symbols. It
includes inactive and expired instruments, so it is not a valid active roster by
itself. `VEOF` and `VESAF` appeared more than once.

Filtering by a present `securityGroupId` yielded this active-looking snapshot:

| Group | Meaning | Records observed |
|---|---|---:|
| `ST` | Stocks | 1,525 |
| `EF` | ETFs | 20 |
| `EW` | Covered warrants | 328 |
| `MF` | Mutual funds | 3 |
| `BS` | Bonds | 91 |
| `FU` | Futures | 8 |

These are dated observations, not hard-coded product constants. Build the
current roster from the filtered catalog plus security definitions, and retain
status/listing dates with each instrument.

Observed market IDs were `STO`, `STX`, `UPX`, `DVX`, and `HCX`. OHLC worked for
stocks, ETFs, covered warrants, mutual funds, futures (including the
`DERIVATIVE` alias), and indices. Bond instrument and security-definition calls
worked, while bond OHLC returned HTTP 400.

The ten observed indices were `VNINDEX`, `VN30`, `VN100`, `HNX`, `HNX30`,
`UPCOM`, `VNXALLSHARE`, `VNDIVIDEND`, `VN50GROWTH`, and `VNMITECH`. Instrument
`indexName` supplied current membership for VN30, VN100, and HNX30, but it does
not provide point-in-time historical membership.

Observed futures aliases included `VN30F1M`, `VN30F2M`, `VN30F1Q`, `VN30F2Q`,
and `V100F1M`. Treat the rolling alias and concrete contract symbol as separate
identities.

### Board semantics

An FPT security definition returned seven boards spanning round-lot, odd-lot,
negotiated, and post-close families. Board is therefore part of event identity,
unit normalization, aggregation, and product semantics; it cannot be discarded
after symbol lookup.

Observed depth also varies by venue and board:

| Example | Board | Bid/offer levels |
|---|---|---:|
| FPT on HOSE | `G1` | 3 / 3 |
| SHS on HNX | round lot | 10 / 10 |
| VGI on UPCOM | round lot | 10 / 10 |
| FPT odd lot | `G4` | 3 / 3 |

The API does not expose full order add/cancel semantics. These are market-by-
price snapshots, not a reconstructable order-by-order book.

## Historical coverage observed

The existing 30-symbol Universe was tested without recording secrets or account
data:

- 30/30 symbols had daily data fresh through 2026-08-24.
- 28/30 had at least 970 daily bars; 29/30 had at least 250.
- 15/30 covered the full ten-year query window.
- Newer listings explained the two short series: `TCX` returned 210 daily bars
  and `VPL` returned 323.
- 30/30 had one-minute history, security definitions, a latest quote, and
  same-day foreign data.
- One-minute series ranged from 8,737 to 14,916 bars in the query window.

FPT returned 2,657 daily bars from 2016-01-04 through 2026-08-24 and 14,909
one-minute bars from 2026-05-25 through 2026-08-24. Queries for earlier one-minute
dates returned null arrays. This is observed retention, not a contractual
retention guarantee.

Other sampled retention boundaries differed by dataset:

| Dataset | Earliest observed availability in this audit |
|---|---|
| One-minute OHLC | 2026-05-25 |
| Quotes | 2026-07-27 |
| Expected price | 2026-07-27 |
| Foreign activity | 2026-06-01 |
| Trades | Present on 2026-04-01; absent on sampled 2026-03-02 |

`GET /market/working-dates` returned 256 dates from 2026-08-24 through
2027-08-24. It should be treated as a future market calendar, not a historical
trading-day authority.

### Resolution and timestamp traps

REST `1H` works. Lowercase `1h` returned HTTP 200 with an empty result, making a
spelling error indistinguishable from “no data” unless the client validates the
resolution before calling DNSE.

Daily timestamps showed two hour patterns: older histories included hours 07:00
and 09:00, while newer listings used 09:00. Store a Vietnamese trading date
separately from the provider timestamp. Never derive session date from UTC
conversion alone.

## Unit contract derived from reconciliation

Unit normalization must occur once, at ingestion, and remain traceable to the
raw field and board.

| Field family | Provider unit | Canonical normalization |
|---|---|---|
| Stock OHLC/trade/quote/close/expected/secdef price | Thousand VND | Multiply by 1,000 to VND |
| `G1` trade `matchQtty` and `totalVolumeTraded` | Board unit of 10 shares | Multiply by 10 to shares |
| `G4` odd-lot trade quantity | Share | Keep as shares |
| OHLC volume | Share | Keep as shares |
| Foreign volume | Share | Keep as shares |
| `grossTradeAmount` | Billion VND | Multiply by 1,000,000,000 to VND |
| Foreign buy/sell amount | VND | Keep as VND |
| Futures price | Index point | Keep as points; never label as VND |

The `G1` factor was inferred by reconciling FPT trade quantities to minute and
daily OHLC volume. A single global quantity multiplier would corrupt odd-lot and
possibly other board data. Quote quantity scaling across all boards still needs
a live-market verification.

## Full-day FPT reconciliation

The 2026-08-24 FPT session provided a concrete consistency test:

| Dataset | Rows | Pages | Approximate JSON size | Exact duplicates |
|---|---:|---:|---:|---:|
| Trades `G1` | 7,883 | 8 | 3.020 MB | 0 |
| Quotes `G1` | 19,366 | 20 | 7.845 MB | 212 |
| Foreign `G1` | 378 | 1 | 0.194 MB | 0 |
| Expected price `G1` | 2,465 | 3 | 0.581 MB | 180 |
| One-minute bars | 226 | — | — | — |

After applying the `G1` quantity factor, trades aggregated to the minute bars,
and minute bars aggregated exactly to the daily bar:

```text
open 72.5 | high 72.7 | low 71.4 | close 71.4 | volume 4,611,900
```

Quote and expected-price snapshots require idempotent deduplication. A payload
hash plus source, symbol, board, provider event time, and event family is a safe
starting identity; it must not be mistaken for a provider sequence number.

FPT trades carried `BUY` and `SELL` aggressor sides. Among 1,000 latest trades,
495 provider timestamps were unique. Exact rows remained distinct because
cumulative fields changed, confirming that timestamp alone is not an event key.

After close, FPT's latest quote retained non-empty depth while
`totalBidQtty`/`totalOfferQtty` were zero. Those total fields are not an
unconditional ground truth for visible depth.

## Data-quality findings

### Historical price integrity

The daily Universe scan found 45 bars across 20 symbols violating at least one
of these invariants:

```text
high >= max(open, close)
low  <= min(open, close)
```

MCH had 13 violations. One FPT example on 2019-08-07 returned open 16.87, high
17.41, low 17.13, close 17.41. This is sufficient to require validation and a
quality/refusal state before derived indicators use the bar.

Older FPT prices appear adjusted at source: the series is around 8.9 in 2016 and
71.4 in 2026. That is an inference from scale, not a provider contract. DNSE
does not expose price-basis or corporate-action adjustment metadata, so the
series cannot safely become the platform's canonical raw EOD history.

### Failure semantics

The client must turn these provider behaviors into explicit typed outcomes:

| Input condition | Observed response |
|---|---|
| Unknown symbol | HTTP 200, empty result |
| Invalid/reversed OHLC range | HTTP 200, null OHLC arrays |
| Invalid resolution spelling | HTTP 200, empty/null result |
| Missing or invalid instrument type | HTTP 400 |
| Missing `from` in one test | One bar rather than a validation error |
| More than one day for event-history endpoints | HTTP 400 |
| Page size above 1,000 | HTTP 400 |

An empty success therefore means “unknown” until the request contract, symbol,
session calendar, and retention window have been checked.

### Official SDK risks

The official [DNSE OpenAPI SDK](https://github.com/dnse-tech/openapi-sdk) was
audited at tag `v2.1.0` (`b63869cba601db83ea1b52305d9b619d25ca02d7`).
It should inform a local adapter, not be imported unchanged:

- The REST client configures `urllib3.PoolManager` with certificate and hostname
  verification disabled.
- The quote parser reads `qtty`, while the current REST/docs field is
  `quantity`.
- The session parser reads `sendingTime`, while the current docs use `time`.
- Reconnect reauthenticates and resubscribes, but does not replay missed events.
- Subscriptions are keyed only by channel, which can overwrite a prior symbol
  set for that channel.
- Dispatch uses six unbounded queues. It preserves per-symbol ordering, not a
  global event order, and has no overload policy.
- REST responses have no formal typed domain models; callers receive raw status
  and body.
- MessagePack key expansion remains ambiguous without live payload tests.

## What DNSE unlocks for Stock_Massive

### 1. Realtime market pulse

Session-aware breadth, advancing/declining/unchanged counts, ceiling/floor
locks, volume acceleration, index-relative moves, and estimated VN30 can replace
coarse request-time snapshots with a continuously updated market state.

### 2. Market microstructure

Trades plus depth snapshots enable spread and spread-bps, three/ten-level depth,
book imbalance, cumulative volume delta, aggressor flow, trade intensity, VWAP,
effective spread, price impact, liquidity shocks, and queue-at-band monitoring.
These metrics must state whether they use full observed depth or only the venue's
published top levels.

### 3. Auction intelligence

Expected ATO/ATC price and quantity paths enable auction imbalance, indicative
close dislocation, closing-price quality, and “what changed into ATC” evidence.

### 4. Foreign-flow evidence

Intraday foreign volume/value and room updates enable participation rate,
pressure, acceleration, reversal, and room-exhaustion signals. This directly
unblocks the currently refused
`foreign_flow_pressure.net_volume_over_adtv` reading in
`apps/api/src/stocks/signals/foreign_flow.py`.

### 5. Intraday bars and replay

Closed and updating bars can support 1/3/5/15/30-minute and hourly charts,
realized volatility, volume anomalies, session replay, and deterministic
feature recomputation. It can consolidate the current VCI request-time
intraday path, the local five-minute collector, and KBS order-stat path without
mixing their semantics.

### 6. UPCOM reference-price reconstruction

Board separation makes it possible to reconstruct the prior-day continuous
round-lot VWAP while excluding odd-lot and negotiated trades. That is the data
currently missing from the price-band signal's UPCOM logic.

### 7. Derivatives and cross-market monitoring

Futures and index feeds enable basis, front/next spread, expiry and roll state,
futures-index lead/lag, and an open-interest matrix when the live
security-definition payload supplies open interest.

### 8. Proactive monitoring

The normalized event stream can trigger evidence-backed alerts for limit
lock/unlock, spread shock, queue imbalance, signed-flow anomaly, foreign-flow
reversal, auction dislocation, and futures-basis expansion.

DNSE does **not** close the platform's gaps in fundamentals, valuation history,
corporate actions, news, proprietary trading, complete industry taxonomy,
point-in-time index membership, full HOSE depth, or order add/cancel history.

## Fit with the current repository

Current source ownership is defined in
`apps/api/src/stocks/providers/contracts.py`: FiinQuant owns main market and
valuation snapshots, while vnstock owns reference and fundamental snapshots.
DNSE should be added as a realtime/event source, not forced into the existing
one-snapshot-per-session abstraction.

The existing intraday paths are split across:

- request-time VCI ticks in `apps/api/src/stocks/price/service.py`;
- five-minute aggregation in `apps/api/src/stocks/intraday_collector.py`;
- KBS order statistics in `apps/api/src/stocks/trading/service.py`.

`stock_intraday_bars` currently lacks source, resolution, board, price basis,
schema version, and a collision-safe uniqueness contract for a multi-source
feed. `provider_snapshots` is an EOD/session snapshot model and should not store
DNSE ticks or depth snapshots.

## Recommended integration boundary

```text
DNSE REST bootstrap/reconcile + DNSE WebSocket live feed
                         |
                    raw boundary
                         |
 TradeTick | BookSnapshot | ForeignFlowSnapshot | AuctionSnapshot
 SessionState | IndexTick | SecurityDefinition | ClosedBar
                         |
 Redis hot projections + partitioned durable event store
                         |
 deterministic bars/features/replay + alerts + AI evidence
```

Every normalized event should carry:

- source, event family, schema version, and raw payload hash;
- symbol, exchange, board, product group, and trading day/session;
- provider event time and platform observation time;
- raw unit, normalized unit, and normalization rule version;
- validation result plus quality/refusal reason.

Use REST for instrument bootstrap, a one-day event backfill, reconnect
reconciliation, and EOD checks. Use WebSocket for live state. At EOD, reconcile
DNSE event rollups to DNSE daily data first; only then compare with FiinQuant.
Never overwrite provenance to make two providers appear identical.

## Suggested delivery order

1. Define normalized contracts, board/unit rules, validation, and deduplication.
2. Ingest trades and closed one-minute bars for the configured Universe.
3. Add foreign-flow snapshots and unblock volume-over-ADTV evidence.
4. Add quote depth and liquidity projections.
5. Add session and expected-price/auction projections.
6. Add index feeds and market breadth.
7. Add futures, basis, expiry, and open-interest features.
8. Add replay, operational telemetry, and alert evaluation.

Promotion gates should include reconciliation error, duplicate rate, late-event
rate, reconnect gap, end-to-end latency, queue pressure, and provider-rate-budget
metrics. A feed that is connected but cannot prove completeness should report
degraded evidence, not silently look healthy.

## Remaining live-market tests

The following questions require a controlled run during HOSE/HNX/UPCOM trading
hours:

1. Actual JSON and MessagePack payloads for every selected channel.
2. Maximum symbols/channel subscriptions and sustainable event throughput.
3. Quote quantity scale by board and venue.
4. Event ordering and duplicate behavior under load.
5. Reconnect gap size, resubscribe behavior, and REST reconciliation sufficiency.
6. End-to-end latency distribution and server/client clock skew.
7. Session transitions and ATO/ATC expected-price behavior in real time.

These tests are required before the feed can claim realtime completeness. They
do not block building the normalization contract or REST-backed prototype.

## Primary sources

- [DNSE API platform overview](https://developers.dnse.com.vn/docs/guide/intro/api_platform/)
- [Authentication](https://developers.dnse.com.vn/docs/guide/intro/authentication)
- [Market-data REST reference](https://developers.dnse.com.vn/docs/dnse/market-data/)
- [WebSocket connection guide](https://developers.dnse.com.vn/docs/guide/market-data/connect)
- [Rate limits](https://developers.dnse.com.vn/docs/guide/ratelimits)
- [API versioning](https://developers.dnse.com.vn/docs/guide/versioning/api)
- [Official DNSE OpenAPI SDK](https://github.com/dnse-tech/openapi-sdk)

See also [Vietnamese market-data sources](./vn-market-data-sources.md) for the
broader provider comparison. That earlier survey predates this live OpenAPI
audit and describes DNSE's previous LightSpeed generation.
