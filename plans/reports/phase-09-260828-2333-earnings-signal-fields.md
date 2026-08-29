# Phase 09 — Signal Field `earnings.*`

Status: DONE_WITH_CONCERNS (one shared file had to be touched; see §6)

## 1. What was built

Three registered Signal Fields, all served through `serve_field` / `get_field`,
all reading `financial_statement_line` through `src/stocks/financial/reads.py`
only:

| field | reads | unit / sign | kind |
|---|---|---|---|
| `earnings.eps_basic_yoy_pct` | `eps_basic_vnd`, quarter vs same quarter prior year | percent / signed | vocabulary, stored |
| `earnings.net_profit_yoy_pct` | `net_profit_loss_after_tax`, same-quarter-prior-year | percent / signed | vocabulary, stored |
| `earnings.gross_profit_trend` | `gross_profit`, least-squares slope over 4 consecutive quarters scaled by their own average level (percent of level per quarter) | percent / signed | vocabulary, stored |

All three: `projection = BarProjection.VOLUME` (no price arithmetic, so no
price-basis/band refusal inherited), `min_sessions = 1`,
`lookback_sessions = 5`, `requires_quarterly_statements = True`.

Mechanism follows the `requires_foreign_share_flow` precedent exactly — the
field declares the need, `serve_field` loads, `FieldWindow` carries it, no field
opens its own query:

- `src/stocks/signals/earnings.py` (new) — `QuarterlyStatements`,
  `quarterly_statements_for()`, the three readings, period arithmetic.
- `src/stocks/signals/fields.py` — `SignalField.requires_quarterly_statements`,
  `FieldWindow.quarterly`, and a declaration-time refusal for a **ranked** field
  that asks for quarters (the cross-sectional path loads one quarter for a whole
  sample, so declared there the field would refuse for every member of every
  ranking under a code naming the store).
- `src/stocks/signals/serving.py` — loads the quarters at the same
  `cutoff = health.last_session or frame.bars[-1].session_date` the foreign room
  uses.
- `src/stocks/signals/registry.py` — three declarations + `EARNINGS_FIELDS` +
  `_index()` entries.
- `src/agent/tools/signals.py` — `CATALOG_AXES["earnings"] = Axis.FUNDAMENTAL`
  and three `DISPLAY_NAMES` rows. **Mandatory, not optional**: both tables are
  checked in both directions at import (`_check_the_catalog_holds`,
  `_check_the_display_names_hold`), so a new namespace/field without them fails
  the build.
- `tests/test_signal_earnings.py` (new) — 18 tests.

Two rules worth naming, both derived from measurement rather than taste:

1. **An exact zero is read as a line that was not filed.** Measured: 2 491 of
   9 536 `eps_basic_vnd` rows are exactly `0.0000`, and the filings they sit in
   carry trillions of net profit (BID/CTG/MBB/TCB/HPG/SSI all file a 2026-Q2
   profit in the trillions and an EPS of exactly zero); meanwhile **0** of 9 432
   `net_profit_loss_after_tax` rows are zero, so nothing is lost by reading a
   zero the same way everywhere. Read the other way, VPL — EPS 94 in 2025-Q2 and
   `0.0000` in 2026-Q2 — would have printed exactly −100%, a feed gap narrated as
   a collapse.
2. **The cutoff decides which quarters existed.** Only quarters whose *end* is
   at or before the window's newest session are visible, the same "as it stood
   then" rule `fundamentals_on_or_before` keeps. Filing lag is not modelled and
   cannot be: this table's `observed_at` is collection time and the whole store
   was backfilled at once. Documented in the module docstring as a limit.

## 2. Industry coverage — measured, not assumed

All queries pinned to the real DB (`docker exec stockmassive-db-1 psql -U postgres -d stockmassive`).

**Which lines exist at all:**

```sql
select item_id, statement, count(distinct symbol) syms, count(distinct period) qs
from financial_statement_line
where item_id in ('eps_basic_vnd','net_profit_loss_after_tax','gross_profit')
group by 1,2;
-- eps_basic_vnd | income | 1235 | 34
-- gross_profit  | income | 1192 | 34
-- net_profit_loss_after_tax | income | 1222 | 34
```

**Banks file no gross profit — every one of the exceptions is a bank:**

