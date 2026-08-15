# Universe có trần, dữ liệu phục vụ từ Snapshot

Hệ thống chỉ thu thập và phân tích cho **Universe** — tập mã được cấu hình, trần 100 mã — và mọi endpoint chỉ đọc từ `SnapshotStore`; một collector chạy sau phiên là nơi duy nhất gọi ra ngoài, trừ đúng một ngoại lệ được nêu tên ở [Amendments](#amendments). Mỗi tài khoản chọn tối đa 10 mã.

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
- Giới hạn 10 mã mỗi tài khoản là lựa chọn sản phẩm — buộc người dùng chọn, vì chính việc chọn làm phân tích sâu có nghĩa — chứ không phải ràng buộc kỹ thuật. Khác trần Universe, trần này **có** mặt trong giao diện, vì người dùng chạm vào nó mỗi lần thêm mã.
- Collector phải gom lô: một lời gọi 50 mã mất ~5 giây, 50 lời gọi một mã mất ~100 giây.
- API bị khoá ở một worker chừng nào collector còn nằm trong tiến trình API. Muốn scale API thì phải tách collector ra trước.

## Amendments

- **Trần Watchlist là 10 mã, không phải 5.** Con số 5 trong bản gốc đã lỗi thời;
  `CONTEXT.md` và [ADR-0014](0014-atomic-spend-admission-and-workload-models.md)
  đều tính theo 10. Lý do sản phẩm ở đoạn Consequences không đổi — chỉ con số đổi.
- **`search_news` là ngoại lệ cache-aside duy nhất** của luật "chỉ Collector gọi
  Provider Source", với hạn mức và cách cô lập do
  [ADR-0014](0014-atomic-spend-admission-and-workload-models.md) đặt ra — lane
  riêng, single-flight theo mã, cache Redis, và cùng một Redis quota arbiter với
  Collector. Giá trị của tin tức rơi theo giờ, nên đây là chỗ duy nhất một request
  của người dùng được phép chạm nhà cung cấp. Mọi tool số học của **Tool Catalog**
  vẫn store-only: một người dùng nhấn agent liên tục không bao giờ tiêu được hạn
  mức vnstock của Collector.

  Ngoại lệ này thu hẹp **đúng ba câu**, và cả ba được gọi tên ở đây chứ không
  âm thầm ghi đè:

  1. Câu ở đầu ADR này — *"một collector chạy sau phiên là nơi duy nhất gọi ra
     ngoài"*;
  2. [ADR-0004](0004-market-wide-profit-ranking-census.md) — *"User requests
     never call a Provider Source"*;
  3. [ADR-0005](0005-separate-signal-warm-up-from-deep-backfill.md) — *"User
     refreshes only reread stored data; they never trigger either process or
     call a Provider Source"*.

  Cả ba vẫn đúng cho mọi Capability của Snapshot; chỉ tin tức — thứ không phải
  một Capability và không nằm trong `provider_snapshots` — ra khỏi luật đó.

  Thứ giữ cho đây là một ngoại lệ chứ không phải một tiền lệ là **arbiter**:
  `apps/api/src/core/quota.py` là chiếc rổ rò rỉ duy nhất trên Redis cho toàn bộ
  hạn mức tài khoản vnstock, và `apps/api/src/core/news_lane.py` là lane tin tức
  chạy trong đó — cache tươi 6 giờ, single-flight theo mã, 5/15 rpm, và tối đa
  24 giờ phục vụ dữ liệu cũ *có nhãn* khi Collector đang giữ lease hoặc nhà cung
  cấp hỏng. **Mất Redis là fail-closed cho mọi lời gọi Provider Source**: endpoint
  đọc từ store vẫn phục vụ bình thường, còn lời gọi ra ngoài bị từ chối thay vì
  rơi về một nhịp cục bộ mà không tiến trình nào khác nhìn thấy.
- Danh sách endpoint còn gọi provider trong request nằm ở
  [`docs/serving-path.md`](../serving-path.md). Các endpoint đó **không** phải
  đường đi của agent.
