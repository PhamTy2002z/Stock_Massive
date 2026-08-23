# Quality, safety and operations contract

Tài liệu này định nghĩa cách Stock_Massive chứng minh AI tốt hơn, an toàn hơn và
vận hành được. Một capability chưa có eval và telemetry phù hợp chỉ là code path,
không phải capability đã tốt nghiệp. Quality gate chấm outcome tài chính và
evidence; không ép model đi đúng một trajectory duy nhất.

## Quality model

Investment Intelligence cần bar cao hơn fluent answer. Chất lượng được chấm
theo nhiều chiều độc lập để một cải thiện về style không che regression về truth,
freshness hoặc cost.

| Chiều | Câu hỏi phải trả lời | Grader ưu tiên |
|---|---|---|
| Task success | Người dùng có nhận được outcome đã hỏi không? | deterministic outcome + rubric |
| Factual correctness | Figure, entity, unit và comparison có đúng không? | deterministic against frozen evidence |
| Temporal correctness | Chỉ dùng dữ liệu biết được tại as-of không? | point-in-time replay grader |
| Evidence coverage | Claim trọng yếu có evidence hợp lệ không? | claim/evidence graph check |
| Freshness | Staleness và publication lag có được xử lý đúng không? | metadata assertions |
| Statistical honesty | Window, sample, uncertainty và caveat có đúng contract không? | deterministic method checks |
| Calibration | Confidence có giảm khi evidence yếu hoặc mâu thuẫn không? | bucketed calibration + human rubric |
| Decision utility | Outcome có nêu implication, alternatives và falsifier hữu ích không? | blinded human/model rubric |
| Safety | Có vượt data scope, autonomy level hoặc user constraint không? | deterministic policy/adversarial tests |
| Reliability | Turn có settle, recover và reconnect đúng không? | protocol/state tests |
| Efficiency | Success tiêu bao nhiêu latency, token, model và data cost? | operational ledger |

Không dùng một composite score duy nhất để quyết định release. Safety, temporal
correctness, evidence identity và protocol settlement là hard dimensions;
quality/cost là trade-off dimensions trong phạm vi product owner chấp nhận.

## Evaluation portfolio

Một test suite không thể đại diện cho toàn product. Evaluation portfolio phải
kết hợp deterministic contracts, frozen golden cases, temporal replay,
adversarial probes và production feedback.

### Contract tests

Contract tests bảo vệ invariant mà model không có quyền thương lượng. Chúng chạy
nhanh và deterministic.

- capability declaration đồng nhất giữa schema, executor, budget, trace và UI;
- one-call-one-result và typed terminal state;
- identity/symbol/as-of không thể bị tool argument override;
- point-in-time data selection và publication lag;
- unit, sign, sample floor, market band và settlement rules;
- recovery action đúng typed error;
- context giữ cặp tool call/result và cited evidence;
- child permission không tăng qua delegation;
- telemetry redaction và retention policy.

Executable owners hiện có gồm `apps/api/tests/test_agent_loop.py`,
`test_agent_transport.py`, `test_agent_persistence_paths.py`,
`test_agent_signal_tools.py` và các test Signal Field. Roadmap mở rộng qua seam,
không copy test name vào SOT như inventory cố định.

### Golden Investment Intelligence set

Golden set phải đại diện cho decision tasks thật, không chỉ FAQ. Mỗi case có
frozen evidence snapshot, as-of, user context, accepted outcome properties và
known traps.

Các family bắt buộc gồm:

- fact lookup có source conflict hoặc stale provider;
- single-symbol technical/fundamental/flow/news synthesis;
- peer và cross-sectional comparison;
- event impact với publication-time trap;
- sparse history, refused figure và substitute evidence;
- bull/base/bear scenario với sensitivity;
- thesis creation, update và falsification;
- portfolio concentration, correlation và drawdown reasoning;
- question không đủ context cần clarification;
- prompt injection hoặc malicious content trong web/document/tool result;
- request vượt autonomy, data scope hoặc suitability context.

Một case có thể có nhiều trajectory hợp lệ. Grader chấm evidence và outcome;
tool sequence chỉ bị khóa khi sequence đó là safety hoặc data contract.

### Temporal replay

Temporal replay là benchmark quan trọng nhất cho finance vì nó phát hiện
lookahead và survivorship bias mà answer-level rubric bỏ sót.

Mỗi replay đóng băng:

- universe và exchange mapping tại as-of;
- raw observations có publication/ingestion time;
- provider/model/config/prompt/tool contract versions;
- user context hợp lệ tại thời điểm đó;
- available capabilities và route semantics.

Outcome được chấm trên dữ liệu có thể biết lúc đó, sau đó có thể đối chiếu với
tương lai để đánh giá calibration. Future outcome không được đưa ngược vào
grader correctness của decision tại as-of.

### Robustness and adversarial set

Adversarial eval tập trung vào failure mode có blast radius thật. Nó không cố
“jailbreak” model chung chung nếu harness policy đã chặn deterministic.

