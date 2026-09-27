# Close the host-owned-numbers delivery gaps

Status: done (2026-09-27) · Branch: `feat/host-owned-numbers` · Follows
`plans/260926-1448-host-owned-numbers/` (report: `plans/reports/delivery-260926-1600-host-owned-numbers.md`).

## Outcome
The gaps left open by that delivery that need no business decision are closed,
and the community key becomes configuration. The paid statements provider stays
an owner decision (one `FinancialsProvider` class when chosen).

## Decisions (owner delegated the choice, 2026-09-27)
1. **Provider cache, in process.** `market_data`, `financials` and `company`
   re-read the provider on every call, which spends the 16/min quota on repeats.
   A TTL cache inside `vnstock_provider` (one process, and `vnai` counts its
   quota per process, so Redis would add serialisation risk for no gain).
   A cache hit reports when the data was actually fetched as `retrieved_at`.
   TTL: bars reaching today 60 s, closed ranges 6 h, statements 12 h, events
   and news 15 min. Successes only.
2. **Prose dates are checked.** A full date (`dd/mm/yyyy`) in an answer must
   appear in a source the Turn read (any common Vietnamese or ISO spelling, or
   day/month on a page that omits the year), be today, or come from the user's
   question. Otherwise it is labelled `chưa kiểm chứng` and goes through the
   same one repair round as a figure. Month-only and bare years are not checked.
3. **A timed-out read says it can be retried.** Idempotent reads that hit their
   bound tell the model a repeat call is safe (the page usually lands in the
   cache seconds later).
4. **Community key as configuration.** `VNSTOCK_API_KEY` is forwarded to the
   container (`vnai` reads it itself); with it the gate allows 48/min instead
   of 16.

## Non-goals
Paid statements provider (owner decision), SSE source pill for data tools,
holding the draft back during repair, page-vs-structured conflict labels.

## Acceptance
- Repeating a question within the TTL makes no second provider request.
- `13/07/2026` written where the sources say `10/07/2026` is labelled.
- Backend and web suites pass; lint and type-check clean.

## Result
- Same STB question asked twice: provider reads took 580–1636 ms, then 9–36 ms
  (cache hits, no provider log line).
- About 50 full dates across two live answers, none mislabelled; the ledger's
  only gaps were two invented percentages.
- Backend 1496 passed. Web unchanged in this plan.
