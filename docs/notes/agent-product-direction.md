# Note: what the agent should do beyond question-answering

Raw brainstorm captured on 2026-08-17, kept verbatim in Vietnamese. It argues the
product differentiator is running multi-step analysis, portfolio watch and proactive
alerts rather than answering one-off questions, and ranks what retail investors in
this market actually care about. Not a spec — no decision here is binding.

---

Nhưng AI ở đây làm gì ? User chat -> AI trả lời thì nhiều bên làm quá rồiĐúng, nếu chỉ dừng ở mức “User hỏi → AI trả lời” thì đã bão hòa rồi. ENSA, Dolphin AI, Mập Thông Thái, ChatGPT… đều làm được việc đó.
Muốn có cửa, AI Agent phải làm được những việc mà chatbot thông thường làm kém hoặc không làm được.
AI ở đây nên đóng vai trò gì?
Không phải “trả lời câu hỏi”, mà là thực hiện công việc phân tích giúp user.





























Chatbot thông thườngAI Agent đúng nghĩaTrả lời câu hỏi rời rạcThực hiện quy trình phân tích nhiều bướcTrả lời xong là hếtCó trí nhớ dài hạn về danh mục & sở thích của userDựa vào kiến thức chungKết nối data thật + tính toán + kiểm chứngChỉ textXuất báo cáo, bảng biểu, cảnh báo, watchlistReactive (chờ hỏi)Proactive (tự động theo dõi & báo)
Những việc AI Agent nên làm (ví dụ cụ thể)
1. Phân tích theo quy trình có cấu trúc

User nói: “Phân tích cổ phiếu HPG giúp tôi”
Agent không chỉ nói chung chung, mà tự chạy các bước:
Lấy dữ liệu tài chính mới nhất
Tính các chỉ số (P/E, ROE, nợ/VCSH, biên lợi nhuận…)
So sánh với trung bình ngành
Phân tích dòng tiền gần đây
Tóm tắt rủi ro chính
Đưa ra kết luận có cấu trúc + mức tin cậy


2. Quản lý danh mục cá nhân

User thêm danh mục → Agent nhớ mã + số lượng + giá vốn
Hàng ngày/tuần tự động:
Báo lãi/lỗ
Cảnh báo cổ phiếu đang yếu đi
Đề xuất rebalance
Theo dõi tin tức liên quan đến đúng những mã user đang giữ


3. Theo dõi chủ động (Proactive)

Tự động gửi thông báo khi:
Có tin bất thường về mã trong watchlist
Khối ngoại / tự doanh mua bán mạnh
Giá chạm ngưỡng user đặt
Báo cáo tài chính sắp ra có dấu hiệu bất thường


4. Thực hiện tác vụ phức tạp

“So sánh 5 mã ngân hàng đang có trong danh mục của tôi theo tiêu chí an toàn và hiệu quả”
“Tìm giúp tôi 5 mã midcap thỏa mãn: tăng trưởng doanh thu >15%, ROE >18%, nợ thấp, dòng tiền dương”
“Viết báo cáo phân tích nhanh về VHM để tôi gửi sếp”

5. Kết hợp công cụ (Tool-using)
Agent biết khi nào cần:

Gọi API lấy giá & khối lượng thật
Đọc báo cáo tài chính mới
Tính toán chỉ số
Vẽ biểu đồ đơn giản
Xuất file PDF/Excel

Tóm lại
Câu hỏi đúng không phải là “AI trả lời gì”, mà là:
AI giúp user tiết kiệm bao nhiêu thời gian và giảm bao nhiêu quyết định sai?
Nếu chỉ chat qua lại thì không đủ.
Phải biến nó thành trợ lý làm việc chứ không phải chatbot hỏi đáp.

Bạn muốn hướng Agent nghiêng về phía nào hơn?

