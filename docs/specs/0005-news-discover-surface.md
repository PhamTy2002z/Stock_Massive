# Product specification — the News Discover surface

A Perplexity-Discover-style news surface inside the single-screen shell: a
market-wide feed, an in-shell reading view, and a sources panel — built from
the VCI company-news lane the platform already trusts. This spec records the
layout decisions taken from the owner's reference screenshots (2026-08-17) and
scopes what v1 serves honestly versus what the reference renders that this
system cannot yet claim.

Read with:

- [`0002-alpha-desk-product.md`](0002-alpha-desk-product.md) — the shell this
  surface plugs into. The three-region layout, the view-as-state rule and the
  inspector mechanics all stand; this spec adds a view and an inspector tab,
  it does not add a route.
- [`0004-general-expert-answer-bar.md`](0004-general-expert-answer-bar.md) —
  D9/W5 make news part of the answer product. This surface is the browsing
  counterpart: the same cleared sources, presented as a destination.
- `docs/research/news-sources.md` — the source-clearance decision this spec
  inherits. VCI (and exchange disclosures carried through it) stay the only
  provider; nothing here widens that set.

## 1. What the reference does, and what we keep

The reference product (rebo.ai.vn, screenshots captured 2026-08-17) is an
AI-news reader: a discover feed, an article page with AI-composed prose,
per-claim citation chips, a key-takeaways box, and a slide-in panel listing
the sources behind the article.

Decisions:

| # | Decision | Choice |
| --- | --- | --- |
| N1 | Placement | News is a fourth `ShellView` (`"news"`), entered from a sidebar nav row ("Tin tức"), never a route. Switching to it and back must lose neither the composer draft nor the article being read. |
| N2 | Article page | In-view reading state (`newsArticle` in the shell reducer), not a page. "Trở về" is a state transition; scroll and feed stay warm. |
| N3 | Sources panel | The reference's slide-in sources list maps onto the existing inspector: a third `InspectorTab` (`"news"`), with drag-resize and wide-toggle inherited for free. |
| N4 | Honesty bar | v1 renders what the source actually serves: one source per item, no AI-composed article body, no per-claim citation chips, no "15 nguồn" aggregation. The layout keeps the reference's shape; the labels never claim synthesis that did not happen. |
| N4a | Feed source (revised 2026-08-17) | The market feed is **CafeF category RSS**, not VCI. VCI serves no prose — measured 0/50 non-null on every content, source and link column across FPT/STB/VNM — so the reader had a headline and nothing else. VCI stays as a per-symbol **disclosure** list in the rail, labelled as disclosures rather than as news. See the correction section in `docs/research/news-sources.md`. |
| N4b | Article text (revised 2026-08-19) | The reader shows the article's **full body**, extracted from CafeF's own page when the reader opens it, above a link to the original. This reverses the original N4b — "full text is never fetched or stored" — at the product owner's explicit direction after the constraint was restated. The copyright position is unchanged and is what shapes the implementation: the body is fetched per read and cached, never stored in the database; `robots.txt` is `Allow: /`; every reading surface still ends by attributing the extract to CafeF and linking the original. Feeds cannot supply this — CafeF's RSS carries no `content:encoded`, and neither does any Vietnamese finance feed measured beside it (VnExpress, Vietstock, Thanh Niên, Vietnambiz, VnEconomy: 0/5). See `docs/research/news-sources.md`. |
| N4c | Facets | The reference's editorial facet row becomes real: eight slugs served by the API — `moi-nhat`, `chung-khoan`, `kinh-te`, `tai-chinh`, `bat-dong-san`, `doanh-nghiep`, `cong-nghe`, `the-gioi` — each backed by a CafeF category feed whose *contents* were checked, not just its name. Our slugs are the contract; CafeF's paths stay an implementation detail. Two of the reference's labels are dropped: "Đọc nhiều" needs a read-count no source publishes, and CafeF has no retail feed. Chứng khoán and Doanh nghiệp take those slots — on a market platform they are the facets a reader came for. |
| N5 | Rail widget | The reference's weather widget becomes a market widget (VNINDEX + indices) — this is a market product; weather is not its context. |
| N6 | Data budget | The feed no longer spends vnstock quota at all: CafeF is plain HTTP, one request per category, behind a Redis response cache (300s trading / 900s off-hours, 24h stale). An article body is one further request, made only when a reader opens that article and cached for 24h — a rebuild still costs one request, not one per headline. The rail's disclosure list is the only vnstock call on this surface, one per symbol, on the existing per-symbol cache. |
| N7 | AI layer | Key-takeaways boxes, citation chips and composed articles are explicitly deferred to the agent lane (spec 0004 W5/W6). When they land, they enter this surface as clearly-labelled agent output, not as provider prose restyled. |

## 2. Layout, from the screenshots

### Feed (default state of the view)

Two columns inside the main region (`max-w-[1180px]`, rail hidden below `xl`):

1. **Pill tab row** — the seven category slugs of N4c, served by
   `GET /stocks/news/categories`. Selecting one refetches that facet rather than
   filtering in the client: each is its own upstream feed.
2. **Hero block** — a narrow left column stacking two small cards beside one
   large hero card (16:9 image, serif headline ~1.9rem, two-line summary,
   source line). Items 0–2 of the feed.
