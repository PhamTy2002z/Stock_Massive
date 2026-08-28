---
phase: 7
title: "MARKET_INDEX từ bar_daily series=index"
status: pending
priority: P3
effort: "4h"
dependencies: [3]
---

# Phase 07: MARKET_INDEX từ bar_daily series=index

> **Sửa 2026-08-28 sau red-team.** Bản đầu dựa vào R5 — "xoá FiinQuant thì mọi
> chuỗi chỉ số rỗng vĩnh viễn" — và vì thế chặn Phase 08. **R5 sai**:
> `provider_snapshots` có **0 dòng** capability `market_index` ở mọi source. Không
> có chuỗi nào để mất. Phase này **không còn chặn Phase 08**, và hạ xuống P3.

## Overview

Nếu vẫn làm, phase này nối `bar_daily` `series='index'` vào cổng đọc chung, để
Study/field tương lai có benchmark. Nó **không** làm field nào sống lại ngay.

## Requirements

- Functional: chuỗi VNINDEX phục vụ được từ `bar_daily`.
- Functional: quyết định basis cho series index viết thành câu (xem dưới).
- Non-functional: cùng cổng đọc như equity — không dựng đường thứ hai.

## Architecture

### Đo trước, đừng tin R5 cũ

```sql
SELECT capability, source, count(*) FROM provider_snapshots GROUP BY 1,2;
-- fundamental/vnstock 2854 · market/fiinquant 36528 · market/vnstock 31160
-- reference/vnstock 220 · valuation/fiinquant 35245
```

Không có dòng `market_index` nào. Và `prepare_bars(series=BarSeries.MARKET_INDEX)`
có **0 call site** trong `src/` hay `tests/` — chuỗi ký tự đó chỉ xuất hiện trong
một docstring (`cross_sectional.py:62`). Field duy nhất khai cần index,
`relative_strength.beta_vs_market_index`, trả `UNAVAILABLE` vô điều kiện
(`cross_sectional.py:316-325`), và Phase 04 cố ý giữ nguyên.

Nên: xoá FiinQuant **không mất gì** ở phía index. Phase 08 đi trước được.

### Phải tranh luận thẳng với một quyết định đã ghi

`providers/contracts.py:172-179` ghi rõ vì sao MARKET_INDEX **cố ý** không có
cover source: *"a vnstock index series would carry a basis that asserts a
rescaling nobody performed, and a window mixing it with the Main Source's would
be refused as `mixed_price_basis` for a seam that does not exist in the market."*

Mọi dòng index trong `bar_daily` là `adjusted_at_source` (3.991 dòng). Một chỉ số
**không thể** điều chỉnh corporate action — nhãn đó khẳng định một phép rebase
không ai thực hiện. Đó đúng là điều `contracts.py` từ chối.

Bản đầu ghi "kiểm `bars.py` không hỏi band/adjustment cho index — đã đúng". Nửa
đúng: `bars.py:696` không hỏi band/adjustment, nhưng cổng basis ở `:680-683` có
chú thích *"Asked of both series"* — nó **có** chạy cho index. Sau Phase 03 luật
mới cho phép toàn-adjusted, nên nó qua được; nhưng ý nghĩa của nhãn vẫn sai.

**Phase này phải quyết và ghi ra:** dòng index nên mang `price_basis` gì. Ba lựa
chọn — giữ `adjusted_at_source` và khai rằng với index nó nghĩa là "không áp
dụng"; thêm một giá trị basis thứ ba cho instrument không điều chỉnh được; hay
sửa ingest ghi nhãn khác. Không được lặng lẽ lật `contracts.py:172-179` bằng một
dòng đổi map.

### Vì sao vẫn đáng làm

`bar_daily` đã có **3.991 phiên VNINDEX từ 2010-08-31**, tươi tới 2026-08-27 —
sâu 15 năm. Chi phí phase này là đường nối, không phải dữ liệu. Nhưng nó là món
**tuỳ chọn**: không field nào chờ nó, nên xếp sau khi đường tới hạn đã thông.

Đơn vị: index là **điểm** (1.821,32), equity là VND. `vnstock_daily.py` đã quyết
scale theo `series` một lần lúc ingest (`models.py:425-427`). Không scale lại.

## Related Code Files

- Modify: `apps/api/src/stocks/signals/sessions.py` (nhánh MARKET_INDEX → `BarDaily`
  where `series='index'`)
- Modify: `apps/api/src/stocks/providers/contracts.py:172-179` (ownership + **ghi
  lý do đảo quyết định cũ**)
- Modify: `apps/api/src/stocks/signals/bars.py` (nhánh index qua cổng chung)
- Tests: chuỗi index đọc được · đơn vị là điểm · không hỏi band · basis đúng luật mới

## Implementation Steps

1. Quyết chuyện `price_basis` cho index; viết lý do vào `contracts.py` cạnh đoạn
   nó đảo. Không xoá đoạn cũ — sửa nó có ngày tháng.
2. Đổi ownership map: MARKET_INDEX main = vnstock. Chú ý
   `validate_distinct_sources` (`contracts.py:144-149`) raise khi `cover is main`.
3. Nối `sessions.py` nhánh index sang `bar_daily` `series='index'`.
4. Test đơn vị: giá trị ở thang điểm, không nhân 1000.
5. Đọc 250 phiên VNINDEX gần nhất; khẳng định không lỗ, giá trị hợp lý.
6. `make test`.

## Success Criteria

- [ ] Chuỗi VNINDEX đọc được từ `bar_daily`, không qua `provider_snapshots`
- [ ] Quyết định `price_basis` cho index ghi thành câu trong `contracts.py`
- [ ] Đơn vị là điểm; không có phép scale thừa
- [ ] MARKET_INDEX không còn khai fiinquant
- [ ] `make test` xanh

## Risk Assessment

- **Nhân đôi scale.** *Tín hiệu:* VNINDEX ra 1.821.320. *Phản ứng:* bước 4 bắt
  được; đừng bỏ test đó.
- **`validate_distinct_sources` raise lúc import.** VALUATION hiện
  `main=FIINQUANT, cover=VNSTOCK`; đổi main sang vnstock mà giữ cover là
  `cover is main` → raise. *Tín hiệu:* mọi test vỡ ở collection. *Phản ứng:* bỏ
  cover chứ không chỉ đổi main. (Phase 08 gặp cùng bẫy cho VALUATION.)
- **Lật quyết định cũ mà không ai biết.** *Tín hiệu:* `contracts.py:172-179` vẫn
  còn nguyên văn trong khi map đã đổi. *Phản ứng:* bước 1 là điều kiện, không
  phải thủ tục.
