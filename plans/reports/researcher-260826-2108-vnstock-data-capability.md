# Research: khả năng dữ liệu vnstock — tier Free vs Bronze vs Diamond

Ngày: 2026-08-26. Nguồn chính: introspect trực tiếp package `vnstock` 4.0.5 +
`vnai` 2.5.6 đã cài ở `apps/api/.venv` (đọc source + chạy live call thật ra
production API của VCI/Vietcap), đối chiếu GitHub README + web docs.
Ký hiệu: **OBSERVED** = đọc code hoặc chạy thật trong session này. **PRIOR** =
tài liệu web/README, chưa tự chạy. **UNKNOWN** = không tìm được bằng chứng
công khai.

## Tóm tắt kiến trúc quan trọng nhất

`pip install vnstock` (bản cài trong repo, 4.0.5, mới nhất PyPI 4.0.7) **không
có khái niệm Bronze/Diamond như một "chế độ" riêng trong chính package này**.
Cơ chế thật (OBSERVED, đọc `vnai/beam/auth.py` + `vnai/beam/patching.py`):

- `vnai` là package con theo dõi usage + gate tính năng, cài kèm `vnstock`.
- Tier được xác định qua **API key** đăng ký tại vnstocks.com, lưu ở
  `~/.vnstock/api_key.json`. Không có key → tier `guest`.
- **QUAN TRỌNG**: monkey-patch trong `vnai/beam/patching.py::limit_ohlcv_periods`
  áp giới hạn độ sâu OHLCV **cứng, không đọc tier** — tất cả tier (kể cả có
  API key trả phí) qua package `vnstock` công khai đều bị cắt: 1 phút → 180
  ngày, 5m/15m/30m/1H → 365 ngày, ngày/tuần/tháng → 8 năm, intraday tick →
  30.000 dòng/lần gọi. Để bỏ giới hạn này, docstring của
  `vnstock/api/__init__.py` (OBSERVED) nói thẳng: phải đổi sang package **riêng
  tư, chỉ cấp cho sponsor**: `vnstock_data` (a.k.a `vnstock-data-pro`), không
  public trên PyPI, không introspect được ở đây.
- Chỉ có **báo cáo tài chính** (`balance_sheet/income_statement/cash_flow/ratio`)
  là tier-aware ngay trong package công khai: `guest=4 kỳ`, `free (có API key)=8
  kỳ`, `bronze/silver/golden=None (không giới hạn)` (OBSERVED,
  `vnai/beam/patching.py::get_max_periods`).
- Rate limit theo tier (OBSERVED, `vnai/beam/auth.py::TIER_LIMITS`, req/phút -
  giờ - ngày): `guest 20-1200-5000` · `free 60-3600-10000` ·
  `bronze 180-10800-50000` · `silver 300-15000-100000` ·
  `golden 500-30000-150000` · `diamond 600-36000-180000`. Khớp với con số
  180/600 mà CLAUDE.md đã ghi.

## Bảng tier × capability

| Capability | Guest (không key) | Free (có API key) | Bronze/Silver/Golden/Diamond (vnstock, có key trả phí) | `vnstock_data` (sponsor-only, riêng tư) |
|---|---|---|---|---|
| Rate limit | 20/phút | 60/phút | 180→600/phút theo bậc | không rõ, PRIOR: cao hơn nhiều ("tăng tốc 5-8 lần") |
| OHLCV 1 phút | 6 tháng (cứng) | 6 tháng (cứng) | **vẫn 6 tháng** — patch không đọc tier | PRIOR: "vô hạn"/đầy đủ lịch sử |
| OHLCV 5/15/30m/1H | 1 năm (cứng) | 1 năm (cứng) | **vẫn 1 năm** | PRIOR: không giới hạn |
| OHLCV daily/week/month | 8 năm (cứng) | 8 năm (cứng) | **vẫn 8 năm** | PRIOR: không giới hạn |
| Intraday tick (`Quote.intraday`) | 30.000 dòng/call, cursor `last_time` | như guest | như guest | PRIOR: cao hơn |
| Báo cáo tài chính (số kỳ/lần gọi) | 4 kỳ | 8 kỳ | **không giới hạn** (đây là feature THẬT sự tier-gated trong package công khai) | full |
| Batch/screener toàn thị trường | không có (chỉ gọi từng mã) | không có | không có | UNKNOWN |
| Derivative price board, odd-lot pricing | không có (theo docstring cảnh báo) | không có | không có | PRIOR: có (docstring liệt kê rõ) |
| Licence thương mại/SaaS | **Cấm** (LICENSE.md: cá nhân/nghiên cứu, cấm thương mại, cấm phân phối lại) | Cấm như guest | Cấm như guest — trả tiền sponsor **không** đổi licence sử dụng | UNKNOWN — cần hỏi trực tiếp `support@vnstocks.com`, giới hạn "≤500 user" trong CLAUDE.md **không xác minh được công khai** |

