# Scout — bản đồ backend harness (`apps/api`)

Ngày 2026-08-27 · read-only · nhánh `feat/study-canvas-runtime` · alembic head **duy nhất** `e6b3d90c41af` (32 revision, `apps/api/alembic/versions/e6b3d90c41af_add_the_quarterly_financial_store.py`).

---

## 1. Router surface còn sống

Bốn router được include, tất cả prefix `/api/v1` (`src/main.py:116-119`).

| Method | Path | Module:line |
|---|---|---|
| GET | `/` | `src/main.py:162` |
| GET | `/health` | `src/main.py:167` |
| GET | `/scheduler/status` | `src/main.py:172` |
| POST | `/api/v1/auth/register` | `src/auth/router.py:47` |
| POST | `/api/v1/auth/login` | `src/auth/router.py:72` |
| POST | `/api/v1/auth/refresh` | `src/auth/router.py:87` |
| POST | `/api/v1/auth/logout` | `src/auth/router.py:101` |
| GET | `/api/v1/auth/me` | `src/auth/router.py:107` |
| POST | `/api/v1/threads` | `src/agent/router.py:219` |
| GET | `/api/v1/threads` | `src/agent/router.py:234` |
| GET | `/api/v1/threads/{thread_id}` | `src/agent/router.py:241` |
| PATCH | `/api/v1/threads/{thread_id}` (rename + pin) | `src/agent/router.py:262` |
| DELETE | `/api/v1/threads/{thread_id}` (hard delete, cascade) | `src/agent/router.py:291` |
| POST | `/api/v1/threads/{thread_id}/turns` | `src/agent/router.py:333` |
| GET | `/api/v1/turns/{turn_id}/events` (**SSE**) | `src/agent/router.py:400` |
| GET | `/api/v1/turns/{turn_id}` | `src/agent/router.py:445` |
| POST | `/api/v1/turns/{turn_id}/cancel` | `src/agent/router.py:500` |
| GET | `/api/v1/artifacts/{artifact_id}` (frames — đường duy nhất) | `src/agent/router.py:464` |
| POST/DELETE | `/api/v1/messages/{message_id}/flag` | `src/agent/flag_router.py:88`, `:121` |
| POST/DELETE | `/api/v1/messages/{message_id}/helpful` | `src/agent/flag_router.py:139`, `:169` |
| GET | `/api/v1/assets/favicon?domain=` | `src/alpha/favicons.py:350` |

**Không tồn tại**: endpoint gửi message rời (message luôn nằm trong `POST .../turns`), endpoint sửa/xoá message, endpoint list artifact theo thread, endpoint ops/loop, endpoint stocks/signals.

SSE auth **không** dùng `Depends(get_current_user)`: `streaming_user_id` tự parse `Authorization: Bearer` rồi đóng session trước khi stream (`src/agent/router.py:185-208`) — vì response sống tới 10 phút. Header stream + heartbeat 15s comment frame (`src/agent/sse.py:32-36`).

## 2. Model thread/message/turn/tool_call/artifact

Tất cả ở `src/alpha/models.py`.

| Bảng | Cột đáng dùng | line |
|---|---|---|
| `agent_thread` | `id` (Uuid), `user_id`→`users.id` CASCADE, **`title`** (String 255, nullable), `symbols` (ARRAY(String20) + GIN index), **`pinned_at`**, `created_at`, **`updated_at`** (onupdate) | `:26-60` |
| `agent_message` | `id` BigInt, `thread_id`, `seq` (unique per thread), `role` (`user`\|`assistant`\|`summary`), `content` JSONB, `created_at`, `flagged_reason`, `flagged_at`, `helpful_at` | `:84-141` |
| `agent_tool_call` | `thread_id`, `request_message_id`, `tool_name`, `tool_call_id`, `arguments`/`result` JSONB, `spilled_bytes`, `status`, `error`, **`outcome`**, `latency_ms`, `prompt_tokens`, `completion_tokens`, `started_at` | `:143-215` |
| `agent_turn` | `id` Uuid, `thread_id`, `request_message_id`, `response_message_id`, `retry_of_turn_id`, `status`, `terminal_reason`, `cancel_requested_at`, `started_at`, `finished_at`, `last_event_seq`, `draft_content` JSONB (checkpoint) | `:330-378` |
| `agent_artifact` | `id` Uuid, `turn_id` (nullable), `thread_id` (nullable), `study_name`, `study_version`, `params`/**`frames`**/`canvas_spec`/`provenance` JSONB, `created_at` | `:447-500` |
| `agent_knowledge` | user memory: `user_id`, `symbol`, `title`, `body`, `source_url`, `retrieved_at`, `as_of`, `tsv` | `:217-236` |
| `llm_call_usage` | ledger: `owner_type`, `owner_id`, `lane`, `route`, `model`, token counters, `reserved_micro_usd`, `actual_micro_usd`, `pricing_version` | `:380-432` |

