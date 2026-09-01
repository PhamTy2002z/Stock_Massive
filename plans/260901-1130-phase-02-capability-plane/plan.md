---
plan: 260901-1130-phase-02-capability-plane
title: "Phase 2 — Unified Capability Plane"
status: done — gate xanh 2026-09-01, hai câu hỏi mở chuyển P5
roadmap: "docs/roadmap.md §10 Phase 2"
branch: feat/phase-02-capability-plane
---

# Phase 2 — Unified Capability Plane

Roadmap authority: [`docs/roadmap.md`](../../docs/roadmap.md) §10 Phase 2,
§6 (quy tắc dependency 3–4), §9 (nguyên tắc thi công).

## Outcome

Một declaration duy nhất quyết định model thấy tool nào và tool được parse,
authorize, budget, execute, trace, trim, hiển thị ra sao. Resolved capability
sở hữu đủ các trục roadmap liệt kê: name/version, schema, description,
availability, handler, read/write effect, trust/data class, **permission
rule**, idempotency, concurrency/barrier, **timeout**/cost, output policy,
display metadata. Đây là điều kiện để Phase 11/12 thêm capability không tạo
dispatch path thứ hai.

## Non-goals

- Không dựng policy engine `allow|ask|deny` theo resource — đó là Phase 5.
  Phase này chỉ đưa **permission rule vào declaration** và cho executor một
  điểm enforce duy nhất.
- Không có approval flow cho `ask` — chưa tồn tại trước Phase 5.
- Không đổi lane/loop semantics, không đổi round backstop 30s — Phase 3.
- Không thêm capability nào ngoài catalog 5 tool; không đổi hành vi runtime
  của 5 tool đang ship (tất cả khai `allow`, timeout khai trên bound nội bộ
  sẵn có).
- Không thêm dependency (không `jsonschema`); "schema model = schema executor"
  chứng minh bằng identity của frozen schema trên surface, không bằng
  validator mới.

## Gap analysis — verify trong code thật (2026-09-01)

Nền đã tồn tại và **đọc cùng một nguồn** (không tin nhãn Done của P0/P1):

| Trục roadmap | Thực tế trong code |
|---|---|
| name/version | `ToolEntry.name` + `contract_version` (`registry.py`) |
| schema | frozen một lần trong `ResolvedTool.from_entry`; model đọc `surface.offered_schemas`, executor lookup `surface.by_name` — cùng object (`definitions.py`, `executor.py:210`) |
| description, availability | `check_fn`/`requires_env`, TTL cache 30s, reason sanitized |
| handler | `ToolEntry.handler` + `handler_identity` |
| effect, idempotency, concurrency | có; `plan_segments` đọc effect+concurrency quyết barrier |
| trust/data class | `content_trust`; `untrusted.wrap_result(resolved=…)` đọc declaration |
| cost | phân loại `access NETWORK/STORE` → hai ceiling admission per-round (`executor._admit`) đọc declaration qua surface |
| output policy | `max_result_size_chars` → `TurnBudget(registry_limits=…)` build từ surface (`loop.py:980`) |
| display | `display_name`/`summary_detail_arg`/`summarise`; `summarise_call(resolved=…)` |
| trace | executor `_record` ghi một entry mỗi call, dispatched hay không |
| **permission rule** | **chưa tồn tại** |
| **timeout per-call** | **chưa tồn tại** — chỉ có backstop `wait_for` 30s cấp round, timeout ở đó giết cả Turn (`loop.py:1638`) |

Typed result hiện có: `unknown_tool`, `tool_unavailable`, `invalid_arguments`,
`blocked_call`, `halted_turn`, `tool_failed`, `dispatch_failed`,
`round_fanout_exceeded`. Gate Phase 2 đòi thêm **denied** và **timeout**
settle một typed result.

## Thiết kế

### 1. `ToolPermission` trên declaration (`registry.py`)

- Enum `ALLOW | ASK | DENY`. Field **bắt buộc, không default** — `register()`
  refuse registration thiếu permission, cùng cơ chế với `display_name`. Không
  default nghĩa là phase này **không đặt default permission nào** (default
  permission là cửa một chiều, để nguyên cho P5).
