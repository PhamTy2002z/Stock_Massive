# Phase 07 — Studies as templates

**Plan:** `plans/260829-2304-signal-desk-analysis-compiler/`
**Ngày:** 2026-08-30
**Trạng thái:** Done

## Điều đã làm

Bốn Study viết tay thành **template** trên chính đường ống của analysis
compiler. Một `StudyDefinition` bây giờ là:

```
name · version · question · display_name · params_model · requires
archetype · plan: tuple[Step] · board: Mapping · headline: fn · precheck: fn|None
```

`compute` / `view` / `frames` / `widgets` **đã xoá**. Bốn module Study cũ đã xoá
khỏi disk.

### Đường chạy

```
run_study(name, params)
  → precheck (Universe)          — refusal trước khi đọc gì
  → warm                          — như cũ
  → for step in plan:
        QueryStep  → query.read_source (đúng reader chat dùng)
        ReadStep   → reader của chính template
        ComputeStep→ studies/compute/runner (đúng sandbox + validator model dùng)
     mỗi bước → store_frame → một artifact riêng, addressable "<id>#<step>"
  → grammar.parse(board) → grammar.validate → composer.compile_board
     → archetypes.check → lint.score → BoardSpec v2 → store_composition
  → StoredArtifact(headline, provenance, spec, steps)
```

Một renderer (`composer.compile_board`, dời từ `agent/tools/studies.py`), một
đường lưu (`frames_buffer`), một kiểu artifact.

### Bốn template

| Template | Plan | Frames khớp fixture |
|---|---|---|
| `intraday_liquidity_profile` v2 | 1 query + 5 compute | `profile` · `heatmap` · `ranking` |
| `entry_condition_review` v2 | 1 query + 1 read + 8 compute | `range_band` · `price_context` · `earnings_quarters` · `conditions` |
| `volume_at_price` v2 | 2 read + 4 compute | `ladder` |
| `earnings_dislocation_screener` v2 | 3 read + 5 compute | `scatter` · `ranking` · `filters` |

Mọi frame còn sống khớp fixture pre-port **cell-for-cell, tolerance 1e-9**, kể
cả `columns`, `unit`, `labels`, `pointRoles`, `cellRoles`.

Headline khớp theo từng khoá và từng giá trị, **trừ đúng một con số**:
`intraday_liquidity_profile.phaseSummary.am` là `0,2889` trước và `0,2890` sau.
Nguyên nhân là chỗ lấy số: Study cũ cộng share nó vừa tính rồi làm tròn một lần
ở cuối; template cộng share **bức tranh vẽ ra**, tức đã làm tròn bốn chữ số, nên
mười sáu bucket mang mười sáu lần làm tròn. Giữ chứ không sửa: một headline khớp
tới chữ số cuối với chính bảng dưới nó đáng hơn một tổng tròn hơn mà lệch với
từng ô. `test_templates_regression.py` khai con số này ra
(`LOOSER_BY_ROUNDING`) và cho nó đúng một đơn vị của chữ số cuối; mọi khoá khác
vẫn so ở 1e-9.

Fixture chụp trên **store thật** (as-of 2026-08-28 16:00 VN) trước khi port, ở
`apps/api/tests/studies/fixtures/pre-port/*.json`. Phép so giữ lâu dài ở hai
chỗ, và hai chỗ đó trả lời hai câu khác nhau:

- `tests/studies/test_templates_regression.py` — chạy lại đúng bốn template với
  đúng tham số đã chụp và so từng ô. **Skip khi store trống**, vì DB của suite
  là DB của người dev và chỉ có thứ một test vừa trồng; chạy nó bằng
  `DATABASE_URL=… UNIVERSE_SYMBOLS=… make test-one T=tests/studies/test_templates_regression.py`.
  Đo 2026-08-30: **9 passed**.
- Bốn file test theo Study — trồng một window tổng hợp có đáp án biết trước rồi
  khẳng định trên frame engine sinh ra. Đây là phần hermetic, chạy trong
  `make test`.

## Ba quyết định đảo một câu của plan, cả ba có số

### 1. Bước thứ ba: `ReadStep`

Plan khai hai loại bước. Đo được ba câu trả lời của store **không có source
`query` nào**:

- lưới bước giá của sàn dưới một thang giá (`price_band.tick_size` +
  `resolve_band_regime`, và board của mã trong phiên đó);
