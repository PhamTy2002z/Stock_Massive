# Gỡ khái niệm "thanh bảng" khỏi Signal Desk

Ngày 2026-08-29 · nhánh `feat/study-canvas-runtime` · chỉ `apps/web`.

## Đã bỏ

- `shell-state.tsx`: state `deskViews`, hằng `DESK_STRIP_SLOTS`, helper
  `stripOf` / `withStrip` / `surface`, action `close-desk-view`, interface
  `SignalDeskTab` (gộp thẳng vào `SignalDeskBoard` — không còn ai import).
- `overlays.tsx`: prop `onStrip` truyền vào BoardSwitcher.
- `board-switcher.tsx`: prop `onStrip` trong `BoardSwitcherProps` và tham số
  `onStrip` của `buildRows`.
- `copy.ts`: `BOARD_SWITCHER_COPY.offStrip` (không còn nơi đọc).

## Đã giữ và đổi nghĩa

- `deskBoards` là danh sách duy nhất chrome vẽ ra; `deskPinned` là thứ tự ghim
  (cơ chế restore / `pinsSynced` trong `desk-state.tsx` không đụng tới);
  `deskRecent` là chính các board đó theo thứ tự mới nhất trước, dùng để quyết
  định bảng nào mở sẵn sau khi khôi phục hội thoại; `deskViewArtifactId` giữ
  nguyên.
- `open-desk-view` nay chỉ **thêm** board chưa gặp vào `deskRecent`
  (`fileRecent`), không xáo lại thứ tự — bấm một bảng không làm bảng khác nhảy
  chỗ.
- `pin-desk-view` chỉ đổi `deskPinned`. Bỏ ghim không còn đẩy board lên đầu
  `deskRecent` (đó là luật giữ slot của thanh bảng).
- Hàng "Xem tất cả bảng" trong switcher trước đây hiện khi có board nằm ngoài
  thanh; nay hiện khi hội thoại có ít nhất một bảng. Cổng cũ không còn nghĩa —
  danh sách zero-query vốn đã liệt kê mọi bảng, nên giá trị thật của hàng này là
  đổi cách nhóm sang "theo lượt hỏi".

## Copy

`pin` → "Ghim lên đầu danh sách" · `unpin` → "Bỏ ghim". Không còn chữ "thanh
bảng" trong `src/`.

## Test

- `shell-board-strip.test.tsx` → viết lại thành `shell-desk-boards.test.tsx`:
  giữ đủ bản ghi, thứ tự `deskRecent`, mở bảng không xáo thứ tự, ghim/bỏ ghim,
  pin khôi phục trước khi board tới, đổi hội thoại thì quên hết, khôi phục
  không đảo thứ tự và không tạo bản sao.
- `shell.test.tsx`: các assertion `deskViews` chuyển sang `deskBoards` /
  `deskRecent`; xoá case "lands on the neighbour when the open tab is closed"
  (không còn action). Thêm mock `QueryErrorResetBoundary` cho
  `@tanstack/react-query` vì hai case trong "the workspace on screen" nay dựng
  sẵn một bảng trước khi bấm nút header.
- `board-switcher.test.tsx`: bỏ `onStrip` khỏi mọi lần mount; case "wraps" đi
  lên hai bước vì hàng cuối là hàng đổi nhóm; hai case về "ngoài thanh" đổi
  thành "có gì để đổi nhóm không".

## Cổng

`pnpm type-check` pass · `pnpm lint` pass · `pnpm test` 737/737 pass.
`pnpm build` không chạy (dev server có thể đang mở). `e2e/signal-desk.spec.ts`
chỉ đọc: ba selector "Tất cả bảng", "Close Signal Desk", complementary
"Signal Desk" đều còn nguyên.
