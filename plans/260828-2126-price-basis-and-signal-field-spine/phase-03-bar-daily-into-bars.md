---
phase: 3
title: "Cầu bar_daily → bars.py + luật basis mới"
status: pending
priority: P1
effort: "2d"
dependencies: [2]
---

# Phase 03: Cầu bar_daily → bars.py + luật basis mới

> **Sửa 2026-08-28 sau red-team.** Bản đầu liệt `_basis_of` trong danh sách file
> nhưng **không có bước nào** đổi phán quyết của nó — cả bốn reviewer đều bắt lỗi
> này. Bản đầu cũng không biết có cổng basis **thứ hai**, và vá R4 chỉ nửa vời.

## Overview

Phase nặng nhất. `bar_daily` hôm nay không có đường nào vào `signals/bars.py`.
Phase này dựng cầu, **viết luật basis mới thành câu**, và giải bài toán điều
chỉnh hai lần.

## Requirements

- Functional: `prepare_bars` / `prepare_bars_context` đọc `bar_daily`.
- Functional: **cửa sổ toàn `adjusted_at_source` được phục vụ** trên projection
  PRICE. Đây là yêu cầu số một; thiếu nó thì 20 field PRICE từ chối im lặng và
  mọi success criterion của plan không đạt được.
- Functional: input `adjusted_at_source` không bị máy điều chỉnh nội bộ chạy đè.
- Non-functional: 17 field thuần OHLCV trả số **không đổi** so với trước, trong
  dung sai khai ra, kể cả trên mã có corporate action.

## Architecture

### Luật basis mới — viết thành câu, không để ngầm

`_basis_of` (`bars.py:814-826`) hôm nay: *"Only an all-`raw` window is served."*
Mọi dòng `bar_daily` là `adjusted_at_source`. Nếu không đổi câu đó, Phase 03 nối
xong là **mọi field PRICE trả `UNADJUSTABLE_PRICE_BASIS`** — không exception,
không crash, chỉ là từ chối đồng loạt.

**Luật mới:**

| Cửa sổ | Phán quyết |
|---|---|
| toàn `raw` | phục vụ, `_factors` chạy (đường cũ, còn dùng nếu còn dòng raw) |
| toàn `adjusted_at_source` | **phục vụ**, `_factors` **không** chạy, `adjustment_factor = 1` |
| trộn hai basis | `MIXED_PRICE_BASIS` — giữ nguyên, đây là seam thật |

`UNADJUSTABLE_PRICE_BASIS` không còn nghĩa "adjusted thì không phục vụ được". Thu
hẹp hoặc bỏ nó, và ghi lý do trong docstring — đừng để mã cũ nằm lại với nghĩa cũ.

### Cổng thứ hai

`price_band.py:500-518 _basis_of_the_pair`, gọi từ `:431` trong `measure_band`.
Phase 06 sở hữu việc mở nó. Phase 03 chỉ cần **biết nó tồn tại** và không tuyên
bố "đã xong luật basis" khi mới mở một cổng. Ghi vào phase report.

### Bài toán điều chỉnh hai lần

`_factors` (`bars.py:914-1002`) đọc **chuỗi Corporate Action đã lưu** và tính hệ
số từ *điều khoản đã công bố*, cố ý không tính từ gap giá ở ex-date (`:919-928`).
`Bar.close` là giá đã rebase; `Bar.raw_close` (`:295-305`) chia ngược hệ số ra.

`bar_daily` đã `adjusted_at_source`. Chạy `_factors` lên nó = điều chỉnh hai lần,
sai **im lặng**.

**Quyết định: input `adjusted_at_source` → `adjustment_factor = 1` cho mọi bar.**

Một chỗ tinh tế phải ghi ra: `bar_daily` được provider rebase về **hôm nay**, còn
`_frame` (`bars.py:970-983`) rebase về **phiên cuối của cửa sổ**. Hai mốc khác
nhau lệch nhau một hằng số — triệt tiêu trong return, **không** triệt tiêu trong
`adtv_vnd`, `amihud_illiq`, hay bất kỳ phép so tiền giữa các mã. Phase 05 phải
biết điều này.

