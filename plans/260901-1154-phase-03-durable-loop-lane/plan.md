---
plan: 260901-1154-phase-03-durable-loop-lane
title: "Phase 3 — Durable loop, lane và progress thật"
status: in-progress
roadmap: "docs/roadmap.md §10 Phase 3"
branch: feat/phase-03-durable-loop-lane
---

# Phase 3 — Durable loop, lane và progress thật

Roadmap authority: [`docs/roadmap.md`](../../docs/roadmap.md) §10 Phase 3,
§1 (elicitation), §6 (kiến trúc + quy tắc dependency 9), §7 (nguồn pattern
Temporal/Restate — chỉ từ vựng persist-intent-before-effect, không runtime mới),
§9 (nguyên tắc thi công).

## Outcome

Loop semantics Hermes trên state OpenCode: Turn phục hồi có giới hạn hoặc kết
thúc có lý do; tiến trình hiển thị là sự thật; contract question card sẵn sàng;
khung lane light/deep tồn tại và trần là config theo lane, không hard-code.

## Non-goals

- Không dựng pipeline 3-pass (research → counterevidence → verification) —
  Phase 6. Deep lane ở phase này chỉ là **trần khác** trên cùng loop.
- Không có elicitation policy trong planner, không đường production nào tự
  phát question part — Phase 6 sở hữu việc *quyết định hỏi*. Phase này chỉ
  ship **contract**: schema, lifecycle, persistence, endpoint, replay.
- Không làm question card UX đầy đủ (evidence chip, thiết kế riêng) — Phase 7.
  Web chỉ nhận event mới không vỡ và render tối thiểu để UI hiện có xanh.
- Không đo/chấm chất lượng routing intent — chưa có số đo nào sở hữu nó trước
  P6; router v1 là heuristic tất định, mặc định light.
- Không đổi permission plane (P5), không đổi tool catalog, không đổi truth
  contract §2, không thêm cột vào bảng hiện có, không drop dữ liệu nào.
- Không đổi 4 giá trị vocabulary DB `agent_tool_call.status` — `pending|denied`
  là trạng thái **wire/draft** (projection), không phải cột trace.

## Gap analysis — verify trong code thật (2026-09-01)

Không tin nhãn Done: đọc trực tiếp `loop.py`, `turns.py`, `events.py`,
`executor.py`, `definitions.py`, `persistence.py`, `alpha/models.py`,
`core/llm/admission.py`, `apps/web/src/hooks/use-live-turn.ts`,
`apps/web/src/lib/alpha-desk/{live-turn,types}.ts`.

