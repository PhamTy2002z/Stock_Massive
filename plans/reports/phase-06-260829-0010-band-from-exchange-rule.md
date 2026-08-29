# Phase 06 — band_pressure trên lưới bước giá: báo cáo

**Ngày:** 2026-08-29 · **Session:** stock-massive-f0
**DB đo:** container `stockmassive-db-1` (ghim host qua `docker exec`, theo R6)

## Cổng thứ hai đã mở — và nó từng tắt câm cái gì

`_basis_of_the_pair` (`price_band.py`) từ chối cặp phiên toàn `adjusted_at_source`.
Mọi dòng `bar_daily` đều là basis đó, nên nó từ chối **mọi phiên của mọi mã** — và
từ chối **không tiếng động**, vì phán quyết bị giữ lại thành `INDETERMINATE`, thứ
`Bar.limit_locked` đọc là *không khoá*. Dây chuyền hậu quả, đo được:

| Mắt | Trước | Sau |
|---|---|---|
| `Bar.limit_locked` | `False` mọi bar | đúng theo phán quyết |
| `BarFrame.without_limit_locks()` | không loại gì | loại đúng phiên trần |
| `WindowHealth.limit_lock_days` | 0 | > 0 trên fixture có phiên trần |
| baseline volatility | tính trên cửa sổ **còn nguyên** phiên `H=L=O=C` — trái docstring "none may skip" | đúng docstring |

Không exception, không refusal, không test đỏ. Đây là lý do test của phase này
nhắm vào **hệ quả** (`limit_lock_days`, `without_limit_locks()`) chứ không nhắm
vào mã refusal: một test chỉ kiểm mã refusal sẽ xanh suốt thời gian hành vi sai.

## Luật mới: nhãn không quyết nữa, giá quyết

| Điều kiện | Kết quả |
|---|---|
| Hai basis khác nhau (target vs anchor) | `MIXED_PRICE_BASIS` — **giữ nguyên**, tỷ số giữa giá raw và giá đã điều chỉnh không phải một bước giá |
| Cùng một basis (kể cả toàn adjusted) | đi tiếp, sang phép thử lưới |
| Bất kỳ trong ba giá — anchor, high, low — lệch lưới bước giá | `PRICE_OFF_TICK_GRID` (mã mới) |
| Sàn UPCOM | `ANCHOR_NOT_STORED` **vĩnh viễn** |

**Ba giá, không phải "close của hai phiên" như phase file viết.** Phase file nói
kiểm close phiên đích và close phiên neo. Nhưng `measure_band` **không dùng
`target.last_price`** ở đâu cả — phán quyết là `high == low == limits.ceiling`, và
`limits` suy từ `anchor.last_price`. Nên kiểm close của phiên đích là kiểm một giá
không tham gia số học. Đã kiểm đúng **ba giá số học thật sự dùng**: `anchor_price`,
`high`, `low`. Chặt hơn đề xuất gốc và phủ đúng chỗ hỏng.

**Đã khai là điều kiện cần-không-đủ** trong docstring `_off_tick_grid`: một giá bị
rebase vẫn có thể tình cờ rơi đúng lưới (hệ số đúng 2 trên giá đã là bội của bước).
Viết ra để người sau không dựng chứng minh lên trên nó.

## Bước 7 — tỉ lệ quyết được, đo trên DB thật

Từ 2026-07-01, phiên có khớp lệnh, đủ close/high/low:

| Sàn | Phiên | Mã | Lệch lưới | **Quyết được** |
|---|---|---|---|---|
| HOSE | 15.624 | 404 | 1.325 | **91,52%** |
| HNX | 8.125 | 288 | 867 | **89,33%** |
| UPCOM | 13.693 | 698 | 1.038 | **0%** — `anchor_not_stored`, lưới không liên quan |

30 mã declared (tập lane chat thật sự phục vụ), cùng cửa sổ:

| Sàn | Mã | Phiên | Lệch lưới | **Quyết được** |
|---|---|---|---|---|
| HOSE | **30/30** | 1.260 | 243 | **80,71%** |

**Cổng rủi ro của phase: "< 80% trên HOSE thì đưa số cho user".** HOSE toàn sàn
91,52% → qua. Tập 30 mã declared **80,71%** → qua, nhưng sát ngưỡng, nên nêu ra
đây thành số chứ không chôn vào docstring.

### Hai chỗ phase file/plan sai, đã sửa

1. **`MCH` không ở UPCOM.** Plan viết "UPCOM là 819/1.751 mã roster (47%), gồm MCH
   trong 30 mã declared". Roster split thì đúng (UPCOM 819 · HOSE 633 · HNX 299 =
   1.751), nhưng `MCH` là **HOSE**, và **cả 30 mã declared đều HOSE**. Nên lane
   chat **không gặp** ca UPCOM hôm nay. Đã sửa trong docstring `price_band.py`.
2. **Tỉ lệ lệch lưới HOSE 6,95% → 8,48%.** Plan đo **chỉ close**; phép đo này kiểm
   cả ba giá số học dùng, nên bắt được nhiều hơn. Cùng một dữ liệu, phép đo chặt hơn.

### Cổng nghiệm thu không dùng FiinQuant — xác nhận lại

