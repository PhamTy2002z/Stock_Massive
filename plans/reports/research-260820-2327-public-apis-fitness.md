# public-apis: nguồn nào dùng được cho Stock_Massive

Ngày: 2026-08-20 · Nhánh: `feat/news-article-body` · Loại: research, không sửa code

## Kết luận một dòng

Không có nguồn nào trong `public-apis` thay được hay bổ sung được dữ liệu cốt lõi
(giá/khối lượng/BCTC/quyền HOSE-HNX-UPCOM). Chỉ còn 2 nguồn keyless đã kiểm chứng
sống, và cả hai chỉ là **bối cảnh vĩ mô**, giá trị biên với sản phẩm hiện tại.

## Phương pháp

- Tải toàn bộ `README.md` (2189 dòng, 50 mục) và grep trực tiếp, không qua summarizer.
- Probe HTTP thật từng ứng viên bằng `curl --max-time`, ghi status code.
- Đọc repo: `providers/contracts.py`, `agent/tools/*`, `docs/serving-path.md`.

## Bằng chứng cứng

### 1. Danh sách không có Việt Nam

```
grep -niE "vietnam|viet nam|hanoi|asean" README.md  →  0 hit / 2189 dòng
```

Mục Finance (853–919) có 60+ entry: Mỹ, Brazil, Ấn Độ, Nam Phi, Thổ, Hàn.
Không có HOSE/HNX/UPCOM. Mục Open Data có `K-Data Gate` (Hàn), không có bản VN.

Chứng cứ phụ — kể cả nguồn global lớn nhất cũng không có VN-Index:

```
GET query1.finance.yahoo.com/v8/finance/chart/^VNINDEX  →  404 "No data found"
```

### 2. Cột `Auth` của public-apis đã lỗi thời (probe thật)

| Entry | README nói | Probe thật | Kết luận |
|---|---|---|---|
| Exchangerate.host | `No` | `{"code":101,"type":"missing_access_key"}` | **Đã thương mại hoá**, README sai |
| Econdb | `No` | `401 Authentication credentials were not provided` | **Đã đóng**, README sai |
| Frankfurter | `No` | `200`, nhưng `grep -c vnd` trên `/v1/currencies` = **0** | Sống, **không có VND** (bộ ECB) |
| Fed Treasury | `No` | `200` trên `avg_interest_rates`; `404` trên `daily_treasury_yield_curve` | Sống nhưng **không có yield curve ngày** (nó nằm ở CSV `home.treasury.gov`, đã xác nhận `200`) |
| Goldprice.dev | `No` | `/api`, `/api/prices`, `/api/v1/spot` đều trả SPA HTML | **Không xác minh được** endpoint |
| Currency-api | `No` | `200`, `usd.vnd` có, `date=2026-08-20` | **Sống, có VND, đúng ngày** |
| World Bank | `No` | `200`, VN CPI 2025 = 3.31% | **Sống**, nhưng **tần suất năm** |
| Statistics of the World | `No` | `200` trên `/api/v1/countries/VNM`, có Việt Nam | Sống, nhưng giá trị mới nhất lệ thuộc WB (2013/2014/2023), host Vercel cá nhân |
| FRED | `apiKey` | `400 api_key is not set` | Không probe được, cần key (free) |

Bài học vận hành: **không tin cột `Auth`**, phải probe trước khi đưa vào plan.

### 3. Chi phí kiến trúc của việc thêm một nguồn

Repo không phải chỗ "cắm thêm API cho vui". Đường đi của một nguồn mới:

- `docs/serving-path.md` + ADR 0001: request người dùng **không** chạm Provider Source
  với mã trong Universe. Muốn dữ liệu vào đường đọc-từ-store thì phải qua `Collector`.
- `providers/contracts.py:38` — `Capability` là enum đóng, mỗi capability có
  `SourceOwnership(main=…, cover=…)` khai báo tĩnh ở `SOURCE_OWNERSHIP_BY_CAPABILITY`.
  Hiện có `MARKET`, `VALUATION`, `REFERENCE`, `FUNDAMENTAL`, `MARKET_INDEX`.
  Vĩ mô/FX **không khớp** một cái nào: cả 5 đều là chuỗi khoá theo `symbol`
  (`SymbolSnapshot.normalize_symbol`). Thêm chuỗi không-symbol = **Capability thứ 6 + Adapter**
  — đúng việc mà `serving-path.md` đã cân nhắc và tạm bỏ ở #27.
