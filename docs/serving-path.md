# Đường phục vụ: endpoint nào đọc store, endpoint nào đóng băng

`docs/adr/0001` đặt ra lời hứa: request của người dùng không chạm `Provider Source`. Lời hứa đó **không** phủ toàn bộ API — nó phủ những gì `Collector` thu thập cho `Universe`. Bảng dưới nói rõ từng endpoint per-symbol đứng ở đâu và vì sao, để không ai phải đoán bằng cách đọc code.

Quyết định phạm vi nằm ở #27.

## Đọc từ store

| Endpoint | Capability | Ghi chú |
|---|---|---|
| `GET /stocks/{symbol}/snapshot` | cả bốn | Phiên gần nhất, mỗi phần kèm nguồn và tuổi dữ liệu |
| `GET /stocks/{symbol}/series/market` | `market` | Chuỗi phiên, `interval` `1D`/`1W`/`1M`. Bar tuần/tháng gộp từ phiên, không lấy mẫu |
| `GET /stocks/{symbol}/series/valuation` | `valuation` | P/E, P/B từng phiên. Không có `interval`: trung bình một tỷ số là một khẳng định hệ thống không có cơ sở để đưa ra |

Cả ba từ chối mã ngoài Universe bằng 404 với cùng một câu, và từ chối chuỗi ký tự không phải mã bằng 422 — hai lỗi khác nhau, người dùng đi sửa hai chỗ khác nhau.

Tuổi dữ liệu tính từ `effective_at` (phiên mà số liệu nói về), không phải từ lúc job chạy. Với chuỗi, chỉ phiên mới nhất được đánh giá cũ hay không: phần còn lại của lịch sử cũ theo định nghĩa.

## Đóng băng — vẫn gọi provider trong request

| Nhóm | Endpoint | Vì sao đóng băng |
|---|---|---|
| Lịch sử dưới một phiên | `/{symbol}/history` với `interval` `1m`…`1H` | Store giữ một bar mỗi phiên. Đây cũng là đường duy nhất cho mã **ngoài** Universe |
| Trong phiên | `/{symbol}/intraday`, `/{symbol}/volume-analysis`, `/{symbol}/volume-anomalies`, `/{symbol}/intraday-order-stats` | Luồng trong phiên nằm ngoài phạm vi `docs/adr/0001` và #6 |
| Hồ sơ doanh nghiệp | `/{symbol}/company`, `/detail`, `/shareholders`, `/officers`, `/insider-deals`, `/ratio-summary` | Không `Capability` nào chứa dữ liệu này. Đưa vào store nghĩa là thêm `Capability` thứ năm cùng `Adapter` của nó — cân nhắc ở #27 và tạm bỏ: dữ liệu đổi theo sự kiện doanh nghiệp chứ không theo phiên, nên tốn rất ít hạn mức |
| Báo cáo tài chính | `/{symbol}/financials/*` (6 endpoint) | `FundamentalSnapshot` giữ kỳ báo cáo, LNST 12 tháng và vốn chủ — vừa đủ cho điểm sức khoẻ. Sáu endpoint này trả báo cáo đầy đủ; nới hợp đồng ingestion tới hình dạng đó là việc riêng, chưa làm |
| Toàn thị trường | `/price-board`, `/market-indices`, `/analytics/*`, … | #6 đóng băng ngay trong spec |

Đóng băng **không** có nghĩa là hỏng hay sắp xoá. Nghĩa là: hành vi giữ nguyên, không mở rộng, và ai đọc phải biết những endpoint này tiêu hạn mức theo số người dùng chứ không theo lượng dữ liệu.

## Frontend chọn đường nào

Biểu đồ giá thử `/series/market` trước cho mọi khoảng từ 5 phiên trở lên; gặp 404 thì lùi về `/history`. Nên với mã trong Universe, biểu đồ dài không tốn một lời gọi provider nào; với mã ngoài Universe nó vẫn vẽ được, chỉ là bằng đường đóng băng. Khoảng "1 phiên" luôn đi `/history` vì nó cần bar 5 phút.
