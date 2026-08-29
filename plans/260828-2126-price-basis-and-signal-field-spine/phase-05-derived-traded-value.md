---
phase: 5
title: "traded_value suy diễn — ba field liquidity"
status: done
priority: P2
effort: "6h"
dependencies: [4]
---

# Phase 05: traded_value suy diễn — ba field liquidity

> **Viết lại 2026-08-28 sau red-team.** Bản đầu suy diễn ở sai tầng (chỉ cứu 2/3
> field), đặt ngưỡng dừng theo trung vị trong khi lỗi nằm ở đuôi, và biến dữ liệu
> vắng thành số `0`, phá refusal đang chạy.

## Overview

`bar_daily` không có cột giá trị giao dịch, và điều đó cố ý:
`vnstock_daily.py:33-34` bảo caller tự tính `close × volume`. Phase này làm đúng
thế — **ở đúng tầng**, một lần.

## Requirements

- Functional: `liquidity_profile.{adtv_vnd, amihud_illiq, adtv_percentile}` trả số.
- Functional: `WindowHealth.adtv` khác `None` — nó là thứ `adtv_percentile` đọc.
- Non-functional: suy diễn trả `None` khi không suy được, **không bao giờ** `0`.
- Non-functional: số suy diễn khai là suy diễn ở contract và `Provenance`.

## Architecture

### Suy ở tầng nào — bản đầu sai chỗ này

Bản đầu nói "tính ở gateway `bars.py` khi dựng `Bar`". Nhưng hai trong ba field
**không đọc `Bar`**:

| Chỗ đọc | Vị trí | Đọc gì |
|---|---|---|
| `adtv_vnd`, `amihud_illiq` | `market_behavior.py:185,255` | `bar.total_value_vnd` — tầng `Bar` |
| `_adtv_standing` | `bars.py:1111` | `usable[day].total_value_vnd` — tầng **`SessionSnapshot`** |
| `_peer_average` | `bars.py:1147-1156` | `row.total_value_vnd` — tầng **`SessionSnapshot`** |

`WindowHealth.adtv` đến từ `_adtv_standing`, và `adtv_percentile_reading`
(`market_behavior.py:295`) đọc đúng `window.health.adtv`. Suy diễn trong `_frame`
không bao giờ chạm tới đó → `adtv_percentile` vẫn `RANKING_UNAVAILABLE`, và
chuẩn thanh khoản toàn thị trường mà `WindowHealth` công bố biến mất im lặng.

**Quyết định: suy ở seam dựng `SessionSnapshot` trong `sessions.py`** — chính chỗ
Phase 03 đã sửa. Một số, cả hai tầng cùng thấy, DRY thật sự.

### Vắng dữ liệu phải là `None`, không phải `0`

**24,41%** dòng equity trong `bar_daily` có `volume = 0` (197.492/809.085). VHM
riêng nó giữ 1.309 dòng volume 0 và 1.412 dòng **trước ngày niêm yết 2018-05-17**
ở một mức giá đóng băng.

`average_over_sessions` (`market_behavior.py:186-190`) trả `None` → refusal
`TRADED_FIGURE_NOT_STORED` chỉ khi gặp `None`, **không** khi gặp `0.0`. Nên
`close × 0 = 0.0` sẽ lọt qua refusal và kéo trung bình xuống theo tỉ lệ phiên
chết, không ai biết.

Luật: `volume == 0` → `traded_value = None`. Refusal cũ tiếp tục làm việc của nó.

(`amihud_illiq` đã tự vệ sẵn — `market_behavior.py:255-257` chặn `traded <= 0` —
nên nó xuống cấp êm; `adtv_vnd` mới là chỗ xuống cấp **sai**.)

### Ba khác biệt phải khai

1. `close × volume` là **xấp xỉ**. Giá trị thật là tổng `giá × khối lượng` từng
   lệnh; dùng giá đóng cửa cho cả phiên là gần đúng.
