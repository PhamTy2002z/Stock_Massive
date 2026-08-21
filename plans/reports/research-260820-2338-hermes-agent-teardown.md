# Hermes Agent — mổ code, rút tinh hoa, và cái gì đem được sang Stock_Massive

Đọc trực tiếp source (`NousResearch/hermes-agent`, MIT, sparse clone 2026-08-20).
Không đọc README.

Quy mô: **4.457 file Python / 71 MB**. Riêng `agent/` là 141 file / 126.055 dòng,
`tools/` 127 file / 123.448 dòng. Vòng lặp hội thoại `agent/conversation_loop.py`
một mình **8.436 dòng**. Để so: toàn bộ `apps/api/src/agent` của ta là 13.151 dòng.

Kết luận sớm để đọc phần sau có khung: giá trị của Hermes **không** nằm ở kiến
trúc lớn (nó là coding agent terminal, không dùng được ở đây). Nó nằm ở **hai
chục module nhỏ, mỗi module là một vết thương sản xuất đã lành**, và ở **một
nguyên tắc duy nhất xuyên suốt** mà Stock_Massive đang làm ngược.

---

## 1. Nguyên tắc trung tâm: mọi guard đều fail-OPEN

Đây là điều đáng học nhất, và nó trả lời trực tiếp cho câu "sao chatbot tệ".

Hermes có 17 module tên dạng guard/stop/budget/classifier. **Không một cái nào**
chặn câu trả lời khi nó không chắc. Trích nguyên văn docstring:

- `empty_response_guard.py`: *"Two independent guards, both failing **OPEN** to
  today's behaviour."* — và: *"Attempts with missing usage or `output_tokens > 0`
  (model generated something) never classify as deterministic and keep the full
  retry budget."*
- `repetition_guard.py`: *"The detection is deliberately conservative: only LONG
  verbatim repeats (60+ chars) whose occurrences cover a majority of the fragment
  trip the guard, so ordinary truncated responses are never blocked."* Và:
  *"Returns False for non-string / empty / short inputs (**fail-open**: never
  blocks a continuation the guard cannot confidently judge)."*
- `empty_response_guard.py` về định giá: *"except Exception — **pricing must never
  break the loop**"*.
- `context_engine.py`: mọi hook optional đều `return None` mặc định — *"Default is
  a safe no-op … so the agent loop's post-tool-call prune path never raises
  `AttributeError`"*.

Đối chiếu với ta. `ADR-0015` chọn hướng ngược lại một cách có ý thức:

> *"A model assertion never substitutes for a backend check … the model cannot
> certify that it passed this validator — there is no field it can set."*

Và `grounding.py`:

> *"An invalid block is never displayed … the Turn ends `incomplete` with the
> stable reason `grounding_failed`."*

Đó là fail-CLOSED trên đường đi của **mọi** câu trả lời. Hệ quả đo được: 58% Turn
chết, category B 0/30, và ba câu hỏi tối 20/08 → hai màn hình trắng.

**Tinh hoa #1: guard được phép làm chậm, làm rẻ, làm ồn — không được phép làm
trắng màn hình.** Khi guard không chắc, nó nhường đường.

---

## 2. Chống bịa số bằng prompt, không bằng validator

Ta xây 1.302 dòng `grounding.py` để bảo đảm "model kể lại số, không tự tính".
Hermes giải cùng bài toán bằng **một khối prose 9 dòng** nằm trong stable tier của
cached prompt (`agent/prompt_builder.py:411`):

```
# Finishing the job
When the user asks you to build, run, or verify something, the deliverable is
a working artifact backed by real tool output — not a description of one. …
If a tool, install, or network call fails and blocks the real path, say so
directly and try an alternative … NEVER substitute plausible-looking fabricated
output (made-up data, invented file contents, synthesised API responses) for
results you couldn't actually produce. Reporting a blocker honestly is always
better than inventing a result.
```

Comment phía trên khối đó ghi rõ nó sinh ra từ đâu: *"Observed on DeepSeek v4-flash
on the same task: pushed through PEP-668 wall, then returned fabricated listings."*

Và ghi rõ lý do nó **ngắn**: *"Short on purpose. This block is shipped to every
user, every session, in the cached system prompt — token cost is paid once at
install and then amortised across all sessions via prefix caching."*