**Không có soft-delete ở đâu cả** — không cột `deleted_at`/`archived_at` trên bất kỳ bảng agent nào; `DELETE /threads/{id}` là xoá thật, cascade sang message/turn/tool_call/artifact (`src/agent/router.py:291-313`). **Không có metadata JSONB tự do trên thread** (chỉ `symbols` array). Message không có cột `symbol`/`ticker` — symbol nằm ở thread.

## 3. SSE event vocabulary

`EventType` — **tám** loại, `src/agent/events.py:74-88`:

| event | payload | nơi phát |
|---|---|---|
| `turn.snapshot` | `{through_seq, status, terminal_reason, text, thoughts[], tool_calls[], canvases[], message_id, elapsed_ms}` | dựng per-subscriber lúc `subscribe()`, không bao giờ `publish()` (`events.py:341`, `:510-548`) |
| `content.delta` | `{text, kind, round}` · `kind` ∈ `answer`\|`thought` (`messages.py:48-49`) | `events.py:346-367`; gọi ở `loop.py:1613` (thought) và `:1620` (answer) |
| `tool.call` | allowlist `TOOL_CALL_FIELDS` = `id,name,status,summary,round,results,result_count,kind` | `events.py:118-127`, `:379`; gọi `loop.py:1624` |
| `canvas.ready` | allowlist `CANVAS_FIELDS` = `artifactId,studyName,title,blockCount,round` | `events.py:129-143`, `:386`; gọi `loop.py:1635-1637` qua `getattr` (optional-publisher) |
| `turn.completed` / `turn.incomplete` / `turn.failed` / `turn.cancelled` | `{status, terminal_reason, elapsed_ms, ...}` | `events.py:393-421`; map status→event ở `terminal_event_for` (`:493`) |

Envelope: `{version, seq, type, turn_id, data}`, `ENVELOPE_VERSION = 2` (`events.py:66`, `:145-161`). `seq` = SSE `id` → `Last-Event-ID`; reconnect **restate bằng snapshot**, không replay (`router.py:400-443`). Heartbeat là SSE comment, không tiêu seq.

**Không có event nào cho reasoning status riêng** — "reasoning/status" đi qua `content.delta` với `kind="thought"`. **Không có event `refusal`** — refusal là `turn.failed`/`turn.incomplete` + `terminal_reason`. Danh mục terminal_reason: `loop.py:190-227` (`auth_unavailable`, `cancelled_by_user`, `content_policy_blocked`, `context_overflow`, `empty_answer`, `gateway_timeout`, `llm_call_timeout`, `model_refusal`, `model_unavailable`, `output_cap_exceeded`, `route_error`, `route_rate_limited`, `schema_rejected`, `deadline_expired`, `turn_deadline`, `answer_truncated`).

## 4. Turn lifecycle

Vòng chính: `for round_index in range(MAX_TOOL_ROUNDS + 1)` (`loop.py:850`); `exhausted = round_index == MAX_TOOL_ROUNDS` → call cuối với `tool_choice="none"` + `ROUNDS_EXHAUSTED_NOTE` (`loop.py:872-874`, `:296`).

