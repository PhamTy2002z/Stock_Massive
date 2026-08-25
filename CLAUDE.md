# CLAUDE.md — Stock_Massive

Harness-first AI product. `apps/api` (FastAPI) chạy lane chat trên khung
Hermes-style; `apps/web` (Next.js App Router) hiển thị đúng một cột chat.
Domain vỏ hiện tại là chứng khoán VN (30 mã Universe), sẽ được tham số hoá
thành domain pack ở phase harness đa domain.

# Pivot 2026-08-25 — harness-first, hard freeze

Repo vừa rẽ khỏi "nền tảng dữ liệu chứng khoán" sang "AI product B2C/B2B
đa domain trên khung Hermes". Ba tuyên bố cứng:

1. **Xoá sạch mọi UI + API hiển thị giá trị thị trường** — bảng giá,
   Monitor, realtime feed, market indices, sector performance, news, alpha
   desk analysis lane, watchlist, financial statements, company overview,
   trading endpoints, backfill, collector, warmup, sector historical,
   volume analysis, DNSE ingress, FiinQuant provider, CafeF news feed.
2. **Chỉ giữ AI + backend data cho AI** — `src/agent/*`, `src/auth/*`,
   `alpha/{envelope, field_profile, models, refusals, reasons, favicons,
   schemas, producer(shim)}`, `stocks/{signals, universe, trading_day,
   shared, providers/{contracts,normalize,store(mini)}, realtime/
   {contracts,storage,health,policy}, listing_roster(mini), models,
   schemas}`. Web còn `AppShell → ChatView` + `SourcesTab`.
3. **Hard freeze ngoài `src/agent/*`** — PR duy nhất được nhận là harness,
   auth tenant, budget schema. Bug feature chứng khoán (không còn) không
   fix. Feature stocks mới không nhận.

Nguồn data ngoài duy nhất được phép: **vnstock Bronze giai đoạn dev
(180 req/phút), Diamond khi lên prod (600 req/phút, licence phân phối
≤500 user)**. DNSE, FiinQuant, CafeF **vi phạm điều khoản SaaS** — đã rip.

Rollback: tag `v-with-market-surfaces` (local, chưa push) + backup
`backups/pre-rip-out-260825.sql.gz` (7.2M dump full DB).

# Roadmap harness

- **Phase 0 (đã xong 2026-08-25):** rip market surfaces xuống lane chat.
  940 test API pass, 406 test web pass, type-check/lint/build xanh.
- **Phase 1 (kế tiếp):** tham số hoá `agent/prompt/` + `agent/toolsets.py`
  thành **domain pack** — `signals` bundle chuyển thành pack `vn-equity`
  (prompt fragment + tool bundle + universe khái niệm). Bundle `web` +
  `memory` là core.
- **Phase 2:** B2B foundations — multi-tenant workspace, thread ownership
  theo tenant, budget owner đổi khoá `(tenant, user)`, memory tenant
  isolation. Mở rộng phạm vi hard freeze thành `src/agent/*` + `src/auth/*`
  + `src/core/config`.
- **Phase 3:** domain pack thứ hai để phá giả định "chứng khoán là duy
  nhất".
- **Backlog:** realtime path (unfreeze sau harness đa domain, chỉ chạy
  trên vnstock Diamond staging/prod).

# Tham chiếu bắt buộc — `docs/hermes/`

Mọi đề xuất và triển khai vào `src/agent/` phải đọc `docs/hermes/` trước.
- Vào `hermes-synthesis-260821-0030.md` trước (bản hợp nhất 9 vùng), rồi
  mở đúng report của vùng đang làm: `hermes-core-loop` · `hermes-turn-
  lifecycle` · `hermes-route-subagent` · `hermes-context` · `hermes-tools`
  · `hermes-memory` · `hermes-orchestrator-state` · `hermes-mcp-ops-eval`
  · `hermes-web-security`.
- Đây là **research**, không phải mô tả code hiện tại. Kiểm lại với code
  thật trước khi dựa vào một câu đối chiếu.

# Commands

- Dev: `pnpm dev` (db/redis/api trong Docker + web trên host — API 8000,
  web 3000). Web trong container: `pnpm dev:full`.
- Debug Python trên host: `pnpm dev:api:detach` rồi `make dev` tại
  `apps/api`.
