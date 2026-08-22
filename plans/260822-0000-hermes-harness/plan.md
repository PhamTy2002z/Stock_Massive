# Hermes harness swap — xoá harness cũ, AI tổng quát

Ngày 2026-08-22. Branch `feat/hermes-harness` (worktree, base develop 9f264ca).

Chỉ thị chủ sản phẩm, đã tái khẳng định 4 lần: xoá toàn bộ harness agent cũ, xoá
hết tool đọc dữ liệu nội bộ, xoá cơ chế trả lời qua Recommendation Validator, xây
lại theo khung Hermes Agent như một **AI tổng quát**. Dữ liệu vnstock/FiinQuant từ
nay **chỉ phục vụ bảng giá visual**; AI không đọc chúng nữa.

Report `plans/reports/brainstorm-260820-2323-hermes-harness-swap.md` khuyến nghị
ngược lại (phương án B/C, không xoá). Chủ sản phẩm bác. Plan này thi hành chỉ thị.

## 1. Contract

- **Outcome** — người dùng hỏi bất cứ điều gì và nhận câu trả lời của một AI tổng
  quát: văn xuôi streaming, có thể dùng tool tri thức ngoài (web) và bộ nhớ hội
  thoại, không có khối phân tích dán nhãn, không citation per-figure, không widget.
- **Constraints** — giữ `src/core/llm/*` (biên LLM, spend admission, route breaker,
  taxonomy lỗi); giữ serving path bảng giá (`src/stocks/**`, `src/alpha/router.py`,
  `src/alpha/analysis_router.py`) nguyên vẹn; giữ auth; giữ SSE backend-owned turn
  làm hạ tầng vận chuyển (Hermes cũng cần lớp tương đương) nhưng đổi payload.
- **Non-goals** — không port terminal/sandbox/file tool của Hermes; không port
  gateway Telegram/Discord; không port Programmatic Tool Calling; không giữ
  Signal Registry bridge cho AI (Signal Registry vẫn sống cho bảng giá).
- **Acceptance** — `make test` xanh ở `apps/api`; `pnpm type-check`, `pnpm lint`,
  `pnpm test`, `pnpm build` xanh ở `apps/web`; không còn import `src.agent.tools`
  hay `grounding` ở đâu; hỏi một câu thường nhận được câu trả lời streaming.

## 2. Xoá hẳn

Backend `apps/api/src/agent/`:

| Đường dẫn | Vì sao |
|---|---|
| `tools/**` (21 tool, 13 file) | toàn bộ tool đọc store/Signal Registry/vnstock/knowledge/sandbox |
| `grounding.py` (1410) | Recommendation Validator + degraded notice — cơ chế trả lời bị xoá |
| `manifest.py` (370) | Evidence Manifest |
| `widgets.py` (1138) | typed widget registry sinh từ AI |
| `progress.py` (324) | activity trail 5 phase gắn với tool store |
| `suggestions.py` (228) | follow-up chip sinh từ evidence |
| `context.py` (363) | build message theo Evidence Manifest |
| `blocks.py` (77) | tách block dán nhãn |
| `mcp/**` (3 file) | MCP registry |
| `prompt/sections.py` (539) | System Prompt Contract cũ |
| ~~`limits.py` (130)~~ | **SAI — đã khôi phục.** Không phải trần tool store: đây là rate limit SSE subscribe/reconnect theo user, và sau Next proxy mọi người dùng chung một IP nên bỏ nó thì một kết nối chập chờn làm nghẽn tất cả. `router.py:416,425` phụ thuộc |
| `admission.py` (144) | gộp vào loop mới |

Ngoài `src/agent/`:

| Đường dẫn | Vì sao |
|---|---|
| `src/alpha/widget_router.py` | endpoint replay widget của agent message |
| `src/eval/` — 8 module chạm `src.agent` (`scoring`, `harness`, `record`, `cases`, `versions`, `report`, `categories/quality`, `categories/safety`) | Eval Battery chấm harness cũ |
| `tests/` — 29 file agent-only (496 test) + 5 file eval-coupled (187 test) | test hợp đồng cũ |
| `apps/web/src/components/alpha/widgets/**` | widget từ AI |
| `apps/web/src/components/alpha/message/{citation-chips,figure,content-block,search-progress,source-list,source-drawer,answer-actions,suggestions}.tsx` | grounding/citation/progress UI |