| Hằng | Giá trị | line |
|---|---|---|
| `MAX_TOOL_ROUNDS` | 4 | `loop.py:160` |
| `MAX_EXTERNAL_TOOL_CALLS` | 6 (chỉ tool `reads_external`) | `loop.py:289`, chặn ở `:1400-1412` |
| `SESSION_CONCURRENCY` | 3 | `loop.py:171` |
| `DEFAULT_MAX_OUTPUT_TOKENS` | 4 000 | `loop.py:180` |
| `MAX_CONTEXT_COMPRESSIONS` / factor | 2 / 0.6 | `loop.py:243-244` |
| `MAX_OUTPUT_TOKENS_REDUCTIONS` / factor / floor | 2 / 0.5 / 1 000 | `loop.py:250-252` |
| `LLM_CALL_TIMEOUT_SECONDS` / `TOOL_TIMEOUT_SECONDS` / `TURN_DEADLINE_SECONDS` | 120 / 30 / 600 | `loop.py:262`, `:265`, `:270` |
| `MAX_USER_INPUT_BYTES` | 8 KiB | `turns.py:77`, kiểm 2 lần (`schemas.py:189`) |

Guardrails: thang bốn bậc đếm trên một Turn — `TurnGuardrails` (`guardrails.py:165`), `Verdict` (`:50`), `Decision` (`:118`), signature qua `call_signature`/`result_signature` (`:153`, `:159`). Halt chỉ dừng **vòng tool**, không dừng Turn (`loop.py:866-873`).

Untrusted wrapping: quyết bởi `registry.reads_external(name)` (`untrusted.py:69`), mà `reads_external` được **suy ra từ `content_trust`** — mặc định `UNTRUSTED` khi không khai (`registry.py:243`, `:268-283`).

**Extension point sạch cho event mới**:
1. Thêm hằng vào `EventType` + allowlist field tuple + method trên `TurnPublisher` (mẫu `canvas_ready`, `events.py:386-391`) — additive, client subscribe theo tên nên không cần bump `ENVELOPE_VERSION` (`events.py:81-84` nói rõ luật này).
2. Loop gọi qua `getattr(self._publisher, "<name>", None)` như `_publish_canvas` (`loop.py:1631-1638`) — publisher là protocol optional (`loop.py:639-653`), nên test publisher cũ không vỡ.
3. Nhớ vào checkpoint **trước** khi announce (`loop.py:1639-1641`) và thêm khoá tương ứng vào `snapshot_from_draft` (`events.py:510-548`) — nếu không, browser reconnect mất event.
4. Projection payload từ tool result đặt ở `messages.py` cạnh `canvas_of`/`outcome_of` (`messages.py:359`, `:398`).

## 5. Model / provider selection

- Model id **chỉ** ở `Settings`: `llm_model_batch = "gpt-5.6-luna"`, `llm_model_session = "gpt-5.6-terra"` (`src/core/config.py:80-81`); `llm_base_url`, `llm_api_key` (`:78-79`).
- Hai workload, không phải hai model cho user chọn: `Workload.BATCH` / `Workload.SESSION` (`core/llm/config.py:48-56`); `LLMConfig.model_for(workload)` (`:240-252`) — không fallback ngầm sang workload kia.
- Lane chat luôn dùng `Workload.SESSION`. **Không có surface nào cho user chọn model** — không field trong `CreateTurnRequest` (`agent/schemas.py:165-196`), không cột trên `agent_thread`.
- Env liên quan: `LLM_STREAMING_ENABLED`, `LLM_REASONING_HISTORY_REQUIRED`, `LLM_CAPABILITY_PROBE_ENABLED`, `LLM_ROUTE_BREAKER_ENABLED`, `LLM_PROMPT_CACHE_CONTROL_ENABLED` (`config.py:92-115`), 8 biến giá + `LLM_PRICING_VERSION` (`:134-143`).

## 6. Share thread / public link

**Không có.** `grep -rniE "share(d|able|_link|_token)?|public_link|publish"` trên `src/` chỉ trả về: chữ "shared" trong docstring về Redis breaker/route, và "share" nghĩa **tỷ trọng thanh khoản** trong `studies/intraday_liquidity.py`. Không model, không route, không token, không cột. Thread luôn gate theo `current_user.id`; thread của người khác trả 404 chứ không 403 (`router.py:298-303`).

