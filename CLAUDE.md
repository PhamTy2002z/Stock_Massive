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
   fix. Feature stocks mới không nhận. **Mở từ 2026-08-26** cho đúng bốn
   surface của Signal Desk: `src/studies/*` (mới) · `src/stocks/
   intraday/*` (mới) · bundle `studies` trong `src/agent/` · surface Signal Desk
   trong `apps/web`. **Mở thêm 2026-08-27** cho spine daily của phase 08a:
   `src/stocks/providers/vnstock_daily.py` (mới) · `src/stocks/
   backfill_daily.py` (mới) · `src/stocks/listing_roster.py` ·
   `src/stocks/universe.py`. **Mở thêm 2026-08-28** cho plan
   `plans/260828-2126-price-basis-and-signal-field-spine/` — chuyển 30 Signal
   Field khỏi giá FiinQuant sang `bar_daily`, đúng tám surface dưới đây, mỗi
   surface kèm giới hạn của nó:

   | Surface | Giới hạn |
   |---|---|
   | `stocks/trading_day.py` | đổi nguồn lịch sang `bar_daily`, giữ nguyên chữ ký hàm công khai |
   | `stocks/signals/{sessions,bars}.py` | chuyển nguồn + luật basis mới; không thêm Signal Field |
   | `stocks/signals/corporate_actions.py` | vá `_session_low`; không đổi công thức hệ số |
   | `stocks/signals/{price_band,market_behavior}.py` | cổng basis thứ hai + band từ luật sàn |
   | `stocks/signals/{registry,serving,issues,cross_sectional,foreign_flow,fields}.py` | khai projection + refusal đúng input; không thêm mã refusal mới |
   | `stocks/providers/{contracts,store}.py` | gỡ FiinQuant khỏi bản đồ ownership |
   | `stocks/schemas/snapshot.py` | gỡ echo REST của nguồn đã xoá |
   | `stocks/signals/earnings.py` (mới) | Signal Field `earnings.*` |

   Bảng này **là** ranh giới. File nằm ngoài bảng cần amendment mới, không
   phải một dòng nới. Phần còn lại của `src/stocks/*` — `realtime/*`,
   `providers/normalize.py`, `models.py` ngoài bảng mới — **vẫn freeze**.

Nguồn data ngoài duy nhất được phép: **vnstock Bronze giai đoạn dev
(180 req/phút), Diamond khi lên prod (600 req/phút, licence phân phối
≤500 user)**. DNSE, FiinQuant, CafeF **vi phạm điều khoản SaaS** — đã rip.

Rollback: tag `v-with-market-surfaces` trên `origin` (đã push 2026-08-26)
+ backup `backups/pre-rip-out-260825.sql.gz` (7.2M dump full DB).

# Roadmap harness

Authority: **`docs/roadmap.md`** — hai track, mỗi phase có Objective ·
Trước→Sau · checklist · gate. Tóm tắt:

- **Track C — Core harness (mọi user):** C0 nền lane chat (Current, xong
  2026-08-25) · C1 search & tổng hợp có citation · C2 context & cache ·
  C3 tool plane / nudge có trần / idempotency · C4 evaluator plane (Golden
  Question Set, dựng lại sau khi rip eval) · C5 domain pack + progressive
  instruction (Phase 1 cũ) · C6 tenant / permission / entitlement (Phase 2
  cũ) · C7 delegation có điều kiện · C8 domain pack thứ hai (Phase 3 cũ).
- **Track S — Signal Desk (paid):** S0 runtime qua Study (Current, đang đóng)
  · S1 thư viện Study + desk theo mã · S2 thesis + human approval · S3
  proactive scan. Mọi S mở sau gate C4; entitlement gắn ở C6.
- **Backlog:** realtime path (sau C8, chỉ vnstock Diamond).

## Đã chốt 2026-08-26 — Signal Desk qua Study

Lane chat kết xuất **Signal Desk** — surface phân tích động — thay vì chỉ trả
text. Từ vựng chuẩn 2026-08-28: **Signal Desk**, không còn "canvas" trong
code, contract hay tài liệu (cột `agent_artifact.signal_desk_spec`, revision
`f8c2d4a96e17`). Cơ chế:
model chọn một **Study** (recipe phân tích có tên, có version,
deterministic) và điền params; **engine tính, artifact giữ số, registry
vẽ**. Ba luật cứng:

- `StudyResult.frames` — dãy/ma trận số — **không bao giờ** vào message
  gửi model. Model chỉ thấy `headline` (~300 token). Test đọc transcript
  giữ luật này.
- Widget có **name + version**, danh mục ở `contracts/signal-desk-
  widget-catalog.json` (sinh từ `src/studies/widgets.py`, test giữ đồng bộ).
  Viewer gặp version không biết → fallback `data_table`, không crash.
- `as_of` đóng băng lúc tạo artifact; mở lại thread là **render lại
  artifact**, không tính lại.

