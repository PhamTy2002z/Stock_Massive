# Harness và hướng phát triển financial research

Thời điểm: 2026-09-06 15:45 ICT. Trạng thái: khuyến nghị để thảo luận, không phải roadmap đã chấp thuận.

## Kết luận

Giữ Hermes/OpenCode làm nguồn tham khảo cho runtime; chưa có bằng chứng cần thay runtime hoặc thêm harness thứ ba. Ưu tiên một luồng nghiên cứu doanh nghiệp hoàn chỉnh trên nền hiện có: khám phá nguồn → đọc tài liệu → lấy dữ liệu đúng loại → kiểm chứng → trả lời đủ nhu cầu → biểu đồ khi hữu ích.

Không tiếp tục phát triển harness chung tách rời câu hỏi tài chính thật. Cũng không lấy việc vẽ được chart làm thước đo agent thông minh. Nút thắt được source xác nhận hiện nằm ở khả năng đọc tài liệu, phạm vi dữ liệu, kế hoạch truy xuất cứng và mức độ chart đáp ứng ý định người dùng.

## Phương pháp và giới hạn

Đọc CLAUDE.md, roadmap hiện tại, source loop/tool/evidence/visual, kế hoạch Signal Desk và graduation report. Đối chiếu README upstream Hermes, OpenCode, Deep Agents và Flint qua GitHub ngày nêu trên. Context7 không có tài liệu Flint nên dùng nguồn chính thức trực tiếp. Đây là so sánh kiến trúc, không phải benchmark các framework.

Workspace có nhiều thay đổi chưa commit, gồm loop, ledger và visual; kết luận source phản ánh working tree hiện tại. Không sửa code, không chạy live model/provider, không chạy lại suite. Các số test hoặc trạng thái paid gate trong tài liệu là kết quả được báo cáo trước đây, không phải kết quả đo của lượt phân tích này.

## Những gì nền hiện tại đã có

- Durable Turn/typed state, checkpoint, SSE, cancellation và settlement.
- Capability resolution và tool executor thống nhất, permission, budget, guardrails.
- Context management, web search/fetch, memory/session tools.
- Deep pipeline research → counterevidence → clean-context verification; claim/evidence ledger.
- Signal Desk dùng market evidence, host assemble input, Flint compile, ECharts render.

Roadmap ghi Phase 1–5 Done, Phase 6 có code nhưng vẫn Target vì quality gate chưa tốt nghiệp toàn bộ. Signal Desk graduation report cũng ghi chưa có paid/live release hoàn chỉnh. Không đồng nhất nhiều unit test xanh với chất lượng nghiên cứu tài chính đã được chứng minh.

## Các phát hiện có bằng chứng source

| Phát hiện | Nguồn | Hệ quả |
|---|---|---|
| Chat không được cấp market tool; Signal Desk thêm market tool theo mode | `apps/api/src/agent/toolsets.py`, `CLAUDE.md` | Nhu cầu dữ liệu của cùng câu hỏi đang phụ thuộc lựa chọn hiển thị |
| Market tool chỉ OHLCV, KBS qua Vnstock, 1D/15m, tối đa 250 rows; internal profile | `apps/api/src/agent/tools/market_data.py` | Chưa thể đọc BCTC, segment, sở hữu, corporate actions hoặc benchmark chỉ bằng tool này; production không được dùng feed này theo policy hiện tại |
| `_fetch_page` decode body thành text rồi xử lý HTML, không phân nhánh PDF | `apps/api/src/agent/tools/web.py:1043` | Tìm thấy URL BCTC chưa có nghĩa agent đọc được báo cáo gốc |
| `parse_document` có PDF/XLSX/DOCX và test, nhưng search production source chỉ thấy định nghĩa | `apps/api/src/agent/evidence/documents.py:429`, `apps/api/tests/test_agent_document_evidence.py` | Có năng lực parser riêng lẻ, chưa xác nhận một đường production nối nó vào research; PDF dùng pypdf text extraction, chưa có OCR ở parser này |
| Planner bắt đúng 4 calls: 4 search hoặc 3 search + 1 market read | `apps/api/src/agent/loop.py:1715` | Cấu trúc batch được dùng làm gate, chưa đánh giá batch có phù hợp câu hỏi hay không; query khác chuỗi cũng chưa chắc khác góc nhìn |
| Sau verification, loop validate ledger rồi COMPLETE | `apps/api/src/agent/loop.py:2032` | Ledger hỗ trợ độ tin cậy của claim, chưa phải bằng chứng rằng đã trả lời hết nhu cầu; gaps có thể còn khi Turn hoàn tất |
| `_numbers_supported` tìm số trong excerpt; publisher identity được dùng cho multi-source verdict | `apps/api/src/agent/evidence/ledger.py:161` | Có giá trị kiểm tra cơ học nhưng số xuất hiện không chứng minh đúng dòng/kỳ/chỉ tiêu; hai báo có thể sao lại cùng một nguồn |
| Một market read → candles + volume; nhiều reads → đường giá đóng cửa tuyệt đối | `apps/api/src/agent/visual.py:262` | Đây là biểu đồ OHLCV có nguồn, chưa phải visualization linh hoạt theo yêu cầu nghiên cứu |
| Visual chỉ nhận evidence được claim VERIFIED/SINGLE_SOURCE dùng | `apps/api/src/agent/visual.py:245` | Có coupling giữa khả năng xuất chart và việc narrative claim dẫn market evidence; chưa đo tần suất nó gây mất chart |

