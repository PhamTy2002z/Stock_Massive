---
phase: 7
title: "Turn mang đính kèm, thread vẽ lại"
status: done
priority: P1
effort: "7h"
dependencies: [3, 5, 6]
---

# Phase 07: Turn mang đính kèm, thread vẽ lại

## Overview

Nối các nửa: id đính kèm đi cùng câu hỏi, thành content part trong message gửi
model, và ở lại transcript để mở lại thread vẽ lại được. Bản đầu chỉ sai **chỗ** —
nó chỉ `loop.py`, và ở đó không có gì để sửa.

## Requirements

- Functional: `CreateTurnRequest` nhận danh sách id; đính kèm thành content part ở
  đúng chỗ; `history_of` không đánh mất chúng; `GET /threads/{id}` trả đủ metadata
  cho FE vẽ lại.
- Non-functional: `build_messages` giữ purity; luật idempotency không đổi hình dạng;
  trần 8 KiB không bị lách bằng một con số thứ hai vô danh.

## Architecture

### Chỗ tiêm thật

`grep Role.USER src/agent/loop.py` → **0**. Message người dùng dựng ở
`messages.py:688` trong `_turn_messages`:

```
loop.py:1100-1117   _construct → Transcript(turns=(*request.history,
                                  TranscriptTurn(user_text=…, tool_calls=…)))
                              → build_messages(transcript, budget)
messages.py:688     _turn_messages → Message(role=Role.USER, content=turn.user_text)
```

`TranscriptTurn` (`:565-580`) có ba trường: `user_text`, `tool_calls`,
`assistant_text`. Không có slot nào cho đính kèm. Nên: `TranscriptTurn` mang thêm
đính kèm, và `_turn_messages` là chỗ dựng content part.

### Purity giữ được, vì "lượt mới nhất" là thuộc tính của snapshot

`build_messages` khai *"Pure: the same transcript and the same budget give the same
list, every time"* (`:793-794`). Luật "ảnh chỉ ở lượt mới nhất" **không** được cài
bằng một round counter đọc trong hàm — làm vậy là phá contract. Nó là thuộc tính
của snapshot: `_turn_messages` phát content part chỉ cho `TranscriptTurn` **cuối
cùng** của `Transcript`. Cùng transcript vẫn cho cùng list; purity nguyên vẹn.

### `history_of` là chỗ thứ hai, bản đầu bỏ sót

`router.py:171-173` đọc `text = str(record.content.get("text") or "")` rồi
`TranscriptTurn(user_text=text)`. Payload lưu có `attachments` nhưng không ai đọc.
Hệ quả nếu để nguyên: model mất ảnh sau đúng một lượt, trong khi FE vẫn vẽ chip —
UI khẳng định liên tục mà model không có.

Chiều ngược cũng phải chặn: nếu `history_of` nạp lại đính kèm vào mọi
`TranscriptTurn`, một thread 10 lượt mỗi lượt một ảnh sẽ gửi 10 ảnh ở lượt 10.
Đây là lý do luật "chỉ lượt mới nhất" ở trên là **hai** luật cùng lúc: nó chặn cả
gửi lại qua vòng tool và gửi lại qua lịch sử thread.

Nên `history_of` nạp lại **metadata** (để placeholder còn trong `user_text` render
được và FE vẽ được), còn pixel thì không. Hệ quả — model mất pixel sau một lượt —
được ghi ra ở §Câu hỏi chưa giải quyết của plan, không giấu.

### Trần 8 KiB, một số hay hai số

`MAX_USER_INPUT_BYTES = 8 * 1024` được ép **hai chỗ** có chủ ý:
`schemas.py:223-231` (*"Checked here as well as in the lifecycle"*) và
`turns.py:386`. Bản đầu mở cửa thứ hai vào cùng prompt với "trần ký tự riêng" không
tên, không liên hệ, dẫn từ ngân sách ảnh lớn hơn nhiều bậc. Phase này phải chọn:
dùng lại `MAX_USER_INPUT_BYTES` cho nội dung tệp inline (một số, một nghĩa), hoặc
đặt một hằng số có tên và **ghi vào bình luận vì sao một số thứ hai là hợp pháp**.
Không có lựa chọn thứ ba là để nó vô danh.

