# Roadmap — AI Agent for Investment (Stock_Massive)

Tài liệu này là authority cho scope sản phẩm và thứ tự phát triển. Code và test
sở hữu hành vi đang chạy; roadmap sở hữu quyết định, dependency, gate tốt
nghiệp và thứ tự thực hiện. Các tài liệu trong `docs/Harness/` là
research/contract trước pivot; khi xung đột, roadmap này thắng.

**Mục tiêu sản phẩm:** Stock_Massive trở thành một **AI Agent for Investment**
cho nhà đầu tư Việt Nam, với hình dạng sản phẩm là **Evidence Desk** (§1): một
bàn kiểm chứng nơi câu trả lời là cấu trúc *kết luận ← claim ← bằng chứng ←
thời điểm* mà người dùng bóc được từng lớp. Ưu tiên đã chốt: **chất lượng
trước tốc độ và trước chi phí** — memo được phép chậm nhiều phút và tiêu nhiều
lượt model, miễn là quá trình hiển thị trung thực theo thời gian thực và kết
quả đạt hợp đồng sự thật (§2).

**Nguồn học kiến trúc:**

- **Hermes Agent là nguồn học chính** cho runtime core: vòng lặp model↔tool có
  retry/fallback/cancel, error taxonomy map sang typed recovery, bounded nudge
  thay vì màn hình trắng, guard fail-open, context layering, kỷ luật budget và
  observability content-light.
- **OpenCode là nguồn học cho tầng advanced**: durable typed session/state (đã
  áp dụng làm spine), unified capability plane, permission `allow/ask/deny`,
  progressive rules/skills, hidden specialist cho tác vụ phụ có contract nhỏ,
  và — khi roadmap mở gate — **code execution trong sandbox**.
- Học invariant và boundary đã chứng minh, không copy sản phẩm coding-agent.
  Tầng finance evidence là phần tự xây, không có nguồn để port.

**Về `text.md`:** file mẫu này đã bị xoá khỏi repo và **không phải nguồn sự
thật**. Không transcript mẫu nào là golden answer. Chất lượng được sở hữu bởi
§2/§3 và corpus eval Phase 1.

## 1. Sản phẩm đích: Evidence Desk

### Bốn job

1. **Stress-test luận điểm (hero):** "Tôi định mua X vì A, B, C — kiểm chứng
   giúp tôi." Agent tách tiền đề, kiểm từng cái, chủ động săn phản chứng.
2. **Memo sự kiện:** "X giảm ba phiên, chuyện gì vậy?" — memo theo rubric §3.
3. **Kiểm chứng dữ kiện:** đối chiếu một con số/claim với nguồn gốc.
4. **Phân xử mâu thuẫn nguồn:** hai nguồn lệch nhau — hiển thị cả hai và giải
   thích vì sao lệch.

Bốn job dùng chung một engine (Phase 6); khác nhau ở intent frame và render.

### Năm object cốt lõi

- **Memo:** verdict tổng → rubric §3 → phản chứng → cần theo dõi; luôn có
  `as_of` banner.
- **Claim:** khẳng định trọng yếu có loại `fact | inference | scenario`, nối
  evidence IDs, có trạng thái kiểm chứng.
- **Evidence card:** chip citation mở panel: quoted span highlight, publisher,
  publication time, retrieval time, link gốc, conflict note.
- **Verdict tiền đề:** đúng ba trạng thái **Đứng vững / Lung lay / Không kiểm
  chứng được**. "Đúng một phần" biểu đạt bằng Lung lay kèm giải thích; không
  thêm trạng thái thứ tư để giữ eval đơn giản.
- **Watch item / dossier:** "cần theo dõi gì" thành mục có mốc thời gian,
  bấm để chạy lại và đối chiếu memo cũ. Watch item **chỉ sống trong memo và
  thread (dossier theo `symbols[]`)** — không có surface watchlist toàn cục;
  đường Signal Desk/watchlist đã retire giữ nguyên.

### Elicitation — hỏi lại người dùng có kỷ luật

Khi thiếu dữ kiện **không thể khám phá** (horizon, giá vốn, mua mới hay trung
bình giá, mục đích), agent được hỏi lại bằng **question card render từ typed
part**, theo bốn kỷ luật:

1. Chỉ hỏi điều web không trả lời được; hỏi thứ discoverable là defect.
2. Scout-then-ask: research sơ bộ trước, câu hỏi mang evidence chip trong mình.
3. Budget cứng enforce ở backend: tối đa 1 vòng trước memo, tối đa 3 câu, mỗi
   câu 2–4 lựa chọn single-select; vòng hai chỉ khi câu trả lời mở nhánh mới.
4. Luôn có "Bỏ qua — dùng giả định mặc định"; skip thì memo vẫn chạy và giả
   định in rõ đầu memo. Không tồn tại card chặn đường.

Kiến trúc: **câu hỏi là typed part kết thúc Turn** (Turn settle terminal như
mọi Turn; loop hỏi–đáp là loop hội thoại, không phải state treo trong Turn).
Ba trạng thái persist: `answered | skipped | superseded` (user gõ composer
thay vì bấm → card mờ). Schema part có cờ `multi_select` từ v1; UI multi-select
làm sau. Câu hỏi phải rẽ nhánh kết luận — chấm được ở Phase 1.

## 2. Hợp đồng sự thật

"Luôn đúng" không phải cam kết khả thi. Cam kết của sản phẩm tách theo bốn lớp
với mức đảm bảo khác nhau:

| Lớp | Đảm bảo | Cơ chế |
|---|---|---|
| 1. Trung thực với nguồn (claim khớp quoted span) | **Cơ học, hard gate 100%** | Render-only-from-ledger + verifier pass |
| 2. Nguồn nói thật | Bound, không tuyệt đối | Source policy + luật đa nguồn |
| 3. Suy luận hợp lý | Không đảm bảo — dán nhãn + phản biện | Claim typing + counterevidence pass |
| 4. Dự báo | Không ai đảm bảo được | Nhãn scenario, cấm certainty |

**Cơ chế bắt buộc:**

- **Render-only-from-ledger:** số/URL không có evidence ID thì không render
  được về mặt kỹ thuật. Chặn bịa ở tầng code, không ở tầng prompt.
- **Verifier pass context sạch:** một lượt model độc lập (hidden specialist,
  không nhiễm context research) đối chiếu từng claim trọng yếu với quoted
  span. Rớt → hạ xuống "không kiểm chứng được" hoặc loại. **Verifier lỗi
  provider = fail-closed cho nhãn đã-kiểm-chứng, fail-open cho việc trả lời:**
  memo vẫn ra, chip rơi về trạng thái chưa kiểm chứng — không bao giờ render
  claim chưa kiểm như đã kiểm, cũng không bao giờ vì verifier chết mà trắng
  màn hình.
- **Luật đa nguồn:** số trọng yếu cần ≥2 nguồn độc lập *hoặc* 1 nguồn primary
  (filing/CBTT/IR); chỉ có 1 nguồn aggregator → render kèm nhãn "một nguồn".
- **Temporal validity:** không dùng nguồn sau `as_of`; publication lag và
  phiên giao dịch xử lý theo finance temporal rules.
- **Quyền từ chối là đòn bẩy precision:** "không đủ bằng chứng" là outcome
  hạng nhất, được thiết kế UI riêng, không phải lời xin lỗi.

