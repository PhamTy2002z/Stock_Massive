---
title: "Phase 6: Tidy Phase 1 stub, push archive tag, refresh CLAUDE.md"
status: done
---

# Phase 6: Tidy Phase 1 stub, push archive tag, refresh CLAUDE.md

## Overview

Phase 1 domain pack đã bị hoãn vì brief `docs/Text.txt` (canvas dynamic) đảo
định hướng. Stub đã ghi (`plans/260826-1909-phase-1-domain-pack/` +
`src/agent/domain/pack.py`) chưa commit — bỏ đi. Đồng thời chốt Phase 0
+ Phase Cleanup này bằng cách push tag archive và cập nhật CLAUDE.md khớp
đúng thực tế repo.

## Requirements

- Xoá đúng stub Phase 1 (không xoá thư mục Phase 0 hay plan khác)
- Tag `v-with-market-surfaces` push lên `origin` (rollback point trước rip)
- CLAUDE.md:
  - Cập nhật "Không còn tồn tại" ghi thêm lần này (8 stocks dirs, dnse dir, 12 signal modules, config settings, alembic drop)
  - Sửa "Roadmap harness": Phase 1 (domain pack) đổi thành **hoãn**; thêm nhánh "Định hướng canvas dynamic (brief docs/Text.txt)" — chưa thi công, chỉ tham chiếu
  - Khớp lại "Commands", "Tooling", "Không được đụng" nếu có mục lỗi
- Test 940/406 vẫn xanh; startup docker healthy

## Related Code Files

- Delete:
  - `plans/260826-1909-phase-1-domain-pack/` (toàn bộ)
  - `apps/api/src/agent/domain/pack.py`
  - `apps/api/src/agent/domain/vn_equity/` nếu đã tạo (chưa có phần này)
- Modify: `CLAUDE.md`

## Implementation Steps

1. **Verify stub chưa commit**: `git status --short | grep -E "phase-1-domain-pack|agent/domain"` — phải hiện `??`.
2. `rm -rf plans/260826-1909-phase-1-domain-pack apps/api/src/agent/domain`
3. **Cập nhật CLAUDE.md**:
   - Trong "# Không còn tồn tại", thêm block mới `**2026-08-26 (Phase 0 cleanup):**` liệt kê chính xác 8 stocks dirs + dnse + 12 signal + settings + bảng đã drop
   - Trong "# Roadmap harness":
     - "Phase 1 (kế tiếp)" → "Phase 1 (**hoãn**) — domain pack; chờ quyết định về brief `docs/Text.txt`"
     - Thêm section mới: "## Định hướng đang chờ quyết định — canvas dynamic" — 1 đoạn ngắn nói brief này thay/bổ sung roadmap, link `plans/260826-1920-phase-0-cleanup-and-restore-map/plan.md` phase 7-10 làm restore map, và câu hỏi user cần trả lời trước khi động tiếp
4. **Test gate**: `make test` (940), `pnpm type-check && pnpm lint && pnpm test && pnpm build`, `docker compose up -d api` healthy.
5. **Push tag** (chờ user OK):
   - `git tag -l v-with-market-surfaces` xác nhận exist local
   - **Gate**: hỏi user "OK push tag `v-with-market-surfaces` lên origin không?" trước khi push
   - Nếu OK: `git push origin v-with-market-surfaces`
6. **Commit**:
   - `refactor: drop Phase 1 domain pack stub while direction is reconsidered`
   - `docs(claude): record Phase 0 cleanup and pending direction on canvas dynamic`

## Todo

- [ ] Xoá stub Phase 1
- [ ] Refresh CLAUDE.md
- [ ] Test full 940 + 406 xanh
- [ ] Hỏi user OK push tag
- [ ] Push tag nếu OK
- [ ] Commit 2 commit theo thứ tự

## Success Criteria

- `git status --short` sạch (chỉ còn plan file mới)
- CLAUDE.md "Không còn tồn tại" liệt kê đúng những gì Phase 0 cleanup xoá
- CLAUDE.md "Roadmap harness" ghi Phase 1 hoãn + brief canvas dynamic
- `git tag -l v-with-market-surfaces` trong `git ls-remote --tags origin` (chỉ nếu user OK push)
- Test full xanh
- Startup docker healthy

## Risk

- **Tag đã có ai đó clone**: **Signal**: `git push origin :v-with-market-surfaces` báo protected. **Response**: giữ tag local; không cưỡng push.
- **CLAUDE.md drift**: dễ ghi sai tên module đã xoá. **Response**: bước 3 phải dùng output từ `git log --stat` của các commit rip; không viết bằng trí nhớ.
