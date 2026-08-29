# Phase 05 — traded_value suy diễn: báo cáo đo lường

**Ngày:** 2026-08-28 · **Plan:** `260828-2126-price-basis-and-signal-field-spine`
**Session:** stock-massive-f0 · **DB:** container `stockmassive-db-1` (ghim host qua `docker exec`, theo R6)

## Việc đã làm

Suy `total_value_vnd = close × volume` tại seam dựng `SessionSnapshot`
(`signals/sessions.py::_as_snapshot` → `_traded_value`), không phải ở `bars.py`.
Một chỗ suy, hai tầng cùng thấy:

| Tầng tiêu thụ | Vị trí | Field phục vụ |
|---|---|---|
| `Bar.total_value_vnd` | `bars.py:1040` | `adtv_vnd`, `amihud_illiq` |
| `SessionSnapshot` trực tiếp | `bars.py:1152` `_adtv_standing`, `:1195` `_peer_average` | `adtv_percentile` (qua `WindowHealth.adtv`) |

Suy ở `bars.py` sẽ để tầng thứ hai rỗng và khoá `adtv_percentile` vào
`RANKING_UNAVAILABLE` vĩnh viễn — test `test_the_derived_money_reaches_the_gateways_own_standing`
giữ đúng luật này.

**`volume = 0` → `None`, không bao giờ `0.0`.** `average_over_sessions` từ chối cửa
sổ có `None` và cộng thẳng `0.0` vào trung bình, nên trả `0.0` sẽ vừa kéo ADTV
xuống theo tỉ lệ phiên chết vừa tắt câm chính refusal dựng ra để bắt việc đó.

## Bước 5 — bốn thống kê, đo trước khi Phase 08 xoá

**Ngưỡng dừng của phase: p95 > 25% thì dừng và đưa số cho user.**

Cửa sổ đúng đặc tả (30 mã declared, 60 phiên gần nhất, join theo local date):

| Mẫu | mean | median | **p95** | max |
|---|---|---|---|---|
| n=1.668 · 30 mã · 2026-06-02 → 2026-08-24 | 3,981% | 0,860% | **20,367%** | 52,977% |

→ **p95 = 20,37% < 25%. Cổng qua.** Khớp phép đo sớm ghi trong plan
(mean 4,014 · median 0,864 · p95 20,387 · max 52,977).

### Toàn vùng chồng lấn — số phải nêu, không phải số của cổng

| Mẫu | mean | median | p95 | max |
|---|---|---|---|---|
| n=35.175 · 30 mã · 2021-08-05 → 2026-08-24 | 26,468% | 24,865% | 56,708% | 69,171% |

Số này **không** phải mẫu của cổng, và nó không nói phép suy diễn sai. Tách theo
năm cho thấy đúng chữ ký điều chỉnh:

| Năm | n | median lệch **giá trị** | p95 lệch giá trị | median lệch **khối lượng** |
|---|---|---|---|---|
| 2021 | 2.860 | 51,04% | 63,99% | **0,000%** |
| 2022 | 6.972 | 44,31% | 62,60% | **0,000%** |
| 2023 | 6.972 | 35,47% | 55,02% | **0,000%** |
| 2024 | 7.000 | 24,99% | 51,85% | **0,000%** |
| 2025 | 6.959 | 11,17% | 49,97% | **0,000%** |
| 2026 | 4.412 | 1,57% | 22,22% | **0,000%** |

Hai nguồn khớp **tuyệt đối** về khối lượng ở mọi năm (median 0,000%), và lệch giá
trị giảm đơn điệu về hiện tại. Nên toàn bộ khoảng lệch là **một việc duy nhất**:
`bar_daily.close` đã điều chỉnh, còn `total_value_vnd` của FiinQuant là tiền danh
nghĩa lúc đó. Không có phần nào là bất đồng về việc gì đã giao dịch.

**Hệ quả đã ghi vào docstring `_traded_value`:** con số này dùng được cho ba field
đang đọc nó — cả ba trung bình 20 phiên gần nhất, cửa sổ ngắn tới mức thường
không chứa điều chỉnh nào. Nó **không** dùng được để so tiền giao dịch năm này với
năm khác; muốn thế cần giá danh nghĩa mà store không giữ.

