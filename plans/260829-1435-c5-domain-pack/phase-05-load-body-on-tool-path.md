---
phase: 5
title: "Nạp body theo tool path, dính tới cuối Turn"
status: completed
priority: P1
effort: "6h"
dependencies: [4]
---

# Phase 5: Nạp body theo tool path, dính tới cuối Turn

## Overview

Đây là "progressive" của progressive instruction loading: body của pack chỉ đi ra
với những Turn thật sự cần nó, và không Turn nào phải trả thêm một lượt model để
biết điều đó.

Phase này là **đường nhận pack** của `loop.py` — đúng cái mà non-goal của plan
chừa lại (*"không sửa `loop.py` ngoài đường nhận pack"*). Ba trigger, một cờ
per-Turn, một note dính, và một phép giữ chỗ ngân sách đúng bằng chi phí thật.

## Requirements

- Functional: ba trigger deterministic — `TurnMode == "signal_desk"`; lịch sử
  Thread đã có call domain; round này model gọi một tool domain.
- Functional: body **dính** — đã bật thì mọi call còn lại của Turn đều mang nó.
- Functional: chỗ giữ token cho body là **chi phí thật của body**, không phải
  `SYSTEM_NOTE_TOKENS`.
- Functional: Turn không kích trigger nào **không bao giờ** thấy body.
- Non-functional: **không** đổi `MAX_TOOL_ROUNDS` (`loop.py:164`),
  `MAX_EXTERNAL_TOOL_CALLS` (`:293`), `SIGNAL_DESK_NOTE` (`:334-338`),
  `MAX_EMPTY_NUDGES` (`:349`), `plan_segments()`, hay `resolve_tool_surface`.
- Non-functional: `messages.py` **không đổi** — `build_messages` giữ nguyên độ
  thuần.
- Non-functional: cờ sống trên `_TurnState` (per-Turn), **không** trên
  `AgentLoop`, **không** ở biến module.

## Architecture

### Vì sao là system note chứ không phải render lại prompt

Prompt được `render()` **một lần cho cả Turn** ở `loop.py:929`, trước vòng round
bắt đầu ở `:931`. Cơ chế dán thêm một message SYSTEM mỗi call thì **đã có**, ba
chỗ đang dùng nó (`loop.py:1252-1263`): `SIGNAL_DESK_NOTE` cho mode,
`ROUNDS_EXHAUSTED_NOTE` cho trần round, `state.note` cho nudge.

Body đi đường thứ nhất — dính theo Turn, đúng như mode — chứ không đường thứ ba:
`state.note` bị xoá ngay sau call đã mang nó (`loop.py:1284`), và một playbook
chỉ tồn tại một round là một playbook model quên trước khi kết quả tool về.

Comment tại `loop.py:313-318` giải thích vì sao mode là note chứ không phải
section: *"prompt là như nhau cho mọi Turn — đó là thứ làm nó thành prefix
cacheable — và mode là dữ kiện của riêng Turn này"*. Body của pack đứng đúng ở
tầng đó: nó là dữ kiện của riêng Turn này.

**Ghi lại cho C2, để C2 không phải phát hiện lại:** khi `prompt_cache_control`
bật (`core/llm/config.py:151`, hôm nay `False`), một note ở đuôi trả giá đầy đủ
mỗi call. Chỗ đúng của body lúc đó là **block thứ hai ngay sau core**, nơi nó vẫn
nằm trong prefix cacheable — một breakpoint mới sau core, body cached từ call thứ
hai trở đi. Đó là quyết định của C2 (owner `messages.py` + `core/llm`), không phải
của C5, và C5 không dựng sẵn cho nó.

### Ba trigger, đọc ở đâu

