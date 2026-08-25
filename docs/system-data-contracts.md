# System data contracts

This document records why the realtime market-data boundary exists and where
its executable contracts live. It is the durable architecture entry point for
maintainers building adapters, storage, projections, product APIs, or Harness
tools on normalized market evidence.

## Boundary and ownership

Provider wire formats stop before `stocks.realtime`. Adapters may authenticate,
parse, and normalize provider responses, but downstream code receives only the
strict event models exported by
[`stocks.realtime`](../apps/api/src/stocks/realtime/__init__.py). Raw payloads,
credentials, provider-specific units, and adapter exceptions are not part of
that contract.

DNSE owns realtime and microstructure evidence. FiinQuant remains the primary
historical EOD and valuation source, and vnstock remains the reference and
fundamental source. The executable ownership table is
[`SOURCE_OWNERSHIP`](../apps/api/src/stocks/realtime/policy.py). Adding a
provider does not change semantic ownership by itself.

The existing `provider_snapshots` path remains the EOD snapshot owner. Realtime
events use the separate contract boundary in
[`contracts.py`](../apps/api/src/stocks/realtime/contracts.py) and must not be
forced into the EOD identity or update model.

## Evidence identity

Every normalized event carries source, family, instrument and venue identity,
Vietnamese trading-day and session identity, provider and observation time,
canonical units, schema and normalization versions, a raw-payload hash, and an
explicit quality state. The model definitions and invariants are executable in
[`EventMetadata`](../apps/api/src/stocks/realtime/contracts.py) and the eight
concrete event types beside it.

Source is part of evidence identity but not the source-neutral observation key.
This distinction lets the system group comparable observations without erasing
which provider produced each one. Provider timestamps are event time, not
sequence numbers; snapshot families still require explicit duplicate handling.

## Units and board rules

Normalization happens once at ingestion through a declared version, product
group, board, and measure. Unknown versions or unproven combinations refuse
instead of using a global multiplier. The executable registry is
[`NORMALIZATION_RULES`](../apps/api/src/stocks/realtime/normalization.py).

This design preserves the audited distinction between round-lot and odd-lot
trade quantity. It also keeps cash prices in VND and derivatives in index
points. Quote quantity has no admitted rule until a market-hours conformance
run proves its scale; adapters must not borrow the trade-quantity rule.

## Outcomes and quality

An HTTP success with an empty provider body is not automatically valid market
absence. Request validity, symbol knowledge, session calendars, retention, and
provider health determine the typed outcome. The closed outcome taxonomy and
its refusal, absence, degradation, ignore, reconciliation, or retry disposition
are owned by
[`DataOutcomeKind`](../apps/api/src/stocks/realtime/policy.py).

Normalized events use an explicit quality state. A duplicate must identify the
earlier evidence record, a gap remains visible, and stale or degraded evidence
does not become valid merely because a delivery path recovered.

## Reconciliation and provenance

Daily, intraday, and cross-provider comparisons retain two evidence references
and a versioned deterministic method. A reconciliation result may report a
match, mismatch, incomplete comparison, or non-comparable inputs, but it cannot
replace either source. The executable owners are
[`ReconciliationResult`](../apps/api/src/stocks/realtime/policy.py) and
[`merge_evidence`](../apps/api/src/stocks/realtime/policy.py).

The owner-approved v1 profile uses exact absolute tolerances of zero VND for
price, zero shares for volume, and zero VND for value. It runs only in shadow
mode: every completed comparison is appended to
`realtime_reconciliation_audits` with both evidence identities and sources,
scope, comparison values and deltas, profile version, status, quality, and
deterministic checked time. A mismatch degrades the audit quality but never
blocks ingestion or changes either source. The executable owners are
[`STRICT_RECONCILIATION_PROFILE_V1`](../apps/api/src/stocks/realtime/policy.py),
[`ReconciliationProjector`](../apps/api/src/stocks/realtime/reconciliation_projection.py),
and the
[`reconciliation audit migration`](../apps/api/alembic/versions/e2c4a7d19b63_add_reconciliation_audit.py).

