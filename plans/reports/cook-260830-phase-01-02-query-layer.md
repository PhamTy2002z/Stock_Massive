# Phase 01–02 — Amendment & Query layer

Plan: `plans/260829-2304-signal-desk-analysis-compiler/`
Thi công 2026-08-29 → 2026-08-30. Nhánh `develop`.

## Kết quả

| | |
|---|---|
| Phase 01 Amendment & roadmap | **Done** — 4/4 criteria |
| Phase 02 Query layer | **Done** — 5/6 criteria đạt, 1 đạt một phần có lý do vật lý |
| `make test` | **1776 passed**, 3 deselected (sau code review) |
| `pnpm type-check` · `lint` · `test` (837) · `build` | xanh |

## Phase 01 — bảng surface là ranh giới

`CLAUDE.md` nhận khối "Mở thêm 2026-08-29 cho plan `260829-2304`" đặt **sau**
khối C2 (các khối xếp theo thời gian). `docs/roadmap.md` §4 S1 viết lại:
Objective bằng năng lực thay vì "≥10 Study", bảng Trước→Sau 5 dòng, checklist
9 gate của phase 02–09. §3 C4 ghi hai mục "có desk?" và "frames không lọt?"
thuộc phase 09 plan này. §6 giữ nguyên hướng cạnh C4→S1.

Ba đính chính với code thật, ghi ngay trong khối amendment:

1. **Head alembic là `b5d1c7e04a83`**, một head duy nhất (35 revision) — không
   phải `a3f7e21b8d54`, và không có hai head như plan nghi.
2. **`pandas>=2.0.0` / `numpy>=1.24.0` đã ở `requirements.txt:50-51`**;
   `intraday/ingest.py` đã import pandas. Câu hỏi mở #2 của plan (dependency
   của phase 03) **đã có trả lời**, không phải hỏi.
3. **`plans/260826-2158-study-artifact-canvas/` không còn tồn tại** (retire ở
   commit "retire the plans that closed"), nên con trỏ kế nhiệm của bước 4
   không có đích. `relatedTo` giữ tên đó như bản ghi lịch sử.
   `260829-2141-c2-context-and-cache` **đã có** dòng `relatedTo` trỏ ngược lại.

## Phase 02 — số đo

| Criterion | Đo được |
|---|---|
| `query(statement,[VIC,VCB],8 quý)` → 16 hàng × (2+n) cột, VCB thiếu dòng → `statement_line_missing: 8` | **16 hàng × 5 cột**, `{"VCB:statement_line_missing": 8}` — `gross_profit`, VCB là ngân hàng |
| `compare_fields` role đúng hướng `better` | VCB thắng ROE (56,7>23,3) và `max_drawdown_pct` (−28,4>−32,1); VIC thắng ADTV (1,23 nghìn tỉ>304 tỉ) |
| `market_cap_absent` VCB 3→0, ≥28/33 phục vụ | **VCB 28/33** (từ 25) · VNM **29/33** · MWG **29/33** |
| Nhãn ≥95% item_id có `label_vi` | **100%** (645/645); ratio 75/75 |
| Intraday 30/30 mã ≥240 phiên | 30/30 mã có dữ liệu, **29/30 ≥245**; TCX **214** = toàn bộ lịch sử của nó |
| Transcript: frame không lọt | test trên `build_messages` xanh |

**Vì sao TCX không đạt 240 và vì sao đó không phải lỗi:** phiên `bar_daily` đầu
tiên của TCX là **2025-10-21**, tổng 213 phiên. 214 phiên intraday là *nhiều
hơn* lịch sử daily của nó. Trần là ngày niêm yết.

## Bốn thứ code thật nói khác plan

**1. Nhãn cần bốn mã đại diện, không phải ba.** STB/SSI/HPG phủ **88,7%**; 73
id còn lại **toàn bộ** là mẫu bảo hiểm (`provision_for_catastrophe_reserve`,
`subrogation_recoveries`, `loss_from_life_insurance`). Thêm BVH → **100%**.
Đây đúng là phản ứng plan đã ghi sẵn ở *Risk Assessment*.

**2. Response ratio không có `item_en`.** Bản đầu đòi đủ ba `META_COLUMNS` nên
**mọi** nhãn `ratio` bị từ chối — KBS trả `['item','item_id','2026-Q2',…]`, và
docstring của `fetch_ratio` đã ghi sẵn KBS bỏ qua `lang="en"`. Sửa: bắt buộc
`item`+`item_id`, `label_en` để `NULL`.