```sql
with p as (
  select symbol,
         max(case when item_id='net_profit_loss_after_tax' then 1 else 0 end) np,
         max(case when item_id='gross_profit' then 1 else 0 end) gp
  from financial_statement_line where period='2026-Q2' and item_seq=0 group by 1)
select count(*) filter (where np=1 and gp=0) np_only,
       count(*) filter (where np=1 and gp=1) both, count(*) total from p;
-- np_only=30 | both=1094 | total=1137
select string_agg(symbol,' ' order by symbol) from p where np=1 and gp=0;
-- ABB ACB BAB BID BVB CTG EIB EVF HDB KLB LPB MBB MSB NAB NVB OCB PCB PGB
--   SGB SHB SSB STB TCB TIN TPB VAB VBB VCB VIB VPB
```

**Zeros and negatives, which decide the refusal rules:**

```sql
select count(*) filter (where value=0) zero, count(*) rows_ from financial_statement_line
  where item_id='eps_basic_vnd' and item_seq=0;                    -- 2491 / 9536
select count(*) filter (where value=0) zero, count(*) rows_ from financial_statement_line
  where item_id='net_profit_loss_after_tax' and item_seq=0;        -- 0 / 9432
select count(*) filter (where value=0) zero, count(*) filter (where value<0) neg
  from financial_statement_line where item_id='gross_profit' and item_seq=0;  -- 157 zero, 509 neg
```

**Live end-to-end run against the production store** (in the `api` container,
read-only, `latest_trading_day = 2026-08-27`):

```
VCB eps=+64.62% | net_profit=+64.65% | gross_profit_trend=statement_line_missing
VNM eps=+30.88% | net_profit=+27.96% | gross_profit_trend=+4.62%
VHM eps=+50.38% | net_profit=+221.77% | gross_profit_trend=+36.33%
VND eps=+139.67% | net_profit=+139.49% | gross_profit_trend=+1.15%
BID eps=statement_line_missing | net_profit=+20.25% | gross_profit_trend=statement_line_missing
HPG eps=statement_line_missing | net_profit=+50.65% | gross_profit_trend=+19.36%
SSI eps=statement_line_missing | net_profit=+27.31% | gross_profit_trend=+0.10%
V68 all three = fundamental_not_stored   (one filed quarter in the whole store)
```

Coverage over the 30-symbol Universe the chat lane may read (live):

| field | numbers | refusals |
|---|---|---|
| `earnings.net_profit_yoy_pct` | **30 / 30** | — |
| `earnings.eps_basic_yoy_pct` | **19 / 30** | 11 × `statement_line_missing` — ACB BID CTG HPG MBB SHB SSB SSI TCB (EPS filed as 0) · VPL (0 this quarter) · VIC (year-ago EPS −337) |
| `earnings.gross_profit_trend` | **17 / 30** | 13 × `statement_line_missing` — ACB BID CTG HDB LPB MBB SHB SSB STB TCB VCB VIB VPB, i.e. **exactly the banks** |

Industry representatives used in the golden test, each with the figures the
store actually holds for 2025-Q2 … 2026-Q2: bank **VCB** (+ **BID** as the
zero-EPS bank), manufacturer **VNM**, real estate **VHM**, broker **VND**, plus
**V68** for the one-filed-quarter case.

## 3. Refusal codes — no new code, no file touched

| condition | code | why it is the truthful pointer |
|---|---|---|
| no income statement at or before the cutoff | `fundamental_not_stored` | nothing collected for this symbol at this date |
| the same quarter one year earlier is not stored (newly listed / newly filing) | `fundamental_not_stored` | the missing input is that *quarter*, not the line; the window was deliberately not widened |
| a quarter of the 4-quarter run is missing | `fundamental_not_stored` | a slope over a series with a hole is a different series |
| the line is absent from a stored statement (bank × `gross_profit`) | `statement_line_missing` | the filing is there; a reader must not be sent to look for it |
| the line is filed as an exact zero (unreported) | `statement_line_missing` | see §1.1 |
| the year-ago base is negative, or the 4-quarter average level ≤ 0 | `statement_line_missing` | the line is unusable rather than absent — the same wording `cross_sectional._quarterly_ratio` already uses for a non-positive denominator |
| newest quarter older than 150 days (`FUNDAMENTAL_STALE_DAYS`) | `stale_fundamental_period` (**degradation**, never a refusal) | the number was true of its quarter; the quarter and its age travel with it |

