---
phase: 4
title: "Evidence frames — số web có chứng"
status: completed
priority: P2
effort: "10h"
dependencies: [2]
---

# Phase 4: Evidence frames — số web có chứng

## Overview
Câu hỏi ngoài store (vĩ mô, đối thủ chưa niêm yết, số trong tin) vẫn phải lên
board có bằng chứng. `frame_from_evidence` là **chỗ duy nhất** model chép số —
và mỗi số chỉ được nhận khi server tìm thấy nó **trong text trang đã fetch
cùng Turn**. Frame mang `source="web"` và được vẽ khác màu.

## Requirements
- Functional:
  - Tool `frame_from_evidence(url, rows: [{label, value, unit?}] ≤ 20,
    caption ≤ 140)` → frame `table` cột `label, value` + provenance
    `{source: "web", url, fetched_at, matched: n, refused: n}`.
  - `url` phải là URL một `fetch_url` **thành công trong cùng Turn** (đọc
    `agent_tool_call.result` của Turn qua `ToolContext.turn_id`); không →
    `evidence_page_not_fetched`.
  - Mỗi `value` phải xuất hiện trong text trang sau chuẩn hoá số: bỏ dấu phân
    cách nghìn `.`/`,`/khoảng trắng, đổi `,` thập phân, chấp nhận `%`, `tỷ`,
    `triệu`, `nghìn tỷ` với hệ số; không thấy → hàng bị bỏ với
    `evidence_number_not_on_page`; ≥ 1 hàng bị bỏ → `health="degraded"`.
  - Frame lưu qua `store_frame(kind="evidence_frame")`; `as_of = fetched_at`
    (ngày).
  - `compute` **được** nhận evidence frame làm input; kết quả kế thừa
    `source="derived"` + `method_notes` ghi có input web.
- Non-functional: `reads_external=False` (không fetch lại — chỉ đọc trace);
  trả lời < 300 ms.

