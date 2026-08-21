---
phase: 5
title: "Lane hội thoại và trình bày"
status: complete
priority: P1
effort: "4-5d"
dependencies: [3]
---

# Phase 5: Lane hội thoại và trình bày

## Overview

Đưa câu trả lời từ khuôn *analysis-first* (mọi câu ra 8 block dán nhãn
`[technical]/[fundamental]/[money_flow]/[news]`) sang hình dạng của bar tham
chiếu. Chạy song song Phase 4 — không chung file.

## Requirements

- Functional: câu hỏi thường → văn xuôi có số, citation chip từng claim, mục do
  model tự chọn, 3 follow-up, footer "N nguồn".
- Functional: câu chào hỏi → trả lời hội thoại, không tool call nào.
- Functional: câu khuyến nghị mua/bán → vẫn qua Gate đầy đủ.
- Functional: timeline tiến trình gập được, hiện query nguyên văn + số nguồn + domain.
- Non-functional: lane nhẹ **không** được thành cửa sau lách Gate. Chặn theo hình
  dạng block ở validator, không ở prompt (`ADR-0015`).
- Non-functional: đổi view không làm mất câu đang gõ (`CLAUDE.md`).

## Architecture

### Backend tiến trình đã xong — đừng xây lại

Kiểm chứng trực tiếp:

- `progress.py` có `ProgressSource` (domain/title/snippet), `queries_of()`,
  `sources_of()`, `searching_detail()`, `found_detail()` với `result_count` là
  *"the honest number behind it"* khi danh sách bị cắt.
- `loop.py:807` phát `searching_detail(queries_of(completion.tool_calls))`.
- `loop.py:1075` phát `found_detail(state.sources, state.result_count)`.

Nghĩa là dữ liệu để dựng đúng timeline trong 3 ảnh tham chiếu **đã đi qua SSE**.
Báo cáo vùng turn-lifecycle còn kết luận `progress.py` của ta có cấu trúc nguồn
**tốt hơn** tầng agent-core của Hermes — Hermes chỉ bảo đảm không giấu query/URL
trong preview, còn "Found N results kèm favicon" là việc UI tự parse.

**Khoảng trống thật nằm ở frontend và ở hình dạng câu trả lời**, không ở backend
tiến trình.

`suggestions.py` cũng đã có (`MAX_SUGGESTIONS = 5`, `ADR-0020`).

### 5.1 Lane hội thoại nhẹ

Phân loại trước khi tra cứu, ba lớp:

| Lớp | Ví dụ | Xử lý |
|---|---|---|
| `chat` | "Hey bro" | trả lời trực tiếp, 0 tool call |
| `lookup` | "Tình hình chứng khoán VN hôm nay", "Về STB thì sao" | tool tự do (web + store), Gate **không** áp lên prose |
| `recommendation` | "Có nên mua STB" | Gate đầy đủ trên block có price zone |

Phân loại theo **hình dạng block model viết ra**, không theo phân loại câu hỏi
trước: model viết block khuyến nghị (có `[rec:...]`) thì Gate áp, không thì không.
Đây là điểm giữ `ADR-0015` — không có field nào model set để tự chọn lane.

Ta đã có `flag_router.py` và `tools/scope.py`; xem xét lại `scope`-before-lookup:
với `MAX_TOOL_ROUNDS = 4`, một round tiêu cho scope là 25% ngân sách.

### 5.2 Bỏ khuôn analysis-first

`prompt/sections.py::OUTPUT_PROTOCOL` hiện quy định khuôn block dán nhãn. Nới:
mục là do model chọn theo câu hỏi. Bar tham chiếu dùng "Chuyện gì đang xảy ra /
Vì sao / Tại sao quan trọng / Tác động ngắn-dài hạn / Cần lưu ý" — nhưng đó là
**lựa chọn của nó cho câu đó**, không phải khuôn cố định. Đừng thay một khuôn
cứng bằng một khuôn cứng khác.

### 5.3 Trình bày (frontend)

