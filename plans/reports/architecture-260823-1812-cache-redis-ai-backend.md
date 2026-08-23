# Đánh giá kiến trúc cache và Redis cho AI + backend

Ngày đánh giá: 2026-08-23
Phạm vi: source hiện tại, test liên quan, runtime local, tài liệu chính thức hiện hành của FiinQuant, vnstock và Upstash.

## Brainstorm contract

- **Outcome:** xác định cache hiện tại đã đủ an toàn/tiết kiệm cho gói free chưa và chọn kiến trúc đích dùng chung cho backend cùng AI.
- **Constraints:** Postgres là durable store; Redis đã được dùng cho cache, lock, quota và breaker; FiinQuant/vnstock có quota và semantic khác nhau; AI phải giữ point-in-time provenance; không thay public contract trong vòng phân tích này.
- **Non-goals:** chưa sửa code, migration, topology production hoặc mua/nâng gói; không giải quyết quyền sử dụng thương mại của vnstock thay người vận hành.
- **Acceptance:** inventory current-state có bằng chứng; chỉ ra failure mode thật; so sánh tối đa ba phương án; chốt key/TTL/freshness/failure policy cho data, Redis và AI; có thứ tự triển khai đo được.

## Kết luận ngắn

Kiến trúc hiện tại có **nền rất tốt nhưng chưa đủ tốt cho production dựa trên free tier**.

Phần đúng và nên giữ: Postgres là source of truth; SnapshotStore phục vụ store-only; source ownership tường minh; vnstock có một Redis quota arbiter fail-closed; cache polling quan trọng có stale-while-error, distributed single-flight, lock heartbeat và failure cooldown; AI có stable prompt prefix, durable Turn/Analysis, web cache và LLM rate-limit breaker.

Ba blocker khiến chưa thể gọi là tối ưu:

1. Hợp đồng FiinQuant free hiện công bố **tối đa 33 mã lịch sử, sâu 1 năm**, nhưng API thực tế cho batch lớn hơn theo kiểu best-effort. Probe live ngày 2026-08-23 nhận 49/50 và 10/110 mã xen kẽ 504; blocker thật là timeout/partial response và completeness, không phải hard cap 33.
2. Nhiều REST route cũ vẫn cache-aside trực tiếp lên Provider Source. Đặc biệt price board keyed theo mọi tổ hợp watchlist, nên cardinality người dùng trở thành cardinality upstream call.
3. Redis là remote L2 trên mọi request, chưa có L1/HTTP cache và chưa có telemetry theo lane. Với Upstash free, polling hiện tại có thể hết command quota trước khi provider hết quota.

Hướng chọn: **Postgres durable evidence + Redis control plane/current view + L1 hot cache; provider chỉ chạy trong ingestion; AI cache artifact xác định, không semantic-cache câu trả lời.**

## Bằng chứng hiện trạng

### Những gì đã làm tốt

| Vùng | Behavior đã xác minh | Bằng chứng |
|---|---|---|
| Durable data | Snapshot được ghi Postgres; Redis chỉ là current view; series không dùng Redis | `apps/api/src/stocks/providers/store.py:156-161,233-307` |
| Provider semantics | Main/Cover Source theo capability; không silent fallback giữa nguồn khác basis/unit | `apps/api/src/stocks/providers/contracts.py:137-195` |
| Store-only boundary | Tool/serving path có runtime guard cấm chạm Provider Source | `apps/api/src/core/provider_access.py:18-34` |
| vnstock quota | Một leaky bucket Redis; xét cả minute/hour; safety factor 0.9; Collector lease; fail-closed | `apps/api/src/core/quota.py:1-32,64-114,222-289` |
| Hot response cache | Fresh TTL theo giờ giao dịch; stale copy; single-flight; heartbeat; failure cooldown | `apps/api/src/core/cache.py:26-319` |
| Polling outage | Price board/index có stale tối đa 15 phút, không cache empty/partial | `apps/api/src/stocks/price/router.py:40-71,130-197` |
| FiinQuant connection | Market/valuation dùng một shared session và circuit breaker | `apps/api/src/stocks/collector.py:313-333`; `apps/api/src/stocks/providers/fiinquant.py:135-169,314-330` |
| AI prompt cache | Stable prefix đứng trước runtime context; version/hash rõ; explicit cache control chỉ bật sau probe | `apps/api/src/agent/prompt/contract.py:115-172`; `apps/api/src/core/config.py:260-265` |
| AI artifacts | Analysis dùng unique `(symbol, trading_day)`; Turn có durable idempotency/trace | `apps/api/src/alpha/models.py:119-140,146-212`; `apps/api/src/agent/persistence.py` |
| Open web | Redis cache, freshness/staleness label, single-flight và allowance độc lập | `apps/api/src/core/web_lane.py:18-174` |