| Trigger | Đọc | Chèn ở đâu | Ghi chú |
|---|---|---|---|
| Mode | `request.mode == SIGNAL_DESK_MODE` (`loop.py:614`, `:311`) | ngay sau `render()` (`:929`) | mode là lời hứa Turn sẽ ra desk (`:305-311`) — tool domain là chắc chắn |
| Lịch sử | `request.history` (`:601`) → `TranscriptTurn.tool_calls` | cùng chỗ | chỉ cần quét **một** Turn gần nhất là đủ; quét sâu hơn làm một Thread từng hỏi cổ phiếu mang body mãi mãi |
| Tool path | `completion.tool_calls` trước `assert_distinct_ids` (`:1058`) | ngay trước dòng đó | đọc **tên tool model xin gọi**, không đợi kết quả: một call hỏng vẫn là một tín hiệu intent đúng |

Tập tên tool domain = `resolve_toolset(active_pack().toolsets)`
(`toolsets.py:144`) — không hardcode danh sách tên tool trong `loop.py`. Đó chính
là chỗ "đổi pack không sửa `loop.py`" phải đứng vững.

### Cờ ở đâu, và vì sao ở đó

`_TurnState` (`loop.py:755-800`) — per-Turn, dựng ở đầu `_run`, và đã là nơi ở
của đúng loại dữ kiện này: `mode`, `compressions`, `output_reductions`,
`external_calls` đều per-Turn với cùng lý lẽ *"một Turn đã biết điều gì thì round
sau không phải khám phá lại"*.

Kiểm lifetime trước khi thêm state, theo thứ tự: `_TurnState` dựng mỗi lần `_run`
chạy (`loop.py:933`); `AgentLoop` dựng mỗi Turn qua `loop_factory`
(`service.py:120-131`); `ToolContext` dựng mỗi Turn (`loop.py:919-924`). Nên cờ
trên `_TurnState` **không** rò giữa hai Turn, hai người dùng, hay hai tenant —
điều mà một cờ trên `AgentLoop` hoặc một biến module sẽ làm.

### Ngân sách: 160 token là số sai cho một body 900 token

`_construct` giữ chỗ `SYSTEM_NOTE_TOKENS = 160` cho mỗi note
(`loop.py:1105-1117`, hằng ở `:340-345`), và comment tại chỗ nói rõ vì sao phải
giữ chỗ: *"trần mà transcript bị trim và request thật sự gửi đi không được phép
bất đồng"*. Một body ~900 token giữ chỗ 160 làm đúng điều comment đó cấm — context
được dựng tưởng còn chỗ, request đi ra vượt trần, và admission từ chối giữa Turn.

Nên body mang **chi phí đo được của chính nó**: `DomainPack` có
`body_tokens`, tính một lần lúc import bằng
`messages.estimate_tokens(Message(role=SYSTEM, content=body_text))` — cùng hàm
mà budget và thang trim đọc (`messages.py:760`). `_construct` và `_call` cộng
đúng số đó thay vì `SYSTEM_NOTE_TOKENS`.

Chiều import: `agent/domain/pack.py` → `agent/messages.estimate_tokens`.
`messages.py` không import `domain` (nó cố ý không đọc cấu hình gì —
`messages.py:697-703`), nên không vòng.

### Turn dài: body có làm vỡ trần context không

`TURN_CONTEXT_PER_CALL = 32.000` (`core/llm/admission.py:52`). Body 900 token là
**2,8%** trần, và nó chỉ có mặt ở Turn đã đọc store — loại Turn có tool result
ngắn (một figure kèm metadata), không phải loại nạp 20k ký tự một trang web. Thang
trim (`messages.py:958-993`) không đụng system message nên body không bị cắt mất
nửa chừng; nó chỉ làm trần của phần transcript nhỏ đi 900 token, đúng cơ chế mà
`reserved` đang làm cho ba note kia.

## Related Code Files

- Modify: `apps/api/src/agent/loop.py` — import `active_pack`; cờ
  `domain_body: bool` trên `_TurnState` (`:755-800`); quyết định trước vòng round
  (sau `:929`); trigger tool path (trước `:1058`); dán note + `reserved` trong
  `_call` (`:1252-1263`); giữ chỗ trong `_construct` (`:1105-1117`)
- Modify: `apps/api/src/agent/domain/pack.py` — `body_text`, `body_tokens`
- Modify: `apps/api/tests/test_agent_loop.py` — transcript test cho bốn tình
  huống; **thêm ở cuối file**