- 5 tool đang ship khai `ALLOW` tường minh — hành vi runtime không đổi.
- `ResolvedTool` mang field; `identity_payload` thêm field, bump
  `resolver_version` lên `resolved-tool-surface@2`.

### 2. Per-call timeout trên declaration

- `timeout_seconds: float` — default `DEFAULT_TOOL_TIMEOUT_SECONDS = 20.0`,
  phải hữu hạn, > 0. Materialize trên `ResolvedTool` + identity payload.
- Khai cho tool ship dưới backstop round 30s và trên bound nội bộ của handler:
  `fetch_url` 25s (nội bộ 8s/fetch × redirect), `web_search` 20s, ba tool
  memory 10s.

### 3. Executor enforce từ cùng declaration (`executor.py`)

- Thứ tự refusal mỗi call: unknown → unavailable → **permission** → invalid
  args → guardrails → dispatch.
- `DENY` và `ASK` đều settle typed result `permission_denied`,
  `dispatched=False`, một result, sibling không bị ảnh hưởng. Text của `ASK`
  nói thật: approval flow chưa tồn tại nên fail-closed (named assumption A1).
- `_invoke` bọc `asyncio.wait_for(entry.timeout_seconds)`; `TimeoutError` →
  typed result `tool_call_timeout` (`ok=False`, `dispatched=True`, có
  `duration_ms`), ghi `after_call` để repetition ladder nhìn thấy failure,
  ghi trace. Handler `is_async=False` chạy trong thread không cancel được —
  `wait_for` vẫn trả kết quả cho round, thread tự hết theo bound nội bộ của
  nó; ghi rõ trong docstring.

### 4. Contract test = gate (`tests/test_agent_capability_contract.py`)

Mở rộng file đang có, giữ `EXPECTED_CATALOG` là chỗ khoá catalog (thêm cột
permission + timeout):

1. **Một declaration chảy qua mọi consumer:** mở rộng test
   `one_read_only_registration…` — thêm trace writer thật (assert entry ghi
   đúng call), assert schema executor dispatch **là** (identity `is`) schema
   trong `offered_schemas`, assert permission/timeout có mặt trên resolved.
2. **Typed settle:** unknown / invalid args / `DENY` / `ASK` / per-call
   timeout / handler raise — mỗi cái đúng một result, đúng error code, và
   sibling thành công trong cùng batch vẫn trả `ok=True`.
3. **Stable order:** batch trộn reads parallel-safe + write barrier + một call
   denied → results đúng thứ tự model phát.
4. **Registration refusal:** thiếu permission bị `register()` refuse; timeout
   không hữu hạn/âm bị refuse.

## Preflight §9

### 1. Gate có lệnh chạy được chưa?

Có, hai bậc:

```bash
cd apps/api && pytest tests/test_agent_capability_contract.py \
  tests/test_agent_tool_executor.py tests/test_agent_tool_registry.py \
  tests/test_agent_tool_definitions.py -q        # gate của phase
cd apps/api && pytest -q                          # hồi quy toàn suite
python -m compileall -q apps/api/src apps/api/golden apps/api/tests
```

Không cần re-run golden tốn tiền: hành vi 5 tool ship không đổi (permission
`allow`, timeout trên bound nội bộ); thay đổi duy nhất model nhìn thấy là
identity digest của surface (cache key), không phải schema hay prompt.

### 2. Thứ phase trước để lại — verify trong code thật

Bảng gap-analysis trên là kết quả đọc code hôm nay: `registry.py:151-357`,
`definitions.py:48-177`, `executor.py:194-546`, `loop.py:958-996,1634-1651`,
`budget.py`, `toolsets.py`, `test_agent_capability_contract.py`. Golden
release command của P1 tồn tại trong `Makefile` và artifact baseline nằm ở
`apps/api/golden/artifacts/`.

### 3. Unknown

