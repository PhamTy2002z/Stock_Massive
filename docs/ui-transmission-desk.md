# Transmission Desk — đặc tả UI và UX

**Ngày viết:** 26/08/2026
**Nhánh:** `feat/transmission-desk`
**Phạm vi:** mô tả bằng chữ toàn bộ giao diện mới, và chỉ rõ giao diện hiện tại đổi ở đâu.
**Nguyên tắc nền:** đây là bản *cập nhật* trên shell đang chạy, không phải thiết kế lại từ đầu. Mọi thứ đang hoạt động đều giữ; cái mới mọc thêm vào chỗ trống, và đúng một thứ bị đổi vai.

---

## 1. Câu một dòng

Sản phẩm hiện tại mở ra là một ô nhập chờ người dùng nghĩ ra câu hỏi. Sau bản này, mở ra là một trang đã trả lời sẵn: hôm nay có gì thay đổi, nó chạm tới vị thế nào của bạn, và dữ kiện nào sắp tới sẽ chứng minh nhận định đó đúng hay sai. Ô nhập vẫn còn, nhưng lùi xuống làm cửa sau.

---

## 2. Kiểm kê giao diện hiện tại

Phần này ghi lại đúng những gì đang có, để phần sau nói "đổi cái gì" mà không mơ hồ.

### 2.1 Khung ngoài

`app-shell.tsx` dựng một khung ba vùng chiếm trọn chiều cao màn hình: thanh bên trái, cột chính ở giữa, bảng thông tin bên phải. Cột chính có thanh trên cùng (`TopBar`) và phần thân đổi theo trạng thái `view`. Bảng bên phải kéo rộng hẹp được, và dưới 768px thì cột chính bỏ luôn phần chừa chỗ cho nó.

Hàm `MainView` ở `app-shell.tsx:86-94` quyết định thân cột chính hiển thị gì. Thứ tự xét hiện tại: nếu `view` là `news` thì mở trang tin; nếu là `board` thì mở bảng giá; nếu là `new` **hoặc hội thoại đang rỗng** thì mở màn hình trò chuyện mới; còn lại mở khung chat.

Kiểu `ShellView` ở `shell-state.tsx:31` có bốn giá trị: `chat`, `board`, `new`, `news`. Giá trị khởi tạo là `chat` (`shell-state.tsx:135`).

### 2.2 Thanh bên trái

Trên cùng là nút thu gọn thanh bên và nút tìm hội thoại.

Dưới đó là một cụm hai tab chia đôi (`ViewSwitch`, `sidebar.tsx:93`): **Hỏi đáp** và **Bảng giá**. Tab Hỏi đáp sáng khi `view` là `chat` hoặc `new` — tức là màn hình trò chuyện mới vẫn được tính là thuộc nửa hội thoại. Trang tin không thuộc tab nào nên không làm tab nào sáng.

Dưới nữa là danh sách điều hướng (`Nav`, `sidebar.tsx:132`) gồm bốn dòng: **Trò chuyện mới**, **Tin tức**, **Bộ lọc cổ phiếu** và **Báo cáo đã lưu**. Hai dòng cuối bị vô hiệu hoá, hiện nhãn "Sắp ra mắt", và có ghi chú trong code nói rõ lý do: chưa có tài nguyên nào phía sau để bấm.

Cuối cùng là danh sách hội thoại, chia hai nhóm **Đã ghim** và **Hội thoại**, mỗi dòng có menu đổi tên và xoá.

### 2.3 Cột chính

Có bốn thân màn hình.

**Màn hình trò chuyện mới** (`view-new.tsx`) là thứ người dùng gặp đầu tiên khi chưa có hội thoại nào. Nó đặt mọi thứ vào giữa màn hình theo chiều dọc: một lời chào đặt bằng font serif — dòng tiếng Anh duy nhất trong toàn sản phẩm, dạng "Morning, <tên>" — rồi tới ô nhập ở biến thể `opening`, rồi một dòng chỉ số thị trường gồm ba chỉ số dạng chữ đơn cách, rồi một liên kết nhỏ mở bảng giá phiên hôm nay.

**Khung chat** (`view-chat.tsx`) hiển thị dòng hội thoại, tin nhắn trợ lý có markdown, danh sách lời gọi công cụ, dòng thời gian suy luận, các nút hành động trên tin nhắn và nút gắn cờ.

**Bảng giá** (`view-board.tsx`) và **trang tin** (`view-news.tsx`) là hai màn hình còn lại.

### 2.4 Ô nhập

`composer.tsx` là ô nhập dùng chung cho cả màn hình trò chuyện mới lẫn khung chat, nên chuyển qua lại giữa hai màn hình không mất chữ đang gõ dở.