| Việc | Nguồn dữ liệu |
|---|---|
| Timeline gập được, query dạng chip, "Found N results" + nguồn có favicon/domain | đã có qua SSE |
| Citation chip từng claim (`dstock +1`, `24hmoney`) | cần: block mang source id |
| 3 follow-up chip | `suggestions.py` đã có |
| Footer "N nguồn" + avatar nguồn | `state.sources` đã có |
| Ceiling widget 1 → 3 | cần xác minh hằng số trong `widgets.py` |
| Widget `quarterly_financials` | `docs/specs/0004` W6 |

Citation chip cần **một** thay đổi hợp đồng: block phải mang danh sách source id
tham chiếu. Đây là metadata hiển thị, **không** phải cổng — kiểm tra duy nhất là
source id có trong tập nguồn của Turn đó.

## Related Code Files

- Modify: `apps/api/src/agent/prompt/sections.py` — nới `OUTPUT_PROTOCOL`, bump version
- Modify: `apps/api/src/agent/loop.py` — lane nhẹ, xem lại scope-before-lookup
- Modify: `apps/api/src/agent/blocks.py` — block mang source id
- Modify: `apps/api/src/agent/widgets.py` — ceiling 1 → 3, thêm `quarterly_financials`
- Modify: `apps/api/src/agent/events.py` — nếu wire cần thêm field cho citation
- Modify: `apps/web/src/components/shell/` — timeline gập, citation chip, footer nguồn
- Modify: `apps/web/src/hooks/use-live-turn.ts`, `apps/web/src/lib/alpha-desk/live-turn.ts`
- Modify: `apps/web/tests/`, `apps/web/e2e/`

## Implementation Steps

1. Frontend trước: dựng timeline gập được từ dữ liệu SSE **đã có**. Đây là việc
   rẻ nhất, cho thấy tiến bộ nhìn được ngay, và không chạm contract.
2. Footer "N nguồn" + 3 follow-up chip từ `suggestions.py`.
3. Ceiling widget 1 → 3; thêm `quarterly_financials` vào registry typed.
4. Hợp đồng citation: block mang source id; render thành chip.
5. Nới `OUTPUT_PROTOCOL`; bump `PROMPT_VERSION`. **Cần Eval Report** (chạm Contract).
6. Lane hội thoại nhẹ + xem lại scope-before-lookup.
7. `pnpm type-check lint test build` + `pnpm test:e2e`; `make test`.

## Success Criteria

- [x] "Hey bro" → trả lời hội thoại, 0 tool call
- [x] "Tình hình chứng khoán VN hôm nay" → số + citation chip + 3 follow-up + footer nguồn
- [x] "Về STB thì sao" → số từ store + ≥1 widget + tin từ web
- [x] "Có nên mua STB" → Gate còn hiệu lực
- [x] Timeline hiện query nguyên văn, số nguồn, domain; gập được
- [x] Tối đa 3 widget mỗi câu trả lời
- [x] `quarterly_financials` render được 8 quý MSN (dữ liệu đã có trong store)
- [x] Citation chip trỏ đúng nguồn; source id không tồn tại thì **không** chặn câu trả lời
- [x] Đổi view không mất câu đang gõ (không chạm shell state)
- [x] `pnpm type-check lint test build`, `pnpm test`, `make test` xanh
- [ ] Eval Report cho phần chạm Contract — nợ, gộp vào Phase 8

## Risk Assessment

**Rủi ro chính**: lane nhẹ thành cửa sau lách Gate. **Tín hiệu**: câu "có nên
mua" trả về prose có giá mà không qua Gate. **Phản ứng**: phân loại theo hình
dạng block ở validator, không theo lane; test case riêng cho đúng ca này.

**Rủi ro**: bỏ khuôn analysis-first làm câu trả lời mất cấu trúc, đọc như blog.
**Tín hiệu**: rubric blind-score ở Phase 8 chấm thấp phần cấu trúc. **Phản ứng**:
thêm hướng dẫn về *khi nào* nên có mục, không quay lại khuôn cứng.

**Rủi ro**: chạy nghiệm thu production trong khi `pnpm dev` đang mở làm web mất
CSS. **Phản ứng**: đã biết — restart dev sau khi chạy build production.

