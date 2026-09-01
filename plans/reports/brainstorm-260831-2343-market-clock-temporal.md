---
type: brainstorm
date: 2026-08-31
branch: refactor/new-direction
status: accepted
scope: B — market clock trong RuntimeContext
---

# Agent gán nhãn "hôm nay" cho phiên giao dịch không tồn tại

## Tóm tắt

Hỏi "Hôm nay thị trường chứng khoán Việt Nam ra sao?" vào ngày nghỉ lễ
31/8/2026, agent tường thuật một phiên giao dịch không tồn tại. Đo 5 lượt trên
API 8000: **sai 3/5**.

## Bằng chứng repro

| Lượt | Nhận nghỉ lễ | Câu mở đầu |
|---|---|---|
| 0 | có | "không giao dịch do kỳ nghỉ Quốc khánh", phiên gần nhất 28/8 |
| a-1 | không | "Thị trường hôm nay (31/8/2026)... nghiêng nhẹ về tăng" (+0,03%) |
| a-2 | có | đúng, nhưng cùng bộ số lại ghi giảm -0,03% |
| a-3 | không | "Hôm nay, 31/8/2026, thị trường điều chỉnh nhẹ" (-0,03%) |
| a-4 | không | "Thị trường Việt Nam hôm nay điều chỉnh nhẹ" |

Hai phát hiện chỉ có được nhờ chạy thật:

1. **Bằng chứng trong context không chặn được lỗi.** Lượt a-4 đã fetch đúng
   `hsx.vn/vi/tin-tuc/hose-thong-bao-lich-nghi-giao-dich-nam-2026/2422804` rồi
   vẫn viết "thị trường hôm nay điều chỉnh nhẹ". Sửa prompt đơn thuần không đủ.
2. **Nguồn lây nhiễm là bảng giá không nhãn ngày.** Cả 5 lượt cùng ra một bộ số
   (VN-Index 1.832,12 / 0,56 điểm / HOSE 17.365 tỷ / 141 tăng-162 giảm) từ
   `vneconomy.vn/thi-truong-chung-khoan.htm`, `vn.investing.com`,
   `24h.com.vn`. Các bảng này đóng băng ở phiên gần nhất và không in ngày phiên.
   Model đọc số, không thấy ngày, gán ngày lịch đang có trong prompt.

Lỗi thứ hai, độc lập: cùng 1.832,12 và 0,56 điểm, a-1 ghi +0,03%, các lượt khác
ghi -0,03%. Dấu bị chép sai ngẫu nhiên. Không thuộc phạm vi lần này.

## Nguyên nhân gốc

`_runtime()` tại `apps/api/src/agent/router.py:405` dựng `RuntimeContext` chỉ với
`today` và `user_name`. `render()` tại `prompt/contract.py:163` nối đúng một
dòng `- today: <iso>`. Hệ thống không có khái niệm phiên giao dịch ở bất kỳ đâu:
`domain/vn_equity.py` (33 dòng) không nhắc phiên, timezone hay ngày nghỉ.

`apps/api/src/agent/evidence/` có đủ `ClaimRef`, `EvidenceRef` và validator
nhưng không được import ở `loop.py`, `service.py` hay `executor.py` — module
chết. Không có cửa chặn nào giữa số đọc được và nhãn thời gian model gắn cho số.

## Contract

- **Outcome.** Với câu hỏi phụ thuộc phiên, agent không gán nhãn "hôm nay" cho
  số liệu của phiên khác. Ngày không giao dịch là dữ kiện hệ thống.
- **Constraints.** Không thêm tool (catalog 5 tool khóa trong CLAUDE.md); không
  đổi public HTTP/SSE contract; bump `PROMPT_VERSION`/`PROMPT_HASH`; bảng nghỉ
  lễ có năm hiệu lực, ngoài phạm vi phải trả "không xác định".
- **Non-goals.** Không nối evidence ledger vào loop; không sửa lỗi dấu; không
  đụng R1 eval.
- **Acceptance.** Chạy lại repro >=5 lượt, 0 lượt gán "hôm nay" cho phiên 28/8.
  `pytest -q` trong `apps/api` xanh, gồm `test_agent_prompt.py`.

## Phương án đã cân nhắc

| | Làm gì | Rẻ để bỏ | Hỏng đầu tiên khi |
|---|---|---|---|
| A | Chỉ thêm luật thời gian vào `vn_equity` pack | rất rẻ | **đã bị a-4 bác bỏ**: model bỏ qua bằng chứng có sẵn |
| B | A + trạng thái phiên deterministic trong `RuntimeContext` | rẻ | bảng nghỉ lễ hết hiệu lực mà vẫn khẳng định |
| C | B + nối evidence/claim ledger, chặn claim thiếu provenance | đắt | chưa có eval R1 nên không đo được cải thiện |