Nó có một menu đính kèm (`AttachMenu`, `composer.tsx:225`) **đã vẽ nhưng cố tình bất động**. Ghi chú ngay trên hàm liệt kê chính xác những gì còn thiếu ở backend để từng dòng trong menu hoạt động được: không có điểm cuối tải tệp, không có tài nguyên danh mục, không có kho mẫu phân tích, không có sổ đăng ký kết nối.

Phía backend, `turns.py:74` dẫn quyết định kiến trúc số 0015 và nói thẳng: không có tệp đính kèm, và không đường dẫn nào do người dùng cung cấp được tải về.

### 2.5 Bảng thông tin bên phải

`inspector.tsx` có bốn tab, hai cố định và hai chỉ xuất hiện khi có ngữ cảnh.

Cố định: **Thị trường** và **Chi tiết <mã>**. Có điều kiện: tab **Nguồn** chỉ hiện khi đang xem nguồn của một câu trả lời cụ thể, tab **Nguồn tin** chỉ hiện khi đang mở một bài báo. Ghi chú trong code giải thích lý do giống nhau cho cả hai: không có ngữ cảnh thì đó là một tab dẫn tới hư không.

Trên các tab trừ tab Nguồn có một ô tìm mã. Trong tab Thị trường có danh sách theo dõi, thêm mã bằng cách gõ rồi Enter.

### 2.6 Cài đặt và tài khoản

Hộp thoại cài đặt chia ba mục: **Giao diện**, **Hồ sơ**, **Hệ thống**. Có ô tìm trong cài đặt.

### 2.7 Cái chưa hề tồn tại

Tìm toàn bộ mã nguồn không thấy bất kỳ luồng khởi đầu nào: không có wizard, không có màn hình chạy lần đầu, không có tour hướng dẫn. Người dùng đăng ký xong là rơi thẳng vào màn hình trò chuyện mới.

Cũng không có: khái niệm danh mục, dữ liệu vĩ mô, thẻ truyền dẫn, luận điểm, lịch kiểm chứng.

---

## 3. Bản đồ thay đổi

### 3.1 Đổi vai — đúng một thứ

**Màn hình trò chuyện mới thôi làm cửa trước.** Nó không bị xoá, không bị sửa nội dung, vẫn vào được bằng dòng "Trò chuyện mới" ở thanh bên. Nhưng nó không còn là thứ người dùng gặp khi mở ứng dụng.

Lý do: một ô nhập trống đặt người dùng vào thế phải tự nghĩ ra câu hỏi. Với công cụ này, phần khó nhất chính là biết nên hỏi gì — nên đẩy việc đó sang người dùng là chuyển phần việc của sản phẩm cho họ.

### 3.2 Thêm mới

Một màn hình chính mới tên **Bàn làm việc**, giá trị `view` là `desk`, trở thành mặc định.

Một khái niệm mới là **danh mục**, có màn hình nhập và một tài nguyên phía sau.

Một đối tượng hiển thị mới là **thẻ truyền dẫn**, sống trong bàn làm việc.

Một ngăn kéo mới là **bằng chứng**, mở ra từ bất kỳ con số nào.

Một luồng mới là **onboarding bốn bước** chạy đúng một lần sau khi đăng ký.

Một hộp thoại mới là **bản tin gửi khách**.

### 3.3 Sửa nhỏ trên cái đang có

Thanh bên thêm một tab thứ ba. Bảng thông tin bên phải thêm một tab có điều kiện. Cài đặt thêm một mục. Menu đính kèm được kích hoạt một dòng duy nhất.

### 3.4 Không đụng tới

Khung chat, ô nhập, bảng giá, trang tin, danh sách hội thoại, đăng nhập, đăng ký, tài khoản, giao diện sáng tối. Toàn bộ thành phần trong thư mục `alpha` — tin nhắn, markdown, dòng thời gian suy luận, nút gắn cờ, danh sách nguồn — giữ nguyên và sẽ được dùng lại.

---

## 4. Onboarding — wizard bốn bước

Chạy đúng một lần, ngay sau khi đăng ký thành công, trước khi người dùng nhìn thấy bàn làm việc. Có thể bỏ qua ở mọi bước; bỏ qua thì vào thẳng bàn làm việc ở trạng thái rỗng và một dải nhắc nhẹ vẫn còn ở đó.

Wizard chiếm trọn màn hình, nền tối như phần còn lại, nội dung căn giữa trong một cột hẹp. Không có thanh bên, không có bảng bên phải — bốn bước này là toàn bộ những gì người dùng thấy. Trên cùng bên phải có chữ "Bỏ qua" mờ. Dưới cùng có bốn chấm nhỏ chỉ vị trí, chấm hiện tại sáng hơn.

