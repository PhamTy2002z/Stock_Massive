# P2 — figure labels on the UI

Written after the code (the plan-first step was skipped for this phase; the
design is recorded here as built).

## Decisions
- The labels stay in the answer text (the canonical record the reopened
  Thread, a copy and the next Turn read). The web reads them back with a
  rehype plugin (`apps/web/src/lib/alpha-desk/figure-markers.ts`), the same
  mechanism `word-cadence.ts` uses — no new API field, no SSE change.
- Chips: cited = neutral, stale = caution dashed, unverified = caution filled.
  Never the market up/down colours (they mean direction and the reader can
  swap them in settings).
- Source list: the API writes it as a Markdown list so each source is a line;
  a chip's title shows its source line.
- "Báo sai": the existing flag (`wrong_figure`, `agent_message.flagged_reason`)
  is the queue; `python -m scripts.export_flagged_answers` exports it with the
  question and claim ledger (golden was removed, so there is no golden queue).

## Gate (result)
Screenshot of Turn `8cd33c5f` (thread `7e04add8…`) on the dev UI: 22 cited
chips, 9 unverified chips, source list rendered; web tests 519 passed, lint
and type-check clean.