## 7. Trading session / freshness

`src/stocks/trading_day.py` — Trading Day = ngày store có snapshot MARKET, **không** phải calendar:
- `latest_trading_day(session)` → `date | None` (`:43`)
- `trading_days_before(session, day, count)` (`:57`) · `trading_days_between` (`:80`)
- `market_generation(session)` → `max(observed_at)`, token cache-busting (`:101`)

`src/core/trading_calendar.py:10` `is_trading_day(day)` — **chỉ theo weekday**, docstring nói thẳng không có holiday calendar (Tết đọc như 9 phiên thường).

**Không có hàm nào trả trạng thái phiên realtime** (pre-open/continuous/ATC/closed). Gần nhất:
- `stocks/intraday/session_window.py:47` `Phase = Literal["ato","am","pm","atc"]`, `phase_of(time) -> Phase | None` (`:93`), `in_session(time)` (`:98`) — phân loại **bucket start theo giờ trong ngày**, không biết hôm nay có phiên hay không, không có `closed`/`pre_open`.
- `SESSION_SETTLED_AT = time(15, 0)` (`intraday/reads.py:34`) — mốc coi phiên hôm nay đã đóng; dùng ở `latest_closed_session` (`:68-86`) và `studies/reads_daily.py:107`, `:149`.

Freshness đọc được:
- `bar_daily`: PK `(symbol, trading_day)`, có **`observed_at`** + `source` + `price_basis` (`stocks/models.py:434-457`).
- `bar_intraday_15m`: PK `(symbol, bucket_start)`, có `trading_day`, `phase`, **`observed_at`**, `source` (`models.py:378-395`).
- `provider_snapshots`: `effective_at` (session stamp) + `observed_at` (machine clock) — `market_generation` đọc cột sau.
- Study đóng băng freshness vào `Provenance{source, as_of, sessions_used, health, reason}` (`studies/contracts.py:136-160`); `health` ∈ `normal|degraded|unavailable` (`:66`).
- Helper đếm mẫu sẵn có: `reads_daily.sessions_available` (`:132`), `intraday/reads.sessions_available` (`:88`).

**Chưa có** API/route nào báo độ mới của store cho FE.

## 8. Universe

- `Universe` dataclass ba tập: `explicit` (operator khai), `cohort` (Profit Leaders — hiện **không seat**, census đã rip), `market` (toàn sàn) — `src/stocks/universe.py:49-97`. `symbols` = explicit + cohort dedupe; **`market` không nằm trong `symbols`** và không tính vào cap, vì `contains` là thứ `get_field` gate (`:64-97`, giải thích tại `:70-82`).
- Cap: `UNIVERSE_MAX_SYMBOLS = 100`, `UNIVERSE_EXPLICIT_MAX = 50` (`:31`, `:37`).
- Nguồn 30 mã: env `UNIVERSE_SYMBOLS` comma-separated (`core/config.py:46`; `docker-compose.yml:61`; `.env` hiện có **30** mã). `Universe.from_settings` (`:100`) dùng ở startup (`main.py:71`); `build_universe` (`:208`) cho path có DB session.
- **Không có mapping tên công ty trong `universe.py`** — tên nằm ở `listing_roster`.
- `src/stocks/listing_roster.py`: `ListingRosterStore.identity_of(symbol)` → `ListedIdentity{symbol, exchange, company_name, is_listed, icb_code, icb_name}` (`:79-92`); `listed_symbols(exchanges=None)` (`:96-113`); `write(...)` → `RosterRefresh{listed, newly_listed, newly_delisted, unclassified}` (`:66-73`, `:115`); `refresh_roster(...)` (`:226`). Provider `VCI`, một call trả **3 586 dòng mọi loại instrument**, lọc `STOCK_TYPE="STOCK"` (`:39-43`); mã rời sàn giữ lại với `exchange="DELISTED"` (`:47`), refresh rỗng bị **refuse** (docstring `:15-18`). Con số "1 523 mã STOCK" không được ghi trong code — code chỉ ghi 3 586 tổng và "about 1,500" ở `universe.py:70`.

