# Research — Những Material Change nào store hiện tại chứng minh được

**Ngày kiểm tra:** 2026-08-30 (Asia/Saigon)

**Phạm vi:** store/runtime hiện tại, cohort khai báo 30 mã; chỉ đọc, không đổi schema hay dữ liệu.

**Câu hỏi:** gia đình Material Change nào đủ dữ liệu, semantics PIT, provenance và failure mode để làm đầu vào xác định cho Delta Inbox?

## Kết luận ngắn

Store hiện tại chứng minh tốt nhất hai gia đình hẹp: **(1) giá/khối lượng/EOD microstructure theo mã** và **(2) market regime dựa riêng trên VNINDEX EOD**. Đây là tập V1 nhỏ nhất khả thi để thử Delta Inbox: detector xác định tạo delta sau phiên đóng cửa; AI chỉ diễn giải delta cùng Thesis. Việc chọn phạm vi sản phẩm cuối cùng vẫn là quyết định riêng, không phải kết luận của research này.

Không nên gọi fundamental/filing, valuation, foreign flow/positioning, news, sector regime hay peer/cross-section là Material Change PIT ở V1. Một phần phép tính của chúng chạy được ở snapshot hiện tại, nhưng thiếu publication/versioned-universe/event store hoặc dữ liệu gốc. Corporate action là **context/falsifier có cấu trúc**, chưa phải news/event detector tổng quát.

## Phương pháp và trạng thái live

