# Phase 04 — projection khai trên từng field

Plan: `plans/260828-2126-price-basis-and-signal-field-spine/`
Nhánh: `feat/study-canvas-runtime` · 2026-08-28
Trước đó: [Phase 02+03](./cook-260828-2310-phase-02-03-spine-into-signals.md)

## Cổng

| Cổng | Kết quả |
|---|---|
| `make test` (api) | ✅ **1347 passed** |
| `tests/studies/` | ✅ **117 passed** |
| `pnpm type-check` | ✅ |
| `pnpm lint` | ✅ |
| `pnpm test` (web) | ✅ **724 passed / 57 file** |
| `pnpm build` | ⏭ **cố ý bỏ qua** — xem §Cổng production web |

## Việc đã làm

### `projection` là declaration thứ mười

`BarProjection` chuyển từ `bars.py` sang `fields.py`. Hướng import bắt buộc thế:
`bars.py` **đã** import `fields.py`, nên chiều ngược lại là vòng. Và hướng đó
đúng về mặt ý nghĩa — field khai nó cần gì, gateway tuân theo. `bars.py`
re-export lại; không caller nào ngoài `bars.py` từng dùng tên này, nên phép
chuyển không lộ ra ngoài.

`SignalField.projection` **không có default**, đúng như chín declaration kia:
mặc định của gateway là PRICE, và một field không đọc giá nào đang **thầm** thừa
kế mọi refusal về price basis và band đi kèm. Bỏ sót một field bây giờ là
`TypeError` lúc import.

Cả 30 field đã khai. **20 PRICE · 2 VOLUME · 8 refuse sớm.**

Hai field đi VOLUME, mỗi cái kèm lý do viết tại chỗ:

| Field | Vì sao VOLUME |
|---|---|
| `liquidity_profile.adtv_shares` | chỉ đọc `volume`; số cổ phiếu là số cổ phiếu trên cả hai basis. Đứt đơn vị do stock dividend vẫn đi ra dưới `volume_basis_break` |
| `factor_percentiles.roe_percentile` | tỉ số từ BCTC, không đọc giá ở bất kỳ bước nào; nó cần window chỉ để được đóng dấu cùng một cutoff với mọi thành viên khác của mẫu |

Ba field trông giống VOLUME nhưng **phải PRICE**, cũng ghi tại chỗ:

- `liquidity_profile.adtv_percentile` — **không thể** chuyển. Peer standing nó
  xếp hạng chỉ được đo khi projection là PRICE (`bars._adtv_standing`), nên đẩy
  sang VOLUME là khoá nó vào `ranking_unavailable` vĩnh viễn: một refusal do
  chính declaration sinh ra, không phải do store thiếu gì.
- `liquidity_profile.adtv_vnd`, `amihud_illiq` — sau Phase 05 chúng làm số học
  trên `close`.

`volatility_regime.gk_variance_robust_z` giữ PRICE dù estimator là intra-bar
(basis-invariant): reading của nó mang `limit_lock_days`, đến từ máy band, và chỉ
projection PRICE đo band.

### `serving.py` truyền projection cho **cả hai** hàm

`prepare_bars` và `prepare_bars_context` so projection với nhau và raise
`ValueError` **trần** khi lệch — 500 chứ không phải refusal. Truyền cho một trong
hai còn tệ hơn không truyền cho cái nào. Ba chỗ, có comment giải thích tại chỗ
gọi `prepare_bars_context`.

### `registry_version()` — đưa `projection` vào digest

Quyết định: **đưa vào**. Digest phủ sáu declaration một reader hành động theo;
`projection` là cái thứ bảy, và nó quyết định **field có trả lời được hay
không** — nó chọn contract gateway áp lên window, nên chuyển một field giữa hai
projection biến một refusal thành một con số hoặc ngược lại. Đó là thay đổi lớn
hơn với ý nghĩa của câu trả lời so với bất kỳ cái nào trong sáu cái kia, và
Evidence Manifest mang digest này đúng để hai câu trả lời sinh dưới hai luật khác
nhau không bị so như thể cùng luật. Có test: đổi projection của một field →
digest đổi.

`registry_version()` vẫn **dẫn xuất**, không bump tay. Không thêm cơ chế nào.

### Bảy field mất nguồn — không thêm mã refusal nào

