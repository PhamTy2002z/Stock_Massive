# Kiến trúc agent runtime

Tài liệu này mô tả agent runtime trong `apps/api/src/agent` như nó chạy sau đợt
gia cố ngày 2026-09-25 (branch `refactor/agent-harness`). Nó trả lời bốn câu hỏi:
agent tự quyết định làm gì, theo thứ tự nào, khi nào dừng và khi nào hỏi người
dùng. Mỗi quyết định lớn ghi kèm đánh đổi và nguồn gốc (Hermes, nguyên tắc
thiết kế agent công khai của Anthropic, hoặc số đo của chính repo này).

## 0. Quyết định gốc: gia cố, không viết lại

Đợt này được giao toàn quyền viết lại. Nó chọn gia cố tại chỗ, vì ba bằng chứng:

- Runtime đã port phần lớn pattern Hermes có giá trị, mỗi hằng số có số đo đi
  kèm (ví dụ `MAX_EXTERNAL_TOOL_CALLS`, từng là 7 đo trên `llm_call_usage`, nay 20,
  `loop.py`). Viết lại sẽ vứt các số đo đó mà không có số đo mới thay thế.
- Bộ test backend (1507 test) ghim hành vi của loop, context ladder, guardrail,
  settle Turn và SSE replay. Đó là lưới an toàn duy nhất; viết lại làm lưới đó
  mất nghĩa.
- Không có eval so sánh trong phạm vi đợt này. Không đo được thì không chứng
  minh được một bản viết lại "không kém" bản cũ; một thay đổi nhỏ có test riêng
  thì chứng minh được.

Đánh đổi: các điểm yếu mang tính cấu trúc (loop 3.300 dòng trong một file) vẫn
còn. Chúng là nợ bảo trì, không phải lỗi hành vi, và không nằm trong bốn năng
lực đợt này nhắm tới.

## 1. Thành phần

| Thành phần | File | Trách nhiệm |
|---|---|---|
| Turn service | `turns.py`, `service.py` | Tạo Turn bền trước khi chạy, task tách khỏi request, checkpoint, settle nguyên tử, replay SSE |
| Agent loop | `loop.py` | Vòng model ↔ tool, lane, recovery, điều kiện dừng |
| Lane | `lanes.py` | Ngân sách theo loại câu hỏi: số round, số external call, deadline |
| Capability plane | `registry.py`, `toolsets.py`, `tools/` | Một đường đăng ký và dispatch tool; surface theo mode/profile |
| Executor | `executor.py` | Validate tham số theo schema, permission, timeout từng call, song song an toàn |
| Guardrails | `guardrails.py` | Thang allow → warn → block → halt theo chữ ký call |
| Context engine | `messages.py`, `budget.py`, `compaction.py` | Dựng transcript mỗi call, ladder cắt giảm, tóm tắt ngoài băng |
| Prompt | `prompt/` | System prompt tĩnh (cache được) + đuôi runtime |
| Evidence | `evidence/` | Lane deep: plan → research → counterevidence → verify; ledger claim |
| Untrusted | `untrusted.py`, `threat_patterns.py` | Bọc và quét nội dung web |

## 2. Luồng dữ liệu của một Turn

```text
POST turn ─► turns.py tạo agent_turn (idempotent) ─► task nền
  └─► loop.run: chọn lane + surface tool theo mode/profile
        for round in range(lane.max_tool_rounds + 1):
          kiểm tra cancel / deadline
          messages.build (system tĩnh + tóm tắt + lịch sử + Turn hiện tại)
          model.complete(tools, tool_choice)
          ├─ không có tool call ─► câu trả lời ─► settle
          └─ có tool call ─► _round:
               lặp y hệt call đọc đã thành công? ─► dùng lại kết quả, không dispatch
               ngân sách external còn? ─► không: trả lời thay cho call
               executor: validate → permission → guardrail → chạy song song
               kết quả ─► bọc untrusted ─► vào transcript của round sau
  └─► settle một transaction: message + status + terminal_reason
```