### Đính kèm là phần của idempotency payload

`persistence.py:938-947` chỉ thêm `symbols`/`mode` khi khác mặc định, với lý lẽ
*"adding one to every ordinary Turn would make the same question asked before this
existed compare unequal to itself"*. `attachments` theo đúng luật đó. Và nó **phải**
ở trong key: cùng câu hỏi với hai ảnh khác nhau là hai câu hỏi.

## Related Code Files

- Modify: `apps/api/src/agent/schemas.py` — `CreateTurnRequest.attachments`
- Modify: `apps/api/src/agent/router.py` — chủ quyền + `history_of`
- Modify: `apps/api/src/agent/turns.py` — `create(..., attachments=…)` + quyết định trần text
- Modify: `apps/api/src/agent/persistence.py` — payload + đọc lại + gắn `attached_turn_id`
- Modify: `apps/api/src/agent/messages.py` — `TranscriptTurn` + `_turn_messages`
- Modify: `apps/api/tests/test_agent_loop.py`, `tests/test_agent_turn_events.py`

## Implementation Steps

1. `CreateTurnRequest.attachments: list[uuid.UUID] = []` với `max_length` bằng trần
   số lượng phase 05. Bình luận nói vì sao nó trong idempotency payload.
2. Router: đọc từng id qua store phase 05, kiểm `user_id`. Không thuộc user hoặc
   không tồn tại → 404, không phân biệt.
3. `turns.create` nhận `attachments`, truyền vào `store.create_turn`.
4. `persistence.create_turn`: `payload["attachments"] = [str(id), …]` chỉ khi không
   rỗng; đồng thời set `attached_turn_id` trên các hàng đính kèm — đó là cái làm TTL
   của phase 05 phân biệt được rác với hàng đang dùng. Xác nhận `TurnPayloadConflict`
   vẫn bắt "cùng id, khác ảnh".
5. `TranscriptTurn` mang thêm một trường đính kèm (frozen, nên là tuple).
6. `_turn_messages`: với **lượt cuối** của transcript và `LLMRoute` có vision, dựng
   content part cho từng ảnh + placeholder trong `content`. Lượt không phải cuối:
   chỉ placeholder. Cờ đọc từ `LLMRoute` (phase 04), **không** `get_settings()` —
   `loop.py` và `messages.py` không có lần gọi nào và giữ nguyên như vậy.
7. Tệp text: nội dung đọc từ store, bọc bằng `wrap_attachment` (phase 06), nối vào
   `content` dưới trần đã chọn ở §Architecture. Đây là chỗ duy nhất nội dung tệp
   vào prompt.
8. `history_of` (`router.py:157-181`): đọc `attachments` từ payload lưu, dựng
   `TranscriptTurn` mang metadata. Không nạp bytes.
9. Đọc lại: `_message` mang metadata đính kèm ra response (id · tên · media type ·
   kích thước), **không** bytes — FE lấy bytes qua `GET /attachments/{id}`.
10. Test:
   - cùng `turn_id` khác đính kèm → 409;
   - Turn không đính kèm: payload lưu **y như trước** phase này (so dict);
   - id của user khác → 404;
   - `LLMRoute` không vision: không content part nào tới model, đính kèm vẫn trong
     transcript;
   - **thread hai lượt, lượt 1 có ảnh: request của lượt 2 không mang content part
     ảnh nào** — đây là test bản đầu không có và là test quan trọng nhất của phase;
   - `build_messages` vẫn pure: gọi hai lần cùng transcript cho cùng list;
   - `attached_turn_id` được set, nên TTL không xoá hàng đang dùng.

## Success Criteria

- [x] Cùng `turn_id`, khác danh sách đính kèm → 409
- [x] Turn không đính kèm: payload lưu không đổi (test so dict)
- [x] Id của user khác → 404
- [x] Route không vision: không content part nào tới model
- [x] Thread hai lượt: lượt 2 không gửi lại ảnh của lượt 1
- [x] `build_messages` gọi hai lần cho cùng kết quả
- [x] `attached_turn_id` được set khi Turn tạo
- [x] Trần nội dung tệp inline: hoặc là `MAX_USER_INPUT_BYTES`, hoặc có tên và có bình luận biện minh
- [~] `messages.py` vẫn **0** lần gọi `get_settings()`. `loop.py` có **1** — tiền đề của plan sai, xem §Kết quả thi công. Cờ vision không đi qua nó.
- [x] `make test` pass