**3. `Provenance.source` đóng vốn từ làm bốn Study cũ sai.** Cả bốn ghi
`source="vnstock"` — tên nhà cung cấp, không phải *nơi số đến từ*. Đổi sang
`"store"`, đẩy provider xuống `query={"provider":"vnstock"}` nên không mất byte.
FE **không đọc** trường này (`types.ts:280-288`: "Not shown to a reader") và ba
test FE khẳng định người đọc không bao giờ thấy chữ "vnstock" — cả ba vẫn xanh.

**4. Reader `reference` phải ở `stocks/signals/bars.py`.** Cùng một phép đọc
phục vụ hai caller (nhánh market cap + source `reference` của `query`), và
`src/stocks/*` không được import `src/agent/*` — nên đây là chiều import duy
nhất hợp lệ. `reference_snapshots` là phép đọc, `share_counts` là phép chiếu
của nó. Preload trên `BarPreparationContext._shares`: một field cross-sectional
dựng một context rồi gọi `prepare_bars` cả trăm lần.

## Ba quyết định thiết kế đáng ghi

**`cell_roles` là granularity thứ ba, và so sánh cần đúng nó.** Bảng mã × field
có winner theo *cột* và mã theo *hàng*; khẳng định thật là "mã này thắng ở chỉ
báo này". Viết bằng `point_roles` sẽ thành "cả hàng thắng" — đúng câu mà bảng so
sánh sinh ra để tránh. Lên wire là danh sách triple: khoá JSON chỉ là chuỗi.

**`better` không suy được từ `Sign`.** `roe_percentile` và `amihud_illiq` đều
`non_negative`, mà cao là tốt ở cái đầu và xấu ở cái sau. **20/33** field khai
hướng; 13 field còn lại cố ý không (beta là *phơi nhiễm* khác nhau chứ không tệ
hơn; RSI/MACD/BB là vị trí; `size_percentile` to hơn không phải tốt hơn).
Mặc định `None` → không đánh dấu, chứ không đoán.

**Market cap suy từ close *đã công bố*, không phải close đã rebase.** Số cổ
phiếu là số của ngày nó được quan sát; nhân với giá đã quy về mệnh giá mới nhất
của cửa sổ là áp phép chia tách hai lần.

## Ba thứ ngoài kế hoạch phase, đều đã ghi thành dòng bảng có ngày

**`src/stocks/signals/fields.py`** — plan ghi trường `better` ở `registry.py`,
nhưng dataclass sống ở `fields.py`. Thêm enum `Direction` + một trường tuỳ chọn.

**`src/agent/tools/__init__.py`** — `register_all` gọi thêm registrar. Đặt
**sau** `register_price_check_tool` để thứ tự registry khớp thứ tự bundle mở ra.

**`src/agent/prompt/sections.py` — bump 3.1.0 → 3.2.0.** Một tool đã đăng ký mà
prompt không gọi tên là một tool model không với tới, và
`test_the_prompt_names_every_tool_the_agent_actually_has` khẳng định đúng điều
đó. **Chỉ prose danh mục** (238 token đo được), không luật, không playbook.
Hai gate token của C5 **giữ nguyên ngưỡng** và trừ hằng
`CATALOGUE_GROWTH_SINCE_THE_SPLIT = 238` có tên — nới trần sẽ làm bằng chứng
của C5 ngừng đo thứ nó được viết ra để đo.

## Một bug thật trong test đang có

`test_the_loop_names_no_particular_domain` quét `loop.py` tìm **chuỗi con** tên
mỗi tool domain. Một tool tên `query` làm nó đỏ vì một *comment* trong `loop.py`
nói "query inside the deployment" — đúng cái bẫy docstring của chính test đó
cảnh báo với chữ "domain". Siết thành tìm **string literal** (`"query"` /
`'query'`), tức đúng hình dạng thật của việc hardcode.

## Ảnh hưởng sang plan khác

**C2 (`260829-2141`, in_progress).** `PROMPT_VERSION` đổi và `system_core` dày
thêm 238 token, nên baseline replay của C2 (đo `system_core` **53,3%**) là số
của prompt **3.1.0**. Cần đo lại sau khi C2 phase 05 đóng. Phase 08 của plan
này vẫn `blockedBy` C2 phase 05 như đã ghi.

