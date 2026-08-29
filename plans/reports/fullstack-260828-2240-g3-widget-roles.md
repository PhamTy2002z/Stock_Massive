# G3 — màu widget theo vai trò ngữ nghĩa do engine khai báo

Ngày 2026-08-28 · nhánh `feat/study-canvas-runtime` · không commit.

## Hợp đồng

`Frame` nhận hai trường tuỳ chọn, mặc định rỗng nên artifact cũ vẽ y như cũ:

- `column_roles: Mapping[str, str]` — vai trò của **cả một series**, khoá theo tên cột.
- `point_roles: tuple[str | None, ...]` — vai trò của **một cột/điểm/ô**, khớp vị trí với `rows`.

Từ vựng đóng: `series · muted · focus · up · down · neutral · category:1..6`
(`PLAIN_ROLES`, `CATEGORY_ROLES`, `ROLES`, `CATEGORY_SLOTS = 6`, `role_error()`).
Validate trong `Frame.__post_init__` (Frame là frozen dataclass, **không** phải
pydantic model — validate ở `__post_init__` là chỗ tương đương duy nhất trong
file này). Bốn lỗi có thông điệp riêng: từ không thuộc enum · `category:0` /
`category:7` · role trỏ cột không tồn tại · số `point_roles` lệch số dòng.

Payload thêm `columnRoles` + `pointRoles`. `StudyResult.frames` vẫn không bao giờ
vào message — test transcript sẵn có (`test_the_frames_are_absent_from_the_messages_a_turn_would_send`)
pass nguyên.

### Bổ sung giữa chừng — `Provenance`

Theo yêu cầu bổ sung của user (strip in nguyên đoạn dài):

- `reason` ≤ **120** ký tự, một câu tiếng Việt, chỉ nói vì sao dữ liệu thiếu.
- `method_notes: tuple[str, ...]` mới, mặc định rỗng, mỗi mục ≤ **160** ký tự.
- Cả hai đi qua `_check_reader_sentence`: chặn chuỗi rỗng, chặn quá dài, chặn
  identifier dạng `snake_case` (regex, bắt cả tên chưa ai nghĩ tới), chặn 12 từ
  nghiệp vụ hệ thống (`store`, `artifact`, `frame`, `widget`, `provider`,
  `roster`, `universe`, `schema`, `column`, `endpoint`, `payload`, `dataframe`).
- `to_payload()` thêm `methodNotes`.

## File đổi

**API — `apps/api/src/studies/`**

| File | Nội dung |
|---|---|
| `contracts.py` | enum role + `role_error` · hai trường `Frame` + validate · `REASON_LIMIT`/`METHOD_NOTE_LIMIT` · `Provenance.method_notes` + validate |
| `widgets.py` | thêm v2 cho 5 widget, **giữ nguyên v1** |
| `intraday_liquidity.py` | `focus` cho khung giờ đỉnh ở `tiles`/`profile`/`ranking` · reason ngắn · 2 method note · bump v2 |
| `entry_condition_review.py` | `up/down` theo YoY ở `earnings_quarters`, `up/down` cho ô "Lợi nhuận 12 tháng" ở `tiles` · reason ngắn tiếng Việt · 4 method note · `_EVIDENCE_NAMES` · bump `stat_tiles`/`bar_series` lên v2 |
| `earnings_dislocation.py` | `category:1..4` theo vùng ở `scatter` · `focus` hạng 1 ở `ranking` · `focus` ô "Qua cả hai ngưỡng" · `METHOD_NOTES` viết lại · `_period_words`/`_count` · nhãn `dislocation_rank` → "Thứ hạng lệch pha" · bump 3 widget |

**Contracts sinh lại bằng `make contracts`:** `contracts/signal-desk-widget-catalog.json`
(9 → 14 mục) · `contracts/fixtures/artifact-intraday-liquidity.json`.

**Web**

| File | Nội dung |
|---|---|
| `app/globals.css` | `--widget-cat-1..6` cho `:root` và `.light` · cắt lại `--widget-series-muted` |
| `components/signal-desk/widgets/chart-theme.ts` | `colorFor(role)` · `resolveRoles(declared)` |
| `.../frame.ts` | `columnRole(frame, column)` · `pointRole(frame, index)` |
| `.../widgets/{bar-series,line-series,ranked-bars,scatter-quadrant,stat-tiles}.tsx` | tô theo role, giữ nguyên hành vi khi frame không khai gì |
| `.../widget-registry.ts` | đăng ký v2 cạnh v1, cùng một component |
| `lib/alpha-desk/types.ts` | `Frame.columnRoles?` + `Frame.pointRoles?` (phần `Provenance.methodNotes?` do G1 đã thêm) |

## Version widget

