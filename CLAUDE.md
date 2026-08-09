# CLAUDE.md — Stock_Massive

Nền tảng dữ liệu chứng khoán Việt Nam (HOSE/HNX/UPCOM). pnpm monorepo.

## Cấu trúc

- `apps/web` — Next.js + TypeScript (frontend)
- `apps/api` — FastAPI + SQLAlchemy + Alembic (backend), nguồn dữ liệu vnstock
- `docker/`, `docker-compose.yml` — stack dev local (web, api, db Postgres, redis)
- `plans/` — kế hoạch triển khai; `docs/` — tài liệu dự án

## Lệnh thường dùng

Chạy từ repo root:

| Việc | Lệnh |
|---|---|
| Chạy toàn bộ stack dev | `pnpm dev` (docker compose up --build) |
| Dừng / dừng + xóa volume | `pnpm stop` / `pnpm stop:clean` |
| Xem log api / web | `pnpm logs:api` / `pnpm logs:web` |
| Shell Postgres | `pnpm db:shell` (psql, db `stockmassive`) |

Backend (`apps/api`, dùng Makefile — tự chọn `.venv` nếu có):

| Việc | Lệnh |
|---|---|
| Dev server (hot reload, port 8000) | `make dev` |
| Test | `make test` (pytest tests/ -v) |
| Migration | `alembic upgrade head` / `alembic revision --autogenerate -m "..."` |

Frontend (`apps/web`):

| Việc | Lệnh |
|---|---|
| Type check | `pnpm type-check` (tsc --noEmit) |
| Lint | `pnpm lint` |
| Build | `pnpm build` |

## Quy tắc bắt buộc

- **Worktree**: mọi tính năng/sửa lỗi làm trong git worktree, không commit trực tiếp main.
- **Kiểm tra trước khi báo xong**: backend phải pass `make test`; frontend phải pass `type-check` + `build`. Nêu rõ phần chưa kiểm tra được.
- **Không commit**: secrets, `.env`, dữ liệu nhạy cảm, file sinh tự động (`repomix-output.xml`...).
- **Conventional commits**, không nhắc AI trong commit message.

## Trạng thái migration (2026-08-07)

Đang chuyển Supabase → Postgres tự host trong Docker; auth nội bộ JWT + bcrypt:

- Schema/query là SQLAlchemy + Alembic thuần — không port logic Supabase.
- Các nhánh `if "supabase" in url` (bật SSL) trong `apps/api/src/core/database.py`, `alembic/env.py`, field `database_url_direct` trong `config.py`: đang gỡ dần.
- Cache: giữ Upstash Redis, ngoài phạm vi migrate.
- `data_export.sql` ở repo root: KHÔNG xóa/xử lý cho đến khi khôi phục và đối soát xong.
