# Hermes Agent — Lớp điều phối (AIAgent) và Tầng lưu trữ (hermes_state)

Nguồn: clone sparse tại `/private/tmp/.../scratchpad/hermes-agent` (NousResearch/hermes-agent, MIT).
Phạm vi: chỉ đọc code + docstring của các file được giao. Không chạy test, không sửa gì.

## 0. Bối cảnh số liệu

- `run_agent.py` 9181 dòng, `agent/conversation_loop.py` 8436 dòng, `agent/chat_completion_helpers.py` 5351, `agent/agent_runtime_helpers.py` 4448, `agent/agent_init.py` 3030, `agent/turn_finalizer.py` 836.
- `hermes_state.py` 13114 dòng + 3 module tách: `hermes_state_search.py` 2493, `hermes_state_common.py` 690, `hermes_state_schema.py` 1340, `hermes_state_portability.py` 714.
- Toàn bộ `agent/` (141 file) = **126.055 dòng**. Ta (`apps/api/src/agent`, 21 file thật đang dùng) = **8.996 dòng**. Hermes lớn hơn ta ~14×, không phải vì phức tạp gấp 14× mà vì bề rộng sản phẩm (platform adapter, TUI, gateway, skill system, plugin system) mà ta không có.

---

## 1. Kiến trúc điều phối

### 1.1 `AIAgent` giữ state gì (Q1)

`class AIAgent` khai báo tại `run_agent.py:412`. `__init__` (`run_agent.py:435`) nhận **60+ tham số** — nhóm lại:

- **Routing/credential**: `base_url`, `api_key`, `provider`, `api_mode`, `credential_pool`, `providers_allowed/ignored/order`, `openrouter_min_coding_score`.
- **Model**: `model`, `max_tokens`, `reasoning_config`, `service_tier`, `request_overrides`, `fallback_model`.
- **Session/identity**: `session_id`, `platform`, `user_id`, `chat_id`, `thread_id`, `gateway_session_key`, `parent_session_id`, `session_db`.
- **20+ callback**: `tool_progress_callback`, `stream_delta_callback`, `notice_callback`, `reasoning_callback`, `tour_callback`, `step_callback`... — đây là cơ chế duy nhất Hermes dùng để đẩy sự kiện lên CLI/gateway/desktop (không có event bus, không SSE nội bộ như `apps/api/src/agent/sse.py` của ta).
- **Budget/iteration**: `max_iterations`, `iteration_budget` (dùng chung cha-con qua `IterationBudget`, `agent/iteration_budget.py`), `run_budget_seconds`.
- **Toolset**: `enabled_toolsets`, `disabled_toolsets`.
- Bên trong `init_agent()` còn set thêm hàng trăm attribute runtime: `_base_url_lower`, `_fallback_index`, `_interrupt_requested`, `_tool_guardrail_halt_decision`, `session_input_tokens`/`output_tokens`/... — `AIAgent` bản chất là **một túi state per-conversation dùng chung `self`** (không có dataclass tách bạch state theo domain).

`__init__` KHÔNG còn chứa logic — nó chỉ gọi `init_agent(self, ...)` (`run_agent.py:526`) và forward toàn bộ 60 tham số nguyên văn.

### 1.2 Vì sao "god file" bị tách, tách theo tiêu chí nào (Q1)

Docstring `agent/turn_finalizer.py:1-19` trích dẫn thẳng:

> "Extracted from `agent/conversation_loop.py` as part of the god-file decomposition campaign (`~/.hermes/plans/god-file-decomposition.md`, Phase 1 step 4 — the post-loop `TurnFinalizer` seam)."

File plan này nằm ở `~/.hermes/plans/` — **thư mục riêng của người phát triển, không commit vào repo** — nên không đọc được nội dung đầy đủ; chỉ suy ra qua các "seam" đã cắt. Quan sát 7 file có docstring "Extracted from `run_agent.py`" (`agent/codex_runtime.py`, `agent/codex_responses_adapter.py`, `agent/conversation_loop.py`, `agent/iteration_budget.py`, `agent/message_sanitization.py`, `agent/chat_completion_helpers.py`, `agent/turn_finalizer.py`, `agent/tool_dispatch_helpers.py`), tiêu chí tách lộ ra hai loại:

1. **Seam theo pha của turn (stateful)** — cắt dọc theo tiến trình một turn: `agent_init.py` = setup (`__init__`), `conversation_loop.py` = thân vòng lặp gọi model + tool, `turn_finalizer.py` = đuôi sau vòng lặp (lưu trajectory, cleanup, persist, hook). Mỗi seam nhận `agent` làm tham số đầu, xử lý xong trả về, không giữ state riêng.
2. **Cluster theo domain (pure function, stateless)** — `message_sanitization.py`, `iteration_budget.py`, `tool_dispatch_helpers.py`: nhóm hàm không phụ thuộc `agent` (hoặc chỉ đọc, không tạo side-effect ngoài input) theo *một trách nhiệm duy nhất*, ví dụ toàn bộ hàm sanitize ký tự lỗi UTF-8/surrogate nằm một chỗ.