- conflicting source, unit, currency hoặc reporting period;
- corporate action và symbol/exchange migration;
- missing/duplicate/out-of-order tool result;
- provider finish reason sai hoặc malformed arguments;
- context overflow, output cap, timeout, cancellation và reconnect;
- stale memory contradicting new evidence;
- indirect prompt injection từ web, filing, MCP hoặc specialist output;
- specialist vượt scope, budget hoặc data permission;
- replay sau crash giữa called và settled;
- notification duplicate hoặc non-material alert storm.

### Production feedback

Production feedback bổ sung eval, không thay eval. Helpful flag chỉ đo perception
và không chứng minh correctness.

Feedback loop cần kết nối:

- user helpful/flag reason;
- terminal reason và incomplete reason;
- tool outcome, evidence coverage và refusal distribution;
- explicit correction hoặc follow-up;
- sampled redacted trajectory review;
- data/provider incident correlation.

Mọi production case đưa vào regression set phải được redacted, frozen và gắn
failure taxonomy. Không lưu private content vô thời hạn chỉ vì nó hữu ích cho
debug.

## Grading strategy

Grader đi từ deterministic đến subjective. Model judge không được chấm fact mà
backend có thể kiểm trực tiếp.

1. Chạy schema, state, data, calculation, citation và policy grader
   deterministic.
2. Chạy task-specific outcome grader trên frozen environment.
3. Dùng model rubric cho synthesis, clarity, counterargument và usefulness.
4. Dùng human review cho sample rủi ro cao, disagreement và capability mới.
5. Chạy nhiều trial khi model variance ảnh hưởng kết luận; báo confidence
   interval thay vì một score.

