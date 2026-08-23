# Hermes Agent: kiến trúc, runtime và vị trí so với SOTA

Báo cáo này đánh giá Hermes Agent theo trạng thái quan sát đến ngày
**23-08-2026**, ưu tiên implementation tại commit đã khóa thay vì thông điệp
marketing. “SOTA” trong báo cáo luôn gắn với một chiều năng lực hoặc benchmark
cụ thể; không có bằng chứng để kết luận Hermes là SOTA tổng thể.

## 1. Kết luận điều hành

Hermes thực chất là một **coding/research agent chạy cục bộ, đa nhà cung cấp,
tool-rich**, kèm nhiều bề mặt vận hành (CLI, gateway, ACP, batch/Python), chứ
không chỉ là một model hay một vòng ReAct mỏng. Lõi của nó là vòng hội thoại
stateful, registry công cụ, nhiều lớp phục hồi lỗi và một hệ sinh thái mở gồm
MCP, memory, skills và subagent. Kết luận này dựa trên sơ đồ chính thức và điểm
vào `AIAgent`/conversation loop trong source
([architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture),
[AIAgent tại SHA khảo sát](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/run_agent.py#L421),
[conversation loop](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/agent/conversation_loop.py#L1766)).

**Điểm mạnh nổi bật:**

- Độ rộng tích hợp và khả năng chạy qua nhiều provider/backend là rất cao; lỗi
  provider được phân loại chi tiết và nối với retry/fallback, thay vì gom mọi
  lỗi thành một ngoại lệ chung
  ([error classifier](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/agent/error_classifier.py#L30-L87)).
- Tool runtime có những cơ chế thực dụng tốt: schema động, JSON lỗi trả về cho
  model, song song có barrier, spill kết quả lớn, ngân sách output theo lượt và
  guardrail nhiều mức
  ([registry dispatch](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/tools/registry.py#L1044-L1170),
  [tool-result storage](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/tools/tool_result_storage.py#L314-L450)).
- Prompt/context được tổ chức theo độ ổn định để hỗ trợ cache; compression có
  recovery qua search và đã có eval recall trên transcript thật, một thực hành
  tốt hơn việc chỉ đo token giảm được
  ([prompt assembly](https://hermes-agent.nousresearch.com/docs/developer-guide/prompt-assembly),
  [compaction scorecard](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/evals/compaction/README.md)).
- Delegation có context cô lập, hợp đồng output có schema, steering/stop và
  live transcript. Đây là một primitive điều phối hữu ích, không chỉ là lệnh
  gọi agent con đồng bộ
  ([delegation docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation),
  [lifecycle API](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/agent/subagent_lifecycle.py)).

**Điểm yếu trọng yếu:**

- Mặc định local execution không có sandbox OS; guardrail ở mức command/path
  không thay thế containment. Chính hướng dẫn bảo mật nói local backend không
  cách ly và khuyến nghị Docker/SSH khi cần ranh giới mạnh
  ([security guide](https://hermes-agent.nousresearch.com/docs/user-guide/security)).
- Lõi rất lớn và tập trung: `run_agent.py` cùng `conversation_loop.py` gánh
  nhiều trách nhiệm. **Nhận định kiến trúc:** điều này tăng tốc tích hợp nhưng
  làm kiểm chứng invariant và thay đổi an toàn khó hơn một state graph nhỏ,
  typed và checkpoint theo bước.
- Subagent chạy in-process không được resume sau process restart; ngân sách
  iteration thuộc từng child, không phải ngân sách toàn cây. Worktree isolation
  cũng là opt-in, nên durability và containment yếu hơn runtime workflow bền
  vững
  ([delegation lifecycle](https://hermes-agent.nousresearch.com/docs/developer-guide/subagent-lifecycle-api),
  [delegate implementation](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/tools/delegate_tool.py#L1582-L1975)).
- Tài liệu hiện nói mặc định tối đa 3 child đồng thời, trong khi code tại SHA
  khảo sát đặt `_DEFAULT_MAX_CONCURRENT_CHILDREN = 10`; đây là drift có ảnh
  hưởng chi phí/vận hành
  ([docs delegation](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation),
  [hằng số trong code](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/tools/delegate_tool.py#L118-L133)).
- Eval hiện có giá trị nhưng hẹp; chưa thấy kết quả Hermes được công bố trên
  SWE-bench, BrowseComp, GAIA hay benchmark agent tổng quát tương đương. Vì vậy
  không thể suy từ feature breadth sang benchmark superiority.

**Verdict:** Hermes mạnh hơn phần lớn harness tối giản ở “production scar
tissue”: provider diversity, recovery, tool ergonomics và khả năng tùy biến.
Nó tương đương các framework hàng đầu ở nhiều primitive, nhưng yếu hơn
LangGraph/OpenAI durable runners về resume/checkpoint, yếu hơn Codex về sandbox
mặc định, và chưa có bằng chứng benchmark để đứng trên các agent đầu bảng. Nó
được tối ưu cho **local power-user autonomy và openness**, không phải cho một
workflow tài chính có toolset nhỏ, ranh giới dữ liệu chặt và auditability là ưu
tiên như Stock_Massive.

## 2. Bằng chứng, phương pháp và độ tin cậy

Nghiên cứu dùng source chính thức, tài liệu của chủ dự án, spec/framework docs
first-party và paper gốc. Source code thắng tài liệu khi hai nguồn mâu thuẫn;
claim từ docs được ghi là claim, không được nâng thành hành vi runtime đã quan
sát. Không chạy benchmark end-to-end với model/provider thực, nên mọi kết luận
về runtime quality ngoài eval công bố đều là suy luận.

**Mốc phiên bản đã khóa:**

| Nguồn | Mốc khảo sát | Cách dùng | Tin cậy |
|---|---|---|---|
| Hermes Agent | `30d4555085ec684ff140d5841b5456b5d2291a72`, commit 23-08-2026 | Nguồn chính cho cơ chế implementation | Cao |
| Hermes release | `v2026.8.19` / `v0.20.5`, phát hành 21-08-2026; tag trỏ `fcbd1076a93841fa88855acce810e342a5b78101` | Mốc release gần nhất, không thay SHA khảo sát | Cao |
| OpenAI Codex | `83d1fe0e67b1323f71febc2925817732b449f1d9`, 23-08-2026 | Sandbox/app-server baseline | Cao cho source được dẫn |
| OpenAI Agents SDK Python | `233467994fac7e7dbd868931573cc9a4302c0a16`, 23-08-2026 | Loop, tracing, durable runner baseline | Cao cho source/docs được dẫn |
| LangGraph | `f09cfe8ffc1eeffd68f4b628ed69c30f7cad229f`, 20-08-2026 | Persistence/interrupt baseline | Cao cho source/docs được dẫn |
| Anthropic Claude Code/engineering | Trang live, ngày phiên bản tổng thể không công bố | Context/subagent/eval pattern | Trung bình; đã gắn ngày bài khi có |
| MCP | Spec GA ngày 28-07-2026 | Chuẩn giao thức | Cao |

SHA và release Hermes được kiểm tra trực tiếp từ repository/release chính thức
([release `v2026.8.19`](https://github.com/NousResearch/hermes-agent/releases/tag/v2026.8.19),
[commit khảo sát](https://github.com/NousResearch/hermes-agent/commit/30d4555085ec684ff140d5841b5456b5d2291a72)).
Các trang docs Hermes là trang live, nên nội dung của chúng có thể đổi sau ngày
khảo sát; các claim quan trọng vì thế được ghim thêm vào permalink code.

Nhãn dùng xuyên báo cáo là **Cao** khi code/spec khóa phiên bản xác nhận trực
tiếp; **Trung bình** khi chỉ có docs first-party hoặc hành vi phụ thuộc cấu
hình/provider; **Thấp** khi là suy luận kiến trúc chưa có benchmark/runtime
trace. Các tài liệu nội bộ cũ của Stock_Massive chỉ dùng để giữ quyết định và
phát hiện thay đổi, không dùng làm bằng chứng về Hermes hiện tại.

## 3. Bản đồ kiến trúc và vòng đời một lượt

Hermes gom nhiều entry point vào cùng một lõi agent. Provider adapters chuyển
OpenAI-compatible Chat Completions, Codex Responses và Anthropic Messages về
một dạng message nội bộ gần OpenAI; sau đó cùng đi qua prompt assembly, context
engine, tool registry và state store
([provider runtime](https://hermes-agent.nousresearch.com/docs/developer-guide/provider-runtime),
[agent loop](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop)).

```text
CLI / Gateway / ACP / Batch / Python API
                 |
                 v
        AIAgent + provider resolver
                 |
     prompt assembly + context engine
                 |
       model call / stream / recovery
          |                  |
      final text          tool calls
          |                  |
     persist/return   parse -> plan groups
                             |
                    registry -> backend/MCP
                             |
                 normalize/spill/budget result
                             |
                     append -> next iteration

SQLite state: session, message, usage, compression, delegation
Observers: hook events / gateway OTLP / optional trajectory export
```

Một lượt đi theo chuỗi cụ thể sau; đây là tổng hợp từ docs và code, không phải
trace đo tại runtime:

1. Entry point resolve provider/model/credentials và mở hoặc tạo session.
2. User message được ghi vào lịch sử; system prompt ổn định đã dựng cho session
   được tái sử dụng, còn lớp ephemeral gắn vào call hiện tại.
3. Context engine kiểm tra ngưỡng và có thể compact trước request; adapter định
   dạng message, cache-control và nội dung multimodal theo provider.
4. Provider call chạy interruptible. Error classifier quyết định retry có
   jitter, fallback, giảm payload/context, hay trả lỗi
   ([recovery branch](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/agent/conversation_loop.py#L4662)).
5. Nếu model trả text cuối, Hermes persist/flush rồi trả về. Nếu trả tool call,
   executor parse arguments, áp guardrail, chia nhóm tuần tự/song song, dispatch
   và chuẩn hóa kết quả.
6. Tool results được append đúng thứ tự call; kết quả quá lớn được spill hoặc
   cắt theo ngân sách lượt. Loop quay lại model cho đến final, giới hạn iteration,
   deadline, interrupt hoặc lỗi không phục hồi.

Thiết kế là imperative loop, không phải graph khai báo. **Suy luận, độ tin cậy
trung bình:** cách này phù hợp với sản phẩm terminal cần nhiều nhánh tương thích
ngược; đổi lại, replay một phần và chứng minh state transition khó hơn graph có
checkpoint rõ ràng.

## 4. Tool calling, thực thi và MCP

Tool runtime của Hermes là một subsystem hoàn chỉnh: definition được tạo từ
registry, availability có thể phụ thuộc môi trường, call được chuẩn hóa và
output được quản lý theo ngân sách. Đây là một trong những phần tái sử dụng tốt
nhất của thiết kế.

**Schema, parse và dispatch.** `ToolEntry` giữ tên, schema, handler, metadata và
check khả dụng; `get_definitions()` chỉ expose tool đạt check và cache check ngắn
hạn. API-facing schema dùng dạng function tool. Arguments phải parse thành JSON
object; JSON lỗi hoặc scalar tạo synthetic tool error và handler không chạy
([ToolEntry](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/tools/registry.py#L204),
[argument parsing](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/agent/tool_executor.py#L164-L185)).
Registry bắt exception, sanitize và trả lỗi JSON cho model, tránh làm sập toàn
loop; nhưng lỗi model-visible vẫn cần được xem là dữ liệu không tin cậy.

**Song song và barrier.** Hermes không `gather` mọi call mù quáng. Nó tạo các
nhóm liên tiếp tối đa của call được đánh dấu an toàn để song song, chặn tại tool
interactive/unsafe/không nhận diện, xét xung đột target file và chỉ cho MCP song
song khi server opt-in. Worker pool có giới hạn 8, còn kết quả được phát theo
thứ tự call ban đầu
([segmented execution](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/run_agent.py#L8323-L8365),
[concurrent executor](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/agent/tool_executor.py#L1070)).
Pattern đáng lấy là **parallel-read, serialize-side-effect, stable emission
order**.

**Retry và recovery.** Provider retry/fallback nằm ở conversation loop; tool
handler nói chung không có một retry policy phổ quát vì retry side effect có
thể gây lặp. Loop còn xử lý malformed name/id, call lặp và các tín hiệu không
tiến triển. Đây là lựa chọn đúng hướng: retry transport idempotent có thể tự
động, còn side effect phải có idempotency key hoặc xác minh trước khi lặp.

**Output handling.** Mỗi result có thể được persist ra file và thay bằng stub;
sau đó tổng output của cả lượt còn chịu một budget riêng. Hai tầng này ngăn một
tool lớn hoặc nhiều tool nhỏ cùng làm nổ context
([per-result spill và turn budget](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/tools/tool_result_storage.py#L314-L450)).
Hermes chỉ chuẩn hóa string hoặc multimodal envelope; schema semantic của output
vẫn thuộc từng tool.

**Guardrail.** Quyết định tool đi qua ladder `allow/warn/block/halt`; dangerous
commands còn có hard blocklist luôn bật và approval timeout fail-closed. Tuy
nhiên sensitive-path protection chỉ bao các primitive file chính; terminal vẫn
chạy dưới quyền OS của user. Checkpoint file là opt-in, không phải rollback
transaction phổ quát
([security guide](https://hermes-agent.nousresearch.com/docs/user-guide/security)).

**MCP.** Hermes hỗ trợ stdio, Streamable HTTP và legacy SSE; có timeout theo
server, OAuth/mTLS, lọc env, include/exclude tool, resource/prompt wrappers,
pagination, notification `tools/list_changed` và cache list. Tool được namespace
thành `mcp__server__tool`; song song là opt-in. Server có `trust: full` hoặc
`untrusted`; với untrusted, tool có khả năng write cần approval nếu thiếu
`readOnlyHint`
([MCP runtime source](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/tools/mcp_tool.py),
[MCP guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/mcp)).

Spec MCP GA 28-07-2026 chuyển sang request stateless, `server/discover`, cache
hints và MRTR, đồng thời deprecate các server-to-client primitive cũ
([thông báo GA chính thức](https://github.com/modelcontextprotocol/modelcontextprotocol/blob/main/blog/content/posts/2026-07-28-spec-ga/index.md)).
Code Hermes đã có negotiation `auto/stateless/legacy` và cache hints
([session negotiation](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/tools/mcp_tool.py#L2349-L2550)),
nhưng vẫn giữ sampling/legacy compatibility. Không tìm thấy đủ bằng chứng về
toàn bộ MRTR `inputRequired/inputResponses/requestState`; vì vậy mức tuân thủ
GA đầy đủ là **chưa xác lập**, không nên ghi “fully compliant”.

## 5. Harness và runtime

Harness Hermes tối ưu cho khả năng chạy ở nhiều môi trường hơn là một deployment
model duy nhất. Điều này tạo độ phủ rất tốt, nhưng cũng làm số đường đi cần kiểm
thử lớn hơn đáng kể.

**Provider routing.** Một resolver chung phục vụ CLI, gateway, cron, ACP và các
call phụ; nó quản lý model/provider, scope credentials và fallback chain
([provider runtime](https://hermes-agent.nousresearch.com/docs/developer-guide/provider-runtime)).
Subagent không tự động kế thừa toàn bộ fallback chain của parent, nên “parent
có fallback” không đồng nghĩa delegation cũng có cùng SLO.

**Execution backend.** Terminal có local và các backend cách ly/remote như
Docker/SSH. Local là mặc định và không có isolation. Child process có thể nhận
environment đã lọc secret, nhưng vẫn có thể đọc filesystem theo quyền user;
lọc env không phải sandbox
([tools and terminal backends](https://hermes-agent.nousresearch.com/docs/user-guide/features/tools),
[security guide](https://hermes-agent.nousresearch.com/docs/user-guide/security)).

**Session state.** SQLite dùng WAL, có FTS5/search, lưu session/message/usage,
compression và delegation. Compaction in-place soft-archive message thay vì xóa
thẳng. Lịch sử bình thường và kết quả background đã hoàn tất có đường persist;
execution subagent đang chạy thì không resume qua restart
([state implementation](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/hermes_state.py),
[subagent lifecycle](https://hermes-agent.nousresearch.com/docs/developer-guide/subagent-lifecycle-api)).

**Streaming và event.** Provider stream đi qua loop và có thể bị interrupt;
gateway/ACP chuyển event sang protocol tương ứng. Observer schema
`hermes.observer.v1` phát lifecycle session/turn/API/tool/approval/subagent;
payload đắt chỉ dựng khi hook đăng ký. Gateway OTLP là một plane riêng, mặc
định hướng tới metadata vận hành thay vì prompt/tool content; trajectory export
là plane khác
([observability README](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/docs/observability/README.md),
[trajectory format](https://hermes-agent.nousresearch.com/docs/developer-guide/trajectory-format)).

**Ops verdict.** So với harness đơn giản, Hermes mạnh ở taxonomy lỗi, fallback,
interrupt và event surface. So với durable workflow engine, nó yếu ở checkpoint
của execution đang chạy, exactly-once side effect và resume từ một state
transition cụ thể.

## 6. Context, cache, memory và skills

Hermes coi context là tài nguyên có cấu trúc, không phải một chuỗi prompt được
nối tùy ý. Đây là hướng đúng và tương thích với khuyến nghị first-party của
Anthropic rằng chất lượng agent phụ thuộc vào việc chọn lọc context hữu hạn,
không chỉ mở rộng cửa sổ
([Anthropic context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)).

**Prompt organization.** `build_system_prompt_parts()` chia prompt thành
`stable`, `context` và `volatile`, rồi ghép theo thứ tự đó; system prompt được
dựng cho lifetime session thay vì render lại mỗi lượt
([prompt builder source](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/agent/system_prompt.py#L340-L360),
[assembly order](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/agent/system_prompt.py#L903-L921)).
Context files theo ưu tiên first-match, còn instruction theo call được gắn ở
lớp ephemeral. Cách sắp phần ổn định trước, biến động sau tạo prefix ổn định để
prompt cache có cơ hội hit.

**Cache.** Adapter Anthropic đặt cache-control trên system prompt ổn định và
các mốc recent-message, trong giới hạn breakpoint của API. Docs nêu lợi ích
chi phí lớn, nhưng báo cáo này không coi con số marketing là kết quả đo độc lập
([context compression and caching](https://hermes-agent.nousresearch.com/docs/developer-guide/context-compression-and-caching)).

**Compression.** `ContextEngine` tách `should_compress`, `compress` và
`select_context`, cho phép thay engine mà không đổi loop
([ContextEngine interface](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/agent/context_engine.py#L89-L233)).
Built-in path bảo vệ tail gần nhất, hỗ trợ in-place archive và có thể dùng
session search để phục hồi chi tiết. Eval nội bộ ngày 15-08 dùng bốn transcript
thật dài 500K token, 15 câu recall mỗi transcript: uncompacted 96,7%; current
45,8% ở 162K; lean 40,0% ở 49K; lean + recovery 68,3% ở 49K. Scorecard tự nêu
giới hạn so sánh với Codex do khác model/file-read, nên đây là bằng chứng tốt
cho trade-off nội bộ, không phải leaderboard
([compaction eval](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/evals/compaction/README.md)).

**Memory.** `MEMORY.md` và `USER.md` được snapshot vào prompt đầu session;
ghi file có hiệu lực trên disk ngay nhưng prompt snapshot chỉ đổi ở session mới
hoặc rebuild. `session_search` dùng index để phục hồi chéo session; memory có
scan injection và giới hạn kích thước
([memory guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/memory)).
Đây là memory tiện dụng cho coding agent, nhưng free-text mutable system context
vẫn là trust boundary lớn hơn typed state.

**Skills và “self-improvement”.** Skill dùng progressive disclosure: index nhỏ
ở đầu, nội dung đầy đủ chỉ nạp khi gọi; hỗ trợ định dạng Agent Skills. Curator
có backup/report/restore/pinning, nhưng LLM consolidation mặc định tắt; mặc định
chủ yếu là curation xác định. Vì vậy nên gọi đây là **khả năng quản trị tri thức
tự chỉnh sửa**, chưa phải bằng chứng agent tự cải thiện chất lượng qua thời gian
([skills guide](https://hermes-agent.nousresearch.com/docs/user-guide/features/skills)).

## 7. Subagent và delegation

Delegation của Hermes ưu tiên context isolation và throughput. Parent gửi goal
cùng context chọn lọc; child có transcript mới và chỉ final summary quay lại
parent, giảm ô nhiễm context so với chia sẻ toàn bộ lịch sử.

**Hợp đồng và isolation.** Child được dựng với `skip_context_files=True`,
`skip_memory=True`, không có `clarify`, và mặc định bị chặn `delegate`, memory,
send-message và cron. Orchestrator mode có thể cấp lại delegation trong depth
giới hạn; `MAX_DEPTH = 1` là mặc định
([blocked tools và depth](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/tools/delegate_tool.py#L50-L133),
[child construction](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/tools/delegate_tool.py#L1582-L1975)).

**Concurrency và aggregation.** Top-level delegation có thể background; child
worker trong orchestrator chạy đồng bộ với coordinator. Kết quả aggregate theo
thứ tự input. Code đặt tối đa 10 child đồng thời, trái với docs nói 3. Mỗi child
có iteration budget riêng (mặc định 50); không thấy global token/cost cap bắt
buộc cho toàn cây. Đây là rủi ro bùng chi phí dù depth bị chặn.

**Structured output.** Parent có thể yêu cầu JSON Schema; Hermes parse, validate
và cho đúng một retry. Tuy nhiên nếu dependency `jsonschema` không import được,
implementation chấp nhận JSON parse được mà không validate schema. Đây là
fail-open về integrity, không nên sao chép vào workflow tài chính
([output-schema implementation](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/tools/delegation_output_schema.py)).

**Failure và durability.** Có list/steer/stop, stall detection, optional hard
timeout và trạng thái queued/delivered. Kết quả background được persist trước
delivery, nhưng process restart không nối lại thread child đang chạy; trạng thái
có thể thành unknown. Live transcript lưu thinking/text snippets/tool args/result
trong cache một thời gian, hữu ích cho debug nhưng làm tăng bề mặt secret/PII
([delegation docs](https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation)).

**Filesystem.** Git worktree isolation là opt-in; nếu tắt, child chia sẻ working
directory. Với tác vụ chỉ đọc đây là trade-off nhanh hợp lý; với nhiều child
ghi code, mặc định này kém an toàn hơn Claude Code subagent có tùy chọn worktree
cô lập và Codex sandbox
([Claude Code subagents](https://code.claude.com/docs/en/sub-agents),
[Codex sandbox source](https://github.com/openai/codex/blob/83d1fe0e67b1323f71febc2925817732b449f1d9/codex-rs/core/src/tools/sandboxing.rs)).

## 8. Evaluation và kiểm soát chất lượng

Hermes hiện không còn là dự án “không có eval”: repository có nhiều battery
nhắm vào failure mode cụ thể. Tuy nhiên coverage đó chưa chứng minh chất lượng
agent tổng quát hoặc ưu thế so với hệ thống đầu bảng.

**Eval quan sát được:**

- Compaction eval đo recall so với token budget trên transcript thật, có judge
  rubric và caveat rõ
  ([compaction eval](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/evals/compaction/README.md)).
- Browser-use eval có 204 cell A/B trên task `toscrape`; README cảnh báo raw
  artifacts gốc từng mất và aggregate được phục dựng, mẫu mỗi cell nhỏ. Vì vậy
  provenance đủ để học pattern nhưng chưa đủ cho claim rộng
  ([browser-use eval](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/evals/browser_use/README.md)).
- Read-tool eval tạo hostile workspace xác định và lặp nhiều model/config nhằm
  kiểm tra navigation/tool behavior
  ([read-tool eval](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/evals/readtool/README.md)).
- Batch/mini-SWE runner xuất trajectory, còn verify runner chạy recipe
  bootstrap/build/test/readiness. Chúng xác minh workspace/result kỹ thuật,
  không tự động là grader cho độ đúng câu trả lời
  ([mini-SWE runner](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/mini_swe_runner.py),
  [verify runner](https://github.com/NousResearch/hermes-agent/blob/30d4555085ec684ff140d5841b5456b5d2291a72/agent/verify/runner.py)).

Không tìm thấy score Hermes chính thức trên
[SWE-bench](https://arxiv.org/abs/2310.06770) hoặc
[BrowseComp](https://openai.com/index/browsecomp/) tại mốc khảo sát. Hai nguồn
này chỉ định nghĩa loại bằng chứng ngoài cần có; việc Hermes có mini-SWE runner
không tương đương một submission benchmark được kiểm chứng.

**Failure taxonomy nên theo dõi:** provider auth/rate/overload/timeout/SSL;
context overflow và output cap; malformed/duplicate tool call; side effect có
trạng thái không rõ; no-progress/repetition; interrupt/deadline; subagent
stall/restart; schema mismatch; prompt/tool-output injection. Hermes đã xử lý
nhiều nhánh trong code, nhưng không có một bảng công bố coverage và residual
failure rate tổng thể.

**Verification verdict.** Hermes mạnh ở eval theo failure mode và trajectory
plumbing; OpenAI Agents SDK rõ hơn về testing utilities/tracing như một contract
framework, còn LangGraph rõ hơn về replay/time-travel. Anthropic nhấn mạnh eval
agent phải chấm outcome và nhiều trajectory hợp lệ, thay vì khớp một path duy
nhất
([OpenAI Agents testing](https://openai.github.io/openai-agents-python/testing/),
[Anthropic eval guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents)).

## 9. Bảo mật và ranh giới tin cậy

Hermes có nhiều guardrail hữu ích, nhưng security posture cuối cùng phụ thuộc
mạnh vào execution backend và tool được bật. Không nên nhầm approval UX với
OS-level containment.

| Ranh giới | Cơ chế hiện có | Phần còn hở / verdict |
|---|---|---|
| Model → tool | JSON schema, allow/warn/block/halt, approval, hard blocklist | Model/tool output vẫn untrusted; terminal có đường quyền rộng |
| Tool → host | Lọc env, sensitive-path checks, optional checkpoint | Local mặc định không sandbox; đọc filesystem theo user |
| MCP server → Hermes | Namespace, env filtering, OAuth/mTLS, include/exclude, `untrusted` approval | `trust: full` là mặc định; `readOnlyHint` do server khai báo không phải quyền OS |
| Child → parent | Fresh context, final-summary boundary, blocked tools, depth cap | Shared cwd mặc định; toàn cây không có cost cap bắt buộc |
| Memory/skill → prompt | Size limit, injection scan, progressive disclosure, quarantine/curation | Nội dung persistent vẫn có thể trở thành instruction có đặc quyền cao |
| Observability → operator | Content-light OTLP plane; observer/trajectory tách riêng | Live transcript/trajectory có thể chứa prompt, args, output và secret |
| Process restart | Session/result đã hoàn tất persist | In-flight child không durable-resume; side effect có thể ở trạng thái không rõ |

Threat model thực tế phải giả định repository, webpage, MCP result và child
output đều có prompt injection. Với local backend, một tool-call bị thuyết phục
sai có blast radius bằng quyền user. Biện pháp mạnh nhất là sandbox/credential
scoping/allowlist và xác nhận side effect, không phải thêm câu cảnh báo vào
system prompt
([Hermes security guide](https://hermes-agent.nousresearch.com/docs/user-guide/security),
[MCP authorization specification](https://modelcontextprotocol.io/specification/2026-07-28/basic/authorization)).

## 10. Ma trận so sánh với các pattern SOTA

Ma trận này so **năng lực theo chiều**, không xếp hạng tuyệt đối. “Mạnh hơn” chỉ
có nghĩa là implementation quan sát được tốt hơn baseline được nêu cho chiều
đó; “SOTA benchmark” chỉ dùng khi có benchmark primary-source tương ứng.

| Chiều | Hermes | Baseline first-party | Verdict có giới hạn |
|---|---|---|---|
| Loop/tool breadth | Imperative loop, tool/MCP/provider rất rộng | OpenAI Agents SDK có agent-as-tool, handoff, guardrail, max-turn và session ([run loop](https://openai.github.io/openai-agents-python/running_agents/)) | Hermes mạnh hơn về breadth đóng gói; comparable về primitive |
| Durable execution | Persist session/result, không resume child đang chạy | OpenAI SDK có integrations Temporal/Restate/DBOS/Dapr; LangGraph checkpoint từng bước và resume interrupt ([durable agents](https://openai.github.io/openai-agents-python/running_agents/), [LangGraph persistence](https://docs.langchain.com/oss/python/langgraph/persistence)) | Hermes yếu hơn |
| State graph/replay | Loop imperative, compaction/archive | LangGraph checkpoint, pending writes, time travel ([time travel](https://docs.langchain.com/oss/python/langgraph/use-time-travel)) | Khác mục tiêu; LangGraph mạnh hơn cho audit/replay |
| Provider portability | Nhiều adapter và fallback taxonomy sâu | Agents SDK chủ yếu OpenAI-shaped; LangGraph model-agnostic | Hermes mạnh ở packaged provider routing |
| Tool concurrency | Barrier theo side effect/xung đột, stable order | Agents SDK hỗ trợ manager/agents-as-tools và `asyncio.gather` ([multi-agent](https://openai.github.io/openai-agents-python/multi_agent/)) | Hermes mạnh hơn naive gather; chưa có benchmark throughput chung |
| Tool-output control | Spill từng result + budget toàn lượt | Các baseline cho hook/session nhưng policy tùy app | Hermes mạnh và rất đáng tái sử dụng |
| Sandbox | Local mặc định không isolation; Docker/SSH tùy chọn | Codex định tuyến command qua sandbox policy theo platform ([Codex sandbox](https://github.com/openai/codex/blob/83d1fe0e67b1323f71febc2925817732b449f1d9/codex-rs/core/src/tools/sandboxing.rs)) | Hermes yếu hơn về secure default |
| Context engineering | Stable/context/volatile, cache, compaction + search recovery | Anthropic chủ trương curate context, subagent context isolation ([context engineering](https://www.anthropic.com/engineering/effective-context-engineering-for-ai-agents)) | Comparable về pattern; Hermes có eval nội bộ cụ thể |
| Memory | Prompt snapshot + FTS cross-session + mutable skills | Claude Code có project/user memory và subagent memory ([Claude agents](https://code.claude.com/docs/en/agents)) | Comparable, khác trust/curation choices |
| Subagent isolation | Fresh context, blocked tools, depth cap, schema output | Claude Code: context/tool/worktree/memory riêng, không nested; Anthropic research dùng orchestrator-workers | Comparable primitive; Hermes yếu hơn về durability/global budget |
| Multi-agent quality evidence | Không có benchmark tổng quát công bố | Anthropic báo nội bộ multi-agent hơn single Opus 4 90,2% trên research eval, với chi phí token cao ([research system](https://www.anthropic.com/engineering/multi-agent-research-system)) | Không đủ bằng chứng so chất lượng Hermes; số Anthropic chỉ áp dụng eval nội bộ đó |
| Tracing/observability | Observer events, content-light OTLP, trajectory | OpenAI SDK có traces cho generations/tools/handoffs/guardrails ([tracing](https://openai.github.io/openai-agents-python/tracing/)) | Comparable về event breadth; OpenAI có UX contract rõ hơn, Hermes tách privacy plane tốt |
| MCP 2026 GA | Modern/legacy negotiation, cache hints, nhiều transport | MCP GA stateless + discovery + MRTR | Mạnh về compatibility; full GA conformance chưa xác lập |
| Eval | Targeted compaction/browser/read-tool, verify recipes | SWE-bench/BrowseComp là benchmark gốc; framework baselines có testing/replay | Tốt ở local regression; không có cơ sở gọi overall SOTA |
| Complexity/modularity | Feature-rich nhưng lõi lớn, nhiều global/import-time wiring | LangGraph explicit state/node/checkpoint; Agents SDK typed primitives | Hermes tối ưu tích hợp nhanh; yếu hơn về compositional auditability |

Kết luận “best of the best vs SOTA” vì thế là: Hermes thuộc nhóm tốt nhất về
**độ thực dụng của local multi-provider harness và tool runtime**, comparable
với pattern tốt nhất về context isolation/cache, nhưng không dẫn đầu có bằng
chứng về benchmark, durability, sandbox secure-by-default hoặc graph replay.

## 11. Pattern nên lấy, điều không nên sao chép và lộ trình Stock_Massive

Stock_Massive là financial assistant có toolset nhỏ, SSE/Postgres, ranh giới
dữ liệu và freshness quan trọng; nó không phải coding agent đa backend. Các báo
cáo hiện có cho thấy dự án đã có route-error recovery, deadline distinction,
parallel tool execution, prompt-cache capability/config, session search/memory,
guardrail nhiều mức và SSRF hardening. Vì vậy khuyến nghị dưới đây giữ nguyên
các quyết định đã có, không đề xuất “port Hermes”
([tổng hợp Hermes–Stock_Massive](./hermes-synthesis-260821-0030.md),
[teardown nền](./research-260820-2338-hermes-agent-teardown.md),
[ghi chú trạng thái tài liệu](./README.md)).

**Pattern nên áp dụng:**

- Tách định nghĩa tool, quyết định guardrail, execution và output-budget thành
  contract độc lập; giữ emission order ổn định khi song song.
- Phân loại lỗi theo hành động phục hồi, không theo chuỗi message; retry chỉ khi
  idempotent hoặc có xác minh side effect.
- Đo context compression bằng cặp chỉ số **recall quality / token retained**,
  kèm recovery-search, thay vì chỉ đo token tiết kiệm.
- Tách telemetry content-light khỏi trajectory giàu nội dung; redact theo
  schema và chỉ dựng payload khi subscriber cần.
- Với delegation tương lai, dùng fresh context, tool allowlist, structured
  output fail-closed, global cost/deadline budget và trạng thái durable.

**Điều không nên sao chép:**

- Không nhập mô hình hai file lõi hàng nghìn dòng, registry global/import-time
  và branching tương thích dày vào agent tài chính nhỏ.
- Không bật host shell/local execution hoặc MCP `trust: full` mặc định.
- Không dùng free-text mutable memory/skill như nguồn instruction đặc quyền cao
  thay cho typed state và policy hiện có.
- Không chấp nhận schema khi validator vắng mặt; production phải fail-closed.
- Không dùng budget theo từng child mà thiếu cap toàn cây, và không coi thread
  in-process là durable job.
- Không lưu live thinking/tool args/result dài ngày nếu chưa có retention,
  redaction và access control cụ thể.
- Không để default vận hành chỉ tồn tại trong prose; drift “3 trong docs, 10
  trong code” là ví dụ trực tiếp về rủi ro.

**P0 — phục hồi quality gate hẹp, không đổi kiến trúc.** Tạo golden/eval battery
cho factual freshness, bắt buộc price-check khi cần, tool sequence, citation/
grounding và `incomplete_reason`. Dùng trajectory thật, nhiều path hợp lệ và
outcome grader; không hồi sinh một gate chặn mọi câu trả lời. Giữ quyết định ops
read-only/không auto-alert của solo operator.

**P0 — chống config/docs drift.** Viết contract test đọc runtime defaults và
đối chiếu tài liệu/cấu hình cho max rounds, deadline, cache capability, tool
allowlist và guardrail mode. Capability probe prompt-cache đã tồn tại thì đo và
giữ nó, không thiết kế lại prompt chỉ để giống Hermes.

**P1 — đo context và cache trước khi thêm compaction.** Ghi cache read/write
token, hit/miss và chi phí nếu provider expose. Chỉ đưa compaction vào khi
transcript thật chạm ngưỡng; trước đó xây recall suite và dùng session search
làm recovery. Typed memory hiện tại nên giữ ưu tiên hơn MEMORY.md tự do.

**P1 — mở rộng observability có kiểm soát.** Chuẩn hóa event cho provider call,
tool decision, retry/fallback, deadline và completion reason; default không chứa
prompt/tool result. Trajectory debug phải opt-in, redacted và có TTL.

**P2 — chỉ thêm subagent/MCP khi có workload độc lập đo được.** Các use case
hợp lệ có thể là phân tích song song nhiều filing hoặc kiểm chứng độc lập; khi
đó dùng cây phẳng, durable queue, tổng token/cost/deadline cap và merge theo
schema. Không thêm chỉ vì Hermes có. Nếu MCP xuất hiện, mặc định untrusted,
allowlist tool, capability negotiation GA 2026 và conformance tests.

Thứ tự này ưu tiên chất lượng đo được và trust boundary của Stock_Massive. Nó
không đảo quyết định cũ rằng sandboxed code execution/subagent/MCP chưa đáng
chi phí cho phạm vi hiện tại; P2 là điều kiện mở lại quyết định khi workload và
số liệu thay đổi
([route/subagent decision record](./hermes-route-subagent-260820-2352.md)).

## 12. Câu hỏi mở và giới hạn nguồn

Các điểm dưới đây chưa có đủ bằng chứng primary-source hoặc cần runtime test;
chúng phải được giữ là unknown thay vì điền bằng suy đoán.

- Hermes có tuân thủ đầy đủ MCP 2026-07-28 MRTR, discovery và auth edge cases
  hay chỉ tương thích một phần qua negotiation/cache hints?
- Tỷ lệ fallback/retry thành công, duplicate side effect và unknown-state trong
  workload thật là bao nhiêu?
- Provider nào thực sự bảo toàn semantics giống nhau cho parallel tool call,
  cache-control, reasoning và multimodal sau lớp normalize?
- Chi phí/token latency của cây delegation 10 child trong thực tế, và stall
  monitor có false-positive/false-negative ra sao?
- Observer hooks, live transcript và trajectory đã có redaction test chống secret
  leakage toàn diện chưa?
- Các targeted eval có được chạy bắt buộc trên release/PR hay chỉ là harness có
  thể chạy? Repository cho thấy artifact và runner, nhưng chưa đủ bằng chứng về
  release gate bắt buộc.
- Không có benchmark công khai đủ để so chất lượng end-to-end Hermes với Codex,
  Claude Code hoặc agent nghiên cứu của Anthropic. Mọi verdict trong ma trận vì
  thế chỉ áp dụng đúng chiều được nêu.

Giới hạn cuối cùng là thời điểm: commit Hermes khảo sát mới hơn release gần nhất
hai ngày; một số docs live có thể mô tả main hoặc release không đồng nhất. Báo
cáo đã ghim critical implementation claim vào SHA, nhưng các trang Anthropic và
framework docs live không có version banner ổn định; phiên bản nội dung của các
trang đó ngoài ngày truy cập **không xác lập được**.
