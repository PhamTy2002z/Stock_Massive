# Phase Implementation Report

### Executed Phase
- Phase: phase-10-earnings-screener — Study `earnings_dislocation_screener`
- Plan: `plans/260826-2158-study-artifact-canvas/`
- Status: completed

### Files Modified
- NEW `apps/api/src/studies/earnings_dislocation.py` (~830 lines) — the Study
- `apps/api/src/studies/__init__.py` (+1) — registration import
- `apps/api/tests/test_agent_capability_contract.py` (1 line) — wire-schema sha256 lock
  moved to `670bad3d…c99fef` (the existing comment already explains why registering a
  Study moves it; left in place)
- NEW `apps/api/tests/studies/earnings_fixture.py` (~370 lines) — synthetic 45-symbol market
- NEW `apps/api/tests/studies/test_earnings_dislocation.py` (26 tests)
- `apps/api/src/studies/widgets.py` — **not touched**; all four widgets already existed
- `src/agent/loop.py`, `src/agent/prompt/**`, `src/stocks/**`, `apps/web/**`, alembic —
  **not touched** (`git diff` on `src/agent/loop.py` is empty; the 2.7.0 PROMPT_VERSION in
  the tree predates this phase)

### Tasks Completed
- [x] Params: `period` (default = newest sufficiently-filed quarter), `min_profit_growth_pct`
      20, `max_price_change_pct` 5, `top_n` 10 clamped to 1–20, `universe` `market`|`declared`
- [x] Store-only compute: two market-wide filing reads, one market-wide daily read, one index
      read; no provider call anywhere on the path
- [x] Exclusions counted and named at the first gate each symbol fails, 11 gates, sum invariant
- [x] YoY growth on positive bases both sides; 20-session return and return-minus-VNINDEX
- [x] `dislocation_rank` = growth percentile × (−relative-return) percentile, liquidity floor
      (`adtv ≥ 3 tỷ`) applied as a gate; both components in the ranking frame and the provenance
- [x] Anti-lookahead: only symbols whose `period` filing is stored; roster of today (recorded)
- [x] `headline` / `frames` (`tiles`, `scatter`, `ranking`, `filters`) / `view` with
      `stat_tiles` · `scatter_quadrant` (hero) · `ranked_bars` · `data_table`
- [x] Registered; wire-schema lock updated deliberately

### Tests Status
- `cd apps/api && make test`: **1260 passed** (baseline quoted as 1232; +26 are this phase's
  tests, so the baseline had already moved by 2 before this work started)
- `make lint`: pass
- Focused: `tests/studies` 103 passed
- Golden test: 45 planted symbols, rank order known in advance from
  `growth_rank × price_rank / n²`; the pairs are scrambled so neither axis alone, nor the two
  swapped, reproduces the expected order
- Exclusion arithmetic asserted twice — off the `filters` ladder and off the headline copy
- Transcript guard extended: `frames` cells (`ZZE44`, a gate label, `growth_percentile`,
  `quadrant`) are absent from the messages a Turn would send; the artifactId is present
- Imperative regex (`nên mua|mua ngay|bán ngay|WAIT|BUY|SELL`, case-insensitive) over the
  serialized headline, the canvas title and all four quadrant labels
- Network test: `socket.socket.connect` is replaced with a raising stub after the session's
  connection is warmed; compute runs to completion with zero sockets opened

### Live run (real store, 2026-08-27, inside the api container)
Params: all defaults. Wall clock **0.26 s** (a second run, warm; first run 0.20 s).

```
period 2026-Q2 | prior 2025-Q2 | asOfSession 2026-08-27
screened 1523 | measured 147 | afterFilters 65   health: degraded
excluded  no_filing 597 · no_prior_filing 12 · non_positive_profit 142 ·
          non_positive_prior_profit 58 · insufficient_price_history 192 ·
          thin_liquidity 375 · below_growth_threshold 59 · above_price_change 23
          (concept_unknown 0, prior_concept_unknown 0, price_window_unusable 0)
sum: 1458 excluded + 65 matched = 1523 screened
 1 BVB  rank=0.9394 growth=2461.7% rel=-8.61%  ret=-3.63%  adtv=9.4 tỷ
 2 POW  rank=0.9135 growth=387.0%  rel=-9.00%  ret=-4.01%  adtv=94.2 tỷ
 3 HUT  rank=0.8980 growth=250.8%  rel=-15.12% ret=-10.14% adtv=18.2 tỷ
 4 NTL  rank=0.8783 growth=228.4%  rel=-13.38% ret=-8.39%  adtv=3.9 tỷ
 5 VPL  rank=0.8186 growth=275.2%  rel=-7.50%  ret=-2.52%  adtv=44.2 tỷ
headline 1271 chars
```

