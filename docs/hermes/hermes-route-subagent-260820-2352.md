# Hermes Agent — độ bền tuyến LLM & kiến trúc subagent: đọc code, rút bài học cho Stock_Massive

Nguồn: clone sparse `NousResearch/hermes-agent` (MIT) tại
`/private/tmp/claude-501/.../scratchpad/hermes-agent`. Đối chiếu với
`apps/api/src/core/llm/*` hiện có của Stock_Massive. Chỉ đọc, không sửa.

---

## 1. Kiến trúc độ bền tuyến của Hermes

### 1.1 Taxonomy đầy đủ — `FailoverReason` (`agent/error_classifier.py:30-78`)

| reason | trích comment nguyên văn | hành động phục hồi |
|---|---|---|
| `auth` | "Transient auth (401/403) — refresh/rotate" | rotate credential, thử tiếp |
| `auth_permanent` | "Auth failed after refresh — abort" | dừng, không retry |
| `billing` | "402 or confirmed credit exhaustion — rotate immediately" | rotate credential ngay, không backoff |
| `rate_limit` | "429 or quota-based throttling — backoff then rotate" | backoff rồi rotate credential |
| `upstream_rate_limit` | "Upstream model rate-limited (aggregator 429) — fallback to a different model, NOT credential rotation. The user's key is healthy." | fallback model, **không** rotate |
| `overloaded` | "503/529 — provider overloaded, backoff" | backoff, giữ credential |
| `server_error` | "500/502 — internal server error, retry" | retry nguyên trạng |
| `timeout` | "Connection/read timeout — rebuild client + retry" | rebuild client, retry |
| `ssl_cert_verification` | "deterministic for the host... Retrying reproduces the identical handshake failure, so fail fast" | **không** retry, báo lỗi actionable |
| `context_overflow` | "Context too large — compress, not failover" | compress, không đổi credential/model |
| `payload_too_large` | 413 — compress payload | compress |
| `image_too_large` | ảnh vượt giới hạn 1 ảnh của provider | shrink ảnh, retry |
| `model_not_found` | 404 / invalid model | fallback sang model khác |
| `provider_policy_blocked` | OpenRouter khoá endpoint do chính sách account | không fallback (mọi endpoint đều bị khoá cùng lý do) |
| `content_policy_blocked` | provider safety filter từ chối — "deterministic per-request, don't retry unchanged" | không retry nguyên trạng |
| `format_error` | 400 bad request | abort hoặc strip+retry |
| `invalid_encrypted_content` | Responses replay blob bị từ chối | strip replay state, retry |
| `multimodal_tool_content_unsupported` | provider từ chối content dạng list trong tool message | downgrade sang text, retry |
| `thinking_signature` | Anthropic thinking-block signature sai | strip mọi thinking block, retry |
| `long_context_tier` | Anthropic "extra usage" tier gate | retry, có compress |
| `oauth_long_context_beta_forbidden` | subscription OAuth không có 1M-context beta | strip beta header, retry |
| `llama_cpp_grammar_pattern` | llama.cpp từ chối regex escape trong `pattern`/`format` | strip 2 field đó khỏi tools, retry |
| `unknown` | catch-all | retry với backoff |

**Pipeline phân loại có thứ tự ưu tiên tuyệt đối** (`classify_api_error`,
`error_classifier.py:712-733`, trích nguyên văn docstring):

```
0. Plugin transform_api_error_classification hooks (first valid result wins)
1. Special-case provider-specific patterns (thinking sigs, tier gates)
2. HTTP status code + message-aware refinement
3. Error code classification (from body)
4. Message pattern matching (billing vs rate_limit vs context vs auth)
5. SSL/TLS transient alert patterns → retry as timeout
6. Server disconnect + large session → context overflow
7. Transport error heuristics
8. Fallback: unknown (retryable with backoff)
```

Thứ tự này **là chỗ chứa toàn bộ tri thức run-time** — đảo thứ tự là tái tạo
bug cũ. Vài ràng buộc trật tự đáng chú ý, trích nguyên văn:
- content_policy_blocked "Must run before status-based classification so a 400
  safety block isn't downgraded to a generic `format_error`" (line 847-851).
- ssl_cert_verification "Checked BEFORE the transient-SSL patterns: cert-verify
  messages also contain `[ssl:` which would otherwise match the transient
  list" (line 1046-1048).
- context_overflow-via-disconnect "Must come BEFORE generic transport error
  catch — a disconnect on a large session is more likely context overflow than
  a transient transport hiccup" (line 1068-1071), nhưng **lại bị đảo thêm một
  lớp nữa** cho reasoning model: disconnect trên reasoning model được đọc là
  timeout (proxy idle-kill ~120s) chứ không phải context overflow, vì nếu
  không sẽ "silently delete conversation history on a phantom context-length
  error" (line 1078-1091, Part 1 of #52310).

### 1.2 `rate_limit` vs `upstream_rate_limit` (`error_classifier.py:1258-1293`)

Cả hai đều là HTTP 429, khác nhau ở **ai đang cạn quota**:
- `rate_limit` — key của người dùng cạn hạn mức tại chính provider đang gọi
  → `should_rotate_credential=True, should_fallback=True`. Rotate hợp lý vì
  đổi key khác trong pool có thể còn quota.
- `upstream_rate_limit` — provider chỉ là aggregator (OpenRouter), 429 vì
  **upstream model** (ví dụ DeepSeek) bị nghẽn traffic chung, còn key OpenRouter
  của người dùng vẫn khoẻ. Trích nguyên văn: "marking it exhausted / rotating
  is wrong and burns the key for ~24min. Fall back to a different model."
  → `should_rotate_credential=False, should_fallback=True`.

Phân biệt bằng cách đọc `error_context.metadata.raw` (OpenRouter bọc lỗi
upstream vào 1 JSON string lồng bên trong) qua `_is_openrouter_upstream_error`
— không dựa vào status code, dựa vào **hình dạng thân lỗi**.

Riêng 429 còn có nhánh thứ ba đứng trước cả hai: Z.AI/Zhipu dùng 429 cho
overload toàn server (not per-key) — nếu match `_OVERLOADED_PATTERNS` thì trả
`overloaded` (chỉ backoff, giữ nguyên credential), tránh "burning the pool
while the endpoint is still busy" (#14038, #15297).

