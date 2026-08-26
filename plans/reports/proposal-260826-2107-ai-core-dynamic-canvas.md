# Đề xuất: biến AI thành core — Study → Artifact → Canvas

Ngày 2026-08-26. Nguồn của đề xuất: `docs/idea.md` (brief canvas dynamic),
`docs/Harness/` (SOT contract + target architecture), `docs/hermes/`,
issue #34 (quyết định đã ghi về visualization protocol),
`plans/reports/researcher-260826-2108-vnstock-data-capability.md`,
`plans/260826-1920-phase-0-cleanup-and-restore-map/phase-{07..10}`,
và đo trực tiếp trên store + vnstock live trong session này.

Ký hiệu claim: **OBSERVED** = đã chạy/đọc trong session này ·
**PRIOR** = tài liệu, chưa tự kiểm · **ASSUMED** = chưa xác minh, kết luận dựa vào.

---

## 1. Kết luận trước

Kiến trúc nên xây là **ba seam: Study → Artifact → Canvas**. Model chọn và
diễn giải; **engine tính; artifact giữ số; registry vẽ.** Model không bao giờ
nhìn thấy dãy số, không bao giờ sinh code chart, không bao giờ làm số học.

Và một đảo thứ tự quan trọng so với `idea.md`: **case Intraday Liquidity phải
là case xây trước, không phải case demo cuối.** Lý do là dữ liệu — đo thật hôm
nay, nó là case duy nhất trong ba case chạy được **ngay, ở tier free, bằng một
request 2,1 giây**, trong khi hai case còn lại cần một dự án dữ liệu market-wide.

Ba điều `idea.md` đề xuất mà tôi **không** khuyến nghị làm như đã viết: canvas
tự do do model sinh (mục 4.1), Buy Decision với verdict chỉ thị (mục 6.3), và
thứ tự case theo brief (mục 5).

---

## 2. Trạng thái thật của harness hôm nay

Đo trên nhánh `refactor/harness-first`.

| Vùng | Thực tế OBSERVED | Ý nghĩa cho canvas |
|---|---|---|
| Tool plane | `registry.ToolEntry` sở hữu schema + handler + availability + `reads_external` + `max_result_size_chars`. `toolsets.CHAT_TOOLSETS = ("web","memory","signals")` = 8 tool | Điểm mở rộng đã có. Thêm bundle `studies` là **cộng thêm**, không sửa loop |
| Evidence plane | 25 Signal Field đăng ký, **tất cả trả một scalar**. `EvidenceFigure.as_wire()` = value + unit + source + health + asOf + sessionsUsed | **Đây là khoảng trống lớn nhất.** Chart cần dãy số; evidence plane hiện chỉ biết một số |
| Context budget | 3 rung: cap theo tool, preview 15% cửa sổ, tổng 30% cửa sổ | Chính hệ thống này **cấm** đưa dãy 780 số vào context. Nó buộc thiết kế handle+preview |
| System prompt | `contract.py::_assert_no_formatting_hole` cấm mọi `{`/`}`; `render()` chỉ nhận 2 giá trị typed (`today`, `user_name`) | **Không được** nhồi catalog widget vào prompt. Catalog phải đến qua schema tool |
| SSE | `ENVELOPE_VERSION = 2`, `EventType` enum 7 loại. Client subscribe theo **allowlist tên event** và reducer có nhánh `default` | Thêm event `canvas.ready` là additive, forward-compatible. Client cũ bỏ qua, không crash |
| Layout web | `app-shell.tsx` đã có **ba vùng**: sidebar · transcript · inspector (resizable phải, hiện chỉ chứa SourcesTab) | **Canvas không cần layout mới.** Nó là tab thứ hai trong inspector đã tồn tại |
| Chart lib | **Không có.** recharts 3.10.1 đã bị rip cùng Phase 0 | Cần một dependency mới → cần user chấp thuận |

Một tài sản đáng nêu: `tools/signals.py` có `_check_the_catalog_holds()` và
`_check_the_display_names_hold()` — kiểm hai chiều lúc import, field đăng ký mà
thiếu nhãn thì **fail lúc import** chứ không ship. Study registry và widget
registry nên bắt chước đúng khuôn này, không phát minh khuôn mới.

---

## 3. Dữ liệu — đây là ràng buộc quyết định, không phải chi tiết triển khai

