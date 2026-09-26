# Host-owned numbers — delivery report (2026-09-26)

Branch `feat/host-owned-numbers` (from `develop`, 19 commits), **local only —
not pushed, not merged**. Plan: `plans/260926-1448-host-owned-numbers/`.
Test model: `kiro-glm-5`.

## Outcome

Every figure in every answer, on every lane, is now checked against that Turn's
own tool data (`apps/api/src/agent/evidence/grounding.py`) and shown on the UI
as a chip: a cited figure carries its source number and date (`phiên 25/09/2026`,
`kỳ đến 30/06/2026`, `tính từ số liệu đến 25/09/2026`, `20/08/2026`), an old
source says `nguồn cũ`, and a figure nothing backs says `chưa kiểm chứng` — never
deleted. A draft with unsupported figures gets one tool-free repair first. Every
answered Turn writes a claim ledger. All four phases passed their gates; the
one partial item is CAR, which the free sources publish only in some quarters.

| Phase | Gate | Result |
|---|---|---|
| P0 figure check | 4 UI questions clean, ledger on every Turn | **passed**, re-run after P3 |
| P1 statements + calculator | ROE, P/B, NPL, CAR for 5 banks from tools, 10 samples checked | **passed** for ROE, P/B, NPL; CAR only where disclosed |
| P2 UI | chips, source list, report-wrong queue | **passed** |
| P3 events, news, screener | answer on UI through the figure check | **passed**; news depends on a flaky upstream |

## What changed

**Before P0.** Golden harness removed on the owner's instruction (`53477a2`).
Three tests already failing on `develop` fixed; pytest kept off the shared
Upstash Redis (`4a19e2f`).

**P0** (`d0ad3ac` … `937deb2`)
- Figure check: formats (`56.500`, `56,5 nghìn`, `56.5k`, tỷ / nghìn tỷ, %,
  English separators), rounding at the written precision, period rules (a named
  period must contain the source's date; "hiện tại" must be the latest session
  even with a date beside it; a date after "so với" is a comparison; a
  price-like figure for a session the market feed covers must match the feed,
  not a page), web > 120 days → `nguồn cũ`, reader's numbers exempt.
- `get_market_data`: host picks the window (last 3 months to today), leads with
  the latest session, says what today is for a stale window.
- `web_search`: a query with a past year carries a note naming today.
- Bugs found live and fixed: **indices were scaled ×1000 and printed in đồng**;
  optional tool arguments sent as `null` failed validation; vnstock's 26 s
  import timed out the first read after each restart.

