# Vnstock Bronze cho VisgniteAI — kiểm định trước khi mua

Ngày kiểm định: 2026-08-29  
Phạm vi: quyền lợi kỹ thuật, độ phù hợp với VisgniteAI, giới hạn giấy phép và
các điều kiện cần xác nhận trước khi thanh toán.

## Kết luận trực tiếp

**Bronze là gói hợp lý để phát triển VisgniteAI, nhưng chưa đủ bằng chứng để
cam kết “mua là dùng được toàn bộ” và không phải gói để chạy sản phẩm thương
mại.**

Bronze mở **toàn bộ thư viện riêng `vnstock_data`** cùng mức 180 yêu cầu/phút,
10.800/giờ, 50.000/ngày và 600.000/tháng. Đây là bước nhảy lớn hơn việc chỉ tăng
quota: nó mở Market, Reference, Fundamental, Analytics, Macro, Insights và dữ
liệu đa tài sản. Tuy nhiên Bronze không có `vnstock_ta`, `vnstock_news`,
`vnstock_pipeline`, tăng tốc pipeline 5X hay WebSocket thời gian thực.

Khuyến nghị mua chỉ sau khi Vnstock trả lời bằng văn bản các điểm ở mục
“Điều kiện go/no-go”, hoặc cấp trial để chạy ma trận nghiệm thu. Package Sponsor
là closed-source nên tài liệu công khai không thể chứng minh endpoint thực tế,
schema, độ sâu lịch sử và cách tính quota tại thời điểm mua.

## Sửa lại kết luận từ báo cáo 2026-08-26

Báo cáo cũ chỉ introspect được package OSS `vnstock`, nên đánh dấu nhiều khả
năng Sponsor là UNKNOWN. Tài liệu chính thức hiện hành của `vnstock_data`
v3.2.8 xác nhận Bronze được cấp **trọn gói `vnstock_data`**, không chỉ nới quota
cho package OSS. Vì vậy:

- Kết luận cũ về hạn chế của `vnstock` Community vẫn đúng.
- Kết luận “Bronze chỉ giúp chạy nhanh hơn” không còn đầy đủ.
- Các hàm khối ngoại, tự doanh, sổ lệnh, giao dịch thỏa thuận, lô lẻ, screener,
  macro và multi-asset cần đánh giá theo `vnstock_data`, không theo package OSS.
- Chưa thể nâng bằng chứng lên OBSERVED cho đến khi có quyền cài và chạy package
  Sponsor thật.

## Bronze thực sự mở những gì

| Nhóm | Quyền Bronze | Giá trị với VisgniteAI | Mức ưu tiên |
|---|---|---|---|
| Quota | 180/phút; 10.800/giờ; 50.000/ngày; 600.000/tháng | Full-market scan và backfill nhanh hơn, nhưng app phải bỏ limiter Community cũ | Rất cao |
| Package | Toàn bộ `vnstock_data`; 150+ hàm theo tài liệu | Mở surface Sponsor thật thay vì chỉ dùng `vnstock` OSS | Bắt buộc |
| Equity market | OHLCV, quote, trade history, trades, order book, session stats, foreign flow, proprietary flow, block trades, odd lot, volume profile, summary | Lấp các trường flow/evidence còn thiếu; nâng Signal Desk và market monitor | Rất cao |
| Reference | Danh sách mã, sàn/ngành, index/member, công ty, cổ đông, lãnh đạo, công ty con, sự kiện, hồ sơ công bố, tin theo mã | Nâng chất lượng entity, sự kiện và provenance | Rất cao |
| Fundamental | Bảng cân đối, KQKD, dòng tiền, ratio, note, filing, financial health; tối đa số kỳ nguồn có | Phù hợp kho tài chính dạng long và nghiên cứu point-in-time | Rất cao |
| Analytics | Lịch sử P/E, P/B và định giá chỉ số | Thêm benchmark và market regime có bằng chứng | Cao |
| Insights | Ranking, screener và các nhóm sentiment/flow/sector/equity thử nghiệm | Giảm số request per-symbol và tạo candidate set cho scan | Cao, nhưng experimental phải gắn nhãn |
| Macro | GDP, CPI, IIP, xuất nhập khẩu, FDI, cung tiền, lãi suất, FX, vàng, dầu, thép, DXY, Fed, lợi suất | Cho phép domain pack vĩ mô thứ hai | Trung bình-cao |
| Multi-asset | Index, futures, warrants, bonds, ETF, funds, crypto, forex, commodities | Dữ liệu có quyền truy cập nhưng phần lớn ngoài scope HOSE/HNX/UPCOM hiện tại | Chỉ mở khi có quyết định sản phẩm |
| Hạ tầng | Installer CLI/GUI, Python 3.10–3.14, server/cloud/CI/Docker | Có thể tích hợp backend và CI; cần xác nhận cách tính device cho container | Cao |

