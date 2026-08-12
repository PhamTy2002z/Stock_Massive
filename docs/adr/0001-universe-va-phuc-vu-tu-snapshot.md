# Universe có trần, dữ liệu phục vụ từ Snapshot

Hệ thống chỉ thu thập và phân tích cho **Universe** — tập mã được cấu hình, trần 100 mã — và mọi endpoint chỉ đọc từ `SnapshotStore`; một collector chạy sau phiên là nơi duy nhất gọi ra ngoài. Mỗi tài khoản chọn tối đa 5 mã.

ADR-0004 introduces one narrow exception to the collection boundary: the
Profit Ranking Census reads minimal fundamental and listing fields market-wide
to determine which 50 symbols enter the Universe. It does not collect market
Snapshots outside the Universe, and the serving boundary remains unchanged.

Trần Universe **không đến từ hạn mức nhà cung cấp**. Đo thực tế (`apps/api/prototypes/probe_fiinquant_free_tier.py`) cho thấy gói FiinQuant free trả về đủ 110 mã lịch sử trong một lời gọi, và hạn mức 90 request/phút tính theo **lời gọi** chứ không theo mã — thu thập EOD cho 100 mã tốn khoảng 60 request/tháng trên hạn mức 100.000. Con số 33 trên trang Pricing chỉ áp cho luồng realtime, thứ kiến trúc này không dùng. Trần tồn tại vì hai lý do khác: gateway trả 504 khi một lời gọi gom quá nhiều mã kèm lịch sử dài, và collector phải chạy xong trong một cửa sổ thời gian sau phiên.

## Considered Options

- **Gọi thẳng nhà cung cấp theo từng request** (cách hiện tại với vnstock). Bị loại vì lượng gọi ngoài tăng theo số người dùng, và vì gói FiinQuant free chỉ cho một kết nối đồng thời — nhiều worker sẽ đạp lên nhau khi đăng nhập.
- **Thu thập theo nhịp trong phiên.** Hoãn, không loại: hạn mức thừa sức chịu, nhưng sản phẩm là công cụ phân tích chứ không phải bảng giá, nên chưa có nhu cầu.
- **Không đặt trần.** Bị loại vì 504 là có thật; trần đóng vai trò van an toàn cho collector, không phải hạn ngạch bán cho người dùng.

## Consequences

- Lượng gọi ngoài là hằng số theo số mã, không phụ thuộc số người dùng.
- Mọi dữ liệu đều có tuổi. Giao diện phải hiển thị tuổi đó trung thực, và người dùng thêm mã trong phiên sẽ không thấy số liệu ngày hôm đó cho tới sau 15:00.
- Trần 100 mã không được xuất hiện trong giao diện người dùng. Chạm trần là tín hiệu vận hành gửi cho người quản trị, không phải thông báo cho người dùng.
- Giới hạn 5 mã mỗi tài khoản là lựa chọn sản phẩm — buộc người dùng chọn, vì chính việc chọn làm phân tích sâu có nghĩa — chứ không phải ràng buộc kỹ thuật.
- Collector phải gom lô: một lời gọi 50 mã mất ~5 giây, 50 lời gọi một mã mất ~100 giây.
- API bị khoá ở một worker chừng nào collector còn nằm trong tiến trình API. Muốn scale API thì phải tách collector ra trước.
