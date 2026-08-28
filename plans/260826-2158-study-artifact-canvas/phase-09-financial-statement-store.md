# Phase 09 — Store BCTC quý market-wide (nhóm E)

Phụ thuộc 08 (roster + ICB). Phần dễ sai nhất của lộ trình (R5).

## Context

vnstock Finance: 1 mã/request, wide-format theo quý (3 cột meta `item`,
`item_en`, `item_id` + 8 cột quý `2026-Q2 … 2024-Q3`). Quét 1.523 mã STOCK
listed ≈ 9 phút/lượt Bronze, ~27 phút free.

## Sửa spec 2026-08-27 (probe live STB · SSI · HPG)

Hai số đo đổi phần rủi ro nhất của phase:

1. **`net_profit_loss_after_tax` có ở CẢ BA template** — STB (bank, 26 dòng) ·
   SSI (securities, 79 dòng) · HPG (non-financial, 25 dòng). Nghĩa là khái niệm
   `net_profit` — input duy nhất phase 10 thật sự cần — **không cần mapping
   theo ngành**. R5 co lại: template chỉ còn cần cho `core_operating_result`,
   khái niệm không có consumer nào trong lộ trình hiện tại (bank dùng
   `net_operating_profit_before_allowance_for_credit_loss`, securities dùng
   `operating_profit_loss`, non-financial dùng dòng khác). v1 **ship
   `net_profit` + `pretax_profit` + `equity` universal**;
   `core_operating_result` ghi là non-goal v1 thay vì dựng ba template mapping
   cùng một `item_id` cho có.
2. **`item_id` KHÔNG unique trong một response.** SSI có hai dòng
   `business_income_tax_deferred` (4.585.945.424 và 758.786.600 ở 2026-Q2) và
   hai dòng `gain_loss_from_revaluation_of_derivatives`. PK
   `(symbol, period, statement, item_id)` của bản cũ bị **chính response của
   provider** vi phạm; giữ "dòng cuối thắng" là mất dữ liệu. Thêm `item_seq`
   (thứ tự xuất hiện của `item_id` đó trong response, 0-based) vào PK; reader
   giải một khái niệm lấy `item_seq = 0`.

Thêm một cảnh báo chất lượng nguồn: SSI có `business_income_tax_expenses` =
1.528.966.041.130 ở 2026-Q2 — dương và xấp xỉ `operating_profit_loss`, tức
nhãn không đúng nội dung. **Golden test không được tin nhãn**; đối chiếu bằng
quan hệ số học (`net_profit = pretax − tax`) và bằng số công bố.

### Valuation: có đường vnstock, nhưng không có lịch sử

Probe 2026-08-27 (`Finance.ratio`):

- `source="VCI"` trả **chỉ 4 quý của 2018** — cũ 8 năm, vô dụng.
- `source="KBS"` trả **hiện tại** (2026-Q2) với `pe_ratio` · `pb_ratio` ·
  `trailing_eps` · `book_value_per_share_bvps` · `roe` · `roa` · `beta` + chỉ
  tiêu tăng trưởng. Có đủ cho cả ba template (STB 32 chỉ tiêu · SSI 49 ·
  HPG 58). `Finance` chỉ nhận `source` là `VCI` hoặc `KBS` — không có TCBS.

→ **Lỗ hổng `valuation` (0 dòng vnstock) lấp được, không cần FiinQuant.**
Nhưng ba hạn chế đo được, ghi để 08b không hứa quá:

1. **Chỉ ~3 kỳ phân biệt.** Cột trả về là
   `['2026-Q2','2025-Q4','2026-Q1','2025-Q4_1']` — không theo thứ tự và lặp
   một kỳ (pandas thêm hậu tố `_1`). Dùng được như **snapshot valuation gần
   nhất**, không dùng được như một series quý.
