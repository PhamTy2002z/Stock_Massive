---
phase: 4
title: "Research launchpad empty state"
status: todo
priority: P1
effort: ""
dependencies: [2, 3]
---

# Phase 04: Research launchpad empty state

## Overview

Giải hai P1 cùng lúc: #1 "Empty state không biểu đạt lợi thế evidence-led" và #4
"Reassurance cho tác vụ tài chính đến quá muộn". Đây là phase kéo heuristic thấp
nhất của critique — **Help & Documentation 1/10** — lên mức dùng được, và là phase
quyết định điểm Design Specificity ("UI có bản sắc ở lớp thị giác, nhưng generic
ở lớp trải nghiệm").

Hiện `view-chat.tsx:306-317` render đúng hai thứ khi chưa có thread: `Greeting` +
`Composer variant="opening"`. Không starter, không trust line, không trạng thái
dữ liệu.

## Requirements

Functional:

- Lời chào tiếng Việt tự nhiên. Xoá sạch chuỗi tiếng Anh.
- 4 starter **theo tác vụ nghiên cứu**, không theo feature. Mỗi cái kèm mô tả
  output rất ngắn.
- Một trust line dưới composer nêu: nguồn · thời điểm dữ liệu · giới hạn vai trò.
- Chip session + độ mới dữ liệu, lấy từ `GET /market/context` (phase 03).
- Cụm mở đầu nằm **cao hơn** optical center.
- Toàn bộ launchpad collapse khi conversation bắt đầu.

Non-functional:

- Endpoint context lỗi hoặc trả `null` → chip **không render**, empty state vẫn
  dùng được bình thường. Không skeleton vĩnh viễn, không placeholder.
- Starter là câu hỏi thật gửi vào lane, không phải template điền chỗ trống.

## Architecture

**Lời chào.** `lib/greeting.ts:42-67` có 3 nhóm × 6 dòng, **hardcode tiếng Anh**
("Evening"), giờ VN lấy từ `market-session.ts:134-139`. Critique gọi đây là
"Orientation valley: 'Evening' phá Vietnamese-first flow". Viết lại toàn bộ bảng
chuỗi sang tiếng Việt tự nhiên ("Chào buổi tối" chứ không phải "Buổi tối"). Giữ
nguyên cơ chế 3 nhóm theo giờ — nó đúng, chỉ chuỗi sai. Xoá docstring stale
(`:38-40`, đã ghi ở phase 01).

**Bốn starter — nội dung là quyết định sản phẩm, không phải copy.** Critique đề
xuất bốn tác vụ; giữ nguyên bốn cái đó vì chúng map đúng vào capability thật của
12 tool đang có:

| Starter | Tool thật đứng sau | Mô tả output |
|---|---|---|
| Tóm tắt thị trường hôm nay | `get_field` trên tập `market` + `get_series` | nguồn · thời điểm · rủi ro |
| Phân tích luận điểm cho một mã | `get_field`, `run_study` | bằng chứng · độ chắc chắn · điều kiện vô hiệu |
| So sánh hai mã | `get_field` ×2, `render_canvas` | hai cột số · nguồn · chênh lệch |
| Tìm yếu tố có thể phủ định luận điểm | `get_field`, `list_studies` | falsifier · ngưỡng · điều cần theo dõi |

Bốn cái này **phải kiểm được là gửi được thật**. Test: click từng starter →
`POST /threads/{id}/turns` được gọi với đúng nội dung. Một starter dẫn tới refusal
là thất bại của phase này, không phải của model.

Starter thứ hai và thứ ba cần một mã. Không mở form điền — starter gửi câu hỏi
để lane tự hỏi lại mã, hoặc dùng một mã trong Universe làm ví dụ tường minh
("Phân tích luận điểm cho HPG"). **Chốt: dùng mã tường minh.** Một câu hỏi gửi
được ngay tốt hơn một form; và nó dạy user cú pháp bằng ví dụ, đúng mục
"Recognition rather than recall".

**Trust line — sửa sau red-team, không dùng nguyên văn critique.** Câu critique đề
xuất ("Câu trả lời nêu **nguồn**…") hứa hộ model điều prompt **cấm**:
`prompt/sections.py:239` — *"Tra rồi thì nêu thời điểm, **đừng nêu nguồn**"*;
`:363` — *"**Không viết phần dẫn nguồn**… Việc đó là của giao diện"*. Uncertainty
cũng là có điều kiện (`:367`), không phải luôn luôn.

Nên trust line nói cái **hệ thống** làm, không cái model viết:

> Nguồn và thời điểm dữ liệu hiện ở tab Nguồn cạnh mỗi câu trả lời. Nội dung hỗ
> trợ nghiên cứu, không phải khuyến nghị giao dịch.

Câu này đúng với cả `prompt/sections.py` và output contract
(`investment-intelligence-contract.md:156`, nơi as-of/freshness là nghĩa vụ của
**outcome**, và phase 10 là chỗ giao nó). Phase 12 thêm một test đối chiếu trust
line với prompt contract để hai chỗ không lệch nữa. Phase 11 dùng **cùng câu** này
trong file export.

Đặt **dưới** composer mở đầu, cỡ `meta`, ink bậc thấp. Nó không được cạnh tranh
với composer về thị giác — nó là điều kiện, không phải lời mời.

**Chip market context.** Một hook mới `use-market-context.ts` gọi phase 03.
Ba luật cứng:

1. `isLoading` → **render gì cũng không** (không skeleton). Empty state xuất hiện
   trong <100ms; một chip nhảy vào sau 300ms tốt hơn một ô xám nhấp nháy.
2. `error` hoặc `data == null` → không render. Không toast, không retry banner —
   đây là thông tin phụ trợ, hỏng thì im lặng.
3. Nhánh `null` trong payload → bỏ đúng dòng đó, giữ các dòng còn lại.

Nội dung chip: trạng thái phiên + độ mới. `sessionsBehind == 0` → "dữ liệu đến
phiên 26/08"; `> 0` → "trễ 3 phiên" kèm tone cảnh báo. Không bao giờ hiện một
badge màu mà không có số đứng sau.

**Vị trí dọc.** Cụm hiện căn giữa. Đẩy lên: `justify-content` với offset âm
khoảng 8% chiều cao viewport, hoặc grid với hàng trên nhỏ hơn hàng dưới. Phải
kiểm ở chiều cao thấp (768px) rằng cụm **không** bị cắt và không tạo scroll.

**Collapse.** Khi `messages.length > 0`, starter + trust line không render. Chip
market context **giữ lại** — nó chuyển lên TopBar (hoặc giữ nguyên chỗ) vì độ mới
dữ liệu liên quan tới mọi câu trả lời, không chỉ câu đầu. Chốt: chip di chuyển
lên TopBar khi có thread.

## Related Code Files

Modify:

- `apps/web/src/lib/greeting.ts` — bảng chuỗi sang tiếng Việt, xoá docstring stale
- `apps/web/src/components/shell/view-chat.tsx:306-317` — cụm empty state
- `apps/web/src/components/shell/top-bar.tsx` — nhận chip khi có thread
- `apps/web/src/lib/query-keys.ts` — khoá cho market context

Create:

- `apps/web/src/hooks/use-market-context.ts`
- `apps/web/src/components/shell/launchpad.tsx` — starter + trust line
- `apps/web/src/components/shell/market-context-chip.tsx`
- `apps/web/src/components/shell/launchpad.test.tsx`
- `apps/web/src/components/shell/market-context-chip.test.tsx`

## Implementation Steps

1. Viết lại `greeting.ts` sang tiếng Việt; cập nhật test hiện có nếu nó assert
   chuỗi Anh.
2. `use-market-context.ts` + `market-context-chip.tsx`. Test **ba nhánh xấu
   trước** (loading, error, null) rồi mới nhánh tốt — đây là acceptance #2 của
   plan và dễ bị bỏ nếu làm sau.
3. `launchpad.tsx`: 4 starter + trust line. Starter là button thật, mỗi cái có
   accessible name tiếng Việt, hit area theo luật phase 01.
4. Ghép vào `view-chat.tsx`, đẩy cụm lên trên optical center.
5. Collapse: starter/trust line ẩn khi có message; chip chuyển lên TopBar.
6. Test: click từng starter → mutation gửi turn với đúng nội dung; ở 768px cao
   không có scroll dọc ở empty state.
7. Cổng đầy đủ web + đo bundle.

## Success Criteria

- [ ] Grep `greeting.ts` và empty state: không còn chuỗi tiếng Anh
- [ ] 4 starter, mỗi cái click được và gửi turn thật (test khẳng định payload)
- [ ] Trust line hiện ở empty state, ẩn khi có thread
- [ ] Chip **không render** ở cả ba nhánh: loading · error · `data == null`
- [ ] Nhánh `null` lẻ trong payload → chỉ mất dòng đó
- [ ] `sessionsBehind > 0` hiện số phiên trễ, không chỉ hiện màu
- [ ] Ở viewport 1440×768 empty state không sinh scroll dọc; cụm nằm trên optical
      center. **Đo bằng e2e** (phase 12) — bản đầu định dùng
      `getBoundingClientRect()` trong vitest, nhưng jsdom trả rect 0 nên assertion
      `0 < h/2` **luôn xanh** và không kiểm gì
- [ ] Chip **không** hiện `phase` tự tin vào ngày lễ ở mức gây hiểu sai: giới hạn
      này đã ghi ở phase 03 §Risk (lịch lễ không có nguồn); phase này chỉ hiển thị
      cái phase 03 trả về, không tự suy diễn thêm
- [ ] Chip xuất hiện ở TopBar khi có thread
- [ ] `pnpm test` xanh; First Load route `/` ≤235 kB (214 + 10%)

## Risk Assessment

**Starter dẫn tới refusal.** Nếu "Tóm tắt thị trường hôm nay" gặp store thiếu
dữ liệu index thì user nhận refusal ở click đầu tiên — tệ hơn cả empty state
trống. Tín hiệu: chạy thật 4 starter, đếm refusal. Phản ứng đã định: starter nào
refuse thì **đổi câu**, không đổi model, không nới quyền. Nếu cả bốn đều phụ
thuộc dữ liệu chưa ingest thì phase này phải đợi — ghi thành blocker, không phát
hành một launchpad dẫn vào ngõ cụt (đúng cái phase 02 vừa xoá).

**Mã tường minh trong starter thành quảng cáo cho một mã.** "Phân tích luận điểm
cho HPG" khiến HPG được hỏi bất thường nhiều. Chấp nhận: đây là ví dụ, và nó nằm
trong 30 mã declared. Nếu muốn tránh, xoay vòng mã theo ngày — **không** làm ở
phase này (thêm state không cần thiết); ghi lại nếu ai phản đối.

**Chip im lặng khi lỗi che mất sự cố thật.** Nếu `/market/context` chết 3 ngày,
không ai biết. Đây là đánh đổi có chủ ý: chip là thông tin phụ trợ cho user, không
phải kênh giám sát. Giám sát thuộc observability, không thuộc UI.

**Trust line dài thành noise.** Hai câu là trần. Nếu cần thêm điều kiện, nó thuộc
một trang riêng, không thuộc empty state.

Rollback: additive thuần trên web; `git revert`. Endpoint phase 03 giữ nguyên
(nó không có caller khác nhưng cũng không hại).