Focused suite: **210 passed**, gồm trading-hours cache, vnstock quota/Redis, snapshot store, response caches, FiinQuant provider, web lane và LLM route resilience.

### Free-tier contract hiện hành

**FiinQuant free:** trang pricing hiện ghi 1 connection, 100,000 request/tháng, 90 request/phút, 80 request/giây; realtime tối đa 33 mã; historical 1D tối đa 33 mã và 1 năm. Nguồn: [FiinQuant Pricing](https://fiinquant.vn/Pricing).

Hai điểm cần được hiểu như policy vận hành, không phải hard cap kỹ thuật:

- `MAX_BATCH_SYMBOLS = 100` là trần thử nghiệm; collector giữ batch mặc định 50 và chia đôi khi gateway 504;
- `backfill_main_source_days = 5 * 365` tại `apps/api/src/core/config.py:125-130`.

Các probe repo (`apps/api/prototypes/fiinquant_limits_round2.json`) từng nhận đủ 110 mã và khoảng 5 năm. Probe live sau đó xác nhận request trên 33 không bị entitlement từ chối, nhưng có thể trả thiếu hoặc 504. Hệ thống được phép tận dụng capacity này, miễn không đặt SLO lên phần vượt published entitlement và luôn kiểm tra đủ ticker.

**vnstock:** README hiện ghi Guest 20 request/phút, Community free 60, Sponsor 180–600; tài liệu rate-limit ghi thêm 3,000 request/giờ. Vnstock là extraction toolkit, không phải contracted market-data provider, và license hiện hướng tới personal/non-commercial use. Nguồn: [vnstock README](https://github.com/thinh-vu/vnstock), [vnstock rate-limit guide](https://vnstocks.com/blog/api-rate-limit-la-gi-cach-xu-ly-trong-vnstock).

Arbiter hiện tại đã đúng khi tier có key bị bound bởi 3,000/giờ: safety 0.9 tạo nhịp bền khoảng 45 request/phút, không phải 60.

**Upstash free:** hiện gồm 256 MB và 500K command/tháng. Nguồn: [Upstash Redis pricing](https://upstash.com/pricing/redis).

### Runtime local tại thời điểm đánh giá

- 1,745 Redis key; 5.28 MB dataset; 0 eviction.
- 126,158 command trong khoảng uptime 7 ngày; ngoại suy tuyến tính khoảng 540K/tháng. Đây là dev traffic, không phải production forecast, nhưng đã vượt mức Upstash free nếu giữ nhịp.
- 13,216 hit / 8,175 miss, hit ratio tổng khoảng 61.8%; hiện chưa tách được theo cache lane.
- 1,446 `stock:snapshot:*` key không TTL; dung lượng hiện nhỏ nhưng namespace giữ symbol/source cũ vô hạn.
- Hai hook price board và market index cùng poll mỗi 15 giây khi tab foreground. Chỉ hai GET Redis này đã là 480 command/giờ/tab, khoảng 57,600 command cho 20 ngày × 6 giờ/tab. Khoảng 9 tab-user tương đương đã dùng hết 500K command/tháng, chưa tính miss, SET, EVAL, quota, rate limit, web và AI.

## Failure modes cần sửa

### P0 — correctness/contract

1. **Published entitlement drift.** Free-tier coverage và depth đang dựa vào probe rộng hơn contract. Provider có thể siết lại mà test adapter vẫn xanh.
2. **Cache publish trước DB commit.** `SnapshotStore.save()` flush trong savepoint rồi ghi Redis; outer transaction chỉ commit khi `get_sync_db()` thoát. Nếu phần sau của cycle làm transaction rollback, Redis có thể phục vụ snapshot không tồn tại trong Postgres. Cache write phải xảy ra after-commit hoặc qua outbox.
3. **FiinQuant coordination chỉ process-local.** Shared session/breaker bảo vệ hai adapter trong một collector instance, nhưng không phải account-wide Redis lease cho catch-up/backfill/index và nhiều API replica. Free tier chỉ có một connection.
4. **Wall-clock freshness không phải market calendar.** `TradingHoursCache` coi 09:00–15:00 mọi weekday là trading, gồm lunch break và ngày nghỉ; off-hours TTL một giờ có thể refresh cùng dữ liệu nhiều lần trước phiên mới.
5. **Key không version semantic.** Nhiều response key không mang schema/provider/basis/universe/trading-day version. Deploy đổi nghĩa nhưng payload vẫn parse được có thể tiếp tục phục vụ nghĩa cũ.

### P1 — quota/cost amplification

1. `price_board` cache key là sorted symbol combination. Hai watchlist khác nhau tạo hai key và hai live reads dù phần lớn symbols trùng nhau.
2. Legacy company/financial/market routes vẫn có provider loader trong request path. Cache làm giảm xác suất gọi, chưa loại Provider Source khỏi serving.
3. Mọi hit đi thẳng Redis; không có bounded in-process L1 hoặc shared HTTP/CDN response cache cho public, user-independent market view.
4. Fresh và stale đang là hai Redis records, tăng write count; metadata freshness không cùng payload thành một contract thống nhất.
5. `clear_prefix()` dùng SCAN + DELETE và generic cache instances rải ở routers/services; chưa có policy registry/metrics owner chung.

### P1 — AI-specific

1. Prompt-prefix cache tốt nhưng Analysis v1 prefix chỉ khoảng 436 token theo measurement cũ, dưới breakpoint khoảng 2,048 token của route dev; không nên padding prompt để ép cache.
2. Chưa có baseline theo lane cho context cache hit/churn, dù SOT yêu cầu metric này.
3. Không nên semantic-cache final chat answer: answer phụ thuộc user/thread/memory, tool availability, evidence freshness và model contract. Hit sai rẻ hơn một call nhưng đắt hơn về financial truth.
4. Có thể cache deterministic evidence/derived artifacts, nhưng key phải chứa field/method version và data revision; chỉ `(symbol, day)` là chưa đủ khi snapshot cùng ngày được provider bổ sung số liệu.

## Ba phương án

| Phương án | Ưu điểm | Điểm gãy đầu tiên | Assumption tải trọng |
|---|---|---|---|
| A. Chỉ tune TTL hiện tại | Ít code, giữ contract REST | Unique watchlist và Redis outage tiếp tục chạm provider; FiinQuant entitlement vẫn lệch | Ít user, một process, upstream rộng hơn published tier |
| **B. Store-first 3 tầng** | Provider quota độc lập user traffic; giữ provenance; scale vừa đủ; tận dụng code hiện có | Cần chuyển dần legacy route và chốt realtime coverage ≤33 | EOD/near-real-time đủ cho product; Postgres vẫn là authority |
| C. Redis-centric stream/materialized view | Latency rất thấp, phù hợp realtime fan-out lớn | Tăng vận hành, memory/command cost và consistency burden; không hợp free tier hiện tại | Nhiều nghìn client hoặc licensed realtime feed |

**Chọn B.** Đây là thay đổi nhỏ nhất giải quyết cả quota, correctness, Redis cost và AI truth. C chỉ đáng xét khi có licensed realtime feed và tải đo được; A rẻ nhất để bắt đầu nhưng không đạt outcome.

## Kiến trúc đích đề xuất

```text
FiinQuant / vnstock
        |
        v
Provider policy + account-wide Redis admission/lease
        |
        v
Scheduled ingestion / canonical refresh
        |
        +---- transaction ----> PostgreSQL point-in-time store (authority)
                                  |
                                  +-- after commit/outbox --> Redis L2 views
                                                             |
Client/API --> bounded L1 --> Redis L2 --> PostgreSQL L3 -----+
                 |             |
                 |             +-- never load provider on miss
                 +-- ETag/short HTTP cache for shared views

AI runtime --> stored evidence / deterministic fields / persisted Analysis
           --> provider-native prompt-prefix cache
           --> Redis web/artifact cache, never final-answer semantic cache
```

### 1. Provider policy và coverage

- Tạo một provider policy owner cho `connection`, `rpm`, `hourly`, `monthly`, `symbol_cap`, `history_depth`, capability và license mode.
- FiinQuant free lấy 33 mã/365 ngày/1 connection làm contractual baseline cho SLO và cảnh báo, không làm hard cap client-side. Background ingestion dùng batch 50, chia đôi khi 504 và retry đúng tập ticker thiếu một lần; trần 100 chỉ là best-effort.
- Tách rõ:
  - `realtime/core evidence universe`: tối đa 33 mã trên FiinQuant free;
  - symbol ngoài coverage: explicit vnstock-backed/degraded tier hoặc yêu cầu nâng FiinQuant. Không silent fallback.
- Với product thương mại, vnstock không được coi là production entitlement cho đến khi license được xác nhận.
- Mọi FiinQuant job/replica dùng cùng account lease Redis. Monthly call counter dùng để cảnh báo, không thay published server enforcement.

### 2. Ingestion và current view

- Provider chỉ được gọi bởi ingestion/refresh workers. Request path chỉ đọc store.
- Refresh dựa trên Trading Day/data readiness và `next_change_at`, không chỉ `datetime.weekday()`.
- Price board dùng một hoặc vài canonical sets có version, không key theo mọi tổ hợp watchlist. API lọc subset từ canonical payload.
- Nếu cần near-realtime 15 giây, worker refresh upstream một lần mỗi cadence cho toàn core set; N clients chỉ fan-out stored view.
- Postgres commit trước; sau commit mới publish Redis. Với nhiều write, dùng transactional outbox/idempotent cache projector.

### 3. Redis contract

Một Redis instance hiện đủ; giữ `noeviction`, đặt TTL/bounds cho data keys và alert memory. Control keys không được hy sinh để cache data.

Namespace đề xuất:

```text
sm:v1:control:vnstock:account
sm:v1:control:fiinquant:lease
sm:v1:control:llm:breaker:{route}:{model}

sm:v{schema}:view:snapshot:{capability}:{source}:{symbol}
sm:v{schema}:view:board:{coverage_version}:{trading_day}
sm:v{schema}:view:index:{trading_day}
sm:v{schema}:artifact:field:{method_version}:{data_revision}:{symbol}:{day}:{field}
sm:v1:web:{kind}:{digest}
```

- Một cache record mang `payload`, `effective_at`, `observed_at`, `schema_version`, `data_revision`, `fresh_until`, `stale_until`; Redis TTL đặt tới `stale_until`. Không cần fresh/stale duplicate key.
- L1 in-process bounded TTL 1–5 giây cho hot board/index; Redis L2 theo freshness contract; Postgres L3. L2 miss về Postgres, **không về provider**.
- Static/session-closed data cache tới `next_change_at` hoặc theo trading-day revision; fundamentals invalidate khi statement version mới tới.
- Negative cache chỉ cho typed absence/refusal, TTL ngắn và reason rõ; không cache generic empty response như domain fact.
- Version prefix thay cho broad `clear_prefix`; deploy mới tự bỏ qua old namespace, cleanup bất đồng bộ có bound.

### 4. HTTP/browser

- Giữ TanStack Query L1 trên browser và dừng poll background như hiện tại.
- Với shared market views, thêm ETag từ `data_revision`; trả 304 hoặc short `s-maxage/stale-while-revalidate` nếu data license cho phép.
- Cân nhắc một SSE feed cho canonical core board chỉ khi polling command/latency được đo là bottleneck. Chưa cần Redis Pub/Sub/Streams ở quy mô hiện tại.

### 5. AI cache

- Giữ stable contract/tool schemas ở đầu prompt; tiếp tục đo `cached_input_tokens`. `cache_control` chỉ bật sau route capability probe; không padding prompt.
- Analysis persisted theo `(symbol, trading_day)` chính là shared output artifact. Chat Turn persisted/idempotent; không thêm semantic answer cache.
- Cache các phép xác định đắt: cross-section, Signal Field, prepared bars, Evidence Envelope seed và web reads. Key phải gồm method/field/profile version + snapshot/data revision + scope.
- Tool result lớn đi qua evidence handle/preview và có đường recovery về artifact đầy đủ, phù hợp SOT context architecture.
- User memory không vào privileged cache prefix; tiếp tục đọc qua scoped tool như bài học Hermes hiện tại.

### 6. Telemetry bắt buộc

Theo từng lane/key family:

- L1/L2/L3 hit, miss, stale serve, load, negative hit;
- single-flight owner/follower/wait/failure cooldown;
- provider call theo source/capability/job, queue wait, refusal, entitlement drift;
- Redis command, bytes, key count, TTL coverage, latency/error và projected monthly commands;
- AI cached-input/write token, artifact hit/churn, cost/latency per successful outcome;
- data age và stale/conflict rate tới final Analysis/Turn.

Alert gợi ý: 70% và 85% monthly provider/Redis allowance; any FiinQuant concurrent-session refusal; snapshot key không TTL; cache publish failed after committed DB write; serving path attempted Provider Source.

## Thứ tự triển khai đề xuất

### Phase 0 — khóa contract và correctness

1. Chốt contractual baseline FiinQuant free 33/1 năm; giữ adaptive batch best-effort, completeness validation và drift telemetry.
2. Đưa snapshot Redis publish sang after-commit/outbox; thêm rollback test.
3. Thêm account-wide FiinQuant lease và metrics per provider/job.
4. Thêm cache namespace/schema/data revision và observability cơ bản.

**Acceptance:** không Redis payload nào tồn tại nếu DB transaction rollback; không job/replica thứ hai mở FiinQuant connection; deployment free không đặt SLO lên coverage >33 mã hoặc history >1 năm; partial response không âm thầm làm mất ticker.

### Phase 1 — cắt quota amplification

1. Canonical core board/index refresh từ ingestion; request path store-only.
2. Chuyển legacy route theo mức traffic/provider cost, price-board/index trước.
3. Thêm bounded L1 và one-record freshness envelope; ETag cho shared view.
4. Thay wall-clock TTL bằng market/data readiness policy.

**Acceptance:** tăng client từ 1 lên N không làm provider call tăng theo N; Redis command/client giảm rõ so baseline; Redis outage vẫn phục vụ Postgres LKG và không gọi upstream.

### Phase 2 — AI artifact cache

1. Baseline prompt-cache/context metrics theo Turn và Analysis.
2. Cache cross-section/field/evidence artifacts bằng data revision.
3. Đo quality/cost replay trước và sau; giữ final-answer semantic cache ngoài scope.

**Acceptance:** giảm DB compute/token cost mà figure, provenance, as-of và cited evidence không đổi; cache hit không vượt user/symbol/day scope.

## Theo/lệch bài học Hermes và SOT

- **Theo:** stable/context/volatile separation; prompt cache chỉ là optimization; memory/evidence qua typed tools; Redis breaker cross-process; guard serving fail-open về durable store.
- **Lệch có chủ đích:** provider admission fail-closed, vì vnstock có quota chung và có thể `sys.exit()`; đây là threat model khác LLM breaker, vốn fail-open để tránh trắng màn hình.
- **Không port:** credential pool, nhiều tầng provider fallback, Redis-centric orchestrator hoặc semantic answer cache. Chúng không giải quyết bottleneck hiện tại và phá source/provenance clarity.

## Câu hỏi chưa giải quyết

1. Stock_Massive là hệ thống cá nhân/non-commercial hay sẽ có doanh thu? Câu trả lời quyết định vnstock có thể ở production path hay chỉ ở dev/research.
2. Product có bắt buộc SLO realtime cho hơn 33 mã không, hay EOD coverage rộng theo best-effort là đủ? Nếu bắt buộc SLO đó, free FiinQuant vẫn không có contract bảo đảm dù API hiện cho gọi rộng hơn.
3. Production sẽ self-host Redis cùng VPS hay dùng Upstash? Với polling đa người dùng, Upstash free cần L1/HTTP cache mạnh hoặc chuyển PAYG; self-host Redis phù hợp topology hiện tại hơn.