**Tinh hoa #2: prompt là cơ chế thực thi hạng nhất khi nó nằm trong prefix được
cache.** Ta bác bỏ điều này trong `ADR-0015` (*"refuses to let the Contract be an
enforcement mechanism"*) và trả giá bằng 1.302 dòng validator cộng 58% Turn trắng.

Không có nghĩa là bỏ hết kiểm tra backend. Có nghĩa là: kiểm tra backend dành cho
chỗ có hậu quả tài chính (block khuyến nghị mua/bán), còn "đừng bịa số" là việc
của prompt.

---

## 3. Prompt ba tầng theo độ ổn định cache

`agent/system_prompt.py:340` — `build_system_prompt_parts()` trả về đúng ba khoá:

| Tầng | Nội dung | Đổi khi nào |
|---|---|---|
| `stable` | identity (`SOUL.md`), tool guidance, skills prompt, platform hint | không bao giờ trong một session |
| `context` | workspace snapshot, context file (`AGENTS.md`/`CLAUDE.md`), system_message | mỗi session |
| `volatile` | MEMORY.md snapshot, USER.md, timestamp, session/model line | mỗi session |

Ghép `stable → context → volatile`, cache trên `agent._cached_system_prompt`, và:

> *"Hermes never re-renders parts of this string mid-session — that's the only way
> to keep upstream prompt caches warm across turns."*

Cái tách bạch thật sự sắc là **cái gì KHÔNG được vào prompt cache** — mục
"API-call-time-only layers": `ephemeral_system_prompt`, prefill, gateway session
overlay, và recall từ memory provider ở turn sau. Những thứ này *append vào user
message của turn hiện tại*, không ghi vào system prompt.

Ta đã có phần này tốt: `prompt/contract.py` có `prefix()` trả về đúng phần ổn
định, và `contract_hash()` hash prose để một lần sửa quên bump version vẫn đổi
hash. **Chỗ ta thiếu là tầng `volatile`** — không có memory snapshot nào cả, nên
không có ký ức xuyên phiên (xem #6).

---

## 4. `select_context()` vs `compress()` — hai động từ khác nhau

Thiết kế sắc nhất trong `agent/context_engine.py`:

> - `compress()` : context quá dài → làm nó ngắn hơn.
> - `select_context()` : turn này thuộc một context **khác** → dùng cái đó.

Và lý do vì sao phải tách:

> *"Without this hook, engines that need per-turn access to the message list have
> to force `should_compress()` to return True so that `compress()` is invoked every
> turn purely as a callback — which conflates selection with compression."*

Kèm hợp đồng rất rõ: giá trị trả về là **request-only**, không được coi là
transcript đã lưu; chạy trước cache-control và trước mọi sanitizer, nên bản thay
thế vẫn phải qua validation; mặc định `return None` để không ảnh hưởng cache.

`ContextEngine` là ABC pluggable, chọn bằng `context.engine` trong config.yaml.
Ngưỡng nén 75%, `protect_first_n=3`, `protect_last_n=6`.

**Tinh hoa #4:** ta chưa có khái niệm nào tương đương. `context.py` của ta chỉ có
`ContextBudget` + `build_messages` — tức chỉ có `compress`, không có `select`.
Với câu hỏi tài chính thì `select_context` chính là chỗ đúng để nói "câu này về
STB, nạp transcript và snapshot của STB", thay vì nhồi tất cả rồi cắt.

---

## 5. Taxonomy lỗi route — và đây là món ta cần ngay

`agent/error_classifier.py` (89 KB) thay chuỗi `if "rate limit" in str(e)` rải rác
bằng một enum `FailoverReason`, **mỗi nhánh gắn một hành động phục hồi khác nhau**:

| Reason | Hành động |
|---|---|
| `auth` / `auth_permanent` | refresh/rotate credential / abort |
| `billing` | rotate ngay |
| `rate_limit` | backoff rồi rotate credential |
| `upstream_rate_limit` | **fallback sang model khác, KHÔNG rotate** — *"The user's key is healthy"* |
| `overloaded` (503/529) | backoff |
| `server_error` (500/502) | retry |
| `timeout` | **rebuild client** rồi retry |
| `ssl_cert_verification` | fail fast — *"Retrying reproduces the identical handshake failure"* |
| `context_overflow` | **compress, không failover** |
| `payload_too_large` (413) | compress payload |
| `image_too_large` | thu nhỏ ảnh rồi retry |

Cộng một synthetic code riêng cho trường hợp SDK OpenAI từ chối SSE `data:` field
của provider — *"Keeping this distinct from generic JSON parse failures lets the
classifier make narrow, provider-stream-specific recovery decisions."*

**Đây là món đắt giá nhất cho Stock_Massive ngay lúc này.** Ops 7 ngày của ta:
`gateway_timeout: 3` + `route_error: 1` trên 11 Turn = 36% Turn chết vì route.
`git log` gần đây toàn `fix/route-rate-limit`, `fix/route-thought-signature`,
`fix/route-error-log` — tức ta đang phát hiện lại từng nhánh của bảng trên, mỗi
lần một commit. Ta đã có `RouteRateLimited`, `GatewayTimeout`, `MalformedArguments`
trong `src/core/llm/errors.py`; cái thiếu là **map từ reason sang hành động phục
hồi**, và nhất là hai nhánh ta chưa có: `timeout → rebuild client` và
`upstream_rate_limit → đổi model chứ đừng đổi key`.

---

## 6. Ký ức xuyên phiên: snapshot vào prompt, không phải RAG

- `MEMORY.md` + `USER.md` được **đóng băng vào volatile tier** lúc dựng prompt.
  Ghi giữa session cập nhật xuống đĩa nhưng **không** mutate prompt đã dựng, cho
  tới một rebuild path (session mới, hoặc rebuild do compaction).
- `agent/curator.py` (88 KB) tự động curate memory; `session_search` (FTS5 +
  LLM summarize) để recall xuyên phiên. Prompt có câu dạy model chủ động dùng:
  *"When the user references something from a past conversation … use
  session_search to recall it before asking them to repeat themselves."*
- `agent/learning_graph.py`, `insights.py`, `skill_*` — vòng tự cải thiện: tạo
  skill sau task phức tạp, sửa skill trong lúc dùng.

**Tinh hoa #6:** ký ức là **snapshot ổn định trong prompt** cộng **một tool để
truy hồi khi cần**, không phải nhồi RAG mỗi turn. Cách này giữ cache ấm.

Với ta: `agent_thread` / `agent_message` đã có sẵn trong DB. Thiếu đúng hai thứ —
một `MEMORY` snapshot cho volatile tier (danh mục theo dõi, khẩu vị rủi ro, mã
hay hỏi) và một tool `session_search`.

---

## 7. Guardrail vòng tool: quyết định, không tác dụng phụ

`agent/tool_guardrails.py` — controller *pure*, trả `ToolGuardrailDecision` với
`action ∈ {allow, warn, block, halt}`; **runtime mới quyết định** biến decision
thành guidance, synthetic tool result, hay dừng turn:

> *"The controller in this module is intentionally side-effect free … Runtime code
> owns whether those decisions become warning guidance, synthetic tool results, or
> controlled turn halts."*

Ngưỡng cấu hình được, và đáng chú ý là **warn trước, halt rất muộn**:
`exact_failure_warn_after=2`, `same_tool_failure_warn_after=3`,
`same_tool_failure_halt_after=**8**`, `no_progress_warn_after=2`.

Kèm hai frozenset phân loại tool — `IDEMPOTENT_TOOL_NAMES` (read_file,
web_search, session_search…) vs `MUTATING_TOOL_NAMES` (terminal, write_file,
send_message…) — và trong `tool_result_classification.py` là
`NO_EFFECT_TOOL_NAMES` với ghi chú: *"Unknown/plugin/MCP tools stay
effect-capable by default"* (an toàn mặc định cho cái không biết).

Ta có `MAX_TOOL_ATTEMPTS` và ceiling 8 round, nhưng không có tầng **warn**. Ta
nhảy thẳng từ allow sang kết thúc Turn. Thang `allow → warn → block → halt` là
thứ nên bê nguyên.

---

## 8. Deadline: một primitive, không phải sáu

`agent/deadline.py` mở đầu bằng chẩn đoán tự thân:

> *"The tree currently carries at least six site-local deadline mechanisms, each
> built for one incident, none shared … Every new stall report grows that list by
> one."*

Bốn hàm thay cả sáu: `resolve_timeout` (config > env cũ > default),
`clamp_timeout` (timeout lớn overflow `time_t` trong `Lock.acquire` trên macOS —
giết cả batch tool), `run_bounded_async`, `run_bounded_sync`, `kill_process_tree`.

Chi tiết kỹ thuật đáng nhớ nhất trong cả repo:

> *"`asyncio.wait_for` schedules its expiry on the loop; when the loop thread
> itself is blocked in a synchronous call, **every asyncio-based timeout in the
> process is silently disabled**."*

Nên deadline của họ chạy trên `threading.Timer` daemon, không trên event loop. Và
`bounded_response.py` giải thích cùng lớp bug cho httpx: `iter_bytes()` block
*bên trong* socket read, nên kiểm giờ giữa các chunk không cứu được — phải đọc
trên daemon thread và đóng response khi hết hạn.

Bất biến của họ: *"A timeout produced by this layer is OUR deadline, not the
provider's"* — và phải classify khác với transport timeout.

**Với ta**: `LLM_REQUEST_TIMEOUT_SECONDS=120` là timeout duy nhất, và
`gateway_timeout` của ta hiện không phân biệt "ta bỏ cuộc" với "provider bỏ cuộc".
Đó là 3/11 Turn.

---

## 9. Song song hoá là việc của prompt, không chỉ của runtime

`PARALLEL_TOOL_CALL_GUIDANCE` (`prompt_builder.py:454`) — comment giải thích rất
sạch: runtime đã chạy song song các call độc lập từ lâu, *"The missing piece was
telling the **model** to emit those calls together in the first place."*

Và lý do nó là vấn đề **chi phí**, không chỉ độ trễ: mỗi assistant turn resend
toàn bộ hội thoại; một model gọi một tool mỗi turn nhân số round-trip lên, kéo
theo chi phí context bị gửi lại.

Ta đã có `asyncio.gather` trong `loop.py` (và cả assertion `tool_call_id` rất
tốt) nhưng Contract của ta không có câu nào dạy model batch. Miễn phí để thêm.

---

## 10. Những thứ nhỏ khác đáng ghi

- `think_scrubber.py`, `message_sanitization.py` — dọn surrogate/non-ASCII, sửa
  tool-call arguments méo, đóng tool sequence bị ngắt giữa. Ta đã gặp đúng lớp này
  (`fix(agent): read the fullwidth brackets a Vietnamese answer actually types`).
- `prompt_cache_boundary.py` / `prompt_cache_scope.py` / `prompt_caching.py` —
  cache breakpoint là module riêng, `effective_cache_ttl`.
- `reasoning_effort.py`, `reasoning_timeouts.py`, `reasoning_summaries.py` —
  thinking model được đối xử như một hạng công dân riêng. Ta vừa vá tay việc này
  (`carry a route's reasoning token back with the tool calls it signed`).
- `title_generator.py` (32 KB) — sinh tiêu đề thread. UX nhỏ, tốn một call rẻ.
- `verification_evidence.py` + `verification_stop.py` + `verify/recipes.py` — họ
  **cũng** có khái niệm "bằng chứng", nhưng nó dùng để quyết định *khi nào được
  dừng*, không phải để quyết định *có được nói*. Khác biệt đúng một chữ mà đổi cả
  hệ quả.
- `agent/battery.py`, `moa_loop.py` (mixture-of-agents), `subagent_lifecycle.py`,
  `delegate_tool.py` — subagent song song có vòng đời riêng và budget riêng
  (`delegation.max_iterations` mặc định 50, parent 500).
- `iteration_budget.py` — counter thread-safe có **refund**: iteration của
  `execute_code` được hoàn lại để không ăn vào budget.

---

## 11. Cái KHÔNG đem sang

- Toàn bộ `tools/` (127 file): terminal, sandbox 7 backend, browser, file ops.
  `ADR-0011` đã từ chối sandboxed execution, và không tool nào đọc được store này.
- `gateway/` + `plugins/platforms/*` (Telegram/Discord/Slack/WhatsApp/Matrix/
  Feishu): non-goal.
- `ui-tui/`, `web/`, `apps/desktop/`: ta có Next.js shell riêng.
- `hermes_state.py` (592 KB): state cho CLI đa phiên trên SQLite. Ta có Postgres
  + `agent_thread`/`agent_message` rồi.
- Provider adapter (`anthropic_adapter`, `bedrock_adapter`, `vertex_adapter`,
  `codex_*`): `src/core/llm` của ta đã là boundary OpenAI-compatible và đã có
  budget lane + spend admission mà Hermes **không** có tương đương chặt chẽ.

**Không có commit nào nên là "copy từ Hermes".** Kiến trúc không tương thích;
giá trị nằm ở bài học, và mỗi bài học phải viết lại cho hình dạng của ta.

---

## 12. Đem sang cái gì, theo thứ tự

Xếp theo (giá trị cho triệu chứng đang có) ÷ (công).

| # | Việc | Sửa triệu chứng nào | File của ta |
|---|---|---|---|
| 1 | **Đảo grounding sang fail-open**: guard không chắc thì nhường đường; chỉ block khi *integrity* (số chống lại chính citation của nó) hoặc khi là block khuyến nghị có giá | Màn hình trắng, category B | `src/agent/grounding.py`, `loop.py` |
| 2 | **Khối prose chống bịa** vào stable tier, thay vì validator gác mọi câu | Chất lượng + màn hình trắng | `prompt/sections.py` |
| 3 | **Taxonomy lỗi route + hành động phục hồi**, nhất là `timeout → rebuild client` và `upstream_rate_limit → đổi model không đổi key` | 36% Turn chết vì route | `src/core/llm/errors.py`, `client.py` |
| 4 | **Thang `allow → warn → block → halt`** cho vòng tool; halt rất muộn | Turn chết sớm | `loop.py`, `tools/catalog.py` |
| 5 | **`PARALLEL_TOOL_CALL_GUIDANCE`** vào Contract | Độ trễ, chi phí | `prompt/sections.py` |
| 6 | **Deadline một primitive**, phân biệt deadline của ta vs của provider | `gateway_timeout` | `src/core/llm/transport.py` |
| 7 | **`empty_response_guard`**: hai empty liên tiếp cùng signature → đừng retry, đổi model | Chi phí, Turn trắng | `src/core/llm/client.py` |
| 8 | **Volatile tier + `session_search`**: MEMORY snapshot (danh mục, khẩu vị, mã hay hỏi) + tool truy hồi phiên cũ | "Hỏi lại câu cũ phải kể lại từ đầu" | `prompt/contract.py`, `agent/persistence.py` |
| 9 | **`select_context()`** tách khỏi nén: câu về STB nạp context của STB | Chất lượng câu trả lời sâu | `agent/context.py` |
| 10 | `title_generator` cho thread | UX | `agent/suggestions.py` (đã có chỗ) |

Mục 1–5 là phần chạm đúng ba nhóm triệu chứng đã nêu và đều nhỏ. Mục 8–9 là phần
làm chatbot "thực thụ" theo nghĩa Hermes, nhưng chỉ có nghĩa sau khi 1–5 xong.

---

## 13. Bài học meta, và nó là bài học lớn nhất

Mỗi module nhỏ của Hermes mở đầu bằng **số hiệu sự cố**: NS-503 (`bị tính ~$2.33
cho một câu trả lời rỗng`), #86581 (`một turn sinh 60.698 ký tự lặp, gửi thành 31
tin Discord`), #85125 (`sáu cơ chế deadline rời rạc`), #83220 (`timeout lớn
overflow time_t trên macOS`), openclaw#95108, cline#11514.

Họ không thiết kế trước cho đúng. Họ **thả cho chạy, hứng sự cố, rồi đóng từng
sự cố thành một module nhỏ fail-open**, và ghi số hiệu vào docstring để người sau
không gỡ mất.

Stock_Massive làm ngược: 20 ADR và một validator 1.302 dòng dựng **trước** khi có
người dùng nào, để chặn một lớp lỗi (model bịa số) mà chưa từng đo tần suất — và
lớp bảo vệ đó tự trở thành sự cố lớn nhất (58% Turn trắng).

Đó chính xác là điều bạn nói: *build quá cao mà base chưa có*. Hermes có
126.055 dòng trong `agent/` — nhưng nó đến đó bằng cách trả lời được trước, rồi
mới cứng lên từng vết.

---

## Câu hỏi chưa giải quyết

1. `select_context()` cho miền tài chính nên khoá theo **symbol** hay theo
   **thread**? Hermes khoá theo topic/session; câu hỏi chứng khoán hay nhảy mã
   giữa thread, nên đây không phải map 1-1.
2. Chống bịa bằng prompt có đủ khi câu trả lời mang **giá và vùng mua**? Tôi
   nghiêng: đủ cho prose, **không** đủ cho block khuyến nghị — giữ Gate ở đúng đó
   (mục 1). Cần bạn xác nhận vì nó là ranh giới rủi ro tài chính, không phải
   quyết định kỹ thuật.
3. Bật `session_search` nghĩa là câu hỏi của người dùng đi vào một tool đọc
   transcript cũ. Có ràng buộc riêng tư nào giữa các user không, hay thread luôn
   là của một user?
