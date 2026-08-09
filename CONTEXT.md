# Stock_Massive

Nền tảng phân tích sâu cổ phiếu Việt Nam: người dùng chọn một số ít mã đưa vào tài khoản, hệ thống dựng số liệu, insight và biểu đồ cho chính những mã đó. Không phải công cụ theo dõi toàn thị trường, không đưa khuyến nghị mua bán.

## Language

### Nguồn dữ liệu

**Provider Source**:
Một nhà cung cấp dữ liệu bên ngoài mà hệ thống lấy số liệu về — hiện có `vnstock` và `fiinquant`.
_Avoid_: API, data feed, upstream

**Capability**:
Một lớp dữ liệu có thể được sở hữu bởi một Provider Source độc lập với các lớp khác: `market` (giá, khối lượng, dòng tiền), `valuation` (P/E, P/B), `reference` (sở hữu và số lượng cổ phiếu, đổi chậm), `fundamental` (báo cáo tài chính).
_Avoid_: data type, category, domain

**Snapshot**:
Một bản ghi dữ liệu đã chuẩn hoá của một mã tại một thời điểm, sau khi qua ranh giới Provider Source — luôn mang theo nguồn, `effective_at` (dữ liệu nói về lúc nào) và `observed_at` (hệ thống thấy nó lúc nào).
_Avoid_: record, row, data point

**Adapter**:
Đoạn mã dịch phản hồi thô của một Provider Source thành Snapshot. Adapter là nơi duy nhất được biết hình dạng dữ liệu của nhà cung cấp.
_Avoid_: client, wrapper, connector

**Main Source**:
Provider Source được chọn phục vụ một Capability, vì nó có dữ liệu mạnh hơn và hạn mức cao hơn cho lớp dữ liệu đó.
_Avoid_: primary, default provider

**Cover Source**:
Provider Source phục vụ phần một Capability mà Main Source không với tới — nằm ngoài Universe, sâu hơn độ sâu lịch sử được cấp, hoặc nhà cung cấp không có.
_Avoid_: fallback, backup, secondary

### Phạm vi phục vụ

**Universe**:
Tập hợp mã mà hệ thống cam kết thu thập và phân tích, trần 100 mã. Trần là van an toàn cho collector — thời gian chạy và sức chịu của gateway — chứ không phải hạn mức bán cho người dùng, nên không xuất hiện trong giao diện.
_Avoid_: watchlist, danh mục, market coverage

**Backfill**:
Lần nạp lịch sử duy nhất cho một mã mới vào Universe, lấy phần sâu hơn khả năng của Main Source từ Cover Source. Chạy một lần rồi thôi; từ đó Main Source nối tiếp mỗi ngày.
_Avoid_: import, sync, migration

**Collector**:
Tiến trình chạy sau phiên, là nơi duy nhất được gọi ra Provider Source. Request của người dùng không bao giờ chạm tới nhà cung cấp.
_Avoid_: job, worker, crawler
