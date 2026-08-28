---
phase: 2
title: "Lịch giao dịch chuyển sang bar_daily"
status: pending
priority: P1
effort: "1d"
dependencies: [1]
---

# Phase 02: Lịch giao dịch chuyển sang bar_daily

## Overview

`trading_day.py` suy toàn bộ lịch phiên từ `provider_snapshots` capability
`market`. Bảng đó **không còn writer nào** trong `src/`, nên lịch đứng yên ở
2026-08-24 vĩnh viễn. Chuyển sang `bar_daily.trading_day` — cột `Date` thật,
do vnstock nuôi, tươi tới 2026-08-27.

## Requirements

- Functional: bốn hàm công khai của `trading_day.py` (`latest_trading_day:43`,
  `trading_days_before:56`, `trading_days_between:79`, `market_generation:101`)
  trả cùng kiểu như cũ nhưng đọc `bar_daily`.
- Functional: **mọi truy vấn lọc `series`** — xem §Lọc series bên dưới.
- Functional: `latest_trading_day()` không phụ thuộc đồng hồ treo tường.
- Functional: có một đường giữ `bar_daily` tươi (giải R2), không để lửng.
- Non-functional: `sessions.py:117` khớp row theo `effective_at` **bằng đúng** —
  lịch và row phải cùng hệ quy chiếu, không được lệch nhau nửa bước.

## Architecture

**Vì sao không sửa timezone.** Đã đo: `latest_trading_day()` trả
`2026-08-24 Monday`, đúng. `providers/normalize.py:23-36 day_in_vn` đã
`astimezone(VN_TZ)`. Không có lỗi lệch ngày để sửa — ba claim của red-team
2026-08-27 đã bị đảo, xem `plan.md` §"Đo lại".

**Chỗ thật sự phải cẩn thận.** `trading_day.py` và `signals/sessions.py:117` hiện
dùng **cùng một tập giá trị** `effective_at`: lịch trả ra ngày, `sessions_on_days`
dựng lại `datetime` nửa đêm VN và khớp `IN (...)` chính xác. Đổi nguồn lịch sang
`bar_daily` mà `sessions.py` còn đọc `provider_snapshots` thì hai bên rời nhau và
mọi lookup trượt.

Cách tránh cửa sổ hỏng: phase 02 đổi `trading_day.py`, phase 03 đổi `sessions.py`
ngay sau, trong một nhánh liên tục. Nếu buộc phải tách, `trading_day` đọc **giao**
của hai nguồn cho tới khi 03 xong — không phải hợp.

### Lọc series — không được quên

`bar_daily` cố ý gộp `equity` và `index` vào một bảng, và `models.py:411-418` nói
rõ việc đó chỉ an toàn vì *"nothing is derived from the table"*. Phase này làm
một thứ dẫn xuất từ nó, nên điều kiện an toàn đó không còn.

`providers/contracts.py:46-54` đã mô tả chính xác tai nạn: *"One index row landing
before the Universe's would move `latest_trading_day` forward and refuse every
symbol for one session of missing history."* `backfill_daily.py:113-129` chạy
index như **scope riêng** (`SCOPE_INDEX`) và `_one_symbol` nuốt mọi exception theo
từng mã (`:236-287`), nên một lần chạy đứt giữa chừng là đủ tạo ra ngày chỉ có
index. Hôm nay hai series tình cờ trùng (cùng 3.991 ngày, cùng max 2026-08-27),
nên test sẽ không bắt được.

Thêm một tầng nữa: ngay trong `series='equity'`, chỉ **846/1.522** mã có dòng
ngày 2026-08-27. `distinct(trading_day)` trên toàn bảng là phép **hợp** — nó
tuyên một ngày là phiên khi bất kỳ mã nào có dòng.

