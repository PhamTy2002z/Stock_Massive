# SSI FastConnect Data — khảo sát tích hợp làm provider

> **Đã bị vượt một phần (2026-08-21).** Toàn bộ tài liệu này phân tích FCData **v2**
> (`fc-data.ssi.com.vn/api/v2`). Sau đó phát hiện SSI đang chạy song song một thế hệ
> **v3** (`api.ssi.com.vn/api/v3`, SDK `ssi-sdk` 3.2.0 phát hành 2026-08-12) với tập
> endpoint và field khác. v3 **không có** field giá điều chỉnh, nhưng **có** `icb_code`/
> `icb_name`. Đọc `docs/research/ssi-fastconnect-capabilities.md` trước khi dùng bất kỳ
> kết luận nào ở đây.

Ngày: 2026-08-21 · Phạm vi: FCData (market data). FCTrading nằm ngoài phạm vi.
Nguồn: đặc tả chính thức `FastConnectData_Specs_v2_0.pdf` (26 trang, bản V2.0,
changelog cuối 10/05/2022), `guide.ssi.com.vn`, PyPI `ssi-fc-data`, và nghiên cứu
đã có tại `docs/research/vn-market-data-sources.md:73-108`.

## Kết luận trước

FCData **là nguồn EOD tốt nhất trong ba nguồn đang xét cho Capability `market`**,
và là nguồn duy nhất khảo sát được cấp **giá đóng cửa thô và giá đã điều chỉnh
trong cùng một dòng** — đúng thứ `docs/adr/0006` đang thiếu ở Cover Source. Nó
**không** cấp được `valuation`, `fundamental`, vốn hoá, số cổ phiếu lưu hành hay
corporate action, nên không thay được cả FiinQuant lẫn vnstock.

Chặn đường không phải kỹ thuật mà là **điều khoản**: dữ liệu chỉ dùng cho giao
dịch của chính khách hàng, không được cấp cho bên thứ ba. Dùng cho pilot nội bộ
thì hợp; làm xương sống phục vụ end user thì vi phạm.

## 1. FCData cấp được gì — soi theo contract hiện có

### 1.1 `Capability.MARKET` — `DailyStockPrice` khớp gần như trọn `MarketSnapshot`

`GET /api/v2/Market/DailyStockPrice` (spec §4.9), tham số `Symbol`, `FromDate`,
`ToDate` (DD/MM/YYYY), `PageIndex` 1–10, `PageSize` ≤ 100, `Market`.

| Field `MarketSnapshot` | Field FCData | Ghi chú |
|---|---|---|
| `last_price` | `closeprice` | giá thô của phiên |
| `open_price` / `high_price` / `low_price` | `openprice` / `highestprice` / `lowestprice` | |
| `change_pct` | `perpricechange` | có cả `pricechange` tuyệt đối |
| `reference_price` | `refprice` | |
| `ceiling_price` / `floor_price` | `ceilingprice` / `floorprice` | vnstock **không** có cặp này |
| `volume` | `totalmatchvol` | có thêm `totaltradedvol` (khớp + thoả thuận + lô lẻ) |
| `total_value_vnd` | `totalmatchval` | có thêm `totaltradedvalue`, `totaldealval` |
| `foreign_buy_volume` / `foreign_sell_volume` | `foreignbuyvoltotal` / `foreignsellvoltotal` | |
| `foreign_buy_value_vnd` / `foreign_sell_value_vnd` | `foreignbuyvaltotal` / `foreignsellvaltotal` | spec đánh máy sai thành `Toreignsellvaltotal`; ví dụ JSON trả đúng `foreignsellvaltotal` |
| `foreign_net_value_vnd` | `netforeignval` | có cả `netforeivol` cho net khối lượng |
| `active_buy_volume` / `active_sell_volume` | `totalbuytradevol` / `totalselltradevol` | **cần đo**: ví dụ trong spec trả `0` cho cả bốn trường trade — đúng kiểu "chưa công bố" mà `docs/adr/0002` đã gặp với `bu`/`sd` của FiinQuant |
| `market_cap_vnd` | **không có** | phải giữ nguồn khác |

