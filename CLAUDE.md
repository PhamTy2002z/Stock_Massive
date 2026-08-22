# CLAUDE.md — Stock_Massive

Nền tảng dữ liệu chứng khoán Việt Nam (HOSE/HNX/UPCOM): `apps/api` (FastAPI) phục vụ dữ liệu, `apps/web` (Next.js App Router) hiển thị.

# Commands
- Dev: `pnpm dev` (db/redis/api trong Docker + web trên host — API 8000, web 3000). Web trong container: `pnpm dev:full`
- Debug Python trên host: `pnpm dev:api:detach` rồi `make dev` tại `apps/api`
- Dừng / logs: `pnpm stop`, `pnpm logs`, `pnpm logs:api`
- Đổi code Python: container mount `src/` + `alembic/`, nên `docker compose restart api` là đủ — không cần build lại
- Migration: `pnpm db:migrate`. Tạo revision: `alembic revision --autogenerate -m "..."` tại `apps/api` với DB đang lên
- Test API: `make test` tại `apps/api` — chạy trên **host**, vì container không mount `tests/`
- Test một file API: `pytest tests/path/test_x.py -v` · một case: `pytest tests/path/test_x.py -k "<tên>"`
- Test web: `pnpm test` tại `apps/web` · một file: `pnpm vitest run src/path/x.test.ts` · một case: `pnpm vitest run -t "<tên test>"`
- Cổng web: `pnpm type-check`, `pnpm lint`, `pnpm test`, `pnpm build` tại `apps/web`
- E2E: `pnpm test:e2e` tại `apps/web` — cổng nghiệm thu streaming: Playwright tự dựng FastAPI thật (`apps/api/tests/e2e/server.py`) + bản production của Next. Cần DB đã migrate + `pnpm exec playwright install chromium`; tắt `pnpm dev` trước vì bản production phá `.next` của dev

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
- Không chạy `git push`, không tạo PR khi chưa được yêu cầu trực tiếp
- Không đổi schema/dữ liệu (migration, drop, bulk update) khi chưa backup