Năm widget lên **v2**: `stat_tiles` · `bar_series` · `ranked_bars` · `line_series`
· `scatter_quadrant`. `session_heatmap` · `range_strip` · `condition_checklist` ·
`data_table` giữ **v1** (không đọc role).

**v1 vẫn nằm trong catalog và trong registry FE, trỏ cùng component.** Bỏ v1 đi
thì mọi artifact đã lưu rơi xuống `data_table` — đúng thứ cơ chế version sinh ra
để tránh. Một component phục vụ cả hai là trung thực: frame của v1 không khai
role, mà component không nhận role thì vẽ đúng như trước. Viewer đời cũ chỉ biết
v1 gặp block v2 → fallback `data_table`, không crash (`widget-registry.test.ts`
giữ nguyên hai test degrade).

Hệ quả: `agent/tools/studies.py::_newest_version("line_series")` giờ trả 2, nên
Signal Desk model tự soạn cũng dùng v2. Controller đã sửa assert trong
`tests/test_agent_composition.py`.

## Contrast

Skill `dataviz` **không có** trong catalog skill của runtime (đã kiểm
`~/.claude/skills/`), nên tính bằng script Python (WCAG relative luminance) ở
scratchpad. Nền: dark `--widget-surface` = `220 5% 12%`, light = `0 0% 100%`.

| Token | Dark HSL | Dark | Light HSL | Light |
|---|---|---|---|---|
| `--widget-cat-1` | 190 70% 62% | 8.82:1 | 190 90% 27% | 5.88:1 |
| `--widget-cat-2` | 240 72% 74% | 5.68:1 | 240 62% 46% | 9.45:1 |
| `--widget-cat-3` | 300 55% 70% | 6.86:1 | 300 55% 40% | 6.29:1 |
| `--widget-cat-4` | 335 70% 68% | 5.90:1 | 335 70% 42% | 6.25:1 |
| `--widget-cat-5` | 75 52% 58% | 9.20:1 | 75 80% 25% | 5.42:1 |
| `--widget-cat-6` | 165 62% 52% | 8.59:1 | 165 90% 24% | 5.73:1 |
| `--widget-series-muted` (cắt lại) | 213 40% 56% | 4.68:1 | 217 40% 58% | 3.51:1 |

Tất cả ≥ 3:1 ở cả hai theme. Sáu hue cách nhau ≥ 25°, và cách ≥ 22° khỏi bốn màu
đã có nghĩa: amber ~30° (brand + focus), violet ~262° (đọc là *trần*), đỏ ~3°
(giảm), xanh lá ~140° (tăng). Ghi chú trong CSS nói rõ ràng buộc này, kèm luật
"category và up/down không cùng một bức tranh".

`--widget-series-muted` cũ (`213 26% 40%` / `217 38% 80%`) đo được **2.71:1** và
**1.70:1** — dưới sàn, và không code nào dùng (đã grep). Cắt lại để role `muted`
có màu dùng được; `SERIES_MUTED` (đường thứ hai mặc định của `line_series`) vẫn
trỏ `--widget-neutral`, không đổi hình.

## `focus` quá một

`resolveRoles` đếm `focus`; > 1 thì **rút hết** về `null` (không phải về
`"series"`), để mỗi widget rơi về mặc định của chính nó — biểu đồ về màu series
(`colorFor(null) === SERIES`), ô số về ink của trang. Không có crash, và **không
in chữ nào ra DOM**: theo luật cứng mới, "frame khai hai focus" là câu về hệ
thống, không phải về doanh nghiệp. `focusSpent` trả về cho test đọc.

## Luật cấm từ kỹ thuật trong text widget

- `bar-series.tsx`: khi frame tự khai role, ghi chú trần trục bỏ mệnh đề "được tô
  màu nhấn" (không còn đúng) — vẫn thuần tiếng Việt.
- `earnings_dislocation`: nhãn cột `dislocation_rank` → "Thứ hạng lệch pha";
  `2026-Q2` → "quý II/2026" ở tiêu đề panel, ô "Kỳ báo cáo" và reason; đếm mã
  nhóm kiểu Việt (`1.523`).
- `entry_condition_review`: cột `evidence` từng mang khoá frame và
  `condition-checklist.tsx` in thẳng vào tooltip "Số liệu trong khối
  `price_context`". Khoá vẫn là khoá **bên trong** `_Condition.evidence_ref`
  (test giữ liên kết khoá ↔ frame), nhưng dòng frame mang tên tiếng Việt qua
  `_EVIDENCE_NAMES`; nhãn cột đổi "Khối dữ liệu" → "Đối chiếu ở".
- vitest `widget-roles.test.tsx` khẳng định 18 từ (`frame`, `role`, `widget`,
  `store`, `artifact`, `kind`, `version`, `category:`, tên tool, tên widget…)
  không có trong `textContent` của 5 widget.
