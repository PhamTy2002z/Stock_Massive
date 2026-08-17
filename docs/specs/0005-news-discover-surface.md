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
| N4 | Honesty bar | v1 renders what VCI actually serves: one source per item, provider prose, no AI-composed article body, no per-claim citation chips, no "15 nguồn" aggregation. The layout keeps the reference's shape; the labels never claim synthesis that did not happen. |
| N5 | Rail widget | The reference's weather widget becomes a market widget (VNINDEX + indices) — this is a market product; weather is not its context. |
| N6 | Data budget | Free vnstock tier stands (spec 0004 D6). The feed aggregates VN30 only, capped at 12 symbols per rebuild, behind a Redis response cache with stale fallback — one rebuild is at most 12 provider calls, and a quota refusal mid-rebuild serves the partial feed rather than a blank screen. |
| N7 | AI layer | Key-takeaways boxes, citation chips and composed articles are explicitly deferred to the agent lane (spec 0004 W5/W6). When they land, they enter this surface as clearly-labelled agent output, not as provider prose restyled. |

## 2. Layout, from the screenshots

### Feed (default state of the view)

Two columns inside the main region (`max-w-[1180px]`, rail hidden below `xl`):

1. **Pill tab row** — "Mới nhất" plus one pill per contributing symbol
   (top-by-count, max 6). Client-side filter; the reference's editorial
   categories (Kinh tế, Tài chính…) require a taxonomy no endpoint serves,
   so symbols are the honest v1 facets.
2. **Hero block** — a narrow left column stacking two small cards beside one
   large hero card (16:9 image, serif headline ~1.9rem, two-line summary,
   source line). Items 0–2 of the feed.
3. **Card row** — four equal cards (items 3–6).
4. **Stream** — remaining items as rows: date gutter on the left (shown once
   per date group), title + summary in the middle, fixed thumbnail on the
   right.

Right rail (sticky): market widget (N5), "Mới cập nhật" (five most recent),
"Theo mã" symbol chips that drive the same filter as the pill row.

The repeated identity unit is the **source line** (source pill + symbol +
date). The reference's favicon-cluster-plus-"15 nguồn" is a multi-source
aggregation claim; ours names the single provider per item (N4).

### Reader

A single centered reading column (~720px) rendered in place of the feed:
serif headline (~2.1rem, Newsreader — already the system's one serif),
Vietnamese long-form date, source line, clickable symbol chip (opens the
symbol inspector), lead paragraph, hero image, provider prose split into
paragraphs, then **Bài liên quan** — three same-symbol cards. Top bar: back
(state transition), external "Bài gốc" link, and "Nguồn" opening the
inspector tab.

### Sources tab (inspector)

Header "Nguồn tham khảo"; the open article's own source entry first (source,
date, title, snippet, external link), then "Tin khác về {symbol}" — up to
eight same-symbol feed entries, each clickable to swap the open article. The
tab button renders only while an article is open.

## 3. Serving path

Two provider-backed endpoints, both behind `TradingHoursCache` with stale
fallback, mirroring the company router's discipline:

- `GET /stocks/news/feed` — VN30 aggregation (N6), `heavy_rate_limit`,
  TTL 900s trading / 3600s off-hours, stale 24h. Sorted newest-first,
  capped at 120 items. A symbol whose fetch fails is skipped and absent from
  the response's `symbols`; a quota refusal with nothing gathered maps to the
  standard 503.
- `GET /stocks/{symbol}/news` — the per-symbol lane, `standard_rate_limit`,
  same TTLs, stale 7d. Wires the previously-unreachable
  `CompanyService.get_company_news`, whose row mapping is rewritten for the
  VCI frame (the old mapping read TCBS-era column names and would have served
  empty fields).

`NewsItem` widens with `summary`, `content` (HTML-stripped plain text),
`url`, `image_url` — all optional, all provider-derived. The feed item adds
`symbol`.

This is a Collector-free path on purpose: news is provider prose served
through response caches, not a Capability in the store. If news ever needs a
data age, provenance in the Evidence Manifest, or agent tools reading it from
the store, that is the moment to revisit — the same trigger the company
router's docstring names.

## 4. Out of scope for v1

- Editorial categories, read-counts ("Đọc nhiều nhất") and any ranking beyond
  recency — no signal exists to back them.
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
