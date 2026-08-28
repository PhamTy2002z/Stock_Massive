# Phase 08a — market-wide daily price spine

- Phase: `phase-08-market-wide-daily-spine.md` (nửa 08a)
- Plan: `plans/260826-2158-study-artifact-canvas/`
- Status: completed (backend only, no serving change)
- Suite: `make test` → **1118 passed** (baseline 1060; +58 mới)

## Files

| File | Δ |
|---|---|
| `apps/api/alembic/versions/d4a71c9e5b82_add_the_market_wide_daily_bars.py` | mới, 60 dòng, head `c2e94a7b1f30` → `d4a71c9e5b82` |
| `apps/api/src/stocks/models.py` | +58 (`BarDaily`, không đụng gì khác) |
| `apps/api/src/stocks/providers/vnstock_daily.py` | mới, ~330 dòng |
| `apps/api/src/stocks/backfill_daily.py` | mới, ~290 dòng |
| `apps/api/src/stocks/listing_roster.py` | +~290 (writer + `listed_symbols`; reader `identity_of` nguyên văn) |
| `apps/api/src/stocks/universe.py` | +~60 (`Universe.market`, `with_market`, `build_universe(..., with_market=False)`) |
| `apps/api/tests/stocks/daily/{__init__,fixtures,test_vnstock_daily,test_backfill_daily}.py` | mới, 34 test |
| `apps/api/tests/stocks/test_listing_roster.py` | mới, 16 test |
| `apps/api/tests/stocks/test_universe_market.py` | mới, 8 test |

Không đụng: `signals/*`, `realtime/*`, `providers/{contracts,normalize,store}.py`,
`agent/*`, `studies/*`, `apps/web/*`, revision alembic đã commit.

## Acceptance

1. **`bar_daily`** đã tạo trên DB Docker, đúng cột spec liệt kê; `series` và
   `price_basis` là cột thật. `price_basis` ghi `adjusted_at_source` từ hằng
   `vnstock_daily.PRICE_BASIS`, không hardcode ở chỗ đọc. Xác minh `\d bar_daily`
   + query: 15 dòng VNINDEX đều `adjusted_at_source`.
2. **Idempotent.** `_upsert` dedup `(symbol, trading_day)` **trước** khi dựng
   statement (test: `test_a_session_the_provider_repeats_does_not_abort_the_
   transaction` — sau đó session vẫn dùng được, đúng bài `CardinalityViolation`).
   Chạy CLI lần hai: `skipped=1 rows=0`, row count không đổi.
3. **Paging.** `end = min(trading_day nhận được) - 1 ngày`, dừng khi call rỗng,
   khi đủ depth, hoặc khi một page **không lùi được nữa** (đo được: provider trả
   cả phiên ngoài `[start, end]`, nên "page rỗng" một mình không đủ để dừng).
   `MAX_PAGES = 6` là chốt cuối.
4. **Job không có checkpoint.** Tiến độ suy từ store: `count(trading_day) ≥
   sessions` **và** `max(trading_day) ≥` phiên mới nhất mà chính `bar_daily` đang
   giữ cho series đó. Một mã lỗi → log + `SymbolReport.error`, run tiếp; mỗi mã
   một session/một commit riêng nên transaction abort chỉ mất một mã. CLI:
   `python -m src.stocks.backfill_daily --scope declared|market|index
   [--sessions N]`, exit 1 nếu có mã lỗi.
5. **Roster writer.** `refresh_roster(session)` + `ListingRosterStore.write`.
   `Exchange.parse` lo HSX→HOSE; `DELISTED` giữ dòng với `is_listed=False` và
   **giữ nguyên sàn cũ**; ICB nullable là dòng bình thường; ICB read fail chỉ mất
   tên ngành, không mất refresh.
6. **Universe hai nửa.** `Universe.market` là tập thứ ba, **không** vào
   `symbols`, nên `contains()` và do đó `get_field` không đổi.
   `test_get_field_refuses_a_symbol_that_is_only_in_the_market_half` gọi thẳng
   `SignalTools.get_field` và khẳng định `error == "cannot_read"` +
   `"outside the Universe"` — đúng mã refusal cũ.
7. **Offline.** Mọi test tiêm `fetch` / `fetch_listings` / `fetch_industries`
   hoặc monkeypatch `Quote` + `safe_vnstock_call`. Không test nào ra mạng
   (`pytest.ini` vẫn loại marker `network`; không test mới nào cần nó).
8. `make test` 1118 passed. Không lỗi type/compile mới (`py_compile` sạch trên
   cả 5 file src; dòng ≤ 88 ký tự trừ dòng dữ liệu CSV trong fixture).
9. **Không đụng đường đọc của signals.** `build_universe(session)` vẫn trả đúng
   nửa declared (`with_market` default `False`); `provider_snapshots`,
   `signals/bars.py`, `trading_day` không bị chạm. 1060 test cũ vẫn xanh.

## Quyết định phải ghi lại