## Risk Assessment

**Rủi ro: một Turn nhiều ảnh vẫn phá `TURN_INPUT_TOTAL` dù đã đếm đúng.** Đếm đúng
làm trần **nổ đúng lúc** thay vì nổ muộn — nó không làm trần to ra.
*Tín hiệu:* `BudgetRefusal("turn_input_total")` hoặc `turn_context_per_call` lúc tạo
Turn.
*Phản ứng đã định:* refusal ở **tạo Turn** với câu đọc được ("bỏ một ảnh"), trước
khi ngân sách bị giữ. Đây là điều bản đầu không có: nó để lỗi rơi vào giữa lượt,
nơi người đọc không có hành động nào để làm.

**Rủi ro: model mất pixel sau một lượt làm câu trả lời tiếp nối sai.** Người đọc hỏi
*"còn cột thứ hai?"* và model không còn ảnh.
*Tín hiệu:* câu trả lời lượt 2 mâu thuẫn với lượt 1, hoặc mô tả chung chung.
*Phản ứng đã định:* placeholder còn trong `content` nên model **biết** có một ảnh nó
không còn thấy — nó phải nói ra điều đó thay vì bịa. Nếu nó bịa, đó là một câu prompt
ở phase 06, không phải một lý do để gửi lại ảnh mọi lượt.

**Rủi ro: sửa `_turn_messages` phá purity mà test không bắt.**
*Tín hiệu:* test "gọi hai lần cùng kết quả" ở bước 10.
*Phản ứng:* nếu cần biết "lượt nào là cuối" mà không có trong snapshot, đó là dấu
thiết kế sai — thêm dữ kiện vào `Transcript`, không đọc trạng thái ngoài.

## Kết quả thi công — 2026-08-29

`make test`: **1507 passed, 3 deselected** (28 test mới). `make lint` pass.

**Tiêu chí "`loop.py` vẫn 0 lần gọi `get_settings()`" dựa trên một tiền đề sai.**
Red-team finding 14 ghi *"`loop.py` có 0 `get_settings()`"*. Đo lúc thi công:
`loop.py:1836` có một lần gọi — `_asked()` chọn `ASKED_LIMIT` hay
`ASKED_LIMIT_OUTSIDE_DEBUG` để quyết log giữ được bao nhiêu chữ của câu hỏi. Nó
**không** thuộc plan này (là việc riêng trên cùng branch, chưa commit) và không
liên quan đính kèm. Phase này thêm **0** lần gọi mới, và cờ vision đọc từ
`config.route.vision` đúng như tiêu chí muốn. Tick `[~]` chứ không `[x]`: số 0
không đúng, ý định thì đạt.

**Cờ vision là dữ kiện của snapshot, không phải của môi trường.**
`Transcript.vision: bool = False` — cùng lý lẽ với `system_prefix`: chỉ caller giữ
`LLMRoute`, và `build_messages` đọc cấu hình sẽ biến purity của nó thành một lời
khai về môi trường. Mặc định `False` nên mọi caller viết trước khi có ảnh dựng đúng
context nó vẫn dựng, **và** một route chưa ai đo vision không được gửi pixel nhờ một
giá trị mặc định.

**Trần đếm số lượng không phải trần ràng buộc — đo ra mới thấy.**
`MAX_IMAGES_PER_TURN = 8` chia ngân sách ảnh mỗi call cho chi phí một ảnh
1024×768. Nhưng `MAX_IMAGE_PIXELS` cho **một** ảnh lấy tới nửa ngân sách đó
(3.999 token). Đo thật: **ba** ảnh 1800×1800 = 11.493 token so với trần 8.000 —
nằm trong trần đếm, vượt trần ngân sách. Nên thêm
`attachments.assert_within_turn_budget` — phép cộng, chạy ở router **trước** khi có
row nào, với câu tiếng Việt nói đúng hành động còn lại: *"hãy bỏ một ảnh rồi gửi
lại"*. Trần đếm vẫn giữ, ở schema, vì nó rẻ và chạy trước.