- ADR 0014: mọi lời gọi provider đi qua arbiter hạn mức ở `core/quota.py` theo lane.
  Nguồn keyless không tiêu quota vnstock, nhưng vẫn cần circuit breaker riêng
  (mẫu có sẵn: `ProviderCircuitBreaker` trong `fiinquant.py:132`).
- Nếu số liệu mới lọt vào Signal Registry hoặc Analysis Field Profile →
  **PR bắt buộc đính Eval Report** (CLAUDE.md, `docs/agents/eval-battery.md`).

### 4. Đường rẻ đã có sẵn — và giới hạn của nó

Tool catalog hiện tại (`agent/tools/`, 12 tool):

```
get_analysis  get_company_profile  get_financials  get_price_series  get_watchlist
screen_universe  search_news  web_search  fetch_url  run_python
recall_facts  remember_fact
```

- `web.py` đã có `web_search` + `fetch_url` hardened (SSRF guard: `validate_public_url`,
  chặn IP nội bộ, giới hạn redirect 4, timeout 8s), và docstring gọi thẳng kết quả là
  **"untrusted external claims"**.
  ⇒ Câu hỏi kiểu "DXY đang thế nào", "giá vàng thế giới" **agent đã trả lời được rồi**,
  chỉ là ở tư cách khẳng định ngoài, không phải số hệ thống.
- `compute.py:1` — `run_python` chạy trong **networkless container**.
  ⇒ Không thể dùng `run_python` như lối tắt để fetch API. Muốn số vào phép tính
  thì số phải đi qua provider/store. Không có đường thứ ba.

Đây là điểm quyết định: khoảng cách giữa "nhắc được trong văn bản" (đã có, chi phí 0)
và "tính được, backtest được, ràng buộc validator" (phải qua Capability mới) rất lớn,
và các nguồn keyless còn sống **không đủ chất lượng** để đáng bước qua khoảng cách đó.

## Phán quyết từng ứng viên

| Nguồn | Dùng làm gì được | Phán quyết |
|---|---|---|
| **Currency-api** (jsdelivr CDN) | USD/VND ngày | ⚠️ Chỉ hiển thị. Là tỷ giá tham chiếu crowd-sourced, **không phải VCB/liên ngân hàng**. Với sản phẩm tài chính, hiện sai tỷ giá tệ hơn không hiện. Phụ thuộc CDN không SLA, license phải kiểm |
| **World Bank** | CPI/GDP VN theo năm | ⚠️ Tần suất năm → vô dụng cho quyết định giao dịch. Chỉ hợp một dòng bối cảnh tĩnh |
| **FRED** (key free) | DXY, DGS10, FEDFUNDS, CPIAUCSL | ✅ Chất lượng tốt nhất trong list. Nhưng chỉ vĩ mô Mỹ, và `web_search` đã phủ nhu cầu văn bản |
| **Fed Treasury** | Lãi nợ công Mỹ | ❌ Không phải yield curve ngày. Trùng và yếu hơn FRED |
| **Statistics of the World** | Vĩ mô 218 nước | ❌ Dữ liệu dẫn lại World Bank, host cá nhân → thêm điểm hỏng, không thêm dữ liệu |
| **Frankfurter** | FX | ❌ Không có VND |
| **Exchangerate.host / Econdb** | — | ❌ Đã cần key, README sai |
| **Goldprice.dev** | Vàng spot | ❌ Không xác minh được endpoint; kể cả sống thì là XAU thế giới, không phải SJC |
| **Alpha Vantage / Finnhub / Polygon / Twelve Data / IEX / Marketstack / Yahoo wrapper** | — | ❌ Không phủ mã HOSE/HNX/UPCOM. Đốt tiền không đổi được gì trong sản phẩm |
| **Mục News (23 entry)** | Tin | ❌/⚠️ Xem dưới |
| **Crypto (80+ entry)** | Proxy risk-appetite | ❌ Tín hiệu rất yếu, không xứng một provider |

