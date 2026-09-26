# Host-owned numbers — delivery report (2026-09-26)

Branch `feat/host-owned-numbers` (from `develop`), not pushed, not merged.
Plan: `plans/260926-1448-host-owned-numbers/`. Test model: `kiro-glm-5`.

## Outcome

Every answer on every lane now has its figures checked against the Turn's own
tool data by `apps/api/src/agent/evidence/grounding.py`. Each figure is either
cited in place with its source date (`[1 · phiên 25/09/2026]`,
`[2 · 20/08/2026]`, `[3 · kỳ đến 30/06/2026]`) or labelled
`[chưa kiểm chứng]` / `[… · nguồn cũ]`, never deleted; a draft with unsupported
figures gets one tool-free repair round first. Every answered Turn writes a
claim ledger. P0 passed its gate. P1 is built and passes for ROE and P/B; **NPL
and CAR are blocked on a data-source decision** (see below). P2 and P3 were not
started.

## Changes by phase

**Before P0.** Golden harness removed on the owner's instruction
(`53477a2`). Three tests that were already failing on `develop` were fixed and
the suite was kept off the shared Upstash Redis (`RATE_LIMIT_ENABLED=false`
under pytest) (`4a19e2f`).

**P0 — host-owned figures** (`d0ad3ac`, `6f91d81`, `0636b77`, `937deb2`)
- `get_market_data`: host picks the window when the model gives none (end =
  today, start = 92 days before); result leads with the latest session (close,
  change, %, volume, whether today had a session); a window ending > 7 days
  before today carries "Hôm nay là …".
- `web_search`: a query naming a past year carries a `year_note`.
- Figure check: unit/format normalisation (`56.500`, `56,5 nghìn`, `56.5k`,
  tỷ / nghìn tỷ, %, English separators), rounding at the written precision,
  period rules (a sentence's named period must contain the source's date;
  "hiện tại" must be the latest session; a date after "so với" is a comparison;
  a price-like figure for a session the market feed covers must match the feed,
  not a page), web sources older than 120 days → `nguồn cũ`, reader's own
  numbers exempt.
- Loop: repair round (≤1), labels + dated source footer, ledger on every
  answered Turn; prompt rules for exact figures, missing data and conflicts.
