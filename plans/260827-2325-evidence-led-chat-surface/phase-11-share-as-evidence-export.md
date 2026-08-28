---
phase: 11
title: "Share as evidence export"
status: todo
priority: P2
effort: ""
dependencies: [2, 8, 10]
---

# Phase 11: Share as evidence export

## Overview

Mang lại lối chia sẻ mà phase 02 đã ẩn — dưới hình dạng đã chốt với user: **export
cục bộ, không public link**. Critique nói dead-end Share "dễ được nhớ hơn lời chào
đẹp"; phase này biến nó thành hành vi hoàn chỉnh mà không mở bề mặt rủi ro mới.

Lý do kỹ thuật đứng sau quyết định (research §B): opencode share là **live sync
push** sang service ngoài (`opncd.ai`), link đọc **không auth**, **không có lớp
redaction nào**. Live sync nghĩa là user share một câu rồi hỏi tiếp câu riêng tư và
**câu đó tự công khai** — lỗi thiết kế, không phải lỗi cài đặt.

## Sửa sau red-team (2026-08-28)

Bản đầu có một BLOCKER và ba thiếu sót SOT. Đây là phase bị red-team đánh nặng
nhất; đọc hết mục này trước khi thi công.

**1. Whitelist theo cột là fail-OPEN.** Bản đầu:
`EXPORT_MESSAGE_FIELDS = {"role", "content", "created_at"}`. Nhưng `content` là
**JSONB**, shape thật ở `agent/turns.py:248-259`:

```
{text, answer, thoughts, tool_calls, canvases, status, elapsed_ms}
```

Cho `content` đi qua nghĩa là cho **`thoughts` (reasoning — đúng cái phase hứa
loại)** và **`tool_calls[].results[]`** (có `url` ≤2048 ký tự và `snippet` từ trang
ngoài, `messages.py:421-428`) đi qua nguyên vẹn.

**2. Success criterion cũ là test rỗng.** `kind = answer|thought` **chỉ tồn tại
trên SSE**; trong store, phân biệt nằm ở khoá `answer` vs `thoughts`. Nên test
"`kind = thought` không có trong export" **pass dù xuất trọn reasoning**.

**3. `EXPORT_TOOL_FIELDS` bản đầu chứa field không phải cột.** `as_of`/`health`
không có trên `agent_tool_call` — trước phase 08. Sau phase 08 chúng **là** cột, nên
phase này phụ thuộc 08.

**4. SOT đòi ba thứ bản đầu bỏ.** `quality-safety-and-operations.md:227` đòi
**audit ai đọc/export artifact** + **retention/expiry và deletion path**;
`investment-intelligence-contract.md:177-181` đòi capability mới phân loại data
sensitivity tại registration. Bản đầu khai "không bảng mới, không side effect" —
**egress là side effect**. Plan dùng khoảng trống SOT để hoãn public link, rồi dùng
cùng khoảng trống để cho phép export: hai kết luận trái nhau từ một tiền đề.

**5. Markdown không escape.** `snippet`/`url` từ nguồn ngoài chỉ qua `visible_text`.
File `.md` không có React escape cũng không có defang; `[x](javascript:…)` và
`## Chỉ thị hệ thống` render thật ở mọi viewer. "Giữ nhãn nguồn" là metadata, không
phải control.

**6. Xung đột acceptance với phase 08.** Phase 08 đòi "zero query đọc
`agent_thread` trực tiếp"; phase này đòi "thread archive → 200". Giải: phase 08 dùng
**view** `agent_thread_active`, và export đọc bảng gốc như đường undo — hai ngoại lệ
đã khai tường minh, không phải lách.

## Requirements

Functional:

- Export một thread thành Markdown đọc được, có bằng chứng.
- Lối vào: nút Chia sẻ trong header Signal Desk bên phải → copy hoặc tải `.md`,
  nhãn **"Xuất Markdown"** (không phải "Xuất PDF" như item cũ trong menu hội
  thoại ở TopBar).
