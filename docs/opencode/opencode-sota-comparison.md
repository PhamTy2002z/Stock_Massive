# OpenCode — đối chiếu best practice và SOTA

“SOTA agent harness” không phải một bảng xếp hạng duy nhất. Model quality,
agent-computer interface, sandbox, orchestration, context management,
observability, và product integration là các trục độc lập. Tài liệu này so sánh
kiến trúc có bằng chứng, không suy ra chất lượng từ star hoặc marketing.

## Chuẩn so sánh

Một harness mạnh cần được đánh giá trên ít nhất tám trục:

1. task success trên benchmark hoặc golden set phù hợp;
2. ACI/tool ergonomics và protocol correctness;
3. isolation, approval, và secret/network boundary;
4. context selection, compaction, và cache efficiency;
5. recovery taxonomy và bounded retries;
6. subagent isolation, budget, cancellation, và join semantics;
7. session durability, replay, and observability;
8. extensibility mà không phá safety boundary.

SWE-agent đã cho bằng chứng thực nghiệm rằng chỉ thay Agent-Computer Interface
cũng làm thay đổi mạnh kết quả trên SWE-bench; vì vậy tool design phải được đo,
không chỉ review bằng cảm giác. Xem
[SWE-agent paper](https://arxiv.org/abs/2405.15793) và
[official ACI guide](https://github.com/SWE-agent/SWE-agent/blob/main/docs/background/aci.md).

## Ma trận kiến trúc

| Trục | OpenCode | Codex | Claude Code | OpenHands | Kết luận có giới hạn |
|---|---|---|---|---|---|
| Core openness | Source mở, provider-neutral | CLI source mở, gắn chặt OpenAI product/model path hơn | CLI runtime không mở toàn bộ | Platform và SDK source mở | OpenCode thuận lợi nhất để audit/port provider layer; không suy ra task success |
| Client/server | OpenAPI server là core; TUI/IDE/SDK là clients | CLI/app/cloud surfaces, kiến trúc source riêng | CLI/IDE/SDK surfaces | Agent Server và remote runtime API | OpenCode có contract programmatic rõ và nhẹ |
| Host isolation | Permission gate; execution thường trên host | Sandbox + approval policy là first-class | Permission modes, hooks, sandbox options tùy surface | Docker sandbox runtime là first-class | OpenCode thua OpenHands/Codex về isolation mặc định |
| Tool lifecycle | Typed part, hooks, abort, output truncation, MCP | Typed tools, sandbox mediation, approvals | Hooks trước/sau tool, permission rules, MCP | Action/observation qua sandbox runtime | OpenCode rất mạnh về extensibility; hook/plugin là trusted code |
| Rules/context | `AGENTS.md`, lazy nested rules, skills, compaction | `AGENTS.md`, skills, context policies | `CLAUDE.md`, rules, skills, hooks, subagents, compaction | Microagents, skills, workspace context | OpenCode có progressive disclosure tốt; cache efficiency cần số đo |
| Subagents | Child sessions, profile permission, foreground; background experimental | Multi-agent/subagent support tùy Codex surface | Custom subagents, isolated context, hook/permission control | Multi-agent primitives trong SDK/platform | OpenCode có lineage rõ nhưng chưa là DAG scheduler |
| Provider abstraction | Rộng, có transform per provider/model | Tập trung OpenAI | Tập trung Anthropic | Model-agnostic SDK | OpenCode/OpenHands phù hợp nghiên cứu portability hơn |
| Observability | V1 có durable parts/SSE; V2 thêm event log/projector nhưng chưa parity | Traces/session UI tùy surface | Transcripts, hooks, telemetry tùy setup | Event stream, runtime observations | OpenCode có primitive tốt; thiếu published harness eval trong snapshot |

Nguồn chính cho các cột ngoài OpenCode:

- Codex source: [openai/codex](https://github.com/openai/codex); security model:
  [Running Codex safely at OpenAI](https://openai.com/index/running-codex-safely/).
- Claude Code subagents:
  [Create custom subagents](https://code.claude.com/docs/en/sub-agents); steering
  layers:
  [skills, hooks, rules, and subagents](https://claude.com/blog/steering-claude-code-skills-hooks-rules-subagents-and-more).
- OpenHands sandbox:
  [Runtime architecture](https://docs.openhands.dev/openhands/usage/architecture/runtime);
  remote agent boundary:
  [Agent Server overview](https://docs.openhands.dev/sdk/guides/agent-server/overview).

## OpenCode thuộc nhóm “best of the best” ở đâu

### Server-first local agent

OpenCode biến local coding agent thành API-addressable service mà không buộc
người dùng dựng platform lớn. OpenAPI-generated SDK, SSE event stream, session
fork/revert/share/diff, và TUI-as-client là một tổ hợp rất tốt cho IDE và custom
automation. Xem [Server](https://opencode.ai/docs/server/).

### Unified capability plane

Built-in, custom, và MCP tools dùng chung schema transform, permission,
pre/post hook, abort, tool state, and output policy. Điều này giảm bypass path —
một capability mới không cần một loop riêng.

### Durable agent UX

Typed message parts giữ reasoning, text, tool progress, snapshot, patch, token,
cost, và error. Child session lineage có thể điều hướng. Đây là nền tốt cho
replay/debug hơn transcript text thuần.

Nhánh V2 còn đi xa hơn bằng persist-intent-before-effect, append event,
projector, và run coordinator theo session. Tuy nhiên source tự đánh dấu các
phần chưa xong, nên đây là kiến trúc đang xây, không phải lợi thế release đã
được chứng minh end-to-end.

### Progressive context

Nested rules nạp khi read file, skill body nạp khi gọi, old tool outputs được
prune trước LLM summary, và recent tail được bảo vệ theo token budget. Hình dạng
này phù hợp với best practice context engineering hiện đại.

## OpenCode chưa chứng minh SOTA ở đâu

### Không có sandbox boundary tương đương OpenHands

Permission ask/deny giảm accidental action nhưng không cô lập process khỏi host.
OpenHands đặt action executor trong Docker runtime và nói rõ mục tiêu isolation,
resource control, và reproducibility trong
[Runtime architecture](https://docs.openhands.dev/openhands/usage/architecture/runtime).
Với repo hoặc web content không tin cậy, đây là khác biệt threat model, không
phải feature checklist.

### Chưa có benchmark harness công khai gắn với kiến trúc

Snapshot khảo sát không tìm thấy report chính thức chứng minh riêng OpenCode loop,
subagent, compaction, hoặc permission policy cải thiện SWE-bench, cost, latency,
hay regression rate bao nhiêu. Vì vậy không xếp hạng task performance.

### Recovery taxonomy còn tương đối rộng

Retry layer có bounded exponential backoff và header awareness, nhưng nhiều
phân loại dựa trên message regex. Nó chưa biểu diễn đầy đủ failure scope theo
credential, endpoint, model deployment, payload, content policy, và local
deadline. Đây là khoảng trống reliability có thể đo bằng error corpus.

### Background orchestration còn experimental

Background subagent cần feature flag. Không có bằng chứng trong snapshot cho
worktree isolation, deterministic multi-child join, file ownership, hoặc
cross-agent transaction. Capability spawn chưa đủ để gọi là multi-agent SOTA.

### Plugin power mở rộng trust boundary

Plugin có thể sửa tool arguments và chạy shell qua Bun API. Đây là extension
surface mạnh, nhưng plugin dependency supply chain phải được quản như executable
code. Permission của model không bảo vệ khỏi plugin đã được process load.

## Best practices tổng hợp

### Agent loop

- Persist state transition trước khi phụ thuộc vào UI stream.
- Treat finish reason như tín hiệu, không phải chân lý duy nhất.
- Bảo toàn một result cho mọi tool call, kể cả deny, abort, và dispatch failure.
- Tách overflow recovery khỏi transient retry.
- Bound retry, step, tool fan-out, wall clock, và output.
- Surface content filter và structured-output failure bằng typed error.

### Tool/ACI

- Dùng tool chuyên biệt cho read/search/edit thay vì shell cho mọi việc.
- Giữ schema nhỏ, mô tả routing rõ, output có cấu trúc và có thể truncate.
- Full output là artifact; prompt chỉ nhận preview và retrieval handle.
- Permission check và lifecycle hook phải nằm trên mọi execution path.
- Unknown capability phải mặc định conservative.
- Đo tool selection accuracy, invalid argument rate, repeat rate, và task result.

### Context

- Tách stable rules, scoped rules, skill catalog, skill body, transcript, và
  volatile environment.
- Nạp instruction theo subtree và theo nhu cầu.
- Prune deterministic trước summarize lossy.
- Giữ recent user intent và cặp tool call/result nguyên vẹn.
- Dùng provider usage làm backstop cho token estimate.
- Đo cache hit và post-compaction task retention.

### Subagent

- Fresh context mặc định; resume khi task thực sự tiếp nối.
- Propagate deny và workspace boundary xuống child.
- Giao ownership, acceptance criteria, và output contract rõ.
- Không duplicate work; không spawn cho task một bước.
- Bound depth, budget, background job, và cancellation.
- Đo delegation uplift thay vì giả định parallel luôn nhanh hơn.

### Safety

- Phân biệt permission, sandbox, và authorization; chúng không thay thế nhau.
- Không cho open-ended network và secrets vào cùng untrusted execution context.
- Treat project rules, MCP server, remote instructions, plugin, và tool output là
  các trust boundary khác nhau.
- Log ai/agent nào đã phê duyệt action nào với scope nào.
- Test bypass qua subagent, custom tool, MCP, plugin, và external directory.

## Phán quyết

OpenCode là một trong các reference harness tốt nhất để học **product
architecture của coding agent mở**: modular server core, durable session,
provider portability, capability extension, và context hierarchy. Nó không phải
reference duy nhất cho safety hoặc measured task performance. Một kiến trúc
production mạnh hơn sẽ ghép:

- server/session/tool ergonomics của OpenCode;
- sandbox và network isolation của OpenHands/Codex;
- steering/hook/subagent discipline của Claude Code;
- ACI evaluation discipline của SWE-agent;
- domain-specific golden set và operational telemetry của chính sản phẩm.
