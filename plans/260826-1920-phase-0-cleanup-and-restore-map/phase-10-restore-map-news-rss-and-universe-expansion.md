---
title: "Phase 10: Restore map — news RSS and universe expansion"
status: reference-only
---

# Phase 10: Restore map — news RSS & universe expansion

## Overview

**Reference-only.** Hai việc còn lại của restore map: (a) news feed thay
CafeF scraping đã rip bằng RSS chính thức + web_search fallback, (b) mở
rộng Universe từ 30 mã declared ra toàn HOSE+HNX theo mô hình
`Universe.declared` + `Universe.market` đã đề nghị ở Phase 8.

## Brief origin

- **News (catalyst / event)**:
  - `docs/Text.txt` line 158 ("Khối ngoại mua hay bán"), line 350 ("Foreign
    investors net selling"), line 411 ("Restructuring story remains"),
    line 493 ("Completion of restructuring", "Resolution of VAMC-related")
- **Universe rộng**:
  - `docs/Text.txt` line 178-185 (Universe: HOSE + HNX ~1.200 doanh nghiệp)
  - Peer comparison Bank sector cần MBB, TCB, CTG… không thuộc 30 declared

## News — nguồn thay CafeF

- **CafeF scraping đã rip** (vi phạm ToS)
- Thay bằng:
  - **RSS chính thức**: HOSE (`hsx.vn/rss`), HNX (`hnx.vn/rss`), Vietstock,
    NDH, CafeF **RSS** (khác với scraping HTML — cần verify điều khoản)
  - **Agent web_search fallback**: khi câu hỏi cần catalyst context, agent
    dùng `web_search` + `fetch_url` — cost cao hơn nhưng không cần thu thập
    trước
- Không cần Redis cache trước — RSS đủ nhẹ để agent fetch on-demand

## Universe — mô hình mở rộng

- **`Universe.declared`**: 30 mã ưu tiên (hiện tại) — có tất cả signal
  fields, có test coverage, có allocation LLM budget
- **`Universe.market`**: toàn bộ mã từ `listing_roster` (~1.600 HOSE + HNX +
  UPCOM). Chỉ có signal fields tối thiểu (bar_daily, 52w, sector). Không có
  intraday bucket, foreign flow chi tiết, opportunity score chi tiết
- **`Universe.contains(symbol, scope="declared")`** — API mới, scope
  parameter mặc định "declared" (giữ tương thích lane chat)
- Agent tool `get_field(symbol, field)`:
  - Nếu `field` thuộc "declared-only" (intraday_bucket, foreign_flow_net_20d)
    → refuse với `symbol_not_in_declared_scope`
  - Nếu `field` thuộc "market" (bar_daily, 52w, sector, earnings_absolute_qtr)
    → OK cho mọi mã

## Module cần restore / mở rộng

- `src/stocks/news/*` — restore nhẹ, chỉ RSS parser + storage
- `src/stocks/universe.py` — thêm `scope` argument + `Universe.market`
  membership
- `src/stocks/listing_roster.py` — mở rộng từ mini (identity-only) sang full
  (exchange, listing_date, sector)
- Table `news_item` với source + rss_link + fetched_at + relevant_symbols[]
- Table `listing_roster` (đã có mini, mở rộng column)

## Config setting mới

- `rss_feeds: list[dict]` — list of `{name, url, source_type}`
- `rss_poll_interval_seconds: int` (default 900 = 15m)

## Việc PHẢI KHÔNG làm

- Không build News React component
- Không build News agent tool cho tới khi có canvas
- Không đưa RSS content vào untrusted-tool-result wrap — RSS là dữ liệu
  cấu trúc (title + link + pubDate), khác với web fetch. Nhưng nếu agent
  `fetch_url` bài viết chi tiết, wrap vẫn có

## Placeholder success criteria

- ≥ 4 RSS source hoạt động, dedup theo GUID
- `Universe.declared` giữ 30 mã, `Universe.market` load ≥ 1.500 mã từ
  listing_roster
- Agent tool refuse chính xác khi mã ngoài declared cho field declared-only
- Test 940 vẫn xanh (bổ sung test cho scope logic)

## Risk

- **RSS availability**: HSX/HNX RSS có thể không stable → cần fallback
  Vietstock/NDH; đừng phụ thuộc 1 nguồn duy nhất
- **License RSS**: đọc lại điều khoản mỗi nguồn — RSS thường được phép,
  nhưng full-text content thì không
- **Universe drift**: khi listing_roster update (delisting, new listing),
  cần cron sync; không hard-code
