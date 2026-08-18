# Research: Vietnamese market data sources beyond vnstock

Question: which HOSE/HNX/UPCOM data sources can Stock_Massive use and scale with, as
replacements or supplements for vnstock (currently capped at 20 req/min guest /
60 req/min registered)?

Method: primary sources only — official docs sites, vendor pricing pages, exchange
websites and the installed `vnstock` package source were fetched on **2026-08-17**.
Blog posts were used only as pointers. Every claim carries an inline link to the
source that owns it. Where a number is not on a primary page it is marked
**not publicly documented**.

Context in this repo: `apps/api/src/stocks/providers/contracts.py` already defines a
two-source `ProviderSource` enum (`fiinquant`, `vnstock`), and
`apps/api/src/stocks/providers/fiinquant.py` notes the FiinQuant free tier's
33-symbol realtime ceiling and a measured 110-symbol historical batch. Prior research
on news endpoints lives in `docs/research/news-sources.md`.

## TL;DR — ranked for Stock_Massive

| # | Source | Type | Rate ceiling (documented) | Streaming | Auth | Commercial-use posture |
|---|---|---|---|---|---|---|
| 1 | **FiinQuant** (FiinGroup) | licensed vendor SDK | 90–7,500 req/min by tier; 100k–2.4M req/month | yes, 33–1,500 realtime symbols by tier | account + paid tier | licensed data vendor — cleanest |
| 2 | **SSI FastConnect (FCData)** | broker API, official docs | rate-limited per connection key, numbers not public, negotiable | yes, 8 channel types | SSI brokerage account, free | ToS: customer's own trading only, no third-party provision |
| 3 | **DNSE LightSpeed** | broker API, official docs | "per DNSE policy", not public | yes, MQTT over WSS, public topics without auth | DNSE brokerage account | ToS: own trading only, no redistribution without written approval |
| 4 | **Vietstock DataFeed** | licensed vendor feed | contract | "historical & updated data" via API/Sync | sales contract | licensed, targets brokerages |
| 5 | **HNX direct info service** | exchange | contract | realtime Message/XML, leased line/Internet | information-usage contract | fully licensed, incl. redistribution |
| 6 | **vnstock** (status quo) | open-source wrapper of unofficial endpoints | 20 guest / 60 community / 180–600 sponsor req/min | no | optional registration | custom personal-use license — **not for commercial use** |
| 7 | Direct unofficial endpoints (VCI, TCBS, VNDIRECT, CafeF) | scraping | none stated; can be blocked anytime | no | none | no contract, ToS/fragility risk |

---

## 1. Official / exchange sources

### HOSE (hsx.vn)