- **`safe_vnstock_call` làm "cửa sổ không có dữ liệu" và "provider chết" giống
  nhau.** Đo 2026-08-27: `Quote('STB').history(start='1995-01-01', ...)` raise
  `RetryError[ValueError('Không tìm thấy dữ liệu...')]` bên trong, và wrapper
  nuốt mọi exception thành `None`. Nên `fetch_daily` raise, còn **vòng paging
  quyết nghĩa**: page đầu lỗi = mã lỗi (báo lên job); page sau lỗi = hết lịch sử
  (dừng, **giữ** những page đã ghi). Nếu không tách như vậy, mọi mã mới lên sàn
  mà hỏi 400 phiên sẽ rollback cả phần đã ghi.
- **Phiên mới nhất tham chiếu là của chính `bar_daily`**, không dùng
  `trading_day.latest_trading_day` — cái đó suy từ capability `market` của
  `provider_snapshots`, tức đúng câu hỏi basis mà 08b mới quyết. Không nối bảng
  mới vào quyết định cũ.
- **Roster: ba tập, không hai.** `entries` (share có sàn) · `shares` (mọi mã
  type STOCK, kể cả `DELISTED`) · `mentioned` (mọi mã response nêu). Cần cả ba
  vì response chứa 3.586 dòng gồm CW/BOND/FU/ETF: một mã đã lưu mà thiếu trong
  `entries` có ba lý do và chỉ hai là delisting. Mã chỉ được nêu dưới type khác
  (ETF `E1VFVN30`) **giữ nguyên trạng thái** — refresh này không phát biểu gì về
  nó. Mã `DELISTED` mà store **chưa** có dòng thì bỏ qua, không tạo dòng mới:
  không có sàn để ghi và ở đây chưa từng thấy nó niêm yết.
- **Roster hiện có 1.751 dòng đều `is_listed=true`** (bản cũ nạp từ
  `all_symbols()`). Refresh đầu tiên sẽ chuyển **228 mã `DELISTED`** thành
  `is_listed=false` — đúng ngữ nghĩa, và `envelope.py` chỉ đọc `identity_of` cho
  30 mã declared nên không ảnh hưởng.
- **Phiên đang chạy vẫn được ghi.** Job chạy giữa giờ ghi cả phiên hôm nay với
  số dở dang; lần chạy sau upsert đè bằng số đã đóng. Không thêm bộ lọc
  "phiên đã đóng" vì spec không yêu cầu và nó sẽ đổi định nghĩa depth; đã ghi
  thẳng vào docstring module để người đọc `bar_daily` biết mà tự chọn.

## Đã chạy thật

- `alembic upgrade head` trong container: `c2e94a7b1f30 → d4a71c9e5b82`, OK.
- Smoke CLI **một call mạng**: `--scope index --sessions 5` → `rows_written=15
  sessions_stored=15 calls=1 span=2026-08-07..2026-08-27`, giá **không scale**
  (max close 1831.56 điểm). Chạy lại → `skipped=1 rows=0`.
- **Chưa chạy** backfill `declared` / `market` (1.523 call) — để orchestrator.
- 15 dòng VNINDEX thật đang nằm trong `bar_daily`; run `index` thật sẽ nối sâu
  thêm, không cần dọn.

## Kích thước DB

| | trước | sau (hiện tại) |
|---|---|---|
| `bar_daily` | không có | 56 kB / 15 dòng |
| DB `stockmassive` | 110 MB | 110 MB |

Ước lượng khi đầy: `bar_intraday_15m` đang 3.985 dòng / 680 kB ≈ 175 B/dòng với
một index; `bar_daily` có hai index nên ~200 B/dòng → **~600k dòng ≈ 110–130 MB**,
tức DB xấp xỉ gấp đôi. Nằm trong dự đoán của spec.

## Chưa đạt (thuộc 08b, nêu thẳng)

- 71.773 dòng fiinquant **chưa xoá** — xoá bây giờ là mọi window signals thành
  `UNADJUSTABLE_PRICE_BASIS`.
- `valuation` từ vnstock **chưa backfill** (vẫn 0 dòng vnstock).
- **Acceptance #6 của `plan.md` vì thế chưa done.**

## Việc còn lại của orchestrator

1. `python -m src.stocks.backfill_daily --scope declared` (30 mã × ~1–2 call).
2. `--scope index` (nối sâu VNINDEX tới 2.000 phiên).
3. Trước `--scope market`: chạy `refresh_roster(session)` một lần để roster
   phản ánh 1.523 mã STOCK đang niêm yết (job **không** tự refresh — nó chỉ
   log cảnh báo nếu roster rỗng). Rồi `--scope market` chạy nền, một luồng.
4. Cập nhật trạng thái phase qua `ak plan` (tôi không đổi ô status).

## Unresolved

- `make lint` ở `apps/api` **fail sẵn từ trước**: target hardcode `python`
  (không có trên PATH) trong khi các target khác dùng `$(PYTHON)` = `.venv`. Lỗi
  có trước phase này; tôi không sửa vì Makefile không thuộc file ownership.
- Ai gọi `refresh_roster` theo định kỳ? 08a chỉ có hàm, không có scheduler —
  spec không yêu cầu job cho nó.
- `bar_daily` chưa có ai đọc. Phase 10 (screener) sẽ là consumer đầu tiên và là
  chỗ quyết "phiên đang chạy có được tính hay không".
