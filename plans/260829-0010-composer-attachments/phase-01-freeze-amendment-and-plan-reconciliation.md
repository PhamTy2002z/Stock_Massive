---
phase: 1
title: "Amendment freeze và giải xung đột plan"
status: done
priority: P1
effort: "2h"
dependencies: []
---

# Phase 01: Amendment freeze và giải xung đột plan

## Overview

Không một dòng code sản phẩm. Phase này ghi bảng freeze **tứ hợp**, giải xung đột
với plan `260827-2325` ở **cả hai lớp**, sửa một comment đang là bản ghi sống sót
của quyết định plan này đảo, và ghi ghi chú roadmap.

## Requirements

- Functional: CLAUDE.md có bảng amendment phủ tứ hợp `Related Code Files` của cả
  mười phase; `260827-2325/phase-02` không còn xoá menu **và** contract test của
  nó không còn cấm end state của phase 10; `turns.py:81` nói đúng invariant sống;
  `docs/roadmap.md` mang ghi chú UI.
- Non-functional: không xoá lý lẽ cũ — ghi lại kèm ngày và kèm cái đã đảo nó.

## Architecture

Bốn tài liệu độc lập. Đi đầu vì rẻ và vì nó chặn một collision phá hoại:
`260827-2325/phase-02` xoá `AttachMenu`.

## Related Code Files

- Modify: `CLAUDE.md` — thêm khối "Mở thêm 2026-08-29"
- Modify: `plans/260827-2325-evidence-led-chat-surface/phase-02-distill-dead-end-affordances.md`
- Modify: `plans/260827-2325-evidence-led-chat-surface/plan.md` — frontmatter `blockedBy`
- Modify: `apps/api/src/agent/turns.py` — chỉ comment ở `:81`
- Modify: `docs/roadmap.md` — Track S

## Implementation Steps

1. **CLAUDE.md.** Thêm khối "**Mở thêm 2026-08-29** cho plan
   `plans/260829-0010-composer-attachments/`" kèm nguyên bảng ở `plan.md`
   §"Ranh giới freeze — tứ hợp mọi phase". Giữ giọng các khối trước: bảng **là**
   ranh giới, file ngoài bảng cần amendment mới.
2. **Đối chiếu bảng.** Trước khi commit bảng: đọc `Related Code Files` của cả mười
   phase file, lập tứ hợp, so với bảng. Đây là một success criterion, không phải
   một lời khuyên — bản đầu của plan này ship một bảng mà chính nó vi phạm ≥11 file.
3. **Hẹp phase-02 của plan kia — lớp một, hành động.** Ở `:45` đổi *"Xoá cả menu +
   nút Attach"* sang *"Xoá các row không có handler; giữ menu và nút"*. Sửa `:82`
   và `:103` cho khớp. Lưu ý citation của chính nó đã cũ: nó ghi `composer.tsx:236-276`
   và *"7 item"*, thật là `:382-425` với sáu row — sửa luôn.
4. **Hẹp phase-02 — lớp hai, contract.** Đây là lớp bản đầu bỏ sót và là chỗ đụng
   thật:
   - `:100-102` — assertion *"zero control có `disabled` hoặc `aria-disabled` mà
     không có `aria-describedby` giải thích"* đổi thành *"mọi control `disabled`
     đều được mô tả bằng chương trình"*. Phase 10 làm phần code cho nó thoả.
   - `:118-129` — bỏ *"không còn 'sắp ra mắt'"* và *"Không nút Attach, không menu
     Attach trong DOM"*.
   Thêm ngay dưới một khối:

   > **Đảo tiền đề 2026-08-29.** Lý lẽ "cả 7 disabled, không item nào có handler"
   > đúng khi viết. `plans/260829-0010-composer-attachments/` cho hai row handler
   > thật và đặt bốn row còn lại là badge có chủ ý. Menu không còn là ngõ cụt toàn
   > phần, nên phép xoá toàn phần hết cơ sở, và contract "không có control
   > disabled" đổi thành "control disabled phải được mô tả".