Mỗi bước chỉ hỏi một thứ. Không bước nào có hai câu hỏi.

### Bước 1 — Bạn đang làm gì với thị trường

Một câu hỏi lớn ở trên, ba lựa chọn xếp dọc bên dưới, mỗi lựa chọn là một khối bấm được có tiêu đề và một dòng giải thích.

Lựa chọn thứ nhất, **Tôi tự đầu tư**: dòng giải thích nói sản phẩm sẽ tập trung vào danh mục của chính bạn.

Lựa chọn thứ hai, **Tôi là môi giới, tư vấn cho khách**: dòng giải thích nói sẽ bật thêm phần soạn bản tin gửi khách và quản lý nhiều danh mục.

Lựa chọn thứ ba, **Tôi phân tích ngành, chưa có danh mục cụ thể**: dòng giải thích nói sẽ bỏ qua bước nhập danh mục và hiển thị toàn ngành.

Chọn xong là tự sang bước kế, không cần bấm nút tiếp.

Câu trả lời quyết định hai thứ về sau: có hiện nút soạn bản tin gửi khách hay không, và bước 2 có bị bỏ qua hay không.

### Bước 2 — Danh mục của bạn

Bỏ qua hoàn toàn nếu bước 1 chọn phương án thứ ba.

Tiêu đề nói rõ mục đích: "Cho tôi biết bạn đang nắm gì, để tôi chỉ nói phần liên quan tới bạn." Ngay dưới là một dòng nhỏ hơn giải quyết trước nỗi lo thường gặp: không cần giá vốn, không cần số lượng, không cần kết nối tài khoản chứng khoán. Hệ thống không cần biết bạn lãi lỗ bao nhiêu để nói cơ chế nào đang tác động tới vị thế nào.

Phần nhập là một vùng văn bản nhiều dòng, mỗi dòng một mã kèm tỷ trọng, dạng "MBB 25". Bên dưới vùng nhập là một dòng ví dụ mờ. Vùng nhập chấp nhận dán thẳng từ bảng tính: nếu dán vào một khối có dấu tab hoặc nhiều cột, hệ thống tự nhận cột mã và cột số.

Ngay bên phải vùng nhập, cập nhật theo từng ký tự gõ vào, là bản xem trước: mỗi mã nhận diện được hiện thành một dòng có tên đầy đủ của doanh nghiệp và tỷ trọng đã chuẩn hoá. Mã không nhận ra được hiện màu cảnh báo kèm chữ "không tìm thấy mã này". Tổng tỷ trọng hiện ở cuối; nếu không bằng 100% thì có một dòng nhỏ nói hệ thống sẽ tự chuẩn hoá về 100%, chứ không chặn người dùng lại.

Nếu người dùng thuộc nhóm ngân hàng ngoài phạm vi sáu ngân hàng đang hỗ trợ, dòng đó vẫn được nhận nhưng kèm ghi chú "chưa có dữ liệu phơi nhiễm cho mã này" — thành thật ngay từ đầu thay vì để họ phát hiện ở màn hình chính.

Nút chính ở dưới cùng ghi "Tiếp tục". Bên cạnh là "Tôi nhập sau", dẫn thẳng sang bước 3.

### Bước 3 — Cách sản phẩm này nói chuyện

Bước này không hỏi gì. Nó dạy người dùng đọc thẻ, và nó tồn tại vì thẻ truyền dẫn không giống bất cứ thứ gì họ từng thấy trong một ứng dụng chứng khoán.

Màn hình hiện một thẻ mẫu thu nhỏ, dùng dữ liệu thật của chính danh mục vừa nhập nếu có. Bên cạnh thẻ, ba chú thích được đánh số dẫn tới ba phần của nó.

Chú thích thứ nhất trỏ vào con số phần trăm lớn: "Đây là khả năng nhận định này đúng, không phải khả năng giá tăng. Nó thay đổi khi có dữ liệu mới."

Chú thích thứ hai trỏ vào phần điều kiện: "Mỗi nhận định đều kèm điều kiện để nó sai. Điều kiện viết trước ngày số liệu ra, và khoá lại — không sửa được sau khi biết kết quả."

Chú thích thứ ba trỏ vào một con số có gạch chấm dưới: "Mọi con số đều bấm được, dẫn thẳng tới trang trong báo cáo tài chính mà nó lấy ra."

Dưới cùng là một câu ngắn nói điều sản phẩm không làm: không đưa khuyến nghị mua bán, không dự báo giá.

Một nút duy nhất: "Đã hiểu".

### Bước 4 — Khi nào bạn muốn được báo

Tiêu đề nói rõ nguyên tắc: hệ thống chỉ báo khi có thứ đáng báo, không báo mỗi khi có tin.

Ba công tắc bật tắt xếp dọc, cả ba mặc định bật.

