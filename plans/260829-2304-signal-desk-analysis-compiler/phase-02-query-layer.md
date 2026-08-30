---
phase: 2
title: "Query layer — frame từ store"
status: completed
priority: P1
effort: "20h"
dependencies: [1]
---

# Phase 2: Query layer — frame từ store

## Overview
Mở toàn bộ bảng thô của store cho model dưới dạng **frame** (không trả số):
`query` đọc nhiều mã × nhiều cột × cửa sổ từ sáu nguồn; `compare_fields` trả
bảng mã × Signal Field có role thắng/thua. Kho BCTC 302k dòng đi vào agent lần
đầu. Đây là trục "dữ liệu" của compiler.

## Requirements
- Functional:
  - Tool `query(source, symbols[≤10], columns?, window, statement?, items?)`
    → `frameId` + summary (n hàng, n cột, as_of, refusal đếm). `source ∈
    {bar_daily, intraday_15m, statement, ratio, reference, corporate_actions}`.
  - Tool `compare_fields(symbols[2..10], field_ids[1..8])` → frame `table`
    hàng = mã, cột = field, `point_roles`/`cell_roles` `winner|loser` theo
    hướng tốt của field (khai trong registry, mặc định "cao là tốt", các field
    rủi ro/illiquidity đảo).
  - Mọi luật của `get_field` giữ per-cell: field đăng ký · mã trong Universe ·
    phiên đã đóng · refusal thành `null` + đếm trong provenance.
  - Frame nhiều mã: cột `symbol` đứng đầu; frame theo thời gian giữ cột
    `session`/`period` đầu; labels tiếng Việt cho mọi cột (BCTC lấy từ bảng
    nhãn mới).
  - `market_cap_vnd` suy từ `close × reference.shares` khi bar không có →
    `market_cap_absent` VCB 3 → 0 trên store thật.
  - Backfill intraday 30 mã declared (1 request/mã, tier free).
- Non-functional: `MAX_QUERY_CELLS = 50_000`, `MAX_QUERY_ROWS = 5_000`; trả
  lời < 2 s trên store thật cho 10 mã × 8 quý × 174 chỉ tiêu; tool
  `reads_external=False`, `ToolAccess.STORE`, `PARALLEL_SAFE`.

## Architecture
```
query(args) ── validate ── reader theo source ── Frame ── frames_buffer.store_frame ── {frameId, summary}
                              │ bar_daily → stocks/signals/bars (BarFrame) hoặc select trực tiếp bar_daily
                              │ intraday_15m → stocks/intraday/reads
                              │ statement → stocks/financial/reads.lines_for / (mới) lines_for_many
                              │ ratio → financial/reads.ratios_for / (mới) ratios_for_many
                              │ reference → provider_snapshots capability=reference (shares, foreign room)
                              └ corporate_actions → bảng corporate_actions
```
- `frames_buffer.store_series` tổng quát hoá thành `store_frame(kind_tag, …)`
  với `study_name ∈ {field_series, query_frame, compare_frame}`; `read_frame`
  và ownership theo `turn_id` **không đổi**.
- Frame BCTC: kind `table`, cột = `period` + item_id đã chọn; item không có
  ở template ngân hàng → `null`, đếm `statement_line_missing`. Labels từ
  `financial_statement_item` (mới): `(statement, item_id) → label_vi, label_en`,
  nạp một lần bằng `fetch.py` (response đã có `item`, `item_en`) cho ba mã đại
  diện ba template (STB, SSI, HPG) + hợp nhất.
- `compare_fields` gọi `figure_for_field` per (mã, field) ở phiên gần nhất;
  hướng tốt là trường mới `SignalField.better = "higher" | "lower" | None`
  khai trong `stocks/signals/registry.py` — **một trường thêm**, không đổi công
  thức. `None` → không gán role.

## Related Code Files
- Create: `apps/api/src/agent/tools/query.py` (tool `query` + `compare_fields`,
  schema, summarise, readers dispatch)
