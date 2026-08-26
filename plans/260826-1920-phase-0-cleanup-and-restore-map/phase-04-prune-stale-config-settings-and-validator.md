---
title: "Phase 4: Prune stale config settings and validator"
status: done
---

# Phase 4: Prune stale config settings & validator

## Overview

`src/core/config.py` còn hàng chục setting chỉ phục vụ code đã bị rip:
FiinQuant credentials, DNSE realtime spine, backfill/warmup lanes, alpha
desk toggles, `_complete_realtime_configuration` validator. Sau Phase 0
chúng không có ai đọc; giữ lại làm cấu hình lừa dối và env-example lừa dối.

## Requirements

- Xoá đúng những setting không còn ai đọc; không đụng setting còn dùng (LLM, budget, DB, Redis, JWT, universe, agent, tenant)
- Cập nhật `.env.example` bỏ tương ứng
- Test 940 pass

## Related Code Files

- Modify: `apps/api/src/core/config.py`
- Modify: `apps/api/.env.example`
- Modify: `apps/api/README.md` nếu có nhắc setting đã rip

## Danh sách setting bị rip (theo grep hiện tại)

| Setting | Vị trí | Ghi chú |
|---------|--------|---------|
| `fiinquant_username`, `fiinquant_password` | line 44-46 | FiinQuant vi phạm ToS, không dùng lại |
| `realtime_ingestion_enabled` | line 56 | DNSE spine đã rip; restore vnstock sau sẽ dùng tên khác |
| `dnse_api_key`, `dnse_api_secret`, `dnse_board_ids` | line 57-59 | DNSE ToS violation |
| `realtime_queue_size`, `realtime_worker_count`, `realtime_shutdown_timeout_seconds` | line 60-62 | spine config, spine đã rip |
| `backfill_enabled`, `backfill_hour`, `backfill_minute`, `backfill_symbols_per_run`, `backfill_depth_days`, `backfill_main_source_days` | line 128-142 | backfill lane đã rip |
| `warmup_window_trading_days` | line 160-163 | warmup lane đã rip |
| `alpha_desk_enabled`, `alpha_desk_suggestions_enabled` | line 232, 282 | alpha desk lane đã rip |
| `_complete_realtime_configuration` validator | line 398-403 | validator DNSE, không còn field để verify |

## Implementation Steps

1. Grep chéo: cho mỗi setting, `grep -rn "settings\.<name>\|\.settings\.<name>" src/ tests/` → phải rỗng trước khi rm.
2. Xoá field từ `Settings` class.
3. Xoá validator `_complete_realtime_configuration` (nó chỉ tồn tại để verify DNSE fields).
4. Xoá dòng tương ứng trong `.env.example`.
5. Grep sạch trong `apps/api/README.md`, `apps/api/docs/` (nếu còn); xoá dòng dead.
6. `make test`.

## Todo

- [ ] Grep chéo từng setting → confirm 0 caller
- [ ] Xoá 15+ field khỏi `Settings`
- [ ] Xoá validator `_complete_realtime_configuration`
- [ ] Update `.env.example`
- [ ] Test xanh 940
- [ ] Commit `refactor(config): drop settings orphaned by Phase 0`

## Success Criteria

- `grep -inE "dnse|fiinquant|alpha_desk|realtime_ingestion|realtime_queue|realtime_worker|backfill|warmup" src/core/config.py` trả rỗng
- Startup Docker `api` container: `docker compose up -d api` healthy; log không có warning "unused settings"
- `make test` 940 pass

## Risk

- **Env override**: nếu môi trường prod/CI có set `DNSE_API_KEY=...` như env var và setting bị rm, Pydantic sẽ **fail** vì extra field. **Signal**: startup crash `ValidationError`. **Response**: `Settings.Config.extra = "ignore"` (nếu chưa) hoặc grep CI/CD secrets và xoá tương ứng — nhưng repo này chưa push, chưa có CI cụ thể.
