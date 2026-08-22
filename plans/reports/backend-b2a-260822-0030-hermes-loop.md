# B2a — Hermes loop + prompt (backend)

Worktree `feat/hermes-harness`, `apps/api`. Plan `plans/260822-0000-hermes-harness/plan.md` §3, §4, §4b, §6; ADR-0026; B1 report.

## File tạo/sửa

| File | Dòng | Nội dung |
|---|---|---|
| `src/agent/prompt/sections.py` | 272 | **Viết lại từ đầu.** 8 section tiếng Việt của một trợ lý tổng quát: vai trò, nguyên tắc không ghi đè, **“không có dữ liệu nội bộ, không bịa số”**, công cụ + nguyên tắc dùng, nội dung ngoài là dữ liệu, bộ nhớ, văn phong, bối cảnh lượt. `PROMPT_VERSION = "2.0.0"`. Không brace nào trong body |
| `src/agent/prompt/contract.py` | 185 | `RuntimeContext(today, user_name=None)`, `render/prefix/contract_hash/cache_key`, `sanitise_name` + `MAX_NAME_CHARS=64`. Giữ hai tính chất cũ: prefix tĩnh hằng định, hash tính trên prose |
| `src/agent/prompt/__init__.py` | 34 | Re-export |
| `src/agent/loop.py` | 1900 | **Viết lại từ đầu** (cũ 2174) |
| `src/agent/service.py` | 189 | Wiring lại: `register_all()` một lần, `trace=persistence.record_tool_call`, bỏ catalog/suggest/spill/version |
| `src/agent/limits.py` | 130 | **Phục hồi nguyên văn từ `develop`** — xem “Lệch brief” #1 |
| `tests/test_agent_loop.py` | 1196 | Viết lại (62 test) |
| `tests/test_agent_prompt.py` | 190 | Mới (43 test) |

Không chạm file nào khác. `events/sse/schemas/router/turns/persistence/ops/main.py/jobs.py/models.py/eval/e2e` nguyên trạng.

## Dataclass cuối cùng — B2b khớp chính xác vào đây