### 3.1 Store hôm nay (OBSERVED, `provider_snapshots`)

| capability | rows | symbols | days | khoảng | source |
|---|---|---|---|---|---|
| market | 67.688 | 32 | 2.544 | 2016-06-20 → 2026-08-23 | **fiinquant 36.528** (2021-08→nay) + vnstock 31.160 (2016→2021-08) |
| valuation | 35.245 | 30 | 1.261 | 2021-08-04 → 2026-08-24 | **fiinquant 100%** |
| fundamental | 2.854 | **1.343** | 34 | 2018-03-30 → 2026-06-29 | vnstock |
| reference | 220 | 30 | 8 | 2026-08-09 → 2026-08-24 | vnstock |
| market_index | — | — | — | **không có dòng nào** | — |

Ba điều đọc ra được, cả ba đều quan trọng:

1. **Toàn bộ giá 5 năm gần nhất và toàn bộ valuation là dữ liệu FiinQuant** —
   provider mà `CLAUDE.md` tuyên bố "vi phạm điều khoản SaaS — đã rip". Code
   đã rip; **dữ liệu thì chưa.** Mọi canvas vẽ giá gần đây, mọi P/E, mọi
   `check_price_claim` đối chiếu bar trong store hiện đang chạy trên nguồn đó.
   Đây là nợ provenance, không phải nợ kỹ thuật.
2. **fundamental có 1.343 mã nhưng 1.088 mã chỉ có đúng 1 snapshot**, và payload
   chỉ gồm `trailing_12_month_net_income_vnd` + `parent_equity_vnd`. Không có
   lợi nhuận theo quý, không có doanh thu, không có tách core/bất thường →
   **case Earnings Screener không tính được từ store hiện tại.**
3. **Không có market_index** → mọi phép "so với VN-Index" trong `idea.md`
   (relative performance, vốn là lập luận mạnh nhất của case 2) hiện bằng không.

### 3.2 vnstock — đo live, không đọc doc

Đã gọi thật trong container `api`, tier guest, không API key:

| Câu hỏi | Kết quả OBSERVED |
|---|---|
| Intraday 15m cho STB, 30 phiên? | **6.644 dòng, 70 phiên, 2,14 giây, 1 request.** `Quote(symbol='STB', source='VCI').history(interval='15m')`. Range 2026-06-18 → 2026-08-26 |
| Trần lịch sử | 1m = 6 tháng · 5/15/30m/1H = **1 năm** · daily = 8 năm. Trần **cứng, không đọc tier** — Bronze/Diamond y hệt guest |
| BCTC quý | **8 quý** ở tier community (2026-Q2 → 2024-Q3), 2,87 s/mã, wide-format, `item_id` là khoá ổn định. Bronze+ = không giới hạn kỳ |
| YoY quý tính được? | **Có.** 8 quý đủ cho 2026-Q2 vs 2025-Q2. STB thật: 1,347T vs 2,894T = **−53% YoY** |
| Listing | `all_symbols()` = **1.751 mã**; HSX 756 · HNX 313 · UPCOM 820; có `industries_icb()` |
| VN-Index | `Quote('VNINDEX')` daily hoạt động, ~7 năm |
| Batch/screener | **Không có.** 1 mã / 1 request, tuần tự |
| Khối ngoại theo phiên | **Không có time-series.** Chỉ snapshot room/volume |
| Licence | LICENSE.md trong wheel + `pip show` + README GitHub — **ba nguồn khớp: cấm thương mại, cấm phân phối lại, ở MỌI tier kể cả trả tiền.** Sponsor chỉ nới quota kỹ thuật |

Hai đảo ngược so với giả định trong `phase-07`:

- `phase-07` thiết kế **poll live** ("không stream, chỉ poll", 60s/mã). Điều đó
  hàm ý phải tích luỹ 30 ngày mới có heatmap. **Sai** — vnstock trả lịch sử
  intraday 1 năm trong một request. Không có cold start. Collector poll vẫn cần
  cho dữ liệu trong phiên, nhưng **không** phải đường tới case 1.
- `phase-07` giả định cần Bronze cho intraday. **Không cần** — free/guest đủ.
  Bronze chỉ thật sự cần cho **quét market-wide** (case 2), nơi 1.600 × 2,9 s
  ≈ 77 phút tuần tự ở guest hạ xuống ≈ 9 phút.

