# Iterations

Mỗi vòng một nhóm thay đổi. Patch riêng của từng vòng ở `evals/patches/` (revert:
`git apply -R evals/patches/<file>`). Đo offline bằng `evals/refetch_tools.py` (gọi lại tool dữ liệu
trong container để có kết quả đầy đủ — trace chỉ giữ bản preview) + `evals/replay_grounding.py`
(chạy grounding cũ và mới trên cùng câu trả lời, cùng nguồn).

## Vòng 1 → sửa: kỳ của ô bảng đọc từ tiêu đề cột

**Chẩn đoán.** Nhóm mất điểm lớn nhất ở vòng 1 là **Số** (câu mới 1/5, câu neo 1/4). Trong đó có
một lớp lỗi nguy hiểm nhất vì harness *tự nói sai*: N2 (060ca6ad) có 5 ô trong bảng
"Chỉ số | Q3/2025 | Q4/2025 | …" mang nhãn nguồn của kỳ khác, được coi là grounded.
Truy nguyên:
- Dữ liệu: KBS trả 3 kỳ và bỏ `Quý 4/2025` (`dropped_periods: ['Quý 4/2025']`); model tự điền ô
  Q4/2025 bằng số Q3/2025 (tự đánh dấu `*`).
- Kiểm chứng: `grounding._context` lấy nguyên dòng bảng làm ngữ cảnh thời gian, nhưng dòng
  "| Nợ/Vốn CSH | 0.93 | 0.97 |" không nêu kỳ — kỳ nằm ở dòng tiêu đề. `periods()` không thấy kỳ
  nào → luật kỳ không áp → số khớp ở *bất kỳ* kỳ nào cũng qua, và nhãn chọn nguồn mới nhất.
- Loại trừ: kết quả `get_financial_ratios` bị cắt ở 24.000/38.213 ký tự (`MAX_RESULT_CHARS`)
  và chứa cùng dữ liệu 3 lần (`statements`, `excerpt`, `parts`), nhưng model vẫn thấy trọn JSON
  `statements` (kết thúc ở ký tự 14.312) → không phải nguyên nhân của ô sai; ghi lại, chưa sửa.

**Giả thuyết.** Thêm tiêu đề cột vào ngữ cảnh của ô bảng thì (a) ô chép từ kỳ khác thành
`chưa kiểm chứng` (lý do `wrong_period`) và đi vào repair round, (b) ô đúng số mang đúng nhãn kỳ,
(c) cột mang tên mã chỉ khớp báo cáo của mã đó.

**Thay đổi** (`evals/patches/r1-table-column-period.patch`): `grounding._table_header` tìm dòng đầu
của bảng; `_context(line, offset, header)` đặt ô tiêu đề của cột chứa con số trước dòng đó.
3 test mới trong `tests/test_agent_grounding.py`.

**Kết quả trước/sau (replay offline trên 9 Turn vòng 1, nguồn đầy đủ):**

| Turn | Số chưa kiểm chứng trước → sau | Thay đổi |
|---|---|---|
| N2 060ca6ad | 12 → 15 | "2.157", "48.2%", "51.8%" (ô Q4/2025 chép từ Q3/2025) grounded → `wrong_period`; "0.97" nhãn 30/06/2026 → 31/12/2025 (Vietcap Q4/2025 đúng là 0,97); "1.67" nhãn 31/12/2025 → 30/09/2025; "10.00%" nhãn sự kiện 25/05/2026 → 30/09/2025 |
| A3 9c211aa8 | 9 → 8 | "1.785,11 điểm" dưới cột "Đóng cửa 25/9" `wrong_period` → grounded phiên 25/09/2026 (VCI xác nhận 1785,11) |
| A1, A2, A4, N1, N3, N4, N5 | không đổi | — |

Không có nhãn đúng nào bị mất; mọi thay đổi đều đúng theo dữ liệu. Backend 1502 → 1505 passed.
Trên tiêu chí **Số** của `grade.py`, N2 vẫn K (3 ô `wrong_period` giờ là `chưa kiểm chứng`), nên tỉ
lệ đạt chưa đổi; cái đổi là không còn nhãn nguồn nói sai kỳ.