## 9. Prompt

`PROMPT_VERSION = "2.7.0"` (`src/agent/prompt/sections.py:29`) — CLAUDE.md còn ghi 2.6.0, **đã lệch**.

Chín section: `MISSION` (`:41`), `INVARIANTS` (`:59`), `HONESTY` (`:120`), `TOOLS` (`:165`), `UNTRUSTED` (`:279`), `MEMORY` (`:321`), `STYLE` (`:347`), `CONTEXT` (`:373`). Luật đã ghim:
- Thứ tự ưu tiên 4 bậc, không ghi đè được (`:63-73`).
- **Không ra chỉ thị hành động cho vị thế cụ thể** — không "bán đi", không tỷ trọng mục tiêu, không mức vào/ra (`:97-104`).
- **Bảng điều kiện**: không cộng trạng thái thành phán quyết, không động từ mệnh lệnh, không gắn mức giá với hành động (`:106-120`) — mới, thêm cho `entry_condition_review`.
- **Số của store thắng số của web**, và khác biệt phải nêu ra (`:143-146`).
- Chỉ đọc được Signal Field đã đăng ký, mã trong Universe, phiên gần nhất đã đóng (`:126-132`); không bịa số VN (`:148-153`); ba lựa chọn khi được hỏi một con số (`:155-157`).
- `TOOLS` mở bằng "Bạn có **mười hai** công cụ" (`:168`) — khớp `CHAT_TOOLSETS`.

Contract: `prompt/contract.py:172` `cache_key = model|PROMPT_VERSION|PROMPT_HASH|tool_signature` — hash tự bắt edit quên bump version.

## 10. Toolsets — 12 tool

`CHAT_TOOLSETS = ("web", "memory", "signals", "studies")` (`src/agent/toolsets.py:98`), kiểm tại import (`:229-247`). `CORE_TOOLS = ()` (`:37`).

| tool | bundle | content_trust | reads_external | khai tại |
|---|---|---|---|---|
| `web_search` | web | UNTRUSTED | **True** | `tools/web.py:310`, `:338` |
| `fetch_url` | web | UNTRUSTED | **True** | `tools/web.py:351`, `:366` |
| `session_search` | memory | TRUSTED_STRUCTURED | False | `tools/memory.py:79`, `:105` |
| `remember_fact` | memory | TRUSTED_STRUCTURED | False (WRITE) | `tools/memory.py:110`, `:148` |
| `recall_facts` | memory | TRUSTED_STRUCTURED | False | `tools/memory.py:153`, `:172` |
| `list_fields` | signals | TRUSTED_STRUCTURED | False | `tools/signals.py:331`, `:343` |
| `get_field` | signals | TRUSTED_STRUCTURED | False | `tools/signals.py:352`, `:362` |
| `get_series` | signals | TRUSTED_STRUCTURED | False | `tools/signals.py:372`, `:382` |
| `check_price_claim` | signals | TRUSTED_STRUCTURED | False | `tools/price_check.py:130`, `:173` |
| `list_studies` | studies | TRUSTED_STRUCTURED | False | `tools/studies.py:320`, `:330` |
| `run_study` | studies | TRUSTED_STRUCTURED | False, `is_async=False` | `tools/studies.py:339`, `:353`, `:363` |
| `render_canvas` | studies | TRUSTED_STRUCTURED | False, `is_async=False` | `tools/studies.py:366`, `:376` |

Chỉ 2 tool tính vào `MAX_EXTERNAL_TOOL_CALLS`. Bundle `signals` gồm cả `check_price_claim` (declared ở `price_check.py`, không ở `signals.py`).

## 11. Auth / tenant