Công tắc thứ nhất, **Bản tin sáng**: một lần mỗi ngày làm việc, tóm tắt những gì đổi từ lần bạn xem. Có ô chọn giờ, mặc định 7 giờ sáng.

Công tắc thứ hai, **Khi một nhận định đổi trạng thái**: chỉ khi độ tin thay đổi đáng kể hoặc nhận định bị bác bỏ, không phải mỗi lần có số mới.

Công tắc thứ ba, **Khi tới hạn kiểm chứng**: báo trước một ngày khi sắp có số liệu quyết định một nhận định đúng hay sai.

Dưới ba công tắc là một dòng nhỏ: "Đổi lại bất cứ lúc nào trong Cài đặt."

Nút cuối cùng ghi "Vào bàn làm việc".

### Sau wizard

Trạng thái hoàn thành được lưu vào hồ sơ người dùng. Lần đăng nhập sau không chạy lại.

Có một đường vào lại: trong Cài đặt, mục mới sẽ có dòng "Xem lại phần giới thiệu".

---

## 5. Bàn làm việc — màn hình chính mới

Đây là thân cột chính khi `view` bằng `desk`. Thanh bên và bảng bên phải vẫn nguyên như hiện tại.

Nội dung nằm trong một cột đọc rộng vừa phải, căn giữa, chứ không trải hết chiều ngang. Đây là màn hình để đọc, không phải để quét bảng số, nên chiều dài dòng được giữ trong khoảng dễ đọc.

### 5.1 Phần mở đầu

Dòng đầu tiên là ngày hôm nay viết bằng chữ, cỡ nhỏ, màu mờ.

Dưới đó là một tiêu đề lớn — đây là phần tử duy nhất trên màn hình ở cỡ chữ đó. Nó không phải nhãn cố định như "Bảng điều khiển" mà là **kết luận của hôm nay**, sinh theo dữ liệu. Ví dụ dạng câu: "Thanh khoản thắt lại, chi phí vốn ngân hàng đang lên." Khi không có gì đáng kể, nó nói đúng như vậy: "Hôm nay không có thay đổi đáng kể."

Dưới tiêu đề là một đoạn văn ngắn nói có mấy thay đổi và chúng có chạm tới danh mục của người dùng hay không.

Nếu chưa có danh mục, ngay dưới đoạn văn là một nút cam — nút hành động chính và là nút cam duy nhất trên màn hình — ghi "Thêm danh mục của bạn".

### 5.2 Dải danh mục

Chỉ hiện khi đã có danh mục. Một dải ngang gọn, nền nhạt hơn nền trang một bậc, liệt kê từng mã kèm tỷ trọng. Không có biểu đồ tròn, không có giá, không có lãi lỗ — dải này chỉ để xác nhận hệ thống đang nói về đúng danh mục nào. Cuối dải có chữ "Sửa" mờ.

### 5.3 Danh sách thẻ

Phần thân chính. Các thẻ xếp dọc, cách nhau đủ rộng để không dính vào nhau.

Thứ tự không theo thời gian và không theo độ giật gân. Nó theo tích của bốn yếu tố: mức độ nghiêm trọng, độ mới so với lần người dùng xem gần nhất, độ tin cậy, và mức phơi nhiễm của danh mục người dùng. Một thay đổi lớn nhưng không chạm danh mục sẽ nằm dưới một thay đổi vừa phải nhưng chạm đúng vị thế nặng nhất.

### 5.4 Phần "Sắp tới"

Sau danh sách thẻ, cách một đường kẻ mảnh và một khoảng trống rộng.

Tiêu đề "Sắp tới", dưới đó một câu giải thích mục đích: những mốc này sẽ chấm điểm các nhận định ở trên.

Danh sách các mốc, mỗi dòng gồm ngày ở cột trái dạng chữ đơn cách, tên sự kiện ở giữa, và nếu mốc đó sẽ chấm điểm nhận định nào thì bên phải hiện số lượng bằng màu cam. Ví dụ nội dung: ngày công bố thống kê tiền tệ của Ngân hàng Nhà nước, ngày công bố chỉ số giá tiêu dùng, ngày ra báo cáo tài chính quý của nhóm ngân hàng.

### 5.5 Phần "Còn thắc mắc gì"

Cuối trang, sau một đường kẻ nữa.

Đây là chỗ chat xuất hiện trên bàn làm việc, và nó ở cuối chứ không ở đầu — sau khi người dùng đã đọc xong, không phải trước.

Không có ô nhập ở đây. Chỉ có ba đến bốn viên gợi ý dạng nút bo tròn, nội dung sinh theo các thẻ đang hiển thị chứ không cố định. Ví dụ: "Giải thích cơ chế này kỹ hơn", "So sánh CASA của MBB và TCB", "Nếu CASA tăng thì sao".