| Trục roadmap P3 | Thực tế trong code |
|---|---|
| Error taxonomy → bounded action | ✅ `recovery_for` + `_TERMINAL_REASONS` MRO (`loop.py:221-243`); compress ≤2, lower-cap ≤2, nudge ≤1, round budget 2× call timeout |
| Không tin `finish_reason` một mình | ✅ `TRUNCATED` + `EMPTY_ANSWER` tách riêng (`loop.py:1081-1122`) |
| Hết budget → partial + blocker | ✅ `BudgetRefusal` không mua apology call (`loop.py:1041-1051`) |
| Terminal write idempotent | ✅ first-terminal-wins (`persistence.py:1083-1086`); sweep freeze `incomplete` không resume |
| Hai cửa terminal tập trung | ✅ `_finish`/`_finish_bare` (`turns.py:456-539`) |
| SSE snapshot/replay atomic | ✅ subscribe/publish sync một block (`events.py`) |
| P2 hand-off: permission + per-call timeout | ✅ `permission_denied`/`tool_call_timeout` typed result, enforce một điểm (`executor.py:360-373,425-439`); 84 test gate |
| **Lane profile** | ❌ `MAX_TOOL_ROUNDS=4` (`loop.py:165`), `TURN_DEADLINE_SECONDS=600` (`loop.py:283`, `turns.py:97`), `MAX_EXTERNAL_TOOL_CALLS=7` (`loop.py:322`) đều hằng module; admission per-owner `TURN_OUTPUT_TOTAL=20_000` (`admission.py:50,327`) khớp đúng arithmetic (4+1)×4_000 của light |
| **Intent router** | ❌ không tồn tại |
| **Progress part typed** | ❌ chỉ có `content.delta(kind=thought)` + `tool.call`; recovery/lane/attempt không phát sự kiện nào; timeline không có audit trail typed |
| **Question part typed** | ❌ không tồn tại (schema, state, endpoint, bảng — đều chưa) |
| **Lifecycle tool call pending/denied trên wire** | ❌ `ToolCallStatus` chỉ `running|ok|error` (`messages.py:54-59`); web union cứng `"running"|"ok"|"error"` (`types.ts:49`) |
| **Persist intent trước execute** | ❌ checkpoint chỉ sau append text và sau round (`loop.py:1079,1132`); call `running` chỉ sống trên SSE, chưa từng vào draft trước dispatch |
| **0 orphan tool state sau terminal** | ❌ `_finish_bare`/sweep giữ nguyên draft cuối — call `running` trong draft bị đông cứng nguyên trạng (`turns.py:509-511`, `frozen_message`) |
| **Cancellation truyền xuống model/tool** | ❌ `cancelled()` chỉ poll ở biên round (`loop.py:1001,1140`); model call in-flight chạy hết `wait_for` 120s rồi mới thấy cancel |
| Retry/specialist cùng envelope Turn | ✅ một phần — retry của client tiêu cùng `_call_timeout`/round budget; Turn path chưa có specialist nào (verifier P6) |
| Client chịu event type mới | ✅ cơ chế — `EventSource` chỉ addEventListener các type liệt kê (`use-live-turn.ts:41-49`), named event lạ không bao giờ bắn tới client cũ |

## Thiết kế

### 1. Lane profile + intent router (`agent/lanes.py` — file mới)

- `LaneProfile` frozen dataclass: `name`, `max_tool_rounds`,
  `deadline_seconds`, `max_external_calls`, `max_output_tokens`,
  `owner_output_total` (arithmetic `(rounds+1) × output` khai ngay trên
  profile, một chỗ, như docstring `loop.py` đòi).
- `LIGHT` = giá trị hiện tại: 4 round / 600s / 7 external / 4_000 output /
  20_000 total. `DEEP` = trần hào phóng (giá trị là **cửa hai chiều**):
  10 round / 1_800s / 20 external / 4_000 output / 44_000 total.
- `route_intent(user_text, attachments) -> LaneProfile`: heuristic tất định
  v1, **mặc định light**; deep chỉ khi text khớp pattern memo-shape rõ (từ
  khóa kiểm chứng/luận điểm/memo + độ dài câu hỏi). Chất lượng routing do P6
  sở hữu; ở đây chỉ cần seam typed + tất định + test được.
- Loop nhận `lane: LaneProfile` (default `LIGHT`): thay mọi chỗ đọc
  `MAX_TOOL_ROUNDS` / `MAX_EXTERNAL_TOOL_CALLS` / deadline bằng lane;
  `ROUNDS_EXHAUSTED_NOTE` thành hàm theo lane. Hằng module giữ nguyên tên,
  trở thành giá trị của `LIGHT` (roadmap nói đúng câu này).
- `turns.py`: `TurnService.create` gọi router một lần, truyền deadline lane
  vào `wait_for` và loop; lane name đi vào progress part đầu tiên.
- Admission: `SpendRequest` thêm field optional `owner_output_total`
  (default `None` → giữ `TURN_OUTPUT_TOTAL` 20_000); ledger clamp bằng trần
  cứng config (`TURN_OUTPUT_TOTAL_MAX = 60_000`) — caller là code tin cậy
  nhưng ledger vẫn giữ bound. `TURN_COST_MICRO_USD` 500_000 giữ nguyên
  (margin đo được của light ~100k worst-case × deep 2.5× vẫn lọt; đo lại ở P6).

