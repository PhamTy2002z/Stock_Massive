# Phase 09a — market-wide quarterly financial store

- Plan: `plans/260826-2158-study-artifact-canvas/phase-09-financial-statement-store.md`
- Branch: `feat/study-canvas-runtime` (uncommitted, working tree)
- Status: completed

## Files added / modified

| File | Lines | What |
|---|---|---|
| `apps/api/alembic/versions/e6b3d90c41af_add_the_quarterly_financial_store.py` | 86 | new revision on head `d4a71c9e5b82`; two additive tables, downgrade drops |
| `apps/api/src/stocks/models.py` | +172 | `FinancialStatementLine`, `FinancialRatioSnapshot`, `SmallInteger` import (insertions only) |
| `apps/api/src/stocks/financial/__init__.py` | 31 | statement vocabulary; imports nothing, so a reader does not pay for vnstock |
| `apps/api/src/stocks/financial/fetch.py` | 302 | provider calls, column checks, wide→long, `item_seq`, period dedup |
| `apps/api/src/stocks/financial/templates.py` | 213 | concept resolver (`net_profit`, `pretax_profit`, `equity`) + `unknown` |
| `apps/api/src/stocks/financial/store.py` | 160 | idempotent upsert, per-symbol ingest |
| `apps/api/src/stocks/financial/reads.py` | 158 | one symbol's quarters; one quarter market-wide |
| `apps/api/src/stocks/financial_scan_job.py` | 362 | CLI `--scope declared|market [--statements ...]`, resumable, no checkpoint table |
| `apps/api/tests/stocks/financial/{fixtures,test_fetch,test_templates,test_store_reads,test_financial_scan_job}.py` | 1,122 | 79 tests, all offline |

Nothing outside the owned list changed. `models.py` diff is 172 insertions, 0 deletions.
`core_operating_result` not built (non-goal v1).

## Gates

- `cd apps/api && make test` → **1232 passed** (baseline 1152 + 79 new + 1 added
  concurrently by the phase-08 agent whose files are also in this tree). One
  transient failure in `tests/stocks/daily/test_backfill_daily.py` appeared on a
  run that overlapped that agent's edit; that file passes in isolation (18) and
  the next full run was clean.
- `make lint` (apps/api) → pass. New modules also `py_compile`d explicitly.
- `docker compose exec api alembic upgrade head` → `e6b3d90c41af`; both tables and
  both indexes verified in the container database.

## Live declared-scope scan (30 symbols, 4 requests each)

| Measure | Value |
|---|---|
| First run | 30 attempted, 0 skipped, **50,728 rows written**, 0 failures, 114 s |
| Stored | 46,576 statement lines + 4,152 ratio rows, 30 symbols |
| Second run | 30 skipped, **0 rows written**, counts unchanged (46,576 / 4,152) |
| Quarters stored | 2026-Q2 … 2024-Q3 (statements), 2026-Q2 / 2026-Q1 / 2025-Q4 (ratios) |
| max `item_seq` | 3 (four `accumulated_depreciation` rows on one balance sheet) |

**Coverage at the latest stored quarter (2026-Q2), declared scope:**

- `net_profit` **30/30 = 100%**
- `pretax_profit` 30/30 = 100% (28 resolved by label, 2 by the tax identity: SSI and TCX)
- `equity` 30/30 = 100%

STB `equity` = 62,807,249,000,000, identical to the `parent_equity_vnd` already
stored under the `fundamental` Capability in `provider_snapshots` for the same
quarter — the cross-check the brief asked for, in the live store.

Duplicate survival in the live store: `SSI` 2026-Q2 income
`business_income_tax_deferred` is two rows — `(seq 0, 4,585,945,424)` and
`(seq 1, 758,786,600)` — both values intact.

The market-wide scan was **not** run.

## Where the data contradicted the brief

