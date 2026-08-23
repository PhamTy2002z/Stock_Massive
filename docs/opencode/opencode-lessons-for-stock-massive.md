# OpenCode — bài học cho Stock_Massive

Stock_Massive không phải coding agent chạy shell trên repository. Nó là trợ lý
phân tích chứng khoán có web/store tools, turn budget, durable transcript, SSE,
và yêu cầu grounding. Vì vậy mục tiêu không phải port OpenCode; mục tiêu là lấy
những invariant làm harness hiện tại rõ, bền, và đo được hơn.

Đối chiếu này đọc trực tiếp các owner hiện tại trong `apps/api/src/agent`, đặc
biệt `loop.py`, `executor.py`, `events.py`, `messages.py`, `guardrails.py`,
`registry.py`, `turns.py`, và `persistence.py`.

## Những gì ta đã làm tốt ngang hoặc sâu hơn

### Bound là arithmetic, không phải cảm tính

`loop.py` ràng buộc tool rounds, max output, external calls, round timeout, call
timeout, và turn deadline với spend admission. OpenCode có step cap, retry cap,
truncate, và compaction, nhưng Stock_Massive đã làm rõ hơn quan hệ budget giữa
round và cost cho domain của mình.

### Tool failure luôn trở thành result

`executor.py` bảo đảm unknown, blocked, timeout, handler error, skipped, và
fan-out overflow đều sinh đúng một `ToolResult` theo thứ tự call. Đây là cùng
invariant protocol mà OpenCode processor bảo vệ bằng typed tool part.

### Repetition ladder sâu hơn doom-loop prompt

`guardrails.py` phân biệt exact failure, same-tool failure, và no-progress, rồi
đi qua `allow → warn → block → halt`. OpenCode snapshot chủ yếu hỏi permission
khi thấy cùng tool/input lặp liên tiếp. Không nên thay ladder hiện tại bằng cơ
chế đơn giản hơn.

### SSE replay contract phù hợp sản phẩm

`events.py` có snapshot không tiêu sequence, bounded subscriber queue, drop
subscriber chậm, và tách thought khỏi answer. Đây là durable UX phù hợp hơn việc
port nguyên message-part protocol dành cho IDE coding.

### Recovery phân biệt input overflow và output cap

`loop.py` compact input cho `ContextOverflow` và giảm reserve cho
`OutputCapExceeded`. Đây là invariant quan trọng mà OpenCode cũng tách overflow
khỏi transient retry.

## Nên học từ OpenCode

### 1. Tạo capability resolution plane rõ hơn

**Hiện trạng:** registry, definitions, toolsets, executor, untrusted wrapper,
display projection, và budget classification cùng tham gia dựng một tool.

**Bài học:** tạo một resolved-tool view duy nhất theo turn, gom declaration đã
kiểm chứng gồm schema, availability, external/store kind, concurrency safety,
permission/policy class, display metadata, và handler. Không cần plugin system
hay MCP nếu chưa có use case.

**Acceptance signal:** thêm tool mới không cần sửa bảng tên song song; contract
tests chứng minh executor, prompt schema, trace, budget, và UI projection đọc
cùng declaration.

### 2. Persist typed part/state thay vì suy ra từ text

**Hiện trạng:** event contract đã typed, nhưng durable transcript vẫn chủ yếu
xoay quanh turn/message/tool-call record của riêng sản phẩm.

**Bài học:** nếu cần resume, audit, hoặc richer replay, chuẩn hóa lifecycle
`pending/running/completed/error/interrupted` tại storage owner, không suy ra từ
event đã phát. Chỉ làm khi product requirement cần resume hoặc postmortem sâu;
hiện tại restart cố ý không resume turn.

**Acceptance signal:** database và SSE projection trả cùng terminal tool state
sau disconnect/restart mà không sửa semantic hiện tại.

### 3. Progressive instruction loading cho domain packs

**Hiện trạng:** prompt sections và tool schemas mang nhiều knowledge domain.

**Bài học:** tách catalog nhỏ khỏi body chi tiết cho các playbook như định giá,
technical signal, sector comparison, hoặc risk analysis. Nạp body khi intent hoặc
tool path cần, tương tự skill progressive disclosure; không nạp mọi playbook vào
mọi turn.

**Acceptance signal:** giảm input tokens mà Golden Question Set không giảm
grounding/completeness; không dựa vào subjective prompt review.

### 4. Deterministic prune trước lossy summary

**Hiện trạng:** `messages.py` dựng context và summary theo budget riêng.