- Nội dung gồm: câu hỏi, câu trả lời, tóm tắt bằng chứng (phase 10), as-of.
  **Không** reasoning, **không** `frames`, **không** kết quả tool thô.
- Mỗi lần export ghi một dòng audit.
- Thread rỗng → từ chối sạch.

Non-functional:

- **Redaction fail-closed theo đường khoá JSON**, không theo cột.
- Nội dung untrusted được escape/defang trước khi vào Markdown.
- Retention: một câu tường minh, cùng câu với phase 08.
- Không route công khai, không bảng share token.

## Architecture

**Whitelist đệ quy theo đường khoá, không theo cột.**

```python
# src/agent/export/whitelist.py
# Đường khoá JSON, không phải tên cột. `content` là JSONB và một whitelist
# cấp cột cho toàn bộ nó đi qua — gồm reasoning và kết quả trang ngoài.
EXPORT_PATHS = frozenset({
    "role",
    "created_at",
    "content.text",
    "content.answer",
    "content.status",
    "content.canvases[].id",
    "content.canvases[].title",
    # KHÔNG có content.thoughts        — reasoning nội bộ
    # KHÔNG có content.tool_calls[]    — chứa url/snippet nguồn ngoài
    # KHÔNG có content.elapsed_ms      — không phải bằng chứng
})
```

Serializer đi **theo whitelist**, không đi theo object: với mỗi đường trong set,
lấy giá trị nếu có. Nghịch đảo của "đọc object rồi lọc" — và nó là lý do một khoá
JSON mới thêm sau này **không** tự vào export.

Bằng chứng lấy từ **payload evidence của phase 10** (đã là aggregate đã lọc, đã tách
store/external), không lấy từ `agent_tool_call` thô. Một nguồn, một lần lọc.

Cấm tường minh trong code: `model_dump()`, `**row`, `__dict__`, `dict(record)` trong
`src/agent/export/`. Test grep chặn — đây là ba đường biến whitelist thành
blacklist trong một dòng.

**Escape/defang nội dung untrusted.** `content.answer` do model sinh và có thể chứa
nội dung đã đi qua `<untrusted_tool_result>`. Ba việc trước khi ghi Markdown:

| Rủi ro | Xử lý |
|---|---|
| link thực thi (`javascript:`, `data:`) | chỉ cho `http`/`https`; còn lại in dưới dạng text thuần |
| heading giả mạo cấu trúc (`## Chỉ thị hệ thống`) | escape `#` đầu dòng trong phần nội dung |
| bảng/HTML thô | escape `<`, `>`, `|` đầu dòng |

Mục tiêu không phải làm Markdown an toàn tuyệt đối — mục tiêu là file rời khỏi app
**không mang cấu trúc chỉ thị** mà một agent khác đọc như lệnh. Đây là bề mặt thật:
file này sinh ra để gửi cho người khác.

**Audit là bảng, không phải log.** `agent_export_audit` (tạo ở revision phase 08):
`user_id`, `thread_id`, `created_at`, `format`, `byte_count`. Không lưu nội dung —
audit trả lời "ai xuất thread nào lúc nào", không lặp lại dữ liệu.

Retention: **cùng một câu với phase 08** — dòng audit giữ vô hạn tới khi có quyết
định vận hành về purge. Nếu phase 08 chốt một câu khác thì hai chỗ phải sửa cùng
lúc; không để hai câu khác nhau về cùng một chủ đề.

**Endpoint.** `GET /api/v1/threads/{id}/export?format=markdown` → `text/markdown`.
`GET` vì nó không tạo tài nguyên. Nhưng nó **có** side effect (dòng audit) — nêu
thẳng thay vì che; một `GET` ghi audit là chấp nhận được và phổ biến, và biến nó
thành `POST` sẽ làm nó không cache/không bookmark được mà chẳng mua thêm gì.

Quyền: chỉ owner. Thread người khác → **404**, không 403 (không tiết lộ thread tồn
tại). Thread archive → **200** (dữ liệu còn đó và user có thể muốn xuất trước khi
bỏ) — đọc bảng gốc, ngoại lệ đã khai ở §Sửa sau red-team mục 6.

