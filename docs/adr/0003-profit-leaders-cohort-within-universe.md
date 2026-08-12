# Keep the Profit Leaders Cohort within the Universe

The Volume Spike screen must cover exactly 50 currently listed HOSE or HNX
profit leaders without turning Stock_Massive into a full-market tracker. The
system therefore reserves part of the bounded Universe for the dynamic Profit
Leaders Cohort and collects its Snapshots through the existing Collector. It
does not restore the legacy market-wide OHLCV collector or call a Provider
Source from a user request.

## Consequences

The Universe must always have capacity for all 50 cohort members within its
existing 100-symbol cap. Configuration can claim at most the remaining 50
places after deduplication and is rejected if it exceeds that capacity; the
system never evicts an explicitly selected symbol silently. Ranking refreshes
stage a candidate cohort while its new members receive a rolling history
warm-up. The previous cohort stays active until at least 45 candidate members
are evaluable, after which the new cohort can activate with `partial` Signal
Coverage until all 50 are ready. The secondary screen covers the whole bounded
Universe and is labelled **All Universe**, never **All Market**.

Only currently listed HOSE or HNX equities can stay active. When a listing
census confirms that a member has left those exchanges, the next eligible
symbol from the same ranking becomes a candidate replacement and receives a
Warm-up; the active result can report `partial` coverage during that transition.

Cohort membership is a versioned read model rather than a ranking recomputed on
each request. Every version records its reporting period, census provenance,
ordered members, and `candidate` or `active` state. Activation is atomic and
older versions remain available for exact historical evaluation. A historical
Volume Spike query uses the version that was active on the requested Trading
Day, never today's survivors projected backward.

A failed census, Warm-up, or collection cycle cannot replace the active version
or erase the last-known-good signal. Serving continues from that data with
`lagging` or `stale` Signal Freshness until a complete transaction advances it.
