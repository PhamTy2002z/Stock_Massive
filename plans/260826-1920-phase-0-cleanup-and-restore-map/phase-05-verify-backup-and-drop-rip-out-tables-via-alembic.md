---
title: "Phase 5: Verify backup and drop rip-out tables via alembic"
status: done
---

# Phase 5: Verify backup & drop rip-out tables via alembic

## Overview

CLAUDE.md ghi rõ: "revision drop tách ra sang PR sau khi backup đã xác minh
restore được". Phase này thi hành. Verify `backups/pre-rip-out-260825.sql.gz`
restore được vào một DB tạm, rồi mới viết alembic revision drop các bảng
của feature đã rip.

## Requirements

- Backup restore verified bằng `pg_restore --list` + `psql` count vài bảng chính
- Revision alembic mới: một revision drop toàn bộ bảng của feature đã rip (đặt tên "drop tables orphaned by Phase 0 rip-out")
- `alembic upgrade head` xanh trên DB dev; `alembic downgrade -1` phải revert được (drop → create trở lại) — hoặc ghi rõ downgrade **không được hỗ trợ**, chỉ restore từ backup
- Test 940 pass sau upgrade

## Related Code Files

- Create: `apps/api/alembic/versions/<hash>_drop_tables_orphaned_by_phase_0.py`
- Verify (không sửa):
  - `apps/api/alembic/versions/dbd106456567_add_the_nine_alpha_desk_tables.py`
  - `apps/api/alembic/versions/a3c7e21b8f65_add_the_analysis_tool_call_trace_table.py`
  - `apps/api/alembic/versions/c8f2a6d31e04_add_realtime_ingestion_spine.py`
  - `apps/api/alembic/versions/e7a2c9b41f58_profit_census_and_cohort_versions.py`
  - `apps/api/alembic/versions/dd*` etc — mọi migration tạo bảng phải xác định trạng thái

## Candidate tables cần drop

Theo CLAUDE.md "Không còn tồn tại" + tên migration:

| Bảng | Nguồn migration | Ghi chú |
|------|-----------------|---------|
| `alpha_desk_*` (9 bảng) | `dbd106456567` | Alpha desk lane rip |
| `analysis_tool_call_trace` | `a3c7e21b8f65` | Analysis lane rip |
| `analysis_run` | `f3b0d7c15a92` | Analysis lane rip |
| Realtime spine tables (bar, trade, metric, snapshot...) | `c8f2a6d31e04` | DNSE spine rip |
| Reconciliation audit | `e2c4a7d19b63` | Realtime rip |
| Profit census + cohort versions | `e7a2c9b41f58` | Cohort seating bỏ |
| Market monitor snapshot | (search) | Monitor rip |
| Watchlist | (search) | Watchlist rip |
| Sector historical | (search) | Sector historical rip |
| Price history intraday | (search) | Intraday collector rip |

**Danh sách chính xác được xác lập trong Step 2 dưới đây** — không hard-code
tên bảng vào phase này, xác định bằng `\dt` trên DB dev sau khi restore.

## Implementation Steps

1. **Verify backup restore**:
   - `mkdir -p /tmp/restore_check && cd /tmp/restore_check`
   - `gunzip -c /Users/typham/Dev/Stock_Massive/backups/pre-rip-out-260825.sql.gz > pre-rip.sql`
   - `docker compose exec db psql -U stock -c 'CREATE DATABASE restore_check;'`
   - `docker compose exec -T db psql -U stock -d restore_check < pre-rip.sql`
   - `docker compose exec db psql -U stock -d restore_check -c '\dt' | tee /tmp/pre-rip-tables.txt`
   - Diff với `docker compose exec db psql -U stock -d stock_massive -c '\dt'` để lấy list bảng "còn trong DB main nhưng không thuộc bộ core"
2. **Xác định bộ core còn dùng**: đọc `src/stocks/models.py`, `src/agent/persistence.py`, `src/auth/*/models.py`, `alembic/versions/*` cho migration KHÔNG bị rip. Bộ này giữ.
3. **Lập danh sách bảng drop**: pre-rip tables ∩ (KHÔNG bộ core).
4. **Ghi revision**:
   - `cd apps/api && alembic revision -m "drop tables orphaned by Phase 0 rip-out"`
   - Điền `def upgrade():` với `op.drop_table(...)` từng bảng
   - Điền `def downgrade():` với `raise NotImplementedError("restore from backups/pre-rip-out-260825.sql.gz")` — không tự tạo lại schema đã rip
5. **Chạy**:
   - `alembic upgrade head`
   - `\dt` xác nhận drop xong
   - `make test` full → xanh
6. **Xoá DB tạm**: `DROP DATABASE restore_check;`

## Todo

- [ ] Verify backup restore vào `restore_check` DB
- [ ] Diff bảng để xác định danh sách drop
- [ ] Viết alembic revision drop
- [ ] `alembic upgrade head` trên DB dev
- [ ] `make test` xanh
- [ ] Commit `feat(db): drop tables orphaned by Phase 0 rip-out`

## Success Criteria

- Backup restore verified trên DB tạm; các bảng gốc đều load
- Alembic revision mới có tên bảng chính xác; `upgrade` xanh; `downgrade` raise NotImplementedError
- DB dev sau `upgrade head`: `\dt` chỉ còn bộ core (auth, agent, alpha shim, stocks core, universe, threads)
- `make test` 940 pass sau upgrade
- Không tự tay drop bảng — mọi thao tác phải qua alembic

## Risk

- **Bảng bị drop nhưng còn code đọc**: model class chưa xoá kịp. **Signal**: test đỏ với `UndefinedTableError`. **Response**: revert revision (`alembic downgrade` không được → restore từ backup), rồi bổ sung code cleanup trước khi retry.
- **Backup không restore được**: **Signal**: `pg_restore` báo lỗi. **Response**: **Dừng phase**, chuyển user quyết định — không drop khi không có rollback.