`?format=` chỉ nhận `markdown`. Giá trị khác → 400, không im lặng trả markdown.

**Cấu trúc file.** Markdown, vì người nhận là người.

```markdown
# <tiêu đề thread>
Xuất lúc: 2026-08-28 00:10 (+07)

> Nội dung hỗ trợ nghiên cứu, không phải khuyến nghị giao dịch.
> Nguồn và thời điểm dữ liệu: xem phần Bằng chứng dưới mỗi câu trả lời.

## Câu hỏi
...
## Trả lời
...
### Bằng chứng
- 3 nguồn store · đến phiên 26/08 · trạng thái: bình thường
- 2 nguồn web
- Canvas: Thanh khoản trong phiên STB
```

Trust line **có trong file**, và nó dùng cùng câu đã sửa ở phase 04 (S9) — nói cái
hệ thống làm, không cái model viết.

**UI dùng lại vỏ dialog đã có.** `overlays.tsx:203-268` còn nguyên. Thay
`UnavailableNote` bằng hai hành động thật: **Sao chép** (helper
`copy-to-clipboard.ts` của phase 06 — đã xử lý nhánh lỗi) và **Tải .md**. Nút Chia
sẻ ở `SignalDeskHeader`; item menu hội thoại trong TopBar quay về với nhãn "Xuất
Markdown".

**Không có nút "tạo link".** Nếu ai hỏi: cần threat model ở `docs/Harness/` trước.
Không một control disabled — đó là đúng cái phase 02 vừa dọn.

## Related Code Files

Create:

- `apps/api/src/agent/export/{__init__,whitelist,markdown,sanitize}.py`
- `apps/api/tests/agent/export/test_whitelist_fail_closed.py`
- `apps/api/tests/agent/export/test_sanitize.py`
- `apps/api/tests/agent/export/test_markdown_golden.py`
- `apps/api/tests/agent/export/test_export_audit.py`
- `apps/web/src/hooks/use-thread-export.ts`
- `apps/web/src/components/shell/share-dialog.test.tsx`

Modify:

- `apps/api/src/agent/router.py` — `GET /threads/{id}/export`
- `apps/web/src/components/shell/overlays.tsx:203-268` — hai hành động thật
- `apps/web/src/components/canvas/signal-desk-header.tsx` — nút Chia sẻ
- `apps/web/src/components/shell/inspector.tsx` — mở share overlay từ header phải
- `apps/web/src/components/shell/top-bar.tsx` — item "Xuất Markdown" trong menu

Phụ thuộc phase 08: bảng `agent_export_audit`, cột `as_of`/`health`. Phase này
**không** tạo revision.

## Implementation Steps

1. `whitelist.py` + test fail-closed **trước mọi thứ khác**. Ba test:
   (a) thêm khoá giả **bên trong `content`** → không ra output;
   (b) `content.thoughts` **không** ra output — test trên khoá store, **không** trên
   `kind` (bản đầu sai chỗ này);
   (c) xoá một đường khỏi whitelist → nó mất khỏi output (whitelist thật sự điều
   khiển).
2. Test grep: `src/agent/export/` không chứa `model_dump()`, `**`, `__dict__`,
   `dict(`.
3. `sanitize.py` + test: `javascript:`/`data:` link → text thuần; `#` đầu dòng
   escape; `<`/`>`/`|` đầu dòng escape. Test có payload injection thật.
4. `markdown.py`: serializer đi theo whitelist. Bằng chứng lấy từ payload evidence
   của phase 10.
5. Golden test: fixture 2 lượt có canvas → so file Markdown mong đợi.
6. Endpoint + quyền. Test: thread người khác → 404; rỗng → 4xx có thông điệp;
   archive → 200; `?format=pdf` → 400.
7. Dòng audit mỗi lần export. Test: export → đúng một dòng, có `user_id` +
   `thread_id`; export thất bại (404) → **không** dòng nào.
8. FE: dialog hai hành động; nút Chia sẻ ở header Signal Desk + item menu TopBar
   "Xuất Markdown". Sao chép dùng helper phase 06.