## Nhánh news — phân tích riêng (vì đang làm `feat/news-article-body`)

Repo đã có `cafef_rss.py` + `cafef_article.py` và tool `search_news`. Commit `3c49458`
vừa thêm đọc body từ trang gốc. Trong 23 entry mục News:

- Keyless: `Noozra` (RSS aggregator, probe trả SPA → không xác minh được API),
  `Inshorts` (Ấn Độ), `Chronicling America` (báo Mỹ thế kỷ 19), `Spaceflight News`,
  `Florida Man` — **không cái nào liên quan**.
- Có key và có thể phủ VN: `NewsData`, `GNews`, `Currents`, `TheNews`, `MarketAux`.
  **Không kiểm chứng được nếu không có key** — không tự nhận là phủ hay không phủ.

Nếu muốn xét tiếp, phép thử quyết định (làm trước khi viết một dòng code):

1. `country=vn` / `language=vi` có trả kết quả thật không, hay rỗng.
2. Trong nguồn có CafeF / Vietstock / ĐTCK / VnEconomy không, hay chỉ Reuters/AFP dịch.
3. Có gắn **ticker** VN không (`MarketAux` bán điểm này) — nếu không có ticker thì
   không ghép được vào watchlist, giá trị sụp.
4. Có trả **full body** không. Nếu chỉ trả `description`, nó **không thay được**
   `cafef_article.py` — vừa mất tiền vừa vẫn phải scrape.

Điều kiện thắng: chỉ đáng đổi khi phủ được ≥3 publisher VN **kèm ticker**, tức là
thay thế được N scraper tương lai bằng 1 API. Chỉ thêm 1 nguồn tin thì tự viết
RSS adapter thứ hai theo mẫu `cafef_rss.py` rẻ hơn và không lệ thuộc bên thứ ba.

## Khuyến nghị

**Mặc định: không thêm gì.** Lý do không phải "nguồn kém", mà là bất đối xứng chi phí:
Capability thứ 6 + Adapter + Collector + eval gate, để đổi lấy tỷ giá tham chiếu
và CPI theo năm — trong khi `web_search` đã trả lời được phần văn bản với chi phí 0.

Nếu vẫn muốn có bối cảnh vĩ mô, thứ tự đúng:

1. Bắt đầu bằng **prompt/UI**, không phải provider: cho phép agent dùng `web_search`
   cho macro, nhãn rõ là khẳng định ngoài. Chi phí gần 0, không chạm eval gate.
2. Chỉ khi số liệu vĩ mô cần **vào phép tính** (ví dụ tương quan VN-Index vs DXY)
   thì mới mở Capability thứ 6, và mở bằng **FRED** (nguồn có SLA, có history),
   không bằng CDN cộng đồng.
3. FX/vàng nội địa: `public-apis` **không giải quyết được**. Nguồn đúng là VCB/SBV/SJC —
   nằm ngoài list, phải tự scrape, và phải xét robots.txt như đã làm với CafeF
   (`cafef_rss.py:15`).

## Câu hỏi còn treo

1. Vĩ mô/FX có nằm trong scope Alpha Desk không, hay agent chỉ trả lời cấp mã/ngành?
   Nếu chỉ cấp mã → câu trả lời gọn là "không có nguồn nào phù hợp", dừng ở đây.
2. Tỷ giá/vàng cần bản **nội địa** (VCB/SJC) hay bản quốc tế là đủ? Nếu nội địa thì
   toàn bộ mục Currency Exchange của list vô nghĩa.
3. Có ngân sách cho API tin tức có key để chạy 4 phép thử ở trên không? Không có key
   thì không thể kết luận về mục News.
4. `#27` (Capability thứ năm cho hồ sơ doanh nghiệp) còn đang mở — nếu nó được làm,
   Capability vĩ mô có nên đi kèm cùng đợt để chỉ mở rộng `SOURCE_OWNERSHIP_BY_CAPABILITY`
   một lần?