`src/stocks/signals/issues.py`, `src/alpha/reasons.py` and
`apps/web/src/lib/signal-issues.ts` are **untouched** — all three codes plus the
staleness code already exist at both ends, and `reasons.py`'s existing sentence
("the line this figure divides is not in it") is literally true for all three
fields (both YoY fields divide by the prior-year line; the trend divides the
slope by the four quarters' average level). A test asserts a reader sentence
exists for each of the three codes these fields can emit.

## 4. Tests — `tests/test_signal_earnings.py`, 18 tests

The per-industry golden test is written so a **global refusal is red**: it
asserts a *number* per industry per field, and lists the refusals in the failure
message. Highlights:

- `test_at_least_one_symbol_per_industry_answers_with_a_number` — parametrised
  over the three fields × their required industries (bank / manufacturer /
  real estate / broker; the trend field excludes bank by design).
- `test_a_bank_is_refused_the_gross_profit_line_it_does_not_file` — asserts the
  specific code, not "some refusal".
- `test_two_fields_over_one_filing_disagree_about_it` — BID: EPS refuses,
  net profit answers +20.25%.
- formula pins for the YoY percentage and the least-squares slope, computed in
  the test from the fixture figures rather than copied from a run.
- `test_a_company_with_one_filed_quarter_has_no_year_ago_quarter` (V68).
- cutoff tests: `quarterly_statements_for` at 2026-08-21 / 2026-05-15 /
  2026-06-29, and the field's answer moving with the cutoff.
- `test_a_quarter_past_every_filing_deadline_degrades_the_answer`.
- `test_they_are_served_on_quantities_rather_than_prices` — the same window that
  gives `mixed_price_basis` on the price projection still answers here.
- `test_a_ranked_field_may_not_ask_for_a_symbols_quarters`.
- `test_the_registry_digest_moves_when_these_fields_are_registered` — asserted
  by monkeypatching the three fields **out** of `REGISTRY` and comparing
  `registry_version()`; nothing hand-bumped. (Note: this build's
  `registry_version()` already hashes `projection` as a seventh declaration, so
  the Phase 04 note in the phase file is already resolved in code.)

## 5. Gates

- `make test` (host, `apps/api`): **1423 passed**, 0 failed, 40s — the whole
  suite, including the other session's in-flight edits present in the tree.
- `tests/test_signal_earnings.py`: 18 passed.
- `make lint` (`py_compile`): pass. All touched modules byte-compile.
- Web gates **not run**: no file under `apps/web` was changed, no new refusal
  code, no change to `contracts/signal-desk-widget-catalog.json`. Nothing in
  `apps/web` mirrors the Signal Registry (checked).

## 6. Concerns / deviations

1. **`src/agent/tools/signals.py` had to be edited** (2 hunks: one
   `CATALOG_AXES` line, three `DISPLAY_NAMES` lines). It was not in the phase's
   file list, and it is unavoidable: that module refuses to import when a
   registered namespace has no axis or a registered field no display name. The
   file already carried your in-flight `_ISSUE_GROUPS` work; my hunks are pure
   insertions in two unrelated regions and the full suite is green with both.
   Flagging it because it is a shared file.
2. **`fields.py` and `serving.py`** were modified as the task instructed
   (declaration flag + loader). Both are additive; no existing signature changed.
3. **A negative year-ago base is reported as `statement_line_missing`.** The
   line is present and real, so "missing" is a slight stretch — it follows the
   precedent `_quarterly_ratio` set for non-positive denominators ("the line
   being unusable rather than absent") rather than opening a fourth code, since
   a new code means editing `issues.py`, `reasons.py` and `signal-issues.ts`,
   all locked. Live impact: 1 of 30 Universe symbols (VIC). If you would rather
   have a distinct code (e.g. "the year-ago quarter was a loss, so a percentage
   change against it is not orderable"), that is a two-sentence follow-up in
   three files.
4. **`get_series` over an `earnings.*` field costs ~6 small indexed queries per
   point** (one period index read + up to 5 statement reads). At the default 60
   points that is ~360 queries for a step function that changes 4 times a year.
   Not fixed here (no scope for a series-level cache), and `MAX_WINDOW_READS`
   does not see it because the cost is not in sessions.
5. **Plan status not edited.** The phase file's front matter still says
   `status: pending`; plan bookkeeping is yours (the hook forbids editing status
   cells directly).

Status: DONE_WITH_CONCERNS
Summary: Three `earnings.*` Signal Fields serve real numbers out of the
quarterly statement store through the declared-flag/`FieldWindow` path, with a
per-industry golden test that goes red on a global refusal; live Universe
coverage is 30/30, 19/30 and 17/30, and every refusal names a missing input.
Concerns/Blockers: `src/agent/tools/signals.py` had to be edited (import-time
axis/display-name gates) while another session holds that file; a negative
year-ago base reuses `statement_line_missing` rather than opening a new code.
