# Brainstorm — Menu đính kèm của Composer

Ngày 2026-08-29 · nhánh `feat/study-canvas-runtime` · nguồn: page feedback trên `/`

## Outcome

Menu `+` của composer thôi là một hàng sáu row inert. Ba row có nghĩa:

1. **Thêm tệp hoặc ảnh** — chạy thật, đầy đủ cả ảnh (lựa chọn B).
2. **Chụp màn hình** — chạy thật; thay chỗ row web-search-ish cũ.
3. **Nghiên cứu sâu** ("Signal Research") — row hiện diện với badge *Sắp ra mắt*,
   kèm một ghi chú trong roadmap ở đúng phase sẽ làm.

Ba row còn lại giữ `disabled`.

## Trước → Sau

| Row hôm nay | Sau |
|---|---|
| Thêm tệp hoặc ảnh · *disabled* | **Chạy thật** — upload tệp + ảnh |
| Chụp màn hình bảng giá · *disabled* | **Chạy thật** — "Chụp màn hình", capture màn hình → ảnh đính kèm |
| Thêm vào danh mục · *disabled* | giữ *Sắp ra mắt* |
| Mẫu phân tích · *disabled* | giữ *Sắp ra mắt* |
| Nguồn dữ liệu kết nối · *disabled* | giữ *Sắp ra mắt* |
| Tra tin tức thị trường · *disabled* | **gỡ** — xem "Quyết định phụ" |
| — | **Nghiên cứu sâu** · *Sắp ra mắt* (mới) |

## Bằng chứng đã xác minh

- Modal là `AttachMenu`, `apps/web/src/components/shell/composer.tsx:382`.
  Con trỏ DevTools trong feedback (`desk-state.tsx:651`) trỏ lệch.
- Badge *Sắp ra mắt* do `MenuItem` tự vẽ cho mọi row `disabled`
  (`shell/primitives.tsx:184-189`). Giữ badge = không phải viết gì.
- `web_search` **đã luôn bật**: `WEB_TOOLS_ENABLED` + `TAVILY_API_KEY` có trong
  `.env`; bundle `web` nằm trong `CHAT_TOOLSETS` (`agent/toolsets.py`). Một row
  "bật web search" sẽ là một công tắc cho thứ đã bật.
- Route LLM là **OpenAI Chat Completions**, không phải Anthropic Messages:
  `tool_calls` · `tool_call_id` · `response_format.json_schema`
  (`core/llm/protocol.py:248-296`). Qua cliproxy `:8317/v1`, model
  `gpt-5.6-luna` (batch) / `gpt-5.6-terra` (session). ⇒ block ảnh có dạng
  `{"type":"image_url","image_url":{"url":"data:…"}}`.
- `core/llm/protocol.py:268` chỉ sinh `{"type":"text"}`. Không có đường cho ảnh.
- `CapabilityProbe` (`core/llm/probe.py:105-144`) đang chạy 5 check độc lập,
  mỗi check theo đúng lý lẽ "cách duy nhất biết route nhận một field là gửi thử
  một cái". Đây là nhà của check `vision_input` thứ sáu.

## Ràng buộc

**Cần amendment freeze.** CLAUDE.md mở tám surface cho plan price-basis; không
surface nào phủ việc này. Lựa chọn B đòi mở thêm:
`src/core/llm/{protocol,transport,probe}.py` · một surface upload mới
(router + storage) · `src/agent/{schemas,persistence,messages}.py`. Bảng freeze
phải được sửa **trước** khi code, không phải sau.

**Ràng buộc chịu lực nhất — invariant của `Message`.**
`protocol.py:238-246` bắt `segments` phải nối lại đúng bằng `content`, với lý do
được viết ra: "route đọc block và ledger đo string phải đang đọc cùng một
prompt". Một ảnh không có text. Đây là quyết định thiết kế trung tâm của cả
phase — invariant phải được **mở rộng** cho một loại segment không-text, không
phải bị vô hiệu hoá. Nếu bỏ nó, ledger im lặng đo sai mọi lượt có ảnh.

**Kế toán token — hai lần sửa, đây là câu cuối (red-team 2026-08-29).** Lỗ có
thật, ở phía **trước** call, không phải ở ledger đối chiếu:

| | Nguồn số | Thấy ảnh? |
|---|---|---|
| Cổng trước call (`turn_context_per_call`, `turn_input_total`) và thang giảm context | `estimate_tokens` = `4 + ceil(len(content)/3)` (`agent/messages.py:652-659`) → `build_messages` (`:806`) → `loop.py:1178` → `admission.py:682-686`, `:308` | **Không** — placeholder ~19 ký tự = 11 token cho một ảnh 1.500-3.000 token |
| Đối chiếu sau call | `usage.input_tokens` route trả về (`admission.py:483-491`) | Có |

Hệ quả nặng nhất không phải sai số tiền mà là **thang phục hồi bị vô hiệu**: khi
route trả context overflow, `loop.py:1311` so `smaller.estimated_tokens >=
context.estimated_tokens`, thấy *"nothing was given up"* và re-raise. Nên
`estimate_tokens` phải nhận chi phí khai báo cho content part ảnh. Trần cần canh
là `TURN_INPUT_TOTAL = 100_000` cho cả Turn, với `MAX_TOOL_ROUNDS + 1` = **5**
call (`loop.py:23`, `:913`) — không phải 4.

**Trần 8 KiB.** `CreateTurnRequest.text` bị chặn ở 8 KiB
(`agent/schemas.py:224-231`). Tệp không được đi lẫn trong `text`.

**Tin cậy.** Tệp và ảnh người dùng nạp là nội dung bên thứ ba, nhưng **không**
cùng lớp với `ContentTrust.UNTRUSTED` của tool result: nó do chính người dùng
đưa vào. Prompt injection qua chữ trong ảnh là thật. Cần chốt lớp tin cậy này,
không mặc định im lặng.

**Chụp màn hình là chuyện riêng tư.** `getDisplayMedia` trả về cả màn hình,
có thể gồm thứ người dùng không định gửi. Bước xem trước rồi mới gửi là **yêu
cầu**, không phải điểm hoàn thiện. Cần HTTPS hoặc localhost.

**Replay.** Mở lại thread phải vẽ lại đính kèm. Theo đúng luật `as_of` của
`agent_artifact`: hàng đính kèm là bất biến.

## Cổng nghiệm thu

1. Check `vision_input` trong `CapabilityProbe` **pass trên route thật** — cổng
   đầu tiên và là cổng chặn. Không pass thì lựa chọn B không thi công được, và
   phần tệp text vẫn đi tiếp được.
2. Ảnh nạp qua UI → model đọc và mô tả được nội dung ảnh trong câu trả lời.
3. Invariant `Message.__post_init__` còn hiệu lực, có test cho segment
   không-text; ledger đếm ảnh chứ không bỏ qua.
4. Mở lại thread cũ vẽ lại đính kèm, không gọi lại model.
5. Chụp màn hình có bước xem trước, có huỷ.
6. Ba row còn lại vẫn mang badge; `Nghiên cứu sâu` mang badge.
7. `docs/roadmap.md` có ghi chú UI ở phase tương ứng (Track S, S1/S2).
8. `make test` · `pnpm type-check` `lint` `test` `build` pass.

## Non-goals

- Không xây chế độ nghiên cứu sâu. Chỉ row + badge + ghi chú roadmap.
- Không đụng `SignalDeskToggle` và không đưa desk trở lại làm menu item —
  `composer.tsx:377-379` ghi rõ nó đã bị gỡ khỏi đây có chủ đích.
- Không thêm công tắc bật/tắt web search.
- Không làm ba row còn lại.

## Quyết định phụ (đã tự chốt, không hỏi)

**Gỡ row "Tra tin tức thị trường"** thay vì để nó mang badge. Badge *Sắp ra mắt*
trên một năng lực đã bật là một câu sai nói với người đọc: model đã tra web
được từ mọi lượt chat. Nói được là "sắp có" thì nó phải chưa có.

## Lỗ hổng phát hiện ngoài phạm vi — chưa sửa

`createTurn` (`apps/web/src/lib/alpha-desk/api.ts:103-113`) **không gửi `mode`**.
Backend `CreateTurnRequest.mode` mặc định `chat` (`agent/schemas.py:221`), nên
công tắc Signal Desk hiện chỉ đảo layout FE — mọi Turn chạy `chat`, desk chỉ
được vẽ khi model tự chọn gọi tool `studies`. Cùng chỗ đó web gửi
`active_symbol`, một field **không khai trong schema** nên Pydantic bỏ im lặng.

Hai cái này độc lập với menu đính kèm. Đề nghị tách một fix riêng.
