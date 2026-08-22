---
phase: 2
title: "Thang guardrail tới được bằng 4 round"
status: complete
---

# Phase 2 — Thang guardrail tới được bằng 4 round

## Lớp lỗi đang mở

`guardrails.py:86-87` mang ngưỡng của Hermes:
```python
exact_failure_block_after: int = 5
same_tool_failure_halt_after: int = 8
```

Hermes có ≥8 round mỗi turn. Ta có `MAX_TOOL_ROUNDS = 4` (`loop.py:143`) và
`MAX_EXTERNAL_TOOL_CALLS = 6` (`loop.py:261`). Và 4/5 tool nằm trong `PARALLEL_SAFE_TOOLS`
(`executor.py:54`), nên cả batch chạy `asyncio.gather` — **mọi `before_call` của một round
quyết định xong trước khi `after_call` đầu tiên kịp chạy**.

Số học ra thế này:

| Rung | Ngưỡng | Tới được? |
|---|---|---|
| `warn` exact | 2 | ✅ round 1 |
| `warn` same-tool | 3 | ✅ round 2 |
| `warn` no-progress | 2 | ✅ |
| `block` exact | 5 | ❌ 4 round × 1 call = 4 lần fail. Chỉ tới nếu model fan-out ≥5 call **byte-identical** trong một round |
| `halt` same-tool | 8 | ❌ với `web_search`/`fetch_url`: trần 6 call/Turn < 8. **Bất khả** |

Test loop-level tự thừa nhận: `test_a_halt_makes_the_next_call_the_answering_one` phải dựng
fan-out 8 call mới chạm halt, và comment ghi *"one round can reach it"* — tức biết là chỉ
một round mới tới được.

**Thang thực chất là warn-only trên bề mặt 5 tool thật.** Đây đúng lớp lệch số học mà
`docs/hermes/hermes-synthesis-260821-0030.md` §6 cảnh báo: *"loop.py nói 8 round, code là 4.
Chỗ nào quan trọng thì đọc code, đừng đọc lời tự thuật."*

## Thay đổi

### `agent/guardrails.py`

Ngưỡng mới, và mỗi con số phải là **một phép tính có nguồn**, ghi vào docstring của
`GuardrailThresholds` theo đúng khuôn `loop.py:136-143`:

| Field | Cũ | Mới | Phép tính |
|---|---|---|---|
| `exact_failure_warn_after` | 2 | 2 | giữ. Cảnh báo sớm là đúng |
| `same_tool_failure_warn_after` | 3 | 3 | giữ |
| `no_progress_warn_after` | 2 | 2 | giữ |
| `exact_failure_block_after` | 5 | **3** | `before_call` chặn khi đã có `>= block_after` lần fail, tức lần gọi **thứ tư** bị chặn: fail ở round 0, 1, 2 → round 3 bị chặn. Vừa khít 4 round. Ngưỡng 5 nằm ngoài tầm |
| `same_tool_failure_halt_after` | 8 | **6** | Bằng `MAX_EXTERNAL_TOOL_CALLS`. Một tool fail 6 lần đã tiêu hết ngân sách external — hai con số là **một dữ kiện**, nên viết là một. Tới được trong 4 round bằng fan-out bình thường (2+2+2), không cần batch bất thường |

`same_tool_failure_halt_after = 6` phải để lại comment nói rõ nó gắn với
`loop.py:MAX_EXTERNAL_TOOL_CALLS`, và đổi một cái là đổi cả hai. Không import chéo — module
này `Pure: no session, no clock, no Settings` và phải giữ vậy; ràng buộc sống trong docstring
+ một test khẳng định hai số bằng nhau.

### Không đổi ở phase này

Mù song song trong một round (`before_call` của cả batch chạy trước `after_call` nào) **không**
đóng ở đây. Nó đóng ở Phase 3 bằng trần fan-out: một round không mang được 8 call giống nhau
thì rung không bị lách. Hai phase bù nhau, và tách ra vì một cái là số học của ladder, một
cái là biên của executor.