Bảng `agent_knowledge` giữ lại (bộ nhớ hội thoại, không phải dữ liệu thị trường).
Bảng `agent_thread`/`agent_message`/`agent_tool_call`/`agent_turn` giữ — `agent_message.tsv`
đã là session-search FTS của Hermes; `admission.py` của `core/llm` join
`agent_turn`/`agent_thread` cho spend admission của cả Analysis lane.

## 3. Dựng mới theo Hermes

`apps/api/src/agent/`:

| File | Nguồn Hermes | Nội dung |
|---|---|---|
| `registry.py` | `tools/registry.py` | `ToolEntry(name, toolset, schema, handler, check_fn, max_result_size_chars)`, `register()`, `definitions()`, chống shadow tool trùng tên khác toolset, cache `check_fn` TTL 30s |
| `toolsets.py` | `toolsets.py` | dict `{description, tools, includes}`, `resolve_toolset()` đệ quy, `CORE_TOOLS` |
| `definitions.py` | `model_tools.get_tool_definitions` | điểm duy nhất build schema gửi model, cache theo `(toolsets, registry generation)` |
| `executor.py` | `tool_executor.py` + `tool_dispatch_helpers.py` | dispatch, `_PARALLEL_SAFE_TOOLS`, segment planner parallel/sequential, chuẩn hoá kết quả, ghi trace |
| `guardrails.py` | `tool_guardrails.py` | ladder `allow → warn → block → halt`: `exact_failure_warn_after=2`, `same_tool_failure_warn_after=3`, `no_progress_warn_after=2`, `exact_failure_block_after=5`, `same_tool_failure_halt_after=8` |
| `budget.py` | `tool_result_storage.py` + `budget_config.py` | 3 tầng: per-tool cap → per-result spillover (preview + con trỏ đọc lại) → per-turn aggregate; scale theo context window (`window_chars = context_length*4`, per_result `clamp(15%, 8K..100K)`, per_turn `clamp(30%, 16K..200K)`) |
| `untrusted.py` | `make_tool_result_message` | bọc `<untrusted_tool_result source="...">` cho web/mcp khi >32 ký tự, defang delimiter lồng |
| `loop.py` | `conversation_loop.py` | vòng lặp gọn: prompt tổng quát → round tool → stream text. Không grounding, không manifest, không widget |
| `prompt/` | — | prompt AI tổng quát, versioned + hash (giữ để cache prefix ổn định) |

Toolset khởi điểm — **không tool nào chạm dữ liệu thị trường**:

| Tool | Toolset | Đọc gì |
|---|---|---|
| `web_search` | `web` | Tavily |
| `fetch_url` | `web` | HTTP, SSRF guard giữ nguyên luật cũ (chặn IP nội bộ, giới hạn redirect/byte) |
| `session_search` | `memory` | `agent_message.tsv` (transcript của chính người dùng) |
| `remember_fact` | `memory` | `agent_knowledge` (write) |
| `recall_facts` | `memory` | `agent_knowledge` (read) |

## 4. Contract SSE mới

Envelope giữ nguyên hình dạng (`{version, seq, type, turn_id, data}`), `version` lên `2`.
Framing, heartbeat comment 15s, `Last-Event-ID` → snapshot restate: giữ.

| `type` | `data` | Thay cho |
|---|---|---|
| `turn.snapshot` | `{through_seq, status, terminal_reason, text, tool_calls: [{id,name,status,summary}], message_id}` | bản cũ có `blocks`/`widgets`/`progress` |
| `content.delta` | `{text}` | `content.block` |
| `tool.call` | `{id, name, status: "running"\|"ok"\|"error", summary}` | `turn.activity` (5 phase) |
| `turn.completed` / `turn.incomplete` / `turn.failed` / `turn.cancelled` | `{status, terminal_reason, message_id}` | giữ |

