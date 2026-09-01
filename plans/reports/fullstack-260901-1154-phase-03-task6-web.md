# Task 6 — minimal web projection of the typed contract

Plan: `plans/260901-1154-phase-03-durable-loop-lane/plan.md` (Thiết kế §6).
Branch `feat/phase-03-durable-loop-lane`, code commit `b445427`.

## Kết quả

Client nhận đủ contract mới, chat UI hiện có xanh, và một cửa nhỏ phía backend
được mở để stream và transcript nói cùng một chuyện.

### 1. Backend — một thay đổi duy nhất

- `apps/api/src/agent/events.py:139-171` — `TOOL_CALL_FIELDS` thêm `"error"`.
  `TurnToolCall.as_wire` (`messages.py:479-504`) vốn đã mang code này, nên đây
  chỉ là mở đúng một khoá trên allowlist; payload arguments/result vẫn bị chặn.
- Test pin allowlist: `tests/test_agent_turn_events.py:109-152` (set khoá) +
  test mới `test_a_refused_call_carries_the_code_that_says_why_it_never_ran`
  (`:155-171`) — `denied` mang `permission_denied`, call `ok` mang `None`.
- **Lệch phạm vi đã ghi rõ:** ba câu comment ở `messages.py:64-69`,
  `loop.py:868-871` và `tests/test_agent_loop.py:988-992` khẳng định
  "`TOOL_CALL_FIELDS` carries no `error`". Sau thay đổi này chúng nói sai sự
  thật, nên đã sửa **chỉ phần prose**, không đổi một dòng hành vi hay assert
  nào. Không file backend nào khác bị chạm.

### 2. Contract trên client

- `types.ts` — `TurnEventType` += `part.progress` | `part.question`
  (`:15-33`); `ToolCall.status` = `pending|running|ok|error|denied` (`:56-71`);
  hai predicate `toolCallWaiting` / `toolCallFailed` (`:110-133`) để 10 call
  site không tự so sánh chuỗi; `ProgressKind`, `ProgressPart`, `QuestionState`,
  `QuestionOption`, `QuestionPart`, `ResolvedQuestion`; `SnapshotData` +=
  `progress?` / `question?`; `AssistantContent` += `progress` / `question`.
  `ProgressPart.payload` để `Record<string, unknown>` — allowlist phía backend
  đã quyết định nội dung, khai tên field ở đây là claim một shape client chưa
  kiểm.
- `read-content.ts` — `readProgressPart(s)` (drop kind lạ, sort theo `seq`),
  `readQuestion(value, fallbackState)` (từ chối card < 2 option), status call
  đọc theo danh sách 5 giá trị nên `pending`/`denied` giữ nguyên thay vì rơi về
  fallback.
- `use-live-turn.ts:41-51` — `EVENT_TYPES` += hai type mới. Đây là điểm chết
  người: named event không bao giờ bắn `message` handler.

### 3. Reducer

`live-turn.ts` — `LiveTurn` += `progress: ProgressPart[]`, `question`.
`part.progress` append + sort theo `seq` (`:291-299`); `part.question` set một
card (`:301-308`); snapshot thay cả mảng progress, còn `question` **không** bị
xoá khi snapshot trả null — snapshot dựng từ draft luôn null (đúng thiết kế
`events.snapshot_from_draft:596-611`), xoá theo đó thì đúng người đang xem card
lại mất card.

### 4. Render tối thiểu

- `pending` → hình dạng đang chạy, `denied` → hình dạng lỗi, qua hai predicate:
  `reasoning-timeline.tsx` (single row, group row, đếm settled/failed) và
  `tool-call-list.tsx`. `copy.ts` thêm `TOOL_CALL_COPY.pending/denied` và
  `REFUSED_CALL_LABELS.permission_denied`.