Một chi tiết ingest: 15m trả **96 bucket/phiên** (grid 24 giờ) trong khi phiên
VN chỉ có ~17 bucket thật. Lớp aggregation phải lọc theo session window, nếu
không mọi thống kê bị pha loãng 5,6 lần. `session_window.py` trong restore map
đúng là chỗ giải việc này.

### 3.3 Ba case của `idea.md` chấm theo dữ liệu

| Case | Dữ liệu | Compute | Compliance | Sẵn sàng |
|---|---|---|---|---|
| **1. Intraday Liquidity** | ✅ 1 request, free tier | bucket + normalize + rank — thuần pandas | ✅ mô tả microstructure, không khuyến nghị | **Hôm nay** |
| **3. Buy Decision** | ✅ daily 8y + 8 quý + 52w suy ra được. ⚠️ giá gần đây là FiinQuant | trend + range + so kế hoạch | ❌ **verdict chỉ thị vi phạm luật đã ghim** | Sau khi reframe |
| **2. Earnings Screener** | ❌ cần store BCTC market-wide + backfill giá 1.600 mã + VN-Index + phân ngành | screening + scoring + ICB peer | ⚠️ "opportunity score" dễ đọc thành khuyến nghị | Dự án dữ liệu riêng |

Đây là lý do thứ tự xây **không** theo thứ tự brief.

---

## 4. Kiến trúc đề xuất

### 4.1 Vì sao không để model sinh canvas

`idea.md` mô tả canvas như thứ model tự dựng theo câu hỏi. Bốn bằng chứng nói
không:

1. **FinVerBench**: accuracy của LLM rơi từ 95,6% ở lookup đơn giản xuống
   **gần 0%** ở multivariate calculation (`research-260823-2212-portfolio-intelligence-landscape.md`).
   Case 1 là 70 phiên × 17 bucket = 1.190 ô cần chuẩn hoá và xếp hạng. Giao cho
   model là giao cho vùng nó dở nhất.
2. **Budget plane đã cấm**: rung 2 cắt mỗi result ở 15% cửa sổ, rung 3 cắt tổng
   ở 30%. Dãy số đủ vẽ heatmap không đi qua được.
3. **SOT dependency rule 6**: "Evidence plane không tin text answer để suy ngược
   provenance." Số bị model copy vào code chart là số mất provenance.
4. **Issue #34 đã quyết**: registry typed có version, **không** chart grammar tự
   do, **không** sandbox sinh ảnh. Quyết định đó vẫn đúng ở phần này.

### 4.2 Ba seam

```
  Câu hỏi user
       │
       ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ MODEL — hiểu ý định, chọn Study, điền params, viết diễn giải  │
  │ Không tính. Không thấy dãy số. Không sinh markup.             │
  └──────────────────────────────────────────────────────────────┘
       │  run_study(name, params)          headline + artifact_id
       ▼                                            ▲
  ┌──────────────────────────────────────────────────────────────┐
  │ STUDY — hàm thuần, có version, deterministic                  │
  │   compute(ctx) -> StudyResult{ headline, frames, provenance } │
  │   view(result) -> CanvasSpec[ block{widget, binding, opts} ]  │
  └──────────────────────────────────────────────────────────────┘
       │ frames (dãy/ma trận) — KHÔNG vào context model
       ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ ARTIFACT — bảng agent_artifact, as-of đóng băng lúc tạo        │
  └──────────────────────────────────────────────────────────────┘
       │ canvas.ready(artifactId)  →  web fetch qua boundary đã auth
       ▼
  ┌──────────────────────────────────────────────────────────────┐
  │ CANVAS — widget registry keyed (name, version)                │
  │ Widget nhận data + label + provenance. Không fetch. Không     │
  │ top-N. Không route. Unknown version → bảng, không crash.      │
  └──────────────────────────────────────────────────────────────┘
```

**Study** là đơn vị mới. Nó là recipe phân tích có tên, có version, tính bằng
code ta viết:

```
StudyDefinition
  name             "intraday_liquidity_profile"
  version          1
  params_schema    {symbol, sessions, bucket_minutes, metric}   ← model điền
  requires         (Capability.INTRADAY_BAR,)                    ← tiền đề dữ liệu
  compute          (StudyContext) -> StudyResult
  view             (StudyResult) -> CanvasSpec

StudyResult
  headline         dict ≤ ~300 token — đủ để model lập luận và viết prose
  frames           dict[str, Frame] — dãy/ma trận, KHÔNG vào context
  provenance       source · asOf · sessionsUsed · health · reason khi từ chối
```