Không so verdict với FiinQuant, đúng như phase file đã sửa: `ceiling_price` null ở
**36.504/36.528 = 99,93%** dòng. `price_band.py:10-12` đã ghi lý do (`_fetch_history`
truyền `band=None` cố ý). Cổng thay là tỉ lệ quyết được ở trên + fixture có phiên
trần.

## Đã tái dùng, không dựng lại

Phase file bản đầu định nối `listing_roster` vào đường dựng bar. **Không thêm truy
vấn nào**: `BandRegimeResolver`, `band_limits`, `tick_size`, `measure_band` neo vào
close phiên trước, và `BarPreparationContext._listed_exchanges` nạp roster theo lô
— tất cả đã có sẵn. `_off_tick_grid` chỉ đọc `regime.exchange` mà `measure_band`
đã cầm.

Phép thử "vắng ex-date" của bản đầu **không dùng**, đúng như phase file đã sửa:
`CorporateActionStore.save()` có 0 caller, bảng phủ 29/1.522 mã, nên "không có
dòng" bị đọc thành "không có ex-date" và luật sẽ tuyên mọi phiên quyết được.

## Thay đổi

| File | Thay đổi |
|---|---|
| `signals/issues.py` | `PRICE_OFF_TICK_GRID` mới (đặt sau `ANCHOR_MISSING`, trong nhóm band) |
| `signals/price_band.py` | `_basis_of_the_pair` mở cho cặp cùng basis · `_off_tick_grid` mới · `measure_band` gọi nó trước `band_limits` · docstring UPCOM vĩnh viễn |
| `alpha/reasons.py` | câu tiếng Anh cho mã mới |
| `apps/web/src/lib/signal-issues.ts` | câu tiếng Việt cho mã mới |
| `tests/test_price_band.py` | viết lại `test_an_adjusted_session_...` (test cũ tự khai chờ phase này) + 2 test mới |
| `tests/test_signal_registry.py` | `_on_tick` cho fixture + class `TestTheBandVerdictOnAnAdjustedWindow` (5 case) |

### Fixture từng viết giá không tồn tại trên thị trường

`store_quiet_history` làm tròn giá tới **0,1 đồng** (ví dụ 20.134,6đ). HOSE không
báo giá ở bước nào như thế — bước là 10/50/100 tuỳ mức giá. Việc này vô hình khi
phán quyết band do **cột basis** quyết, và hiện ra ngay khi nó do **giá** quyết:
59/61 phiên của fixture lệch lưới, nên `limit_lock_days` tụt 3 → 2 và một test
đang xanh chuyển đỏ.

Đã sửa **fixture**, không nới phép kiểm: `_on_tick` snap mọi giá về bước giá gần
nhất. Phép kiểm đúng, fixture sai. Mọi phiên fixture viết ra giờ là phiên có thể
đã giao dịch thật.

## Test — 8 case mới/viết lại

| Case | Giữ luật gì |
|---|---|
| `test_an_adjusted_session_still_on_the_grid_is_judged` | nhãn adjusted không còn chặn; 25.800 → ceiling 27.600, `LimitLock.CEILING` |
| `test_a_price_off_the_quoting_grid_is_refused_by_name` | giá rebase → `PRICE_OFF_TICK_GRID`, `limits is None` |
| `test_a_session_and_an_anchor_on_two_bases_is_still_a_seam` | `MIXED_PRICE_BASIS` không bị nới theo |
| `test_a_ceiling_lock_is_counted_on_an_adjusted_window` | **`limit_lock_days > 0`** — cổng thứ hai đã mở thật |
| `test_the_frame_actually_drops_the_locked_sessions` | `without_limit_locks()` loại đúng số phiên trần |
| `test_an_upcom_session_is_undecided_and_stays_that_way` | UPCOM → `ANCHOR_NOT_STORED` mọi bar |
| `test_a_rebased_window_says_so_rather_than_reporting_no_locks` | cửa sổ scale 1,037 → khai lý do, **không** trả "chưa từng đạt trần" |
| `test_band_pressure_answers_on_an_adjusted_window` | field đích trả số > 0 qua `serve_field` |

## Success Criteria

- [x] `band_pressure` trả số, không đọc FiinQuant
- [x] Phiên lệch lưới nhận lý do có tên; UPCOM undecided vĩnh viễn, viết ra
- [x] **`limit_lock_days > 0`** trên fixture có phiên trần
- [x] `without_limit_locks()` loại đúng phiên trần trên fixture đó
- [x] Tỉ lệ quyết được theo sàn ghi vào phase report
- [x] `make test` xanh — **1405 passed**

## Cần user biết

**Tập 30 mã declared quyết được 80,71%**, sát ngưỡng 80% mà phase file đặt làm tín
hiệu "đưa số cho user". Toàn sàn HOSE thì 91,52%. Nghĩa là ~1/5 phiên của chính
các mã lane chat phục vụ sẽ trả `price_off_tick_grid` thay vì một con số. Đó là
**từ chối đúng** — giá đã bị rebase thì band không đo được — nhưng nếu muốn field
này phủ dày hơn thì đường đi là ingest giữ thêm giá chưa điều chỉnh, không phải nới
phép kiểm.
