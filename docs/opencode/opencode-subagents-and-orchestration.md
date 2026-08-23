# OpenCode — subagent và orchestration

OpenCode mô hình hóa subagent như một agent profile chạy trong child session.
`task` là tool tạo hoặc resume child, gửi prompt, chờ kết quả hoặc đưa job xuống
background, rồi trả một kết quả đã đóng gói về parent. Đây là context isolation
bằng session lineage, không phải nhiều agent chia sẻ một transcript.

## Agent profile

Mỗi agent có tên, description, mode (`primary`, `subagent`, hoặc `all`), model
tùy chọn, prompt, permission rules, step cap, và model options. Built-in profiles
gồm `build`, `plan`, `general`, `explore`, cùng các hidden agents cho compaction,
title, và summary. Xem [Agents](https://opencode.ai/docs/agents/) và
[`agent/agent.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/agent/agent.ts).

Điểm thiết kế tốt là agent profile không phải class runtime riêng. Nó là policy
và prompt bundle đi vào cùng session loop. Vì vậy primary và subagent dùng chung
protocol repair, tool state, provider adapter, compaction, và event model.

## Vòng đời `task`

Source owner là
[`tool/task.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/tool/task.ts).

1. Kiểm tra depth từ parent lineage; mặc định chỉ một cấp nếu config không đổi.
2. Permission-gate loại subagent được gọi.
3. Resolve profile và model; nếu không có model riêng, kế thừa model/variant của
   assistant đang gọi.
4. Resume `task_id` cũ hoặc tạo child session có `parentID`.
5. Dẫn xuất session permission cho child.
6. Resolve prompt parts rồi chạy chính `SessionPrompt.prompt()` trên child.
7. Lấy text part cuối làm task result, hoặc surface typed failure.
8. Foreground chờ result; background trả job metadata và sau đó inject synthetic
   result vào parent.

Task prompt chính thức còn dặn model không dùng subagent cho một file hoặc một
symbol đơn giản, giao scope rõ, không làm trùng phần đã giao, và dùng task ID để
resume context. Xem
[`tool/task.txt`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/tool/task.txt).

## Context isolation

Child session nhận prompt chi tiết và tự dựng system/context/tool surface. Parent
không tự động copy toàn bộ transcript vào child. Khi child hoàn tất, parent nhận
kết quả cuối qua tool result; full child transcript vẫn truy cập được bằng
session navigation/API. Đây là isolation tốt cho context cost và debugging.

Best practice đi kèm:

- prompt delegate phải tự đủ bối cảnh;
- scope file và acceptance criteria phải rõ;
- final result cần cô đọng vì đó là payload quay về parent;
- task liên quan cần resume cùng child thay vì mở context mới;
- parent không duplicate work trong lúc child chạy;
- UI phải hiển thị lineage và permission request của child.

## Permission inheritance có chủ ý

`deriveSubagentSessionPermission()` truyền xuống:

- mọi parent **session deny rule**;
- mọi `external_directory` rule;
- mặc định deny `todowrite` và nested `task` nếu profile con không tự khai quyền.

Nó không truyền toàn bộ permission của parent agent. Comment trong source nói rõ
parent agent restrictions chỉ quản agent cha; capability của child do profile
child quyết định. Owner là
[`agent/subagent-permissions.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/agent/subagent-permissions.ts).

Đây là một trade-off hợp lý nhưng dễ cấu hình sai:

- Nếu child profile rộng, một plan agent hẹp vẫn có thể giao việc mạnh hơn, trừ
  các deny được propagate.
- Nếu tổ chức muốn capability không bao giờ tăng qua delegation, phải express
  restriction dưới dạng session deny, không chỉ agent-local rule.
- `external_directory` luôn truyền xuống vì child không được dùng delegation để
  thoát worktree boundary.

**Threat model:** delegation phải monotonic với explicit deny. Đó là invariant
an toàn thực, còn việc child được có quyền riêng rộng hơn là product choice.

## Foreground và background

Foreground task chờ child và có thể được “promote” sang background. Abort parent
foreground task sẽ cancel child/job. Background task chạy qua `BackgroundJob`,
trả ngay job metadata, rồi khi xong inject một synthetic message vào parent và
khởi động parent loop tiếp. Source owner là
[`tool/task.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/tool/task.ts)
và
[`background/job.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/background/job.ts).

Tại snapshot này, background subagent bị gate bởi
`OPENCODE_EXPERIMENTAL_BACKGROUND_SUBAGENTS=true`. Vì vậy:

- không coi schema `background` là ổn định;
- client phải xử lý job completion đến sau turn hiện tại;
- parent transcript phải đánh dấu synthetic message để không nhầm là user input;
- file ownership phải không overlap vì child và parent cùng worktree.

## Orchestration là model-driven, không phải scheduler DAG

OpenCode cung cấp primitives: description-based routing, `task`, child session,
depth cap, background job, result injection, và session navigation. Nó không cung
cấp một planner DAG có dependency graph, file lock, merge coordinator, consensus,
hay transaction across agents.

**Suy luận:** đây là lựa chọn KISS đúng cho coding CLI. Model tự quyết định khi
delegate; runtime chỉ enforce depth, permission, lifecycle, và visibility. Nhưng
nó không đủ cho multi-tenant hoặc high-contention automation nếu không thêm:

- ownership/lease trên file hoặc worktree;
- budget per child và tổng budget per root;
- cancellation propagation đã kiểm thử;
- child event projection đầy đủ trên mọi client;
- deterministic join policy khi nhiều child cùng hoàn thành;
- evaluation cho delegation benefit versus overhead.

## Khi nào dùng subagent

### Nên dùng

- khảo cứu nguồn ngoài độc lập với implementation;
- scan codebase rộng có output cô đọng;
- các workstream không chạm cùng file;
- specialist có permission/model/prompt khác rõ rệt;
- task có thể xác minh riêng trước khi trả kết quả.

### Không nên dùng

- đọc một file, tìm một symbol, hoặc chạy một command ngắn;
- task cần state nội bộ chưa được ghi vào prompt;
- parent phải kiểm tra lại toàn bộ output, làm mất lợi ích context;
- nhiều agent sửa chung shared config hoặc migration sequence;
- latency/cost của child lớn hơn số turn tiết kiệm được.

## Thước đo orchestration

Một harness không trở thành SOTA vì spawn được nhiều agent. Cần đo:

- success rate cùng task với và không delegation;
- wall-clock, token, và provider cost;
- tỷ lệ child result bị parent làm lại;
- conflict/revert rate trên workspace;
- permission escalation incidents;
- orphan job và cancellation latency;
- context reduction của parent;
- số clarification turn do delegate thiếu context.

Không có các số đó, “parallel” chỉ là capability, chưa phải performance claim.