Model gặp Study qua **hai tool trong bundle mới `studies`**, `reads_external=False`:

- `list_studies()` — catalog: tên, câu hỏi nó trả lời, params, availability.
  Đúng khuôn `list_fields` đã có.
- `run_study(name, params)` — trả `headline` + `artifact_id` + provenance.

Vì catalog đến qua **schema tool**, không qua prompt: thêm một Study **không**
cần sửa prompt, **không** void prefix cache, **không** vi phạm
`_assert_no_formatting_hole`. Đây là lý do kiến trúc này vừa với repo này chứ
không chỉ vừa về nguyên tắc.

### 4.3 Chống vách đá recipe — ba tầng

Điểm yếu thật của registry: câu hỏi thứ N+1 không có Study thì rơi xuống vực.
Ba tầng để không có vực:

| Tầng | Cơ chế | Đánh đổi |
|---|---|---|
| **1. Study** | Recipe dựng sẵn, có golden test, cache được | Đẹp nhất, hẹp nhất |
| **2. Composition** | `get_series(field, symbol, window)` — em ruột còn thiếu của `get_field` — rồi `render_canvas(blocks)`: model chọn widget trên frame handle | Kém bóng bẩy, không bao giờ tắc |
| **3. Sandbox** (conditional, chưa làm) | Study soạn lúc chạy, chạy trong container per-call dưới gVisor theo `docs/research/python-sandbox-options.md` | Mở vô hạn, nhưng là dự án hạ tầng, cần graduation gate |

Tầng 2 là thứ khiến đề xuất này khác một danh sách dashboard. Nó cũng là thứ
đang **thiếu nhất** trong evidence plane: 25 field đều trả scalar, không có gì
trả dãy.

### 4.4 Widget cần cho ba case

`web-viz-inventory.md` đã ghi khuôn: widget nhận `{categories, series}`, series
tự mang label, top-N là policy của caller, empty state phải nói ra, palette
dùng token `--chart-*`, và **widget hiển thị dữ liệu store phải mang tuổi của
nó** (`{source, effectiveAt, ageSeconds, stale}`).

| Widget | Case | Có sẵn trong recharts? |
|---|---|---|
| `stat_tiles` | 1,2,3 | không cần chart lib |
| `bar_series` | 1,3 | ✅ |
| `session_heatmap` | 1 | ❌ **SVG tự vẽ** |
| `ranked_bars` | 1,2 | ✅ |
| `line_series` | 2,3 | ✅ |
| `scatter_quadrant` | 2 | ✅ scatter, annotation tự thêm |
| `data_table` | 2, fallback | không cần chart lib |
| `range_strip` | 3 | ❌ SVG tự vẽ |
| `condition_checklist` | 3 | không cần chart lib |
| `scenario_cards` | 3 | không cần chart lib |

7/10 không cần hoặc dùng được recharts; 2 phải tự vẽ SVG (repo đã có tiền lệ
tự vẽ SVG tốt). Không thấy lý do lấy echarts.

---

## 5. Lộ trình

Thứ tự theo **dữ liệu sẵn có × giá trị chứng minh kiến trúc**, không theo thứ tự
brief.

### Phase A — Spine + case Intraday Liquidity chạy hết đường (vertical slice)

Cố tình chỉ một Study, bốn widget, nhưng **đủ hết đường từ câu hỏi tới pixel**.
Đây là phase chứng minh kiến trúc; nếu nó sai, sai ở đây rẻ nhất.

- `src/studies/` — `StudyDefinition`, `StudyResult`, `Frame`, registry với kiểm
  hai chiều lúc import theo khuôn `tools/signals.py`
- Alembic revision mới: bảng `agent_artifact` (turn_id, thread_id, study_name,
  study_version, params, frames JSONB, canvas_spec JSONB, provenance, created_at)
- Bundle `studies`: `list_studies` + `run_study`, `reads_external=False`
- Event SSE `canvas.ready` — additive vào `EventType`, restate trong snapshot
- Ingest intraday vnstock → `bar_intraday_15m` (bảng **đã có trong DB**, chỉ
  reconnect) + lọc session window 96 → ~17 bucket
