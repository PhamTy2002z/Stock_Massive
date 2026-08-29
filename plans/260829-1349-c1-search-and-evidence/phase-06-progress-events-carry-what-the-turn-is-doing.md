---
phase: 6
title: "Rail hiện số nguồn và domain đã có trên dây"
status: pending
priority: P2
effort: "3h"
dependencies: [3]
---

# Phase 6: Rail hiện số nguồn và domain đã có trên dây

## Overview

**Phase này đã co từ 8h xuống 3h và từ api+web xuống web-only.** Bản đầu định
dựng `agent/progress.py` + hai `EventType` mới + khoá snapshot mới. Red-team
chứng minh dữ liệu đó **đã ở trên dây từ trước**, và bản đầu đo sai.

## Tiền đề bản đầu đo sai

Bản đầu kết luận *"rail không hiện query"* từ `grep "query" reasoning-timeline.tsx`
→ chỉ ra một comment ở `:48`. Grep trượt vì dữ liệu **không đi qua biến tên
`query`** — nó đi qua trường `summary`:

| Mắt xích | Ở đâu | Trạng thái |
|---|---|---|
| `summarise_call` dựng `"{display_name}: {query\|url}"` | `messages.py:225-268`, đọc `summary_detail_arg` | Có |
| `web_search` khai `summary_detail_arg="query"`; `fetch_url` khai `"url"` | `tools/web.py:330`, `:362` | Có |
| Publish lúc call **bắt đầu** (RUNNING) | `loop.py:1516-1520`, `_publish_call:1714-1716` | Có |
| Rail render `{call.summary}` nguyên văn | `reasoning-timeline.tsx:276`, `:431` | **Đang hiện** |
| Payload cho phép `results`, `result_count` | `events.py:120-129` (`TOOL_CALL_FIELDS`) | Có |
| Item kết quả mang `url` + `source` | `messages.py:513-520` (`_display_item`) | Có |

Nên **query nguyên văn đã hiện trên rail hôm nay**, và số nguồn + domain đã có
trong payload `tool.call` — chỉ là chưa được vẽ.

Dựng thêm một cặp event cho cùng dữ liệu sẽ đẻ ra hai row một call, làm snapshot
lệch live, và vi phạm chính chỉ dẫn bản đầu tự đặt: *"chọn chỗ đã biết call
bắt đầu/kết thúc, đừng thêm hook thứ hai"*.

## Requirements

- Functional: dưới mỗi tool call đã xong, rail hiện **số nguồn** và **domain**
  từ `results` của payload `tool.call` đang có.
- Non-functional: **không** thêm `EventType`. Không tạo `agent/progress.py`.
  Không đụng `snapshot_from_draft`.
- Non-functional: không đổi luật gập/mở, không đổi cách gộp theo round, không
  đụng `SignalDeskToggle`.
- Non-functional: một call → **một row**.

## Architecture

Việc duy nhất còn lại là ở web, và nó nhỏ: đọc `results[].source` từ payload
`tool.call` đã nhận, gộp thành danh sách domain khác nhau, vẽ một dòng phụ.

`EVENT_TYPES` phía web là allowlist additive (`use-live-turn.ts:41-50`) nên
không consumer nào exhaustive-match — nhưng đó là lý do **có thể** thêm event,
không phải lý do **nên** thêm.

**Cửa mở lại có điều kiện.** Nếu sau khi làm phần web vẫn chứng minh được một
dữ kiện cần thiết không đi qua `tool.call` được — ví dụ tiến trình *bên trong*
một call dài — thì mở lại phần backend như một plan rời, kèm bằng chứng dữ kiện
đó thiếu thật. Không mở trước.

## Related Code Files

- Modify: `apps/web/src/components/alpha/message/reasoning-timeline.tsx` — dòng phụ dưới mỗi call
- Modify: `apps/web/src/lib/alpha-desk/types.ts` — **chỉ nếu** `ToolResult` thiếu trường cần; kiểm trước, đừng thêm mù
- Modify: `apps/web/src/components/alpha/message/reasoning-timeline.test.tsx`

Không còn file api nào trong phase này.

## Implementation Steps

1. Đọc payload `tool.call` thật trên một Turn đang chạy, xác nhận `results[].source`
   và `result_count` tới được web. Nếu tới rồi thì `types.ts` không cần đụng.
2. Vẽ dòng phụ: số nguồn + danh sách domain khác nhau. Domain lấy từ
   `results[].source` — trường này **đã là hostname** (`web.py:503`), không cần
   parse lại ở web.
3. Test: một call → một row. Không sinh row thứ hai.
4. Test: luật gập/mở và gộp theo round không đổi.
5. Nội dung do model và trang ngoài sinh → đi qua đúng đường thoát của
   `SourceList` (`source-list.tsx` in plain text, không `dangerouslySetInnerHTML`).
   Không ngoại lệ cho "chỉ là một dòng phụ".

## Success Criteria

- [ ] Rail hiện số nguồn và domain khác nhau dưới mỗi `web_search` đã xong
- [ ] **Không** `EventType` mới; `events.py` không đổi
- [ ] **Không** tạo `agent/progress.py`
- [ ] Một call → đúng một row (test)
- [ ] Luật gập/mở và gộp theo round không đổi — test cũ xanh nguyên
- [ ] Domain hiện ra không parse lại ở web — dùng `results[].source` backend đã dựng
- [ ] Dòng phụ in plain text, không đường nào cho markup của trang ngoài
- [ ] Năm cổng xanh

## Risk Assessment

**Rủi ro: `results[].source` không tới web như mong đợi.**
Tín hiệu: bước 1 cho thấy trường thiếu.
Phản ứng: thêm nó vào `TOOL_CALL_FIELDS` (`events.py:120-129`) — một dòng
allowlist, **không** phải một event mới. Nếu đến mức này thì phase quay lại có
một file api, và bảng amendment C1 trong CLAUDE.md phải ghi thêm dòng đó.

**Rủi ro: phase này bị coi là "đã xong sẵn" và bỏ qua.**
Nó không xong: query hiện rồi, nhưng **số nguồn và domain thì chưa được vẽ**.
Đó là phần người đọc cần để biết câu trả lời dựa trên mấy nguồn.

**Rủi ro: trượt lịch chặn phase 08.**
Không chặn. Phase này không đổi số nào của bốn grader; phase 08 chạy được thiếu
nó và ghi rõ trong report.