**Metric công bố được (đo ở Phase 1, giám sát ở Phase 9):** fabrication rate
lớp 1 = 0% (hard gate); disclosure conflict/thiếu dữ liệu/nhãn suy luận =
100%; material-claim accuracy trên corpus có ground truth = con số đo nhiều
trial, chỉ công bố sau khi đo; production có sampling audit người review và
nút "báo sai" trên từng claim — lỗi xác nhận thành case corpus mới.

## 3. Rubric chất lượng câu trả lời

Câu hỏi phân tích chứng khoán: output tốt trả lời năm ý — **đang xảy ra gì,
vì sao, tại sao quan trọng, tác động ngắn/dài hạn, cần theo dõi gì** — cấu
trúc theo intent, không phải template bắt buộc. Kèm theo: mở đầu bằng kết
luận; phân biệt fact/inference/scenario; không biến headline, analyst target
hay technical level một nguồn thành certainty; nêu thẳng conflict và khoảng
trống; thiếu horizon/risk context vẫn phân tích nhưng in rõ giả định, không
giả personalization. Rubric tự chứa, không tham chiếu transcript mẫu nào.

## 4. Outcome contract

Agent phải: (1) hiểu câu hỏi, horizon và mức rủi ro thật sự được hỏi; (2) lập
kế hoạch và research nhiều hướng song song; (3) phân biệt discovery
(`web_search`) với retrieval (`fetch_url`); (4) tổng hợp thành phân tích nêu
mâu thuẫn và khoảng trống; (5) gắn claim với nguồn, thời điểm, mức chắc chắn;
(6) tự phục hồi có giới hạn khi model/provider/tool sai hợp đồng; (7) luôn
settle Turn typed, không màn hình trắng; (8) giữ context dài không rơi intent,
citation, cặp call/result; (9) không tăng quyền vì prompt, web, memory, MCP
hay child session; (10) đo chất lượng/cost/latency trên outcome thật trước khi
mở capability mới; (11) hỏi lại user đúng kỷ luật §1 khi thiếu dữ kiện
non-discoverable; (12) sau gate Phase 11: chạy tính toán trong sandbox và phân
biệt số agent tính với số trích nguồn.

Bậc thang năng lực: **Evidence Desk (Phase 1–9)** → scale-out (Phase 10, theo
usage) → compute sandbox (Phase 11) → delegation/MCP (Phase 12). Ranh giới
theo `PRODUCT.md`: research và decision support; không đặt lệnh; không
personalized advice khi chưa có quyết định product/legal và human-approval
flow riêng.

**Chính sách chi phí và tốc độ (đã chốt):** chất lượng trước; envelope
model/deadline hào phóng theo lane; bound tồn tại để *chấm dứt có lý do*
(chống loop lú, repetition), không phải để tiết kiệm. Phase 9 đo cost per
successful outcome làm **đồng hồ định giá**, không phải phanh.

## 5. Phạm vi

### Giữ và nâng cấp

- FastAPI server lõi; Next.js là client của contract HTTP/SSE.
- Thread, Turn, message, tool call, usage, cancel, SSE replay.
- Web search/fetch, memory qua tool, attachment đọc-only.
- One-call-one-result, bounded concurrency, budget arithmetic, typed recovery,
  repetition ladder, hai cửa terminal tập trung.
- SSRF/redirect/DNS protections, untrusted-content boundary, injection scan.
- Nền golden web-first hiện có tại `apps/api/golden` (runner đóng băng web
  tại seam `WebLane.read`; run nửa xanh chấm `incomplete`, không phải pass
  thấp) và telemetry tái tạo được. Harness eval cũ tại `apps/api/eval` đã
  xoá — Phase 1 mở rộng golden, không dựng lại đường cũ.

### Đã xóa (Phase 0, hoàn tất)

Signal Desk/analysis board UI-state-event-API; Study/Board DSL, widget
catalog, frame buffer, compute sandbox cũ, artifact render; tool đọc/tính
indicator/series/statement/local store; prompt ép board; scheduler/backfill
của đường đã bỏ.

### Không xây trong roadmap lõi

- Chart/board/Study engine mới dưới tên khác; catalog chỉ báo built-in; local
  market store cho agent; watchlist surface toàn cục.
- Shell trên host, file-write ngoài sandbox, LSP, browser-computer-use,
  plugin npm.
- Generic MCP marketplace, `trust: full` mặc định, provider matrix rộng.
- Memory free-text tự chèn system prompt; skill tự sửa policy; hồ sơ rủi ro
  do model suy ra (vừa vướng PDPL vừa vượt ranh advice).
- Broker/order execution, position sizing cá nhân hóa, auto-trading.
- Multi-agent cho answer chính trước khi single-agent đạt gate.

Code execution không bị cấm tuyệt đối: tồn tại duy nhất dạng Conditional
Phase 11 trong sandbox, qua đúng capability/permission plane.

## 6. Kiến trúc đích

```text
Next.js client  (memo · verdict card · citation chip/Inspector · timeline
    │            · question card · dossier — projection của typed contract)
    │ HTTP + SSE
    ▼
FastAPI transport
    ▼
Durable Session / Turn / typed Part state            ← OpenCode spine
  (answer · thought · progress · question · claim/citation parts)
    ▼
Intent Router → Lane profile (light | deep)          ← trần round/deadline/pass
    ▼
Agent Loop + provider recovery + bounded budgets     ← Hermes discipline
    ├── Context Engine
    ├── Resolved Capability Plane
    ├── Permission + Guardrail Plane
    ├── Tool Executor
    │     ├── web_search · fetch_url
    │     ├── session_search · remember_fact · recall_facts
    │     └── execute_code (sandbox)                 ← Conditional, Phase 11
    ├── Deep-lane pipeline: research → counterevidence → verification
    │     (verifier = hidden specialist, context sạch)
    └── Evidence store hai tầng + Claim Ledger       ← finance core
          ├── tầng cache sản phẩm: nội dung web công khai, share toàn hệ
          │   thống theo canonical URL + cửa sổ as_of, retention riêng
          └── tầng trajectory artifact: riêng tư, TTL eval/debug
           ▼
       cited final answer (chỉ render từ ledger)

Cross-cutting: observability · eval · privacy · cost · cancellation
```

### Quy tắc dependency

1. Client chỉ đọc product contract; không suy diễn durable state từ animation.
2. Session/Turn không hiểu provider wire shape.
3. Agent loop chỉ nhận resolved capabilities, không biết registry cụ thể.
4. Mọi tool — kể cả `execute_code` tương lai — đi qua cùng schema, permission,
   budget, timeout, lifecycle, output policy; không có đường gọi tắt.
5. Tool result, nội dung web, output sandbox là data không tin cậy.
6. Evidence identity, publication time, retrieval time không bị mất khi trim,
   summary, persist hay render.
7. Guard heuristic được fail-open; authorization, tenant scope, SSRF, schema
   integrity, sandbox isolation, external side effect fail-closed. Nhãn
   "đã kiểm chứng" fail-closed; việc trả lời fail-open.
8. Evidence store hai tầng: tầng cache sản phẩm chứa **duy nhất nội dung web
   công khai** (share được, không dính user data); thread, giả định elicitation,
   memo, trajectory giàu nội dung là dữ liệu riêng tư — telemetry mặc định
   content-light, trajectory artifact có TTL/access-control riêng.
9. Progress event map 1-1 với sự kiện thật của loop; cấm stage giả bấm giờ.

## 7. Nguồn học: adopt và điều chỉnh

### Hermes — runtime core (nguồn học chính)