- `users`: `id`, `email` unique, `hashed_password`, `full_name`, `is_active`, **`is_admin`** (`src/auth/models.py:8-24`).
- `refresh_tokens`: `token_hash` (SHA, unique), `expires_at`, `revoked_at` — row giữ sau revoke để phát hiện replay (`:27-49`).
- JWT HS: `create_access_token(user_id)` với `sub` + `exp` (`auth/security.py:46-55`), `decode_access_token` (`:58`); config `auth_secret`, `jwt_algorithm`, `access_token_expire_minutes`.
- **Không có tenant/workspace**: `grep -rni "tenant|workspace" src/` → **0 hit**. Mọi ownership là `user_id` đơn. Đúng như CLAUDE.md (Phase 2 mới có).

## 12. Budget

Hai lớp khác nhau, dễ lẫn:
- **Envelope tiền**: `BudgetLanes{monthly_envelope_usd, analysis_usd, turn_usd, emergency_usd}` (`core/llm/config.py:166-172`), giá trị env `LLM_BUDGET_MONTHLY_USD=45.0`, `ANALYSIS=10.0`, `TURN=30.0`, `EMERGENCY=5.0` (`core/config.py:148-151`). `BudgetLane` enum `analysis|turn|emergency` (`core/llm/admission.py:65-68`); map lane→ceiling ở `:833-835`. Validate lúc startup: `enforce_budget_validation` (`core/llm/budget.py:334`, gọi `main.py:75`).
- **Khoá owner**: `CallOwner{type: OwnerType, id: str, user_id: int|None}` (`admission.py:77-83`); `OwnerType` = `analysis_run` \| **`turn_request_message`** \| `capability_probe` (`:71-74`). Lane chat ghi `owner_type="turn_request_message"`, `owner_id = request_message_id` — **chưa có tenant trong khoá**.
- Quota per-user: `LLM_USER_TURN_STARTS_PER_DAY=20`, `LLM_USER_ACTIVE_TURNS=1`, `LLM_SYSTEM_ACTIVE_TURNS=3`, `LLM_USER_DAILY_USD=3.0`, `LLM_USER_ROLLING_30D_USD=15.0` (`core/config.py:161-165`); `0` = không giới hạn nhưng vẫn ghi ledger.
- `src/agent/budget.py` là chuyện **khác**: ngân sách ký tự/token cho *kết quả tool* (`PER_RESULT_FRACTION=0.15`, `PER_TURN_FRACTION=0.30`, `TurnBudget` `:195`). Đừng lẫn với envelope.

## 13. Freeze boundary thực tế

**ĐƯỢC sửa** (mở theo CLAUDE.md, và đúng với working tree hiện tại):
- `apps/api/src/agent/**` — toàn bộ (harness là surface duy nhất luôn mở).
- `apps/api/src/auth/**` — chỉ cho tenant/budget schema.
- `apps/api/src/studies/**` — toàn bộ (`contracts`, `registry`, `runner`, `widgets`, `warmup`, `frames_buffer`, `reads_daily`, `reads_fundamental`, các Study).
- `apps/api/src/stocks/intraday/**`.
- `apps/api/src/stocks/providers/vnstock_daily.py`, `apps/api/src/stocks/backfill_daily.py`.
- `apps/api/src/stocks/listing_roster.py`, `apps/api/src/stocks/universe.py`.
- `apps/api/src/stocks/models.py` — **chỉ bảng mới**; `bar_daily`, `bar_intraday_15m`, `financial_statement_line`, `financial_ratio_snapshot` đã thêm theo đường này.
- `apps/api/src/stocks/financial/**` + `financial_scan_job.py` (mới, chưa track — phase 09a).
- `apps/web/src/components/canvas/**`, `contracts/canvas-widget-catalog.json`.
- Alembic: **thêm** revision mới trên head `e6b3d90c41af`. Không sửa file đã commit.