### 1.3 `backend_identity.py` — trục nào bị lỗi làm mất hiệu lực

Câu hỏi lõi (trích nguyên văn docstring, dòng 3-5): *"is this candidate the
same backend as the one that failed, along the axis that failure
invalidated?"* — "provider" gộp chung 3 trục độc lập, mỗi loại lỗi vô hiệu hoá
1 trục khác nhau:

- **credential surface** (`FailureScope.CREDENTIAL`) — 401/402 giết chết mọi
  model, mọi host dùng chung key đó.
- **endpoint** (`FailureScope.ENDPOINT`) — DNS fail/connection refused giết
  chết mọi model đứng sau URL đó, bất kể model/credential.
- **model deployment** (`FailureScope.MODEL`) — timeout/overload/429/model
  không tương thích chỉ giết deployment của **một** model. Case thật: aux
  `glm-5.2` timeout trong khi `macaron-v1-venti` cùng endpoint vẫn phục vụ
  turn 448K-token bình thường (`backend_identity.py:22-25`).

Trước khi module này tồn tại, **6 call site ở 4 subsystem** tự implement
so sánh này theo cách khác nhau, và **5 incident riêng biệt** đều vá đúng 1
điểm rồi các điểm khác vẫn giữ bug — trích issue list ở docstring dòng 9-12:
`#22548` (alias cùng URL bị coi khác backend), `#70893` (xai-oauth vs xai
cùng host nhưng credential khác), `#59561` (aux chain skip nhầm sibling
model), `#72468` (**cùng bug lặp lại 3 tuần sau** ở site khác), `#62984 /
#54250 / #57584` (dedup bỏ qua base_url gộp nhầm nhiều endpoint pool thành
một). Đây là lý do module hoá thành 1 "single owner" thay vì sửa từng nơi.

Nguyên tắc bảo toàn: mọi trục chưa chứng minh được (`Optional` rỗng) phải trả
lời "khác nhau" (thử tiếp, tốn nhất 1 RTT) — không bao giờ trả "giống nhau"
(skip, tốn nhất là mất failover) — trích `same_credential_surface` docstring
dòng 133-135: *"Conservative on purpose: an unprovable axis must answer
'different'... rather than 'same'"*.

### 1.4 Credential pool rotation (`agent/credential_pool.py`, 3195 dòng)

Trạng thái 3 mức: `STATUS_OK` → `STATUS_EXHAUSTED` (TTL cooldown, tự phục hồi)
→ `STATUS_DEAD` (vĩnh viễn, chỉ gỡ bằng re-auth ghi đè — line 65-73). TTL theo
loại lỗi (line 118-131):

| lỗi | TTL cooldown |
|---|---|
| 401 | 5 phút |
| 429 | 1 giờ |
| default | 1 giờ |
| **sole credential** (không còn key nào khác để rotate) | 1 phút — trích: "an hour of hard failures with nothing to fall back to" bị thay bằng cooldown ngắn |

Chốt an toàn quan trọng nhất — `mark_exhausted_and_rotate` (`credential_pool.py:2048-2166`)
có **bộ đếm chặn vòng lặp vô hạn** `_unmatched_rotation_streak`: khi danh tính
credential lỗi không khớp bất kỳ entry nào trong pool (OAuth wrapper key xoay
runtime), không có bound thì retry loop chạy "~6/sec, starving the event
loop" mãi mãi (`#70401`, line 2111-2119). Cap ở "một vòng lặp qua hết entry
khả dụng" rồi surface lỗi thay vì đoán tiếp.

Một hazard đa-profile: refresh token là single-use, nên khi 1 profile refresh
và rotate token, nó phải write-through về `auth.json` root, nếu không **profile
khác đọc lại token cũ đã bị revoke** → chết theo domino `refresh_token_reused`
(`#48415` / `#43589`, `_write_through_provider_state_to_global_root` dòng
595-610). Bug refresh version 1 tự đóng cửa write-through sau lần refresh đầu
vì check "key đã tồn tại chưa" luôn đúng sau khi entry được tạo — sửa bằng
cách track **nguồn gốc** state đọc từ đâu (`#74339`, line 1203-1220).

### 1.5 Rate-limit guard xuyên tiến trình (`agent/nous_rate_guard.py`)

Trích nguyên văn lý do tồn tại (dòng 1-11): mỗi 429 từ Nous tạo ra **tới 9
lệnh gọi API mỗi turn** (3 SDK retry × 3 Hermes retry), mỗi lệnh đều tính vào
RPH — ghi state 429 vào 1 file dùng chung (`~/.hermes/rate_limits/nous.json`,
atomic write qua temp+rename) để **mọi session** (CLI/gateway/cron/aux) đọc
trước khi gọi, "eliminate the amplification effect".

Chống retry-amplification KHÔNG đồng nghĩa với "cứ 429 là trip breaker toàn
cục": `is_genuine_nous_rate_limit` (dòng 192-244) phân biệt (a) bucket của
chính caller cạn thật (breaker nên trip) khỏi (b) upstream model cụ thể tạm
hết công suất (breaker KHÔNG nên trip, vì Nous multiplex nhiều model sau 1
key — trip nhầm sẽ khoá luôn các model khác vẫn khoẻ). Bằng chứng dùng 2
tín hiệu: header `x-ratelimit-remaining-*`/`reset-*` của chính response 429,
và state "last-known-good" từ response thành công gần nhất; chỉ khi
`remaining==0` VÀ `reset >= 60s` mới coi là (a).

### 1.6 Jittered backoff (`agent/retry_utils.py:90-128`)

```
delay = min(base_delay * 2^(attempt-1), max_delay) + uniform(0, jitter_ratio*delay)
```
Seed decorrelate bằng `time_ns() XOR (counter*0x9E3779B9)` — không chỉ dựa
vào clock thô để 2 request khởi tạo cùng millisecond vẫn ra jitter khác nhau.
Thundering herd bị chặn: "multiple sessions hitting the same rate-limited
provider concurrently" (docstring dòng 3-5) — không có jitter, N session cùng
bị 429 sẽ đồng loạt retry đúng cùng thời điểm exponential-backoff, tạo đợt
sóng 429 thứ hai. Ngoài core function còn có 1 policy theo provider cụ thể
(Z.AI GLM-5.2 overload 1305) chuyển từ short exponential sang bảng
30/60/90/120s sau 3 lần thử đầu — minh chứng: policy backoff không nhất
thiết là hằng số toàn cục, có thể theo (base_url, model).

