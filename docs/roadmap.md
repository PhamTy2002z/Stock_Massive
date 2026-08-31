# Roadmap AI Harness — Stock_Massive

Tài liệu này là authority cho thứ tự phát triển sau pivot **harness-first**.
Mục tiêu sản phẩm hiện tại không còn là Signal Desk hay một engine phân tích
deterministic. Mục tiêu là một AI agent chứng khoán dùng web và tool, có vòng
lặp bền, context tốt, guardrail rõ và trả lời có bằng chứng ở chất lượng tương
đương hình dạng trong [`text.md`](../text.md).

`text.md` là **mẫu trải nghiệm**, không phải nguồn sự thật hay golden answer:
nó minh họa cách mở đầu bằng kết luận, giải thích chuyện gì đang xảy ra, nguyên
nhân, ý nghĩa, tác động và điều nhà đầu tư cần theo dõi. Mọi số, mốc giá và nguồn
trong output thật vẫn phải được agent kiểm chứng tại thời điểm trả lời.

Code và test sở hữu hành vi đang chạy. Roadmap sở hữu quyết định, dependency,
gate tốt nghiệp và thứ tự thực hiện. Các tài liệu trong `docs/Harness/` là
research/contract trước pivot; khi xung đột, roadmap này thắng.

## 1. Outcome contract

Stock_Massive phải trở thành một **web-first financial research agent** có thể:

1. hiểu câu hỏi và horizon người dùng thực sự hỏi;
2. lập kế hoạch tìm kiếm, tìm nhiều hướng song song và đọc các nguồn cần thiết;
3. phân biệt discovery (`web_search`) với retrieval (`fetch_url`);
4. tổng hợp bằng chứng thành câu trả lời rõ ràng, nêu mâu thuẫn và khoảng trống;
5. gắn claim trọng yếu với nguồn, thời điểm và mức chắc chắn;
6. tự phục hồi có giới hạn khi model, provider hoặc tool sai hợp đồng;
7. luôn settle Turn thành trạng thái typed, không để màn hình trắng;
8. giữ context hữu ích qua hội thoại dài mà không làm rơi intent, citation hay
   cặp tool-call/tool-result;
9. không tăng quyền vì prompt, nội dung web, memory, MCP hay child session;
10. đo chất lượng, cost và latency trên outcome thật trước khi mở capability mới.

Với câu hỏi phân tích chứng khoán, output tốt thường trả lời được năm ý trong
`text.md`: **đang xảy ra gì, vì sao, tại sao quan trọng, tác động ngắn/dài hạn,
và cần theo dõi gì**. Đây là rubric theo intent, không phải template bắt buộc cho
mọi câu hỏi.

## 2. Phạm vi mới

### Giữ và nâng cấp

- FastAPI là server lõi; Next.js là client của contract HTTP/SSE.
- Thread, Turn, message, tool call, usage, cancel và SSE replay.
- Web search/fetch, memory qua tool và attachment đọc-only khi còn đúng contract.
- One-call-one-result, bounded concurrency, budget arithmetic, typed recovery,
  repetition ladder và hai cửa terminal tập trung.
- SSRF protection, redirect/DNS validation, untrusted-content boundary và
  injection scan hiện có.
- Golden/eval web-first và operational telemetry có thể tái tạo.

### Xóa khỏi product path

- Mọi UI, state, event, API mode và persistence projection dành riêng cho
  Signal Desk/analysis board.
- Study registry/runner/template, Board DSL, widget catalog, frame buffer,
  compute sandbox và artifact render.
- Tool để đọc/tính Signal Field, indicator, series, statement hoặc local market
  store cho agent: `list_fields`, `get_field`, `query`, `compare_fields`,
  `get_series`, `compute`, `check_price_claim`, `list_studies`, `run_study`,
  `frame_from_evidence`, `render_signal_desk`.
- Prompt/playbook ép câu hỏi có số thành board hoặc ưu tiên dữ liệu local.
- Scheduler/backfill và code indicator/calculation chỉ phục vụ đường sản phẩm đã
  bỏ, sau khi reverse-dependency audit chứng minh không còn public owner khác.

### Không xây trong roadmap lõi

