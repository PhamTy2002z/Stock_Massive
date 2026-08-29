# Composer Attachments — phase 01 · 03 · 04 · 05

Plan: `plans/260829-0010-composer-attachments/`. Phase 02 có report riêng
(`phase-02-260829-binary-transport-through-proxy.md`, chạy bởi subagent).

## Phase 01 — Amendment freeze và giải xung đột plan

**Đối chiếu bảng freeze với tứ hợp thật** (success criterion, ghi ra được). Rút
`Related Code Files` của cả mười phase, mọi đường dẫn đều rơi vào một dòng của
bảng:

| Đường dẫn từ phase | Dòng bảng phủ nó |
|---|---|
| `core/llm/{protocol,transport}.py` (03) | dòng 1 |
| `core/llm/config.py` (03, 04) | dòng 2 |
| `core/config.py`, `.env.example` (04) | dòng 3 |
| `agent/messages.py` (03, 07) | dòng 4 |
| `agent/attachments.py` (05) | dòng 5 |
| `agent/{schemas,persistence,turns,router}.py` (01, 05, 07) | dòng 6 |
| `agent/{untrusted,prompt/sections}.py` (06) | dòng 7 |
| `alembic/versions/*` (05) | dòng 8 |
| `main.py` (04) | dòng 9 |
| `scripts/probe_vision.py`, `Makefile` (04) | dòng 10 |
| `apps/api/tests/*`, `apps/web/**/*.test.*` (03–10) | dòng 11 |
| `alpha-desk/[...path]/route.ts`, `lib/alpha.ts` (02) | dòng 12 |
| `components/shell/*`, `components/alpha/message/*`, `hooks/use-live-turn.ts`, `lib/alpha-desk/*` (08–10) | dòng 13 |
| `docs/roadmap.md`, `CLAUDE.md`, `plans/260827-2325-*` (01, 10) | dòng 14 |

`core/llm/probe.py` **không** trong bảng, đúng như plan yêu cầu — cổng vision là
script rời, không phải check thứ sáu của `CapabilityProbe`.

**Một dòng đã thêm lúc thi công phase 05,** đúng thủ tục phase 01 định trước
(dừng → thêm dòng kèm ngày → tiếp), không phải "nới một dòng trong im lặng":

| Surface | Vì sao ngoài bảng |
|---|---|
| `src/alpha/models.py` | model ORM của schema agent sống ở đây, không ở `src/agent/*`. Chỉ thêm `AgentAttachment`, không đụng model nào đang có. `alembic/env.py` **không** cần sửa — nó import từ module này nên `Base.metadata` tự nhận bảng mới. |

**Xung đột `260827-2325/phase-02` — đã hẹp cả hai lớp.**
- Lớp hành động: `:45` từ *"Xoá cả menu + nút Attach"* → *"Xoá các row không có
  handler; giữ menu và nút"*. Citation cũ (`composer.tsx:236-276`, *"7 item"*)
  sửa thành `:382-425`, **sáu** row.
- Lớp contract: assertion a11y *"zero control có `disabled`… mà không có
  `aria-describedby`"* → *"mọi control `disabled` đều được mô tả bằng chương
  trình"*. Success Criteria bỏ dòng *"Không nút Attach, không menu Attach trong
  DOM"*, và dòng grep `disabled` nới đúng cho row mang badge **có**
  `aria-describedby`.
- Lý lẽ cũ giữ nguyên văn, kèm khối *"Đảo tiền đề 2026-08-29"* ngay dưới bảng.
- `blockedBy` hai chiều: `260827-2325/plan.md` giờ khai
  `260829-0010-composer-attachments`; plan này đã có `blocks` từ trước.

**`turns.py`.** Comment `docs/adr/0015: no attachments` viết lại: nửa "không
fetch URL người dùng đưa" còn đúng và giữ; nửa "no attachments" đã bị plan này
đảo, và ghi rõ đính kèm **không** đi qua `MAX_USER_INPUT_BYTES` — Turn trỏ chúng
bằng id, trần nằm ở kho. `MAX_USER_INPUT_BYTES` không đổi.