## 3. Agent loop và thứ tự công việc

Model quyết định thứ tự; host giữ quyền cuối về ngân sách, quyền, và lý do dừng.
Phương pháp mà model được dạy (prompt mục "Cách làm việc"):

1. **Tách câu hỏi thành các ý** cần trả lời, nhận ra ý nào phụ thuộc ý nào.
2. **Khám phá trước khi kết luận**: tra những gì tra được; không đoán.
3. **Song song việc độc lập**: các truy vấn độc lập đi cùng một round. Executor
   chạy song song các tool `PARALLEL_SAFE`, tuần tự tool ghi (`executor.py`).
4. **Nhánh bị chặn không chặn cả Turn**: một nguồn lỗi hay rỗng thì làm tiếp
   các ý khác, rồi nêu rõ ý nào chưa có bằng chứng.
5. **Tự kiểm đủ ý trước khi trả lời**: mọi ý đã có bằng chứng, hoặc đã được nói
   rõ là thiếu và thiếu gì.

Nguồn: Anthropic, "Building effective agents" (vòng agent đơn giản, model tự
lập kế hoạch, host đặt giới hạn) và hướng dẫn prompting về tool song song. Không
thêm tool `todo` của Hermes: một Turn có 4 round ở lane light, một kế hoạch dài
hơn Turn không tồn tại, và danh sách việc trong prompt rẻ hơn một vòng tool.

Lane deep (`evidence/pipeline.py`) giữ pipeline riêng: planner bắt buộc
`web_search` → research → counterevidence → verifier context sạch.

## 4. Thiết kế tool

Mỗi mô tả tool trả lời bốn câu: nó làm gì, khi nào dùng, khi nào **không** dùng,
và tham số lấy từ đâu. Đây là điểm Anthropic nhấn mạnh nhất trong "Writing
tools for agents": mô tả là prompt, và tham số bị bịa thường do mô tả không nói
nguồn của tham số.

Quy tắc nguồn tham số (ghi vào cả mô tả tool lẫn prompt):

- `fetch_url.url` chỉ lấy từ kết quả `web_search`, từ tin nhắn người dùng hoặc
  từ một trang đã đọc. Không tự dựng URL.
- `get_market_data.symbol` chỉ lấy từ câu hỏi hoặc từ nguồn đã đọc; tên công ty
  chưa rõ mã thì tìm mã trước. `start`/`end` suy từ câu hỏi và ngày hiện tại
  trong bối cảnh Turn.
- Thiếu một tham số mà không nguồn nào có và chỉ người dùng biết thì hỏi,
  không điền giá trị mặc định tự nghĩ ra.

Đọc và ghi tách bằng `ToolEffect` trên `ToolEntry`. Tool ghi duy nhất là
`remember_fact` (phạm vi của chính người dùng); nó bị chặn sau khi Turn đã đọc
nội dung untrusted (`executor.py`), và được checkpoint ý định trước khi chạy.

Surface theo mode: `chat` có năm tool web/memory; `signal_desk` thêm
`get_market_data` trên profile `personal_internal`. Prompt không liệt kê cứng
số tool nữa: danh sách tool của chính lượt đó là nguồn sự thật duy nhất, vì một
con số ghi cứng sai ngay khi surface khác đi.

## 5. Chiến lược context

Giữ nguyên, đã có từ Phase 4:

- System prompt tĩnh, render một lần, là prefix cache được; giá trị runtime
  (ngày, trạng thái phiên, tên) nằm ở đuôi.
- Lịch sử cũ chỉ còn văn xuôi; Turn hiện tại mang đủ call và kết quả.
- Ladder khi vượt trần: thu gọn kết quả đã cũ → bỏ Turn cũ (giữ 2) → thu gọn
  mọi kết quả → rút văn xuôi → `ConstructedContextTooLarge` (settle
  `context_overflow`, giữ câu trả lời dở).