**Gắn `attached_turn_id` trong cùng transaction với Turn, không phải một call thứ
hai.** Hai commit để lọt hai trạng thái sai: row gắn vào một Turn không tạo được,
và — cái gây hại — Turn đã commit mà row còn chưa gắn, nên sweep 24h xoá bytes một
Turn đang trỏ tới. Trạng thái thứ hai không cứu được. Nên `UPDATE` nằm trong
`persistence._create_turn`, cùng `session.commit()`, và kiểm quyền sở hữu **lại** ở
đó: đây là chỗ ghi, và chỗ ghi là chỗ duy nhất việc kiểm không phải lời khuyên.

**Payload lưu metadata, không chỉ id — lệch bước 4 của plan, có lý do.** Plan viết
`payload["attachments"] = [str(id), …]`. Nhưng bước 9 lại đòi `_message` trả metadata
ra response, và `_message(record)` không có session để join. Lưu metadata giải cả ba
việc bằng không query thêm: idempotency so đúng (mọi trường của một hàng đính kèm là
bất biến sau khi nạp, nên cùng id luôn cho cùng metadata — không thể làm một Turn
khác chính nó), FE vẽ lại chip khi mở thread, và placeholder của lượt cũ còn tên tệp
sau khi bytes không còn được gửi. Cùng khuôn `symbols`/`mode` đang dùng: dữ kiện về
request, đặt cạnh chữ của request. Vẫn **chỉ khi không rỗng** — test so dict xác nhận
Turn không đính kèm lưu y như trước.

**Trần text inline: `MAX_ATTACHMENT_TEXT_BYTES`, cùng giá trị `MAX_USER_INPUT_BYTES`,
ghim bằng test.** Không import được vì `turns` → `loop` → `messages` là một vòng;
vòng đó là lý do **duy nhất** có hai tên. Một test khẳng định hai số bằng nhau nên
chúng không trôi thành hai chính sách. Cùng giá trị vì cùng một câu hỏi: một lượt
được đặt bao nhiêu chữ trước mặt model dưới danh nghĩa lời của người đọc — và tệp họ
chọn là lời của họ y như câu họ gõ. Trần **tiêu theo lượt**, không theo tệp: hai tệp
mỗi cái quá nửa trần thì cộng lại đúng trần, vì per-file là cách một trần thôi làm
trần. Cắt thì **nói ra** (`TRUNCATION_NOTE`) — tệp bị cắt im lặng là tệp model đọc
như tệp đủ.

**Một test của tôi sai và cái sai đáng ghi:** nó đếm ký tự `y` để đo phần nội dung
tệp, nhưng `TRUNCATION_NOTE` chứa chữ *"đây"* — có `y`. 8193 > 8192. Đổi filler sang
`Z`, và assertion siết từ `<=` thành `==` vì giờ nó đo đúng thứ nó tưởng đang đo.

**Luật "chỉ lượt mới nhất" là hai luật cùng lúc, và cả hai có test.** Vòng tool:
`_turn_messages` phát content part chỉ cho `TranscriptTurn` **cuối** của snapshot —
không round counter, nên purity còn nguyên (test: đảo thứ tự snapshot thì ảnh đi
theo, không gì khác đổi). Lịch sử thread: `history_of` dựng metadata, không bytes.
Test thang 10 lượt mỗi lượt một ảnh → **đúng một** ảnh tới model.

**Chỗ duy nhất nội dung nạp vào message** là `_attachment_block`. Đó là điều làm
`wrap_attachment` của phase 06 không thể bị lách: có một cửa, và nó ở đây.

**Một sửa hình dạng ngoài kế hoạch:** `attachment_store`/`Attachments` dời từ cuối
`router.py` lên cạnh `Desk`. Alias khai sau lần dùng đầu resolve về class trần và
FastAPI đọc nó thành response field — lỗi import, không phải lựa chọn.
