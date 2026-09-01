# Task 1 — Lane profile + intent router + admission plumbing

Branch `feat/phase-03-durable-loop-lane`, commit `848d33c`.
Suite: **1181 passed, 3 deselected** (baseline P2: 1144; +37 new tests).

## Cái đã dựng

### `apps/api/src/agent/lanes.py` (mới)

- `LaneProfile` frozen dataclass, `__post_init__` (lanes.py:68-92) enforce hai
  thứ: mọi ceiling là int dương / deadline dương, và arithmetic
  `owner_output_total == (max_tool_rounds + 1) * max_output_tokens`. Profile sai
  arithmetic **không tồn tại được** (ValueError khi construct), thay vì chỉ là
  comment trong docstring loop.
- `LIGHT` (lanes.py:100) = đúng hằng hiện tại: 4 / 600.0 / 7 / 4_000 / 20_000 /
  100_000. `DEEP` (lanes.py:120) = 10 / 1_800.0 / 20 / 4_000 / 44_000 / 280_000.
  `DEEP.max_output_tokens == LIGHT.max_output_tokens` là cố ý: deep mua thêm
  *vòng bằng chứng*, không mua câu trả lời dài hơn.
- `route_reason(user_text) -> (LaneProfile, str)` (lanes.py:161) — pure, không
  I/O, không LLM. `DEEP_KEYWORDS` là **tuple** (không phải frozenset) để reason
  string tất định theo thứ tự khớp đầu tiên; `DEEP_MIN_CHARS = 240` đo trên text
  đã collapse whitespace, nên một khối line-break dán vào không thành "dài".
  Reason: `keyword:<từ>` | `length:<n>` | `default`. `route_intent` =
  `route_reason(...)[0]`.
- Không fold dấu tiếng Việt (đã ghi trong comment lanes.py:131-137): "kiem
  chung" → light. Sai về phía trần thấp hơn là hướng an toàn; chất lượng routing
  thuộc P6.

### `loop.py`

- `AgentLoop.__init__` nhận `lane: LaneProfile = LIGHT` (loop.py:940). Mọi chỗ
  enforce trần trong loop đọc lane: round loop (1039), `exhausted` (1061), note
  hết vòng (1212), external ceiling (1653), `SpendRequest` owner totals
  (1356-1357).
- `max_output_tokens` / `deadline_seconds` đổi default thành `None` = "lấy của
  lane"; caller truyền số thì số đó thắng (test đang dùng `deadline_seconds=0.0`
  vẫn xanh). Hệ quả: `self._deadline` luôn là float → nhánh `is None` trong
  `_expired` là code chết và đã bỏ (loop.py:1960-1966) — mọi lane đều đặt tên một
  wall clock, nên "Turn không có deadline" không còn là state cấu hình được.
- `ROUNDS_EXHAUSTED_NOTE` → `rounds_exhausted_note(rounds)` (loop.py:373);
  hằng module giữ nguyên tên = `rounds_exhausted_note(MAX_TOOL_ROUNDS)`
  (loop.py:404), string byte-identical với bản cũ (test cũ import nó vẫn xanh).
- Hằng `MAX_TOOL_ROUNDS` / `MAX_EXTERNAL_TOOL_CALLS` / `TURN_DEADLINE_SECONDS` /
  `DEFAULT_MAX_OUTPUT_TOKENS` giữ literal + comment nói rõ chúng là giá trị của
  `LIGHT`; test so hai bên nên không drift. Không còn call site production nào
  *enforce* bằng hằng (verify: `grep` trong `apps/api/src` chỉ còn docstring của
  `guardrails.py`, `attachments.py`, `executor.py`).
- Recovery bounds, nudge, guardrail ladder: **không chạm**.

### `turns.py` + `service.py`

- `RunningTurn` thêm `lane` / `lane_reason` (turns.py:143-151) — routed một lần
  trong `create` (turns.py:409-424), log một dòng, chưa phát progress part (việc
  của task 2).
- `_execute`: loop factory nhận `lane=running.lane`; `asyncio.wait_for` dùng
  `running.lane.deadline_seconds` khi service không được cấu hình deadline
  (turns.py:471-480). `TurnService(deadline_seconds=...)` đổi default sang `None`
  = "mỗi Turn theo lane của nó"; một số truyền vào là **trần cứng đè mọi lane**
  (đường của operator/test). Nếu để `min(service, lane)` thì deep 1_800s sẽ bị
  cắt về 600 — đúng nghĩa vô hiệu hóa lane, nên không làm.
