# G1 — điều hướng board + vốn từ hiển thị của Signal Desk

Ngày: 2026-08-28 · Nhánh: `feat/study-canvas-runtime` · Không commit.

## Phạm vi đã làm

1. Strip 5 slot + board switcher (⌘K / nút trên strip) + pin theo thread.
2. Announcement mang thêm `symbol`, `asOf`, `studyDisplayName` (BE → FE).
3. Bổ sung coordinator: gỡ mọi từ kỹ thuật backend khỏi text hiển thị trên board
   (block, provenance strip, switcher) + strip một dòng + disclosure "Cách tính".

## Hành vi mới

### Strip và bản ghi board

`shell-state` tách hai khái niệm từng bị gộp làm một:

- `deskBoards` — **mọi** board của hội thoại, theo thứ tự dựng. Không bao giờ mất
  trong lúc thread còn trên màn hình.
- `deskViews` — **strip**, tối đa `DESK_STRIP_SLOTS = 5`, dẫn xuất từ
  `deskPinned` (theo thứ tự ghim) rồi `deskRecent` (mới nhất trước).

Hệ quả:

- Board mới vào đầu `deskRecent`; board thứ 6 rời strip nhưng vẫn trong "Tất cả".
- Mở board đã rời strip → được kéo lại vào đầu recent. Mở board **đang** trên
  strip → strip giữ nguyên thứ tự (một hàng target không được nhảy dưới tay).
- Đóng tab = rời strip + bỏ ghim, **không** xoá board; slot trống được board kế
  tiếp lấp.
- Bỏ ghim không làm board rơi khỏi strip ngay: nó chuyển lên đầu recent.
- `thread` xoá cả ba danh sách như trước.

**Đổi hành vi có chủ ý (đã cập nhật test cũ, không nới lỏng):** thứ tự strip từ
"theo thứ tự công bố" → "pinned trước, rồi mới nhất trước". Hai assertion trong
`shell.test.tsx` được viết lại theo đúng quyết định này và thêm assertion mới cho
`deskBoards` giữ nguyên thứ tự gốc.

### Board switcher

`components/signal-desk/board-switcher.tsx` (mới, tự viết listbox — repo **không**
có `cmdk`, không thêm dependency).

- Mở bằng ⌘K/Ctrl+K **khi inspector đang ở tab Signal Desk**; ở mọi chỗ khác ⌘K
  vẫn mở command palette. Và bằng nút `LayoutGrid` trên strip, có ghi "N bảng nữa".
- Rỗng ⇒ nhóm "Đã ghim" + "Gần đây" + dòng "Xem tất cả bảng" (chỉ hiện khi thực
  sự có board ngoài strip).
- Gõ ⇒ lọc theo title · mã · tên phân tích tiếng Việt · slug (slug chỉ để **khớp**,
  không bao giờ in ra). Bỏ dấu + hạ chữ + `đ→d`.
- `*` hoặc nút "Tất cả" ⇒ toàn bộ board theo thời gian, nhóm theo "Lượt hỏi N".
- ↑↓ vòng, Enter mở + đóng, Esc đóng (qua listener sẵn có của shell), pin/unpin
  ngay trong từng dòng.
- Không ảo hoá (vài trăm dòng), không gallery riêng, không tab theo mã.
- Chỉ một `SignalDeskPanel` được mount — `inspector.tsx` không đổi cấu trúc.

### Pin

`localStorage` key `alpha-desk.board-pins`, một record `{threadId: string[]}`,
qua `guardedStore`. Giới hạn 5 ghim/thread, nhớ 24 thread. Đọc lại khi mở thread;
ghi khi người đọc đổi. `desk-state` giữ hai ref (`restoredPins`, `pinsSynced`) để
frame "thread vừa đổi, pin đã xoá nhưng chưa khôi phục" không bị ghi đè thành
"người dùng bỏ hết ghim".

### Announcement (BE)

`messages.py::signal_desk_of` thêm ba khoá, **không tốn truy vấn nào**:

- `symbol` — đọc từ `payload["headline"]["symbol"]` đã có sẵn.
- `asOf` — đọc từ `payload["provenance"]["asOf"]` đã có sẵn.
- `studyDisplayName` — tra `studies.REGISTRY[name].display_name` (import trong hàm
  để `messages` không kéo tầng DB vào module scope).