Hai thứ vượt trên cả hai provider hiện tại:

- **`closepriceadjusted` đứng cạnh `closeprice`.** `ADR-0006` chọn `PriceBasis.RAW`
  + điều chỉnh lúc đọc, và ghi rõ Cover Source (vnstock) chỉ có
  `adjusted_at_source` nên một window nằm trọn trong vùng đó bị từ chối. FCData
  cấp thẳng basis `RAW` cho toàn dải lịch sử, tức một `SsiMarketHistoryProvider`
  sẽ **xoá được lớp lỗi `mixed_price_basis`** ở mối nối backfill/collector.
- **`averageprice` (VWAP phiên)** — không có ở cả hai nguồn hiện tại.

### 1.2 `Capability.MARKET_INDEX` — `DailyIndex` đủ dùng, hơn cả bản FiinQuant

`GET /Market/DailyIndex`, `Indexcode` bắt buộc (mã lấy từ `IndexList`), `FromDate`/
`ToDate`, `PageSize` ≤ 1000, `OrderBy`/`Order`.

`indexvalue` → `last_price`; `change`, `ratiochange` → `change_pct`;
`totalmatchvol` → `volume`; `totalmatchval` → `total_value_vnd`. Không có
open/high/low của index — `MarketIndexSnapshot` để ba trường đó optional nên hợp
contract, chỉ là chuỗi index sẽ mỏng hơn chuỗi equity.

Thêm ngoài contract, hữu ích cho market breadth mà hiện chưa có nguồn nào:
`advances` / `nochanges` / `declines`, số mã trần (`ceilings`) và sàn (`floors`),
`totaldealvol`/`totaldealval` (thoả thuận) và `totalvol`/`totalval` (gộp),
`tradingsession` (ATO/LO/ATC/PT/BREAK/C/H).

### 1.3 `Capability.REFERENCE` — cấp một nửa

- `SecuritiesDetails` (§4.3) có **`ListedShare`** → `ShareCount(ShareType.LISTED)`.
  `ReferenceSnapshot.canonical_shares()` ưu tiên `OUTSTANDING` rồi mới `LISTED`,
  nên đây là input hợp lệ nhưng hạng hai. **Không có** cổ phiếu lưu hành, không
  có freefloat.
- `DailyStockPrice` có **`foreigncurrentroom`** → `current_foreign_room`.
  `total_foreign_room` **chỉ có trên streaming channel `R`** (`TotalRoom`), không
  có trên REST. Validator `current ≤ total` vẫn qua vì cả hai optional.
- `SecuritiesDetails` còn cấp thứ repo chưa có nguồn nào: `LotSize`,
  `FirstTradingDate`, bảng bước giá (`TickPrice1-4` / `TickIncrement1-4`), và
  metadata phái sinh/CW (`Underlying`, `ExercisePrice`, `ContractMultiplier`).

### 1.4 `Capability.VALUATION` và `FUNDAMENTAL` — không có gì

Grep toàn spec cho `PE`, `PB`, `EPS`, `financial`, `market cap`, `outstanding`,
`dividend`, `corporate action`: **không một kết quả**. FCData là feed giao dịch,
không phải feed cơ bản. FiinQuant giữ `valuation`, vnstock giữ `fundamental` và
`CorporateActionProvider` — không đổi.

### 1.5 `ListingRosterProvider` — thay không được

`GET /Market/Securities` trả `Market`, `Symbol`, `StockName`, `StockEnName`, phủ
HOSE/HNX/UPCOM/DER (`totalRecord: 560` cho riêng HOSE trong ví dụ). Ba trường
đầu map thẳng `ListingEntry.symbol` / `exchange` / `company_name`, và `Exchange.parse`
nhận đúng cách viết của SSI.

Nhưng **không có ICB**: `ListingEntry.icb_code` / `icb_name` là đầu vào của Profit
Ranking Census (`docs/adr/0004`) và chỉ vnstock cấp. Đổi roster sang SSI là mất
phân loại ngành, nên chỗ này vnstock vẫn giữ.