Bấm một viên sẽ chuyển sang khung chat với câu đó **đã điền sẵn vào ô nhập nhưng chưa gửi**. Người dùng sửa rồi tự gửi.

Cơ chế này đã có sẵn trong mã nguồn: hành động `ask` ở `shell-state.tsx:239-242` nhận một câu, đặt vào `draft`, chuyển `view` sang `chat`. Ghi chú của tác giả ngay trên đó viết đúng tinh thần cần thiết: câu hỏi được *mời*, không phải được *hỏi thay*. Không cần thiết kế mới cho phần này, chỉ cần gọi đúng hành động đã có.

---

## 6. Thẻ truyền dẫn

Đối tượng hiển thị trung tâm. Nó có hai trạng thái, và sự khác biệt giữa hai trạng thái là điều quan trọng nhất trong toàn bộ thiết kế này.

### 6.1 Trạng thái đóng — mặc định

Thẻ đóng chỉ trả lời hai câu, và không nhiều hơn.

Bên trái, từ trên xuống: một tiêu đề cỡ lớn viết bằng tiếng Việt thường, không có từ chuyên môn — ví dụ "Chi phí huy động đang tăng". Dưới đó một đoạn văn ngắn giải thích chuyện gì đang xảy ra, cũng không có từ chuyên môn, dài khoảng ba dòng. Dưới nữa, chỉ khi đã có danh mục, là một đoạn thứ hai nói riêng về danh mục của người dùng: mã nào chịu ảnh hưởng rõ nhất, mã nào gần như không.

Bên phải là một con số phần trăm cỡ rất lớn — độ tin cậy — kèm dòng chú "khả năng đúng" bên dưới, và dòng thứ ba cho biết nó đã đổi bao nhiêu điểm trong tuần, tô xanh nếu tăng và vàng nếu giảm.

Dưới cùng thẻ là một dòng mảnh: bên trái ghi ngày và nguồn sẽ kiểm chứng, bên phải là lời mời mở rộng — "Xem cơ chế và bằng chứng".

Toàn bộ thẻ đóng là một nút bấm được. Bấm chỗ nào cũng mở.

**Cái cố tình không có ở trạng thái đóng:** không bảng số, không tên chỉ tiêu tài chính, không chuỗi mũi tên, không nhãn viết hoa. Người dùng liếc qua trong ba giây phải hiểu chuyện gì và nó có liên quan tới mình không. Chi tiết là phần thưởng cho người bấm vào, không phải thuế thu của người lướt qua.

### 6.2 Trạng thái mở

Phần mở rộng nằm dưới, ngăn bằng một đường kẻ mảnh. Nó có năm khối, mỗi khối có một tiêu đề nhỏ in thường.

**Khối "Chuỗi tác động".** Các bước được đánh số, xếp dọc, mỗi bước là một câu hoàn chỉnh chứ không phải nhãn kỹ thuật. Viết "Ngân hàng Nhà nước hút bớt tiền đồng về để giữ tỷ giá", không viết "NHNN hút VND". Dưới danh sách là một câu nói rõ điều kiện kích hoạt: chuỗi này chỉ chạy khi ngân hàng phụ thuộc huy động bán buôn trên một ngưỡng nào đó.

**Khối "Ai chịu ảnh hưởng".** Một bảng gọn, mỗi ngân hàng một dòng, nền chìm hơn thân thẻ. Mỗi dòng gồm mã, tỷ trọng huy động bán buôn, chỉ số CASA, và ở cuối dòng là kết luận bằng chữ — "nhạy nhất", "trung tính", "được che", "ít ảnh hưởng" — tô màu tương ứng đỏ, vàng, xanh, xám.

Ngân hàng nào chưa công bố số liệu cần thiết thì ô đó ghi **"chưa có số quý này"**, không phải một con số ước lượng. Ngay dưới bảng, nếu có ít nhất một dòng như vậy, xuất hiện một câu giải thích: ngân hàng đó chưa công bố, hệ thống để trống thay vì ước lượng. Đây là hành vi cố ý và cần được nhìn thấy, không phải lỗi cần giấu.

**Khối "Điều gì có thể làm nhận định này sai".** Danh sách đánh số các phản lực, mỗi mục một câu. Đây không phải phần miễn trừ trách nhiệm ở cuối trang mà là một phần ngang hàng với các khối khác.

**Khối điều kiện kiểm chứng.** Đặt trong một hộp nền chìm để tách khỏi phần diễn giải. Câu đầu nói rõ ngày nào và nguồn nào sẽ quyết định. Dưới đó hai dòng đối nhau: "Đúng nếu" tô xanh kèm điều kiện định lượng, "Sai nếu" tô đỏ kèm điều kiện định lượng. Dòng cuối của hộp ghi ngày viết hai điều kiện này và nói rõ chúng không sửa được nữa.

