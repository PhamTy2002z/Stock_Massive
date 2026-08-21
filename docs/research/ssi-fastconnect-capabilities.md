# Research: SSI FastConnect — full capability surface and real quota limits

Question: exactly what data can SSI FastConnect deliver, and what are the actual
rate limits? Prior work (`plans/reports/research-260821-1920-ssi-fastconnect-fitness.md`,
`plans/reports/brainstorm-260821-1930-ssi-integration.md`) mapped the **FCData V2.0**
field set from the 2022 PDF spec but could not find a single published quota number,
the history depth, or the streaming transport. This document closes those gaps.

Method: primary sources only — official docs sites, official SDK source code, the
official OpenAPI files, the legal ToS page, and **one live unauthenticated probe of
the production host** (2026-08-21). Blogs were not used. Every claim links to the
source that owns it. Claims are tagged: **[confirmed]** = a primary source says it,
**[inferred]** = derived, with the derivation stated, **[not found]** = searched and
absent. Nothing here is estimated.

## TL;DR — the headline finding

**There are two live generations of FastConnect, and the prior reports only saw the
old one.** All previous analysis in this repo targets `fc-data.ssi.com.vn/api/v2`
(FCData V2.0, spec frozen 2022, docs frozen 2025-02-18, pre-KRX). SSI has since
shipped a **v3 API on a new host, a new developer portal, and a new SDK family**, and
v3 is the one being actively maintained.

