# Nghiên cứu: nguồn dữ liệu chứng khoán Việt Nam & thư viện tính toán tài chính có provenance

Ngày viết: 2026-09-27 (Asia/Saigon). Nhắm ba lỗi: (5) chỉ số BCTC ngân hàng
(NPL/CAR/LDR/NIM) lấy từ báo, không có dữ liệu/tool tính; (4) nguồn cũ không
đánh dấu ngày; (2) model bịa số. Nguồn không truy cập được (lỗi chứng chỉ TLS
của sandbox chặn `WebFetch` tới hầu hết domain `.vn`) bị ghi rõ "chưa xác minh"
thay vì lấp bằng suy đoán.

## Kết luận nhanh

Không có ứng viên nào — kể cả thương mại — trả sẵn NPL/CAR/LDR/NIM theo cấu
trúc cho ngân hàng Việt Nam; đây là mục **phải tự xây** (xem mục cuối). Với dữ
liệu giá/sự kiện, vnstock (đang dùng) vẫn là lựa chọn hợp lý nhất vì đã tích
hợp, có gate quota, và giấy phép 2026.09 (đọc trực tiếp từ
`thinh-vu/vnstock@main:LICENSE.md`) cho phép dùng trong sản phẩm có doanh thu
miễn không đóng vai "sản phẩm mà giá trị chính là cấp quyền truy xuất dữ liệu
thị trường cho bên thứ ba" — Stock_Massive là agent nghiên cứu nội bộ, không
bán lại dữ liệu, nên rơi vào phạm vi được phép, không cần thoả thuận riêng.
Với tính toán có công thức in kèm, FinanceToolkit (JerBouma, MIT) là lựa chọn
tốt nhất cho các tỷ số phổ quát (ROE, P/B, thanh khoản...) nhưng xác nhận
**không có** hàm ngân hàng chuyên biệt (đọc trực tiếp mã nguồn
`ratios_controller.py`, 2026-09-27).

## Bảng ứng viên — dữ liệu thị trường / BCTC / sự kiện (câu hỏi C)