- Study `intraday_liquidity_profile` v1: bucket volume, liquidity share, spike
  frequency, xếp hạng cửa sổ
- Canvas panel = tab thứ hai trong inspector đã tồn tại, cạnh Sources
- Widget: `stat_tiles`, `bar_series`, `session_heatmap`, `ranked_bars`
- Test: golden test `(params) → StudyResult`; test web cho đường degrade khi
  version widget không biết

### Phase B — Evidence dạng dãy + tầng composition

- `get_series` — em ruột còn thiếu của `get_field`; `Frame` mang đúng bộ
  provenance như `EvidenceFigure`
- `render_canvas(blocks)` — model soạn canvas trên frame handle
- Widget thêm: `line_series`, `scatter_quadrant`, `data_table`

### Phase C — Case 3, reframe thành Condition Review

- Study `entry_condition_review`: vị thế giá trong dải 52 tuần, vùng tích luỹ
  suy ra từ price structure (**tính lại, không hard-code** — `idea.md` tự nói
  đúng điều này), xu hướng lợi nhuận theo quý, tiến độ so kế hoạch
- Widget: `range_strip`, `condition_checklist`, `scenario_cards`
- `PROMPT_VERSION` bump kèm luật framing (mục 7)

### Phase D — Spine dữ liệu market-wide

Phase trả nợ. Một backfill giải bốn việc cùng lúc.

- Backfill daily OHLCV market-wide từ vnstock → **xoá nợ provenance FiinQuant**
- VN-Index daily → mở lại toàn bộ trục relative performance
- Phân ngành ICB + listing roster từ `all_symbols()` → peer group thật
- Universe hai nửa: `declared` (30 mã, full signal) + `market` (~1.700 mã,
  signal tối thiểu) theo đúng `phase-10`

### Phase E — Store BCTC + case Earnings Screener

- BCTC quý market-wide, job quét ~1.600 mã (Bronze ≈ 9 phút/lượt)
- **Mapping line-item theo ngành** — `income_statement` của STB (bank) có 26
  dòng và không có doanh thu/COGS; doanh nghiệp sản xuất có bộ khác. "Lợi nhuận
  core" mà `idea.md` muốn lọc **không** rút ra được bằng một khoá chung. Đây là
  phần dễ sai nhất của cả lộ trình
- Study `earnings_dislocation_screener` + canvas scatter-quadrant

### Không làm

- Model sinh code/markup/chart grammar tự do (mục 4.1)
- Nhồi catalog widget vào system prompt (vi phạm `contract.py`)
- Đưa dãy số vào context model (vi phạm budget plane)
- Sandbox tầng 3 ở giai đoạn này
- Realtime streaming (poll đủ; và trần lịch sử vnstock không đổi theo tier)
- Tái tạo signal khối ngoại từ vnstock — **không có nguồn**. Hai field
  `foreign_flow_pressure.*` sẽ vĩnh viễn `no_value` khi dữ liệu FiinQuant cũ
  đi. Nhánh drill-down "khối ngoại mua hay bán" của `idea.md` hiện không trả lời
  được

---

## 6. Rủi ro, xếp theo mức độ chặn

### R1 — Licence vnstock cấm thương mại ở mọi tier · **chặn sản phẩm, không chặn dev**

Ba nguồn độc lập khớp nhau (LICENSE.md trong wheel, `pip show`, README GitHub):
cấm thương mại, cấm phân phối lại, **kể cả tier trả tiền**. Sponsor nới quota
kỹ thuật, không cấp quyền thương mại — bằng chứng là chính code patch chỉ chạm
rate limit và số kỳ BCTC.

Câu "licence phân phối ≤500 user" trong `CLAUDE.md` **không xác minh được** qua
nguồn công khai. Nếu nó đến từ email riêng với `support@vnstocks.com` thì nó
đúng nhưng cần được lưu thành văn bản; nếu là suy luận thì nó sai theo hướng
nguy hiểm.

Điều đáng nói thẳng: đây **cùng lớp vấn đề** với việc đã rip DNSE/FiinQuant/CafeF
vì vi phạm điều khoản. Nguồn duy nhất còn lại có đúng khuyết điểm đó.