## Vận hành đã chạy

- Backup `backups/pre-statement-item-labels-260829.sql.gz` (15M, `gzip -t` xanh)
- Revision `c4e8a1f70b62` (additive-only; `downgrade` là `drop_table`)
- `make seed-statement-labels` — 16 request, 778 dòng nhãn
- `make backfill-intraday SCOPE=declared` — 30/30 mã, ~4.000 dòng/mã, hai lần
  provider timeout tự hồi phục, 0 mã fail
- `_fetch_from_vnstock` giờ đi qua `quota_arbiter()` — trước đó **không** đi,
  tức nó tiêu slot mà không đếm, cạnh một daily spine đang đếm

## Code review — một CRITICAL, bốn HIGH, đã sửa hết

| # | Mức | Vấn đề | Sửa |
|---|---|---|---|
| 1 | CRITICAL | `corporate_actions` hỏi `getattr(action,"ratio",None)` / `"cash_amount"` — **hai cột không tồn tại** (thật là `exercise_ratio`/`value_per_share`). Default nuốt `AttributeError` → mọi ô `None`, `missing` báo **không thiếu ô nào** | đọc thẳng thuộc tính, bỏ default; nhãn đổi theo docstring của `models.py` ("đọc theo `kind`, không theo tên"); thêm cột `confirmation` |
| 2 | HIGH | `frameId` là khoá **cuối**, mà `budget.py` cắt giữ **phần đầu** → một bản đọc rộng mất đúng thứ duy nhất vẽ được, sau khi row đã commit | `frameId` lên đầu cả hai tool; `columns`+`labels` → `columnCount` + `columnSample` (12 tên) |
| 3 | HIGH | `compare_fields` không truyền `cross_sections`/`peers` → 10 mã × 5 field ranked = **50** lượt xếp hạng toàn Universe cho việc cần **5** | hoist ra ngoài vòng lặp. Đo: 10×8 = **1,164 s**, 80/80 ô |
| 4 | HIGH | market cap suy diễn: không cutoff theo phiên (giá quá khứ × cổ phiếu hôm nay), `STALE_MARKET_CAP` thành nhánh chết, `.date()` lệch VN_TZ | `on_or_before=` + VN_TZ + **chỉ suy diễn khi `0 ≤ tuổi ≤ REFERENCE_STALE_DAYS`**; ngoài biên giữ `market_cap_absent` như trước |
| 5 | HIGH | test **không gọi handler nào** — hai test "chứng minh ba luật" tự viết payload rồi assert trên chính literal đó | file test seed store của chính nó (30 phiên + phiên index + một corporate action); **29 passed, 0 skipped** |

MEDIUM/LOW đã sửa: `ratio` lấy kỳ từ bảng ratio (hai bảng ghi độc lập, rollback
theo part) · mã refusal `quarter_not_filed` tách khỏi `statement_line_missing` ·
`MAX_WINDOW`/`MAX_ITEMS` vào schema + ước lượng chặn **trước** khi query chạy ·
`QuotaRefused` → `StudyRefused(COHORT_WARMING)` ở `warmup` (nếu không, một
Study intraday với Redis chết thành lỗi tool thô đếm vào `same_tool_failure_halt_after`) ·
`.PHONY` · comment "Twelve"→"Sixteen" · `_coverage` đếm cả bảng ratio · seed
script `acquire()` thật · `ShareCount` → `SharesOnRecord` (trùng tên với
`providers/contracts.ShareCount`) · `_window(True)` không còn thành 1 ·
`no_dated_corporate_action`.

**Một finding không sửa, có lý do:** `cell_roles` chưa được FE đọc — đó đúng là
phạm vi **phase 06** trong bảng surface. Đã đổi tên test cho khớp thứ nó thật sự
chứng minh.

**Sau sửa:** `make test` **1776 passed** · năm cổng web xanh · sáu nguồn `query`
đều trả frame trên store thật, chậm nhất 0,030 s.

## Chưa chốt

1. Câu hỏi #3 và #4 của plan (ai viết 50 câu golden; khi nào gửi 9 câu go/no-go
   Bronze) vẫn mở — thuộc phase 09 và 10.
2. Baseline `system_core` của C2 cần đo lại dưới prompt 3.2.0.
3. TCX sẽ tự đạt ≥240 phiên intraday vào khoảng 2026-09, không cần hành động.