- Bugs found by the live runs and fixed: **indices were scaled ×1000 and
  written in đồng** (VN-Index 1.785.110 đồng); optional tool arguments sent as
  `null` (strict mode's "omitted") failed validation; vnstock's import takes
  26 s (it phones home) and timed out the first market read after each restart
  — now warmed on a start-up thread.

**P1 — statements + calculator** (`e5599fc`, `2290b0f`, `01796ed`, `35203d4`)
- `get_financial_ratios` behind `FinancialsProvider`; `KbsFinancials` (dev
  only, same `personal_internal` gate). Fixes vnstock's KBS period mislabelling
  (it sorts headers by a repeating ID), drops quarters the feed lists twice,
  always reads 8 periods (at 4 the feed's values slide one quarter), states
  that NPL and CAR are not carried.
- `calculate`: fixed operations, formula printed. The figure check accepts a
  calculation only if every input is printed in another source this Turn read,
  and dates it by its newest input.
- Structured data grounds only figures about its own ticker when the sentence
  or table row names tickers read this Turn (a live Turn had cited STB's ROE to
  a TCB line and TCB's P/B to ACB's calculation because the digits coincided).
- Loop: a route that answers the last round with tool calls it was denied now
  gets the one empty-reply nudge (a live Turn settled `empty_answer` after 20
  reads); each lane's output budget funds the nudge and the repair
  (`RECOVERY_CALLS = 2`, 52.000 tokens, under the ledger's 60.000 hard cap).

## Acceptance evidence

P0 — final run after the last fix, `kiro-glm-5`, 2026-09-26 15:45–15:55:

| Question | Turn | grounded / labelled | Note |
|---|---|---|---|
| Phân tích STB | `572b66cb-8ed8-4a9c-85e6-a016f275c6fd` | 15 / 1 | current price 76.500 đ, phiên 25/09/2026 |
| STB trên chứng khoán hôm nay | `bf3c636f-9683-4131-9189-e506975f44e1` | 10 / 0 | |
| Thị trường tuần vừa qua | `b31da85f-cd45-4450-b43b-4af8e2dcfbad` | 15 / 12 | labelled = self-computed daily changes and rows copied onto the wrong session |
| VIC hôm nay | `9c9835a2-d4f2-4059-8c03-3c0c11bd19f0` | 7 / 0 | |

- No price stated as current carries a wrong year in any of the four (the
  15:10 baseline Turn `f82f272c` said "hiện tại (tháng 9/2025) 35.000–38.000").
- One false accept found in the "tuần" Turn (a weekly page grounding 22/09's
  close with 24/09's number) — fixed afterwards (`937deb2`, unit-tested), not
  re-run live.
- Ledger: 4/4 in the final run; 10 of 12 test Turns since deployment — the two
  without one ended on the route's own 504 before writing any answer, and a
  ledger is anchored to an answer message.
- Golden: removed by the owner, so the golden criterion no longer applies.
- Tests: API 1470 passed; web 508 passed (unchanged, no web code touched).

P1 — tool level, 5 banks × 2 quarters (Q2/2026, Q1/2026):
- ROE and P/B from `get_financial_ratios` for STB, VCB, TCB, MBB, ACB.
- Independent check: P/B × BVPS against the market close on the quarter's last
  session. 7/10 match to ±0,05. The 3 misses (MBB Q2, MBB Q1, ACB Q1) sit a
  constant factor from the close while P/E × EPS = P/B × BVPS holds within
  0,5 % in every period — the signature of a close adjusted for a share
  dividend, not of a mislabelled period. The market tool now says historical
  closes may be adjusted.
- Live Turn `8cd33c5f-4d27-41a7-b850-68fa3f3cb0cd` ("So sánh ROE và P/B … P/B
  theo giá hiện tại"): 5 ratio reads, 5 market reads, 5 `calculate` calls;
  every P/B is `close / BVPS` cited to its own ticker's calculation
  (e.g. STB 2,30x = 76.500 / 33.315,68, "tính từ số liệu đến 25/09/2026");
  22 figures grounded, 8 labelled — the model's "ROE (TTM)" numbers, which the
  source does not print, were labelled rather than accepted.
- P0 regression after all P1 changes: "Phân tích STB"
  `4c14796c-6c21-4106-8085-b1c6d904f299` — 18 grounded, 1 `nguồn cũ`,
  0 unverified; current price 76.500 đ, phiên 25/09/2026. (Two earlier retries
  ended on the LLM route's own 504/timeout.)
- **Gate: passed for ROE and P/B; not passable for NPL and CAR on a free source.**

## Remaining risks
- The free statements feed is unreliable by construction (page-size dependent
  alignment, duplicated quarters); fine for development, not for users.
- Literal matching can accept a fabricated figure that equals a real one in a
  long page; the period and market-feed rules narrow it, nothing closes it.
- Prose dates are not checked, only figures ("tuần nào trong tháng 9/2025?"
  appeared once in prose).
- The streamed draft is visible for the seconds a repair takes; the settled
  message replaces it (no SSE contract change was made).
- Conflict detection between a page and structured ratios is not automated:
  definitions differ (quarterly vs annualised NIM/ROE, period-end vs today's
  P/B), so a mechanical "mâu thuẫn" label would be wrong more often than right.

## Waiting on the owner
1. **NPL and CAR** — no free structured source; P1's gate cannot pass for them.
   A paid provider must supply per bank per quarter: NPL, CAR (as published
   under Circular 41), loan groups 1–5, total loans, equity, total assets,
   shares outstanding, with unambiguous period keys, publication dates and a
   licence for display. Plug-in: one class implementing `FinancialsProvider`.
2. **P4** (watchlist, alerts) — out of scope as decided.
3. Merge to `main` — not done; the branch is local.