**Roadmap.** Ghi chú row *"Nghiên cứu sâu"* đặt ở **S2**, không phải S1, vì
"nghiên cứu sâu" là *nhiều bước tổng hợp thành một thesis có `Provenance`* —
đúng Objective của S2; S1 chỉ fan-out Study song song trong một Turn. Ghi rõ nó
khác `260827-2325/phase-09` (control độ sâu của **một** câu trả lời).

`ak plan validate ./plans/260829-0010-composer-attachments` → exit 0.

## Phase 03 — Content part không-text và chi phí token

`ImageContent` là type **riêng**; `ContentSegment` không đổi một dòng nào (bốn
site của nó vẫn là bốn ranh giới cache system prompt).

- `Message.images` + `__post_init__` bắt mỗi ảnh phải được **gọi tên** trong
  `content`. Invariant cũ giữ nguyên nghĩa, chỉ mở rộng phạm vi.
- `as_wire`: có ảnh → `content` **luôn** là list block, kể cả `cache_control` tắt
  (route nhận string thì không có chỗ đặt ảnh). Block ảnh là `image_url` + data
  URI — route là OpenAI Chat Completions, không phải Anthropic Messages.
- `_mark_tail_breakpoints`: đi ngược tìm block **text** cuối thay vì `content[-1]`
  mù; message không có block text nào thì bỏ qua.
- `estimate_tokens` cộng `estimated_tokens` của từng ảnh.

**Chống hồi quy im lặng — hai test riêng như plan đòi:** payload của message text
thuần không đổi, **và** estimate của nó không đổi (`4 + ceil(len/3)` khẳng định
bằng số cụ thể, không so tương đối).

Test đắt nhất là test wire: dựng qua `transport._messages` với
`prompt_cache_control=True` + một message có ảnh, khẳng định marker nằm trên block
**text**. Không phase nào của bản đầu có test này, và unit test của `as_wire` sẽ
xanh trong khi wire thật sai.

## Phase 04 — Cổng vision qua serializer thật

**PASS cả ba lượt.** Số và câu trả lời nguyên văn ở
`plans/reports/probe-260829-vision-route.md`.

| | |
|---|---|
| Chi phí một ảnh 1024×768 | **930 token** (`2207 − 1277`) |
| Phần cố định của request | 347 token |
| `prompt_cache_control` bật | PASS — marker lên block text, route nhận |
| Fork "route không đọc được ảnh" | **không kích hoạt**; 05→10 nguyên phạm vi |

Cờ ở `LLMRoute`, đọc từ `Settings.llm_vision_enabled` qua
`llm_config_from_settings`. **Đính chính một dữ kiện của red-team finding 14:**
câu *"`loop.py` có 0 `get_settings()`"* **sai** — `loop.py:1841` có một lần gọi
(`ASKED_LIMIT` chọn theo `debug`), đã có sẵn trên working tree, không thuộc plan
này. Đúng là: phase 04 thêm **0** lần gọi mới, và cờ vision tới `loop` qua
`config.route.vision` chứ không qua một `get_settings()` đọc giữa loop.
`llm_vision_measured_model` giữ model đã đo; `main.py` log WARNING khi lệch, và
**không** chặn boot (cùng lý lẽ vì sao đây không phải check thứ sáu).
`.env` đã đặt `LLM_VISION_ENABLED=true` (không commit). Thời gian boot không đổi
— script chạy tay, không nằm trong lifespan.

### Bản đầu của script sai, và cách nó lộ ra

Script đầu vẽ bốn chữ số bằng font bitmap 3×5 tự viết. Ảnh hợp lệ, người đọc
được. Model trả *"a plain white rectangular image with no visible objects"* rồi
bịa số — đúng bằng câu nó trả lời khi **không** có ảnh. Nếu chỉ đọc kết quả
FAIL và đi thẳng vào fork, plan đã thu phạm vi 05→10 vì một lỗi của chính phép
đo. Bốn phép thử tách nguyên nhân:

| Nghi phạm | Phép thử | Kết quả |
|---|---|---|
| PNG greyscale | vẽ lại colour type 2 | vẫn "blank white" |
| Encoder tự viết | nạp/lưu lại bằng Pillow | vẫn đọc sai |
| Route không chở ảnh | ảnh một màu ngẫu nhiên | **đọc đúng** |
| Model không đọc chữ | chữ số font thật | **đọc đúng `2662`** |

Script chốt lại dùng ba **dải màu dọc** rút từ sáu màu, tính cả thứ tự — một đáp
án trong 216, và phải đọc được *vị trí* mới đúng thứ tự. Ảnh dựng bằng stdlib:
Pillow **có** trong container nhưng chỉ là dep bắc cầu của matplotlib, không có
trong `requirements.txt`, và một cổng dựa lén vào dep bắc cầu là cổng chết vào
ngày dep đó đổi.

Hệ quả cho phase 06: model đọc **chữ khử răng cưa** chính xác, nên injection qua
screenshot là mối lo có thật, không phải giả định.

## Phase 05 — Kho đính kèm, quota và trần

**Migration.** `alembic heads` đọc lúc thi công → `a3f7e21b8d54`, và nó **đã
applied** (`alembic current` = head), nên `upgrade head` không chạy lại phép xoá
có cổng row-count của nó. Revision mới `b5d1c7e04a83`, parent `a3f7e21b8d54`.
Backup trước: `backups/pre-agent-attachment-260829.sql.gz` (13M, không commit).
`alembic upgrade --sql` render sạch trong container; sau apply `alembic heads`
trả **một** head.

**Một lỗi đã bắt bằng migration thật:** bản đầu khai `user_id` là UUID.
`users.id` là **integer** sequence, và mọi bảng user-scoped khác ở
`alpha/models.py` khai `Integer`. Postgres từ chối FK; đã sửa model + revision.
Nếu chỉ tin `create_all` của test thì lỗi này qua được — điều đáng ghi vì red-team
để claim *"`make test` dựng schema bằng `create_all` nên migration không gặp
test"* ở trạng thái `UNVERIFIED`: **claim đó đúng**,
`tests/test_agent_transport.py:227` gọi `Base.metadata.create_all`.

**Trần — phép tính ghi cạnh hằng số** (`agent/attachments.py`):

```
TURN_INPUT_TOTAL = 100_000   bó trước TURN_CONTEXT_PER_CALL vì 5 × 32_000 = 160_000
MAX_TOOL_ROUNDS + 1 = 5 call, đính kèm cưỡi câu hỏi mới nhất → gửi lại đủ 5 lần
ngân sách ảnh cả Turn = 100_000 − 5 × 12_000 = 40_000
mỗi call                = 40_000 / 5          =  8_000
tại 930 token/ảnh đo được                     =  8 ảnh
```
→ `MAX_IMAGES_PER_TURN = 8`.

**`MAX_IMAGE_PIXELS = 3.38 Mpx`** — không ảnh nào được lấy quá nửa ngân sách ảnh
của một call. Đây là trần **pixel**, không phải byte, vì một PNG nén tốt có thể
nhỏ về byte và khổng lồ về pixel: trần byte không bó nó, và `IMAGE_TOKENS` chỉ
đúng khi kích thước bị bó. Chi phí token tính **theo diện tích**
(`image_tokens_for`) chứ không phải một hằng số cho mọi ảnh — đo năm kích thước
trên route thật, 1,18–1,49 token/kilopixel, các ảnh lớn tụ ở 1,18.

**Đọc bytes, không tin nhãn.** `sniff_image` đọc header PNG/JPEG/WebP lấy cả media
type **và** kích thước pixel. `text/plain` và `text/csv` không có magic byte —
module ghi rõ điều đó và phòng thủ ở đường phục vụ lại thay vì giả vờ sniff được:
`application/octet-stream` + `nosniff` + `Content-Disposition: attachment`. Repo
không có CSP, không có `nosniff` mặc định (`next.config.js` không khai
`headers()`), nên đây là lớp duy nhất.

