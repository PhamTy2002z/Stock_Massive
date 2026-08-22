# B1 — Hermes tool layer (backend)

Worktree `feat/hermes-harness`, `apps/api`. Plan `plans/260822-0000-hermes-harness/plan.md` §2, §3, §6.

## Xoá (git rm)

| Nhóm | Số file |
|---|---|
| `src/agent/tools/**` (catalog, data, computations, compute, fields, knowledge, news, scope, spillover, suite, web, _html, __init__) | 13 |
| `src/agent/mcp/**` | 3 |
| `grounding.py`, `manifest.py`, `widgets.py`, `progress.py`, `suggestions.py`, `context.py`, `blocks.py`, `limits.py`, `admission.py` | 9 |
| `src/agent/prompt/sections.py` | 1 |
| **src tổng** | **26** |
| tests agent-only (build_messages, computation_tools, compute_tools, data_tools, grounding, knowledge_tools, manifest, mcp_registry, news_tool, progress, spillover, system_prompt, tool_catalog, tool_suite, web_tools, widget_release, widgets, widget_replay_route) | 18 |

`tests/test_agent_threat_patterns.py` không tồn tại trong repo → không xoá được, bỏ qua.
`tests/test_agent_guardrails.py` viết lại (module `guardrails.py` bị thay hoàn toàn theo §3).

## Dựng mới

| File | Dòng | Nội dung chính |
|---|---|---|
| `src/agent/registry.py` | 309 | `ToolEntry`(name, toolset, schema, handler, check_fn, requires_env, is_async, description, max_result_size_chars), `ToolContext`, `register/deregister/clear`, chống shadow (`ToolShadowError`, `override=True`), cache `check_fn` TTL 30s (clock injectable), `generation()`, `definitions()`, `get_max_result_size()`, `declared_result_sizes()`, `object_schema()` |
| `src/agent/toolsets.py` | 161 | `TOOLSETS` {web, memory}, `CORE_TOOLS=()`, `resolve_toolset()` đệ quy + memo mọi cấp, `UnknownToolsetError`, `ToolsetCycleError`, `clear_memo()`, `describe()` |
| `src/agent/definitions.py` | 99 | `get_tool_definitions()` — điểm DUY NHẤT build schema; LRU bounded 32 entry, key `(registry generation, toolsets)`, entry tự hết hạn sau `CHECK_TTL_SECONDS` để gate lật vẫn được nhìn thấy |
| `src/agent/executor.py` | 364 | `plan_segments()` parallel/sequential, `PARALLEL_SAFE_TOOLS`, `ToolExecutor.run()` (`asyncio.gather`, không thread pool), parse args JSON → result lỗi (không raise), guardrail before/after, chuẩn hoá result → text, trace callback (sync/async, lỗi trace không mất câu trả lời), mọi call đều có đúng 1 result |
| `src/agent/guardrails.py` | 271 | ladder allow→warn→block→halt đúng 5 ngưỡng §3, `call_signature = (tool, sha256(canonical_json(args)))`, `before_call` block trước dispatch, `after_call` warn/halt, `no_progress` theo hash result, `reset()` |
| `src/agent/budget.py` | 318 | 3 tầng: registry cap → per-result preview (cắt tại newline + `ResultCursor`, không raise) → per-turn aggregate (`TurnBudget.rebalance()`, halve lớn nhất trước, floor 512). Scale: `window=ctx*4`, per_result clamp(15%, 8K..100K), per_turn clamp(30%, 16K..200K). Thứ tự: pinned > config > registry > default |
| `src/agent/untrusted.py` | 100 | `wrap_result()` bọc `<untrusted_tool_result source=...>` khi ≥32 ký tự, `defang()` vô hiệu hoá delimiter lồng (mở + đóng, case/space-insensitive), sanitize nhãn source |
| `src/agent/tools/web.py` | 496 | `web_search` (Tavily, gate `web_tools_enabled` + `tavily_api_key`), `fetch_url` (gate `web_tools_enabled`). Giữ nguyên luật cũ: chỉ http/https, chặn credential, `is_global` cho mọi địa chỉ DNS trả về, DNS-pinned socket + TLS theo hostname, denylist domain + subdomain, re-validate mỗi redirect, `MAX_REDIRECTS=4`, `capped_body()` chặn theo `web_fetch_max_bytes` (declared + streaming), timeout 8s. HTML extractor inline (thay `_html.py`, chỉ 1 consumer) |
| `src/agent/tools/memory.py` | 367 | `session_search` (FTS accent-insensitive trên `agent_message.content->>'text'`, join `agent_thread.user_id`), `remember_fact`, `recall_facts` (`agent_knowledge`, chỉ row của chính user). Transaction ngắn qua session factory, handler async + `to_thread` |
| `src/agent/tools/__init__.py` | 23 | `register_all()` — đăng ký tường minh, idempotent (không side effect lúc import) |

