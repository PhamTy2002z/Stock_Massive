# Review — Signal Desk board menu / roles / volume_at_price (260829-0015)

Phạm vi: diff chưa commit trong bốn surface Signal Desk (API `src/studies/*`,
`src/stocks/intraday/ingest.py`, `src/agent/{messages,events,loop,tools}`, contract
catalog; Web `components/shell/*`, `components/signal-desk/**`, `lib/alpha-desk/*`,
`globals.css`, e2e). Bỏ qua `src/stocks/signals/**`, `providers/**`, `price_band.py`,
`backfill_daily.py`, `earnings.py` theo yêu cầu.

## Cổng

| Cổng | Kết quả |
|---|---|
| `make test` (apps/api) | **ĐỎ ở collection** — `tests/test_provider_contracts.py` gọi `ProviderSource.FIINQUANT` đã bị xoá khỏi `src/stocks/providers/contracts.py`. Là của phiên khác (phase-08 retire FiinQuant), nhưng nó chặn cả suite. |
| `pytest tests --ignore=tests/test_provider_contracts.py` | 1408 passed |
| `pytest tests/studies` | 143 passed |
| `pnpm type-check` / `pnpm lint` | pass |
| `pnpm vitest run` (shell + signal-desk + lib/alpha-desk) | 501 passed / 35 file |

Ba luật cứng: **không vi phạm**. `frames` không lọt vào message model (`run_study` chỉ
trả `headline` + `provenance`; `signal_desk_of` chỉ thêm `symbol`/`asOf`/`studyDisplayName`).
Widget name+version có v2 mới, v1 giữ nguyên, catalog đồng bộ (test giữ). `as_of` vẫn
đóng băng; `read_frame` trả dict thô nên `Provenance.__post_init__` mới **không**
re-validate artifact cũ — đúng hướng.

---

## Critical

Không có.

---

## High

### H1 — `_merged_provenance` đánh rơi `methodNotes`, đường `get_series` mất hẳn phần "Cách tính"

`apps/api/src/agent/tools/studies.py:681-711`

`signals.py:566-570` vừa được thêm để sinh `method_notes` (`_issue_note`) cho mỗi frame
gathered, lưu vào `frames_buffer`. Nhưng `render_signal_desk` gộp provenance qua
`_merged_provenance`, và dict trả về chỉ có `source/asOf/sessionsUsed/health/reason` —
không có `methodNotes`. Kết quả: mọi board dựng bằng `get_series + render_signal_desk`
(một trong **hai** đường Signal Desk theo CLAUDE.md) không bao giờ hiện disclosure
"Cách tính", dù dữ liệu đã tính xong. Chỉ đường `run_study` có.

Đồng thời `reason` ở đây là `"; ".join(...)` nhiều câu, không đi qua
`_check_reader_sentence` (vì là dict thô), nên có thể vượt `REASON_LIMIT=120` và không bị
chặn — validator chỉ bảo vệ đường `Provenance(...)`.

Sửa: thêm `"methodNotes": [...]` gộp từ `sources` (dedupe theo thứ tự) vào
`_merged_provenance`, và cắt/kiểm `reason` bằng chính `_check_reader_sentence`.

### H2 — Esc trong Signal Desk đóng luôn cả pane, không chỉ lớp trên cùng

`apps/web/src/components/shell/shell-state.tsx:880-883`

```ts
if (event.key === "Escape") {
  dispatch({ type: "overlay", overlay: null })
  if (state.inspector !== null) dispatch({ type: "close-inspector" })
}
```

BoardMenu (`overlay: "board-menu"`) và BoardSwitcher (`overlay: "boards"`) đều được mở
**từ trong** inspector, và `board-menu.tsx:53` ghi rõ "Escape là của shell". Kịch bản: mở
dropdown tên bảng → bấm Esc → dropdown đóng **và** cả Signal Desk biến mất. Trước đợt này
palette/share hiếm khi mở cùng inspector nên gần như không chạm; giờ là đường đi mặc định.