The design rejects last-write-wins source mixing. A repeated identity must be
declared as a duplicate, and distinct providers remain separately addressable
even when their source-neutral observation key matches.

## Retention

Retention is versioned because storage cost, replay needs, provider terms, and
security posture can change independently from event schema. The exact current
durations and rationale are owned by
[`RETENTION_POLICY`](../apps/api/src/stocks/realtime/policy.py).

The policy keeps raw events for the shortest incident-replay window, normalized
events and projections for the same analysis window, replay artifacts for a
bounded evaluation window, and operational metadata only long enough for
incident trends. A later policy version may change durations without rewriting
historical event meaning.

## Security posture

Normalized models use strict unknown-field rejection and contain only the raw
payload hash. They expose no field for API keys, authorization values, access
tokens, raw payloads, or arbitrary provider exception text. Typed outcomes avoid
free-form diagnostics so credentials cannot be copied into event payloads or
logs through this boundary.

The executable security and mutation evidence is in
[`test_realtime_contracts.py`](../apps/api/tests/test_realtime_contracts.py) and
[`test_realtime_policy.py`](../apps/api/tests/test_realtime_policy.py). Adapter
and persistence phases must add their own redaction and access-control tests at
their respective boundaries.

## DNSE adapter boundary

Phase S1 keeps DNSE authentication, transport, wire parsing, pagination, rate
budgets, reconnect recovery, and operational metrics in
[`stocks.realtime.dnse`](../apps/api/src/stocks/realtime/dnse/). The package
maps admitted JSON evidence into the S0 contracts or returns a typed outcome.
It does not expose account or trading operations.

MessagePack remains refused until a sanitized live payload proves its schema.
Book snapshots also remain refused at normalization until the controlled
market-hours probe proves quote quantity scale. These refusals preserve the S0
rule that an adapter cannot borrow an unverified unit conversion from another
event family.

The read-only
[`probe`](../apps/api/src/stocks/realtime/dnse/probe.py) records which REST and
WebSocket transport surfaces and market-hours claims were actually observed.
An outside-hours run cannot graduate the remaining live conformance gate.

## Realtime ingestion spine

Phase S2 persists normalized events in the dedicated `realtime_events` table.
It never writes realtime evidence to `provider_snapshots`. The
[`RealtimeEventStore`](../apps/api/src/stocks/realtime/storage.py) uses the S0
evidence ID as the durable idempotency key, records the retention-policy
version, orders replay by provider time, observation time, and evidence ID, and
stores at-least-once checkpoints separately from events.

The bounded [`IngestionSpine`](../apps/api/src/stocks/realtime/spine.py) writes
overflow to `realtime_spills` before returning queue pressure. A clean shutdown
drains its queue within the configured limit; a timed-out or cancelled item
remains recoverable from the spill table. Reprocessing can repeat delivery, but
the event primary key and monotonic projection order prevent double counting.

Redis holds only rebuildable hot projections. Each event family uses a
source-neutral normalized payload and a monotonic event-order key. The current
session, latest per-symbol events, and feed/data health can therefore be rebuilt
from PostgreSQL without a live DNSE call. The read-only
`GET /api/v1/realtime/health` endpoint reads durable health and returns `404`
when ingestion has never recorded a state; it does not convert missing state
into a healthy response.

Runtime activation is explicit. Set `REALTIME_INGESTION_ENABLED=true` only
after applying the realtime migration and configuring PostgreSQL, Redis,
`DNSE_API_KEY`, and `DNSE_API_SECRET`. `DNSE_BOARD_IDS` selects the admitted
boards. Queue size, worker count, and shutdown timeout remain bounded settings.
Book subscriptions stay disabled until the deferred S1 market-hours probe
proves quote quantity scale.

## Trades, bars, projections, and serving