No self-serve data API exists. HOSE distributes market data through information-usage
contracts; per press coverage of the new hsx.vn site, customers "can receive
information directly from the exchange or through … global information distributors
like Refinitiv, Bloomberg, and Yonhap"
([thoibaotaichinhvietnam.vn](https://thoibaotaichinhvietnam.vn/hose-ra-mat-giao-dien-website-moi-de-su-dung-nhieu-tinh-nang-noi-bat-175626.html)).
HOSE has also unilaterally cut data classes before — proprietary-trading data was
discontinued for downstream vendors from 2022-03-01
([tuoitre.vn](https://tuoitre.vn/tu-1-3-hose-ngung-cung-cap-du-lieu-giao-dich-tu-doanh-cua-cong-ty-chung-khoan-2022021117525973.htm)).
Fees and contract terms: **not publicly documented** — sales contact required. The
hsx.vn site itself is a JS app whose data-services section was not reachable by
plain fetch at research time.

### HNX (hnx.vn)

HNX runs an explicit information-provision service ("dịch vụ cung cấp thông tin"):
realtime trading data for the listed, UPCOM, government-bond, derivatives and
corporate-bond markets, delivered as **Message/XML over leased line or Internet**,
under contract —
[hnx.vn/vi-vn/dich-vu-cctt/huong-dan-yeu-cau-ky-thuat-sgtc.html](https://hnx.vn/vi-vn/dich-vu-cctt/huong-dan-yeu-cau-ky-thuat-sgtc.html).
(Note: at fetch time the hnx.vn TLS chain failed verification — "unable to verify
the first certificate" — the summary above comes from the indexed page content.)
Fees: **not publicly documented**.

### VSDC (vsd.vn)

The depository (Tổng công ty Lưu ký và Bù trừ chứng khoán) provides
depository/clearing services — deposit, withdrawal, transfer, blocking of securities
([vsd.vn](https://vsd.vn/vi/sd/rft7xrkuPfGyGNk-dm6arA)) — it is not a market-data
feed and is not a candidate here.

**Assessment**: the exchanges are the only path to a fully licensed feed with
redistribution rights, but it is a bespoke leased-line/contract sale with no public
pricing — realistic only when Stock_Massive serves paying customers at scale.

## 2. Broker APIs

### SSI FastConnect — official, documented, free with an SSI account

Two products, **FCData** (market data) and **FCTrading**, with official docs at
[guide.ssi.com.vn](https://guide.ssi.com.vn/ssi-products) and official sample
clients in Python/Node/Java/.NET
([python-fcdata](https://github.com/SSI-Securities-Corporation/python-fcdata),
streaming URL `https://fc-data.ssi.com.vn/`).

- **REST endpoints** (base `https://fc-data.ssi.com.vn/api/v2/Market/`, AccessToken
  via ConsumerID/ConsumerSecret): `Securities`, `SecuritiesDetails`,
  `IndexComponents`, `IndexList`, `DailyOhlc`, `IntradayOhlc` (default 1-minute
  resolution), `DailyIndex`, `DailyStockPrice` (includes foreign activity), covering
  HOSE, HNX, UPCOM and derivatives. Pagination is capped: `pageIndex` 1–10,
  `pageSize` up to 1000 —
  [API specs](https://guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs).
- **Streaming**: 8 channel types — `F` (security status), `X-QUOTE` (best bid/ask,
  3 levels HOSE / 10 levels HNX–UPCOM–derivatives), `X-TRADE` (matched price/vol),
  `X` (snapshot), `B` (OHLCV by tick), `R` (foreign room), `MI` (realtime indices),
  `OL` (odd lot); subscribe as `X-QUOTE:ACB-VND` or `F:ALL` —
  [streaming data](https://guide.ssi.com.vn/ssi-products/fastconnect-data/streaming-data).
- **Rate limits**: exist per API and are counted **per connection key** for FCData;
  the numeric values are **not publicly documented**; increases go through an SSI
  account executive; SSI explicitly recommends streaming over polling —
  [general information](https://guide.ssi.com.vn/ssi-products/general-information).
- **Access & price**: requires an SSI brokerage account; the service is **free**
  ("Dịch vụ FastConnect API được cung cấp miễn phí") and valid **1 year** per
  registration, renewable —
  [đăng ký dịch vụ](https://guide.ssi.com.vn/ssi-products/tieng-viet/dang-ky-dich-vu).
- **Licensing risk**: the registration terms state the API data serves only the
  customer's own securities trading and must not be provided to any third party
  ([đăng ký dịch vụ](https://guide.ssi.com.vn/ssi-products/tieng-viet/dang-ky-dich-vu),
  [developer ToS](https://developers.ssi.com.vn/term-condition)) — serving this data
  to Stock_Massive end users would breach the terms.
- **Reputation**: the de-facto standard broker API in VN algo circles; stable enough
  that vnstock's docs ship an SSI integration guide
  ([docs.vnstock.site](https://docs.vnstock.site/integrate/ssi_fast_connect_api/)).

### DNSE LightSpeed / Entrade X — official docs, MQTT websocket feed

Official handbook at [hdsd.dnse.com.vn](https://hdsd.dnse.com.vn/san-pham-dich-vu/dnse-lightspeed-api)
(Trading REST API + Market Data), aimed at individual investors, fintechs and
institutions. The KRX-era docs live under `lightspeed-api_krx`; several deep URLs
404'd during research (the doc tree is being reorganized — pre-KRX pages remain at
`lightspeed-api-truoc-krx`, and a V2 exists:
[DNSE LightSpeed API V2](https://hdsd.dnse.com.vn/san-pham-dich-vu/dnse-lightspeed-api/dnse-lightspeed-api-v2)).

- **Market data transport**: MQTT over WebSocket Secure. Pre-KRX host
  `wss://datafeed-lts.dnse.com.vn:443/wss`; the KRX feed host is
  `datafeed-lts-krx.dnse.com.vn`, port 443, path `/wss`, ClientID
  `<dnse-price-json-mqtt-ws-sub>-<username>-<random_sequence>`
  ([môi trường](https://hdsd.dnse.com.vn/san-pham-dich-vu/lightspeed-api-truoc-krx/iii.-market-data/2.-dac-ta-thong-tin-cac-message/2.1.-moi-truong.md),
  KRX host per the KRX environment page indexed from
  [hdsd2.entrade.com.vn](https://hdsd2.entrade.com.vn/api-lightspeed/iii.-market-data/2.-dac-ta-thong-tin-cac-message/2.1.-moi-truong)).
- **Topics** (JSON messages): `plaintext/quotes/stock/SI/{symbol}` (stock info),
  `.../stock/TP/{symbol}` (bid/offer), `.../stock/tick/{symbol}` (matches),
  `plaintext/quotes/index/MI/{marketID}`, `plaintext/quotes/{type}/OHLC/{resolution}/{symbol}`,
  `plaintext/quotes/session/{exchangeCode}` —
  [topics](https://hdsd.dnse.com.vn/san-pham-dich-vu/lightspeed-api-truoc-krx/iii.-market-data/2.-dac-ta-thong-tin-cac-message/2.2.-topics.md).
- **Auth**: public topics need no auth; otherwise JWT (valid 8h) from
  `services.entrade.com.vn/dnse-user-service/api/auth`, MQTT username =
  `investorId`, password = JWT
  ([môi trường](https://hdsd.dnse.com.vn/san-pham-dich-vu/lightspeed-api-truoc-krx/iii.-market-data/2.-dac-ta-thong-tin-cac-message/2.1.-moi-truong.md)).
- **Access**: requires a DNSE trading account; individuals register online via
  Entrade X, institutions on paper
  ([hướng dẫn đăng ký](https://hdsd.dnse.com.vn/san-pham-dich-vu/lightspeed-api/i.-huong-dan-dang-ky)).
  Fees: **not publicly documented**.
- **Rate/connection limits**: "API call rate limits per DNSE requirements" — numbers
  **not publicly documented**
  ([product terms](https://hdsd.dnse.com.vn/die-u-khoa-n-di-ch-vu-dnse/dieu-khoan-san-pham-dich-vu/dieu-khoan-san-pham-lightspeed-api)).
- **Licensing risk**: product terms restrict data to "the customer's own securities
  trading purposes … must not … provide to third parties without written notice and
  DNSE approval"; redistribution requires regulatory licensing on the customer's side
  ([product terms](https://hdsd.dnse.com.vn/die-u-khoa-n-di-ch-vu-dnse/dieu-khoan-san-pham-dich-vu/dieu-khoan-san-pham-lightspeed-api)).

### TCBS

No official public API documentation was found. The widely used
`apipubaws.tcbs.com.vn` endpoints (bars, stock insight, financials) are **unofficial**
— they power community libraries (vnstock 3.x had a TCBS explorer; vnstock's own
blog lists TCBS as one of its sources,
[vnstocks.com](https://vnstocks.com/blog/api-rate-limit-la-gi-cach-xu-ly-trong-vnstock)),
but TCBS publishes no docs, no rate limits and no ToS for them. Same fragility class
as any scraped endpoint.

### VNDIRECT

`dchart-api.vndirect.com.vn` (TradingView-style OHLC history) and
`finfo-api.vndirect.com.vn` (`/v4/stock_prices`, `/stocks`, `/industries`) are
**undocumented publicly**; usage knowledge circulates via community code (e.g.
[vnquant issue #6](https://github.com/phamdinhkhanh/vnquant/issues/6)). VNDIRECT's
official API offering is an institutional "APIs – White Labeling" service, by
contract ([vndirect.com.vn](https://www.vndirect.com.vn/en/institutional-customer/international-markets/apis-white-labeling-2/)).
Rate limits: **not publicly documented**.

### BSC, VPS

BSC advertises an OpenAPI program (OAuth2, data + order execution, integrated with
Fireant/vStock/DATX) but the introduction page
(`bsc.com.vn/NewProducts/OpenApiIntroduction`) returned 404 at research time and no
self-serve docs were found. No public API for VPS was found at all. Neither is a
candidate today.

## 3. Commercial data vendors

### FiinGroup — FiinQuant (already a provider in this repo) and FiinPro-X

FiinQuant is a Python data SDK with historical + realtime (order-matching) data and
indicator tooling ([docs.fiinquant.vn](https://docs.fiinquant.vn/fiinquant-en));
FiinGroup markets it as "real-time … directly connected to the KRX trading system"
([fiingroup.vn](https://fiingroup.vn/en/news-fg/FiinQuant-%E2%80%93-Real-Time--High-Speed--and-Reliable-Trading-Data-for-Vietnam-s-Stock-Market-id2466736.html)).
Published tiers ([fiinquant.vn/Pricing](https://fiinquant.vn/Pricing); VND prices
render client-side and were not captured — **contact/checkout page for amounts**):

| Tier | Realtime symbols | History | Req/month | Req/min | Req/s | Connections |
|---|---|---|---|---|---|---|
| Free (Trải nghiệm) | 33 | 1 year | 100,000 | 90 | 80 | 1 |
| Basic | 50 | 3 years | 200,000 | 720 | 80 | 4 |
| Advanced | 100 | 6 months–5 years | 300,000 | 1,100 | 100 | 6 |
| Professional | 200 | 1–10 years | 400,000 | 1,500 | 120 | 6 |
| Enterprise | 1,500 | 3–15 years | 2,400,000 | 7,500 | 300 | 40 |

Repo experience (`apps/api/src/stocks/providers/fiinquant.py`): the 33-symbol cap is
realtime-only; historical calls succeeded at 110 symbols per request. Prior research
(`docs/research/news-sources.md`) found FiinQuant has **no news function**.
FiinPro-X, the desktop/institutional terminal, launched at ~9,000,000 VND/month on
12-month terms ([fiingroup.vn](https://www.fiingroup.vn/vi/news-fg/RA-MAT-FIINPRO-X---NEN-TANG-DU-LIEU-TAI-CHINH-TOAN-DIEN-VA-CHUYEN-SAU-id1746788.html),
[cafef.vn](https://cafef.vn/ra-mat-fiinpro-x-nen-tang-du-lieu-tai-chinh-toan-dien-va-chuyen-sau-188230412191508773.chn)) —
a human terminal, not an API.

### Vietstock

**DataFeed** is a licensed feed for institutions: indices/trading data, financials,
news/disclosures, derivatives and macro, historical + updated data, delivered via
**API or scheduled Sync Data**, with an SLA-style pitch (≤2% error commitment, 98%
reliability); pricing **on contact** —
[dichvu.vietstock.vn](https://dichvu.vietstock.vn/du-lieu-tai-chinh/datafeed---du-lieu-tai-chinh-tich-hop-chuyen-nghiep).
Consumer-side, VietstockFinance sells Free/Basic/Pro/Premium web tiers (a 2020 promo
listed Pro at 29,880,000 VND/12 months) —
[vietstock.vn](https://vietstock.vn/2020/12/mua-15-ngay-mien-phi-350-ngay-truy-xuat-du-lieu-tai-chinh-4511-810159.htm).
No self-serve public API; per `docs/research/news-sources.md`, the site's news JSON
endpoint returns `[]` without CSRF cookie+token.

### Wichart / WiData

Charting + macro data platform; price/volume/foreign data shown with a stated 2–5s
delay from exchange data ([wichart.vn blog/support](https://wichart.vn/support));
an Excel add-in WiData is sold at [widata.vn/gia](https://www.widata.vn/gia). API
access and pricing: **not publicly documented** — contact sales.

### Simplize

Consumer analysis app; Basic free, Premium reported at 199,000 VND/month via
third-party reviews ([vuachungkhoang.com](https://vuachungkhoang.com/simplize/),
[App Store listing](https://apps.apple.com/app/id1659974715)). No public API docs
found — not an ingestion candidate.

### CafeF

Free **EOD file downloads** (MetaStock/AmiBroker format, full history from 2000, all
tickers + indices) at [s.cafef.vn/du-lieu-download.chn](https://s.cafef.vn/du-lieu-download.chn) /
[cafef.vn/du-lieu/du-lieu-download.chn](https://cafef.vn/du-lieu/du-lieu-download.chn),
plus scrapeable ajax endpoints. Per this repo's earlier check
(`docs/research/news-sources.md`): robots.txt allows everything, **no ToS page
exists**, content is VCCorp-copyrighted — usable but informal, zero support, zero
contract.

### Refinitiv/LSEG, Bloomberg

Both carry HOSE/HNX as licensed exchange distributors (HOSE names Refinitiv,
Bloomberg and Yonhap as distribution channels —
[thoibaotaichinhvietnam.vn](https://thoibaotaichinhvietnam.vn/hose-ra-mat-giao-dien-website-moi-de-su-dung-nhieu-tinh-nang-noi-bat-175626.html);
Refinitiv also powered the ASEAN Exchanges portal including Vietnam —
[lseg.com](https://www.lseg.com/en/media-centre/press-releases/refinitiv/2020/february/asean-exchanges-selects-refinitiv-digital-solutions-to-power-investors)).
Enterprise terminal/feed pricing, **not public**; both are an order of magnitude
above domestic vendors and only sensible if global multi-asset coverage is needed.

## 4. Free / open-source libraries

### vnstock (thinh-vu/vnstock) — what it actually wraps

The installed 4.x package (`apps/api/.venv/.../vnstock/explorer/`) contains
explorers for **VCI, KBS, MSN, FMarket** (plus `misc`); the upstream endpoints,
read from each `const.py`:

- **VCI (Vietcap)** — `https://trading.vietcap.com.vn/api/`,
  `https://trading.vietcap.com.vn/data-mt/graphql`,
  `https://iq.vietcap.com.vn/api/iq-insight-service` (news)
- **KBS (KB Securities)** — `https://kbbuddywts.kbsec.com.vn/iis-server/investment`, `/sas`
- **MSN** — `https://assets.msn.com/service/Finance` (forex/crypto/international)
- **FMarket** — `https://api.fmarket.vn/res/products` (mutual funds)

TCBS was a 3.x-era source and still appears in vnstock's own materials
([vnstocks.com blog](https://vnstocks.com/blog/api-rate-limit-la-gi-cach-xu-ly-trong-vnstock)).
None of these are contracted APIs — they are the brokers' own web/app backends, so
"switching to VCI directly" inherits exactly the same unofficial-endpoint fragility,
minus vnstock's quota layer.

- **Quotas** (vnstock's own metering): Guest 20 req/min; Community (free
  registration) 60 req/min; Sponsor/Insider 180–600 req/min —
  [github.com/thinh-vu/vnstock](https://github.com/thinh-vu/vnstock); the blog also
  cites 60 req/min + 3,000 req/hour, counted independently per source
  ([vnstocks.com](https://vnstocks.com/blog/api-rate-limit-la-gi-cach-xu-ly-trong-vnstock)).
  Insider tier prices: **not publicly documented** (membership page renders
  client-side, [vnstocks.com/insiders-program](https://vnstocks.com/insiders-program)).
- **License risk (important)**: vnstock uses a **custom personal-use license** — the
  README states it is "không dành cho mục đích thương mại" (not for commercial
  purposes); commercial use requires a license from the author —
  [github.com/thinh-vu/vnstock](https://github.com/thinh-vu/vnstock). Stock_Massive
  as a commercial product cannot stand on vnstock long-term without that license.

### vnquant (phamdinhkhanh/vnquant)

Scrapes **CafeF and VNDIRECT** for OHLC and financial reports; last documented
version 0.1.2, low maintenance activity —
[github.com/phamdinhkhanh/vnquant](https://github.com/phamdinhkhanh/vnquant).
Strictly worse than vnstock for this repo.

## 5. Realtime / streaming options

| Feed | Transport | Content | Limits | Auth |
|---|---|---|---|---|
| SSI FCData streaming | streaming via official SDKs at `https://fc-data.ssi.com.vn/` ([client](https://github.com/SSI-Securities-Corporation/python-fcdata)) | `F`, `X-QUOTE` (3/10-level book), `X-TRADE`, `X`, `B` (tick OHLCV), `R` (foreign room), `MI` (indices), `OL` ([docs](https://guide.ssi.com.vn/ssi-products/fastconnect-data/streaming-data)) | quota per connection key, numbers not public | ConsumerID/Secret (SSI account) |
| DNSE LightSpeed | MQTT over WSS (`datafeed-lts[-krx].dnse.com.vn:443/wss`) | tick, stock info, top price, indices, OHLC candles, session events (JSON) ([topics](https://hdsd.dnse.com.vn/san-pham-dich-vu/lightspeed-api-truoc-krx/iii.-market-data/2.-dac-ta-thong-tin-cac-message/2.2.-topics.md)) | not published | public topics: none; else JWT (8h) |
| FiinQuant | SDK realtime subscription | order-matching data, KRX-connected ([fiingroup.vn](https://fiingroup.vn/en/news-fg/FiinQuant-%E2%80%93-Real-Time--High-Speed--and-Reliable-Trading-Data-for-Vietnam-s-Stock-Market-id2466736.html)) | 33/50/100/200/1,500 symbols, 1–40 connections by tier ([pricing](https://fiinquant.vn/Pricing)) | account + tier |
| HNX direct | Message/XML, leased line or Internet | realtime trading data, all HNX markets ([hnx.vn](https://hnx.vn/vi-vn/dich-vu-cctt/huong-dan-yeu-cau-ky-thuat-sgtc.html)) | contract | information-usage contract |
| Vietstock DataFeed | API / Sync Data | historical + updated market/fundamental data ([dichvu.vietstock.vn](https://dichvu.vietstock.vn/du-lieu-tai-chinh/datafeed---du-lieu-tai-chinh-tich-hop-chuyen-nghiep)) | contract | contract |

## 6. Recommendation for Stock_Massive

The provider seam (`apps/api/src/stocks/providers/`, `ProviderSource` +
`Capability`) already isolates this decision per data class. Ranked moves:

1. **Scale on FiinQuant, not vnstock.** It is the only self-serve source with
   *published* rate limits, and even its cheapest paid tier (Basic: 720 req/min,
   200k/month, 4 connections) is 12× the current vnstock ceiling; Enterprise reaches
   7,500 req/min and 1,500 realtime symbols
   ([fiinquant.vn/Pricing](https://fiinquant.vn/Pricing)). The adapter, circuit
   breaker and normalization already exist in `fiinquant.py` — a tier upgrade is a
   config change, not an engineering project. It is also licensed data, which
   vnstock's personal-use license is not.
2. **Treat vnstock as a fallback/dev source only, and flag the license.** Its custom
   license forbids commercial use without the author's permission
   ([GitHub](https://github.com/thinh-vu/vnstock)), and its backends (VCI, KBS) are
   unofficial broker endpoints that can change or block at any time. Going "direct
   to VCI" removes the quota layer but keeps every other risk.
3. **For streaming ticks, DNSE's MQTT feed is the cheapest experiment** (public
   topics need no auth; JSON over WSS; free with a DNSE account) and SSI FCData is
   the best-documented one — but **both brokers' terms restrict the data to the
   customer's own trading and forbid provision to third parties**
   ([DNSE terms](https://hdsd.dnse.com.vn/die-u-khoa-n-di-ch-vu-dnse/dieu-khoan-san-pham-dich-vu/dieu-khoan-san-pham-lightspeed-api),
   [SSI terms](https://guide.ssi.com.vn/ssi-products/tieng-viet/dang-ky-dich-vu)).
   Fine for the internal VN30 pilot; not a lawful backbone for serving end users.
   FiinQuant's realtime stream is the licensed path, sized by tier.
4. **When Stock_Massive serves paying users**, price a Vietstock DataFeed contract
   and an HNX information-usage contract (HOSE via sales contact) against FiinQuant
   Enterprise — those are the only redistribution-clean options.
5. **CafeF EOD dumps** remain a free integrity cross-check for historical backfills
   (full EOD from 2000, no auth), but with no ToS/contract they should never be a
   primary source.

Gaps to close with sales contacts (nothing public): FiinQuant tier prices in VND,
SSI FCData numeric rate limits, DNSE fees/limits, Vietstock DataFeed and exchange
contract pricing.