- `LoopFactory` contract giờ là `(*, checkpoint, publisher, lane)`. Cập nhật 3
  factory: `service.py:120`, `tests/test_agent_transport.py:191`,
  `tests/e2e/server.py:207` (hai fake `ScriptedLoop` nhận và bỏ `lane`, có comment
  nói vì sao).

### `core/llm/admission.py`

- `SpendRequest` thêm `owner_output_total` / `owner_input_total` optional
  (admission.py:117-125). `None` → hành vi hôm nay, nguyên văn.
- Trần cứng `TURN_OUTPUT_TOTAL_MAX = 60_000`, `TURN_INPUT_TOTAL_MAX = 300_000`
  (admission.py:52-66). `_owner_token_total` (admission.py:690) **clamp** khi
  vượt (log warning) và **raise ValueError** khi giá trị không phải int dương
  (0, âm, float, bool). Clamp thay vì refuse có lý do ghi trong docstring: refuse
  sẽ biến lỗi cấu hình thành Turn "hết budget ở call đầu", đọc log ra thành vấn
  đề tiền — sai chỗ để đi tìm.
- `preflight_turn`, `TURN_COST_MICRO_USD`, `check_candidate_shape`: không đổi.

## Test

- `tests/test_agent_lanes.py` (mới, 25 test): arithmetic hai profile + không
  construct được profile sai; `LIGHT` == hằng của `loop.py` **và**
  `turns.TURN_DEADLINE_SECONDS` **và** `TURN_OUTPUT_TOTAL`/`TURN_INPUT_TOTAL`;
  `DEEP` nằm trong trần cứng ledger; router tất định (default, từng keyword,
  case/whitespace, length, whitespace không phải length, cùng input cùng reason).
- `tests/test_agent_loop.py` +3: default lane gửi đúng owner totals hôm nay;
  lane `max_tool_rounds=1` dừng ở trần của nó và note nói "1" (khác note light);
  lane `max_external_calls=3` refuse call thứ 4 bằng `external_budget_exhausted`.
- `tests/test_spend_admission.py` +6 (trong `TestTurnCeilings`): total được nới
  thì admit cái default sẽ refuse (cả input và output), vượt trần cứng bị clamp
  (test này fail nếu bỏ clamp), giá trị không phải số đếm dương → ValueError.
- `tests/test_agent_turn_lifecycle.py` +2: câu "Viết memo…" route DEEP, lane +
  reason nằm trên `RunningTurn`, loop được build từ đúng lane đó; câu thường →
  LIGHT/`default`.

## Verify (chạy trên host)

```
pytest tests/test_agent_lanes.py tests/test_agent_loop.py \
  tests/test_turn_admission.py tests/test_agent_turn_lifecycle.py -q   # 239 passed
pytest -q                                                              # 1181 passed, 3 deselected
python3 -m compileall -q apps/api/src apps/api/golden apps/api/tests    # sạch
git diff --check                                                       # sạch
```

Không chạm `events.py`, parts, `executor.py`, `messages.py`, web, migration.
Không đổi contract HTTP/SSE. Không golden run (light giữ nguyên hành vi).

## Câu chưa giải quyết

1. **Guardrail rung vs deep lane.** `DEFAULT_THRESHOLDS.same_tool_failure_halt_after`
   được pin bằng `MAX_EXTERNAL_TOOL_CALLS` (7) trong
   `tests/test_agent_guardrails.py:127`. Trên deep (20 external) ladder vẫn dừng
   ở 7 — chặt hơn, an toàn, nhưng nghĩa là "rung theo trần Turn" giờ chỉ đúng cho
   light. Có nên cho `TurnGuardrails` đọc lane không? Nằm ngoài scope task này.
2. `guardrails.py:83-85` viết "four tool rounds … and six external calls" —
   "six" đã stale từ 2026-08-29 (giờ là 7). Không sửa vì file ngoài ownership.
3. `plans/260901-1154-phase-03-durable-loop-lane/plan.md` đang dirty từ trước khi
   task bắt đầu (orchestrator tự sửa mục admission). Không stage, không commit.
4. `lane_reason` hiện chỉ vào log + `RunningTurn`; part `lane_selected` là của
   task 2 — chưa có mặt trên SSE hay draft.