Bỏ hẳn: `widget.ready`, `Activity` enum, `ProgressSource`, `Citation`, `ReleasedBlock`,
`unverified_figures`, `source_ids`, `answer_kind`, `risk_notice`, `evidence_manifest`,
`sources_and_methods`, `suggestions`, `search_progress`, `widget_refusals`.

Message content canonical mới: `{text, tool_calls}`.

`TurnDraft` mới: `{text, rounds_used, tool_calls, boundary}`.
`TurnOutcome` mới: `{status, terminal_reason, text, rounds_used, rounds_exhausted, tool_calls, usage, summary_needed, provider_request_id}`.

## 4b. Việc frontend để lại cho B2

- Message content canonical phải mang `status` (hoặc tương đương) để
  `AssistantView.completed` biết một câu trả lời đã lưu là hoàn chỉnh hay bị cắt.
  Hiện frontend đọc `status` optional và **mặc định là hoàn chỉnh**, nên một Turn
  `incomplete` đã lưu sẽ đọc như bình thường tới khi B2 ghi field này.
- `apps/api/tests/e2e/server.py` phải phát `content.delta` (e2e đã đổi `say()` thành
  một delta). E2E chưa chạy được tới khi B2 xong.
- Mất theo `answer-actions.tsx`: hàng Copy/Gửi lại ở cấp câu trả lời. Copy/Sửa/Gửi lại
  trên bong bóng câu hỏi vẫn còn. Chưa thêm lại — chờ chủ sản phẩm quyết có cần không.
- `globals.css` còn rule `.vg-chunk` chết (reveal cadence đã bỏ). Không dọn ở nhánh
  này vì file đang được sửa song song ở cây chính.

## 4c. Import còn vỡ sau B1 — việc của B2b

Đo bằng grep sau khi B1 xoá, không phải phỏng đoán:

| File | Import vỡ | Xử lý |
|---|---|---|
| `src/agent/ops.py` | `.grounding.GROUNDING_FAILED` | bỏ chiều grounding khỏi ops snapshot |
| `src/agent/router.py` | `src.agent.context.TranscriptTurn` | chuyển sang dataclass của loop mới |
| `src/agent/turns.py` | `.grounding` (`GROUNDING_FAILED`, `ReleasedBlock`), `.manifest` (`GateOutcome`, `assemble_message`, `build_manifest`) | dựng message canonical `{text, tool_calls, status}` tại chỗ |
| `src/alpha/widget_router.py` | `tools.data.StoreBackedTools`, `widgets.WidgetDataResolver` | xoá file, bỏ mount ở `main.py` |
| `src/eval/harness.py` | `manifest`, `tools.suite.IntelligentQuantCatalog` | dọn theo §2 |
| `src/eval/scoring.py` | `blocks`, `grounding`, `manifest` | dọn theo §2 |
| `src/eval/versions.py` | `tools.suite.tool_catalog_version` | không còn khái niệm này |
| `src/main.py` | `agent.mcp.{close,initialize}_mcp_registry` | bỏ; MCP đã xoá |
| `tests/e2e/server.py` | `agent.admission.TurnAdmission`, `agent.grounding`, `agent.limits.SubscriptionLimiter` | viết lại, phát `content.delta` |
| `tests/test_agent_loop.py`, `test_agent_transport.py`, `test_agent_turn_lifecycle.py`, `test_turn_admission.py`, `test_eval_quality.py`, `test_eval_safety.py`, `test_eval_scoring.py` | nhiều | viết lại theo contract mới, hoặc xoá cùng phần bị bỏ |

**Bẫy**: `src/core/llm/{__init__,client,probe,protocol}.py` có `from .admission import ...` —
đó là `src/core/llm/admission.py` (spend admission, ADR-0014), **không** phải
`src/agent/admission.py` đã xoá. Không sửa những dòng này.

## 5. Thứ tự thi hành

1. **B1 — lớp tool Hermes**: xoá `tools/**` + 12 file trí tuệ cũ; dựng
   `registry/toolsets/definitions/executor/guardrails/budget/untrusted` + 5 tool mới.