- Create: `apps/api/alembic/versions/<rev>_add_financial_statement_item_labels.py`
- Create: `apps/api/scripts/seed_statement_item_labels.py` + Makefile target
- Modify: `apps/api/src/studies/frames_buffer.py:68-108` (`store_frame`),
  `:44-56` (kind tags)
- Modify: `apps/api/src/studies/contracts.py:91-99` (roles thêm
  `winner, loser, benchmark, warning, stale`), `:295-335` (`Provenance.source`
  vocab `store|web|derived` + trường `query`)
- Modify: `apps/api/src/stocks/financial/reads.py` (thêm `lines_for_many`,
  `ratios_for_many`; không đổi hàm cũ)
- Modify: `apps/api/src/stocks/signals/registry.py` (trường `better`),
  `apps/api/src/stocks/signals/bars.py` (market cap từ shares)
- Modify: `apps/api/src/alpha/models.py` (model `FinancialStatementItem`)
- Modify: `apps/api/src/agent/toolsets.py:46-89` (`signals` += `query`,
  `compare_fields`); test đếm tool tương ứng
- Modify: `apps/api/src/stocks/intraday/ingest.py` + `apps/api/Makefile`
  (`backfill-intraday SCOPE=declared`)
- Tests: `apps/api/tests/test_agent_query_tools.py` (mới),
  `tests/test_agent_study_tools.py` (frames absent mở rộng),
  `tests/test_signal_cross_sectional.py` hoặc file sở hữu `market_cap_absent`
  (cuối file), `tests/studies/test_frames_buffer.py`

## Implementation Steps
1. **Backup DB** trước revision (`backups/pre-statement-item-labels-<date>.sql.gz`).
2. Model + revision `financial_statement_item`; parent đọc bằng `alembic heads`
   lúc thi công (hiện `a3f7e21b8d54`; kiểm có hai head không —
   `b5d1c7e04a83` tồn tại).
3. Script seed nhãn: fetch STB/SSI/HPG qua `financial/fetch.py`, ghi
   `(statement, item_id, label_vi, label_en)`; upsert; log số dòng; chạy một
   lần, kết quả đếm ghi vào report phase.
4. `contracts.py`: roles mới + `Provenance.source` vocab; test `role_error`.
5. `frames_buffer.store_frame`; giữ `store_series` là wrapper mỏng.
6. `financial/reads.py`: `lines_for_many(session, symbols, periods, items) →
   dict[(symbol, period, item_id) → Decimal]`, `ratios_for_many`.
7. `tools/query.py`: schema (enum source, giới hạn), readers, dựng Frame,
   labels, provenance (`sessions_used`, `health`, refusal đếm), summary cho
   model (≤ 60 token: nguồn, kích thước, as_of, số ô null theo mã).
8. `compare_fields`: đọc `figure_for_field`, gán role theo `better`; frame kind
   `table`; provenance gộp theo `_merged_provenance` hiện có.
9. `bars.py`: nhánh suy market cap; test trên VCB thật: `factor_percentiles.*`
   phục vụ thay vì `market_cap_absent`.
10. `toolsets.py` + test đếm; `list_fields` không đổi.
11. Intraday backfill target; chạy cho 30 mã; ghi số bar vào report.
12. Test frames-absent: transcript sau `query`/`compare_fields` không chứa số
    ngoài summary.

## Success Criteria
- [x] `query(statement, [VIC,VCB], periods=8, items=[revenue…,net_profit…])`
      trả frame 16 hàng × (2+n) cột trên store thật; VCB thiếu doanh thu →
      `null` + `statement_line_missing: 8`. **Đo:** 16 hàng × 5 cột,
      `{"VCB:statement_line_missing": 8}` — `gross_profit`, VCB là ngân hàng.
- [x] `compare_fields([VIC,VCB], [roe_percentile, adtv_vnd, max_drawdown_pct])`
      trả role winner/loser đúng hướng `better`. **Đo:** VCB thắng ROE
      (56,7 > 23,3) và thắng `max_drawdown_pct` (−28,4 > −32,1, nông hơn là
      tốt hơn); VIC thắng ADTV (1,23 nghìn tỉ > 304 tỉ).
