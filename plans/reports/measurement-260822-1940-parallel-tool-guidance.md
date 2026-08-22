# Số đo Phase 5 — đoạn prose dạy model gọi tool song song

Ngày đo: 2026-08-22. Plan: `plans/260822-1908-agent-core-fail-open/phase-05-parallel-tool-guidance.md`.

Phase 5 đổi một đoạn prose trong mục `TOOLS` của system prompt và bump
`PROMPT_VERSION` `2.2.0` → `2.3.0`. Eval Battery/Gate đã bị xoá ở `1974c24`, nên
không còn harness đo sẵn; phép đo dưới đây làm bằng tay và đây là toàn bộ bằng
chứng cho thay đổi đó.

## Tính chất phải chứng minh

Plan đặt bar rõ: **cùng số call, ít round hơn** — không phải *nhiều call hơn*.
Lý do là chi phí trước cả độ trễ: mỗi round thêm là một lần gửi lại toàn bộ hội
thoại. Nếu số call tăng mà round không giảm thì đoạn prose làm hại và phải revert.

## Cách đo

Script: `measure_rounds.py` (scratchpad của session, không commit — nó phụ thuộc
`request_message_id` chưa dùng nên không tái dùng được nguyên trạng).

- Chạy `AgentLoop` thật qua `build_client`, model `gpt-5.6-terra`, `trace=None`
  và `checkpoint=None` nên không ghi gì vào store của agent. Ledger chi tiêu vẫn
  ghi, đúng như một lượt thật.
- 6 câu hỏi cố định, mỗi câu **cần từ hai lần tra độc lập với nhau** — đó là hình
  dạng duy nhất mà prose về batching có thể tác động tới. Câu cần tra tuần tự
  không đổi số round dù prompt nói gì, đưa vào chỉ làm loãng phép đo.
- 4 rep mỗi arm → **24 lượt mỗi arm**, 48 lượt tổng.
- Chạy đan xen theo block để xu hướng thời gian không dồn hết vào một arm:
  `before(2 rep)` → `after(2 rep)` → `before(2 rep)` → `after(2 rep)`.
- Mỗi arm dùng một dải `request_message_id` riêng. Cần thiết: ledger tính
  `TURN_INPUT_TOTAL` theo owner = id message yêu cầu, nên một id trùng message
  thật thừa hưởng chi tiêu cũ của nó và bị từ chối ngay lượt đầu — lần chạy thử
  đầu tiên đã chết đúng vì việc này.

## Số

| | before (2.2.0) | after (2.3.0) | Δ |
|---|---|---|---|
| lượt | 24 | 24 | |
| round | 51 | 44 | **−13,7 %** |
| tool call | 107 | 102 | **−4,7 %** |
| call / round | 2,098 | 2,318 | **+10,5 %** |
| input token | 307 372 | 289 272 | −5,9 % |
| output token | 10 216 | 9 817 | −3,9 % |
| lượt `complete` | 24/24 | 24/24 | |
| lượt từng phát >1 call trong một round | 20/24 | 22/24 | |

Theo block, để tách xu hướng thời gian:

| block | round | call | call/round |
|---|---|---|---|
| before | 27 | 56 | 2,074 |
| after | 24 | 54 | 2,250 |
| before-b | 24 | 51 | 2,125 |
| after-b | 20 | 48 | 2,400 |

Ghép cặp theo từng câu (4 quan sát mỗi arm mỗi câu), mean số round:

| câu | before | after | call before | call after |
|---|---|---|---|---|
| 1 lãi suất VCB vs TCB | 3,00 | 3,25 | 6,75 | 7,50 |
| 2 giá vàng SJC + tỷ giá | 1,75 | 1,00 | 3,25 | 2,00 |
| 3 dân số + GDP VN/Thái | 2,50 | 2,00 | 7,00 | 6,00 |
| 4 CEO VinFast + doanh số | 2,00 | 2,00 | 5,00 | 5,00 |
| 5 VAT + hiệu lực giảm | 1,75 | 1,00 | 1,75 | 1,50 |
| 6 Bitcoin + vàng thế giới | 1,75 | 1,75 | 3,00 | 3,50 |

3 câu giảm, 2 câu không đổi, 1 câu tăng.

## Đọc số