- Modify: `apps/api/tests/test_agent_domain_pack.py` — `body_tokens` khớp
  `estimate_tokens`
- Read-only: `apps/api/src/agent/messages.py` — **không sửa**

## Implementation Steps

1. Thêm `body_text` + `body_tokens` vào `DomainPack`. `body_text` dựng bằng cùng
   khuôn `_static_text` của core (`contract.py:115-117`) để hai tầng đọc như một
   tài liệu chứ không như hai định dạng.
2. Thêm cờ vào `_TurnState`, kèm comment cùng giọng với `mode` (`:764`): vì sao
   per-Turn, và vì sao nó dính.
3. Quyết định trước vòng round: mode, rồi lịch sử. Quét lịch sử chỉ **một Turn
   gần nhất**; viết lý do tại chỗ.
4. Trigger tool path: trước `assert_distinct_ids` (`:1058`), so tên call với
   `resolve_toolset(active_pack().toolsets)`. Không hardcode tên tool.
5. `_call`: dán note khi cờ bật, cộng `pack.body_tokens` vào `reserved`; `_construct`
   giữ chỗ cùng số. Hai chỗ phải cùng **một biểu thức**, không phải hai hằng bằng
   nhau: comment tại `:1105-1109` nói thẳng rằng trần dùng để trim và request thật
   sự gửi đi không được phép bất đồng, và hai biểu thức chép tay là cách rẻ nhất
   để chúng bất đồng.
6. Transcript test, dùng `FakeClient` (`tests/test_agent_loop.py:145-163`) và
   `client.requests[n].messages`:
   - hỏi một câu không domain, model không gọi tool domain → body **không xuất
     hiện ở call nào**;
   - model gọi một tool domain ở round 1 → body **không** ở call 1, **có** ở call 2
     và mọi call sau;
   - `mode="signal_desk"` → body ở **call 1**;
   - `history` mang một Turn có call domain → body ở **call 1**;
   - `SIGNAL_DESK_NOTE` vẫn đi kèm ở mode đó — hai message riêng, không gộp.
7. Test ngân sách: `spend.input_tokens` của call mang body lớn hơn call không mang
   đúng khoảng `body_tokens` (±SAI SỐ của estimate), và không call nào vượt
   `TURN_CONTEXT_PER_CALL`.
8. Test "đổi pack không sửa `loop.py`": pack giả có body khác → note đổi theo, và
   `git diff loop.py` giữa hai lần chạy là rỗng (kiểm bằng mắt, ghi vào report).
9. `make test` + `make lint`.

## Success Criteria

- [x] Bốn tình huống transcript đúng như bước 6, mỗi tình huống một test. **Bản
      đầu sai**: trigger lịch sử đọc `TranscriptTurn.tool_calls`, thứ `history_of`
      không bao giờ điền, nên nó chết trong production và test tự dựng shape để
      xanh. Sửa bằng trường `tool_names` (amendment hai file trong `CLAUDE.md`);
      test dựng lại qua `history_of()`, đã chứng minh đỏ được.
- [x] Turn không domain **không có** một ký tự nào của body trong bất kỳ call nào
- [x] Body **dính**: xuất hiện ở mọi call sau khi bật, không chỉ call kế tiếp
- [x] `reserved` cộng `body_tokens`, không cộng `SYSTEM_NOTE_TOKENS`, ở **cả**
      `_construct` lẫn `_call`
- [x] `SIGNAL_DESK_NOTE` không đổi một ký tự và vẫn là message riêng
- [x] `MAX_TOOL_ROUNDS`, `MAX_EXTERNAL_TOOL_CALLS`, `MAX_EMPTY_NUDGES`,
      `plan_segments`, `resolve_tool_surface` **không đổi** — test cũ xanh nguyên
- [x] Không sửa `src/agent/messages.py`. Diff của nó trong cây làm việc là
      dedup URL của C1, xuất hiện **giữa phiên** từ một tiến trình khác trên
      cùng cây — không nhắc `domain`/`pack`/`body_tokens` một lần nào