## Trả lời từng câu hỏi

**1. Intraday (câu hỏi quan trọng nhất)** — OBSERVED, đã chạy live thật:
`vnstock.api.quote.Quote(symbol, source="VCI").history(interval="15m",
count_back=...)` trả bar **1 phút native rồi resample client-side** thành
5m/15m/30m/1H (xem `_INTERVAL_MAP`: cả 4 khung này đều map server-side về
`ONE_MINUTE`, resample bằng pandas ở `_RESAMPLE_MAP`). Đã gọi live cho VNM:
lấy được **16.321 dòng 1-phút từ 2026-05-15 đến 2026-08-26** không lỗi, không
cần API key. Giới hạn cứng là 6 tháng lùi từ hiện tại cho khung 1m, 1 năm cho
5/15/30m/1H — **thoải mái đủ cho "30 phiên gần nhất bucket 15 phút"** (30
phiên ≈ 6 tuần, nằm sâu trong ngưỡng 1 năm). Ngoài ra còn `Quote.intraday()` —
dữ liệu khớp lệnh tick thật (giá + khối lượng mỗi lệnh khớp), trả tối đa
30.000 dòng/lần gọi qua endpoint `LEData/getAll`, phân trang bằng cursor
`last_time`; không thấy giới hạn ngày cụ thể trong code nhưng đây rõ ràng là
feed thời gian thực của sàn (matching engine), thực tế chỉ hữu dụng cho phiên
hiện tại/gần nhất — PRIOR/chưa verify độ sâu lịch sử thực của endpoint này vì
không test lúc thị trường mở.
→ **Kết luận: đủ cho use case "30 phiên × bucket 15 phút cho 1 mã" ngay ở
guest tier, không cần Bronze.**

**2. Historical OHLCV daily** — OBSERVED: guest tier lấy được daily VNINDEX
1.738 dòng từ 2019-09-12 đến nay (~7 năm dữ liệu thật có, nằm trong ngưỡng 8
năm). Rate limit 20/phút (guest) — 60/phút (free key).

**3. Financial statements** — OBSERVED: chỉ **1 mã/lần gọi**, không có
endpoint batch/screener toàn thị trường trong package công khai (đã grep
toàn bộ `vnstock/explorer`, không có "screener"). Guest = 4 kỳ gần nhất
(income_statement live trả `2026-Q2, 2026-Q1, 2025-Q4, 2025-Q3`), free (key)
= 8 kỳ, Bronze trở lên = không giới hạn kỳ nhưng **vẫn phải gọi tuần tự từng
mã**. `ratio()` có sẵn P/E, P/B, P/S, EV/EBITDA, ROE, ROA, current/quick
ratio, debt/equity — đủ cho "lợi nhuận cao nhưng giá chưa tăng" nếu tính thủ
công qua income_statement + giá. **Rủi ro vận hành cho use case "Top 10 toàn
market Q3"**: quét ~1.600 mã × 1 request/mã tuần tự → guest 20/phút ≈ 80
phút, free 60/phút ≈ 27 phút, Bronze 180/phút ≈ 9 phút một lượt full-market
scan. Không có cách nào lấy 1 request cho nhiều mã.

**4. Company/listing** — OBSERVED live: `Listing(source="VCI").all_symbols()`
→ 1.751 mã đang niêm yết. `symbols_by_exchange()` → HSX 756, HNX 313, UPCOM
820, BOND 95, DELISTED 1.602 (tổng 3.586 dòng bao gồm lịch sử). Có
`industries_icb()` (phân ngành ICB) và `symbols_by_industries()` — đủ cho
sector/industry classification. Đủ HOSE + HNX + UPCOM cho use case
"toàn market Q3 screener".