### Hệ quả: `raw_close` mất nghĩa

Với factor = 1, `raw_close == close`, mà `close` là giá đã điều chỉnh — **không**
phải giá sàn công bố. Ba chỗ phụ thuộc:

| Chỗ | Xử lý |
|---|---|
| `market_behavior.py:406,415-420` (`band_pressure`) | Phase 06 |
| `agent/tools/price_check.py:337` (nhánh BAND) | **R7** — xem dưới |
| `agent/tools/price_check.py:411` (nhánh STORE) | **R7** |

Không khôi phục giá raw bằng cách nhân ngược hệ số nội bộ vào giá provider: hệ số
của ta và của provider không bảo đảm bằng nhau.

### R7 — `check_price_claim` mất 2/3 nhánh

`check_price_claim` là **control an ninh**: nó kiểm một giá model nhặt từ nội dung
web không tin cậy. Sau phase này, nhánh BAND và STORE trả `unverified` vĩnh viễn
cho mọi mã, mọi phiên; chỉ còn TICK — một phép kiểm lưới bước giá mà một giá bịa
hợp lý vượt qua dễ dàng.

Bản đầu ghi việc này thành một dòng ghi chú. Sai mức: đây là control bị tắt như
tác dụng phụ của việc chuyển nguồn dữ liệu. **Phải có quyết định ghi ra** (câu hỏi
mở #4): hoặc dựng lại phép so STORE trên giá đã điều chỉnh với dung sai khai rõ,
hoặc chấp nhận và đổi prompt/UI để verdict `unverified` được **hiện ra** thay vì
bị hấp thụ. Phase này không tự chọn; nó phải đưa số và câu hỏi lên.

### R4 — `_session_low` hỏng **hai** lớp

Bản đầu chỉ thấy một:

1. `corporate_actions.py:720` order theo `ProviderSnapshot.written_at` — cột không
   tồn tại (`models.py:27-35` có `created_at`). `AttributeError` khi chạm từ `:410`.
2. `corporate_actions.py:709-710` dựng cửa sổ ngày bằng **UTC**
   (`tzinfo=timezone.utc`), trong khi phiên đóng dấu nửa đêm **VN** (`D-1 17:00+00`).

Vá mỗi (1) là thay một lỗi **ồn** bằng một lỗi **câm**: hàm chạy trơn và trả
`None` cho mọi phiên, khiến `:415-419` rơi xuống `NO_CORROBORATING_GAP` — mọi
corporate action đáng lẽ xác nhận được thành `unconfirmed`. Mà Phase 06 lại đọc
chính chuỗi đó.

**Cách vá đúng:** đổi hẳn truy vấn sang `bar_daily`, khoá trên cột `Date` gốc —
tránh cả hai lỗi cùng lúc. Và thêm test: hàm này hiện **không có test nào**, đó
là lý do một tham chiếu tới cột không tồn tại sống sót được.

## Related Code Files

- Modify: `apps/api/src/stocks/signals/sessions.py` (`sessions_on_days:108`,
  `sessions_in_range:149` → `BarDaily`)
- Modify: `apps/api/src/stocks/signals/bars.py` (`_basis_of:814`, `:684`,
  `prepare_bars:571`, `prepare_bars_context:495`, `_factors:914`, `raw_close:295`)
- Modify: `apps/api/src/stocks/signals/corporate_actions.py:708-720`
- Modify: `apps/api/src/stocks/providers/store.py:41 resolve_sessions`
- Modify: `apps/api/src/alpha/envelope.py:737` (probe qua cùng cổng)
- Read: `apps/api/src/agent/tools/price_check.py:337,411` (R7 — chưa sửa ở đây)
- Tests: mọi test signals · golden test corporate action · **test `_session_low`**

**Caller không được quên** (bản đầu chỉ kể định nghĩa):
`sessions_on_days` — `price_check.py:247`, `bars.py:520`, `bars.py:1129`;
`sessions_in_range` — `price_band.py:490`, `bars.py:630`;
`resolve_sessions` — `sessions.py:171`, `corporate_actions.py:725`;
`prepare_bars` — `serving.py:66,201`, `alpha/envelope.py:737`,
`tests/test_signal_registry.py:194`, `tests/signal_windows.py`.

## Implementation Steps

1. **Golden test trước.** ≥ 3 mã có corporate action trong 250 phiên gần nhất, và
   **≥ 1 mã có phiên trần đã biết** (để Phase 06 có fixture). Ghi giá trị hiện tại
   của 17 field OHLCV vào fixture. Đây là lưới an toàn cho R1.
2. **Đổi luật `_basis_of`** theo bảng trên; viết câu mới vào docstring. Test:
   cửa sổ toàn adjusted **được phục vụ**; cửa sổ trộn vẫn `MIXED_PRICE_BASIS`.
3. Đổi `sessions.py` đọc `BarDaily` → dựng `SessionSnapshot`, cột không có để
   `None`, `price_basis` lấy từ cột, **lọc `series`**.
4. Bỏ qua `_factors` khi mọi row là `adjusted_at_source`; `adjustment_factor = 1`.
   Ghi lý do + chú ý "hai mốc rebase khác nhau" vào docstring.
5. Sửa docstring `raw_close`: nó chỉ là giá sàn công bố khi factor ≠ 1.
6. Vá `_session_low`: đổi sang `bar_daily`, thêm test khẳng định nó trả được số
   cho một phiên đã lưu.
7. `resolve_sessions` — chỉ còn một source; đơn giản hoá. **Hai chỗ gọi**:
   `sessions.py:171`, `corporate_actions.py:725`.
8. Chạy golden test. **Lệch quá dung sai = dừng.**
9. `make test` + `tests/studies/`.

## Success Criteria

- [ ] **Cả 20 field PRICE trả số** trên window `adjusted_at_source` — không chỉ
      nhóm VOLUME
- [ ] Luật basis mới có câu trong docstring và có test cho cả ba nhánh bảng
- [ ] Không module nào trong `signals/` đọc `provider_snapshots` capability MARKET
- [ ] `_factors` không chạy trên window `adjusted_at_source`
- [ ] Golden test: 17 field OHLCV khớp giá trị trước, trong dung sai đã khai
- [ ] `_session_low` chạy được **và có test**; không còn dùng UTC dựng cửa sổ ngày
- [ ] R7 đã đưa lên thành câu hỏi có số, không phải ghi chú
- [ ] `make test` + `tests/studies/` xanh

## Risk Assessment

- **R1 điều chỉnh hai lần** — rủi ro chính. Sai im lặng. *Tín hiệu:* golden test
  lệch trên mã có action, khớp trên mã không có. *Phản ứng:* quay lại bước 4,
  đừng nới dung sai.
- **Mở một cổng rồi tưởng xong.** *Tín hiệu:* field PRICE trả số nhưng
  `limit_lock_days` = 0 khắp nơi. *Phản ứng:* đó là cổng thứ hai còn đóng —
  Phase 06, không phải bug mới.
- **Dung sai chưa quyết** (câu hỏi mở #3). *Tín hiệu:* lệch nhỏ và **đều** trên
  mọi mã có action → lệch phương pháp, không phải bug. *Phản ứng:* đo biên độ,
  khai ra, chốt với user trước khi tick.
- **`prepare_bars` raise `ValueError` trần** ở `bars.py:612-613` nếu
  `serve_cross_section` truyền projection cho `prepare_bars` mà không truyền cho
  `prepare_bars_context` — 500 chứ không phải refusal. *Tín hiệu:* lỗi 500 trên
  đường cross-section sau Phase 04. *Phản ứng:* Phase 04 phải truyền cả hai chỗ.