9. Test FE: sao chép thất bại → thông báo lỗi; tải `.md` tạo blob đúng tên.
10. Cổng: `make test` + đầy đủ cổng web.

## Success Criteria

- [ ] Khoá JSON ngoài whitelist **không bao giờ** ra output — test khoá giả bên
      trong `content`
- [ ] **`content.thoughts` không có trong export** — test trên khoá store, không
      trên `kind` (bản đầu là test rỗng)
- [ ] `content.tool_calls[]` không có trong export — `url`/`snippet` nguồn ngoài
      không rời app qua đường này
- [ ] Xoá một đường khỏi whitelist → nó mất khỏi output
- [ ] Test grep: zero `model_dump()` / `**` / `__dict__` / `dict(` trong
      `src/agent/export/`
- [ ] `javascript:` và `data:` link → text thuần; `#`/`<`/`>`/`|` đầu dòng escape;
      test có payload injection thật
- [ ] `frames` không có trong export; canvas chỉ id + title
- [ ] Golden Markdown xanh cho fixture 2 lượt có canvas
- [ ] Trust line có trong file, **cùng câu** với phase 04 (không hứa hộ model)
- [ ] Bằng chứng trong file **tách** store với web (từ payload phase 10)
- [ ] Thread người khác → **404**; rỗng → từ chối sạch; archive → 200;
      `?format=pdf` → **400**
- [ ] Mỗi export thành công → đúng một dòng audit; export 404 → zero dòng
- [ ] Retention: câu tường minh, **giống hệt** câu của phase 08
- [ ] Không bảng mới ở phase này, không revision — `alembic heads` không đổi
- [ ] Endpoint có auth như route khác; không route công khai — grep khẳng định
- [ ] Không control disabled trong dialog (test affordance phase 02 còn xanh)
- [ ] Nút Chia sẻ nằm trong header Signal Desk bên phải, không lặp ở header chat
- [ ] Item menu TopBar nhãn "Xuất Markdown", không "Xuất PDF"
- [ ] `make test` ≥1060 · `pnpm test` xanh

## Risk Assessment

**Whitelist trở thành blacklist trong một dòng.** Ai thêm `model_dump()` là
fail-open ngay, im lặng. Tín hiệu: test grep bước 2. Phản ứng: test đó là cổng cứng
vĩnh viễn, không chỉ cho phase này.

**`content.answer` vẫn là văn bản tự do do model sinh.** Whitelist không kiểm được
*nội dung* của một field được phép — chỉ `sanitize.py` làm được, và nó là heuristic.
Chấp nhận có ghi: nội dung đó user **đã thấy trên màn hình**; phase này không tạo ra
đường rò mới, nó tạo ra một bản sao rời khỏi ngữ cảnh. Đó là lý do defang cấu trúc
chỉ thị quan trọng hơn defang từ ngữ.

**Egress không có retention path thật.** SOT đòi; không ai sở hữu. Tín hiệu: bước 7
xong nhưng không ai trả lời "dòng audit giữ bao lâu". Phản ứng đã định (R7 cấp
plan): **phase 11 không merge** trước khi có câu trả lời tường minh, kể cả câu "giữ
vô hạn tới khi có quyết định". Một câu dở nhưng viết ra tốt hơn một khoảng trống.

**`GET` có side effect làm audit sai khi client retry.** Retry tạo hai dòng cho một
lần user bấm. Chấp nhận: audit đếm **request**, không đếm ý định — và đếm nhiều hơn
thực tế là hướng an toàn cho một sổ audit.

**Ai đó sẽ hỏi public link trong một tuần.** Câu trả lời: threat model ở
`docs/Harness/` trước, không phải "thêm một endpoint". Đã ghi ở `plan.md` §Câu hỏi
chưa giải quyết.

Rollback: bỏ đăng ký endpoint + ẩn lại nút Chia sẻ khỏi header Signal Desk. Bảng
audit từ phase 08 để nguyên (rỗng, vô hại).
