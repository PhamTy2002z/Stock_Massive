---
title: "Composer Attachments"
description: "Menu + của composer thôi là sáu row inert: tệp và ảnh đi thật tới model qua một đường có kế toán token đúng, chụp màn hình đi cùng đường, row nghiên cứu sâu nhận đúng một badge trung thực."
status: done
priority: P2
effort: "10 phase"
tags: [web, api, llm, upload, security, freeze-amendment]
created: 2026-08-29
relatedTo: [260827-2325-evidence-led-chat-surface]
blocks: [260827-2325-evidence-led-chat-surface]
---

# Plan: Composer Attachments

Nguồn quyết định: page feedback trên `/` (2026-08-28) + ba câu trả lời chốt, ghi
ở `plans/reports/brainstorm-260829-0010-composer-attachments.md`.

1. **Tệp + ảnh đầy đủ** (lựa chọn B), không phải chỉ tệp text.
2. **Bỏ "Web search"**, thay bằng **"Chụp màn hình"** chạy thật.
3. **"Nghiên cứu sâu"** là chế độ nhiều bước — *không* làm ở đây; row mang badge
   *Sắp ra mắt* và roadmap nhận một ghi chú ở đúng phase.
4. Row "Tra tin tức thị trường" **gỡ hẳn** (user chốt 2026-08-29 sau khi red-team
   nêu đây là quyết định chưa hỏi — xem §Red Team Review, finding 16).

> **Bản này là bản sau red-team (2026-08-29).** Bốn reviewer, 37 finding thô, 15
> sau dedupe: 6 Critical · 9 High · một chùm Medium. Hai reviewer trả `BLOCKED`.
> Bản đầu sai ở **bốn dữ kiện nền** và chúng được sửa tại chỗ, không giấu. Đọc
> §Red Team Review trước khi tin một câu đối chiếu nào trong plan này.

## Vì sao có plan này

`AttachMenu` (`apps/web/src/components/shell/composer.tsx:382`) có sáu row, cả
sáu `disabled`. Badge *Sắp ra mắt* do `MenuItem` tự vẽ cho mọi row `disabled`
(`shell/primitives.tsx:184-189`), nên hôm nay menu là sáu lời hứa và không một
hành vi nào. Và nó có **0 test** — grep `AttachMenu|Thêm tệp|attachOpen` toàn
`src` + `e2e` trừ `composer.tsx` trả về rỗng.

## Bốn dữ kiện bản đầu ghi sai

Ghi ra đây vì ba trong bốn cái đã đi vào lập luận của nhiều phase.

| Bản đầu viết | Thật |
|---|---|
| *"`admission.py` không đo `len(content)` nên ảnh được đếm tự động — không có lỗ kế toán"* | `estimate_tokens` = `4 + ceil(len(content)/3)` (`messages.py:652-659`) **là** thứ quyết định cái gì vào mỗi call. Placeholder 19 ký tự = 11 token cho một ảnh 1.500-3.000 token. `build_messages` tưởng còn chỗ, không xuống thang giảm, và `loop.py:1311` kết luận *"nothing was given up"* rồi re-raise. Thang phục hồi bị vô hiệu. |
| *"Message người dùng được dựng trong loop"* | `grep Role.USER src/agent/loop.py` → **0**. Nó dựng ở `messages.py:688` trong `_turn_messages`, và `TranscriptTurn` (`:565-580`) không có slot nào cho đính kèm. |
| *"head hiện tại `f8c2d4a96e17`"* | Head thật là `a3f7e21b8d54`, **untracked**, `down_revision = f8c2d4a96e17`. `upgrade()` của nó raise `RuntimeError` nếu `provider_snapshots` có row nhưng khác `{market: 36_528, valuation: 35_245}`. |
| *"thư mục upload sẽ chết mỗi lần `docker compose restart api`"* | `restart` giữ writable layer. Và tiền lệ `agent_artifact.signal_desk_spec` là **JSONB**, không phải nhị phân — repo không có một cột `bytea`/`LargeBinary` nào. |

