---
title: "Nghiên cứu Vnstock: dùng cá nhân → pilot → SaaS/production"
date: 2026-09-04
status: "DONE_WITH_CONCERNS"
scope: "Vnstock community, Diamond Builder, vnstock_data, OHLCV/liquidity, Evidence Desk"
source_policy: "Nguồn chính thức của Vnstock/GitHub/PyPI và probe read-only; không đọc hoặc ghi lộ secret"
---

# Vnstock: dùng cá nhân → pilot → SaaS/production

## Kết luận điều hành

| Quyết định | Kết luận |
|---|---|
| Dùng ngay cho phát triển cá nhân | **GO có điều kiện**. Community `vnstock` đủ để thử nghiệm read-only với OHLCV ngày, quote/price board, trades/intraday và listing; phải coi đây là adapter nghiên cứu, không phải hợp đồng dữ liệu ổn định. |
| Mua Diamond 5.400.000 VND/năm ngay | **HOLD/NO-GO cho mục đích “mua là được SaaS”**. Trang bán hàng quảng bá quyền phân phối ứng dụng giới hạn dưới 500 user, nhưng license hiện hành yêu cầu thỏa thuận bằng văn bản cho commercial integration và tách riêng quyền dữ liệu nguồn. |
| Đưa Vnstock vào Evidence Desk hiện tại | **NO-GO implementation**. Catalog runtime vẫn đúng năm tool và Phase 6 hiện là web-only; một market-data capability là one-way door, phải có deviation/amendment và gate riêng trước khi đăng ký tool. |
| Production | **Chỉ GO sau khi có văn bản** bao phủ software license, quyền từng upstream source, SaaS/container/CI identity, quota/SLA, schema/freshness và xử lý khi hết hạn. |

**Tóm tắt một câu:** Vnstock là lựa chọn hợp lý để học và đo rủi ro bằng các probe nhỏ ngay bây giờ; Diamond có thể là đường tới pilot thương mại dưới 500 user, nhưng giá/quota trên trang không thay thế một giấy phép SaaS và quyền khai thác dữ liệu của KBS/VCI/MAS/CafeF hay nguồn khác.

## Phạm vi, phương pháp và trạng thái interrupted report

- Đã kiểm tra mục tiêu `plans/reports/research-260904-2254-vnstock-personal-to-saas-production.md`; file không tồn tại khi bắt đầu nên không có bản interrupted nào cần phục hồi. Chỉ tạo file này; không sửa code, test, config, database hay roadmap.
- Đã đọc [`CLAUDE.md`](../../CLAUDE.md), các phần liên quan của [`docs/roadmap.md`](../../docs/roadmap.md), báo cáo Bronze cũ [`research-260829-2015-vnstock-bronze-full-power.md`](research-260829-2015-vnstock-bronze-full-power.md), package metadata và source hiện có.
- Bằng chứng bên ngoài chỉ dùng trang/docs/license/privacy chính thức của Vnstock, GitHub chính thức của `thinh-vu/vnstock`, PyPI metadata và probe HTTP read-only. Các con số/quyền được ghi dưới đây là “quan sát tại ngày 2026-09-04”, không xem marketing/config bundle là SLA.
- Có probe dùng credential đã lưu trong runtime để xác định entitlement `free`; không đọc, in, preview, commit hoặc đưa giá trị key vào báo cáo. Shell hiện không export `VNSTOCK_API_KEY`. Các probe còn lại dùng guest/no-key path hoặc chỉ gọi endpoint đọc.

## Môi trường đã xác minh