`events.py::SIGNAL_DESK_FIELDS` mở allowlist đúng ba khoá đó. `frames`/`headline`
vẫn bị chặn — có test khẳng định. Không đụng `frames_buffer.py`, `contracts.py`,
`tools/studies.py`.

### Vốn từ hiển thị (scope bổ sung)

- `signal-desk-block.tsx`: `"Không có dữ liệu cho khối “{block.frame}”"` →
  `SIGNAL_DESK_COPY.blockNoData` = "Phần này chưa có số liệu."; cả hai nhánh
  degrade (`version lạ` và `widget throw`) → `SIGNAL_DESK_COPY.blockAsTable` =
  "Hiển thị dạng bảng — bản này chưa vẽ được biểu đồ." Không còn tên widget,
  version, frame id.
- `provenance-strip.tsx`: bỏ `provenance.source`. Còn một dòng
  `dữ liệu 28/08/2026 (7 ngày trước) · 21 phiên · thiếu một phần`,
  `whitespace-nowrap`, phần `reason` là mảnh duy nhất được `truncate` — không bao
  giờ xuống dòng thứ hai.
- `reason` **chỉ hiển thị khi map được toàn bộ** qua `SIGNAL_ISSUE_SENTENCES`
  (tách theo `;`). Một phần không map được ⇒ bỏ cả câu. Đây là điều kiện đúng vì
  BE hiện trả chuỗi kỹ thuật tiếng Anh (`"store holds 21 of 30 sessions"` trong
  `intraday_liquidity.py`, `"store chỉ có báo cáo ..."` trong
  `earnings_dislocation.py`). Trạng thái vẫn được nói bằng từ health.
- `Provenance.methodNotes?: string[]` thêm vào type FE (G3 chưa thêm lúc tôi đọc),
  mặc định `[]`; hiện sau disclosure `<details>` nhãn "Cách tính", thu gọn mặc định.
- Switcher hiển thị `studyDisplayName`, không bao giờ slug/artifactId.

## File đã đổi

Web — sở hữu:
- `src/components/shell/shell-state.tsx` — `SignalDeskBoard`, `DESK_STRIP_SLOTS`,
  `deskBoards`/`deskPinned`/`deskRecent`, strip dẫn xuất, action `pin-desk-view`
  + `desk-pins-restored`, overlay `boards`, ⌘K có ngữ cảnh.
- `src/components/shell/desk-state.tsx` — truyền đủ trường announcement vào strip,
  đọc/ghi pin theo thread.
- `src/components/shell/inspector.tsx` — `offStripCount`, `onOpenSwitcher`.
- `src/components/shell/overlays.tsx` — `BoardPicker`.
- `src/components/signal-desk/board-switcher.tsx` — **mới**.
- `src/components/signal-desk/signal-desk-header.tsx` — nút switcher + số board ngoài strip.
- `src/components/signal-desk/signal-desk-block.tsx` — copy.
- `src/components/signal-desk/provenance-strip.tsx` — viết lại.
- `src/lib/alpha-desk/{copy.ts,types.ts,desk-session.ts,read-content.ts}`.
- `e2e/signal-desk.spec.ts` — bỏ assertion `/vnstock/`, thay bằng caption mới.

API:
- `src/agent/messages.py` — `signal_desk_of` + hai helper.
- `src/agent/events.py` — `SIGNAL_DESK_FIELDS`.
- `tests/e2e/server.py` — payload giả lập mang đủ trường mới.

Test mới/đổi:
- `src/components/shell/shell-board-strip.test.tsx` — **mới**, 18 case.
- `src/components/signal-desk/board-switcher.test.tsx` — **mới**, 16 case.
- `src/components/signal-desk/provenance-strip.test.tsx` — **mới**, 9 case.
- `src/lib/alpha-desk/desk-session.test.ts` — +8 case pin storage.
- `src/components/signal-desk/signal-desk-block.test.tsx` — +2 case vốn từ.
- `src/components/signal-desk/signal-desk-header.test.tsx` — +3 case.
- `src/components/shell/shell.test.tsx`, `signal-desk-panel.test.tsx`,
  `signal-desk-block-boundary.test.tsx`, `message.test.tsx`,
  `signal-desk-building.test.tsx`, `transcript.test.ts`, `live-turn.test.ts` — cập nhật.