# Quy ước
- Nhánh: commit thẳng lên `develop`, không tách nhánh riêng. `main` protected, chỉ nhận merge từ `develop`.
- Commit: conventional commits, mô tả thay đổi kỹ thuật, không tham chiếu AI.
- API: mỗi domain trong `src/stocks/<domain>/` có `router.py` mỏng + `service.py` giữ logic; auth ở `src/auth/`; hạ tầng dùng chung (config, database, cache, redis, scheduler, vnstock client) ở `src/core/`. Đừng nhồi logic hay query vào router.
- Agent (`src/agent/`) là **trợ lý tổng quát** trên khung kiểu Hermes (`registry` · `toolsets` · `definitions` · `executor` · `guardrails` · `budget` · `untrusted`). Lane chat chọn ba bundle `web` + `memory` + `signals` = 8 tool. `toolsets.CHAT_TOOLSETS` là selection duy nhất và nó phải được **viết ra**: `AgentLoop(toolsets=None)` mặc định về đúng tuple đó, **không** về "mọi bundle đã đăng ký", nên bundle thứ tư thêm mai không tự tới tay hội thoại. Thêm/đổi tool thì đi qua `registry`/`toolsets`/`definitions`, không hardcode trong `loop.py`.
- **Lane chat giờ đọc được store**, đảo `1e7b936` (*"an assistant that reads none of our data"*). Nó đọc **duy nhất** Signal Field đã đăng ký, cho mã trong Universe, ở phiên gần nhất đã đóng — không bảng giá, không watchlist, không tin tức, không BCTC thô. `get_field` có **hai chữ ký từ một registration**: `ToolContext.symbol` có (lane Analysis) thì nó thắng và argument `symbol` nêu mã khác **bị handler từ chối**; không có context (lane chat) thì `symbol` là argument, qua `validate_symbol` + kiểm Universe. `trading_day` **không bao giờ** là argument ở lane nào.
- Luật đã ghim trong prompt (`PROMPT_VERSION` 2.3.0): **số của store thắng số của web** và sự khác nhau phải nói ra · tách hai khối bằng chứng trong câu trả lời · nêu mức và hệ quả, **không** ra chỉ thị hành động cho vị thế cụ thể (không "bán đi", không tỷ trọng mục tiêu, không mức vào/ra).
- `MAX_EXTERNAL_TOOL_CALLS = 6` chỉ tính tool có `reads_external` bật, không tính ba tool `signals` — chúng đọc Postgres trong deployment. `MAX_TOOL_ROUNDS = 4` ở lane chat, 6 ở lane Analysis.
- Kết quả tool có bị bọc `<untrusted_tool_result>` hay không do **`registry.ToolEntry.reads_external`** quyết, không do danh sách tên nào. Mặc định là `True`: tool không khai thì được bọc. Thêm tool đọc store thì khai `reads_external=False`, đừng sửa `untrusted.py`.
- `check_price_claim(symbol, price, session_date?)` kiểm một mức giá nguồn ngoài: bước giá sàn · biên độ so close phiên trước · đối chiếu bar trong store. Trạng thái thứ tư `unverified` **không phải** "hợp lệ". Nó fail-open tuyệt đối: không xoá số, không chặn câu trả lời. Nó chỉ phủ **giá** — doanh thu/lợi nhuận/biên gộp không có bước giá nào để kiểm. Tỷ lệ model thực sự gọi nó đo bằng `agent/ops.py::read_price_check_compliance`; chưa có backstop quét văn bản và đó là quyết định, không phải bỏ quên.
- Analysis lane là **vòng lặp**, không phải một lời gọi: `alpha/analysis_loop.py` cho model 6 round đọc store rồi mới hỏi fragment (`promptVersion v2`); `generation.py` một-lời-gọi vẫn còn và bật/tắt bằng `ANALYSIS_EVIDENCE_LOOP_ENABLED` (`promptVersion v1`). Vòng lặp đánh đổi tính tái lập lấy audit: mọi lời gọi tool ghi vào `analysis_tool_call`. Hai Analysis cùng `fieldProfileVersion` giờ **có thể** mang bộ figure khác nhau — trace là thứ nói ra sự khác biệt. Dữ liệu vnstock/FiinQuant phục vụ bảng giá và Analysis lane, không phục vụ lane chat.
- Ngân sách LLM: envelope $45/tháng chia ba lane 10 Analysis / 30 Turn / 5 emergency. Trần một Analysis là **24.000 input / 3.000 output / $0,015** — đó là trần cho *cả vòng lặp*, không phải cho một lời gọi; cái chặn thật qua nhiều lời gọi là `ANALYSIS_COST_MICRO_USD` tính trên `owner=(analysis_run, run_id)`. Budget Validation chặn startup nếu các lane không cộng đúng bằng envelope — đổi một lane thì đổi cả envelope. Đặt cả bốn giá trị về `0` cho route thuê bao: ledger vẫn ghi token và giá, chỉ bỏ phần từ chối bằng USD.
- Web: sản phẩm là **một màn hình duy nhất** ở `/` — shell 3 vùng ở `src/components/shell/` (sidebar · cột chính · inspector phải). Bốn view `chat`/`board`/`new`/`news` và settings là state/overlay của shell, không phải route: đổi view không được làm mất câu đang gõ dở. Chỉ `(auth)` là trang riêng.

# Definition of done
1. `make test` tại `apps/api` pass
2. `pnpm type-check`, `pnpm lint`, `pnpm test`, `pnpm build` tại `apps/web` pass
3. Phần nào không chạy được thì nêu rõ phần đó, đừng ẩn lỗi
4. Không thêm dependency mới nếu chưa hỏi

# Fail đang có sẵn
`tests/test_deployment_topology.py::test_the_topology_is_written_down_where_the_next_reader_will_look` đòi `docs/streaming-topology.md`, file đã bị xoá cùng `docs/` ở commit `b352417`. Không phải hồi quy của thay đổi đang làm — hoặc dựng lại tài liệu đó, hoặc bỏ assert.

# Không còn tồn tại
Eval Battery / Eval Gate / Eval Report bị xoá ngày 2026-08-22: `src/eval/`, `make eval*`, biến `EVAL_*`, bảng `eval_run`, lane ngân sách eval. PR chạm agent loop, tool schema hay prompt **không** còn cổng đo nào; muốn có bar mới thì phải dựng lại từ đầu. Chữ `eval` còn trong code là lệnh `EVAL` của Redis (`core/redis.py::eval_script`), và trong `docs/hermes/` là mô tả harness của repo Hermes.