Lưu ý phân trang: `pageIndex` **tối đa 10** và `pageSize` tối đa 1000 → trần cứng
**10.000 dòng cho một tổ hợp tham số**. Đọc cả register ~1.600 mã vẫn vừa, nhưng
phải lặp theo `Market` để không đụng trần.

### 1.6 Streaming — đây mới là phần FCData thắng tuyệt đối

Tám channel, subscribe theo `CHANNEL:SYMBOL` / `CHANNEL:A-B` / `CHANNEL:ALL`:

| Channel | Nội dung | Giá trị với repo |
|---|---|---|
| `X-QUOTE` | 3 mức giá HOSE, 10 mức HNX/UPCOM/DER + `EstMatchedPrice` | sổ lệnh — hiện không có nguồn nào |
| `X-TRADE` | giá/khối lượng khớp từng lệnh | tick thật, thay được `intraday/collect` |
| `X` | snapshot gộp: `Ceiling`/`Floor`/`RefPrice`/`Open`/`High`/`Low`/`Avg`/`PriorVal`/`LastPrice`/`Change`/`RatioChange`/`TotalVol`/`TotalVal` + 10 mức bid/ask | một message là gần trọn `MarketSnapshot` trong phiên |
| `R` | `TotalRoom`, `CurrentRoom`, `FBuyVol`, `FSellVol`, `FBuyVal`, `FSellVal` | **nguồn duy nhất khảo sát được có `total_foreign_room`** |
| `B` | OHLCV theo tick: `Open`,`High`,`Low`,`Close`,`Volume`,`Value` | nến realtime |
| `MI` | index realtime, đầy đủ như `DailyIndex` + `IndexValEst`, `AllQty`, `AllValue` | |
| `F` | trạng thái mã: `TradingSession`, `TradingStatus` (N/D/H/S/NL/ND/ST/SA/SP) | phát hiện halt/suspend/hủy niêm yết — repo hiện suy ra từ giá |
| `OL` | lô lẻ, kèm 3 mức bid/ask riêng | |

SSI nói thẳng: *"To receive real-time update, you should use streaming connection
rather than using API for polling to avoid rate limit violation."* Trang guide
không công bố transport hay URL; SDK Python dùng lớp `MarketDataStream`
(websocket). Giới hạn số mã subscribe: không công bố.

### 1.7 Soát đầy đủ: SSI hơn hai nguồn hiện tại ở đâu

Bổ sung sau khi đọc lại `providers/vnstock_provider.py:570-585`. Docstring của
`VnstockMarketHistoryProvider` ghi rõ: *"money traded, the flow pairs, the
permitted band and market cap are not in this answer, and are left empty rather
than guessed at."*

Nghĩa là 31.160 dòng vùng 2016→2021 **không chỉ sai Price Basis mà còn rỗng bốn
nhóm field** — giá trị giao dịch, cặp dòng tiền ngoại, dải biên độ, vốn hoá — chỉ
còn OHLC và volume. SSI điền được ba trong bốn (trừ vốn hoá). Đây là lý do mạnh
hơn lý do basis đã nêu ở §1.1.

**Hơn vnstock, trên vùng lịch sử sâu:** basis thô + adjusted trong một dòng;
`totalmatchval`; sáu field khối ngoại; trần/sàn/tham chiếu; `averageprice` (VWAP
phiên); thoả thuận tách riêng (`totaldealvol`/`totaldealval`); tổng gồm lô lẻ
(`totaltradedvol`/`totaltradedvalue`); `foreigncurrentroom` **trên mỗi phiên** so
với 190 dòng snapshot hai tuần hiện có; số lệnh mua/bán (`totalbuytrade` /
`totalselltrade`, cần đo).

