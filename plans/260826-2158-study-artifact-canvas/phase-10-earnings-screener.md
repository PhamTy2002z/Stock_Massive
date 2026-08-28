# Phase 10 — Study `earnings_dislocation_screener` (nhóm E, chốt)

Phụ thuộc 06 (scatter_quadrant, data_table) + 08a (giá daily + VN-Index) +
09 (BCTC store). Case 2 của `idea.md`.

## Sửa spec 2026-08-27

- **`adtv` suy ra, không đọc cột.** vnstock daily trả `time, open, high, low,
  close, volume` — **không có cột giá trị giao dịch**. Sàn thanh khoản tính
  `median(close × volume)` trên cửa sổ, ghi rõ trong provenance là xấp xỉ
  (giá đóng cửa × khối lượng, không phải giá khớp trung bình).
- **Basis không ảnh hưởng trục giá của screener.** `bar_daily` là
  `adjusted_at_source`; return 20 phiên và relative-vs-VNINDEX là tỷ số nên
  bất biến với adjust, trừ đúng phiên ex-date. Nêu trong provenance.
- Universe market = **1.523 mã STOCK listed** (số đo 2026-08-27), không phải
  ~1.600.

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

## Kết quả nghiệm thu (2026-08-28)

- `make test`: **1260 pass** (baseline 1232, +26). `make lint` xanh.
- `loop.py` diff **trống**, không đổi prompt, không migration, không file web —
  acceptance #5 của plan (Study thêm được mà không đụng cơ chế) đứng vững ở
  Study **thứ ba**.
- Chạy thật trên store: **1.523 mã quét, 0,27 giây**, 174 đo được, 77 khớp.
  Loại trừ cộng khớp tuyệt đối: 1.446 + 77 = 1.523.
  `no_filing` 399 · `thin_liquidity` 453 · `insufficient_price_history` 239 ·
  `non_positive_profit` 170 · `non_positive_prior_profit` 74 ·
  `below_growth_threshold` 70 · `above_price_change` 27 · `no_prior_filing` 14.
- `health: degraded` đúng như phải thế: store mới có 74,7% mã ở 2026-Q2 và
  đó là trần của nguồn (xem phase-09).
- Kiểm tay ba mã top từ store: BVB `264,83/10,338 → +2.461,7%` · KSF
  `4.535,2/40,98 → +10.967%` · POW `3.707,7/761,35 → +386,99%`. Số học đúng
  từng con.

### `template_unknown` không tồn tại

Spec liệt `template_unknown` làm một lý do loại. Dữ liệu bác:
`net_profit_loss_after_tax` giải được **theo nhãn** ở cả ba template, nên
`concept_unknown` = 0 hôm nay. Lý do loại thật mà dữ liệu ép ra là quý gốc
thiếu và lợi nhuận không dương.

### Hiệu ứng nền thấp — chưa xử, chờ quyết

Top list đang bị chi phối bởi mã có **quý gốc gần bằng 0**: BVB +2.462% vì quý
2025-Q2 chỉ 10,3 tỷ; KSF +10.967% từ nền 41 tỷ. Bộ lọc hiện chỉ đòi lợi nhuận
**dương** ở cả hai quý, mà dương-nhưng-tí-xíu vẫn ra phần trăm khổng lồ.
`dislocation_rank` dùng percentile nên ảnh hưởng bị chặn, nhưng thứ tự top vẫn
do nhóm này chiếm.

Đây là **đổi ngữ nghĩa sàng lọc mà plan đã đặc tả**, nên không tự sửa. Hai
đường: (1) sàn lợi nhuận quý gốc (vd ≥50 tỷ VND) thành một lý do loại đếm
được; (2) đổi sang tăng trưởng TTM thay YoY một quý — mượt hơn nhưng cần 5 quý
và giảm số mã đo được. Để nguyên cũng hợp lệ nếu coi đây là màn hình thô.

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
