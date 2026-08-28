---
phase: 6
title: "band_pressure trên lưới bước giá"
status: pending
priority: P2
effort: "1d"
dependencies: [5]
---

# Phase 06: band_pressure trên lưới bước giá

> **Viết lại 2026-08-28 sau red-team.** Bản đầu sai bốn chỗ nền: (1) dựa vào phép
> đo một-mã "80/80 khớp" mà toàn bộ 30 mã chỉ cho **60,59%**; (2) đề nghị nối
> `listing_roster` vào đường dựng bar — việc **đã có sẵn**; (3) đặt phép thử quyết
> định lên chuỗi corporate action **đã chết**; (4) đặt cổng nghiệm thu là so với
> `limit_lock` của FiinQuant, thứ **99,93% null**. Quyết định "tự tính band từ
> luật sàn" của user giữ nguyên; cách làm thì đổi hẳn.

## Overview

`band_pressure.limit_days_in_window` đếm phiên trần/sàn. Sau Phase 03 mọi giá là
`adjusted_at_source`, và band nằm trên lưới bước giá của giá **thật đã giao dịch**.
Phase này quyết định từng phiên: giá của phiên đó có còn nằm trên lưới không —
nếu có thì tính band, nếu không thì từ chối có tên.

## Requirements

- Functional: `band_pressure` trả số cho phiên quyết được.
- Functional: phiên không quyết được nhận `band_undecided_reason` — không bao giờ
  nhận band đoán.
- Functional: cổng basis thứ hai `_basis_of_the_pair` được mở đúng cách, và việc
  loại phiên trần/sàn khỏi baseline volatility **hoạt động trở lại**.
- Non-functional: không đọc số nào của FiinQuant.

## Architecture

### Cái đã có — đừng dựng lại

Bản đầu viết "Thiếu duy nhất một đường nối: anchor". Sai. Đã có sẵn:

| Thứ | Vị trí |
|---|---|
| `measure_band` neo vào close phiên trước và gọi `band_limits(regime.exchange, anchor_price)` | `price_band.py:390-440`, `:438` |
| `BandRegimeResolver` phân giải sàn từ roster, có cả lịch sử chuyển sàn | `price_band.py:279-345` |
| Roster đã nạp theo lô cho cả cửa sổ | `bars.py:511,534` `_listed_exchanges` |
| `band_limits`, `resolve_band_regime`, `tick_size` | `price_band.py:251,375,241` |

Thêm một truy vấn roster thứ hai là tạo hai bản sao cùng một sự thật, có thể lệch
nhau. **Tái dùng `BarPreparationContext._listed_exchanges`.**

### Cái thật sự chặn: cổng basis thứ hai

`measure_band` gọi `_basis_of_the_pair(target, anchor)` ở `price_band.py:431`.
Cặp toàn `adjusted_at_source` → `UNADJUSTABLE_PRICE_BASIS` → `_undecided(...)` →
`LimitLock.INDETERMINATE` cho **mọi phiên của mọi mã**. Hậu quả dây chuyền:

- `Bar.limit_locked` (`bars.py:291-292`) luôn `False`;
- `BarFrame.without_limit_locks()` (`bars.py:322-333`) không loại gì → baseline
  volatility tính trên cửa sổ còn nguyên phiên `H=L=O=C`, đúng cái docstring nói
  *"none may skip"*;
- `WindowHealth.limit_lock_days` = 0 → `limit_lock_degradation` không bao giờ
  bắn, câu trả lời không được đánh dấu suy giảm;
- `UNEXPLAINED_PRICE_GAP` (`bars.py:879`) **bất khả đạt**, vì nó nằm sau
  `PRICE_MOVE_EXCEEDS_BAND` (`price_band.py:451`).

Không exception, không refusal, không test đỏ.

### Phép thử quyết định: lưới bước giá, không phải vắng ex-date

Bản đầu định dùng "không có ex-date giữa phiên đó và hôm nay → quyết được".
Không dùng được: `CorporateActionStore.save()` có **0 caller** trong `src/`
(collector đã rip), bảng giữ **284 dòng / 29 mã** trên tổng **1.522 mã**
`bar_daily`, ex-date mới nhất 2026-09-10. Với 98% mã, bảng rỗng — và "không có
dòng" bị đọc thành "không có ex-date", nên luật sẽ tuyên **mọi** phiên quyết được.
Đó là cách sai tệ nhất: sai mà tự tin.

Thay bằng phép thử **tự chứng từ chính dữ liệu**: giá đã điều chỉnh của một phiên
có còn nằm trên lưới bước giá của mức giá đó không.

- Giá sàn công bố **luôn** nằm trên lưới bước giá (HOSE: 10đ dưới 10k, 50đ từ
  10k–50k, 100đ từ 50k).
- Giá bị rebase bởi một hệ số không tròn thì **rơi khỏi lưới**.

Đo trên HOSE, từ 2026-07-01, 15.624 phiên có khớp lệnh:

```
off_grid 1.086 / 15.624 = 6,95%   ·   74 mã dính
```

Tức **93,05% phiên quyết được**, và 6,95% còn lại tự khai chúng đã bị rebase.

**Luật:**

