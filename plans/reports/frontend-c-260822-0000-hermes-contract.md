# Frontend C — Hermes SSE contract (apps/web)

Ngày 2026-08-22. Worktree `hermes-harness`, branch `feat/hermes-harness`.
Phạm vi: chỉ `apps/web`. Nguồn sự thật: `plans/260822-0000-hermes-harness/plan.md` §4.
Trong lúc làm, `docs/streaming-topology.md` (phiên khác) đã ghi đúng cùng contract §4 —
frontend khớp với bảng event trong đó.

## Kết quả cổng kiểm tra (chạy thật)

| Cổng | Trước | Sau |
|---|---|---|
| `pnpm type-check` | pass | **pass** (0 lỗi) |
| `pnpm lint` | pass | **pass** (0 error, 0 warning) |
| `pnpm test` | 35 file / 488 test pass | **31 file / 363 test pass**, 4.5s |
| `pnpm build` | — | **pass** (9 route, First Load JS shared 102 kB) |

`pnpm install` phải chạy trước: worktree chưa có `node_modules`.
Build chạy ở worktree riêng nên không chạm `.next` của dev server cây chính.

## Xoá (git rm) — 6711 dòng

| Nhóm | File |
|---|---|
| widgets | toàn bộ `components/alpha/widgets/` (21 file, gồm `widgets.test.tsx`, `transcript.test.tsx`, `palette.test.ts`) |
| grounding/citation UI | `message/{citation-chips,figure,content-block,search-progress,source-list,source-drawer,answer-actions,suggestions}.tsx` |
| reveal cadence | `message/word-cadence.ts` (xem "Quyết định" bên dưới) |
| charts mồ côi | `charts/{comparison-bars,range-track,index}.ts(x)` — grep xác nhận chỉ widgets import; `.gitkeep` giữ lại |
| test hợp đồng cũ | `lib/alpha-desk/{live-turn,transcript,copy}.test.ts`, `message/message.test.tsx` |

`widgets/units.ts` → **`src/lib/units.ts`** (git mv, giữ history). Sửa 2 import ở
`analysis/figure-row.tsx:3` và `analysis/price-zone-band.tsx:3`. Analysis lane + REST bảng
giá không đổi hành vi (không sửa file nào trong `components/alpha/analysis/**`,
`lib/alpha-desk/analysis.ts`, `hooks/use-*`, `lib/api.ts`, `shell/view-board|view-news|inspector|watchlist-section`).

## Contract cũ → mới

| Cũ | Mới |
|---|---|
| 8 event, `version: 1` | 7 event, `version: 2` (`TURN_EVENT_VERSION` trong `types.ts`) |
| `content.block` → append block | `content.delta` → **append text** vào chuỗi đang stream |
| `turn.activity` (5 phase) + `ProgressStep`/`ProgressSource` | `tool.call` → upsert theo `id`, `status: running\|ok\|error`, `summary` do backend viết |
| `widget.ready` | (bỏ) |
| snapshot `{activity, progress, blocks, widgets}` | snapshot `{through_seq, status, terminal_reason, text, tool_calls, message_id}` |
| content canonical `{text, blocks, answer_kind, risk_notice, evidence_manifest, sources_and_methods, search_progress, suggestions}` | `{text, tool_calls}` |
| `AssistantView {blocks, riskNotice, searchProgress, suggestions, widgets, widgetRefusals, completed}` | `AssistantView {text, toolCalls, completed}` |
| `DraftEntry {blocks, activity, steps, appendedIndex, …}` | `DraftEntry {text, toolCalls, phase, terminalReason}` |

Type bị xoá khỏi `types.ts`: `Citation`, `CitationSource`, `ContentBlock`, `WidgetSpec`,
`RiskNotice`, `EvidenceManifest`, `SourceAndMethod`, `ProgressStep`, `ProgressDetail`,
`ProgressSource`, `ActivityPhase`, `answer_kind`. Giữ nguyên: `TurnStatus`, `TurnEvent`,
`FlagReason`, `MessageFlag`, `Thread*`, `Turn`, `CreatedTurn`.