**Bài học:** đo và ưu tiên các phép biến đổi lossless hoặc deterministic: bỏ
duplicate tool snippets, thay old full result bằng trace handle, bảo vệ recent
user intent và result đang được trích dẫn, rồi mới dùng LLM summary nếu vẫn vượt.

**Acceptance signal:** context tokens giảm; citation/source retention và answer
correctness không giảm trên replay corpus.

### 5. Provider-quirk owner tập trung

**Hiện trạng:** `src/core/llm` đã có client, recovery, error taxonomy, routing,
và metrics.

**Bài học:** tiếp tục giữ provider/model transforms ở boundary này. Không để
tool loop hiểu message-shape quirks. Bổ sung failure scope chỉ khi error corpus
chứng minh cùng status cần recovery khác nhau.

**Acceptance signal:** mỗi production error shape map tới typed cause và bounded
action; không có retry string matching mới trong agent loop.

### 6. Hidden specialist chỉ cho tác vụ phụ xác định

OpenCode dùng hidden agents cho title, summary, và compaction. Stock_Massive chỉ
nên dùng model phụ khi task có input/output contract nhỏ và đo được, chẳng hạn
thread title hoặc compaction summary. Không dùng mixture-of-agents cho answer
chính nếu chưa có uplift trên Golden Question Set.

**Acceptance signal:** specialist giảm cost/latency hoặc tăng retention với
confidence interval đủ; failure của specialist fail-open theo policy rõ.

## Không nên port

| OpenCode surface | Lý do từ chối hiện tại |
|---|---|
| HTTP server + SDK mới | FastAPI router/SSE đã là product server; thêm server lõi thứ hai tạo duplicate contract |
| Coding tools, LSP, patch, worktree | Ngoài threat model và domain outcome của Stock_Massive |
| Host shell và plugin npm | Tăng executable supply-chain risk, không tạo giá trị phân tích cổ phiếu |
| Generic MCP marketplace | Chỉ thêm khi có provider cụ thể và permission/data contract rõ |
| Background multi-agent | Shared data/tool budget và join semantics chưa có nhu cầu chứng minh |
| Full provider compatibility matrix | Ta cần các route đã chọn, không cần trả chi phí maintain mọi model family |
| OpenCode message schema nguyên bản | Event v2 hiện tại đã phù hợp UI và durable contract của ta |

## Khoảng cách thực sự cần đo

Trước khi đổi harness, thêm hoặc dùng các metric sau làm decision gate:

- grounding/completeness trên Golden Question Set;
- empty-after-tools và nudge recovery rate;
- invalid tool arguments và unknown tool rate;
- repeated-call warn/block/halt distribution;
- tool result bytes/tokens trước và sau context construction;
- context overflow, output-cap reduction, và compression convergence;
- provider retry count theo typed cause;
- SSE reconnect consistency và dropped subscriber rate;
- answer latency, model cost, và external data cost per successful turn;
- citation retention sau transcript trimming.

Không có baseline thì một refactor architecture không thể chứng minh là nâng
cấp.

## Thứ tự ưu tiên đề xuất

### P0 — giữ invariant hiện tại

- Không làm yếu one-call-one-result, SSE snapshot, budget arithmetic, typed
  recovery, hoặc repetition ladder.
- Chốt contract tests ở các owner hiện có trước mọi refactor.

### P1 — giảm drift giữa tool owners

- Audit registry/definitions/toolsets/executor/untrusted/display projections.
- Hợp nhất declaration chỉ nơi có duplicate fact đã chứng minh.
- Đo invalid arguments, external/store classification, và trace consistency.

### P2 — context efficiency có số đo

- Instrument input composition theo layer.
- Thêm deterministic prune có golden replay tests.
- Thử progressive domain packs sau khi có baseline.

### P3 — specialist hoặc subagent có điều kiện

- Chọn một task phụ nhỏ.
- So sánh single-agent và specialist về success, tokens, latency, và failure.
- Chỉ mở rộng nếu uplift vượt overhead và cancellation/permission contract rõ.

## Decision filter

Mỗi ý tưởng lấy từ OpenCode phải qua bốn câu hỏi:

1. Nó sửa failure mode nào đã thấy trong trace hoặc test?
2. Owner nào trong Stock_Massive phải thay đổi?
3. Metric nào chứng minh tốt hơn?
4. Có thể lấy invariant nhỏ hơn thay vì port subsystem không?

Nếu không trả lời được cả bốn, giữ nó trong research, không đưa vào code.