- Dừng / logs: `pnpm stop`, `pnpm logs`, `pnpm logs:api`.
- Đổi code Python: container mount `src/` + `alembic/`, nên
  `docker compose restart api` là đủ — không build lại.
- Test API: `make test` tại `apps/api` — chạy trên **host**, container
  không mount `tests/`.
- Test một file API: `pytest tests/path/test_x.py -v` · một case:
  `pytest tests/path/test_x.py -k "<tên>"`.
- Test web: `pnpm test` tại `apps/web` · một file:
  `pnpm vitest run src/path/x.test.ts` · một case:
  `pnpm vitest run -t "<tên test>"`.
- Cổng web: `pnpm type-check`, `pnpm lint`, `pnpm test`, `pnpm build` tại
  `apps/web`.
- E2E: `pnpm test:e2e` tại `apps/web` — Playwright dựng FastAPI thật
  (`apps/api/tests/e2e/server.py`) + bản production của Next. Tắt
  `pnpm dev` trước.

# Tooling

- pnpm 9, Node 22. Không npm, không yarn.
- **Không** phải pnpm workspace: root lockfile rỗng, `apps/web` có
  `package.json` + lockfile riêng. Cài dep web bằng
  `pnpm --dir apps/web add <pkg>`.
- Python dep ở `apps/api/requirements.txt`; Makefile tự dùng `.venv` nếu
  có.
- Nhiều worktree song song: đặt `API_PORT`/`WEB_PORT` khác nhau và sửa
  `CORS_ORIGINS`.

# Không được đụng

- `apps/api/alembic/versions/**` đã commit — thêm revision mới, không sửa
  file cũ. Bảng dữ liệu thị trường (bar realtime, monitor snapshot, price
  history intraday, watchlist, alpha desk, sector historical...) tạm giữ
  trong DB — revision drop tách ra sang PR sau khi backup đã xác minh
  restore được.
- Không commit secrets, `.env`, dump database, dữ liệu nhạy cảm, file
  sinh tự động. `backups/` là thư mục cho snapshot trước rip-out — không
  commit lên remote (kiểm `.gitignore` trước khi push).
- Không chạy `git push`, không tạo PR khi chưa được yêu cầu trực tiếp.
- Không đổi schema/dữ liệu (migration, drop, bulk update) khi chưa
  backup.

# Quy ước

- **Nhánh:** rip-out lớn dùng branch riêng (hiện tại: `refactor/harness-
  first`). Sau khi nhận PR về `develop`. Feature bình thường vẫn commit
  thẳng lên `develop`; `main` chỉ nhận merge từ `develop`.
- Commit: conventional commits, mô tả thay đổi kỹ thuật, không tham
  chiếu AI.
- Agent (`src/agent/`) trên khung Hermes-style (`registry` · `toolsets` ·
  `definitions` · `executor` · `guardrails` · `budget` · `untrusted`).
  Lane chat chọn ba bundle `web` + `memory` + `signals` = 8 tool.
  `toolsets.CHAT_TOOLSETS` là selection duy nhất và phải được **viết
  ra**: `AgentLoop(toolsets=None)` mặc định về đúng tuple đó. Thêm/đổi
  tool đi qua `registry`/`toolsets`/`definitions`, không hardcode trong
  `loop.py`.
- **Lane chat đọc store**, đảo `1e7b936`. Chỉ đọc Signal Field đã đăng ký,
  cho mã trong Universe, ở phiên gần nhất đã đóng. `get_field` có **hai
  chữ ký từ một registration**: `ToolContext.symbol` có (từng cho lane
  Analysis — lane đó đã bỏ) thì nó thắng; không có context (lane chat) thì
  `symbol` là argument. `trading_day` **không bao giờ** là argument.
- Luật đã ghim trong prompt (`PROMPT_VERSION` 2.3.0): **số của store
  thắng số của web** · tách hai khối bằng chứng · nêu mức và hệ quả,
  **không** ra chỉ thị hành động cho vị thế cụ thể.
- `MAX_EXTERNAL_TOOL_CALLS = 6` chỉ tính tool có `reads_external` bật,
  không tính ba tool `signals`. `MAX_TOOL_ROUNDS = 4` ở lane chat.
- Kết quả tool có bọc `<untrusted_tool_result>` do
  `registry.ToolEntry.reads_external` quyết, mặc định `True`. Tool đọc
  store khai `reads_external=False`.
