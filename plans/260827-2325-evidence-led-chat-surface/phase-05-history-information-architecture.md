---
phase: 5
title: "History information architecture"
status: todo
priority: P1
effort: ""
dependencies: [2]
---

# Phase 05: History information architecture

## Overview

Giải P1 #3: "Sidebar history là một bức tường title ít thông tin". Hơn 14
conversation gần như đồng hạng, title truncate, không ticker, không timestamp,
không active state. Critique gọi chi phí này là "lặp lại hằng ngày".

**Phát hiện đảo scope của phase này:** `agent_thread` **đã có** `title`,
`updated_at` (onupdate), `pinned_at`, và `symbols` ARRAY + index GIN (scout api
§2). Metadata mà critique đòi **đã tồn tại trong DB** — nó chỉ chưa ra tới UI.
Nên phase này **không cần migration**, không cần cột mới, không bị chặn bởi làn
migration. Nó là phase web + một chỗ nới payload API.

Row hiện tại chỉ có dot + title truncate (`sidebar.tsx:301-313`).

## Requirements

Functional:

- Nhóm theo recency: Hôm nay · 7 ngày qua · Cũ hơn.
- Ticker chip trên row khi `symbols` không rỗng.
- Timestamp tương đối trên row.
- Chỉ mở N row đầu mỗi nhóm, còn lại sau "Xem thêm".
- Truy cập full title qua tooltip **accessible** (không phải `title=` thuần).
- Active state rõ cho thread đang mở.
- Nhóm ghim sắp theo `pinned_at`, ẩn khi rỗng.

## Sửa sau red-team (2026-08-28)

Hai điều chỉnh:

**1. Pin/unpin đã hoạt động** (`sidebar.tsx:340-343,382-393`) — bản đầu nói sai là
chưa. Contract là `pinned: bool` (`schemas.py:57`), server tự
`coalesce(pinned_at, now())`. Nên phase này **không** làm pin, và criteria cũ
"unpin = `null`" bị bỏ: nó đòi đổi public contract mà không có lý do.

**2. Ticker chip sẽ trống 100% mọi thread cho tới khi phase 08 xong.** Cơ chế union
`symbols` **đã chạy** (`persistence.py:391-395`, từ `CreateTurnRequest.symbols`)
nhưng lane chat **cố ý gửi rỗng** — `desk-state.tsx:169-170`: *"guessing which
symbols a sentence is about would put a parser in the browser and a wrong answer in
the idempotency payload"*. Lý do đó đúng và không đảo; phase 08 điền `symbols` từ
argument tool call ở **server**.

Nên phase này: code chip đầy đủ + test với dữ liệu giả, và ghi thẳng rằng trên môi
trường thật chip trống tới sau 08. Đây **không** phải lỗi cần sửa ở đây.

Non-functional:

- **Nhóm recency tính ở server**, không ở FE (`plan.md` §Nguyên tắc: FE không giữ
  state phái sinh). FE nhận thread đã gắn nhãn nhóm.
- Danh sách 14+ thread không được gây relayout khi mở "Xem thêm".

## Architecture

**Nhóm ở đâu — và vì sao không ở FE.** Ranh giới "hôm nay" phụ thuộc timezone và
mốc nửa đêm. Nếu FE tính, một tab mở qua nửa đêm sẽ hiện nhóm sai cho tới khi
refresh, và hai client ở hai timezone sẽ thấy hai kết quả. Server tính: response
của `GET /threads` gắn thêm `recencyGroup: "today" | "last_7_days" | "older"`.
FE chỉ gom theo nhãn.

Đây là nới payload, **không** đổi shape phá tương thích — thêm một field. Không
bump version API.

**Ticker chip từ `symbols`.** Cột đã có + GIN index. Row hiện chưa nhận field
này — kiểm `schemas.py` xem `symbols` có trong response `GET /threads` chưa; nếu
chưa thì thêm. Luật hiển thị: tối đa 3 chip, còn lại "+N". `symbols` rỗng →
**không chip nào**, không placeholder (cùng luật với phase 04).

Chip là **mã**, dùng JetBrains Mono theo vai trò font đã ghi ở phase 01. Chip
không phải link ở phase này — biến nó thành lối đi nhanh theo mã là scope của
persona Alex và không thuộc phase này; ghi lại, không làm.

**Timestamp.** `updated_at` đã có `onupdate`. Hiển thị tương đối trong nhóm
(`14:32` cho hôm nay, `Thứ Ba` cho 7 ngày, `26/08` cho cũ hơn) — định dạng khác
nhau theo nhóm, vì trong nhóm "hôm nay" thì ngày là dư thông tin.

**Tooltip accessible.** `title=` thuần không đọc được bằng screen reader ổn định
và không hiện bằng bàn phím. Cần: row có `aria-label` chứa **full title**, cộng
một tooltip hiện khi focus (không chỉ hover). Tooltip dùng `role="tooltip"` +
`aria-describedby`. Nếu shell chưa có primitive tooltip thì tạo một cái nhỏ ở
`primitives.tsx` — đây là primitive thứ hai sau menu, đủ để biện minh.

**"Xem thêm" không được relayout.** Mở thêm row làm danh sách dài ra; nếu nút
"Xem thêm" ở dưới thì nó nhảy. Giữ nút tại chỗ và chèn row **phía trên** nó, và
đặt `scroll-margin` để row mới không đẩy row đang focus ra khỏi khung. N = 7 cho
nhóm đầu, 5 cho các nhóm sau — đủ để critique's "14+ đồng hạng" xuống ≤4 quyết
định thấy được cùng lúc (mục tiêu cognitive load của plan).

