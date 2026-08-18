# Separate signal Warm-up from deep Backfill

A Volume Spike needs only the target Trading Day and 20 preceding Trading Days,
while the existing Backfill walks years of Main and Cover Source history. New
Profit Leaders Cohort members therefore receive a repeatable, recent Main Source
Warm-up instead of waiting for deep Backfill or 21 daily Collector cycles. Deep
Backfill remains responsible for long-range charts and never gates signal
readiness.

## Consequences

Warm-up persists every session in its bounded window and can repair missed
recent collection cycles. Backfill selection must use fair rotation and retry
backoff so repeatedly failing symbols cannot occupy every per-run slot. The
23:00 market catch-up retries when the Main Source has not advanced the Trading
Day. User refreshes only reread stored data; they never trigger either process
or call a Provider Source.

Successful Collector and Warm-up transactions advance a market generation used
by Volume Spike cache keys together with Signal Scope, resolved Trading Day,
threshold, exchange filter, and Cohort Version. A separate corporate-action
generation makes action ingestion or correction move the key as well, because
the prepared volume window's health depends on those stored rows. Operator-only
commands can trigger census retry, Warm-up, and market catch-up through the
existing tracked run mechanism; they obey the same one-at-a-time guards as
scheduled work.
