# Hermes — vòng lặp hội thoại và dựng prompt

Đọc trực tiếp: `agent/conversation_loop.py` (8.436 dòng), `agent/prompt_builder.py`
(2.598), `agent/system_prompt.py` (1.028). Cộng các module guard nhỏ và
`agent/verification_*.py` để dựng luận điểm trung tâm.

Phủ của toàn bộ đợt khảo sát: `hermes-coverage-260820-2352.md`.

---

## 1. Ba nguyên tắc quản trị, suy ra từ code chứ không từ tài liệu

### 1.1 Fail-OPEN, tuyệt đối và có tuyên bố

17 module trong `agent/` mang tên guard/stop/budget/classifier. Không cái nào
chặn câu trả lời khi nó không chắc. Trích nguyên văn:

- `empty_response_guard.py:38` — *"Two independent guards, both failing OPEN to
  today's behaviour."*
- `empty_response_guard.py:30` — *"Attempts with missing usage or `output_tokens
  > 0` (model generated something — think-block stripping, whitespace, flaky
  decoding) never classify as deterministic and keep the full retry budget."*
- `repetition_guard.py:19` — *"The detection is deliberately conservative: only
  LONG verbatim repeats (60+ chars) whose occurrences cover a majority of the
  fragment trip the guard, so ordinary truncated responses … are never blocked."*
- `repetition_guard.py:54` — *"Returns False for non-string / empty / short
  inputs (fail-open: never blocks a continuation the guard cannot confidently
  judge)."*
- `subscription_view.py:5` — *"same fail-open philosophy: when not logged in or
  the portal is unreachable, return a struct with `logged_in=False` and let the
  surface degrade gracefully (never crash)."*
- `empty_response_guard.py` (hàm `_estimate_attempt_cost`) — `except Exception`
  kèm comment *"pricing must never break the loop"*.
- `context_engine.py` — mọi hook tuỳ chọn mặc định `return None`: *"Default is a
  safe no-op … so the agent loop's post-tool-call prune path never raises
  `AttributeError` on them."*

Ngưỡng cũng nói lên điều đó. `tool_guardrails.ToolCallGuardrailConfig`:
`exact_failure_warn_after=2`, `same_tool_failure_warn_after=3`,
`no_progress_warn_after=2`, và **`same_tool_failure_halt_after=8`**. Cảnh báo
sớm, dừng rất muộn.

### 1.2 Mỗi module là một sự cố đã đóng, có số hiệu trong docstring

- NS-503 — *"the 'charged ~$2.33 for an empty answer' incident class"*
  (`empty_response_guard.py`)
- #86581 — *"a single turn produced a 60,698-char response delivered as 31
  Discord messages"* (`repetition_guard.py`)
- #85125 — *"at least six site-local deadline mechanisms, each built for one
  incident, none shared … Every new stall report grows that list by one"*
  (`deadline.py`)
- #83220 — timeout lớn overflow `time_t` trong `Lock.acquire(timeout=)` trên
  macOS, giết cả batch tool (`deadline.py`)
- #84047 — *"`asyncio.wait_for` schedules its expiry on the loop; when the loop
  thread itself is blocked in a synchronous call, every asyncio-based timeout in
  the process is silently disabled"* (`deadline.py`)
- #9400 — model yếu trả rỗng sau tool call (`conversation_loop.py:7649`)
- #32421 — content-filter làm stream đứng (`conversation_loop.py:3784`)
- #62625 — cảnh báo overflow im lặng (`context_engine.py`)
- #79161 — rotation session_id phá cache prefix (`prompt_cache_scope.py`)
- #81867 — builder tự khai biên prefix ổn định (`prompt_cache_boundary.py`)
- #50233 — thread mất ContextVar `HERMES_HOME` đọc sai `SOUL.md`
  (`system_prompt.py:388`)
- Cùng các port từ ngoài: `openclaw#95108` (bound Anthropic error stream),
  `cline#11514` (khuyến khích parallel tool call), `codex#21069` (spill hook
  output), `opencode#23770` (cho phép cấu hình truncate).

