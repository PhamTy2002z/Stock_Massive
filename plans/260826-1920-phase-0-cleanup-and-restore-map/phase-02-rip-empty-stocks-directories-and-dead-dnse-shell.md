---
title: "Phase 2: Rip empty stocks directories and dead dnse shell"
status: todo
---

# Phase 2: Rip empty stocks directories & dead dnse shell

## Overview

Xoá 8 directory `src/stocks/*` chỉ còn `__pycache__` sau Phase 0, cùng
`src/stocks/realtime/dnse/` cũng chỉ còn `__pycache__`. Đây là "vỏ rỗng" —
không có `.py` nào, `__init__.py` cũng bỏ; giữ lại chỉ làm nhiễu grep và làm
docs/CLAUDE.md nói dối.

## Requirements

- Xoá đúng 9 dir; không đụng `stocks/{providers,realtime,signals,schemas,shared,models,universe.py,trading_day.py,listing_roster.py}`.
- Sau khi rm, `import src.stocks` vẫn OK (do các dir đã xoá không được re-export ở `stocks/__init__.py`).
- `make test` xanh.

## Related Code Files

- Delete:
  - `apps/api/src/stocks/analytics/`
  - `apps/api/src/stocks/company/`
  - `apps/api/src/stocks/financial/`
  - `apps/api/src/stocks/market/`
  - `apps/api/src/stocks/monitor/`
  - `apps/api/src/stocks/news/`
  - `apps/api/src/stocks/price/`
  - `apps/api/src/stocks/trading/`
  - `apps/api/src/stocks/realtime/dnse/`

## Implementation Steps

1. `cd apps/api && for d in src/stocks/{analytics,company,financial,market,monitor,news,price,trading} src/stocks/realtime/dnse; do git rm -rf "$d" 2>/dev/null || rm -rf "$d"; done`
2. Verify không còn: `find src/stocks -type d -empty` phải rỗng.
3. Grep sanity: `grep -rn "src.stocks.\(analytics\|company\|financial\|market\|monitor\|news\|price\|trading\)\b" src/ tests/` phải rỗng.
4. Note: `stocks/trading_day.py` (single file) và tests giữ nguyên — khác `trading/` dir.
5. Chạy `make test`.

## Todo

- [ ] Xoá 9 directory
- [ ] Test xanh 940
- [ ] Commit `refactor(api): rip empty stocks shells left by Phase 0`

## Success Criteria

- 9 dir không còn trên disk và trong git tree
- Test 940 pass, không có new failure
- Không có file nào import từ 9 dir đó (kiểm bằng grep sau khi rm)