**`Content-Length` kiểm trước body — và vì sao endpoint không khai body param.**
FastAPI parse body **trước** khi solve dependency, nên với
`file: UploadFile = File(...)` thì form đã spool và validate xong trước khi hàm —
hay bất kỳ `Depends` nào canh nó — kịp từ chối: request vượt trần trả **422 sau
khi đã nhận đủ**. Đã đo: test `content_length` đỏ đúng như vậy trước khi sửa.
Endpoint đọc `request.form()` bằng tay sau khi kiểm header. Giá phải trả: hình
dạng multipart nằm ở docstring thay vì ở schema OpenAPI.

**Rate limit — một điều cần user quyết.** Đã áp `heavy_rate_limit` như plan yêu
cầu. Nhưng nó **key theo IP**, và chính docstring `agent/router.py:33-36` nói sau
proxy Next mọi reader dùng chung một IP — đó là lý do `subscribe` cố ý **không**
dùng nó. Nghĩa là một reader nạp dồn có thể 429 mọi người. Trần thật sự bó
*per-reader* là quota row + byte (key theo `user_id`). Đã ghi cả hai vế vào
docstring endpoint. Xem §Câu hỏi chưa giải quyết.

**Chủ quyền + TTL.** `GET` trả 404 cho cả "của người khác" và "không tồn tại",
bình luận nói rõ đây là chủ ý. `sweep_orphans` xoá đúng hàng
`attached_turn_id IS NULL` quá TTL 24h; test khẳng định nó **không** xoá hàng đã
gắn Turn.

**Vì sao Postgres — ba lý do thật** ghi trong docstring model, và **không** nhắc
`docker compose restart` (tiền đề sai của bản đầu): chủ quyền là một cột đọc qua
cùng owner-scoped join · `pg_dump` đã là quy trình backup · Turn và đính kèm nó
gọi tên commit/rollback cùng nhau.

## Cổng

| Cổng | Kết quả |
|---|---|
| `make test` (`pytest tests/ --ignore=tests/e2e`) | **1479 passed**, 3 deselected |
| `make lint` (apps/api) | pass |
| `alembic heads` | một head `b5d1c7e04a83` |
| `pnpm type-check` `lint` `test` (apps/web) | pass — 750/750 (phase 02) |
| `pnpm build` (apps/web) | pass — `E2E_NEXT_DIST_DIR=.next-verify`, `.next` của dev không bị đụng |

Một test hợp đồng đã bắt lỗi thật và **không** bị nới:
`test_llm_config.py::test_no_source_file_outside_settings_names_a_model` đỏ vì
comment mới ở `protocol.py` nêu tên model đã đo. Sửa comment (trỏ report thay vì
nêu tên), không sửa test.

## Hai lỗi tìm ra lúc nghiệm thu tay, sau khi mọi cổng đã xanh

Cả hai đều ở chỗ unit test cấu trúc không với tới, và đáng ghi vì chúng cùng một
hình dạng: **một mảnh nối giữa hai tầng, mà mỗi tầng tự nó đều đúng.**

### 1. Cờ vision không tới container (vùng phase 04)

`.env` khai `LLM_VISION_ENABLED=true`, `Settings` đọc được, `LLMRoute` mang được
— nhưng `docker-compose.yml` **không forward** biến đó, nên
`docker compose exec api env` trả chuỗi rỗng và `GET /capabilities` trả
`{"vision": false}`. Hệ quả: ảnh nạp được, lưu được, tính token được, và **không
bao giờ tới model** — im lặng hoàn toàn. Chính `docker-compose.yml` đã viết ra
luật bị vi phạm, ba lần trong cùng file: *"a switch that only exists in the
settings class is one a container never sees."*