- Route báo tràn thì nén 0,6 lần, tối đa 2 lần; báo vượt output cap thì hạ một
  nửa, tối đa 2 lần, sàn 1.000 token. Lấy nguyên từ Hermes.
- Tóm tắt Thread chạy ngoài băng sau khi Turn settle, khi quá 8 Turn sống.

## 6. Chính sách lỗi và retry

| Tình huống | Xử lý | Nơi |
|---|---|---|
| Tool lỗi | Kết quả lỗi có kiểu trả về model; guardrail cảnh báo ở lần 2, chặn call y hệt ở lần 4, halt tool ở lần lỗi thứ 7 | `executor.py`, `guardrails.py` |
| Tool timeout | Timeout từng call (20–25 s) thành kết quả lỗi; cả round quá 30 s thì settle `tool_timeout` | `executor.py`, `loop.py` |
| Output rỗng sau tool | Nhắc một lần (`EMPTY_AFTER_TOOLS_NOTE`), rồi `empty_answer` | `loop.py` |
| Tham số sai schema | `INVALID_ARGUMENTS` trả về model, không dispatch | `executor.py` |
| JSON tham số hỏng | Nhắc model gửi lại một lần, giữ note của stage đang chờ; lần hai thì settle `route_error` với câu trả lời dở | `loop.py` |
| Call đọc lặp y hệt | Dùng lại kết quả đã có (cả bản hiển thị và verdict quét), không dispatch, không trừ ngân sách external, kèm lời nhắc đừng lặp | `loop.py` |
| Không tiến triển | Kết quả y hệt lần trước ở lần thứ 2 → cảnh báo | `guardrails.py` |
| Route lỗi | Phân loại theo MRO (`_TERMINAL_REASONS`); rate limit và auth không retry; retry và failover model ở `core/llm/client.py` | `loop.py`, `core/llm/` |
| Dữ liệu mâu thuẫn | Prompt: nêu cả hai nguồn kèm thời điểm, ưu tiên nguồn sơ cấp, không tự chọn một số mà không nói; lane deep có counterevidence và verifier | `prompt/`, `evidence/` |
| Yêu cầu mơ hồ | Xem mục 8 | `prompt/` |
| Context quá dài | Ladder và recovery ở mục 5 | `messages.py`, `loop.py` |

Nguyên tắc chung, lấy từ Hermes và từ hướng dẫn của Anthropic về tool error:
lỗi mà model tự sửa được thì trả về model như một kết quả; lỗi mà model không
sửa được thì settle Turn với lý do có tên và giữ câu trả lời dở. Ngoại lệ duy
nhất có chủ đích: route trả hai tool call trùng id hoặc thiếu id
(`ToolCallIdMismatch`) vẫn làm Turn thất bại, vì ghép kết quả vào nhầm call còn
tệ hơn không có kết quả.

## 7. Điều kiện dừng

Turn kết thúc khi và chỉ khi một trong các điều sau xảy ra. Mỗi điều ứng với một
`terminal_reason` ổn định:

- Model trả lời không kèm tool call (`complete`). Lời dẫn trước tool call không
  bao giờ được tính là câu trả lời.
- Hết round: call cuối có `tool_choice="none"` và lời nhắc số round thật của lane.
- Guardrail halt: call kế là call trả lời, không có tool.
- Hết ngân sách external: các call còn lại được trả lời thay, Turn tiếp tục để
  model trả lời từ những gì đã có.
- Cancel, deadline Turn (600 s ở lane light), timeout call model (120 s), hết
  ngân sách tiền, lỗi route không phục hồi.

"Báo tiến độ" và "hoàn thành" tách bằng cấu trúc: tiến độ là `progress` part
(round, số external call đã dùng, hết round, halt) và lời dẫn trước tool call;
hoàn thành là text cuối không kèm tool call. Model được dạy tự kiểm đủ ý trước
khi dừng (mục 3); host đặt trần cứng để dừng luôn xảy ra.

