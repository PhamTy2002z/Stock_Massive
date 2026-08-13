# Research: per-symbol Vietnamese stock news sources

Resolves issue #17. Question: which sources can reliably provide recent news for a
given HOSE/HNX/UPCOM symbol, and is a per-symbol news section viable for v1?

Method: primary sources only — the actual endpoints were fetched for the real HOSE
symbol **STB** (Sacombank) on 2026-08-10, the installed libraries were read, and
robots.txt / terms-of-use pages were checked. Candidates: vnstock (already a
dependency), FiinQuant (already a provider in this repo, added at user request),
CafeF, Vietstock, Fireant, Google News RSS.

## TL;DR — ranked list

| # | Source | Per-symbol | Auth | Freshness (STB test) | Format | Legal for a commercial product |
|---|---|---|---|---|---|---|
| 1 | **vnstock 4.x → VCI `news()`** | yes, native | none (vnstock quota layer) | newest 2026-08-07, 50 items | DataFrame/JSON, full content + source links | same posture as the price/fundamental data already served |
| 2 | **CafeF** `du-lieu/ajax/events_relatednews_new.aspx` | yes | none | newest 07/08/2026 (site feed: minutes-old) | HTML fragment | robots.txt allows everything; no ToS page exists; VCCorp copyright |
| 3 | **Vietstock** | HTML page only (`getnewsbycode` returns `[]`) | CSRF cookie+token | today (category RSS) | server-rendered HTML | robots allows content pages; ToS page must be reviewed |
| 4 | **Fireant** `restv2.fireant.vn/posts` | yes (`taggedSymbols`) | scraped public JWT (exp 2029) | yesterday | cleanest JSON | **ToS explicitly forbids building a business on the content** — blocked |
| 5 | **Google News RSS** | keyword query only | none | today, 35 sources | RSS, Google-redirect links | **feed copyright: personal, non-commercial use only** — blocked |
| 6 | **FiinQuant / FiinQuantX** | — | account login | — | Python SDK | licensed, but **has no news function at all** — out |

**Verdict: a per-symbol news section is viable for v1**, built on vnstock's VCI
news backend (already a dependency, already half-wired in `CompanyService`), with
CafeF's ajax endpoint as the only reasonable fallback. Details per candidate below.

## 1. vnstock (installed 4.0.5) — VCI and KBS news backends — RECOMMENDED

### Access method

`vnstock` is already pinned (`vnstock>=4.0.0,<5.0.0`, `apps/api/requirements.txt`)
and wrapped by `apps/api/src/core/vnstock_client.py`. Version 4.0.5 ships two
per-symbol news backends (found by reading the installed package):

- **VCI** — `vnstock/explorer/vci/company.py:651` `Company.news()` calls
  `GET https://iq.vietcap.com.vn/api/iq-insight-service/v1/news?ticker={symbol}&fromDate=...&toDate=...&languageId=1&page=0&size=50`
  (`_fetch_news`, line 160; base URL in `explorer/vci/const.py`).
- **KBS** — `vnstock/explorer/kbs/company.py:659` `Company.news(page, page_size)` calls
  `GET https://kbbuddywts.kbsec.com.vn/iis-server/investment/stockinfo/news/{symbol}`
  (base URL in `explorer/kbs/const.py`).

No broker API key is needed; vnstock's own quota layer meters the calls.

### Live test (STB, 2026-08-10)

