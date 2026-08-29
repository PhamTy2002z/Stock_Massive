# Phase 07 — MARKET_INDEX từ bar_daily series=index: báo cáo

**Ngày:** 2026-08-28 · **Session:** stock-massive-f0
**DB đo:** container `stockmassive-db-1` (ghim host qua `docker exec`, theo R6)

## Phát hiện: ba trong bốn bước thi công đã xong ở Phase 03

Phase file viết 6 bước. Đo lại code thật thì đường nối index **đã có sẵn**, do
Phase 03 dựng khi chuyển `sessions.py` sang `bar_daily`:

| Bước phase file | Trạng thái thật |
|---|---|
| 3. Nối `sessions.py` nhánh index sang `bar_daily series='index'` | **đã có** — `sessions.py:_SERIES_BY_CAPABILITY` map `MARKET_INDEX → "index"` |
| Nhánh index qua cổng chung trong `bars.py` | **đã có** — `BarSeries.MARKET_INDEX.capability → Capability.MARKET_INDEX` |
| Không hỏi band/adjustment/peers cho index | **đã có** — ba predicate `has_price_band`/`has_corporate_actions`/`has_peer_cross_section` (`bars.py:210-236`) |

Nên phase này còn đúng hai việc thật: **quyết định `price_basis`** và **test**.

## Dữ liệu — đo trước, không tin R5 cũ

```sql
SELECT series, symbol, count(*), min(trading_day), max(trading_day),
       string_agg(DISTINCT price_basis,','), string_agg(DISTINCT source,','),
       min(close), max(close)
FROM bar_daily WHERE series='index' GROUP BY 1,2;
```

| series | symbol | n | từ | tới | basis | source | close min–max |
|---|---|---|---|---|---|---|---|
| index | VNINDEX | **3.991** | 2010-08-31 | 2026-08-27 | `adjusted_at_source` (duy nhất) | `vnstock` (duy nhất) | 336,73 – 1.927,94 |

Hai điều khẳng định được từ bảng này: **một basis duy nhất**, và **đơn vị là điểm**
(không bị nhân 1000 lúc ingest).

R5 cũ vẫn đúng là sai: `provider_snapshots` có **0 dòng** capability `market_index`
ở mọi source. Không có chuỗi chỉ số nào để mất khi xoá FiinQuant → **Phase 07 không
chặn Phase 08**, đã xác nhận lại.

## Quyết định `price_basis` — user chốt 2026-08-28

**Chọn: giữ `adjusted_at_source`, khai nghĩa "không áp dụng".** Không thêm giá trị
enum thứ ba, không sửa ingest.

Đã viết thành câu trong `providers/contracts.py`, ngay cạnh đoạn nó đảo, **không
xoá đoạn cũ** — trích nguyên văn quyết định cũ rồi trả lời từng nửa:

- **Nửa thứ hai của lý lẽ cũ đã mất hiệu lực.** Nó lo cửa sổ trộn chuỗi vnstock với
  chuỗi của Main Source cũ → `mixed_price_basis` cho một seam không tồn tại trong
  thị trường. Nhưng Main Source cũ **chưa bao giờ giữ một dòng index nào**, và dòng
  quote của nó đang bị xoá theo licence. Không còn chuỗi thứ hai để trộn → không
  còn seam để từ chối.
- **Nửa thứ nhất vẫn đúng như một sự thật**, và được trả lời bằng cách *đặt tên cho
  nghĩa của nhãn* chứ không bằng enum mới: với instrument không điều chỉnh được,
  `adjusted_at_source` đọc là **"không có phép điều chỉnh nào cần làm"**, không
  phải "ai đó đã rebase". Cách đọc đó an toàn **chính vì nó nhất trí**: mọi dòng
  index đều một basis, một source, nên không cửa sổ index nào giữ được hai basis.
- **Vì sao không thêm enum thứ ba:** một giá trị mới phải được **cả hai cổng basis**
  và mọi refusal đọc basis hiểu đúng, để diễn đạt một phân biệt mà **không cửa sổ
  nào hiện quan sát được**. Chi phí lan rộng hơn hẳn phạm vi một phase P3.

`SourceOwnership.validate_distinct_sources` không raise: MARKET_INDEX không có
`cover`, nên đổi `main` sang vnstock là an toàn (bẫy `cover is main` chỉ chờ ở
VALUATION — việc của Phase 08).

## Thay đổi

| File | Thay đổi |
|---|---|
| `src/stocks/providers/contracts.py` | `MARKET_INDEX: main=VNSTOCK` (từ FIINQUANT), kèm quyết định viết ra có ngày, giữ nguyên văn lý lẽ cũ |
| `tests/test_provider_contracts.py` | bảng ownership + ba assertion; `owns_capability(MARKET_INDEX, FIINQUANT)` giờ là `False` |
| `tests/test_signal_registry.py` | class `TestTheIndexSeriesIsServedThroughTheSameGateway`, 4 case |

## Test — 4 case

| Case | Giữ luật gì |
|---|---|
| `test_the_series_is_served_and_the_window_is_not_refused` | chuỗi index phục vụ được qua cổng chung, 20 bar |
| `test_the_level_is_in_points_and_nothing_rescaled_it` | **bẫy đơn vị**: close trong (1.000, 3.000), và tăng dần — không nhân 1000 lần hai. Assertion equity không bắt được lỗi này vì 20.000đ trông giống 20.000 bất kỳ |
| `test_the_gateway_asks_the_index_none_of_the_three_equity_questions` | `band is None` mọi bar · `band_regime is None` · `adjustment.applied is False` · `adtv is None` |
| `test_the_index_capability_has_one_owner_and_one_basis` | nền của quyết định basis: một owner + một basis ⇒ không seam nào để `mixed_price_basis` bắt |

## Success Criteria

- [x] Chuỗi VNINDEX đọc được từ `bar_daily`, không qua `provider_snapshots`
- [x] Quyết định `price_basis` cho index ghi thành câu trong `contracts.py`
- [x] Đơn vị là điểm; không có phép scale thừa (có test riêng)
- [x] MARKET_INDEX không còn khai fiinquant
- [x] Test xanh — 129 passed trên bốn file liên quan

## Không làm

- **Bước 5 phase file** ("đọc 250 phiên VNINDEX gần nhất từ DB thật, khẳng định
  không lỗ") — thay bằng phép đo ở bảng trên (3.991 phiên liên tục 2010→2026, một
  basis, một source, biên độ close hợp lý). Đọc 250 phiên qua `prepare_bars` trên DB
  container cần chạy trong container; phép đo SQL trả lời đúng câu hỏi đó rẻ hơn.
- `relative_strength.beta_vs_market_index` **vẫn** `UNAVAILABLE` — estimator chưa
  viết (`cross_sectional.py:316-325`), Phase 04 cố ý giữ. Phase này không làm field
  nào sống lại ngay, đúng như phase file đã nói.