### 2. Progress part typed (`agent/parts.py` — file mới)

Nguyên tắc §6.9: map 1-1 sự kiện thật của loop, cấm stage giả bấm giờ.
Không nhân đôi kênh `tool.call` — chi tiết per-call (query nguyên văn, domain,
số nguồn) đã sống ở đó; progress part là audit trail của **loop/pipeline**,
tham chiếu round/call id thay vì copy payload.

- `ProgressPart` frozen dataclass, `kind` đóng:
  - `lane_selected {lane, reason}` — một lần đầu Turn;
  - `model_attempt {round, status: running|completed|error|cancelled,
    terminal_reason?}` — lifecycle model attempt roadmap đòi (pending của
    attempt chính là reservation trong `llm_call_usage`, không phát part);
  - `tool_round {round, calls, external_used}` — khi round dispatch;
  - `recovery {action: compress|lower_output_cap|empty_nudge, attempt, bound}`
    — mỗi lần recovery thật chạy;
  - `tools_halted {reason}`, `rounds_exhausted {}`, `deadline {}`.
- Sống ở: `_TurnState.progress` → mỗi part phát SSE event mới
  **`part.progress`** (additive) *và* vào draft checkpoint (`progress: [...]`)
  → snapshot restate (`events.py` `_remember` + `subscribe`) → message content
  cuối mang `progress` (audit trail trong transcript, roadmap đòi persist).
- `TOOL_CALL_FIELDS`-style allowlist cho payload: progress không bao giờ chứa
  text web/tool (content-light, không có đường injection lên kênh render).

### 3. Question part typed + ba trạng thái persist

- Schema (trong `agent/parts.py`): `QuestionPart {question_id, prompt,
  options: [{id, label, detail?}] (2–4), multi_select: bool (flag từ v1, UI
  sau), skip_label}`. Trạng thái: `pending | answered | skipped | superseded`
  + `selected_option_ids`.
- **Bảng mới `agent_question`** (`alpha/models.py` + alembic additive):
  `id Uuid PK, thread_id FK, turn_id FK, message_id FK nullable, payload
  JSONB, state String(16), selected_option_ids JSONB, created_at,
  resolved_at`. Bảng mới vì `agent_message` là immutable mà state đổi sau
  terminal; mutable state cần row riêng — cùng lý do `agent_turn` tồn tại.
- Lifecycle: Turn kết thúc bằng question = Turn settle **`complete`** như mọi
  Turn (roadmap §1: loop hỏi–đáp là loop hội thoại, không phải state treo);
  message content mang part `question`; row `agent_question` state `pending`.
  SSE phát `part.question` (additive) ngay trước terminal event để client
  đang live thấy card không cần refetch.
- Chuyển trạng thái (một transaction, first-write-wins như terminal):
  - `POST /questions/{id}/answer {selected_option_ids}` → `answered`
    (validate option id thuộc payload; multi chỉ khi `multi_select`);
  - `POST /questions/{id}/skip` → `skipped`;
  - `create_turn` trên thread có question `pending` → `superseded` trong cùng
    transaction tạo Turn (user gõ composer thay vì bấm — đúng §1).
  - Mọi endpoint owner-scoped qua user như mọi row khác; idempotent: gọi lại
    cùng state trả 200 nguyên trạng, đổi state đã resolve trả 409.
- Replay: GET thread merge state từ `agent_question` vào part trong message
  content (renderer đọc part + state — ba trạng thái sống qua F5, gate đòi).
- Phase này **không** có đường production phát question (non-goal); TurnService
  expose seam `settle_with_question(...)` cho P6 + test contract dùng.

### 4. Lifecycle tool call: pending/denied trên wire + persist intent + 0 orphan