`terminal_hints.py` đi xa hơn: tần suất pattern lỗi được **đào từ DB sản xuất**.
*"Frequencies quoted below come from a 250k-terminal-result window of the
production session DB (Aug 2026): together these classes cover ~14k failed calls
whose retry chains averaged 1.4 extra tool turns each."* Và `~9,175x: gh CLI
version drift`.

Họ không thiết kế trước cho đúng. Họ đo cái gì đau nhất rồi đóng nó lại.

### 1.3 Một concern, một chủ

- `deadline.py` thay 6 cơ chế deadline rời rạc.
- `backend_identity.py` — *"Every fallback / dedup / skip / quarantine decision …
  ultimately asks one question … Before this module, that question was
  re-implemented inline at six call sites across four subsystems."*
- `error_classifier.py` — *"Replaces scattered inline string-matching with a
  centralized classifier that the main retry loop … consults for every API
  failure."*
- `threat_patterns.py` — *"single source of truth for prompt-injection /
  promptware"*.
- `tool_result_classification.py` — hai frozenset dùng chung, và mặc định an
  toàn: *"Unknown/plugin/MCP tools stay effect-capable by default."*

---

## 2. `conversation_loop.py` — kiến trúc phục hồi, không phải kiến trúc điều phối

`run_conversation()` bắt đầu ở dòng 1762. Thân nó là **26 nhánh phục hồi có
tên**, mỗi nhánh một lớp lỗi:

| Dòng | Nhánh |
|---|---|
| 1856 | Per-turn setup (prologue) |
| 2051 | Pre-API-call `/steer` drain — người dùng chen lệnh giữa turn |
| 2102 | Wall-clock run-budget wrap-up notice |
| 2836 | Nous Portal rate limit guard |
| 3530 | Content-policy refusal **trả HTTP 200** |
| 3667 | Thinking-budget exhaustion |
| 3728 | Repetition-dominated truncation (#86581) |
| 3784 | Content-filter stream stall → fallback (#32421) |
| 4561 | Image-rejection recovery |
| 4652 | Bedrock SDK streaming failure |
| 4680 | Classify the error for structured recovery decisions |
| 4974 | Invalid encrypted reasoning replay recovery |
| 5017 | Native compaction rejection recovery |
| 5050 | llama.cpp grammar-parse recovery |
| 5196 | Respect disabled auto-compaction on overflow |
| 5263 | Anthropic Sonnet long-context tier gate |
| 5421 | Auth-failure provider failover |
| 5455 | Nous Portal: record rate limit & skip retries |
| 5670 | Distinguish two very different errors (input overflow vs output cap) |
| 7147 | Post-call guardrails |
| 7587 | Partial stream recovery |
| 7641 | Post-tool-call empty response nudge |
| 7704 | Thinking-only prefill continuation |
| 7738 | Empty response retry |
| 7849 | Exhausted retries — try fallback provider |
| 8052 | Dropped tool-call recovery (copilot/Claude) |
| 8244 | Kanban worker terminal-tool stop guard |

Bài học hình dạng: **một agent thực thụ không phải một vòng lặp gọi tool. Nó là
một vòng lặp gọi tool bọc trong hai chục đường phục hồi.** Vòng lặp "đẹp" của ta
(`loop.py`, 1.376 dòng) đúng về nguyên lý và mỏng về phục hồi.

Một chi tiết nhỏ đáng nhớ, dòng 5670: phân biệt *"Prompt too long"* (input vượt
context window → giảm context + nén) với *"max_tokens too large"* (input ổn,
nhưng `input + max_tokens > window` → giảm **output cap**, **không** thu
`context_length`). Comment ghi rõ: *"max_tokens = output token cap (one
response); context_length = total window (input + output combined)."* Hai lỗi
trông giống nhau, sửa ngược nhau.

---

## 3. Phát hiện trung tâm: **nudge tổng hợp thay cho kết thúc turn**

Đây là câu trả lời cho 58% Turn `grounding_failed` của ta.

Khi model làm sai hợp đồng — trả rỗng, chỉ có reasoning, khai tool call rồi không
gửi, sửa code mà chưa chứng minh — Hermes **không** kết thúc turn. Nó chèn một
message tổng hợp nói rõ thiếu gì và phải làm gì, rồi `continue`.

Các nudge, nguyên văn:

```
_EMPTY_TOOL_RESPONSE_NUDGE (conversation_loop.py:1186)
"You just executed tool calls but returned an empty response.
 Please process the tool results above and continue with the task."