**Chọn B.** Điều làm B khác a-4: ở a-4 thông tin nghỉ lễ nằm trong
`untrusted_tool_result`, mà `sections.py:UNTRUSTED` dạy model coi đó là dữ liệu
để đánh giá. Ở B nó nằm trong system prompt, cùng hạng với `today` mà model vốn
đã tin tuyệt đối.

## Rủi ro còn lại

B làm model tin ngày, không làm model tin số. Lỗi dấu +/- và các số không nhãn
ngày vẫn còn; đó là phạm vi C và cần R1 eval để đo trước.

## Dọn dẹp

Repro để lại trong DB dev: user `repro.clock@example.com` (id 7193) và 5 thread.

## Câu hỏi chưa giải quyết

- Nguồn nào giữ bảng nghỉ lễ: hằng số trong code, config, hay bảng DB?
- Có mở R1 eval để đo lỗi numeric provenance trước khi làm C không?

---

## Kết quả triển khai (2026-09-01)

Đã triển khai phương án B.

**Thay đổi**

- `apps/api/src/agent/domain/trading_calendar.py` (mới) — lịch nghỉ giao dịch
  2026 lấy từ thông báo HOSE, đối chiếu hai nguồn độc lập (vietnambiz, DNSE).
  Cuối tuần suy ra từ ngày nên đúng ở mọi năm; ngày lễ là bảng có
  `COVERED_YEARS`, ngoài phạm vi trả `UNKNOWN` chứ không trả "open".
- `prompt/contract.py` — thêm `MarketPhase`, `MarketDay`; `RuntimeContext` có
  trường `market` mặc định `UNKNOWN` (không có trạng thái im lặng);
  `render()` phát `market_today` và `previous_trading_day`.
- `prompt/sections.py` — section CONTEXT dạy model đọc hai nhãn đó và cấm gán
  nhãn "hôm nay" cho số không kèm ngày phiên. `PROMPT_VERSION` 4.0.0 -> 4.1.0.
- `router.py:_runtime` — dựng `market` từ cùng ngày local đã dùng cho `today`.
- Test mới `tests/test_agent_trading_calendar.py` (16 case).

Luật temporal đặt ở section CONTEXT của core thay vì trong `vn_equity` pack như
brainstorm dự kiến: nó giải thích chính các dòng giá trị mà core render, và nói
cùng một luật ở hai chỗ là cách để hai chỗ lệch nhau.

**Đo lại** — 5 lượt, cùng câu hỏi, ngày nghỉ lễ 1/9/2026:

| | Trước | Sau |
|---|---|---|
| Gán "hôm nay" cho phiên khác | 3/5 | **0/5** |

Cả 5 lượt đều nêu rõ hôm nay nghỉ lễ và gắn số liệu vào đúng phiên 28/8.
`pytest -q`: 1053 passed. `test_agent_loop.py` phải nới ngưỡng tầng
`system_dynamic` từ <20 lên <40 token vì tầng này nay mang thêm hai dòng giá trị
— nới đúng bằng nội dung mới, không phải để giấu lỗi.

**Điều đo được mà brainstorm chưa lường**

Hai trong năm lượt trả lời với **0 lần gọi tool**: model tin thẳng trạng thái
lịch trong prompt. Rẻ và đúng trong trường hợp này, nhưng nó cũng nói rõ cái
giá: khi bảng lịch sai, model sẽ nói sai mà không kiểm chứng gì. Đây chính là
rủi ro "bảng mục" đã nêu, nay có bằng chứng hành vi. `COVERED_YEARS` là thứ giữ
cho rủi ro đó hữu hạn; bảng phải được gia hạn cho 2027 trước tháng 1/2027.

**Chưa sửa**

Lỗi dấu +/- khi chép số từ bảng giá vẫn nằm ngoài phạm vi. Sau fix cả ba lượt
có số đều ghi +0,03%, nhưng đó không phải kết quả của thay đổi này và không
được coi là bằng chứng đã sửa.

## Câu hỏi chưa giải quyết

- Ai gia hạn bảng nghỉ lễ cho 2027, và có nên có test tự fail khi
  `COVERED_YEARS` không còn chứa năm hiện tại không?
- Có mở R1 eval để đo lỗi numeric provenance trước khi tính tới C không?