- `ToolCallStatus` wire thêm `PENDING`, `DENIED` (messages.py); executor
  `permission_denied` → wire status `denied` (trace DB vocab 4 giá trị giữ
  nguyên — projection ≠ trace).
- **Persist-intent-before-effect** (từ vựng Temporal/Restate, không runtime
  mới): trước khi dispatch một round chứa call có `effect=WRITE`, checkpoint
  boundary với các call ở `pending`; round chỉ-read giữ nguyên đường cũ
  (không có gì cần reconcile). Sau kết quả, checkpoint boundary như hiện tại.
- **Settle mọi call chưa terminal khi Turn terminal**: `_ended` (loop),
  `_finish_bare` và `frozen_message`/sweep (turns.py) quét draft — call còn
  `running|pending` → `error="interrupted"` (cancel → `"cancelled_by_user"`),
  `dispatched` giữ sự thật. Gate "0 orphan tool state" đo trên: draft persist
  cuối, message content, snapshot replay.

### 5. Cancellation truyền xuống model/tool

- `RunningTurn` giữ `cancel_event: asyncio.Event`; `cancel()` và shutdown set
  event (predicate `cancelled()` giữ nguyên cho compat).
- Loop: `_complete` chạy trong task, `asyncio.wait({call_task, event_wait},
  FIRST_COMPLETED)` — cancel đến giữa model call thì **cancel task ngay**,
  settle `cancelled_by_user` với partial đã có; không chờ hết 120s.
  Reservation của call bị hủy reconcile theo đường `usage_unknown` sẵn có của
  ledger — tiền tính là đã tiêu, trung thực.
- Executor: nhận `cancel_event` optional; check tại biên segment; segment
  parallel (toàn read, theo declaration P2) bị cancel in-flight được — mỗi
  call bị hủy settle một typed result `cancelled`; call `effect=WRITE` đang
  chạy **được chạy nốt** (một write tool duy nhất `remember_fact`, idempotent
  theo row) — đây là chỗ "0 duplicate external effect" được giữ.
- One-call-one-result giữ nguyên trên mọi path cancel.

### 6. Web projection tối thiểu (giữ chat UI xanh)

- `types.ts`: `TurnEventType` += `part.progress`, `part.question`; ToolCall
  status union += `pending | denied`; type cho progress/question payload.
- `use-live-turn.ts` EVENT_TYPES += hai type mới; `live-turn.ts` reducer:
  append progress part vào `state.progress[]`, giữ question part trên state;
  render: timeline hiện có coi `pending` như `running`, `denied` như `error`
  (copy tối thiểu); question card render dạng tối giản (prompt + options
  disabled-style + skip) — UX thật là P7.
- Thread view: message content có `question` part thì render trạng thái từ
  payload merge (answered/skipped/superseded hiển thị mờ) — đủ cho gate
  replay, không phải UX P7.

### 7. Fault-injection gate suite (`tests/test_agent_fault_injection.py` — mới)

Ma trận gate roadmap, mỗi ô một test, chạy bằng fake client/tool world sẵn có
(`agent_tool_world.py`, pattern `test_agent_loop.py`):

| Fault | Phải settle |
|---|---|
| LLM call timeout | `incomplete/llm_call_timeout` |
| Route rate limit | `incomplete/route_rate_limited` |
| Malformed args / trùng call id | `MalformedArguments` nổi → `incomplete/turn_failed`; args hỏng → typed result `invalid_arguments`, sibling sống |
| Empty completion | nudge một lần → `incomplete/empty_answer` nếu vẫn rỗng |
| Context overflow | compress ≤2 → `incomplete/context_overflow` |
| Output cap | reduce ≤2 → `incomplete/output_cap_exceeded` |
| Tool declared-timeout | typed result `tool_call_timeout`, Turn sống |
| Cancel giữa model call | task hủy ngay, `cancelled/cancelled_by_user`, partial giữ |
| Cancel giữa tool round | read hủy typed, write chạy nốt đúng **một** lần |
| Disconnect/replay | snapshot mới = text + thoughts + tool_calls + progress đã phát; không call nào `running|pending` sau terminal |
| Shutdown/sweep | frozen draft không còn orphan status |
| Question ba trạng thái | answered/skipped/superseded persist, sống qua snapshot-from-draft và GET thread |