**Pin thật.** `pinned_at` là **timestamp, không phải boolean** — nên thread ghim
xếp theo thời điểm ghim, và unpin là set `null`. PATCH đã có (scout api §1) và đã
phân biệt "không gửi" với "gửi null" qua `model_fields_set` — cơ chế đủ, chỉ cần
wire. Nhóm ghim nằm **trên** mọi nhóm recency và không tham gia nhóm recency
(một thread ghim không xuất hiện hai lần).

**Active state.** Thread đang mở: `aria-current="page"` + dấu hiệu thị giác dùng
amber `--primary` (token đã có). Đây cũng vá "Minor Observation" của critique:
"'Trò chuyện mới' lặp ở sidebar và top bar nhưng thiếu active state tương ứng".

## Related Code Files

Modify:

- `apps/api/src/agent/schemas.py` — thêm `recencyGroup` + đảm bảo `symbols`,
  `updatedAt`, `pinnedAt` có trong response `GET /threads`
- `apps/api/src/agent/persistence.py` — query thread list, tính nhóm
  (**không** `service.py` — file đó không giữ query thread)
- `apps/web/src/components/shell/sidebar.tsx:171-353` — `Conversations`, row,
  nhóm, "Xem thêm", pin, active state
- `apps/web/src/components/shell/primitives.tsx` — primitive tooltip
- `apps/web/src/hooks/use-threads.ts` (tên theo scout web §5) — nhận field mới

Create:

- `apps/api/tests/agent/test_thread_recency_group.py`
- `apps/web/src/components/shell/conversations.test.tsx`

## Implementation Steps

1. API: thêm `recencyGroup` vào response. Test biên **trước**: 23:59:59 hôm nay
   vs 00:00:00 hôm sau; đúng 7 ngày vs 7 ngày 1 giây; timezone Asia/Ho_Chi_Minh.
2. Xác nhận `symbols`/`updatedAt`/`pinnedAt` đã ra tới FE; thêm nếu thiếu.
3. FE: gom theo nhãn server, render 3 nhóm. Nhóm rỗng → không render tiêu đề.
4. Row: title + ticker chip (≤3, "+N") + timestamp theo định dạng của nhóm.
5. Primitive tooltip + `aria-label` full title. Kiểm bằng bàn phím, không chỉ
   chuột.
6. "Xem thêm" (7 / 5 / 5), chèn phía trên nút.
7. Pin/unpin qua PATCH; nhóm ghim trên cùng, ẩn khi rỗng, không trùng recency.
8. Active state `aria-current="page"`.
9. Cổng: `make test` + đầy đủ cổng web.

## Success Criteria

- [ ] `recencyGroup` tính ở server; test biên nửa đêm + biên 7 ngày + timezone VN xanh
- [ ] Ba nhóm render đúng; nhóm rỗng không có tiêu đề
- [ ] `symbols` rỗng → zero chip; `symbols` 5 mã → 3 chip + "+2" (test với dữ liệu
      giả — trên môi trường thật chip trống tới sau phase 08, đã ghi ở §Sửa sau
      red-team)
- [ ] Timestamp định dạng khác nhau theo nhóm
- [ ] Full title đọc được bằng **bàn phím** (focus → tooltip hiện + `aria-label`)
- [ ] Mở "Xem thêm" không làm nút dịch chuyển (test đo vị trí trước/sau)
- [ ] Số quyết định thấy được cùng lúc trong sidebar ≤ 7 + 1 nút mỗi nhóm
- [ ] Nhóm ghim sắp theo `pinned_at`; thread ghim **không trùng** trong nhóm
      recency. Pin/unpin đã hoạt động sẵn — phase này không đổi contract
      `pinned: bool`
- [ ] Thread đang mở có `aria-current="page"`
- [ ] `make test` ≥1060 · `pnpm test` xanh

## Risk Assessment

**Nhóm ở server nhưng cache ở client làm nhãn cũ.** Thread nhóm "today" hôm qua
vẫn mang nhãn "today" trong cache sau nửa đêm. Tín hiệu: nhóm sai sau khi để tab
mở qua đêm. Phản ứng đã định: query market/thread list đặt `staleTime` ngắn hơn
khoảng cách tới nửa đêm, hoặc đơn giản hơn — invalidate thread list khi
`GET /market/context` (phase 03) báo `tradingDay` đổi. Chọn cách hai: nó dùng lại
tín hiệu đã có, không thêm timer.

**`symbols` chưa được điền cho thread cũ.** Cột tồn tại không có nghĩa là có dữ
liệu. Nếu thread cũ có `symbols` rỗng thì chip chỉ hiện cho thread mới. Tín hiệu:
query đếm thread có `symbols` rỗng. Phản ứng: **không** backfill ở phase này —
zero chip là trạng thái đúng cho một thread chưa gắn mã. Ai điền `symbols` và khi
nào là câu hỏi của phase 08 (title/metadata tự sinh); ghi liên kết, không lấn.

**Tooltip thành primitive thứ ba phải bảo trì.** Chấp nhận: hai caller đã biết
(full title ở đây, và phase 10 sẽ cần cho evidence). Nếu chỉ một caller thì dùng
`aria-label` + không tooltip.

**Pin không có trần.** 50 thread ghim làm nhóm ghim thành bức tường mới. Phản
ứng: nhóm ghim cũng chịu luật "Xem thêm" với N = 5. Không đặt trần cứng.

Rollback: field API là additive (client cũ bỏ qua); FE revert được độc lập. Không
migration.