| Adopt | Điều chỉnh |
|---|---|
| Imperative loop retry/fallback/cancel | Loop nhỏ, typed, theo lane profile |
| Tool registry, synthetic error, stable order | One-call-one-result mọi failure path |
| Parallel-read + barrier | Web read song song; side effect serialize |
| Result preview/spill + budget round | Preview có provenance; full body ở evidence store |
| Error taxonomy theo recovery action | auth/rate/overload/timeout/context/output/policy/schema |
| Bounded nudge, guard fail-open | Hết budget → partial answer trung thực |
| Context stable/scoped/volatile + usage feedback | Đo token thật; không mất evidence vì cache |
| Content-light observer | Trace giàu nội dung chỉ opt-in |

Không bê: terminal coding agent, TUI, gateway đa nền tảng, 40+ shell tool,
fallback 7 tầng. Hermes không có grader chất lượng — Phase 1 tự dựng.

### OpenCode — spine và tầng advanced

| Adopt | Điều chỉnh |
|---|---|
| Server là core, client là projection | Giữ FastAPI/SSE; không server thứ hai |
| Typed durable session/part | Turn/part lifecycle của repo |
| Một capability path | Một resolved declaration duy nhất |
| Permission allow/ask/deny | Default-deny capability lạ |
| Progressive rules/skills, prune trước summary | Domain pack nạp theo intent |
| Hidden specialist cho tác vụ phụ nhỏ | Verifier, title, compaction — contract nhỏ đo được |
| Sandbox code execution | Phase 11; ephemeral, không egress mặc định |
| Subagent là child session | Phase 12; deny truyền xuống, budget toàn cây |

### Finance layer — tự xây

Claim–evidence ledger, `as_of`/phiên/timezone, publication lag, corporate
action, đơn vị/tiền tệ, source conflict, uncertainty, suitability boundary.
Không có harness nào để port nguyên tầng này, nhưng từng mảnh có nguồn học
pattern — xem bảng dưới.

### Nguồn học pattern theo phase (không phải nguồn harness thứ ba)

Hermes và OpenCode vẫn là hai nguồn học duy nhất cho harness core; các đối
thủ coding-agent khác (Codex, Claude Code, OpenHands, LangGraph…) đã được
đối chiếu trong `docs/hermes/` và `docs/opencode/` và không mang lại thứ
Evidence Desk thiếu. Các hệ thống dưới đây là **nguồn học pattern ở mức
phase plan**: học shape đã chứng minh, không port code, không thêm
dependency, và không adopt cơ chế trust citation-by-prompt của chúng (hợp
đồng sự thật §2 mạnh hơn). Phase plan của phase tương ứng thêm bước scout
nguồn này trước khi thiết kế phần liên quan.

| Nguồn | Phase | Học gì |
|---|---|---|
| STORM / Co-STORM (Stanford) | P6 | Perspective-guided question generation — bản mẫu cho counterevidence pass; đa góc nhìn tăng coverage có số đo |
| GPT Researcher | P6 | Planner→executor fan-out nhỏ gọn; per-source summary giữ URL |
| Open Deep Research (HuggingFace) | P6 | Vòng browsing đo trên GAIA — tham chiếu cho ngưỡng "fetch đủ để kết luận" |
| SAFE (DeepMind) | P6 | Verifier pass: tách claim → search độc lập → chấm từng claim, nhiều trial; các failure mode đã biết của claim decomposition |
| FacTool / RARR | P6 | Biến thể claim-extraction → retrieval → verdict/revise; tham chiếu cho chính sách rớt verify → hạ nhãn hoặc loại |
| Anthropic Citations API | P6 | Span-grounding cơ học ở tầng provider — cùng triết lý render-only-from-ledger; probe như named assumption (gateway đa model có thể không hỗ trợ) |
| Inspect AI (UK AISI) | P1 | Tách task/solver/scorer; epochs = multi-trial mặc định; log viewer đọc lại từng trial — pattern khi mở rộng `grade.py`, không dựng framework mới |
| promptfoo / Braintrust | P1 | Gate hồi quy trong CI và artifact versioning cho release corpus |
| Temporal / Restate | P3 | Từ vựng persist-intent-before-effect, idempotent terminal write — chỉ khái niệm, không thêm runtime |
| OpenTelemetry GenAI semconv (+ Langfuse) | P9 | Chuẩn đặt tên trace Turn → attempt → tool, tương thích content-light mặc định |

Đã xét và loại: AutoGen/CrewAI/LangGraph-as-runtime (tạo dispatch path thứ
hai, vi phạm quy tắc dependency §6.3; multi-agent bị chặn trước gate P12),
Perplexity-style render (citation không verify — anti-pattern của §2),
MindSearch (verdict reference-only tại
[`docs/research/mindsearch-alpha-desk.md`](research/mindsearch-alpha-desk.md)).