**KHÔNG được sửa** (freeze):
- `apps/api/src/stocks/realtime/**` (`contracts`, `storage`, `health`, `policy`).
- `apps/api/src/stocks/signals/**` (24 module: `registry`, `fields`, `serving`, `bars`, `issues`, `sessions`, `price_band`, 11 module pack…).
- `apps/api/src/stocks/providers/{contracts,normalize,store}.py`.
- `apps/api/src/stocks/models.py` phần bảng cũ (`provider_snapshots`, `realtime_*`, `listing_roster` schema, `corporate_actions`).
- `apps/api/src/stocks/trading_day.py`, `src/core/**` (trừ khi contract LLM/config thay đổi có chủ đích), `src/alpha/**` (trừ `models.py` khi thêm bảng agent).
- Mọi `apps/api/alembic/versions/*.py` đã commit.

Lệch cần lưu: CLAUDE.md ghi `PROMPT_VERSION 2.6.0`, thực tế **2.7.0**; CLAUDE.md ghi "8 tool / 3 bundle", thực tế **12 tool / 4 bundle**; CLAUDE.md nói `src/studies/*` là "mới", giờ có 11 module.

## 14. Test suite

`apps/api/tests` — **62 file `test_*.py`** (79 file `.py` tổng, kể `conftest.py`, fixtures, `e2e/server.py`). Cấu trúc: `tests/` (48 file phẳng, chủ yếu agent + llm) · `tests/studies/` (7 test + 2 fixture) · `tests/stocks/{,daily,financial,intraday}/` · `tests/e2e/` (chỉ `server.py`, Playwright chạy từ web) · `tests/fixtures/`.

Test giữ luật kiến trúc:

| Test | Luật nó ghim | path |
|---|---|---|
| `test_agent_capability_contract.py` | `EXPECTED_CATALOG` khoá `(toolset, effect, idempotency, access, content_trust, concurrency)` cho **cả 12 tool** — thêm tool phải sửa file này | `tests/test_agent_capability_contract.py:18+` |
| `test_agent_study_tools.py` | `frames` **không bao giờ** vào message gửi model: `test_the_model_is_handed_a_headline_and_an_id_and_never_the_frames` (`:155`), `test_the_frames_are_absent_from_the_messages_a_turn_would_send` (`:178`) — kiểm "không cell nào reachable", không chỉ "key absent" | `tests/test_agent_study_tools.py` |
| `tests/studies/test_widget_catalog.py` | `contracts/canvas-widget-catalog.json == widgets.catalog_payload()` (`:34`) + fallback vẽ mọi frame kind (`:38`) | `tests/studies/test_widget_catalog.py:26-40` |
| `tests/studies/test_registry.py` | hai chiều: tên trùng, widget lạ, requirement không fetch được | — |
| `tests/studies/test_runner.py` | frames khớp declaration; canvas chỉ vẽ frame tồn tại | — |
| `test_agent_toolsets.py` | `CHAT_TOOLSETS` là selection duy nhất, `AgentLoop(toolsets=None)` về đúng tuple | — |
| `test_agent_prompt.py` | prompt hash / `PROMPT_VERSION` | — |
| `test_turn_sse.py`, `test_agent_turn_events.py` | envelope, seq, snapshot-vs-replay, heartbeat không tiêu seq | — |
| `test_agent_untrusted_results.py` | wrapping theo `reads_external` | — |
| `tests/studies/test_reads_daily.py` | `SERIES_EQUITY`/`SERIES_INDEX` không drift khỏi `providers/vnstock_daily.py` | — |

Guard ở import (không cần test): `widgets.py:127` fallback phải nằm trong catalog · `warmup.py:82` `WARMERS == KNOWN_REQUIREMENTS` · `toolsets.py:247` `_check_the_chat_selection_holds()`.

## Câu chưa giải được

1. "1 523 mã STOCK" không có trong code — chỉ có 3 586 dòng tổng (`listing_roster.py:39`) và "about 1,500" (`universe.py:70`). Nếu plan cần con số chính xác, phải query `listing_roster` thật.
2. `KNOWN_REQUIREMENTS = frozenset({"intraday_bar_15m"})` (`studies/contracts.py:60`) — `entry_condition_review` khai `requires=()`, nên daily/fundamental **không** có warmer: một mã backfill chưa tới sẽ refuse. Nếu tính năng mới cần warm daily, phải mở rộng `KNOWN_REQUIREMENTS` + `WARMERS` cùng lúc.
