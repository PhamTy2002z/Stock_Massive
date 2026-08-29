---
phase: 9
title: "Signal Field earnings.*"
status: done
priority: P2
effort: "1d"
dependencies: [1]
---

# Phase 09: Signal Field earnings.*

# (kế thừa mục 09b của plan 260826-2158-study-artifact-canvas)

> **Viết lại 2026-08-28 sau red-team.** Bản đầu chọn ba field dựa trên `net_revenue`
> và `net_margin` trong `financial_statement_line` — hai item đó có **0 dòng** ở
> bảng đó. Chúng chỉ có ở ratio store, nơi chỉ phủ 30 mã × **3 quý liên tiếp**,
> tức không đủ để tính bất kỳ so sánh cùng kỳ năm trước nào. Ba field mới chọn
> theo item đã đo là có thật và có độ sâu.

## Overview

Store BCTC quý dựng xong ở phase 09a của plan Study nhưng **chưa Signal Field nào
đọc**. Phase này mở đường từ store đó ra `get_field` — lane chat trả được số kết
quả kinh doanh, không chỉ số giá.

Không phụ thuộc phép xoá FiinQuant: nó không chạm `provider_snapshots`, `bars.py`,
hay price basis. Chỉ cần Phase 01 (mở freeze).

## Requirements

- Functional: ≥ 3 Signal Field `earnings.*`, đăng ký qua `registry.py`, phục vụ
  qua `serve_field`.
- Functional: refusal dùng ba mã đã có — `fundamental_not_stored`,
  `statement_line_missing`, `market_cap_absent` — trừ khi không mã nào trỏ đúng.
- Non-functional: golden test per-industry; **từ chối toàn cục là test đỏ**.

## Architecture

### Nguồn — đo 2026-08-28, không suy

| Bảng | Dòng | Mã | Kỳ |
|---|---|---|---|
| `financial_statement_line` | 302.528 | 1.235 | 2018-Q1 → 2026-Q2 (34 quý) |
| `financial_ratio_snapshot` | 4.152 | **30** | 2025-Q4 → 2026-Q2 (**3 quý**) |

Item có độ phủ thật trong `financial_statement_line`:

| item_id | mã | quý | từ |
|---|---|---|---|
| `eps_basic_vnd` | **1.235** | 34 | 2018-Q1 |
| `eps_diluted_vnd` | **1.235** | 34 | 2018-Q1 |
| `net_profit_loss_after_tax` | **1.222** | 34 | 2018-Q1 |
| `gross_profit` | **1.192** | 34 | 2018-Q1 |
| `net_revenue` | **0** | — | không tồn tại |
| `net_margin` | **0** | — | không tồn tại |

`net_revenue` không phải một dòng chuẩn ở bảng này — dòng doanh thu đi theo mẫu
biểu từng ngành: `revenue_in_brokerage_services` (42 mã),
`net_revenue_of_insurance_premium` (13), `revenue_from_real_estate_investment` (13)…
Đây chính là rủi ro R5 của plan Study, và nó có thật.

### Ba field, chọn theo item đo được

| Field | Đọc | Nói được gì |
|---|---|---|
| `earnings.eps_basic_yoy_pct` | `eps_basic_vnd`, cùng quý năm trước | EPS tăng/giảm bao nhiêu — 1.235 mã, 8 năm |
| `earnings.net_profit_yoy_pct` | `net_profit_loss_after_tax`, cùng quý năm trước | lợi nhuận sau thuế YoY — 1.222 mã |
| `earnings.gross_profit_trend` | `gross_profit`, chuỗi 4 quý | lãi gộp đang nở hay co — 1.192 mã |

Cả ba **không cần** `market_cap_vnd` — thứ đã mất cùng FiinQuant, và vốn đã null
ở 99,48% dòng FiinQuant từ trước. Chúng cũng không cần ratio store, nên không bị
kẹt ở 30 mã × 3 quý.

`pe_ratio`/`pb_ratio` **có sẵn** trong ratio store như số provider đã tính. Nếu
muốn thêm, đó là field đọc số provider — phải khai rõ trong `Provenance`, không
trộn với số tự tính, và chấp nhận độ phủ 30 mã × 3 quý.

