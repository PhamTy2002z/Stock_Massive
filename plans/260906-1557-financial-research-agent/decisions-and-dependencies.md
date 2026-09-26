# Quyết định, phạm vi và dependency

Ngày 2026-09-06. Tất cả thay đổi dưới đây là **PROPOSED**, chưa amend roadmap.

## Outcome và ranh giới

Agent chuyên nghiên cứu cổ phiếu Việt Nam: kiểm chứng luận điểm, memo sự kiện, tra cứu dữ kiện, phân xử mâu thuẫn; hỗ trợ BCTC và thuyết minh, tin tức, thông tin ngách theo ngành/doanh nghiệp, diễn biến giá và phản ứng thị trường. User nhận câu trả lời có bằng chứng, khoảng trống và bước tiếp theo; không cam kết biết mọi dữ kiện hoặc chứng minh nhân quả từ tương quan.

Giữ single-agent runtime hiện có, không migrate Hermes/OpenCode/Deep Agents; giữ Flint chính thức, không fork/copy template/post-process compiler output. Không order execution, tư vấn phân bổ cá nhân hóa, terminal dữ liệu toàn thị trường, Study/Board DSL, widget engine, global watchlist. Dossier theo thread và rerun chủ động vẫn trong phạm vi. Monitoring tự chạy chỉ được xem xét ở conditional phase và cần phê duyệt mới.

## Decision register

| ID | Hiện tại → evidence | Đề xuất và trade-off | Gate / owner |
|---|---|---|---|
| D1 | P6 web-first; PDF parser có nhưng fetch URL chỉ HTML | Mở đọc document qua `fetch_url` và attachment, giữ cùng security/tool plane. Thêm MIME/provenance và quota thay vì runtime mới | Product + backend duyệt typed contract; phase 1 |
| D2 | Market chỉ Signal Desk + personal_internal | Cho nguồn **đã được cấp quyền** khả dụng theo intent/policy ở cả Chat và Signal Desk; mode chỉ điều khiển visual. Vnstock hiện tại vẫn internal-only | Product + data owner xác nhận quyền trước phase 4 |
| D3 | Catalog thêm đúng một OHLCV tool | Mở dataset cần thiết trong provider-neutral read surface: giá, benchmark, corporate actions, financial statements khi provider có quyền/coverage. Không mở toàn SDK | Catalog/schema/resource/rights manifest duyệt phase 1; thực hiện phase 4 |
| D4 | Core hiện chưa thực thi arithmetic trước P11 | Đề xuất phép tính hữu hạn trên observation IDs, Decimal, unit checks, provenance. Không shell/eval/code model sinh. Có sẵn `CALCULATION` enum không phải authorization | Đây vẫn là compute deviation; phải duyệt trước phase 5. Nếu bác, dùng reported figures và đánh dấu job định lượng bị giới hạn |
| D5 | Bốn tool call đầu cố định; gaps là prose | Coverage theo requirement của câu hỏi, bounded targeted recovery. Giữ một loop/budget/guardrail/state machine | Đo lỗi baseline trước; duyệt thay batch gate và additive checkpoint contract trước phase 6 |
| D6 | Claim verdict được recompute theo nguồn/ID/số | Làm rõ semantic support là điều kiện cần, mechanical checks không nâng semantic rejection; claim bị bỏ sót vẫn nằm denominator. Phân biệt semantic accuracy với provenance validity | Ưu tiên sửa cause-aligned, kiểm bằng failing fixture; nếu đổi nghĩa truth/public label phải Product duyệt phase 1 |
| D7 | So sánh `observed_at` với cutoff dù pipeline gán retrieval time | Phân biệt retrieved_at với published/available_at. Historical query chỉ dùng **phiên bản đã có ở cutoff**, không lấy bản restated mới chỉ vì kỳ cũ | Policy amendment nếu thay semantics; historical/version fixtures trước phase 2 |
| D8 | Hai publisher có thể được coi là độc lập | Ghi origin của thông tin; syndicated copies không là hai xác nhận độc lập; unknown independence giữ single-source | Product duyệt source policy trước phase 2 |
| D9 | Visual chỉ OHLCV, chart shape theo số call | Mở chart theo câu hỏi và dataset đã kiểm; model chỉ chọn type/field/evidence refs. Host bind số; chart intent versioned, không DSL thứ hai | Public part schema và Flint capability spike trước phase 7 |
| D10 | Sequential P6→P7→P8→P9, compute ở P11 | W1 baseline; W2–W6 là work package mở rộng P6; W7=P7 + Signal amendment; W8=P8; W9=P9; W10=P10–12. D4 là ngoại lệ nhỏ cần duyệt rõ | Phê duyệt mapping trước code; không thực hiện phase sau bằng cách đổi tên |