| Hạng mục | Kết quả | Ý nghĩa |
|---|---|---|
| Python trong `apps/api/.venv` và system Python | `vnstock` **4.0.5**; import thông báo có 4.0.7 mới hơn | Project đang lệch latest; phải pin và canary trước khi nâng. PyPI hiện liệt kê Community 4.0.7, phát hành 2026-08-20: [PyPI vnstock](https://pypi.org/project/vnstock/). |
| Sponsor package | `vnstock_data` không cài trong hai môi trường đã kiểm tra | Không thể xác nhận runtime behavior/quota của Diamond từ package sponsor trong môi trường hiện tại. |
| Auth | Runtime có credential đã lưu và xác định tier `free` (60/min, 3.600/hour); không báo secret | Đây là entitlement quan sát được, không phải quyền Diamond. |
| Project dependency | `apps/api/requirements.txt` không có Vnstock | Không tự ý thêm SDK/provider vào project; research này không mở capability. |
| Community license metadata | `vnstock` ghi “Personal, research, non-commercial; contact support@vnstocks.com for other use” | Community package không phải giấy phép commercial/SaaS. Xem [pyproject.toml](https://raw.githubusercontent.com/thinh-vu/vnstock/main/pyproject.toml) và [LICENSE.md](https://raw.githubusercontent.com/thinh-vu/vnstock/main/LICENSE.md). |

## Bề mặt kỹ thuật đã xác minh

### 1. Community so với sponsor

Trang so sánh chính thức mô tả `vnstock` community ở v4.0.6 và `vnstock_data` sponsor là các đường package khác nhau; sponsor có thêm nhiều method và quota. [Bảng so sánh Free/Sponsor](https://vnstocks.com/docs/vnstock/so-sanh-free-va-sponsor) liệt kê:

| Năng lực | Community quan sát/được docs mô tả | Sponsor được docs mô tả | Nhận xét cho Stock_Massive |
|---|---|---|---|
| Equity market | 3 method chính; KBS/VCI; day/hour/minute | 12 method; KBS/VCI/MAS/VND tùy lớp; tick, 1m/5m/15m/1H/day/week/month | OHLCV/quote/trades có thể bắt đầu ở community; flow/order-book nâng cao cần entitlement riêng. |
| OHLCV | KBS và VCI native adapter, daily đã probe được | Toàn listing history theo docs sponsor | Không giả định “toàn lịch sử” khi chưa xác nhận source/plan. |
| Liquidity / market microstructure | Quote/price board, trades/intraday; field tùy source | `order_book`, `session_stats`, `volume_profile`, `odd_lot`, `block_trades`, foreign/proprietary flow và summary | V1 chỉ lưu provider-reported fields; không tự biến quote thành tín hiệu/khuyến nghị. |
| Fundamental/macro/insights | Phạm vi community hẹp hơn | Sponsor mở thêm finance, valuation, macro, ranking/screener theo bảng so sánh | Không cần cho personal pilot OHLCV; không đưa local analysis engine vào Evidence Desk. |

Trang giới thiệu sponsor nói community có các giới hạn lịch sử/thời gian và sponsor mở rộng chúng: daily free tối đa 8 năm, minute free tối đa 1 năm, intraday free 30.000 rows; reports free là 4 kỳ guest/8 kỳ với API key, còn sponsor tùy nguồn. Đây là giới hạn package/docs tại thời điểm trang v3.2.8, không nên coi là cam kết cho mọi source: [Giới thiệu vnstock_data](https://vnstocks.com/docs/vnstock-data/gioi-thieu-vnstock-data).

### 2. Method và schema

Docs Market Layer liệt kê equity methods `ohlcv`, `trade_history`/`trades`, `quote`, `order_book`, `session_stats`, `foreign_flow`, `proprietary_flow`, `block_trades`, `odd_lot`, `volume_profile`, `summary`; historical methods nhận start/end/interval, snapshot methods trả trạng thái phiên hiện tại. [Market Layer v3](https://vnstocks.com/docs/vnstock-data/market-layer-v3).

Schema docs chính thức là tham chiếu tốt để viết adapter, nhưng là docs versioned chứ chưa phải schema contract bất biến:

| Dataset | Schema canonical được docs nêu | Rủi ro cần giữ trong adapter |
|---|---|---|
| OHLCV | `time datetime64[ns]`, `open/high/low/close float64`, `volume int64` | Đơn vị giá và timezone không nằm đủ trong tên cột. KBS live trả giá theo nghìn; không được coi `72.5` là 72,5 VND. |
| Intraday/trade history | `time`, `price`, `volume`, `match_type`, `id` (kèm index ở schema sponsor) | `time` live là naive; `id` có thể do adapter tổng hợp; phân biệt trade time với retrieval time. |
| Foreign/proprietary flow | time, buy/sell volume/value, net volume/value | Đây là provider-reported data; source, kỳ và đơn vị phải đi cùng row. |
| Quote/price board | symbol, exchange, ceiling/floor/reference/open/high/low/close/average, volume, total value, bid/ask levels, foreign buy/sell/room | Quote hiện không có observation timestamp; bid/ask có dtype hỗn hợp. |
| Session/liquidity | average/total match/deal volume/value, trade/order counts, foreign aggregates, active buy/sell ratio | Snapshot phải gắn retrieval time và market session; không suy ra freshness từ row date. |
| Summary | 52-week high/low, dividend, beta, EPS, BVPS, market cap, PE/PB/ROE, changes, dividend yield, foreign ownership | Có thể là dữ liệu tính sẵn của nguồn; không trình bày như phép tính của Evidence Desk nếu không có provenance. |

Tham chiếu: [Data structure index](https://vnstocks.com/docs/vnstock-data/cau-truc-du-lieu/index) và [Market schema](https://vnstocks.com/docs/vnstock-data/cau-truc-du-lieu/market).

### 3. Source routing và provenance

Docs data-sources nêu các nguồn/layer: VCI và KBS cho listing/quote/market/company; MAS cho finance; VND Insights; MBK/SPL cho macro/commodity; CafeF adapter cho một số flow; Fmarket fund; Binance, Dukascopy/FXSB cho tài sản quốc tế. Routing được mô tả theo mục đích: KBS cho movement/realtime/OHLCV/intraday/order book ngắn hạn, VCI cho chuỗi dài, MAS cho finance; VCI có thể bị cloud IP policy chặn. [Data sources](https://vnstocks.com/docs/vnstock-data/data-sources).

Đây là provenance của **connector**, không tự động là provenance của publisher/exchange. Vnstock license nói thư viện không sở hữu, lưu trữ hay phân phối market data; thiết bị/server của user gọi trực tiếp third-party server. Vì vậy Evidence Desk phải lưu tối thiểu:

`provider`/`source`, dataset và symbol; `retrieved_at` có timezone; `as_of`/phiên; source timezone; unit/scale/currency; adjusted/unadjusted; request args; package/version; endpoint family; raw response hash; normalized payload hash; freshness/quality/error state; và stable citation/artifact URL nếu row được trích dẫn.

Không có bằng chứng rằng fallback KBS→VCI→VND là SLA của Vnstock; docs chỉ đưa pattern/routing. Không được trả lời “nguồn chính thức” chỉ vì Vnstock đã normalize row.

### 4. Pagination, argument và failure surface

- Market docs ghi `limit` per page mặc định 1.000, `page`, và `get_all=True` sẽ quét nhiều page; docs cũng cảnh báo `get_all` trên mã thanh khoản cao. Vì vậy mỗi page có thể tiêu quota/latency; cần xác nhận định nghĩa “request” và backoff trước production.
- Native community KBS trade method dùng `page_size`; probe gọi Unified UI với `limit=5` vẫn trả 100 rows, cho thấy argument bị lọc im lặng ở đường UI. Đây là lỗi contract đáng kể nếu caller nghĩ đã bounded.
- Source code KBS hiện có endpoint history `/stocks/{symbol}/data_{interval_suffix}` và trade history `/trade/history/{symbol}`, chuẩn hóa OHLCV/trades và scale giá stock/ETF theo nghìn. [KBS quote adapter](https://raw.githubusercontent.com/thinh-vu/vnstock/main/vnstock/explorer/kbs/quote.py). Endpoint live quan sát được là `https://kbbuddywts.kbsec.com.vn/iis-server/investment`; VCI là `https://trading.vietcap.com.vn/api/`. Đây là upstream/internal API surface, không phải public SLA của Vnstock.
- `invalid symbol` trả `ValueError`, trong khi reversed dates và weekend-only no-data bị bọc thành `tenacity.RetryError`; taxonomy lỗi hiện không đủ để phân biệt input invalid, no data, provider outage và retry exhaustion.
- Lịch sử phiên bản ghi nhiều lần sửa VCI truncation/pagination, đổi finance schema sang VAS tidy long-form và thay source finance; do đó phải pin version, có live contract matrix và canary upgrade. [Version history](https://vnstocks.com/docs/vnstock-data/lich-su-phien-ban).

## Quota, giá và Diamond

### Quota được quảng bá hiện tại

Pricing page hiện tại hiển thị các mức sau; con số được đọc từ trang/Next.js pricing bundle ngày 2026-09-04, không coi là SLA. [Insiders Program](https://vnstocks.com/insiders-program) · [pricing bundle hiện tại](https://vnstocks.com/_next/static/chunks/3274-1ad682d30be71db4.js).

| Tier | Giá hiển thị | Rate limit (requests/minute/hour/day/month) | Library/đặc tính chính |
|---|---:|---:|---|
| Community | Miễn phí | 60 / 3.600 / 10.000 (bảng tháng 100.000) | `vnstock`; REST khoảng 1–3 giây; 1 device |
| Bronze | 180.000đ/tháng | 180 / 10.800 / 50.000 (600.000/tháng) | `vnstock_data`; REST 1–3 giây; 1 device mỗi OS theo card |
| Silver | 189.000đ/tháng, kỳ thanh toán quarterly | 300 / 15.000 / 100.000 (1.500.000/tháng) | `vnstock_data`, `vnstock_ta`, `vnstock_news`; REST 1–3 giây |
| Golden | 2.399.000đ/năm | 500 / 30.000 / 150.000 (2.500.000/tháng) | 4 library gồm pipeline; WSS; pipeline 5–8x theo FAQ/card |
| Diamond Builder | **5.400.000đ/năm** | **600 / 36.000 / 180.000 / 3.500.000 requests** (phút/giờ/ngày/tháng trong bảng) | 4 library, WSS, full source-dependent reports; card quảng bá deployment/product dưới 500 user |

Có hai điểm phải xác minh trước khi thanh toán/production:

1. Bundle có `pricing.amount: 450.000 VND` và `period: yearly`, trong khi field hiển thị cho người dùng là `price: 5.400.000đ` và `/ năm`. `450.000` đúng bằng `5.400.000/12`, nên cách hiểu hợp lý nhất là monthly-equivalent/metadata nội bộ (không phải bằng chứng về một checkout price khác); nguồn first-party hiện không nói field này là số tiền checkout. Khi lập ngân sách, dùng giá hiển thị và invoice/checkout, không dùng `pricing.amount`.
2. Một trang onboarding sponsor khác mô tả dải sponsor là 180–500 req/min, trong khi intro và pricing bundle cho Diamond là 600 req/min. Ngược lại, **3.500.000 requests/tháng là quota tháng được bảng pricing ghi rõ**, không phải giá tháng. [Intro sponsor](https://vnstocks.com/docs/vnstock-data/gioi-thieu-vnstock-data) và [onboarding/install](https://vnstocks.com/onboard-member/cai-dat-go-loi/cai-dat-nang-cao) không đủ để giải quyết mâu thuẫn 500/600; cần entitlement live hoặc xác nhận bằng văn bản.

### Diamond có cho SaaS/production không?

**Câu trả lời an toàn hiện tại: chưa thể coi là “có” chỉ nhờ mua Diamond.**

- Card Diamond của trang bán hàng ghi “Giấy phép phân phối ứng dụng độc lập (< 500 user)”, cho phép đóng gói thư viện như tính năng chìm trong sản phẩm thương mại; card cũng ghi 5 Mac + 5 Windows + 3 Linux (tổng 13 thiết bị) và 20 lần đổi thiết bị/ngày trên Linux, phù hợp CI/CD/Railway/Docker/Vercel. Đây là một tín hiệu thương mại tích cực, không phải văn bản đầy đủ của SaaS license.
- [Chính sách thành viên](https://vnstocks.com/onboard-member/chinh-sach-thanh-vien) nói sponsorship không phải là một giao dịch bán sản phẩm và riêng Diamond “hỗ trợ giấy phép phân phối thương mại giới hạn (dưới 500 người dùng)”. Từ “hỗ trợ” không định nghĩa user là account, active user, concurrent user hay end user.
- [License hiện hành](https://vnstocks.com/onboard/giay-phep-su-dung) (`license-2026.09`, `tos-2026.09`) nói sponsor package là quyền tạm thời, không độc quyền, không chuyển nhượng, chỉ trong thời gian contribution hợp lệ; internal deployment chỉ theo tier/agreement; **commercial integration chỉ với written software license agreement**. License đó cũng nói không chuyển quyền truy cập, lưu trữ, hiển thị, phân phối hay khai thác commercial đối với third-party data/index/trademark.
- Community [LICENSE.md](https://raw.githubusercontent.com/thinh-vu/vnstock/main/LICENSE.md) còn hẹp hơn: personal/research/non-commercial; không commercial/organizational use hoặc redistribution nếu chưa có chấp thuận bằng văn bản. Không dùng license community để suy ra quyền Diamond.

Do đó, Diamond chỉ là **điều kiện cần có thể có**, không phải điều kiện đủ cho SaaS. Phải xin agreement nêu đích danh sản phẩm Stock_Massive, mô hình multi-tenant, ngưỡng 500 user, hidden feature, raw/normalized/derived data, cache/retention, container/CI redeploy, source credentials, expiry và termination.

### Quyền thư viện và quyền upstream data là hai lớp khác nhau

| Lớp quyền | Vnstock hiện nói gì | Hệ quả |
|---|---|---|
| Software/package | Community personal/non-commercial; sponsor package chỉ cho member, tạm thời/non-transferable; commercial integration cần written agreement | Không copy, redistribute wheel/source hay nhúng sponsor vào SaaS trước khi có agreement. |
| Vnstock account/quota/device | Tier, device, API limits, WSS và pipeline là benefit theo membership; quyền có thể bị block/revoke và chấm dứt khi hết hạn/vi phạm | Không xem quota cao là license dữ liệu; phải thiết kế hết hạn/disable rõ ràng. |
| Upstream data | Vnstock là technical connector, không bán/trao quyền source data; user chịu trách nhiệm terms/access/storage/display/distribution | Phải audit riêng KBS, VCI, MAS, CafeF, VND…; dữ liệu derived không tự động thoát khỏi upstream ToS. |
| Privacy/telemetry | [Privacy policy](https://vnstocks.com/onboard/chinh-sach-quyen-rieng-tu) nêu account/device ID, IP, install date, auth history, plan, limits và optional library/operation/latency/error/environment telemetry; không chủ động đọc source code/file/portfolio content theo policy | Key chỉ ở backend secret store; xem deployment/device telemetry là một dependency compliance, không đưa vào model context. |

## Cloud/deployment và vận hành

Installer chính thức hỗ trợ Python 3.10–3.14, headless server/cloud, non-interactive install, CI/CD, GitHub Actions, Docker và env `VNSTOCK_API_KEY`; [advanced install](https://vnstocks.com/onboard-member/cai-dat-go-loi/cai-dat-nang-cao). Điều này chứng minh **khả năng kỹ thuật triển khai**, không chứng minh quyền SaaS, SLA hay quyền nguồn dữ liệu.

Các ràng buộc vận hành cần tính từ đầu:

- Chạy Vnstock ở backend worker; không gửi key cho browser, LLM hay user prompt. Một credential dùng chung có thể đụng quota/device/account boundary.
- Container ephemeral có thể tạo device identity mới; Diamond card quảng bá Linux đổi device 20 lần/ngày nhưng chưa có định nghĩa chính thức về container, replica, autoscaling hay CI retry.
- VCI có thể bị block trên cloud theo docs data-sources; source fallback không guaranteed. Phải có explicit degraded state, không silently đổi nguồn.
- REST latency 1–3 giây là quảng bá tier thấp; WSS chỉ được quảng bá Golden/Diamond. Không có SLA/freshness/uptime public trong các nguồn đã kiểm tra.
- `get_all=True`, đa mã và song song có thể nhân số page/request; không được suy quota bằng số DataFrame rows.

## Bằng chứng live probe (2026-09-04)

Probe chỉ đọc, không đặt lệnh, không ghi upstream, không tiết lộ key. Credential persisted được runtime nhận là `free`; các chi tiết secret bị loại khỏi log. Kết quả là behavior của package/provider tại thời điểm probe, không phải guarantee.

| Probe | Kết quả quan sát | Quyết định kỹ thuật |
|---|---|---|
| KBS `Quote.history` FPT, `2026-08-24..28`, `1D` | Thành công khoảng 1,0s; 5 rows; `time/open/high/low/close/volume`; giá như `72.5` (nghìn VND); timestamp naive ở 07:00 | Adapter bắt buộc gắn unit=`VND_thousand`, timezone policy và retrieval time. |
| KBS quote FPT | Thành công khoảng 0,55s; 1 row, 31 fields; giá/`total_value` là full VND ints; bid/ask dtype hỗn hợp; không có observation timestamp | Quote không thể dùng raw DataFrame làm evidence; cần schema/typing/observation wrapper. |
| KBS trades FPT qua Unified UI với `limit=5` | Trả 100 rows; `limit` bị lọc im lặng; native arg là `page_size`; price lại theo nghìn, time naive | Bounded call phải validate args sau dispatch, không tin row count do caller truyền. |
| KBS `get_all=True` | Có thêm cột tên `va`, khác tên `value` trong comment/docs | Schema drift/alias phải được ghi nhận và test; không rename âm thầm trước khi lưu raw. |
| VCI OHLCV FPT cùng khoảng ngày | Trả 100 rows bắt đầu từ 2026-04-08, không trim theo start; các rows cuối khớp KBS | Provider semantics khác nhau; adapter phải post-filter và đánh dấu source/coverage. |
| Symbol không hợp lệ | `ValueError` | Có thể phân loại input error. |
| Reversed dates hoặc weekend-only no-data | Bị bọc thành `tenacity.RetryError` | Cần unwrap/normalize error taxonomy; retry không được biến no-data thành outage mơ hồ. |
| Guest/other read-only checks | KBS history/intraday, listing all_symbols (1.522 rows), price board VCI (1 row, 28 columns) chạy được; KBS price-depth có lần lỗi `RetryError` bọc `AttributeError` | Community đủ cho bounded research, nhưng coverage/endpoint không production-grade theo mặc định. |
| Endpoint/provider | KBS base quan sát `https://kbbuddywts.kbsec.com.vn/iis-server/investment`; VCI base `https://trading.vietcap.com.vn/api/` | Đây là dependency upstream cần allowlist/monitoring và quyền riêng; không hard-code thành public contract. |

Các probe này xác nhận OHLCV và provider-reported liquidity fields có thể lấy được, nhưng cũng xác nhận bốn rủi ro không thể bỏ qua: scale không đồng nhất, timestamp thiếu timezone/observation semantics, pagination/argument silent behavior và lỗi retry che mất nguyên nhân.

## Gợi ý kiến trúc cho Evidence Desk

Roadmap hiện định nghĩa Evidence Desk là web-first, render từ ledger, giữ `as_of`/publication/retrieval time và không xây local market store, scheduler, indicator/Study engine. Vì vậy research này **không đề xuất đăng ký tool hay thêm dependency trong turn hiện tại**.

Nếu deviation/amendment sau này mở market data, hình dạng nhỏ nhất nên là **một** read-only `get_market_data` với dataset enum giới hạn (`ohlcv`, `quote`, `trades`; liquidity provider-reported chỉ khi gate mở), thay vì một tool cho mỗi provider. Provider KBS/VCI/MAS… nằm sau adapter; không expose endpoint/raw arbitrary URL cho model.

Các invariant nên khóa trước implementation:

1. Result numeric-only sau validation có thể dùng `ContentTrust.TRUSTED_STRUCTURED`; mọi provider string/raw message vẫn là untrusted và phải sanitize. Registry hiện đã có hai trạng thái này: [`registry.py`](../../apps/api/src/agent/registry.py).
2. Mỗi result phải mang symbol, dataset, provider, package/version, retrieved time có timezone, `as_of`/session, timezone, unit/currency/scale, adjusted flag, request bounds, source route, quality/error state và hash raw/normalized.
3. Evidence contracts hiện có `STORE_FIGURE` và `CALCULATION`, nhưng ledger text renderer hiện canonicalize `item.canonical_url` hoặc `source` thành URL. Một market row cần stable public source URL hoặc durable internal evidence-artifact/card URL; link tới docs Vnstock chỉ chứng minh schema/tool, **không chứng minh giá trị row vừa trả**. Xem [`evidence/contracts.py`](../../apps/api/src/agent/evidence/contracts.py) và [`evidence/ledger.py`](../../apps/api/src/agent/evidence/ledger.py).
4. `source` phải giữ provider/source identity và retrieval timestamp; `as_of` của quote snapshot không được suy ra từ ngày request. Conflict KBS/VCI phải hiện là conflict/degraded, không silently chọn số đẹp hơn.
5. Free pilot chỉ direct OHLCV/quote/trades và liquidity fields do provider trả; derived analytics, indicators, ranking, prediction, alert, portfolio advice và order execution đều ngoài scope.
6. Capability mới chỉ được mở sau deviation/amendment, permission/budget/timeout/untrusted boundary và roadmap gate. Không khôi phục bất kỳ Signal Desk, stock-store read, scheduler hay global watchlist path nào.

## Lộ trình cá nhân → pilot → production

### A. Personal development — làm ngay

- Giữ community `vnstock` trong venv nghiên cứu riêng; pin 4.0.5 cho reproducibility của probe hiện tại, chỉ nâng 4.0.7 sau canary. Không thêm vào `apps/api/requirements.txt` và không đổi runtime catalog.
- Chạy các case bounded: một mã thanh khoản cao và một mã ít thanh khoản; KBS/VCI; daily OHLCV, quote, trades/intraday; invalid symbol, no-data, reversed dates, weekend, pagination. Ghi unit/timezone/schema/raw hash và latency nhưng không ghi key.
- Dùng rate cap 60/min, 3.600/hour, 10.000/day của free entitlement làm hard ceiling; tránh `get_all=True` và đa mã cho tới khi đo request accounting.
- Đánh giá output như dữ liệu kiểm thử/learning, không dùng làm primary evidence cho answer và không hiển thị như advice. Acceptance cá nhân: no secret leak, no unit mix-up, post-filter đúng date, errors phân loại được, replay tái lập được.

### B. Pilot — chỉ sau roadmap/license gate

- Xin trial/entitlement sponsor và written agreement trước khi đưa dữ liệu vào một backend pilot. Xác nhận Diamond thực sự 600 hay 500 req/min, source/library version nào, WSS có được cấp cho use case và user count tính thế nào.
- Chạy contract matrix với KBS/VCI/MAS/CafeF/VND theo dataset được cấp; đo freshness, coverage, scale, timezone, latency p50/p95, 429/retry, page count, cloud IP block, source conflict, restart/device identity và expiry.
- Chỉ expose một capability bounded; quota budget theo request/page (không theo rows), circuit breaker khi nguồn sai, explicit unavailable/degraded, audit log không secret. Gắn mỗi numerical claim với market evidence artifact URL/card ổn định.
- Pilot exit khi có written rights cho tất cả output cần hiển thị/cache/derived, schema canary xanh qua ít nhất một upgrade, và test legal/technical dưới ngưỡng user của agreement.

### C. Production — điều kiện bắt buộc

- Agreement phải cho phép **named product + SaaS/multi-tenant + hidden feature + named deployment**, không chỉ “personal/internal” hoặc “Diamond supports distribution”.
- Upstream terms phải cho phép access, cache/retention, display/API output, derived fields, quote/trade history và evidence retention; nếu không có thì loại source khỏi production.
- Key chỉ backend; device/container enrollment ổn định; quotas, WSS/REST, cloud allowlist, support/escalation và SLA/freshness được test/ghi trong runbook.
- Có source/version pin, adapter contract tests, canary upgrade, schema/units validation, provenance/evidence ledger, monitoring, rollback về “market data unavailable”, và policy xóa/khóa data khi membership/license hết hạn.

## Risk matrix

| Rủi ro | Khả năng / tác động | Bằng chứng | Mitigation và điều kiện NO-GO |
|---|---|---|---|
| Hiểu Diamond = quyền SaaS tự động | Cao / Rất cao | License 2026.09 yêu cầu written commercial agreement; policy chỉ nói hỗ trợ dưới 500 user | NO-GO nếu chưa có agreement nêu rõ SaaS, user semantics và named product. |
| Không có quyền upstream data | Cao / Rất cao | Vnstock nói không transfer source-data/index/trademark rights | Audit ToS từng source; NO-GO cho source không cho cache/display/derived/retention. |
| Quota/metadata có cách hiểu khác nhau | Trung bình / Cao | Bảng pricing ghi 600/min và 3.500.000 requests/tháng; onboarding ghi sponsor 500/min; bundle lưu `pricing.amount=450k` (đúng 5.4m/12) nhưng card hiển thị 5.4m/năm | Dùng giá hiển thị/checkout cho billing; lấy live entitlement + written confirmation cho quota, không suy quota từ metadata giá. |
| Đơn vị giá và timestamp sai | Cao / Cao | KBS OHLCV/trades giá nghìn, quote full VND; timestamps naive/07:00 | Typed normalization, unit/timezone required; reject ambiguous rows. |
| Schema/pagination drift | Cao / Cao | `va` vs `value`, VCI ignores requested start, version history sửa pagination/schema | Pin version, raw preservation, post-filter, contract matrix và upgrade canary. |
| Cloud/source outage hoặc IP block | Trung bình-cao / Cao | Docs cảnh báo VCI cloud IP policy; direct third-party endpoints, no public SLA | Health/freshness, explicit degraded state, source-specific rights/allowlist; không silent fallback. |
| Quota bị nhân bởi page/parallel/get_all | Cao / Cao | Docs cảnh báo get_all; UI `limit=5` trả 100 | Request/page budget, bounded page_size, no `get_all` mặc định, monitor 429. |
| Credential/device/privacy | Trung bình / Rất cao | Installer dùng key/env; privacy thu device/IP/deployment context; Diamond device limits | Backend secret store, no prompt/browser exposure, stable enrollment, redacted logs, expiry runbook. |
| Retry che lỗi input/no-data | Cao / Trung bình-cao | Reversed/weekend trả `RetryError`; price_depth bọc `AttributeError` | Unwrap error classes, no retry on validation/no-data, quality state in ledger. |
| Evidence không chứng minh row | Cao / Cao | Docs link chỉ mô tả schema; ledger cần canonical URL; quote không có observation timestamp | Durable row/artifact URL + raw/normalized hash + observed/as_of; otherwise answer unavailable. |
| Vượt ranh Evidence Desk/advice | Trung bình / Rất cao | Roadmap cấm local store/indicator/advice; capability addition one-way door | Deviation/amendment trước; direct facts only; không ranking/portfolio/order/scheduler. |

## Điều kiện go/no-go chính xác

Chỉ chuyển từ HOLD sang pilot/production khi tất cả câu trả lời dưới đây là “yes” và có artifact lưu được:

1. Có written software license cho Stock_Massive, commercial integration, SaaS/multi-tenant, hidden feature và named production deployment.
2. Văn bản định nghĩa `<500 user` (active/end/concurrent/account), team/service accounts, trial users và cách tính khi scale.
3. Có upstream permission riêng cho từng source cần dùng: access, automated backend calls, cache/retention, display/API, derived metrics, evidence citation và post-expiry retention/deletion.
4. Đã chốt Diamond price/invoice, tier thực nhận, 500 hay 600 req/min, hour/day/month limits, WSS entitlement, library/version và support/SLA.
5. Đã chốt request accounting: method/page, `page_size`, `get_all`, parallelism, retry/429, multi-symbol, shared account và whether rows or HTTP calls count.
6. Đã chốt device/container/CI identity, Linux 20 changes/day, autoscaling/replica behavior, server region/IP allowlist và rotation/revocation.
7. Contract matrix chứng minh schema, unit, currency, timezone, adjustment, `as_of`, freshness, date filtering và error taxonomy trên KBS/VCI (và source nào được cấp).
8. Có stable evidence artifact/citation URL hoặc public source URL cho từng returned row/claim; hash raw/normalized và ledger path replay được.
9. Có canary/rollback khi package/source schema đổi, và kế hoạch disable/delete khi membership/license hết hạn hoặc upstream thu hồi quyền.
10. Capability đã được roadmap owner mở bằng deviation/amendment; permission, budget, trust boundary và no-advice scope đã review.

## Câu hỏi chưa giải quyết

1. Checkout/invoice có xác nhận 5.400.000đ/năm và `pricing.amount=450.000 VND` chỉ là monthly-equivalent/metadata; quota tháng là 3.500.000 requests hay có điều kiện khác?
2. Entitlement Diamond hiện hành là 600 hay 500 req/min, và limits hour/day/month nào là authoritative?
3. “Dưới 500 user” là user nào, có áp dụng cho end users multi-tenant, internal staff, anonymous users và service accounts không?
4. Written agreement có cho phép SaaS backend, hidden library, raw/normalized/derived output, evidence artifact, cache và retention sau expiry không?
5. Mỗi upstream KBS/VCI/MAS/CafeF/VND cho phép automated access, cloud/container, display, redistribution và derived data đến mức nào?
6. Quota tính theo HTTP call, page, method, symbol, `get_all`, retry hay rows; có burst/429 response và SLA/freshness công bố không?
7. Device identity hoạt động thế nào với Docker, Railway, Vercel, autoscaling replicas, CI redeploy và disaster recovery; 20 Linux changes/day áp dụng cho account hay host?
8. WSS endpoint/auth/reconnect/backfill và data retention semantics của Diamond là gì?
9. Schema contract/version compatibility giữa docs sponsor v3.2.8, project community 4.0.5 và PyPI 4.0.7 được bảo đảm ra sao; VCI cloud IP allowlist/fallback có SLA không?
10. Khi license bị revoke/hết hạn, app có phải dừng ngay, xóa cached/evidence data nào, và có grace period/export hợp lệ không?