- **VCI**: returned **50 items**, newest `2026-08-07T16:37:32` ("STB: Thông báo về
  tỷ lệ sở hữu nước ngoài tối đa") — 3 days old, i.e. current up to the last
  disclosure. Columns include `news_title`, `news_short_content`,
  `news_full_content`, `news_source`, `news_source_link`, `news_image_url`,
  `public_date`. Mix of exchange disclosures and press articles, in Vietnamese.
- **KBS**: returned only **1 item** for STB despite `page_size=5`
  (newest `2026-08-03`), with sparse columns (`title`, `publish_time`, `url`).
  Not reliable as a primary feed.

### Per-symbol filtering

Native: the ticker is a query parameter on both backends. Works for any
HOSE/HNX/UPCOM symbol vnstock resolves.

### Freshness

VCI carries same-week items with intraday timestamps; suitable for a "recent
news" section refreshed a few times per day.

### Quota / cost

Free, but it draws from the same vnstock allowance the whole API shares:
**20 requests/min guest tier, 60 with `VNSTOCK_API_KEY`**
(`apps/api/src/stocks/providers/vnstock_provider.py:54-57`). One news call per
symbol, so news fetching must be cached/paced like the other vnstock jobs (heavy
jobs are already off by default for this reason, per `CLAUDE.md`). For v1,
fetch-on-demand with a Redis TTL of hours is enough — news per symbol changes a
few times a week, not per minute.

### Legal workability

vnstock is open source but proxies undocumented broker APIs (Vietcap IQ, KB
Securities). This is the same legal posture as the price/fundamental data the
platform already serves through vnstock — no new exposure class, but no SLA and
endpoints can change without notice.

### Repo integration note

`CompanyService.get_company_news()` already exists
(`apps/api/src/stocks/company/service.py:261`) but (a) **no router exposes it** —
it has no callers — and (b) its column mapping predates vnstock 4.x/VCI: it reads
`title` / `publish_date` / `source` / `price` / `price_change_ratio`, while VCI
returns `news_title` / `public_date` / `news_source` and no price columns, so as
written it would emit items with empty titles. Wiring a v1 news endpoint means
fixing this mapping and adding a route, not building from scratch.

## 2. CafeF — best non-vnstock option: per-symbol, no auth, permissive robots

- **Category RSS (not per-symbol):** `GET https://cafef.vn/thi-truong-chung-khoan.rss`
  → HTTP 200, `application/rss+xml`, newest item minutes old
  (`pubDate Mon, 10 Aug 26 18:39:00 +0700`). Market-wide only; the RSS index
  (`https://cafef.vn/index.rss`) lists category feeds and **no per-symbol RSS**.
- **Per-symbol Ajax endpoint (the useful one):** the historical
  `s.cafef.vn/Ajax/Events_RelatedNews_New.aspx` 301-redirects to
  `https://cafef.vn/du-lieu/ajax/events_relatednews_new.aspx`. Verified working:
  `GET https://cafef.vn/du-lieu/ajax/events_relatednews_new.aspx?symbol=STB&floorID=0&configID=0&PageIndex=1&PageSize=10&Type=2`
  → HTTP 200, `text/html`, no auth, `Access-Control-Allow-Origin: *`.
  Returns a `<ul>` of STB items with dates, e.g.
  `07/08/2026 16:37 — "STB: Thông báo về tỷ lệ sở hữu nước ngoài tối đa"`,
  `31/07/2026 16:18 — "STB: Giải trình BCTC riêng và hợp nhất Quý 2 năm 2026"`.
  `Type=2` = disclosures + related news; `PageIndex`/`PageSize` paginate.
- **Caveat:** the response is an HTML fragment (no JSON variant found) — you parse
  `<span class="timeTitle">` + anchor tags; dates are `dd/MM/yyyy HH:mm`. Undocumented,
  so it can change shape without notice.
- **Legal:** `https://cafef.vn/robots.txt` is `User-agent: * / Allow: /` (nothing
  disallowed; Google-News sitemaps advertised). **No terms-of-use page exists** —
  the footer links only a privacy policy; content is © 2007–2026 VCCorp. No explicit
  prohibition on reuse, but the articles themselves are copyrighted press content —
  fine for headline + link + date, not for republishing full text.

## 3. Vietstock — per-symbol only via HTML scraping; JSON API effectively closed

- **Category RSS:** `https://vietstock.vn/rss` lists ~40 category feeds (e.g.
  `https://vietstock.vn/830/chung-khoan/co-phieu.rss`, HTTP 200, fresh same-day
  items). **No per-symbol RSS exists.**
- **`POST https://finance.vietstock.vn/data/getnewsbycode`:** reachable, but needs
  the anti-CSRF pair (cookie + form token harvested from
  `https://finance.vietstock.vn/STB/tin-moi-nhat.htm`). Even with valid tokens it
  returned **HTTP 200 with an empty `[]` body** for every parameter combination
  tried; the param contract is not visible in the page's JS bundle. Not usable
  without reverse-engineering a full browser session.
- **What works:** the per-symbol news list is server-rendered inside
  `https://finance.vietstock.vn/STB/tin-moi-nhat.htm` (real STB items with source
  tags, e.g. HOSE / FILI, dated 07/08/2026 and 04/08/2026) — i.e. HTML scraping.
- **Legal:** robots.txt on both hosts disallows only assets/admin paths, not
  content. A terms page exists (`https://vietstock.vn/thoa-thuan-su-dung-dich-vu.htm`,
  HTTP 200) and must be reviewed before productionizing.
- **Assessment:** highest implementation and maintenance cost for no advantage over
  CafeF/vnstock. Skip.

## 4. Fireant — technically the cleanest, legally blocked

- `GET https://restv2.fireant.vn/posts?symbol=STB&type=1&offset=0&limit=10` without
  auth → **HTTP 401**. With the long-lived public JWT still embedded in the
  fireant.vn web app (decoded: `iss=accounts.fireant.vn`, exp 2029-11-17, scopes
  `posts-read`, `symbols-read`, …) → HTTP 200 with a clean JSON array: `title`,
  `description`, `date`, `postSource` (HSX, press), `taggedSymbols` incl. `STB`,
  and attached disclosure PDFs. Newest item `2026-08-09T22:35:00+07:00` — one day old.
- **Legal — hard blocker:** the terms (`https://accounts.fireant.vn/termsofuse`)
  state verbatim: *"Người sử dụng không được phép xây dựng mô hình kinh doanh sử
  dụng các nội dung cho dù là có hoặc không vì lợi nhuận."* ("Users may not build a
  business model using the content, whether or not for profit.") Additionally
  `https://fireant.vn/robots.txt` explicitly disallows AI crawlers (ClaudeBot,
  GPTBot, CCBot, …), and the integration would depend on a token scraped from
  their web bundle that can be rotated at any time. **Do not use.**

## 5. Google News RSS — freshest and broadest, legally blocked for a product

- `GET https://news.google.com/rss/search?q=%22STB%22%20OR%20%22Sacombank%22&hl=vi&gl=VN&ceid=VN:vi`
  → HTTP 200, **100 items from 35 distinct sources**, newest published today
  (2026-08-10T10:01:00Z). No API key, no documented quota (silent IP throttling
  applies).
- **Per-symbol filtering is keyword-based only** — false positives for acronym
  tickers like STB and no ticker field; needs client-side filtering. All links are
  Google redirect URLs (`news.google.com/rss/articles/CBMi...`) that must be
  resolved to the publisher URL.
- **Legal — hard blocker:** the feed's own `<copyright>` element states it is
  *"made available solely for the purpose of rendering Google News results within
  a personal feed reader for personal, non-commercial use. Any other use of the
  feed is expressly prohibited."* **Do not use in the product.**

## 6. FiinQuant / FiinQuantX — no news capability

Added to the evaluation at the user's request (its quota is more generous than
vnstock's in many cases; the repo already logs in through
`apps/api/src/stocks/providers/fiinquant.py`).