Về truth contract: ledger có thể enforce ID/URL/đơn vị/thời gian và render provenance. Clean-context verifier vẫn là model; sự tương đương ngữ nghĩa giữa claim và nguồn cần eval và human audit. Không thể suy ra bảo đảm semantic accuracy 100% chỉ từ cấu trúc ledger.

## Nên neo vào đâu

| Tham chiếu | Vai trò phù hợp | Quyết định đề xuất |
|---|---|---|
| Hermes | Loop, recovery, context và bounded persistence | Giữ; không nhập tự động self-editing memory/skills vào finance truth boundary |
| OpenCode | Server/client boundary, typed durable state, capability/permission | Giữ; không coi host permission là sandbox isolation |
| Deep Agents / LangGraph | Planning, context offloading, checkpointing, delegation | Tham khảo khi có lỗi cụ thể; không migrate. Các tính năng tài liệu giới thiệu chồng lấn đáng kể với nền hiện có, không cung cấp nguồn BCTC VN |
| STORM, SAFE/FacTool và các research pattern đã có trong roadmap | Đa góc nhìn, decomposition và đánh giá support từng claim | Dùng ở tầng research/eval theo roadmap; chưa benchmark lại upstream trong lượt này |
| Flint | Semantic chart specification → compiler → renderer | Giữ ở vai trò visualization; không gán trách nhiệm tìm/chuẩn hóa/chứng minh dữ liệu |

README Deep Agents xác nhận runtime dựa trên LangGraph cùng filesystem, subagents, context management và memory. Đây là ứng viên tốt nếu bắt đầu từ trắng; chưa có bằng chứng migration cải thiện outcome của repo hiện tại. Chỉ xem xét lại khi đo được một vấn đề runtime cụ thể mà thay đổi nhỏ ở nền hiện có không xử lý được.

## Hướng sản phẩm được khuyến nghị

Chọn một job xuyên suốt, ví dụ: “Lợi nhuận HPG quý gần nhất tăng do hoạt động chính hay khoản bất thường; giá đã phản ứng thế nào?”

Agent cần biết tìm BCTC/CBTT và thuyết minh; phân biệt quý riêng với lũy kế, hợp nhất với riêng lẻ, lợi nhuận sau thuế với phần cổ đông công ty mẹ; tìm phản chứng; đọc chuỗi giá đúng cửa sổ công bố. Kết quả gồm câu trả lời, bảng số liệu truy nguồn và chart nếu dữ liệu đủ.

Ba nhóm nguồn bổ sung nhau:

1. Filing/IR/CBTT và tài liệu ngành cho sự kiện, BCTC, thông tin ngách. Lưu provenance đến trang/bảng, entity, kỳ, đơn vị, publication time, phiên bản điều chỉnh.
2. Nguồn structured có quyền sử dụng phù hợp cho giá, corporate actions và các dataset thật sự phục vụ job đã chọn. Đánh giá quyền phần mềm và quyền upstream riêng; chưa chọn vendor khi chưa có probe và xác nhận quyền.
3. Web search để phát hiện nguồn, tin mới, phản chứng và góc nhìn. Kết quả search không thay thế một kho chuỗi số có kỳ/thời gian rõ ràng.

Thông tin ngách nên theo doanh nghiệp/ngành của câu hỏi: sản lượng, backlog, dự án, nguyên liệu, khách hàng, giao dịch liên quan. Không cần xây toàn bộ data platform hoặc knowledge graph trước khi hoàn thành một job.

Đối với phản ứng thị trường, mức tăng giá sau tin chỉ là quan sát. Kết luận tương đối cần benchmark, cửa sổ công bố và corporate actions; suy luận nguyên nhân phải tách khỏi đồng thời xảy ra.