## Đã khai là suy diễn ở đâu

- `sessions.py` — docstring module + `_traded_value` nêu cả ba khác biệt (một giá
  cho cả phiên · close đã điều chỉnh nhưng volume thì không · không tách được
  thoả thuận) kèm số đo trên.
- `registry.py` — `interpretation` của cả ba field nói rõ là ước lượng.
  `adtv_vnd`: "close × volume, sai nhất ở phiên biến động mạnh".
  `amihud_illiq`: "field ước lượng này tốn nhất, vì nó đánh trọng số đúng phiên
  mà một giá đóng cửa đại diện cho phiên tệ nhất".
  `adtv_percentile`: ước lượng áp đều cho cả mẫu nên ảnh hưởng vị trí ít hơn mức.
- `market_behavior.py` — docstring `adtv_money_reading` + `amihud_illiquidity_reading`.
- `Provenance.method_notes` — `studies/earnings_dislocation.py::METHOD_NOTES` đã có
  câu này sẵn (viết bởi session Signal Desk); không study nào khác đọc traded value.

`registry.py` là contract của field, và `interpretation` nằm trong digest sáu
thuộc tính của `registry_version()` — nên định danh registry đã đổi theo, tự động.

## Test

`tests/test_signal_registry.py::TestTradedMoneyIsDerivedRatherThanRefused` — 6 case:

| Case | Giữ luật gì |
|---|---|
| `test_the_money_is_the_close_times_the_shares` | số học, trên bar của gateway |
| `test_the_two_fields_that_read_a_bar_answer_with_a_number` | `adtv_vnd` + `amihud_illiq` ra số |
| `test_the_derived_money_reaches_the_gateways_own_standing` | `health.adtv is not None` — suy diễn tới tầng thứ hai |
| `test_the_percentile_answers_off_that_standing` | `adtv_percentile` ra số 0–100 |
| `test_a_session_that_did_not_trade_is_missing_rather_than_zero` | `volume=0 → None`, `TRADED_FIGURE_NOT_STORED` vẫn bắn |
| `test_amihud_steps_over_that_session_instead_of_refusing` | amihud tự vệ mẫu số, `zero_volume_days ≥ 1` |

## Success Criteria

- [x] Ba field `liquidity_profile` trả số từ `bar_daily`
- [x] `health.adtv is not None` trên fixture
- [x] Phiên `volume = 0` cho `None`, refusal `traded_figure_not_stored` vẫn bắn
- [x] Số suy diễn khai là suy diễn ở contract và `Provenance`
- [x] Bốn thống kê ghi vào phase report **trước** Phase 08
- [x] `make test` xanh — 1390 passed

## Truy vấn dùng để đo

```sql
-- cửa sổ 60 phiên (mẫu của cổng)
WITH days AS (SELECT DISTINCT trading_day FROM bar_daily
              WHERE series='equity' AND trading_day <= '2026-08-24'
              ORDER BY trading_day DESC LIMIT 60),
f AS (SELECT symbol, (effective_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date d,
             (payload->>'total_value_vnd')::numeric tv
      FROM provider_snapshots
      WHERE source='fiinquant' AND capability='market'
        AND payload->>'total_value_vnd' IS NOT NULL
        AND symbol IN (<30 mã declared>)),
j AS (SELECT abs(b.close*b.volume - f.tv)/f.tv*100.0 err_pct
      FROM f JOIN days ON days.trading_day=f.d
      JOIN bar_daily b ON b.symbol=f.symbol AND b.trading_day=f.d AND b.series='equity'
      WHERE f.tv>0 AND b.volume>0 AND b.close IS NOT NULL)
SELECT avg(err_pct), percentile_cont(0.5) WITHIN GROUP (ORDER BY err_pct),
       percentile_cont(0.95) WITHIN GROUP (ORDER BY err_pct), max(err_pct) FROM j;
```