- [x] `market_cap_absent` VCB 3 → 0; 33 field VCB đo lại ≥ 28 phục vụ.
      **Đo:** VCB **28/33** (từ 25), VNM và MWG **29/33** (từ 26). Refusal còn
      lại đúng như khai: 3 × `foreign_flow_not_stored`, 1 × `unavailable`
      (`beta_vs_market_index`), 1 × `statement_line_missing`.
- [~] Intraday 15m: 30/30 mã declared có ≥ 240 phiên. **Đo:** 30/30 mã có dữ
      liệu; **29/30 có ≥ 245 phiên**, TCX có **214** — và 214 là *toàn bộ lịch
      sử của nó*: phiên daily đầu tiên của TCX là 2025-10-21, tổng 213 phiên.
      Trần là ngày niêm yết, không phải backfill.
- [x] Nhãn: ≥ 95% item_id trong store có `label_vi`. **Đo: 100%** (645/645).
      Lượt đầu ba mã đại diện cho 88,7%; 73 id còn lại **toàn bộ** là mẫu bảo
      hiểm, nên seed thêm BVH — đúng phản ứng ghi trong *Risk Assessment*.
- [x] Transcript test: không frame nào lọt; `make test` xanh.
      **Đo:** `make test` **1769 passed**; năm cổng web xanh.

## Risk Assessment
- Nhãn không phủ item_id lạ (template bảo hiểm) → fallback label = item_id
  humanised, đếm `label_missing` trong provenance; tín hiệu: < 95% → nạp thêm
  mã đại diện, không đoán nhãn.
- `reference.shares` cũ (220 dòng, 30 mã) → market cap stale; provenance ghi
  `stale_shares` với ngày; phase 10 làm tươi.
- Đọc 10 mã × 174 item × 8 quý một câu SQL — đo; > 2 s → index
  `(symbol, period)` đã có? kiểm `e6b3d90c41af`.


## Evidence — thi công 2026-08-29/30

**Backup trước migration:** `backups/pre-statement-item-labels-260829.sql.gz`
(15M, `gzip -t` xanh). Revision `c4e8a1f70b62`, parent `b5d1c7e04a83` đọc từ
`alembic heads` lúc thi công — **một head duy nhất**, không phải hai như plan
nghi, và không phải `a3f7e21b8d54` như plan ghi. Additive-only, nên `downgrade`
là `drop_table` chứ không `NotImplementedError`.

**Nhãn cần bốn mã, không phải ba.** STB/SSI/HPG phủ 88,7%; 73 id thiếu **toàn
bộ** là dòng của doanh nghiệp bảo hiểm (`provision_for_catastrophe_reserve`,
`subrogation_recoveries`, `loss_from_life_insurance`). BVH đưa lên **100%**.
`REPRESENTATIVES` giờ là bốn mã, có ghi lý do tại chỗ.

**`item_en` là tuỳ chọn, và đó là phép đo.** Bản đầu đòi đủ ba `META_COLUMNS`
nên **mọi** nhãn `ratio` bị từ chối: response KBS trả `['item','item_id',
'2026-Q2',…]` và không có cột tiếng Anh — chính docstring của `fetch_ratio` đã
ghi KBS bỏ qua `lang="en"`. Sửa: bắt buộc `item` + `item_id`, `label_en` để
`NULL`. Kết quả 75/75 id ratio có nhãn.

**`Provenance.source` đóng vốn từ làm bốn Study cũ sai.** Cả bốn ghi
`source="vnstock"` — tên nhà cung cấp, không phải *nơi số đến từ*. Đổi sang
`source="store"` và đẩy tên provider xuống `query={"provider": "vnstock"}`, nên
không mất byte nào. FE **không đọc** trường này (`types.ts:280-288` ghi rõ
"Not shown to a reader"), và ba test FE khẳng định người đọc không bao giờ thấy
chữ "vnstock" — cả ba vẫn xanh. `contracts/fixtures/artifact-intraday-
liquidity.json` sinh lại bằng `make contracts`.