Phase S3 derives one-minute and accepted higher-resolution bars only from
durable normalized trades. Derived bars carry their input evidence IDs and
method version; a DNSE daily close rolls stored internal one-minute bars into a
separate daily observation. Reconciliation retains both observations and an
explicit tolerance profile. No comparison rewrites provider or derived values.

Trade, foreign-flow, and UPCOM reference-input metrics are rebuildable Redis
projections with board identity, units, quality, evidence IDs, as-of time, and a
method version. The UPCOM input admits only G1 continuous trades, excluding
odd-lot, negotiated, and auction activity. The share-denominated foreign-flow
signal reads DNSE share counts directly from `realtime_events`; it never writes
them into `provider_snapshots` and refuses when any requested session is
missing or invalid.

The read-only trades, bars, foreign-flow, projection, and health routes under
`/api/v1/realtime` never call a provider. Event reads require a timezone-aware
bounded window, use query-bound stable cursors, enforce current Universe
membership, and expose normalized source, board, units, freshness, quality,
and evidence without raw DNSE payloads. Full-market instrument-catalog refresh
is a separate bounded runtime operation with no Universe argument; symbol live
subscriptions remain Universe-filtered.

## Market Monitor serving contract

Market Monitor derives cross-sectional HOSE and HNX readings from stored
evidence only. FiinQuant owns EOD price, index, foreign-flow, and valuation
history; vnstock owns listing and classification reference data; and DNSE owns
the admitted realtime overlay. Request handlers don't instantiate providers or
replace one source with another.

Authenticated reads are available under
`/api/v1/stocks/market-monitor` through the `overview`, `breadth`, `flows`,
`sectors`, `stocks`, and `stocks/{symbol}` resources. Every response includes
the requested exchange scope, as-of and generation times, separate EOD and
realtime evaluated/eligible coverage where live evidence is used, source
freshness, method versions, and typed issues. Selected 1/5/20-session horizons
apply consistently to foreign flow, sector return, and sector relative
strength. A
partial, stale, disconnected, or unavailable result remains an HTTP success
when the request itself is valid, and a missing value remains `null` rather
than becoming zero. Market valuation coverage uses the requested exchange
cohort as its denominator, and valuation percentiles require at least 20 stored
sessions. Overview active flow is the admitted DNSE signed value divided by
ADTV for the realtime-evaluable cohort.

The browser reaches this authenticated API through the narrow same-origin
`/api/alpha-desk/stocks/market-monitor` proxy subtree. Durable workspace state
is URL-addressable across the five lenses: Overview, Breadth, Money Flow,
Sectors, and Stocks. The implementation owners are
[`stocks.monitor`](../apps/api/src/stocks/monitor/),
[`use-market-monitor.ts`](../apps/web/src/hooks/use-market-monitor.ts), and the
[`market-monitor components`](../apps/web/src/components/market-monitor/).

The realtime overlay remains limited to admitted DNSE G1 evidence. A
disconnected overlay keeps historical EOD evidence visible with its own state;
it doesn't claim full-market realtime coverage. Production activation remains
blocked on the separate S1 market-hours probe.

## Rejected alternatives

The architecture rejects four shortcuts because they produce plausible but
incorrect market data:

- A universal quantity multiplier cannot represent round-lot and odd-lot boards.
- A provider timestamp cannot stand in for a unique sequence number.
- Last-write-wins storage cannot preserve cross-provider disagreement.
- Keeping raw payloads on normalized events expands credential and proprietary
  data exposure without improving the consumer contract.

## Next steps

Run the deferred S1 market-hours probe before production graduation. Outside
market hours, the implemented S3 contracts can be rebuilt and verified through
deterministic replay. The S3 tolerance decision is complete, but production
graduation still requires the S1 live probe. Keep v1 immutable; consider a v2
non-zero tolerance only after 10–20 live sessions demonstrate a legitimate,
repeatable provider difference. Fixture evidence must not be described as
measured live capacity or quote quantity scale.
