---
phase: 8
title: "Thread lifecycle & titles"
status: todo
priority: P1
effort: ""
dependencies: [5]
---

# Phase 08: Thread lifecycle & titles

## Overview

Phase duy nhất của plan có alembic revision. Nó giải mục **Recovery** của critique
("Undo delete — không mất thread nghiên cứu vì một click") và mục **History** phần
title.

Hiện trạng: `DELETE /threads/{id}` là **hard cascade**, không confirm, không undo,
không toast, không rollback `onError`. Một click mất vĩnh viễn một thread nghiên
cứu.

## Sửa sau red-team (2026-08-28)

Bản đầu sai bốn chỗ và bỏ sót ba. Năm điều chỉnh, đọc trước khi thi công:

**1. `agent_thread` ở `src/alpha/models.py:26`, không ở `src/agent/models.py`.**
File đó **không tồn tại**. Freeze amendment của phase 01 đã sửa theo.

**2. Query thread ở `persistence.py`, không `service.py`.** Sáu đường đọc thật:

| Đường | Vị trí |
|---|---|
| chính | `src/agent/persistence.py:378,429-439,452,485,516,569,620,695-716` |
| ops | `src/agent/ops.py:320-341` |
| admission | `src/core/llm/admission.py:900-902` |
| **memory tool — raw SQL** | `src/agent/tools/memory.py:213-222` |

**3. Lọc archive phải là view Postgres, không helper Python.** `memory.py` là raw
SQL `JOIN agent_thread` để full-text search **nội dung message**; một helper trả
`select()` không dùng được ở đó. Nếu bỏ sót: user xoá thread → ba ngày sau model
trích lại nội dung của nó. Đây là rò rỉ, không phải lỗi hiển thị.

**4. Revision mang bốn nhóm thay đổi, không một.** Vẫn **một** revision —
`alembic heads` xác minh 2026-08-28: một head `e6b3d90c41af` (revision của Study
09a, đã done), nên phase này **hết bị chặn**.

**5. `symbols` đã có cơ chế union đang chạy, nhưng lane chat cố ý gửi rỗng.**
`persistence.py:391-395` union từ `CreateTurnRequest.symbols`; `desk-state.tsx:169-170`
gửi rỗng có chủ ý — *"guessing which symbols a sentence is about would put a parser
in the browser and a wrong answer in the idempotency payload"*. Lý do đó đúng và
không đảo. Nên phase này điền `symbols` **từ argument của tool call ở server**, đi
qua **đúng đường union đã có**, không mở đường thứ hai trong `loop.py`.

## Requirements

Functional:

- Xoá thread là **archive**, hoàn tác được trong một cửa sổ thời gian.
- Thread archive không xuất hiện ở **bất kỳ** đường đọc nào, gồm full-text search
  của memory tool.
- Title tự sinh hai tầng: derived đồng bộ ngay, LLM background.
- Rename của user **không bao giờ** bị title tự sinh ghi đè.
- `symbols` điền từ tool call ở server (nuôi ticker chip của phase 05).
- Revision mở đường cho phase 09 (tier đã dùng), 10 (as-of/health), 11 (audit).

Non-functional:

- Precedence title enforce **trong transaction**, không ở call site.
- Usage title generator vào ledger. Cảnh báo: `OwnerType` chỉ có ba giá trị
  (`admission.py:71-74`) — xem §Architecture.
- Migration additive. `downgrade` drop được.

## Architecture

**Revision: bốn nhóm, một lần.**

| Đối tượng | Thay đổi | Cho phase |
|---|---|---|
| `agent_thread` | `archived_at` timestamptz null · `title_source` text null (`derived\|llm\|user`) · `research_tier` text null | 08, 09 |
| `agent_turn` | tier đã dùng thật (text null) | 09 |
| `agent_tool_call` | `as_of` date null · `health` text null | 10 |
| view `agent_thread_active` | `SELECT * FROM agent_thread WHERE archived_at IS NULL` | 08 |
| `agent_export_audit` (bảng mới) | user_id · thread_id · created_at · format · byte_count | 11 |

`agent_tool_call` **chưa có** `as_of`/`health` (`alpha/models.py:157-205` — chỉ có
`result` JSONB, `outcome`, `status`, `latency_ms`, token counts). Không có hai cột
này thì phase 10 phải parse chúng từ văn bản kết quả tool, và không test nào bắt
được lúc format đổi. User chốt thêm cột.