**The market-wide scan had not finished.** `financial_statement_line` held 2026-Q2 for
929 symbols at the time of the run (81 when this phase started, 332 an hour in), i.e. 926 of
the 1523 roster symbols — 61% coverage, under the 85% line the phase's own risk note draws, so
the run reports `health: degraded` and the provenance names the coverage. The screen is
correct; its population is not yet the market.

Two rows hand-checked against the store: POW 3,707,672,320,897 / 761,350,344,625 − 1 =
386.99% ✓; close 13,150 / 13,700 − 1 = −4.01% ✓; VNINDEX 1,831.56 / 1,744.66 − 1 = +4.98% ✓;
relative −9.00% ✓. BVB's 2,461.7% is a real base effect (10.3 tỷ in 2025-Q2 against 264.8 tỷ),
not a resolver artefact.

### Deviations from the spec, and why
1. **Four frames, not three.** `stat_tiles` has to draw a frame, so `tiles` exists beside
   `scatter`, `ranking` and `filters` — the same shape both shipped Studies use.
2. **Headline key `dislocationRank`, not `rank`.** In the frames `rank` is the row's position;
   a model handed `"rank": 0.87` would narrate "hạng 0,87". Three keys were added for the same
   reason the other Studies carry them: `priorPeriod` (a growth figure is meaningless without
   the base quarter), `asOfSession`, and `measured` (the population the percentiles were taken
   over — without it `afterFilters` is a count out of a universe most of whose members were
   never measurable).
3. **Eleven gates, named from the data rather than from the brief's three.** `template_unknown`
   is not a cause that exists: `net_profit_loss_after_tax` resolves by label under all three
   templates (`stocks/financial/templates.py`), so an unreadable filing surfaces as
   `concept_unknown` — measured 0 today. The causes the data forced and the brief did not list:
   `no_prior_filing` and `prior_concept_unknown` (a YoY needs two quarters), `non_positive_profit`
   and `non_positive_prior_profit` (a percentage out of a loss is unusable — the rule
   `entry_condition_review` already keeps), `insufficient_price_history`, and the guard
   `price_window_unusable` (mixed price basis, a non-positive base close, or an index lookup
   that fails; none has ever fired).
4. **A refusal floor of 15 measurable symbols**, reusing `signals/fields.PERCENTILE_ABSOLUTE_FLOOR`.
   `min_sample_for` is deliberately *not* used and the code says why: its 0.6 share assumes every
   member of the sample is expected to answer, whereas here exclusion is the screen's own
   product — most of a market of 1,523 legitimately fails a liquidity floor.
5. **Provenance carries the methodology.** `Provenance` has no field for a note and the browser
   renders no caption for a `data_table`, so the five limits (approximated traded value, the
   trailing-20-session window instead of a publication date, the composite's formula, the
   basis argument, the roster's survivorship) live in `provenance.reason`. That costs the model
   ~150 tokens deliberately: the spec asks it to narrate the methodological limits.

### Issues Encountered
- **The default-period rule needed inventing.** "Quý gần nhất đã công bố đủ" cannot mean
  `max(period)` — the newest quarter is always half-filed — and cannot be a share of the market
  either, since a scan mid-walk makes every quarter look empty. It is the newest of the last 8
  quarters holding ≥ 80% of what the store's fullest recent quarter holds. Tested against a
  fixture where three symbols have filed 2026-Q3 and forty-two have filed 2026-Q2.
- **A fixture that sat exactly on a threshold decided its own count.** Growth of exactly 20.0
  against a floor of 20.0 turns on whether `1.2 − 1` is a shade under `0.2` in binary — it is.
  The fixture now sits half a point off both thresholds and says so; the Study's comparison was
  never wrong.
- **Destructive tests run inside rolled-back transactions.** One assertion needs an empty
  `financial_statement_line`, and a committed truncation would have taken rows the market-wide
  scan collected. Every test that breaks something now does it in an uncommitted transaction.
- **The plan file and status were not touched** — not in this phase's file ownership, and plan
  status is not edited by hand.

### Next Steps
- Re-run the live screen when the market-wide scan finishes; `health` should turn `normal` once
  coverage passes 85%, with no code change.
- `thin_liquidity` removed 375 of 1,523 and `insufficient_price_history` 192. Both are honest,
  but if a later phase wants a screen of UPCOM smallcaps the floor becomes a parameter — it is
  a module constant today, on purpose.

### Unresolved questions
1. Point-in-time filing dates remain absent from the provider, so "phản ứng giá quanh ngày công
   bố" stays out of reach. If a filing-date source appears, the reaction window becomes
   per-symbol and this Study ships as version 2 rather than as an edit.
2. Survivorship for past quarters (a roster as it stood then) is recorded as out of scope; a
   screen of 2024-Q2 today silently excludes companies delisted since.