- **"Chạy" và "trả về số" là hai việc.** `agent_tool_call.status` là `ok`
  cho ba loại: có số · `no_value:<signal issue>` · `cannot_read`.
  Cột `outcome` là chỗ duy nhất phân biệt. Vốn từ ở
  `agent/messages.py::outcome_of`.
- **Sàn percentile là hàm mẫu**: `signals/fields.py::min_sample_for`
  = `max(ceil(0.6 × mẫu), 15)`.
- **`min_sessions` là sàn lịch sử, `lookback_sessions` là cửa sổ đọc** —
  `SignalField.window_sessions` giải hai cái.
- **Mã refusal phải trỏ đúng input thiếu.** `_quarterly_ratio` chia ba
  nguyên nhân: `fundamental_not_stored` · `statement_line_missing` ·
  `market_cap_absent`. Thêm mã thì thêm câu ở **cả** `alpha/reasons.py`
  và `apps/web/src/lib/signal-issues.ts`.
- `check_price_claim` kiểm giá nguồn ngoài: bước giá · biên độ · bar
  trong store. Trạng thái thứ tư `unverified` **không phải** "hợp lệ".
  Fail-open, không chặn câu trả lời.
- Ngân sách LLM: envelope $45/tháng chia ba lane 10 Analysis / 30 Turn /
  5 emergency. Analysis lane đã bỏ (rip-out) — envelope chưa reweight,
  ledger vẫn ghi. Đặt cả bốn giá trị về `0` cho route thuê bao.
- Web: sản phẩm là **một màn hình duy nhất** ở `/` — shell 2 vùng chính ở
  `src/components/shell/` (sidebar + cột chat). Inspector phải chỉ còn
  panel Sources. Chỉ `(auth)` là trang riêng.

# Definition of done

1. `make test` tại `apps/api` pass
2. `pnpm type-check`, `pnpm lint`, `pnpm test`, `pnpm build` tại
   `apps/web` pass
3. Phần nào không chạy được thì nêu rõ, đừng ẩn lỗi
4. Không thêm dependency mới nếu chưa hỏi

# Không còn tồn tại

**2026-08-25 (rip-out harness-first):**
- **Web UI:** `view-board`, `view-news`, `view-new`, `watchlist-section`,
  `components/market-monitor/*`, `components/alpha/analysis/*`,
  `news-sources`, `hooks/use-{price-board,market-monitor,market-indices,
  vn30-overview,sector-performance,price-history,news,analysis,watchlist-
  rail}`, `lib/market-monitor/*`, `query-keys.stock*` (tất cả trừ auth +
  threads). Inspector chỉ còn panel Sources.
- **API routers:** `stocks_router`, `jobs_router`, `realtime_router`,
  `watchlist_router`, `analysis_router`, `alpha_desk_router`,
  `loop_ops_router`, `stocks/signals/router`. Endpoint duy nhất còn:
  `auth`, `agent` (alpha desk service router), `message_flag`,
  `favicons`, health.
- **API modules:** `stocks/{monitor,realtime{ingress+coordinator+spine
  +projections+dnse+aggregation+bar_projection+metric_projection+metrics
  +service+normalization+router+reconciliation*},price,market,news,
  analytics,financial,company,trading}`, `stocks/{backfill,collector*,
  intraday_collector,corporate_action_collector,warmup,session_window,
  series_view,census,cohort,snapshot_router,jobs*,listing_roster(full),
  market_index,service,router}`, `alpha/{analysis_loop,analysis_reads,
  analysis_router,analysis_run,dispatcher,generation,jobs,loop_ops_router,
  naming,nightly,on_demand,producer(full),production,router,watchlist}`,
  `stocks/providers/{cafef_article,cafef_rss,fiinquant,store(full),
  vnstock_provider}`, `stocks/signals/{router,volume_spike,position_
  sizing}`, `src/eval/*`.
- **Tests:** ~140 test file cho code đã xoá.
- Vẫn giữ 30 mã Universe declared, không còn cohort seating.

**2026-08-22 (đã ghi trước đó):**
- Eval Battery / Eval Gate / Eval Report: `src/eval/*` (đã rip lại lần
  này), `make eval*`, biến `EVAL_*`, bảng `eval_run`, lane ngân sách
  eval. Chữ `eval` còn trong code là lệnh Redis (`core/redis.py::eval_
  script`).
