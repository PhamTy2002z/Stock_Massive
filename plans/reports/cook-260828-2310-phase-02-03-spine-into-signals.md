# Phase 02 + 03 — lịch giao dịch và gateway signals chuyển sang `bar_daily`

Plan: `plans/260828-2126-price-basis-and-signal-field-spine/`
Nhánh: `feat/study-canvas-runtime` · 2026-08-28
Trước đó: [Phase 01](./cook-260828-2237-phase-01-green-baseline.md)

## Kết quả đo trên dữ liệu thật

`make test`: **1347 passed**, 0 failed (mốc Phase 01: 1305).

Probe chạy **trong container** `stockmassive-api-1` (R6 — xem §Bẫy hai Postgres),
`serve_field` cho STB, `serve_cross_section` cho 30 mã declared, `end =
latest_trading_day() = 2026-08-27`:

| | Số | Chi tiết |
|---|---|---|
| **Trả số** | **19** | 17 field một mã + `factor_percentiles.roe_percentile` (ranked 30/30) + `momentum_rank.percentile_12_2` (ranked 28/30) |
| Từ chối, đúng input thiếu | 11 | xem bảng dưới |

Trước Phase 03, cả 30 field đều từ chối `unadjustable_price_basis` trên dữ liệu
thật, vì mọi dòng `bar_daily` là `adjusted_at_source`.

| Field | Mã từ chối | Ai mở |
|---|---|---|
| `band_pressure.limit_days_in_window` | `unadjustable_price_basis` | **Phase 06** — cổng basis thứ hai (`price_band._basis_of_the_pair`) |
| `liquidity_profile.adtv_vnd` | `traded_figure_not_stored` | **Phase 05** |
| `liquidity_profile.amihud_illiq` | `no_traded_sessions` | **Phase 05** |
| `liquidity_profile.adtv_percentile` | `ranking_unavailable` | **Phase 05** |
| `foreign_flow_pressure.*` (3) | `foreign_flow_not_stored` | vĩnh viễn |
| `factor_percentiles.{earnings_yield, book_yield, size}_percentile` | `market_cap_absent` (30/30 mã) | vĩnh viễn |
| `relative_strength.beta_vs_market_index` | `unavailable` | estimator chưa viết |

**`company_profile.foreign_room_pct` TRẢ SỐ** — 63,75 cho STB. Plan liệt nó vào
nhóm ⛔ `foreign_room_not_stored`; sai. Room đọc capability `reference`, mà
`reference` có **220 dòng của vnstock**, không phải FiinQuant. Phase 08 xoá
FiinQuant không đụng nó. Bảng 30 field của plan phải sửa: **8 field chết vĩnh
viễn, không phải 9** — và tổng của bảng đó hiện là **31**, không phải 30
(`momentum_rank` bị đếm hai lần: nó là cross-sectional, không nằm trong nhóm 17).

## Quyết định đã áp

### Lịch giao dịch (Phase 02)

`trading_day.py` đọc `bar_daily`, **chỉ `series='index'`**. Đo trước khi chọn:
VNINDEX và Universe-30 cho **cùng 3.991 phiên, 0 ngày lệch hai chiều**; VNINDEX
thắng vì một mã một phiên, không có bài toán phủ không đều (845/1.522 mã có dòng
ở phiên mới nhất, nên phép **hợp** trên equity tuyên phiên cho mã không có lịch sử).

**Phiên đã đóng đo bằng `observed_at`, không bằng đồng hồ.** `vnstock_daily` ghi
phiên đang chạy với những gì provider có; số của nó không tự khai điều đó.
Điều kiện: `observed_at >= trading_day 15:00 VN`. Có test khẳng định hai lần gọi
`latest_trading_day` hai bên mốc 15:00 trong một Turn không thể khác nhau.

Phép thử "đã đóng" **chỉ áp cho `latest_trading_day`**, viết rõ lý do trong
docstring: đó là chỗ duy nhất một cửa sổ được *chọn* điểm cuối, nên là chỗ duy
nhất phiên dở dang lọt vào; hai hàm còn lại đi lùi từ một ngày caller đã nêu.

`market_generation` **đã xoá** cùng test — nó khoá một signal cache đã bị rip.
`trading_days_between` **giữ**: 0 caller trong `src/` nhưng là câu hỏi thứ ba tự
nhiên của module lịch, có test, và Phase 05–07 sẽ cần.