**Quyết định — cần user chốt (câu hỏi mở #5):** lịch định nghĩa trên
`series='index'` (VNINDEX là một mã, có phiên là thị trường có phiên — sạch nhất),
hay trên Universe declared 30 mã (khớp ngữ nghĩa "thị trường ta phục vụ"). Không
dùng hợp của 1.522 mã.

**Phiên chưa đóng — không dùng đồng hồ.** `studies/reads_daily.py:102-108` cắt
phiên hôm nay bằng `SESSION_SETTLED_AT` (15:00 VN, `intraday/reads.py:34`). Đừng
sao chép cách đó vào đây, vì hai lý do:

1. **Mất tính tất định trong một Turn.** `latest_trading_day` hiện là truy vấn
   thuần. Gắn `datetime.now(VN_TZ)` vào là một Turn gọi `get_field` lúc 14:59:50
   và `get_series` lúc 15:00:10 đo hai cửa sổ khác nhau — phá đúng lời hứa ở
   docstring `trading_day.py:1-16` rằng *"hai mươi phiên là cùng hai mươi phiên
   cho mọi người"*.
2. **Đồng hồ không chứng minh phiên đã đóng.** `backfill_daily.py:184-193` lấp
   ngược từ `cursor = today` **bao gồm hôm nay**, nên một lần chạy lúc 11:00 ghi
   một bar dở dang của hôm nay vào `bar_daily`, không dấu vết. Tệ hơn:
   `is_deep_enough` (`:140-172`) thấy `last >= reference` nên **bỏ qua mã đó** ở
   lần chạy sau phiên — bar dở dang không bao giờ được sửa trong ngày.

**Dùng dấu vết trong dữ liệu:** chỉ nhận phiên có `observed_at` muộn hơn giờ đóng
cửa của chính `trading_day` đó. Và yêu cầu job giữ tươi (R2) chạy **sau** giờ đóng.

**Giải R2 — ai nuôi bar_daily.** `backfill_daily.py` có `run()` (`:176`) và
`newest_stored_session()` (`:134`) nhưng không caller nào trong `src/`, `Makefile`
hay `scripts/`. Ba đường, chọn một và ghi lý do vào phase report:

1. Target `make backfill-daily` + cron ngoài app — rẻ nhất, hợp với việc hiện
   không có scheduler nào trong app.
2. Job trong app theo `trading_day` — đúng chỗ nhưng phải dựng scheduler mới.
3. Lazy: `latest_trading_day` thấy cũ hơn N phiên thì kích ingest — trộn đọc với
   ghi, dễ gây bão request; **không khuyến nghị**.

Bất kể chọn gì: `latest_trading_day` phải phân biệt được "chưa có phiên nào" với
"phiên mới nhất đã cũ N ngày", và nói ra cái thứ hai.

## Related Code Files

- Modify: `apps/api/src/stocks/trading_day.py` (bốn hàm công khai + `_day_start`)
- Modify: `apps/api/tests/test_trading_day.py` (fixture đổi sang `BarDaily`)
- Create hoặc Modify: đường giữ tươi — `apps/api/Makefile` target, hoặc job mới
- Read: `apps/api/src/stocks/backfill_daily.py:134-138,176`,
  `apps/api/src/studies/reads_daily.py:81,107,132,149`,
  `apps/api/src/stocks/intraday/reads.py:34`
- Không đụng: `apps/api/src/stocks/signals/sessions.py` (phase 03)

## Implementation Steps

1. Viết test đỏ trước: seed `BarDaily` vài phiên + một phiên hôm nay chưa đóng;
   khẳng định `latest_trading_day` bỏ phiên chưa đóng.
2. Đổi `latest_trading_day` → `max(BarDaily.trading_day)` có cắt phiên chưa đóng.
3. Đổi `trading_days_before` / `trading_days_between` → `distinct(trading_day)`
   trên `BarDaily`, giữ nguyên ngữ nghĩa "không bao giờ độn ngày giả".
4. `market_generation` có **0 caller** trong `src/` (chỉ `tests/test_trading_day.py`).
   Docstring nói "Signal cache keys carry it" nhưng cache đó không còn sau rip.
   **Xoá nó** cùng test, đừng bỏ công port một hàm chết. `trading_days_between`
   cũng 0 caller trong `src/` — giữ hay xoá, ghi quyết định ra.
5. Cập nhật docstring module: nguồn lịch giờ là `bar_daily`, và câu về "mọi
   adapter ghi nửa đêm VN" không còn là lời giải thích của lịch nữa.
6. Chạy toàn bộ test signals — năm caller trong `src/` đều đi qua đây
   (`agent/tools/price_check.py:244,509`, `agent/tools/signals.py:472,619`,
   `signals/serving.py:185`, `signals/bars.py:501,516,617,627`,
   `signals/price_band.py:488`).
7. Dựng đường giữ tươi đã chọn.
8. Đo lại: `latest_trading_day()` phải trả phiên gần nhất `bar_daily` có.

## Success Criteria

- [ ] `latest_trading_day()` trả phiên đã đóng mới nhất của tập series đã chốt
- [ ] Mọi truy vấn lọc `series`; không truy vấn nào chạy trên cả hai series
- [ ] Hai lần gọi `latest_trading_day()` cách nhau qua mốc 15:00 trong một Turn
      không thể khác nhau
- [ ] Phiên chưa đóng không bao giờ được trả, và phép kiểm dựa vào `observed_at`
      chứ không dựa vào đồng hồ
- [ ] `trading_days_before(day, N)` không độn ngày không có phiên
- [ ] Có đúng một đường được viết ra để giữ `bar_daily` tươi, và nó chạy được
- [ ] `make test` xanh; năm caller trong `src/` không đổi chữ ký
- [ ] `market_generation` đã xoá cùng test của nó

## Risk Assessment

- **Cửa sổ giữa 02 và 03.** Lịch đã sang `bar_daily`, row còn ở
  `provider_snapshots` → `sessions_on_days` trượt sạch, mọi field
  `INSUFFICIENT_HISTORY`. *Tín hiệu:* test signals đỏ hàng loạt ngay sau phase 02.
  *Phản ứng:* làm 02 và 03 liên tục; nếu buộc phải tách, dùng lịch giao hai nguồn.
- **Độ phủ theo mã, không phải lỗ phiên.** Bản đầu ghi "2026-08-19 không có dòng
  cho STB" — **sai**, dòng đó tồn tại (close 74.800, volume 4.934.700), và
  2026-08-19 có 862 mã. Vấn đề thật là phủ **không đều**: 846/1.522 mã ở ngày mới
  nhất. *Tín hiệu:* mã thưa dữ liệu refuse ở phiên mới nhất trong khi mã dày thì
  không. *Phản ứng:* đó chính là lý do phải chọn tập định nghĩa lịch ở §Lọc series,
  chứ không phải backfill thêm.
- **Chọn đường giữ tươi rồi không ai chạy.** *Tín hiệu:* **không dùng được**
  `market_generation` làm tín hiệu — nó có 0 caller và sắp bị xoá. Dùng tuổi của
  `max(bar_daily.observed_at)`: quá N phiên thì báo. *Phản ứng:* câu hỏi mở #1 —
  cần người quyết, không giấu trong code.
- **Ingest không có chốt chặn.** `bar_daily` không có CHECK constraint nào trên
  `trading_day` (`models.py:434-450`), và `vnstock_daily.py:89` chỉ kiểm **tên
  cột**. Một dòng provider dị dạng (ngày tương lai, ngày cuối tuần) dịch lịch của
  cả thị trường. *Tín hiệu:* `latest_trading_day` nhảy về tương lai.
  *Phản ứng:* thêm chốt cuối tuần/tương lai ở biên ingest trước khi lịch phụ
  thuộc vào dòng provider.