### Ngành khác nhau, dòng khác nhau

Bốn item trên là dòng chuẩn xuyên ngành, nên đỡ được phần lớn bài toán mẫu biểu.
Nhưng vẫn phải kiểm: ngân hàng có `net_profit_loss_after_tax` không? bảo hiểm có
`gross_profit` không? Golden test per-industry trả lời, không phải giả định.

Khi dòng cần không có cho ngành đó → `statement_line_missing`. **Không** thay
bằng dòng gần giống.

### Không bump `registry_version()` bằng tay

`registry.py:1233-1237` ghi rõ: hàm này là SHA-256 **dẫn xuất** từ chính các
declaration, *"không bump bằng tay, vì một version phải nhớ bump là một version
rồi sẽ gọi sai registry, và nó nằm trong Evidence Manifest, nơi sai thì im lặng."*
Success criterion là **khẳng định nó đã đổi**, không phải sửa nó.

Lưu ý kèm cho Phase 04: digest chỉ phủ sáu declaration
(`name, unit, sign, claim, source, interpretation`) — `projection` không nằm
trong đó. Phase 04 đổi *field nào trả số* mà không đổi định danh registry; hoặc
đưa `projection` vào digest, hoặc viết ra vì sao không.

## Related Code Files

- Create: `apps/api/src/stocks/signals/earnings.py`
- Modify: `apps/api/src/stocks/signals/registry.py` (`_index():1171`, `REGISTRY:1186`)
- Modify: `apps/api/src/alpha/reasons.py`, `apps/web/src/lib/signal-issues.ts` (nếu cần mã mới)
- Read: `apps/api/src/stocks/financial/reads.py` (`lines_for:60`, `periods_for:45`,
  `latest_period:37`), `apps/api/src/stocks/signals/fundamentals.py`
- Tests: mỗi field một test có số + một test refusal; golden test per-industry

## Implementation Steps

1. Đọc `fundamentals.py` xem field kế toán hiện có đăng ký thế nào; theo khuôn đó.
2. Viết `earnings.py` với ba field; đọc qua `financial/reads.py`, không truy vấn
   thẳng bảng.
3. Đăng ký vào `_index()`.
4. Golden test per-industry: ≥ 1 ngân hàng, ≥ 1 sản xuất, ≥ 1 bất động sản, ≥ 1
   chứng khoán. **Test phải đỏ nếu field từ chối trên mọi ngành** — một refusal
   toàn cục cũng là "refusal có tên", nên tiêu chí cũ sẽ xanh giả.
5. Refusal: kiểm ba mã cũ có trỏ đúng nguyên nhân không; thêm mã mới chỉ khi không.
6. `make test` + bốn cổng web.

## Success Criteria

- [ ] 3 field `earnings.*` trả **số thật** cho ≥ 1 mã ở mỗi ngành đã test
- [ ] Golden test per-industry đỏ khi field từ chối toàn cục
- [ ] Mọi refusal trỏ đúng input thiếu, câu có ở cả API và web
- [ ] `registry_version()` **khác** trước/sau (khẳng định, không sửa tay)
- [ ] `make test` + bốn cổng web xanh

## Risk Assessment

- **Ánh xạ dòng theo ngành sai im lặng.** *Tín hiệu:* golden test ngân hàng cho
  giá trị vô lý hoặc 0. *Phản ứng:* `statement_line_missing`, đừng thay dòng.
- **Cùng quý năm trước không có.** Hai field YoY cần quý `Q(n)` của năm trước.
  34 quý từ 2018-Q1 là đủ cho mã cũ, không đủ cho mã mới niêm yết. *Tín hiệu:*
  refusal tập trung ở mã mới. *Phản ứng:* đó là `fundamental_not_stored`, đúng —
  không nới cửa sổ để lấp.
- **Ratio store quá hẹp nếu ai đó kéo field sang percentile.** 30 mã × 3 quý,
  trong khi `min_sample_for` = `max(ceil(0.6 × mẫu), 15)`. *Tín hiệu:* field
  percentile luôn refuse thiếu mẫu. *Phản ứng:* ba field này cố ý không phải
  percentile; giữ vậy cho tới khi ratio store phủ rộng hơn.