2. `close` sau Phase 03 là giá **đã điều chỉnh**. Tích quanh ex-date lệch khỏi
   tiền thật đã trao tay — hệ số giá và hệ số khối lượng không phải một
   (`bars.py:241-242`: ACB 2025, khối lượng ×1,15 còn giá ×0,8355).
3. Không tách được thoả thuận (put-through).

### Ngưỡng dừng theo đuôi, không theo trung vị

Đo sớm (30 mã declared, chồng lấn từ 2026-06-01, n=1.696 cặp):

```
mean 4,014% | median 0,864% | p95 20,387% | max 52,977%
```

Volume thì khớp gần như tuyệt đối (median 0,057%, max 1,08%) — nên **toàn bộ
đuôi đến từ close-vs-VWAP**, tức lỗi lớn nhất đúng vào ngày biến động mạnh. Mà
ngày biến động mạnh chính là ngày `amihud_illiq` đánh trọng số cao nhất: tử số
của nó là `|R_t|`.

Ngưỡng dừng theo trung vị sẽ luôn qua (0,86%) và bỏ lọt đuôi. **Dùng p95.**

## Related Code Files

- Modify: `apps/api/src/stocks/signals/sessions.py` (seam dựng `SessionSnapshot`)
- Modify: `apps/api/src/stocks/signals/market_behavior.py:176,238,282`
- Modify: `apps/api/src/stocks/signals/registry.py` (mô tả field nói rõ ước lượng)
- Read: `apps/api/src/stocks/signals/bars.py:1111,1147-1156` (hai chỗ tiêu thụ)
- Tests: ba field · một test `volume=0 → None` · một test `health.adtv is not None`

## Implementation Steps

1. Suy `traded_value` ở `sessions.py`, trả `None` khi `volume == 0` hoặc `close`
   là `None`.
2. Khai cờ/tên cho biết là ước lượng; cập nhật `Provenance`.
3. Xác nhận cả `Bar.total_value_vnd` lẫn `_adtv_standing` cùng thấy số đó.
4. Docstring `amihud_illiq`: mẫu số giờ là ước lượng.
5. **Đo trước khi Phase 08 xoá** — 30 mã declared, 60 phiên: so `close × volume`
   với `total_value_vnd` của FiinQuant, ghi **mean · median · p95 · max** vào
   phase report. Ngưỡng dừng: **p95 > 25%** thì dừng và đưa số cho user.
6. `make test`.

## Success Criteria

- [ ] Ba field `liquidity_profile` trả số từ `bar_daily`
- [ ] `health.adtv is not None` trên fixture — chứng minh suy diễn tới được cả hai tầng
- [ ] Phiên `volume = 0` cho `None`, và refusal `traded_figure_not_stored` vẫn bắn
- [ ] Số suy diễn khai là suy diễn ở contract và `Provenance`
- [ ] Bốn thống kê (mean/median/p95/max) ghi vào phase report **trước** Phase 08
- [ ] `make test` xanh

## Risk Assessment

- **Đuôi tệ hơn dự kiến.** *Tín hiệu:* bước 5 cho p95 > 25%. *Phản ứng:* đưa số
  cho user quyết — chấp nhận và khai biên độ trong `Provenance`, hay chuyển ba
  field sang refusal. Không tự chọn.
- **Đo sau khi đã xoá.** Bước 5 chỉ làm được khi dòng FiinQuant còn. Đây là lý do
  Phase 05 đứng trước Phase 08.
- **Dòng rác trước ngày niêm yết.** VHM có 1.412 dòng trước 2018-05-17 ở giá đóng
  băng. *Tín hiệu:* ADTV lịch sử của mã mới niêm yết trông đều bất thường.
  *Phản ứng:* `volume = 0` → `None` đã xử lý phần lớn; nếu còn dòng giá đóng băng
  mà volume khác 0 thì đó là việc của ingest, ghi ra chứ đừng vá ở tầng đọc.