Nguồn nội bộ: [`docs/hermes/README.md`](hermes/README.md),
[`docs/opencode/README.md`](opencode/README.md),
[`plans/reports/research-260827-2318-hermes-vs-opencode-harness.md`](../plans/reports/research-260827-2318-hermes-vs-opencode-harness.md).
Upstream: [Hermes architecture](https://hermes-agent.nousresearch.com/docs/developer-guide/architecture),
[Hermes agent loop](https://hermes-agent.nousresearch.com/docs/developer-guide/agent-loop),
[Hermes tools runtime](https://hermes-agent.nousresearch.com/docs/developer-guide/tools-runtime),
[OpenCode tools](https://opencode.ai/docs/tools/),
[OpenCode permissions](https://opencode.ai/docs/permissions/),
[OpenCode rules](https://opencode.ai/docs/rules/),
[MCP elicitation](https://modelcontextprotocol.io/specification/draft/client/elicitation)
(mô hình accept/decline/cancel cho question card).

## 8. Baseline đang có

Invariant **Current**, mọi phase phải giữ: Turn có deadline + tool-round/
external-call cap + spend admission; executor một result mỗi call trên mọi
failure path; fan-out theo call order; typed recovery tách overflow/output
cap/provider error; repetition `allow → warn → block → halt`; cancel
idempotent, exit qua terminal owner tập trung; SSE snapshot/replay; SSRF/
rebinding/redirect protections; untrusted result bị cap + quét injection.
Tool catalog đúng năm capability web + memory/session. Attachment là input
của Turn, không phải tool.

**Đã verify trực tiếp trong code (2026-09-01):** năm tool khai báo tại
`toolsets.py`; `MAX_TOOL_ROUNDS = 4` và turn deadline trong `loop.py` (trở
thành giá trị của lane light — deep lane nâng qua lane config Phase 3); ladder
trong `guardrails.py`; snapshot/replay atomic trong `events.py`; hai cửa
terminal `_finish`/`_finish_bare` trong `turns.py`; SSRF `is_global` + DNS
pinning + redirect re-validation trong `tools/web.py`. Nền có sẵn cho phase
sau: module `evidence/` (contracts, documents, numbers, validation — nền Phase
6), endpoint flag/helpful theo message trong `flag_router.py` (nền nút "báo
sai" Phase 7/9), golden runner `apps/api/golden/run.py` (nền Phase 1).

**Đo được trên baseline Phase 1 (2026-09-01), là ràng buộc cho phase sau:**
`published_at` rỗng trên **0/981** source — provider search không trả ngày công
bố và không có bước trích ngày từ nội dung trang, nên publication lag của §2 là
thứ Phase 6 phải *tạo ra* chứ không phải đọc sẵn. Ranh giới research/advice giữ
được ở câu hỏi hỏi thẳng "nên mua mã nào" nhưng mất ở câu hỏi phân bổ vốn: cả
ba trial trả lời bằng tỷ trọng và số tiền cụ thể. Trần egress per-Turn chạm khi
sáu Turn chạy song song — dữ liệu đầu vào cho egress budget hai tầng Phase 5.

## 9. Nguyên tắc thi công

Roadmap sở hữu quyết định và gate; nó cố tình không nói file nào, hàm nào.
Tầng giữa roadmap và code là **phase plan**, và các luật dưới đây tồn tại để
khi thực tế va vào roadmap thì có protocol xử lý, thay vì lật kèo ngầm.

### Gate phải chạy được

Mọi gate quy được về một lệnh chạy được hoặc một metric có ngưỡng số. Gate
không quy được là **bug của roadmap**: sửa roadmap trước khi viết code. Báo
"không đạt" chỉ hợp lệ ở dạng *gate X, số đo Y, blocker Z* — không nhận
"cách này không tốt" như một lý do dừng.

### Preflight trước khi mở phase

Mỗi phase mở bằng một phase plan trong `plans/` (theo naming convention của
repo) và phải qua bốn câu:

1. Mỗi gate của phase đã có lệnh/test/metric chạy được chưa?
2. Mọi thứ phase này giả định phase trước để lại đã **verify trong code
   thật** chưa — không tin nhãn Done suông?
3. Unknown discoverable → scout ngay trong lúc plan; unknown không
   discoverable → ghi thành named assumption kèm fallback ("nếu sai thì làm
   gì").
4. Đường lùi nếu giữa phase phải dừng là gì?

Trượt câu nào → phase chưa ready: sửa plan, không lao vào code.

### Luật phản biện quyết định

Quyết định đã ghi trong roadmap kèm căn cứ **chỉ được thách thức bằng bằng
chứng mới** — thực tế code, số đo, hành vi provider — không bằng lo ngại trừu
tượng hay khẩu vị. Thách thức = dừng, viết deviation report (quyết định gốc →
bằng chứng mới → trade-off → các phương án) vào `plans/reports/`, chờ product
owner quyết. Không bao giờ tự đảo rồi báo sau. Roadmap giữ thẩm quyền bằng
cách được **amend tường minh**, không phải bằng cách bất biến hay bị bypass.

### Cửa một chiều và hai chiều

- **Hai chiều** (đổi rẻ — agent được đề xuất và điều chỉnh trong phạm vi
  phase): hình dạng field của part, giá trị lane config, ngưỡng budget, cấu
  trúc module nội bộ, copy UI.
- **Một chiều** (dừng và chờ người quyết, bất kể phase): public HTTP/SSE
  contract, drop/migrate dữ liệu, ranh giới pháp lý research/advice, default
  permission, thêm capability ngoài catalog, thay đổi hợp đồng sự thật §2.

## 10. Lộ trình theo phase — triển khai tuần tự

Nhãn: **Done** / **Target** / **Conditional**. Phase sau chỉ mở khi gate
phase trước xanh. Mỗi phase giữ chat UI hiện có xanh (client là projection —
contract đổi tới đâu, projection theo tới đó, không gộp UI lớn vào phase
backend).

### Khả năng mở khóa theo phase

Bảng quản trị tính năng: gate phase nào xanh thì AI/hệ thống có thêm đúng
những gì — không có khả năng nào xuất hiện ngoài bảng này.

| Phase xanh | AI/hệ thống có thêm |
|---|---|
| P0 (done) | Agent chat web-research 5 tool, trả lời có nguồn cơ bản trên surface sạch |
| P1 (done) | Chưa thêm tính năng user-facing — thêm khả năng **biết mình sai ở đâu**: bảng điểm chất lượng chạy một lệnh; mọi thay đổi sau đều có số đo trước/sau |
| P2 | Quản trị catalog tính năng bằng declaration: thêm/gỡ/bật/tắt một capability qua đúng một khai báo + permission, không sửa code rải rác |
| P3 | Turn bền và trung thực: phục hồi lỗi provider theo loại, tiến trình thật hiển thị realtime, contract question card sẵn sàng, khung lane light/deep |
| P4 | Hội thoại dài không xuống cấp: dossier nhiều memo vẫn giữ intent, citation, evidence — điều kiện cho user dùng lâu dài |
| P5 | Được phép tăng tự chủ an toàn: fan-out research rộng hơn mà injection/SSRF/permission đã có adversarial suite chặn lưng |
| P6 | **Khả năng lõi của sản phẩm:** deep memo 3-pass — stress-test luận điểm, memo sự kiện, kiểm số, phân xử nguồn; claim đã verify, citation thật, biết từ chối |
| P7 | User nhìn thấy và thao tác được mọi thứ: verdict card, evidence card, timeline ba hồi, question card, dossier/watch item, nút báo sai |
| P8 | Agent nhớ có consent: hồ sơ giả định opt-in (không hỏi lại điều đã khai), domain knowledge nạp theo intent |
| P9 | Quản trị release: dashboard chất lượng/chi phí per outcome, sampling audit, kill switch + rollback cho từng capability và prompt |
| P10 | Chịu tải đông user: evidence cache dùng chung, coalescing câu hỏi nóng, queue giờ cao điểm, tenant envelope cho B2B |
| P11 | Agent tự viết + chạy tính toán định lượng trong sandbox; số agent tính có provenance, phân biệt với số trích nguồn |
| P12 | Ủy quyền có kiểm soát: subagent/MCP/side-effect trong boundary cha, budget toàn cây |

### Phase 0 — Teardown Signal Desk và local analysis — **Done**

Production path chỉ còn chat/research với năm tool web + memory/session.
Schema/data lịch sử chưa drop: retirement là quyết định migration riêng,
không chặn Phase 1.

### Phase 1 — Evaluation contract — **Done (2026-09-01)**

**Outcome.** §2 và §3 thành corpus + grader chạy được, nhiều trial là mặc
định (chính sách chi phí §4 đã mở khóa). Mở rộng nền `apps/api/golden` hiện
có (`run.py` + `grade.py` + `web_first.json`), không dựng framework mới.

**Checklist.**

- Case family theo bốn job §1: thesis-check (tách tiền đề, verdict ba trạng
  thái, phản chứng), event memo, fact verification, source conflict; cộng
  fact lookup, diễn biến tuần, outlook, thiếu dữ liệu, câu khuyến nghị.
- Family **elicitation quality**: chấm cả over-ask (hỏi thứ discoverable, hỏi
  không rẽ nhánh kết luận) lẫn under-ask (âm thầm giả định sai điều trọng yếu).
- Family **material-claim accuracy** có ground truth đóng băng — nơi con số
  "% đúng" được sinh ra một cách trung thực.
- Mỗi case đóng băng query, page snapshot, publication/retrieval time,
  accepted outcome properties, known traps; không đóng băng một trajectory;
  không transcript mẫu nào là golden answer.
- Deterministic graders: settlement, citation URL, evidence identity, material
  numeric claim, temporal validity, refusal/policy, budget, nhãn đa nguồn.
- Rubric judge: synthesis, cấu trúc theo intent, chất lượng phản biện,
  uncertainty, decision utility; judge không chấm số backend kiểm được.
- Artifact ghi code SHA, prompt/tool/model/config/data versions, trial count.
- Phase plan scout nguồn pattern §7 trước khi thiết kế grader mới (Inspect
  AI cho cấu trúc solver/scorer/epochs; promptfoo/Braintrust cho regression
  gate) — chỉ học pattern, ràng buộc "không dựng framework mới" giữ nguyên.

**Gate.** Toàn corpus chạy bằng **một lệnh**, artifact in pass/fail theo từng
dimension; run nửa xanh là `incomplete`. Hard dimensions 100% trên corpus
release: terminal settlement, 0 citation giả, 0 claim số trọng yếu thiếu
evidence, 0 nguồn sau `as_of`, 0 vượt permission/suitability. Baseline nhiều
trial có confidence interval trước khi khóa threshold quality/latency/cost.

**Kết quả và amendment (2026-09-01).** Corpus `release-v1` (40 case, 11 family)
chạy bằng `make golden-release`; baseline 3 trial tốn $3,47, 120/120 Turn
terminal, artifact + report tại `apps/api/golden/artifacts/`, số đo đầy đủ tại
[`plans/reports/phase-01-260901-release-baseline.md`](../plans/reports/phase-01-260901-release-baseline.md).

Phase đóng ở phần nó sở hữu — **hợp đồng đo lường**: một lệnh, pass/fail theo
từng dimension kèm Wilson CI, run nửa xanh là `incomplete`, artifact ghi đủ
provenance, threshold soft chưa khoá vì mới có một baseline.

Mệnh đề "hard dimension 100%" **không đóng ở đây, và đó là amendment tường
minh**: nó là thuộc tính của *hệ thống được đo*, không phải của bộ đo, và Phase
6 đã khai đúng nó trong gate của mình ("Golden Phase 1 đạt hard gates"). Đọc
theo cách cũ thì P1 và P6 chặn lẫn nhau. Trạng thái đo được, mỗi dòng có chủ:

| Hard dimension | Baseline | Chủ sở hữu |
|---|---|---|
| settlement · citation_url · budget | 100% | giữ, hồi quy chặn ở P9 |
| refusal_policy | 4/6 — hai case đưa lời khuyên phân bổ | prompt P6 + ranh giới pháp lý §13.3 (P7) |
| evidence_identity | 29/32 — source thiếu title | evidence card P6/P7 |
| material_claim | BLIND — chưa đóng băng ground truth | P6 |
| temporal_validity | BLIND — **0/981 source có publication time** | source policy P6 |

Hai dòng BLIND là phát hiện, không phải nợ kỹ thuật của bộ đo: `published_at`
không tồn tại ở bất kỳ đâu trong pipeline hôm nay, nên luật temporal validity
của §2 chưa đo được. Gate coi hard dimension không quyết định được là `BLIND`
chứ không phải xanh, nên không phase nào đi qua nó bằng cách im lặng.

### Phase 2 — Unified Capability Plane — **Done (2026-09-01)**

**Outcome.** Một declaration duy nhất quyết định model thấy tool nào và tool
được parse, authorize, budget, execute, trace, trim, hiển thị ra sao.

Resolved capability sở hữu: name/version, schema, description, availability,
handler, read/write effect, trust/data class, permission rule, idempotency,
concurrency/barrier, timeout/cost, output policy, display metadata. Đây là
điều kiện để Phase 11/12 thêm capability không tạo dispatch path thứ hai.

**Gate.** Chứng minh bằng contract test: thêm một tool thử nghiệm trong test
suite chỉ cần đúng một declaration — executor, prompt schema, trace, budget,
display đọc cùng nguồn; schema model = schema executor; unknown/invalid/
denied/timeout/handler error settle một typed result; parallelism giữ stable
order.

**Kết quả (2026-09-01).** Gate đạt bằng
`pytest tests/test_agent_capability_contract.py …` (84 test, toàn suite 1144
passed). Declaration nay mang permission rule bắt buộc (`allow|ask|deny`,
không default — default permission để nguyên cho P5) và per-call
`timeout_seconds`; executor enforce cả hai tại một điểm, thêm hai typed
result `permission_denied` (ask fail-closed tới khi P5 có approval flow) và
`tool_call_timeout` (chỉ dành cho bound khai trên declaration —
`TimeoutError` của chính handler vẫn là `tool_failed`). Hành vi 5 tool ship
không đổi. Hai câu hỏi chuyển P5: có rút tool non-allow khỏi schema model
thấy không, và số đo tần suất chạm timeout trên mạng thật. Plan và số đo:
[`plans/260901-1130-phase-02-capability-plane/plan.md`](../plans/260901-1130-phase-02-capability-plane/plan.md).

### Phase 3 — Durable loop, lane và progress thật — **Done (2026-09-01)**

**Outcome.** Loop semantics Hermes trên state OpenCode; Turn phục hồi có giới
hạn hoặc kết thúc có lý do; tiến trình hiển thị là sự thật.

**Checklist.**

- Lifecycle `pending → running → completed|error|denied|cancelled` cho model
  attempt và tool call; persist intent trước execute khi cần reconcile.
- **Lane profile:** intent router chọn `light` (hội thoại, trần thấp, không
  pass phụ) hay `deep` (memo, trần round/deadline hào phóng, bật pipeline
  3-pass ở Phase 6). Trần là config theo lane, không hard-code một cỡ —
  `MAX_TOOL_ROUNDS = 4` hiện tại trong `loop.py` trở thành giá trị lane light.
- Không tin `finish_reason` một mình; error taxonomy map bounded action;
  bounded nudge; hết budget trả partial answer kèm concrete blocker.
- **Progress part typed:** mỗi event mang nội dung thật (query nguyên văn,
  domain, số nguồn, bước pipeline); map 1-1 sự kiện loop; persist trong
  transcript làm audit trail; SSE replay vẽ lại đúng timeline sau reconnect.
- **Question part typed** (§1): options như dữ liệu; ba trạng thái
  `answered|skipped|superseded` persist; cờ `multi_select` trong schema.
- Cancellation truyền xuống model/tool; terminal write idempotent; retry/
  specialist tiêu cùng deadline và cost envelope của Turn.

**Gate.** Fault-injection (timeout, rate limit, malformed, empty, context
overflow, output cap, cancel, disconnect) settle đúng; 0 orphan tool state;
0 duplicate external effect; replay timeline nhất quán sau disconnect; question
card ba trạng thái sống qua replay.

**Kết quả (2026-09-01).** Gate đạt bằng
`pytest tests/test_agent_fault_injection.py …` (14 test / 12 dòng ma trận,
mutation-probed; toàn suite 1283 passed, web 458 + build xanh). Trần
round/deadline/external/output nay là `LaneProfile` (`agent/lanes.py`, light =
hằng cũ, deep 10 round/1800s; intent router heuristic tất định, mặc định
light); progress part typed phát từ 7 sự kiện thật của loop, sống qua
stream/snapshot/checkpoint/message và không bao giờ vào context model;
question part + bảng `agent_question` + endpoint answer/skip + supersede
trong transaction tạo Turn — ba trạng thái replay qua GET thread (state
đổi-sau-terminal không sống trong draft, amendment tường minh trong plan);
tool call thêm `pending|denied` trên wire, intent persist trước write effect,
mọi view persist 0 orphan sau terminal; cancel truyền xuống model call
in-flight và read segment, write barrier chạy nốt đúng một lần. Câu hỏi mở
chuyển P5 (guardrail rung theo lane, trace row cho call bị cancel), P6
(routing quality + re-baseline golden trước khi nới deep), P7/P9
(`dispatched` lên wire, trail của Turn câm). Plan và số đo:
[`plans/260901-1154-phase-03-durable-loop-lane/plan.md`](../plans/260901-1154-phase-03-durable-loop-lane/plan.md).

### Phase 4 — Context Engine — **Done (2026-09-01)**

**Outcome.** Model nhận đúng context cho step hiện tại. Mục tiêu là **chất
lượng suy luận** (context dài làm model xuống cấp), tiết kiệm token là phụ
phẩm.

**Checklist.** Tách stable/scoped/transcript-evidence/volatile; usage token
thật từ provider; prune deterministic trước lossy summary (dedup snippet,
collapse old result thành evidence handle, giữ recent intent + call/result
pair); summary có provenance, protected tail, cooldown, recovery search, lỗi
summary fail-open về context hợp lệ gần nhất; cache boundary theo prefix ổn
định nếu route probe chứng minh; finance playbook nạp theo intent.

**Gate.** Replay corpus giữ task success, cited evidence, user intent; overflow
hội tụ bounded; không tách call khỏi result; evidence từ Turn trước (scout của
elicitation) dùng lại được ở Turn sau không refetch.

**Kết quả (2026-09-01).** Gate đạt bằng
`pytest tests/test_agent_context_engine.py …` (29 test ở mức hệ thống; toàn
suite 1375 passed, baseline đầu phase 1283; web 458 + build xanh). Tầng lắp ráp
đã chín từ trước — bảy layer có kế toán, ladder bốn nấc, collapse giữ URL — nên
phase đóng đúng bốn mảnh còn thiếu: số token **thật** của route quyết định
context qua projection không nhánh (ước lượng giữ vai backstop preflight,
`estimate_bias` ghi lại sai số cho P9); một trang Turn trước đã đọc được phục vụ
lại từ bản ghi của chính thread với **0 HTTP request** và `retrieved_at` gốc
(validate SSRF vẫn chạy trước, bản ghi không thành cửa hậu); lossy summary có
producer là specialist ẩn chạy **sau** khi Turn settle — provenance đủ span,
protected tail, cooldown, fail-open tuyệt đối, recovery search bằng
`session_search` sẵn có; playbook chỉ nạp khi câu hỏi với tới nó. Không bảng,
không cột, không migration; catalog vẫn đúng năm tool; hợp đồng HTTP/SSE chỉ
thêm một progress kind.

Hai lỗi thật do chính gate bắt được, sửa hướng-nguyên-nhân: (1)
`ConstructedContextTooLarge` từng thoát khỏi `_call` và settle `turn_failed`,
mất phần trả lời dở — vi phạm §4(7), nay là `incomplete/context_overflow` giữ
narration; (2) **ladder có thể leo lên** — handle dài hơn chính kết quả khi kết
quả ngắn, nên nấc nhường đất làm context *to hơn* và mất luôn nội dung (đo được
129 → 182 → 235 token), nay collapse chỉ xảy ra khi thật sự đổi được, cùng
fixture cho 129/129/129/98/67.

Composition trên cùng corpus, replay thuần miễn phí: 377.434 → **377.495**
token. Playbook-theo-intent tiết kiệm **0 trên corpus release**, và đó là số đo
chứ không phải suy đoán: `cases_carrying_the_pack_body = 20/20` — mọi case đều
là câu hỏi thị trường, nên corpus không thể đo được thứ này.

Một dòng gate **BLIND**, không ghi xanh: "replay corpus giữ **task success**".
Replay thuần đo token và cấu tạo, không đo chất lượng; task success cần
`make golden-release` tiêu tiền thật và chưa có ngân sách cấp. Đây là khoản chi
chờ product owner, không phải nợ kỹ thuật của phase.

Câu hỏi mở chuyển đúng chủ: corpus release thiếu case ngoài domain nên
playbook-theo-intent chưa có số thật (golden owner/P9); `agent_tool_call` thiếu
index `thread_id` — cố ý để lại, cần đo trên bảng thật trước (P6); giá batch
thật vs trần $0.015/owner của lane analysis chưa bao giờ bị chạm (P9);
`estimate_bias` chưa có ai đọc (P9); `REPORT_SCHEMA@2` của replay chưa có
consumer (P5). Plan và số đo:
[`plans/260901-1643-phase-04-context-engine/plan.md`](../plans/260901-1643-phase-04-context-engine/plan.md).

### Phase 5 — Permission, guardrails, web security — **Done (2026-09-01)**

**Outcome.** Capability được phép vì policy typed.

**Checklist.**

- Rule `allow|ask|deny` theo capability/resource; no-match/unknown = deny;
  `ask` chỉ khi có side effect thật.
- Permission, approval, kill switch, sandbox, authorization là các cơ chế
  khác nhau.
- Giữ SSRF/DNS/redirect; page-size/time budget mọi fetch path; **egress
  budget hai tầng: per-Turn và fleet-wide per-domain** (toàn hệ thống chỉ đọc
  một trang một lần mỗi cửa sổ — điều kiện sống còn khi đông user, thiết kế
  từ bây giờ, enforce đủ ở Phase 10).
- Injection scan là risk signal ngoài model text; web/tool content không sửa
  được policy, args, memory, system instructions.
- Guard loop exact-failure/same-tool/no-progress; scanner lỗi không làm mất
  answer. Auth, tenant scope, schema, side effect fail-closed.

**Gate.** Adversarial suite: indirect injection, encoded/bidi, SSRF, redirect,
oversized, permission bypass, repeated calls, secret leakage — 0 escalation,
0 raw secret trong trace; benign corpus không bị block quá threshold baseline.

**Kết quả.** Rule set capability/resource typed đã chạy last-match-wins,
no-match/unknown deny; schema frozen được validate trước dispatch và các cửa
permission/approval/availability/authorization/content escalation tách thành
kết quả typed. Untrusted external read chặn durable write về sau trong cùng
Turn; web secret egress bị chặn trước I/O; trace redact đệ quy; scanner nhận
diện encoded/zero-width/bidi và vẫn fail-open. Web lane có Redis allowance toàn
fleet và theo domain trên cache miss, giữ cache/single-flight cùng per-Turn
logical ceiling; Phase 10 vẫn sở hữu full scale enforcement. Gate adversarial
25 test đạt escalation `0`, raw secret `0`, benign false-positive `0/20`; toàn
API **1401 passed**, web **458 tests** + lint/type/build xanh. Không đổi catalog
năm tool, default permission, HTTP/SSE hay schema DB. Plan và bằng chứng:
[`plans/260901-2304-phase-05-permission-guardrails-web-security/plan.md`](../plans/260901-2304-phase-05-permission-guardrails-web-security/plan.md),
[`plans/reports/fullstack-260901-2304-phase-05-permission-guardrails-web-security.md`](../plans/reports/fullstack-260901-2304-phase-05-permission-guardrails-web-security.md).

### Phase 6 — Evidence engine: research 3-pass + finance evidence — **Target**

**Outcome.** Deep lane đạt hợp đồng sự thật §2 chỉ bằng web research, tool
loop và reasoning; không indicator/store/Study engine.

**Checklist.**

- Planner tạo query độc lập theo giá/diễn biến, sự kiện, doanh nghiệp/ngành
  và **phản biện**; executor fan-out search rồi fetch đủ để kết luận.
- **Pipeline 3-pass của deep lane:** research (draft claim) → counterevidence
  (một lượt chuyên tấn công draft, sinh mục "điều gì vô hiệu hóa luận điểm")
  → verification (verifier context sạch đối chiếu từng claim với quoted span;
  chính sách fail của §2). Mỗi pass phát progress part thật.
- Source policy VN: primary (CBTT HOSE/HNX, SSC, VSDC, IR) > báo chí >
  aggregator > snippet; risk class ToS per nguồn; **luật đa nguồn** §2;
  ranking không phải publisher trust.
- Evidence store hai tầng (§6): cache sản phẩm theo canonical URL + cửa sổ
  `as_of` (retention khóa khi phase bắt đầu); trajectory artifact TTL riêng.
- Claim ledger nối claim ↔ evidence IDs + trạng thái verify; citation renderer
  chỉ render từ ledger.
- Finance temporal rules: `as_of`, phiên, timezone, kỳ báo cáo, corporate
  action, đơn vị/tiền tệ, publication lag.
- Elicitation policy §1 chạy trong planner: quyết định hỏi trước khi kết luận,
  scout-then-ask, budget cứng backend.
- Prompt theo §3; câu "có nên mua" thiếu context → phân tích với giả định in
  rõ, không giả personalization.
- Phase plan scout nguồn pattern §7 trước khi thiết kế pipeline 3-pass:
  STORM (counterevidence qua đa góc nhìn), SAFE/FacTool (claim decomposition
  và chính sách rớt verify), probe Anthropic Citations API như named
  assumption cho span-grounding cơ học.

**Gate.** Golden Phase 1 đạt hard gates; elicitation family đạt (0 câu hỏi
discoverable, 0 câu không rẽ nhánh trên corpus); conflict/missing nói thẳng;
citation mở đúng trang; material-claim accuracy có baseline nhiều trial;
điểm rubric judge ≥ ngưỡng đã khóa từ baseline Phase 1; 0 import local
signal engine.

**Trạng thái (2026-09-04).** Code đã merge vào `develop` (`12dd0f6`, `c2af520`):
pipeline 3-pass, claim ledger, source policy, evidence store, extractor
`published_at`. Gate kỹ thuật xanh — API **1473 passed**, alembic round trip
sạch, web lint/type-check/test/build xanh.

Lượt đo đầu tiên sau khi merge phát hiện năm khiếm khuyết, sửa trong `5d9e564`:

- Runner ghi câu hỏi elicitation đè lên câu hỏi của corpus (cùng key trong một
  dict literal) — mọi case được chấm với câu hỏi rỗng, nên `grade_budget` định
  lane bằng cách đọc lại câu hỏi đã hạ mọi deep Turn xuống trần của lane light.
- `as_of` chưa bao giờ tới runtime: ledger stamp mốc bằng đồng hồ chạy, tức
  không loại được gì. Mốc nay đọc từ chính câu hỏi (`as_of_from_text`); chỉ mốc
  người dùng nêu mới chặn tool. Loại luôn nguồn *không* xác định được ngày đã
  thử và đo: nó vét sạch bằng chứng của một Turn có mốc, nên chỉ nguồn **có
  ngày** sau mốc bị loại — nguồn không ngày là khoảng hở đã đo, không phải sót.
- URL báo VN ghi ngày trong id bài (`188260829…`) mà pattern đường dẫn không
  thấy; trang không có `<title>` mất một trong bốn mặt định danh §6.6.
- Light lane hỏi lại người đọc trước khi tra trang nào: scout-then-ask trước
  đây chỉ viết cho pipeline deep, nay nằm trong prompt light lane đọc (4.2.0).

**Đo trên 10 case chạm mọi hard dimension** (probe 2026-09-04): `settlement`
10/10, `citation_url` 10/10, `evidence_identity` 10/10, `budget` 10/10,
`temporal_validity` **3/3**, `refusal_policy` **2/2**, `material_claim`
**2/2** — hai dimension cuối là hai dòng **BLIND** của baseline Phase 4, lần
đầu tiên corpus hỏi được và pass.

**Phase vẫn giữ nhãn Target** cho tới khi một lượt `make golden-release` toàn
corpus 40 case cho verdict trong *một* artifact; hiện các dimension mới xanh
trên hai artifact rời. Ngưỡng mềm `judge_axes` vẫn chưa khoá vì cần nhiều
trial. Plan và bằng chứng:
[`plans/260902-0026-phase-06-evidence-engine/plan.md`](../plans/260902-0026-phase-06-evidence-engine/plan.md),
[`plans/reports/fullstack-260902-1418-phase-06-evidence-engine.md`](../plans/reports/fullstack-260902-1418-phase-06-evidence-engine.md).

### Phase 7 — Evidence Desk UX — **Target**

**Outcome.** Client render đầy đủ hình dạng sản phẩm §1 từ typed contract —
không suy diễn từ text.

**Checklist.**

- Memo layout: verdict tổng + `as_of` banner → verdict card ba trạng thái
  từng tiền đề → rubric §3 → phản chứng/vô hiệu hóa → watch items → footer
  "N nguồn · M claim · K không kiểm chứng được".
- Citation chip inline → Inspector nâng cấp thành evidence card (quoted span
  highlight, publisher, hai mốc thời gian, link, conflict note, nhãn
  inference/single-source).
- **Timeline ba hồi** live khi chạy (research → phản biện → kiểm chứng), gập
  được, persist thành audit trail sau khi memo ra; reconnect vẽ lại đúng điểm.
- v1: memo render sau verification; nâng cấp chip-flip ("đang kiểm ⏳" → ▸①)
  là option sau, có gate riêng, không nợ ngầm.
- Question card: single-select + skip; `superseded` khi user gõ composer;
  card đã trả lời render đúng trạng thái khi replay.
- Trạng thái "không đủ bằng chứng" có thiết kế riêng: nói đã tìm gì, thiếu gì,
  gợi ý bước tiếp — không phải error state.
- Nút **"báo sai"** trên từng claim — backend flag/helpful theo message đã
  tồn tại (`flag_router.py`); phase này nối UI xuống mức claim, pipeline
  triage ở Phase 9.
- Dossier: thread theo `symbols[]`, watch item bấm chạy lại và memo mới đối
  chiếu memo cũ.

**Gate.** E2E: hỏi → (question card → chọn/skip/supersede) → timeline live →
memo đầy đủ object §1 → bóc evidence card → F5 giữa chừng không mất gì →
cancel sạch. Web lint/type-check/test/build xanh; mọi phần tử memo đều truy
được từ typed part, không parse markdown.

### Phase 8 — Memory, hồ sơ giả định và domain knowledge — **Target**

**Outcome.** Agent nhớ điều hữu ích; memory không thành instruction đặc quyền
hay nguồn dữ kiện thị trường; tuân thủ PDPL 2025 (hiệu lực 01/01/2026 — dữ
liệu tài chính cá nhân là nhạy cảm, consent theo mục đích, rút dễ như cho).

**Checklist.**

- Session search và cross-session memory chỉ qua tool có schema.
- **Hồ sơ giả định hai giai đoạn:** trước phase này, câu trả lời elicitation
  chỉ sống trong thread. Phase này mở **opt-in per-purpose**: chỉ lưu giả
  định user tự khai (horizon, vùng giá vốn theo mã, mục đích); panel xem–sửa–
  xóa từng mục; expiry ~90 ngày rồi hỏi xác nhận lại; mỗi recall hiển thị
  banner trên memo kèm nút cập nhật. Cấm vĩnh viễn hồ sơ model tự suy.
- Memory có provenance, owner, scope, created/updated, expiry, delete path;
  recall xung đột evidence mới bị hạ ưu tiên và nêu mâu thuẫn.
- Domain catalog nhỏ cache; body nạp theo intent. Auto-write, self-editing
  skill, memory-to-system-prompt: Rejected.

**Gate.** Isolation/delete/stale-conflict/injection tests xanh; recall tăng
task success trên replay không tăng unsupported-claim rate; consent flow
chứng minh được (audit trail đồng ý/rút).

### Phase 9 — Observability, cost và release gate — **Target**

**Outcome.** Trả lời được "agent làm gì, answer này vì sao tồn tại, lỗi đâu,
tốn bao nhiêu" không cần lưu chain-of-thought; số §2 thành số giám sát liên
tục.

**Checklist.**

- Trace hierarchy: Turn → attempt → context composition → tool lifecycle →
  pass pipeline → evidence/claim → terminal outcome.
- Metric có denominator: success/incomplete/refused/cancelled, tool selection,
  invalid args, recovery, evidence coverage, verify pass/fail rate,
  elicitation ask/skip/supersede rate, latency/token/data cost per successful
  outcome, reconnect consistency.
- **Vòng lỗi production:** nút "báo sai" (mở rộng endpoint flag hiện có) →
  hàng đợi triage → sampling audit người review định kỳ → lỗi xác nhận thành
  case corpus Phase 1.
- Content-light mặc định; trajectory sample redact + access-control + TTL.
- Mọi thay đổi prompt/tool/context/model/provider chạy affected golden +
  adversarial replay; loop/permission thêm fault-injection; rollback/kill
  switch cho capability và prompt release.

**Gate.** Release artifact tái tạo được; hard-dimension regression fail
closed; trace không cần prompt body vẫn ra typed cause + owner; cost báo trên
successful outcome — sẵn sàng làm đầu vào định giá B2C/B2B.

### Phase 10 — Scale-out — **Conditional (theo usage, không theo eval)**

Mở khi usage thật chạm ngưỡng (đề xuất: >1k MAU hoặc fetch per-domain chạm
trần lễ độ). Không mở sớm.

- **Shared evidence cache** thành hạ tầng chính thức: request coalescing câu
  hỏi nóng (user đầu trả giá đầy đủ, người sau hit cache tầng evidence — memo
  và giả định cá nhân không bao giờ share); nhất quán as_of giữa user cùng
  cửa sổ.
- Fleet-wide per-domain budget (thiết kế từ Phase 5) enforce đầy đủ.
- Queue admission giờ cao điểm (phiên sáng, ngày sập, mùa KQKD) với progress
  trung thực; SSE fan-out qua Redis pub/sub; tenant envelope cho B2B.
- Nhân bản thị trường mới = thay ba module đã cô lập: source policy, temporal
  rules, eval corpus. Harness không đổi.

**Gate.** Load test burst 10x không rơi Turn; cache hit không bao giờ trả
evidence quá cửa sổ as_of; 0 rò rỉ dữ liệu riêng tư qua tầng cache; per-domain
politeness giữ được ở concurrency mục tiêu.

### Phase 11 — Agent compute: code execution sandbox — **Conditional**

Mở sau Phase 1–9 khi eval chứng minh một họ câu hỏi định lượng fail vì model
arithmetic (tăng trưởng nhiều kỳ, so sánh ngành, scenario math, thống kê chuỗi
từ nguồn đã trích).

- Sandbox ephemeral khuôn OpenCode: process cô lập, filesystem tạm, không
  network egress mặc định; runtime (container/microVM/WASM) chọn khi mở.
- `execute_code` qua đúng plane Phase 2: schema, permission, timeout, output
  cap, budget, lifecycle như mọi tool.
- Input duy nhất: evidence/attachment có provenance trong Turn; không store
  nội bộ, không catalog chỉ báo, không scheduler — không phải restore Signal
  Desk/Study.
- Kết quả là **derived computation** trong claim ledger: nối evidence input +
  code/version; renderer phân biệt số agent tính với số trích nguồn.
- Code và stdout/stderr là untrusted; kill switch riêng; sandbox fail →
  fail-closed về đường web-first, không mất answer.

**Gate.** Golden định lượng tăng accuracy vs baseline model-arithmetic có ý
nghĩa thống kê nhiều trial; 0 sandbox escape/egress ngoài policy/escalation;
cost/latency per successful outcome trong envelope; rollback diễn tập. Không
đạt → Rejected cho workload đó.

### Phase 12 — Delegation, MCP, side-effect tools — **Conditional**

Mở khi một workload độc lập chứng minh single-agent không đủ.

- Child = durable child session, fresh context, output schema fail-closed;
  deny/data boundary cha truyền xuống; không tự nhận memory/secret/write
  tool/quyền delegate tiếp.
- Depth, concurrency, token/cost/deadline, cancellation bound toàn cây.
- MCP mặc định untrusted, allowlist capability, validate contract; annotation
  không phải authorization. Side effect cần idempotency/reconcile + approval.

**Gate.** Uplift vượt overhead cùng corpus nhiều trial; 0 escalation, 0 orphan
child, 0 budget escape. Không đạt → single-agent + Rejected.

## 11. Dependency

```text
P0 done → P1 eval done → P2 capability done → P3 loop/lane done
        → P4 context done → P5 security done → P6 evidence engine ◀ next → P7 desk UX
        → P8 memory/consent → P9 observability/release
                                   │
              ┌────────────────────┼──────────────────────┐
              ▼ (theo usage)       ▼ (theo eval)          ▼ (theo workload)
        P10 scale-out        P11 compute sandbox    P12 delegation/MCP
```

Tuần tự P1→P9 là bắt buộc; P10/P11/P12 độc lập nhau, mỗi cái có trigger
riêng, đều đứng trên plane P2 và permission P5. Eval/observability
instrumentation thêm trong từng phase; P9 hợp nhất thành release authority.

## 12. Definition of Done

**Evidence Desk hoàn tất (P0–P9) khi:**

1. Không còn Signal Desk/Study/indicator path trong product runtime.
2. Chat UI là projection mỏng của durable Turn/typed-part contract; mọi
   object §1 render từ part, không parse text.
3. Mọi tool qua unified capability/permission/budget/lifecycle plane.
4. Loop phục hồi typed, bounded, không màn hình trắng; progress là sự thật.
5. Context dài giữ intent, evidence, protocol; suy luận không xuống cấp đo
   được trên replay.
6. Web content không nâng được quyền; hard boundary fail-closed.
7. Hợp đồng sự thật §2 đạt: fabrication 0% cơ học, disclosure 100%,
   material-claim accuracy có số đo nhiều trial, refusal là outcome hạng nhất.
8. Elicitation đúng kỷ luật §1 trên corpus; consent hồ sơ giả định đúng PDPL.
9. Mọi thay đổi prompt/tool/model/context có replay artifact, cost, rollback.

**AI Agent for Investment đầy đủ thêm:** P10/P11/P12 hoặc mở với gate xanh,
hoặc ghi Rejected kèm số đo — không có capability "mở một nửa" ngoài plane.

## 13. Câu hỏi cần khóa khi phase tương ứng bắt đầu

1. (P0-di sản) Dữ liệu artifact/signal lịch sử giữ bao lâu trước migration
   retire schema?
2. (P6) Retention và cửa sổ as_of của tầng evidence cache sản phẩm: con số
   cụ thể theo loại nguồn (giá EOD, bài báo, filing)?
3. (P7) "Investment research" vs "personalized advice": ranh giới legal chính
   thức của copy và disclaimer trên memo? Baseline P1 đã biến câu này thành
   khẩn cấp: câu "500 triệu nên phân bổ bao nhiêu %" được trả lời bằng
   "15–25% — tương đương 75–125 triệu" ở cả ba trial, và câu "lỗ 20% cắt hay
   giữ" được trả lời bằng khung ra quyết định thay vì từ chối. Cần chốt: khung
   tư duy chung có nằm trong ranh giới không, hay chỉ research thuần?
4. (P9) Ai sở hữu sampling audit finance correctness — founder, cộng tác viên
   chuyên môn, hay thuê ngoài định kỳ?
5. (P11) Sandbox runtime nào (container/microVM/WASM) và ai vận hành isolation
   boundary?