- chỉ tiêu lợi nhuận mà **template báo cáo của chính người nộp** quyết
  (`financial/templates.Concept`) — một ngân hàng và một doanh nghiệp sản xuất
  nộp hai `item_id` khác nhau cho cùng một khái niệm;
- một phép quét rộng hơn số mã model bao giờ cũng được đưa: `MAX_SYMBOLS = 10`,
  và screener chạy trên 30 (declared) tới 1.523 (market) mã.

Cả ba là **sự thật về hình dạng store** — reads — không phải số học. Nên
`ReadStep` nằm trên trục đọc và chỉ trên đó: mọi con số một template *suy ra*
vẫn đi qua `ComputeStep`, sandbox và validator, đúng điều kiện model nhận.
`registry` chạy validator **lúc import**, nên "template không gõ số thị trường"
là thuộc tính của bản build.

Plan đã lường trước một đặc quyền cho template (mục *Risk Assessment*, namespace
`lib` whitelist trong sandbox). Đường đó bị bỏ: whitelist `stocks` **trong**
worker phá đúng cái biên mà sandbox là — worker hạ quyền xuống `nobody`, chặn
mọi import ngoài năm module, và một cầu nối tới `stocks` sẽ mở lại tất cả.

### 2. Frame `tiles` bỏ đi ở cả bốn

Consumer duy nhất của `tiles` là block `stat_tiles` của spec v1. Dải KPI của
board v2 *là* thứ thay nó: mỗi ô `tiles` từng mang giờ là một `Ref` server tra
`(frame, row, col)` rồi format một lần lúc đóng băng. Phép so mạnh hơn chứ không
yếu đi — bốn file test khẳng định dải KPI resolve ra **đúng những con số**
`tiles` mang.

Một hệ quả phải xử: `format.number` đọc đơn vị của **frame**, mà một frame có
một đơn vị. Một tỉ trọng đọc ra từ frame `unit="shares"` in thành `0,14` thay vì
`13,6%`. Nên ba template có thêm một `ComputeStep` nhỏ `unit="%"` — không vẽ, chỉ
để trích dẫn.

### 3. Gate "≤ hiện tại + 20%" không đạt được, và đó là số học

| | Trước | Sau | Lần |
|---|---|---|---|
| `intraday_liquidity_profile` | 50,1 ms | 1,43 s | 29× |
| `entry_condition_review` | 6,7 ms | 2,20 s | 328× |
| `volume_at_price` | 4,9 ms | 1,12 s | 228× |
| `earnings_dislocation_screener` | 44,9 ms | 1,48 s | 33× |

Một lượt gọi sandbox tốn **260 ms** đo tại chỗ (n=4, `pandas` import trong tiến
trình con mới), và một plan có 4–8 bước compute. Không có cách viết plan nào cho
+20%: sàn là một lượt gọi sandbox, tức đã 5× cái Study nhanh nhất.

Cái +20% đo sai thứ. Trần thật sự là `TURN_COST_MICRO_USD = 500.000` và
`MAX_TOOL_ROUNDS = 4`; một giây rưỡi trong một Turn ba mươi giây không chạm cái
nào, và đổi lại là **một** đường tính có validator thay vì bốn đường tính không
ai đọc. Cùng hình dạng với hai gate đã đảo trước đó của C1 (citation) và C2 (20%
constructed token): một ngưỡng viết trước khi có phân bố.

## Ba bug tìm ra khi port, cả ba sửa

### `sessionsUsed` sai một bậc độ lớn, ở hai chỗ

`read_source` đặt `sessions_used = len(frame.rows)`, nên một lượt đọc 15 phút của
30 phiên khai **480 phiên** trên dải provenance người đọc nhìn.
`composer.merged_provenance` lấy `max` qua mọi frame, nên một frame derived 24
hàng khai **24 phiên** cho một thang giá một phiên.

Sửa hai chỗ:
- `query._answered` đếm giá trị khác nhau của trục `session` (rồi `period`, rồi
  hàng nếu không có trục nào) — đúng cho cả `query` của model;
- `merged_provenance` chỉ lấy `sessionsUsed` từ frame **nguồn store**, bỏ qua
  derived. Một frame derived khai chiều cao của chính nó, và chiều cao không
  phải số phiên. Board toàn frame derived thì rơi về `max`, vì khi đó chiều cao
  là con số duy nhất có.

