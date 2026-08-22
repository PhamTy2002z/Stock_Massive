# Hermes Agent — vòng đời turn, streaming, công bố tiến trình

Đọc code thật tại sparse clone `hermes-agent` (NousResearch/hermes-agent, MIT)
+ 2 trang doc build được (`agent-loop.md`, `gateway-internals.md`, fetch qua
raw.githubusercontent.com). Đối chiếu với
`apps/api/src/agent/{turns.py,loop.py,events.py,progress.py,persistence.py}`
và `live-turn.ts` để phần (4)/(5) cụ thể.

**Phạm vi**: Hermes là CLI/gateway đa nền tảng chạy 1 process, 1 session
SQLite dài hạn, resume bằng replay lại list message cũ. Stock_Massive là
backend multi-tenant, mỗi Turn là 1 transaction DB + SSE, không bao giờ
resume model call — khác biệt kiến trúc lớn nhất, chi phối toàn bộ phần (5).

## 1. Sơ đồ vòng đời một turn (Hermes)

```
run_conversation(user_message, ...)
  │
  ├─ PROLOGUE — build_turn_context()  [agent/turn_context.py, ~1 lần/turn]
  │   1. install_safe_stdio, recover rotated session
  │   2. set_session_context, bind write-origin, restore primary runtime
  │   3. reset per-turn retry counters + IterationBudget mới
  │   4. append user message vào messages[], stamp timestamp
  │   5. reset think-scrubber + stream-context-scrubber
  │   6. system prompt: restore-or-build (cache theo session)
  │   7. TẠO SESSION ROW (_ensure_db_session) — SAU khi system prompt sẵn
  │   8. idle-compaction (nếu idle lâu) → preflight compression (nếu >50% ctx)
  │   9. pre_llm_call plugin hook → nội dung chèn vào api_content sidecar
  │  10. memory prefetch (external memory provider)
  │  11. CRASH-RESILIENCE PERSIST (persist user turn trước khi gọi model)
  │  12. kick auto-title (instant, fire-and-forget)
  │   → trả về TurnContext (messages, system_prompt, turn_id, ...)
  │
  ├─ LOOP — while retry_count < max_retries (agent/conversation_loop.py, ~2400 dòng)
  │   mỗi vòng: TurnRetryState mới (1 lần/API-call attempt)
  │     → build api_messages → gọi model (_interruptible_api_call, streaming)
  │     → think_scrubber lọc reasoning theo delta
  │     → nếu tool_calls: dispatch tools (tuần tự hoặc ThreadPoolExecutor)
  │        tool_progress_callback("tool.started"/"tool.completed", ...)
  │     → nếu lỗi: 1 trong ~16 nhánh retry 1-lần (OAuth, 429, compress-restart,
  │        length-continuation, thinking-sig strip, ...) — MỘT SỐ NHÁNH
  │        `return {...}` THẲNG, KHÔNG đi qua finalizer (mục 2.3)
  │     → nếu text response cuối: break ra khỏi loop
  │
  └─ EPILOGUE — finalize_turn()  [agent/turn_finalizer.py, ~1 lần/turn]
      - budget-exhausted fallback; rollback compression-display nếu interrupt
      - _save_trajectory, _cleanup_task_resources (lỗi KHÔNG làm mất response)
      - drop nudge, close_interrupted_tool_sequence, micro-compact, persist DB
      - transform_llm_output/post_llm_call/on_session_end hooks; build result
        dict; drain /steer; spawn background memory/skill review
```

---

## 2. Từng cơ chế + số hiệu sự cố

### 2.1 Prologue: thứ tự tạo session row vs compression

`agent/turn_context.py:749-759` — session DB row được tạo **sau** khi
`_cached_system_prompt` có giá trị, và **trước** preflight compression:

> "Must run BEFORE preflight compression: in-place compaction inserts message
> rows referencing this session ... rotation creates a child with
> parent_session_id pointing at it — with `PRAGMA foreign_keys=ON`, a missing
> parent row fails both INSERTs on a fresh oversized first turn."