Việc cần làm không phải kỹ thuật: **gửi email xin điều khoản thương mại bằng văn
bản, làm song song ngay từ Phase A.** Nó không chặn code, nó chặn ngày có user.

### R2 — Nợ provenance FiinQuant trong store · **chặn mọi canvas có giá gần đây**

36.528 dòng market và 35.245 dòng valuation từ 2021-08 tới nay là FiinQuant.
Phase D xoá nợ này. Trước Phase D, mọi canvas vẽ giá gần đây đang vẽ dữ liệu ta
đã tuyên bố không có quyền phân phối. Case 1 (intraday, kéo mới từ vnstock)
**không** vướng — thêm một lý do làm nó trước.

### R3 — Endpoint vnstock là dashboard nội bộ Vietcap, không SLA · **rủi ro vận hành thường trực**

`Quote.history()` gọi thẳng `trading.vietcap.com.vn/.../OHLCChart/gap-chart`.
Không changelog, không cam kết. Package một maintainer, đã đổi kiến trúc licence
và API nhiều lần. Hệ quả thiết kế: **ingest phải idempotent và store phải là
nguồn phục vụ**, canvas không bao giờ gọi provider trực tiếp. Kiến trúc đề xuất
đã thoả điều này, nhưng cần nói rõ là ràng buộc, không phải tuỳ chọn.

### R4 — Facade `Vnstock` có thể EOL 2026-08-31 · **rủi ro có ngày, chưa xác nhận**

`src/core/vnstock_wrapper.py:12` dùng `from vnstock import Listing, Vnstock`.
Claim EOL là **PRIOR** (websearch). Tôi đã kiểm: bản 4.0.5 đang cài **không phát
DeprecationWarning nào** — nên claim chưa được xác nhận. Dù vậy chuyển sang
`vnstock.api.{quote,financial,listing}` là việc nhỏ, và các probe trong session
này đều đã dùng đường mới thành công. Nên làm sớm vì rẻ, không vì đã chắc.

### R5 — Mapping line-item BCTC theo ngành · **rủi ro đúng/sai số, ở Phase E**

Đã nêu ở Phase E. Nêu lại vì nó là chỗ một canvas trông rất thuyết phục có thể
sai: lọc "lợi nhuận core" bằng khoá sai cho ngành sai thì kết quả vẫn đẹp.

---

## 7. Xung đột với quyết định đã ghi — cần user quyết, không tự đảo

### D1 — Trần "một widget mỗi câu trả lời" của issue #34

Issue #34 (CLOSED COMPLETED, 2026-08-12) quyết: *"The default ceiling is one
Widget per answer; a second requires an explicit user request"*, và *widget
"may not redraw OHLCV, candlesticks, volume, valuation history... already owned
by Stock 360"*.

`idea.md` mô tả canvas 5–8 widget. Hai điều này xung đột trực tiếp.

Nhưng tiền đề của #34 đã mất: **Stock 360 và Analysis lane đều đã bị rip
2026-08-25.** Trần một-widget và luật "đừng vẽ lại cái Stock 360 sở hữu" đều
được viết cho một thế giới có dashboard song song. Thế giới đó không còn.

Phần **vẫn còn đúng** của #34 và tôi đề nghị giữ nguyên: registry typed có
version · model không phát chart grammar tự do · dãy số không đi qua model ·
artifact đóng băng as-of, mở lại thread không tự tính lại `latest` · web kiểm
lại spec và degrade thay vì crash · widget mang ngày dữ liệu · màu không bao giờ
tải nghĩa một mình.

Đề nghị của tôi: **đảo có phạm vi.** Canvas trong panel phải = nhiều widget.
Transcript chat giữ nguyên tinh thần #34: text trước, tối đa một widget inline.
Đây là đảo một quyết định đã ghi nên cần user nói rõ, tôi không tự làm.

### D2 — Buy Decision của `idea.md` vi phạm luật đã ghim trong prompt

`CLAUDE.md` ghim ở `PROMPT_VERSION` 2.3.0: *"nêu mức và hệ quả, **không** ra chỉ
thị hành động cho vị thế cụ thể"*. SOT `investment-intelligence-contract.md` đặt
"A3 — Propose" ở trạng thái **Conditional** và "Action proposal" phải có
prerequisites + approval, không tự execute.