2. **B2 — loop + wiring**: `loop.py` mới, `prompt/` mới; sửa `events/sse/schemas/router/turns/persistence/service`
   theo contract §4; cắt `main.py`, `stocks/jobs.py` (re-home `TOOL_CALL_RETENTION_DAYS`),
   `alpha/models.py` (bỏ vocabulary chết), xoá `alpha/widget_router.py`; dọn `src/eval/`.
3. **C — frontend**: viết lại `lib/alpha-desk/{types,live-turn,transcript}.ts`,
   `hooks/use-live-turn.ts`, `components/alpha/message/*`, `shell/{desk-state,view-chat}.tsx`;
   xoá widgets + component grounding. Giữ toàn bộ REST bảng giá và Analysis lane.
4. **D — cổng kiểm tra**: `make test`; `pnpm type-check && lint && test && build`.
5. **E — tài liệu**: ADR mới ghi quyết định + đánh dấu ADR bị thay thế
   (0009, 0011, 0012, 0015, 0018, 0019, 0020, 0021, 0022, 0023, 0024 và phần agent của 0007/0008/0013/0016).

C chạy song song với B1/B2 vì contract §4 đã chốt trên giấy.

## 6. Rủi ro đã biết

- `src/core/llm/admission.py:19-20,910-919` join `AgentTurn`/`AgentThread` → không xoá 2 bảng.
- `src/stocks/jobs.py:14,68,83` import `TOOL_CALL_RETENTION_DAYS` từ `agent.persistence`
  và xoá `AgentToolCall` trong scheduler production → phải re-home hằng số, không bỏ job.
- `main.py:110` gọi `sweep_interrupted_turns()` vô điều kiện → giữ đường tương đương.
- `apps/web/src/lib/alpha.ts` dùng chung cho chat và rail watchlist → tách cẩn thận.
- `apps/web/src/components/alpha/widgets/units.ts` được Analysis lane import
  (`figure-row.tsx:3`, `price-zone-band.tsx:3`) → di chuyển chứ không xoá.
- `apps/web/src/components/charts/*` chỉ widget dùng → thành mồ côi khi xoá widget.
- `app-shell.tsx:81-89` suy ra màn hình "new" từ `desk.entries.length === 0`.
- Eval gate của repo yêu cầu Eval Report cho PR chạm agent loop/tool schema/validator.
  Việc này chạm cả năm mục; Eval Battery cũ bị xoá cùng harness nên gate phải được
  định nghĩa lại trước khi merge vào `develop`.
- **Deploy không chỉ là restart.** `docker-compose.yml:149` mount
  `./apps/api/src:/code/src` của **cây chính**, nên container api dev đọc source cây
  chính chứ không đọc worktree này. Muốn service chạy harness Hermes phải build image
  từ worktree hoặc đổi bind mount. Một phiên Claude khác đang giữ cây chính với công
  việc Phase 7 chưa commit (`session_search`, memory kind/origin/expiry, injection
  scan, contract 1.10.0, migration `b7d2f5a10c93`, ADR-0025) — nên `develop` sẽ tiến
  lên trước khi nhánh này merge, và merge sẽ có xung đột thật ở `src/agent/tools/`,
  `prompt/`, `docs/adr/`.
- Baseline eval đã lệch từ trước cả nhánh này: fixture pin
  `tool_catalog_version=2d08b9a89e49281f`, HEAD đo `39e3555fc8c48e30`. Số trong
  `docs/eval/` không mô tả hệ thống nào đang chạy.

## 7. Câu hỏi để lại cho chủ sản phẩm

- Analysis lane (`src/alpha/analysis_router.py`, `src/stocks/signals/**`, UI
  `components/alpha/analysis/**`) đang được giữ vì nó thuộc phần "visual" và không
  import `src.agent`. Nếu muốn xoá luôn thì nói, đây là quyết định riêng.
- Eval gate: harness cũ bị xoá nên Eval Battery cũ vô nghĩa. Cần chốt gate mới
  (hoặc bỏ gate) trước khi merge `feat/hermes-harness` vào `develop`.
- Deploy: một phiên Claude khác đang chạy plan `260821-0020` trên cây chính và
  định deploy kiến trúc cũ. Cần chốt phiên nào ra service trước.
