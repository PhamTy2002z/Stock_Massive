---
title: "Phase 9: Restore map — market indices and sector membership"
status: reference-only
---

# Phase 9: Restore map — market indices & sector membership

## Overview

**Reference-only.** Ghi phạm vi backend cho Buy Decision View, Stock Detail
Drill, Peer Comparison — cả 3 view brief đều cần VNIndex + sector index +
peer membership.

## Brief origin

- `docs/Text.txt` line 388-554 (Buy Decision cho STB @ 74.6k):
  - 52W high / low
  - Support / resistance zones (auto-suggest ~71-72.5k / ~76-77k)
  - Sacombank sector = Bank → peer MBB, TCB, CTG
  - H1/2026 profit, NPL 7.5%, plan completion %
  - Restructuring / VAMC catalyst timeline
- `docs/Text.txt` line 297-352 (Stock Detail Drill STK03):
  - Earnings trend Q4/25 → Q3/26
  - Stock price series overlay
  - Relative return vs VNIndex + Sector
- `docs/Text.txt` line 546-550 (Peer Comparison STB vs MBB vs TCB):
  - Bank sector ranking

## Data cần

- **Indices**:
  - VN-Index intraday + daily
  - VN30, HNX-Index, HNX30 (nếu dùng)
  - Sector index (VNBANK, VNREAL, VNSEC, ...)
- **Sector membership**:
  - Symbol → sector mapping
  - Symbol → industry (sub-sector)
  - Update khi cổ phiếu re-classify
- **52W high/low**:
  - Field derived từ `bar_daily` (1 năm rolling)
- **Support/Resistance auto**:
  - Local minima/maxima trên bar_daily 60-90 phiên
  - Hoặc: volume-weighted price level clustering

## Module cần restore

- `src/stocks/market/*` (dir đã rip Phase 2, restore lại core)
- `src/stocks/market_index.py` (nếu file rời)
- Sector membership store (chưa có standalone, có thể nằm trong `company`)
- `src/stocks/sector_historical.py` — sector index series (rút gọn, không cần "historical dashboard")
- Extend `providers/vnstock_provider.py` cho index series + sector mapping
- Table `market_index_daily`, `market_index_intraday`, `sector_membership`

## Signal fields mới

- `52w_high`, `52w_low`, `52w_range_position` (% from low to high)
- `support_zone_1`, `support_zone_2`, `resistance_zone_1`, `resistance_zone_2` — mỗi zone: (low, high, strength)
- `vnindex_relative_return_20d`, `vnindex_relative_return_60d`
- `sector_relative_return_20d`
- `sector_membership` — sector code
- `peer_list` — top N mã cùng sector theo market cap
- `plan_completion_percent` — H1 profit / annual plan (from company disclosures)

## Việc PHẢI KHÔNG làm

- Không build support/resistance chart component
- Không build peer comparison canvas
- Không tự viết clustering algorithm phức tạp — dùng scipy peak-finding hoặc
  quantile-based level detection

## Placeholder success criteria

- VN-Index + 10 sector index có bar_daily + intraday
- Sector membership cover 100% Universe (30 declared) + ≥ 90% HOSE+HNX
- 8+ signal fields mới hoạt động với `check_price_claim` + `get_field`
- Peer list trả 5 mã cùng sector cho mỗi mã Universe