Sửa: `if (state.overlay !== null) { dispatch({overlay:null}); return }` trước khi xét
`close-inspector`.

---

## Medium

### M1 — `desk-views-restored` hồi sinh board đã đóng và đẩy nó lên đầu strip

`apps/web/src/components/shell/shell-state.tsx:594-604`

Sau `close-desk-view` (id bị gỡ khỏi `deskRecent`, giữ trong `deskBoards`), lần
`desk-views-restored` kế tiếp mà `deskBoards` có thay đổi (một board mới về) sẽ
`fileRecent` lại **toàn bộ** tabs, unshift id đã đóng về đầu `deskRecent`.

Đã dựng probe reducer để xác nhận: đóng `a1`, rồi restore `[a1,a2,a3]` →
`deskViews = ["a3","a1","a2"]` thay vì `["a3","a2"]`.

Guard `if (deskBoards === state.deskBoards) return state` chỉ chặn được trường hợp không
có gì mới. Sửa: chỉ `fileRecent` các id chưa có trong `deskBoards` trước khi merge, hoặc
giữ một tập `deskClosed`.

Mức Medium chứ không High vì hiện **không UI nào dispatch `close-desk-view`** — xem M2.

### M2 — Bộ máy strip 5 slot + `close-desk-view` đã thành code chết sau khi bỏ tab strip

`shell-state.tsx:114 (DESK_STRIP_SLOTS)`, `:460-500 (surface/stripOf/withStrip)`,
`:648-667 (close-desk-view)`; `copy.ts` `offStrip` không có nơi dùng.

Header giờ nhận `boards={state.deskBoards}` (toàn bộ), BoardMenu và BoardSwitcher cũng đọc
`deskBoards`. `state.deskViews` chỉ còn đúng một consumer: `overlays.tsx:226` `onStrip=`,
dùng để quyết định có hiện dòng "Xem tất cả bảng". Vì `DESK_STRIP_SLOTS = 5` và
`onStrip` chứa 5 board mới nhất, hội thoại ≤5 board sẽ **không bao giờ** thấy dòng đó, và
nhóm theo "Lượt hỏi N" chỉ tới được bằng cách gõ `*`.

Kèm theo: `shell-board-strip.test.tsx` có nguyên block `describe("closing a tab")` với 4
test cho một hành vi không có affordance nào gọi tới — test xanh nhưng không chứng minh
sản phẩm.

Kèm theo (luật text): `BOARD_SWITCHER_COPY.pin = "Ghim vào thanh bảng"` / `unpin = "Bỏ ghim
khỏi thanh bảng"` nói tới "thanh bảng" mà người đọc không còn nhìn thấy.

Đề xuất: hoặc bỏ hẳn `deskViews/deskRecent/close-desk-view/DESK_STRIP_SLOTS` và cho
`onStrip` = danh sách rỗng (dòng "Xem tất cả" luôn hiện khi có board), hoặc giữ strip và
render nó. Giữ cả hai nửa là chỗ hai luật sẽ trôi ra khỏi nhau.

### M3 — `SETTLE_GRACE` (bucket ATC đóng 15:01) lệch `SESSION_SETTLED_AT` (15:00)

`apps/api/src/stocks/intraday/ingest.py:238-250` vs `apps/api/src/stocks/intraday/reads.py:34`

Bucket 14:45 (ATC — bucket lớn nhất phiên) chỉ được ghi từ 15:00 + `SETTLE_GRACE` = **15:01**.
Nhưng `SESSION_SETTLED_AT = 15:00`, nên trong cửa sổ 15:00:00–15:00:59:

- `reads.latest_closed_session` coi hôm nay là phiên đã đóng;
- `volume_at_price`: `underway = local.time() < 15:00` → `False` → `health="normal"`,
  `reason=None`, mà ladder lại **thiếu toàn bộ khối lượng ATC**;