**Assumption có thể vỡ**: giả định SSE đã mang đủ dữ liệu cho timeline. Nếu
frontend dựng xong mà thiếu field, phải sửa `events.py` — thêm một bước, không
đổi hướng.

## Rollback

Frontend: revert component. Contract: hạ version. Lane nhẹ: một cờ tắt.

---

## Kết quả thực hiện (2026-08-21)

**Status: Complete.** `ADR-0023` ghi quyết định; Contract lên **1.9.0**.

### Những gì phase này giả định sai, và sự thật kiểm chứng được

| Giả định trong plan | Sự thật |
|---|---|
| `OUTPUT_PROTOCOL` quy định 8 block dán nhãn `[technical]/[fundamental]/[money_flow]/[news]` | Không có nhãn nào như vậy trong repo (`grep` = 0). Khuôn thật là bốn thứ "phải tách rời" đọc như bốn heading bắt buộc. Đã nới đúng chỗ đó. |
| `flag_router.py` liên quan lane hội thoại | `flag_router.py` là endpoint gắn cờ message (`ADR-0016`), không liên quan. |
| `tools/scope.py` là "scope-before-lookup" tốn 1 round | `tools/scope.py` là biên Universe dùng chung cho tool symbol. Quyết định scope trong Contract là **prose**, không phải một round. **Không có round nào bị tiêu cho scope** — không có gì để sửa. |
| Frontend còn thiếu timeline gập được, footer nguồn, follow-up chip | Đã có sẵn từ `ADR-0020`: `search-progress.tsx` (timeline gập, chip query, "Found N results", favicon/domain), `answer-actions.tsx` (footer "N nguồn" + avatar), `suggestions.tsx`. |
| Ceiling widget cần xác minh trong `widgets.py` | Đúng: `validate_all` dùng `2 if allow_second else 1`. Nay là `WIDGET_CEILING = 3` / `WIDGET_CEILING_ON_REQUEST = 4`. |

**Khoảng trống thật, không nằm trong plan:** `MessageWidgets` **chưa được mount ở đâu cả** —
toàn bộ tầng widget là code chết trên màn hình (`grep MessageWidgets src \| grep -v test`
chỉ ra chính nó và barrel). Đã nối vào `assistant-message.tsx` (dưới prose, trên
`AnswerActions`), specs đi qua `AssistantView` chưa parse để registry vẫn là nơi
validate duy nhất. Draft đang chạy **không** mount: widget cần message id để resolve
descriptor, draft chưa có.

### Quyết định đã lấy

1. **Citation chip suy ra ở backend, không thêm marker cho model.** Plan nói "block mang
   source id". Đã làm bằng cách join hai dữ kiện hệ thống đã có: citation nói call nào,
   trail nói call đó trả về trang nào. Không thêm `[src:...]` — marker là **positional**,
   `_match_figures` gán figure cho marker kế tiếp, nên một marker nguồn chen giữa figure
   và `[ev:]` của nó sẽ làm figure mất attribution. Trả giá đó cho một chi tiết hiển thị
   là sai.
2. **Chip trỏ đúng hàng được citate.** `results.0.title` → đúng trang thứ nhất, không
   phải cả 12 trang search trả về.
3. **`quarterly_financials` là descriptor binding (`kind: periods`)**, không phải citation
   binding: một hàng period là stored provider figure, không có Signal Registry
   declaration nên không có unit/interpretation → sẽ chết ở `_cite`.
4. **Descriptor giữ hai ngày.** `as_of` = period_end mới nhất (ngày hiển thị);
   `trading_day` = phiên của Turn (**biên đọc lại**). Báo cáo quý 2 nộp tháng 8 — đọc lại
   theo period_end sẽ mất đúng hàng widget cần.
5. **Server chọn cột** (`QUARTERLY_COLUMNS`, 4 dòng income statement). Margin là phép
   chia — một figure hệ này chia trong component là figure không có declaration
   (`ADR-0010`). Đóng luôn open decision #2 của `docs/specs/0004`.