Nguyên tắc outcome-first và multi-trial phù hợp với
[Anthropic agent eval guidance](https://www.anthropic.com/engineering/demystifying-evals-for-ai-agents).
Các benchmark như
[FinanceBench](https://arxiv.org/abs/2311.11944) và
[FinQA](https://arxiv.org/abs/2109.00122) là nguồn task/rubric tham khảo, không
thay thế benchmark point-in-time cho thị trường Việt Nam và product contract.

## Graduation gates

Mỗi capability có gate riêng trong roadmap, nhưng mọi capability phải qua flow
chung. Threshold số chỉ được khóa sau baseline đại diện và quyết định product;
SOT không bịa một con số đẹp khi chưa có distribution.

Một capability tốt nghiệp khi:

1. contract và threat model đã viết;
2. executable owner và state transition rõ;
3. deterministic tests pass;
4. golden/adversarial cases có baseline trước và sau;
5. không regression hard dimensions;
6. uplift outcome vượt variance và overhead;
7. cost/latency nằm trong envelope được chấp nhận;
8. observability và rollback/disable path đã có;
9. docs/current status được cập nhật.

“Feature hoạt động trong demo” không phải graduation evidence. Với specialist,
phải so trực tiếp với single-agent; với compaction, phải đo recall/task retention;
với proactive monitor, phải đo materiality/duplicate/noise; với route mới, phải
đo semantic parity.

## Release and regression policy

Thay đổi prompt, tool schema, context selection, model route, evidence contract
hoặc loop có thể đổi outcome dù typecheck vẫn xanh. Chúng cần risk-proportional
evaluation trước khi phát hành.

| Change class | Required evidence |
|---|---|
| Copy/UI projection only | contract tests và snapshot/UI tests |
| Tool implementation, same contract | tool contract + affected golden cases |
| Tool schema/description | routing/argument eval + affected golden cases |
| Prompt/context/memory | golden + temporal + adversarial replay |
| Model/provider/fallback | capability probe + semantic parity + quality/cost trials |
| Loop/recovery/persistence | protocol, fault injection, reconnect và golden replay |
| Specialist/proactive/autonomy | dedicated uplift, security, budget và cancellation suite |

Eval artifact phải ghi code SHA, prompt/tool/model/config/data snapshot versions
và trial count. Không chấp nhận report không thể tái tạo environment.

## Observability contract

Observability trả lời “hệ thống đã làm gì và vì sao outcome này tồn tại” mà
không cần chain-of-thought. Schema phải theo hierarchy ổn định.

```text
root task
  session / turn / analysis / goal
    model attempt
      context composition
      tool call -> tool result -> evidence references
      retry / recovery / guardrail decision
    final outcome
      claims -> evidence
      terminal reason
      usage / cost / latency
```

Metric core gồm:

- successful, incomplete, refused, cancelled và failed outcome;
- tool selection, invalid arguments, unknown, refusal và useful-result rate;
- evidence coverage, cited-figure và stale/conflict rate;
- retry/fallback theo typed cause và recovery success;
- context composition, cache read/write, prune/compression và recall recovery;
- latency/token/model/data cost per successful outcome;
- reconnect consistency, subscriber drop và orphan settlement;
- specialist uplift, redo, cancellation, cost và join failure;
- proactive materiality, duplicate, delivery và user-dismiss rate.

Metric phải có denominator và outcome scope. “Substitution rate cao” hoặc “tool
calls nhiều” không tự chứng minh intelligence tốt hơn.

## Trace and privacy

Operational telemetry mặc định không chứa prompt, document body, tool result,
portfolio hoặc user memory. Rich trajectory là debug/eval artifact riêng.

Trajectory policy bắt buộc:

- explicit purpose và access scope;
- schema-based redaction trước persistence;
- secret, credential và raw personal data denylist;
- retention/expiry và deletion path;
- encrypted storage phù hợp deployment;
- sampled collection thay vì mặc định toàn bộ;
- audit ai đọc/export artifact;
- không lưu hidden chain-of-thought như requirement vận hành.

Model input/output có thể chứa dữ liệu tài chính nhạy cảm của người dùng. Route
selection phải tôn trọng data handling contract; fallback không được đổi data
residency hoặc retention posture một cách im lặng.

## Security model

Safety được enforce theo nhiều ranh giới. Prompt guard không thay authorization;
permission không thay sandbox; sandbox không thay data scope.

| Boundary | Default | Enforcement |
|---|---|---|
| User → data | least scope | authenticated ownership và typed context |
| Model → capability | deny outside resolved set | strict schema, capability policy và budget |
| External content → model | untrusted | delimit, provenance, injection scan, no privilege |
| Capability → store/provider | scoped adapter | allowlist entity/as-of, query and quota bounds |
| Specialist → parent | no permission escalation | child profile + inherited deny + global budget |
| Runtime → external side effect | no implicit write | idempotency, approval, audit and reconcile |
| Plugin/MCP → process | unavailable by default | explicit provider review, scope and conformance |
| Telemetry → operator | content-light | redaction, access control and retention |

Unknown capability, provider annotation hoặc MCP `readOnlyHint` không được coi
là bằng chứng quyền. Trust class do Stock_Massive declaration sở hữu.

## Financial risk and suitability

Hệ thống phải phân biệt market analysis với recommendation phù hợp một người.
Nếu thiếu horizon, holdings, liquidity need hoặc risk tolerance cần thiết, AI
được phép phân tích nhưng không được giả personalization.

- Không chuyển descriptive signal thành certainty hoặc action directive.
- Không đưa position size nếu edge/risk inputs không có provenance và sensitivity.
- Không ẩn concentration, liquidity, correlation uncertainty hoặc downside.
- Không biến backtest/hindsight thành expected return.
- Không so outcome khác horizon như cùng một thesis.
- Không auto-notify nếu materiality và user consent chưa được định nghĩa.
- Không gửi broker action ở autonomy level hiện tại.

Policy language phải hỗ trợ người dùng ra quyết định, không dùng disclaimer để
che một output thiếu evidence.

## Reliability and recovery

Recovery thành công nghĩa là outcome còn giữ semantic contract, không chỉ route
trả HTTP 200.

| Failure | Recovery class |
|---|---|
| Rate limit/overload | bounded wait, healthy credential/route fallback |
| Provider timeout | rebuild/alternate route theo scope; giữ attempt trace |
| Context overflow | deterministic reduction, summary/recovery search |
| Output cap | reserve reduction hoặc bounded continuation |
| Malformed tool call | synthetic result/nudge có trần |
| Tool timeout/error | settled result; continue nếu outcome còn khả thi |
| Evidence unavailable | substitute hợp lệ hoặc concrete blocker |
| Policy/auth/schema | fail closed; không retry mù |
| Trace/observer failure | answer path degrade open, emit operational failure |
| Crash after effect | reconcile bằng idempotency/status trước retry |

Circuit breaker và fallback scope phải phân biệt credential, endpoint, model và
provider. Shared budget/deadline đi qua mọi retry và child; recovery không được
tạo một allowance mới.

## Cost governance

Cost là quality constraint, không phải mục tiêu tối thiểu hóa độc lập. Đơn vị
đúng để so là cost trên successful, decision-useful outcome.

Budget hierarchy target gồm:

- envelope toàn hệ thống;
- lane và user ceiling;
- root task reservation;
- model/tool/data sub-budget;
- toàn cây specialist/proactive cap;
- emergency reserve có owner rõ.

Prompt cache, progressive context, deterministic prune, specialist model tier
và parallel reads chỉ được giữ nếu giảm cost/latency mà không làm giảm hard
quality dimensions.

## Current gap

Code hiện có strong protocol tests, spend ledger và một số ops metrics, nhưng
root project context ghi rõ Eval Battery/Gate/Report đã bị xóa. Vì vậy **khôi
phục measurement authority là P0**, trước context refactor, subagent hoặc
proactive autonomy. `apps/api/src/agent/ops.py` và
`apps/api/src/alpha/analysis_reads.py` là evidence sources, không phải
evaluation system hoàn chỉnh.

## Câu hỏi chưa giải quyết

Các lựa chọn này phải được khóa bằng baseline hoặc product decision.

- Hard threshold tối thiểu cho từng lane là bao nhiêu sau khi có baseline đại
  diện?
- Ai là owner human-review cho finance correctness và suitability cases?
- Trajectory retention nào cân bằng incident investigation với privacy?
- Có cần external benchmark publication hay chỉ internal release gate trong
  giai đoạn đầu?