_CODEX_INCOMPLETE_NUDGE
"[System: Your previous response contained only internal reasoning and never
 produced a visible answer or tool call. Do not keep thinking. Produce your
 final answer as plain text now (or make the tool call you were planning).]"

_CODEX_ACK_CONTINUATION_NUDGE
"[System: Continue now. Execute the required tool calls and only send your
 final answer after completing the task.]"

_DROPPED_TOOLCALL_NUDGE_CONTENT
"Your previous turn indicated a tool call but none was included. Do not narrate
 a plan or restate intent — issue the actual tool call now to continue the task."
```

Ba tính chất của cơ chế:

**Chuỗi message phải hợp lệ.** `conversation_loop.py:7690` — chèn assistant
`"(empty)"` trước rồi mới chèn user nudge: *"the message sequence stays valid:
tool(result) → assistant('(empty)') → user(nudge). Without this, we'd have
tool → user which most APIs reject as an invalid sequence."*

**Message tổng hợp được đánh dấu.** `_empty_recovery_synthetic: True`, để
finalizer bóc khỏi transcript bền. Kèm cảnh báo thật thà: *"this pair is only
stripped from the durable transcript once the turn reaches finalization; an
interrupt/crash mid-retry can still persist it."*

**Có trần, và trần rất thấp.** `_post_tool_empty_retried` là cờ một lần.
`build_verify_on_stop_nudge` có `max_attempts=2`.

### 3.1 Và bản áp cho "bằng chứng" — trùng khít bài toán grounding của ta

`verification_evidence.py:3` — *"It is deliberately **passive**: it never decides
to run a suite, never blocks completion, and never upgrades targeted checks into
'repo green'."*

`verification_stop.py:3` — *"This module is intentionally **policy-only**. It
never runs checks itself; it turns the passive verification ledger into a
**bounded follow-up** when the model tries to finish immediately after editing
code without fresh evidence."*

Nudge nó sinh ra (`verification_stop.py:305`):

```
[System: You edited code in this turn, but the workspace does not have fresh
passing verification evidence yet.

Verification status: {…}

Changed paths:
{…}

Run the relevant verification command now (`make test`, …), read any failure,
repair the code, and summarize what passed. If verification is not possible,
explain the concrete blocker instead of claiming the work is fully verified.]
```

Câu cuối là bản lề: **hoặc chứng minh được, hoặc nói rõ vướng gì — không có
đường thứ ba là màn hình trắng.**

Kèm ba lớp chống dương tính giả, tất cả đều nhường đường:
- Chỉ đếm path có hành vi kiểm chứng được. Sửa `.md`/`README`/`LICENSE` thì
  không nudge: *"a SKILL.md or README edit must never demand a /tmp verification
  script."*
- Tắt trên bề mặt hội thoại: *"OFF on a conversational platform … where the
  verification narrative reaches a human as chat noise."*
- `snapshot is None` → `return None`. Không đọc được ledger thì im lặng.

---

## 4. Dựng prompt — ba tầng theo độ ổn định cache

`system_prompt.py:340` `build_system_prompt_parts()` trả về đúng ba khoá:

| Tầng | Nội dung |
|---|---|
| `stable` | identity (`SOUL.md` hoặc `DEFAULT_AGENT_IDENTITY`), tool guidance, skills prompt, environment/platform hint |
| `context` | workspace snapshot, file context dự án, `system_message` của caller |
| `volatile` | skills index, `MEMORY.md`, `USER.md`, block memory provider, dòng timestamp/session/model |

Ghép `stable → context → volatile`, cache trên `agent._cached_system_prompt`.
Bất biến, nguyên văn (`system_prompt.py:355`): *"Hermes never re-renders parts of
this string mid-session — that's the only way to keep upstream prompt caches warm
across turns."*

Phần sắc nhất là **cái gì không được vào**. Từ `prompt-assembly.md`:
`ephemeral_system_prompt`, prefill message, gateway session overlay, và recall
memory ở turn sau — tất cả **append vào user message của turn hiện tại**, không
ghi vào system prompt. Hook `pre_llm_call` cũng vậy.

File context: ưu tiên first-match-wins (`.hermes.md` → `AGENTS.md` →
`CLAUDE.md` → `.cursorrules`), **quét injection** (`_scan_context_content`),
truncate 70/20 head/tail có marker, cap scale theo context window (sàn 20k, trần
500k). `.hermes.md` bị bóc YAML frontmatter.

### 4.1 Ba khối guidance — chống bịa bằng prose, trong prefix được cache

`prompt_builder.py:411`, nguyên văn:

```
# Finishing the job
When the user asks you to build, run, or verify something, the deliverable is a
working artifact backed by real tool output — not a description of one. Do not
stop after writing a stub, a plan, or a single command. Keep working until you
have actually exercised the code or produced the requested result, then report
what real execution returned.
If a tool, install, or network call fails and blocks the real path, say so
directly and try an alternative (different package manager, different approach,
ask the user). NEVER substitute plausible-looking fabricated output (made-up
data, invented file contents, synthesised API responses) for results you
couldn't actually produce. Reporting a blocker honestly is always better than
inventing a result.
```

Sinh từ đâu, có ghi: *"Observed on DeepSeek v4-flash on the same task: pushed
through PEP-668 wall, then returned fabricated listings."*

Vì sao ngắn, cũng có ghi: *"Short on purpose. This block is shipped to every
user, every session, in the cached system prompt — token cost is paid once at
install and then amortised across all sessions via prefix caching."*

`prompt_builder.py:454` `PARALLEL_TOOL_CALL_GUIDANCE` — và lý do nó tồn tại:
*"The hermes-agent runtime already executes a batch of tool calls concurrently
when they are independent … The missing piece was telling the **model** to emit
those calls together in the first place."* Nó là vấn đề **chi phí** trước cả độ
trễ: mỗi turn thêm là một lần gửi lại toàn bộ hội thoại.

`OPENAI_MODEL_EXECUTION_GUIDANCE` — ban đầu chỉ cho GPT/Codex/Grok, sau bỏ hàng
rào vì eval trace cho thấy DeepSeek/Kimi cùng lỗi: *"doing financial math in
prose, skipping read-back verification after external writes, 'repairing'
malformed identifiers, and claiming completeness despite count mismatches."*

Ghi chú: *"financial math in prose"* là đúng lớp lỗi mà `grounding.py` của ta
được xây để chặn. Hermes chặn nó bằng prose trong prefix. Ta chặn bằng 1.302
dòng validator gác mọi câu trả lời.

---

## 5. Đối chiếu trung tâm với Stock_Massive

`ADR-0015` chọn hướng ngược một cách có ý thức: *"A model assertion never
substitutes for a backend check … the model cannot certify that it passed this
validator — there is no field it can set, and no branch below reads one."* Và
`grounding.py`: *"An invalid block is never displayed … the Turn ends
`incomplete` with the stable reason `grounding_failed`."*

Đó là fail-CLOSED trên đường đi của **mọi** câu trả lời. Kết quả đo:

| | Hermes | Stock_Massive |
|---|---|---|
| Guard không chắc | nhường đường | chặn |
| Model sai hợp đồng | chèn nudge, `continue`, trần 1–2 lần | kết thúc Turn `incomplete` |
| Chống bịa số | prose 9 dòng trong prefix cache | validator 1.302 dòng runtime |
| Bằng chứng | ledger thụ động + policy sinh follow-up | điều kiện để được nói |
| Không chứng minh được | *"explain the concrete blocker"* | màn hình trắng |
| Đo được | — | 58% Turn `grounding_failed`, category B 0/30 |

Ta đã đi được nửa đường mà chưa tới: commit `d699345` cho một block bị chặn
**một** lần rewrite, và `ADR-0018` hạ cấp prose thay vì chặn. Miếng còn thiếu là
miếng cuối: sau khi hết lượt rewrite, **thả câu trả lời kèm câu nói thẳng chỗ
không chứng minh được**, thay vì kết thúc trắng.

---

## 6. Port sang gì, cụ thể

| # | Việc | File của ta | Ghi chú |
|---|---|---|---|
| 1 | Thay `raise` bằng nudge tổng hợp có trần. Hết trần thì thả block kèm câu backend-authored nói rõ không chứng minh được figure nào | `agent/loop.py`, `agent/grounding.py` | Đã có sẵn `REPAIR_FALLBACK`, `repair_instruction`, và cơ chế "một rewrite" — chỉ cần đổi đích của đường thất bại |
| 2 | Khối prose chống bịa vào tầng `stable` | `agent/prompt/sections.py` | Ngắn, đặt cạnh `INVARIANTS`. Bump `PROMPT_VERSION` |
| 3 | `PARALLEL_TOOL_CALL_GUIDANCE` | `agent/prompt/sections.py` | `loop.py` đã `asyncio.gather`; Contract chưa dạy model batch |
| 4 | ~~Tầng `volatile` cho contract~~ → **thay bằng**: mở rộng tool `remember_fact`/`recall_facts` | `agent/tools/knowledge.py` | **Đã sửa 2026-08-21.** Khuyến nghị ban đầu (chèn snapshot MEMORY vào prompt) va vào một bất biến có chủ đích: `contract.py::_assert_no_formatting_hole` cấm mọi free-text vào system prompt, `render()` chỉ nhận 5 giá trị typed. Bất biến đó là hàng rào chống injection mà Hermes phải bù bằng `_scan_context_content`. Giữ hàng rào; đưa ký ức qua đường tool, không qua prompt. Chi tiết: `hermes-memory-260820-2352.md` |
| 5 | Thang `allow → warn → block → halt`, halt ở lần 8 | `agent/loop.py` | Ta nhảy thẳng allow → kết thúc Turn |
| 6 | Tách "deadline của ta" khỏi "timeout của provider" | `core/llm/transport.py` | `gateway_timeout` hiện gộp hai thứ; 3/11 Turn |
| 7 | Guard empty deterministic: 2 lần rỗng cùng signature → đổi model, đừng retry | `core/llm/client.py` | Tiết kiệm tiền và cứu Turn |
| 8 | Phân biệt input-overflow vs output-cap | `core/llm/errors.py` | Hai lỗi sửa ngược nhau |

Mục 1 và 2 chạm đúng 58% Turn trắng. Mục 6–8 chạm 36% Turn chết vì route.

---

## 7. Cái không port

- Kiến trúc lớn: Hermes là coding agent terminal. 7 sandbox backend, 40+ tool
  shell/file/git, TUI, gateway đa nền tảng — `ADR-0011` đã từ chối lớp đó, và
  không tool nào của nó đọc được store của ta.
- `SOUL.md` / persona file: ta không cần persona người dùng tự sửa.
- Provider adapter riêng cho từng nhà: `core/llm` của ta đã là biên
  OpenAI-compatible, và đã có budget lane + spend admission nguyên tử mà Hermes
  không có tương đương chặt chẽ.
- Skills tự sinh: chỉ có nghĩa sau khi base trả lời được.

**Không commit nào nên là "copy từ Hermes".** Giá trị là bài học; mỗi bài học
phải viết lại cho hình dạng của ta.

---

## Câu hỏi chưa giải quyết

1. Sau khi hết lượt rewrite, câu "không chứng minh được" do backend viết nên nói
   đến mức nào? Nêu tên field bị thiếu là rõ ràng nhưng rò cấu trúc nội bộ; nói
   chung chung thì người đọc không hành động được.
2. Nudge có tiêu một lời gọi model. Với trần 2 lần, một Turn xấu có thể tốn 3
   lời gọi. Trên route trả tiền thì được — nhưng cần chốt trần theo tiền hay
   theo số lần.
3. `ADR-0015` nói thẳng "prompt không phải cơ chế thực thi". Đưa khối prose
   chống bịa vào là **sửa một quyết định kiến trúc đã ghi**, không phải thêm
   tính năng. Cần bạn xác nhận trước khi làm, và ADR-0015 phải được amend chứ
   không lặng lẽ trái.