Không file nào import `src.stocks*`, `vnstock`, Signal Registry, hay bảng analysis/provider_snapshots/stock_daily_ohlcv (grep đã kiểm).

## Test

| File | Dòng | Phủ |
|---|---|---|
| `tests/agent_tool_world.py` | 50 | scaffolding: registry cô lập, stub entry |
| `tests/test_agent_tool_registry.py` | 125 | shadow reject/override, re-register cùng toolset, generation, cache check_fn trong/ngoài TTL, invalidate khi re-register, check_fn raise, `requires_env`, thứ tự definitions, declared size |
| `tests/test_agent_toolsets.py` | 94 | 5 tool đúng thứ tự, include đệ quy + dedup, diamond sâu 24 cấp (chứng minh memo), memo bền qua call, unknown → raise, cycle → raise, CORE_TOOLS dẫn đầu |
| `tests/test_agent_tool_definitions.py` | 117 | cache hit (probe 1 lần), invalidate theo generation (register + deregister), gate lật được thấy sau TTL, thứ tự theo request, cache bounded ở 32, mặc định = toàn bộ toolset |
| `tests/test_agent_guardrails.py` | 152 | args đảo thứ tự = cùng call, warn lần 2 (exact), warn lần 3 (same-tool), block lần 6, halt lần 8, block cũng tính vào halt, no_progress warn, streak reset, `reset()` |
| `tests/test_agent_tool_budget.py` | 136 | scale 3 mốc (giữa/floor/ceiling), preview + cursor, text không newline, thứ tự pinned>config>registry>default, per-tool cap, rebalance cắt cái lớn nhất và giữ thứ tự, dừng ở floor không loop |
| `tests/test_agent_untrusted_results.py` | 77 | bọc + nhãn source, tool nội bộ không bọc, <32 ký tự không bọc, forge thẻ đóng/mở bị defang, case+space trick, nhãn source độc bị làm sạch |
| `tests/test_agent_tool_executor.py` | 313 | batch toàn parallel-safe → 1 segment; write → barrier riêng, không đảo thứ tự; tool lạ → sequential; chạy chồng thật (peak=3) nhưng result đúng thứ tự phát; write không chồng (peak=2); handler blocking; unknown tool; JSON args hỏng; handler raise; block không dispatch; halt bỏ phần còn lại nhưng vẫn trả result cho mọi call; warn đi kèm result; trace mọi call; trace lỗi không mất answer; tool tắt |
| `tests/test_agent_web_tools.py` | 299 | 7 dạng địa chỉ nội bộ (loopback, ::1, 10/8, LAN, 169.254, 0.0.0.0), DNS rebind, answer trộn, scheme lạ, credential, denylist + subdomain, normalize, cap byte (declared + streaming + dưới cap), page read + cap từ settings, redirect tới địa chỉ nội bộ, redirect limit, denylist chặn trước request, lane chết → `web_unavailable`, search cap 5 + strip HTML, query rỗng, gate flag/key, declared result size |
| `tests/test_agent_memory_tools.py` | 226 | Postgres thật (DB throwaway): session_search thấy thread của mình (2 match), accent-insensitive, KHÔNG thấy thread người khác, không match → reason, query rỗng bị refuse; remember_fact không cần URL, có URL giữ nguồn, URL sai bị refuse, người khác không recall được, title rỗng bị refuse |

Kết quả chạy thật:

```
python3 -m pytest tests/test_agent_tool_registry.py tests/test_agent_toolsets.py \
  tests/test_agent_tool_definitions.py tests/test_agent_guardrails.py \
  tests/test_agent_tool_budget.py tests/test_agent_untrusted_results.py \
  tests/test_agent_tool_executor.py tests/test_agent_web_tools.py \
  tests/test_agent_memory_tools.py --noconftest -q
→ 110 passed in 0.89s
```

`--noconftest` là bắt buộc ở bước này: `tests/conftest.py:16` import `src.main`, và `src.main` → `router` → `loop.py` đang vỡ (B2 chưa làm). Memory test cần `DATABASE_URL` trỏ Postgres Docker (`192.168.33.101:5432`, PG16) vì Postgres brew trên `localhost` là PG14 và không có extension của repo.

## Quyết định lệch spec (cần B2/chủ sản phẩm biết)

