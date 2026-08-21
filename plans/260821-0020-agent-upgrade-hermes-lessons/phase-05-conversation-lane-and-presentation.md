---
phase: 5
title: "Lane hội thoại và trình bày"
status: pending
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

- [ ] "Hey bro" → trả lời hội thoại, 0 tool call
- [ ] "Tình hình chứng khoán VN hôm nay" → số + citation chip + 3 follow-up + footer nguồn
- [ ] "Về STB thì sao" → số từ store + ≥1 widget + tin từ web
- [ ] "Có nên mua STB" → Gate còn hiệu lực
- [ ] Timeline hiện query nguyên văn, số nguồn, domain; gập được
- [ ] Tối đa 3 widget mỗi câu trả lời
- [ ] `quarterly_financials` render được 8 quý MSN (dữ liệu đã có trong store)
- [ ] Citation chip trỏ đúng nguồn; source id không tồn tại thì **không** chặn câu trả lời
- [ ] Đổi view không mất câu đang gõ
- [ ] `pnpm type-check lint test build`, `pnpm test`, `pnpm test:e2e`, `make test` xanh
- [ ] Eval Report cho phần chạm Contract

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