Phát hiện lặp có ba tầng: call đọc lặp y hệt được dùng lại, kết quả y hệt
thì bị cảnh báo no-progress, call lỗi y hệt thì bị chặn.

## 8. Khi nào hỏi người dùng

Chính sách (prompt mục "Khi nào hỏi"):

- **Không tra web để tìm thông tin chỉ người dùng có** (danh mục, giá vốn, khẩu
  vị rủi ro, mã họ đang nói tới khi câu hỏi không xác định được mã). Xem
  `recall_facts`/`session_search`; không có thì hỏi, trừ khi có một cách hiểu
  hợp lý nhất. Phần còn lại của câu hỏi vẫn tra như thường, nên lane deep vẫn
  chạy planner và cổng scout-then-ask của nó không bị prompt làm trái.
- **Tra trước** khi thứ còn thiếu có thể tìm được. Phần lớn câu tưởng là mơ hồ
  sẽ rõ sau một lượt tìm.
- **Làm tiếp với giả định đã nêu** khi có một cách hiểu hợp lý nhất; ghi giả
  định đó ở đầu câu trả lời để người dùng sửa nếu sai.
- **Hành động không đảo ngược được**: runtime không có tool nào như vậy. Tool ghi
  duy nhất là `remember_fact` (đảo ngược được, trong phạm vi của người dùng) và
  chỉ dùng khi người dùng muốn lưu.

Một câu hỏi làm rõ là câu trả lời hoàn chỉnh của Turn đó: model hỏi một câu gọn,
Turn settle `complete`, câu trả lời của người dùng là Turn mới. Lane deep có thêm
thẻ `QuestionPart` với kỷ luật scout-then-ask và một lần hỏi
(`evidence/pipeline.py`). Không có tool `clarify` giữa Turn như Hermes: runtime
là request/response theo Turn, và một pause giữa Turn cần một hợp đồng SSE mới.

## 9. Pattern Hermes: lấy gì và vì sao

| Pattern | Trạng thái | Lý do |
|---|---|---|
| Ngân sách vòng lặp theo round | Có | Round là bước quyết định; fan-out trong round không tốn thêm bước |
| Nhắc một lần khi rỗng sau tool | Có | Một lần là đủ để biết; lần hai là trả tiền để học lại |
| Thang guardrail theo chữ ký call | Có | Chặn lặp lỗi trước khi dispatch, không tốn tiền |
| Dùng lại call đọc idempotent | Có (2026-09-25) | Guardrail cũ chỉ cảnh báo sau lần lặp; lặp đầu tiên vẫn tốn một trong 7 external call |
| Sửa tool call hỏng một lần | Có (2026-09-25) | Hermes trả lỗi JSON về model để model tự sửa; repo cũ vứt cả Turn |
| Nén context / hạ output cap có giới hạn | Có | Đúng hệ số và số lần của Hermes |
| Tách timeout route và deadline nội bộ | Có | Hai nguyên nhân, hai cách sửa |
| Bọc và quét nội dung untrusted | Có | Trang web là dữ liệu, không phải chỉ dẫn |
| Tool `todo` | Không lấy | Turn 4 round; danh sách việc trong prompt đủ |
| Tool `clarify` giữa Turn | Không lấy | Cần hợp đồng SSE mới; hỏi = settle Turn là đủ |
| Tràn kết quả ra file | Không lấy | Không có filesystem cho model; ladder cắt giảm đã xử lý |
| Xoay vòng credential, 7 route fallback | Không lấy | Một route, một credential |

## 10. Rủi ro còn lại

- Chất lượng reasoning thực tế chưa được đo: prompt và mô tả tool mới chưa chạy
  qua golden harness (`make golden-release`, tốn tiền thật).
- Việc dùng lại call y hệt so chữ ký tuyệt đối của tham số; hai truy vấn gần
  giống nhau vẫn là hai call. Cảnh báo no-progress vẫn là lưới cho trường hợp đó.
- `loop.py` vẫn là một file lớn; tách nó là việc bảo trì riêng.