| Chỗ | Spec nói | Thực tế | Lý do |
|---|---|---|---|
| `session_search` | FTS qua `agent_message.tsv` "đã có" | Cột `tsv` **không tồn tại** trên `agent_message` (chỉ `agent_knowledge` có). Dùng `to_tsvector('simple', immutable_unaccent(content->>'text'))` tính tại query, lọc trước bằng join `agent_thread.user_id` (index sẵn) | Thêm generated column + GIN index cần một migration; migration nằm ngoài file ownership của B1 và dễ đụng thứ tự revision với B2. Nếu muốn index, mở một task riêng |
| `PARALLEL_SAFE_TOOLS` | "5 tool đọc-thuần" | 4 tool: `web_search`, `fetch_url`, `session_search`, `recall_facts` | §3 chỉ có 5 tool và `remember_fact` là write. Cho nó vào allowlist là mở đúng thứ allowlist tồn tại để chặn |
| `remember_fact` | (bản cũ có `symbol`, `source_url` bắt buộc) | Bỏ `symbol` (import `src.stocks.shared` bị cấm), `source_url` optional → sentinel `memory://conversation` | Cột `source_url` NOT NULL, không sửa schema ở bước này. Sentinel không phải URL http nên không ai nhầm là trang mở được |
| `recall_facts` | bản cũ đọc cả row `user_id IS NULL` (fact dùng chung) | chỉ row của chính user | Không còn seed fact dùng chung; strict là mặc định an toàn |
| `fetch_url` page cap | bản cũ 3.000 ký tự | 20.000 ký tự | Trước đây trang web là nguồn phụ cạnh store; giờ nó thường là toàn bộ căn cứ của câu trả lời. Budget tầng 2/3 vẫn cắt nếu vượt |
| `ResultCursor` | "con trỏ để model đọc lại phần bị ẩn" | cursor mô tả (offset/hidden/total) + câu hướng dẫn, KHÔNG hứa cơ chế fetch lại | Không có tool nào fetch phần bị ẩn; hứa một handle không tồn tại làm model đi tìm tool không có. Nếu muốn đọc lại thật thì phải thêm `offset` vào schema `fetch_url` — chưa làm vì ngoài scope |
| WebLane | — | giữ nguyên: Redis chết → `reason: web_unavailable`, không fallback fetch trực tiếp | Giữ đúng luật cũ (cache + single-flight + 30 req/phút). Nhưng lưu ý: **web là nguồn tri thức ngoài duy nhất của AI mới**, nên Redis chết = AI mất web. Nếu chủ sản phẩm muốn fail-open thì đó là một quyết định policy, nói thì sửa |

## Để lại cho B2

Import vỡ (đã grep toàn `src/`, `eval/`, `tests/`):

| File | Thiếu |
|---|---|
| `src/agent/loop.py` | `.blocks`, `.context`, `.grounding`, `.progress`, `.tools.*`, `.suggestions`, `.widgets`, và API guardrails cũ (`GuardrailLadder`, `judge_round`) — guardrails.py giờ là `TurnGuardrails.before_call/after_call` |
| `src/agent/service.py` | `admission`, `limits`, `tools` |
| `src/agent/turns.py` | `grounding`, `manifest` |
| `src/agent/router.py` | `context` |
| `src/agent/ops.py` | `grounding` (dòng 80) |
| `src/agent/prompt/__init__.py`, `prompt/contract.py` | `.sections` |
| `src/main.py` | `src.agent.mcp` (dòng 14) |
| `src/alpha/widget_router.py` | `agent.tools`, `agent.widgets` — plan §2 nói xoá file này |
| `src/eval/{harness,scoring,versions}.py` | `manifest`, `tools`, `blocks`, `grounding` |
| `tests/e2e/server.py` | `agent.admission`, `agent.grounding`, `agent.limits` |
| `tests/{test_agent_loop, test_agent_transport, test_agent_turn_lifecycle, test_agent_persistence_paths, test_eval_quality, test_eval_safety, test_eval_scoring, test_turn_admission}.py` | các module trên |

Lưu ý wiring cho B2:
- Gọi `src.agent.tools.register_all()` một lần lúc startup (không có side effect lúc import).
- Lấy schema chỉ qua `definitions.get_tool_definitions(toolsets)`; đừng gọi `registry.definitions()` trực tiếp ở đường nóng (mất cache).
- `TurnBudget` cần `context_length` của model đang chạy → `budget.thresholds_for_context(...)`; `registry_limits=registry.declared_result_sizes()`.
- Bọc untrusted ở tầng dựng message: `untrusted.wrap_result(tool_name, text, source=...)` cho mọi tool result.
- `ToolExecutor(context=ToolContext(user_id, thread_id, now), guardrails=TurnGuardrails(), trace=...)`; `ExecutionOutcome.halted` là tín hiệu dừng round.
- `conftest.py:16` import `src.main` → cả suite còn đỏ ở collection cho tới khi B2 sửa xong.

Status: DONE
Summary: Xoá 26 file trí tuệ cũ + 18 file test cũ; dựng registry/toolsets/definitions/executor/guardrails/budget/untrusted + 5 tool (web × 2, memory × 3) với 110 test mới xanh.
Concerns: `agent_message.tsv` không tồn tại nên session_search dùng FTS tính tại query (không index) — cần chốt có làm migration hay không; `PARALLEL_SAFE_TOOLS` là 4 tool chứ không phải 5; ResultCursor chỉ mô tả, chưa có đường đọc lại phần bị ẩn; Redis chết = mất web tool (giữ luật cũ, có thể là policy cần đổi).