2. **Không tái tạo được lịch sử valuation.** 35.245 dòng valuation fiinquant
   là 5 năm; vnstock không có đường nào trả lại độ sâu đó. Field nào cần
   percentile valuation theo nhiều năm sẽ **degrade sau khi xoá fiinquant** —
   đây là chi phí thật của 08b, không phải chi tiết.
3. **Quy ước đơn vị khác nhau giữa nguồn**: ROE của KBS là 4,74 (phần trăm),
   của VCI là 0,0589 (phân số). Normalize một lần ở adapter, có test.
4. `lang="en"` bị KBS bỏ qua — `item` trả tiếng Việt; khoá dùng là `item_id`.

## Requirements

1. **Bảng mới `financial_statement_line`**: `symbol · period (text 2026-Q2) ·
   statement (income|balance|cashflow) · item_id text · item_seq smallint ·
   value numeric · source · observed_at` — PK `(symbol, period, statement,
   item_id, item_seq)`. Long format — không đóng cứng cột theo một ngành.
   `item_seq` là bắt buộc, không phải phòng xa: xem "Sửa spec" trên.
2. **Bảng `financial_ratio_snapshot`** từ `Finance.ratio()`: P/E, P/B, ROE,
   ROA… theo quý (long format tương tự).
3. **Job quét** khuôn checkpoint/resume của phase 08; lịch: sau mùa công bố
   BCTC chạy dày (tuần), bình thường thưa (tháng). Tier: chạy được ở free,
   nhanh hơn ở Bronze — job không giả định tier.
4. **Khái niệm chuẩn hoá** — `src/stocks/financial/templates.py`:
   `net_profit` = `net_profit_loss_after_tax` (universal, đã đo trên cả ba
   template) · `pretax_profit` (bank:
   `net_accounting_profit_loss_before_tax`, khác: dòng pretax tương ứng) ·
   `equity` từ balance sheet. `core_operating_result` **non-goal v1** (không
   consumer). Vẫn giữ ba golden test trên mã thật (STB=bank, SSI=securities,
   HPG=non_financial) — chúng bây giờ kiểm *store + resolve đúng số*, không
   kiểm một mapping ba nhánh không còn tồn tại.
   - Mã không khớp template / thiếu item → khái niệm đó `unknown`, KHÔNG
     đoán — screener phase 10 loại mã unknown và nói ra số mã bị loại.
5. **Signal fields mới** (đăng ký đủ 9 thuộc tính ADR-0010):
   `earnings.qoq_yoy_growth_pct`, `earnings.ttm_net_profit_vnd`,
   `earnings.plan_completion_pct` (nếu có kế hoạch — v1 bỏ qua nếu nguồn
   không có). Refusal codes mới thêm câu ở cả `alpha/reasons.py` và
   `signal-issues.ts`.

## Kết quả nghiệm thu 09a (2026-08-27/28)

- `make test`: **1232 pass** (baseline 1152, +79 test offline). Alembic head
  `e6b3d90c41af`, một head.
- Declared 30 mã: 50.728 dòng (46.576 statement + 4.152 ratio), 0 lỗi, 114 giây.
  Chạy lần hai: 30 mã bỏ qua, 0 dòng — idempotent.
- Coverage declared tại 2026-Q2: `net_profit` **30/30** · `pretax_profit` 30/30
  (28 theo nhãn, **2 theo đẳng thức thuế**) · `equity` 30/30. `equity` của STB
  khớp `parent_equity_vnd` trong `provider_snapshots` tới từng đồng.
- Dòng `item_id` trùng của SSI vào store thành hai dòng thật:
  `(seq 0, 4.585.945.424)` và `(seq 1, 758.786.600)` — không mất dữ liệu.

### `pretax_profit` không universal (sửa lại spec một lần nữa)