## Ranh giới freeze — tứ hợp mọi phase

Bản đầu viết bảng bốn surface rồi các phase của chính nó sửa ≥11 file ngoài bảng.
Bảng dưới đây là **tứ hợp** `Related Code Files` của cả mười phase. `probe.py`
đã **bỏ khỏi bảng**: phase 04 lập luận không đụng nó.

| Surface | Giới hạn |
|---|---|
| `src/core/llm/{protocol,transport}.py` | thêm một content part không-text + cho `_mark_tail_breakpoints` bỏ qua block không-text; **không** đổi luật cache, không đổi giá |
| `src/core/llm/config.py` | nơi cờ vision thuộc về (`LLMRoute`), cùng chỗ `prompt_cache_control` đang ở |
| `src/core/config.py` · `.env.example` | một cờ `llm_vision_enabled`, mặc định `False` |
| `src/agent/messages.py` | `TranscriptTurn` mang đính kèm · `_turn_messages` là chỗ tiêm · `estimate_tokens` tính chi phí segment |
| `src/agent/attachments.py` (mới) + router upload | nhận-lưu-đọc + quota; không xử lý ảnh, không thumbnail server-side |
| `src/agent/{schemas,persistence,turns,router}.py` | đính kèm vào payload Turn + `history_of`; không đổi luật idempotency đã có |
| `src/agent/{untrusted,prompt/sections}.py` | một lối bọc theo nguồn + một câu prompt + bump `PROMPT_VERSION` |
| `alembic/versions/*` (revision mới) | chỉ thêm; parent đọc lúc thi công, không hardcode |
| `src/main.py` | đúng một dòng log cảnh báo khi model lệch model đã đo vision |
| `apps/api/scripts/*` · `Makefile` | script đo vision |
| `apps/api/tests/*` · `apps/web/src/**/*.test.*` | test cho mọi phase trên |
| `apps/web/src/app/api/alpha-desk/[...path]/route.ts` · `src/lib/alpha.ts` | một đường nhị phân; không đổi luật auth/retry |
| `apps/web/src/components/shell/*` · `components/alpha/message/*` · `hooks/use-live-turn.ts` · `lib/alpha-desk/*` | UI đính kèm; không đụng `SignalDeskToggle` |
| `docs/roadmap.md` · `CLAUDE.md` · `plans/260827-2325-*` | ghi chú + giải xung đột |
| `src/alpha/models.py` | **thêm 2026-08-29 lúc thi công phase 05** — bảng ORM sống ở đây, không ở `src/agent/*`; chỉ thêm `AgentAttachment` |

Phase 01 ghi bảng này vào CLAUDE.md **trước** dòng code đầu tiên, và có một
success criterion đối chiếu bảng với tứ hợp thật.

## Xung đột plan — hai lớp, không phải một

`plans/260827-2325-evidence-led-chat-surface/phase-02` (còn `pending`) dự định
xoá cả `AttachMenu` + nút Attach (`:45`), lý lẽ: *"Không item nào có handler ở
bất kỳ đâu"*.

Lớp thứ hai, bản đầu bỏ sót và mới là chỗ đụng thật: phase-02 đó **mandate một
test** ở `:100-102` khẳng định *"zero control có `disabled` hoặc `aria-disabled`
mà không có `aria-describedby` giải thích"*, và Success Criteria `:118-129` đòi
*"không còn 'sắp ra mắt'"* + *"Không menu Attach trong DOM"*. Plan này giữ **bốn**
row `disabled` mang badge, và `MenuItem` vẽ badge là một `<span>` trần không `id`,
không `aria-describedby`. Plan nào chạy sau cũng đỏ.

Phase 01 giải cả hai lớp; phase 10 làm phần code để contract đã hẹp thật sự
thoả được.

## Nguyên tắc xuyên suốt

- **Ảnh phải nhìn thấy được với `estimate_tokens`.** Đây là bài học đắt nhất của
  red-team: mọi trần, mọi thang giảm, mọi refusal trước call đều đọc con số đó.
  Một ảnh tốn 11 token trên giấy là một ảnh không có trần nào.