**Hỏi lại (vòng 2, sau `docker compose restart api` lúc 12:27):** câu nhắm điểm vừa sửa N2 (bảng DGC theo
quý) và N3 (bảng CTG/BID/VPB theo mã) sạch hoàn toàn ở phần bảng; replay vòng 2 cho thấy bản sửa sửa đúng 2
nhãn ở A1 ("4,99%" cột Q2/2026 từ `wrong_period` → grounded; "0,35%" nhãn 30/09/2025 → 30/06/2026) và
không đổi nhãn nào ở Turn khác. Câu neo tụt Ngày và Thiếu/không chắc 1 câu, đều ở A4 — Turn bản sửa không
chạm tới (replay: 0 thay đổi) → dao động của model.

**Quyết định: giữ.**

## Vòng 2 → sửa: lượt planning của lane deep trả prose thì được hỏi lại một lần

**Chẩn đoán.** Nhóm mất điểm lớn nhất vòng 2 (và vòng 1): mọi Turn lane deep rỗng — N7, N10 vòng 2; N7, N9
vòng 1 — 14/27 ô K của câu mới vòng 2. Truy nguyên:
- Lane deep đến từ `mode:signal_desk` (mọi Turn Signal Desk) hoặc `length:265` (câu dán tin dài).
- Pipeline bắt đầu bằng lượt planning gọi model với `tool_choice="required"` (`loop.py`); khi completion không
  có tool call, `_advance_deep_pipeline` fail ngay với `planner_returned_no_search_batch` → ledger rỗng,
  `verifier_failed`, không chart (chart chỉ dựng ở bước verification, `loop.py` `build_visual`).
- Đo trực tiếp route: `tool_choice="required"` và ép một function cụ thể đều bị bỏ qua — model trả
  `finish_reason=stop`, không tool call, chỉ lời chào. Capability Probe đang tắt nên harness không biết.
- Nguyên nhân gốc: harness dựa vào một năng lực route không có; không có đường phục hồi.

**Giả thuyết.** Khi lượt planning trả prose, bỏ prose (không đưa cho người đọc) và hỏi lại đúng một lần với
ghi chú nói rõ lượt này chỉ nhận tool call + note planning gốc → model tuân theo, pipeline chạy đủ, Signal Desk
có chart. Lần thứ hai vẫn prose thì fail đóng như cũ.

**Thay đổi** (`evals/patches/r2-planning-retry.patch`): `MAX_PLANNING_RETRIES = 1`, `PLANNING_RETRY_NOTE`,
`_TurnState.planning_retries`; `_advance_deep_pipeline(..., market)` gắn lại `planner_note(market=...)`.
Không thêm loại sự kiện SSE (hợp đồng public). 2 test mới; 2 test đếm số lần gọi model được cập nhật
(`[1] → [1, 1]`, attempt `running/completed` ×2) vì hành vi mới là hỏi thêm một lần. Backend 1507 passed.

