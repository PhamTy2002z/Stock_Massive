# Research: vnstock sponsor tiers — cái gì mua được, cái gì không

Câu hỏi: nếu Stock_Massive trả tiền cho một gói tài trợ vnstock, gói nào là đúng
và nó mở ra chính xác những gì cho repo này?

Method: nguồn sơ cấp, fetch ngày **2026-08-24** — trang docs chính thức
`vnstocks.com/docs/*`, README của `thinh-vu/vnstock` trên GitHub, và bảng quyền
lợi cùng bảng thư viện do người dùng đọc trực tiếp từ trang tài trợ (trang này
render client-side nên WebFetch không đọc được, xem §6). Không dùng blog tổng
hợp. Mọi claim mang **verification grade**:

- **[trang]** — một trang chính thức ghi thẳng câu đó
- **[người dùng đọc]** — lấy từ bảng người dùng dán vào từ trang tài trợ
- **[suy luận]** — dẫn ra từ hai claim khác, có nêu phép dẫn
- **[không tìm được]** — đã tra và không có

Bối cảnh repo: `docs/research/vn-market-data-sources.md` (17/08) đã xếp hạng các
nguồn và khuyến nghị scale trên FiinQuant. Tài liệu này không đảo khuyến nghị
đó; nó trả lời một câu hẹp hơn — gói vnstock nào, và vì sao.

---

## TL;DR

**Bronze là gói đúng nếu mua, nhưng lý do mua yếu hơn tưởng — và không cấp bách.**

Điều chỉnh quan trọng, đo trực tiếp ngày 2026-08-24: **lịch sử giá đã đủ sâu.**
`provider_snapshots` (capability `market`) có **2.527 phiên/mã từ 2016-07 tới
2026-08**, và **28 trong 30 mã Universe có ≥970 phiên**. Signal field đọc bảng
này (`signals/sessions.py:41,108`), không đọc `stock_daily_ohlcv`. Nên nhóm
risk/performance của Portfolio Intelligence — Sharpe, Sortino, bốn field
drawdown, beta, correlation, momentum 12-2 — **không bị chặn bởi dữ liệu**, và
không cần mua gì để mở khoá. Xem §4.1.

Cái Bronze thật sự mua được, sau khi trừ phần trên:

1. **Khối ngoại theo khối lượng.** `foreign_buy_volume` và `foreign_sell_volume`
   có trong schema payload nhưng **null 2.527/2.527 phiên** — không adapter nào
   ghi. `vnstock_data` cấp cột này ở nguồn KBS và CafeF (§3), làm sống
   `FOREIGN_FLOW_SHARE_PRESSURE`.
2. **Nửa lịch sử khối ngoại theo tiền đang thiếu.** `foreign_net_value_vnd` chỉ
   có ở **1.258/2.527 phiên**.
3. **Dòng tiền tự doanh** (`proprietary_flow()`) và **giao dịch nội bộ**
   (`insider_deal()`) — dữ liệu repo hoàn toàn chưa có.
4. **Hạn mức cao hơn** cho phần lịch sử sâu hơn 5 năm và cho `sector_historical`
   đang tắt.

Ba thư viện còn lại — `vnstock_ta`, `vnstock_news`, `vnstock_pipeline` — repo
không dùng được hoặc đã có thứ tương đương. Nên Silver, Golden, Diamond mua thêm
thiết bị và tiện ích, không mua thêm dữ liệu cho sản phẩm này.

**Không gói nào giải quyết giấy phép thương mại.** Đó là một cuộc thương lượng
riêng và nó độc lập với tier.

**Khuyến nghị:** đây là mua để **lấp trục money flow**, không phải mua để mở khoá
portfolio analytics. Nó không chặn Phase 0–2. Có thể hoãn tới khi trục money flow
vào scope, và dùng khoảng đó để hỏi xong câu license ở §6.

---

## 1. Năm tier và cái phân biệt chúng

**[người dùng đọc]** — bảng quyền lợi trên trang tài trợ:

| Hạng mục | Diamond | Golden | Silver | Bronze | Community |
|---|---|---|---|---|---|
| Số thiết bị truy cập | 13 | 6 | 6 | 3 | 1 |
| Lượt đổi thiết bị/ngày | 20 | 8 | 5 | 3 | 3 |
| 5X tốc độ tải dữ liệu | có | có | — | — | — |
| Dữ liệu thời gian thực | Real-time | Real-time | trễ 1–3s | trễ 1–3s | trễ 1–3s |
| Số lượng hàm chức năng | Đầy đủ | Đầy đủ | Đầy đủ | Đầy đủ | Tối giản |
| Báo cáo tài chính | Tối đa của nguồn | Tối đa của nguồn | Tối đa của nguồn | Tối đa của nguồn | 8 kỳ |
| Thông tin thị trường | Đầy đủ | Đầy đủ | Đầy đủ | Đầy đủ | Cơ bản |
| Chỉ số vĩ mô · hàng hoá · Insights | có | có | có | có | — |
| Bộ thư viện | 4 gói | 4 gói | 3 gói | **1 gói `vnstock_data`** | vnstock open source |
| Hỗ trợ | 2h + remote | 2h + remote | 4h | 6h | cộng đồng |

Hai dòng đáng chú ý vì chúng bác một giả định dễ mắc:

- **Bronze và Silver giống nhau ở toàn bộ phần dữ liệu.** Cùng "Đầy đủ" cho hàm,
  báo cáo tài chính, thông tin thị trường, vĩ mô, hàng hoá, Insights. Cùng độ
  trễ 1–3s. Khác biệt nằm ở thiết bị, thư viện và thời gian hỗ trợ.
- **`5X tốc độ tải` chỉ có ở Golden và Diamond.** Đây là thứ duy nhất trong bảng
  thực sự tăng throughput, và cả Bronze lẫn Silver đều không có.

---

## 2. Bốn thư viện, và cái repo này dùng được

**[người dùng đọc]** — mô tả trên trang tài trợ, cộng **[trang]** cho phần docs.

### `vnstock_data` — Bronze đã có

Bốn dòng quyền lợi được nêu: dữ liệu intraday chi tiết từng phút · **tăng giới
hạn API từ 3–10 lần** · **giao dịch khối ngoại & dòng tiền** · báo cáo tài chính
& định giá.