**5. Market index** — OBSERVED: VNINDEX qua `Quote(symbol="VNINDEX",
source="VCI")` hoạt động bình thường (dùng `_VCI_INDEX_MAPPING` để map ký hiệu
chỉ số nội bộ). `Listing.all_future_indices()` có sẵn cho phái sinh. Không
test riêng VN30/HNX-Index nhưng cùng cơ chế mapping nên PRIOR tin cậy cao là
hoạt động tương tự.

**6. Foreign flow / proprietary trading** — OBSERVED: **không có time-series
khối ngoại mua/bán ròng theo phiên** trong package VCI công khai. Chỉ có
snapshot hiện tại trong `Trading.price_board()`: `foreign_total_volume`,
`foreign_total_room`, `foreign_holding_room` (room còn lại, không phải giá
trị mua/bán ròng lịch sử). `Company.trading_stats()` cũng chỉ là snapshot.
Không thấy proprietary trading (tự doanh) ở đâu trong VCI explorer. Đây là lý
do dự án đang tự lưu `foreign_net_value_vnd` trong bar riêng
(`src/stocks/signals/foreign_flow.py`) từ nguồn khác đã bị rip-out (DNSE) —
**nếu chỉ dùng vnstock, không tái tạo được field này**.

**7. Rate limit thực tế + giá tiền** — OBSERVED rate limit (bảng trên).
**Giá tiền VND/tháng từng gói: UNKNOWN** — trang `vnstocks.com/insiders-program`
và `onboard-member` render bằng JS, WebFetch không lấy được nội dung bảng
giá; GitHub Sponsors đã bị thay bằng thanh toán trực tiếp trên site (Stripe),
cũng không lộ số tiền qua fetch. Không tìm thấy trang cache/blog nào công khai
số tiền cụ thể. Cần hỏi trực tiếp `support@vnstocks.com` hoặc đăng nhập trang
để xem giá.

**8. Điều khoản licence** — OBSERVED, 2 nguồn độc lập khớp nhau:
(a) `LICENSE.md` đóng gói trong wheel `vnstock-4.0.5.dist-info/licenses/` —
"chỉ dành cho mục đích cá nhân... nghiêm cấm sử dụng thương mại bởi bất kỳ tổ
chức nào... nghiêm cấm phân phối lại" trừ khi có văn bản đồng ý từ tác giả.
(b) README GitHub hiện tại nói thẳng "toolkit is aimed at individuals and not
for commercial purposes", muốn dùng thương mại phải liên hệ tác giả xin
licence riêng.
`pip show vnstock` cũng in ra field License: "Custom: Personal, research,
non-commercial; contact support@vnstocks.com for other use" — 3 nguồn khớp.
**Trả tiền sponsor (Bronze→Diamond) không tự động đổi licence sử dụng** —
patch code chỉ nới rate limit + số kỳ báo cáo tài chính, không có dòng nào
cấp quyền thương mại. Muốn build SaaS/redistribute hợp pháp phải xin licence
riêng bằng văn bản, khả năng cao gắn với gói sponsor cao + hợp đồng riêng —
**claim "≤500 user" trong CLAUDE.md không xác minh được qua nguồn công khai
trong lần research này** (UNKNOWN — có thể đến từ email trao đổi riêng của
người dùng với support@vnstocks.com, không phải từ tài liệu public).

**9. Rủi ro nguồn dữ liệu** — Package hiện tại (4.0.5) **chỉ còn nguồn VCI**
(Vietcap) làm explorer chính cho equity (`vnstock/explorer/vci/`), cộng MSN
(forex/vàng/crypto), KBS (một nguồn phụ khác), fmarket (quỹ mở). **TCBS đã bị
loại khỏi package cài đặt** — chỉ còn vết tích trong vài file mapping/const,
không còn module `explorer/tcbs`. PRIOR (WebSearch): VCI từng phải migrate
Listing/Company/Finance từ GraphQL sang REST vì lỗi kết nối — xác nhận các
nguồn này là **scrape endpoint nội bộ của công ty chứng khoán, không phải API
chính thức có SLA**, dễ gãy khi Vietcap đổi cấu trúc site. Class
`vnstock.api.quote.Quote.history()` gọi thẳng
`https://trading.vietcap.com.vn/.../chart/OHLCChart/gap-chart` — endpoint nội
bộ dashboard trading của Vietcap, không phải API public có tài liệu chính
thức.
**Cảnh báo vận hành thêm**: lớp `Vnstock` legacy (`from vnstock import
Vnstock`, đúng cú pháp CLAUDE.md có thể đang dùng ở nơi khác trong repo) sẽ
**EOL 2026-08-31** (PRIOR, WebSearch — chỉ còn 5 ngày kể từ hôm nay) — nên
dùng `from vnstock.api.quote import Quote` / `from vnstock.api.financial
import Finance` / `from vnstock.api.listing import Listing` thay vì lớp
`Vnstock()` facade cũ.