**Hỏi lại (vòng 3):** log api xác nhận retry chạy ở cả 3 Turn deep (N7, N9, N10: "planning pass answered in
prose … asking once more"), và cả 3 vẫn prose ở lần hai. Không Turn nào cứu được; câu mới tụt ở 6/7 tiêu chí
(phần lớn do N5 lỗi tool và dao động model, không do retry). **Quyết định: revert** (gỡ hằng, trường state, 2
test; trả 2 test đếm lượt gọi về như cũ). Giữ lại một dòng log ghi nguyên văn prose planner trả về — đó là cái
dẫn tới chẩn đoán đúng bên dưới.

## Vòng 3 → sửa: note của harness đi bằng vai user thay vì system (+ tên thứ trong `today`)

**Chẩn đoán.** Log mới cho thấy planner *có định* gọi tool nhưng viết nó thành text:
`'Tôi sẽ tìm kiếm … <tool_call>web_search.instant(query: "MSN … 2024")'` (lần hai: `</think>Tôi không thể truy
cập dữ liệu chứng khoán…`). Thử trực tiếp trên route, cùng tools, cùng `tool_choice="required"`, chỉ khác chỗ
đặt note planning:
- note là **system message đặt sau câu hỏi** (đúng như `loop._appended` đang làm): 2/2 lần prose, 0 tool call;
- note nằm **trong vai user**: 2/2 lần đúng batch 3 `web_search` + 1 `get_market_data`.
Nguyên nhân gốc: route kiro (và nhiều route OpenAI-compatible) xử lý kém system message không nằm đầu hội thoại.
Mọi note giữa Turn (planning, research, counter, repair số, nudge, hết vòng, guardrail) đều đi đường này.

**Thay đổi** (`evals/patches/r3-harness-notes-user-role.patch`): `_appended` gửi note bằng `Role.USER` với tiền
tố `HARNESS_NOTE_PREFIX = "[Ghi chú của hệ thống, không phải người dùng viết]\n"`; ước lượng token của repair
note theo cùng dạng. 1 test mới (note planning là message user cuối, chỉ còn 1 system message); 9 assertion so
sánh nội dung note trong `test_agent_loop.py` thêm tiền tố. Nội dung note không đổi; lớp untrusted không đổi (note
là chữ của harness, không phải nội dung tool).

Kèm theo, cùng lần deploy: `evals/patches/r3-weekday-in-today.patch` — dòng `- today:` của runtime tail thêm tên
thứ (`2026-09-27 (Chủ nhật)`); vòng 1–2 model gọi Chủ nhật là "thứ Bảy/thứ 7" ở 3 câu trả lời.

**Lưu ý đo lường:** từ lần restart 13:27, container cũng chạy các thay đổi của phiên `stock-massive-fb`
(executor chặn năm cũ trong tham số tool, `web_search` dùng Tavily `topic=news` khi có `recency_days`,
grounding thêm luật sai thứ / "phiên hôm nay" khi nghỉ / P/E báo cáo gọi là "theo giá gần nhất"). Vòng 4 đo
tổng các thay đổi đó; chỉ phần deep lane (N7, N9) và thứ trong tuần quy được riêng cho thay đổi của vòng này.
Test: các test agent liên quan pass; `make test` còn đỏ 2 test prompt/context-engine và nhóm auth/message_flags
(`users.preferences` chưa có trên DB host) — đều do phiên khác, đỏ cả khi gỡ hết thay đổi của vòng này.

## Sửa kèm vòng 4: 5xx "cooldown … rate_limit" là rate limit, không phải lỗi gateway

**Chẩn đoán.** Lượt chạy đầu của vòng 4 mất 11/14 Turn trong 5 s: proxy kiro throttle bằng
`500 {"message":"kiro: token is in cooldown for 36.5s (reason: rate_limit_exceeded)"}`; `errors.classify_status`
đọc mọi 5xx thành `GatewayTimeout` → breaker mở → Turn kết thúc. Client đã có nhánh chờ-thử-lại cho 429 (≤3 lần,
≤60 s) nhưng lỗi này không đi vào đó. Người dùng thật gặp y hệt (Turn BĐS 27/09).

**Thay đổi** (`evals/patches/r4-cooldown-500-is-rate-limit.patch`): `_COOLDOWN` regex; 5xx có "cooldown for Ns …
rate_limit" → `RouteRateLimited(retry_after=N)`. 2 test (thân kiro thật → rate limit với `retry_after`; 5xx chỉ
nhắc "limit" vẫn là gateway). 160 test LLM pass.

**Kết quả:** sau deploy 14:00, lượt chạy lại hoàn tất A4, N1, N2 (không còn `gateway_timeout`), rồi dừng vì 402
hết hạn mức — lỗi khác, đúng là phải dừng. **Giữ.**

## Kết quả vòng 4 cho thay đổi của vòng 3 (note vai user + tên thứ)

Chưa đo được phần chính: N7 (deep, injection) và N9 (deep, chart) nằm trong 8 câu bị 402. Bằng chứng gián tiếp:
thử trực tiếp route (2/2 vs 0/2) ở mục chẩn đoán vòng 3; câu neo vòng 4 không tụt tiêu chí nào so với vòng 3 và
tăng ở Số/Năm/Ngày (A3 lần đầu đúng tuần ngay từ lệnh đầu — nhưng executor chặn năm cũ của phiên song song cũng
góp phần, không tách được). Tên thứ: A4 vẫn viết "có thể là cuối tuần hoặc nghỉ lễ" dù prompt ghi Chủ nhật →
chưa thấy hiệu quả rõ. **Quyết định: giữ tạm, chờ đo N7/N9 khi có quota.**

**Hỏi lại đầy đủ (vòng 4 hoàn tất 14:52):** 2/2 Turn deep **qua planning** (N7 injection, N9 chart) — vòng 1–3: 0/7.
Chưa Turn deep nào ra câu trả lời: N7 hỏng ở research draft (`research_draft_schema_invalid`, phiên
`stock-massive-fb` nhận sửa `evidence/pipeline._object_text`: bỏ phần trước `</think>`, lấy object JSON đầu tiên);
N9 research pass chạm trần vòng tool, route vẫn trả tool call ở lượt final → câu dẫn bị công bố làm answer (chưa
sửa, ứng viên vòng sau). Không tiêu chí câu neo nào tụt; câu mới tăng ở Số 3→6, Năm 7→8, Ngày 2→4, Tool 6→10.
**Quyết định: giữ** note vai user và tên thứ.

