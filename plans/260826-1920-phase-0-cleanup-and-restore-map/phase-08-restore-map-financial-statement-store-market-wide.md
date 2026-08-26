---
title: "Phase 8: Restore map — financial statement store market-wide"
status: reference-only
---

# Phase 8: Restore map — financial statement store market-wide

## Overview

**Reference-only.** Ghi phạm vi backend cần để phục vụ Earnings Opportunity
Screener (brief `docs/Text.txt` line 169-385) — screener quét Q3/2026 toàn
thị trường HOSE+HNX (~1.200 doanh nghiệp) tìm cổ phiếu profit tăng mạnh mà
giá chưa phản ánh.

## Brief origin

`docs/Text.txt` line 169-385 (Earnings Opportunity Screener):
- Universe: HOSE + HNX (~1.200 mã)
- Period: quarterly (Q3/2026 mockup)
- Filter: Net Profit > 0, YoY Profit Growth > 20%, Price Change < 5%,
  exclude extraordinary profit
- Metric: absolute profit, YoY, price change, vs VNIndex, opportunity score
- Drill-down: earnings trend Q4/25 → Q3/26, why the gap (core profit /
  cash flow / margin / sector concern / foreign selling)

## Data cần

- Financial statement quarterly cho toàn HOSE+HNX
  - `net_profit_after_tax`
  - `net_profit_before_tax`
  - `revenue`
  - `operating_profit` (core)
  - `operating_cash_flow`
  - `gross_margin`
  - `net_margin`
  - `earnings_extraordinary_items` (loại core vs non-core)
- Time series ≥ 8 quý (2 năm) để tính YoY
- Publication date để filter "đã công bố"
- Foreign flow monthly + net selling 20d

## Module cần restore

- `src/stocks/financial/*` (toàn bộ dir) — hiện là shell rỗng
- `src/stocks/company/*` — company metadata (sector, exchange, listing date)
- Extend `src/stocks/providers/vnstock_provider.py` — financial statement endpoint
- Table `financial_statement`, `financial_ratio`, `earnings_calendar` (còn trong DB — reconnect)

## Universe scope

**Quan trọng**: hiện tại `universe.py` = 30 mã declared. Screener cần
~1.200 mã. Hai lựa chọn:

- **A.** Đổi `Universe.contains()` return True cho mọi mã trong `listing_roster`
  (toàn HOSE+HNX) → chi phí LLM lớn khi agent list top 10
- **B.** Chia hai concept: `Universe.declared` (30 mã ưu tiên đọc kỹ) +
  `Universe.market` (toàn HOSE+HNX cho screener) → khi agent gọi screener,
  đọc `market`; khi đọc field cụ thể cho 1 mã, cần `market.contains()`

Chọn B (Phase 10 restore map bàn tiếp).

## Signal fields mới cần đăng ký

- `earnings_yoy_growth` — quarterly / annual
- `earnings_absolute_qtr` — net profit quarter
- `core_earnings_share` — operating profit / total profit
- `earnings_quality_score` — cash flow / net profit
- `price_change_since_qtr_start`
- `relative_return_20d_vs_vnindex`
- `relative_return_20d_vs_sector`
- `opportunity_score` — công thức: earnings_growth * (1 - price_change) * quality * liquidity
- `foreign_flow_net_20d`

## Việc PHẢI KHÔNG làm

- Không build Screener React component
- Không build agent tool `screen_universe`
- Không hard-code opportunity score weights vào signal — score phải là 1 field độc lập, thay công thức không đụng lane chat

## Placeholder success criteria

- Financial statement store có ≥ 8 quý cho ≥ 1.100 mã (95% HOSE+HNX)
- 9 signal fields mới liệt kê trong `list_fields`
- Screener agent tool trả top 10 mã trong ≤ 2s cho query Q3/2026
- Có mechanism refetch khi mùa BCTC (cron mỗi ngày sau 17h)

## Risk cần lường trước

- **License vnstock**: financial statement toàn thị trường có nằm trong
  Bronze/Diamond scope không? Bronze 180 req/phút có kịp fetch 1.200 mã
  × 8 quý không? → cần kiểm license trước khi commit approach.
- **Storage**: 1.200 mã × 8 quý × ~40 field ≈ 384k row; nhỏ, không lo.