| Điều kiện | Kết quả |
|---|---|
| Cả close phiên đích và close phiên neo đều trên lưới bước giá của sàn | band quyết được |
| Một trong hai rơi khỏi lưới | `band_undecided_reason` — giá đã bị rebase |
| Sàn UPCOM | `band_undecided_reason` **vĩnh viễn** — neo là VWAP phiên trước (`price_band.py:331-335`), `bar_daily` không có VWAP |
| Phiên trước không có trong store | lý do cũ, giữ nguyên (`bars.py:255-270`) |

**Giới hạn phải khai:** trên-lưới là điều kiện **cần, không đủ**. Một giá rebase
vẫn có thể tình cờ rơi đúng lưới. Phép thử này loại được phần lớn ca xấu, không
phải tất cả — viết câu đó vào docstring, đừng để người sau tưởng nó là chứng minh.

UPCOM là 819/1.751 mã roster (47%), gồm MCH trong 30 mã declared. Nói thẳng nó
vĩnh viễn không quyết được, đừng để phase sau đi tìm cách "sửa".

### Cổng nghiệm thu — không so được với FiinQuant

Bản đầu đặt cổng "so verdict limit-lock với FiinQuant, ≥ 90%". Không đo được:

```sql
SELECT count(*), count(*) FILTER (WHERE payload->>'ceiling_price' IS NULL)
FROM provider_snapshots WHERE source='fiinquant' AND capability='market';
-- 36528 | 36504   →  99,93% null
```

`price_band.py:10-12` đã ghi lý do: *"`ceiling_price`/`floor_price` là `None` trên
mọi bar lịch sử, vì `_fetch_history` truyền `band=None` cố ý."* Bản đầu trích file
này cho `band_limits` mà không đọc dòng đó.

**Cổng thay:** tỉ lệ phiên quyết được theo sàn và theo mã (đo được, không cần
FiinQuant), cộng một fixture có phiên trần đã biết để khẳng định
`limit_lock_days > 0`.

## Related Code Files

- Modify: `apps/api/src/stocks/signals/price_band.py:431,500-518` (cổng thứ hai),
  `:331-335` (UPCOM khai vĩnh viễn undecided)
- Modify: `apps/api/src/stocks/signals/bars.py` (`band_undecided_reason` mới;
  **tái dùng** `_listed_exchanges`, không thêm truy vấn)
- Modify: `apps/api/src/stocks/signals/market_behavior.py:313,406,415-420`
- Read: `apps/api/src/stocks/signals/price_band.py:241 tick_size`, `:251 band_limits`
- Tests: quyết được · undecided vì lệch lưới · undecided vì UPCOM · undecided vì
  thiếu phiên trước · **`limit_lock_days > 0` trên fixture có phiên trần**

## Implementation Steps

1. Thêm lý do undecided mới cho "giá lệch lưới bước giá" vào `issues.py`, kèm câu
   ở `alpha/reasons.py` và `signal-issues.ts`.
2. Mở `_basis_of_the_pair` cho cặp toàn `adjusted_at_source`, theo đúng luật
   Phase 03 đã viết cho `_basis_of`.
3. Thêm phép thử lưới bước giá vào `measure_band`; lệch lưới → `_undecided`.
4. UPCOM → undecided vĩnh viễn, ghi lý do vào docstring.
5. Nối `band_pressure` dùng `close` (bằng `raw_close` ở phiên quyết được).
6. Fixture có phiên trần: khẳng định `limit_lock_days > 0` và
   `without_limit_locks()` thật sự loại phiên đó.
7. Đo tỉ lệ quyết được theo sàn/mã, ghi vào phase report.
8. `make test`.

## Success Criteria

- [ ] `band_pressure` trả số, không đọc FiinQuant
- [ ] Phiên lệch lưới nhận lý do có tên; UPCOM undecided vĩnh viễn, viết ra
- [ ] **`limit_lock_days > 0`** trên fixture có phiên trần — cổng thứ hai đã mở thật
- [ ] `without_limit_locks()` loại đúng phiên trần trên fixture đó
- [ ] Tỉ lệ quyết được theo sàn ghi vào phase report
- [ ] `make test` xanh

## Risk Assessment

- **Trên-lưới không chứng minh chưa rebase.** *Tín hiệu:* một mã vừa chia tách mà
  mọi phiên vẫn "quyết được". *Phản ứng:* đã khai là điều kiện cần-không-đủ; nếu
  cần chắc hơn thì cộng thêm điều kiện "không có dòng CA cho mã này trong cửa sổ"
  — nhưng **không** dùng riêng nó, vì bảng rỗng cho 98% mã.
- **Biên độ sàn có ngoại lệ.** Ngày giao dịch không hưởng quyền, phiên chào sàn,
  cổ phiếu bị kiểm soát, **và chuyển sàn** (`EXCHANGE_MIGRATIONS` đang rỗng cố ý
  — `price_band.py:190-192` — nên band lịch sử dùng sàn *hôm nay*). *Tín hiệu:*
  verdict sai tập trung quanh các ca đó. *Phản ứng:* thêm vào danh sách undecided;
  từ chối có tên vẫn đúng hơn một verdict sai.
- **Tỉ lệ quyết được thấp bất ngờ.** *Tín hiệu:* < 80% trên HOSE. *Phản ứng:*
  đưa số cho user — có thể field này nên nhận refusal vĩnh viễn thay vì phục vụ
  một phần. Quyết định thuộc user, không tự chọn.
