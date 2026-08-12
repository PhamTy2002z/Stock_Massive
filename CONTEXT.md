# Stock_Massive

Nền tảng phân tích sâu cổ phiếu Việt Nam: người dùng chọn một số ít mã đưa vào Watchlist, hệ thống dựng Analysis — số liệu, insight, biểu đồ và nhận định — cho chính những mã đó mỗi ngày giao dịch. Không phải công cụ theo dõi toàn thị trường; có đưa nhận định vùng giá cụ thể kèm miễn trừ trách nhiệm.

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

### Sản phẩm AI

**Watchlist**:
Danh sách mã một người dùng đã lưu để được phân tích lại mỗi Trading Day, trần 10 mã; mã đã thành `unsupported` không tính vào trần. Khác Universe: Universe là cam kết thu thập dữ liệu của hệ thống, Watchlist là lựa chọn của từng người dùng — nên trần Watchlist có mặt trong giao diện, còn trần Universe thì không.
_Avoid_: wishlist, favorites, danh mục

**Analysis**:
Bản phân tích AI của một mã cho một Trading Day — dashboard theo template cố định cộng nhận định bằng chữ. Khoá theo `(symbol, trading_day)` và dùng chung toàn hệ thống, không thuộc về người dùng nào: hai Watchlist chứa cùng một mã đọc đúng một Analysis, thêm lại một mã vừa gỡ trong cùng ngày không sinh bản mới, và gỡ mã không xoá gì. Đổi lại, Analysis không được cá nhân hoá theo người dùng.
_Avoid_: report, insight, bản tin

**Analysis Run**:
Bản ghi việc sản xuất một Analysis cho một `(symbol, trading_day)`: `pending` khi Trading Day đã có Snapshot nhưng chưa tới lượt mã này, `producing` khi đang chạy, `ready`, hoặc `failed` kèm lý do và số lần đã thử. Tách khỏi Analysis vì trạng thái thất bại của từng mã phải sống sót qua một lần restart — không có nó thì một mã fail trông y hệt một mã chưa tới lượt, và giao diện không biết có nên mời thử lại. Một Analysis Run ở `ready` luôn có nghĩa Analysis tương ứng đã tồn tại đầy đủ; trạng thái nửa vời chỉ sống ở đây, không bao giờ ở Analysis.
_Avoid_: job, task, attempt

**Thread**:
Một cuộc hội thoại giữa một người dùng và agent, giữ toàn bộ ngữ cảnh mà v1 có — ngoài Thread, v1 không có ký ức dài hạn nào. Mang theo danh sách mã nó đã chạm, để trả lời được "những Thread nào nói về FPT" mà không cần bảng nối. Thứ tự tin nhắn do một số thứ tự trong Thread giữ, không do thời điểm ghi: hai tin nhắn có thể trùng millisecond khi đang stream.
_Avoid_: conversation, chat, session

**Turn**:
Một lượt đối đáp trong một Thread: tin nhắn của người dùng, các vòng gọi tool mà agent thực hiện để trả lời, rồi câu trả lời. Là đơn vị của mọi trần trong hệ thống — trần vòng gọi tool, trần phiên đồng thời, chi phí token — và là đơn vị người dùng huỷ được. Một Turn bị huỷ hoặc chết giữa đường vẫn để lại Tool Call Trace của phần đã chạy.
_Avoid_: request, exchange, round

**Tool Call Trace**:
Bản ghi một lần agent gọi tool — tên, tham số, kết quả, độ trễ, token, lỗi. Neo vào tin nhắn của người dùng đã khởi phát Turn đó, vì tin nhắn ấy đã tồn tại trước lần gọi đầu tiên còn câu trả lời thì chưa. Đủ để đọc lại chuỗi quyết định của agent, nhưng không cam kết chạy lại ra kết quả cũ: dữ liệu trong store đổi mỗi đêm và model không tất định.
_Avoid_: log, audit, span

**Capability Probe**:
Bài kiểm tra hợp đồng chạy lúc khởi động trên tuyến LLM đang cấu hình: buộc `tool_choice`, gọi tool song song khi stream, structured output, và một vòng tool khép kín. Tuyến nào không qua thì hệ thống từ chối khởi động và in lý do, thay vì chạy với một tuyến âm thầm bỏ rơi tham số. Tồn tại vì lớp dịch của gateway từng bỏ im lặng đúng những tham số này — thất bại kiểu đó không lộ ra ở runtime, nó chỉ làm câu trả lời sai đi.
_Avoid_: health check, smoke test, ping

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

**Trading Day**:
Một ngày mà hệ thống có Snapshot EOD — `date(max(effective_at))` trong `provider_snapshots`, chứ không phải một ngày trên lịch. Định nghĩa theo dữ liệu vì hệ thống không có lịch nghỉ lễ: `is_trading_day()` chỉ biết thứ trong tuần nên đọc Tết thành ngày giao dịch, và một Analysis đóng nhãn một phiên không tồn tại thì không diff được với bản của phiên sau.
_Avoid_: session date, ngày giao dịch theo lịch