**Bar đạt.** Round giảm 13,7 % trong khi số call *cũng* giảm 4,7 %. Chế độ hỏng
mà plan muốn revert vì nó — nhiều call hơn mà round không giảm — không xảy ra
theo cả hai chiều.

**Confound đã kiểm, và nó không giải thích được số.** Chuỗi round theo thời gian
là 27 → 24 → 24 → 20, giảm đơn điệu, nên riêng cột round không phân biệt được
"prose có tác dụng" với "route ấm dần". Cột `call/round` thì phân biệt được: nếu
là xu hướng thời gian thuần, `before-b` (đo *sau* `after`) phải ≥ 2,250. Nó là
2,125 — thấp hơn cả hai block `after` và cao hơn block `before` đầu chỉ 0,05.
Hai arm tách nhau sạch trên cột này, thứ tự thời gian thì không.

**Biên độ nhỏ, và có một lý do rõ.** Model đã tự batch trước khi được dạy: 20/24
lượt của arm `before` đã phát >1 call trong một round, mean 2,098 call/round.
Đoạn prose không mở ra một hành vi mới, nó dồn thêm một phần hành vi đã có. Với
n=24 mỗi arm thì khoảng tin cậy còn rộng; kết luận đúng là *hướng nhất quán,
biên độ nhỏ*, không phải *thắng chắc*.

**Câu 1 là điểm phải canh.** Nó là câu duy nhất xấu đi trên cả hai cột (round
3,00 → 3,25, call 6,75 → 7,50). Nếu về sau thấy số call tổng tăng thì đây là
hình dạng câu hỏi để soi đầu tiên.

## Quyết định

Giữ thay đổi. `PROMPT_VERSION = 2.3.0`.

Ngưỡng revert cho lần đo sau: số call trung bình mỗi lượt **tăng** so với 4,458
của arm `before` mà mean round **không** dưới 2,125.

## Trần external là ràng buộc sống, ở cả hai arm

Lỗi call thật trong 48 lượt, đọc từ `TurnToolCall.error` chứ không phải từ log:

| | before | after |
|---|---|---|
| `external_budget_exhausted` | 10 call, ở 6/24 lượt | 8 call, ở 4/24 lượt |
| `tool_failed` | 0 | 1 (DNS trong container) |

Các dòng `Open-web url read failed: WEB_FETCH_MAX_BYTES / HTTP 400 / HTTP 429`
trên console **không** là call lỗi: tool hấp thụ chúng và trả kết quả, đúng
fail-open. Chúng không xuất hiện trong cột `error` của lượt nào.

`MAX_EXTERNAL_TOOL_CALLS = 6` bị chạm ở 6/24 lượt arm `before` và 4/24 lượt arm
`after`. Đây là điều đáng chú ý nhất ngoài bar: **rủi ro mà Phase 5 tự nêu —
"trần external bị tiêu hết nếu model batch mạnh" — không thành hiện thực, nó còn
đỡ đi.** Nhưng trần đó đang chặn thật, trên cả hai arm, ở đúng những câu cần
nhiều lần tra nhất: 6 trong 10 lượt chạm trần là câu so sánh lãi suất hai
ngân hàng.

Ba việc theo sau, không thuộc phạm vi plan này:

1. `MAX_EXTERNAL_TOOL_CALLS = 6` có thể là con số thấp cho câu so sánh hai đối
   tượng. Nó vào `MAX_TOOL_ROUNDS` và trần fan-out 8 bằng một phép tính
   (`executor.py`), nên đổi nó là đổi cả ba.
2. `external_budget_exhausted` **không** ghi hàng nào vào `agent_tool_call`: nó
   được đặt trên `TurnToolCall` trong `loop.py::_round` và không đi qua
   `executor._record`. Nghĩa là `tool_call_errors` của Phase 4 sẽ *không* thấy
   nó, dù prose của Phase 4 có kể tên nó. Số ở trên đo được chỉ vì script đọc
   `TurnOutcome` trong process.
3. Con số đó ghép với finding của code review Phase 2–3 (external budget bị trừ
   trước khi dispatch): với 4–6 lượt trên 24 đã chạm trần, một call bị trần
   fan-out cắt mà vẫn bị trừ tiền là chuyện xảy ra được, không phải giả thuyết.
