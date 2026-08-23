# OpenCode — context, rules, skills, và compaction

OpenCode dựng context từ nhiều nguồn có vòng đời khác nhau: prompt theo model,
environment, project/global instructions, nested directory rules, MCP
instructions, skill catalog, transcript, file attachments, và compaction
summary. Điểm đáng học là nạp context theo scope và thời điểm, không phải nhét
mọi thứ vào một system prompt cố định.

## Các tầng context

| Tầng | Khi nạp | Owner |
|---|---|---|
| Model harness prompt | Mỗi model call, chọn theo model family | [`session/system.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/system.ts) |
| Environment | Mỗi step | [`session/system.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/system.ts) |
| Global và project rules | Mỗi step | [`session/instruction.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/instruction.ts) |
| Nested directory rules | Khi `read` chạm file trong subtree | [`tool/read.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/tool/read.ts) |
| Remote/custom instructions | Mỗi step, fetch có timeout | [`session/instruction.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/instruction.ts) |
| MCP instructions | Khi server và permission cho phép | [`session/system.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/system.ts) |
| Skill catalog/body | Catalog trong system; body khi gọi `skill` | [Skills](https://opencode.ai/docs/skills/) |
| Conversation | Mỗi step, đã lọc compacted history | [`message-v2.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/message-v2.ts) |

## `AGENTS.md` không chỉ có một cấp

Official rules docs định nghĩa project `AGENTS.md`, global
`~/.config/opencode/AGENTS.md`, fallback `CLAUDE.md`, config `instructions`, và
remote URL. File đầu tiên khớp trong từng category thắng; custom instructions
được hợp nhất thêm. Xem [Rules](https://opencode.ai/docs/rules/).

Source bổ sung một behavior quan trọng: khi tool `read` mở file, instruction
service đi ngược từ thư mục file lên worktree root, tìm instruction file gần đó,
và gắn nội dung chưa được nạp vào tool result trong `<system-reminder>`. Metadata
`loaded` ngăn cùng file bị gắn lặp trong transcript. Đây là lazy hierarchical
context; owner là
[`session/instruction.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/instruction.ts)
và
[`tool/read.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/tool/read.ts).

### Ưu điểm

- Monorepo không phải trả token cho mọi package rule ngay từ đầu.
- Agent nhận instruction gần code đúng lúc nó đọc code.
- Metadata bền cho biết instruction nào đã vào context.
- Global preference và project contract vẫn có mặt ngay từ system assembly.

### Rủi ro

- Một repository không tin cậy có thể chứa `AGENTS.md` mang instruction độc hại.
  Đây là prompt trust boundary, không phải text trung tính.
- Remote instructions là content thay đổi ngoài commit của repo; pin URL hoặc
  commit nếu dùng cho rule bắt buộc.
- Instruction fetch fail trả rỗng để không chặn turn. Availability cao hơn,
  nhưng policy quan trọng có thể biến mất im lặng nếu chỉ đặt ở URL.
- Nested rule chỉ được khám phá qua đường `read`; một tool khác truy cập file mà
  không đi qua read contract có thể không kích hoạt cùng rule.

**Khuyến nghị:** rule ảnh hưởng safety hoặc public contract phải ở file versioned
trong repo. Remote instructions chỉ nên bổ sung knowledge không quyết định quyền.

## Skill dùng progressive disclosure

Agent system prompt nhận danh mục skill ngắn. Body `SKILL.md` chỉ đi vào
conversation sau khi model gọi tool `skill`; tool được permission gate như mọi
capability khác. Điều này giảm prompt cố định và để permission profile từ chối
skill khi cần. Official owner là [Skills](https://opencode.ai/docs/skills/) và
source owner là
[`skill/index.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/skill/index.ts).

Best practice ở đây là tách:

- **catalog:** tên, mô tả, trigger;
- **instruction body:** nạp khi task cần;
- **artifact/tool:** thực thi qua capability plane;
- **permission:** quyết định agent có được nạp hoặc chạy hay không.

Nếu catalog mô tả mơ hồ, model không gọi skill; nếu body nạp sẵn hết, context
phình. Chất lượng description vì vậy là một phần của routing performance.

## Compaction gồm ba quyết định khác nhau

OpenCode không dùng một thao tác “summarize everything”.

### Chọn head và recent tail

Compaction chọn vùng history cũ để tóm tắt nhưng giữ recent turns theo token
budget. Nó có thể split một turn lớn để giữ phần tail vừa budget. Prior compaction
summary được truyền vào lần sau thay vì xếp chồng toàn bộ summary cũ. Owner là
[`session/compaction.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/compaction.ts).

### Prune tool output xác định

Sau turn, prune đi ngược transcript, bảo vệ recent tool output và tool `skill`,
rồi đánh dấu output cũ là compacted khi lượng tiết kiệm vượt ngưỡng. Durable
part còn nguyên metadata/call identity; model không nhận lại body đã dọn.

### LLM summary và auto-continue

Hidden `compaction` agent không có tool, nhận history đã serialize và tạo
summary. Nếu compaction do overflow giữa một request, OpenCode có thể replay
user turn hoặc chèn synthetic continue message. Plugin hook có thể thay prompt,
thêm context, hoặc tắt auto-continue.

**Suy luận:** tách selection, deterministic prune, và LLM summary là đúng hướng
SOTA. Nó giúp lossless cleanup chạy trước lossy summarization và giữ owner của
mỗi policy rõ.

## Context overflow không phải retry

Processor phân biệt context overflow với transient provider error. Overflow đặt
`needsCompaction`; loop tạo compaction task rồi tiếp tục. Nếu user tắt automatic
compaction, error được surface thay vì lén xóa history. Xem
[`session/processor.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/processor.ts)
và
[`session/retry.ts`](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/retry.ts).

Đây là invariant quan trọng: **retry chỉ hợp lý khi input không đổi có cơ hội
thành công**. Overflow cần thay input; output-cap cần thay output reserve; rate
limit cần chờ; auth failure cần credential action.

## Prompt caching và drift

OpenCode có provider-specific transform và cache options, nhưng snapshot này
không chứng minh một chiến lược stable/context/volatile prefix tổng quát được
enforce ở session assembler. Vì vậy không nên tuyên bố OpenCode có prompt-cache
architecture tối ưu chỉ từ việc provider layer hỗ trợ cache metadata.

Muốn đánh giá cache SOTA cần đo ít nhất:

- cache read/write tokens theo turn;
- system prefix churn;
- tool schema churn;
- cost sau compaction;
- tác động của agent switch và child session.

Không có số đo đó thì “cache-friendly” chỉ là giả thuyết.