**Hơn FiinQuant — vá đúng lỗ 403 mà `docs/adr/0002` ghi.** ADR liệt bốn chỗ
FiinQuant bị 403: room NĐTNN, giao dịch theo nhà đầu tư, độ rộng thị trường, danh
sách mã theo ngành. SSI vá hai: **room** (`foreigncurrentroom` REST; `TotalRoom` +
`CurrentRoom` streaming `R` — nguồn duy nhất có `total_foreign_room` mà
`signals/fields.py:357` khai báo và chưa ai điền) và **độ rộng thị trường**
(`DailyIndex`: `advances`/`nochanges`/`declines`/`ceilings`/`floors`, **có lịch
sử**). Không vá được ICB: `IndexComponents` cho thành phần index, không cho ngành.
Thêm: `closepriceadjusted` cho phép đối chiếu Adjustment Factor **ngay trên vùng
2021→2026 hiện tại**, không cần chờ backfill; `TradingStatus` lịch sử
(`D` hủy niêm yết, `H` tạm dừng, `S` ngừng, `NL` niêm yết mới, `SA`/`SP` ngưng
khớp lệnh/thoả thuận) trong khi repo đang suy trạng thái từ giá; `IndexList` theo
sàn, còn `MARKET_INDEX` hiện chỉ có fiinquant và không có cover.

**Hơn cả hai — repo chưa có nguồn nào:** lớp tài sản ngoài equity (phái sinh, CW,
ETF, bond, OEF, MF, kèm `Underlying`, `ExercisePrice`, `ExerciseStyle`,
`ContractMultiplier`, `SettlMethod`, `MaturityDate`, `FirstTradingDate`/
`LastTradingDate`); sổ lệnh 10 mức + `EstMatchedPrice`; **`IntradayOhlc` nhận
`FromDate`/`ToDate`, tức lịch sử intraday 1 phút** chứ không chỉ phiên hiện tại
(`stock_intraday_bars` đang có 17 dòng); `LotSize` và bảng bước giá
(`TickPrice1-4`/`TickIncrement1-4`) thay hằng số; lô lẻ (`OL`); `ISIN`.

**Vẫn thua:** `market_cap` và P/E, P/B (FiinQuant); BCTC, ICB, corporate action
(vnstock); cổ phiếu lưu hành và freefloat — SSI chỉ có `ListedShare`.

## 2. Rào cản, theo mức độ nghiêm trọng

1. **Điều khoản (chặn kiến trúc, không chặn thử nghiệm).** Đăng ký dịch vụ ghi dữ
   liệu chỉ phục vụ giao dịch của chính khách hàng và không được cấp cho bên thứ
   ba (`guide.ssi.com.vn/ssi-products/tieng-viet/dang-ky-dich-vu`,
   `developers.ssi.com.vn/term-condition`). Đúng như `docs/research/vn-market-data-sources.md:319-323`
   đã kết luận: hợp cho pilot VN30 nội bộ, không hợp làm nền phục vụ end user.
2. **Rate limit không có số.** Guide chỉ xác nhận *có* giới hạn, tính **trên mỗi
   connection key** cho FCData, và lỗi trả về dạng `API calls quota exceeded!
   maximum admitted x per y s` / `Connection has been blocked, quota x exceeded
   by y`. Muốn nâng thì qua account executive. Với repo này đây là rủi ro thật:
   `DailyOhlc` giới hạn **30 ngày mỗi request** (spec §4.6), nên backfill 5 năm ×
   1.600 mã là ~100.000 request — không cách nào ước lượng thời gian chạy trước
   khi đo. `DailyStockPrice` không ghi giới hạn dải ngày nhưng `PageSize ≤ 100`
   và `pageIndex ≤ 10` cũng chặn ở 1.000 dòng mỗi truy vấn.
3. **Ba credential, hạn 1 năm.** `ConsumerID` + `ConsumerSecret` + `PrivateKey`
   (chữ ký RSA+SHA256), hiện *chưa có trong `.env`*. Dịch vụ hiệu lực 1 năm kể từ
   khi đăng ký, SSI báo trước 7 ngày; hết hạn thì kết nối trả `The connection is
   invalid` — nghĩa là cần một cảnh báo hết hạn ở phía mình, không có ở
   FiinQuant/vnstock.
