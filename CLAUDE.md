# CLAUDE.md — Stock_Massive

Nền tảng dữ liệu chứng khoán Việt Nam (HOSE/HNX/UPCOM): `apps/api` phục vụ dữ liệu, `apps/web` hiển thị.

## Cấu trúc

- `apps/api` — FastAPI + SQLAlchemy + Alembic. Domain ở `src/stocks/` (`market`, `price`, `trading`, `financial`, `analytics`, `company`, `providers`); auth ở `src/auth/`; hạ tầng dùng chung (config, database, cache, redis, scheduler, vnstock client) ở `src/core/`. Agent ở `src/agent/` là **trợ lý tổng quát** trên khung kiểu Hermes (`registry` · `toolsets` · `definitions` · `executor` · `guardrails` · `budget` · `untrusted`) — nó **không đọc dữ liệu của hệ thống này**: chỉ có 5 tool (`web_search`, `fetch_url`, `session_search`, `remember_fact`, `recall_facts`). Dữ liệu vnstock/FiinQuant phục vụ bảng giá và Analysis lane, không phục vụ agent (`docs/adr/0026`).
- `apps/web` — Next.js App Router + TypeScript, mã ở `src/`. Sản phẩm là **một màn hình duy nhất** ở `/`: shell 3 vùng trong `src/components/shell/` (sidebar · cột chính · inspector phải). Ba view `chat` / `board` / `new` là state của shell chứ không phải route — đổi view không được làm mất câu đang gõ dở. Cài đặt cũng vậy: một overlay của shell (`settings-dialog.tsx`, nội dung ở `src/components/settings/`), mở bằng ⇧⌘, hoặc menu tài khoản. Chỉ `(auth)` là trang riêng.
- `docker-compose.yml` — stack dev: `db` (Postgres), `redis`, `api`; `web` chỉ lên khi bật profile `full`.

Mỗi app tự quản dependency riêng — `apps/web` có `package.json` + lockfile riêng, script ở root chỉ là wrapper quanh `docker compose` và `pnpm --dir apps/web`. Root lockfile rỗng; đây không phải pnpm workspace.

## Chạy

Nguồn sự thật cho lệnh: `package.json` ở root, `apps/api/Makefile`, `apps/web/package.json`. Những gì không đọc được từ đó:

- `pnpm dev` chạy `db`/`redis`/`api` trong Docker còn web trên host, để Next.js có file watching native. Cần web trong container thì `pnpm dev:full`.
- `make dev` ở `apps/api` chạy backend thẳng trên máy khi cần debug Python; `db`/`redis` vẫn lấy từ Docker (`pnpm dev:api:detach`).
- Áp migration trong container bằng `pnpm db:migrate`. Tạo revision thì chạy `alembic revision --autogenerate -m "..."` tại `apps/api` với DB đang lên.
- vnstock là điểm nghẽn quota: 20 req/phút khi thiếu `VNSTOCK_API_KEY`, 60 khi có. Các job nặng (`SECTOR_HISTORICAL_ENABLED`, `BACKFILL_ENABLED`) mặc định tắt vì lý do này.
- Chạy nhiều worktree song song: đặt `API_PORT`/`WEB_PORT` khác nhau, và sửa `CORS_ORIGINS` cho khớp origin mới của web.
- `pnpm test:e2e` tại `apps/web` là cổng nghiệm thu streaming của Alpha Desk: Playwright tự dựng FastAPI thật (`apps/api/tests/e2e/server.py`) và bản build production của Next, rồi lái bằng Chromium. Cần DB đã migrate và `pnpm exec playwright install chromium`. Chi tiết ở `docs/streaming-topology.md`.

## Quy tắc bắt buộc 

- **Nhánh** — `develop` là nhánh làm việc: mọi tính năng/sửa lỗi commit thẳng lên `develop`, không tách nhánh riêng. `main` được protected và chỉ nhận merge từ `develop`.
- **Cổng kiểm tra trước khi báo xong** — backend: `make test` tại `apps/api`. Frontend: `pnpm type-check`, `pnpm lint`, `pnpm test`, `pnpm build` tại `apps/web`. Phần nào không chạy được thì nêu rõ phần đó.
- **Commit** — Conventional Commits, mô tả thay đổi kỹ thuật. Giữ ngoài index: secrets, `.env`, dữ liệu nhạy cảm, dump database, file sinh tự động.
- **Eval gate** — đang **treo, chưa được thay**. Gate cũ đòi Eval Report cho PR chạm System Prompt Contract, tool schema/`tool_catalog_version`, Signal Registry, Analysis Field Profile, `llm_model_*`, agent loop hoặc Recommendation Validator. `docs/adr/0026` xoá ba trong số đó (Contract cũ, `tool_catalog_version`, Recommendation Validator) và Eval Battery cũ chấm đúng những tính chất vừa bị xoá — groundedness, citation, recommendation. Nên gate **không** thoả được theo lời văn cũ, và cũng **không** được coi là đã bỏ: PR chạm agent loop, tool schema hoặc prompt vẫn phải nói rõ đã đo gì. Bar mới cho một trợ lý tổng quát phải được chốt trước khi nhánh Hermes vào `develop`. Phần gate còn nguyên hiệu lực: Signal Registry, Analysis Field Profile, `llm_model_*` — chúng thuộc bảng giá/Analysis lane, không bị ADR-0026 chạm.

`apps/api/AGENTS.md` do vnstock tự sinh (hướng dẫn dựng môi trường vnstock), không phải quy ước của repo này.

## Agent skills
- **Eval Battery** — `make eval` tách khỏi `make test` vì nó tốn tiền; chạy trên `EVAL_DATABASE_URL` riêng và không bao giờ ghi vào store của dev/prod. Quy trình đóng băng lại Eval Fixture: `docs/agents/eval-battery.md`.