- artifact đóng băng con số thiếu đó vĩnh viễn (không recompute).

Sửa một dòng: `SESSION_SETTLED_AT` suy từ bucket cuối + `BUCKET_MINUTES` + `SETTLE_GRACE`,
đúng cách `FIRST_BUCKET_SETTLED_AT` được suy ra ở `volume_at_price.py:103`.

### M4 — Câu hỏi người dùng ghi nguyên văn vào log ứng dụng

`apps/api/src/agent/loop.py:1836-1848`

`_log_catalog_without_a_run` log `state.question` (200 ký tự nguyên văn user text) ở mức
INFO, kèm `turn_id`/`thread_id` trong `extra`. Đây là nội dung do người dùng gõ đi vào log
sink — nếu log được ship ra collector ngoài thì là user content vượt trust boundary, và nó
gắn với `thread_id` nên không ẩn danh.

Ít nhất: xác nhận log sink là nội bộ; hoặc chỉ log `turn_id`/`thread_id` và để nơi phân
tích đọc câu hỏi từ DB qua id.

Ghi chú phụ: phễu này tính cả Turn đã vẽ board bằng `get_series + render_signal_desk` (chỉ
kiểm `list_studies ∈ names and run_study ∉ names`) — đúng nghĩa "không có công thức", nhưng
người đọc report sẽ hiểu là "không vẽ được gì".

### M5 — `_window` refuse mọi ngày lễ trong tuần

`apps/api/src/studies/volume_at_price.py:284-300`

`expected = local.weekday() < 5 and local.time() >= 09:31` → mọi ngày nghỉ lễ rơi vào
T2–T6 (Tết ~7 ngày + ~5 lễ khác) `volume_at_price` từ chối trả lời hoàn toàn. Docstring có
ghi nhận, và "an toàn hơn là gán nhầm tên phiên" là quyết định đúng — nhưng có sẵn một tín
hiệu rẻ để phân biệt: nếu **không mã nào** trong store có bucket hôm nay thì đó là thị
trường nghỉ, không phải bars chưa về. Một `select ... limit 1` trên `BarIntraday15m.trading_day
== today` (không lọc symbol), hoặc `trading_day.latest_trading_day`, đủ để hạ mức từ refuse
xuống "trả phiên gần nhất kèm reason".

### M6 — `provenance.methodNotes` đi vào context của model, chưa tính vào ngân sách headline

`apps/api/src/agent/tools/studies.py:511`

`run_study` trả `"provenance": artifact.provenance.to_payload()` cho model, và payload này
giờ mang `methodNotes`. `earnings_dislocation.METHOD_NOTES` là 5 câu ≈ 700 ký tự (~250
token) thêm vào mỗi lần gọi, ngoài trần "headline ~300 token" mà `tools/studies.py:71` ghi.
Nếu chủ ý cho model đọc thì nên nói rõ trong comment ngân sách; nếu không thì tách
`methodNotes` khỏi payload model và chỉ lưu vào artifact.

---

## Low

### L1 — `SERIES_MUTED` và role `"muted"` trỏ hai token khác nhau

`chart-theme.ts:33` `SERIES_MUTED = hsl(var(--widget-neutral))`, nhưng
`ROLE_TOKENS.muted = "--widget-series-muted"` (`:47`). `globals.css` vừa re-cut
`--widget-series-muted` cho đạt 3:1 với lý do "một token không ai dùng an toàn được" — mà
`line-series.tsx` vẫn dùng `SERIES_MUTED` = `--widget-neutral` cho đường phụ mặc định. Hai
đường phụ trên hai chart sẽ khác màu tuỳ frame có khai role hay không.

### L2 — Nút tên bảng có `aria-label` che mất nhãn nhìn thấy