4. **SDK gần như bỏ hoang.** `ssi-fc-data` 2.2.2 trên PyPI, upload **2024-06-05**,
   `requires_python >=3.5`, **không khai một dependency nào** (`requires_dist:
   None`) — tức cài xong vẫn thiếu thư viện lúc chạy. Repo GitHub 41 commit, 31
   star. Khuyến nghị: **gọi REST trực tiếp bằng `requests`** (chỉ cần
   `POST AccessToken` rồi Bearer token — `vnstock_provider.py` đã theo lối tự
   dựng), chỉ mượn SDK khi làm streaming.
5. **Tài liệu lệch nhau.** Spec PDF §2 khai host `https://fc-market.ssi.com.vn`,
   còn mọi URL endpoint trong cùng file đó lẫn guide web đều là
   `https://fc-data.ssi.com.vn/api/v2/Market/`. Bản spec là V2.0 với changelog
   dừng ở 05/2022 — **trước KRX**; guide web không có trang nào nói về thay đổi
   thời KRX. Phải probe bằng credential thật trước khi tin field nào cũng còn.
6. **Thiếu `market_cap_vnd`.** Nếu SSI lên làm Main của `market`, vốn hoá mất
   nguồn — `MarketSnapshot.market_cap_vnd` hiện lấy từ FiinQuant `get_overview`
   và đã trễ một phiên (`ADR-0002`). Muốn giữ thì phải tự tính từ
   `ListedShare × closeprice`, mà `ADR-0002` nói rõ vốn hoá là **do provider báo,
   không suy ra** từ `canonical_shares()`.

## 3. So với hai nguồn đang dùng

| | vnstock | FiinQuant (free) | SSI FCData |
|---|---|---|---|
| Tính chính thức | endpoint broker không công khai (VCI/KBS) | SDK có hợp đồng | **API chính thức, có spec PDF** |
| Rate limit | 20/60 rpm, đo được | 720 req/phút ở tier Basic, **công bố** | có, **không công bố số** |
| Giá | miễn phí, license cấm dùng thương mại | free tier / tier trả tiền | **miễn phí** với tài khoản SSI |
| `PriceBasis` | chỉ `adjusted_at_source` | `raw` | **`raw` + `adjusted` cùng dòng** |
| Trần/sàn/tham chiếu | không | có | có |
| Khối ngoại | một phần | có | có, đủ vol + val + net |
| Vốn hoá | — | có (trễ 1 phiên) | **không** |
| P/E, P/B | có | có | **không** |
| BCTC | **có** | không (403/rỗng) | **không** |
| Corporate action | **có** | không | **không** |
| ICB ngành | **có** | 403 | **không** |
| Realtime | không | theo tier (33–1.500 mã) | **8 channel, không giới hạn công bố** |
| Redistribution | cấm (license tác giả) | được, theo tier | **cấm** |

Đọc ngang: FCData và FiinQuant **trùng nhau gần hết** ở phần EOD. Cái FCData thêm
được là `closepriceadjusted`, `averageprice`, market breadth, và streaming. Cái nó
mất so với FiinQuant là vốn hoá và P/E, P/B.

## 4. Chỗ cắm trong repo, nếu làm

Seam đã có sẵn và không phải sửa kiến trúc:

- `apps/api/src/stocks/providers/contracts.py:33` — thêm `SSI = "ssi"` vào
  `ProviderSource`. **Lưu ý ràng buộc dữ liệu**: `metadata.source` được ghi vào
  store và `uq_provider_snapshot_identity` khoá theo nó, nên thêm một source là
  thêm một nhánh lịch sử, không phải đổi tại chỗ.
- `SOURCE_OWNERSHIP_BY_CAPABILITY` (`contracts.py:157`) — `SourceOwnership` chỉ
  cho **một** cover mỗi capability. `market` đang là `main=fiinquant,
  cover=vnstock`; muốn SSI vào làm cover thì **phải đẩy vnstock ra**, không phải
  thêm vào. Đây là quyết định của `ADR-0002` và cần một ADR mới để đổi.
- Adapter mới `providers/ssi_fcdata.py`, theo đúng khuôn `fiinquant.py`:
  `SsiProviderBase` + `ProviderCircuitBreaker` (`fiinquant.py:132` — dùng lại
  được nguyên, không phải viết lại) + một class cho mỗi protocol.
  Implement được: `MarketHistoryProvider`, `MarketDataProvider`,
  `MarketIndexHistoryProvider`, một phần `ReferenceDataProvider`.