5. **Frontmatter hai chiều.** `260827-2325/plan.md` thêm
   `260829-0010-composer-attachments` vào `blockedBy`. Kiểm hai bên trỏ nhau.
6. **`turns.py:81`.** Comment hiện tại: `# docs/adr/0015: no attachments, and no
   user-supplied URL is ever fetched.` `docs/adr/` đã bị xoá, nên dòng đó là bản
   ghi sống sót duy nhất của một quyết định plan này đảo. Viết lại nó nói đúng
   invariant sống: trần bytes áp lên **câu người dùng gõ**; đính kèm đi bằng id và
   bị chặn bởi trần riêng của kho (phase 05). Nêu cái đã đảo quyết định cũ.
   Không đụng `MAX_USER_INPUT_BYTES`.
7. **Roadmap.** Trong Track S, tại phase mà chế độ nghiên cứu nhiều bước thuộc về
   (đọc §4 rồi chọn giữa S1 và S2, đừng đoán), thêm một dòng checklist: *"Row
   'Nghiên cứu sâu' trong `AttachMenu` bỏ badge và nối vào lane này"* + trỏ về
   plan này. Nêu rõ nó khác `phase-09` của `260827-2325` (độ sâu **một** câu trả
   lời) ở chỗ nào.
8. **Ghi head alembic thật.** Thêm một dòng vào `plan.md` §"Nguyên tắc" hoặc vào
   phase 05: branch này đang mang `a3f7e21b8d54` **chưa commit**, `upgrade()` của
   nó raise theo row count. Ai chạy phase 05 phải biết trước.
9. `ak plan validate` + `ak plan reindex` nếu index lệch.

## Success Criteria

- [ ] Bảng trong CLAUDE.md **bằng** tứ hợp `Related Code Files` của mười phase (đối chiếu ghi ra được)
- [ ] `probe.py` **không** trong bảng
- [ ] `260827-2325/phase-02` giữ menu; assertion a11y đã đổi thành "được mô tả"; Success Criteria không còn cấm badge
- [ ] Lý lẽ cũ còn nguyên văn kèm khối đảo tiền đề
- [ ] Hai `plan.md` trỏ nhau qua `blocks`/`blockedBy`
- [ ] `turns.py:81` không còn nói "no attachments"; `MAX_USER_INPUT_BYTES` không đổi
- [ ] `docs/roadmap.md` có dòng checklist ở đúng phase Track S, phân biệt được với `phase-09`
- [ ] `ak plan validate ./plans/260829-0010-composer-attachments` exit 0

## Risk Assessment

**Rủi ro: phase-02 của plan kia được chạy trước phase này.** Nó xoá `AttachMenu`
và land một test cấm badge.
*Tín hiệu:* `260827-2325/phase-02` chuyển `done`, hoặc `affordance.test.tsx` xuất
hiện, hoặc `AttachMenu` biến mất khỏi `composer.tsx`.
*Phản ứng đã định:* dựng lại menu từ git (`git log -p -- apps/web/src/components/shell/composer.tsx`)
và sửa test đã land. Đắt hơn hẳn việc đi trước — nên phase này là cách tránh,
không phải cách chữa.

**Rủi ro: bảng tứ hợp vẫn thiếu vì một phase sau này thêm file.**
*Tín hiệu:* một phase 02-10 sửa file không có trong bảng.
*Phản ứng đã định:* phase đó **dừng**, thêm một dòng vào bảng CLAUDE.md kèm ngày,
rồi tiếp. Không "nới một dòng" trong im lặng — đó chính là hành vi bảng tồn tại
để chặn.

**Rủi ro: chọn sai phase Track S cho ghi chú.**
*Tín hiệu:* đọc §4 thấy chế độ nhiều bước cần human approval → nó là S2.
*Phản ứng:* để ghi chú ở phase muộn hơn trong hai phase khả dĩ.