1. **Statement depth is a property of the installed client, not of the request.**
   The brief (and the spec) said eight quarter columns. The host venv
   (vnstock 4.0.5) answered **four** and printed "Financial statements limited to
   4 periods"; the API container (vnstock 4.0.7) answered **eight, occasionally
   nine**, same account, minutes apart. The normaliser reads however many quarter
   columns arrive, so no code depends on the number — but no reader may assume a
   depth either, and both measurements are recorded in `fetch.py`.
2. **`pretax_profit` is not universal.** Measured: STB (bank) and HPG
   (non-financial) both report `net_accounting_profit_loss_before_tax`; SSI
   (securities) reports **no correctly labelled pretax line at all**. Its pretax
   figure arrives under `business_income_tax_expenses` (+1,528,966,041,130 for
   2026-Q2). Refusing it would have made pretax unknown for every securities
   house; guessing from the label is what the phase forbids. The resolver
   therefore accepts that one candidate **only when the arithmetic proves it**:
   `net == candidate + tax_current + tax_deferred`, which holds to the dong for
   all four of SSI's quarters and fails for STB, where the same `item_id` really
   is the tax. The answer carries `basis = labelled | tax_identity | unknown`, so
   the screener can see which kind of evidence it got.
3. **The duplicated `item_id` is worse than "an id repeated".** SSI's second
   `business_income_tax_deferred` row is labelled "Lợi nhuận thuần phân bổ cho
   lợi ích của cổ đông không kiểm soát" — the minority interest line arriving
   under another line's id (758,786,600, and net − that figure is exactly
   `attributable_to_parent_company`). So the provider maps two different lines
   onto one id; `item_seq` is load-bearing and `item_seq = 0` is the right
   occurrence for a concept.
4. **The duplicated ratio period label is a duplicated column.** KBS answers
   `['2026-Q2','2025-Q4','2026-Q1','2025-Q4_1']`, and the `_1` column's values
   are byte-identical to the `2026-Q2` column's. One of the two labels is wrong
   and neither is knowable, so the first column per period wins and the later one
   is dropped — three real quarters of ratios, as the spec predicted.

## Decisions worth knowing

- **One part is one transaction, not one symbol.** `get_sync_db` rolls back on
  exception, so a symbol whose cash flow fails would lose its income statement on
  every run forever (the failure recurs). The job commits per part and reports the
  symbol as failed with the parts that landed already stored. `ingest_symbol`
  stays single-transaction; the job owns durability granularity.
- **Two skip references, one per table.** Statements come from VCI, ratios from
  KBS, and the two publish a quarter on their own schedule; judging ratio currency
  by the statements' newest quarter would refetch the market forever whenever one
  source ran ahead.
- **`source` is `vnstock.VCI` / `vnstock.KBS`, per row.** The sub-source is part
  of the meaning: KBS reports ROE as 4.74 where VCI reports 0.0589 for the same
  thing.
- **`financial/__init__.py` imports nothing.** `fetch` pulls pandas and vnstock at
  module load (repo pattern), so the statement vocabulary lives in the package
  root and phase 09b's Signal Fields can import `financial.reads` without paying
  for the provider client.
- Tests that write use invented tickers (`ZZFIN*`, `ZZSCAN*`) with captured real
  numbers; golden concept tests are pure in-memory over captured frames.

## Unresolved questions

1. `item_id` is `String(128)`; the longest measured is 101 characters
   (`loss_from_disposals_or_sales_of_investments_in_subsidiaries_associates_and_joint_ventures_before_2016`).
   A longer id from a future provider release would fail the insert rather than
   truncate. Left as is — widening is a one-line migration, silent truncation is
   not recoverable.
2. Statement depth beyond the client's window cannot be backfilled. Depth
   accumulates only if the scan runs at least once per quarter; nothing in the
   repo schedules it yet.
3. Phase 09b will need a rule for `plan_completion_pct`; no plan/target line was
   found in any of the three templates.