Cả hai loại đều giữ **re-export ngược lại `run_agent.py`** để `from run_agent import X` và `mock.patch("run_agent.X", ...)` cũ không vỡ (`agent/iteration_budget.py:7-8`: *"`run_agent` re-exports `IterationBudget` so existing imports keep working unchanged."*).

AGENTS.md xác nhận đây là hạng mục công việc được khuyến khích công khai (`AGENTS.md:60-64`):

> "**Refactor god-files into clean modules.** Extracting a multi-thousand-line cluster out of `cli.py` / `run_agent.py` / `gateway/run.py` into a focused mixin or module is wanted work, even when the diff is huge and mechanical."

### 1.3 Pattern "module function nhận `agent` làm tham số đầu + thin forwarder" (Q2)

Ví dụ chuẩn: `build_api_kwargs(agent, api_messages, tools_for_api=None)` ở `agent/chat_completion_helpers.py:1825`. `AIAgent` không có method `build_api_kwargs` riêng — code gọi thẳng hàm module-level, truyền `self`.

Với `run_conversation` thì khác — **không hoàn toàn "thin"**: `run_agent.py:8467` định nghĩa `def run_conversation(self, ...)` với docstring `"""Forwarder — see agent.conversation_loop.run_conversation."""`, nhưng thân forwarder này dài ~370 dòng, giữ lại toàn bộ phần **cross-cutting của hạ tầng relay/kanban/observability**: tạo `relay_turn_id`, mở `durable_turn_lease_thread` (giữ turn sống qua mất kết nối — xem `run_agent.py:8820-8850`), rồi mới gọi hàm đã tách `run_conversation(self, user_message, ...)` từ `agent/conversation_loop.py:1762`, và `finally` dọn lease.

**Lợi**:
- Test-patch cũ (`mock.patch("run_agent.OpenAI", ...)`, `patch("run_agent.cleanup_vm", ...)`) tiếp tục hoạt động dù logic đã dời đi — vì `run_agent.py` vẫn import/re-export các symbol đó (`run_agent.py:100-110`).
- `run_agent.py` co lại còn phần **điều phối hạ tầng process-wide** (lease, task_context cho observability), còn logic nghiệp vụ turn nằm module riêng, dễ đọc/test độc lập.

**Hại**:
- "Forwarder" là forwarder giả — code đọc `run_agent.py` để hiểu hạ tầng lease vẫn phải nhớ thân thật nằm ở `conversation_loop.py`, hai file phải đọc cùng nhau mới hiểu một turn. God-file không biến mất, chỉ **chia hai lớp** (infra glue ở trên, business logic ở dưới) — độ phức tạp tổng không giảm, chỉ dễ định vị hơn.
- Mọi module tách phải tự khai báo `_ra()` để gọi lại symbol trên `run_agent` — một lớp indirection runtime cho mọi lời gọi cross-module.

**Vì sao cần `_ra()`**: mỗi module tách định nghĩa riêng
```python
def _ra():
    """Lazy reference to run_agent so callers can patch
    run_agent.OpenAI / run_agent.cleanup_vm / ... and have those
    patches reach this code path."""
    import run_agent
    return run_agent
```
(xuất hiện gần như nguyên văn ở `agent/agent_init.py:98`, `agent/chat_completion_helpers.py:104`, `agent/conversation_loop.py:536`, `agent/system_prompt.py:67`, `agent/tool_executor.py:270`...). Lý do: test suite (28+ file theo comment `run_agent.py:104-110`) patch trực tiếp attribute trên module `run_agent` (`run_agent.cleanup_vm`, `run_agent.OpenAI`). Nếu module tách `import cleanup_vm` tĩnh ở đầu file, patch trên `run_agent.cleanup_vm` không có tác dụng (binding đã chụp giá trị cũ). `_ra()` trì hoãn import đến lúc gọi, luôn đọc attribute *hiện tại* trên `run_agent` — giữ nguyên hợp đồng test cũ mà không phải viết lại hàng trăm test. Cái giá: mọi lời gọi xuyên module tốn một `import` + attribute lookup runtime, và nó chỉ đúng khi patch nhắm vào `run_agent.<name>` — patch nhắm module con (`agent.chat_completion_helpers.cleanup_vm`) sẽ không được `_ra()` nhìn thấy vì `_ra()` luôn trỏ về `run_agent`.

### 1.4 Request kwargs xây thế nào (Q3)

`build_api_kwargs(agent, api_messages, tools_for_api=None)` — `agent/chat_completion_helpers.py:1825-2114` — rẽ theo `agent.api_mode`, mỗi nhánh gọi `_get_transport().build_kwargs(...)` với tập tham số khác nhau:

| api_mode | tham số riêng | ghi chú |
|---|---|---|
| `anthropic_messages` | `preserve_dots`, `is_oauth`, `drop_context_1m_beta`, `fast_mode` | merge thêm `_merge_nous_portal_messages_extra_body` cho route Nous Portal (`:1854`) |
| `bedrock_converse` | `region`, `guardrail_config`, không dùng OpenAI client | bypass hoàn toàn SDK OpenAI (`:1858-1868`) |
| `codex_responses` | `context_management` (native compaction, chỉ bật cho gpt-5.6 trên OpenAI/ChatGPT-Codex/xAI), `replay_encrypted_reasoning`, `github_reasoning_extra` | xAI cần **deep-copy** `tools_for_api` trước khi strip `pattern`/`format`/slash-enum khỏi JSON Schema — không copy sẽ **mutate schema tool dùng chung cho mọi agent** (`:1912-1930`, bug #27907) |
| `chat_completions` (default, có provider profile) | `provider_profile`, `ollama_num_ctx`, `openrouter_min_coding_score`, `qwen_session_metadata` | có registry `providers/` cung cấp hook theo provider; không có profile → rơi vào "legacy flag path" cồng kềnh hơn (từng flag `is_openrouter`, `is_nous`, `is_qwen_portal`, `is_kimi`, `is_lmstudio`...) |

Tham số **bị bỏ khi provider không hỗ trợ**: `temperature` bị omit hoàn toàn nếu `_fixed_temperature_for_model` trả sentinel `OMIT_TEMPERATURE` (một số model chỉ nhận temperature=1 hoặc không nhận field này — `:1975-1983`); `max_tokens` Anthropic-compatible chỉ set khi model nằm trong `_ANTHROPIC_OUTPUT_LIMITS` — comment giải thích rõ: nhiều proxy (Bedrock, NVIDIA, LiteLLM, vLLM) default 4096 nếu thiếu field này, dễ vỡ khi có thinking + tool call lớn (`:2002-2012`); ảnh trong message bị `_prepare_messages_for_non_vision_model` strip nếu model không vision.

### 1.5 Cleanup tài nguyên mỗi turn (Q4)

`agent/turn_finalizer.py:266-292` (`finalize_turn`) bọc 3 bước dọn dẹp fallible **độc lập nhau**, mỗi bước fail không chặn bước sau:
```python
_cleanup_errors = []
try: agent._save_trajectory(...)
except Exception as e: _cleanup_errors.append(f"save_trajectory: {e}")
try: agent._cleanup_task_resources(effective_task_id)
except Exception as e: _cleanup_errors.append(f"cleanup_task_resources: {e}")
...
try: <_persist_session sau khi strip empty-response scaffolding>
except Exception as e: _cleanup_errors.append(f"persist_session: {e}")
```
Docstring giải thích lý do (**issue #8049**): trước đây một raise ở bất kỳ bước nào (file I/O của trajectory, gọi VM/browser qua network, SQLite write) làm mất luôn `final_response` mà caller đang chờ — "subprocess wrappers saw an empty stdout with no traceback". `cleanup_errors` giờ được đính vào `result` để caller biết turn "xong nhưng dọn dẹp lỗi", không nhầm với "turn lỗi".

`cleanup_task_resources(agent, task_id)` (`agent/chat_completion_helpers.py:3195-3238`): dọn VM sandbox + browser session cho task, **có exception** cho môi trường persistent (`persistent_filesystem=True`, hoặc browser headed mode) — không dọn để không huỷ session người dùng đang xem, để lại cho "idle reaper" riêng dọn theo TTL.

**Rò rỉ tài nguyên từng xảy ra** (đọc được qua comment):
- **httpx connection pool** (`agent/chat_completion_helpers.py:4066-4079`): abort giữa stream (`interrupt`) mà không gọi `stream.close()` trên đúng thread sở hữu để lại connection "checked out" vĩnh viễn khỏi pool — mỗi lần interrupt rò một connection tới khi pool cạn.
- **SQLite fd leak** trong read-connection pool (`hermes_state.py:3578-3583`, `:3634-3648`): connection mở trên một thread rồi bị close trên thread khác → `sqlite3.ProgrammingError` bị `except Exception: pass` nuốt mất → fd không giải phóng, permit pool bị "stranded" vĩnh viễn. Có cả file ảnh `sqlite_leak_fix.png` ở root repo minh hoạ pattern này (không đọc nội dung ảnh, chỉ ghi nhận sự tồn tại — bằng chứng đây là một bug đủ nghiêm trọng để họ vẽ diagram debug).
- **Stream callback leak sang turn sau**: `agent._stream_callback = None` được set cứng cuối `finalize_turn` (`:767`) với comment "Clear stream callback so it doesn't leak into future calls" — một turn cũ quên clear sẽ khiến turn sau gọi nhầm callback cũ.

---

## 2. Tiêu chí tách module & quy ước `AGENTS.md`

### 2.1 The Footprint Ladder (`AGENTS.md:182-212`)

Quy tắc chọn nơi đặt một năng lực mới, ưu tiên từ ít footprint nhất:
1. Extend code có sẵn (0 surface mới)
2. CLI command + skill (0 model-tool footprint)
3. Service-gated tool qua `check_fn` (0 footprint khi chưa cấu hình)
4. Plugin (ngoài core)
5. MCP server trong catalog (0 core-schema footprint, tái dùng được)
6. New core tool — **chọn cuối cùng**, chỉ khi thực sự nền tảng và không dùng terminal+file/MCP thay được.

Lý do nêu rõ: *"New model tools are the expensive exception — every tool ships on every API call."* Đây là tư duy áp được cho tool catalog của ta (`apps/api/src/agent/tools/suite.py` — `IntelligentQuantCatalog`) khi cân nhắc thêm tool mới.

### 2.2 Bất biến khác trong `AGENTS.md` (trích nguyên văn)

- **`.env` chỉ cho secret** (`AGENTS.md:647-660`, mục "What we don't want"): *"`.env` is for secrets only (API keys, tokens, passwords). All behavioral settings — timeouts, thresholds, feature flags, display prefs — go in `config.yaml`. ... Reject PRs that tell users to 'set X in your .env' unless X is a credential."*
- **Prompt-cache stability** (`AGENTS.md:1206-1216`): *"Do NOT implement changes that would: Alter past context mid-conversation / Change toolsets mid-conversation / Reload memories or rebuild system prompts mid-conversation. ... The ONLY time we alter context is during context compression."* Kèm quy tắc lệch pha: lệnh sửa system-prompt-state (skill, tool, memory) default **deferred** (áp dụng phiên sau), có cờ `--now` để invalidate ngay.
- **Không hardcode `~/.hermes`** (`AGENTS.md:1317-1320`): *"Hardcoding `~/.hermes` breaks profiles ... This was the source of 5 bugs fixed in PR #3575."* — dùng `get_hermes_home()`.
- **Behavior contracts over snapshots** (`AGENTS.md:73-77`, mở rộng ở dòng 1506+): test phải assert *quan hệ bất biến*, không snapshot giá trị hiện tại (model list, config version literal, enum count) — snapshot-test vỡ mỗi lần thêm model/provider mới.
- **god-file refactor được khuyến khích công khai** (`AGENTS.md:60-64`, đã trích ở 1.2).
- **Speculative infrastructure bị từ chối** (`AGENTS.md:97-99`): hook/callback không có consumer cụ thể bị reject — *"Adding a hook is easy; removing one after plugins depend on it is hard."*
- **Third-party product không vào core tree** (`AGENTS.md:118-127`): observability backend, SaaS vendor không được merge vào `plugins/` trong chính repo core — phải là plugin repo riêng, vì gánh maintenance dài hạn cho một backend họ không sở hữu.
- **"Surface capability is a property of the SESSION, never of the process env"** (`AGENTS.md:213-251`): năng lực chỉ dùng được vì "ai đang ở đầu kết nối" (desktop pane, browser trong app) phải resolve theo **session's platform**, không theo env var của backend process — vì backend process có thể phục vụ nhiều session/topology khác nhau cùng lúc.

Không tìm thấy nội dung `~/.hermes/plans/god-file-decomposition.md` (nằm ngoài repo, thuộc máy dev gốc) — chỉ suy luận được tiêu chí qua kết quả tách (mục 1.2).

---

## 3. Tầng lưu trữ

### 3.1 Schema (Q6)

`SCHEMA_VERSION = 26` (`hermes_state_common.py:219`). `SCHEMA_SQL` (`:249-434`) khai báo qua `CREATE TABLE IF NOT EXISTS` — bảng chính:

- **`sessions`**: PK `id` (TEXT/UUID), `parent_session_id` self-FK, `session_key`/`chat_id`/`chat_type`/`thread_id` (định danh routing gateway), `system_prompt_hash` → FK `system_prompts(hash)` (dedupe system prompt lặp lại giữa session), cột usage/cost tổng hợp (`input_tokens`, `estimated_cost_usd`...), `end_reason`, `archived`/`pinned`/`hidden`/`rewind_count`.
- **`messages`**: PK autoincrement `id`, FK `session_id`, `role`, `content`, `tool_call_id`/`tool_calls`/`tool_name`, `reasoning`/`reasoning_content`/`reasoning_details`/`codex_reasoning_items` (nhiều biến thể vì mỗi provider trả reasoning khác định dạng), `active`/`compacted` (đánh dấu message bị context-compression che, không xoá), `api_content` (bản đã gửi API, tách khỏi `content` hiển thị).
- **`session_model_usage`**: composite PK `(session_id, model, billing_provider, billing_base_url, billing_mode, task)` — usage/cost tách theo *model+route+task* trong một session (một session có thể gọi nhiều model: main + auxiliary task).
- **`compression_locks`**, **`session_turn_leases`**: lock có `expires_at` — cơ chế lease timeout thay vì lock vĩnh viễn, tránh deadlock khi process crash giữa turn.
- **`async_delegations`**: theo dõi subagent chạy nền, có `owner_pid`/`owner_started_at` để phát hiện dead-owner.

**Lineage khi session bị reset/rotate** (Q6): không có bảng lineage riêng — quan hệ suy ra từ `sessions.parent_session_id` + heuristic SQL. `_RESET_END_REASONS` (`hermes_state_common.py:101-114`):
```python
_RESET_END_REASONS = (
    "session_reset", "session_switch", "idle", "daily",
    "suspended", "resume_pending_expired",
)
```
Một session con được coi là "reset continuation" (không phải branch, không phải subagent) nếu nó mang marker `model_config.$._reset_from` (session mới) HOẶC — với DB cũ trước khi có marker — khớp `_legacy_reset_child_sql`: cùng `session_key` với parent VÀ `parent.end_reason IN _RESET_END_REASONS` (`:117-130`). Có 4 loại quan hệ cha-con phân biệt bằng SQL riêng: `_BRANCH_CHILD_SQL` (marker `_branched_from`, giữ hiển thị vĩnh viễn), `_COMPRESSION_CHILD_SQL` (con sinh ra do context bị nén, giấu khỏi picker), `_RESET_CHILD_SQL` (giấu khỏi picker, coi là "chuyển tiếp" không phải hội thoại riêng), và **ephemeral** (`_ephemeral_child_sql`: có `parent_session_id` nhưng KHÔNG rơi vào 3 loại trên → subagent run, giấu hoàn toàn). `_LISTABLE_CHILD_SQL` (`:148-152`) = root hoặc branch/reset — đây là filter mà mọi picker UI dùng để không show rác subagent/compression.

### 3.2 FTS5 (Q7)

`FTS_SQL` (`hermes_state_common.py:483-528`): bảng `messages_fts` là **external-content FTS5** (`content='messages', content_rowid='id'`) trên 3 cột `content`, `tool_name`, `tool_calls` — không tự chứa dữ liệu, chỉ index, dữ liệu thật vẫn ở `messages`. Đồng bộ qua 3 trigger AFTER INSERT/DELETE/UPDATE — **update chỉ bắn khi đúng 3 cột đó đổi** (`AFTER UPDATE OF content, tool_name, tool_calls` + `WHEN old.content IS NOT new.content ...`) để tránh ghi FTS mỗi khi chỉ `compacted`/`observed` đổi (comment ghi rõ đây là fix issue **#68858 / #73639** — I/O saturation).

`FTS_TRIGRAM_SQL` (`:547-608`): bảng thứ hai `messages_fts_trigram` dùng tokenizer `trigram` cho tìm kiếm substring CJK (unicode61 mặc định tách ký tự CJK thành từng token đơn, vỡ phrase match). Nguồn là **view** `messages_fts_trigram_src` loại `role='tool'` — vì tool output (base64, file dump) là ~90% byte nhưng gần như không ai search, index trigram tốn ~2.6× dung lượng text nó bao — loại bỏ tiết kiệm đáng kể.

Cập nhật: real-time qua trigger cho mọi write bình thường. Có cơ chế **deferred rebuild** khi tokenizer FTS5 không có sẵn hoặc index bị detach do corrupt: 2 key trong `state_meta` (`fts_rebuild_high_water`, `fts_rebuild_progress`) định nghĩa "row nào đã có trong index" trong lúc rebuild nền chạy dần — mọi trigger đều gate theo `id > high_water OR id <= progress` để không ghi trùng/ghi thiếu (`hermes_state_common.py:459-481`).

### 3.3 `apply_wal_with_fallback` (Q8)

`hermes_state.py:1064-1064+` (docstring rất dài). WAL cho phép nhiều reader đồng thời + một writer không block nhau — cần cho gateway đa nền tảng đọc/viết cùng session.db. Fallback về DELETE journal khi:
- Filesystem không hỗ trợ WAL (NFS, SMB, một số FUSE, ZFS) — SQLite có thể **raise** `OperationalError("locking protocol")` hoặc (đặc biệt macOS NFS) **im lặng không raise**, chỉ trả về mode vẫn là "delete" qua kết quả PRAGMA — hàm phải đọc giá trị trả về, không dựa vào absence-of-exception.
- SQLite build còn **WAL-reset corruption bug** (issue **#69784**) — dò qua `is_sqlite_wal_reset_vulnerable()`; nếu có, **từ chối bật WAL trên DB mới/không-WAL**, nhưng **không bao giờ downgrade một DB đang WAL** (an toàn hơn là để nguyên).
- Có gate cấu hình `database.journal_mode` (`resolve_journal_mode()`) cho operator chọn DELETE tường minh (ví dụ trên virtiofs/NFS/SMB).

`require_wal=True` cho phép caller yêu cầu WAL bắt buộc → raise `WalUnsupportedError` (subclass `sqlite3.OperationalError`) thay vì fallback âm thầm. Có "gate lịch sử" đáng chú ý: comment tại `hermes_state.py:1080-1095` kể lại một PR (**#71724**) từng revert gate #69784 với lý luận "DELETE mới là mode gây corrupt", nhưng bị maintainer đảo lại vì so sánh đó bị **confound** (SQLite version khác kèm fix khác) — giữ gate lại vì chưa có bằng chứng WAL an toàn hơn trên runtime đang ship.

### 3.4 Portability (Q9)

`hermes_state_portability.py` — `export_session`/`export_session_lineage`/`export_all` để backup/analysis (JSONL), `import_sessions` để phục hồi. **Bị loại khi export → import** (không phải lúc export): `import_sessions` (`:284-378`) chủ động **reset** các field runtime "sống": `last_activity_at`, `last_activity_description`, `last_activity_provenance` — vì bản export vẫn *bao gồm* chúng (đúng bản ghi), nhưng phục hồi lại một nhãn "đang hoạt động" trên máy không có agent nào đang chạy là **giả tạo activity** khiến watchdog/session-listing hiểu sai. Cũng reset gateway routing/handoff/rewind — vì import trả lại *lịch sử hội thoại*, không phải *quyền sở hữu một channel/process đang sống*. Session id trùng bị skip; con trỏ về parent không tồn tại trong payload bị "detach" (`parent_session_id=NULL`) để không vỡ FK khi import một phần.

### 3.5 Migration schema (Q10)

**Không có engine migration có version-down như Alembic.** Hai lớp:
1. **Cột thêm (additive)**: `_reconcile_columns()` (`hermes_state_schema.py:553-612`) diff cột khai báo trong `SCHEMA_SQL` (nguồn sự thật duy nhất, parse bằng regex) với cột thật (`PRAGMA table_info`), `ALTER TABLE ADD COLUMN` cho cột thiếu — **mỗi lần mở DB**, không cần version-gate. Docstring: *"Column additions are handled by `_reconcile_columns()` ... Version-gated migration blocks are no longer needed for ADD COLUMN."*
2. **Đổi PK / backfill dữ liệu (không declarative được)**: giữ chain `if current_version < N: ...` trong `_init_schema` (`hermes_state_schema.py:899-960+`) — chỉ dùng cho việc SQLite không tự làm được bằng ALTER (đổi PRIMARY KEY phải rename→create→copy→drop, ví dụ `_heal_gateway_routing_pk` dòng 620, `_heal_session_model_usage_pk` dòng 693) hoặc backfill dữ liệu một lần (v10 trigram backfill). `SCHEMA_VERSION` chỉ là **một số nguyên trong bảng `schema_version`**, so sánh `current_version < N`, **không có rollback**.

So với Alembic của ta: Hermes chấp nhận rủi ro "ALTER TABLE ADD COLUMN không kiểm soát được thứ tự" để đổi lại **zero-downtime, không cần chạy lệnh migrate tay** trên máy người dùng cuối (SQLite local, không ai chạy `alembic upgrade`). Alembic đúng hơn cho Postgres nhiều người viết đồng thời + cần rollback được.

---

## 4. Bài học (issue/PR density)

Tổng cộng **300 số issue/PR duy nhất** xuất hiện trong comment/docstring của các file được giao (đếm bằng `grep -oE "#[0-9]{3,6}" | sort -u`) — quá nhiều để viết bài học riêng cho từng số trong ngân sách báo cáo này. Phân bố theo file (số lượng issue riêng biệt):

`run_agent.py` 60, `agent/conversation_loop.py` 62, `agent/chat_completion_helpers.py` 44, `agent/agent_runtime_helpers.py` 54, `agent/agent_init.py` 28, `hermes_state.py` 62, `agent/turn_finalizer.py` 16, `hermes_state_schema.py` 11, `hermes_state_search.py` 10, `hermes_constants.py` 7, `hermes_logging.py` 2, `utils.py` 3, `hermes_bootstrap.py` 1, `hermes_state_common.py` 2, `hermes_state_portability.py` 1. (`agent/__init__.py`, `agent/errors.py`, `hermes_time.py`, `agent/trace_upload.py`, `agent/trajectory.py`: 0.)

**Mật độ này tự nó là bài học**: một comment gắn số issue mỗi khi sửa một bug cụ thể (không chỉ mô tả hành vi) là văn hoá review của Hermes — dòng code khó hiểu luôn có "vì sao" truy vết được, không chỉ "làm gì". Đây khớp với rubric ở `AGENTS.md` mục "Before you call it a bug — verify the premise": *"If you can't point to the exact line where the bug manifests AND show the fix changes that line's behavior, you haven't verified the premise."*

Bài học một-dòng cho các issue **đã đọc có ngữ cảnh đầy đủ** trong lúc research (không phải toàn bộ 300):

| # | Bài học |
|---|---|
| #8049 | Cleanup cuối turn phải cô lập lỗi từng bước — 1 raise không được nuốt mất response đã có |
| #27907 | Sanitize schema tool cho provider lỗi (xAI) phải deep-copy trước khi mutate — schema dùng chung toàn agent |
| #24996 | Fallback chain cạn hết cần cooldown ngắn, tránh client retry ngay lập tức re-marshal context 80k token |
| #81521 | Đóng stream bị interrupt phải join thread sở hữu trước khi raise — tránh corrupt LIFO stack scope |
| #68858 / #73639 | Trigger FTS5 phải gate theo cột thực đổi (`UPDATE OF`), không phải mọi UPDATE — tránh I/O saturation |
| #69784 | Biết một bug cụ thể của runtime dependency (SQLite WAL-reset) và giữ workaround dù benchmark sau nói khác — vì benchmark bị confound |
| #71724 | Đảo một quyết định an toàn dựa trên so sánh benchmark không kiểm soát biến — bài học review: yêu cầu "cùng runtime version" mới so sánh được |
| #63048/#63425 | Thứ tự check (auto-detect provider trước khi validate credential-pool) quan trọng — đảo thứ tự tạo regression |
| #76354 | Export/import field "đang sống" (activity) là bất đối xứng có chủ đích — export giữ, import reset |
| #3575 | 5 bug cùng gốc (hardcode `~/.hermes`) → nâng thành rule cứng trong AGENTS.md, không sửa từng chỗ |
| #16751 | Re-index FTS cho tool_name/tool_calls — bị supersede bởi #23270's external-content layout, nhưng giữ lại code cũ "cho khảo cổ" (đọc được tại sao một migration step trở nên unreachable) |
| #59203 | Composite PK thêm sau không ALTER được trên SQLite → cần rebuild bảng (`_heal_gateway_routing_pk`) — SQLite giới hạn ALTER PK là ràng buộc thật, không phải thiếu sót |
| #43849/#44100 | "Assistant row có tool_calls nhưng không có text" là invariant cần hàm riêng kiểm tra (`_is_pure_tool_call_tail`) — không inline check rải rác |

Danh sách đầy đủ 300 số có thể tái tạo bằng lệnh grep trên; phần còn lại (chưa đọc ngữ cảnh riêng từng cái) không được gán bài học ở đây để tránh suy đoán không có nguồn.

---

## 5. Port được gì sang `apps/api/src/agent/{service,runtime,persistence}.py` + `CLAUDE.md`

Bối cảnh: kiến trúc của ta (`service.py` 187 dòng = composition root DI, `turns.py` 732 dòng = lifecycle Turn, `persistence.py` 1047 dòng = transaction ngắn) **đã** theo mẫu sạch hơn Hermes ngay từ đầu — không có class 9000 dòng, không có 60-tham-số constructor. Vì vậy phần lớn kỹ thuật "chống god-file" của Hermes (seam theo pha, `_ra()`, forwarder) **giải quyết một vấn đề ta chưa có**. Cái đáng port là các *quy ước process* và một vài *pattern lỗi cụ thể*, không phải kiến trúc.

**Port cụ thể:**

1. **Cleanup cô lập theo bước, gom lỗi vào result** (từ `finalize_turn`, mục 1.5/#8049) → `apps/api/src/agent/turns.py`/`persistence.py`: nếu terminal-transaction hoặc bất kỳ bước dọn dẹp sau khi turn xong (ví dụ ghi `agent_tool_call` retention, invalidate cache) có thể raise, bọc từng bước với try/except riêng, gom vào một field kiểu `cleanup_errors` trên kết quả turn — tránh một lỗi phụ (vd. dọn cache) làm mất câu trả lời đã sinh ra thành công. Đối chiếu: `turns.py:27-33` đã có nguyên tắc "một transaction terminal", nhưng chưa rõ có tách các bước *sau* terminal transaction (nếu có) theo kiểu cô lập lỗi này chưa — cần audit.
2. **Quy tắc "no cross-tool reference trong tool schema description"** (`AGENTS.md` known pitfalls) → áp cho `apps/api/src/agent/tools/suite.py` / `manifest.py`: mô tả tool không nên nhắc tên tool khác theo cách cứng (vì tool đó có thể bị tắt/thiếu key) — nếu cần liên kết, làm động lúc build catalog, không viết cứng trong docstring/description tool.
3. **Đưa nguyên tắc ".env chỉ cho secret" vào `CLAUDE.md`** — hiện `CLAUDE.md` không có câu này rõ ràng. Thêm một dòng ngắn: *"Biến môi trường (`.env`) chỉ dành cho secret (API key, token, DB credential); mọi cấu hình hành vi (timeout, feature flag, ngưỡng) đi vào settings/config, không tạo `ENV_VAR` mới cho việc này."* — khớp tinh thần `src/core/config.py` (Pydantic Settings) đang có, chỉ cần nói rõ để tránh trôi dần.
4. **Footprint Ladder rút gọn cho tool mới** — thêm vào `CLAUDE.md` mục "Agent skills" hoặc gần đó: trước khi thêm tool mới vào `IntelligentQuantCatalog`, ưu tiên: mở rộng tool có sẵn → endpoint API thường (không phải agent tool) → tool có `check_fn`/gate theo config → tool mới (cuối). Lý do đưa vào CLAUDE.md: mọi tool mới tốn schema trên *mọi* lời gọi model, và ta chưa có văn bản nào nói rõ tiêu chí này — quyết định hiện đang ngầm định trong đầu người viết code.
5. **"Behavior contracts over snapshots"** cho test — nên nói rõ trong `CLAUDE.md`/test convention: test invariant (quan hệ giữa field), không test giá trị cụ thể (danh sách model, version literal) — để test không vỡ mỗi lần thêm provider/model.
6. **Ghi lại lý do khi *không* làm gì (documented non-migration)** — pattern `hermes_state_schema.py` mục v11 ("SUPERSEDED by v23 ... Kept only for source archaeology") là ví dụ tốt cho việc giữ code chết có chủ đích kèm giải thích, thay vì xoá sạch không dấu vết — có thể ghi thành quy ước ngắn trong `development-rules.md`/`review-audit-self-decision.md` cá nhân (không phải CLAUDE.md project, vì đây là quy ước review chung).

---

## 6. Không port gì — vì sao

- **`_ra()` lazy-module-reference pattern**: giải quyết vấn đề "test patch trên module cũ phải xuyên qua module mới" — chỉ cần khi tách một class/module lớn ra làm nhiều mà giữ back-compat import. Ta không có `run_agent.py` 9000 dòng để tách, và test của ta (`apps/api/tests/`) patch trực tiếp đối tượng được DI qua `service.py`/`build_alpha_desk`, không patch theo tên module toàn cục — không có vấn đề để `_ra()` giải quyết.
- **60-tham-số constructor + init module riêng (`agent_init.py`)**: `AlphaDeskService.__init__` của ta nhận **6** tham số đã-được-xây (dataclass hoá), không nhận scalar rời rồi tự resolve provider/credential như Hermes — không cần tách init ra module riêng vì init đã ngắn (`service.py:60-76`).
- **Toàn bộ persistence layer kiểu SQLite pool (WAL/DELETE fallback, read-connection pool, fd-leak fix)**: ta dùng Postgres qua SQLAlchemy async pool (`docs/specs/0003 §10.5`, pool 15 connection) — không có single-file lock, không có network-filesystem WAL vấn đề, không cần tự viết connection pool tay. Đây là lớp phức tạp nhất trong `hermes_state.py` (hàng nghìn dòng) và **hoàn toàn không áp dụng**.
- **FTS5 full-text search trên transcript**: đã note trong đề bài ta không có; port riêng schema (external-content + trigram) không hợp lý cho Postgres — nếu cần full-text search trên `agent_message`, Postgres có `tsvector`/`pg_trgm` native, không cần mô phỏng kiến trúc SQLite FTS5 external-content.
- **Session lineage 4 loại (branch/reset/compression/ephemeral) qua SQL heuristic**: đây là hệ quả của việc Hermes cho phép resume/rotate/branch một session CLI cục bộ (đa nền tảng, đa profile). `agent_thread`/`agent_turn` của ta là **Turn không resume sau restart** (`turns.py:33-36`, "A restart never resumes... an honest incomplete is worth more than a plausible continuation") — mô hình đơn giản hơn có chủ đích, không có nhu cầu lineage phức tạp này. Port vào sẽ là over-engineering ngược YAGNI.
- **Export/import state + trace upload lên HuggingFace**: tính năng hướng người dùng cá nhân/desktop app di chuyển dữ liệu giữa máy, hoặc chia sẻ transcript để research — không khớp mô hình multi-tenant Postgres của Alpha Desk (không có "máy của user" để export/import giữa, dữ liệu đã ở server).
- **Toàn bộ 20+ callback trên `AIAgent`**: cơ chế event của Hermes (không SSE nội bộ, callback trực tiếp) tồn tại vì Hermes phải chạy sync trong nhiều host process khác nhau (CLI, gateway, TUI) không có event loop chung. Ta đã có SSE (`sse.py`) + checkpoint model (`turns.py`: "bounded, not per token") — kiến trúc publish/subscribe rõ ràng hơn, không cần port callback rời rạc.

---

## 7. Câu hỏi chưa giải quyết

1. Nội dung đầy đủ `~/.hermes/plans/god-file-decomposition.md` không đọc được (ngoài repo) — chỉ biết "Phase 1 step 4" qua trích dẫn gián tiếp trong `turn_finalizer.py`. Nếu cần đối chiếu toàn bộ roadmap tách file, phải hỏi trực tiếp maintainer Hermes hoặc tìm bản plan tương đương trong PR description trên GitHub (không truy cập được từ sparse clone).
2. Không xác nhận được bằng test thực tế liệu `finalize_turn`'s cleanup-cô-lập-lỗi pattern (mục 5.1) đã có tương đương trong `apps/api/src/agent/turns.py` sau terminal transaction hay chưa — cần đọc kỹ phần code sau `_finish_terminal_transaction`-tương-tự trong `turns.py` (ngoài phạm vi file được giao lần này) trước khi áp dụng.
3. 300 issue number chỉ được thống kê + gán bài học cho ~13 cái có ngữ cảnh đọc kỹ; phần còn lại cần một pass riêng (có thể giao một agent khác đọc `CONTRIBUTING.md`/git log Hermes thật nếu cần độ đầy đủ cao hơn).
4. Không xác minh được `sqlite_leak_fix.png` chứa gì cụ thể (không mở ảnh) — chỉ dùng làm bằng chứng gián tiếp về mức độ nghiêm trọng của bug fd-leak.