- [x] Không tên tool domain nào hardcode trong đường nhận pack; tập tên đọc từ
      `resolve_toolset(active_pack().toolsets)`. **Tiêu chí gốc viết sai**: nó đòi
      `grep run_study` = 0, nhưng `CATALOG_TOOL`/`RUN_TOOL` (`loop.py:1980-1981`)
      đã hardcode từ trước C5 cho log "đọc catalog mà không chạy Study" — nợ của
      việc khác, không phải của plan này. Test giữ nó ở **đúng hai dòng**:
      mention thứ ba của bất kỳ tool domain nào là đỏ
- [x] `make test` + `make lint` xanh; năm cổng xanh

## Risk Assessment

**Rủi ro chính: deadlock bootstrap — body không bao giờ nạp.**
Nếu câu *"Hỏi store trước khi hỏi web"* (`sections.py:225-227`) vô tình đi xuống
body ở phase 04, model không được bảo hãy hỏi store → không gọi tool domain →
trigger 3 không bao giờ bật. Hai trigger kia che một phần, nhưng một Turn chat
thường hỏi về một mã sẽ **im lặng mất** playbook.
Tín hiệu: trong artifact/transcript, tỉ lệ Turn gọi tool `signals` giảm.
Phản ứng đã quyết trước: Luật 3 ở `plan.md`, và test bước 6 tình huống hai —
nhưng test đó dùng model giả nên **không** bắt được deadlock thật. Phép kiểm thật
là phase 06 trên corpus. Nếu tỉ lệ giảm: chuyển câu trigger về core, không thêm
trigger thứ tư.

**Rủi ro: giữ chỗ ngân sách sai làm Turn chết giữa đường.**
Tín hiệu: `BudgetRefusal` (`loop.py:972-981`) hoặc `ContextOverflow` tăng.
Phản ứng: hai chỗ giữ chỗ phải là **một biểu thức**; test bước 7 là chỗ bắt.

**Rủi ro: body dán ở đuôi làm model coi nó là chỉ dẫn mới nhất và ưu tiên quá
mức.** Note ở cuối message list có độ nổi cao.
Tín hiệu: Turn domain trả lời máy móc theo playbook, bỏ qua câu hỏi thật.
Phản ứng: body là prose **đã chạy trong prompt hôm nay**, không phải prose mới —
nên rủi ro này là rủi ro *vị trí*, không phải *nội dung*. Nếu quan sát được, đường
xử lý là chuyển sang block thứ hai sau core (đường di trú đã ghi ở §Architecture),
không phải viết lại prose.

**Rủi ro: trigger lịch sử làm mọi Turn của một Thread mang body vĩnh viễn.**
Tín hiệu: tỉ lệ Turn mang body xấp xỉ 100% trên các Thread dài.
Phản ứng: quét **một** Turn gần nhất, đã ghi ở bước 3. Nếu vẫn cao, hạ trigger
lịch sử xuống chỉ áp cho Turn kế tiếp ngay sau một Turn domain — không bỏ hẳn, vì
câu hỏi tiếp nối là chỗ hồi quy dễ nhất.

**Rủi ro: xung đột `loop.py` với C1 phase 04.**
C1 sửa hằng số ở `:293`; C5 sửa `:755-800`, `:929`, `:1058`, `:1105-1117`,
`:1252-1263`. Khác hunk.
Phản ứng: không nhánh nào reflow file; không nhánh nào đổi hằng số của nhánh kia.

## Rollback

`git revert` phase này: cờ, ba trigger và note biến mất; pack vẫn còn body nhưng
không ai đọc — trạng thái đúng bằng cuối phase 04, tức prompt **thiếu** playbook
domain. Nên rollback phase 05 một mình chỉ là bước đầu; bước hai là revert phase
04. Thứ tự bắt buộc **05 trước, 04 sau**, và ghi vào PR.

Rollback nóng không cần deploy: không có cờ cấu hình nào bật/tắt được cơ chế này,
và **cố ý không thêm** — một cờ nữa trong `Settings` là một tổ hợp nữa không ai
test. Nếu vận hành cần tắt nhanh, đường đúng là revert commit.