- **Installed FiinQuantX 0.1.67 has no news API surface.** A case-insensitive
  search for "news" across the installed package returns nothing; the typed
  surface in `FiinQuant.pyi` is exclusively market/quant data
  (`Fetch_Trading_Data`, `Trading_Data_Stream`, `FundamentalAnalysis`,
  `StockScreening`, `OrderBook`, `MarketBreadth`, `BidAsk`, `TickerList`, …).
- **The current official docs confirm it:** the function catalog at
  `https://docs.fiinquant.vn/fiinquant-en/function-and-formula` covers real-time /
  historical trading data, order book, indicators, support data and index
  constituents — **no news or per-ticker events function exists**. Distribution is
  a self-hosted pip index (`https://fiinquant.github.io/fiinquantx/simple`), auth
  is username/password login, pricing/quota is not published.
- **Assessment:** generous quota does not help — FiinQuant simply does not serve
  the news use case. Keep it for market/valuation data only.

## Verdict: per-symbol news is viable for v1

**Yes — build v1 on vnstock's VCI `company.news()`**:

1. It is already a dependency and already half-integrated:
   `CompanyService.get_company_news()` exists; v1 work is fixing its VCI column
   mapping (`news_title`/`public_date`/`news_source`) and exposing a route.
2. The data is good: 50 per-symbol items with titles, snippets, full content,
   original-source links and intraday timestamps; fresh to the last disclosure.
3. Quota fits if cached: one request per symbol against the shared 20/60 rpm
   vnstock allowance, so serve from a Redis cache with a multi-hour TTL and fetch
   on demand (do not bulk-poll the whole universe on a schedule in v1).
4. Legal posture is unchanged: the platform already relies on the same vnstock →
   broker-API channel for prices and fundamentals.

**Fallback / enrichment (optional, post-v1):** CafeF's
`du-lieu/ajax/events_relatednews_new.aspx` — the only other per-symbol source with
no auth and no prohibitive terms; costs an HTML-fragment parser.

**Rejected:** Fireant (ToS forbids commercial reuse; scraped token), Google News
RSS (personal non-commercial only; keyword matching), Vietstock (JSON API returns
empty even with CSRF tokens; scraping-only, ToS review needed), FiinQuant (no news
capability).