**P1** (`e5599fc` … `50a814b`)
- `get_financial_ratios` behind `FinancialsProvider`: `KbsFinancials` (fixes
  vnstock's period mislabelling, drops duplicated quarters, fixed page size) and
  `VciFinancials` (NPL, coverage, CAR when disclosed, TTM ROE/ROA, NIM, LDR,
  CASA) — vnstock's VCI parser kept the oldest four rows, which is why it only
  ever returned 2018.
- `calculate`: fixed operations with the formula printed; a result is accepted
  only if every input is printed in another source this Turn read.
- Ticker-bound grounding (a figure about STB cannot rest on TCB's line), a
  nudge when a route answers the last round with denied tool calls, and a lane
  budget that funds the nudge and the repair.

**P2** (`84f7203`) — rehype plugin turning the labels into chips; source list
as a Markdown list; `scripts/export_flagged_answers.py` exports the "báo sai"
queue (the existing `wrong_figure` flag) with question and ledger.

**P3** (`8ee5784` … `96ba912`)
- `vnstock_provider.py`: one door for every vnstock call. **vnai allows 20
  requests/min for guests and calls `sys.exit` on breach** — in a server that is
  a `SystemExit` no handler catches. The gate stops at 16/min and turns
  `SystemExit` into a `rate_limited` refusal; provider failures are logged.
- `get_company_events` (dividends with ex-right/record/pay dates, AGMs, insider
  deals), `get_company_news`, `screen_stocks` (group/industry/list universe,
  price-board fields in one request, reported fields cached 12 h and read in
  parallel within 9 s, uncovered tickers named).
- Figure check: multi-part results become separate sources, a multi-ticker
  source answers only on each ticker's line, news > 30 days is `nguồn cũ`,
  decimals are never skipped as counts.

## Acceptance evidence

**P0 regression on the final build** (after P3), 2026-09-26 ~17:20:

| Question | Turn | grounded / labelled |
|---|---|---|
| Phân tích STB | `8024d279-b74c-460e-ad76-65985bc497e3` | 11 / 1 ("gấp 3,5 lần", self-computed) |
| STB trên chứng khoán hôm nay | `ad142b16-0ef1-4409-beb6-7fc8792af9b7` | 9 / 0 |
| Thị trường tuần vừa qua | `6441b2ef-64cc-465b-b2a3-36a76e0b498c` | 21 / 9 (model's wrong closes for 22–23/9, wrong TCB price, self-computed weekly change) |
| VIC hôm nay | `ae92e8c1-6fca-487b-b5e4-1ae8e55e809a` | 6 / 0 |

No current price carries a wrong year; every "hiện tại" is phiên 25/09/2026;
ledger 4/4. Baseline for comparison: Turn `f82f272c` (15:10) called
"35.000–38.000 đồng (tháng 9/2025)" current while its tool said 56.500 and the
real latest close was 76.500.

**P1**
- P/B × BVPS vs quarter-end close, 5 banks × 2 quarters: 7 exact, 3 off by a
  constant factor explained by dividend-adjusted closes (P/E × EPS = P/B × BVPS
  in every period).
- NPL to Q2/2026 for STB, VCB, TCB, MBB, ACB; cross-checked VCB 0,61 % (three
  pages) and STB Q4/2025 6,41 %; TCB 1,08 % vs one article's 1,15 % unresolved.
- CAR: STB 9,69 %, VCB 12,01 %, ACB 10,97 % at Q2/2025 only; the tool names it
  as missing for the latest quarter.
- Live Turn `8cd33c5f-4d27-41a7-b850-68fa3f3cb0cd`: P/B at today's price via
  `calculate` for all five banks, each cited to its own ticker's calculation.

**P2** — screenshot of thread `7e04add8-6629-40f1-9437-d32836d45f8e` on the dev
UI: 22 cited chips, 9 unverified chips, source list rendered.

**P3**
- Events `7d42c94e-fe51-4773-a702-8053de080cd2`: VCB dividend 450 đồng cited to
  "ngày 23/07/2026" (ex-right date), 10 s.
- Screener `3414d2d7-6a93-4c40-928b-efffcfffeb27`: one `screen_stocks` call,
  9 VN30 banks with P/B < 1,5, 37 figures cited with quarter or session dates.
- News `bf7bbc11-7c19-4f44-998f-4ac93c83610f`: the Vietcap news endpoint timed
  out; the model fell back to web pages, undated figures labelled "không rõ ngày".

**Tests**: API 1490 passed; web 519 passed; lint and type-check clean.

## Remaining risks
- **Free data is development-grade.** KB's ratio feed aligns values by page
  size and lists quarters twice; Vietcap's trading host and news endpoint time
  out intermittently from this network; historical closes are dividend-adjusted.
- **Provider quota**: 16 requests/min for the whole process. Several users at
  once, or one screen over 60 tickers, will see `rate_limited`.
- Literal matching can still accept a fabricated figure that equals a real one
  in a long source; the period, feed and ticker rules narrow it.
- Prose dates are not checked, only figures.
- The streamed draft is visible for the seconds a repair takes; the settled
  message replaces it.
- Page-vs-structured conflicts are not labelled automatically (definitions
  differ: quarterly vs annualised, period-end vs today's P/B).
- The P2 phase file was written after the code.

## Waiting on the owner
1. **A paid statements provider** for complete CAR and reliable quarters: per
   bank per quarter NPL, CAR, loan groups 1–5, total loans, equity, total
   assets, shares; unambiguous period keys and publication dates; a display
   licence. Plug-in: one class implementing `FinancialsProvider`.
2. **vnstock quota**: registering the free community key raises it to 60/min
   (a data-source registration, so not done without you).
3. **P4** (watchlist, alerts) — out of scope as decided.
4. **Merge / push** of `feat/host-owned-numbers`.