### Giữ `bar_daily` tươi (R2)

`make backfill-daily SCOPE=index|declared|market`, cron ngoài app — không dựng
scheduler mới. Run **exit non-zero khi một mã lỗi HOẶC khi một lượt sạch vẫn để
spine cũ**: `spine_freshness()` trả `(latest_session, last_observed_at,
age_days)` và phân biệt "chưa có phiên nào" với "cũ N ngày". Đó là R2 — job là
thứ duy nhất nuôi lịch, nên một lượt chạy im lặng thành công là cách phiên mới
nhất đóng băng trong khi mọi câu trả lời vẫn kèm ngày.

**Chốt chặn ingest:** `vnstock_daily` từ chối phiên tương lai hoặc cuối tuần
**trước khi ghi**, vì `bar_daily` không có CHECK constraint nào trên
`trading_day` và phép kiểm response chỉ đọc **tên cột**. Một dòng dị dạng dịch
cửa sổ của cả thị trường. Hai fixture sinh "ngày liên tiếp" đã sửa thành ngày
làm việc — chúng đang khẳng định một response sàn không thể tạo ra.

### Luật basis mới (Phase 03)

`_basis_of` ba nhánh, viết thành câu trong docstring, có test cho cả ba:

| Cửa sổ | Phán quyết |
|---|---|
| toàn `raw` | phục vụ, `_factors` chạy |
| trộn hai basis | `MIXED_PRICE_BASIS` |
| toàn `adjusted_at_source` | **phục vụ**, `_factors` **không** chạy |

Cơ sở viết ra: provider restate cả chuỗi về một mốc, nên cửa sổ **nhất quán nội
tại**, và mọi tỉ số một field lấy trên đó không đổi theo hằng số tỉ lệ. Có test
chứng minh trực tiếp — cùng window nhân 2,5 cho `gk_variance_robust_z` **cùng một
số**, đo qua chính gateway chứ không qua bar dựng tay, để một thay đổi sau này
làm field đọc **mức giá** sẽ vỡ ở đó.

`_adjusts_from_actions()` tách riêng khỏi `_basis_of` và có test chuyên: cùng một
ex-date đã lưu, window `raw` cho `adjustment.applied = True`, window `adjusted`
cho `False`. Đây là lưới an toàn cho R1 (điều chỉnh hai lần, sai im lặng).

`UNADJUSTABLE_PRICE_BASIS` **thu hẹp**, không xoá: nó không còn do gateway phát,
chỉ còn `price_band._basis_of_the_pair`. Nghĩa mới ghi trong `issues.py`: một
*câu hỏi* không trả lời được (giá công bố), không phải một *cửa sổ* không đọc
được. Đúng cảnh báo của plan — sau Phase 03, `limit_lock_days = 0` khắp nơi và
`band_pressure` từ chối; đó là cổng thứ hai còn đóng, Phase 06.

`Bar.raw_close` giữ nguyên công thức, docstring sửa: nó là giá sàn công bố **chỉ
trên window raw**. Không nhân ngược hệ số nội bộ vào giá provider — hai hệ số
không bảo đảm bằng nhau, làm thế là bịa ra giá thứ ba.

### R4 — `_session_low`

Hỏng hai lớp: order theo `ProviderSnapshot.written_at` (cột không tồn tại →
`AttributeError`) **và** dựng cửa sổ ngày bằng UTC trong khi phiên đóng dấu nửa
đêm VN. Vá bằng cách gọi lại chính `sessions_in_range` — một reader duy nhất, cột
`Date` không có bounds để dựng và không có zone để sai.

**Hàm này trước đây không có test nào**, đó là lý do một tham chiếu tới cột không
tồn tại sống sót. Thêm `tests/test_corporate_actions.py` — file test đầu tiên cho
module đó: 7 case, 4 cho `_session_low`, 3 cho `confirm_ex_date`.

### R7 — nhánh STORE của `check_price_claim`, dựng lại có điều kiện

Quyết định đã chốt với user. Cơ chế: so giá công bố với `[low, high]` **chỉ khi
không có corporate action ex-date nào giữa phiên đó và phiên mới nhất đã lưu** —
khi đó provider chưa rescale gì, nên giá lưu **chính là** giá sàn in ra. Có
ex-date ở giữa → `unverified`, kèm `rescaledSince` liệt kê đúng những ngày đó.

**Tiền đề đo được, và nó đúng gần như tuyệt đối.** 30 mã declared, từ 2026-05-01,
join theo local date:

| Có ex-date sau phiên? | Cặp so | Khớp tuyệt đối | Lệch tối đa |
|---|---|---|---|
| **Không** | 1.169 | **100,00 %** | **0,000 %** |
| Có | 1.087 | 18,22 % | 51,853 % |

Con số "60,59% khớp" của plan là hai nhóm này trộn lại. Tách theo đúng điều kiện
ex-date thì phép so hoặc chính xác tuyệt đối, hoặc phải từ chối.

Dung sai khai tường minh: `STORE_TOLERANCE = 0.1%`, đi trong payload dưới
`tolerancePct`. Hôm nay nó hấp thụ **0** (giá equity vào theo nghìn đồng, scale
một lần lúc ingest, không mất số lẻ); nó tồn tại vì một phép so giữa hai nguồn mà
không khai dung sai là phép so có dung sai không ai chọn.

Nhánh BAND **vẫn mất** — band là phần trăm của giá tham chiếu **công bố**, và giá
rebased không phải số đó. Ghi ra chứ không giấu.

### Golden test — dung sai, theo quyết định đã chốt

Trong suite: bất biến tỉ lệ (đã nêu trên). Ngoài suite: lệch thật giữa FiinQuant
`raw` và `bar_daily` `adjusted` trên 6 mã nhiều corporate action nhất, toàn vùng
chồng lấn 2021-08 → 2026-08:

| Mã | Cặp so | Khớp tuyệt đối | Lệch tối đa | Lệch trung vị |
|---|---|---|---|---|
| BID | 1.254 | 0,4 % | 46,91 % | 24,39 % |
| MBB | 1.259 | 0,7 % | 63,87 % | 48,84 % |
| MCH | 1.251 | 0,8 % | 54,96 % | 52,26 % |
| SHB | 1.253 | 7,8 % | 56,80 % | 27,48 % |
| SSI | 1.255 | 0,4 % | 67,00 % | 44,57 % |
| TCX | 8 | 100,0 % | 0,00 % | 0,000 % |

Chữ ký adjustment tích luỹ, đúng như plan mô tả. **Dung sai tuyệt đối bằng 0 là
bất khả thi** giữa hai phương pháp adjust — nhưng nó cũng không phải điều cần đo:
17 field OHLCV là tỉ số, và test bất biến tỉ lệ chứng minh chúng không đổi. Field
tính theo **mức** VND — `indicator_pack.macd_12_26_vnd` — **đổi**, và đổi đúng
theo hệ số; khai rõ ở đây.

## Bẫy hai Postgres (R6) — đã đụng phải

`localhost:5432` từ **host** trỏ vào Postgres brew, có schema `bar_daily` nhưng
**0 dòng**. Dữ liệu thật ở container `stockmassive-db-1`. Đo:

```
localhost   bar_daily rows = 0   server ::1/128
127.0.0.1   bar_daily rows = 0   server 127.0.0.1/32
container   bar_daily rows = 813.076
```

Hệ quả cụ thể trong phase này: hai test CLI của `backfill_daily` phải
monkeypatch `spine_freshness` thay vì dựa vào DB test — chúng đang mô tả trạng
thái spine, không đo nó. Mọi probe dữ liệu thật chạy bằng
`docker exec -w /code -e PYTHONPATH=/code stockmassive-api-1`.

## Ba thứ dọn thêm, có lý do

1. **`providers/store.py::resolve_sessions` đã xoá.** Nó chọn một trong hai bản
   sao của một phiên do hai source ghi; `bar_daily` khoá `(symbol, trading_day)`,
   không còn gì để chọn. `SNAPSHOT_MODEL_BY_CAPABILITY` giữ — `sessions.py` vẫn
   phải quyết một dòng thành `MarketSnapshot` hay `MarketIndexSnapshot`.
2. **`stocks/intraday/__init__.py` bỏ re-export.** `trading_day` nhập
   `SESSION_SETTLED_AT` từ `intraday.reads`, và package `__init__` import
   `ingest` → kéo **pandas + vnstock** vào sau mọi reader của `trading_day`, tức
   toàn bộ đường phục vụ. Không caller nào dùng các tên re-export (mọi chỗ đều
   import submodule theo tên), nên bỏ là đủ. Đo lại sau khi sửa: vnstock **không
   còn** trên đường `signals/`.