## Đối chiếu kế hoạch đang dở

Scan file thực tế chỉ có `260905-0001-signal-desk-visual-harness/plan.md` trước plan mới. Nó đã có nhiều implementation trong dirty working tree và gate live chưa đóng theo graduation report. Giữ nguyên code và trạng thái, thêm dependency hai chiều: plan cũ `blocks` plan này, plan này `blockedBy` plan cũ.

Phase 1 được đọc/chẩn đoán và đề xuất amendment ngay; không tự khẳng định baseline đã tốt nghiệp. Muốn hợp nhất graduation cũ vào release mới phải có quyết định thay gate riêng, ghi owner và acceptance thay thế; mặc định không làm vậy. Không cập nhật hoặc khôi phục các plan file đã biến mất chỉ vì index/roadmap còn tên.

## Các lựa chọn và giả định chưa khóa

| Chủ đề | Giả định lập kế hoạch | Nếu sai |
|---|---|---|
| Rollout | Internal pilot rồi customer beta | SaaS ngay: quyền dữ liệu và vận hành trở thành blocker sớm; không bypass |
| Hero job | BCTC + sự kiện, sau đó phủ toàn bộ các family còn lại | Đổi thứ tự corpus/nguồn, giữ full scope |
| Data | Có thể khảo sát nguồn thương mại; chưa có vendor hay ngân sách được chọn | Public-only: tài liệu và lịch sử công khai có quyền phù hợp; ghi rõ thiếu realtime/coverage; không hứa ngang provider |
| Eval | Đề xuất 3 trial cho baseline/release; ceiling do owner cấp | Chưa có ceiling: chỉ offline gate, không gọi live quality đã đạt |
| Finance review | Có người kiểm ground truth và adjudicate | Không có: chưa phát hành claim về accuracy, customer release chờ |
| OCR | Sẽ gặp PDF scan; parser text không đủ một phần corpus | Probe corpus để chọn OCR cục bộ/dịch vụ có quyền privacy; không mặc định gửi tài liệu riêng cho bên thứ ba |

## Scope đầy đủ nhưng thi công theo khả năng đã chứng minh

Tất cả family người dùng yêu cầu nằm trong phase 1–9. Các dataset industry-specific không bị cắt; triển khai playbook tìm/đọc nguồn và mở adapter chỉ khi nguồn thực tế đòi hỏi. Không cần một class/provider framework cho từng loại chỉ tiêu.

Phase 10 là kế hoạch conditional có trigger, deliverable và gate riêng cho scale, sandbox, delegation/MCP. Không gọi chúng đã được cho phép; không lấy việc chưa xây chúng làm lý do trì hoãn sản phẩm research đã đạt gate.

## Unresolved questions

Ai phê duyệt quyền nguồn và ground truth? Ngân sách nguồn/eval? Chấp thuận D1–D10 tới mức nào? Có ranh giới research/advice chính thức cho customer copy? Phải có câu trả lời trước phase sở hữu quyết định, không cần câu trả lời để đọc và đánh giá plan.