**Reader `reference` ở `stocks/signals/bars.py`, không ở `tools/query.py`.**
Cùng một phép đọc phục vụ hai caller (nhánh market cap và source `reference`),
và `src/stocks/*` không được import `src/agent/*`, nên đây là chiều import duy
nhất hợp lệ. `reference_snapshots` là phép đọc; `share_counts` là phép chiếu
của nó — không phải hai truy vấn. Preload trên `BarPreparationContext._shares`:
một field cross-sectional dựng một context rồi gọi `prepare_bars` cả trăm lần,
và đọc share count trong vòng lặp đó là một trăm truy vấn cho một câu trả lời
không đổi.

**Market cap suy từ close *đã công bố*, không phải close đã rebase.** Số cổ
phiếu là số của ngày nó được quan sát; nhân nó với giá đã quy về mệnh giá mới
nhất của cửa sổ là áp phép chia tách hai lần.

**`SignalField.better` khai ở `fields.py`, đặt giá trị ở `registry.py`.**
Trường tuỳ chọn mặc định `None`, khác chín khai báo bắt buộc — và bất đối xứng
đó là chủ đích: chín cái kia đúng với mọi số hệ thống công bố, cái này là một
phán đoán chỉ một số figure chấp nhận. **20/33 field** khai hướng; 13 field
còn lại không (beta là *phơi nhiễm* khác nhau chứ không tệ hơn; RSI/MACD/BB là
vị trí; `size_percentile` to hơn không phải tốt hơn). `Sign` **không** thay thế
được: `roe_percentile` và `amihud_illiq` đều `non_negative` mà cao là tốt ở cái
đầu và xấu ở cái sau.

**`cell_roles` là granularity thứ ba, và so sánh cần đúng nó.** Bảng mã × field
có winner theo *cột* và mã theo *hàng*; khẳng định thật là "mã này thắng ở chỉ
báo này". Viết bằng `point_roles` sẽ thành "cả hàng thắng" — đúng câu mà một
bảng so sánh sinh ra để tránh. Lên wire là danh sách triple, không phải object
lồng: khoá JSON chỉ là chuỗi, nên `(row, col)` sẽ phải viết `"3|roe"` rồi parse
lại ở đầu kia.

**Ba luật của role, đều có test:** cột không khai hướng → không đánh dấu; chỉ
một ô có số → không đánh dấu (một mình thì không có gì để hơn); hoà → không
đánh dấu.

**`query`/`compare_fields` đăng ký **sau** `check_price_claim`** để thứ tự
registry khớp thứ tự bundle `signals` mở ra. Hai thứ tự lệch nhau là hai hợp
đồng phải khai riêng, và resolved-surface cache key trên một trong hai.

**Ba test hợp đồng phải sửa, và một trong ba là bug thật của test:**
`test_the_loop_names_no_particular_domain` quét `loop.py` tìm **chuỗi con** tên
mỗi tool domain. Một tool tên `query` làm nó đỏ vì một *comment* trong `loop.py`
nói về "query inside the deployment" — đúng cái bẫy docstring của chính test đó
cảnh báo với chữ "domain". Siết lại thành tìm **string literal** (`"query"` /
`'query'`), tức đúng hình dạng thật của việc hardcode.

**Prompt bump 3.1.0 → 3.2.0, và đây là bề mặt duy nhất ngoài kế hoạch phase.**
Một tool đã đăng ký mà prompt không gọi tên là một tool model không với tới —
`test_the_prompt_names_every_tool_the_agent_actually_has` khẳng định đúng điều
đó. Chỉ thêm **prose danh mục** (238 token đo được), không đổi một luật nào,
không đụng playbook. Hai gate token của C5 giữ nguyên ngưỡng và trừ đi hằng
`CATALOGUE_GROWTH_SINCE_THE_SPLIT = 238` có tên, thay vì nới trần — nới trần sẽ
làm bằng chứng của C5 ngừng đo thứ nó được viết ra để đo.

