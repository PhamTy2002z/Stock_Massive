# P3 — company events, news by ticker, natural-language screener

## Constraints found (2026-09-26)
- vnstock guest quota: 20 requests/min per process, and `vnai` exits the
  process on breach → every call goes through `tools/vnstock_provider.py`
  (limiter at 16/min, `SystemExit` → `rate_limited`). Done in `8ee5784`.
- Vietcap's `trading.vietcap.com.vn` host times out from this network; its
  company events and news endpoints answer. KB's price board answers for many
  symbols in one request (price, change, volume, value, foreign flow).
- No screener in this vnstock build.

## Changes
1. `tools/company.py` — `get_company_events(symbol)` (AGM, dividends with
   ex-right/record/pay dates, insider deals) and `get_company_news(symbol)`
   (titles by publication date), both Vietcap, one dated line per item.
2. `tools/screener.py` — `screen_stocks(universe, filters, sort_by, limit)`.
   Universe: an index group (VN30, VN100, HNX30…), an ICB industry name, or an
   explicit ticker list (≤ 60). Market fields from one price-board request per
   50 tickers; fundamental fields (P/B, P/E, ROE TTM, NPL) from Vietcap ratios,
   cached per ticker for 12 h and fetched only within the limiter's room — the
   result names the tickers it could not cover yet instead of guessing.
3. Figure check: news lines older than 30 days are `nguồn cũ`; a multi-ticker
   source (screener) grounds figures only for the tickers it lists.
4. Prompt: when to use each tool.

## Gate
The three features answer on the UI through the same figure check, and the
P0 questions re-run clean (regression).