## Các thay đổi quyết định cần thảo luận trước implementation

Đây là deviation đề xuất, chưa thay authority hoặc mở capability:

| Quyết định hiện tại | Evidence mới | Trade-off và lựa chọn |
|---|---|---|
| Market access chỉ theo Signal Desk mode | Chat cũng có câu hỏi cần chuỗi giá; source khóa theo toolset | Giữ để thử nghiệm nội bộ đơn giản, hoặc sau khi có quyền nguồn, cấp dữ liệu theo intent + policy, mode chỉ chọn trình bày. Khuyến nghị lựa chọn sau |
| Deep planner có batch cố định | `_valid_planner_calls` enforce số lượng/type, kể cả khi user đã cung cấp tài liệu/URL | Giữ tính dự đoán hiện tại, hoặc đo corpus rồi thay gate batch bằng yêu cầu bằng chứng tối thiểu theo job. Giữ budget và permission |
| Compute đợi Phase 11 sau Phase 1–9 | Ledger kiểm số có sẵn, không chứng minh phép tính mới; use case tài chính có tăng trưởng/tỷ trọng | Giữ gate nếu nguồn đã có số cần dùng. Nếu eval chứng minh thiếu phép tính là blocker, đề xuất tính toán hữu hạn có provenance hoặc mở sớm sandbox với gate riêng; chưa kết luận cần sandbox tổng quát |
| Chart shape suy từ số market reads | Source chỉ có candles/volume/raw-price lines | Giữ scope và nói đúng khả năng hiện tại. Sau khi dataset mới đã đáng tin, cho model đề xuất loại chart/field/evidence IDs, host bind số và validate bằng compiler hiện có |

Không cần bỏ Signal Desk hoặc thay Flint để thực hiện hướng này. Tạm dừng mở rộng chart vô hạn; đầu tư vào nguồn và khả năng trả lời trước. So sánh hiệu suất phải dùng return/index-base với phép tính truy nguồn; raw-price lines hiện tại chỉ so sánh mức giá.

## Trình tự đề xuất và tiêu chí đo

1. Dùng golden hiện có, chọn khoảng 20 câu đại diện: BCTC, tin/sự kiện, thông tin ngách, phản ứng thị trường, mâu thuẫn/thiếu dữ liệu. Chấm cả việc tìm được dữ liệu và trả lời đủ yêu cầu; từ chối đúng không được tính là đã đáp ứng nhu cầu.
2. Phân loại lỗi theo bước: discovery, download/parse, source coverage/rights, kỳ/đơn vị/entity, reasoning/verification, visualization. Có denominator theo từng nhóm.
3. Hoàn thành đường tài liệu đã tìm được → parser → evidence có trang/kỳ/đơn vị. Ưu tiên reuse parser hiện có; OCR chỉ mở khi mẫu PDF thật chứng minh cần.
4. Probe một nguồn structured hợp lệ cho job đã chọn, gồm coverage, ngày/kỳ, điều chỉnh, độ trễ, tỷ lệ lỗi và quyền phân phối. Không cần nhiều adapter trước khi có provider thực.
5. Chỉ sửa planner/coverage/research loop ở lỗi corpus chứng minh. Thêm trường hợp số đúng nhưng sai chỉ tiêu/kỳ và nhiều bài cùng nguồn gốc để chấm verifier.
6. Đưa một job qua toàn bộ text → evidence → visual → refresh/replay. Sau đó mới mở rộng dataset và chart family.

Ngưỡng chất lượng cụ thể cần khóa từ baseline hiện có và ground truth có người kiểm. Báo cáo này không gán một tỷ lệ đạt tùy ý. Paid release cần ceiling theo repository; không chạy trong lượt phân tích.

## Nguồn và câu hỏi còn mở

- [Roadmap](../../docs/roadmap.md)
- [Signal Desk plan](../260905-0001-signal-desk-visual-harness/plan.md)
- [Graduation report](../260905-0001-signal-desk-visual-harness/reports/graduation-report.md)
- [Hermes README](https://github.com/NousResearch/hermes-agent)
- [OpenCode README](https://github.com/anomalyco/opencode)
- [Deep Agents README](https://github.com/langchain-ai/deepagents)
- [Flint README và library contract](https://github.com/microsoft/flint-chart)

Cần khóa khi chuyển sang delivery: job ưu tiên đầu tiên; internal hay sản phẩm cho khách hàng; quyền/budget nguồn dữ liệu; ngân sách baseline; ai kiểm ground truth tài chính. Chưa có live trace từ một prompt bị kẹt nên không khẳng định một phát hiện source nào là nguyên nhân duy nhất của trải nghiệm được mô tả.