- **Một content part riêng, không nhồi `ContentSegment`.** Nó có đúng 4 site,
  **cả bốn là ranh giới cache system prompt** (`probe.py:294-295`,
  `messages.py:678-679`), và docstring `:204-218` nói nó tồn tại cho System Prompt
  Contract. Nhồi ảnh vào làm một frozen type mang hai nghĩa và `__post_init__`
  mang hai luật.
- **`untrusted.py` là invariant đóng nhờ registration** — *"an undeclared one
  reads as external"* (`:11-28`). Đường đính kèm không có registration, nên nếu
  không mở một lối vào theo nguồn thì nó fail-**open**. Và `MIN_WRAP_CHARS = 32`
  (`:48`, `:89`) nghĩa một dòng 28 ký tự đi không có bọc.
- **Route là OpenAI Chat Completions**, không phải Anthropic Messages
  (`protocol.py:248-296`), qua cliproxy `:8317/v1`. Block ảnh là `image_url`.
- **Cổng đo phải đo đúng payload production gửi.** Tiền lệ ở chính repo:
  `JsonSchemaFormat` (`protocol.py:298-305`) ghi *"a gateway was measured silently
  dropping `response_format`"*.
- **Đính kèm là bất biến**; mở lại thread là đọc lại hàng đã lưu.
- **Người dùng thấy trước khi gửi** — với chụp màn hình đây là yêu cầu, không
  phải điểm hoàn thiện.
- Trước migration: backup DB (`pg_dump` vào `backups/`, không commit), và **đọc
  `alembic heads` lúc thi công**, không tin số trong plan. Cụ thể lúc viết: branch
  `feat/study-canvas-runtime` mang `a3f7e21b8d54` **chưa commit**, và `upgrade()`
  của nó raise `RuntimeError` nếu `provider_snapshots` có row nhưng khác
  `{market: 36_528, valuation: 35_245}` — ai chạy phase 05 gặp nó **trước**
  migration của mình.

## Phases

| # | Phase | Vùng | Dep | Trạng thái |
|---|-------|------|-----|------------|
| 01 | [Amendment freeze và giải xung đột plan](./phase-01-freeze-amendment-and-plan-reconciliation.md) | docs | — | done |
| 02 | [Đường nhị phân qua proxy](./phase-02-binary-transport-through-proxy.md) | web | 01 | done |
| 03 | [Content part không-text và chi phí token](./phase-03-non-text-content-part-and-token-cost.md) | api | 01 | done |
| 04 | [Cổng vision qua serializer thật](./phase-04-vision-gate-through-real-serializer.md) | api | 03 | done |
| 05 | [Kho đính kèm, quota và trần](./phase-05-attachment-store-and-quota.md) | api + db | 02, 04 | done |
| 06 | [Ranh giới tin cậy cho nội dung nạp](./phase-06-trust-boundary-for-uploads.md) | api | 01 | **done** |
| 07 | [Turn mang đính kèm, thread vẽ lại](./phase-07-turn-carries-attachments.md) | api | 03, 05, 06 | **done** |
| 08 | [UI đính kèm tệp và ảnh](./phase-08-web-attach-ui.md) | web | 07 | **done** |
| 09 | [Chụp màn hình](./phase-09-screen-capture.md) | web | 08 | **done** |
| 10 | [Hình dạng cuối của menu và a11y](./phase-10-menu-final-shape-and-a11y.md) | web + docs | 09 | **done** |

Phase 04 là **cổng chặn** và giờ đứng **sau** 03, vì một cổng đo payload thô
không chứng minh gì về payload `as_wire` sinh ra. Fork khi route không đọc được
ảnh nằm trong phase 04.

## Đã làm trước plan này