- Đối chiếu contract: module xác định phải sở hữu PIT/freshness, calculation và provenance; khi thiếu bằng chứng phải trả blocker thay vì tự hoàn tất (`docs/Harness/investment-intelligence-contract.md:27-35`, `:77-113`, `:156-175`).
- Kiểm tra code path thực thi của query/signals/studies, không suy từ tên bảng. Query tool chỉ đọc sáu nguồn được khai báo và gắn `source`, `as_of`, health/refusal (`apps/api/src/agent/tools/query.py:137-145`, `:206-277`, `:375-420`). Signal serving là gateway có window/refusal (`apps/api/src/stocks/signals/serving.py:41-131`).
- Chạy SQL trong transaction `READ ONLY` trên Postgres của runtime và smoke 33 signal fields tại `as_of=2026-08-28`; chi tiết [Q1–Q4, E1](#bằng-chứng-read-only). Không log DSN hay credential.
- Các số cũ đã được kiểm lại: 302.528 statement lines vẫn đúng; “intraday 4 mã” không còn đúng — hiện là 31 mã; foreign flow vẫn bằng không ở đường thực thi. Số cũ nằm tại `plans/260829-2304-signal-desk-analysis-compiler/plan.md:83-89`.

## Ma trận năng lực

| Gia đình | Owner thực thi / asset tái dùng | Coverage live | Freshness / `as_of` | Baseline hoặc detector xác định khả dĩ | Provenance | Failure/refusal hiện có | Blocker cho Material Change PIT |
|---|---|---|---|---|---|---|---|
| **Price / volume / microstructure** | `bar_daily`, `intraday_15m`; signal gateway và registry 33 fields (`apps/api/src/agent/tools/query.py:793-898`; `apps/api/src/stocks/signals/registry.py:1383-1417`) | Daily: 813.107 dòng/1.523 mã, cohort 30/30 mới nhất 2026-08-28; 29/30 có ≥250 dòng. Intraday: 122.880 dòng/31 mã, cohort 30/30 mới nhất 2026-08-28 [Q1–Q2]. Smoke: volatility/ADTV/Amihud/mean-reversion/realized-vol/price-zone 30/30; các field 250-session 28/30 [E1]. | Trading day lấy từ VNINDEX, chỉ phiên settled/closed; operational stale sau 4 ngày (`apps/api/src/stocks/trading_day.py:1-40`, `:69-128`, `:152-212`). | Delta phiên gần nhất so với phiên trước; return/volume surprise so median/ADTV; volatility-regime z (ngưỡng hiện hữu 3,0); limit-band/volume-basis quality break (`apps/api/src/stocks/signals/registry.py:151-180`, `:514-748`). | Bar giữ source, source-row, observed-at, adjustment metadata (`apps/api/src/stocks/models.py:402-454`); query trả provenance/as-of. | `missing_session`, `insufficient_history`, `volume_basis_break`, `price_off_tick_grid`; exact trailing days không tự pad. Smoke thấy 2 mã thiếu 250-session và 14 mã off-tick ở band pressure [E1]. | Chưa có owner lưu “previous scan”/delta và chưa có proactive scan job; phải xây orchestration mới. Intraday không cần cho V1 post-close, chỉ là asset tái dùng sau này. |
| **Fundamental / filing** | Long-form statement/ratio query; earnings fields và financial scan job (`apps/api/src/agent/tools/query.py:901-1071`; `apps/api/src/stocks/signals/earnings.py:79-112`; `apps/api/src/stocks/financial_scan_job.py:119-183`) | 302.528 statement lines/1.235 mã; 2026-Q2 có 1.137 mã và cohort 30/30. Ratio: 4.152 dòng/30 mã, 2025-Q4–2026-Q2 [Q3]. Smoke: net-profit YoY 30/30; EPS YoY 19/30; gross-profit trend 17/30 [E1]. | `as_of` hiện là period end/quarter, không phải ngày công bố. Module tự ghi rõ không có filing lag/publication time (`apps/api/src/stocks/signals/earnings.py:46-54`). | Sau khi có publication ledger: so filing mới với filing trước, YoY/TTM surprise và restatement delta. Phép tính YoY hiện tại là asset tái dùng, chưa phải detector PIT. | Dòng có period/source/observed-at (`apps/api/src/stocks/models.py:460-564`). | Thiếu statement line trả refusal; smoke có 11 EPS và 13 gross-profit thiếu [E1]. | **Loại khỏi strict V1:** không có publication time; upsert ghi đè value/source/observed nên không giữ lịch sử restatement (`apps/api/src/stocks/financial/store.py:43-72`, `:139-161`). Dùng quarter-end làm effective tạo lookahead. |
| **Valuation** | Không còn valuation reader. Asset gần nhất là factor percentiles từ fundamental snapshots + derived market cap (`apps/api/src/stocks/signals/cross_sectional.py:137-172`; `apps/api/src/stocks/signals/bars.py:1192-1221`). | Không có capability `valuation` trong provider snapshots [Q4]. Bốn factor percentiles chạy 30/30 tại snapshot hiện tại [E1], nhưng đó không chứng minh PIT history. | Fundamental snapshots dùng `period_end` làm effective; roster/peer set là trạng thái hiện tại (`apps/api/src/stocks/signals/fundamentals.py:61-110`; `apps/api/src/stocks/models.py:197-202`). | Candidate sau khi sửa PIT: percentile/rerating delta so versioned peer cohort và market-cap tại cùng as-of. | Snapshot có capability/symbol/source/effective/observed/schema/payload (`apps/api/src/stocks/models.py:22-61`). | Relative-strength comparator chủ động trả unavailable vì rolling estimator chưa viết (`apps/api/src/stocks/signals/cross_sectional.py:298-329`). | **Loại khỏi strict V1:** valuation surface cũ đã rip; current percentile thiếu publication-time và versioned peer universe. |
| **Flow / positioning** | Ba foreign-flow fields + foreign-room reference; không có portfolio/position ledger (`apps/api/src/stocks/signals/registry.py:1000-1189`; `plans/reports/brainstorm-260823-2212-portfolio-intelligence.md:42-50`). | Ba foreign-flow fields từ chối 30/30 với `foreign_flow_not_stored`; foreign-room 29/30 chạy được nhưng 1 degraded/exhausted [E1]. `realtime_events` có 0 dòng [Q4]. | Foreign-room là observation hiện có; không thay thế chuỗi buy/sell flow. | Candidate chỉ sau khi có event history: net foreign-flow surprise/persistence so trailing window và room constraint. | Room trả state, available share, as-of (`apps/api/src/stocks/signals/reference.py:77-138`). | Refusal được khai báo rõ: flow/room not stored hoặc room exhausted (`apps/api/src/stocks/signals/issues.py:221-236`). | **Loại khỏi V1:** không có chuỗi foreign/proprietary flow, không có user position/portfolio ledger; room đơn lẻ không chứng minh positioning change. |
| **Market / sector regime** | VNINDEX trong `bar_daily`; current listing roster có ICB (`apps/api/src/stocks/signals/cross_sectional.py:137-172`; `apps/api/src/stocks/models.py:188-232`). | VNINDEX có 3.992 phiên tới 2026-08-28 [Q1]. Roster có 1.751 dòng, 1.523 listed, 19 ICB codes [Q4]. | VNINDEX dùng cùng closed-session contract. ICB roster chỉ current state, không có historical versions. | **Market V1:** VNINDEX return/trend/realized-vol/volatility-regime delta. **Sector candidate sau này:** breadth/relative-return trên membership versioned. | Bar provenance đầy đủ như hàng price; roster có observed-at nhưng không lịch sử membership. | Missing/stale VNINDEX làm calendar/market baseline fail closed. | Chỉ market-wide regime đủ cho V1. **Sector regime bị loại** vì không có sector index/breadth baseline và membership lịch sử; dùng roster hiện tại gây survivorship/lookahead. |
| **News / event** | Corporate-actions query là structured event asset; generic web search/fetch chỉ on-demand (`apps/api/src/agent/tools/query.py:1122-1181`; `apps/api/src/agent/tools/web.py:409-527`, `:643-669`). | Corporate actions: 284 dòng/29 mã cohort; 66 confirmed, 218 unconfirmed, 50 undated [Q3]. Không thấy persisted article/news store; realtime-events 0 [Q4]. | Query loại action undated; event date có nhưng publication time/newly-announced semantics không đầy đủ. Web `published_at` tùy chọn và không phải approved deterministic store. | Corporate action effective-date/change-since-last-scan có thể làm context/falsifier. General-news detector cần ingest → entity link → dedup → approved-source policy → event/publication time. | CorporateAction có source/observed/confirmation metadata (`apps/api/src/stocks/models.py:239-349`). | Undated actions bị loại và trả refusal; news fields cố ý unavailable đến khi approved-source news được persist (`apps/api/src/alpha/field_profile.py:277-294`). | **Loại general news/event khỏi V1.** Corporate action không nên được nâng thành một family độc lập trước khi có publication/version semantics; chỉ dùng context với cờ confidence. |
| **Peer / cross-section** | Cross-sectional registry: momentum/trend, factor percentile; Universe khai báo hiện tại (`apps/api/src/stocks/signals/cross_sectional.py:137-329`; `apps/api/src/stocks/universe.py:208-243`). | Current cohort 30; momentum/trend 28/30, factor percentile 30/30; relative strength 30/30 refused (28 estimator unavailable, 2 thiếu history) [E1]. | Peer set và ICB membership không versioned theo `as_of`; query tool còn giới hạn 10 symbols/request (`apps/api/src/agent/tools/query.py:89-103`). | Candidate sau này: rank/dispersion/relative-return delta so fixed, versioned cohort; guard min cross-section (`apps/api/src/stocks/signals/fields.py:82-102`). | Field reading có as-of, quality/refusal; snapshot inputs có source/effective/observed. | Explicit unavailable cho relative strength; insufficient history; min-cross-section guard. | **Loại khỏi strict V1:** current-universe ranking không chứng minh PIT cross-section; factor input còn filing-time gap. |

## Reusable, ripped/dead và owner còn thiếu

**Reusable ngay:** daily/intraday bars; closed-session calendar; bar provenance; deterministic field registry/refusals; VNINDEX; earnings calculations (chỉ sau khi input PIT được sửa); corporate-action records như context; study runner có frozen `as_of`/artifacts (`apps/api/src/studies/runner.py:1-24`). Catalog hiện có bốn study executable, không phải ba: earnings dislocation, entry condition review, intraday liquidity profile và volume at price (`apps/api/src/studies/registry.py:44-62`, `:103-153`).

**Ripped/dead:** `apps/api/src/alpha/producer.py` chỉ còn compatibility shim `ProductionFailure`, không có nightly producer (`apps/api/src/alpha/producer.py:1-10`). Post-rip universe seating đã bỏ (`apps/api/src/stocks/universe.py:208-243`). FiinQuant/legacy REST importer và valuation reader đã retire; các provider `market` rows cũ không phải capability live (`plans/reports/phase-08-260829-0010-retire-fiinquant.md:63-77`, `:167-199`).

**Owner còn thiếu:** S3/proactive scan, persisted delta identity, compare-to-previous-scan semantics và delivery/inbox state chưa tồn tại; roadmap cũng mô tả S3 là bước có điều kiện/new owner (`docs/roadmap.md:561-583`). Vì vậy nghiên cứu này xác nhận **input capability**, không tuyên bố Delta Inbox đã có.

## Đề xuất tập V1 nhỏ nhất để quyết định

1. **Per-symbol EOD price/volume/microstructure change** cho 5–30 mã do user khai báo. Detector tối thiểu: daily return, volume-vs-trailing baseline, volatility-regime z, band/quality break; mọi output phải có current/baseline/as-of/method/provenance/refusal.
2. **VNINDEX EOD market regime change** làm context chung: return/trend/realized-vol/volatility-regime delta trên cùng closed session.
3. **Corporate action chỉ là context/falsifier**, không phải family bắt buộc: action có date/source/confidence được đính kèm; undated/unconfirmed phải hiện cờ hoặc bị từ chối.

Tập này không cần realtime, broker sync, push/email, portfolio ledger, buy/sell recommendation hay open-ended generated analysis. Nó đủ để kiểm thử proposition “sau close/event-driven, evidence-backed Material Changes liên quan đến Thesis” mà không giả vờ store có dữ liệu chưa tồn tại.

## Bằng chứng read-only

Tất cả truy vấn dưới đây chạy trong `BEGIN TRANSACTION READ ONLY ... ROLLBACK` trên DB runtime ngày 2026-08-30.

- **Q1 — daily/index:** `bar_daily` = 813.107 dòng, 1.523 symbols, 2010-08-31..2026-08-28; VNINDEX = 3.992 dòng. Cohort 30/30 có 2026-08-28; depth min/max 214/3.992, 29/30 có ≥250 dòng.
- **Q2 — intraday:** `intraday_bars` = 122.880 dòng, 31 symbols, 2025-08-26..2026-08-28; cohort = 118.895 dòng, 30/30 mới nhất 2026-08-28, session depth 214..252.
- **Q3 — fundamentals/events:** `financial_statement_lines` = 302.528 dòng/1.235 symbols/34 periods; 2026-Q2 = 1.137 symbols và cohort 30/30. `financial_ratio_snapshots` = 4.152 dòng/30 symbols/3 periods. `corporate_actions` = 284 dòng/29 symbols, 66 confirmed, 218 unconfirmed, 50 undated.
- **Q4 — supporting stores:** `listing_roster` = 1.751 dòng, 1.523 listed, 19 ICB codes. `provider_snapshots`: fundamental 2.854, market 31.160, reference 220; không có capability valuation. `realtime_events` = 0.
- **E1 — executable smoke:** gọi registry trên current declared Universe 30 với `as_of=2026-08-28`, session read-only. Kết quả: price/liquidity core 30/30 trừ ADTV-shares 26/30 và band-pressure 16/30 degraded; 250-session risk/trend 28/30; factor percentiles 30/30; foreign-flow 0/30; foreign-room 29/30; EPS YoY 19/30, net-profit YoY 30/30, gross-profit trend 17/30. Relative strength 0/30 usable vì estimator chưa có/thiếu history. Đây là coverage vận hành tại snapshot, không phải bằng chứng historical PIT.

Mẫu truy vấn kiểm đếm (rút gọn, không chứa secret):

```sql
BEGIN TRANSACTION READ ONLY;
SELECT count(*), count(DISTINCT symbol), min(trading_day), max(trading_day)
FROM bar_daily;
SELECT count(*), count(DISTINCT symbol), min(trading_day), max(trading_day)
FROM bar_intraday_15m;
SELECT count(*), count(DISTINCT symbol), min(period), max(period)
FROM financial_statement_line;
SELECT capability, count(*), count(DISTINCT symbol),
       min(effective_at), max(effective_at), max(observed_at)
FROM provider_snapshots GROUP BY capability;
ROLLBACK;
```

## Câu hỏi chưa giải quyết

1. “Material” ở V1 dùng threshold chung hay policy do user cấu hình theo từng Thesis/symbol, và ai sở hữu version của policy đó?
2. Delta identity/baseline nên so với phiên gần nhất, lần scan gần nhất hay lần user đã đọc; retention/idempotency contract là gì?
3. Corporate action unconfirmed có được phép xuất hiện như context, hay phải fail closed đến khi confirmed?
4. Publication-time và restatement ledger nào sẽ làm owner cho fundamental/filing PIT; backfill lịch sử có nguồn nào đủ tin cậy?
5. Versioned universe/ICB membership nào sẽ mở khóa sector và peer/cross-section mà không survivorship bias?
6. Freshness SLO cho post-close scan là bao nhiêu, và VNINDEX thiếu/stale có chặn toàn scan hay chỉ market-context family?