- `apps/api/tests/test_agent_study_tools.py` — +2 case (`signal_desk_of`).
- `apps/api/tests/test_agent_turn_events.py` — +1 case (allowlist sự kiện).

## Lệnh và kết quả

| Lệnh | Kết quả |
|---|---|
| `pnpm type-check` (apps/web) | pass |
| `pnpm lint` (apps/web) | pass |
| `pnpm test` (apps/web) | **56 file / 709 test pass** |
| `pnpm build` (apps/web) | pass |
| `make test-one T=tests/test_agent_transport.py tests/test_agent_study_tools.py tests/test_agent_turn_events.py tests/test_agent_signal_desk.py` | 93 pass |
| `make test-one T="…loop/lifecycle/capability/prompt…"` | 210 pass |
| `make test` (apps/api) | 1281 pass / **49 fail — tất cả nằm ngoài phạm vi G1** |

### 49 failure của `make test` (không phải của tôi)

| File | Nguyên nhân |
|---|---|
| `tests/test_agent_price_check.py` (18) | `sqlite3.OperationalError: no such table: bar_daily` — bảng mới của spine daily phase 08a chưa vào schema test |
| `tests/test_price_band.py` (15) | `SnapshotMetadata.observed_at` đòi timezone-aware |
| `tests/test_signal_registry.py` (13) | cùng nguyên nhân trên |
| `tests/test_indicator_pack.py` (3) | cùng nguyên nhân trên |

Trong một lần chạy sớm hơn còn có `tests/studies/test_earnings_dislocation.py`,
`test_entry_condition_review.py`, `test_agent_composition.py` đỏ vì
`Provenance.method_notes` (G3) và widget v2 (agent widget); lần chạy cuối chúng đã
xanh — agent kia đã sửa xong. Tôi không đụng vào file của họ.

## Quyết định đáng ghi

- **`reason` bị bỏ hẳn khi không map được**, thay vì cắt ngắn chuỗi kỹ thuật. Một
  dòng nửa tiếng Việt nửa log tệ hơn là chỉ có từ health.
- **`studyName` (slug) vẫn nằm trong announcement** và được switcher dùng để
  *khớp* tìm kiếm, nhưng có test khẳng định nó không bao giờ vào DOM. Bỏ hẳn slug
  sẽ làm trace/export mất khoá.
- **Nút switcher không phải `role="tab"`** — nó không chọn gì, nó mở đường tới thứ
  strip không chứa được.
- `scrollIntoView` được feature-detect (jsdom không có; và nó là phần optional của
  DOM — throw ở đó sẽ hạ cả danh sách).

## Câu chưa giải quyết

1. `render_signal_desk` không có `symbol` và không có `display_name` (nó lưu dưới
   kind `composed_signal_desk`, không phải Study đăng ký). Switcher rơi về title —
   title do model viết nên vẫn đọc được, nhưng board loại này không tìm được theo
   mã. Nếu muốn, BE có thể suy `symbol` từ frame nguồn — cần đụng `tools/studies.py`,
   ngoài phạm vi đã giao.
2. `methodNotes` hiện chưa có nguồn: G3 đang thêm `Provenance.method_notes` ở BE.
   FE đã sẵn sàng (`methodNotes?`, default `[]`), nhưng cần G3 đặt tên khoá wire
   đúng `methodNotes` (camelCase) trong `Provenance.to_payload()` thì disclosure
   mới hiện.
3. E2E chưa chạy (`pnpm test:e2e` cần dựng server, và `pnpm dev` có thể đang mở).
   Spec đã được sửa theo caption mới nhưng chưa được chạy xác nhận.

Status: DONE_WITH_CONCERNS
Summary: Strip 5 slot + board switcher ⌘K + pin theo thread đã xong hai đầu FE/BE; đồng thời đã gỡ hết từ kỹ thuật backend khỏi block, provenance strip và switcher, strip giờ là một dòng có disclosure "Cách tính".
Concerns/Blockers: `make test` còn 49 đỏ nhưng đều ở `bar_daily`/timezone của domain signals — ngoài G1, tôi không sửa. `methodNotes` chờ G3 đặt đúng tên khoá wire. E2E chưa chạy xác nhận.
