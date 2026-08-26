---
title: "Phase 1: Kick-off and inventory verification"
status: todo
---

# Phase 1: Kick-off & inventory verification

## Overview

Xác nhận bức tranh nợ Phase 0 trước khi cắt. Không sửa gì code trong phase
này — chỉ chạy các lệnh kiểm kê để chứng minh phần "đã rip" trên CLAUDE.md
khớp với `git ls-files` hiện tại, và ghi ra file kê khai (`inventory.md`)
làm chứng cứ cho các phase sau.

## Requirements

- [ ] Đối chiếu section "Không còn tồn tại" trong CLAUDE.md với thực tế repo
- [ ] Liệt kê 8 dir `src/stocks/{analytics,company,financial,market,monitor,news,price,trading}` — xác nhận rỗng
- [ ] Liệt kê 12 signal module mồ côi + verify không có test riêng
- [ ] Liệt kê setting stale trong `src/core/config.py`
- [ ] Liệt kê alembic migration đã tạo bảng bị rip (candidate drop)
- [ ] Verify `backups/pre-rip-out-260825.sql.gz` tồn tại + size khớp (7.2M)

## Implementation Steps

1. Ghi `inventory.md` cạnh `plan.md` với 5 mục:
   - **Empty stocks dirs**: `find src/stocks -type d -empty`
   - **Orphan signals**: 12 module + số reverse-imports (đang là 0)
   - **Stale settings**: grep trong `src/core/config.py`
   - **Alembic drop candidates**: tên bảng theo file migration
   - **Backup**: `ls -la backups/`, `sha256sum backups/pre-rip-out-260825.sql.gz`
2. Chạy `make test` để chốt baseline 940 pass, `pnpm test` để chốt 406 pass.
3. Ghi HEAD commit + `git log --oneline -3` vào `inventory.md`.

## Todo

- [ ] Ghi `plans/260826-1920-.../inventory.md`
- [ ] Commit `docs(plans): record Phase 0 cleanup inventory` (chỉ inventory + plan)

## Success Criteria

- `inventory.md` chứa đủ 5 mục với output lệnh làm chứng
- `make test` xanh (940 pass), `pnpm test` xanh (406 pass)
- HEAD được ghi vào inventory để rollback trỏ đúng