Tất cả ở `src.agent.loop`. **`context.py` không được dựng lại**; transcript type nằm trong `loop.py` (lý do ở “Lệch brief” #2).

```python
class TurnStatus(str, Enum):      COMPLETE | INCOMPLETE | CANCELLED
class ToolCallStatus(str, Enum):  RUNNING | OK | ERROR      # value = "running"|"ok"|"error"

@dataclass(frozen=True)
class TurnToolCall:               # MỘT type cho cả SSE, transcript và trace
    id: str
    name: str
    arguments: Mapping[str, Any] = {}
    status: ToolCallStatus = RUNNING
    result_text: str | None = None      # NGUYÊN VĂN; budget cắt lúc dựng message
    summary: str = ""                   # câu tiếng Việt, frontend render thẳng
    error: str | None = None
    guidance: str | None = None         # warn của guardrail, nằm NGOÀI thẻ untrusted
    duration_ms: int = 0
    dispatched: bool = True
    signature: str | None = None
    @property finished -> bool           # status is not RUNNING
    def as_wire() -> {id, name, status, summary}   # đúng payload SSE tool.call

@dataclass(frozen=True)
class TranscriptTurn:
    user_text: str
    tool_calls: tuple[TurnToolCall, ...] = ()
    assistant_text: str | None = None
    @property completed_calls -> tuple[TurnToolCall, ...]

@dataclass(frozen=True)
class TurnRequest:
    thread_id: uuid.UUID | str
    request_message_id: int
    user_id: int
    user_text: str
    runtime: RuntimeContext
    history: tuple[TranscriptTurn, ...] = ()
    summary: str | None = None
    summarised_turns: int = 0

@dataclass(frozen=True)
class TurnDraft:
    text: str | None
    rounds_used: int
    tool_calls: tuple[TurnToolCall, ...]
    boundary: bool = False

@dataclass(frozen=True)
class TurnOutcome:
    status: TurnStatus
    terminal_reason: str | None
    text: str | None
    rounds_used: int
    rounds_exhausted: bool
    tool_calls: tuple[TurnToolCall, ...]
    usage: Usage
    summary_needed: bool = False
    provider_request_id: str | None = None

@dataclass(frozen=True)
class RuntimeContext:            # src.agent.prompt
    today: date
    user_name: str | None = None      # sanitise: 1 dòng, không ':', không '<>' , cap 64
```

Còn export từ `loop.py`: `Transcript`, `ContextBudget`, `ConstructedContext`, `ConstructedContextTooLarge`, `build_messages`, `estimate_tokens`, `shown_result`, `summarise_call`, `terminal_reason_for`, `assert_distinct_ids`, `SessionSlots`, `SessionCapacityExceeded`, `TurnAdmission`, `TurnRefused`, `TurnPreflight`, `ADMISSION_STATUS`, `SpendIdentity`, `TURN_SPEND`, `ToolCallIdMismatch`, `TurnPublisher`, `CHARS_PER_TOKEN`, `MESSAGE_OVERHEAD_TOKENS`, `SUMMARY_LABEL`.

### terminal_reason — bảng đầy đủ

`turn_deadline`, `llm_call_timeout`, `tool_timeout`, `answer_truncated`, `cancelled_by_user`, `model_refusal`, `context_overflow`, `output_cap_exceeded`, `content_policy_blocked`, `model_unavailable`, `schema_rejected`, `route_rate_limited`, `auth_unavailable`, `gateway_timeout`, `deadline_expired`, `route_error`, cộng mọi `BudgetRefusal.reason`.

Đã đối chiếu với `apps/web/src/lib/alpha-desk/copy.ts` của C: **khớp hết trừ `deadline_expired`** (C chưa có, rơi về `UNNAMED_REASON`). `MalformedArguments` không phải terminal_reason — nó **raise** ra khỏi loop để `turns.py` ghi `turn_failed` (giữ nguồn phát cho `turn.failed`).

## API/signature B2b phải cung cấp

1. **`events.TurnPublisher` phải có đúng hai method loop gọi** (loop khai `Protocol` cấu trúc, không import `events`):
   ```python
   def content_delta(self, text: str) -> Any: ...   # text là ĐÚNG đoạn vừa append
   def tool_call(self, payload: Mapping[str, Any]) -> Any: ...   # = TurnToolCall.as_wire()
   ```
   Bất biến phải giữ khi bọc thành SSE: `"".join(mọi content.delta) == snapshot.text == message.content["text"]`. Loop đã bảo đảm dấu ngăn `"\n\n"` nằm **bên trong** delta.

2. **`TurnService.__init__` bỏ `tool_catalog_version` và `mcp_servers_version`.** `service.py` gọi:
   ```python
   TurnService(store=persistence, loop_factory=loop_factory, config=resolved)
   ```
   `loop_factory(*, checkpoint, publisher)` và `agent.run(request, cancelled)` giữ nguyên hợp đồng cũ.

3. **`router.py`**: `from src.agent.context import TranscriptTurn` → `from src.agent.loop import TranscriptTurn`; `history_of()` dựng `TurnToolCall(id=..., name=..., arguments=..., status=ToolCallStatus.OK, result_text=...)` (đổi `call_id=` → `id=`). Bỏ `from src.agent.runtime import ...`; `_runtime()` chỉ còn `RuntimeContext(today=now.date(), user_name=<User.full_name hoặc None>)`.

4. **`src/agent/runtime.py` là file chết — xoá.** Nó `from .prompt import MarketState` (không còn) và chỉ `router.py` dùng nó. `src.stocks.trading_day`/`core.trading_calendar` vẫn sống cho bảng giá.

5. **`admission.py` đã gộp vào `loop.py`** theo plan §2: `TurnAdmission`, `TurnRefused`, `TurnPreflight`, `ADMISSION_STATUS`, `UNMAPPED_ADMISSION_STATUS`. `router.py` đổi import sang `src.agent.loop`. Hành vi 429/503 không đổi.

6. **`ops.py`/`turns.py`/`eval/*`**: `AnswerKind` và `MarketState` không còn tồn tại. `answer_kinds` trong ops snapshot mất chủ đề — B2b quyết bỏ cột hay thay bằng chiều khác.

7. **`persistence.record_tool_call`** nhận đúng shape cũ; loop tự adapt từ trace entry của executor. `trace["result"]` giờ là `{"chars": int, "dispatched": bool}` chứ không phải body kết quả (lý do ở “Lệch brief” #4).

8. **Message content canonical** nên là `{text, tool_calls: [as_wire()], status}` — plan §4b: frontend đọc `status` optional và **mặc định là hoàn chỉnh**, nên `TurnOutcome.status` phải được ghi vào content.

## Giữ / bỏ so với loop cũ

**Giữ nguyên (không viết lại `src/core/llm`):** `build_client`/`ReservedLLMClient`, `Message/ToolCall/ToolSchema/Completion`, `SpendRequest`+`CallOwner` (ADR-0014: mọi call có owner id), `RouteBreaker`, taxonomy lỗi đầy đủ, và **`recovery_for`** — dùng bảng `RECOVERIES` thay cho 12 nhánh `except`: chỉ `COMPRESS` và `LOWER_OUTPUT_CAP` là việc của loop, phần còn lại terminal với reason tra theo MRO. Đây là chỗ rút gọn lớn nhất mà không mất hành vi nào.

**Giữ hành vi:** `MAX_TOOL_ROUNDS=4`; deadline cả Turn; cap output token + hai phục hồi ngược chiều (`MAX_CONTEXT_COMPRESSIONS=2` × 0.6 cho `ContextOverflow`; `MAX_OUTPUT_TOKENS_REDUCTIONS=2` × 0.5, sàn 1.000 cho `OutputCapExceeded`); trần thời gian một round (`ROUND_TIMEOUT_MULTIPLE=2.0`); checkpoint + publisher callback; cancellation; `assert_distinct_ids`; bất biến JSON trên tool arguments; `MAX_EXTERNAL_TOOL_CALLS=6`; `SessionSlots`/`SessionCapacityExceeded`; `SpendIdentity` (eval dùng cùng một loop).

Giữ 4 round chứ không nâng: `(MAX_TOOL_ROUNDS + 1) × DEFAULT_MAX_OUTPUT_TOKENS = 5 × 4.000 = 20.000 = TURN_OUTPUT_TOKENS`. Nâng round mà không hạ cap là tiêu một ngân sách chưa ai kiểm. Có test giữ đẳng thức này.

**Bỏ hẳn:** grounding/Recommendation Validator, Evidence Manifest, widget, progress 5 phase, suggestions (+ call model rẻ), answer kind, block splitting, symbol/Universe/Trading Day/MarketState, Signal Registry, `spillover.py` cũ (dùng `budget.py`), `GuardrailLadder`/`judge_round` cũ (dùng `TurnGuardrails.before_call/after_call` qua executor), `pair_results`/`admit_round`/`ToolAttempts` (executor đã bảo đảm mỗi call đúng một result, đúng thứ tự), `_repair`/`MAX_GATE_ATTEMPTS`/`REPAIR_NOTE`, `NEWS_TOOL`.

**Dùng API B1 đúng wiring notes:** `register_all()` ở `service.py`; `definitions.get_tool_definitions(toolsets)` gọi một lần đầu Turn (không gọi `registry.definitions()`); `TurnBudget(thresholds_for_context(ctx), registry_limits=registry.declared_result_sizes())`; `untrusted.wrap_result()` ở tầng dựng message; `ToolExecutor(context=ToolContext(user_id, thread_id, now), guardrails=TurnGuardrails(), trace=...)`; `ExecutionOutcome.halted` → `state.tools_halted`.

Hai điểm đáng đọc code:
- `warn` của guardrail đi **ngoài** thẻ `<untrusted_tool_result>` (`shown_result`): để trong thẻ thì một trang web đọc như tiếng nói của harness.
- rung 3 của budget được **áp lại mỗi lần dựng message** (`_shown_calls` → `rebalance()`), vì “vượt trần cả Turn” là dữ kiện của Turn: một kết quả từ 3 round trước vẫn có thể bị bắt nhường chỗ bây giờ.

## Lệch brief — và tại sao

| # | Chỗ | Brief/plan nói | Đã làm | Lý do |
|---|---|---|---|---|
| 1 | `src/agent/limits.py` | plan §2 xoá: “trần theo tool store” | **Phục hồi nguyên văn từ `develop`** (`git checkout develop -- src/agent/limits.py`) | Lý do trong plan **sai**: file này là rate-limit cho SSE subscribe/reconnect **theo user**, không liên quan tool store. Bỏ nó là quay về limiter theo IP — mà sau proxy Next mọi user chung một IP, nên một người mạng kém sẽ rate-limit cả hệ thống (ADR-0013 nói rõ). `router.py:416,425` phụ thuộc. Không sửa một dòng nào của file; nếu chủ sản phẩm vẫn muốn xoá thì đó là một quyết định riêng |
| 2 | `context.py` | B1 xoá; brief cho tôi 3 vùng file | Transcript type + `build_messages` + `estimate_tokens` **nằm trong `loop.py`** | Loop mới bắt buộc phải có thang nén context (không có nó thì phục hồi `ContextOverflow` vô nghĩa). Dựng lại `context.py` là chạm file thứ 4 mà không ai sở hữu và B2b có thể tạo trùng. Đổi lại `loop.py` dài 1.900 dòng; phần thuần khiết (`build_messages`) vẫn test độc lập được. Đã bỏ phần thuộc grounding: không còn nhét `tool_call_id:` vào body message |
| 3 | `admission.py` | plan §2 “gộp vào loop mới” | Gộp thật, ~110 dòng trong `loop.py` | Nó là câu hỏi ở `POST` trước khi mở stream, ở cạnh `SessionSlots` là đúng chỗ |
| 4 | `agent_tool_call.result` | — | Ghi `{"chars", "dispatched"}` thay vì body kết quả | Trace entry của executor (B1) chỉ mang `result_chars`, không mang text; loop dùng hook đó vì nó ghi ngay khi từng call xong (sống sót một round bị cắt). Điền một stand-in “giống thật” vào cột audit còn tệ hơn để trống. Không có consumer nào đọc cột này (đã grep: chỉ `ops.py` đếm `tool_name`/`status`, `jobs.py` xoá theo tuổi). Muốn body thật thì thêm field vào trace entry của executor — ngoài scope tôi |
| 5 | `RuntimeContext` | “thu về tối thiểu” | `today` + `user_name` optional | `user_name` là chuỗi do user khai → mặt tấn công duy nhất trong prompt. Đã sanitise: cắt 64 ký tự, bỏ newline/`:`/`<>`, nên nó không giả mạo được một dòng `- key: value` hay đóng thẻ untrusted. Có test |
| 6 | `context_length` cho budget | brief: “context_length của model đang chạy” | Dùng `ContextBudget.max_tokens` (mặc định `TURN_CONTEXT_PER_CALL = 32.000`) | `LLMConfig` **không có** field nào mô tả context window của model (đã grep toàn `src/`). Trần thật mà loop gửi là 32K do admission áp; chia phần trăm của một cửa sổ mà loop không bao giờ lấp là chia một con số tưởng tượng. Nếu sau này thêm `LLM_CONTEXT_LENGTH` vào settings thì truyền vào `AgentLoop(budget=ContextBudget(max_tokens=...))` là đủ |
| 7 | `tool_timeout` | không có trong brief | Thêm: một round tool có trần 30s → `tool_timeout` | `TOOL_TIMEOUT_SECONDS` là hằng số cũ mà bản mới sẽ để mồi vì `executor.py` không có trần thời gian nào. Một `fetch_url` treo sẽ ngốn hết deadline Turn. Đã settle mọi call chưa xong thành `error` trước khi kết Turn, để reader reconnect không thấy spinner vĩnh viễn. `copy.ts` của C đã có câu cho `tool_timeout` |
| 8 | `summary` của tool call | plan §4 chỉ nói có field `summary` | Câu tiếng Việt theo template mỗi tool (`Tìm trên web: …`, `Đọc trang …`) | `tool-call-list.tsx` + `types.ts` của C nói rõ backend viết câu và frontend render **verbatim**. Một chuỗi `web_search: q` sẽ hiện nguyên như vậy trên màn hình. Argument lấy theo allowlist per-tool: tool thêm sau chỉ hiện tên, không hiện field chưa ai review |
| 9 | Text streaming | “phát theo delta” | Một delta cho mỗi khối prose model trả về (route hiện tại trả completion nguyên khối) | `LLMClient` chỉ có `complete()`, không expose hook token-level; brief cấm viết lại lớp `core/llm`. Plan §4b cũng nói e2e đã đổi `say()` thành **một** delta. Bất biến “tổng delta = text” được test |
| 10 | `rounds_exhausted` | — | Chỉ True khi đúng chạm trần round, KHÔNG True khi guardrail halt | Halt xảy ra ở round 1 vẫn báo “đã dùng hết 4 round” là nói sai với cả model và với ops snapshot. Note `ROUNDS_EXHAUSTED_NOTE` cũng chỉ gửi khi thật sự hết round |

## Test — kết quả chạy thật

```
python3 -m pytest tests/test_agent_loop.py tests/test_agent_prompt.py \
  tests/test_agent_tool_registry.py tests/test_agent_toolsets.py \
  tests/test_agent_tool_definitions.py tests/test_agent_guardrails.py \
  tests/test_agent_tool_budget.py tests/test_agent_untrusted_results.py \
  tests/test_agent_tool_executor.py tests/test_agent_web_tools.py --noconftest -q
→ 205 passed in 1.67s        (B2a mới: 105 — loop 62, prompt 43; B1 giữ nguyên: 100)
```

`--noconftest` vẫn bắt buộc: `tests/conftest.py:16` import `src.main`, và `src.main` → `router` → `turns`/`ops` đang vỡ tới khi B2b xong.

`python -m py_compile src/agent/loop.py src/agent/service.py src/agent/prompt/*.py` sạch (`make lint` của repo chỉ là py_compile). Không có ruff/flake8 trong môi trường. Quét AST: không import thừa nào ngoài `from __future__ import annotations`.

`tests/test_agent_memory_tools.py` (của B1) **không chạy được trên host này**: `psycopg` chỉ có trong `.venv`, mà hook chặn đọc đường dẫn `.venv`. Không thuộc scope B2a; B1 đã báo xanh.

`make test` toàn bộ **chưa chạy được** — collection đỏ vì conftest, đúng như dự kiến của plan.

### Loop — 62 test, phủ những gì brief yêu cầu

| Brief yêu cầu | Test |
|---|---|
| round cap | trần đúng `MAX_TOOL_ROUNDS`, call cuối `tool_choice="none"` + note, các call trước `"auto"`, Turn không cần tool tốn 1 call/0 round, đẳng thức `5 × 4.000 ≤ TURN_OUTPUT_TOKENS` |
| deadline | hết đồng hồ trước call đầu → không gọi route; hết giữa Turn → giữ text + 1 round, không mua call trả lời |
| ContextOverflow vs OutputCapExceeded | nén thì message **ít đi** và output cap **không đổi**; hạ cap thì cap **halve** và message **không đổi**; hết hạn mức nén → terminal `context_overflow`; không có gì để nhường → **không trả tiền lần hai**; sàn `MIN_OUTPUT_TOKENS` |
| cancellation | huỷ trước call đầu → không call nào; huỷ sau round 1 → giữ nguyên round đó |
| tool arguments không parse | args là chuỗi JSON hỏng → result `invalid_arguments`, Turn vẫn COMPLETE, **model được cho biết** (có message TOOL, không phải call rỗng); route trả `MalformedArguments` → raise |
| distinct ids | id trùng/thiếu → `ToolCallIdMismatch`; là subclass `MalformedArguments`; id khác nhau đi qua im lặng |
| external tool cap | 8 call `web_search` qua 4 round → handler chạy đúng 6, 2 call còn lại `external_budget_exhausted` + `dispatched=False` + có result_text; tool local **không** bị trừ vào budget này |
| halted từ guardrail | 8 call fail cùng tool trong 1 round → halt; round tiếp là call trả lời (`tool_choice="none"` + `HALT_GUIDANCE`), `rounds_used==1`, `rounds_exhausted is False`, **không** gửi note “hết round”; call `ok` bên cạnh vẫn giữ, mọi call của round đều có result |
| delta đúng thứ tự | `"".join(deltas) == outcome.text`; prose 2 round → 2 delta có `"\n\n"` bên trong delta thứ hai; thứ tự phát `delta → tool → tool → delta`; Turn không nói gì thì không phát delta |

Ngoài yêu cầu: 8 lỗi route × reason (parametrize), subclass thừa hưởng reason theo MRO, `llm_call_timeout`, `BudgetRefusal` không mua call xin lỗi, `ModelRefusal` là câu trả lời và tới được người đọc, `answer_truncated`, `tool_timeout` + settle call treo, tool.call `running → ok|error`, `summary` không đổi giữa hai event, trace 1 row/call đúng `request_message_id`, trace vỡ không mất câu trả lời, checkpoint ở mọi đường terminal, `SessionSlots` refuse/unlimited, cache breakpoint trên system message, call đang chạy bị loại khỏi context, thang nén (collapse trước khi drop Turn), `ConstructedContextTooLarge`, summary thay các Turn nó phủ, wrap untrusted + guidance nằm ngoài, tool local không bị wrap, `as_wire()` đúng 4 field, budget cắt kết quả to (model đọc bản cắt, trace giữ size thật), note hệ thống nằm trong hạn mức token đã đặt.

### Prompt — 43 test

Prefix hằng định giữa 2 Turn khác nhau (và không rò `today`/`user_name` lên trên biên); render byte-stable; phần biến thiên đúng là các dòng cuối; hash đổi khi prose đổi **và** khi chỉ version đổi; `cache_key` mang hash nhưng không mang giá trị runtime; **27 phrase của harness cũ không lọt vào prompt** (`[ev:`, `[rec:`, `[zone:`, Evidence Manifest, Recommendation Gate/Validator, `[technical]`/`[fundamental]`/`[money_flow]`/`[news]`, answer kind, Signal Registry, Trading Day, Universe, Watchlist, widget, risk notice, price zone, `indicator_pack`, HOSE…); prompt gọi tên đúng 5 tool; prompt nói về `untrusted_tool_result`; không body nào có brace; tên user không mang được newline/`:`/`<>` vào prompt, bị cap 64, tên toàn dấu câu → không có tên; `today` không phải date → TypeError.

## Câu hỏi còn treo

1. `deadline_expired` chưa có câu trong `copy.ts` của C — thêm câu hay gộp vào `gateway_timeout`?
2. `ops.py` đếm `answer_kinds`; vocabulary đó đã chết. Bỏ chiều đó hay thay bằng `terminal_reason`?
3. `limits.py` được phục hồi ngược plan §2 — cần chủ sản phẩm xác nhận (xem Lệch #1).
4. `agent_tool_call.result` giờ chỉ ghi kích thước. Có muốn body thật (phải mở rộng trace entry của `executor.py`) không?

Status: DONE_WITH_CONCERNS
Summary: Viết lại `prompt/` (3 file, prompt trợ lý tổng quát tiếng Việt, trung thực về việc không có dữ liệu nội bộ) và `loop.py` (1.900 dòng, giữ nguyên biên `core/llm` + dùng bảng `recovery_for` thay 12 nhánh except, dùng đủ API B1), wiring lại `service.py`; 105 test mới xanh, 205 test toàn lớp agent xanh.
Concerns: (1) Đã phục hồi `src/agent/limits.py` ngược với plan §2 vì lý do xoá trong plan là sai — cần xác nhận. (2) `context.py` không dựng lại; transcript type nằm trong `loop.py` nên B2b phải sửa import của `router.py`. (3) `src/agent/runtime.py` là file chết cần B2b xoá. (4) `agent_tool_call.result` chỉ còn kích thước, không còn body. (5) `TurnService.__init__` phải bỏ `tool_catalog_version`/`mcp_servers_version` — `service.py` đã gọi theo signature mới nên hiện chưa import được cho tới khi B2b sửa `turns.py`. (6) Không có hook streaming token-level ở `core/llm`, nên một completion = một delta.