| | FCData v2 (prior reports) | FastConnect v3 (this document) |
|---|---|---|
| REST base | `https://fc-data.ssi.com.vn/api/v2/Market/` | `https://api.ssi.com.vn/api/v3/` |
| Streaming | SignalR, `wss://fc-datahub.ssi.com.vn/v2.0` | plain WebSocket, `wss://stream.ssi.com.vn/ws/v3` |
| Docs | [guide.ssi.com.vn](https://guide.ssi.com.vn/ssi-products) — FCData pages last touched 2025-02-19 | [developers.ssi.com.vn](https://developers.ssi.com.vn/docs/api-reference) — portal licence dated 2025-11-24 |
| SDK org | [SSI-Securities-Corporation](https://github.com/SSI-Securities-Corporation) — FCData last push 2024-06-05 | [SSI-Securities-Inc](https://github.com/SSI-Securities-Inc) — pushes 2026-08-12/16 |
| Credentials | ConsumerID + ConsumerSecret | apiKey + apiSecret (+ clientId), OTP only for trading |
| Rate-limit visibility | none | `X-RATELIMIT-LIMIT` / `-REMAINING` / `-RESET` + HTTP 429 |
| Live at research time | yes (responds) | yes (responds) |

Both hosts answered on 2026-08-21. Neither site announces the other, and **no
deprecation notice for v2 exists anywhere** **[not found]** — searched
[guide.ssi.com.vn change log](https://guide.ssi.com.vn/ssi-products/change-log)
(last entry 2025-02-18) and the whole developer portal doc tree.

Answers to the four questions that blocked the prior reports:

| Question | Answer | Confidence |
|---|---|---|
| Post-KRX spec? | Yes — a full **v3** API, not a v2.1. See §1. | **[confirmed]** |
| Numeric rate limit? | **`X-RATELIMIT-LIMIT: 100`**, measured live on v3. Period not published; observed to reset in <20 s. FCTrading docs publish a sample shape of `5 per 1s` / `30 per 5s`. Official SDKs default to **10 req/s** client-side. See §3. | **[confirmed]** number, **[not found]** period |
| History depth? | **Daily OHLCV: from the symbol's first trading day. Intraday: most recent 1 year.** Stated twice by SSI. See §4. | **[confirmed]** |
| Price for third parties? | Explicitly forbidden, **including processed/derived data**. Verbatim in §5. | **[confirmed]** |

## 1. The v3 API surface (post-KRX)

Evidence that v3 is real and current, not a mock-up:

- `pyproject.toml` in [ssi-sdk-python](https://github.com/SSI-Securities-Inc/ssi-sdk-python)
  publishes package `ssi-sdk`; PyPI shows **3.0.1 first released 2026-03-27, latest
  3.2.0 on 2026-08-12** ([pypi.org](https://pypi.org/pypi/ssi-sdk/json)). So v3 went
  public around March 2026 **[inferred from release dates]**.
- The GitHub org [SSI-Securities-Inc](https://github.com/SSI-Securities-Inc) was
  created 2025-07-17, lists `blog: https://ssi.com.vn/`, and holds v3 SDKs for
  Python, Go, Node/TypeScript, .NET plus `ssi-fastconnect-v3-tutorials`.
- A live unauthenticated GET to `https://api.ssi.com.vn/api/v3/data/indexList`
  returned `HTTP/2 401` with body `{"code":401,"msg":"Unauthorized"}` and real
  rate-limit headers (probe, 2026-08-21).

### 1.1 Endpoint inventory

| v3 endpoint | Purpose | v2 equivalent |
|---|---|---|
| `POST /api/v3/auth/token` | accessToken + refreshToken from apiKey/apiSecret; `otp` only needed for trading rights | `POST /Market/AccessToken` |
| `POST /api/v3/auth/refresh` | refresh without re-sending secret | — (new) |
| `POST /api/v3/auth/requestOtp` | SMS/Email/SmartOTP request | — (new) |
| `GET /api/v3/data/securitiesByBoard` | securities list + master metadata, filter by one of `symbol`/`board`/`index` | `Securities` + `SecuritiesDetails` + `IndexComponents` |
| `GET /api/v3/data/securitiesSummary` | per-session trading summary for a symbol **or an index** | `DailyStockPrice` |
| `GET /api/v3/data/indexList` | index list, optional `board` | `IndexList` |
| `GET /api/v3/data/indexSummary` | index summary by trading date | `DailyIndex` |
| `GET /api/v3/data/ohlc` | OHLCV, `timeFrame` 1m/3m/5m/15m/30m/1h/1d | `DailyOhlc` + `IntradayOhlc` |
| `GET /api/v3/data/masterdata` | ceiling / floor / reference price by trading date | fields inside `DailyStockPrice` |
| `GET /api/v3/data/ohlc/download` | **bulk CSV download** of full OHLC history | — (new) |

Sources: [api-reference overview](https://developers.ssi.com.vn/docs/api-reference)
and the per-endpoint pages ([data-ohlc](https://developers.ssi.com.vn/docs/api-reference/data-ohlc),
[data-securitiesSummary](https://developers.ssi.com.vn/docs/api-reference/data-securitiesSummary),
[data-securitiesByBoard](https://developers.ssi.com.vn/docs/api-reference/data-securitiesByBoard),
[data-indexSummary](https://developers.ssi.com.vn/docs/api-reference/data-indexSummary),
[data-masterData](https://developers.ssi.com.vn/docs/api-reference/data-masterData)).
The download endpoint is in the SDK as `EP_DATA_OHLC_DOWNLOAD = "/api/v3/data/ohlc/download"`
([constant.py](https://github.com/SSI-Securities-Inc/ssi-sdk-python/blob/main/ssi_sdk/constant.py))
but its SDK wrapper still `raise NotImplementedError("OHLC download is not implemented yet")`
([market_data.py](https://github.com/SSI-Securities-Inc/ssi-sdk-python/blob/main/ssi_sdk/services/market_data.py)) —
so the endpoint exists server-side and the client does not use it yet **[confirmed]**.

### 1.2 v2 endpoint inventory, corrected

The prior reports listed 9 endpoints. The official SDK also ships a 10th:
`MD_BACKTEST = 'api/v2/Market/BackTest'` taking `selectedDate` + `symbol`
([api.py](https://github.com/SSI-Securities-Corporation/python-fcdata/blob/master/ssi_fc_data/model/api.py),
[model.py](https://github.com/SSI-Securities-Corporation/python-fcdata/blob/master/ssi_fc_data/model/model.py)).
It appears in **neither** the PDF spec nor the web guide nor the OpenAPI file —
undocumented, purpose unknown **[not found]**.

Two other corrections to the prior reports:

- **Host discrepancy resolved.** The 2022 PDF's `fc-market.ssi.com.vn` is stale. The
  official OpenAPI file shipped by SSI declares `servers: [{url:
  "https://fc-data.ssi.com.vn/api/v2/Market/"}]`
  ([docs repo, `swagger (1).json`](https://github.com/SSI-Securities-Corporation/docs/blob/main/.gitbook/assets/swagger%20(1).json)),
  and the [connection guide](https://guide.ssi.com.vn/ssi-products/fastconnect-data/connection-guide)
  lists `https://fc-data.ssi.com.vn/v2.0/Market`.
- **Pagination is more generous than the PDF says.** The current web spec gives
  `pageIndex` 1–10 and `pageSize` ∈ {10, 20, 50, 100, 1000} default 10 for **every**
  FCData endpoint including `DailyStockPrice`
  ([api-specs](https://guide.ssi.com.vn/ssi-products/fastconnect-data/api-specs)) —
  so the prior report's "`DailyStockPrice` PageSize ≤ 100" is superseded. The hard
  ceiling per parameter combination is **10,000 rows** (10 × 1000) **[inferred]**.
- The PDF's `DailyOhlc` **"Max range 30 days"** on `ToDate` is real (spec §4.6, line
  798 of the extracted text) but is **not restated** in the current web spec or in v3
  **[confirmed for v2.0 PDF only]**.

### 1.3 What v3 gains over v2 — field level

Fields that exist in v3 and had **no source at all** in v2 REST:

| v3 field | Endpoint | Why it matters |
|---|---|---|
| `icbCode`, `icbName` | `securitiesByBoard` | ICB sector classification. Prior reports concluded "SSI has no ICB" and kept vnstock for the listing roster; **v3 has it**. |
| `totalForeignRoom` | `securitiesSummary` | Total foreign room per session on REST. In v2 this existed **only** on streaming channel `R`. |
| `totalPropBuy/Value`, `totalPropSell/Value` | `indexSummary` | Proprietary-trading (tự doanh) flow — the data class HOSE cut for downstream vendors in 2022 (`docs/research/vn-market-data-sources.md`). |
| `iIndex`, `iNav` | `securitiesByBoard` | ETF iNAV. |
| `openInterest`, `settlementPrice` | `securitiesSummary`, `securitiesByBoard` | Derivatives. |
| `1w`, `1M` timeframes | SDK `Timeframe` enum | Weekly/monthly bars. |

Retained from v2: `average` (session VWAP), `remainForeignRoom`, six foreign
buy/sell volume+value fields, `totalDeal`/`totalDealValue` (put-through),
`totalTradeBuy`/`totalTradeSell` (trade counts), market breadth
(`totalAdvanceStock`/`totalDeclineStock`/`totalNoChangeStock`/`totalCeilingStock`/
`totalFloorStock`), `listedShare`, `lotSize`, `firstTradingDate`/`lastTradingDate`/
`maturityDate`, CW metadata.

### 1.4 What v3 **loses** versus v2 — the important regression

| Missing in v3 | Present in v2 | Impact |
|---|---|---|
| **Adjusted close** | `closepriceadjusted` on `DailyStockPrice` | Grepped all v3 endpoint docs and all v3 SDK models for `adjust`/`điều chỉnh`: **zero hits** **[confirmed absent]**. This was the single strongest argument in both prior reports for adopting SSI (it would have erased `mixed_price_basis` per `ADR-0006`). On v3 that argument does not hold. |
| Tick-size table | `TickPrice1-4`/`TickIncrement1-4` on `SecuritiesDetails` | No v3 equivalent found. |
| Trading-status codes | `TradingStatus` (N/D/H/S/NL/ND/ST/SA/SP) on channel `F` + REST | v3 has a `market` topic for "đầu ngày và cờ phiên" but no documented status enum. |
| `ISIN`, `ExerciseStyle`, `SettlMethod`, `ContractMultiplier` | `SecuritiesDetails` | Not in `securitiesByBoard`. |

Also absent from **both** generations **[confirmed]**: market capitalisation, P/E, P/B,
EPS, outstanding-share count, free float, financial statements, corporate actions,
dividends. FastConnect is a trading feed, not a fundamentals feed. `listedShare` is
the only share count offered.

## 2. Data coverage summary

| Data class | v2 | v3 | Notes |
|---|---|---|---|
| Equity EOD OHLCV | ✓ | ✓ | HOSE/HNX/UPCOM |
| Raw + adjusted close on one row | ✓ | **✗** | see §1.4 |
| Ceiling/floor/reference | ✓ (in `DailyStockPrice`) | ✓ (separate `masterdata` call) | v3 costs an extra request |
| Session VWAP | ✓ `averageprice` | ✓ `average` | |
| Foreign flow (vol+val+net) | ✓ | ✓ | |
| Total foreign room | streaming `R` only | ✓ REST | |
| Market breadth | ✓ `DailyIndex` | ✓ `indexSummary` | with history |
| Proprietary trading | ✗ | ✓ | |
| ICB sector | ✗ | ✓ | |
| Put-through / odd lot | ✓ | ✓ | |
| Intraday bars | ✓ `IntradayOhlc` | ✓ `ohlc` w/ `timeFrame` | 1 year cap, §4 |
| Order book | streaming `X-QUOTE` (3 lvl HOSE / 10 lvl HNX-UPCOM-DER) | streaming `quote` topic | v3 depth not stated **[not found]** |
| Derivatives / CW / ETF / bond | ✓ | ✓ | |
| Valuation, fundamentals, corp. actions | ✗ | ✗ | |

## 3. Quota and rate limits — the actual numbers

This is the section the prior reports could not fill. Ranked by evidential strength.

### 3.1 Measured live (strongest)

An unauthenticated `GET https://api.ssi.com.vn/api/v3/data/indexList` on 2026-08-21
returned:

```
HTTP/2 401
x-ratelimit-limit: 100
x-ratelimit-remaining: 99
```

Observations across a small probe (≈14 requests total, all on the 401 path):

- `x-ratelimit-limit` is constantly **100**.
- `x-ratelimit-remaining` decrements per request (99 → 98 → 97).
- A single request every 20 s always showed `remaining: 99`, so **the window resets in
  under 20 s** **[measured]**.
- Inside a fast burst the value was **non-monotonic** (99, 99, 98, 97, 99, 98),
  which is what distributed per-node counters look like **[inferred]**.
- `x-ratelimit-reset` was **not emitted** on the 401 path, so the period could not be
  read directly **[not found]**.

Two caveats that must not be lost: this is the **pre-authentication** bucket, and the
per-API-key bucket that SSI documents may be a different number entirely; and the
period is unknown, so "100" alone does not give a req/s figure.

By contrast, the v2 host emits **no rate-limit headers at all** — a request to
`https://fc-data.ssi.com.vn/api/v2/Market/IndexList` returned only ASP.NET headers
(`x-aspnet-version: 4.0.30319`). v2 gives you no quota telemetry whatsoever
**[measured]**.

Integration gotcha found in the same probe: **v2 returns `HTTP/2 200` for an auth
failure**, with the real status inside the body
(`{"message":"Missing Authorization header","status":401}`). v3 returns a correct
`HTTP/2 401`. Any v2 client that trusts the HTTP status will silently treat auth
failures as success **[measured]**.

### 3.2 Published by SSI (numbers, but for FCTrading)

SSI never publishes an FCData number, but FCTrading exposes
`GET https://fc-tradeapi.ssi.com.vn/api/v2/Trading/rateLimit`, and its documented
sample response contains real values —
[FCTrading API Specs](https://guide.ssi.com.vn/ssi-products/fastconnect-trading/api-specs):

```json
{"message":"Success","status":200,
 "data":[{"endpoint":"*","period":"1s","limit":5},
         {"endpoint":"*","period":"5s","limit":30}]}
```

The same page documents the quota model: `endpoint` is one of `*` (all APIs),
`post:*`, `get:*`, or `*:*/api_name`; `period` has format `s,m,h,d`; `limit` is a
number. This is the shape behind the `"API calls quota exceeded! maximum admitted x
per y s"` error string — `x` = `limit`, `y` = `period` **[inferred, high confidence]**.

**There is no equivalent `rateLimit` endpoint for FCData** in the v2 SDK, the v2
OpenAPI file, or the v3 SDK **[not found]** — so an FCData integrator cannot query
their own quota; on v3 they can only read the response headers.

### 3.3 Official SDK defaults (what SSI's own engineers assume)

Every v3 SDK ships the same client-side throttle default:

- Python: `DEFAULT_RATE_LIMIT_PER_SECOND = 10` in
  [constant.py](https://github.com/SSI-Securities-Inc/ssi-sdk-python/blob/main/ssi_sdk/constant.py),
  wired into `Config.rate_limit_per_second` and enforced by a token-bucket
  `RateLimiter` in [retry.py](https://github.com/SSI-Securities-Inc/ssi-sdk-python/blob/main/ssi_sdk/utils/retry.py).
- Go: `DefaultRateLimitPerSecond = 10` in
  [config.go](https://github.com/SSI-Securities-Inc/ssi-sdk-go/blob/main/config.go);
  the [Go README](https://github.com/SSI-Securities-Inc/ssi-sdk-go/blob/main/README.md)
  documents it in a config table as `10 | Giới hạn request/giây (0 = không giới hạn)`.

Other SDK defaults worth copying: `DEFAULT_TIMEOUT = 60` s,
`DEFAULT_MAX_RETRIES = 5`, `DEFAULT_RETRY_DELAY = 2` s with exponential backoff, and
retry **only** on `httpx.TimeoutException` — a 429 raises `RateLimitError` carrying
`Retry-After` and is never auto-retried. Default page size is `DEFAULT_SIZE = 1000`.

Note the tension: the SDK assumes 10 req/s while SSI's own published FCTrading sample
is 5 per 1 s. Do not treat 10 as a granted allowance **[inferred]**.

### 3.4 Documented mechanism, no numbers

- v3, the page explicitly dedicated to limits
  ([Điều kiện sử dụng & Môi trường](https://developers.ssi.com.vn/docs/getting-started/terms-and-environments)):
  "Hệ thống áp dụng rate limit cho **từng API Key**", exposed via the three
  `X-RATELIMIT-*` headers, `HTTP 429 Too Many Requests` on breach, "Đợi đến thời
  điểm `X-RATELIMIT-RESET` trước khi gọi tiếp." **No values.**
- v2 ([General Information](https://guide.ssi.com.vn/ssi-products/general-information)):
  "The rate limit is applied to **each API**… For FC Data, the limit is counted on
  **each connection key**." Error strings `"API calls quota exceeded! maximum admitted
  x per y s"` (API) and `"Connection has been blocked, quota x exceeded by y"`
  (streaming). "If you request to increase the rate limit value, please contact to
  your account executive." Plus the standing advice: "To receive real-time update, you
  should use streaming connection rather than using API for polling to avoid rate
  limit violation."
- Multiple keys per account are allowed — v3 FAQ: "Có. Khách hàng có thể tạo nhiều
  API Key và gán mục đích sử dụng khác nhau cho từng key"
  ([FAQ](https://developers.ssi.com.vn/docs/getting-started/faq)). Since the quota is
  per key, this is a legitimate way to widen throughput **[inferred]**.

### 3.5 Streaming and non-request limits

| Limit | Value | Confidence |
|---|---|---|
| Max symbols per subscription | not published | **[not found]** — searched both doc trees and all SDKs |
| Max concurrent connections | not published | **[not found]** |
| Subscription scope | enforced per key; `*` means "toàn bộ mã trong **phạm vi quyền**", and `LIST_SUBSCRIPTION` returns the granted scope as e.g. `{"trading":"order.*;portfolio.123456","data":"trade.*;quote.*;room.*"}` ([Heartbeat và Subscription](https://developers.ssi.com.vn/docs/api-reference/getHeartbeatStructure)) | **[confirmed]** |
| Heartbeat | server PINGs every **30 s**; client must PONG or the session closes ([getting-started](https://developers.ssi.com.vn/docs/getting-started), [FAQ](https://developers.ssi.com.vn/docs/getting-started/faq)) | **[confirmed]** |
| CSV download link TTL | **30 minutes** ([terms-and-environments](https://developers.ssi.com.vn/docs/getting-started/terms-and-environments)) | **[confirmed]** |
| Fixed-IP allow-list | must register a fixed IP for the service on the iBoard API screen ([Service registration](https://guide.ssi.com.vn/ssi-products/service-registration)) | **[confirmed]** |
| Refresh-token lifetime | doc sample has `refreshExpiresAt − expiresAt = 86400` s, i.e. refresh outlives access by 24 h ([api-keys](https://developers.ssi.com.vn/docs/getting-started/api-keys)) | **[inferred from sample]** |
| Access-token lifetime | not published. v2 SDK refreshes when <3600 s remain ([access_token.py](https://github.com/SSI-Securities-Corporation/python-fcdata/blob/master/ssi_fc_data/model/access_token.py)) | **[not found]** |
| SmartOTP `transactionId` TTL | 30 s | **[confirmed]** |

**Conclusion on quotas.** SSI does not publish an FCData rate limit, in either
generation, anywhere. What exists and is usable today: a live `X-RATELIMIT-LIMIT: 100`
header on v3, a per-key counting rule, a 429 + `Retry-After` contract, a published
FCTrading sample of 5/1s and 30/5s, an official SDK default of 10 req/s, and an
escalation path through an account executive. Any number beyond that would be
invention.

## 4. History depth — answered

Both v3 pages state it identically:

| Data | Range |
|---|---|
| OHLCV **daily** | "Từ ngày mã chứng khoán bắt đầu giao dịch" — from the symbol's first trading day |
| OHLCV **intraday** (1m, 5m, 15m, 30m, 1h) | "1 năm gần nhất" — most recent 1 year |
| CSV download URL | valid 30 minutes |

Sources: [terms-and-environments](https://developers.ssi.com.vn/docs/getting-started/terms-and-environments)
(a limits table) and [FAQ](https://developers.ssi.com.vn/docs/getting-started/faq)
("Dữ liệu lịch sử có bao nhiêu năm?"), plus the `data-ohlc` endpoint description
itself: "Thời gian cung cấp 1 năm gần nhất cho dữ liệu intraday, dữ liệu daily cung
cấp từ khi mã chứng khoán được giao dịch." **[confirmed, three independent pages]**

This is the answer the prior reports flagged as the single most important unknown, and
it is favourable: daily history is bounded by listing date, not by a retention window.
Caveats: it is stated for **`data-ohlc`** (open/high/low/close/volume/value only), not
for `securitiesSummary` — whose depth is **not stated** **[not found]**. And the v2
`DailyStockPrice` depth remains undocumented **[not found]**. Neither can be verified
without credentials.

## 5. Account, cost and legal boundary — verbatim

### 5.1 Eligibility and cost

- Requires an SSI trading account. v3: "Có tài khoản giao dịch tại SSI · Đăng ký
  FastConnect qua Developer Portal và được phê duyệt · Đồng ý điều khoản sử dụng dịch
  vụ" ([terms-and-environments](https://developers.ssi.com.vn/docs/getting-started/terms-and-environments)).
- **Free, and this is now sourced properly.** v3 FAQ, "Tôi có thể dùng API miễn phí
  không?" → *"Có. Hiện tại SSI chưa thu phí đối với dịch vụ FastConnect API."*
  ([FAQ](https://developers.ssi.com.vn/docs/getting-started/faq)). Note the wording is
  "**chưa** thu phí" — *does not yet charge*, not *is free*. Correction to earlier repo
  research: the sentence "Dịch vụ FastConnect API được cung cấp miễn phí" attributed to
  [dang-ky-dich-vu](https://guide.ssi.com.vn/ssi-products/tieng-viet/dang-ky-dich-vu)
  in `docs/research/vn-market-data-sources.md` is **not on that page today** — grepping
  the entire downloaded guide tree (both languages) for `miễn phí`/`free` returns zero
  hits **[confirmed absent]**.
- Registration is **not** self-serve despite the portal. v3: branch/PGD or hotline
  1900545471, activation email in 2–4 working hours, then e-contract signing
  ([registration](https://developers.ssi.com.vn/docs/getting-started/registration)).
  v2 is blunter: "Currently, FastConnect API is registered at the counter or through
  your account executive. We will notify later when online registration is provided."
  ([Service registration](https://guide.ssi.com.vn/ssi-products/service-registration)).
  The same v3 doc set also says registration happens "qua Developer Portal" — the two
  v3 pages contradict each other **[confirmed contradiction]**.
- No UAT/sandbox today: "Thông tin môi trường UAT sẽ được thông báo khi sẵn sàng"
  ([terms-and-environments](https://developers.ssi.com.vn/docs/getting-started/terms-and-environments)).
- Credentials, corrected: **FCData needs only ConsumerID + ConsumerSecret**. The v2
  [connection guide](https://guide.ssi.com.vn/ssi-products/fastconnect-data/connection-guide)
  lists exactly those two, the SDK's `accessToken` dataclass carries exactly those two,
  and the guide states the RSA+SHA256 signature applies to "a json body with
  placing/amend/cancel order" — i.e. FCTrading. The three-credential set
  (incl. `PrivateKey`) is issued per account but the PrivateKey is not used for market
  data **[confirmed]**. This corrects the prior report's "Ba credential" for FCData.

### 5.2 Term, renewal, and the 90-day dormancy rule

The governing legal text is
[developers.ssi.com.vn/term-condition](https://developers.ssi.com.vn/term-condition)
("Điều khoản và Điều kiện Đăng ký Dịch vụ Fast Connect API"), which is an inseparable
part of the customer's online-trading service appendix. Verbatim:

> **4.1 Thời hạn và Tái đăng ký** — "Dịch vụ FastConnect API có thời hạn hiệu lực mặc
> định là 01 (một) năm kể từ thời điểm kích hoạt. Nhằm đảm bảo tính liên tục của giao
> dịch, hệ thống sẽ thực hiện gửi thông báo nhắc nhở tự động qua Email đăng ký vào thời
> điểm 14 (mười bốn) ngày trước khi dịch vụ hết hạn. Khách hàng có thể thực hiện xác
> nhận gia hạn trực tuyến tại thông báo của SSI để tiếp tục sử dụng Dịch vụ mà không
> làm gián đoạn kết nối. Thời gian gia hạn của các lần kế tiếp nếu được SSI chấp thuận
> sẽ là 01 năm kể từ ngày hết hạn của thời hạn hiệu lực trước đó."

> **4.2 Quy định về tạm dừng kết nối tự động** — "Nếu hệ thống không ghi nhận bất kỳ
> tín hiệu kết nối hoặc giao dịch nào từ định danh API của Khách hàng trong vòng 90
> (chín mươi) ngày liên tục, dịch vụ sẽ được chuyển sang trạng thái Tạm ngừng hoạt
> động."

> **4.3 Chấm dứt dịch vụ** — "SSI có quyền ngừng cung cấp dịch vụ này cho Khách hàng
> theo quyết định của SSI bất cứ khi nào cần thiết mà không cần phải thông báo cho
> Khách hàng."

Two new operational facts here that no prior report had: the **90-day inactivity
auto-suspension**, and **online renewal**. Also a **conflict between two SSI sources**
on the reminder lead time: the ToS says **14 days**, while
[General Information](https://guide.ssi.com.vn/ssi-products/general-information) says
"SSI sends a email to notify you **7 days** before the expiration date". On expiry the
key returns `{ message: 'The connection is invalid', status: 400, data: null }`.

### 5.3 The third-party clause — verbatim, and stricter than assumed

From §3 "Cam kết của Khách hàng" of the same ToS:

> "Khách hàng không được cung cấp thông tin xác thực (khóa bí mật) API cho bất kỳ đối
> tượng nào khác."
>
> "**Thông tin nhận được từ API chỉ phục vụ cho mục đích giao dịch chứng khoán của
> Khách hàng. Khách hàng không được sử dụng cho mục đích khác, không được cung cấp cho
> bên thứ ba bất kỳ dù là một phần hay toàn bộ thông tin, thông tin nguyên gốc hay đã
> được xử lý.**"

No English version of this text exists — the developer portal is Vietnamese-only and
`/term-condition` has no `/en` variant **[not found]**. Working translation (not
SSI's): *information received from the API serves only the Customer's own securities
trading; the Customer may not use it for other purposes and may not provide to any
third party any part or all of the information, whether in original or processed form.*

The operative words are **"đã được xử lý"** — *processed*. This closes the gap that
`plans/reports/brainstorm-260821-1930-ssi-integration.md` recorded as "Signal phái
sinh là vùng xám" (derived signals are a grey area). They are not a grey area: derived
output is named in the clause. A source-filter gate at the serving layer, which that
brainstorm made a hard requirement, does **not** bring the design into compliance if
indicators computed from SSI data reach external users. This is a finding that
contradicts an accepted scope decision and needs the user's judgment, not a silent
patch.

Also note §3's opening: "Khi đăng ký dịch vụ Fast Connect API **Trading**, Khách hàng
đồng ý rằng:" — the commitments are introduced under the Trading heading, though the
information clause is written generically about "thông tin nhận được từ API". Whether
FCData-only customers are bound by the same clause is genuinely ambiguous in the text
**[unresolved — legal reading, not a research gap]**.

## 6. Streaming transport — answered for both generations

| | v2 | v3 |
|---|---|---|
| Protocol | **ASP.NET SignalR** (classic, not Core) | **plain WebSocket**, JSON frames |
| URL | `wss://fc-datahub.ssi.com.vn/v2.0` (Node), `https://fc-datahub.ssi.com.vn/v2.0` (Python/.NET), `https://fc-datahub.ssi.com.vn/` (Java) | `wss://stream.ssi.com.vn/ws/v3` |
| Handshake path | `v2.0/signalr` | — |
| Hub / method | hub `FcMarketDataV2Hub`; server method `SwitchChannels`; client callbacks `Broadcast`, `Error` | `{"method":"SUBSCRIBE\|UNSUBSCRIBE\|LIST_SUBSCRIPTION\|PING\|PONG","channel":"TRADING\|DATA\|HEARTBEAT","topics":[...]}` |
| Auth | `Authorization: Bearer <accessToken>` header on connect | Bearer access token |
| Subscription syntax | `CHANNEL:SYMBOL`, `CHANNEL:A-B`, `CHANNEL:ALL` (e.g. `X-QUOTE:ACB-VND`, `F:ALL`) | `topic.[index/exchange/symbol-symbol/*]@[tick/1m/5m]` (e.g. `trade.SSI`, `trade.ACB-SSI-GVR-KDH`, `trade.vn30`, `trade.hose`) |
| Channels/topics | `F`, `X`, `X-QUOTE`, `X-TRADE`, `B`, `R`, `MI`, `OL` | `trade`, `quote`, `room`, `put`, `oddlot`, `market` (+ trading-side `order`, `portfolio`) |
| Dependencies | `websocket-client>=1.5.2` + a **vendored** SignalR client (Matthew Whited's `signalr-client` v0.0.17 in Node; a bundled `ssi_fc_data/signalr/` package in Python) | `httpx>=0.27`, `websockets>=13`, `websocket-client>=1.7` |
| Reconnect | vendored `transports/reconnection.py`; SDK surfaces `CONNECTION_LOST_ERROR_MESSAGE = 'Connection lost: Try to reconnect to server!'` | client must re-subscribe after reconnect: "Sau khi reconnect, cần subscribe lại các topic cần theo dõi" |

Sources: v2 — [fc_md_stream.py](https://github.com/SSI-Securities-Corporation/python-fcdata/blob/master/ssi_fc_data/fc_md_stream.py),
[api.py](https://github.com/SSI-Securities-Corporation/python-fcdata/blob/master/ssi_fc_data/model/api.py),
[connection guide](https://guide.ssi.com.vn/ssi-products/fastconnect-data/connection-guide),
and the [change log](https://guide.ssi.com.vn/ssi-products/change-log) entry for
2023-09-13 recording the move from `fc-data` to `fc-datahub`. v3 —
[Kết nối WebSocket](https://developers.ssi.com.vn/docs/api-reference/connectWebSocket),
[Heartbeat và Subscription](https://developers.ssi.com.vn/docs/api-reference/getHeartbeatStructure),
[Sub/Unsub Market Data](https://developers.ssi.com.vn/docs/api-reference/subscribeUnsubscribeMarketData),
[constant.py](https://github.com/SSI-Securities-Inc/ssi-sdk-python/blob/main/ssi_sdk/constant.py).

Two notes. The prior repo research recorded the v2 streaming URL as
`https://fc-data.ssi.com.vn/` — that is the **stale value still hard-coded in the SDK
README's sample `config.py`**, superseded by `fc-datahub` in the 2023-09-13 changelog
entry **[confirmed]**. And v3 `quote` messages carry full `bids`/`asks` arrays today
with a documented plan to switch to deltas: "Bản nâng cấp sau sẽ chỉ trả ra các giá
trị thay đổi" — a forward-compatibility hazard for any parser.

v3 market-data message field sets are terse single/double-letter keys: `trade` =
`s,t,p,q,a,si,o,h,l,v` (with `si` = `B` buy-up / `S` sell-down); `room` =
`s,t,tr,cr,bq,bv,sq,sv`; `quote` = `s,t,bids,asks`; `put` = `s,t,p,q,tq,tv`;
`oddlot` = `s,t,p,q,bids,asks`.

## 7. FCTrading — out of FCData scope, but it does add data

Recorded briefly because it is the same credential and the same ToS. FCTrading
supplies **account-state data no market-data feed can give**: cash and derivatives
balances, stock/derivative positions, purchasing power and margin ratio (`ppmmrAccount`),
max buy/sell quantity, order book and order history, audit order book, cash-in-advance
amounts/history/fees, cash and stock transfer histories, and Online Right Subscription
(dividend, exercisable quantity, history). v3 adds FCO conditional orders (7 types: TS,
PRO, ST, TPRO, BB, OCO, MA) with `fco-list`, `fco-orderbook`, `fco-statusHistory`.

It supplies **no market data that FCData lacks** **[confirmed]** — its only relevant
extra is the `rateLimit` endpoint discussed in §3.2. It is the only place SSI publishes
a quota number, and only as a doc sample.

Sources: [FCTrading API Specs](https://guide.ssi.com.vn/ssi-products/fastconnect-trading/api-specs),
the official [FCTrading OpenAPI file](https://github.com/SSI-Securities-Corporation/docs/blob/main/.gitbook/assets/openapi.json)
(`FastConnect Trading API v2.0`, server `https://fc-tradeapi.ssi.com.vn/api/v2/Trading/`),
[api-reference overview](https://developers.ssi.com.vn/docs/api-reference).

## 8. Source credibility and documentation quality

Worth stating plainly, because it affects how much of §1 can be trusted before a probe.

| Source | Weight | Why |
|---|---|---|
| Official SDK source code (both orgs) | highest | executable, versioned, dated; endpoint constants cannot be aspirational |
| Official OpenAPI files in the `docs` repo | high | machine-readable, SSI-authored |
| `developers.ssi.com.vn/term-condition` | high | legal text, contractually binding, and the newest of all sources |
| `guide.ssi.com.vn` | high but **stale for FCData** | GitBook, per-page `lastmod` in sitemap; every FCData page ≤ 2025-02-19 |
| `developers.ssi.com.vn/docs/*` | medium-high | authoritative in substance, but see below |
| `developers.ssi.com.vn` marketing home | **low** | claims "99.9% Uptime SLA", "<50ms", "<10ms", "1000+ Đối tác", and testimonials citing a Go SDK that only appeared later; treat as copy, not spec |
| `FastConnectData_Specs_v2_0.pdf` | historical | changelog ends 2022-05-10; still the only field-level v2 reference |

Documentation defects found in the v3 portal, each of which is an integration risk:

- `getting-started` describes WebSocket channels as `F:STOCK`, `F:INDEX`, `T:ORDER`,
  `T:ACCOUNT`; the WebSocket reference describes `trade.SSI@tick` / `channel: DATA`.
  The two are irreconcilable; the SDK enums follow the reference.
- `first-api-call` uses query param `pageNumber` and dates `2026-05-20`; the endpoint
  reference uses `pageIndex` and `YYYY/MM/DD`.
- `data-ohlc` documents timeframes `1m,3m,5m,15m,30m,1h,1d`; the market-data
  subscription page says valid intervals are "tick, 1m, 5m (không có 3m)"; the SDK
  `Timeframe` enum has `1m,3m,5m,15m,1h,1d,1w,1M` — **no `30m`**.
- Several sidebar slugs 404 (`appendix`, and the error-code table is unreachable by
  guessed URL), so the promised 429/ErrCode reference could not be read **[not found]**.
- Pagination `pageSize` has a documented default of 10 but **no documented maximum**;
  the SDK uses 1000.

## 9. Recommendation

Ranked, and framed against the decisions already accepted in
`plans/reports/brainstorm-260821-1930-ssi-integration.md`.

1. **Target v3, not v2 — but reopen the ADR premise first.** The brainstorm's core
   justification was `closepriceadjusted` erasing `mixed_price_basis` and
   `unadjustable_price_basis` for the 2016→2021 window. **v3 has no adjusted price
   field.** So the choice is now explicit and neither option is the one that was
   approved: build on v2 (the field exists, docs frozen pre-KRX, no rate-limit
   telemetry, HTTP 200 on auth failure, SDK abandoned since 2024-06) or build on v3
   (maintained, ICB + total foreign room + proprietary flow + CSV bulk download, real
   429 semantics — but you must compute adjustments yourself from a corporate-action
   source, which is exactly what `ADR-0006` already does with vnstock). Ranked: **v3**,
   because a frozen pre-KRX API is a worse long-run bet than an adjustment you already
   compute; but this reverses a stated rationale and is the user's call, not a patch.
2. **Do the probe, and probe v3.** Cost is zero (no fee today, SSI account needed, 2–4h
   activation). Measure: authenticated `X-RATELIMIT-LIMIT` and the reset period;
   whether `securitiesSummary` reaches 2016; whether `totalTradeBuy`/`totalTradeSell`
   return real numbers or the `0` the v2 spec sample showed; and whether
   `/api/v3/data/ohlc/download` works despite the SDK not wiring it. Register the fixed
   IP up front — without it nothing connects. Everything after this step is assumption.
3. **Do not build the ingestion path around REST pagination if the CSV download
   works.** `pageIndex ≤ 10` × `pageSize ≤ 1000` capped v2 at 10,000 rows per parameter
   set; v3 documents no maximum but the SDK uses 1000. A working
   `/api/v3/data/ohlc/download` changes the backfill from ~22,000 requests to one file
   per symbol, and makes the whole quota question much less load-bearing. Verify before
   sizing anything.
4. **Treat the legal position as unresolved, not mitigated.** §5.3's "đã được xử lý"
   language covers derived output. The source-filter gate is necessary but not
   sufficient. Either get written SSI confirmation for the intended use, or keep SSI to
   internal cross-check and validation only — which is what `docs/research/vn-market-data-sources.md`
   already ranks it for, and which does not require deleting the 31,160 vnstock rows.
5. **Operational hygiene, regardless of tier.** Add a key-expiry alert (1 year, and the
   reminder lead time is itself inconsistent between two SSI pages), plus a **90-day
   dormancy heartbeat** — an idle key gets auto-suspended, which no other provider in
   this repo does. Read `X-RATELIMIT-REMAINING` into the existing
   `ProviderCircuitBreaker` rather than hard-coding any number; on 429, honour
   `Retry-After` and never blind-retry, matching the official SDK's behaviour.

## 10. Limitations of this research

- **No credentials.** Every response schema here is documentation and SDK models, never
  observed payloads. Field presence, actual history depth, null-vs-zero behaviour, and
  the authenticated quota are unverified.
- The rate-limit measurement is the **unauthenticated 401 path only**, ~14 requests, one
  vantage point, one moment. `x-ratelimit-limit: 100` may not be the authenticated
  per-key value, and the period was not determined.
- No v3 field-level spec PDF exists; v3 field lists come from HTML endpoint pages and
  SDK dataclasses, which may lag the server.
- Vietnamese-only legal text; the translation in §5.3 is mine, not SSI's, and this
  document is not a legal opinion.
- Directory listing at `ssi.com.vn/upload/files/KHCN/` is 403, so the PDF inventory
  could not be enumerated; only guessed filenames were tested (`_v2_1`, `_v3_0` → 404).
- Not covered: FCTrading field-level specs, iData/SSI-for-Excel (a separate SSI product
  whose GitBook source does carry balance-sheet, cash-flow, income-statement and
  supply-demand function classes — a fundamentals surface FastConnect lacks, worth its
  own study), UAT environment, and pricing should SSI start charging.

## 11. Questions only a real credential can answer

1. What is `X-RATELIMIT-LIMIT` and the reset period for an **authenticated** FCData
   key, and is it per endpoint or global (`endpoint: "*"` in the FCTrading model)?
2. How far back does `data/securitiesSummary` actually reach — is it the same
   "from first trading day" as `data/ohlc`, or shallower?
3. Does `/api/v3/data/ohlc/download` work, what is its format, and is it quota-charged
   as one request?
4. Do `totalTradeBuy` / `totalTradeSell` / `totalBuy` / `totalSell` carry real values,
   or always `0` as in the v2 spec sample — the same trap `docs/adr/0002` hit with
   FiinQuant's `bu`/`sd`?
5. Is v2 still fed post-KRX with the same field completeness, or is it a frozen
   compatibility layer? A one-symbol comparison of v2 `DailyStockPrice` against v3
   `securitiesSummary` for the same session settles it.
6. Is there any adjusted-price field on v3 that the docs omit?
7. What is the actual access-token TTL, and what order-book depth does the v3 `quote`
   topic deliver per exchange?
8. Does SSI consider an FCData-only customer bound by §3 of the ToS, which is
   introduced under a "Fast Connect API **Trading**" heading — and would SSI confirm in
   writing whether indicators derived from FCData may be shown to external users?
