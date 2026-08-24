# Investment Intelligence Harness — Source of Truth

Thư mục này là authority cho contract và kiến trúc AI của Stock_Massive. Nó
định nghĩa sản phẩm phải trở thành loại intelligence system nào và harness phải
giữ những invariant nào. Thứ tự tiến hóa nằm ở
[`docs/harness-roadmap.md`](../harness-roadmap.md), tách khỏi delivery của data
platform trong [`docs/system-roadmap.md`](../system-roadmap.md). Code và test vẫn
là authority cho hành vi đang chạy.

## Tuyên bố sản phẩm

Stock_Massive là một **Investment Intelligence system có AI làm core**, không
phải dashboard gắn thêm chatbot. AI là runtime chính để hiểu ý định, lập kế
hoạch nghiên cứu, chọn capability, kết hợp bằng chứng, kiểm tra mâu thuẫn, tạo
kịch bản và giải thích quyết định. Dữ liệu, phép tính, policy và audit trail là
các module xác định bao quanh model để năng lực tăng mà độ tin cậy không giảm.

Mục tiêu không phải cho model quyền tùy ý. “Bung toàn bộ khả năng AI” nghĩa là
mở rộng có đo lường về perception, reasoning, memory, simulation, delegation,
personalization và proactive intelligence. Quyền tạo side effect tài chính
không tự phát sinh từ năng lực suy luận.

## Authority và cách xử lý xung đột

Các nguồn có vai trò khác nhau. Khi nội dung xung đột, dùng thứ tự authority
dưới đây thay vì chọn tài liệu mới nhất theo ngày.

1. Luật thị trường, policy bảo mật và quyết định người dùng sở hữu giới hạn
   không được vượt.
2. SOT này sở hữu product contract, target architecture và graduation gates.
3. Source, schema và test sở hữu hành vi hiện tại.
4. Plan sở hữu cách triển khai một thay đổi đã được chấp nhận.
5. Research Hermes/OpenCode và các report sở hữu evidence lịch sử, không sở
   hữu kiến trúc của Stock_Massive.

Nếu code chưa đạt target trong SOT, đó là roadmap gap, không phải lý do mô tả
code như thể target đã tồn tại. Nếu code thay đổi contract đã được chấp nhận,
thay đổi phải cập nhật SOT hoặc ghi rõ vì sao contract cũ bị thay thế.

## Trạng thái quyết định

Mọi capability trong bộ tài liệu dùng một trong bốn trạng thái sau. Trạng thái
ngăn ý tưởng dài hạn bị hiểu nhầm thành behavior đã phát hành.

| Trạng thái | Ý nghĩa |
|---|---|
| **Current** | Có executable owner và test hoặc trace chứng minh |
| **Target** | Kiến trúc đã chọn, cần plan và implementation để đạt |
| **Conditional** | Chỉ mở khi graduation gate ghi trong roadmap đạt |
| **Rejected** | Không phù hợp product/threat model hiện tại; muốn đảo phải có evidence mới |

## Đọc theo thứ tự

Bộ SOT được chia theo câu hỏi mà một maintainer hoặc coding agent cần trả lời.

| # | Tài liệu | Quyết định mà tài liệu sở hữu |
|---|---|---|
| 1 | [Investment Intelligence contract](investment-intelligence-contract.md) | AI tồn tại để làm gì, truth model là gì và quyền dừng ở đâu |
| 2 | [Target architecture](target-architecture.md) | Các deep module, interface, turn lifecycle và dependency direction |
| 3 | [Quality, safety and operations](quality-safety-and-operations.md) | Cách chứng minh correctness, quality, reliability, security và cost |
| 4 | [Harness roadmap](../harness-roadmap.md) | Thứ tự mở AI capability, dependency và graduation gate |
| 5 | [System roadmap](../system-roadmap.md) | Thứ tự xây data platform, DNSE realtime, product surface và vận hành |

## Nguồn evidence

Hai hồ sơ harness là nền so sánh chính. Tài liệu domain và source hiện tại được
dùng để biến best practice tổng quát thành kiến trúc tài chính riêng.

- [Hermes architecture and SOTA research](../hermes/research-260823-1649-hermes-agent-architecture-sota.md)
  cung cấp recovery taxonomy, tool runtime, context/cache, guardrail,
  delegation và operational lessons.
- [Hermes synthesis](../hermes/hermes-synthesis-260821-0030.md) ghi các bài học
  đã đối chiếu với Stock_Massive.
- [OpenCode primary-source research](../opencode/research-260823-opencode-primary-sources.md)
  cung cấp session state, capability resolution, provider seam, context và
  child-session model.
- [OpenCode lessons for Stock_Massive](../opencode/opencode-lessons-for-stock-massive.md)
  ghi phần nên học, phần đã làm tốt và phần không nên port.
- [Quant methods for Vietnamese EOD equities](../research/quant-methods-eod-vn.md)
  sở hữu các ràng buộc microstructure và statistical honesty đã nghiên cứu.

## Vận hành measurement authority

Các target `eval-*` trong [`apps/api/Makefile`](../../apps/api/Makefile) là
entry point ổn định cho validation, offline smoke, paid run, comparison và
release gate. CLI thực thi nằm tại
[`src/eval/cli.py`](../../apps/api/src/eval/cli.py); JSON artifact là authority,
còn Markdown chỉ là projection có thể tạo lại từ JSON.

Repository policy nằm tại
[`eval/gate-policy.json`](../../apps/api/eval/gate-policy.json). Trạng thái
baseline được fail closed bởi
[`investment-intelligence-v1.json`](../../apps/api/eval/baselines/investment-intelligence-v1.json):
Stage 0 đã tốt nghiệp với paid distribution được owner review và artifact
digest `36bc44f7c00966cd`; các gate sau tiếp tục fail closed nếu identity này hoặc
repository-owned policy không tương thích.

## Quy tắc bảo trì

SOT phải ngắn hơn implementation và bền hơn tên helper. Khi cập nhật, trỏ đến
executable owner thay vì sao chép code hoặc danh sách tool đang biến động.

- Cập nhật product contract chỉ khi mục tiêu, quyền hoặc domain invariant đổi.
- Cập nhật architecture khi seam hoặc dependency direction đổi.
- Cập nhật `docs/harness-roadmap.md` khi AI capability tốt nghiệp, bị từ chối
  hoặc dependency đổi; cập nhật `docs/system-roadmap.md` khi data/system phase
  đổi trạng thái.
- Cập nhật quality gates trước khi mở một lớp autonomy mới.
- Không đưa benchmark result, incident log hoặc phase report vào authority
  evergreen; link đến artifact sở hữu chúng.

## Câu hỏi chưa giải quyết

Các quyết định sau cần product evidence hoặc lựa chọn rõ của người dùng trước
khi trở thành target.

- Stock_Massive có bao giờ gửi lệnh tới broker, hay vĩnh viễn dừng ở decision
  support và user-approved export?
- Portfolio context sẽ chỉ do người dùng nhập, hay được đồng bộ từ broker?
- Proactive intelligence được phép gửi notification theo trigger nào và với
  quota nào?
- Mức giải thích tối thiểu khác nhau thế nào giữa nhà đầu tư mới và người dùng
  chuyên nghiệp?