| Assumption | Nếu sai thì làm gì |
|---|---|
| **A1.** `ASK` fail-closed (settle `permission_denied`) là đủ cho tới P5 — không capability nào ship cần ask trước đó | P5 thay refusal bằng approval flow tại đúng một điểm enforce; field shape là cửa hai chiều |
| **A2.** Timeout khai (25/20/10s) không cắt nhầm call lành trên mạng VN thật | Giá trị là config trên declaration — nâng số, không đổi cơ chế; nếu fetch chuỗi redirect vượt 25s thật thì typed result vẫn giữ Turn sống, model được bảo và gọi lại hẹp hơn |
| **A3.** Đổi `resolver_version` làm miss cache prompt-prefix đúng một lần mỗi combination | Vô hại — cache tự làm đầy lại; không state bền nào đọc digest cũ |

Unknown discoverable đã scout xong trong plan: backstop 30s (`loop.py:278`),
bound nội bộ fetch 8s (`tools/web.py:67`), 12 chỗ khởi tạo `ToolEntry`
(2 file ship + 6 file test + 1 factory), không có `jsonschema` trong deps.

### 4. Đường lùi

Pure code trong `apps/api/src/agent/` + tests; không migration, không đổi
bảng, không đổi contract HTTP/SSE, không đổi tool catalog. Dừng giữa phase =
revert nhánh `feat/phase-02-capability-plane`; production không đổi.

## Cửa một chiều — kiểm tra

Không chạm: public HTTP/SSE giữ nguyên; không drop data; không đổi ranh giới
legal; **không đặt default permission** (field bắt buộc, tool ship khai
tường minh); không capability ngoài catalog; không đụng hợp đồng sự thật §2.

## Việc

| # | Việc | File |
|---|---|---|
| 1 | Permission + timeout trên `ToolEntry`/`ResolvedTool`, refusal khi đăng ký, identity payload @2 | `registry.py`, `definitions.py` |
| 2 | Executor enforce permission + per-call timeout, hai typed result mới | `executor.py` |
| 3 | Khai permission/timeout cho 5 tool ship + factory test | `tools/web.py`, `tools/memory.py`, `tests/agent_tool_world.py` |
| 4 | Contract test gate + cập nhật test hiện có | `tests/test_agent_capability_contract.py`, `tests/test_agent_tool_{executor,registry,definitions}.py`, `tests/test_agent_{loop,untrusted_results}.py` |

## Nghiệm thu

1. Gate test xanh bằng lệnh ở Preflight-1; toàn suite `pytest -q` xanh;
   `compileall` sạch.
2. Thêm một tool thử nghiệm trong test suite chỉ cần **đúng một declaration**
   — executor, prompt schema, trace, budget, display đọc cùng nguồn, chứng
   minh bằng test số 1.
3. Unknown/invalid/denied/timeout/handler-error settle một typed result;
   parallelism giữ stable order — test số 2, 3.
4. `git diff --check` sạch; không tham chiếu Signal Desk/Study nào mới.

## Kết quả (2026-09-01)

Gate **đạt**: 84 test gate xanh (`test_agent_capability_contract.py` + ba file
executor/registry/definitions), toàn suite 1144 passed (baseline trước phase
1136), compileall và `git diff --check` sạch. Hành vi runtime 5 tool ship
không đổi. Report thi công:
[`plans/reports/fullstack-260901-1130-phase-02-capability-plane.md`](../reports/fullstack-260901-1130-phase-02-capability-plane.md).

Một defect bắt được khi nghiệm thu và đã sửa kèm regression test:
`socket.timeout` là alias của `TimeoutError`, nên wire timeout 8s bên trong
`fetch_url` sẽ bị nhãn nhầm thành `tool_call_timeout` kèm câu văn sai số giây;
executor nay bắt exception của handler **bên trong** coroutine được `wait_for`
bọc, để `TimeoutError` thoát ra chỉ có thể là bound khai trên declaration.

Hai câu hỏi mở, đúng chủ sở hữu là **Phase 5** (policy plane):

1. Tool `deny`/`ask` hiện vẫn nằm trong `offered_schemas` — chỉ availability
   lọc surface. Có rút tool non-allow khỏi schema model thấy hay không là
   quyết định của policy plane, không phải của declaration.
2. Timeout khai (25/20/10s) chưa có số đo tần suất chạm trên mạng thật —
   theo dõi qua log `passed its declared bound` trước khi P5 tinh chỉnh.