### `run_study` không chịu trần board của Turn

`MAX_SIGNAL_DESKS_PER_TURN = 2` đếm row `composed_signal_desk`. Trước port một
Study ghi row dưới **tên của chính nó**, nên phép đếm không bao giờ thấy nó, và
`run_study` chưa từng phải kiểm. Sau port board của template *là* một
composition — nên một Turn có thể vẽ hai board nó tự soạn **cộng thêm** một
board mỗi lần gọi `run_study` (`MAX_TOOL_ROUNDS = 4`, và `run_study` không tính
vào `MAX_EXTERNAL_TOOL_CALLS` vì nó đọc store). Thêm đúng cổng
`render_signal_desk` đang dùng vào `run_study`; hai board một Turn là một khẳng
định về thứ người đọc tiếp nhận được, và nó không phụ thuộc ai vẽ.

### Catalog widget stale từ phase 05/06

`contracts/signal-desk-widget-catalog.json` thiếu **sáu** widget phase 05/06 đã
thêm vào `src/studies/widgets.py`. `make contracts` chưa chạy lúc đóng phase 06,
và `test_widget_catalog.py` chỉ kiểm một chiều nên không bắt được. Đã sinh lại.

## Code review, và bảy thứ nó tìm ra

Review sau khi bốn template xanh. Bảy phát hiện, sáu đã sửa.

**Một Study bị từ chối commit các artifact nó đã ghi trước đó.** `run_study`
**return** payload refusal từ trong `with self._open()`, và return là một lối ra
bình thường nên `get_sync_db` commit trên đường ra. Không chỉ là rác:
`auto_compose_for_turn` vẽ **mọi** frame một Turn thu được, nên một Study từ
chối trả lời sẽ kết thúc Turn bằng một board dựng từ mảnh vụn của chính nó.
Sửa: `session.rollback()` trước khi trả refusal — mất luôn phần warm đã fetch,
đúng đánh đổi runner đã ghi ("nửa lượt chạy không phải thứ để giữ").

**`volume_at_price` tính con số trung tâm trong một `ReadStep`.** `_ladder` chia
`volume / len(steps)` và cộng dồn — đó *là* phép ước lượng cả board dựa vào,
tức là một phép tính, và nó nằm ngoài validator. Câu "mọi con số một template
suy ra vẫn đi qua ComputeStep" **sai** với template này. Sửa: read giờ phát ra
**lưới** — một dòng mỗi `(khung, giá)` kèm khối lượng của khung và số bước giá
nó được yết qua — và một `ComputeStep` mới (`rungs`) làm phép chia rồi gộp theo
giá. `ladder` vẫn khớp fixture từng ô sau khi chuyển.

**`intraday_liquidity` sắp hạng bằng một sort không ổn định, sau khi đã làm
tròn.** `profile` làm tròn `share` về 4 chữ số rồi `ranking` sort cột đó bằng
quicksort mặc định của pandas. Đo được ở đúng bề rộng lưới bucket (n=17,
pandas 2.3.3): thứ tự **đảo**. Hai khung giờ cách nhau một phần trăm nghìn cùng
làm tròn về một số, và hàng 0 — nguồn của cả bốn KPI, dấu `focus`, và toàn bộ
headline — rơi vào khung mà partition tình cờ để lại trước. Fixture STB không có
tie nên nó đúng trên fixture và sai chỗ khác. Sửa: `kind="mergesort"`, nên tie
giữ thứ tự đồng hồ — cũng chính là thứ `idxmax` cho dấu `focus` trên `profile`.
Một leader, và cùng một leader trên cả hai bức tranh.

**Ô heatmap của một phiên không giao dịch là `0.0` thay vì lỗ.** Study cũ trả
`None` cho cả phiên khi tổng bằng 0; port điền 0.0, tức nói "khung giờ đó có tồn
tại và không ai giao dịch" — đúng câu docstring của chính module cấm. Sửa: một
cột `share_drawn` để trống khi tổng bằng 0; `profile` vẫn cộng 0.0 như cũ.

**Đọc hai lần, và hai lần đó có thể lệch nhau.** `volume_at_price` gọi
`_window` + `_bars` trong cả hai read; `earnings_dislocation` gọi
`_default_period` bốn lần. Dưới read-committed mỗi câu lệnh là một snapshot
riêng, nên một bucket hoặc một batch BCTC commit giữa hai bước làm một frame mô
tả một store frame sau không còn thấy — mà `as_of` thì đang hứa một khoảnh khắc.
Sửa: `StudyContext.scratch`, một dict per-run các bước dùng chung; cả hai
template resolve một lần.