**Dải chân thẻ.** Ngăn bằng một đường kẻ. Bên trái là một câu về thành tích của cơ chế này — đã kiểm mấy lần, đúng mấy lần. Bên phải là nút hành động: với môi giới là "Soạn bản tin gửi khách", với nhà đầu tư cá nhân là "Lưu vào theo dõi".

### 6.3 Từ chuyên môn

Những từ không tránh được — CASA, bps, NIM, huy động bán buôn, nợ nhóm 2 — được gạch chấm mờ ở dưới. Rê chuột hoặc chạm vào hiện một câu giải thích bằng tiếng Việt thường. Không có bảng thuật ngữ riêng; giải thích đến đúng lúc người đọc gặp từ đó.

---

## 7. Ngăn kéo bằng chứng

Mở ra khi bấm vào bất kỳ con số nào có gạch chấm. Trượt vào từ mép phải, phủ lên bảng thông tin hiện tại, nền phía sau tối đi. Đóng bằng nút X, bấm ra ngoài, hoặc phím Esc.

Nội dung từ trên xuống.

Tiêu đề là tên con số, ví dụ "CASA TCB". Ngay dưới là một dòng nói con số này thuộc loại nào bằng tiếng Việt thường: "Trích từ báo cáo tài chính", "Tính bằng mã, đã đăng ký", "Suy ra, chưa hiệu chuẩn".

Kế đến là chính con số đó, đặt ở cỡ rất lớn.

Nếu là số tính toán, một hộp nền chìm hiện công thức bằng chữ, rồi tử số và mẫu số với giá trị thật của chúng.

Sau đó là danh sách các trường thông tin, mỗi dòng nhãn bên trái giá trị bên phải: tên tài liệu, vị trí chính xác trong tài liệu ở mức trang và số thuyết minh và dòng, kỳ báo cáo, ngày doanh nghiệp công bố, ngày hệ thống đọc được, và tên người đã kiểm lại hoặc chữ "chưa có".

Nếu con số từng bị đính chính, một hộp viền vàng xuất hiện: giá trị cũ, mũi tên, giá trị mới, và một câu giải thích vì sao vẫn giữ bản cũ — khi chấm điểm một nhận định viết ngày nào, hệ thống dùng con số biết được vào ngày đó, không dùng con số hôm nay.

Dưới cùng, cố định, là một nút mở thẳng tài liệu gốc tại đúng trang.

---

## 8. Bản tin gửi khách

Chỉ có với người dùng đã chọn "Tôi là môi giới" ở bước 1 của wizard.

Mở ra dạng hộp thoại giữa màn hình. Nội dung là một bản nháp đã soạn sẵn, đúng năm đoạn theo thứ tự cố định: một dòng tiêu đề có ngày; một đoạn nói chuyện gì đang xảy ra; một đoạn nói nó chạm tới vị thế nào trong danh mục của khách và ở mức nào; một đoạn bằng chứng ủng hộ; một đoạn bằng chứng phản chiều; một câu hỏi mở để môi giới thảo luận với khách. Cuối cùng là một dòng miễn trừ in nghiêng nói rõ đây là phân tích dữ liệu chứ không phải khuyến nghị đầu tư.

Đoạn phản chiều là bắt buộc và không tắt được. Nếu không có bằng chứng phản chiều thì thẻ đó lẽ ra đã không được sinh ra.

Chân hộp thoại có một dòng chữ nhỏ bên trái nhắc rằng hệ thống không gửi thay, và hai nút bên phải: "Sửa" và "Sao chép".

**Không có nút gửi.** Sản phẩm không kết nối tới khách hàng cuối. Môi giới sao chép rồi tự gửi qua kênh của họ. Mọi lần mở và sao chép đều ghi vào nhật ký kiểm toán.

---

## 9. Thay đổi cụ thể trên các thành phần đang có

### 9.1 Thanh bên

Cụm tab hai ô thành ba ô: thêm **Bàn làm việc** vào trước Hỏi đáp, và nó là tab sáng mặc định.

Quy tắc tab nào sáng được mở rộng theo đúng tinh thần hiện tại: tab Bàn làm việc sáng khi `view` là `desk`; tab Hỏi đáp giữ nguyên quy tắc cũ, sáng khi `view` là `chat` hoặc `new`; tab Bảng giá sáng khi `view` là `board`.

Trong danh sách điều hướng, dòng **Báo cáo đã lưu** đang bị vô hiệu hoá sẽ được kích hoạt và đổi tên thành **Luận điểm đang theo**, dẫn tới danh sách các nhận định người dùng đã lưu. Dòng **Bộ lọc cổ phiếu** giữ nguyên trạng thái vô hiệu hoá.

