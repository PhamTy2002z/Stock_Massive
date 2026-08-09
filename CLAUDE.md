# CLAUDE.md — Stock_Massive

Nền tảng dữ liệu chứng khoán Việt Nam (HOSE/HNX/UPCOM): `apps/api` phục vụ dữ liệu, `apps/web` hiển thị.

## Cấu trúc

- `apps/api` — FastAPI + SQLAlchemy + Alembic. Domain ở `src/stocks/` (`market`, `price`, `trading`, `financial`, `analytics`, `company`, `providers`); auth ở `src/auth/`; hạ tầng dùng chung (config, database, cache, redis, scheduler, vnstock client) ở `src/core/`.
- `apps/web` — Next.js App Router + TypeScript, mã ở `src/` với route group `(auth)` / `(dashboard)`.
- `docker-compose.yml` — stack dev: `db` (Postgres), `redis`, `api`; `web` chỉ lên khi bật profile `full`.

Mỗi app tự quản dependency riêng — `apps/web` có `package.json` + lockfile riêng, script ở root chỉ là wrapper quanh `docker compose` và `pnpm --dir apps/web`. Root lockfile rỗng; đây không phải pnpm workspace.

## Chạy

Nguồn sự thật cho lệnh: `package.json` ở root, `apps/api/Makefile`, `apps/web/package.json`. Những gì không đọc được từ đó:

- `pnpm dev` chạy `db`/`redis`/`api` trong Docker còn web trên host, để Next.js có file watching native. Cần web trong container thì `pnpm dev:full`.
- `make dev` ở `apps/api` chạy backend thẳng trên máy khi cần debug Python; `db`/`redis` vẫn lấy từ Docker (`pnpm dev:api:detach`).
- Áp migration trong container bằng `pnpm db:migrate`. Tạo revision thì chạy `alembic revision --autogenerate -m "..."` tại `apps/api` với DB đang lên.
- vnstock là điểm nghẽn quota: 20 req/phút khi thiếu `VNSTOCK_API_KEY`, 60 khi có. Các job nặng (`DAILY_OHLCV_ENABLED`, `SECTOR_HISTORICAL_ENABLED`) mặc định tắt vì lý do này.
- Chạy nhiều worktree song song: đặt `API_PORT`/`WEB_PORT` khác nhau, và sửa `CORS_ORIGINS` cho khớp origin mới của web.

## Quy tắc bắt buộc

- **Nhánh** — `develop` là nhánh tích hợp; mọi tính năng/sửa lỗi tách nhánh riêng từ `develop`, làm trong git worktree, rồi merge ngược về `develop`. `main` được protected và chỉ nhận merge từ `develop`.
- **Cổng kiểm tra trước khi báo xong** — backend: `make test` tại `apps/api`. Frontend: `pnpm type-check`, `pnpm lint`, `pnpm test`, `pnpm build` tại `apps/web`. Phần nào không chạy được thì nêu rõ phần đó.
- **Commit** — Conventional Commits, mô tả thay đổi kỹ thuật. Giữ ngoài index: secrets, `.env`, dữ liệu nhạy cảm, dump database, file sinh tự động.

`apps/api/AGENTS.md` do vnstock tự sinh (hướng dẫn dựng môi trường vnstock), không phải quy ước của repo này.

## Agent skills

- **Issue tracker** — GitHub Issues của `PhamTy2002z/Stock_Massive`, thao tác qua `gh`. Chi tiết: `docs/agents/issue-tracker.md`.
- **Triage labels** — 5 nhãn canonical mặc định: `needs-triage`, `needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`. Chi tiết: `docs/agents/triage-labels.md`.
- **Domain docs** — single-context: `CONTEXT.md` + `docs/adr/` ở root, do `/matt:domain-modeling` tạo khi có thuật ngữ hoặc quyết định cần chốt. Chi tiết: `docs/agents/domain.md`.