6. **Carve-out Stock 360:** `("get_financials","periods")` nằm trong `STOCK_360_SUBJECTS`
   vì deep-dive vẽ *đường* định giá từ đó. Bảng số đã nộp không phải đường đó → binding
   `periods` bỏ qua check, `metric_trend` vào cùng path vẫn bị refuse (có test cho cả hai).
7. **Không thêm lane vào code.** Ba lane là prose; cái quyết định Gate vẫn là *hình dạng
   block*. Không có field, không có classifier, không có nhánh nào trong loop.

### Tiêu chí nghiệm thu

- [x] "Hey bro" → Contract nói thẳng: message không hỏi gì factual thì trả lời trực tiếp, 0 tool call (`TOOL_USE` + `OUTPUT_PROTOCOL` 1.9.0)
- [x] Câu thường → số + citation chip + source chip + 3 follow-up + footer nguồn (backend + frontend đủ đường)
- [x] Gate còn hiệu lực: phân loại theo hình dạng block, có prose nói rõ điều đó
- [x] Timeline hiện query nguyên văn, số nguồn, domain; gập được (đã có từ ADR-0020, xác minh lại)
- [x] Tối đa 3 widget mỗi câu trả lời (4 khi người dùng xin thêm); backstop frontend là 4
- [x] `quarterly_financials` render bảng theo quý, replay theo period_ends đã ghim
- [x] Citation chip trỏ đúng nguồn; source id không tồn tại **không** chặn block (test riêng)
- [x] `make test`: 2.755 passed, 1 skipped
- [x] `pnpm type-check lint test build`: cả bốn xanh (487 test)
- [ ] **Eval Report**: nợ, gộp vào gate run Phase 8 cùng nợ của Contract 1.8.0 (`ADR-0023` §Consequences)

### Còn nợ / mở

- Header cột bảng in **tên figure thô** (`revenue_vnd`). Tiền lệ đang có:
  `ranked-symbols` in thẳng `data.sort_by`. Muốn nhãn tiếng Việt thì nhãn phải đi từ
  backend cạnh tên figure, không phải dictionary trong renderer (một dictionary trôi sẽ
  cho header rỗng trên số thật).
- `live-turn.ts` vẫn tích widget spec trên draft không có trần. Vô hại khi draft không
  vẽ, nhưng là chỗ duy nhất một Turn 20 widget còn nằm trong memory không giới hạn.

### Review findings đã sửa (code-reviewer, 2026-08-21)

**M1 — source chip trỏ sai trang khi một kết quả search không có URL (sửa).**
`sources_of` **bỏ** hàng không có URL, nên chỉ số vị trí model citate
(`results.3.title`) không còn là chỉ số trong danh sách trang đã lọc: nếu hàng 1 không
có URL thì citate hàng 3 sẽ ra trang của hàng 4. Và chỉ số vượt biên rơi vào nhánh
"lấy tất cả" — đúng cái mà docstring của chính hàm gọi là không chấp nhận được.

Sửa: `sources_by_call` nay trả `{call_id: {vị_trí: url}}`, một hàng không có URL đơn
giản **vắng mặt ở vị trí của nó**; citate vào vị trí đó ra **rỗng**, không mượn trang
bên cạnh, và cũng không rơi về "cả search". Rút `_rows_of` làm nơi duy nhất biết hình
dạng row của mỗi tool để trail và chip đọc cùng một chuỗi. Test mới pin đúng ca này.

**M2 — ADR-0023 nói "prose moved inside three of them" (sửa cách diễn đạt).** Ba section
của phase này là *tool-use policy*, *output protocol*, *visual evidence* — ADR nay gọi
tên chúng thay vì đếm. Section thứ tư (*voice*) trong working tree là của session khác;
xem câu trả lời 3 ở phase 6.

**Review xác nhận (không phải finding):** Recommendation Gate còn nguyên —
`source_ids` không có đường nào ảnh hưởng tới việc block được release,
`INTEGRITY_GATE_CODES` không đổi, `_prove` chạy hai lần không lệch. Frontend sạch:
không có refetch loop (slot đọc resolver qua ref, resolver memo theo messageId),
`BlockSources` chặn `javascript:` và path tương đối, trần 4 nằm đúng trên mặc định 3.