### 1.7 Timeout: deadline của ta vs của provider

`agent/deadline.py` (đã đọc trước, xác nhận lại điểm nối): trích nguyên văn
design invariant (dòng 53-57): *"A timeout produced by this layer is OUR
deadline, not the provider's. Callers that feed errors into
`error_classifier.py` should classify `DeadlineExpired` distinctly from
transport timeouts (the #59549 / #80323 misattribution class)."* Tức là có
**2 loại timeout khác bản chất**: (1) ta tự cắt vì đã chờ đủ ngân sách thời
gian của MÌNH (deadline layer, dùng `threading.Timer` daemon vì không tin
tưởng asyncio timer khi event loop bị block đồng bộ), (2) provider/transport
tự báo "tôi không trả lời kịp" (httpx timeout/connection error) — 2 cái này
nếu bị gộp chung 1 nhãn thì log sẽ đổ lỗi sai bên.

Bổ sung ở `error_classifier.py` §7b: circuit breaker "5 lần liên tiếp không
phản hồi" là **lỗi cục bộ trước khi có network call** (`_check_stale_giveup`),
KHÔNG phải transport timeout — nếu phân loại nhầm thành `unknown` thì retry
loop đốt hết `max_retries` để chạm circuit breaker N lần với network overhead
= 0 trước khi mới fallback (line 1109-1129).

`agent/bounded_response.py` giải quyết một lớp khác: đọc thân lỗi streaming
403+ không bị "unbounded" theo 2 chiều — (1) server tuyên bố body khổng lồ →
tràn RAM, (2) server mở body rồi treo mãi không gửi thêm byte → hang vô hạn.
Vì `httpx.iter_bytes()` **block bên trong socket read**, kiểm tra wall-clock
giữa 2 chunk không cắt được 1 lần đọc đang treo — nên phải chạy đọc trên
1 daemon thread và caller đợi có hard deadline, timeout thì `response.close()`
để hủy đọc (ported từ `openclaw/openclaw#95108`).

### 1.8 Context overflow vs output-cap (`agent/model_metadata.py`)

`parse_available_output_tokens_from_error` + `is_output_cap_error`
(dòng 1617-1838) phân 2 lỗi 400 nhìn giống nhau nhưng recovery ngược nhau,
trích nguyên văn (dòng 1620-1626):
```
1. "Prompt too long" — INPUT vượt context window. Fix: compress history.
2. "max_tokens too large" — input ổn, nhưng input+requested_output > window.
     Fix: giảm max_tokens cho lần gọi này. KHÔNG đụng context_length.
```
Lý do phải tách: nếu lỗi output-cap bị đọc lầm thành context-overflow, retry
loop sẽ compress input (vốn đã fit) rồi gọi lại với **max_tokens vẫn to như
cũ**, provider từ chối lại y hệt, session "death-loop" tới khi "cannot
compress further" (`#55546`, DashScope). Cả hai hàm parse theo 6+ format lời
văn khác nhau tuỳ vendor (Anthropic `available_tokens:`, DashScope
`Range of max_tokens should be [1, N]`, vLLM `at least N input tokens`, ...).
Có 1 case bù trừ tinh vi: vLLM khi max_tokens là ràng buộc chính, số
"input tokens" nó báo là suy diễn ngược từ max_tokens (không đo thật) — công
thức tổng quát walk giảm cap ~65 token/lần không bao giờ hội tụ, code phát
hiện dạng suy biến này và **halving cap trực tiếp** thay vì trừ margin.

---

## 2. Kiến trúc Subagent

### 2.1 Subagent được cấp gì / bị cắt gì (`tools/delegate_tool.py`, `_build_child_agent` dòng 1578-1757+)

- **Conversation hoàn toàn mới** — không thấy lịch sử parent; nhận
  `ephemeral_system_prompt` build riêng từ goal+context.
- **`skip_context_files=True`, `skip_memory=True`** — không đọc file ngữ cảnh
  dự án và không đụng `MEMORY.md` chung (line 1956-1957).
- **`clarify_callback=None`** — không được hỏi lại người dùng (đúng với
  `DELEGATE_BLOCKED_TOOLS` chặn cả tool `clarify` — line 51-56).
- **Toolset = giao của (toolset cha) ∩ (toolset caller yêu cầu) − blocked
  set** — không bao giờ "gained tools the parent lacks" (line 1656). Blocked
  cứng: `delegate_task` (không đệ quy), `clarify`, `memory`, `send_message`,
  `cronjob` (line 50-56) — trừ khi role=`orchestrator` thì được trả lại
  toolset `delegation` (line 1699-1700), và chỉ khi độ sâu còn dưới
  `max_spawn_depth` (mặc định `MAX_DEPTH=1`: cha(0)→con(1), cháu bị chặn).
- **Budget iteration riêng, KHÔNG chia sẻ với cha**: `iteration_budget.py`
  docstring dòng 1-9 nói thẳng — cha mặc định `max_iterations=500`
  (`cli.py:16845`), mỗi subagent mặc định `delegation.max_iterations=50`
  (`_build_child_agent(..., iteration_budget=None  # fresh budget per
  subagent)`, line 1975) — nghĩa là **tổng số iteration của cả cây có thể
  vượt cap của cha**, việc kiểm soát tổng chi phí là trách nhiệm của người
  cấu hình, không phải cơ chế tự động.
- **Approval callback riêng cho thread con**: vì subagent chạy trên
  `ThreadPoolExecutor` worker không kế thừa threading-local approval callback
  của CLI, mặc định auto-DENY lệnh nguy hiểm (`_subagent_auto_deny`,
  line 78-90), chỉ auto-approve khi user set
  `delegation.subagent_auto_approve: true` — luôn log `warning` để audit.
- **Session/kế thừa provider**: kế thừa `api_key`/`base_url` của cha trừ khi
  có `override_*` từ config delegation (route subagent sang model rẻ hơn).

### 2.2 Delegation nền (background) (`tools/async_delegation.py`)

Kiến trúc: 1 daemon `ThreadPoolExecutor` module-level (không dùng
`with` block để tránh join lúc thoát) chạy con, khi xong đẩy event
`type="async_delegation"` vào **`process_registry.completion_queue`** —
CÙNG hàng đợi mà CLI/gateway đã poll khi agent idle. Lý do tái dùng thay vì
tự viết drain loop mới (docstring dòng 13-20, trích nguyên văn): kết quả chỉ
surfaces như **1 turn MỚI** khi agent đang idle, "never spliced between a
tool result and an assistant message" — giữ nguyên bất biến cứng "never
mutate past context" và tính hợp lệ role-alternation + prompt cache.

Payload hoàn chỉnh (goal gốc, context, toolsets, model, thời điểm dispatch,
status, tóm tắt kết quả đầy đủ) — vì "the parent may be deep in unrelated
context and won't remember why the subagent existed" (dòng 24-27).

**`output_schema` (`tools/delegation_output_schema.py`, 151 dòng, đầy đủ)**:
caller có thể truyền JSON Schema; child nhận 1 khối "OUTPUT CONTRACT" nối vào
context; parent validate câu trả lời cuối bằng `jsonschema`; sai thì gửi
**đúng 1** turn retry duy nhất kèm lỗi verbatim, KHÔNG paste lại schema —
`MAX_SCHEMA_RETRIES = 1`, lý do (dòng 22-24): "More retries make frontier
models drop fields that were right the first time."

### 2.3 Worktree isolation (`tools/subagent_worktree.py`, 352 dòng, đầy đủ)

Opt-in (`delegation.worktree_isolation: true`, mặc định `false`), chỉ git,
chỉ terminal backend local (docker/ssh/modal thì worktree tạo trên host
không thấy được trong sandbox → bỏ qua có log, không half-apply). Mỗi con
1 worktree tại `<repo>/.worktrees/subagent-<id>` trên branch
`hermes-subagent/<id>` nhánh từ HEAD hiện tại của cha. Prune chỉ khi **CẢ 2**
git probe (`rev-list --count`, `status --porcelain`) thành công VÀ chứng minh
0 commit + tree sạch — nếu probe fail thì **giữ nguyên worktree**, gắn cờ
`inspection_failed=True` + note giải thích, KHÔNG bao giờ coi "trạng thái
không đo được" là "coi như trống" (fail-safe cho `#88113`, trích nguyên văn
dòng 27-31: "if a git inspection probe fails the state is unknown, so the
worktree is kept").

### 2.4 Mixture-of-Agents (`agent/moa_loop.py`, 2453 dòng)

Fan-out song song sang N "reference model" (`ThreadPoolExecutor`,
`_run_references_parallel`), mỗi model advise độc lập; aggregator (model
đang act chính) nhận toàn bộ output các reference dán vào context làm
"guidance block" rồi tự tổng hợp câu trả lời cuối — Hermes KHÔNG chọn 1 câu
trả lời tốt nhất, chỉ đưa reference làm ngữ cảnh cho model chính quyết định.

**"Cache MISS" nghĩa là gì** (`MoAChatCompletions.__init__`, dòng 1561-1571,
trích nguyên văn): fan-out được re-run mỗi khi **state hội thoại tiến lên**
(user message mới HOẶC tool result mới) — cache key là "signature" của view
render ra cho reference models; đổi signature = cache MISS = advisor chạy
lại thật (tốn tiền, ghi usage/cost); trùng signature = cache HIT = trả kết
quả cũ, không re-run, không tính phí lần 2. Đây là cơ chế "fire on every
new state, skip on no-op re-call" — chứ KHÔNG phải cache đúng nghĩa để tiết
kiệm tiền tuỳ ý.

Kiểm soát chi phí: mặc định `every_n` cadence "user_turn" — advisor chỉ chạy
1 lần mỗi user turn, các tool-iteration sau tái dùng (`#67199`); có policy
`every_n:<N>` là trung gian giữa "chạy mọi iteration" (đắt, latency × độ sâu
tool loop) và "chỉ 1 lần/turn" (`#63393`). `reference_max_tokens` CHỈ áp cho
fan-out, cuộc gọi tổng hợp của aggregator không giới hạn (từng bị hardcode
cap làm cắt cụt câu trả lời dài, `#53580`).

### 2.5 Chống mangled edit đa-subagent (`tools/file_state.py`, 332 dòng, đầy đủ)

`FileStateRegistry` process-wide, 3 bảng: read stamp theo (task_id, path) →
(mtime, ts, partial); last-writer toàn cục theo path → (task_id, ts);
per-path `threading.Lock`. `check_stale(task_id, path)` gọi **TRƯỚC** mỗi
write, trả cảnh báo theo 3 mức nghiêm trọng giảm dần: (1) sibling subagent
đã ghi file này SAU LẦN ĐỌC GẦN NHẤT của agent hiện tại → nguy cơ đè mất
thay đổi của sibling; (2) mtime trên đĩa khác mtime lúc đọc (external edit
không rõ ai); (3) agent chưa từng đọc file này. Bổ sung `lock_path(path)`
context-manager để bọc cả khối read→modify→write — path khác nhau chạy song
song, cùng path serialize. Đây trực tiếp giải quyết case "subagent B viết
file mà subagent A đã đọc trước đó, A viết tiếp theo sẽ đè mất B" — độc lập
với check overlap-path trong 1 agent đơn (`run_agent._should_parallelize_tool_batch`).

---

## 3. Toàn bộ số hiệu issue/PR trong docstring + bài học 1 dòng

| File | Issue/PR | Bài học 1 dòng |
|---|---|---|
| error_classifier.py | #14038, #15297 | 429 không luôn là rate-limit — Z.AI dùng 429 cho overload server, phải đọc body trước khi rotate credential |
| error_classifier.py | #18028 | Refusal an toàn có thể không mang status code (Codex SDK) — match theo message trước khi rơi vào `unknown` |
| error_classifier.py | #32421 | Filter name cụ thể của provider ("new_sensitive") an toàn hơn từ khoá chung ("policy") để tránh đụng nhánh khác |
| error_classifier.py | opencode#37848 (ported) | "throttling" dễ bị nhầm với "too many tokens" (context overflow) — check throttle trước |
| error_classifier.py | opencode#40707 (ported) | Lỗi serialize giữa dòng không status code, nếu chỉ match theo type sẽ đốt hết retry ở `unknown` trước khi fallback |
| error_classifier.py | PR #58446 | Thông báo "model không hỗ trợ tool" xác định (deterministic) phải fail nhanh, không rơi vào `unknown` retryable |
| error_classifier.py | NemoClaw#4846 | Idle-kill ~120s của gateway cloud dễ giả làm context-overflow trên reasoning model có pha suy nghĩ dài |
| error_classifier.py | #52310 | Reclassify disconnect trên reasoning model thành timeout, không context_overflow — tránh xoá lịch sử hội thoại nhầm |
| error_classifier.py | #55933 | Lỗi shape adapter cục bộ (MoA) không nên fallback sang model khác — sẽ đổi ngầm route MoA của user |
| error_classifier.py | #78796 | 404 trống không tên gì (NVIDIA NIM) vẫn phải nhận diện chắc là model sai id, không đốt 3 lần retry |
| error_classifier.py | #82154 | Cùng 1 thân lỗi 400 có thể là billing thật HOẶC content-filter — gắn cờ "unverified" thay vì assert chắc |
| backend_identity.py | #22548 | Alias khác tên cùng URL vẫn là 1 backend — đừng so sánh bằng label |
| backend_identity.py | #70893 | Cùng host khác provider label (`xai` vs `xai-oauth`) có thể là credential khác — provider label KHÔNG suy ra endpoint |
| backend_identity.py | #59561, #72468 | 1 bug lặp lại đúng dạng ở 2 call site cách nhau 3 tuần — chứng minh cần 1 module owner logic, không sửa rời rạc |
| backend_identity.py | #62984, #54250, #57584 | Dedup bỏ qua base_url gộp nhầm nhiều endpoint riêng biệt (1 pool) thành 1 |
| credential_pool.py | #82154 | Verdict billing chưa chắc → cooldown ngắn hơn, tránh giam key khoẻ 1 giờ |
| credential_pool.py | #58265 | Log "no entries" không throttle sẽ storm cross-process file lock trên Windows, treo event loop |
| credential_pool.py | #48415, #43589 | Refresh token single-use rotate ở 1 profile phải write-through về root, không thì profile khác chết theo |
| credential_pool.py | #70401 | Rotation không khớp identity phải có bound — nếu không retry ~6/s vô hạn, đói event loop |
| credential_pool.py | #32849 | Lỗi OAuth vĩnh viễn (revoked) phải chuyển DEAD hẳn, không hưởng TTL 1h rồi lặp lại mỗi giờ |
| credential_pool.py | #74339 | Check "key đã tồn tại" tự đóng cửa write-through sau lần đầu — phải track nguồn state đọc từ đâu |
| credential_pool.py | #43747 | Cooldown theo `reset_at` có thể lỗi thời khi quota mở lại sớm hơn dự kiến — cần probe sống để mở khoá sớm |
| credential_pool.py | #79156 | credential_id và api_key thực tế mâu thuẫn — phải tin key thực sự gửi request, không tin id đã stale |
| credential_pool.py | PR #4210 | Không tự động đọc credential ngoài (Claude Code) khi user chưa cấu hình rõ provider — vi phạm consent |
| credential_pool.py | #15099 | Thiếu `obtained_at` làm token mới trông "già" hơn thật, ảnh hưởng logic pruning theo tuổi |
| credential_pool.py | #9331 | Thiếu env var ở 1 process không được xoá pool entry của MỌI process khác (destructive read) |
| transports/chat_completions.py | #17426 | Field riêng của Gemini (`thinking_config`) gửi cho Gemma → 400 — phải gate theo tên model cụ thể |
| transports/chat_completions.py | #47868 | Field debug nội bộ lọt ra ngoài bị provider strict từ chối — phải strip trước khi gửi wire |
| transports/chat_completions.py | #58755 | Chuẩn hoá 1 nơi, không phải mọi payload path đều đi qua layer chung |
| transports/chat_completions.py | #61871 | Format usage riêng của DeepSeek native (`prompt_cache_hit_tokens`) khác OpenAI-compat — cần đọc theo alias |
| transports/chat_completions.py | #78941, #79017 | Cache key phải theo scope logic (session/compression-lineage), không theo session_id vật lý — sống sót qua rotate |
| transports/chat_completions.py | #89503 | Giá trị effort mở rộng riêng của app (`ultra`) phải clamp về vocabulary chuẩn trước khi gửi OpenAI-compat wire |
| deadline.py | #43272, #53161, #63302 | Timeout hardcode / env var tự phát ("HERMES_*_TIMEOUT") bỏ qua config người dùng — cần 1 nơi resolve chung |
| deadline.py | #83220 | Timeout do user nhập lớn tràn `time_t` trên macOS trong `Lock.acquire(timeout=...)` — cần clamp platform-safe |
| deadline.py | #84047 | Khi event loop bị block đồng bộ, mọi asyncio timeout trong process bị vô hiệu hoá ngầm |
| deadline.py | #63309 | Deadline phải chạy bằng `threading.Timer` daemon, không tin asyncio timer khi loop có thể bị block |
| deadline.py | #71148, #59549, #84967, #68139 | Kill-on-timeout không giết cả cây tiến trình con → để lại orphan |
| deadline.py | #59549, #80323 | Nhầm deadline CỦA TA với timeout CỦA PROVIDER là 1 lớp lỗi phân loại riêng, cần class `DeadlineExpired` tách biệt |
| deadline.py | #85125 | 6 cơ chế deadline cục bộ khác nhau cho 6 incident khác nhau — hợp nhất về 1 tầng chung mới chặn được lớp bug này |
| bounded_response.py | openclaw#95108 (ported) | Đọc thân lỗi streaming không cap byte + deadline cứng sẽ hang vô hạn nếu server treo giữa chunk |
| model_metadata.py | #15779 | `/model switch` quên đọc context_length riêng của user, rơi về fallback 128K sai |
| model_metadata.py | #22268 | Metadata tĩnh lệch với con số live của OpenRouter — phải đồng bộ cache và fallback |
| model_metadata.py | #46620 | Timeout urllib3 phẳng (10s mỗi retry stage) qua proxy 403-CONNECT phình thành nhiều phút — cần (connect, read) tách riêng |
| model_metadata.py | #50372 | Bảo đảm string immutable + id-equality để cache fingerprint không bị alias giả |
| model_metadata.py | #63122 | Modelfile num_ctx khác GGUF training max — chọn nhầm cái lớn hơn tạo "false-safe window" khi compress |
| model_metadata.py | #55546 | Output-cap error bị đọc lầm thành context-overflow → compress vô ích, session chết loop |
| model_metadata.py | #84482, #8731 | Context length sai trong catalog bên thứ 3 hoặc model custom/local cần đường tự-unblock qua config, không chờ network probe |
| delegate_tool.py | #10213 | Endpoint chỉ nói Anthropic Messages protocol phải được tự nhận diện, không mặc định chat_completions rồi 404 |
| delegate_tool.py | #10760, #63169 | Session không có nơi nhận kết quả detached (HTTP one-shot, cron worker) phải fallback về chạy đồng bộ |
| delegate_tool.py | #14726 | Subagent "timeout 300s, 0 API call" mà không log gì — cần dump chẩn đoán trước khi gọi API |
| delegate_tool.py | #16816 | Không kế thừa ACP transport của cha khi con đổi provider — kế thừa nhầm bỏ qua override credential |
| delegate_tool.py | #20558/#20563 | `api_mode` không được kế thừa khi con dùng provider khác cha — mỗi provider có API surface riêng |
| delegate_tool.py | #60203, #62151 | Thread phụ (interrupt worker, daemon-pool) làm subagent trông "kẹt" giống provider chậm — cần dump tên+stack thread |
| delegate_tool.py | #64240, #64484 | Completion event không khoá theo session key đúng cách sẽ rò rỉ sang consumer không liên quan hoặc bị khoá chặn nhầm |
| delegate_tool.py | PR #71508 | Đo "còn sống" của batch nền bằng token stream, không chỉ bằng số lần gọi API hoàn tất |
| delegate_tool.py | #7833 | 2 custom endpoint khác nhau bị coi như hoán đổi được, con kế thừa nhầm pool của cha, đè mất base_url đã chỉ định |
| delegate_tool.py | #80450 | Transport pin cứng qua config phải fail loud nếu binary không có trên PATH, không âm thầm rơi về default |
| delegate_tool.py | #81141 | Heuristic phát hiện "goal giả" (todo/task N) không được đụng vào code hợp lệ chứa placeholder cú pháp |
| delegate_tool.py | #81267 | Handle log của con bị đóng khi con vẫn còn flush trên daemon thread → transcript mất âm thầm |
| delegate_tool.py | #9126 | Tổng ngân sách tóm tắt của N subagent phải chia theo N, không thì cả batch cùng vượt cửa sổ context của cha |
| delegate_tool.py | Kilo-Org/kilocode#9448 (ported) | Footer chi phí phải gộp cả spend của subagent, không chỉ API call trực tiếp của cha |
| async_delegation.py | #51690 | Metadata "stall" nên additive, chỉ xuất hiện khi có finalize từ stall-monitor, không phá format cũ |
| async_delegation.py | #55578 | Subagent nền của 1 session đã kết thúc phải bị chấm dứt theo — không thì orphan rò rỉ vào chat khác hoặc đốt token vô ích |
| async_delegation.py | #57498 | Route completion theo session id đã ghim từ lúc spawn, không suy luận lại "row mới nhất" — tránh route sai đích |
| async_delegation.py | #69567/#69594 | Không đóng connection sqlite tường minh sẽ leak fd/WAL, chạm `RLIMIT_NOFILE` trên gateway dài hạn |
| subagent_worktree.py | #88113 | Probe git fail phải coi trạng thái là KHÔNG BIẾT — giữ nguyên worktree, không suy luận "0 commit = an toàn xoá" |
| moa_loop.py | #53580 | Cap max_tokens cứng cho lời tổng hợp của aggregator từng cắt cụt câu trả lời dài |
| moa_loop.py | #53802 | Sau fallback+restore, callback hiển thị phải được rebind, không thì UI im lặng mất tiến độ suốt phần còn lại session |
| moa_loop.py | #59959 | Output của reference model có thể lộ PII người dùng paste vào — cần filter riêng cho UI/trace/aggregator |
| moa_loop.py | #60345 | Reference model có context window nhỏ hơn aggregator cần trim riêng, không thì 400 bị nuốt thành "[failed]" âm thầm |
| moa_loop.py | #63393 | Chạy advisor mọi tool-iteration nhân chi phí theo độ sâu tool loop — cần cadence trung gian |
| moa_loop.py | #64187 | Override reasoning effort theo model của từng slot phải áp trước global, không thì aggregator chạy default câm lặng |
| moa_loop.py | #66793 | Resolve lại toàn bộ preset+runtime mỗi iteration gây "đứng hình" 5-30s — phải cache cho đời turn |
| moa_loop.py | #67199 | Cadence rẻ nhất mặc định là 1 lần/user-turn, không phải mọi iteration |
| moa_loop.py | #72626 | Cấu trúc "peel" tách phần hướng dẫn tuần hoàn khỏi cache phải đồng bộ tuyệt đối 2 phía tạo/gỡ, lệch là cache breakpoint rơi sai chỗ |
| moa_loop.py | #76085, #84733 | Cache TTL cấu hình có thể bị policy per-destination hạ ngầm (1h→5m) — phải stamp rõ nguồn cấu hình |
| thread_context.py | #33057, #30882 | Worker thread trần mất ContextVar approval → lệnh nguy hiểm tự động auto-approve sai chế độ |
| thread_context.py | GHSA-qg5c-hvr5-hjgr / #15216 | Worker thread mất callback approval CLI → không thể hỏi lại user, phải fail-closed |

---

## 4. Bài học tổng hợp (cross-cutting)

1. **1 module "owner" cho mỗi loại quyết định lặp lại nhiều nơi.** `backend_identity.py`
   và `file_state.py` đều sinh ra sau khi cùng 1 bug tái diễn ở nhiều call
   site khác nhau (#59561→#72468, #62984/#54250/#57584). Bài học: nếu logic
   "có nên coi 2 thứ là giống nhau/đè nhau không" xuất hiện > 1 nơi, tách
   module ngay lần thứ 2.
2. **Không tin unprovable axis.** Cả `backend_identity.same_credential_surface`
   và `subagent_worktree.finalize` đều chọn "an toàn hơn" khi thiếu chứng cứ
   — trả "khác nhau"/"giữ lại" thay vì đoán "giống nhau"/"xoá". Chi phí sai
   một chiều rẻ hơn chiều khác rất nhiều.
3. **Phân loại lỗi theo NGUYÊN NHÂN THẬT, không theo status code.** 429 là
   3 nguyên nhân khác nhau (overload/rate_limit/upstream_rate_limit), 400 là
   ít nhất 6 nguyên nhân khác nhau (context/output-cap/thinking-sig/policy/
   format/grammar) — mỗi nguyên nhân đúng 1 recovery, sai nguyên nhân = sai
   recovery = death-loop hoặc đốt credential vô cớ.
4. **Cross-process state khi nhiều tiến trình share 1 quota.** `nous_rate_guard.py`
   tồn tại đúng vì lý do Stock_Massive đang có: nhiều tiến trình (CLI/gateway/
   cron) share 1 route/quota. Nếu không có state chia sẻ, mỗi tiến trình tự
   retry độc lập nhân tổng số request lên gấp N.
5. **Budget/ngân sách của con độc lập với cha, tổng có thể vượt cha.** Đây là
   quyết định thiết kế CÓ Ý, không phải bug — Hermes không tự động giới hạn
   tổng chi phí cây subagent, để người cấu hình tự chịu trách nhiệm.
6. **1 retry bounded tốt hơn N retry không bounded.** `output_schema` chỉ cho
   đúng 1 retry (model "quên" field đúng nếu retry nhiều); `MAX_SCHEMA_RETRIES=1`
   là quyết định đo được, không phải mặc định tuỳ tiện.

---

## 5. Port sang `apps/api/src/core/llm/*` — xếp theo mức giảm 36% turn chết

Đối chiếu code thật: `route_error` (nhánh `except LLMError` chung ở
`apps/api/src/agent/loop.py:744-758`) là **catch-all** khi `classify_status`
(`errors.py:279-303`) không rơi vào 1 trong 4 nhánh named (401/403, 429,
408/5xx) — nghĩa là MỌI lỗi 400 (bad request, context overflow, output-cap,
content policy, model không tồn tại...) hiện nay đổ chung vào 1 `LLMError`
vô hình dạng, Turn chết không có recovery hint. Đây chính là lỗ hổng taxonomy
mà `error_classifier.py` của Hermes được sinh ra để vá — xếp theo tác động
giảm tỷ lệ chết:

1. **Mở rộng `classify_status` cho nhánh 400** (chưa có, hiện fallthrough về
   `LLMError` chung cuối hàm `errors.py:302`) — port tối thiểu 2 phân biệt
   từ `model_metadata.parse_available_output_tokens_from_error` /
   `is_output_cap_error`: thêm 1 exception `ContextOverflow` (input quá dài
   → nên có route xử lý khác — nén/rút gọn tool result — không phải bug của
   route) và giữ output-cap (max_tokens quá lớn) là lỗi **retryable với
   max_tokens nhỏ hơn**, không lẫn với input-too-long. Đây là ứng viên số 1
   vì `route_error` đang chiếm 1/4 số turn chết trong mẫu đo và hiện KHÔNG
   có recovery path nào — chỉ cần thêm nhánh nhận diện + log rõ nguyên nhân
   thật đã tự nó giảm số "route_error" mù mờ, dù chưa auto-recover.
2. **Cross-process rate-limit breaker kiểu `nous_rate_guard.py`** — Collector
   (job nền) và API (request người dùng) đang **share cùng 1 route + cùng
   quota vnstock/LLM_BASE_URL** nhưng KHÔNG có state chia sẻ nào giữa 2
   process. Nếu route 429, Collector vẫn tiếp tục gọi vô tư trong khi API
   cũng retry độc lập → nhân đúng lớp "retry amplification" mà module này
   tồn tại để chặn. Port dạng tối giản: 1 file JSON tại
   `HERMES_HOME`-equivalent (ví dụ `var/rate_limits/route.json`), ghi atomic
   khi `RouteRateLimited` được raise (đã có class sẵn, chỉ thêm hook ghi
   file ở `client.py` hoặc `transport.py._classified`), đọc trước khi dispatch
   ở cả 2 process. Không cần độ tinh vi "genuine vs upstream" của Hermes vì
   route hiện là single-model, single-key.
3. **Jittered backoff thay `wait_exponential` cố định** (`client.py:70`,
   hiện `wait_exponential(multiplier=0.5, max=4)` không jitter) — port
   `jittered_backoff()` nguyên công thức từ `retry_utils.py:90-128`. 2
   process (Collector+API) cùng bị `GatewayTimeout` cùng lúc sẽ retry đúng
   cùng nhịp exponential không jitter → tự tạo sóng request thứ 2. Đổi 3
   dòng, rủi ro gần như 0, lợi ích trực tiếp với chính vấn đề "3 gateway_timeout
   trong 7 ngày".
4. **Bound việc đọc thân lỗi streaming** (`transport.py:126`,
   `body = (await response.aread()).decode(...)` khi status ≥ 400 trong
   nhánh streaming) — hiện KHÔNG có cap byte lẫn deadline riêng, chỉ dựa vào
   `httpx.Timeout(request_timeout_seconds)` tổng của cả request. Nếu proxy
   trả 400+ rồi treo giữa thân lỗi, `aread()` có thể chờ tới hết 120s trước
   khi raise — trùng đúng với `gateway_timeout` đang được đo, nhưng thực ra
   là "đọc lỗi bị treo" chứ không phải "route không trả lời". Port ý tưởng
   (không cần port nguyên `bounded_response.py` 148 dòng): cap
   `response.aread()` bằng `asyncio.wait_for` với deadline riêng ngắn hơn
   (vài giây), fallback đọc phần đã có nếu timeout.
5. **Tách `DeadlineExpired` khỏi `GatewayTimeout`** — hiện `_timeout()`
   (`transport.py:266-269`) gộp mọi `httpx.RequestError` (kể cả
   `TimeoutException`) thành `GatewayTimeout`, đúng với thiết kế 1-lớp hiện
   tại. Nếu sau này thêm 1 deadline tầng ứng dụng (ví dụ ngân sách thời gian
   của 1 Turn tổng, không phải của 1 API call), phải tách 2 khái niệm ngay
   từ đầu như `deadline.py` cảnh báo (#59549/#80323 misattribution) — ghi
   chú thiết kế cho tương lai, chưa cần code ngay vì hiện chưa có deadline
   tầng Turn.

**Không xếp cao** (dù liên quan trực tiếp taxonomy) — phân biệt
`rate_limit` vs `upstream_rate_limit`: route hiện là 1 proxy OpenAI-compatible
đơn (`LLM_BASE_URL`), chưa rõ có multiplex nhiều upstream model hay không
(câu hỏi mở, mục 7). Nếu route không phải aggregator, phân biệt này vô nghĩa.

---

## 6. Subagent có đáng cho dự án này không — trả lời thẳng

**Không, không đáng — ở quy mô và use-case hiện tại.**

Lý do:
- Stock_Massive là nền tảng dữ liệu chứng khoán với 1 route batch + 1 route
  session, KHÔNG phải coding agent đa bước cần phân rã goal tự do thành
  nhiều subtask độc lập (đó là lý do `delegate_tool.py` tồn tại ở Hermes —
  1 agent lập trình cần "đi làm nhiều việc song song rồi tổng hợp").
- Chi phí duy trì tương xứng: `delegate_tool.py` riêng đã 4926 dòng,
  cộng `async_delegation.py` (1603), `moa_loop.py` (2453),
  `subagent_worktree.py` (352) — một hệ thống lớn hơn TOÀN BỘ
  `apps/api/src/core/llm/*` hiện tại (3259 dòng) gộp lại nhiều lần, cho 1
  use-case (multi-agent orchestration) chưa được yêu cầu bởi bất kỳ tính
  năng nào của Stock_Massive.
- Rủi ro vận hành đi kèm không nhỏ: cần iteration budget riêng, approval
  callback riêng cho thread, worktree isolation, output-schema validation,
  file-state registry chống mangled edit — tất cả tồn tại để giải quyết vấn
  đề **do chính kiến trúc subagent tạo ra**, không phải vấn đề Stock_Massive
  đang có.

Nếu tương lai có nhu cầu cụ thể (ví dụ: "phân tích song song N mã CP, mỗi mã
1 lời gọi LLM độc lập, tổng hợp báo cáo"), pattern rẻ và độc lập đáng học lại
là **`delegation_output_schema.py`** (151 dòng, tách biệt hoàn toàn khỏi
subagent framework) — validate JSON output với 1 retry bounded — chứ không
phải toàn bộ kiến trúc subagent.

---

## 7. Không port gì — và vì sao

- **`credential_pool.py` (3195 dòng) toàn bộ** — Stock_Massive dùng 1 API key
  tĩnh cho route (`config.py: LLMRoute.api_key`), không multi-provider,
  không OAuth, không cần rotation. Port cơ chế này là giải quyết vấn đề
  không tồn tại.
- **`backend_identity.py` full mechanism** — chỉ có ý nghĩa khi có ≥ 2
  candidate để so sánh (fallback model, credential pool). Route hiện tại
  không có fallback chain. Port sớm là đầu tư cho kiến trúc chưa quyết định
  có cần hay không.
- **`ssl_guard.py` / `ssl_verify.py`** — dành cho corporate CA bundle/proxy
  TLS-inspecting của người dùng cuối cài Hermes trên máy cá nhân đa dạng hệ
  điều hành. `LLM_BASE_URL` của Stock_Massive là 1 endpoint hạ tầng biết
  trước, không cần cơ chế phát hiện CA bundle hỏng.
- **Toàn bộ subagent/MoA/worktree** — theo lý do đã nêu ở mục 6.
- **`model_metadata.py` (3607 dòng)** — catalog context-length/pricing đa
  provider (OpenRouter, models.dev, Ollama...). Stock_Massive chỉ có 2 model
  tên cố định qua `Settings` (`llm_model_batch`, `llm_model_session`) và đã
  có `probe.py` tự kiểm tra khả năng model lúc boot theo đúng nhu cầu của
  chính nó — không cần trùng lặp 1 catalog đa-provider.
- **`command_token_source.py` (`key_cmd`)** — hữu ích khi route dùng SSO/IAM
  broker cấp token ngắn hạn. Route hiện tại dùng static API key qua env; chỉ
  đáng xem lại nếu tương lai đổi sang credential ngắn hạn (ghi chú ở mục 8).

---

## 8. Câu hỏi chưa giải quyết

- `route_error:1` trong 7 ngày đo được là lỗi cụ thể gì (400 gì, hay
  "no choices", hay JSON không parse được)? Cần log body thật trước khi
  quyết định thêm bao nhiêu nhánh phân loại ở mục 5.1 — không nên đoán và
  port toàn bộ taxonomy 400 của Hermes nếu chỉ 1 nguyên nhân cụ thể lặp lại.
- `LLM_BASE_URL` có multiplex nhiều model/upstream provider phía sau (như
  Nous Portal/OpenRouter) hay là 1 endpoint single-model thật? Quyết định
  toàn bộ mục "không xếp cao" ở phần 5 (rate_limit vs upstream_rate_limit).
- Collector và API có chạy trong CÙNG container/process hay khác container?
  Nếu khác container hoàn toàn tách biệt filesystem, cơ chế "file chia sẻ" ở
  mục 5.2 cần đổi sang Redis (đã có `src/core/redis` sẵn trong repo) thay vì
  file JSON — chưa xác nhận được từ code đã đọc trong phạm vi nhiệm vụ này.
- Có kế hoạch thêm model fallback (đổi sang model/provider khác khi route
  chết) trong tương lai gần không? Nếu có, nên đầu tư `backend_identity`-style
  ngay khi thiết kế fallback đầu tiên, tránh lặp lại đúng lớp bug #59561/#72468
  (sửa 1 nơi, quên chỗ khác).

---

Status: DONE
Summary: Đã đọc đầy đủ error_classifier/backend_identity/credential_pool/nous_rate_guard/retry_utils/deadline/bounded_response/model_metadata (Phần A) và delegate_tool/async_delegation/output_schema/subagent_worktree/moa_loop/file_state (Phần B), đối chiếu trực tiếp với apps/api/src/core/llm/* và agent/loop.py để xếp hạng port theo tác động thật lên route_error/gateway_timeout đã đo.
Concerns: 3 câu hỏi mở ở mục 8 cần xác nhận từ người vận hành trước khi bắt tay port mục 5.1/5.2 — đặc biệt route_error thật là gì và Collector/API có tách container hay không.