Kiến trúc ba lớp (Unified UI → Core Adapter → Implementation) với sáu module:
Reference · Market · Fundamental · Analytics · Macro · Insights. Nguồn được hỗ
trợ: **VCI, KBS, MAS, MSN, FMARKET, VND, MBK, SPL**
([kiến trúc thư viện](https://vnstocks.com/docs/vnstock-data/kien-truc-thu-vien)).
Repo hiện chỉ dùng VCI và KBS qua vnstock, cộng FiinQuant riêng.

### `vnstock_ta` — Silver trở lên

60+ chỉ báo kỹ thuật, công thức đối chiếu TradingView, bốn nhóm chỉ báo, hỗ trợ
Agent Skill vẽ biểu đồ.

**Repo không cần.** Đã có ba field `RSI`, `MACD`, `BOLLINGER_PERCENT_B`, và
`docs/research/quant-methods-eod-vn.md` kết luận từ Sullivan-Timmermann-White
(1999) rằng sau hiệu chỉnh data-snooping thì *"there is scant evidence that
technical trading rules were of any economic value"* ngoài mẫu. Ba field đó tồn
tại như **từ vựng mô tả** với câu disclaimer trong contract, không như tín hiệu.
Thêm 57 chỉ báo nữa làm dài catalog mà không thêm tín hiệu nào.

### `vnstock_news` — Silver trở lên

21 trang báo, trích xuất Markdown, RSS + Sitemap, mở rộng được nguồn.

Đây là thư viện tốt và nó làm đúng việc mà `src/stocks/providers/cafef_rss.py`
và `cafef_article.py` đang tự làm. Nhưng trục news nằm trong **non-goals của
Portfolio Intelligence v1**. Đây là lý do nâng lên Silver *về sau*, không phải
bây giờ.

### `vnstock_pipeline` — Golden trở lên

Thu thập theo lịch, xử lý song song, "nhanh gấp 5-8 lần", xuất CSV/Parquet/DuckDB.

**Repo không nên nhập.** Đã có `src/core/scheduler.py` và
`src/stocks/collector_schedule.py` với job đặt tên, cộng một quota arbiter dùng
chung ở `src/core/quota.py` mà `docs/adr/0014` quy định allowance thuộc về
account chứ không thuộc adapter. `src/stocks/providers/vnstock_provider.py:13-16`
ghi lại chính xác lỗi đã phải dọn: *"Neither adapter paces itself. The allowance
belongs to the account... an adapter with a pacer of its own was one of the three
copies that together added up to more than the account had."* Nhập một
orchestrator có pacer riêng vào đó là dựng lại copy thứ tư.

---

## 3. Hàm và cột thật của `vnstock_data`

**[trang]** — [Market layer v3](https://vnstocks.com/docs/vnstock-data/market-layer-v3):

| Nhóm | Hàm |
|---|---|
| Chuỗi thời gian | `ohlcv()` · `trade_history()` · `foreign_flow()` · `proprietary_flow()` |
| Intraday chi tiết | `trades()` · `block_trades()` · `odd_lot()` |
| Snapshot | `quote()` · `order_book()` · `session_stats()` · `volume_profile()` · `summary()` |

`foreign_flow()` nhận `start`, `end`, `interval` như `ohlcv()`, và trả *"lịch sử
thống kê khối lượng và giá trị mua/bán ròng của nhà đầu tư nước ngoài"*.

**Tên cột theo nguồn** **[trang]** —
[thống kê giao dịch](https://vnstocks.com/docs/vnstock-data/du-lieu-giao-dich):

| Nguồn | Cột khối ngoại | Đơn vị |
|---|---|---|
| VCI | `fr_buy_value_matched`, `fr_sell_value_matched`, `fr_net_value_total`, `fr_total_room`, `fr_current_room` | **tiền** (VND) |
| KBS | `foreign_buy_volume`, `foreign_sell_volume` (trong `price_board`) | **khối lượng** (cổ phiếu) |
| CafeF | `fr_buy_volume`, `fr_sell_volume`, `fr_net_volume`, `fr_ownership` | **khối lượng** + % sở hữu |

Đây là câu trả lời cho câu hỏi quyết định: **có cột khối lượng, ở KBS và CafeF.**

Hai lưu ý từ chính docs: khung phút (`1m`, `5m`, `15m`, `1H`) *"chỉ khả dụng với
tài khoản Premium/Pro tuỳ nguồn"* — đó là gate của **nguồn dữ liệu**, không phải
của tier vnstock; và lịch sử CafeF sâu nhưng *"đôi khi bị khuyết ngày"*.

---

## 4. Chiếu vào repo: Bronze mở được gì

### 4.1 Lịch sử giá KHÔNG bị chặn — hiệu chỉnh một kết luận sai

Bản đầu của tài liệu này, và hai report brainstorm/UI trước nó, kết luận rằng độ
sâu lịch sử chặn toàn bộ nhóm risk. **Kết luận đó sai, vì đo sai bảng.**

`stock_daily_ohlcv` là bảng của collector cũ: 119.525 dòng, 1.710 mã, tối đa 80
phiên/mã, chuỗi có lỗ hổng. Nhưng **Signal field không đọc bảng đó.**
`src/stocks/signals/sessions.py:41,108` đọc `ProviderSnapshot`.

Đo trên `provider_snapshots`, capability `market`, ngày 2026-08-24:

```
FPT · HPG · VCB · VNM : 2.521 phiên, 2016-07-20 → 2026-08-20
trung bình toàn bộ     : 2.109 phiên/mã   (min 7 · max 2.521)
FPT chi tiết           : 2.527 dòng, last_price 2.527/2.527, volume 2.527/2.527
```

Phân bố trên đúng 30 mã Universe:

| Độ sâu | Số mã | Mã |
|---|---|---|
| **≥970 phiên** (ngưỡng để CI của Sharpe không chứa 0) | **28** | ACB, BID, BSR, CTG, FPT, GAS, GVR, HDB, HPG, LPB, MBB, MCH, MSN, MWG, SAB, SHB, SSB, SSI, STB, TCB, VCB, VHM, VIB, VIC, VJC, VNM, VPB, VRE |
| 1–59 phiên | 2 | TCX, VPL (mã mới) |

Điều này nhất quán với thiết kế đã ghi trong config: `backfill_main_source_days
= 5 * 365` với comment *"đo thực tế: FiinQuant free trả ~5 năm nến ngày"*, và
`backfill_depth_days = 10 * 365`. `src/stocks/backfill.py:1-6` nói rõ vnstock là
**Cover Source**, chỉ dùng cho phần **sâu hơn 5 năm**: *"The Main Source is
granted about five years of daily history. Anything deeper than that is loaded
once, from vnstock."*

**Hệ quả cho quyết định mua:** nhóm risk/performance của portfolio đã có đủ mẫu
trên 28/30 mã. Nâng gói vnstock **không** mở khoá nhóm đó, vì nhóm đó không bị
khoá. Sàn 250 phiên và ngưỡng ~970 phiên đều đã vượt.

### 4.1b Hai job đang tắt, và cái quota thật sự chặn

`src/core/config.py` — flag thật (lưu ý: `DAILY_OHLCV_ENABLED` mà
`data-coverage-audit.md` nêu **không còn tồn tại**; hệ thống job đã được viết lại):

- `backfill_enabled = False` (`config.py:121`) — comment: *"đây là thứ tiêu hạn
  mức vnstock nhiều nhất trong hệ thống, nên bật là một quyết định của người vận
  hành"*
- `sector_historical_enabled = False` (`config.py:348`) — *"disabled until a
  persisted cache exists; otherwise every restart after 15:45 retries a broad
  vnstock scan and starves interactive requests"*
- `backfill_symbols_per_run = 5` — *"trần số mã mỗi lần chạy để không tiêu hết
  hạn mức mà chu kỳ hằng ngày cũng đang dùng"*

Sáu job hiện chạy (`collector_schedule.py:53-69`): `universe-snapshots` (bật,
16:15) · `universe-backfill` (tắt) · `universe-warmup` · `profit-census` ·
`corporate-actions` (bật) · `market-index` (bật, cửa sổ 275 phiên).

`backfill_symbols_per_run = 5` là chỗ quota thật sự cắn: 30 mã cần 6 ngày, và mỗi
mã chỉ nạp phần **sâu hơn 5 năm** từ vnstock. Ở hạn mức cao hơn, trần này nâng
được. Nhưng vì phần 5 năm gần nhất đã do FiinQuant cấp và đã đủ cho mọi sàn mẫu,
đây là cải thiện độ sâu **năm thứ 5 → 10**, không phải điều kiện để có số.

**[suy luận]** — "tăng 3–10 lần" áp lên mức Community 60 req/phút cho 180–600
req/phút, khớp dải Sponsor/Insider mà README công bố. Ở mức thấp nhất (180), một
lượt quét fundamental full-market 1.710 mã × 2 request xuống từ ~57 phút còn ~19
phút — đủ để chạy hằng đêm mà không cạnh tranh với request tương tác.

### 4.2 Trục money flow — đây mới là lý do mua, và nó đo được

`src/stocks/signals/registry.py:1030` — `FOREIGN_FLOW_SHARE_PRESSURE`
(`foreign_flow_pressure.net_volume_over_adtv`) tự khai lý do refuse: *"the Main
Source reports foreign buy and sell as money and no adapter in this system writes
the share counts, so the ratio has no inputs."*

**Xác nhận bằng dữ liệu**, không chỉ bằng comment. Đếm trên 2.527 phiên của FPT
trong `provider_snapshots`:

| Field trong payload | Có giá trị | Ghi chú |
|---|---|---|
| `last_price` | **2.527 / 2.527** | đầy đủ |
| `volume` | **2.527 / 2.527** | đầy đủ |
| `foreign_net_value_vnd` | **1.258 / 2.527** | thiếu ~một nửa lịch sử |
| `foreign_buy_volume` | **0 / 2.527** | key có trong payload, **luôn null** |
| `foreign_sell_volume` | **0 / 2.527** | như trên |
| `market_cap_vnd` | **5 / 2.527** | khớp ghi chú `stale_market_cap` trong CLAUDE.md |

Hai dòng cuối cùng là bằng chứng trực tiếp cho refusal ở `registry.py:1030`:
FiinQuant chỉ ghi `fb`/`fs`/`fn` là **tiền** (`fiinquant.py:825-827`), và
`providers/contracts.py:352-353` đã khai sẵn `foreign_buy_volume` /
`foreign_sell_volume` mà không adapter nào ghi vào.

`vnstock_data` cấp cột khối lượng ở nguồn **KBS** (`foreign_buy_volume`,
`foreign_sell_volume`) và **CafeF** (`fr_buy_volume`, `fr_sell_volume`,
`fr_net_volume`, `fr_ownership`) — xem §3. Đó là input còn thiếu.

Ba thứ đo được mà Bronze lấp: một field chết sống lại, nửa lịch sử
`foreign_net_value_vnd` còn thiếu, và `fr_ownership` (% sở hữu ngoại) mà repo
chưa có ở dạng chuỗi.

Đây **không** phải cải thiện portfolio analytics. Đây là lấp trục money flow —
trục mà `data-coverage-audit.md` xếp là *"biggest gap"*.

### 4.3 Dữ liệu repo hoàn toàn chưa có

- `proprietary_flow()` / `prop_trade()` — **dòng tiền tự doanh**. Không tồn tại ở
  bất kỳ đâu trong repo. `docs/research/data-coverage-audit.md` xếp trục money
  flow là *"biggest gap"* và nêu rõ *"no proprietary-trading data"*.
- `insider_deal()` — giao dịch nội bộ. Cũng chưa có.
- Macro (Commodity, Currency, Economy) — hữu ích cho trục market/regime về sau,
  ngoài scope Portfolio Intelligence v1.
- Báo cáo tài chính *"tối đa của nguồn"* thay vì 8 kỳ. Lưu ý: repo hiện lấy
  valuation từ **FiinQuant**, nên giá trị này chỉ hiện thực nếu chuyển hướng
  fundamental về vnstock.

### 4.4 Cái Bronze KHÔNG giải quyết

**Không giải quyết độ sâu lịch sử giá, vì độ sâu đó đã đủ.** Sàn 250 phiên cho
Sharpe/Sortino/drawdown (`signals/risk.py:151,154`), 250 cho beta
(`cross_sectional.py:153`), 252 cho momentum 12-2 — cả ba đã vượt trên 28/30 mã
Universe (§4.1). Đây là điểm quan trọng nhất phải đọc trước khi trả tiền: nếu
mục tiêu là "mở khoá panel rủi ro của portfolio", **không cần mua gì**.

**Không giải quyết `market_cap_vnd`.** Chỉ 5/2.527 phiên có giá trị, và đó là
nguyên nhân của `stale_market_cap` cùng cửa sổ 21 phiên của bốn factor
percentile. vnstock cấp share count qua capability `reference`
(`vnstock_provider.py:389-390`), nhưng liệu `vnstock_data` cấp **chuỗi lịch sử**
market cap thì **[không tìm được]** — cần hỏi. Nếu có, đây sẽ là dòng đáng tiền
thứ hai.

**Không giải quyết giấy phép thương mại** (§5).

**Không giải quyết Phase 0–2 của Portfolio Intelligence.** Ledger giao dịch, số
học arithmetic, PortfolioField và UI đều không phụ thuộc gói này.

---

## 5. Giấy phép — điểm chặn lớn nhất, và không tier nào chạm tới

**[trang]** — README `thinh-vu/vnstock`: giấy phép tuỳ chỉnh *"hướng đến cá nhân,
không dành cho mục đích thương mại"*, và *"nếu bạn cần dùng cho dự án phát sinh
doanh thu, vui lòng liên hệ tác giả để được cấp phép chính thức"*. Toàn văn ở
`vnstocks.com/onboard/giay-phep-su-dung`.

Bảng quyền lợi ở §1 **không có dòng nào** về quyền dùng thương mại hay phân
phối. Năm tier bán **quota, thiết bị và thư viện** — không bán **quyền**.

Portfolio Intelligence là nguồn ARR chính. Nên dù chọn tier nào, vẫn cần một
license riêng. Trả tiền tier mà không có license đó nghĩa là hạ tầng dữ liệu của
sản phẩm doanh thu đứng trên một giấy phép cá nhân.

`vn-market-data-sources.md` đã nêu cùng kết luận và khuyến nghị FiinQuant vì đó
là **dữ liệu có license**, rate limit công bố, và adapter đã tồn tại trong repo.

---

## 6. Cái không xác nhận được — đọc phần này trước khi chuyển tiền

| # | Câu chưa có đáp án | Vì sao nó quyết định |
|---|---|---|
| 1 | **Rate limit req/phút riêng của Bronze.** Docs và README chỉ cho dải 180–600 cho cả nhóm Sponsor/Insider; mô tả `vnstock_data` chỉ nói "3–10 lần". Không trang nào tách theo tier. **[không tìm được]** | Nếu Bronze là 3× (180) thì kết luận không đổi. Nhưng con số nên được xác nhận, không suy luận. |
| 2 | **Thiết bị tính theo gì.** Bronze có 3 thiết bị và 3 lượt đổi/ngày. **[không tìm được]** | Repo mount `src/` nên `docker compose restart api` là thao tác thường ngày, cộng nhiều worktree song song với `API_PORT` khác nhau. Nếu device tính theo container instance thì Bronze cạn trước trưa. Nếu tính theo machine fingerprint thì không sao. **Đây là câu quyết định Bronze có dùng được không.** |
| 3 | **Giá VND từng tier.** Trang `/insiders-program` render client-side; WebFetch trả về trang điều hướng, không có bảng giá. **[không tìm được]** | Không so được giá trị/giá tiền giữa Bronze và Silver. |
| 4 | **"Thông tin thị trường: Cơ bản" thiếu gì so với "Đầy đủ".** **[không tìm được]** | Đây có thể là nơi khối ngoại và room ngoại nằm — tức là chính thứ ta muốn mua. |
| 5 | **Giá và điều kiện license thương mại.** **[không tìm được]** | Quyết định cả năm tier có dùng được cho sản phẩm có doanh thu hay không. |
| 6 | **`foreign_flow()` trả cột nào ở mỗi nguồn, chính xác.** Docs trỏ tới `schema/02-market.md` mà trang không kèm nội dung. **[không tìm được]** | Cần biết chắc KBS/CafeF cấp volume ở *chuỗi lịch sử*, không chỉ ở `price_board` snapshot — vì `FOREIGN_FLOW_SHARE_PRESSURE` cần chuỗi. |

Năm câu 1, 2, 4, 5, 6 nên hỏi `support@vnstocks.com` trước khi trả tiền. Câu 2 và
câu 5 là hai câu có thể làm quyết định đảo chiều.

---

## 7. Khuyến nghị

1. **Không cần mua để làm Portfolio Intelligence.** Lịch sử giá đã đủ trên 28/30
   mã (§4.1). Phase 0 trong report brainstorm — "backfill lịch sử ≥250 phiên" —
   **đã xong rồi**, chỉ là nó xong ở `provider_snapshots` chứ không ở bảng mà
   audit cũ trỏ tới.
2. **Nếu mua, mua vì trục money flow.** Ba thứ đo được ở §4.2: một field chết
   sống lại, nửa lịch sử `foreign_net_value_vnd` còn thiếu, và `fr_ownership`.
   Cộng `proprietary_flow()` và `insider_deal()` là dữ liệu mới hoàn toàn. Đó là
   trục mà `data-coverage-audit.md` xếp là gap lớn nhất.
3. **Hỏi support câu 2 và câu 5 ở §6 trước khi chuyển tiền.** Nếu device chết
   theo mỗi lần restart container, Bronze không dùng được và phải nhắm Golden (8
   lượt/ngày) — lúc đó phép tính giá/giá trị đổi hoàn toàn. Nếu không có đường
   license thương mại, dừng lại và dồn tiền vào FiinQuant tier. Vì mục 1 đã bỏ
   tính cấp bách, có thời gian để hỏi cho xong.
4. **Nếu mua thì Bronze, không Silver.** `vnstock_data` là thư viện duy nhất
   trong bốn thư viện mà repo dùng được ngay. `vnstock_ta` không dùng được;
   `vnstock_news` chưa tới lượt.
5. **Việc làm sau khi có key:** viết adapter ghi `foreign_buy_volume` /
   `foreign_sell_volume` (schema đã có ở `contracts.py:352-353`), rồi kiểm
   `FOREIGN_FLOW_SHARE_PRESSURE` có trả số. Sau đó cân nhắc `proprietary_flow()`.
6. **Không nhập `vnstock_pipeline`** ngay cả khi lên Golden. Repo đã có scheduler
   và một quota arbiter dùng chung; thêm pacer thứ hai là lỗi đã từng phải dọn
   (`vnstock_provider.py:13-16`).
7. **FiinQuant vẫn là đường dài** — và đo hôm nay cho thấy nó đang làm tốt hơn
   vnstock: `provider_snapshots` cập nhật tới 2026-08-20, `stock_daily_ohlcv` chỉ
   tới 2026-08-07. Bronze không giải quyết quyền phục vụ dữ liệu cho người dùng
   trả tiền.

## Hiệu chỉnh so với các tài liệu trước

| Tài liệu | Claim sai | Đúng là |
|---|---|---|
| `plans/reports/brainstorm-260823-2212-portfolio-intelligence.md` §1.3, §1.4 | "store có tối đa 80 phiên, toàn bộ nhóm risk refuse `insufficient_history`" | Đo `stock_daily_ohlcv` — bảng legacy. Signal field đọc `provider_snapshots`: 2.527 phiên/mã, 28/30 mã ≥970 phiên |
| `plans/reports/ui-260823-2238-portfolio-intelligence-features.md` §2.5, §10 | "panel rủi ro chỉ hiện được khối giải thích, không hiện số" | Panel rủi ro có số thật cho 28/30 mã. TCX và VPL sẽ refuse — và đó là hành vi đúng, không phải trạng thái chung |
| `docs/research/data-coverage-audit.md` | `DAILY_OHLCV_ENABLED` | Flag không còn tồn tại; hệ thống job đã viết lại thành 6 job ở `collector_schedule.py:53-69` |

## Câu hỏi chưa giải quyết

- Nguồn nào (KBS hay CafeF) cấp khối ngoại theo khối lượng ở dạng **chuỗi lịch
  sử** đủ sâu, và chuỗi đó có khớp ngày với `stock_daily_ohlcv` không?
- Có nên chuyển fundamental từ FiinQuant về vnstock để dùng "tối đa của nguồn",
  hay giữ FiinQuant vì lý do license?
- Lịch sử CafeF "đôi khi bị khuyết ngày" — mức khuyết đó có vượt ngưỡng
  `DEGRADED_LIMIT_LOCK_SHARE` và các sàn mẫu hiện có không?