## Vòng 4 → sửa: calculator có phép `average`, nhận tới 66 input

**Chẩn đoán.** N6 (KL phiên gần nhất so với TB 20 phiên) gọi `calculate` 6 lần mà cả 6 kết quả vẫn
`chưa kiểm chứng`. Truy nguyên: model tự cộng 20 khối lượng thành "85.585.200" rồi `divide` cho 20; grounding
(`_resolve_calculations`) chỉ nhận phép tính khi *mỗi input* có trong nguồn gốc → từ chối (đúng). Nguyên nhân gốc là
tool thiếu năng lực: không có phép trung bình, và `MAX_INPUTS = 12` không chứa nổi 20 phiên, nên model không có
đường hợp lệ nào. Câu hỏi "so với trung bình N phiên" là dạng phổ biến.

**Thay đổi** (`evals/patches/r5-calculator-average.patch`): `OPERATIONS["average"]`, công thức in đủ
`(a + b + …) / n`; `MAX_INPUTS = 66` (≈3 tháng phiên); mô tả tool dặn truyền từng giá trị, không truyền tổng tự
cộng. 1 test: 20 khối lượng từ nến ngày → trung bình qua calculator → grounded. 93 test liên quan pass.

**Hỏi lại (vòng 5, sau restart 15:12):** hai câu nhắm thẳng bản sửa — N7 (KL trung bình 10 phiên FPT/MSN) grounded cả
2 số qua `average`; N6 (giá HPG so với TB 20 phiên) có TB "21.498 đồng" grounded, nhưng phần trăm chênh lệch
`chưa kiểm chứng` vì `percent_change` lấy input là một kết quả tính (grounding chỉ nhận input in trong nguồn gốc —
ghi lại làm giới hạn đã biết). Câu mới Số 6→7, Ngày 4→6, Ledger 7→10. **Quyết định: giữ.**

Cùng vòng, phiên `stock-massive-fb` deploy research-prose-thành-answer: 2/2 Turn deep ra câu trả lời lần đầu
(N8 bác 3/3 số trong ghi chú có injection). N9 Signal Desk ra câu trả lời là code matplotlib, không có chart —
việc của phiên đó (fallback không gọi `build_visual`; model không biết host tự vẽ).

## Vòng 5 → sửa: dòng "PHIÊN GẦN NHẤT" ghi thứ, lý do nghỉ và phiên kế tiếp

**Chẩn đoán.** Lỗi lặp lại nhiều vòng nhất ở câu hỏi giá "hôm nay": khi không có phiên, câu trả lời không nói rõ
và không nói được phiên kế tiếp — A2 mọi vòng ("Phiên hôm nay 27/09/2026 chưa có dữ liệu đóng cửa"), A4 vòng 2–5
("có thể là cuối tuần hoặc nghỉ lễ"), N4 vòng 5, N8 vòng 4 và N10 vòng 5 (hỏi thẳng "phiên kế tiếp thứ mấy, ngày
nào" → "ngày làm việc tiếp theo"). Tên thứ trong prompt (vòng 3) không đủ. Truy nguyên: dòng tool model đọc ngay
cạnh giá là `PHIÊN GẦN NHẤT 25/09/2026 (hôm nay 27/09/2026 chưa có phiên đóng cửa)` — không phân biệt "chưa đóng
cửa" với "nghỉ", và không có ngày phiên kế tiếp dù `domain/trading_calendar.py` đã biết cả hai. Model phải tự suy
lịch, và suy sai hoặc né. Đây là sự thật của harness, không nên để model tính.

**Thay đổi** (`evals/patches/r6-market-day-in-latest-line.patch`): `trading_calendar.next_trading_day`;
`market_data._no_session_today` — ngày nghỉ ghi `hôm nay Chủ nhật 27/09/2026 thị trường nghỉ (cuối tuần); phiên kế
tiếp Thứ Hai 28/09/2026` (lễ: `nghỉ lễ <tên>`), ngày giao dịch chưa đóng cửa giữ nguyên câu cũ; `WEEKDAYS` public
trong `prompt/contract.py`. Ngày phiên kế tiếp nằm trong output tool nên kiểm tra ngày của grounding nhận nó.
3 test (lịch: CN→T2, qua kỳ nghỉ Quốc khánh, năm chưa có lịch → None; tool: dòng ngày nghỉ, dòng ngày giao dịch).
