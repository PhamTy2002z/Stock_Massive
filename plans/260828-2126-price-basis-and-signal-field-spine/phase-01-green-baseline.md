---
phase: 1
title: "Mở freeze và chốt nền"
status: done
priority: P1
effort: "2h"
dependencies: []
---

# Phase 01: Mở freeze và chốt nền

> **Viết lại 2026-08-28 sau red-team.** Bản đầu liệt kê 15 test đỏ và một hàm
> chết cần xoá. Đo lại: cổng đã xanh hết, và hàm đó không tồn tại — cái gần tên
> nhất (`plainLocale`) **đang sống**, xoá nó là hỏng mọi con số trong Signal Desk.
> Việc thật của phase này là thứ bản đầu bỏ sót: **mở freeze**.

## Overview

Plan này sửa bảy surface mà `CLAUDE.md` tuyên bố đang freeze. Không có amendment
thì Phase 03 đổ một bản viết lại gateway signals vào một vùng repo tuyên bố cấm
sửa, và người review đúng luật phải từ chối. Phase này mở freeze **trước**, có
giới hạn viết ra, rồi chốt nền xanh để mọi phép so sau này có mốc.

## Requirements

- Functional: `CLAUDE.md` liệt kê đủ bảy surface plan này mở, kèm giới hạn.
- Functional: working tree sạch; năm cổng xanh và ghi lại con số làm mốc.
- Non-functional: **không** đổi hành vi nào. Phase này không sửa code sản phẩm.

## Architecture

### Bảy surface phải mở

`CLAUDE.md` §"Hard freeze ngoài `src/agent/*`" ghi: *"Phần còn lại của
`src/stocks/*` — `realtime/*`, `signals/*`, `providers/{contracts,normalize,store}`,
`models.py` ngoài bảng mới — vẫn freeze."* Plan này sửa:

| Surface | Phase | Giới hạn |
|---|---|---|
| `stocks/trading_day.py` | 02 | đổi nguồn lịch, giữ nguyên chữ ký |
| `stocks/signals/{sessions,bars}.py` | 03, 05, 06 | chuyển nguồn + luật basis; không thêm field |
| `stocks/signals/corporate_actions.py` | 03 | vá R4; không đổi công thức hệ số |
| `stocks/signals/{price_band,market_behavior}.py` | 06 | cổng basis thứ hai + band |
| `stocks/signals/{registry,serving,issues,cross_sectional,foreign_flow}.py` | 04 | khai projection + refusal |
| `stocks/providers/{contracts,store}.py` | 03, 08 | gỡ FiinQuant khỏi ownership |
| `stocks/schemas/snapshot.py` | 08 | gỡ echo REST |

Phase 09 thêm một surface nữa (`signals/earnings.py` mới) — cũng khai ở đây, để
amendment là một lần chứ không rải rác.

**Không mở:** `realtime/*` ngoài hai file enum ở Phase 08, `providers/normalize.py`,
và `models.py` ngoài bảng mới. Nếu Phase 08 thấy phải đụng chúng thì đó là tín
hiệu dừng, không phải cái để mở thầm.

### Nền hiện tại — đo 2026-08-28 21:5x

| Cổng | Kết quả |
|---|---|
| `make test` (api) | ✅ **1284 passed** |
| `pnpm type-check` | ✅ |
| `pnpm lint` | ✅ sạch |
| `pnpm test` (web) | ✅ **616 passed / 50 file** |
| Bản production web | chưa chạy — `pnpm dev` đang mở, phải dừng trước |

Working tree: **174 file** thay đổi, **67** untracked, gồm ba alembic revision
(`d4a71c9e5b82`, `e6b3d90c41af`, `f8c2d4a96e17`) đã apply lên DB container nhưng
chưa vào git. Mọi lời hứa "backup restore được" ở Phase 08 giả định schema tái
tạo được từ code đã commit; hôm nay thì chưa.

## Related Code Files

- Modify: `CLAUDE.md` (amendment freeze; mục "Không còn tồn tại" giữ nguyên)
- Modify: `docs/roadmap.md` (§S0 — kiểm trước, `:286` đã ghi `Current / đang đóng`)
- Modify: `plans/260826-2158-study-artifact-canvas/plan.md` (đã trỏ 08b/09b sang
  plan này ở lần sửa trước; xác nhận lại)
- Commit: 174 file đang chờ, **ưu tiên ba alembic revision**

## Implementation Steps

1. Viết amendment freeze vào `CLAUDE.md` theo bảng trên, kèm ngày và tên plan.
2. Dừng `pnpm dev`, chạy cổng production web, khởi động lại dev.
3. Chạy lại năm cổng, **ghi con số vào phase report** — đây là mốc mọi phase sau
   so vào.
4. Commit theo conventional commits, tách nhóm (alembic + studies core · agent
   tools · web surface · plans/docs). Ba revision đi trong commit riêng, đầu tiên.
5. Đọc `docs/roadmap.md:286` trước khi sửa — nếu đã là `Current` thì chỉ tick hai
   checklist còn lại (contract test transcript đã có ở
   `tests/test_agent_study_tools.py:179,212`), đừng sửa cái đã đúng.
6. `git status --porcelain` phải rỗng.

## Success Criteria

- [ ] `CLAUDE.md` liệt kê đủ tám surface (bảy + `signals/earnings.py`) kèm giới hạn
- [ ] Năm cổng xanh, con số ghi vào phase report làm mốc
- [ ] `git status --porcelain` rỗng; ba alembic revision đã vào git
- [ ] `docs/roadmap.md` §S0 đúng trạng thái (kiểm trước khi sửa)

## Risk Assessment

- **Amendment mở quá rộng.** Freeze mất tác dụng nếu amendment chỉ ghi
  "`src/stocks/*` mở cho plan này". *Tín hiệu:* PR trong plan sửa file không có
  trong bảng. *Phản ứng:* bảng là ranh giới; file ngoài bảng cần amendment mới,
  không phải một dòng nới.
- **Cổng production web phá `.next` của dev.** *Tín hiệu:* web mất CSS sau khi
  chạy. *Phản ứng:* đã biết — dừng dev trước, restart sau.
- **Ba alembic revision đã apply nhưng chưa commit.** Nếu commit sót, Phase 08
  không tái tạo được schema để restore vào DB tạm. *Tín hiệu:* `alembic heads`
  trên bản checkout sạch không ra `f8c2d4a96e17`. *Phản ứng:* bước 4 đặt chúng ở
  commit đầu tiên chính vì lý do này.
