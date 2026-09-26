# P1 — statements adapter + calculator

## Findings that shape it (probed 2026-09-26, vnstock community in the api container)
- KBS `ratio` (CSTC) is current (to Q2/2026) and has ROE (quarter and trailing
  4Q), ROA, P/B, P/E, EPS, BVPS, NIM, CIR, LDR for banks. **No NPL, no CAR.**
- vnstock's KBS parser mislabels periods: it sorts `Head` by `ID`, but IDs repeat
  (1,2,1,2,…) and `Value{i}` follows the original `Head` order. The raw payload
  itself carries several heads for one quarter (three "2025 Q4" entries) with
  different values — those periods are ambiguous at the source.
- KBS balance sheet for banks is empty. VCI's ratio series *does* carry NPL by
  quarter to Q2/2026 and CAR in the quarters a bank disclosed it (0 otherwise);
  vnstock only returned 2018 because its parser keeps the first four rows of an
  oldest-first series. Read raw, it is the free NPL source.

## Changes
1. `tools/financials.py` — `FinancialsProvider` protocol (the adapter seam),
   `KbsFinancials` and `VciFinancials` (dev/test only, same `personal_internal`
   + flag gate as the market read), read together by one tool. Pairs `Value{i}` with `Head[i-1]`, drops any period that
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

## Gate (result, 2026-09-26)
- ROE, P/B: 5 banks from tools; P/B recomputed by `calculate` in a live Turn.
  10 samples P/B×BVPS vs quarter-end close: 7 exact, 3 off by a constant factor
  explained by dividend-adjusted closes (P/E×EPS = P/B×BVPS holds in all).
- NPL: 5 banks from Vietcap to Q2/2026. Cross-checked: VCB Q2/2026 0,61 %
  (3 independent pages), STB Q4/2025 6,41 % (markettimes); TCB Q2/2026 1,08 %
  vs one article's 1,15 % — unresolved (likely consolidated vs separate).
- CAR: only where disclosed — STB 9,69 %, VCB 12,01 %, ACB 10,97 % at Q2/2025;
  none in the last five quarters for TCB, MBB. The tool says so. Complete CAR
  needs a paid source (below) or the banks' own disclosures via `fetch_url`.

## What a paid provider must supply to replace KBS
Per bank per quarter: NPL (nợ nhóm 3–5 / tổng dư nợ), CAR (Basel II/III, as
published under Circular 41/22), loan groups 1–5, total loans, equity, total
assets, net profit, shares outstanding; unambiguous period keys (year, quarter,
consolidated/separate, audited flag) and publication dates; a licence covering
display to end users. Plug-in point: one class implementing `FinancialsProvider`.
