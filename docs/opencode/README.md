# OpenCode — hồ sơ kiến trúc agent

Hồ sơ này mổ OpenCode như một **agent harness**, không chỉ như một CLI. Nó trả
lời bốn câu hỏi: runtime được chia lớp ra sao, một tool call đi qua những bước
nào, subagent và context được cô lập đến đâu, và phần nào đáng học cho
Stock_Massive.

Khảo sát source được cố định tại nhánh `dev`, commit
[`3a31c4e`](https://github.com/anomalyco/opencode/tree/3a31c4ea801915c0b050df4b3842997ea62b6e93),
ngày August 22, 2026. Release gần nhất là
[`v1.18.21`](https://github.com/anomalyco/opencode/releases/tag/v1.18.21), trỏ
tới commit cũ hơn `57fa34f`. Các tính năng gắn cờ `experimental` hoặc chỉ có
trên `dev` được ghi rõ; không được đọc chúng như hợp đồng release ổn định.

## Kết luận ngắn

OpenCode mạnh nhất không phải ở một thuật toán agent mới. Giá trị của nó nằm ở
cách biến vòng lặp model–tool thành một sản phẩm có nhiều client, nhiều provider,
permission có thể cấu hình, session bền, event stream, compaction, plugin hook,
và child session cho subagent.

Năm kết luận quan trọng nhất là:

- **Server là lõi, TUI chỉ là client.** Cùng một OpenAPI contract phục vụ TUI,
  IDE, SDK, web, và automation; đây là boundary sản phẩm tốt hơn việc nhúng agent
  loop trực tiếp vào giao diện. Xem [tài liệu server chính thức](https://opencode.ai/docs/server/).
- **Session là state machine bền, không phải một hàm `while`.** Message, part,
  tool state, snapshot, usage, error, và child session đều được ghi thành dữ
  liệu có định danh. Vòng lặp chỉ điều phối các state đó.
- **Hai thế hệ runtime đang cùng tồn tại.** `SessionPrompt` V1 vẫn là đường chạy
  đầy đủ; `SessionRunner` V2 đang chuyển sang durable event log, projector, và
  serialized drain nhưng chưa parity tool/MCP/retry/cancellation. Không được
  mô tả V2 như kiến trúc đã phát hành hoàn tất.
- **Tool runtime có một đường vào chung.** Built-in, custom tool, MCP tool, và
  resource tool đều đi qua schema transform, permission, lifecycle hook, abort,
  metadata, và output handling trước khi quay về model.
- **Subagent là child session có context riêng.** Parent nhận kết quả cuối, còn
  lịch sử và tool trace nằm trong child; permission `deny` và
  `external_directory` của session cha được truyền xuống, nhưng quyền của agent
  cha không mặc nhiên trở thành quyền của agent con.
- **Không có một “SOTA winner” tuyệt đối.** OpenCode rất mạnh về openness,
  provider portability, extension, và client/server ergonomics; OpenHands mạnh
  hơn về sandbox runtime; Claude Code có steering surface trưởng thành; Codex
  có sandbox/approval posture chặt hơn; SWE-agent chứng minh ACI phải được đo
  bằng benchmark. Xem [đối chiếu SOTA](opencode-sota-comparison.md).

## Đọc theo thứ tự này

| # | Tài liệu | Câu hỏi chính |
|---|---|---|
| 1 | [Kiến trúc hệ thống](opencode-architecture.md) | Boundary giữa client, server, session, provider, tool, và storage là gì? |
| 2 | [Agent loop và tool call](opencode-agent-loop-and-tools.md) | Một turn chạy, retry, compact, và dừng như thế nào? |
| 3 | [Context, rules, và compaction](opencode-context-and-rules.md) | OpenCode dựng context, nạp `AGENTS.md`, và chống context overflow ra sao? |
| 4 | [Subagent và orchestration](opencode-subagents-and-orchestration.md) | Child session, permission inheritance, foreground/background task hoạt động thế nào? |
| 5 | [Đối chiếu SOTA](opencode-sota-comparison.md) | OpenCode hơn, kém, hoặc khác các harness hàng đầu ở đâu? |
| 6 | [Bài học cho Stock_Massive](opencode-lessons-for-stock-massive.md) | Cái gì nên lấy, cái gì nên từ chối, và đo bằng gì? |
| 7 | [Ghi chép nguồn chính](research-260823-opencode-primary-sources.md) | Claim-level evidence, source path, và vùng chưa chắc chắn |

## Cách đọc mức độ chắc chắn

Mỗi tài liệu dùng ba nhãn:

- **Đã kiểm chứng:** hành vi thấy trực tiếp trong source cố định hoặc official
  docs.
- **Suy luận:** kết luận kiến trúc rút ra từ nhiều owner; có thể đúng nhưng không
  phải tuyên bố của dự án.
- **Khuyến nghị:** quyết định dành cho Stock_Massive, không phải mô tả OpenCode.

Không dùng star, marketing claim, hoặc bảng xếp hạng model làm bằng chứng kiến
trúc. “SOTA” trong hồ sơ này là tập các practice có bằng chứng về safety,
reliability, observability, context efficiency, và task performance.

## Cập nhật hồ sơ

Khi OpenCode đổi phiên bản, đừng sửa số liệu bằng trí nhớ. Clone commit mới rồi
đối chiếu các owner sau: `session/prompt.ts`, `session/processor.ts`,
`session/tools.ts`, `session/compaction.ts`, `tool/task.ts`, `agent/agent.ts`,
`permission/index.ts`, và `session/instruction.ts`. Chỉ đổi kết luận nếu source
hoặc test thêm bằng chứng mới.
