# P1 — statements adapter + calculator

## Findings that shape it (probed 2026-09-26, vnstock community in the api container)
- KBS `ratio` (CSTC) is current (to Q2/2026) and has ROE (quarter and trailing
  4Q), ROA, P/B, P/E, EPS, BVPS, NIM, CIR, LDR for banks. **No NPL, no CAR.**
- vnstock's KBS parser mislabels periods: it sorts `Head` by `ID`, but IDs repeat
  (1,2,1,2,…) and `Value{i}` follows the original `Head` order. The raw payload
  itself carries several heads for one quarter (three "2025 Q4" entries) with
  different values — those periods are ambiguous at the source.
- KBS balance sheet for banks is empty; VCI ratio (which lists NPL and CAR)
  returns only 2018 through this community build. No free structured source
  for NPL or CAR was found.

## Changes
1. `tools/financials.py` — `FinancialsProvider` protocol (the adapter seam) and
   `KbsFinancials` (dev/test only, same `personal_internal` + flag gate as the
   market read). Pairs `Value{i}` with `Head[i-1]`, drops any period that
   appears more than once, returns metrics per period with period end and
   report date. Tool `get_financial_ratios(symbol, periods)` renders dated
   lines (period end first) for the figure check and states which metrics this
   source does not carry (NPL, CAR).
2. `tools/calculator.py` — `calculate(operation, inputs)`: fixed operations
   (ratio, percent change, difference, sum, product, divide-as-%), inputs with
   value + unit + label, result rounded and printed with its formula.
3. `evidence/grounding.py` — a calculation's result is a valid source only if
   every input is itself found in this Turn's non-calculation sources; it takes
   the earliest date of those inputs. "Hiện tại" on a structured source means
   that source's latest line within its own freshness window (market 7 days,
   statements 150 days).
4. Prompt: ratios come from `get_financial_ratios`; any derived number goes
   through `calculate`; missing metrics are stated as missing.

Conflict labelling between a page and structured data is **not** automated:
definitions differ (quarterly vs annualised NIM/ROE, period-end vs today's P/B),
so a mechanical "mâu thuẫn" label would be wrong more often than right. The
structured source still wins when both print the same figure, and the prompt
asks for conflicts to be stated.

## Gate
ROE and P/B for 5 banks (STB, VCB, TCB, MBB, ACB) from tools with formula
(P/B recomputed by `calculate` from the latest close and BVPS), checked by hand
against the source rows on 10 samples; P0 re-run still holds.
**NPL and CAR cannot pass on a free source** — needs the owner's data decision.

## What a paid provider must supply to replace KBS
Per bank per quarter: NPL (nợ nhóm 3–5 / tổng dư nợ), CAR (Basel II/III, as
published under Circular 41/22), loan groups 1–5, total loans, equity, total
assets, net profit, shares outstanding; unambiguous period keys (year, quarter,
consolidated/separate, audited flag) and publication dates; a licence covering
display to end users. Plug-in point: one class implementing `FinancialsProvider`.