Phase 04 đặt `.env` rồi dừng ở đó; đúng ra phải kiểm tới biên container. Đã sửa
(forward ở cả `docker-compose.yml` và `docker-compose.prod.yml`) và xác minh:
container giờ trả `LLM_VISION_ENABLED=[true]`.

### 2. Menu đính kèm hiển thị nhưng không bấm được (vùng phase 08–10)

Hai row chạy thật của `AttachMenu` render đúng, đọc là enabled, có handler gắn
đúng — và **mọi cú bấm rơi vào scrim**. `app-shell.tsx` vẽ một
`div.fixed.inset-0.z-[25]` khi overlay mở; scrim là anh em của `main`, còn `main`
là `position: relative; z-index: auto`. Một ancestor đã positioned mà không có
z-index riêng vẫn **sơn như một khối**, nên không gì bên trong `main` vượt được
một anh em z dương của nó — menu nằm dưới scrim dù z-index của nó cao đến đâu.

Đo trên trình duyệt thật: `elementsFromPoint` tại tâm mỗi row trả về scrim đầu
tiên, và nâng composer lên `z-40` **không đổi gì** — chỉ hạ/bỏ scrim mới làm click
tới được nút.

Repo đã biết bệnh này: `components/signal-desk/board-menu.tsx:48-51` ghi đúng nó
(*"the shell's scrim sits above the desk pane… every press would land on the
scrim"*) và vá cục bộ. Bản vá này áp cùng câu trả lời **tại chỗ quyết định
scrim**: overlay `attach` không dựng scrim nữa, nó tự đóng bằng một listener
`pointerdown` ở document — đúng khuôn đã dùng ba lần trong repo
(`sidebar.tsx:330`, `board-menu.tsx:61`, `flag-action.tsx:62`). Press trên chính
trigger được bỏ qua (`aria-expanded="true"`), nếu không click của nó sẽ mở lại
thứ vừa đóng.

**Vì sao 817 unit test không bắt được.** Mọi test của menu này render `Composer`
một mình, nơi scrim của shell không tồn tại. Và jsdom **không có layout**, nên nó
không có hit testing — không đời nào nó nói được pixel người đọc nhắm vào thuộc
control nào. Lưới đúng lớp là e2e: `e2e/composer-attach.spec.ts` dùng
`click({ trial: true })` (chạy đủ kiểm actionability, gồm *receives events*, rồi
dừng trước khi bấm — cần thiết vì cả hai row mở hộp thoại của hệ điều hành).
Đã kiểm ngược: gỡ bản vá thì test đỏ và Playwright nêu đích danh
*"`<div class=\"fixed inset-0 z-[25]\"></div>` intercepts pointer events"*.

Cổng sau bản vá: `pnpm type-check` `lint` pass · `pnpm test` **817 passed** ·
`pnpm build` pass · `pnpm exec playwright test` **8 passed**.

## Câu hỏi chưa giải quyết

1. **Rate limit theo IP trên endpoint nạp — user đã chốt giữ như plan
   (2026-08-29).** `heavy_rate_limit` key theo IP, và sau proxy Next mọi reader
   chung một IP, nên một người nạp dồn có thể 429 cả nhóm. Trần bó *per-reader*
   là quota row + byte theo `user_id`. Caveat ghi trong docstring endpoint. Mở
   lại nếu có lưu lượng thật cho thấy 429 chéo người dùng.
2. **Quota 200 hàng / 200 MB mỗi reader** là con số chọn, không phải suy ra —
   nó chỉ cần lớn hơn `MAX_IMAGES_PER_TURN × số Turn hợp lý mỗi ngày`. Đo lại khi
   có lưu lượng thật.

## Ghi chú build web

`pnpm build` chạy được **không** cần dừng `pnpm dev`: `next.config.js:7` đã có
sẵn `distDir: process.env.E2E_NEXT_DIST_DIR || ".next"` cho đúng việc này. Dùng
`E2E_NEXT_DIST_DIR=.next-verify pnpm build`, rồi xoá thư mục đó. Đã xác nhận dev
server còn sống và `.next` của nó nguyên vẹn sau khi chạy.
