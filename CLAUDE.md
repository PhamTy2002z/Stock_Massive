# CLAUDE.md — Stock_Massive

Nền tảng dữ liệu chứng khoán Việt Nam (HOSE/HNX/UPCOM): `apps/api` (FastAPI) phục vụ dữ liệu, `apps/web` (Next.js App Router) hiển thị.

# Commands
- Dev: `pnpm dev` (db/redis/api trong Docker + web trên host — API 8000, web 3000). Web trong container: `pnpm dev:full`
- Debug Python trên host: `pnpm dev:api:detach` rồi `make dev` tại `apps/api`
- Dừng / logs: `pnpm stop`, `pnpm logs`, `pnpm logs:api`
- Migration: `pnpm db:migrate`. Tạo revision: `alembic revision --autogenerate -m "..."` tại `apps/api` với DB đang lên
- Test API: `make test` tại `apps/api` (chạy trên **host** — container `api` không mount `src`, pytest trong container là code cũ)
- Test một file API: `pytest tests/path/test_x.py -v` · một case: `pytest tests/path/test_x.py -k "<tên>"`
- Test web: `pnpm test` tại `apps/web` · một file: `pnpm vitest run src/path/x.test.ts` · một case: `pnpm vitest run -t "<tên test>"`
- Cổng web: `pnpm type-check`, `pnpm lint`, `pnpm test`, `pnpm build` tại `apps/web`
- E2E: `pnpm test:e2e` tại `apps/web` — cổng nghiệm thu streaming: Playwright tự dựng FastAPI thật (`apps/api/tests/e2e/server.py`) + bản production của Next. Cần DB đã migrate + `pnpm exec playwright install chromium`; tắt `pnpm dev` trước vì bản production phá `.next` của dev
- Eval Battery: `make eval` tại `apps/api` — **tốn tiền**, chỉ chạy khi được yêu cầu. `make eval-smoke` miễn phí. Chạy trên `EVAL_DATABASE_URL` riêng và tự từ chối nếu biến này trống hoặc trỏ vào DB mà API đang phục vụ. Đóng băng fixture: `make eval-fixture` → `make eval-fixture-load`

# Tooling
- pnpm 9, Node 22. Không npm, không yarn.
- **Không** phải pnpm workspace: root lockfile rỗng, `apps/web` có `package.json` + lockfile riêng. Cài dep web bằng `pnpm --dir apps/web add <pkg>`. Script ở root chỉ là wrapper quanh `docker compose`.
- Python dep ở `apps/api/requirements.txt`; Makefile tự dùng `.venv` nếu có.
- vnstock là điểm nghẽn quota: 20 req/phút khi thiếu `VNSTOCK_API_KEY`, 60 khi có. `SECTOR_HISTORICAL_ENABLED` và `BACKFILL_ENABLED` mặc định tắt — đừng bật nếu không cần.
- Nhiều worktree song song: đặt `API_PORT`/`WEB_PORT` khác nhau và sửa `CORS_ORIGINS` cho khớp origin web mới.

# Không được đụng
- `apps/api/alembic/versions/**` đã commit — thêm revision mới, không sửa file cũ
- `apps/api/AGENTS.md` do vnstock tự sinh, không phải quy ước của repo này
- Không commit secrets, `.env`, dump database, dữ liệu nhạy cảm, file sinh tự động
- Không chạy `git push`, không tạo PR. Tui tự làm.
- Không đổi schema/dữ liệu (migration, drop, bulk update) khi chưa backup

# Quy ước
- Nhánh: commit thẳng lên `develop`, không tách nhánh riêng. `main` protected, chỉ nhận merge từ `develop`.
- Commit: conventional commits, mô tả thay đổi kỹ thuật, không tham chiếu AI.
- API: mỗi domain trong `src/stocks/<domain>/` có `router.py` mỏng + `service.py` giữ logic; auth ở `src/auth/`; hạ tầng dùng chung (config, database, cache, redis, scheduler, vnstock client) ở `src/core/`. Đừng nhồi logic hay query vào router.
- Agent (`src/agent/`) là **trợ lý tổng quát** trên khung kiểu Hermes (`registry` · `toolsets` · `definitions` · `executor` · `guardrails` · `budget` · `untrusted`) và **không đọc dữ liệu của hệ thống này**: chỉ 5 tool `web_search`, `fetch_url`, `session_search`, `remember_fact`, `recall_facts`. Thêm/đổi tool thì đi qua `registry`/`toolsets`/`definitions`, không hardcode trong `loop.py`. Dữ liệu vnstock/FiinQuant phục vụ bảng giá và Analysis lane, không phục vụ agent.
- Web: sản phẩm là **một màn hình duy nhất** ở `/` — shell 3 vùng ở `src/components/shell/` (sidebar · cột chính · inspector phải). Ba view `chat`/`board`/`new` và settings là state/overlay của shell, không phải route: đổi view không được làm mất câu đang gõ dở. Chỉ `(auth)` là trang riêng.

# Definition of done
1. `make test` tại `apps/api` pass
2. `pnpm type-check`, `pnpm lint`, `pnpm test`, `pnpm build` tại `apps/web` pass
3. Phần nào không chạy được thì nêu rõ phần đó, đừng ẩn lỗi
4. Không thêm dependency mới nếu chưa hỏi

# Eval gate (đang treo)
Gate cũ đòi Eval Report cho PR chạm System Prompt Contract, tool schema/`tool_catalog_version`, Signal Registry, Analysis Field Profile, `llm_model_*`, agent loop hoặc Recommendation Validator. Việc thay harness bằng trợ lý tổng quát đã xoá ba trong số đó (Contract cũ, `tool_catalog_version`, Recommendation Validator), và Eval Battery cũ chấm đúng những tính chất vừa bị xoá — groundedness, citation, recommendation. Nên gate **không** thoả được theo lời văn cũ, và cũng **không** được coi là đã bỏ: PR chạm agent loop, tool schema hoặc prompt vẫn phải nói rõ đã đo gì. Bar mới cho trợ lý tổng quát phải chốt trước khi nhánh Hermes vào `develop`. Phần còn nguyên hiệu lực: Signal Registry, Analysis Field Profile, `llm_model_*` — thuộc bảng giá/Analysis lane, không bị thay đổi này chạm tới.