Danh sách hội thoại giữ nguyên hoàn toàn.

### 9.2 Hàm chọn màn hình

`MainView` thêm một nhánh cho `desk`, và bỏ điều kiện "hội thoại rỗng thì mở màn hình trò chuyện mới" — vì giờ hội thoại rỗng là trạng thái bình thường của một người chưa bao giờ cần gõ gì.

Kiểu `ShellView` thêm giá trị `desk`. Giá trị khởi tạo đổi từ `chat` sang `desk`.

### 9.3 Thanh trên cùng

Khi đang ở bàn làm việc, thanh trên hiện tên màn hình và một dải trạng thái vĩ mô rất gọn: ba cụm chữ ngắn cho áp lực tỷ giá, thanh khoản và xung lực tín dụng, mỗi cụm có một mũi tên chỉ hướng. Rê chuột vào từng cụm hiện con số đứng sau nó.

Đây là thứ duy nhất mang tính "bảng điều khiển" trong toàn thiết kế, và nó bị giới hạn ở một dòng có chủ ý.

### 9.4 Bảng thông tin bên phải

Thêm một tab có điều kiện thứ ba tên **Luận điểm**, theo đúng quy ước sẵn có của hai tab điều kiện hiện tại: chỉ hiện khi đang mở một thẻ, vì không có thẻ thì đó là tab dẫn tới hư không.

Tab Luận điểm hiển thị lịch sử của cơ chế đang xem: các lần đã chấm trước đây, mỗi lần ghi ngày viết, ngày chấm, kết quả đúng hay sai hay đã đóng, và độ tin của cơ chế đã thay đổi thế nào sau lần đó.

Hai tab cố định Thị trường và Chi tiết mã giữ nguyên. Ô tìm mã giữ nguyên. Danh sách theo dõi giữ nguyên và về sau có thể nối với danh mục, nhưng không phải ở bản này.

### 9.5 Ô nhập và menu đính kèm

Ô nhập giữ nguyên hoàn toàn.

Menu đính kèm hiện đang bất động toàn bộ. Bản này kích hoạt **đúng một dòng**: dòng danh mục, vì giờ đã có tài nguyên phía sau nó. Bấm vào mở đúng màn hình nhập danh mục của bước 2 trong wizard. Các dòng còn lại — tải tệp, mẫu phân tích, sổ kết nối — giữ nguyên trạng thái bất động và giữ nguyên ghi chú giải thích trong mã nguồn.

Đây là một thay đổi có ý nghĩa vượt ngoài kỹ thuật: quyết định kiến trúc số 0015 nói không có tệp đính kèm, và bản này **không đảo quyết định đó**. Danh mục không phải tệp người dùng tải lên để hệ thống đọc; nó là một tài nguyên có cấu trúc mà người dùng khai báo. Phân biệt này cần được ghi lại thành một quyết định kiến trúc mới, nếu không hai tuần nữa nó sẽ bị hiểu nhầm thành "đã cho phép tải tệp".

### 9.6 Cài đặt

Thêm một mục thứ tư tên **Bàn làm việc**, nằm trong nhóm Cấu hình cùng với Giao diện.

Bên trong có bốn phần: sửa danh mục; ba công tắc thông báo giống hệt bước 4 của wizard; chọn vai trò đã khai ở bước 1, đổi được; và dòng "Xem lại phần giới thiệu" để chạy lại wizard.

### 9.7 Màn hình trò chuyện mới

Giữ nguyên từng chi tiết, kể cả lời chào serif tiếng Anh và dòng chỉ số thị trường.

Một điểm cần xử lý: dòng ba chỉ số thị trường hiện chỉ tồn tại ở màn hình này. Khi màn hình này không còn là cửa trước, phần lớn người dùng sẽ không thấy nó nữa. Ba chỉ số đó cần được đưa lên dải trạng thái ở thanh trên hoặc vào tab Thị trường của bảng bên phải, nếu không sẽ mất một thứ đang chạy tốt.

---

## 10. Các trạng thái phải vẽ

Một màn hình chỉ được coi là xong khi cả năm trạng thái đều có.

**Chưa có danh mục.** Bàn làm việc vẫn hiển thị đầy đủ các thẻ ở phạm vi toàn ngành. Đây là điểm quan trọng: sản phẩm có giá trị ngay cả khi người dùng chưa nhập gì. Chỗ lẽ ra là đoạn "danh mục của bạn" thay bằng một lời mời nhẹ, và nút cam ở phần mở đầu vẫn còn.

**Đang tải.** Khung xương của thẻ, không phải vòng xoay giữa màn hình. Số lượng khung xương bằng số thẻ lần trước, để bố cục không nhảy.