Lưu ý vận hành đã có: `agent_tool_call` giữ **90 ngày**, cleanup quét theo
`started_at` (`alpha/models.py` §`__table_args__`). Nên evidence summary của phase
10 chỉ đúng trong 90 ngày — ghi vào phase đó.

**View, không helper.** ORM map vào view cho đường đọc; raw SQL của `memory.py`
đổi `JOIN agent_thread` thành `JOIN agent_thread_active`. Một view giải cả bốn
đường đọc bằng một thứ, và nó **không thể** bị bỏ sót bởi một call site mới viết
bằng SQL thô.

Test grep đổi theo: "zero query đọc `agent_thread` trực tiếp, trừ chính định nghĩa
view và đường undo". Undo phải đọc bảng gốc — thread archive không có trong view.

**Undo không cần cơ chế mới.** `PATCH /threads/{id}` đã phân biệt "không gửi field"
với "gửi `null`" qua `model_fields_set`, và **đã kiểm quyền owner**
(`router.py:279`). Nên:

- `DELETE /threads/{id}` → `archived_at = now()`, trả 204 như cũ.
- Undo → `PATCH {archived_at: null}`.

Không endpoint mới. Kiểm quyền có sẵn nghĩa là không ai undo thread của người khác.

**Cửa sổ undo ở FE; và một danh sách "Đã xoá" vì nó gần như miễn phí.** Bản đầu
nói "không thùng rác, chấp nhận". Nhưng view + kiểm quyền owner đã có nghĩa là một
danh sách thread archive chỉ tốn **một filter đảo dấu** trên endpoint list. Với dữ
liệu là nghiên cứu đầu tư, undo 8s là lối duy nhất thì quá mỏng. Nên: toast 8s
**cộng** một lối vào "Đã xoá" trong sidebar (ẩn khi rỗng, cùng luật nhóm ghim).

Server giữ `archived_at` vô hạn — dữ liệu không tự huỷ. Purge thật là quyết định
vận hành riêng, và nó chưa có chủ; nêu ra ở §Risk.

**Cascade: `archived_at` *tắt* cascade, không thay nó.** Bốn FK trỏ `agent_thread`
với `ondelete="CASCADE"` (`alpha/models.py:111,160,344,476`). Khi `DELETE` thành
archive, cascade **không chạy nữa** — message, tool call, turn, artifact đều còn
nguyên. Đó là điều kiện để undo hoạt động, nhưng nó cũng nghĩa là "xoá" không giải
phóng gì. Ghi thẳng vào docstring revision.

**Title hai tầng.** Research đo từ `docs/hermes/`: chờ answer xong mới sinh title
cho p50 **151s**, p90 **1212s**. Hai mươi phút cho một dòng chữ trong sidebar là
không dùng được.

| Tầng | Nguồn | Lúc nào | `title_source` |
|---|---|---|---|
| 1 | cắt ~48 ký tự ở biên từ, từ message đầu của user | đồng bộ, lúc tạo thread | `derived` |
| 2 | LLM, prompt khuôn opencode **+ ràng buộc cùng ngôn ngữ với message user** | background, sau turn đầu | `llm` |
| 3 | user rename | endpoint đã có | `user` |

Ràng buộc ngôn ngữ là thứ opencode không có và lane tiếng Việt cần — một title
tiếng Anh cho thread tiếng Việt là đúng lỗi "Evening" mà phase 04 vừa sửa.

**Precedence trong transaction, không ở call site.** Viết sai phổ biến:
`if thread.title_source != "user": update(...)` — đó là race (hai turn xong cùng
lúc, hoặc user rename giữa lúc job LLM chạy). Đúng: một câu UPDATE có điều kiện.

| Ghi từ | `WHERE title_source` bổ sung |
|---|---|
| derived | `IS NULL` |
| llm | `IN ('derived')` |
| user | không điều kiện |

**Ngân sách title generator — và giới hạn đã biết.** Luật research §C: cộng **cả**
usage phụ vào ledger, không thì envelope $45 đúng trên giấy và sai trong hoá đơn.
Nhưng `OwnerType` chỉ có ba giá trị (`admission.py:71-74`), nên dùng lại owner_id
của turn thì chi phí title **không tách được** khỏi chi phí turn. Hai đường:

- thêm owner type thứ tư — sạch, nhưng đụng `src/core/llm/*` rộng hơn;
- ghi vào owner của turn và **nói rõ** là không tách được.

Chốt: **ghi vào owner của turn ở phase này**, ghi giới hạn vào success criteria, và
mở owner type thứ tư chỉ khi ledger cho thấy title chiếm tỷ lệ đáng kể. Lý do:
mục tiêu là "chi phí không nằm ngoài sổ", và mục tiêu đó đạt được mà không cần
đụng `core/llm`.

Cộng một luật chặn chi phí ngay từ đầu: **chỉ sinh title LLM khi derived title bị
cắt giữa từ hoặc ngắn hơn ngưỡng.** Thread có message đầu rõ ràng thì derived đã
đủ tốt.

**`symbols` từ tool call.** Tool `get_field`/`run_study` nhận `symbol` làm argument;
`agent_tool_call.arguments` là JSONB đã lưu. Sau turn, union các mã **đã thật sự
được đọc** vào `thread.symbols` qua đường `persistence.py:391-395` đã có. Chính xác
hơn regex trên text, và không đặt parser vào browser — đúng lý do
`desk-state.tsx:169-170` từ chối làm ở FE.

## Related Code Files

Create:

- `apps/api/alembic/versions/<rev>_add_thread_lifecycle_and_evidence_columns.py`
- `apps/api/src/agent/thread_title.py`
- `apps/api/tests/agent/test_thread_archive.py`
- `apps/api/tests/agent/test_thread_title_precedence.py`
- `apps/api/tests/agent/test_no_direct_thread_reads.py` — test grep
- `apps/api/tests/agent/test_memory_tool_skips_archived.py`
- `apps/web/src/components/shell/undo-toast.tsx` + test
- `apps/web/src/components/shell/archived-threads.tsx` + test

Modify:

- `apps/api/src/alpha/models.py` — cột mới + view
- `apps/api/src/agent/persistence.py` — mọi query qua view; union `symbols`
- `apps/api/src/agent/ops.py:320-341` — qua view
- `apps/api/src/core/llm/admission.py:900-902` — qua view
- `apps/api/src/agent/tools/memory.py:213-222` — raw SQL join view
- `apps/api/src/agent/{router,schemas}.py` — `DELETE` → archive; `PATCH`
  `archived_at`; list `?archived=true`
- `apps/api/src/agent/loop.py` — title tầng 2; ghi `as_of`/`health` lúc tool trả
- `apps/web/src/components/shell/sidebar.tsx:344-353` — xoá → toast undo
- `apps/web/src/components/shell/top-bar.tsx` — cùng handler (nối ở phase 02)

## Implementation Steps

1. `alembic heads` phải trả **một** dòng. Nếu hai → dừng.
2. **Backup DB** (`pg_dump` vào `backups/`, không commit).
3. Grep **mọi** query `agent_thread`, liệt kê vào PR description. Đối chiếu với
   bảng sáu đường ở §Sửa sau red-team — nếu tìm được đường thứ bảy, ghi thêm.
4. Revision: 3 cột `agent_thread` + 1 cột `agent_turn` + 2 cột `agent_tool_call` +
   view + bảng audit. Docstring ghi: **archive tắt cascade của 4 FK**, và
   `downgrade` làm thread archive **hiện trở lại**.
5. `downgrade -1` → `upgrade head` sạch.
6. Chuyển **cả sáu** đường đọc sang view, gồm raw SQL của `memory.py`. Test grep +
   test memory tool bỏ qua thread archive. **Chưa đổi `DELETE`** — bước này phải
   xanh trước.
7. `DELETE` → archive. `PATCH` nhận `archived_at: null`. Test round-trip.
8. List `?archived=true` + FE "Đã xoá" (ẩn khi rỗng).
9. Title tầng 1 (derived, đồng bộ) + luật "chỉ gọi LLM khi derived bị cắt".
10. Title tầng 2 + ba câu UPDATE có điều kiện. Test race hai thứ tự.
11. Ghi usage title vào ledger của owner turn. Test khẳng định có ghi.
12. Ghi `as_of`/`health` lúc tool trả kết quả (cột cho phase 10).
13. Union `symbols` từ `agent_tool_call.arguments` qua đường đã có.
14. FE toast undo 8s.
15. Cổng: `make test` + đầy đủ cổng web.