## Viết lại

| File | Nội dung |
|---|---|
| `lib/alpha-desk/types.ts` | 7 event, `TURN_EVENT_VERSION = 2`, `ToolCall`, `SnapshotData`, `AssistantContent {text, tool_calls}` |
| `lib/alpha-desk/live-turn.ts` | state `{text, toolCalls}`; **giữ nguyên** dedupe theo `seq`, phát hiện gap → `needsResync`, snapshot replace toàn bộ, `settled` bỏ qua thứ tự stream, `phaseForStatus` (incomplete có text → `incomplete`, không có → `failed`), `keepCancelling`, `resendPlan` |
| `lib/alpha-desk/transcript.ts` | `AssistantView`/`DraftEntry` mới; đọc `tool_calls` phòng vệ (JSONB): bỏ row không có `id`/`name`, `summary` rỗng → tên tool |
| `lib/alpha-desk/copy.ts` | bỏ `ACTIVITY_COPY`, `PROGRESS_COPY`, `FIRST_RUN` (đã chết: chỉ test cũ dùng), `KNOWN_TERMINAL_REASONS`; bỏ `grounding_failed`; `tool_timeout` đổi câu cho tool web/memory; thêm `TOOL_CALL_COPY`; giữ `terminalSentence`, `CANCELLING_LABEL`, FLAG copy |
| `hooks/use-live-turn.ts` | `EVENT_TYPES` = 7 event mới. Reattach qua desk-session, `invalidateQueries` khi terminal, `send/retry/cancel/attach`, probe 4s: **không đổi** |
| `message/tool-call-list.tsx` (mới) | danh sách tool call, dùng chung cho draft và message canonical (`aria-label` = `TOOL_CALL_COPY.label`) |
| `message/assistant-message.tsx` | tool call list → markdown → note khi `!completed` → FlagAction. Bỏ mọi slot citation/widget/progress/suggestion |
| `message/draft-message.tsx` | tool call list → markdown text → "Đang chuẩn bị…" khi chưa có gì → `TurnStatus` |
| `message/markdown.tsx` | bỏ `stagger` và `trailing` (slot chip citation); giữ luật no-raw-HTML và `rel="noopener noreferrer"` |
| `shell/view-chat.tsx` | call site `AssistantMessage` bỏ `onRetry/onAsk/showSuggestions`; xoá helper `questionAbove`; **giữ** pin/spacer scroll, AnalysisCard, UserMessage (copy/sửa/gửi lại) |
| `api/alpha-desk/[...path]/route.ts` | allowlist còn `watchlist, analyses, threads, turns, messages`. `middleware.ts` không cần đổi (matcher chỉ loại trừ `api/alpha-desk`) |
| `message/turn-status.tsx`, `message-shell.tsx`, `flag-action.tsx`, `shell/desk-state.tsx` | **không cần sửa** — chỉ dùng `LivePhase`/`terminalSentence`/`TranscriptEntry`, tất cả còn sống |

## Test mới

| File | Số test | Bao gồm |
|---|---|---|
| `lib/alpha-desk/live-turn.test.ts` | 33 | delta nối chuỗi theo thứ tự; delta trùng `seq` không in hai lần; gap không vá; event của turn khác bị bỏ; tool.call upsert + thứ tự + thiếu id + fallback summary/status; snapshot replace/áp dụng bất chấp seq/terminal đặt messageId/incomplete rỗng → failed/giữ `cancelling`; 4 ending; `settled` không ghi đè ending đã có; cancel/resync/reset; `resendPlan` |
| `lib/alpha-desk/transcript.test.ts` | 26 | thứ tự theo `seq`, bỏ `summary`; flag đã có; tool_calls phòng vệ (không phải list / row rác / thiếu summary); `completed`; draft thuộc 1 thread, được message canonical thay thế, đứng vững khi Turn fail; pending question; Analysis anchoring |
| `message/message.test.tsx` | 15 | markdown render (bold/table/link rel+target/HTML thành text); tool call list (summary + nhãn outcome, không có call thì không có list, running trên draft); note khi trả lời dở; draft: "Đang chuẩn bị…", giữ text + Retry khi ended badly, không lộ mã `terminal_reason`, không có nút flag |
| `message/flag-action.test.tsx` | sửa fixture `view()` sang `{text, toolCalls, completed}` (nội dung test không đổi) |

