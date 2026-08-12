# Permit a market-wide Profit Ranking Census

The Profit Leaders Cohort must identify the actual 50 leaders among currently
listed HOSE and HNX equities, which cannot be derived from market data held only
for the bounded Universe. The Collector may therefore run a periodic Profit
Ranking Census across those exchanges, reading only trailing-12-month net
income attributable to the parent company, reporting period, exchange, and
listing status. Ranking compares companies at one common reporting period and
excludes UPCOM and delisted symbols.

A reporting period becomes rankable at 95% census coverage. The census runs
weekly, with daily targeted retries for missing symbols while a newer period is
below that threshold. Eligible companies must have positive, non-null profit;
ranking orders profit descending and then symbol ascending so the cohort stays
exactly 50 at a tie. If fewer than 50 companies qualify, the previous cohort
remains active.

## Consequences

This decision narrows ADR-0001's statement that collection covers only the
Universe. The exception applies only to the minimal inputs needed to form the
cohort; price, volume, valuation, reference history, and user-facing reads stay
bounded by the Universe. User requests never call a Provider Source. Candidate
membership is persisted and warmed before activation, so a ranking refresh
does not replace a healthy cohort with one that cannot yet produce a signal.

Raw census observations cross the existing Adapter seam as Fundamental
Snapshots and retain their source and effective time in `provider_snapshots`.
A separate versioned cohort read model stores the derived ranking and activation
state; it does not duplicate provider payloads. Company name, exchange, listing
status, and ICB Level 2 remain reference data and are persisted for Universe
members through `ReferenceSnapshot` rather than fetched by a serving request.