`signal-desk-header.tsx:72` `aria-label={BOARD_SWITCHER_COPY.open}` = "Tất cả bảng", trong
khi text nhìn thấy là tên bảng đang mở. Screen reader đọc "Tất cả bảng" thay vì tên board
(WCAG 2.5.3 Label in Name). E2E cũng đang dựa vào chính điều này
(`getByRole("button", { name: "Tất cả bảng" })`). Dùng `aria-describedby`/`title` cho phần
"mở danh sách", để accessible name chứa tên bảng.

Cùng chuỗi `"Tất cả bảng"` đang được dùng cho 3 thứ: nút header, nút "xem tất cả" trong
switcher (`board-switcher.tsx:132`), và tên nhóm `allGroup` — ba control/landmark trùng tên.

### L3 — Tooltip checklist còn rò khoá kỹ thuật cho artifact cũ

`condition-checklist.tsx:85` `title={`Số liệu trong khối ${text(row, evidence)}`}`.
Backend đã đổi giá trị ô sang tiếng Việt (`_EVIDENCE_NAMES`), nhưng FE giữ nguyên tiền tố,
nên: artifact **mới** → "Số liệu trong khối Đường giá" (đọc gượng); artifact **cũ** (vẫn
render lại theo luật `as_of`) → "Số liệu trong khối price_context", đúng cái leak mà
docstring của `entry_condition_review` nói là đã sửa. Map legacy key ở FE hoặc đổi tiền tố
thành "Đối chiếu ở".

### L4 — `_steps` rơi về `_sampled` sẽ trả mức giá **ngoài** bậc giá của sàn

`volume_at_price.py:344-360`. Docstring hứa "một mức Study báo là mức một lệnh có thể đã
nằm ở đó", nhưng nhánh `_sampled` chia đều theo dong tròn, không theo tick. Thực tế gần như
không chạm (cần một bucket 15 phút rộng >200 tick, vượt cả biên độ ngày), nên chỉ là nợ
đúng-đắn. Nếu giữ, nên `quantize` mỗi mẫu về bậc giá gần nhất.

Cùng file: `_steps:349` `return (first if first == low else low,)` — nhánh `first == low`
không thể xảy ra ở đó (đã swap low/high ở trên), là code chết.

### L5 — Từ hệ thống còn trong catalog widget

`contracts/signal-desk-widget-catalog.json`: `"Như v1, thêm màu cột theo vai trò từng dòng
khai trong frame"` (× 5). `purpose` không render ra DOM nên không phá luật text UI, nhưng
nó đi vào mô tả tool cho model — và "frame" nằm đúng trong `_SHOP_WORDS` của
`contracts.py`. Nên nói "trong dữ liệu của khối".

### L6 — Hai danh sách "từ hệ thống" đã lệch nhau

`apps/api/src/studies/contracts.py` `_SHOP_WORDS` có `provider/roster/universe`;
`provenance-strip.tsx` `SHOP_WORDS` có `registry/tool/row` mà không có ba từ kia. Một
`reason` backend cho qua có thể bị FE **im lặng bỏ hẳn** (`readableReason` trả `null`), và
ngược lại. Nên sinh một phía từ phía kia, hoặc đưa vào contracts như widget catalog.

### L7 — Scope drift & vệ sinh

- `inspector.tsx` bị reformat toàn file sang có dấu chấm phẩy, trong khi các file cùng thư
  mục (`shell-state.tsx`, `signal-desk-header.tsx`, `overlays.tsx`) không dùng — 203 dòng
  diff cho ~40 dòng thay đổi thật.
- Ngoài G1/G2/G3/vá ingest: `CHAT_DEFAULT 427 → 556`, card bo góc `rounded-[18px]` + bỏ
  `border-l`, bỏ border composer, `hooks/use-auth.ts`, `lib/alpha.ts` (+68), proxy
  `route.ts` bắt lỗi upstream, `Dockerfile` healthcheck, `package.json --wait`. Tất cả đều
  hợp lý riêng lẻ nhưng không thuộc mục tiêu đợt này.
- `apps/api/phase-02-vision-capability-gate.md` là file untracked nằm sai chỗ (không trong
  `plans/`).