| Tên | Loại | Lỗi # | Bằng chứng + ngày nguồn | Trưởng thành | Rủi ro bảo mật/giấy phép | Công sức | Link |
|---|---|---|---|---|---|---|---|
| **vnstock** (thinh-vu, đang dùng) | Thư viện Python, bọc API TCBS/SSI/VCI/VNDirect | 5 (một phần) | `LICENSE.md` bản `license-2026.09`, đọc trực tiếp từ repo 2026-09-27; repo push mới nhất 2026-09-27, 1409 sao | Cao — hoạt động hằng ngày, cộng đồng lớn | Giấy phép nguồn-mở-giả (source-available, không OSI); dùng thương mại được phép trong hạn mức thiết bị/quota của cấp; redistribute hoặc bán quyền truy xuất dữ liệu cần thoả thuận riêng. Không có BCTC ngân hàng dạng cấu trúc (NPL/CAR/LDR/NIM) | Thấp (đã tích hợp) | https://github.com/thinh-vu/vnstock |
| **vnstock_data / vnstock premium** | Gói tài trợ, ngoài PyPI | 5 (một phần, mở khoá lịch sử dài hơn + phái sinh) | Trang tài trợ vnstock mô tả gói Diamond/Premium (qua tổng hợp WebSearch, chưa tự fetch được trang do lỗi TLS) — **chưa xác minh** trực tiếp danh sách trường dữ liệu | Không rõ — phụ thuộc cấp tài trợ | Gói `vnstock-data` 0.0.1 trên PyPI **không phải** kênh premium thật (kênh thật phân phối ngoài PyPI) — rủi ro nhầm gói/typosquat, đừng cài gói PyPI này | Vừa (cần liên hệ tác giả, không tự động hoá được) | https://pypi.org/project/vnstock-data/0.0.1/ (nghi vấn, không khuyến nghị) |
| **MCP chính thức của vnstock** | MCP | — | Không tìm thấy repo/tài liệu MCP do chính `vnstock-official` hoặc `vnstock-hq` phát hành; các trang liệt kê (mcpmarket.com, mcp.so) không xác nhận là chính chủ | **Chưa xác minh tồn tại** | — | — | không có link đáng tin |
| **mrgoonie/vnstock-agent** | MCP + CLI cộng đồng, bọc vnstock | 5 (một phần) | Repo push 2026-04-01, 103 sao (gh api, 2026-09-27) | Vừa — nhiều sao nhất trong nhóm MCP cộng đồng nhưng đã 6 tháng không cập nhật | Không có file LICENSE (license=null) → không rõ điều khoản kế thừa từ vnstock lẫn điều khoản riêng; chưa kiểm tra mã nguồn có gửi log/khoá ra ngoài không | Vừa | https://github.com/mrgoonie/vnstock-agent |
| **MaoBui2907/vnstock-mcp-server** | MCP cộng đồng | 5 (một phần) | MIT, push 2025-12-09, 2 sao (gh api) | Thấp — gần như không ai dùng, đã 9+ tháng | MIT rõ ràng nhưng dự án nhỏ, không kiểm chứng bảo trì | Vừa | https://github.com/MaoBui2907/vnstock-mcp-server |
| **archiephan78/ssi-stock-mcp-server** | MCP cộng đồng bọc SSI FastConnect | — | Apache-2.0, push 2025-08-06, 17 sao | Thấp — 14 tháng không cập nhật, ngoài cửa sổ 6 tháng | Cần `FC_DATA_CONSUMER_ID/SECRET` cá nhân nhập vào MCP bên thứ ba — rủi ro rò khoá SSI nếu không tự host | Vừa–Cao | https://github.com/archiephan78/ssi-stock-mcp-server |
| **FiinGroup / FiinQuant + FiinQuantMCP** | Vendor dữ liệu thương mại, kết nối trực tiếp KRX; MCP chính chủ ra mắt 6/2026 | 5 (tiềm năng, dữ liệu ngân hàng chuyên sâu) | Thông cáo chính thức fiingroup.vn (id2831997), không ghi ngày cụ thể trong đoạn trích — **ngày ra mắt suy từ nội dung "tháng 6/2026", chưa tự xác nhận qua trang gốc** vì lỗi TLS khi fetch | Vừa — công ty dữ liệu lâu năm (FiinGroup/FiinRatings), nhưng MCP là sản phẩm rất mới (~3 tháng tuổi) | Giá/điều khoản thương mại cụ thể, có gửi dữ liệu ra ngoài hay không: **chưa xác minh** (chỉ có giới hạn gói free qua trang liệt kê glama.ai, không phải trang chính chủ) | Cao (đăng ký thương mại, hợp đồng) | https://fiingroup.vn/en/news-fg/fiingroup-launches-fiinquantmcp-bringing-vietnams-stock-market-data-into-the-ai-era-id2831997.html |
| **SSI FastConnect Data (FC Data)** | API broker chính thức | — (giá/sự kiện, không phải fundamentals ngân hàng) | `guide.ssi.com.vn/ssi-products/fastconnect-data` — trang chính thức, tồn tại (curl xác nhận không áp dụng, chỉ WebSearch); ngày cập nhật trang **chưa xác minh** | Cao — SSI là công ty chứng khoán lớn, API có spec PDF v2.0 | Cần tài khoản SSI + `consumer_id/secret`; không có dấu hiệu dữ liệu người dùng gửi ra bên thứ ba (chạy trực tiếp với SSI) | Vừa | https://guide.ssi.com.vn/ssi-products/fastconnect-data |
| **DNSE / Entrade X Lightspeed API** | API broker chính thức | — | `hdsd.dnse.com.vn` tài liệu chính thức tồn tại; ngày cập nhật **chưa xác minh** | Vừa — DNSE là công ty chứng khoán hoạt động, tài liệu có bản "trước KRX" và bản mới, cho thấy đang bảo trì | Cần tài khoản DNSE + token đăng nhập; không phát hiện điều khoản gửi dữ liệu ra bên thứ ba, nhưng chưa đọc ToS đầy đủ | Vừa–Cao | https://hdsd.dnse.com.vn/san-pham-dich-vu/api-lightspeed |
| **VNDirect finfo API** (`finfo-api.vndirect.com.vn`) | Endpoint nội bộ không công bố, bị vnstock/vnquant reverse-engineer | 5 (một phần, đang là nguồn ngầm phía sau vnstock) | Nhiều repo cộng đồng dùng (nguyenngocbinh/vnstock, vnquant issue #6); không có tài liệu phát triển viên chính thức | Thấp với vai trò "API độc lập" — đây là endpoint nội bộ, có thể đổi/chặn bất kỳ lúc nào không báo trước | Không có ToS phát triển viên; dùng ngoài ứng dụng VNDirect có thể vi phạm điều khoản trang chủ (`vndirect.com.vn/dieu-khoan-su-dung`, chưa fetch được nội dung) | Thấp nếu qua vnstock (đã có), Cao nếu gọi trực tiếp | không khuyến nghị gọi trực tiếp |
| **TCBS internal API** | Endpoint nội bộ, vnstock đã bọc sẵn | 5 (một phần) | Cùng nguồn với vnstock; không có tài liệu phát triển viên riêng | Thấp độc lập | Không ToS công khai | Thấp qua vnstock, Cao nếu gọi trực tiếp | không khuyến nghị gọi trực tiếp |
| **Vietstock DataFeed** (`dichvu.vietstock.vn`) | Vendor thương mại chính thức | 5 (tiềm năng) | Trang dịch vụ chính thức tồn tại; giá/điều khoản cụ thể **chưa xác minh** (cần liên hệ sales) | Vừa — Vietstock hoạt động lâu năm, có sản phẩm B2B | Kênh thương mại chính thức, rủi ro thấp hơn endpoint scrape | Cao (đàm phán hợp đồng) | https://dichvu.vietstock.vn/du-lieu-tai-chinh |
| **Vietstock API ngầm** (`api.vietstock.vn`) | Endpoint không tài liệu | — | Cộng đồng ghi nhận "công khai nhưng không tài liệu chính thức", đã bổ sung request-verification-token từ 2021 để chặn scrape (nguồn: README cộng đồng, không phải Vietstock chính thức — **thông tin thứ cấp**) | Thấp, có nguy cơ bị chặn cookie | Không rõ chủ thể chịu trách nhiệm nếu bị chặn/khoá | Cao, dễ gãy | xem mục "phổ biến nhưng không nên dùng" |
| **CafeF** | Không có API, chỉ scrape HTML | — | Nhiều repo scrape riêng lẻ (`tuong-nguyen-vn/crawl-data-stock-from-cafef.vn`), không ToS công khai cho phép | Thấp | Không ToS, dễ vỡ khi đổi giao diện | Cao | xem mục loại bỏ |
| **WiChart** | Sản phẩm hiển thị của Vietstock Finance, không có API riêng biệt được xác nhận | — | Không tìm thấy API độc lập trong tìm kiếm | **Chưa xác minh tồn tại dưới dạng API riêng** | — | — | — |
| **SimplizeAPI** | — | — | Không tìm thấy sản phẩm API công khai tên "Simplize" trong kết quả tìm kiếm | **Chưa xác minh tồn tại** | — | — | — |
| **vietfin** (vietfin/vietfin) | Thư viện Python, bọc nhiều API broker | 5 (một phần) | Apache-2.0, push cuối 2024-04-22 — **đã hơn 2 năm, ngoài cửa sổ 6 tháng** | Bỏ hoang | Tự khai "chỉ dùng cá nhân, nghiên cứu, giáo dục" trong docs — mâu thuẫn với bối cảnh sản phẩm có doanh thu | Vừa | https://github.com/vietfin/vietfin (không khuyến nghị) |
| **hungson175/vnfin** | Thư viện Python mới, nhiều nguồn có fallback | 5 (tiềm năng) | Apache-2.0, push 2026-09-19 (8 ngày trước khi viết báo cáo) — rất mới | **Rất thấp** — 1 sao, 1 tác giả, chưa có lịch sử ổn định | License rõ nhưng chưa có ai kiểm chứng nguồn dữ liệu nội bộ dùng endpoint nào | Vừa (cần tự kiểm tra trước khi tin) | https://github.com/hungson175/vnfin — đáng theo dõi, chưa đủ chín để phụ thuộc |
| **HOSE — Công bố thông tin** (hsx.vn) | Nguồn chính thức, miễn phí | 4 (ngày nguồn) | curl xác nhận 200 OK 2026-09-27; không có API JSON/XBRL, chỉ trang HTML + PDF | Cao (cơ quan quản lý) | Không rủi ro bảo mật; công khai | Cao (phải crawl/parse PDF, không có feed cấu trúc) | https://www.hsx.vn |
| **HNX — Công bố thông tin** (hnx.vn) | Nguồn chính thức, miễn phí | 4 | curl xác nhận 200 OK 2026-09-27; chỉ HTML/PDF | Cao | Không rủi ro | Cao | https://hnx.vn |
| **UBCKNN — Cổng công bố thông tin** (congbothongtin.ssc.gov.vn / IDS) | Nguồn chính thức, miễn phí | 4 | curl xác nhận 200 OK 2026-09-27; không tìm thấy bằng chứng có XBRL — **chưa xác minh có/không có XBRL**, kết luận tạm "không có" dựa trên việc tìm kiếm không ra kết quả | Cao | Không rủi ro | Cao | https://congbothongtin.ssc.gov.vn |

Nhóm MCP cộng đồng cùng dạng, sao ~0, nhiều cái `license=null`, không thêm giá
trị so với bảng trên (đều bọc lại vnstock hoặc một endpoint đã liệt kê):
`gahoccode/vnstock-mcp` (0 sao, không license, push 2026-05-09),
`khoantd/vnstock-mcp` (0 sao, push 2026-01-19), `vietnh/vnstock-mcp-server`
(MIT, 0 sao, push 2025-06-12 — >1 năm), `thieung/vnstock-plus-mcp` (0 sao,
không license, push 2026-03-04), `danhthevodanh/vnstock-mcp-server` (0 sao,
không license, push 2026-09-03), `Long0308/vn-stock-api-mcp` (4 sao, không
license, push 2025-11-13). Không khuyến nghị cái nào cho tới khi có nhu cầu cụ
thể mà vnstock trực tiếp không đáp ứng.

## Bảng ứng viên — tính toán tài chính có công thức in kèm (câu hỏi D)

| Tên | Loại | Trưởng thành | Đánh giá kỹ thuật | Công sức | Link |
|---|---|---|---|---|---|
| **FinanceToolkit** (JerBouma) | Thư viện Python, 200+ tỷ số | MIT, 5384 sao, push 2026-09-10 (17 ngày trước) | Đọc trực tiếp `ratios_controller.py` (2026-09-27): có đủ ROE, ROA, P/B, P/E, thanh khoản, đòn bẩy, hiệu quả — mỗi hàm là công thức Python tường minh (đúng tinh thần "formula printed"). **Xác nhận không có** `get_non_performing_loan_ratio`, `get_capital_adequacy_ratio`, `get_net_interest_margin`, `get_loan_to_deposit_ratio` — grep 0 kết quả. Chạy local, xác định (không gọi mạng để tính), cài bằng `pip`. Phù hợp nhất cho tỷ số phổ quát; không giải quyết phần ngân hàng của lỗi 5 | Thấp (thêm dependency) | https://github.com/JerBouma/FinanceToolkit |
| **numpy-financial** | Thư viện Python, hàm TVM (npv/irr/pmt...) | BSD-3, 409 sao, push 2026-09-17 (10 ngày trước) | Bản tách chính thức từ NumPy, xác định, không phụ thuộc mạng — hữu ích nếu cần thêm hàm giá trị tiền tệ theo thời gian, không trực tiếp giải lỗi 5 | Thấp | https://github.com/numpy/numpy-financial |
| **QuantLib** | Thư viện định giá trái phiếu/phái sinh (C++/Python binding) | Rất trưởng thành, dùng rộng rãi trong ngành | **Không phù hợp phạm vi** — hướng tới lãi suất/trái phiếu/phái sinh, không phải tỷ số cổ phiếu/ngân hàng Việt Nam; build binding C++ nặng, vi phạm KISS nếu chỉ cần vài phép chia. Không giải quyết lỗi nào trong 3 lỗi mục tiêu | Cao, không đáng | không khuyến nghị cho phạm vi này |
| **empyrical** (quantopian) | Chỉ số hiệu suất danh mục (Sharpe, drawdown...) | Apache-2.0, 1514 sao, push cuối 2024-07-26 — **bỏ hoang từ khi Quantopian đóng cửa** | Hướng tới lợi nhuận danh mục theo thời gian, không phải tỷ số BCTC/định giá — không giải lỗi 2/4/5 | — | không khuyến nghị (lạc phạm vi + bỏ hoang) |
| **pyfolio** (quantopian) | Báo cáo phân tích danh mục | Apache-2.0, 6426 sao, push cuối 2023-12-23 — **bỏ hoang gần 3 năm** | Phụ thuộc empyrical, cần notebook/matplotlib, nặng, lạc phạm vi | — | không khuyến nghị |
| **quantstats** | Báo cáo phân tích danh mục (Sharpe/CAGR/drawdown) | Apache-2.0, 7659 sao, push 2026-09-26 (hôm qua) — **rất tích cực bảo trì** | Chất lượng cao nhưng vẫn lạc phạm vi: đây là công cụ backtest lợi nhuận, không tính NPL/CAR/ROE/P-B từ BCTC. **Không giải quyết lỗi nào trong 3 lỗi mục tiêu** hiện tại | — | ghi nhận để dùng sau nếu có tính năng backtest, không dùng cho việc này |
| **calc-mcp-server** (slettmayer) | MCP máy tính an toàn, AST allowlist, không `eval()` | MIT, push 2026-09-24 (3 ngày trước) | Đúng pattern "safe calculator, không eval tuỳ ý"; nhưng dự án đã có sẵn tool `calculate` nội bộ (phép toán cố định, in công thức, theo CLAUDE.md) — **trùng chức năng, không cần thêm dependency ngoài**, chỉ dùng làm tài liệu tham khảo thiết kế | Không cần tích hợp | https://github.com/slettmayer/calc-mcp-server (tham khảo, không cài) |

## Phổ biến nhưng không nên dùng

- **`api.vietstock.vn` (endpoint ngầm)** — công khai nhưng không tài liệu
  chính thức, đã bị hardening (verification token) từ 2021 để chặn scrape;
  bản chính thức hợp lệ là Vietstock DataFeed (thương mại, có hợp đồng).
- **CafeF scrape** — không API, không ToS công khai cho phép lấy dữ liệu tự
  động; vỡ ngay khi đổi giao diện.
- **`finfo-api.vndirect.com.vn` / TCBS nội bộ gọi trực tiếp (không qua
  vnstock)** — là endpoint nội bộ bị reverse-engineer, không có cam kết ổn
  định; đã được vnstock bọc sẵn, gọi thêm lần nữa chỉ tăng rủi ro trùng lặp và
  vi phạm giới hạn nhịp gọi ở tầng khác.
- **`vnstock-data` trên PyPI (0.0.1)** — nhiều khả năng không phải kênh
  premium thật của vnstock (kênh thật phân phối ngoài PyPI theo mô tả của
  chính vnstock); đừng cài nhầm.
- **vietfin** — bỏ hoang >2 năm, tự giới hạn "chỉ dùng cá nhân/nghiên cứu"
  trong tài liệu — không khớp bối cảnh sản phẩm có doanh thu.
- **empyrical / pyfolio (Quantopian)** — bỏ hoang từ khi Quantopian đóng cửa
  (2020), và lạc phạm vi (đo lợi nhuận danh mục, không phải tỷ số BCTC).
- **QuantLib** — đúng phạm vi trái phiếu/phái sinh, sai phạm vi cổ phiếu/ngân
  hàng Việt Nam; chi phí build không tương xứng giá trị cho câu hỏi này.
- **Các MCP vnstock cộng đồng 0 sao / không license** (`gahoccode/vnstock-mcp`,
  `khoantd/vnstock-mcp`, `thieung/vnstock-plus-mcp`,
  `danhthevodanh/vnstock-mcp-server`, `Long0308/vn-stock-api-mcp`,
  `MaoBui2907/vnstock-mcp-server`, `vietnh/vnstock-mcp-server`) — không thêm
  giá trị so với gọi thẳng thư viện vnstock đã tích hợp; một số không có file
  LICENSE nên không rõ điều khoản kế thừa; rủi ro cao hơn lợi ích.

## Lỗi nào phải tự xây (không có sản phẩm/thư viện nào giải sẵn)

**Lỗi 5 — NPL, CAR, LDR, NIM cho ngân hàng niêm yết Việt Nam.** Không có thư
viện Python nào (đã kiểm: FinanceToolkit — mã nguồn xác nhận không có; các gói
vnstock/vietfin/vnfin — chỉ trả BCTC dạng dòng chuẩn hoá thông thường, không
có nhóm nợ 1-5 hay vốn tự có/tài sản có rủi ro theo Basel II) và không có
vendor nào được xác nhận trực tiếp (FiinQuant có khả năng cao nhất về mặt
nghiệp vụ vì là công ty dữ liệu tài chính chuyên sâu, nhưng chưa xác minh được
trường dữ liệu cụ thể qua tài liệu chính chủ). Cách phải tự xây: lấy thuyết
minh BCTC ngân hàng (nợ theo Thông tư 31/2024/TT-NHNN hoặc Thông tư
11/2021/TT-NHNN về phân loại nợ, và Thông tư 41/2016/TT-NHNN về tỷ lệ an toàn
vốn Basel II) — dạng số đã có sẵn trong dữ liệu BCTC do vnstock/FinancialsProvider
lấy về nếu đủ chi tiết dòng, hoặc phải parse PDF từ HOSE/HNX/UBCKNN nếu
không — rồi tính bằng một hàm nội bộ theo đúng pattern đã có ở tool
`calculate` (phép toán cố định, in công thức, ghi rõ dòng BCTC/kỳ báo cáo làm
nguồn). Đây là việc thêm một "ratio module" nội bộ, không phải thay `calculate`.

**Lỗi 4 — nguồn cũ không đánh dấu ngày.** Ba cổng công bố chính thức (HOSE,
HNX, UBCKNN/IDS) đều gắn ngày công bố với từng tài liệu — đây là nguồn ngày
tham chiếu đáng tin nhất, nhưng không có feed cấu trúc (JSON/XBRL), nên việc
gắn ngày cho một con số vẫn phải do `grounding.py` xử lý ở tầng host như đang
làm; không có sản phẩm ngoài nào tự động hoá việc này cho dữ liệu BCTC ngân
hàng — vẫn phải tự nối tool nguồn dữ liệu (khi có) với logic gắn ngày sẵn có.

**Lỗi 2 — model bịa số.** Về kiến trúc đã có lời giải (claim ledger +
grounding + tool `calculate` in công thức); khoảng trống thực sự là lỗi 5 —
khi không có tool trả NPL/CAR có nguồn, model không có gì để trích dẫn ngoài
bài báo, nên bịa/copy số báo. Giải lỗi 5 gián tiếp giải phần còn lại của lỗi 2
cho nhóm chỉ số ngân hàng.

## Câu hỏi chưa giải quyết

1. FiinQuantMCP: giá, điều khoản dữ liệu, và liệu gói free/trả phí có field
   NPL/CAR/LDR/NIM theo ngân hàng riêng lẻ hay không — cần liên hệ sales trực
   tiếp hoặc thử tài khoản free vì trang chính chủ không fetch được (lỗi TLS
   sandbox), chỉ có trang tin tức + trang liệt kê bên thứ ba.
2. Nội dung ToS gốc của `vndirect.com.vn/dieu-khoan-su-dung` và
   `hdsd.dnse.com.vn` — chưa fetch được, chỉ biết trang tồn tại.
3. Vnstock có XBRL không, và HOSE/HNX/UBCKNN có kế hoạch nào cho báo cáo điện
   tử có cấu trúc — không tìm thấy bằng chứng nào trong lần tìm kiếm này (có
   thể do từ khoá chưa đúng, không phải bằng chứng phủ định chắc chắn).
4. Bảo mật mã nguồn của các MCP cộng đồng (`mrgoonie/vnstock-agent` v.v.) —
   chưa audit dòng-theo-dòng xem có gửi log/khoá ra dịch vụ thứ ba; chỉ đánh
   giá qua README/lịch sử commit. Cần một lượt đọc mã nguồn riêng trước khi
   cân nhắc cài bất kỳ MCP cộng đồng nào.

Status: DONE_WITH_CONCERNS
Summary: Không tìm thấy nguồn/thư viện nào cung cấp sẵn NPL/CAR/LDR/NIM có cấu trúc cho ngân hàng Việt Nam (kể cả FinanceToolkit và FiinQuant chưa xác nhận được) — đây là hạng mục phải tự xây bằng cách parse thuyết minh BCTC và tính trong một ratio module theo đúng pattern `calculate` đã có; với giá/sự kiện, vnstock (đang dùng) vẫn là lựa chọn hợp lý nhất, giấy phép 2026.09 xác nhận cho phép dùng thương mại trong hạn mức.
Concerns/Blockers: Một số nguồn (FiinQuantMCP pricing/field, VNDirect/DNSE ToS, XBRL của UBCKNN) không fetch được do lỗi TLS của môi trường sandbox — đã ghi "chưa xác minh" thay vì suy đoán; cần một lượt kiểm tra thủ công ngoài sandbox trước khi ký hợp đồng thương mại với FiinGroup/Vietstock.