**Không có thay đổi nào.** Tiêu đề lớn nói thẳng "Hôm nay không có thay đổi đáng kể", đoạn dưới giải thích các nhận định đang theo vẫn giữ nguyên trạng thái và mốc kiểm chứng gần nhất là ngày nào. Phần "Sắp tới" vẫn hiện đầy đủ. Đây là một câu trả lời hợp lệ, không phải trạng thái rỗng cần xin lỗi.

**Thiếu dữ liệu một phần.** Thẻ vẫn hiện, ô thiếu ghi "chưa có số quý này", và có câu giải thích. Không ẩn thẻ, không ẩn ngân hàng đó khỏi bảng.

**Lỗi.** Nói rõ phần nào hỏng và phần nào vẫn dùng được. Nếu chỉ nguồn vĩ mô lỗi, các thẻ dựa trên báo cáo tài chính vẫn hiện.

---

## 11. Bàn phím và trợ năng

Toàn bộ thẻ đóng là một nút, nên tới được bằng phím Tab và mở bằng Enter hoặc Space. Trạng thái đóng mở khai báo bằng thuộc tính `aria-expanded`.

Các con số bấm được là nút thật, không phải thẻ span có sự kiện chuột, nên chúng nằm trong thứ tự Tab và có vòng tiêu điểm nhìn thấy được.

Ngăn kéo bằng chứng bẫy tiêu điểm khi mở, trả tiêu điểm về đúng con số vừa bấm khi đóng, và đóng bằng Esc.

Wizard đi tới bằng Enter, lùi bằng Esc ở bước 2 trở đi.

Thứ tự đọc của trình đọc màn hình khớp với thứ tự nhìn: tiêu đề, đoạn giải thích, đoạn liên quan danh mục, rồi mới tới con số độ tin cậy. Con số không được đọc trước phần giải thích nó.

---

## 12. Màn hình hẹp

Dưới 1024 pixel, bảng thông tin bên phải rút thành một tấm trượt lên từ đáy thay vì cột cố định. Ngăn kéo bằng chứng cũng trượt từ đáy thay vì từ phải.

Dưới 768 pixel, thanh bên thu vào sau một nút. Cột đọc chiếm trọn chiều ngang trừ lề. Bảng "ai chịu ảnh hưởng" trong thẻ mở đổi từ hàng ngang sang các khối xếp dọc, mỗi ngân hàng một khối, để không phải cuộn ngang.

Ở mọi kích thước, con số độ tin cậy không bao giờ xuống dưới đoạn văn — trên màn hẹp nó lên trên tiêu đề thành một dòng riêng, vì nếu để dưới thì người dùng phải cuộn mới thấy phần quan trọng nhất.

---

## 13. Những gì bản này cố tình không làm

Không có biểu đồ giá, không có nến, không có chỉ báo kỹ thuật.

Không có khuyến nghị mua bán, không có giá mục tiêu, không có xếp hạng.

Không có bảng xếp hạng cổ phiếu, không có bộ lọc.

Không cho tải tệp tài liệu lên để hệ thống đọc. Danh mục là tài nguyên khai báo, không phải tệp.

Không tự gửi bất cứ thứ gì cho khách hàng cuối.

Không có dữ liệu thời gian thực. Mọi con số đều thuộc về một kỳ báo cáo hoặc một phiên đã đóng, và luôn hiển thị kèm thời điểm.

---

## 14. Thứ tự dựng

Phần này không phải kế hoạch dự án, chỉ là thứ tự khiến mỗi bước đều kiểm tra được ngay.

Trước hết là khung: thêm giá trị `desk` vào kiểu màn hình, thêm nhánh vào hàm chọn màn hình, đổi mặc định, thêm tab thứ ba vào thanh bên. Xong bước này ứng dụng mở ra là một bàn làm việc rỗng, và mọi thứ cũ vẫn chạy.

Kế đến là tài nguyên danh mục và màn hình nhập, vì mọi thứ khác đều xếp hạng theo nó.

Rồi tới thẻ ở trạng thái đóng, dùng dữ liệu tĩnh. Đây là lúc kiểm tra giả thuyết lớn nhất: người dùng nhìn ba giây có hiểu không.

Rồi tới trạng thái mở và ngăn kéo bằng chứng. Ngăn kéo phải làm cùng lúc với trạng thái mở, vì một con số không bấm được thì cả thiết kế mất điểm phân biệt chính.

Wizard làm sau cùng trong nhóm này — nó dạy người dùng đọc thẻ, nên thẻ phải tồn tại trước.

Bản tin gửi khách, tab Luận điểm và thông báo làm sau, khi vòng lặp chính đã đứng vững.