3. **Card row** — four equal cards (items 3–6).
4. **Stream** — remaining items as rows: date gutter on the left (shown once
   per date group), title + summary in the middle, fixed thumbnail on the
   right.

Right rail (sticky): market widget (N5), "Mới cập nhật" (five most recent), and
**"Công bố thông tin"** — the VCI disclosure list for the selected symbol (N4a),
carrying a note that these are company filings rather than press articles. The
two sources stay visibly distinct rather than blended into one list.

The repeated identity unit is the **source line** (source pill + symbol or
category +
date). The reference's favicon-cluster-plus-"15 nguồn" is a multi-source
aggregation claim; ours names the single provider per item (N4).

### Reader

A single centered reading column (~720px) rendered in place of the feed:
serif headline (~2.1rem, Newsreader — already the system's one serif),
Vietnamese long-form date, source line, category label (or a clickable symbol
chip when the item carries one), the summary set as the lead, hero image, then
the article's own body — paragraphs, subheadings, lists and inline photos with
their captions, drawn from the block tree the API sends (N4b). The lead is not
printed twice: CafeF repeats its standfirst inside the body on many articles,
and `articleBody` in `lib/news.ts` drops the copy. The body is a second request
behind the one that drew this screen, so the column is readable while it lands
and says which part is still coming; if it refuses, the summary stands and the
retry is scoped to the body rather than to the feed. It ends at a link to the
original, labelled as attribution once the body is present. Then **Bài liên
quan** — three same-category cards. Top bar: back (state transition),
external "Bài gốc" link, and "Nguồn" opening the inspector tab.

### Sources tab (inspector)

Header "Nguồn tham khảo"; the open article's own source entry first (source,
date, title, snippet, link to the original), then "Tin khác cùng chủ đề" — up
to eight same-category feed entries, each clickable to swap the open article.
The tab button renders only while an article is open.

## 3. Serving path

Four endpoints. Three read CafeF over plain HTTP; the per-symbol route is the
vnstock lane, and all of them sit behind `TradingHoursCache` with stale
fallback, mirroring the company router's discipline:

- `GET /stocks/news/feed?category={slug}` — one CafeF category feed,
  `heavy_rate_limit`, TTL 300s trading / 900s off-hours, stale 24h, cache key
  per category. Sorted newest-first, capped at 120 items. An unknown slug is
  a 400 before the cache is touched. A CafeF outage raises `CafeFUnavailable`
  → 503, and the cache serves the last good feed rather than nothing.
- `GET /stocks/news/categories` — the slug registry (N4c). No network, so the
  pill row never waits on a feed to learn what the facets are.
- `GET /stocks/news/article?url={url}` — one article's body as blocks in
  reading order, `heavy_rate_limit`, TTL 24h both sides (a published article
  does not go stale on the trading clock), stale 7d, cache key per URL. The
  URL comes from the client, so `is_cafef_article_url` gates it on scheme,
  host and CafeF's `.chn` suffix *before* the cache is touched — without that
  the route is an open proxy to any address a caller names. Extraction reads
  the allowlisted blocks directly inside `div.detail-content`, which is what
  separates prose from the widgets nested in the same container; a body under
  200 characters is reported as `CafeFUnavailable` rather than served, so a
  renamed container fails loudly instead of shipping two sentences.
- `GET /stocks/{symbol}/news` — the VCI disclosure lane,
  `standard_rate_limit`, TTL 900s/3600s, stale 7d. Wires the previously
  unreachable `CompanyService.get_company_news`, whose row mapping is
  rewritten for the VCI frame (the old mapping read TCBS-era column names and
  would have served empty fields).

`NewsItem` carries `summary`, `content`, `url`, `image_url`, `category` — all
optional. Its `id` is a **string**: VCI's `id` column is a hex digest and
CafeF's key is a slug fragment, so an integer id forced a fallback to the
row's position, which silently re-pointed an open article whenever the feed
shifted. The feed item adds an optional `symbol` — a press article belongs to
a category, not to a ticker.

This is a Collector-free path on purpose: news is provider prose served
through response caches, not a Capability in the store. If news ever needs a
data age, provenance in the Evidence Manifest, or agent tools reading it from
the store, that is the moment to revisit — the same trigger the company
router's docstring names.

## 4. Out of scope for v1

- Read-counts ("Đọc nhiều nhất") and any ranking beyond recency — no signal
  exists to back them. (Editorial categories are now served — see N4c.)
- **Per-symbol press news.** CafeF's RSS is category-scoped; the feed cannot
  answer "news about VCB". The rail's disclosure list is not a substitute, and
  the gap is named in `docs/research/news-sources.md` as the next thing to
  research.
- Fetching or storing full article text (N4b).
- AI-composed article bodies, key-takeaways boxes, per-claim citation chips
  (N7).
- Watchlist-scoped feeds and per-user personalization.
- Push/streaming updates; the feed refreshes on the query cache's schedule.

## 5. Eval gate

This surface touches UI, two provider-backed REST endpoints and one service
mapping. It does not touch the System Prompt Contract, tool schemas, the
Signal Registry, the Analysis Field Profile, `llm_model_*`, the agent loop or
the Recommendation Validator — per `docs/agents/eval-battery.md` the PR
carries no Eval Report. `src/agent/tools/news.py` is deliberately untouched.