### Chi tiết surface đáng dùng ngay

1. **Market intelligence:** `foreign_flow`, `proprietary_flow`, `order_book`,
   `trades`, `session_stats`, `block_trades`, `odd_lot`, `volume_profile` giúp
   biến các nhận định dòng tiền/thanh khoản thành dữ liệu truy nguyên được.
2. **Fundamental intelligence:** taxonomy chuẩn hóa khoảng 1.700 chỉ tiêu và
   phân loại doanh nghiệp thường/ngân hàng/chứng khoán/bảo hiểm phù hợp hơn với
   bảng financial long hiện có; vẫn phải adapter schema và kiểm thử đơn vị.
3. **Screening:** ranking và screener toàn thị trường có thể tạo candidate set
   trước khi chạy phân tích sâu, tiết kiệm quota hơn quét mọi hàm cho mọi mã.
4. **Company evidence:** cổ đông, lãnh đạo, công ty con, sự kiện, filing và tin
   theo mã làm giàu evidence graph. Đây không thay thế package `vnstock_news`
   dành cho luồng tin rộng.
5. **Macro regime:** dữ liệu kinh tế, tiền tệ, hàng hóa và toàn cầu có thể làm
   domain pack thứ hai sau khi có contract lưu trữ, freshness và provenance.

## Những gì Bronze không mở

| Không có ở Bronze | Hệ quả |
|---|---|
| `vnstock_ta` | Không có thư viện TA Sponsor; VisgniteAI nên tiếp tục tính chỉ báo bằng engine deterministic của mình |
| `vnstock_news` | Không có pipeline tin tức toàn diện; chỉ có tin theo mã trong Reference |
| `vnstock_pipeline` | Không có bộ pipeline/scheduler Sponsor và không được hưởng tăng tốc tải 5X của Golden/Diamond |
| WebSocket real-time | Bronze dùng REST độ trễ quảng cáo 1–3 giây; Golden/Diamond mới có WebSocket real-time |
| Deep Blog | Không thuộc Bronze |
| Quyền phân phối thương mại | Bronze dành cho phát triển/nghiên cứu; không phải giấy phép public SaaS |
| SLA nguồn dữ liệu | Vnstock là connector tới nguồn bên thứ ba; source hoặc schema có thể thay đổi |

“Vnstock Agent Guide” có ở cả Community, vì vậy không phải lợi ích tăng thêm của
Bronze.

## Mức sẵn sàng của VisgniteAI

Bronze hiện **chưa plug-and-play** với codebase:

- `apps/api/requirements.txt` chỉ khai báo `vnstock`, chưa có installer/private
  package `vnstock_data`.
- `apps/api/src/stocks/providers/vnstock_daily.py` và
  `apps/api/src/stocks/financial/fetch.py` đang import API Community.
- `apps/api/src/core/quota.py` đang model guest/key Community (20/60 mỗi phút và
  cửa sổ giờ cũ), chưa model Bronze theo phút/giờ/ngày/tháng.
- Repo đã có nền lưu `BarDaily`, `BarIntraday15m`, financial statement dạng
  long, snapshot, realtime event/checkpoint/reconciliation và các contract flow;
  vì vậy phần equity Sponsor có điểm gắn rõ ràng.
- Macro, Analytics và Insights chưa có đầy đủ contract lưu trữ/provenance. Không
  nên đưa DataFrame provider thẳng vào LLM hoặc UI vì sẽ phá cam kết evidence,
  as-of, freshness, unit và quality state của sản phẩm.