- `route.ts:292` `(cause as Error).message` in ra `undefined` khi `cause` không phải
  `Error` (AbortError/DOMException/`string`).
- `provenance-strip.tsx` `notes.map((note) => <li key={note}>)` — hai note trùng chữ sẽ
  trùng key.
- `desk-session.ts` `PINS_PER_THREAD = 5` cắt khi ghi, nhưng reducer `pin-desk-view` không
  chặn ghim thứ 6 → ghim thứ 6 biến mất sau khi reload, không có phản hồi nào.

---

## Những chỗ đã kiểm và **không** phải lỗi

- BoardMenu click-ngoài: listener `pointerdown` gắn sau khi menu mount, và
  `surface.current.parentElement` bao cả nút trigger, nên nhấn lại trigger không bị
  double-toggle. Không có scrim của shell ở overlay `board-menu` (Overlays trả null), nên
  không có tranh chấp z-index: menu `z-30` nằm trong `aside z-20`, chồng đúng.
- Khôi phục pin khi đổi thread: `openThread` batch `setThreadId` + `dispatch({type:"thread"})`
  trong cùng một handler, nên effect restore luôn chạy sau khi shell đã clear. Guard
  `pinsSynced`/`restoredPins` đúng, không có write đè.
- `volume_at_price` phân bổ tick: bậc giá đổi ở 10.000 và 50.000 được đi bộ đúng
  (`_first_step_at_or_above` lấy tick tại `low`, vòng lặp lấy lại tick ở mỗi bước); bar
  `low == high` trả về đúng một mức; `Decimal('74500')` và `Decimal('74500.0000')` cùng
  hash nên dict ladder không tách đôi.
- Lọc bucket đang mở: `bucket_start` và `now` đều tz-aware VN, test chốt biên đến từng giây
  (`test_a_bucket_is_written_once_its_grace_has_elapsed_and_not_a_second_before`).
- `readableReason` với reason mới của `volume_at_price` ("Phiên chưa đóng, tính tới 11:00;
  chỉ đọc được 1/5 phiên gần nhất") — split `;` không khớp code nào, rơi về
  `isReaderSentence` và hiện nguyên câu. Đúng.
- Wire camelCase `methodNotes` / `columnRoles` / `pointRoles` khớp hai đầu; ba trường đều
  optional ở FE nên artifact cũ vẫn vẽ.
- `condition_checklist` giữ cả token cũ (`met`/`not_met`) lẫn tiếng Việt → panel cũ vẫn vẽ.
- Test mới không có test rỗng: `test_agent_loop.py` phễu, `test_ingest.py` biên grace,
  `test_volume_at_price.py` (cuối tuần / trước 09:31 / phiên đang chạy) đều assert hành vi.

---

## Việc nên làm, theo thứ tự

1. Gỡ chặn `make test`: đồng bộ `tests/test_provider_contracts.py` với
   `ProviderSource` mới (phiên phase-08).
2. H2 — Esc chỉ đóng lớp trên cùng.
3. H1 — `_merged_provenance` mang theo `methodNotes` + kiểm `reason`.
4. M3 — `SESSION_SETTLED_AT` suy từ `SETTLE_GRACE`.
5. M2 — quyết dứt: bỏ strip hay render strip; kéo theo M1 và câu chữ "thanh bảng".
6. M4 — xác nhận log sink trước khi giữ nguyên văn câu hỏi.
7. M5, M6, rồi nhóm Low.

## Câu hỏi chưa có lời

- `state.deskViews` (5 slot) còn được giữ để render lại strip ở phase sau, hay là tàn dư?
  Câu trả lời quyết định M1/M2 là "sửa" hay "xoá".
- Log của `_log_catalog_without_a_run` đi đâu ở prod? Có collector ngoài không?
- `methodNotes` có chủ ý cho model đọc (để nó nêu giới hạn trong prose) hay chỉ dành cho
  người đọc?