**`auto_compose` sẽ vẽ frame làm việc.** Đo scope `market` của screener:
**2,05 s · 1.523 mã · frame `closes` 28.784 dòng / 2,02 MB JSONB**. Đó là bảng
Study đọc *trên đường* tới câu trả lời, không phải một bức tranh — và
`auto_compose` là thứ một Turn nhận khi model không vẽ gì. Sửa:
`MAX_DRAWABLE_ROWS = 500` (chính trần câu trả lời của sandbox); frame cao hơn
không được chọn, và một Turn chỉ có frame như vậy trả `None` thay vì một board
rỗng. Phần **lưu** 2 MB mỗi lần chạy vẫn còn — đo rồi, nhận, và trim phía SQL
vẫn là việc hoãn.

**Một note đếm nhãn là giả định.** `derived_provenance` đếm `len(constants)`, mà
`constants` là cửa duy nhất để một nhãn tiếng Việt vào sandbox — nên bảng điều
kiện báo "tám giả định đã khai báo" trong đó năm là từ điển nhãn. Sửa: chỉ đếm
constant là **số**.

Một phát hiện **không** sửa: `entry_condition_review` và
`earnings_dislocation_screener` không kiểm Universe, trong khi hai template kia
có. Đây là hành vi trước port (một test của file đó nói rõ Study này "không đọc
luật thành viên": bốn trục nó đo đến từ chính dòng trong store, và một mã
backfill chưa tới sẽ từ chối vì thiếu phiên). Đổi nó là một quyết định sản phẩm
về bề mặt refusal, không phải một phần của phép port — ghi ở *Câu chưa chốt*.

## Ba thứ mất khi port, ghi ra chứ không giấu

1. **Cổng `mixed_price_basis`** của `entry_condition_review`. `BAR_COLUMNS` của
   `query` không có `price_basis` và `_number()` không đọc được enum, nên khôi
   phục nó là mở rộng schema `query` — việc của một amendment sau. Mọi dòng đang
   lưu đều `adjusted_at_source`, nên cổng này chưa từng nổ.
2. **`horizon_sessions` trên 250 vẽ 250**, vì `query.MAX_WINDOW = 250` ("above
   any honest picture"). `sessionsUsed` nói ra sự thật đó thay vì một refusal.
3. **KPI của `entry_condition_review` không mang `role`.** Một `role` là chữ
   viết trước khi có số; màu theo dấu của một con số chưa tính chỉ có hai lựa
   chọn — đôi khi nói dối, hoặc không nói gì. Chọn không nói gì; dấu vẫn được vẽ
   ở chỗ tính được cùng con số (`point_roles` của cột lợi nhuận).

## Bốn tiêu chí của phase

- [x] 4 template frames khớp fixture pre-port — 1e-9, trên store thật.
- [x] Không còn đường render nào ngoài composer — `grep _presentation` = 0 trong
      `src/`; `compile_board` là hàm duy nhất dựng `BoardSpec`, và cả `run_study`
      lẫn `render_signal_desk` gọi nó.
- [x] Template code không có literal lọt validator — `registry` chạy
      `validator.validate` lúc import; một test khẳng định một literal bị từ chối
      và cùng con số qua `constants` thì được nhận.
- [x] `test_agent_signal_desk` + regression mới xanh.

## Câu chưa chốt

1. Có thêm `price_basis` vào `BAR_COLUMNS` của `query` để khôi phục cổng
   `mixed_price_basis` không? Cần một nhánh text cho enum trong `_read_bar_daily`.
2. `closes` của screener lưu một frame 28.784 hàng / 2,02 MB mỗi lần chạy scope
   `market` (đo). Trim bằng `row_number()` phía SQL cắt khoảng một phần ba —
   hoãn có chủ ý; `auto_compose` đã không vẽ nó nữa.
3. `read_source` có nên mang cổng Universe thay vì mỗi template tự thêm không?
   Hôm nay hai trong bốn template có `precheck`, hai không — và
   `run_study(entry_condition_review, symbol=<ngoài Universe>)` trả lời trong khi
   `query`/`get_field` từ chối chính mã đó. Cả hai vế đều là hành vi trước port.
