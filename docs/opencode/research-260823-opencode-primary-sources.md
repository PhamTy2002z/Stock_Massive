# OpenCode — khảo sát kiến trúc agent từ nguồn sơ cấp

Tài liệu này mổ OpenCode như một agent harness, không đánh giá trải nghiệm sản
phẩm. Trọng tâm là vòng lặp runtime, vòng đời tool call, context, permission,
session, subagent, MCP/LSP, compaction, provider abstraction, và độ tin cậy.
Mỗi kết luận mang một trong ba nhãn: **Sự kiện** (docs/source nói hoặc thực thi),
**Suy luận** (kết luận từ bằng chứng), hoặc **Khuyến nghị** (cho Stock_Massive).

Snapshot chính là nhánh `dev` tại commit
[`3a31c4ea801915c0b050df4b3842997ea62b6e93`](https://github.com/anomalyco/opencode/commit/3a31c4ea801915c0b050df4b3842997ea62b6e93),
ngày 2026-08-22. Release gần nhất lúc đọc là
[`v1.18.21`](https://github.com/anomalyco/opencode/releases/tag/v1.18.21),
ngày 2026-08-21, với GitHub `target_commitish` là
[`57fa34f`](https://github.com/anomalyco/opencode/commit/57fa34f23599f65dd1027f9caac31e6c576ce644).
Snapshot `dev` mới hơn release và có thể chứa behavior chưa phát hành. Mọi
permalink source khóa vào snapshot trên; nguồn được truy xuất ngày
**2026-08-23**.

> **Cảnh báo phiên bản:** OpenCode đang chuyển từ `SessionPrompt` V1 sang
> `SessionRunner` V2 dạng event-sourced. Source V2 tự liệt kê nhiều mục chưa
> hoàn tất. Tài liệu mô tả hai đường riêng, không suy diễn V2 đã thay V1.

## Kết luận ngắn

OpenCode có lõi agent hợp lý: model điều khiển vòng lặp, tool call có state rõ,
tool chạy đồng thời, provider được chuẩn hóa thành event stream, context được
compact, và subagent là child session có permission riêng. V1 vận hành đủ vòng;
V2 đang tái cấu trúc thành durable event log + projection + runner nhỏ hơn.
[V1](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/prompt.ts#L1081-L1339),
[V2 và checklist còn thiếu](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/core/src/session/runner/llm.ts#L43-L90).
**Nhãn: Sự kiện.**

Điểm mạnh nhất để học là contract vòng đời: ghi tool call trước side effect,
settle mọi call thành success/failure, đánh dấu call bị ngắt, serialize một drain
trên mỗi session, và giữ provider logic sau seam chuẩn hóa. Điểm yếu lớn nhất là
security boundary: permission chỉ quyết định `allow | ask | deny`; shell vẫn là
process của host, và prompt Kimi nói runtime “is not in a sandbox.”
[Permission](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/permission/index.ts#L28-L167),
[shell spawn](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/tool/shell.ts#L293-L306),
[prompt](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/prompt/kimi.txt#L54-L63).
**Nhãn: Sự kiện + Suy luận.**

Với Stock_Massive, không nên port khung coding agent, shell, LSP, file tools, hay
subagent tổng quát. Phần đáng học có chọn lọc là state machine tool call, một
owner/coalesced wake cho Turn nếu sau này chạy queue nhiều worker, event taxonomy
có thể replay, provider seam, và eval outcome-first. **Nhãn: Khuyến nghị.**

## 1. Phạm vi và phương pháp

Nghiên cứu chỉ dùng nguồn do chủ thể sở hữu:

- tài liệu chính thức tại `opencode.ai/docs` và MDX trong repo;
- source, commit, release, và issue/PR của `anomalyco/opencode`;
- đặc tả MCP chính thức;
- tài liệu chính thức OpenAI/Anthropic về agent loop, sandbox, tracing, context,
  guardrails, và eval;
- source hiện tại của Stock_Massive để rút tác động nội bộ.

Không dùng bài tổng hợp hay benchmark do bên thứ ba diễn giải. “SOTA” ở đây là
tập thực hành tốt nhất có bằng chứng chính chủ, không phải xếp hạng sản phẩm.

## 2. Hai thế hệ runtime cùng tồn tại

**Sự kiện — V1.** `session/prompt.ts` giữ loop cấp session; `processor.ts` chuẩn
hóa stream thành message parts; `llm.ts` chuẩn bị request và chọn runtime;
`tools.ts` materialize built-in/MCP tools; `session.ts` lưu session/message/part.
Application runtime vẫn đăng ký `SessionPrompt.node`.
[Loop](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/prompt.ts#L1081-L1339),
[processor](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/processor.ts#L627-L692),
[wiring](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/effect/app-runtime.ts#L70-L100).

**Sự kiện — V2.** `core/session/runner/llm.ts` orchestration trên durable
`SessionEvent`; `SessionProjector` chiếu event thành bảng đọc;
`SessionRunCoordinator` serialize theo session. V2 đã ghi tool call trước effect
và persist kết quả typed, nhưng source còn đánh dấu chưa xong durable multi-node
ownership/status, bounded retries/repeated calls, MCP/plugin tools, cancellation
settlement, và post-run maintenance.
[Checklist](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/core/src/session/runner/llm.ts#L43-L90),
[projector](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/core/src/session/projector.ts#L111-L208),
[coordinator](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/core/src/session/run-coordinator.ts#L5-L104).

**Suy luận.** V2 là hướng tốt hơn cho recovery/replay, nhưng chưa phải durable
distributed runtime hoàn tất. TODO trong source là uncertainty, không phải
roadmap đã cam kết.

| Concern | V1 | V2 / hướng mới | Trạng thái |
|---|---|---|---|
| Session loop | `session/prompt.ts` | `core/session/runner/llm.ts` | V1 đủ; V2 chuyển tiếp |
| Stream | `session/processor.ts` | `publish-llm-event.ts` | Có ở cả hai |
| LLM | `session/llm.ts` | `@opencode-ai/llm` | AI SDK mặc định; native opt-in |
| Tools | `session/tools.ts` | `core/tool/registry` | V2 chưa parity MCP/plugin |
| State | tables + events | event log + projector | V2 rõ hơn |
| Permission | `permission/index.ts` | `PermissionV2` | Policy, không phải sandbox |
| Context | system/instruction | context epoch | V2 có baseline epoch |

## 3. Runtime loop và tool-call lifecycle

### 3.1 V1 call-flow

**Sự kiện.** Một Turn đi qua chuỗi sau:

1. Đặt session `busy`, tải history đã lọc phần compact.
2. Thoát nếu assistant trước terminal và không còn tool call hợp lệ.
3. Xử lý `subtask`, rồi `compaction`; tự tạo compaction khi usage overflow.
4. Resolve agent/model, áp reminder, persist assistant message.
5. Resolve tool surface theo agent/session/model/permission.
6. Ghép environment → rules → MCP instructions → skills → history.
7. Stream qua `SessionProcessor`.
8. `stop` thì kết thúc; `compact` thì enqueue; còn lại quay vòng để model đọc
   tool result.

[Bước 1–3](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/prompt.ts#L1081-L1168),
[bước 4–8](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/prompt.ts#L1170-L1335).

Nếu provider báo `stop` nhưng message có tool call, loop vẫn tiếp tục để gửi
result về model. Commit gần nhất sửa loại drift này là
[`57fa34f`](https://github.com/anomalyco/opencode/commit/57fa34f23599f65dd1027f9caac31e6c576ce644).
**Nhãn: Sự kiện.**

### 3.2 Tool state và settlement

**Sự kiện.** Processor tạo tool part từ `tool-input-start`; `tool-call` chuyển
sang `running` với input/time; `tool-result` thành `completed`; `tool-error`
thành `error`. Cleanup đợi tối đa 250 ms rồi đánh dấu orphan là
`Tool execution aborted` với `interrupted=true`.
[Transitions](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/processor.ts#L315-L419),
[cleanup](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/processor.ts#L539-L597).

**Sự kiện.** Built-in và MCP tools đi qua `tool.execute.before/after`; tool nhận
session/message/call ID, abort signal, agent, history, metadata callback, và
permission callback. MCP binary bị giới hạn mime/size; text được truncate và có
spill path.
[Built-in wrapper](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/tools.ts#L41-L134),
[MCP wrapper](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/tools.ts#L390-L489).

Ba call liên tiếp có cùng tool name và JSON input kích hoạt `doom_loop`; default
là hỏi người dùng, không tự halt.
[Detector](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/processor.ts#L353-L380),
[default](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/agent/agent.ts#L119-L136).
**Nhãn: Sự kiện.**

**Suy luận.** State machine này quan sát được và không để tool call “mồ côi.”
Nhưng detector cùng-input không phát hiện no-progress khi model đổi nhẹ input
hoặc luân phiên tools.

### 3.3 V2 durable turn

**Sự kiện.** V2 tải projection, chuẩn bị baseline, resolve model/tools, dựng
`LLMRequest`, và kiểm compact trước provider. Mỗi `tool-call` được persist trước;
settlement chạy trong `FiberSet`; runner chờ hết trước continuation. Semaphore
serialize publication dù tools chạy song song.
[Request](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/core/src/session/runner/llm.ts#L168-L237),
[settlement](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/core/src/session/runner/llm.ts#L238-L355).

`SessionRunCoordinator` có một owner local trên mỗi session; call mới join owner
hiện tại, nhiều wake coalesce thành một follow-up; session khác vẫn song song.
[Contract và code](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/core/src/session/run-coordinator.ts#L5-L104).
**Nhãn: Sự kiện.**

**Suy luận.** Persist-intent-before-effect + projection + one-drain là nền đúng.
Nó chưa chứng minh exactly-once side effect sau crash; cần idempotency/reconcile
riêng, và source xác nhận distributed ownership còn TODO.

## 4. Prompt, context, rules, và cache

### 4.1 Prompt assembly

**Sự kiện.** Template được chọn theo model/API ID (GPT/Codex, Anthropic,
Gemini, Kimi, Meta, Trinity, hoặc default). OpenCode thêm exact model ID,
working directory, root, git/platform/date, references, skill index, và MCP
instructions còn visible theo permission.
[Routing](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/system.ts#L27-L49),
[assembly](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/system.ts#L67-L135).

**Suy luận.** Model-specific prompts tăng compatibility nhưng tạo matrix dễ
drift: cùng agent config không đồng nghĩa cùng instruction semantics.

### 4.2 Rules

**Sự kiện.** OpenCode đọc tối đa một global convention file và convention đầu
tiên tìm thấy ở project: `AGENTS.md`, rồi `CLAUDE.md`, rồi `CONTEXT.md`
deprecated. `config.instructions` nhận glob local hoặc URL; local đọc concurrency
8, remote 4, timeout 5 giây; nội dung được đưa nguyên dạng `Instructions from:`
vào system context.
[Rules docs](https://opencode.ai/docs/rules/),
[source](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/instruction.ts#L55-L168).

Khi `read` mở file trong subdirectory, resolver đi ngược về workspace root và
attach nearby instruction chưa claim trong assistant message: lazy,
path-sensitive context.
[Resolver](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/instruction.ts#L171-L220).
**Nhãn: Sự kiện.**

**Suy luận — rủi ro.** Remote instruction được chèn thẳng vào system context;
module không scan prompt injection hay pin hash. Timeout/retry chỉ bảo vệ
transport. Không nên port vào Stock_Massive.

### 4.3 Cache

**Sự kiện.** V2 dùng session ID làm `openai.promptCacheKey`, đồng thời gửi
session-affinity và parent-session headers.
[Source](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/core/src/session/runner/llm.ts#L197-L221).

**Suy luận.** Session key là hint, không chứng minh prefix ổn định. V1 ghép date,
rules, MCP instructions, skills, và provider prompt; không thấy metric hit-rate.

## 5. Permission và safety boundary

### 5.1 Semantics

**Sự kiện.** Rule có `permission`, `pattern`, `action`; match cuối thắng. Không
match thì `ask`; `deny` throw; `ask` publish event và chờ; reply là `reject`,
`once`, hoặc `always`. Approval `always` sống trong runtime state hiện tại.
[Docs](https://opencode.ai/docs/permissions/),
[engine](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/permission/index.ts#L28-L167).

Default agent rule là `* = allow`, `doom_loop = ask`, path ngoài workspace =
ask, và nhạy cảm hơn cho dotenv files. `plan` deny edit nhưng source không deny
bash riêng; trang Agents lại nói Plan hỏi cho mọi bash/file edit.
[Source](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/agent/agent.ts#L119-L180),
[docs](https://opencode.ai/docs/agents/).
**Nhãn: Sự kiện; có docs drift.**

Trang Agents liệt kê `Scout`, nhưng snapshot `agent.ts` chỉ dựng `build`, `plan`,
`general`, `explore`, `compaction`, `title`, và `summary`.
[Docs](https://opencode.ai/docs/agents/),
[source](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/agent/agent.ts#L140-L265).
**Nhãn: Sự kiện; có docs drift.**

### 5.2 Permission không phải sandbox

**Sự kiện.** Shell spawn process host với `cwd` và environment; parser cố nhận
path ngoài workspace để hỏi `external_directory`. Execution path không có OS
isolation, và prompt Kimi xác nhận môi trường không sandbox.
[Path scan](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/tool/shell.ts#L358-L415),
[spawn](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/tool/shell.ts#L430-L566),
[prompt](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/prompt/kimi.txt#L54-L63).

**Suy luận.** Parser tĩnh không thể là boundary cho shell tổng quát: script,
interpreter, symlink, subprocess, dynamic path, hoặc network nằm ngoài hình dạng
command. Permission giúp consent/UX, nhưng blast radius vẫn là quyền host.

OpenAI mô tả sandbox là technical boundary cho write/path/network còn approval
quyết định escalation; Anthropic yêu cầu cả filesystem và network isolation,
được OS enforce xuống subprocess.
[OpenAI, 2026-05-08](https://openai.com/index/running-codex-safely/),
[Anthropic, 2025-10-20](https://www.anthropic.com/engineering/claude-code-sandboxing).
**Nhãn: Sự kiện; đây là khoảng cách SOTA lớn nhất.**

## 6. Session và recovery

**Sự kiện.** V1 session chứa project/directory, optional `parentID`, model/agent,
permission, cost/token totals, summary, revert/share metadata, và timestamps.
Message/part persist riêng; API hỗ trợ children, fork, abort, revert, và share.
[Session](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/session.ts#L499-L744),
[server docs](https://opencode.ai/docs/server/).

V1 stream persist text delta, reasoning, tool state, step start/end, usage,
snapshot, và patch; cleanup đóng text/reasoning và orphan tools.
[Events](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/processor.ts#L278-L535),
[cleanup](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/processor.ts#L539-L597).
**Nhãn: Sự kiện.**

**Sự kiện.** V2 durable event mang aggregate sequence; projector dùng sequence
làm order. Nó chỉ resume assistant mới nhất, không row cũ bị supersede. Prompt,
message, tool, text, reasoning, step, compaction, và revert đều có projection.
[Invariant](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/core/src/session/projector.ts#L111-L208),
[registrations](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/core/src/session/projector.ts#L210-L447).

**Suy luận.** Event sourcing tốt cho replay/audit, nhưng không tự cho exactly-once
side effect; tool executor/idempotency vẫn phải có contract.

## 7. Subagent và Task

**Sự kiện.** Agent có `mode: primary | subagent | all`, model, prompt,
temperature/topP, options, step limit, permission. `general` có surface rộng;
`explore` deny-all rồi allow search/read/web/bash; hidden agents deny tools.
[Schema/defaults](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/agent/agent.ts#L35-L55),
[built-ins](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/agent/agent.ts#L140-L265).

`task` kiểm permission theo subagent type, giới hạn depth mặc định `1`, resume
qua `task_id`, tạo child với `parentID`, dùng model riêng hoặc kế thừa caller.
Foreground chờ result; background experimental tự inject synthetic result.
[Task setup](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/tool/task.ts#L92-L224),
[background](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/tool/task.ts#L227-L358).

Child kế thừa parent session deny rules và `external_directory`; capability còn
lại do subagent rules quyết định. `task`/`todowrite` deny mặc định nếu child
không khai rõ.
[Derivation](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/agent/subagent-permissions.ts#L4-L26).
**Nhãn: Sự kiện.**

**Suy luận.** Fresh child session cô lập transcript và lineage tốt. Nhưng child
dùng cùng workspace/host; isolation là context/permission, không phải process.
Parent agent restriction không tự động là child restriction.

## 8. MCP và LSP

### 8.1 MCP

**Sự kiện.** Local MCP dùng stdio; remote thử Streamable HTTP rồi SSE. Kết nối có
timeout và status typed. OAuth giữ pending transport, kiểm state mismatch chống
CSRF, rồi cache definitions/instructions.
[Connect](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/mcp/index.ts#L210-L405),
[OAuth](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/mcp/index.ts#L792-L950).

Chỉ server `connected` đóng góp namespaced tools, resources, templates, prompts,
và instructions; timeout đặt theo server hoặc fallback global.
[Surface](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/mcp/index.ts#L591-L786),
[docs](https://opencode.ai/docs/mcp-servers/).
**Nhãn: Sự kiện.**

MCP spec yêu cầu consent/control quanh arbitrary data/code paths và authorization
least privilege. OpenCode có consent per tool/OAuth, nhưng allow rộng không tự
bảo đảm scope/token isolation hoặc containment.
[MCP 2025-11-25](https://modelcontextprotocol.io/specification/2025-11-25/basic),
[MCP 2026-07 update](https://blog.modelcontextprotocol.io/posts/2026-07-28/).
**Nhãn: Sự kiện + Suy luận.**

### 8.2 LSP

**Sự kiện.** Khi `cfg.lsp` bật, OpenCode match extension/root, lazy spawn server
một lần, cache client, và đánh dấu failed combination. Client hỗ trợ initialize,
didOpen, diagnostics, definition/reference/symbol/call hierarchy. Model-facing
`lsp` tool vẫn experimental.
[Manager](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/lsp/lsp.ts#L140-L375),
[client](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/lsp/client.ts#L200-L511),
[docs](https://opencode.ai/docs/tools/).

**Suy luận.** Đây là augmentation coding-specific có signal cao nhưng process
management/multi-language cost lớn; không có giá trị trực tiếp cho Stock runtime.

## 9. Compaction

**Sự kiện.** Usable input là model input/context limit trừ output reserve;
auto-compaction có thể tắt. Usage chạm threshold thì loop enqueue compaction.
[Math](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/overflow.ts#L8-L33),
[trigger](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/prompt.ts#L1161-L1168).

Compaction chọn head cần summarize và giữ recent tail theo token budget, có thể
split trong một turn. Pruning đi ngược history, bảo vệ recent/special tools, rồi
mark output cũ compacted nếu tiết kiệm đủ.
[Tail](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/compaction.ts#L115-L269),
[prune](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/compaction.ts#L271-L317).

Hidden compaction agent chạy không tools; plugin có thể thay prompt/context. Sau
auto-compaction, loop replay overflow request hoặc inject synthetic continue; nếu
summary cũng overflow thì dừng với error cụ thể.
[Process](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/compaction.ts#L319-L557).
**Nhãn: Sự kiện.**

Anthropic khuyến nghị compaction high-recall, giữ decisions/unresolved bugs, bỏ
redundant tool output, và eval prompt trên trace phức tạp. OpenCode có tail/prune
đúng hướng; source không kèm eval đo mất thông tin.
[Anthropic, 2025-09-29](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents).
**Nhãn: Sự kiện + Suy luận.**

## 10. Provider/model abstraction

**Sự kiện.** Provider service dựng catalog từ Models.dev, merge plugin, config,
environment credentials, stored auth, custom models, và discovery; lọc
enabled/disabled/experimental/deprecated. Model resolution trả
`providerID/modelID`; language model instance được cache.
[Merge](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/provider/provider.ts#L1370-L1698),
[resolution](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/provider/provider.ts#L1707-L1900),
[docs](https://opencode.ai/docs/providers/).

SDK adapter có thể bundled hoặc dynamic-install/import package được catalog chỉ
định; provider loaders xử lý các auth/options đặc biệt.
[Loading](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/provider/provider.ts#L1709-L1839).

AI SDK `streamText` là mặc định. Native `@opencode-ai/llm` opt-in theo request;
unsupported case fallback AI SDK. Cả hai thành cùng `LLMEvent` stream.
[Runtime seam](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/llm.ts#L224-L340),
[boundary note](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/llm/AGENTS.md).
**Nhãn: Sự kiện.**

**Suy luận.** Boundary này tốt: downstream chỉ đọc event contract. Mặt trái là
compatibility matrix lớn; cần contract tests theo provider, không chỉ interface.

## 11. Reliability, observability, safety, và eval

### 11.1 Retry/recovery

**Sự kiện.** V1 retry tối đa 5 lần, initial 2 giây, exponential factor 2, jitter
25%, cap 30 giây khi không header; ưu tiên retry headers. Context overflow không
retry unchanged; 5xx luôn retry; regex bù SDK không đánh dấu retryable.
[Policy](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/retry.ts#L26-L98),
[schedule](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/retry.ts#L183-L207).

Context overflow đi compaction; content-filter thành error thay vì idle im lặng;
invalid tool name được lowercase-repair hoặc route vào synthetic invalid tool;
interrupted tool được settle error.
[Recovery](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/prompt.ts#L1295-L1328),
[repair](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/llm.ts#L280-L323).
**Nhãn: Sự kiện.**

**Suy luận.** Policy thực dụng nhưng retry taxonomy dựa nhiều vào regex và gom
rộng. Stock hiện phân tách sâu hơn các loại overflow, output cap, policy,
schema, model, và deadline trong `apps/api/src/core/llm/errors.py`.

### 11.2 Observability và guardrails

**Sự kiện.** V1 có structured logs, session/tool spans, optional OpenTelemetry
gắn session ID, token/cost, snapshot/patch, và durable parts. OTel là experimental,
không phải trace taxonomy đầy đủ mặc định.
[Telemetry](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/llm.ts#L208-L221),
[tool span](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/tools.ts#L400-L419).

OpenAI Agents SDK trace mặc định `TaskSpan → AgentSpan → TurnSpan` và generation,
tool, guardrail, handoff; cho phép loại sensitive data.
[OpenAI tracing](https://openai.github.io/openai-agents-js/guides/tracing/).
**Nhãn: Sự kiện.**

OpenCode có permission, doom-loop approval, path gate, truncation, MCP limits,
abort settlement, và content-filter surfacing. Không thấy framework tổng quát
cho input/output/per-tool guardrails. OpenAI SDK phân ba boundary này và practical
guide khuyến nghị defense-in-depth cộng auth/access controls.
[OpenAI guardrails](https://openai.github.io/openai-agents-js/guides/guardrails/),
[practical guide](https://openai.com/business/guides-and-resources/a-practical-guide-to-building-ai-agents/).
**Nhãn: Sự kiện + Suy luận.**

### 11.3 Evals

**Sự kiện có giới hạn.** Snapshot có unit/integration/e2e tests và app performance
benchmark, nhưng truy vấn toàn repo không tìm thấy agent eval suite, trajectory
grader, hoặc outcome grader tương ứng. Đây là “không thấy trong public snapshot,”
không chứng minh không có hệ thống nội bộ.

Anthropic định nghĩa agent eval gồm nhiều trial, transcript đầy đủ, outcome cuối
trong environment, và nhiều grader; ưu tiên grade outcome hơn ép trajectory,
deterministic grader khi có thể, và transcript review lâu dài.
[Anthropic, 2026-01-09](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents).
**Nhãn: Sự kiện; đây là khoảng trống bằng chứng lớn.**

## 12. Ma trận SOTA

Ma trận chấm thiết kế quan sát được, không chấm model hay tuyên bố xếp hạng.

| Tiêu chí | Best practice nguồn sơ cấp | OpenCode | Đánh giá |
|---|---|---|---|
| Loop đơn giản | Model + tools + feedback; chỉ tăng complexity khi đo được ([Anthropic](https://www.anthropic.com/engineering/building-effective-agents)) | V1 rõ nhưng monolith; V2 tách | Một phần |
| Tool lifecycle | Record, execute, settle, expose errors | V1 typed state; V2 persist-before-effect | Mạnh |
| Bounded loop | Explicit max turns/steps ([OpenAI](https://openai.github.io/openai-agents-python/running_agents/)) | Agent steps; doom-loop 3; V2 repeated bound TODO | Một phần |
| Durable replay | Durable progress/recovery | V2 event + projector + local drain | Đang xây |
| Provider seam | Stable event/tool contract | AI SDK/native cùng `LLMEvent` | Mạnh, matrix lớn |
| Context curation | JIT load, clearing, high-recall compaction | Lazy rules, tail, prune, summary | Mạnh; thiếu eval loss |
| Prompt provenance | Nguồn/precedence/bounds rõ | `Instructions from`; remote raw | Trung bình |
| Consent | allow/ask/deny, human control | Last-match, once/always/reject | Mạnh |
| Containment | OS filesystem + network sandbox | Host shell + parser/permission | Yếu |
| MCP security | OAuth/scope/consent/no passthrough | 3 transports, OAuth/state, tool gate | Một phần |
| Subagent isolation | Clean context, bounded delegation | Child/depth/permission/resume | Context tốt; process yếu |
| Parallelism | Independent work, joined results | Tool fibers; background experimental | Tốt, nhạy version |
| Traceability | Task/agent/turn/tool/guardrail hierarchy | Logs/spans/events; OTel experimental | Một phần |
| Guardrails | Layered input/output/tool + access control | Nhiều guard cục bộ, không framework chung | Một phần |
| Agent eval | Multi-trial transcript + outcome graders | Không thấy public harness | Khoảng trống |
| Docs/source | Contract cùng version | Plan/bash và Scout lệch | Cần cải thiện |

## 13. Tác động cho Stock_Massive

### 13.1 Nên học

1. **Tool state machine.** Stock đã bảo đảm mỗi call có một result trong
   [`agent/executor.py`](../../apps/api/src/agent/executor.py); nâng
   persistence/event về
   `pending → running → completed | error | interrupted`, với một owner settle
   orphan. Học invariant, không copy Effect/TypeScript.
2. **Single active drain khi có queue thật.** Mẫu join + coalesced wake nhỏ và
   đúng. Chỉ thêm khi nhiều prompt/steer cùng thread hoặc worker restart là yêu
   cầu thật; không dựng distributed event runner trước triệu chứng.
3. **Event taxonomy trước UI telemetry.** Chuẩn hóa `step`, `tool input`,
   `progress`, `result`, `text`, `reasoning`, `retry`, `compaction`, `permission`
   thành contract versioned thay vì callback mới theo feature.
4. **Normalized provider stream.** Stock đã có
   [`core/llm/streaming.py`](../../apps/api/src/core/llm/streaming.py); nếu thêm
   provider, để lowering/auth/headers sau adapter, loop chỉ đọc normalized event.
5. **Outcome-first eval.** Golden Question Set cần nhiều trial, chấm state/evidence
   thật trong store, deterministic grader cho số/citation, model rubric cho diễn
   giải, và transcript review.

### 13.2 Stock hiện tốt hơn ở đâu

**Sự kiện trên worktree ngày 2026-08-23, có user changes chưa commit.** Stock có
`MAX_TOOL_ROUNDS = 4`, final `tool_choice="none"`, parallel tools, one-shot
empty-answer nudge, per-tool external budget, timeout, fail-open trace, guardrail
ladder, typed/stable prompt prefix, và error taxonomy tách overflow/output cap/
policy/schema/model/deadline. Nguồn:
[`loop.py`](../../apps/api/src/agent/loop.py),
[`executor.py`](../../apps/api/src/agent/executor.py),
[`contract.py`](../../apps/api/src/agent/prompt/contract.py), và
[`errors.py`](../../apps/api/src/core/llm/errors.py).

**Suy luận.** Với trợ lý tài chính, typed prompt boundary và tool surface hẹp
của Stock an toàn, đo được, và dễ eval hơn remote raw instructions + shell/file
tools của OpenCode.

### 13.3 Không port

- Host shell, write/edit/patch, LSP, git snapshot, hoặc broad MCP.
- Remote URL instruction chèn thẳng system prompt.
- Default allow hoặc permission parser như security boundary.
- Dynamic provider package installation.
- General subagent trước khi eval chứng minh single-agent là bottleneck.
- Full event sourcing nếu Turn vẫn freeze/không resume và không cần recovery.
- Model-specific prompt matrix nếu route vẫn một model family.

## 14. Uncertainty và version drift

1. V1/V2 coexist; V2 checklist là evidence đang thi công, không là cam kết.
2. `agents.mdx` đổi 2026-05-08, loop đổi 2026-08-21; docs đã lệch source.
3. Snapshot `dev` đi trước release; background subagent/V2 có thể chưa phát hành.
4. “Không thấy eval” và “không thấy sandbox” chỉ áp public paths đã đọc; riêng
   no-sandbox có xác nhận trực tiếp trong prompt và shell path.
5. Adapter source không chứng minh provider semantics giống nhau; cần contract
   tests thực nghiệm.
6. Permission/OAuth có thật nhưng không suy ra scope, token isolation, hoặc
   side-effect containment đều đạt MCP best practice.
7. Không có nguồn công khai định lượng cache hit, compaction loss, tool success,
   hay task completion; tài liệu không bịa số.

## 15. Sổ nguồn

Ngày source là commit gần nhất chạm file; tất cả truy xuất 2026-08-23.

| Nguồn | Cập nhật/xuất bản | Nội dung |
|---|---:|---|
| [OpenCode snapshot](https://github.com/anomalyco/opencode/tree/3a31c4ea801915c0b050df4b3842997ea62b6e93) | 2026-08-22 | Baseline |
| [v1.18.21](https://github.com/anomalyco/opencode/releases/tag/v1.18.21) | 2026-08-21 | Release; target `57fa34f` |
| [Rules](https://opencode.ai/docs/rules/) | source 2026-04-01 | Rules |
| [Agents](https://opencode.ai/docs/agents/) | source 2026-05-08 | Agents/drift |
| [Permissions](https://opencode.ai/docs/permissions/) | source 2026-06-30 | Policy |
| [MCP](https://opencode.ai/docs/mcp-servers/) | source 2026-06-11 | MCP |
| [LSP](https://opencode.ai/docs/lsp/) | source 2026-05-26 | LSP |
| [Providers](https://opencode.ai/docs/providers/) | source 2026-08-18 | Providers |
| [V1 loop](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/prompt.ts#L1081-L1339) | 2026-08-21 | Loop |
| [Processor](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/processor.ts#L98-L692) | 2026-07-03 | Tool state |
| [Compaction](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/opencode/src/session/compaction.ts#L115-L590) | 2026-08-12 | Context |
| [V2 runner](https://github.com/anomalyco/opencode/blob/3a31c4ea801915c0b050df4b3842997ea62b6e93/packages/core/src/session/runner/llm.ts#L43-L418) | 2026-08-18 | Durable path |
| [MCP spec](https://modelcontextprotocol.io/specification/2025-11-25/basic) | 2025-11-25 | Protocol/security |
| [MCP update](https://blog.modelcontextprotocol.io/posts/2026-07-28/) | 2026-07-28 | Current drift |
| [Anthropic: agents](https://www.anthropic.com/engineering/building-effective-agents) | 2024-12-19 | Simplicity/ACI |
| [Anthropic: context](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents) | 2025-09-29 | Compaction |
| [Anthropic: evals](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents) | 2026-01-09 | Evals |
| [Anthropic: sandbox](https://www.anthropic.com/engineering/claude-code-sandboxing) | 2025-10-20 | Containment |
| [OpenAI: runner](https://openai.github.io/openai-agents-python/running_agents/) | retrieved | Loop/bounds |
| [OpenAI: tracing](https://openai.github.io/openai-agents-js/guides/tracing/) | retrieved | Tracing |
| [OpenAI: guardrails](https://openai.github.io/openai-agents-js/guides/guardrails/) | retrieved | Guardrails |
| [OpenAI: Codex safety](https://openai.com/index/running-codex-safely/) | 2026-05-08 | Sandbox/approval |

## Câu hỏi chưa giải quyết

1. V2 sẽ thay V1 ở release nào, và migration/replay contract ra sao?
2. Có internal agent eval/production trace analysis không công khai không?
3. Cache hit và compaction information loss là bao nhiêu theo provider/model?
4. V2 reconcile side effect thế nào sau crash giữa called và settled event?
5. OpenCode có kế hoạch OS sandbox/network egress boundary không?
6. Stock có triệu chứng production nào thật sự cần queued steer, resume, hoặc
   multi-agent? Nếu chưa, không dựng trước.
