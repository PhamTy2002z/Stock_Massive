# Phase 05 + 06 — Board grammar, composer, và lưới web

`plans/260829-2304-signal-desk-analysis-compiler` · 2026-08-30 · branch `develop`
(chưa commit)

## Kết quả

Signal Desk đi từ "một title và một danh sách block phẳng" sang **board có ngữ
pháp**: dải KPI dẫn dắt, section, caption có chỗ trống, appendix, điểm lint. Bất
biến siết thêm một bậc như plan tuyên bố — **model không gõ một con số nào**:
mọi figure là `{frame_id, column, row|row_where}` server tra và format, và một
chữ số gõ vào caption (kể cả năm) bị từ chối có tên.

Năm cổng xanh:

| Cổng | Kết quả |
|---|---|
| `make test` (apps/api) | **2.090 passed**, 3 deselected |
| `make lint` (apps/api) | pass |
| `pnpm type-check` | pass |
| `pnpm lint` | pass |
| `pnpm test` | **885 passed** / 67 file |
| `pnpm build` | pass |

## Phase 05 — backend

**Bảy module mới** ở `apps/api/src/studies/`: `grammar` (DSL + validator có tên
lỗi) · `composer` (hình dạng frame → widget) · `layout` (đóng gói lưới 12) ·
`archetypes` (5 dạng câu hỏi) · `lint` (điểm trực quan) · `auto_compose` (server
dựng board) · `format` (một ô → chuỗi người Việt đọc).

**Sửa:** `contracts.py` (spec v2: `BoardSpec`/`KpiCell`/`VisualBlock`/
`CaptionBlock`/`ResolvedValue`, và `specVersion` nay có trên **cả** v1 lẫn v2 nên
không nơi nào phải suy ra phiên bản) · `widgets.py` (+8 widget) ·
`frames_buffer.py` (bỏ `MAX_BLOCKS`, `store_composition` nhận payload spec, thêm
`frames_in_turn`) · `agent/tools/studies.py` (schema v2 + pipeline biên dịch) ·
`agent/loop.py` (**một** hook cuối Turn) · `agent/messages.py` (`autoComposed`).

**Test mới:** `test_grammar.py` (38) · `test_composer_shape.py` (25) ·
`test_layout.py` (24) · `test_archetypes.py` (17) · `test_lint.py` (10) ·
`test_auto_compose.py` (18) · `test_format.py` (16) · 4 test hook loop · 6 test
board trong `test_agent_composition.py` gồm end-to-end VIC vs VCB.

## Phase 06 — web

**Mới:** `signal-desk-board.tsx` · `kpi-strip.tsx` · `board-section.tsx` ·
`source-badge.tsx` · `layout.ts` · 7 widget (`grouped-bar`, `comparison-table`,
`donut`, `waterfall`, `bullet`, `text-card`, `caption`) · fixture
`board-v2-compare.json` **sinh từ chính đường code server chạy**, không viết tay.

**Sửa:** `types.ts` (v2 + `cellRoles` trên `Frame`) · `widget-registry.ts` (+6
entry + `NOT_FRAME_WIDGETS`) · `chart-theme.ts` (5 role + `cellColorFor`) ·
`frame.ts` (`cellRole`) · `signal-desk-panel.tsx` (nhánh v2) ·
`signal-desk-export.ts` (v2) · `globals.css` (2 token).

**Bundle:** chunk signal-desk **8.920 → 11.707 byte gzip = +2.787 B (+2,7 KB)**,
đo bằng build lại từ HEAD (`git stash -u -- apps/web`) rồi so cùng chunk async.
Trần là 60 KB.

## Ba chỗ code thật đảo giả định của plan

1. **Schema v2 tốn +1.006 token**, không phải ≤ +600. Đo sau
   `strict_parameters`: 763 → 1.769. Đã rút description như plan dặn — bỏ mô tả
   từng trường của `_ref_schema` (nó xuất hiện **tám lần** trên một schema), và
   bỏ ba tên khỏi enum widget vì chúng không phải hình vẽ của một frame
   (`kpi_strip`, `caption`, `data_table` — mọi lần model chọn đều ra violation).
   Không rút một luật nào. Phần còn lại là cấu trúc: một board có nhiều bộ phận
   hơn một danh sách block, và catalog widget đi từ 13 lên 21 tên.

2. **`visual_ratio ≥ 0,7` khiến board hai hình không mang nổi một caption**
   (2/3 = 0,667). Chính vì thế `comparison_table` **phải** phát ra companion
   `grouped_bar` — luật đã viết trong plan mà bản đầu để treo — và câu ví dụ
   VIC vs VCB mới hợp lệ. Ngưỡng vẫn là hằng chờ phân bố phase 09.

3. **`bucket` không phải trục thời gian.** Bản đầu xếp nó vào `_TIME_NAMES` và
   biến profile thanh khoản trong phiên thành `line_series` — hàm ý có liên tục
   giữa 11:30 và 13:00, lúc thị trường đóng. `intraday_liquidity` đã vẽ nó bằng
   `bar_series` từ đầu, và đó là câu trả lời đúng.

## Quyết định thiết kế đáng ghi

- **Lint đo board *đã biên dịch*, không đo kế hoạch của model.** Hai thứ lệch
  nhau đúng bằng những hình server thêm vào.
- **Sàn KPI được miễn cho board server dựng** (`validate(..., authored=False)`).
  Server có frame, không có câu trả lời; tự chọn ba số để dẫn dắt là server
  quyết định đâu là trọng tâm. Mọi luật khác vẫn áp, và một test parametrize
  1..11 frame giữ board tự dựng qua chính grammar của nó.
- **Server không bao giờ viết một câu.** `auto_compose` sinh 0 caption.
- **Bề rộng đo từ panel, không từ viewport.** Inspector là cột kéo được, nên
  `@media` hỏi sai câu hỏi. `ResizeObserver` trên hộp của chính board, bắt đầu ở
  giả định **rộng** để lần vẽ đầu khớp cách server xếp.
- **Lượt sửa nhớ trong tiến trình, có trần** (`REJECTED_TURNS_REMEMBERED = 512`).
  Câu hỏi "Turn này đã có lượt sửa chưa" vô nghĩa khi Turn kết thúc, nên một
  dòng DB để trả lời nó sẽ sống lâu hơn khoảnh khắc duy nhất nó có nghĩa.

## Hai file nằm ngoài bảng surface — đã amend CLAUDE.md

`src/studies/format.py` (bảng gốc khai sáu module mới, thiếu module thứ bảy) và
`apps/web/src/app/globals.css` (hai token `--widget-benchmark`,
`--widget-warning`). Cả hai đã có dòng riêng kèm giới hạn.

## Còn lại

- **Chưa commit.** Cây làm việc còn cả thay đổi của phase 01–04.
- Phase 07 (Study thành template), 08 (prompt playbook — chờ C2 phase 05), 09
  (golden gate) chưa chạm.
- `donut` không xuất hiện trên board VIC vs VCB vì frame của nó không phải
  phần-của-tổng; nó được giữ bằng test riêng.
