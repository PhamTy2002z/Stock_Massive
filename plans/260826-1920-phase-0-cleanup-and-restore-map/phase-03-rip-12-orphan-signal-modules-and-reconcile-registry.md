---
title: "Phase 3: Rip 12 orphan signal modules and reconcile registry"
status: done (only nulls removed; 11 modules verified live)
---

# Phase 3: Rip 12 orphan signal modules & reconcile registry

## Overview

12 module trong `src/stocks/signals/` không được import bởi bất kỳ file nào
trong `src/agent/`, `src/alpha/`, hay chính `src/stocks/signals/*.py`, và
không có test riêng. Chúng là code chết còn sót lại từ trước Phase 0.

**Cảnh báo:** một số module (`indicators`, `foreign_flow`, `fundamentals`)
có thể register fields vào `SIGNAL_REGISTRY` — nếu vậy, fields cũng chết
theo. Kiểm registry trước khi rm.

## Requirements

- Chứng minh 12 module không đóng góp field runtime nào (grep `SIGNAL_REGISTRY.register` bên trong)
- Sau khi rm, `list_fields` tool trả về đúng bộ field lane chat đang phục vụ
- Test 940 pass (nếu có test dùng field từ module rip → sửa test hoặc restore module)

## Related Code Files

- Delete:
  - `apps/api/src/stocks/signals/corporate_actions.py`
  - `apps/api/src/stocks/signals/cross_sectional.py`
  - `apps/api/src/stocks/signals/foreign_flow.py`
  - `apps/api/src/stocks/signals/foreign_share_flow.py`
  - `apps/api/src/stocks/signals/fundamentals.py`
  - `apps/api/src/stocks/signals/indicators.py`
  - `apps/api/src/stocks/signals/market_behavior.py`
  - `apps/api/src/stocks/signals/moments.py`
  - `apps/api/src/stocks/signals/nulls.py`
  - `apps/api/src/stocks/signals/reference.py`
  - `apps/api/src/stocks/signals/risk.py`
  - `apps/api/src/stocks/signals/volatility.py`
- Modify: `apps/api/src/stocks/signals/registry.py` (nếu import từ 12 file trên)
- Modify: `apps/api/src/stocks/signals/__init__.py` (đã trống, verify không re-export)

## Implementation Steps

1. **Chứng minh mồ côi**: `grep -l "SIGNAL_REGISTRY.register\|register_field" src/stocks/signals/{corporate_actions,cross_sectional,foreign_flow,foreign_share_flow,fundamentals,indicators,market_behavior,moments,nulls,reference,risk,volatility}.py`
2. Nếu có register: liệt kê tên field. Đối chiếu `list_fields` output — nếu không xuất hiện với `AVAILABLE` thì mồ côi thật.
3. Grep import ngược 1 lần nữa cho chắc: `grep -rn "from src.stocks.signals.\(<name>\)" src/ tests/`
4. `git rm src/stocks/signals/{...}.py`
5. Sửa `signals/registry.py` nếu có import từ 12 file: bỏ import, bỏ registration call.
6. Chạy `make test -k signal` trước, `make test` full sau.

## Todo

- [ ] Chạy grep chứng minh 12 mồ côi
- [ ] Ghi kết quả grep vào commit message
- [ ] `git rm` 12 file
- [ ] Sửa `registry.py` nếu cần
- [ ] Test signal xanh, test full xanh
- [ ] Commit `refactor(signals): remove 12 orphan signal modules`

## Success Criteria

- 12 file không còn trên disk
- `signals/registry.py` không import từ tên nào bị rip
- `make test` 940 pass
- `list_fields` tool runtime trả về danh sách field bằng đúng bộ trước khi rip

## Risk

- **Assumption có thể vỡ**: một module tưởng mồ côi thực ra register field
  hiếm dùng nhưng có test integration. **Signal**: `make test -k signal` đỏ
  sau bước rm. **Response**: revert file đó, chuyển sang "quarantine list"
  trong CLAUDE.md và giữ nguyên; phase vẫn continue với các file còn lại.