## Success Criteria

- [ ] `alembic heads` một dòng trước và sau
- [ ] Backup trong `backups/`, không commit (kiểm `.gitignore`)
- [ ] `downgrade -1` → `upgrade head` sạch; docstring ghi cả hai hệ quả (cascade
      tắt, downgrade un-archive)
- [ ] Test grep: zero query đọc `agent_thread` trực tiếp, trừ định nghĩa view và
      đường undo
- [ ] **Memory tool không trích nội dung thread đã archive** — test riêng, đây là
      rò rỉ chứ không phải lỗi hiển thị
- [ ] Xoá → mất khỏi list; undo → về đúng nhóm recency; thread người khác → không
      undo được
- [ ] Danh sách "Đã xoá" hoạt động, ẩn khi rỗng
- [ ] Test race: user rename thắng LLM **và** thắng derived, ở cả hai thứ tự
- [ ] Title derived có ngay khi thread xuất hiện — không thread "Untitled"
- [ ] Title LLM **chỉ** gọi khi derived bị cắt giữa từ / ngắn hơn ngưỡng — test
      khẳng định thread có message đầu rõ ràng **không** gọi LLM
- [ ] Title LLM cùng ngôn ngữ với message user (test có case tiếng Việt)
- [ ] Usage title có trong ledger. **Ghi rõ giới hạn**: không tách được khỏi chi
      phí turn vì `OwnerType` chỉ có ba giá trị — đây là giới hạn đã biết, không
      phải tiêu chí đạt
- [ ] `as_of`/`health` được ghi vào `agent_tool_call` cho tool đọc store; tool web
      để `null` (nó không có hai giá trị đó)
- [ ] Hỏi 2 mã → `thread.symbols` có đúng 2 mã, không trùng, và đi qua đường union
      đã có (không có đường thứ hai — diff khẳng định)
- [ ] Ticker chip của phase 05 hiện đúng sau phase này
- [ ] Toast undo 8s hoạt động; hết 8s toast biến, thread vẫn archive và vẫn trong
      "Đã xoá"
- [ ] `make test` ≥1060 · `pnpm test` xanh

## Risk Assessment

**Đường đọc thứ bảy chưa ai tìm ra.** Bản đầu tìm được một (`service.py`, và nó
sai); red-team tìm được sáu. Không có gì bảo đảm sáu là hết. Tín hiệu: view giải
được vấn đề này tốt hơn helper — một call site mới viết bằng SQL thô vẫn phải chọn
tên bảng, và test grep bắt tên bảng gốc. Phản ứng: giữ test grep làm cổng cứng
vĩnh viễn, không chỉ cho phase này.

**Revision này chặn ba phase (R3 cấp plan).** 09 cần cột tier, 10 cần as-of/health,
11 cần bảng audit. Sai sót ở đây tốn một revision thứ hai và phá luật single-head
với plan Study. Phản ứng: bước 4 xác nhận danh sách cột với cả ba phase **trước**
khi viết, không sau.

**Archive tắt cascade nên "xoá" không giải phóng gì, và purge không có chủ.** Tín
hiệu: kích thước bảng tăng đơn điệu. Phản ứng đã định: nêu ra ở đây và trong
docstring revision; không tự phát minh retention path ở phase này. Nhưng nếu phase
11 (export) cần một câu về retention thì hai chỗ phải nói cùng một câu.

**Title LLM tốn tiền cho mọi thread.** Luật "chỉ gọi khi derived bị cắt" cài ngay,
không đợi hoá đơn. Tín hiệu: ledger cho thấy tỷ lệ title đáng kể. Phản ứng: siết
ngưỡng, hoặc tắt tầng 2 — nó là tầng cải thiện, không phải tầng bắt buộc.

**`downgrade` làm thread archive hiện trở lại.** Không mất dữ liệu, nhưng mất trạng
thái archive — user thấy thread đã xoá quay về. Ghi vào docstring; người rollback
phải biết.

Rollback: `downgrade -1` drop cột + view + bảng audit. Đọc docstring trước khi
chạy.