- Không đụng `signal-desk-block.tsx`, `provenance-strip.tsx` (G1).

## Test

Mới:

- `tests/studies/test_contracts.py` — 6 case role (mặc định im lặng · từ hợp lệ ·
  từ lạ · `category` ngoài 1..6 · role trỏ cột không có · lệch số dòng) + 5 case
  câu người đọc (reason quá dài · reason có code name / shop word · reason rỗng ·
  method note quá dài · method tách khỏi reason).
- `tests/studies/test_earnings_dislocation.py` — method nằm ở `method_notes`,
  screen khoẻ thì `reason is None`, không câu nào chứa từ cấm.
- `tests/studies/test_entry_condition_review.py` — dòng điều kiện trỏ bằng tiếng
  Việt, và mọi khoá `_EVIDENCE_NAMES` là frame có thật.
- `widgets/chart-theme.test.ts` — 12 role đều có token riêng · từ lạ → SERIES ·
  degrade `focus>1` · role thiếu.
- `widgets/widget-roles.test.tsx` — ô số tô theo role và giữ ink khi không khai ·
  degrade focus>1 trên tiles · ghi chú trần trục · role lạ không vỡ · anti-jargon
  cho 5 widget.
- `signal-desk/frame.test.ts` — `columnRole`/`pointRole`, kể cả frame đời cũ.

Kết quả:

| Cổng | Lệnh | Kết quả |
|---|---|---|
| API | `make test` (`apps/api`) | **1347 passed** |
| API | `make lint` | pass |
| Contracts | `make contracts` | deterministic, chạy lại không sinh diff |
| Web | `pnpm type-check` | pass |
| Web | `pnpm lint` | pass |
| Web | `pnpm test` | **57 file / 724 passed** |

`pnpm build` chưa chạy (theo yêu cầu).

Trong lúc làm có cửa sổ đỏ 49 case (`no such table: bar_daily`, bốn file
`test_agent_price_check` · `test_price_band` · `test_signal_registry` ·
`test_indicator_pack`) do commit `b18c9ac` của phiên khác; controller xác nhận là
cố ý và commit sau đã đóng lại. Lần chạy cuối xanh sạch.

## Việc đã chuyển cho người khác

- **`src/agent/tools/signals.py`** — reason của `get_series` ghép mã kỹ thuật
  (`insufficient_history: 3, …`) nên vi phạm contract mới. Đã báo, controller sửa
  ở phiên điều phối và xác nhận 11/11 pass. Tôi không đụng file này.
- **`tests/test_agent_composition.py`** — assert `widgetVersion == 1` thành sai
  sau bump; controller đã đổi sang `study_tools._newest_version("line_series")`.

## Còn tồn (không sửa, ngoài phạm vi đã giao)

1. `types.ts` docstring của `Provenance.reason` vẫn mô tả "free prose … may be an
   internal sentence in English … mapping in `lib/signal-issues.ts`". Backend giờ
   bảo đảm reason là một câu tiếng Việt ngắn, nên strip in thẳng được. File đang
   do G1 sửa nên tôi để nguyên — G1 nên cập nhật câu này cùng lúc vẽ strip.
2. Hai chỗ rò từ kỹ thuật **có sẵn từ trước**, đều hiện qua disclosure
   `data_table` chứ không qua widget chính:
   - `entry_condition_review._conditions_frame` cột `status` mang `met` /
     `not_met` / `unknown` (cột `status_text` bên cạnh đã là tiếng Việt);
   - `earnings_dislocation._filters_frame` cột `code` mang mã cửa lọc
     (`no_filing`, `thin_liquidity`…), nhãn cột đã tiếng Việt.
   Bỏ hẳn hai cột thì widget checklist mất token trạng thái; cần một quyết định
   nhỏ (ẩn cột khỏi bảng, hay để widget đọc token từ chỗ khác).
3. `globals.css:473` có `border-radius: 3px` ngoài thang DESIGN.md — hook design
   báo, nằm ở khối không thuộc thay đổi này, để nguyên.

Status: DONE
Summary: Frame khai được vai trò ngữ nghĩa cho series và cho từng điểm, sáu màu
nhóm mới đạt ≥3:1 ở cả hai theme, năm widget lên v2 mà artifact cũ vẫn vẽ; kèm
`Provenance.reason` ngắn + `method_notes` và dọn từ kỹ thuật khỏi text người đọc.
Concerns/Blockers: hai chỗ rò từ kỹ thuật có sẵn ở cột `status` và `code` (mục
"Còn tồn" #2) cần một quyết định trước khi coi luật cấm từ là kín; docstring
`Provenance.reason` ở `types.ts` chờ G1 nối.