## Quyết định cần biết

- **Bỏ reveal cadence.** `content.delta` append vào một chuỗi, nên rehype plugin chunk sẽ
  re-parse + re-animate *toàn bộ* text mỗi delta → nháy. Delta tự nó đã là cadence, nên
  `word-cadence.ts` bị xoá và `markdown.tsx` không còn `stagger`.
- **Markdown dở dang có thể lộ ký tự cú pháp một nhịp** (ví dụ `**` trước khi delta đóng nó
  tới). Đây là hệ quả chấp nhận của contract mới: giữ text lại tới khi parse sạch chính là
  cái buffering mà đường streaming tồn tại để tránh. Đã ghi trong doc của `markdown.tsx`.
- **Đặt tên `ToolCall` thay vì `ToolCallView`** trong `types.ts`: module này là các shape
  trên dây, và stream + message canonical + view dùng đúng một shape.
- **`AssistantView.completed`** đọc từ khoá `status` tuỳ chọn trên content đã lưu, mặc định
  là "hoàn thành" khi không có. Contract §4 nói message canonical chỉ lưu `{text, tool_calls}`
  → tới khi backend lưu thêm `status`, mọi câu trả lời trong transcript đọc là hoàn thành.
- **Mất nút Copy/Retry dưới câu trả lời** vì `answer-actions.tsx` bị xoá theo lệnh. Copy /
  Sửa / Gửi lại vẫn còn ở bubble câu hỏi (`view-chat.tsx` `UserMessage`). Không tự thêm lại.

## Còn nợ

- **E2E chờ backend B2.** `e2e/streaming.spec.ts` + `e2e/desk.ts` đã cập nhật theo contract
  mới (`say()` = một `content.delta`; assertion đổi từ `getByText` khớp cả element sang
  `toContainText` + đếm lần xuất hiện trong `getByLabel("Assistant message")`; thêm
  `ANSWER_LABEL`). **Chưa chạy**: cần `apps/api/tests/e2e/server.py` mới phát
  `content.delta`/`tool.call`, và `/e2e/turn/churn` phát event tiêu thụ `seq`.
- `src/app/globals.css` còn `.vg-chunk` + `@keyframes vg-chunk-in` mồ côi. Không xoá: file
  không nằm trong danh sách ownership và đang bị sửa song song ở cây chính. `animate-vg-*`
  còn lại vẫn có người dùng (`primitives.tsx`, `inspector.tsx`, `settings-primitives.tsx`).
- `lib/signal-issues.ts:33` còn nhắc "citation contract" — thuộc lane Signal Issue của bảng
  giá, không phải harness; để nguyên.
- Toàn bộ thay đổi đã `git add` nhưng **chưa commit** (không được yêu cầu).

Status: DONE
Summary: apps/web đã chạy đúng contract SSE §4 (7 event, version 2, text + tool call), xoá
6711 dòng widget/citation/progress/cadence, viết lại 3 module lib + 4 component + proxy
allowlist, 74 test mới; type-check/lint/test/build xanh thật.
Concerns: (1) e2e chỉ mới khớp contract trên giấy, phải chờ server e2e của B2; (2)
`AssistantView.completed` chưa có nguồn trên dây — nếu backend không lưu `status` trên
message thì câu trả lời dở dang trong transcript đọc như hoàn thành; (3) nút copy câu trả
lời mất theo `answer-actions.tsx`, cần chủ sản phẩm chốt có dựng lại hay không.