## Adoption risk

- **Community/OSS risk cao**: tác giả đơn lẻ (Thinh Vu), monetize qua
  sponsor, đã đổi kiến trúc licence/tier nhiều lần (GitHub Sponsor → website
  trực tiếp, class `Vnstock` → `vnstock.api`, EOL liên tục). Breaking change
  history: OBSERVED ít nhất 1 lần migrate GraphQL→REST cho VCI, 1 lần đổi hạ
  tầng licence (vnai package tách riêng để đo usage — bản thân việc này là
  dấu hiệu tác giả đang siết chặt kiểm soát dần qua thời gian).
- **Không có SLA, endpoint là nội bộ của Vietcap** — rủi ro gãy bất cứ lúc
  nào không báo trước, không có changelog chính thức từ phía Vietcap.
- **Licence rõ ràng cấm thương mại/SaaS** ở mọi tier công khai — đây là rủi
  ro pháp lý thật, không phải rủi ro kỹ thuật, và **không tự giải quyết bằng
  cách trả tiền sponsor** (patch code không cấp quyền licence, chỉ nới quota
  kỹ thuật).

## Khuyến nghị (xếp hạng)

1. **Cho use case "30 phiên gần nhất, bucket 15 phút, 1 mã"**: dùng
   `Quote(source="VCI").history(interval="15m", count_back=~120)` ở **guest
   hoặc free tier là đủ**, không cần Bronze — đã verify sống. Không cần nâng
   cấp gì cho use case này.
2. **Cho use case "Top 10 mã lợi nhuận Q3 toàn market"**: khả thi về mặt dữ
   liệu (đủ mã, đủ ratio) nhưng **chi phí vận hành là số lượng request tuần
   tự** (~1.600 lần gọi/lượt scan) — Bronze (180/phút, ~9 phút/lượt) là mức
   hợp lý tối thiểu để chạy job này định kỳ mà không quá chậm; guest/free quá
   chậm (27-80 phút/lượt) cho một job cần chạy lại nhiều lần trong ngày.
3. **Trước khi build bất kỳ SaaS/B2B nào dựa trên vnstock**: bắt buộc phải có
   xác nhận bằng văn bản từ `support@vnstocks.com` về phạm vi licence thương
   mại — đừng dựa vào việc "đã trả tiền Bronze/Diamond" để suy ra đã được
   phép thương mại hoá, vì bằng chứng code cho thấy hai việc này tách biệt.
4. Nếu cần lịch sử intraday/OHLCV vượt 6 tháng-1 năm-8 năm, hoặc cần feature
   khối ngoại/tự doanh theo thời gian, **vnstock công khai không đáp ứng
   được** dù trả tiền — phải hỏi thẳng `vnstock_data` (sponsor-only) hoặc tìm
   nguồn khác.

## Unresolved / không verify được

- Giá tiền VND/tháng chính xác từng gói Bronze/Silver/Golden/Diamond — trang
  web JS-rendered, không fetch được nội dung động.
- Claim "licence phân phối ≤500 user" ở CLAUDE.md — không tìm thấy nguồn công
  khai xác nhận trong lần research này; nếu quan trọng cho quyết định B2B,
  cần email lại `support@vnstocks.com` để lấy văn bản chính thức.
- Độ sâu lịch sử thực của `Quote.intraday()` (tick khớp lệnh) — không test
  được lúc thị trường đang mở phiên thật, chỉ đọc code (không thấy giới hạn
  ngày rõ ràng ngoài cap 30.000 dòng/call).
- Chưa test trực tiếp package `vnstock_data` (sponsor-only, không có quyền
  cài) — mọi claim về nó chỉ dựa vào docstring của package công khai và trang
  marketing, chưa verify độc lập.
- Chưa kiểm tra VN30-Index/HNX-Index riêng lẻ (chỉ verify VNINDEX) — PRIOR
  suy luận từ cùng cơ chế `_VCI_INDEX_MAPPING`.