## Validation

Test tại `apps/api/tests/test_agent_guardrails.py` — sửa tên và số của ba test đang neo vào
ngưỡng cũ:
- `test_the_sixth_identical_call_is_blocked_before_it_is_dispatched` → lần thứ tư.
- `test_the_eighth_failure_of_one_tool_halts_the_turn` → lần thứ sáu.
- `test_blocked_calls_still_count_towards_the_halt` — số đổi, tính chất giữ.

Test mới, và đây là cái đáng giá nhất của phase:
1. **Ladder chạm `block` bằng chuỗi call bình thường qua các round**, mỗi round một call,
   trong `MAX_TOOL_ROUNDS`. Không fan-out.
2. **Ladder chạm `halt` bằng `web_search` trong trần `MAX_EXTERNAL_TOOL_CALLS`.** Test này
   trước đây không thể pass — nó là bằng chứng lớp lỗi đã đóng.
3. Một test khẳng định `DEFAULT_THRESHOLDS.same_tool_failure_halt_after == MAX_EXTERNAL_TOOL_CALLS`,
   để lần sau ai đổi một số thì test nói ngay.

`tests/test_agent_loop.py`: hai test halt hiện dựng fan-out 8 → giảm còn 6, giữ nguyên tính
chất đang khẳng định (mọi call có result, Turn không kết thúc, `tool_choice="none"`).

Cổng: `make test`.

## Risk / rollback

- **Risk**: hạ ngưỡng làm `block`/`halt` nổ trên Turn lành. Ngược lại là điều đang xảy ra —
  rung không bao giờ nổ — nên hướng sai lệch hiện tại đã là tệ hơn. `warn` không đổi, và
  `block` vẫn **trả guidance thay cho result** chứ không kết thúc Turn: fail-open giữ nguyên.
- **Risk**: `halt=6` cắt sớm một Turn thật cần 6 lần tra. Không: 6 là số lần **fail** của
  cùng một tool, không phải số lần gọi. Sáu lần fail liên tiếp là Turn đã hỏng.
- **Rollback**: 5 con số trong một dataclass. `git revert`.

## Đã làm (2026-08-22)

`guardrails.py`: `exact_failure_block_after` 5 → **3**, `same_tool_failure_halt_after` 8 → **6**,
và docstring của `GuardrailThresholds` giờ mang phép tính của cả hai rung — kèm câu nói rõ vì
sao không import `loop`: module này giữ nguyên tính pure, đẳng thức do test giữ.

`tests/test_agent_guardrails.py`: đổi tên/số ba test neo vào ngưỡng cũ (`the_sixth_identical_call`
→ `the_fourth_identical_call`, `the_eighth_failure` → `the_sixth_failure`, và vòng `range(8)` của
test reset → `range(6)`). Thêm ba test:
`test_the_block_rung_is_reached_at_one_call_a_round` (dựng đúng hình judge → dispatch → record
của loop, không fan-out, `MAX_TOOL_ROUNDS` vòng),
`test_the_halt_rung_is_reached_inside_the_external_call_budget` (2 call/round, dừng ở
`MAX_EXTERNAL_TOOL_CALLS` — test này **không thể pass** dưới ngưỡng 8), và
`test_the_halt_rung_is_the_external_call_ceiling` (đẳng thức với `MAX_EXTERNAL_TOOL_CALLS`).

`test_blocked_calls_still_count_towards_the_halt` **không cần sửa**: nó tự dựng
`GuardrailThresholds(2, 4)` nên đã độc lập với mặc định — plan dự đoán phải đổi số, code thật thì
không.

`tests/test_agent_loop.py`: hai test halt giảm fan-out 8 → 6, `len(outcome.tool_calls)` 9 → 7,
và comment "Eight failures" viết lại — nó nói rằng chỉ một round mới tới được halt, điều vừa
hết đúng.

Cổng: `tests/test_agent_guardrails.py` 15/15, `tests/test_agent_loop.py` 66/66.