- `apps/api/src/stocks/collector.py:284` `build_collector()` — nơi adapter được
  wire. Khuôn "thiếu credential là trạng thái cấu hình, không phải lỗi" đã có sẵn
  cho FiinQuant, áp y hệ cho SSI.
- `apps/api/src/core/config.py:45` — thêm `ssi_consumer_id`, `ssi_consumer_secret`,
  `ssi_private_key` cạnh `fiinquant_*`.
- **Không** đi qua `core/quota.py`: `VnstockQuotaArbiter` giữ hạn mức của tài khoản
  vnstock: SSI có quota riêng theo connection key nên cần bộ điều tiết riêng, hoặc
  chỉ dựa vào circuit breaker cho tới khi đo được số thật.
- `docker-compose.yml` không phải sửa: adapter chạy trong container `api` như hai
  adapter kia.

Ước lượng: adapter REST cho `market` + `market_index` ≈ quy mô `fiinquant.py`
(~900 dòng có test). Streaming là **một hạng mục khác hẳn** — repo hiện không có
consumer chạy dài nào, `SnapshotStore` khoá theo `effective_at` cấp phiên chứ
không cấp tick, nên nhận tick đòi một đường ghi mới, không phải một adapter mới.

## 5. Khuyến nghị

**Không đưa FCData vào làm Main hay Cover của `market` lúc này.** Ba lý do, theo
thứ tự: điều khoản cấm cấp cho bên thứ ba khiến nó không thể là nền lâu dài;
phần EOD trùng FiinQuant nên lợi ích ròng chỉ là `closepriceadjusted` +
`averageprice`; và đổi cover source của `market` là một ADR chứ không phải một
patch.

**Đáng làm, theo thứ tự tăng dần cam kết:**

1. **Đăng ký lấy credential và probe.** Chi phí bằng không (miễn phí, cần tài
   khoản SSI). Cần đo đúng bốn thứ mà không tài liệu nào trả lời được:
   (a) rate limit thật; (b) `DailyStockPrice` trả về lịch sử từ năm nào;
   (c) `totalbuytradevol`/`totalselltradevol` có số thật hay luôn `0`;
   (d) field nào còn sống sau KRX. Bốn con số này quyết định mọi bước sau, và
   không suy ra được từ spec 2022.
2. **Nếu probe tốt: dùng FCData làm nguồn kiểm tra chéo (cross-check), không
   phải nguồn phục vụ.** Đúng vai `docs/research/vn-market-data-sources.md` đang
   xếp cho CafeF EOD, nhưng chất lượng cao hơn nhiều: `closeprice` thô của SSI
   đối chiếu được với chuỗi `adjusted_at_source` của vnstock để **kiểm định
   Adjustment Factor tính từ Corporate Action** — hiện không có cách nào xác thực
   phép điều chỉnh lúc đọc của `ADR-0006` bằng một nguồn độc lập.
3. **Streaming chỉ khi có nhu cầu intraday rõ ràng.** `X` + `R` + `MI` là feed
   realtime tốt nhất trong các nguồn khảo sát, nhưng nó mở một đường ghi mới
   trong hệ thống và vẫn nằm dưới cùng điều khoản cấm phục vụ bên thứ ba. Không
   làm trước khi có một tính năng cần tick.

## Câu hỏi mở

- Có tài khoản SSI để đăng ký FastConnect chưa? Không có credential thì mọi con
  số ở mục 5.1 vẫn là ẩn số.
- Pilot này còn thuần nội bộ, hay đã có kế hoạch phục vụ người dùng ngoài? Câu
  trả lời quyết định điều khoản SSI là chú thích hay là chặn.
- Nợ `mixed_price_basis` ở mối nối backfill/collector (`ADR-0006`) hiện gây đau
  thật chưa? Nếu có, `closepriceadjusted` của SSI là lý do mạnh nhất để tiến xa
  hơn mức cross-check.