Cộng test đơn vị theo file: `test_agent_lanes.py` (router tất định + arithmetic
profile), `test_agent_parts.py` (schema + allowlist), mở rộng
`test_agent_turn_events.py` (restate progress), `test_agent_transport.py`
(endpoint question), `test_agent_persistence_paths.py` (bảng mới + supersede
transaction).

## Preflight §9

### 1. Gate có lệnh chạy được chưa?

```bash
cd apps/api && pytest tests/test_agent_fault_injection.py \
  tests/test_agent_lanes.py tests/test_agent_parts.py \
  tests/test_agent_loop.py tests/test_agent_turn_lifecycle.py \
  tests/test_agent_turn_events.py tests/test_turn_sse.py -q   # gate phase
cd apps/api && pytest -q                                       # hồi quy suite
python -m compileall -q apps/api/src apps/api/golden apps/api/tests
pnpm --dir apps/web lint && pnpm --dir apps/web type-check \
  && pnpm --dir apps/web test && pnpm --dir apps/web build     # UI xanh
```

Không re-run golden tốn tiền trong phase: router mặc định light giữ nguyên
hành vi 5 tool và trần hiện tại trên đường production; deep lane chỉ mở qua
pattern hẹp + được đo lại ở P6.

### 2. Thứ phase trước để lại — verify trong code thật

Bảng gap-analysis trên, đọc 2026-09-01 trên nhánh `feat/phase-02-capability-plane`
(HEAD `ca01dda`): typed result P2 (`permission_denied`, `tool_call_timeout`)
có mặt và test; terminal idempotent có mặt; SSE atomic có mặt. Suite baseline
1144 passed (ghi ở plan P2).

### 3. Named assumptions (unknown không discoverable)

| Assumption | Nếu sai thì làm gì |
|---|---|
| **A1.** Deep-lane arithmetic (10 round / 44k total / cost ceiling giữ 500k) đủ và không thủng envelope | Giá trị là config trên `LaneProfile` — đổi số không đổi cơ chế; ledger vẫn clamp bằng `TURN_COST_MICRO_USD` nên sai số chỉ làm Turn kết thúc sớm có lý do (`lane_budget`/`user_spend`), không mất answer |
| **A2.** Heuristic router v1 misroute không gây hại | Misroute → chỉ sai trần (deep = nhiều budget hơn, light = ít round hơn); an toàn không đổi vì guard ladder + budget vẫn enforce; P6 sở hữu chất lượng routing và re-baseline golden |
| **A3.** Cancel model call in-flight để reservation `usage_unknown` là chấp nhận được | Đúng thiết kế ledger sẵn có ("tiền đã tiêu dù answer không về"); nếu tỷ lệ usage_unknown tăng bất thường, chỉ số này đã có trong ledger để P9 giám sát |
| **A4.** Alembic additive (`agent_question`) không phá nhánh khác dùng chung DB dev (bài học worktree cũ) | Bảng mới không cột nào chạm bảng cũ; code nhánh khác không biết bảng này vẫn chạy; backup `pg_dump` trước khi upgrade; đường lùi = `alembic downgrade -1` drop bảng rỗng |
| **A5.** Client cũ bỏ qua event type mới | Verify trong code: `EventSource` chỉ nghe named event trong `EVENT_TYPES` (`use-live-turn.ts:141`) — event lạ không bắn handler nào; snapshot thêm key `progress` là additive JSON |