Đo trên dữ liệu thật: cả ba mã đã có **đã nối sẵn** trong reading, không phải
viết mới. `cross_sectional.py:446,513` trả `MARKET_CAP_ABSENT`;
`foreign_flow.py:122,322,349` trả `FOREIGN_FLOW_NOT_STORED` /
`FOREIGN_ROOM_NOT_STORED`. Sau Phase 03 cổng basis không còn chặn trước chúng,
nên chúng tự đến đúng chỗ.

**0 mã refusal mới.** Kiểm hai chiều bằng máy: mọi thành viên `SignalIssue` đều
có câu ở `alpha/reasons.py` **và** ở `apps/web/src/lib/signal-issues.ts`, thiếu
0 ở cả hai phía. `signal-issues.ts` **không cần sửa** — plan liệt nó vào "Related
Code Files" nhưng đó là hệ quả của giả định có mã mới, mà quyết định "dùng ba mã
đã có" đã bỏ giả định đó. Không đụng file web nào.

## Đo lại trên dữ liệu thật — không đổi so với Phase 03

Cùng probe, container `stockmassive-api-1`, `end = 2026-08-27`: **19 field trả
số, 11 từ chối**, y hệt sau Phase 03.

Điều đó đúng và không phải là "phase này không làm gì". Trên spine hôm nay mọi
dòng cùng một basis, nên hai field VOLUME đã chạy được ngay sau Phase 03 nhờ cổng
basis mở. Cái Phase 04 mua là **tính bền**: projection giờ là một declaration
được thi hành, không phải một mặc định thừa kế. Chứng minh cơ học ở
`test_a_volume_field_is_served_where_a_price_field_is_refused` — cùng một window
có seam hai basis: field PRICE nhận `MIXED_PRICE_BASIS`, field VOLUME trả số.
Đó chính là cảnh sẽ xảy ra ở bất kỳ mã nào có cả dòng `raw` lẫn `adjusted`.

## Success Criteria

- [x] Cả 30 field khai projection; import không vỡ (`TypeError` nếu bỏ sót)
- [x] 2 field VOLUME trả số trên window `adjusted_at_source`
- [x] 7 field mất nguồn trả đúng ba mã có sẵn; **0 mã refusal mới**
- [x] `beta_vs_market_index` vẫn `UNAVAILABLE`
- [x] Quyết định về `registry_version()` ghi ra, và có test giữ nó
- [x] `make test` + `tests/studies/` xanh; ba cổng web đọc-được xanh
- [ ] **`adtv_percentile` trả số** — không đạt được ở Phase 04 và không thể đạt.
      Nó cần `SessionSnapshot.total_value_vnd`, mà `bar_daily` **không có cột
      traded value**; suy diễn `close × volume` là Phase 05. Cái Phase 04 làm
      xong là bảo đảm **projection không còn là lý do từ chối**: nếu để nó ở
      VOLUME thì nó sẽ `ranking_unavailable` kể cả sau Phase 05.

## Cổng production web — vì sao bỏ qua

`pnpm build` ghi đè cây `.next` của dev, và session `stock-massive-55` đang sửa
web trực tiếp trong cùng working tree này (30 file, còn dở). Chạy build lúc này
làm hỏng vòng lặp của nó — đúng sự cố đã ghi trong bộ nhớ dự án. Phase 04 **không
sửa file web nào**, nên kết quả build không đổi vì tôi; ba cổng đọc-được
(`type-check`, `lint`, `test`) đã chạy và xanh. Cổng build phải chạy lại khi
session kia đóng việc — nó là điều kiện của Definition of Done, không phải của
riêng phase này.

## Việc phải sửa trong plan (nhắc lại từ báo cáo trước, chưa ai sửa)

1. Bảng "30 Signal Field" trong `plan.md` tổng **31** — `momentum_rank` bị đếm
   vào nhóm 17 trong khi nó là cross-sectional.
2. `company_profile.foreign_room_pct` **không** chết (capability `reference`,
   nguồn vnstock). "22 sống · 8 từ chối" nên là **23 sống · 7 từ chối** sau
   Phase 06.
3. Phase 04 "Related Code Files" liệt `apps/web/src/lib/signal-issues.ts`; không
   cần, vì không có mã refusal mới.

## Câu hỏi chưa giải quyết

1. Ai cài cron `make backfill-daily`? (còn treo từ Phase 02)
2. Nhánh BAND của `check_price_claim` — Phase 06 mở lại được cùng lúc mở
   `band_pressure` không? (còn treo từ Phase 03)
3. `pnpm build` phải chạy lại sau khi session `stock-massive-55` đóng việc web.