3. **`tests/test_price_band.py::write_session`** giờ ghi `BarDaily` và **cũng
   đánh dấu phiên trên lịch** (một dòng VNINDEX). Không có nó thì mọi anchor
   biến mất, vì lịch là series index. Trong production VNINDEX do scope backfill
   riêng lấp; một fixture chỉ ghi dòng equity là đang mô tả ngày thị trường không
   mở.

Trong `write_session`, `basis` **khai tường minh** thay vì suy từ `source`: ở
`bar_daily` nó không suy được — bảng có một writer và basis là một cột. Mặc định
`raw`, vì đó vẫn là basis duy nhất máy band đo được cho tới Phase 06.

## Hai chỗ hình dạng store cũ không còn, test viết lại chứ không vá

- `test_a_session_without_a_range...` — `bar_daily` type high/low NOT NULL, nên
  cách duy nhất một phiên không có range là một giá trị **không phải giá**.
  Reader map giá ≤ 0 thành absent đúng vì lý do đó (contract chặn mọi giá > 0,
  một số 0 để nguyên sẽ fail validation và kéo cả window theo). Test viết lại
  quanh đường đó.
- `TestWhichStoredSessionIsRead` — "Main Source thắng khi hai source cùng giữ một
  phiên" không còn là một luật, nó là **thuộc tính của khoá chính**. Viết lại
  thành: provider restate một phiên thì **thay** dòng cũ (assert đúng 1 dòng), và
  band vẫn đến từ regime chứ không từ dòng lưu (`bar_daily` không có cột
  ceiling/floor nào để lấy).

## Success Criteria — Phase 02

- [x] `latest_trading_day()` trả phiên đã đóng mới nhất của `series='index'`
- [x] Mọi truy vấn lọc `series`
- [x] Hai lần gọi qua mốc 15:00 trong một Turn không thể khác nhau (có test)
- [x] Phiên chưa đóng không bao giờ được trả, kiểm bằng `observed_at`
- [x] `trading_days_before` không độn ngày không có phiên
- [x] Đúng một đường giữ `bar_daily` tươi, chạy được, và **báo khi thất bại im lặng**
- [x] `make test` xanh; năm caller trong `src/` không đổi chữ ký
- [x] `market_generation` đã xoá cùng test

## Success Criteria — Phase 03

- [x] Luật basis mới có câu trong docstring và test cho cả ba nhánh
- [x] Không module nào trong `signals/` đọc `provider_snapshots` capability MARKET
      (còn `fundamental` và `reference` — ngoài phạm vi plan này)
- [x] `_factors` không chạy trên window `adjusted_at_source` (test hai chiều)
- [x] Golden test: bất biến tỉ lệ trong suite + lệch thật đo và khai ở trên
- [x] `_session_low` chạy được **và có test**; không còn UTC dựng cửa sổ ngày
- [x] R7 đã đưa lên thành số và **đã giải**, không phải ghi chú
- [x] `make test` + `tests/studies/` xanh
- [ ] **Cả 20 field PRICE trả số** — 19/30 field trả số hôm nay. Ba field
      liquidity chờ Phase 05 (`total_value_vnd`), `band_pressure` chờ Phase 06
      (cổng basis thứ hai). Đây là thứ tự của chính plan, không phải thiếu sót
      của Phase 03: `bar_daily` **không có cột traded value** và `models.py` nói
      thẳng điều đó.

## Việc phải sửa trong plan

1. Bảng "30 Signal Field" tổng **31** — `momentum_rank.percentile_12_2` bị tính
   vào nhóm 17 trong khi nó là cross-sectional.
2. `company_profile.foreign_room_pct` **không** chết: nó đọc capability
   `reference`, nguồn vnstock, 220 dòng. "22 sống · 8 từ chối" nên là
   **23 sống · 7 từ chối** sau Phase 06.
3. Success criterion của Phase 04 "`adtv_percentile` trả số" không đạt được ở
   Phase 04 — nó cần Phase 05. Đọc đúng là "projection không còn là lý do từ chối".

## Câu hỏi chưa giải quyết

1. Ai chạy cron `make backfill-daily`? Target và exit code đã có; lịch cron thì
   chưa ai cài. Đây là quyết định vận hành, không phải code.
2. Nhánh BAND của `check_price_claim` mất vĩnh viễn. Chấp nhận, hay Phase 06
   (lưới bước giá) mở lại được nó cùng lúc mở `band_pressure`?