Plan thi công: `plans/260826-2158-study-artifact-canvas/`. Bảng
`agent_artifact` giữ một lần chạy Study. Ba case đầu: intraday liquidity
profile · condition review · earnings dislocation screener.

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
- Luật đã ghim trong prompt (`PROMPT_VERSION` 2.6.0): **số của store
  thắng số của web** · tách hai khối bằng chứng · nêu mức và hệ quả,
  **không** ra chỉ thị hành động cho vị thế cụ thể.
- `MAX_EXTERNAL_TOOL_CALLS = 6` chỉ tính tool có `reads_external` bật,
  không tính ba tool `signals`. `MAX_TOOL_ROUNDS = 4` ở lane chat.
- Kết quả tool có bọc `<untrusted_tool_result>` do
  `registry.ToolEntry.reads_external` quyết, mặc định `True`. Tool đọc
  store khai `reads_external=False`.
- **Signal Desk đi hai đường, cùng một luật.** `run_study` chạy công thức có tên;
  `get_series` + `render_signal_desk` cho câu hỏi chưa có công thức. Cả hai trả
  model **id + tóm tắt**, không bao giờ trả `frames`; loop phát `signal_desk.ready`
  từ payload qua `messages.signal_desk_of`. Frame chỉ vẽ được bởi chính Turn tạo ra
  nó (`studies/frames_buffer.py`).
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
  `src/components/shell/` (sidebar + cột chat). Inspector có đúng hai tab:
  Nguồn và Signal Desk. Chỉ `(auth)` là trang riêng.
- Widget Signal Desk có **name + version**; FE giữ registry ở
  `components/signal-desk/widget-registry.ts` và test khớp nó với
  `contracts/signal-desk-widget-catalog.json`. Không vẽ được → `data_table` kèm ghi
  chú, không bao giờ khối trắng. Panel Signal Desk nạp qua `next/dynamic` để
  recharts không nằm trên đường first paint của lane chat.

# Definition of done

1. `make test` tại `apps/api` pass
2. `pnpm type-check`, `pnpm lint`, `pnpm test`, `pnpm build` tại
   `apps/web` pass
3. Phần nào không chạy được thì nêu rõ, đừng ẩn lỗi
4. Không thêm dependency mới nếu chưa hỏi

# Không còn tồn tại

**2026-08-26 (Phase 0 cleanup):**
- **Empty stocks shells** (không track, dọn khỏi disk): `apps/api/src/
  stocks/{analytics,company,financial,market,monitor,news,price,trading}`
  + `apps/api/src/stocks/realtime/dnse`. Còn lại trong `stocks/`:
  `providers`, `realtime`, `signals`, `schemas`, `shared`, `models.py`,
  `universe.py`, `trading_day.py`, `listing_roster.py`.
- **Signal module mồ côi:** `stocks/signals/nulls.py` + test kèm.
  11 module `corporate_actions` · `cross_sectional` · `foreign_flow` ·
  `foreign_share_flow` · `fundamentals` · `indicators` ·
  `market_behavior` · `moments` · `reference` · `risk` · `volatility`
  **giữ nguyên** — reverse-import từ registry / serving / test.
- **Config settings mồ côi khỏi `src/core/config.py`:** `fiinquant_*`,
  `dnse_*`, `realtime_ingestion_enabled`, `realtime_queue_size`,
  `realtime_worker_count`, `realtime_shutdown_timeout_seconds`,
  `realtime_boards`, `_complete_realtime_configuration`, `backfill_*`,
  `warmup_window_trading_days`, `alpha_desk_suggestions_enabled`,
  intraday collector / profit census / cohort / collector /
  corporate-action job / market-index / catch-up / Analysis dispatcher /
  sector-historical job settings, `git_sha` (Evidence Manifest). **Giữ:**
  `alpha_desk_enabled` — `core/llm/config.py` + capability enforcement +
  test vẫn đọc.
- **Bảng DB đã drop qua alembic revision mới** (upgrade path;
  downgrade raise `NotImplementedError` — restore từ backup):
  `analysis_tool_call`, `analysis_run`, `watchlist_entries`, `analysis`,
  `cohort_members`, `cohort_versions`, `profit_ranking_census_runs`,
  `symbol_backfills`, `stock_intraday_bars`, `stock_daily_ohlcv`.
  **Giữ:** `realtime_events`, `realtime_checkpoints`, `realtime_spills`,
  `realtime_health`, `realtime_reconciliation_audits` —
  `stocks/realtime/storage.py` và `signals/foreign_share_flow.py` vẫn đọc.
- **Stub Phase 1 domain pack:** `apps/api/plans/260826-1909-phase-1-
  domain-pack/` + `apps/api/src/agent/domain/` (không có importer).
  Hoãn Phase 1 chờ quyết brief Signal Desk (`docs/Text.txt`).

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