- Progress **không** render: state + type + test, timeline ba màn là P7.
- `question-card.tsx` (mới, 131 dòng) — prompt, option button single-select,
  skip link, mờ + inert khi state ≠ `pending`, đánh dấu option đã chọn, một
  dòng cho `skipped`/`superseded`. Dùng primitive sẵn có, không design mới.
  Render từ `AssistantMessage` (message content) *và* `DraftMessage` (live
  part), cùng vị trí nên lúc swap không nhảy.
- API: `api.ts` `answerQuestion` / `skipQuestion`; hook `useResolveQuestion`
  (`use-threads.ts:312-355`) invalidate thread query như pattern hiện có, không
  optimistic; `desk-state.tsx` expose `answerQuestion`/`skipQuestion`;
  `view-chat.tsx` nối vào hai component.
- **Cần thiết ngoài danh sách file dự kiến:** `src/app/api/alpha-desk/[...path]/route.ts`
  — proxy Next có allowlist `FORWARDED_RESOURCES`; không thêm `questions` thì
  hai endpoint mới trả 404 ngay tại proxy, card thành nút chết. Có test.

### 5. Test

- `live-turn.test.ts` — thứ tự trail, sort theo `seq` của part, payload đi
  nguyên, kind lạ bị drop nhưng seq vẫn tiến, khoá lạ không lọt vào state,
  snapshot thay cả trail (2 hàng chứ không 3), card sống qua reconnect, card
  thiếu option bị từ chối, `pending`/`denied` giữ nguyên + code.
- `transcript.test.ts` — card đọc state đã merge, card mất row → `superseded`,
  answer không hỏi → null, draft mang card live.
- `message.test.tsx` — post đúng option id, skip, card inert khi không có
  handler, answered/skipped/superseded, card trên draft.
- `api.test.ts` — path/method/body của hai endpoint, escape id, 409 mang reason.
- `proxy.test.ts` — `questions` qua được allowlist.

## Verify (host, 2026-09-01)

| Lệnh | Kết quả |
|---|---|
| `pnpm --dir apps/web lint` | pass |
| `pnpm --dir apps/web type-check` | pass |
| `pnpm --dir apps/web test` | 39 files, **458 passed** (trước: 430) |
| `E2E_NEXT_DIST_DIR=.next-verify pnpm --dir apps/web build` | pass |
| `cd apps/api && pytest -q` | **1269 passed, 3 deselected** (baseline 1268) |
| `python3 -m compileall -q apps/api/{src,golden,tests}` | sạch |
| `git diff --check` | sạch |

Build với `E2E_NEXT_DIST_DIR` viết lại `apps/web/next-env.d.ts` (trỏ vào
`.next-verify`); đã `git checkout --` trả lại và type-check lại sau đó.

## Câu chưa trả lời

1. **`readQuestion` fallback `superseded` cho card mất row.** Backend cố tình
   để nguyên content khi row biến mất (`persistence.py:373-379`: vẽ `pending`
   là mời một câu trả lời không chỗ ghi). Client phải chọn một state để vẽ;
   `superseded` là cái gần nghĩa nhất ("đã hỏi, không còn cần trả lời") nhưng
   nó là **suy diễn của client**, không phải state trên row. Nếu P7 muốn một
   nhãn riêng cho ca này thì đó là copy mới, không phải state mới.
2. **Multi-select.** `multi_select` được mang đủ trên type và card, nhưng card
   chỉ gửi một id mỗi lần bấm. Backend nhận một lựa chọn cho cả hai loại câu
   hỏi nên không có gì sai, chỉ là bề mặt chưa mở — P7 sở hữu.
3. **409 sau khi bấm.** Hook hiện báo toast + invalidate thread để card được vẽ
   lại theo state thật. Chưa có copy riêng phân biệt "đã chốt khác" với "lỗi
   mạng"; nếu P7 muốn nói rõ hai ca thì đọc `reason` trên `AlphaRefusalError`.
4. **Progress chưa có mắt nào nhìn.** State đúng và có test, nhưng chỉ P7 mới
   chứng minh được payload từng kind đủ dùng để vẽ ba màn. Nếu thiếu field, chỗ
   sửa là `PROGRESS_FIELDS` phía backend, không phải client.