Unknown discoverable đã scout xong trong plan: vị trí mọi hằng lane
(`loop.py:165,283,322`, `turns.py:97`), arithmetic admission
(`admission.py:50,327`, `preflight_turn:391`), idempotency terminal
(`persistence.py:1083`), reducer web (`live-turn.ts`), 4-value trace vocab
(`alpha/models.py:286-298`).

### 4. Đường lùi

Code trong `apps/api/src/agent/` + `apps/web/src` + một migration additive.
Dừng giữa phase: revert nhánh `feat/phase-03-durable-loop-lane`;
`alembic downgrade -1` drop bảng `agent_question` (rỗng nếu chưa ai phát
question — không đường production nào phát ở phase này). Không state bền nào
khác đổi shape: draft/message content chỉ **thêm** key (`progress`,
`question`), reader cũ đọc dict bỏ qua key lạ.

## Cửa một chiều — kiểm tra

- **HTTP/SSE contract:** chỉ **additive** — hai SSE event type mới, hai
  endpoint mới, key JSON mới; 7 event hiện có và mọi endpoint hiện có giữ
  nguyên shape. Phần thêm là chính checklist Phase 3 roadmap đã quyết
  (progress part, question part, ba trạng thái) — không phải deviation.
- **Data:** không drop, không migrate dữ liệu cũ; một bảng mới.
- **Legal boundary, default permission, capability ngoài catalog, §2:**
  không chạm.

## Việc

| # | Việc | File chính | Giao |
|---|---|---|---|
| 1 | LaneProfile + router + loop/turns/admission đọc lane | `agent/lanes.py` (mới), `loop.py`, `turns.py`, `core/llm/{protocol,admission}.py`, `service.py`, `router.py` | opus |
| 2 | Progress part + SSE `part.progress` + draft/snapshot/message restate | `agent/parts.py` (mới), `loop.py`, `events.py`, `turns.py`, `messages.py` | opus |
| 3 | Tool lifecycle `pending|denied` wire, persist-intent, settle orphan tại terminal | `messages.py`, `loop.py`, `turns.py`, `executor.py` | opus |
| 4 | Cancellation propagate model/tool qua `cancel_event` | `loop.py`, `turns.py`, `executor.py` | opus |
| 5 | Question part: bảng + migration + persistence + endpoints + supersede + replay merge | `alpha/models.py`, alembic (mới), `persistence.py`, `schemas.py`, `router.py`, `turns.py`, `parts.py` | opus |
| 6 | Web projection tối thiểu + types | `apps/web/src/lib/alpha-desk/{types,live-turn}.ts`, `hooks/use-live-turn.ts`, view components tối thiểu | opus |
| 7 | Fault-injection gate suite + test đơn vị mới/mở rộng | `tests/test_agent_fault_injection.py` (mới), `test_agent_lanes.py` (mới), `test_agent_parts.py` (mới), mở rộng 5 file test hiện có | opus |

Thứ tự: 1→(2,3,4 tuần tự vì chung `loop.py`/`turns.py`)→5→6→7 (7 viết xen kẽ
theo từng việc khi hợp lý, gom gate cuối).

## Nghiệm thu

1. Gate suite + toàn `pytest -q` xanh; `compileall` sạch; bốn lệnh web xanh.
2. Ma trận fault-injection: mọi ô settle đúng status/terminal_reason; 0 call
   `running|pending` trong bất kỳ persisted view nào sau terminal; write tool
   chạy đúng một lần trên mọi path cancel/retry.
3. Replay: snapshot sau disconnect = đúng text + thoughts + tool_calls +
   progress đã phát; question ba trạng thái sống qua replay và GET thread.
4. Trần round/deadline/external/output đọc từ `LaneProfile`; không còn call
   site production nào đọc thẳng hằng cũ ngoài định nghĩa `LIGHT`.
5. `git diff --check` sạch; không tham chiếu Signal Desk/Study mới; progress
   payload không chứa text web/tool (allowlist test).
