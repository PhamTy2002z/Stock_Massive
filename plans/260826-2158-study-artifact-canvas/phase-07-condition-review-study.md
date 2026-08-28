# Phase 07 — Study `entry_condition_review` (nhóm C)

Phụ thuộc 06 **và 08a**. Case 3 của `idea.md`, đã reframe theo quyết định
user: **Condition Review, không verdict chỉ thị, không nhãn PREFERRED.**

## Sửa spec 2026-08-27 (đo trước khi thi công)

Ba chỗ bản cũ không thi công được:

1. **Bỏ bước "ensure_daily_bars trong phase này".** Nguồn giá daily do 08a
   dựng (`bar_daily`, vnstock, `adjusted_at_source`); study chỉ đọc store qua
   reader trong `src/studies/`. Đường ghi `provider_snapshots` mà bản cũ chọn
   bị `signals/bars.py::_basis_of` từ chối — chi tiết ở phase-08.
2. **Momentum/risk tính trong Study, không đọc Signal Field.** Bản cũ lấy
   `trend_signal.total_return_12m_pct` · `drawdown_stats.current_drawdown_pct`
   · `indicator_pack.rsi_14`. Ba field đó suy từ `provider_snapshots` capability
   MARKET, mà **nguồn `raw` duy nhất ở đó là 36.528 dòng fiinquant** — tức
   canvas sẽ vẽ số FiinQuant, đúng cái R2 phase này nói là đi vá. Tính lại từ
   `bar_daily`: return 12m, drawdown hiện tại, RSI 14 đều là hàm thuần trên
   series đóng cửa, và series `adjusted_at_source` **là input đúng** cho cả ba
   (adjust là điều ta muốn khi đo lợi nhuận nắm giữ). Thêm: study không còn
   phụ thuộc luật declared-only của `get_field`.
3. **Lợi nhuận quý đọc store, không gọi provider.** Đo 2026-08-27:
   `provider_snapshots` capability `fundamental` source `vnstock` có **≥8 quý
   cho cả 30/30 mã declared** (payload đã có `net_profit_after_tax_vnd`,
   `parent_net_profit_vnd`, `pre_tax_profit_vnd`, `period_end`). Reader nhỏ
   trong `src/studies/` lấy 8 snapshot mới nhất của một mã; không thêm ingest,
   không gọi `Finance` lúc trả lời. Mã ngoài declared thiếu quý → trục earnings
   `unknown`, không refuse cả study.
4. **PROMPT_VERSION: 2.6.0 → 2.7.0** (bản cũ ghi 2.3.0 → 2.4.0, viết trước khi
   phase 04-06 bump lên 2.6.0).

## Context

Câu "Có thể mua STB giá hiện tại không?" trả về: bằng chứng theo 4 trục +
checklist "điều gì phải xảy ra" ✓/✕/chưa rõ — user tự kết luận. Đây là bản
`idea.md` tự đề xuất ở đoạn cuối, và là bản hợp luật prompt 2.3.0 ("nêu mức
và hệ quả, không chỉ thị hành động").

## Requirements

**Vá provenance trước (R2):** study này vẽ giá gần đây. Bước 1 của phase:
`ensure_daily_bars(symbol, sessions=280)` — ingest daily từ vnstock cho mã
được hỏi (1 request/mã, khuôn phase 02, bảng `bar_daily` mới hoặc ghi
`provider_snapshots` capability MARKET source=vnstock — **chốt khi làm: ghi
provider_snapshots để tái dùng `signals/bars.py` reader hiện có**). Canvas
không render dữ liệu FiinQuant.

**Compute** (params: `symbol`, `horizon_sessions` default 250):
- Vị thế giá: last, dải 52w (high/low/percentile vị trí hiện tại).
- Cấu trúc giá gần: vùng tích luỹ suy từ price structure — v1 dùng thuật toán
  đơn giản, khai báo được: cụm đỉnh/đáy cục bộ 60 phiên, lấy dải tần suất
  đóng cửa cao nhất (histogram 20 bin, top-2 dải liên tục). **Tính lại mỗi
  lần, không hard-code** — `idea.md` tự dặn đúng điều này.
- Xu hướng lợi nhuận quý: 8 quý từ vnstock Finance (`net_profit_loss...`
  item_id — probe đã xác nhận shape), YoY 4 quý gần nhất.
- Momentum/risk tính trong Study từ `bar_daily` (xem "Sửa spec" trên):
  return 12 tháng · drawdown hiện tại so đỉnh 52w · RSI 14.
- Checklist điều kiện (backend authored, template theo trạng thái dữ liệu):
  mỗi điều kiện `{label, status: met|not_met|unknown, evidence_ref}` — vd
  "Lợi nhuận quý gần nhất dương và cải thiện YoY", "Giá không sát đỉnh 52w
  (>5% dưới đỉnh)", "RSI không quá mua (<70)". Status do engine tính; câu
  chữ cố định trong code, không do model viết.

**headline**: verdict-free — `{pricePosition, earningsTrend, conditions:
{met, notMet, unknown}}`. **frames**: `price_context` (series 250 phiên +
dải 52w + vùng tích luỹ), `earnings_quarters` (8 quý), `conditions` (table).

**view** → `range_strip` (vị thế trong dải 52w) · `line_series` (giá, overlay
band tích luỹ) · `bar_series` (quý) · `condition_checklist` · ghi chú
disclaimer cố định (khuôn Robinhood/Public: mô tả dữ liệu + giới hạn, không
"nên/hãy").

**PROMPT_VERSION bump** (2.6.0 → 2.7.0): thêm luật framing khi diễn giải
condition review — model tường thuật trạng thái điều kiện, cấm động từ mệnh
lệnh, cấm gắn giá cụ thể với hành động. Amend một lần ở đây, không rải.

**Widget mới:** `range_strip` (SVG tự vẽ — dải min/max + marker, có text
equivalent) · `condition_checklist` (không chart lib) · `scenario_cards`
**bỏ** — không còn scenario chỉ thị sau reframe (cắt khỏi scope so với đề
xuất gốc; ghi rõ để không ai đòi lại nhầm).

## Files

- `src/studies/entry_condition_review.py` + tests (golden: fixture giá
  synthetic có vùng tích luỹ cắm sẵn; checklist statuses deterministic)
- `src/studies/reads_daily.py` (đọc `bar_daily`) + `reads_fundamental.py`
  (8 quý mới nhất của một mã) — **không** module ingest nào ở phase này
- `src/agent/prompt/sections.py` + version bump + test contract_hash đổi
- web: `range-strip.tsx`, `condition-checklist.tsx` + tests

## Validation

- Acceptance #5 plan.md: phase này thêm study mà KHÔNG sửa `loop.py`; bump
  prompt chỉ vì luật framing — kiểm bằng diff.
- Câu hỏi STB thật → canvas 4 block, không có từ chỉ thị trong headline
  (test regex cấm "nên mua|mua ngay|WAIT|BUY" trong headline serialize).

## Risk & rollback

- Thuật toán vùng tích luỹ v1 thô: chấp nhận, nhãn "vùng giá đóng cửa tập
  trung" thay vì "hỗ trợ/kháng cự" (không hứa semantics TA mạnh hơn thuật
  toán). Rollback: gỡ study; prompt 2.4.0 giữ (luật framing vô hại khi study
  vắng).