- Product hiện chỉ tập trung HOSE/HNX/UPCOM. Crypto, forex, fund, bond và phái
  sinh là quyền lợi sẵn có nhưng đưa vào UI là mở rộng scope, không phải bước
  tích hợp mặc định.

Một full-market financial scan hiện có thể tạo tối đa khoảng 6.092 request.
Theo trần phút lý thuyết, Community cần khoảng 101,5 phút và Bronze khoảng
33,8 phút; Bronze dùng khoảng 12,2% quota ngày thay vì 60,9%. Đây chỉ là trần
lý thuyết, chưa tính phân trang nội bộ, retry, latency và các job khác. Việc
Vnstock tính quota theo method hay từng page là một blocker cần xác nhận.

## Kế hoạch dùng hết Bronze sau khi được xác nhận

### Gate 0 — nghiệm thu quyền đã mua

- Cài package Sponsor bằng installer trong môi trường tách biệt; API key chỉ ở
  `.env`/secret store, không gửi qua chat và không commit.
- Xác nhận tier và bốn cửa sổ quota thật.
- Chạy smoke test từng domain, từng source và từng method quan trọng.
- Đo schema, unit, timezone, pagination, empty/error behavior và source fallback.
- Kiểm tra device ID trên local, CI, Docker rebuild và VPS redeploy.

Nếu quyền thực tế không khớp xác nhận bằng văn bản, dừng tích hợp và yêu cầu xử
lý gói; không sửa app theo dữ liệu đoán.

### Gate 1 — lõi Sponsor

- Thêm adapter `vnstock_data` sau provider contract hiện có.
- Thay quota arbiter bằng tier-aware limiter cho phút/giờ/ngày/tháng, dùng chung
  giữa worker/process/device.
- Chuẩn hóa source, symbol, timestamp, unit, pagination, quality và lỗi.
- Thêm contract tests bằng response thật đã được phép lưu, không dùng fake data
  thay cho hành vi provider.

### Gate 2 — equity full-power

- Market bars/quote/trades/order book/session stats.
- Foreign flow, proprietary flow, block/odd-lot và volume profile.
- Fundamental taxonomy, filings, company/reference/event.
- Ranking/screener làm candidate generator, sau đó mới phân tích sâu.

### Gate 3 — domain mở rộng có kiểm soát

- Analytics và Macro được persist dưới contract evidence riêng.
- Insights experimental có feature flag, version và fallback; không coi là API
  ổn định.
- Multi-asset chỉ triển khai sau quyết định sản phẩm riêng.

## Điều kiện go/no-go trước khi thanh toán

Gửi Vnstock và yêu cầu họ trả lời bằng văn bản:

1. Bronze có gồm mọi endpoint `vnstock_data` v3.2.8, đặc biệt CafeF Adapter,
   Insights experimental và tất cả domain multi-asset không?
2. Tài liệu Market ghi 1m/5m/15m/1H chỉ dành cho “Premium/Pro tùy nguồn”. Bronze
   có quyền trên KBS/VCI/CafeF không, và độ sâu lịch sử thật của từng
   interval/source là bao nhiêu?
3. `get_all=True`/auto-pagination tính một request Python hay từng page upstream?
   Quota có dùng chung giữa source, thiết bị, process và container không?
4. Bronze cho một macOS, một Windows, một Linux. Docker rebuild, ephemeral CI
   runner hoặc redeploy cùng Linux host có bị tính là thiết bị mới/đổi thiết bị
   không?
5. Bronze có cho phép phát triển và private-test một SaaS tương lai, lưu/cache
   raw data trong PostgreSQL, tạo derived analytics và cho tester nội bộ dùng
   không? Khi hết subscription phải xóa hoặc ngừng phần dữ liệu nào?
6. Khi nâng Diamond, quyền phân phối dưới 500 user có tự áp dụng cho raw/derived
   data hay vẫn cần giấy phép thương mại bằng văn bản riêng?
7. Có trial 24–72 giờ hoặc cơ chế refund để chạy acceptance matrix trước khi
   cam kết không?
