# Phase 09 — Store BCTC quý market-wide (nhóm E)

Phụ thuộc 08 (roster + ICB). Phần dễ sai nhất của lộ trình (R5).

## Context

vnstock Finance: 1 mã/request, wide-format theo quý, `item_id` là khoá ổn
định (OBSERVED: STB bank có 26 dòng income statement, **không có
doanh thu/COGS** — line-item khác hẳn doanh nghiệp sản xuất). Community = 8
quý (đủ YoY); Bronze = không giới hạn kỳ. Quét ~1.600 mã ≈ 9 phút/lượt Bronze,
~27 phút free.

## Requirements

1. **Bảng mới `financial_statement_line`**: `symbol · period (text 2026-Q2) ·
   statement (income|balance|cashflow) · item_id text · value numeric ·
   source · observed_at` — PK `(symbol, period, statement, item_id)`. Long
   format — không đóng cứng cột theo một ngành.
2. **Bảng `financial_ratio_snapshot`** từ `Finance.ratio()`: P/E, P/B, ROE,
   ROA… theo quý (long format tương tự).
3. **Job quét** khuôn checkpoint/resume của phase 08; lịch: sau mùa công bố
   BCTC chạy dày (tuần), bình thường thưa (tháng). Tier: chạy được ở free,
   nhanh hơn ở Bronze — job không giả định tier.
4. **Industry template mapping** — trái tim của phase:
   `src/stocks/financial/templates.py` — map ICB group → bộ item_id cho
   khái niệm chuẩn hoá: `net_profit`, `pretax_profit`, `core_operating_result`
   (định nghĩa per-template), `equity`. v1 phủ 3 template: `bank`,
   `securities`, `non_financial` (generic). Mỗi template có **golden test
   trên một mã thật** (STB=bank, SSI=securities, HPG=non_financial) với số
   đối chiếu tay từ BCTC công bố.
   - Mã không khớp template / thiếu item → khái niệm đó `unknown`, KHÔNG
     đoán — screener phase 10 loại mã unknown và nói ra số mã bị loại.
5. **Signal fields mới** (đăng ký đủ 9 thuộc tính ADR-0010):
   `earnings.qoq_yoy_growth_pct`, `earnings.ttm_net_profit_vnd`,
   `earnings.plan_completion_pct` (nếu có kế hoạch — v1 bỏ qua nếu nguồn
   không có). Refusal codes mới thêm câu ở cả `alpha/reasons.py` và
   `signal-issues.ts`.

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

- 3 golden test khớp số công bố (sai số làm tròn ≤0,1%).
- Coverage report: % mã market có `net_profit` resolvable per quý gần nhất —
  ghi số thật vào report phase (kỳ vọng ≥85%; thấp hơn → điều tra template).

## Risk & rollback

- R5: template sai → số đẹp mà sai. Chốt: không template nào ship thiếu
  golden test đối chiếu tay. Insurance/utilities lệch template generic →
  unknown, không đoán.
- vnstock đổi item_id: store giữ raw item_id nên dữ liệu cũ an toàn; mapping
  vá được không re-fetch. Rollback: drop 2 bảng mới (downgrade), signals mới
  gỡ đăng ký.
