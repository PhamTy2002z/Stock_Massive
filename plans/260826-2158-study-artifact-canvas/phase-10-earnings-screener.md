# Phase 10 — Study `earnings_dislocation_screener` (nhóm E, chốt)

Phụ thuộc 06 (scatter_quadrant, data_table) + 09 (BCTC store). Case 2 của
`idea.md`.

## Context

"Top mã lợi nhuận tăng mạnh nhưng giá chưa phản ánh" — screening strategy,
không phải một query. `idea.md` đòi đúng: "giá chưa tăng" phải đo **tương
đối** (vs VN-Index — phase 08 đã mở) và mốc từ ngày quanh kỳ công bố, không
phải giá đầu quý.

## Requirements

Params: `period` (vd `2026-Q3`, default quý gần nhất đã công bố đủ),
`min_profit_growth_pct` (default 20), `max_price_change_pct` (default 5),
`top_n` (default 10, clamp ≤20), `universe` (`market` default).

`compute` (đọc store phase 08+09, KHÔNG gọi provider trong compute):
1. Universe market → loại mã `net_profit=unknown` (đếm và **nói ra** số loại
   theo lý do: no_filing · template_unknown · thin_liquidity).
2. YoY growth per mã; lọc growth ≥ ngưỡng, net_profit > 0.
3. Price reaction: return 20 phiên gần nhất + relative vs VN-Index cùng cửa
   sổ. (Mốc "từ ngày công bố" cần publication date per filing — vnstock không
   trả; v1 dùng cửa sổ 20 phiên cố định, ghi rõ hạn chế trong provenance.
   Point-in-time đầy đủ là câu hỏi mở, KHÔNG giả vờ có.)
4. Composite rank — **đặt tên `dislocation_rank`, không phải "opportunity
   score"**: nhãn "opportunity" đọc thành khuyến nghị (cùng lớp vấn đề D2).
   Thành phần minh bạch trong provenance: growth percentile ×
   (−relative_return percentile) × liquidity floor (`adtv ≥ 3 tỷ VND/phiên`
   loại penny không giao dịch được).
5. Anti-lookahead tối thiểu: chỉ xét mã đã có filing kỳ `period` trong store
   tại thời điểm chạy; universe từ roster hiệu lực hiện tại (survivorship của
   quá khứ xa: ngoài scope v1, ghi hạn chế).

`headline`: `{period, screened, afterFilters, excluded: {...reasons}, top: [
{symbol, growthPct, relReturnPct, rank}...≤10 ]}`.
`frames`: `scatter` (growth × relative return, full candidates),
`ranking` (table top_n với các cột minh bạch), `filters` (table tham số +
số mã qua từng cửa).

`view` → `stat_tiles` (screened/matched/top) · `scatter_quadrant` (hero —
nhãn 4 vùng mô tả, không mệnh lệnh: "tăng trưởng cao, giá chưa theo" thay vì
"RẤT HẤP DẪN") · `ranked_bars` · `data_table` (filters).

Diễn giải model: tường thuật phân bố + mã nổi bật + hạn chế phương pháp;
luật framing 2.4.0 áp sẵn.

## Files

- `src/studies/earnings_dislocation.py` + golden test (store fixture ~40 mã
  synthetic 3 template, kết quả rank biết trước; test excluded-reasons đếm
  đúng; test regex cấm từ chỉ thị trong headline)
- Không file web mới (widget đã đủ từ 05/06)

## Steps

1. Fixture store synthetic → golden compute.
2. Study + view + đăng ký.
3. Smoke thật trên store sau phase 09: chạy quý gần nhất, đối chiếu tay 3 mã
   top với BCTC công bố.

## Validation

- Golden xanh; smoke thật: `excluded` + `screened` cộng khớp tổng roster.
- Câu hỏi thật end-to-end ra canvas 4 block < 15s (compute trên store, không
  request mạng).

## Risk & rollback

- Screener tin được đúng bằng phase 09: nếu coverage <85%, phase này hoãn —
  không ship screener trên store thưa rồi đổ cho "thị trường". Rollback: gỡ
  study, store giữ.