Lỗ hổng `mode` — `createTurn` không gửi `mode` nên mọi Turn chạy `chat` ở backend
và công tắc Signal Desk chỉ đảo layout — **đã sửa 2026-08-29**: `api.ts` gửi
`mode`, `use-live-turn.ts` + `desk-state.tsx` truyền `signalDesk`, 3 test mới.
Cùng lúc `active_symbol` — key web gửi mà không schema nào khai — được bỏ gửi
thay vì khai thêm: cả `RuntimeContext` (*"the complete set of what may be
injected, and nothing else"*) và `ToolContext.symbol` (phải `None` ở lane chat)
đều tự khai là đóng.

## Success Criteria

- [x] Một message có ảnh cho `estimate_tokens` **lớn hơn** placeholder của nó, và trong một hệ số đã nêu so với `usage.input_tokens` route trả về
- [x] `vision_input` pass **qua `Message`/`as_wire` thật**, với `prompt_cache_control` cả tắt và bật — 3/3 lượt PASS, `plans/reports/probe-260829-vision-route.md`; fork không kích hoạt
- [x] Nạp một ảnh qua UI → model mô tả được nội dung ảnh
- [x] `GET /attachments/{id}` trả bytes **không hỏng** qua proxy Next — SHA-256 khớp cả hai chiều trên bản production thật, `e2e/composer-attach.spec.ts::an attachment survives the Next proxy byte for byte`
- [x] Một ảnh chứa dòng chữ chỉ thị không đổi được hành vi model; một giá chỉ xuất hiện trong ảnh không được nêu mà không qua `check_price_claim`
- [x] Một tệp `text/plain` 28 ký tự vẫn được bọc (không lọt `MIN_WRAP_CHARS`)
- [x] Quota per-user (số hàng + tổng bytes) từ chối được vòng lặp nạp; hàng không gắn Turn có TTL — `tests/test_agent_attachments.py::TestQuota` (429 `attachment_quota_rows` / `attachment_quota_bytes`) và `::TestSweep`
- [x] Retry và resend một Turn có ảnh gửi lại đúng danh sách đính kèm
- [x] Thread nhiều lượt: ảnh của lượt trước **không** được gửi lại ở lượt sau
- [x] Mở lại thread cũ vẽ lại đính kèm, không gọi model
- [x] Chụp màn hình có bước xem trước và có huỷ
- [x] `AttachMenu` có test đầu tiên: đúng bốn row mang badge, hai row không, mọi row disabled có `aria-describedby`
- [x] `alembic heads` một head sau migration; parent đọc lúc thi công
- [x] `docs/roadmap.md` có ghi chú UI ở đúng phase Track S
- [x] `260827-2325/phase-02` đã hẹp cả bảng hành động **và** Success Criteria **và** contract test a11y, kèm khối đảo tiền đề giữ nguyên văn lý lẽ cũ
- [x] `make test` · `pnpm type-check` `lint` `test` `build` pass

## Red Team Review

### Session — 2026-08-29

**Findings:** 16 (16 accepted, 0 rejected) · 37 thô trước dedupe
**Severity:** 6 Critical · 9 High · 1 chùm Medium
**Reviewer:** Security Adversary (Fact Checker) · Failure Mode Analyst (Flow
Tracer) · Assumption Destroyer (Scope Auditor) · Scope & Complexity Critic
(Contract Verifier). Hai trả `BLOCKED`.

| # | Finding | Sev | Disposition | Áp vào |
|---|---|---|---|---|
| 1 | `estimate_tokens` đo `len(content)` và là thứ quyết định context; ảnh vô hình với mọi trần trước call, thang phục hồi bị vô hiệu | Critical | Accept | 03, 05 |
| 2 | Proxy Next không chở được nhị phân: allowlist · `request.text()` · `Content-Type` hardcode · `passthrough` chỉ `assets`; thêm `lib/alpha.ts` | Critical | Accept | 02 |
| 3 | Head alembic sai; head thật `a3f7e21b8d54` untracked và `upgrade()` raise theo row count | Critical | Accept | 01, 05 |
| 4 | Message người dùng dựng ở `messages.py:688`, không phải loop; `TranscriptTurn` không có slot; purity contract | Critical | Accept | 07 |
| 5 | Bảng freeze không phủ ≥11 file chính plan sửa; lại mở `probe.py` không ai đụng | Critical | Accept | plan.md, 01 |
| 6 | Giải xung đột plan bỏ sót Success Criteria `:118-129` và contract test a11y `:100-102` | Critical | Accept | 01, 10 |
| 7 | Injection qua ảnh; `untrusted.py` fail-open vì không registration; `MIN_WRAP_CHARS` bypass; thiếu bump `PROMPT_VERSION`; ảnh lách `check_price_claim` | High | Accept | 06 |
| 8 | Upload không rate limit, không quota, không ingress cap, GC bị đẩy sang "chưa giải quyết" | High | Accept | 05 |
| 9 | `transport.py:506-509` dập `cache_control` lên block cuối = block ảnh; tín hiệu đã ghi không nổ | High | Accept | 03 |
| 10 | `history_of` bỏ đính kèm lượt trước; chiều ngược là gửi lại n ảnh ở lượt n | High | Accept | 07 |
| 11 | Retry/resend mất đính kèm; 4 call site không phải 3; `signalDesk` không phải phép so sánh hợp lệ | High | Accept | 08 |
| 12 | Cổng vision đo payload thô, không đo `as_wire`; `_cached_result` không key theo model nên drift không fail-closed | High | Accept | 04 |
| 13 | Phase 04 cũ khai dep sai; số học `100_000/4` sai — `MAX_TOOL_ROUNDS+1` = 5 call, và `TURN_INPUT_TOTAL` bó trước | High | Accept | 05 |
| 14 | Cờ vision không có chủ (`loop.py` có 0 `get_settings()`); `ContentSegment` bị chở hai việc | High | Accept | 03, 04 |
| 15 | Đường tệp text lách trần 8 KiB được ép hai chỗ có chủ ý | High | Accept | 06, 07 |
| 16 | Chùm Medium: tiền đề Docker + tiền lệ JSONB sai · `AttachMenu` 0 test · badge ở `:184-189` không phải `:158-164` · `turns.py:81` ghi `docs/adr/0015: no attachments` · `text/csv` không sniff được + repo không có `nosniff`/CSP · `⌘U` không có nhà · kéo-thả/dán là scope tự thêm · pending id không vào `writeDeskSession` · **gỡ row tin tức là quyết định chưa hỏi** | Medium | Accept — user chốt gỡ row 2026-08-29 | 01, 05, 08, 10 |

**Không nhận:** claim rằng `make test` dựng schema bằng `create_all` nên migration
không gặp test — grep `tests/conftest.py` không xác nhận được. Để `UNVERIFIED`;
phase 05 vẫn đổi cổng migration sang `alembic upgrade --sql` vì lý do độc lập.

### Whole-Plan Consistency Sweep

Delta đã lan khắp plan sau khi áp 16 finding:

- **Kế toán token**: câu *"không có lỗ kế toán"* đã **xoá** khỏi `plan.md` và khỏi
  report brainstorm; thay bằng bảng "Bốn dữ kiện bản đầu ghi sai" ở trên và bằng
  bước `estimate_tokens` trong phase 03. Không còn chỗ nào trong plan nói ledger
  tự đếm ảnh.
- **Chỗ tiêm**: mọi câu chỉ `loop.py` là chỗ dựng message đã đổi sang
  `messages.py::_turn_messages` + `TranscriptTurn`. Phase 07 giữ luật "ảnh chỉ ở
  lượt mới nhất" như một **thuộc tính của snapshot**, nên purity của
  `build_messages` còn nguyên.
- **Số học trần**: mọi chỗ ghi "4 vòng" đổi sang **5 call**
  (`MAX_TOOL_ROUNDS + 1`), và `TURN_INPUT_TOTAL` được nêu là ràng buộc bó trước.
- **Head alembic**: mọi hardcode `f8c2d4a96e17` đã bỏ; phase 05 đọc `alembic heads`
  lúc thi công và khai phụ thuộc vào `a3f7e21b8d54`.
- **Citation badge**: `primitives.tsx:158-164` → `:184-189` ở `plan.md`, phase 10,
  và ở report brainstorm.
- **Thứ tự phase**: 8 phase → 10; cổng vision từ #2 xuống #4; proxy tách thành #2;
  ranh giới tin cậy tách thành #6.
- **`probe.py`** rời bảng freeze vì không phase nào sửa nó.
- **Câu hỏi chưa giải quyết**: #1 (GC) và #2 (nhãn tin cậy) đã **thăng lên** thành
  bước bắt buộc của phase 05 và 06, nên không còn là câu hỏi mở.

Không còn mâu thuẫn chưa giải.

## Câu hỏi chưa giải quyết

1. **Đường FE đọc cờ vision.** Phase 08 để mở giữa "thêm trường vào một endpoint
   hiện có" và "một endpoint năng lực nhỏ". Quyết định lúc làm, sau khi đọc
   `GET /usage`.
2. **Trần bytes cuối cùng** là công thức, chưa là hằng số — chỉ chốt được sau
   report của phase 04.
3. **Ảnh của lượt trước có nên gửi lại khi người đọc hỏi tiếp về nó.** Phase 07
   chốt "không" để trần khỏi vỡ, và ghi rõ hệ quả: model mất pixel sau một lượt.
   Nếu chất lượng trả lời sụt rõ, đây là chỗ cần đo lại — không phải chỗ nới trần.

## Còn treo sau khi mười phase đóng — 2026-08-29

Ba việc, không việc nào chặn contract của plan này.

1. **Câu trả lời không hiện trong transcript ở lượt nghiệm thu tay.** Turn chạy
   xong 44s, `agent_message` của assistant có đủ `answer` trong DB (đọc thẳng bằng
   `psql`, và nội dung đúng — xem §Nghiệm thu tay của phase 06), nhưng khung chat
   để trống dưới dòng *"Đã làm việc trong 44s"*. `textOf` và `assistantView` không
   bị đụng ở plan này (đã kiểm lại nguyên văn). Một session khác đang cầm việc này
   (user chốt 2026-08-29). Nó là vấn đề **render**, không phải đường đính kèm: đính
   kèm đã chứng minh xong ở cùng lượt đó.

2. **Luồng `getDisplayMedia` chưa bấm tay.** Nó mở hộp thoại chọn cửa sổ của chính
   trình duyệt, không tự động hoá được. Phần *sau* hộp thoại — xem trước, chấp nhận,
   thành chip — đi chung đường ống với ảnh nạp tay, và đường đó đã nghiệm thu.

3. **Bốn tiêu chí còn `[ ]` thuộc phase 01–05**, không phải phần này: cổng vision
   qua `as_wire` (04) · byte-for-byte của `GET /attachments/{id}` qua proxy (02) ·
   quota + TTL (05) · giải xung đột `260827-2325/phase-02` (01). Session làm 01–05
   báo cả bốn đã xong; tôi để nguyên ô chưa tick vì không tự kiểm chúng.

   Hai ô vừa tick là hai ô tôi **có** kiểm ở đây: `estimate_tokens` cho một message
   mang ảnh là **940** so với **10** của riêng placeholder (`930` là chi phí ảnh khai
   ra, đúng bằng thứ mọi trần đọc); `alembic heads` một head `b5d1c7e04a83`.

   Về byte-for-byte: chiều **lên** đã đo — file nạp qua proxy Next vào store khớp
   md5 `33301c5b1bbebbc271a11fa5fc407b29`, 18.731 byte, y hệt file gốc. Chiều
   **xuống** thì thumbnail trong transcript vẽ được từ `attachmentUrl()` — tức
   `GET /attachments/{id}` qua proxy trả ảnh đọc được — nhưng đó là bằng chứng nhìn,
   không phải phép so byte, nên ô vẫn để trống cho test của phase 02.

4. **Đường bàn phím chưa đi hết** (mở menu → row 1 → picker → chip → nút bỏ).
   `aria-describedby` và trạng thái `disabled` có test; thứ chưa làm là một lượt Tab
   thật.