Canvas case 3 trong `idea.md` có: verdict `WAIT / DON'T CHASE`, ba scenario
trong đó một cái dán nhãn `PREFERRED`, và vùng giá cụ thể `71–72.5k` gắn với
hành động. Đó là khuyến nghị đầu tư, không phải research.

Bằng chứng bên ngoài cùng hướng: pattern Robinhood Cortex và Public Alpha đều
tránh động từ mệnh lệnh và tránh gắn số cụ thể với hành động; disclaimer
boilerplate **không đủ** che liability nếu messaging tổng thể overstate
(`research-260823-2212-portfolio-intelligence-landscape.md` §3.2).

Điều dễ chịu: **`idea.md` tự đề xuất bản đúng** ở đoạn cuối — *"What must happen
for me to BUY?" — AI liệt kê 3–5 điều kiện cần đạt và cập nhật trạng thái ✓/✕*.
Đó vừa là bản hợp luật, vừa là sản phẩm tốt hơn: nó nói cho user cái cần quan
sát thay vì nói cho user cần làm gì.

Đề nghị: giữ toàn bộ bằng chứng và cấu trúc canvas case 3, **bỏ verdict chỉ thị
và nhãn PREFERRED**, đổi thành condition review có checklist. Đây cũng là đảo
một phần brief của user nên cần user xác nhận.

---

## 8. Bốn quyết định cần user

| # | Quyết định | Khuyến nghị |
|---|---|---|
| **1** | Licence vnstock cho sản phẩm có user | Gửi email `support@vnstocks.com` xin điều khoản thương mại **bằng văn bản, ngay, song song Phase A**. Không chặn code, chặn ngày launch |
| **2** | Đảo trần một-widget của issue #34 | Đảo **có phạm vi**: canvas panel nhiều widget; transcript giữ text-trước, ≤1 widget inline. Giữ mọi luật khác của #34 |
| **3** | Chart library (dependency mới) | **recharts** cho 7/10 form + SVG tự vẽ cho `session_heatmap` và `range_strip`. recharts từng được vet ở 3.10.1 trong repo này. Không lấy echarts |
| **4** | Framing case 3 | Reframe thành Condition Review, bỏ verdict + PREFERRED. Giữ hết bằng chứng và bố cục |

---

## 9. Đo thành công của Phase A

Không phải "canvas đẹp". Là:

1. Một câu hỏi tiếng Việt về thanh khoản trong phiên của một mã declared sinh ra
   canvas 4 block, số khớp với `intraday_liquidity_profile` tính lại độc lập
2. `frames` **không** xuất hiện trong bất kỳ message nào gửi model — kiểm bằng
   transcript, không bằng niềm tin
3. Mở lại thread sau đó render đúng slice cũ, `asOf` không đổi
4. Widget version không biết → bảng, transcript không crash
5. `make test` (apps/api) + `pnpm type-check|lint|test|build` (apps/web) xanh
6. Một Study thứ hai thêm được **không** sửa `loop.py`, **không** sửa prompt,
   **không** bump `PROMPT_VERSION`

Tiêu chí 6 là tiêu chí thật. Nếu thêm Study thứ hai phải chạm loop hoặc prompt,
seam đặt sai chỗ và nên sửa trước khi đi tiếp.

---

## 10. Câu hỏi chưa giải quyết

1. Giá VND/tháng từng tier vnstock — trang JS-rendered, không fetch được. Cần
   đăng nhập hoặc hỏi trực tiếp.
2. Độ sâu lịch sử thật của `Quote.intraday()` (tick khớp lệnh) — chỉ đọc code,
   chưa test được lúc thị trường mở.
3. `vnstock_data` (sponsor-only, private) có nới trần lịch sử intraday tới đâu —
   không có quyền cài, mọi claim là PRIOR từ docstring và trang marketing.
4. Frames nên nằm JSONB trong `agent_artifact` hay tách object store khi
   ma trận lớn? Với 70 × 17 thì JSONB thừa sức; câu hỏi mở ở scale market-wide
   (Phase E).
5. `docs/harness-roadmap.md` và `docs/system-roadmap.md` mà `docs/Harness/README.md`
   trỏ tới **đã bị xoá** trong đợt dọn docs. SOT còn contract và target
   architecture nhưng tầng roadmap thì trống. Lộ trình ở mục 5 có nên trở thành
   `docs/harness-roadmap.md` mới, hay giữ là report?