Phân tích chuyên sâu từng mã (kiểu research assistant)
Quản lý & giám sát danh mục (portfolio agent)
Sàng lọc + tìm ý tưởng (stock screener thông minh)
Theo dõi tin tức & dòng tiền (monitoring agent)

Chọn hướng chính đi, mình sẽ phác thảo cụ thể Agent nên có những capability gì.Theo bạn thì người dùng họ quan tâm gì nhất ?Theo mình, người dùng Việt Nam quan tâm nhất theo thứ tự ưu tiên thực tế là:
1. “Tôi kiếm được tiền hay lỗ?” (Quan trọng nhất)
Đây là thứ họ quan tâm số 1, dù ít ai nói thẳng.
Họ không thực sự quan tâm AI thông minh đến đâu, phân tích sâu đến mức nào. Họ quan tâm:

Công cụ này có giúp mình ra quyết định tốt hơn không?
Có giúp mình tránh được lỗ to không?
Có giúp mình tìm được cơ hội không?

Nếu sau 1-2 tháng dùng mà không cảm thấy có lợi ích rõ (dù chỉ là tâm lý), họ sẽ hủy rất nhanh.
2. “Mã nào đáng chú ý / đáng mua?”
Phần lớn nhà đầu tư cá nhân Việt Nam vẫn mang tính tìm ý tưởng nhiều hơn là tự phân tích bài bản.
Họ thích những thứ kiểu:

Hôm nay/tuần này nên để ý mã nào?
Mã nào đang có dòng tiền vào?
Mã nào đang có tín hiệu tốt?

Đây là lý do các nhóm “khuyến nghị”, “watchlist”, “top cổ phiếu” luôn hút tương tác rất mạnh trên Facebook, Telegram, TikTok.
3. Thông tin nhanh & “độc”
Họ rất sợ chậm thông tin. Những thứ được quan tâm cao:

Khối ngoại mua/bán ròng
Tự doanh công ty chứng khoán
Giao dịch thỏa thuận lớn
Tin tức bất ngờ (lãnh đạo bị bắt, thay đổi lớn, kết quả kinh doanh lệch kỳ vọng…)
Biến động giá + khối lượng bất thường

Ai cung cấp thông tin này nhanh – gọn – dễ hiểu sẽ được đánh giá cao.
4. Theo dõi đúng danh mục của họ
Khi đã có danh mục, họ muốn biết:

Hôm nay danh mục mình lãi/lỗ bao nhiêu?
Mã nào đang yếu đi?
Có tin gì liên quan đến mã mình đang giữ không?
Có nên cắt lỗ / chốt lời không?

Phần này nếu làm tốt sẽ tăng retention rất mạnh (vì gắn với tiền thật của họ).
5. Dễ hiểu, không cần kiến thức nhiều
Đa số không thích đọc phân tích dài dòng, thuật ngữ phức tạp.
Họ muốn:

Giải thích ngắn gọn, tiếng Việt dễ hiểu
Có kết luận rõ ràng (tích cực / trung lập / tiêu cực)
Có lý do cụ thể, không chung chung


Tóm lại theo góc độ product:
Người dùng Việt quan tâm nhất theo thứ tự:

Giúp tôi ra quyết định tốt hơn (kiếm tiền / bớt lỗ)
Cho tôi ý tưởng / mã đáng chú ý
Thông tin nhanh, đặc biệt là dòng tiền & tin bất thường
Theo dõi danh mục cá nhân của tôi
Dễ hiểu, không tốn thời gian


Vậy nếu phải chọn 1 hướng để Agent tập trung mạnh nhất lúc đầu, mình nghiêng về:

Kết hợp “Tìm ý tưởng + Theo dõi danh mục + Cảnh báo kịp thời”

Vì đây là những thứ gần với nỗi đau và mong muốn thực tế nhất của đa số nhà đầu tư cá nhân Việt Nam hiện nay.
Bạn thấy nhóm nào trong 5 điểm trên gần với hướng bạn muốn làm nhất?