- Một chart/board/Study engine mới dưới tên khác.
- Shell, file-write, code execution, LSP, browser-computer-use hoặc plugin npm.
- Generic MCP marketplace và `trust: full` mặc định.
- Provider matrix rộng chỉ để đạt feature parity.
- Memory free-text tự chèn vào system prompt hoặc skill tự sửa policy.
- Broker/order execution, position sizing cá nhân hóa hoặc auto-trading.
- Multi-agent cho answer chính trước khi single-agent đạt gate.

## 3. Kiến trúc đích

```text
Next.js client
    │ HTTP + SSE projection
    ▼
FastAPI transport
    ▼
Durable Session / Turn / typed Part state          ← OpenCode spine
    ▼
Agent Loop + provider recovery + bounded budgets   ← Hermes runtime discipline
    ├── Context Engine
    ├── Resolved Capability Plane
    ├── Permission + Guardrail Plane
    ├── Tool Executor
    │     ├── web_search
    │     ├── fetch_url
    │     ├── session_search
    │     ├── remember_fact
    │     └── recall_facts
    └── Evidence / Claim Ledger                    ← finance upgrade
           ▼
       cited final answer

Cross-cutting: observability · eval · privacy · cost · cancellation
```

### Quy tắc dependency

1. Client chỉ đọc product contract; không suy diễn durable state từ animation.
2. Session/Turn không hiểu provider wire shape.
3. Agent loop chỉ nhận resolved capabilities, không biết registry cụ thể.
4. Mọi tool đi qua cùng schema, permission, budget, timeout, lifecycle và output
   policy; không có đường gọi tắt.
5. Tool result và nội dung web luôn là data không tin cậy, không phải instruction.
6. Evidence identity, publication time và retrieval time không bị mất khi trim,
   summary, persist hoặc render citation.
7. Guard heuristic có thể fail-open; authorization, tenant scope, SSRF, schema
   integrity và external side effect phải fail-closed.
8. Operational telemetry không mặc định lưu prompt, page body, memory hay hidden
   reasoning; trajectory giàu nội dung là artifact eval/debug có TTL riêng.

## 4. Conformance Hermes + OpenCode

“Dựa trên Hermes + OpenCode” nghĩa là bám đúng invariant và boundary đã chứng
minh, không chép toàn bộ sản phẩm coding-agent vào domain chứng khoán.

| Nguồn | Adopt | Điều chỉnh cho Stock_Massive |
|---|---|---|
| OpenCode | Server là core, client là projection | Giữ FastAPI/SSE hiện có; không dựng server thứ hai |
| OpenCode | Session/message/tool là typed durable state | Dùng Turn/part lifecycle của repo; chỉ thêm state thiếu cho replay/reconcile |
| OpenCode | Một capability path cho built-in/custom/MCP | Một resolved declaration duy nhất; hiện chỉ expose tool cần cho research |
| OpenCode | Permission `allow/ask/deny`, rule theo capability/resource | Default-deny capability lạ; không lấy default `* = allow` |
| OpenCode | Progressive rules/skills và deterministic prune trước summary | Domain pack nhỏ, nạp theo intent; không remote instruction mặc định |
| OpenCode | Subagent là child session có permission riêng | Conditional; deny của cha truyền xuống, global budget cho toàn cây |
| Hermes | Imperative model↔tool loop có retry/fallback/cancel | Giữ loop nhỏ, typed và phù hợp một web research lane |
| Hermes | Tool registry, synthetic error, stable result order | Bắt buộc one-call-one-result trên mọi failure path |
| Hermes | Parallel-read, barrier cho call không an toàn | Web read có thể song song; side effect tương lai serialize/idempotent |
| Hermes | Result preview/spill + budget toàn round | Prompt nhận preview có provenance; full body ở evidence store có TTL |
| Hermes | Error taxonomy theo recovery action | Phân biệt auth, rate, overload, timeout, context, output, policy, schema |
| Hermes | Bounded nudge và guard fail-open | Không để guard không chắc chắn làm mất câu trả lời |
| Hermes | Context theo stable/context/volatile, usage feedback, cache | Đo token thật; không tối ưu cache bằng cách làm mất evidence |
| Hermes | Content-light observer tách khỏi trajectory | Giữ privacy mặc định; trace giàu nội dung chỉ khi opt-in |
| Finance | — | Claim–evidence, `as_of`, publication lag, source conflict, uncertainty và suitability boundary |