Spec 2026-08-27 đoán `pretax_profit` giải được theo nhãn ở mọi template. Sai:
SSI **không có** dòng pretax gán nhãn đúng — pretax của nó nằm ở
`business_income_tax_expenses` = +1.528.966.041.130. Resolver chỉ nhận ứng viên
đó khi **số học chứng minh** (`net = candidate + tax_current + tax_deferred`) và
ghi bằng chứng đã dùng vào `basis` (`labelled` | `tax_identity` | `unknown`).
Cùng cổng đó **từ chối** dòng cùng tên của STB, nơi giá trị thật đúng là tiền
thuế. Kiểm tay: `1.528.966.041.130 − 301.667.112.228 + 4.585.945.424 =
1.231.884.874.326` = `net_profit` của SSI.

### Coverage market-wide: 74,7%, và lý do không phải template

Quét market `--statements income`: **1.137/1.523 mã** có 2026-Q2 (74,7%), dưới
kỳ vọng ≥85% của spec. Điều tra:

- **288 mã vnstock không có BCTC nào** — probe tay A32 · ACE · BCP đều trả
  frame **rỗng `(0, 0)`**, lặp lại y hệt qua hai lượt quét. Không phải rate
  limit, không phải bug: nguồn không có dữ liệu cho nhóm mã này (phần lớn
  UPCOM nhỏ).
- ~98 mã có BCTC nhưng **chưa công bố quý 2026-Q2**.

Nên ngưỡng 85% của spec không đạt được bằng cách sửa code hay chạy lại; nó là
trần của nguồn. Screener đã tự báo `health: degraded` và nói ra coverage.

### Lỗi im lặng đã vá: constructor provider ngoài wrapper

Quét market-wide chết giữa chừng hai lần với **exit code 0, không mã nào bị
báo lỗi**. Nguyên nhân thật là container api thoát (probe LLM 429 lúc startup —
xem "Nợ ngoài phase"), nhưng truy vết lộ ra một lỗ hổng riêng: `Finance(...)`
và `Quote(...)` được dựng **ngoài** `safe_vnstock_call`, mà vnstock gọi
`sys.exit()` khi hết kiên nhẫn và `SystemExit` là `BaseException` — `except
Exception` bắt-từng-mã của job không thấy nó. Đã dựng cả hai client qua chính
wrapper, thêm hai test giữ luật, và sửa một test cũ stub `safe_vnstock_call`
quá rộng nên che mất đường constructor.

## Files

- `src/stocks/financial/{__init__,fetch,templates,store,reads}.py`
- `src/stocks/financial_scan_job.py` — CLI checkpoint/resume
- Alembic: 2 bảng mới (additive)
- `src/stocks/signals/fundamentals.py` — mở rộng đọc store mới
- Tests: template golden ×3 · long-format round-trip · job resume ·
  signal fields refusal đúng mã input thiếu

## Steps

1. Backup → alembic → bảng.
2. Fetch + store long format (chưa mapping) + smoke 5 mã đa ngành.
3. Templates + golden tests (đối chiếu tay — bước chậm, không tắt).
4. Job quét declared 30 mã trước → verify → market-wide một lượt.
5. Signal fields + refusal wiring hai đầu.

## Validation

- 3 golden test khớp số công bố (sai số làm tròn ≤0,1%) **và** khớp quan hệ
  `net_profit ≈ pretax − tax` — nguồn có nhãn sai (xem cảnh báo trên), nên một
  cổng dựa vào nhãn là cổng không kiểm gì. Số công bố cần user cấp BCTC hoặc
  link; nếu không có, ghi rõ test đối chiếu bằng quan hệ số học thay vì tuyên
  bố đã đối chiếu tay.
- Coverage report: % mã market có `net_profit` resolvable per quý gần nhất —
  ghi số thật vào report phase (kỳ vọng ≥85%; thấp hơn → điều tra template).

## Risk & rollback

- R5: template sai → số đẹp mà sai. Chốt: không template nào ship thiếu
  golden test đối chiếu tay. Insurance/utilities lệch template generic →
  unknown, không đoán.
- vnstock đổi item_id: store giữ raw item_id nên dữ liệu cũ an toàn; mapping
  vá được không re-fetch. Rollback: drop 2 bảng mới (downgrade), signals mới
  gỡ đăng ký.