**Ảnh hưởng C2:** `PROMPT_VERSION` đổi và `system_core` dày thêm 238 token, nên
baseline replay của plan `260829-2141-c2-context-and-cache` (đo `system_core`
53,3%) là **số của prompt 3.1.0**. Cần đo lại sau khi C2 phase 05 đóng.

**Backfill intraday:** 30/30 mã, ~4.000 dòng/mã, hai lần provider timeout tự
hồi phục, không mã nào fail. `_fetch_from_vnstock` giờ đi qua
`quota_arbiter()` — trước đó **không** đi, tức nó tiêu slot mà không đếm, cạnh
một daily spine đang đếm.

**Tốc độ, và một điều bảng số nói ra.** `query(statement, 10 mã, 8 quý, mọi
dòng)` chạy **0,124 s** trên store thật — ngưỡng phi chức năng là 2 s. Nhưng nó
trả **80 hàng × 574 cột = 45.920 ô**, tức *lọt* trần `MAX_QUERY_CELLS = 50.000`
trong gang tấc. 574 cột không phải một bức tranh. Trần ô chặn được cái tệ hơn,
còn cái này là việc của composer ở phase 05: `items` là cách nói "câu hỏi hỏi
về mấy dòng nào", và một frame không nêu `items` là một frame chưa được hỏi
đúng. Ghi lại vì đây là số để đặt lại ngưỡng nếu phase 09 thấy cần.

**Không chạm:** `src/stocks/realtime/*`, `providers/normalize.py`,
`agent/messages.py`, `agent/loop.py`, prune/estimate (C2 sở hữu), `apps/web/*`
ngoài `contracts/fixtures/*` sinh lại.

## Code review — 2026-08-30, và mười một thứ nó bắt được

Reviewer đọc 1.208 dòng `query.py` + toàn bộ diff. Một CRITICAL, bốn HIGH, sáu
MEDIUM/LOW. **Tất cả đã sửa và kiểm chứng lại bằng phép đo, không phải bằng
lập luận.**

**CRITICAL — hai cột `corporate_actions` chết vĩnh viễn.** Reader hỏi
`getattr(action, "ratio", None)` và `getattr(action, "cash_amount", None)`;
`CorporateAction` **không có** hai cột đó — tên thật là `exercise_ratio` và
`value_per_share`. `getattr` có default nên `AttributeError` bị nuốt, mọi ô trả
`None`, và `missing` báo với model rằng **không thiếu ô nào**. Hai trên bốn cột
của một nguồn chưa bao giờ chạy. Sửa: đọc thẳng thuộc tính, **không** `getattr`
default. Nhãn cũng sai — docstring của `models.py` nói feed đặt *tiền theo mệnh
giá* vào `exercise_ratio` trên cổ tức tiền mặt, "đọc theo `kind`, không bao giờ
theo tên" — nên nhãn giờ là *"Tỉ lệ/giá trị theo công bố"*, và cột
`confirmation` được thêm vì một action chưa xác nhận không được phục vụ như sự
thật. Đo lại: 34 hàng cho 5 mã, `exercise_ratio` có số thật.

**HIGH — `frameId` là khoá cuối cùng, tức là thứ bị cắt đầu tiên.** Rung hai
của `budget.py` thay kết quả quá cỡ bằng preview của **phần đầu**. Một bản đọc
BCTC rộng (574 cột đo được ≈ 44.000 ký tự) vượt `MAX_RESULT_CHARS = 32.000`, và
thứ mất đi là **đúng cái duy nhất vẽ được** — sau khi một dòng `agent_artifact`
đã commit. Tool "thành công" và vô dụng. Sửa: `frameId` là khoá **đầu tiên** của
cả hai tool; `columns`+`labels` đầy đủ thay bằng `columnCount` + `columnSample`
(12 tên đầu). Người đọc vẫn thấy đủ tiêu đề — trong panel, chỗ tiêu đề thuộc về.