Nguồn nghiên cứu nội bộ: [`docs/hermes/README.md`](hermes/README.md),
[`docs/opencode/README.md`](opencode/README.md) và
[`plans/reports/research-260827-2318-hermes-vs-opencode-harness.md`](../plans/reports/research-260827-2318-hermes-vs-opencode-harness.md).
Nguồn upstream chính: [Hermes architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture),
[Hermes agent loop](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop),
[Hermes tools runtime](https://hermes-agent.nousresearch.com/docs/developer-guide/tools-runtime),
[OpenCode tools](https://opencode.ai/docs/tools/),
[OpenCode permissions](https://opencode.ai/docs/permissions/) và
[OpenCode rules](https://opencode.ai/docs/rules/).

## 5. Baseline đang có

Các invariant sau là **Current** và phải sống qua đợt teardown:

- một Turn có deadline, tool-round/external-call cap và spend admission;
- executor trả đúng một result cho mỗi call, kể cả unknown, blocked, timeout,
  overflow và handler error;
- read-safe calls có thể fan-out song song và result quay về theo call order;
- provider error, context overflow và output cap có typed recovery khác nhau;
- repetition đi theo `allow → warn → block → halt`;
- cancel idempotent, mọi exit path settle qua terminal owner tập trung;
- SSE snapshot/replay và subscriber isolation;
- web fetch chặn SSRF/rebinding/redirect nguy hiểm;
- untrusted result bị giới hạn, quét injection và không được nâng thành policy;
- web-first golden corpus và grader cơ bản đã tồn tại.

Tool catalog hiện tại có đúng năm capability nêu trong sơ đồ trên. Attachment
đọc-only tiếp tục là input của Turn, không phải tool và không mở lại local
analysis runtime.

## 6. Lộ trình thực hiện

Nhãn: **Current** = có owner + test; **Target** = đã chốt, chưa đạt gate;
**Conditional** = chỉ mở khi dependency và số đo cho phép; **Rejected** = ngoài
scope, chỉ đảo khi có product decision mới.

### R0 — Teardown Signal Desk và local analysis engine — **Current**

**Outcome.** Sản phẩm chỉ còn chat/research surface. Không còn đường UI, prompt,
tool, event hoặc background job nào có thể tạo analysis board hay đọc/tính chỉ
báo cho agent.

**Work surfaces.**

- Frontend: xóa `apps/web/src/components/signal-desk/`; tháo board card,
  board view/menu/switcher, shell board state, `signal_desk.ready`, artifact
  loader/export và test/fixture/e2e sở hữu chúng.
- Agent API: bỏ `TurnMode="signal_desk"`, event/payload/absence handling và mọi
  branch auto-compose/publish/reopen dành cho board trong `apps/api/src/agent/`.
- Capability: xóa các tool analysis liệt kê ở §2 khỏi registry, toolsets, prompt,
  domain pack, display metadata, budget và contract tests.
- Analysis runtime: xóa `apps/api/src/studies/` và test/fixture chỉ sở hữu Study,
  frame, compute, Board DSL hay artifact.
- Data/calculation: audit consumer rồi xóa `apps/api/src/stocks/signals/`, daily
  backfill/scheduler/config và schema/model chỉ còn phục vụ indicator/Study.
- Persistence: dừng mọi write artifact trước; backup database rồi dùng migration
  riêng để retire schema/data khi đã chốt retention. Không drop dữ liệu trong
  cùng thay đổi với code-path teardown.
- Docs/eval: bỏ Signal Desk khỏi contract/golden navigation; giữ research cũ
  ngoài authority path nếu còn giá trị lịch sử.

**Kết quả.** Production path, contract và test hiện chỉ còn chat/research với
năm tool web + memory/session. Signal Desk, Study, board artifact, local
indicator/calculation và scheduler/backfill đã rời executable surface. Các bảng
hoặc cột lịch sử chưa bị drop trong thay đổi này: retirement dữ liệu cần một
quyết định retention, backup và migration riêng.

**Gate đã đạt.**

- `rg` trên production code không còn `signal_desk`, Study/Board DSL và tên tool
  analysis đã retire, ngoài migration/history được ghi chú rõ;
- tool catalog runtime chỉ expose web + memory/session capabilities đã duyệt;
- app chat, restore thread, stream answer, source list, cancel và reconnect xanh;
- API/web lint, typecheck, focused tests và build xanh;
- không còn scheduler gọi pipeline đã xóa; schema retirement được theo dõi như
  quyết định migration độc lập, không phải điều kiện mở R1.

### R1 — Evaluation contract cho câu trả lời đích — **Target**

**Outcome.** Chất lượng kiểu `text.md` trở thành corpus và rubric chạy được,
không còn là cảm giác khi đọc demo.

**Checklist.**

- Viết case family cho fact lookup, diễn biến tuần, outlook/horizon, event impact,
  support/resistance từ nguồn công khai, source conflict, thiếu dữ liệu và câu
  hỏi có tính khuyến nghị.
- Mỗi case đóng băng query, page snapshot, publication/retrieval time, accepted
  outcome properties và known traps; không đóng băng một tool trajectory duy nhất.
- Deterministic graders chấm settlement, citation URL, evidence identity,
  material numeric claim, temporal validity, refusal/policy và budget.
- Rubric judge chấm synthesis, cấu trúc theo intent, counterargument, uncertainty
  và decision utility; judge không chấm con số backend kiểm được.
- Artifact ghi code SHA, prompt/tool/model/config/data versions và trial count.

**Gate.** Hard dimensions phải đạt 100% trên corpus release: terminal settlement,
không citation giả, không claim số trọng yếu thiếu evidence, không dùng nguồn sau
`as_of`, không vượt permission/suitability. Threshold trade-off cho quality,
latency và cost chỉ khóa sau khi có baseline nhiều trial.

### R2 — Unified Capability Plane — **Target**

**Outcome.** Một declaration duy nhất quyết định model thấy tool nào và tool đó
được parse, authorize, budget, execute, trace, trim và hiển thị ra sao.

Resolved capability phải sở hữu: name/version, schema, description, availability,
handler, read/write effect, trust/data class, permission rule, idempotency,
concurrency/barrier, timeout/cost, output policy và display metadata.

**Gate.** Thêm hoặc bỏ một tool không cần sửa bảng tên song song; schema model
nhận đúng schema executor validate; unknown/invalid/denied/timeout/handler error
đều settle một typed result; read-safe parallelism giữ stable emission order.

### R3 — Durable Agent Loop và provider recovery — **Target**

**Outcome.** Loop bám semantics Hermes nhưng state bám session/typed-part của
OpenCode: model có thể sai, provider có thể lỗi, client có thể disconnect, nhưng
Turn luôn phục hồi có giới hạn hoặc kết thúc có lý do cụ thể.

**Checklist.**

- Chuẩn hóa lifecycle `pending → running → completed|error|denied|cancelled` cho
  model attempt và tool call; persist intent trước execute khi cần reconcile.
- Không tin `finish_reason` một mình: còn tool call chưa settle thì loop xử lý
  protocol trước khi stop.
- Error taxonomy map một-một sang bounded action: retry+jitter, wait, alternate
  route, context reduction, output-reserve reduction, nudge hoặc fail-closed.
- Bounded nudge cho malformed/empty/no-synthesis; hết budget trả partial answer
  trung thực kèm concrete blocker thay vì trắng màn hình.
- Cancellation truyền xuống model/tool; terminal write idempotent; orphan read
  call được reconcile, không tuyên bố exactly-once nếu chưa có idempotency.
- Mọi retry/child tương lai tiêu cùng deadline và cost envelope, không được cấp
  allowance mới.

**Gate.** Fault-injection cho timeout, rate limit, malformed call, empty output,
context overflow, output cap, cancel và disconnect đều settle đúng; 0 orphan
tool state; 0 duplicate external effect; semantic recovery pass golden cases.

### R4 — Context Engine — **Target**

**Outcome.** Model nhận đúng context cần cho step hiện tại, không phải toàn bộ
lịch sử và toàn bộ knowledge trên mọi request.

**Checklist.**

- Tách `stable` (identity/policy/tool protocol), `scoped` (intent/domain rules),
  `transcript/evidence` và `volatile` (time/user/Turn state).
- Ghi usage token thật từ provider để hiệu chỉnh estimate và quyết định overflow.
- Prune deterministic trước lossy summary: dedup source/snippet, collapse old
  result thành evidence handle, giữ recent intent và call/result pair.
- Summary có provenance, protected tail, cooldown/anti-thrash và recovery search;
  lỗi summary fail-open về context hợp lệ gần nhất.
- Đặt cache boundary theo prefix ổn định nếu route probe chứng minh hỗ trợ; đo
  cache read/write thay vì suy từ config.
- Nạp finance playbook/skill body theo intent hoặc tool path, không nhét toàn bộ
  domain vào mọi Turn.

**Gate.** Replay corpus giữ nguyên task success, cited evidence và user intent;
input token/cost giảm có confidence interval; context overflow hội tụ trong
bounded attempts; không tách tool call khỏi result.

### R5 — Permission, guardrails và web security — **Target**

**Outcome.** Capability được phép vì policy typed, không vì model tự khai hoặc
tool/server tự gắn nhãn an toàn.

**Checklist.**

- Permission rule `allow|ask|deny` theo capability/resource; no-match và unknown
  mặc định deny. `ask` chỉ tồn tại khi thật sự có side effect cần consent.
- Permission, approval, kill switch, sandbox và authorization là bốn cơ chế
  khác nhau; không dùng cái này thay cái kia.
- Giữ SSRF/DNS/redirect protections; thêm egress/domain policy và page-size/time
  budget trên mọi fetch path.
- Scan injection là risk signal không lọt vào model text; web/tool content không
  thể sửa policy, tool args, memory hoặc system instructions.
- Guard loop theo exact failure/same-tool/no-progress; warn sớm, halt theo budget;
  scanner/metrics lỗi không được làm mất answer.
- Auth, tenant/data scope, schema validator và side effect fail-closed; mất kênh
  approval không bao giờ auto-approve.

**Gate.** Adversarial suite phủ indirect injection, encoded/bidi payload, SSRF,
redirect, oversized result, permission bypass, repeated calls và secret leakage;
0 privilege escalation, 0 raw secret trong trace, benign corpus không bị block
quá threshold đã khóa từ baseline.

### R6 — Web Research + Finance Evidence — **Target**

**Outcome.** Agent đạt chất lượng trả lời đích chỉ bằng web research, tool loop
và reasoning của model; không cần indicator/store/Study engine.

**Checklist.**

- Planner tạo các query độc lập theo giá/diễn biến, sự kiện, doanh nghiệp/ngành
  và phản biện; executor fan-out search rồi fetch các trang đủ để kết luận.
- Source policy phân biệt primary filing/company/exchange, báo chí, aggregator
  và snippet; ranking/relevance không bị gọi nhầm là publisher trust.
- Evidence ledger giữ URL canonical, publisher, title, publication/retrieval
  time, quoted span/hash, entity/symbol, period, unit và source conflict.
- Claim ledger nối từng claim trọng yếu với evidence IDs; citation renderer chỉ
  render từ ledger, không nhận URL model tự gõ.
- Finance temporal rules xử lý `as_of`, phiên giao dịch, timezone, kỳ báo cáo,
  corporate action, đơn vị/tiền tệ và publication lag.
- Prompt dạy model phân biệt fact, inference và scenario; không biến headline,
  analyst target hay technical level của một nguồn thành certainty.
- Khi người dùng hỏi “có nên mua”, thiếu horizon/risk context thì vẫn được phân
  tích nhưng phải nói rõ giả định và không giả personalization.

**Gate.** Golden web-first đạt hard gates R1; source conflict và missing evidence
được nói thẳng; citation mở đúng trang hỗ trợ claim; answer usefulness đạt bar
đã baseline; không có import/runtime dependency vào local signal/calculation
engine.

### R7 — Memory và progressive domain knowledge — **Target**

**Outcome.** Agent nhớ điều hữu ích mà không biến memory thành instruction có
đặc quyền hoặc nguồn dữ kiện thị trường.

- Session search và cross-session memory chỉ qua tool có schema.
- Tách user preference/profile khỏi market evidence và system policy.
- Memory có provenance, owner, scope, created/updated time, expiry và delete path.
- Recall xung đột với evidence mới phải bị hạ ưu tiên và nêu mâu thuẫn.
- Domain catalog nhỏ được cache; body chi tiết nạp theo intent.
- Auto-write, self-editing skill và memory-to-system-prompt vẫn Rejected.

**Gate.** Memory isolation, delete, stale-conflict và injection tests xanh;
recall tăng task success trên replay mà không tăng unsupported-claim rate.

### R8 — Observability, cost và release gate — **Target**

**Outcome.** Có thể trả lời “agent đã làm gì, tại sao answer này tồn tại, lỗi ở
đâu và tốn bao nhiêu” mà không lưu chain-of-thought.

- Trace hierarchy: Turn → model attempt → context composition → tool lifecycle →
  evidence/claim → terminal outcome.
- Metric có denominator: success/incomplete/refused/cancelled, tool selection,
  invalid args, useful result, recovery, evidence coverage, latency/token/data
  cost per successful outcome và reconnect consistency.
- Content-light telemetry mặc định; trajectory sample được redact, access-control,
  TTL và delete.
- Prompt/tool/context/model/provider changes chạy affected golden/adversarial
  replay; loop/permission changes thêm fault-injection.
- Rollback/kill switch tồn tại cho capability và prompt release.

**Gate.** Mỗi release artifact tái tạo được; hard-dimension regression fail
closed; dashboard/trace không cần prompt body vẫn xác định được typed cause và
owner; cost được báo trên successful outcome, không trên raw Turn count.

### R9 — Delegation, MCP và side-effect tools — **Conditional**

Chỉ mở sau R1–R8 khi một workload độc lập chứng minh single-agent không đủ.

- Child là durable child session, fresh context, output schema fail-closed.
- Deny/data boundary của parent truyền xuống; child không tự nhận memory, secret,
  write tool hoặc quyền delegate tiếp.
- Depth, concurrency, total token/cost/deadline và cancellation bound toàn cây.
- MCP mặc định untrusted, allowlist capability, validate server/tool contract;
  server annotation không phải authorization.
- Side effect cần idempotency/reconcile và approval riêng.

**Gate.** Delegation uplift vượt overhead trên cùng corpus nhiều trial; 0 permission
escalation, orphan child và budget escape. Không đạt thì giữ single-agent và ghi
Rejected cho workload đó.

## 7. Dependency và thứ tự

```text
R0 teardown
   ▼
R1 eval contract  ◀ next
   ▼
R2 capability plane ─▶ R3 durable loop
                         ├─▶ R4 context
                         ├─▶ R5 guardrails
                         └─▶ R6 web + finance evidence
                               ▼
                         R7 memory/domain
                               ▼
                         R8 release gate
                               ▼
                         R9 conditional expansion
```

Observability và eval instrumentation được thêm trong từng phase; R8 hợp nhất
chúng thành release authority, không đợi đến cuối mới bắt đầu đo.

## 8. Definition of Done toàn roadmap

Pivot hoàn tất khi:

1. Không còn Signal Desk/Study/indicator/calculation path trong product runtime.
2. Chat UI là một client mỏng của durable Turn/SSE contract.
3. Mọi tool đi qua unified capability, permission, budget và lifecycle plane.
4. Loop phục hồi typed, bounded và không trả màn hình trắng.
5. Context dài giữ intent, evidence và protocol với cost đo được.
6. Web content không thể nâng quyền; mọi hard security boundary fail-closed.
7. Câu trả lời tài chính đạt hard evidence/temporal gates và rubric trải nghiệm
   lấy từ `text.md`.
8. Mọi thay đổi prompt/tool/model/context có replay artifact, cost và rollback.

## 9. Câu hỏi cần khóa khi phase tương ứng bắt đầu

1. Dữ liệu artifact/signal lịch sử giữ bao lâu trước migration retire schema?
2. Memory cross-session mặc định opt-in hay opt-out?
3. “Investment research” hay “personalized advice” là legal/product boundary
   chính thức của output?
4. Ai sở hữu human review cho finance correctness và suitability cases?