## Architecture
```
frame_from_evidence ── trace lookup (agent_tool_call WHERE turn_id, tool_name='fetch_url', url) ── page text
                    ── number_match(value, page_text) per row ── Frame(table) ── store_frame
```
`fetch_url` đã lưu kết quả đầy đủ trong Tool Call Trace (bất biến "đúng thứ
model đã thấy", `MAX_PAGE_TEXT_CHARS = 20_000`), nên không cần lưu thêm trang.

## Related Code Files
- Create: `apps/api/src/agent/tools/evidence.py` (tool + `number_match`)
- Create: `apps/api/src/agent/evidence/numbers.py` (chuẩn hoá số VN/EN — thuần
  hàm, test bảng)
- Modify: `apps/api/src/agent/toolsets.py` (`web` += `frame_from_evidence`;
  `CORE_TOOLSETS` không đổi)
- Modify: `apps/api/src/studies/frames_buffer.py` (kind `evidence_frame`)
- Tests: `apps/api/tests/test_evidence_numbers.py` (bảng ≥ 40 case: `1.234,5`,
  `1,234.5`, `12,5%`, `3,2 nghìn tỷ`, số âm, năm không phải giá trị),
  `tests/test_agent_evidence_tool.py` (page not fetched, partial refuse,
  frames absent)

## Implementation Steps
1. `numbers.py`: `normalise(text) → set[Decimal]` và `contains(page, value,
   unit) → bool`; xử lý hệ số đơn vị; test bảng.
2. Trace lookup: hàm đọc `agent_tool_call` theo `(turn_id, tool_name, url)`
   — dùng shape đã có, không query mới ngoài một select.
3. `tools/evidence.py`: schema, kiểm URL, match từng hàng, dựng Frame,
   provenance, summary (`matched/refused`).
4. `toolsets.py` + test đếm.
5. Test end-to-end với `agent_tool_world.py` (stub fetch): trang stub chứa
   `12,5%` → nhận; `13%` → bị bỏ có tên.

## Success Criteria
- [x] 100% hàng nhận được đều tìm thấy trên trang; 0 hàng nhận khi không có.
      **Đo:** bảng 58 case trong `test_evidence_numbers.py` — 21 case tách dấu
      thập phân (`1.234,5` ↔ `1,234.5`), 11 case đếm chữ số nghĩa, 8 case hệ số
      đơn vị, 18 case verdict. Ba verdict, không hai: `NOT_ON_PAGE` và
      `AMBIGUOUS` là hai sự thật khác nhau và dẫn tới hai refusal khác nhau.
- [x] URL không fetch trong Turn → lỗi có tên, không frame.
      **Đo:** bốn đường vào cùng một `evidence_page_not_fetched` — chưa từng
      fetch · fetch bởi Turn khác · fetch `status != ok` · fetch trả
      `reason: web_unavailable`. Cả bốn đều khẳng định **0 hàng
      `agent_artifact`** được ghi, không chỉ khẳng định mã lỗi.
- [x] Frame web hiện badge nguồn khác ở FE (phase 06 dùng `source="web"`).
      **Backend xong:** `provenance.source == "web"` và
      `study_name == "evidence_frame"` trên hàng đã ghi. Việc vẽ badge là phase
      06 — `apps/web/**` nằm ngoài bề mặt phase này.
- [x] Frames không vào transcript.
      **Đo:** `987654321` (giá trị duy nhất của frame) không có trong message
      `build_messages` dựng; `frameId` thì có.

## Evidence — thi công 2026-08-30

**`agent_tool_call` không có cột `turn_id`, nên "cùng Turn" là một join.** Bảng
neo vào `request_message_id` (bất biến "một Tool Call Trace neo vào message của
người dùng"), nên tra ngược là `agent_turn.id = :turn_id` →
`agent_turn.request_message_id` → `agent_tool_call`. Một select, không query mới
nào ngoài nó, đúng như bước 2 của plan yêu cầu.

**Và một Turn retry không nới rộng "cùng Turn".** `persistence._create_turn`
chèn **một message người dùng mới** cho mỗi Turn, kể cả Turn retry
(`retry_of_turn_id` chỉ là con trỏ), nên `request_message_id` là một-một với
Turn và join trên nó đúng bằng các call của **đúng** Turn đó — không phải của
lượt trước nó.

**Trace giữ kết quả dưới dạng chuỗi JSON, không phải mapping.** `loop._trace_
writer` ghi `{"text": <chuỗi model đã đọc>, "chars": …}` — đó **là** bất biến
của trace ("đúng thứ model đã thấy"). Nên `_payload` parse ngược chuỗi đó chứ
không đọc một trường. Fixture của test ghi hàng y hệt cách loop ghi; một fixture
lưu mapping sẽ test một đường đọc không tồn tại.

**URL so bằng `messages.dedup_key`.** Cùng phép chuẩn hoá rail nguồn đang dùng
(bỏ fragment · `www.` · trailing slash · tracking param · scheme), nên một link
model gõ lại thiếu `www.` vẫn tìm ra trang nó đã đọc. **Chỉ để so trùng** —
`frame.query.url` và `answer.url` là URL fetch trả về, vì bỏ một tham số site
nào đó định tuyến theo sẽ biến link sống thành 404.

**Luật khớp số, và nó là luật của C1 học lại một lần nữa.** Không suy diễn gì:
một giá trị khớp khi nó **in trên trang** — hoặc như trang viết, hoặc như từ
chỉ hệ số bên cạnh nhân nó lên. Ba nhánh:

1. khớp **giá trị đã nhân hệ số** → nhận ngay, vì từ chỉ hệ số phải đứng ngay
   đó thì nhánh này mới với tới được;
2. khớp giá trị **như viết** với **≥ 3 chữ số nghĩa** → nhận;
3. khớp giá trị như viết với < 3 chữ số nghĩa → chỉ nhận khi **đơn vị của chính
   hàng đó** in ngay sau con số (cửa sổ 28 ký tự).

Không nhánh nào khớp mà số có mặt → `evidence_number_ambiguous`; không có mặt →
`evidence_number_not_on_page`. `5` có trên mọi trang từng xuất bản, nên nhận nó
không đơn vị là nhận một trùng hợp làm trích dẫn.

**Chữ số nghĩa đếm thứ trang chọn in.** `1200` → 2 · `100` → 1 · `12,5` → 3 ·
`12,50` → **4**, vì số 0 cuối sau dấu thập phân là do người viết chọn in.

**Dấu thập phân quyết theo từng token, không theo trang.** Có cả hai dấu → dấu
**đứng sau** là dấu thập phân (đọc đúng cả `1.234,5` lẫn `1,234.5`). Chỉ một
dấu → nó nhóm nghìn đúng khi có **đúng ba** chữ số theo sau, nên `12,5` là mười
hai rưỡi và `1,500` là một nghìn rưỡi.

**Từ chỉ hệ số cần biên từ.** `12 tin bài` không được đọc thành 12 tỉ: khớp tiền
tố mà không kiểm ký tự kế tiếp sẽ làm đúng việc đó.

**`as_of` là ngày, không phải phút.** Một con số công bố trên trang là sự thật
của *ngày* đó, và đóng băng theo phút sẽ khiến hai frame dựng từ một trang trong
một Turn khai hai vintage khác nhau.

**Frame giữ đúng hai cột `label, value` như plan khai.** `unit` của frame chỉ
được đặt khi **mọi** hàng còn lại đồng ý một đơn vị; hàng lẫn đơn vị → `None`,
vì một cột có phần trăm cạnh nghìn tỉ không có đơn vị chung và bịa một cái cho
trục là tệ hơn bỏ trống.

**`compute` nhận evidence frame, và nói ra là nó đã nhận.**
`frames_io.derived_provenance` thêm note *"Có số lấy từ trang đã đọc, không phải
số của hệ thống"* khi bất kỳ input nào có `source == "web"` — một con số suy ra
không khá hơn trang nó dựa vào.

**`frame_from_evidence` nằm trong bundle `web`, `access=STORE`.** Nó *về* web
nhưng **không đọc** web: nó đọc Tool Call Trace. Nên `reads_external=False` và
`content_trust=TRUSTED_STRUCTURED` — kết quả trả về là đếm và tên hàng bị bỏ,
không một chữ nào của trang.

## Risk Assessment
- Số tròn nhỏ (`5`, `10`) khớp ngẫu nhiên trên trang → yêu cầu khớp **kèm
  đơn vị hoặc ≥ 3 chữ số nghĩa**; số nhỏ không đơn vị → từ chối
  `evidence_number_ambiguous`. Bài học C1: bag-of-numbers không phân biệt được
  — nên ở đây chỉ nhận khi **đúng chuỗi**, không suy diễn.
- Trang đã prune trong context nhưng trace còn đủ (C2 giữ full result ở
  trace) — phụ thuộc bất biến C2, ghi rõ.