Hai lý do độc lập buộc đúng thứ tự: (a) tránh warning "stored system prompt
is null" + cache-miss lượt đầu (#45499), (b) tránh vi phạm khoá ngoại khi
compression chèn row tham chiếu session chưa tồn tại. Ví dụ kinh điển "thứ
tự side-effect là behavior, không phải chi tiết cài đặt" — đổi thứ tự 2 bước
tưởng độc lập sẽ vỡ silently trên turn đầu của session có input dài.

Compression tương ứng: idle-compaction (wall-clock gap,
`turn_context.py:368-399`) và preflight compression (token threshold, có
OR-gate cho case "vài message rất to" — #27405, `turn_context.py:340-365`).
Mọi lần compression rebuild list phải re-anchor lại index user message hiện
tại (`reanchor_current_turn_user_idx`, #48677/#80622) vì tạo bản copy mới,
không sửa in-place.

### 2.2 Finalizer: dọn transcript, không để mất response

`agent/turn_finalizer.py` là điểm hội tụ **duy nhất** cho: đóng tool-tail bị
interrupt, xoá nudge giả, micro-compact, persist, chạy plugin hooks,
background review. Điểm quan trọng nhất — không để lỗi cleanup làm mất
response đã có (`turn_finalizer.py:266-292`): "A raise from any of them used
to propagate straight out of run_conversation, discarding the partial
final_response the caller is waiting for ... #8049" → `_save_trajectory`,
`_cleanup_task_resources`, `_persist_session` mỗi cái try/except riêng, lỗi
gom vào `result["cleanup_errors"]` thay vì raise.

Invariant #43849/#44100 (`turn_finalizer.py:325-386`): nếu `final_response`
tồn tại và turn không interrupt, transcript PHẢI kết thúc bằng 1 dòng
assistant chứa đúng response — kể cả khi tail hiện tại là
`assistant(tool_calls)` không text (pure tool-call tail, phải fill content
vào chứ không append thêm, tránh assistant→assistant).

### 2.3 Đường early-return KHÔNG qua finalizer

Docstring `codex_runtime.py:795-797`: "This runtime bypasses the normal
conversation-loop finalizer. Mirror its interrupt handoff/cleanup so a hard
stop cannot poison the next turn..." — runtime `codex_app_server` (chạy codex
như subprocess riêng) hoàn toàn không qua `finalize_turn`, phải tự chép lại
thủ công phần interrupt-clear/session-retire.

Trong `conversation_loop.py`, ít nhất 2 nhánh format-recovery `return {...}`
thẳng, ghi rõ trong comment (`4007`, `7092`): stream lặp truncated giữa
tool-call (4 lần retry vẫn hỏng) hoặc invalid JSON args do truncation →
`close_interrupted_tool_sequence` gọi TRỰC TIẾP tại chỗ rồi return dict tối
giản (`completed: False, partial: True`) — thiếu hầu hết field finalizer
thường gắn; "first message truncated" → return `failed: True` không dọn gì
thêm.

Hệ quả: mọi nơi cần đóng tool-tail an toàn phải gọi lại
`close_interrupted_tool_sequence` tại **từng** điểm early-return — đây là lý
do hàm đó nằm ở `message_sanitization.py` (module chia sẻ) thay vì method
riêng của finalizer (`message_sanitization.py:296-327`: "the retry/backoff/
error interrupt aborts in conversation_loop return early and never reach
[finalizer] — this shared helper closes the sequence on all of them").

### 2.4 `turn_retry_state.py` — đếm riêng từng loại retry trên 1 lần gọi API

Một `TurnRetryState` mới được tạo **mỗi vòng lặp ngoài** (mỗi API-call
attempt), gồm ~16 cờ one-shot độc lập: OAuth theo provider (codex, anthropic,
nous, copilot — có case riêng "stale credential surfaces as 400 not 401"),
format-recovery (thinking-signature, multimodal-tool-content,
llama.cpp-grammar, image-shrink, 1M-beta header), transport (429, primary
recovery), auth-failover, và 4 "restart signal" đọc lại sau attempt
(compress-restart, length-continuation, rebuilt-messages — dùng khi
content-filter stall như MiniMax "new_sensitive" escalate sang fallback
provider, #32421 —, redirected-messages khi user gửi correction giữa lúc
đang gọi API). Mỗi cờ fire tối đa 1 lần/attempt; loop-control (`retry_count`,
`max_retries`) CỐ TÌNH ở ngoài object này vì đó là while-mechanics chứ không
phải recovery bookkeeping.

### 2.5 Công bố tiến trình cho người dùng — sự thật khắt khe hơn bar tham chiếu

Hợp đồng callback (`agent-loop.md` mục "Callback Surfaces", đối chiếu code
tại `agent/tool_executor.py:1019-1029, 1826-1836`):

- `tool.started` mang **(tool_name, preview, display_args)** — `preview` là
  `build_tool_preview()` (`agent/display.py:446-596`): với `web_search` đây
  là **query nguyên văn** (`primary_args["web_search"] = "query"`, không
  nhánh nào che giấu), cắt ở `_tool_preview_max_len`. Với `web_extract` là
  `urls`. Hermes KHÔNG giấu query/URL, nhưng cũng không tách "1 chip/1 query"
  — preview là 1 chuỗi cho toàn bộ tool call.
- `tool.completed` mang `(name, None, None, duration, is_error, result=...)`
  — `result` là **toàn bộ kết quả tool đã redact**, không phải cấu trúc
  "N nguồn + domain" chuẩn hoá. Không có event `tool.found_sources` ở tầng
  agent — muốn hiện "Found 15 results kèm favicon" thì tầng gọi phải tự parse
  JSON thô của `web_search_tool` (`{success, data: {web: [{title,url,
  description,position}]}}`, `tools/web_tools.py:838-860`).
- `build_status_phrase()` (`display.py:716-759`): `"is searching the web for
  <query>…"` — verb thân thiện + preview y hệt trên, cap 49 ký tự.
- Ẩn tuyệt đối: system prompt, payload đầy đủ tool args (chỉ preview), nội
  dung `<think>` (think_scrubber, mục 2.8), reasoning chỉ lộ qua
  `reasoning_callback` riêng.

**Kết luận quan trọng cho dự án đích**: bar tham chiếu (rebo.ai.vn) với chip
"Found 15 results" + favicon/domain KHÔNG phải là cái Hermes-framework tự
làm — đó là UI-layer parse raw tool result. Progress.py của Stock_Massive
(`apps/api/src/agent/progress.py`) thực ra đã đi XA HƠN Hermes ở điểm này:
nó có sẵn `ProgressSource(title, url, domain, snippet, published_at)` và
`searching_detail`/`found_detail` chuẩn hoá domain — Hermes không có cấu trúc
tương đương ở tầng agent core. Xem mục 4 để biết khoảng cách còn lại.

### 2.6 `session_activity.py` — quan sát, không quyết định

Contract (`session_activity.py:1-12`): "Observation-only: timestamp + bounded
description/provenance. Notification, timeout, kill, and retry policy stay
in their own components. Consumers distinguish work (API / tool / compacting
/ stalled) from the description text itself."

`_touch_activity()` (`run_agent.py:3972-4025`) là chokepoint ghi
`_last_activity_ts` + `_last_activity_desc` + `provenance` (enum đóng:
`unknown`, `agent.compression`, `agent.compression_timeout`,
`agent.compression_cooldown`). Rate-limit ghi DB ở
`SESSION_ACTIVITY_HEARTBEAT_MIN_INTERVAL_SECONDS = 60s` (hard-code, không cho
config nào biến heartbeat thành high-frequency writer,
`session_activity.py:21-29`).

Ai **quyết định** treo/kill dựa trên timestamp này (module không tự làm):
`gateway/run.py::_watch_gateway_turn_inactivity` treo turn nếu
`seconds_since_activity` vượt 30 phút (docstring dẫn tại
`tool_executor.py:516-548`); 1 daemon-thread heartbeat riêng
(`_run_tool_activity_heartbeat`, `tool_executor.py:522-550`) chạy suốt lúc
tool đang thực thi, đập `_touch_activity` mỗi 30s — vì "một tool im lặng 30+
phút (build, pytest, tải file lớn) trước đây làm đồng hồ đứng yên ở
'executing tool: X' và watchdog reap nhầm turn vẫn đang tiến triển." Ranh
giới "đang làm việc" (heartbeat còn chạy) vs "đã treo" (heartbeat dừng) nằm
đúng ở đây. Kanban dispatcher (`tools/kanban_tools.py`) dùng cùng heartbeat
để tránh reclaim nhầm worker đang chạy (#31752).

### 2.7 `stream_diag.py` — chẩn đoán khi stream đứt giữa đường

Thu thập per-attempt: `started_at`, `first_chunk_at` (TTFB), `chunks`,
`bytes`, header (`cf-ray`, `x-openrouter-provider`, `x-request-id`, ...),
`http_status`. Khi retry, ghi 1 WARNING duy nhất gộp
`flatten_exception_chain()` (đi `__cause__`/`__context__` tối đa 4 tầng để lộ
lỗi httpx thật dưới lớp bọc `openai.APIError`) — mục đích: "is one CF edge /
one downstream provider responsible, or is it random across runs?"
User-facing chỉ 1 dòng compact (`⚠️ {provider} stream drop ({ErrorType})
after {X}s — reconnecting, retry N/M`); full forensic vào `agent.log`.

### 2.8 `think_scrubber.py` — vì sao regex per-delta phá state

Vấn đề cụ thể (`think_scrubber.py:8-19`): khi model stream `<think>` và nội
dung reasoning chia làm nhiều delta riêng (`"<think>"`, `"Let me check..."`,
`"</think>"`), một regex áp riêng lẻ từng delta khớp case "unterminated-open
at boundary" trên delta1, xoá luôn `<think>`, khiến delta2 (nội dung
reasoning) bị coi là text thường và LỘ RA cho người dùng. `StreamingThinkScrubber`
giải quyết bằng state machine có bộ nhớ (`_in_block`, `_buf` giữ phần tag bị
cắt giữa 2 delta, `_last_emitted_ended_newline` để biết open-tag có đang ở
ranh giới block hay chỉ là văn bản nhắc tới `<think>`). Quy tắc: closed pair
`<tag>X</tag>` luôn bị nuốt vô điều kiện (ưu tiên 1); open-tag chỉ được coi
là block-opener nếu đứng ở đầu dòng/đầu stream (ưu tiên 2, tránh nuốt nhầm
câu "use `<think>` tags here"). `reset()` phải gọi đầu mỗi turn
(`turn_context.py:700-707`) để block treo từ 1 stream bị interrupt trước đó
không nhiễm sang turn sau; `flush()` cuối stream: nếu vẫn đang trong block →
bỏ nội dung (rò reasoning còn tệ hơn câu trả lời cụt), nếu không → nhả phần
buffer còn giữ (hoá ra không phải tag thật).

### 2.9 Reasoning model: 3 lớp vá lỗi riêng biệt

- **Stale-timeout floor** (`reasoning_timeouts.py`): NVIDIA Nemotron 3 Ultra
  đo thực tế idle-kill ~120s (NVIDIA/NemoClaw#4846) trong khi default stale
  detector là 90-180s → model bị cắt giữa lúc "nghĩ", lộ ra như
  `BrokenPipeError`/`RemoteProtocolError`. Fix: bảng floor theo slug model
  (regex neo đầu-slug để không match nhầm `olmo-1` với `o1`), áp
  `max(default, floor)`, không bao giờ hạ threshold đã config tay (#52217).
- **Boundary repair cho summary part** (`reasoning_summaries.py`): model họ
  gpt-5.x phát 1 delta `reasoning_content` cho mỗi phần tóm tắt ĐÃ HOÀN
  THÀNH, không có `summary_index` ở chat-wire (khác Responses API) → 2 phần
  dính liền `**A****B**` (render vỡ cả đoạn). Fix: chèn `\n\n` khi delta mới
  mở heading `**` và ký tự cuối phần cũ không phải whitespace (vercel/ai#6742
  vá y hệt ở tầng SDK).
- **Effort clamping** (`reasoning_effort.py`): mỗi provider công bố tập effort
  khác nhau (`ultra` là ladder nội bộ, không wire nào nhận verbatim); clamp về
  "nearest weaker" (không leo cao hơn cái user xin), trừ khi có `overrides`
  khai báo (Kimi K3: `medium→high` vì `high` là default server-side). Sinh từ
  2 lớp lỗi: level mới rơi vào wire không hỗ trợ → HTTP 400 (#89503, #70058),
  hoặc unknown-level bị hạ về default yếu hơn cả mức thấp nhất user xin —
  đảo ngược ladder (#74295, #87279).

### 2.10 `title_generator.py` — rẻ trước, nâng cấp sau

Pattern (`title_generator.py:1-18`): **Stage 1 — derived**, chạy inline, đồng
bộ, không gọi model: lấy dòng đầu message user (đã lột scaffolding
`<command-*>`, `<system-reminder>`, compaction-handoff, model-switch marker),
cắt 48 ký tự tại word-boundary. Chi phí = 0, không thể fail. **Stage 2 —
upgrade**, background daemon thread, 1 model rẻ/nhanh, `thinking` tắt, JSON
schema strict `{"title": "..."}` (loại lớp lỗi "model trả lời câu hỏi thay vì
đặt tên" — guard riêng: title >12 từ bị từ chối, port từ
can1357/oh-my-pi#7306). Provenance `derived < llm < user` enforce ở storage
layer (`set_auto_title` transaction) — stage 2 chỉ ghi đè stage 1, không bao
giờ ghi đè tên user tự đặt. Lý do tách 2 tầng: chờ tới khi assistant trả lời
xong mới đặt tên đo được p50 151s/p90 1212s trên session thật — quá chậm cho
UI cần tên ngay khi mở thread.

### 2.11 `replay_cleanup.py` — vá transcript kết thúc bằng tool_calls treo

`strip_dangling_tool_call_tail()` (`replay_cleanup.py:120-186`): khi tail
transcript là `assistant(tool_calls)` **không có bất kỳ `tool` row nào** trả
lời (process bị SIGKILL giữa lúc tool đang chạy, trước cả khi tool result
được ghi), model lượt sau tự phát lại đúng tool_call đó → nếu lệnh đó là
restart gateway thì tạo **vòng lặp reboot vô hạn** (#49201). Phân biệt theo
rủi ro: tool_call có side-effect (`tool_may_have_side_effect`) → KHÔNG xoá,
chèn tool-result giả "UNKNOWN, inspect state before retrying"; tool chỉ đọc
→ xoá thẳng dòng assistant. Khác `strip_interrupted_tool_tails()` (case CÓ
tool-result mang marker "[command interrupted]" để đọc) — case "dangling"
hoàn toàn không có gì để đọc.

---

## 3. Bài học

1. **Prologue/epilogue là 1 điểm hội tụ, nhưng không đảm bảo MỌI early exit đi
   qua nó** — comment "never reaches finalize_turn" rải rác trong code chứng
   minh mỗi lớp phòng thủ phải hoặc (a) thành helper chia sẻ gọi lại ở mọi
   early-return, hoặc (b) chấp nhận field thiếu ở đường đó. Không có cách 3.
2. **Thứ tự side-effect trong prologue là behavior, không phải tình cờ** —
   tạo session row trước/sau compression có 2 lý do độc lập (NULL
   system_prompt + FK violation), viết thành comment dài chứ không để code tự
   nói.
3. **Observation và policy phải tách bạch** (`session_activity.py`) — ai ghi
   timestamp không phải là ai quyết định kill. Tách này cho nhiều consumer
   (watchdog, dispatcher, CLI) áp policy khác nhau trên cùng 1 nguồn sự thật,
   và sửa 1 bug (heartbeat khi tool im lặng) không đổi observation contract.
4. **Regex đúng cho 1 chuỗi hoàn chỉnh không tự đúng khi chạy per-delta** —
   bộ lọc trên stream phải giữ state qua các lần gọi (buffer phần chưa quyết
   định được), không tái dùng hàm viết cho input tĩnh.
5. **"Rẻ trước, đúng sau" áp dụng cho mọi tác vụ generative phụ** — miễn có 1
   cách rẻ-không-thể-sai lấp chỗ ngay, và storage có precedence rõ ràng để
   nâng cấp không đua với ghi đè của người dùng.
6. **Bar tiến trình đẹp là việc của UI/consumer parse tool result, không phải
   framework agent-loop tự cho** — Hermes chỉ cam kết "không giấu query/URL
   trong preview", cấu trúc hoá kết quả (N nguồn, domain) không có ở tầng
   lõi. Stock_Massive (`progress.py`) đã làm phần này tốt hơn Hermes, chỉ
   thiếu độ chi tiết theo thời gian (mục 4).
7. **Vá lỗi theo bằng chứng đo được, không đoán** — ngưỡng trong
   `reasoning_timeouts.py` neo vào số đo cụ thể (NemoClaw#4846: TTFB ~31s,
   kill tại 120s), không phải hằng số áng chừng — giúp review sau biết khi
   nào ngưỡng lỗi thời.

---

## 4. Port được gì sang `turns.py` / `events.py` / `progress.py` / `use-live-turn.ts`

Đối chiếu code hiện tại: `TurnService._execute` (`turns.py:348-378`) đã gom
MỌI exit path (TimeoutError, CancelledError, AlphaRefusal, Exception, success)
qua đúng 2 cửa `_finish`/`_finish_bare` — cấu trúc này **tốt hơn** Hermes (xem
mục 5, điểm 1), nên phần port ưu tiên là quan sát/chẩn đoán, không phải tái
cấu trúc control-flow.

### 4.1 Chẩn đoán route_error/gateway_timeout — ưu tiên cao nhất (đúng vào vấn đề đo được)

`loop.py:737-740` — `GatewayTimeout` hiện **không log gì cả** (route_error thì
có log message sau commit a78d4eb, gateway_timeout thì im lặng hoàn toàn):

```python
except GatewayTimeout:
    return await self._terminal(
        request, TurnStatus.INCOMPLETE, "gateway_timeout", state
    )
```

Đây là 3/4 lỗi trong "ops 7 ngày: gateway_timeout 3 + route_error 1 / 11
turn". Port từ `agent/stream_diag.py`: thêm 1 dict per-attempt (`started_at`,
`first_chunk_at`, `bytes/chunks` nếu route client lộ được, header
`x-request-id`/tương đương) tại nơi gọi route trong `loop.py`; cả
`except GatewayTimeout` và `except LLMError` log 1 WARNING gộp tên route,
TTFB đã trôi trước khi timeout, header forensic nếu có — y hệt mẫu
`log_stream_retry()` (1 dòng, đầy đủ, không cần bật debug). Không cần port
`flatten_exception_chain()` nguyên bản, nhưng Ý TƯỞNG "lộ lỗi thật dưới lớp
bọc SDK" áp dụng thẳng cho bất kỳ lớp bọc lỗi route nào đang dùng.

### 4.2 `session_activity` — phân biệt "đang chạy chậm" vs "treo thật" trước khi hết deadline

`TurnService._execute` chỉ có 1 deadline cứng
(`asyncio.wait_for(..., self._deadline)`, `turns.py:361`) — turn tiến triển
chậm (tool/route chậm) và turn treo thật hết hạn giống nhau, không có tín
hiệu trung gian trong log/ops. Port tối thiểu (không cần contract đầy đủ):
thêm field observation-only trên `RunningTurn` (`last_activity_at`,
`last_activity_desc`), cập nhật tại boundary đã có (`_activity()`,
`loop.py:1030`, mỗi tool round); log-khi-timeout đọc field này để phân biệt
"chết ngay khi gọi route" (Y≈X) với "chết giữa 1 vòng tool cụ thể" (Y<<X) —
biến 36%-chết-vì-route từ 1 con số thành chẩn đoán được. KHÔNG cần
heartbeat-thread riêng như `_run_tool_activity_heartbeat`: round-trip của
Stock_Massive ngắn hơn process CLI dài hạn của Hermes nhiều, rủi ro "tool im
lặng 30 phút" không tương ứng 1:1 — xác nhận giới hạn timeout tool hiện có
trước (câu hỏi mở, mục 6).

### 4.3 Timeline tiến trình đạt bar tham chiếu — cụ thể theo `progress.py`/`events.py`/`loop.py`

`progress.py` đã có `queries_of`, `sources_of`, `merge_sources`, domain
chuẩn hoá — **gần bar tham chiếu hơn Hermes**. Khoảng cách còn lại nằm ở
`loop.py` (thời điểm phát activity) và `live-turn.ts` (thời điểm ngắt phase):

- **Tách "đang tìm" khỏi "đang đọc trang"**: `loop.py:794-806` hiện gộp mọi
  tool call của round vào 1 activity trước round (`SEARCHING`/`READING_DATA`),
  rồi `_found_sources` gộp kết quả cả round (cả `web_search` và `fetch_url`)
  vào 1 `FOUND_SOURCES` sau round. Bar tham chiếu có 4 bước tách biệt:
  `searching(chips)` → `found N results` → `fetching content from URLs` →
  `fetched content from N URLs`. Port ý tưởng `tool.started` mang preview của
  Hermes (mục 2.5): phát activity `FETCHING_CONTENT` riêng ngay khi model gọi
  `fetch_url` (đọc URL từ arguments như `queries_of` đang làm cho
  `web_search`), TRƯỚC khi tool chạy — rồi 1 activity kết quả riêng cho fetch
  (đếm URL fetch thành công) SAU round, tách khỏi `FOUND_SOURCES` của search.
  Thêm 1 giá trị enum mới trong `Activity` (`events.py:85-104` — vẫn đóng, chỉ
  thêm giá trị) + hàm `fetching_detail()`/`fetched_detail()` trong
  `progress.py` cùng khuôn `searching_detail`/`found_detail`.
- **Phát activity trước khi tool chạy** — `loop.py:800-806` đã đúng cho search
  (đọc arguments trước round). Lặp lại đúng pattern cho `fetch_url` khi thêm
  `FETCHING_CONTENT` — không cần học gì thêm từ Hermes.
- **`live-turn.ts` đã pipe `detail` xuyên suốt** (`live-turn.ts:253-260`) —
  không cần sửa reducer, chỉ cần UI component (`view-new.tsx`) render thêm 2
  phase mới.

### 4.4 Sinh tên thread — pattern rẻ-trước-nâng-cấp-sau

Dự án chưa có title generator (`suggestions.py` chỉ sinh câu hỏi gợi ý sau
câu trả lời — mục đích khác). Nếu cần đặt tên Thread tự động, port pattern 2
tầng của `title_generator.py`: Stage 1 (rẻ, đồng bộ, tại `TurnService.create`)
— dòng đầu message user, cắt ~48-80 ký tự tại word-boundary, không gọi LLM;
Stage 2 (nâng cấp, async, sau/song song Turn đầu) — 1 lời gọi model rẻ, JSON
schema strict, guard "answer-shaped output" (title quá dài → model trả lời
nhầm, bỏ qua). Precedence `derived < llm < user` enforce ở write layer
(`persistence.py`) bằng 1 transaction check-and-set, không phải ở call site.

### 4.5 Dọn transcript sau turn chết giữa vòng tool

Xem mục 5, điểm 3 — khả năng cao **không cần port trực tiếp** `replay_cleanup.py`
vì "freeze, never resume" (`persistence.py:969-1021`) đã tránh lớp lỗi này ở
gốc. Nhưng logic phân loại rủi ro của `strip_dangling_tool_call_tail` — "tool
có side-effect thì KHÔNG xoá, đánh dấu UNKNOWN; tool chỉ đọc thì xoá thẳng" —
đáng dùng lại nếu `message_builder` trong `freeze_interrupted_turns`
(`persistence.py:969-985`, đã có callback) từng cần build message
"incomplete" cho turn đông cứng giữa lúc chạy tool — kiểm tra xem callback
hiện tại có phân loại theo side-effect hay chỉ ghi chung "không hoàn thành"
(câu hỏi mở, mục 6).

---

## 5. Không port gì, và vì sao

1. **KHÔNG port kiến trúc "20 điểm return rải rác, bỏ qua finalizer"** — nợ
   kỹ thuật của Hermes (docstring `turn_finalizer.py` tự gọi code cũ là
   "god-file"), không phải pattern nên học. `TurnService._execute` đã đúng
   từ đầu (mọi lỗi qua `_finish`/`_finish_bare`) — điểm mạnh cần giữ.
2. **KHÔNG port `think_scrubber.py`** — vá việc model chèn tag `<think>` thô
   vào content stream ở chat-completions wire. Stock_Massive chặn theo tầng
   Turn Publisher/Activity enum đóng, không theo lọc text — nếu model tương
   lai chèn `<think>` vào `content`, vấn đề nằm ở route/response-parsing.
3. **KHÔNG port `replay_cleanup.py` nguyên bản** — Hermes phải vá vì nó
   replay thẳng list message thô vào lượt gọi model tiếp theo.
   `persistence.py:969-1021` ("V1 never resumes execution... an honest
   incomplete... is worth more") đóng băng Turn chết thành `incomplete` và
   đóng luôn, không replay tool_calls treo — nếu đúng vậy, #49201 không tồn
   tại ở kiến trúc này (xác nhận thêm mục 6).
4. **KHÔNG port `turn_retry_state.py` nguyên bản** — số nhánh retry của
   Hermes phản ánh việc tự quản nhiều provider/OAuth trực tiếp. Stock_Massive
   có 1 route layer thống nhất, đã tách bạch đủ 5 loại lỗi
   (`loop.py:710-761`) — không OAuth-per-provider, không
   format-recovery-per-vendor cần đếm riêng.
5. **KHÔNG port `KawaiiSpinner`/`display.py`** — bề mặt khác hẳn (terminal
   ANSI vs SSE + React). Chỉ port ý tưởng ở mục 2.5/4.3, không port code.
6. **KHÔNG port `aux_accounting.py`/`oneshot.py`** — kế toán token cho LLM
   call phụ qua ContextVar; `progress.py`/`loop.py` chưa cho thấy nhu cầu đó.

---

## 6. Câu hỏi chưa giải quyết

1. Turn `incomplete` bị đóng băng bởi `freeze_interrupted_turns` — nếu dừng
   giữa lúc gọi tool, `TranscriptToolCall` của round đó có bị đưa vào
   `history` của Turn kế tiếp cùng Thread không? Nếu có, lớp lỗi
   #49201/#48879 vẫn có thể xảy ra và cần 1 bản rút gọn của
   `strip_dangling_tool_call_tail` tại nơi build `history=` truyền vào
   `TurnRequest` — cần đọc `agent/context.py` để xác nhận.
2. `loop.py:_deadline` là 1 giá trị cứng cho toàn turn — có tách riêng
   timeout "1 vòng tool" vs "toàn turn"? Nếu không, activity-heartbeat (mục
   4.2) chỉ có ý nghĩa observability, không đổi thời điểm turn bị cắt — cần
   xác nhận có muốn đổi cả chính sách cắt hay chỉ cần log tốt hơn.
3. Không đọc được `gateway/run.py` (ngoài phạm vi giao) nên watchdog
   `_watch_gateway_turn_inactivity` chỉ trích từ docstring tham chiếu, chưa
   xác minh trực tiếp threshold 30 phút.
4. Chưa xác nhận `progress.py`/`loop.py` có giới hạn tần suất phát
   `FOUND_SOURCES` riêng hay dùng chung `Checkpointer` 1 lần/giây
   (`turns.py:138-171`) — nếu chung, activity mới ở mục 4.3 tự động
   rate-limit đúng, không cần cơ chế riêng.