**HIGH — `compare_fields` chạy cross-section N×M.** `figure_for_field` nhận
`cross_sections=`/`peers=` **đúng vì việc này** ("a cohort measures its rankings
once and passes them in"), vòng lặp không truyền cái nào. 10 mã × 5 field ranked
= **50** lượt xếp hạng toàn Universe cho một câu trả lời cần **5**, mỗi lượt
dựng cửa sổ tới 273 phiên/mã, trên một tool giữ worker thread. Sửa: hoist
`peers` và `serve_cross_section` ra ngoài vòng lặp. Đo: **10 mã × 8 field
(5 ranked) = 1,164 s**, 80/80 ô có số.

**HIGH — market cap suy diễn biến từ chối trung thực thành số sai im lặng.**
Ba lỗi chồng nhau: (a) không có cutoff theo phiên, nên
`serve_cross_section(end=<quá khứ>)` nhân giá tháng Ba với số cổ phiếu tháng
Tám, và cùng một cutoff cho kết quả khác nhau mỗi ngày tính lại; (b)
`STALE_MARKET_CAP` thành nhánh chết vì **mọi** bar giờ có cap, trong khi độ cũ
thật — số cổ phiếu quan sát bao lâu rồi — không đo ở đâu cả (`observed_on` được
điền và **không caller nào đọc**); (c) `.date()` thay vì
`.astimezone(VN_TZ).date()`, lệch với reader anh em của **cùng một bảng**.

Sửa cả ba: `reference_snapshots(..., on_or_before=)` viết đúng như
`reference.foreign_room_on_or_before` viết, VN_TZ, và **nhánh chỉ suy diễn khi
`0 ≤ (phiên − ngày quan sát) ≤ REFERENCE_STALE_DAYS`** — hằng đọc off hợp đồng
Capability reference chứ không khai lại. Ngoài hai biên đó bar giữ `None` và
field từ chối `market_cap_absent` **đúng như trước khi nhánh này tồn tại**.
Phục vụ một số sai với mọi tín hiệu độ tươi nói "ổn" tệ hơn hẳn là từ chối.
Đo: VCB vẫn **28/33** (reference hiện cũ 5 ngày); `share_counts(cutoff=
2026-08-01)` → **0 dòng**, `cutoff=2026-08-24` → **2** — cutoff tự chứng minh.

**HIGH — test không gọi handler nào.** Đúng: lời gọi handler duy nhất là một
`raise` trước khi mở session. Hai test "chứng minh ba luật" **tự viết payload**
rồi assert trên chính literal đó. Sửa: file test giờ **seed store của chính
nó** — 30 phiên `bar_daily` cho hai mã + phiên index (lịch Trading Day đọc off
`series='index'`, nên seed equity không thôi cho ra một store có bar mà không
có phiên) + một `CorporateAction` — và **mọi** test gọi handler thật.
**29 passed, 0 skipped.** Bản trước skip 6 test trên máy không có backfill, tức
mọi khẳng định về handler âm thầm không chạy.

**MEDIUM — `ratio` lấy cửa sổ kỳ từ bảng statement.** Hai bảng được ghi từ hai
response provider **độc lập** và `ingest_symbol` rollback theo part, nên một mã
có ratio Q2 mà statement Q2 fail sẽ **không bao giờ** trả Q2, không refusal nào
nói tại sao. Sửa: `ratio_periods_for_many` đọc bảng ratio.

**MEDIUM — refusal trỏ sai input thiếu.** `periods` là **hợp** các kỳ mọi mã
có, nên một mã nộp 4/8 quý nhận `statement_line_missing` cho **từng cột** của 4
hàng rỗng — sự thật là "thiếu 4 quý", không phải "không khai 20 dòng".
`CLAUDE.md` nói rõ mã refusal phải trỏ đúng input thiếu. Sửa:
`periods_held_by` + mã mới `quarter_not_filed`.

**MEDIUM — trần chỉ kiểm sau khi đã đọc.** `window=34` × 10 mã không `items` nạp
~68.000 dòng vào một dict rồi mới từ chối — trần bảo vệ context của model, không
bảo vệ process. Sửa: `MAX_WINDOW = 250` và `MAX_ITEMS = 60` vào **schema**, cộng
một ước lượng `symbols × periods × WIDEST_STATEMENT_LINES` chặn **trước** khi
query chạy. Câu hỏi thường (10 mã × 8 quý = 16.000) vẫn chạy — nó là câu hỏi
tool này sinh ra để trả.

**MEDIUM — `quota_arbiter().acquire()` đổi hành vi lane chat, không chỉ CLI.**
`_fetch_from_vnstock` nằm trên đường `run_study → warmup → ensure_bars`, và
`acquire()` **raise** (`CollectorLeaseHeld`, `QuotaUnavailable` fail-closed,
`QuotaWaitTooLong`). `run_study` chỉ bắt `StudyRefused`, nên một `RuntimeError`
thuần thoát ra thành lỗi tool thô và đếm vào `same_tool_failure_halt_after`.
Sửa: `warmup._intraday_bars` dịch `QuotaRefused` → `StudyRefused(COHORT_WARMING)`
— đúng vốn từ "dữ liệu đang trên đường".

**LOW đã sửa:** `.PHONY` thiếu hai target · comment "Twelve provider requests"
(thật là 16) · `_coverage` của script seed bỏ sót bảng ratio khỏi mẫu số ·
16 lời gọi của script seed không đếm quota (`financial/fetch.py` chưa bao giờ
gọi arbiter, nên bọc lane không thôi là trang trí — giờ `acquire()` thật) ·
`ShareCount` trùng tên với `providers/contracts.ShareCount` → đổi thành
`SharesOnRecord` · `_window` nhận `True` thành 1 vì `isinstance(True, int)` ·
`no_corporate_action` → `no_dated_corporate_action` (`for_symbols` loại action
không có ex-date, nên "không có sự kiện" là câu sai).

**Nới guard `test_the_loop_names_no_particular_domain` là có lý do, và reviewer
đúng khi cảnh báo.** Guard quét chuỗi con tên mỗi tool domain; một tool tên
`query` làm nó đỏ vì *comment* "query inside the deployment" trong `loop.py`.
Siết thành string literal (`"query"` / `'query'`) — đúng hình dạng thật của
hardcode, và đúng cái docstring của chính test cảnh báo với chữ "domain".
Đánh đổi: `loop.py` viết `get_field` trong docstring giờ đi lọt. Chấp nhận vì
hình dạng cần chặn là *hằng*, không phải văn xuôi.

**Một finding không sửa, có lý do.** `cell_roles` chưa được FE đọc
(`types.ts` khai `columnRoles`/`pointRoles`, không khai `cellRoles`). Đó là
**đúng phạm vi phase 06** trong bảng surface — phase này sở hữu backend, phase
06 sở hữu `apps/web/src/components/signal-desk/**`. Đã đổi tên test
`..._reach_the_browser_...` cho khớp thứ nó thật sự chứng minh.

**Sạch, reviewer kiểm và không thấy vấn đề:** `_upsert` đổi chữ ký (hai caller
cũ giữ nguyên cột) · `label_rows` first-wins khớp `PRIMARY_SEQ` · `_period_end`
· cửa sổ `_read_bar_daily` không off-by-one · `_columns` thứ tự · 20 hướng
`better` đọc lại từng cái không sai · `store_series` giữ `"series"` ·
`Provenance.source` không caller nào còn mong tên provider · cạnh import ·
migration một head, additive-only · `__all__` không tên ma · không race
condition · không rò PII.

**Sau sửa:** `make test` **1776 passed**; năm cổng web xanh; sáu nguồn `query`
đều trả frame trên store thật (bar_daily 0,030 s · intraday 0,004 s · statement
0,008 s · ratio 0,005 s · reference 0,003 s · corporate_actions 0,003 s).