8. Giá Bronze đang hiển thị 180.000đ áp dụng cho kỳ nào, và tiền đã trả có được
   trừ khi upgrade lên Diamond không?
9. Endpoint/source nào bị giới hạn trên cloud/VPS IP, và Vnstock cam kết mức hỗ
   trợ hoặc SLA nào khi nguồn upstream đổi schema?

### Mẫu tin nhắn gửi support

> Chào Vnstock, tôi đang cân nhắc gói Bronze để phát triển private VisgniteAI,
> một ứng dụng nghiên cứu chứng khoán Việt Nam, dự kiến chỉ lên production sau
> khi nâng Diamond/hoàn tất giấy phép thương mại. Trước khi thanh toán, nhờ đội
> ngũ xác nhận bằng văn bản 9 mục: phạm vi endpoint `vnstock_data` v3.2.8; quyền
> intraday Premium/Pro và history depth; cách tính quota khi pagination; device
> ID cho Docker/CI/VPS; quyền dev/private test/persist/cache/derived analytics;
> điều kiện phân phối dưới 500 user khi lên Diamond; trial/refund; kỳ giá
> 180.000đ và upgrade credit; giới hạn cloud/source/SLA. Tôi có thể gửi kèm
> acceptance matrix chi tiết nếu cần. Cảm ơn đội ngũ.

## Quyết định đề xuất

- **GO có điều kiện cho Bronze để development** nếu Vnstock xác nhận các quyền
  intraday, quota pagination, device/container và private development/storage.
- **NO-GO cho production/commercial bằng Bronze.** Dùng Diamond chỉ sau khi có
  xác nhận giấy phép thương mại phù hợp mô hình VisgniteAI; không suy ra quyền
  thương mại chỉ từ tên tier.
- **NO-GO nếu không có trial hoặc xác nhận bằng văn bản** mà mục tiêu là bảo đảm
  mọi endpoint trước khi chi tiền. Closed package khiến việc bảo đảm 100% bằng
  nguồn công khai là không thể.

## Nguồn chính thức

- Quyền lợi tier: <https://vnstocks.com/insiders-program>
- So sánh Community/Sponsor: <https://vnstocks.com/docs/vnstock/so-sanh-free-va-sponsor>
- Giới thiệu `vnstock_data`: <https://vnstocks.com/docs/vnstock-data/gioi-thieu-vnstock-data>
- Market Layer: <https://vnstocks.com/docs/vnstock-data/market-layer-v3>
- Reference Layer: <https://www.vnstocks.com/docs/vnstock-data/reference-layer-v3>
- Fundamental Layer: <https://vnstocks.com/docs/vnstock-data/fundamental-layer-v3>
- Analytics Layer: <https://vnstocks.com/docs/vnstock-data/analytics-layer-v3>
- Insights Layer: <https://vnstocks.com/docs/vnstock-data/insights-layer-v3>
- Macro Layer: <https://vnstocks.com/docs/vnstock-data/macro-layer-v3>
- Data sources: <https://vnstocks.com/docs/vnstock-data/data-sources>
- Installer/onboarding: <https://vnstocks.com/onboard-member>
- Server/cloud/CI: <https://vnstocks.com/onboard-member/cai-dat-go-loi/cai-dat-nang-cao>
- Giấy phép: <https://www.vnstocks.com/onboard/giay-phep-su-dung>
- Chính sách thành viên: <https://vnstocks.com/onboard-member/chinh-sach-thanh-vien>
- Quyền riêng tư/device data: <https://www.vnstocks.com/onboard/chinh-sach-quyen-rieng-tu>
- Store Bronze: <https://vnstocks.com/store?product=member-bronze>

## Giới hạn và câu hỏi còn mở

- Chưa có quyền cài `vnstock_data`, nên chưa thể chạy live acceptance test.
- Các surface Insights được tài liệu gọi là experimental; behavior có thể đổi.
- “Premium/Pro” trong tài liệu interval chưa được map công khai sang Bronze.
- Chưa có bằng chứng công khai đủ rõ về billing period của giá 180.000đ.
- Quyền commercial/derived-data cần văn bản riêng phù hợp mô hình sản phẩm.
- Không có SLA upstream được xác nhận từ tài liệu đã kiểm tra.
