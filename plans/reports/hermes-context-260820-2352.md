# Hermes Agent — quản lý context: đọc code, rút bài học cho Stock_Massive

Nguồn: clone sparse tại `/private/tmp/.../scratchpad/hermes-agent` (agent/, tools/, root .py) + `website/docs/developer-guide/context-compression-and-caching.md` (fetch qua raw URL). Toàn bộ `file:line` dưới đây trỏ vào clone đó, path tương đối từ root repo Hermes.

## 1. Kiến trúc context của Hermes

Không có một "context manager" — có **4 lớp độc lập, xếp tầng**, mỗi lớp tắt/mở riêng:

1. **`ContextCompressor`** (`agent/context_compressor.py`, 8027 dòng, class `ContextCompressor(ContextEngine)` tại dòng 1989) — cơ chế chính: prune tool-result xác định (không LLM) → protect head/tail → summarize middle bằng LLM phụ. Đây là "lossy summarization" theo đúng nghĩa.
2. **`conversation_compression.py`** (4419 dòng) — không phải cơ chế nén khác, mà là **orchestration layer** gọi `ContextCompressor.compress()`, quản lý SQLite session (rotate vs in-place), lock/commit-fence, timeout trên thread pool, và phát lại warning qua gateway.
3. **`native_compaction.py`** (345 dòng) — ủy quyền nén cho **server OpenAI** (Responses API) khi model là gpt-5.6 trên route trực tiếp; compressor local (#1) vẫn luôn "armed" làm fallback.
4. **Prompt caching** (`prompt_caching.py`, `prompt_cache_boundary.py`, `prompt_cache_scope.py`) — không nén gì cả, chỉ đặt `cache_control` breakpoint để giảm cost/latency của phần context KHÔNG đổi giữa các turn. Độc lập hoàn toàn với 3 lớp trên, nhưng lớp #2 (rotation session_id) từng phá lớp này (#79161/#79017).

Nguyên tắc chủ đạo xuyên suốt cả 4 lớp, phát biểu ở nhiều nơi: **ước lượng rough (char/4) chỉ dùng để RA QUYẾT ĐỊNH (preflight, trigger), số thật luôn lấy từ `usage.prompt_tokens` do provider trả về** (`update_from_response`, dòng 3209). Đây là điểm khác biệt lớn nhất với `apps/api/src/agent/context.py` hiện tại — nơi `estimate_tokens` (char/3, dòng 176) là SỐ DUY NHẤT, không có "real usage" nào ghi đè lại.

---

## 2. Từng cơ chế + số hiệu sự cố

### 2.1. Ngưỡng kích hoạt nén, ai quyết định, chống thrash

- **Ngưỡng cơ bản**: `threshold_tokens = effective_window * threshold_percent`, `effective_window = context_length - max_tokens` (trừ phần output reserve) — `_compute_threshold_tokens` (`agent/context_compressor.py:2936-2975`). Có 2 sàn/trần:
  - Model nhỏ (<512K, `_SMALL_CTX_WINDOW_LIMIT` dòng 1231): threshold không dưới 75% (`_SMALL_CTX_THRESHOLD_PERCENT`, dòng 1232) — `_effective_threshold_percent` (2919-2934). Lý do: model context nhỏ mà threshold 50% flat sẽ nén liên tục vô ích.
  - Nếu `floored >= effective_window` (model rất nhỏ, ví dụ 64K = `MINIMUM_CONTEXT_LENGTH` tại `agent/model_metadata.py:405`), threshold = 85% window (`_MIN_CTX_TRIGGER_RATIO`, dòng 2860) — vì `max(0.5*64000, 64000) == 64000` khiến ngưỡng = TOÀN BỘ window, nén không bao giờ chạy được, provider từ chối request trước (**#14690**).
  - Per-model override qua substring match, **key dài nhất thắng** (`resolve_model_threshold`, 1963-1985) — ví dụ `glm-5.2-1M` thắng `glm-5.2`.
- **Ai quyết định chạy**: `should_compress()` (3374) chỉ gọi `should_compress_info()` (3389) — so `tokens < threshold_tokens` rồi hỏi `_automatic_compression_blocked()` (3468). Hai điểm đo tokens KHÁC NHAU cố ý: preflight dùng rough estimate (`should_defer_preflight_to_real_usage`, 3304), verdict "có hiệu quả không" luôn đo trên **real usage** trong `update_from_response` — vì rough có thể dao động qua threshold mỗi turn và tự "reset" strike, mở lại vòng lặp thrash (**#36718**, comment dòng 3252, 3354).
- **Cooldown chống freeze-loop (#11529)**: khi LLM tóm tắt lỗi (429/transient), `_generate_summary` set `_summary_failure_cooldown_until` (qua `_record_compression_failure_cooldown`, 2671) và trả `None`; `compress()` chèn fallback tĩnh và return. Không có cooldown thì mỗi turn sau đó token vẫn > threshold → nén lại → lỗi lại → CLI "đứng hình" (dòng 3490-3494, đây chính là **issue #11529**). Cooldown escalate theo bậc thang timeout: 60s → 300s → 900s (`_TIMEOUT_COOLDOWN_LADDER`, dòng 5051-5057, tái dùng ở `record_timeout_failure` 2699, gộp logic một chỗ vì **#62452**). `/compress` thủ công (`force=True`) xoá cooldown để retry ngay.
- **Anti-thrash (không phải "tiết kiệm <10%" như docstring nói)**: `should_compress` docstring (3374-3384) nói "last two compressions each saved less than 10%" nhưng **code thật** (`update_from_response`, 3209-3273) đo nhị phân: *"real prompt tokens sau nén còn >= threshold hay không"* — không phải % tiết kiệm. Đây là **docstring trôi khỏi hành vi thật** (lý do giải thích tại 3243-3247: system prompt + tool schema là sàn không thể nén được — 50+ tools chiếm 20-30K token cố định, **#14695** — nên đo "có xuống dưới ngưỡng" đúng hơn đo "% giảm"). Strike ghi qua `_record_ineffective_compression_verdict`, ngưỡng trip = 2 lần liên tiếp (`_ineffective_compression_count >= 2` hoặc `_fallback_compression_streak >= 2`, `_automatic_compression_blocked_locally`, 3482).
- **Recovery khỏi trip (không vĩnh viễn — #14694)**: guard bị trip không tắt nén mãi mãi. Sau `_ANTI_THRASH_RECOVERY_SECONDS = 300.0` (dòng 2869) liên tục bị block, cho phép ĐÚNG 1 lần probe (hạ counter về 1, không về 0) — 3502-3532. Đồng hồ chỉ arm khi lần đầu bị BLOCK (lazy), không persist tại thời điểm trip, để restart process không "vô hiệu hoá" guard sớm hơn dự kiến (**#69872** load lại tripped counter từ DB, **#54923** "restart không được tháo guard").
- **`record_rejected_compaction()`** (2517): khi commit-layer (conversation_compression) từ chối một candidate compaction vì nó LÀM PHÌNH transcript, phải tính là 1 strike ineffective — nếu không, breaker không thấy gì, nén lặp lại y hệt mỗi turn, cùng summary request, cùng refusal (**#88568**).

### 2.2. `protect_first_n` / `protect_last_n`

- `protect_first_n`: bảo vệ N message đầu (sau system prompt) chỉ ở **lần nén đầu tiên**. Từ lần nén thứ 2 trở đi, **decay về 0** — `_effective_protect_first_n` (5748-5781): nếu không decay, các turn đầu bị "fossilize" — copy lại vào mỗi child session, không bao giờ bị tóm tắt, làm head phình vô hạn qua một session dài (**#11996**). Có xử lý phục hồi trạng thái decay sau restart bằng cách probe xem message đầu có phải "handoff summary" hay không (`_restart_handoff_probe_bounds`).
- `_protect_head_size` (5783): `head = 1 (nếu có system) + _effective_protect_first_n(...)`. System prompt LUÔN được bảo vệ riêng, độc lập với `protect_first_n`.
- `protect_last_n` (default 20, theo docs) hoạt động **kết hợp** với token budget, không đơn thuần: nó là **sàn tối thiểu về SỐ MESSAGE**, còn tiêu chí chính là **token budget** (`tail_token_budget`, tài liệu: `threshold_tokens * summary_target_ratio`, `summary_target_ratio` mặc định neo ở `max(0.10, min(x, 0.80))`, dòng 3061). Cơ chế cụ thể ở `_find_tail_cut_by_tokens` (6127-6270):
  - Đi ngược từ cuối, cộng token cho tới khi vượt `soft_ceiling = token_budget * 1.5` — cho phép vượt 1.5x để không cắt giữa 1 message khổng lồ.
  - `min_tail = min(protect_last_n, _MAX_TAIL_MESSAGE_FLOOR)` — **`protect_last_n=20` bị chặn trần bởi `_MAX_TAIL_MESSAGE_FLOOR`** (dòng 1211, không lộ giá trị cụ thể ở đoạn đọc nhưng comment nói rõ mục đích: "so a default protect_last_n=20 cannot lock a bulky recent tool run outside the compressible/prunable window", **#61932**).
  - Có 4 "anchor" bắt buộc nằm trong tail, mỗi anchor chỉ được kéo `cut_idx` **lùi lại** (monotonic — tail chỉ lớn thêm, không bao giờ nhỏ đi): user message gần nhất (**#10896**), assistant message gần nhất (**#29824** — bug UI hiển thị "trả lời ngoài compaction summary"), N user message gần nhất nếu `min_tail_user_messages > 1`, và align theo tool_call/result group (`_align_boundary_backward`/`_align_boundary_forward`) để không cắt đứt giữa 1 cặp gọi/kết quả tool (gây mất dữ liệu khi `_sanitize_tool_pairs` xoá tool result mồ côi).
  - Nếu TOÀN BỘ transcript vừa trong `soft_ceiling` (không tìm được điểm cắt có ý nghĩa) → walk lại với `raw_budget` không có hệ số 1.5x, tránh vòng lặp nén vô tận trên transcript ngắn (**#40803**).
- **Phần giữa (middle) bị làm gì**: bị **tóm tắt bằng LLM phụ** thành 1 message summary (rung 3), KHÔNG bị xoá trắng. Nếu LLM phụ thất bại toàn phần → `_build_static_fallback_summary` (4088) — một fallback tĩnh không cần LLM (liệt kê deterministic các file/lệnh đã chạy), tốt hơn mất trắng ngữ cảnh.

### 2.3. Model phụ (auxiliary) để summarize

- Chọn qua `agent.auxiliary_client._resolve_task_provider_model("compression", model=self.summary_model)` (gọi tại dòng 4823-4831) — override bằng config `auxiliary.compression.model/provider/base_url`; nếu không set, dùng `self.model` (model chính) luôn.
- Gọi 1 lệnh LLM duy nhất `call_llm(task="compression", ...)` (dòng 4848), **không set `max_tokens`** — cap output sẽ cắt cụt summary giữa lúc model "thinking", gây summary rỗng hoặc chỉ có phần suy luận (áp dụng cho Anthropic Messages wire và NVIDIA NIM — comment 4802-4809).
- Bọc trong `aux_interrupt_protection()` — nén là atomic, một user message tới giữa lúc gọi LLM phụ không được phép abort nó, nếu không mất cả handoff thật (**#23975**).
- **Fallback thất bại theo tầng**, xử lý tại except-block (4917-5090):
  1. `RuntimeError("no llm provider configured")` → cooldown DÀI (`_SUMMARY_FAILURE_COOLDOWN_SECONDS = 600`, dòng 1195) — lỗi cấu hình vĩnh viễn, không tự phục hồi.
  2. Response rỗng/whitespace (một số proxy trả 200 với `content` rỗng) → coi như lỗi transport, KHÔNG lưu summary rỗng — nếu không sẽ "xoá trắng" các turn đã nén (**#11978, #11914**).
  3. Lỗi có vẻ vĩnh viễn trên aux model riêng (model not found/503/404, timeout, JSON decode lỗi, stream đóng giữa dòng — **#18458**) VÀ `summary_model != model` VÀ chưa fallback → gọi `_fallback_to_main_for_compression()` (4462) rồi **retry ngay trên model chính** (`self._generate_summary(...)` đệ quy 1 lần, dòng 5013).
  4. Lỗi KHÔNG rõ loại nhưng còn cơ hội fallback main model chưa dùng → cũng fallback + retry 1 lần — "mất N turn context luôn tệ hơn 1 lần thử tóm tắt nữa" (**#8620 sub-issue 4**, comment 4977-4984).
  5. Hết đường fallback → cooldown transient theo bậc thang timeout (60/300/900s, escalate theo streak liên tiếp, **#62452**) hoặc 30s (JSON decode/stream đóng) hoặc 60s mặc định; lỗi auth/quota được đánh dấu riêng (`_is_summary_access_or_quota_error`, dòng 87) để **compress() ABORT giữ session nguyên vẹn** thay vì phá middle window đổi lấy 1 placeholder (**#29559, #25585**) — vì lỗi auth/quota có thể MẤT VĨNH VIỄN dữ liệu nếu tiếp tục.
- Yêu cầu ràng buộc từ docs: **aux model phải có context window >= model chính** — nếu không thì compression tự hạ threshold hoặc cảnh báo lúc khởi động (`check_compression_model_feasibility`, thấy tên trong docstring module `conversation_compression.py:6-9`, không đọc thân hàm).

### 2.4. `prune_tool_results_only` — deterministic, không LLM

- Hàm `prune_tool_results_only` (3859-3975) là **rung riêng, KHÔNG dùng compress()**: chạy phase-1 prune (`_prune_old_tool_results`, 3567) mà bỏ hẳn phase tóm tắt LLM.
- **Trigger khác hoàn toàn compress()**: gated trên `self.proactive_prune_tokens` — thấp hơn NHIỀU so với full-compression threshold (docstring: trên model context lớn, `should_compress()` ~50% window hiếm khi chạy, tool output cũ vẫn nằm trong history và gửi lại y nguyên mỗi turn — prune sớm thu hồi phần này mà không rủi ro chất lượng của LLM summarization).
- **3 pass xác định** trong `_prune_old_tool_results`:
  1. **Dedup byte-identical** — hash MD5 12-ký-tự nội dung tool result, giữ bản mới nhất, thay bản cũ = `"[Duplicate tool output — same content as a more recent call]"`. Chạy TRÊN TOÀN LIST kể cả vùng tail được bảo vệ — vì dedup không mất dữ liệu (lossless).
  2. Thay tool result lớn (> `min_prune_chars`, default `_PRUNE_MIN_CHARS = 200`, dòng 678) ngoài tail bằng 1 dòng tóm tắt xác định (`_summarize_tool_result`, 1756) — ví dụ `[terminal] ran npm test -> exit 0, 47 lines output`. Có "ghost-skill defense" (**#32106**): skill vừa load hoặc còn được tham chiếu trong tail giữ nguyên `skill_view` body, không bị demote — nếu không model tưởng skill đó vẫn "còn tải" trong context nhưng thực ra bị tóm tắt mất.
  3. Truncate JSON args của `tool_calls` lớn (> 500 ký tự) ngoài tail — dùng `_truncate_tool_call_args_json` (giữ JSON hợp lệ để không 400 ở request sau).
  4. **Pass 4 — pressure demotion (#61932)**: sau nhiều lần in-place compaction, transcript có thể ngắn tới mức GẦN NHƯ TOÀN BỘ nằm trong "protected tail" nhưng vẫn là các tool output khổng lồ → middle rỗng, không nén được gì, preflight báo "Cannot compress further". Giải pháp: demote NGAY BÊN TRONG vùng bảo vệ, giữ 1 floor gần nhất verbatim (`_PRESSURE_KEEP_RECENT_MESSAGES`, dòng 1222), có thể ghi đè cả ghost-skill defense khi bị áp lực thật.
- **Gate commit (prompt-cache hysteresis)**: chỉ commit khi thu hồi >= `proactive_prune_min_reclaim_tokens`, và sau khi commit phải "chờ" (`_proactive_prune_rearm_tokens`) đủ 1 khoảng tăng token mới bằng `runway = max(reclaimed, proactive_prune_tokens, proactive_prune_min_reclaim_tokens)` trước khi prune lại — vì MỖI lần prune ghi lại message body = phá cache prefix từ điểm sửa đổi trở đi, giống hệt một compaction boundary; prune liên tục sẽ phá cache liên tục.
- **Capability gate trước khi scan**: nếu session store (`_session_db`) không có `archive_and_compact` callable → return no-op NGAY, tránh trả giá quét 3-pass cho một prune sẽ không lưu được (permanent no-op).
- **So sánh với compress()**: `prune_tool_results_only` bảo vệ tail theo **SỐ MESSAGE** (`protect_last_n`), KHÔNG theo token budget — vì `tail_token_budget` xuất phát từ ngưỡng 50% (≈100K trên window 1M) sẽ bảo vệ nguyên session, prune chẳng còn gì để làm.

### 2.5. Prompt caching (Anthropic-style 4 breakpoint)

- **Layout mặc định** (`agent/prompt_caching.py` docstring, dòng 1-11): 4 cache_control breakpoint = system prefix tĩnh + cuối system prompt + 2 message gần nhất không phải system. Không có static prefix → fallback: 1 breakpoint system + 3 message cuối. Tất cả breakpoint dùng CÙNG TTL (5m hoặc 1h).
- Đặt breakpoint: `apply_anthropic_cache_control` (434-479) — nếu message[0] là system và có `static_system_prefix` khớp đầu content, split content thành `[prefix (marked), suffix (marked)]` = 2 breakpoint; còn lại `4 - breakpoints_used` breakpoint rải vào các non-system message CUỐI CÙNG có thể "carry marker" (`_can_carry_marker`, 91-112 — loại các message content rỗng/list không kết dict cuối, vì marker top-level trên layout envelope OpenRouter bị provider bỏ qua âm thầm, phí 1 breakpoint).
- **TTL**: `effective_cache_ttl` (145-167) — clamp `1h` xuống `5m` cho model/provider Qwen/Alibaba (`ALIBABA_FAMILY_PROVIDERS`, dòng 127) vì context cache của họ documented là window 5 phút (renew khi hit), không hỗ trợ tier 1h của Anthropic — gửi `1h` sẽ bị provider "rejected/drop" tạo ra kỳ vọng cache sai (**#84733**).
- **Boundary động cho skill/webhook/cron** (`prompt_cache_boundary.py`): registry `register_stable_prefix()`/`find_stable_prefix()` cho phép builder (skill/webhook/cron) khai báo trước điểm cắt giữa "scaffold tĩnh" và "phần biến đổi" (ticket payload, timestamp) TRONG CÙNG 1 user message string — vì tự parse marker string trong content không an toàn (marker "hợp pháp" có thể xuất hiện trong thân skill hoặc payload sự kiện, **#81867**). Registry giới hạn 32 entry HOẶC 4MB tổng ký tự (`_MAX_ENTRIES`, `_MAX_CHARS`, dòng 41+50), LRU eviction, luôn giữ ít nhất 1 entry mới nhất.
- **Vì sao rotation session_id từng phá cache (#79161/#79017)**: `prompt_cache_scope.py` docstring (1-36) — chế độ nén "legacy" (`compression.in_place: false`) tạo **session_id vật lý mới** giữa cuộc hội thoại để phân đoạn transcript. Cache scope ban đầu (#79161) lấy trực tiếp session_id vật lý làm cache bucket → MỖI lần rotate = 1 bucket cache MỚI dù về logic vẫn là 1 cuộc hội thoại tiếp diễn (**#79017**, mất cache liên tục). Fix: `resolve_prompt_cache_scope()` map session_id vật lý về ROOT của "compression lineage" (`SessionDB.get_compression_lineage`, hardened bởi **#79193**) — CHỦ Ý dùng lineage walk khác với `get_conversation_root` (dùng cho Portal-attribution) vì cái sau follow `parent_session_id` mù quáng, gộp cả `/branch` con và subagent-delegate vào 1 id, phá vỡ ranh giới isolation mà #79161 cố tình dựng lên. Kết quả thực tế trong Hermes hiện tại: **`compression.in_place` mặc định `True` từ #38763** — không rotate nữa, nên bug lineage này chỉ còn ảnh hưởng legacy mode.
- Memoize theo `(agent, session_id)`, chỉ re-walk khi session_id thực sự đổi (rotation) hoặc DB handle đổi — tránh query DB trên mọi API call.

### 2.6. Native compaction OpenAI Responses (gpt-5.6)

- **Chỉ áp dụng khi**: model thuộc family `gpt-5.6` (substring match, 52-57) VÀ route trực tiếp `api.openai.com` hoặc ChatGPT Codex OAuth backend (60-72) — mọi route khác (xAI, GitHub/Copilot, relay, local server) không nhận field vì hầu hết sẽ 400 trên param lạ, và không route nào khác có thể tạo/giải mã blob mã hoá.
- **Cơ chế**: gửi `context_management=[{"type": "compaction", "compact_threshold": N}]`; khi input vượt N token, server trả về 1 output item `type: "compaction"` chứa `encrypted_content` sealed cho endpoint phát hành — client replay lại item này ở các request sau, đứng thay cho lịch sử đã bị prune, model vẫn nhớ dài hạn mà client KHÔNG BAO GIỜ thấy nội dung summary.
- **`resolve_compact_threshold`** (75-106): kẹp threshold native LUÔN THẤP HƠN threshold local `LOCAL_TRIGGER_SAFETY_MARGIN = 8_192` token — để server luôn được nén TRƯỚC; nếu không clamp, threshold native cao hơn local sẽ khiến local summarizer luôn chạy trước, biến config native thành "dead config".
- **Rủi ro lớn nhất — hành vi server đã live-verify (Aug 2026, comment 150-157)**: server **KHÔNG render bất cứ thứ gì đặt TRƯỚC 1 checkpoint replay** — một fact đặt trước checkpoint là "invisible" với model (recall = "NONE"), cùng fact đặt SAU checkpoint thì recall hoàn hảo. → Nếu client gửi lại toàn bộ history cũ (bao gồm plaintext user ask trước điểm nén) một cách ngây thơ, MỌI user ask trước đó chỉ còn sống sót qua bất cứ gì summary mờ của server giữ lại — **goal-drift**. Giải pháp: `prune_pre_checkpoint_items` (186-266) tái cấu trúc wire thành `[checkpoint run] + [retained user messages, budget 64K token, newest-first] + [post]` — bắt chước cách Codex CLI tự rebuild history giữ nguyên user message. Tìm run checkpoint MỚI NHẤT (server có thể emit nhiều compaction item liên tiếp trong 1 response — cũng live-observed) vì nó cumulative, các run cũ bị bỏ.
- **Rủi ro mô hình sai**: gửi field cho gpt-5.1/5.2 "reliably fails server-side" — HTTP 500 trên blocking path, **stall vĩnh viễn trên streaming path** (90s watchdog x 3 retry = 1 turn chết) — KHÔNG có structured "unsupported" để tự downgrade, nên gate CHỈ dựa vào model-family check tường minh, không dựa vào thử-và-lỗi.
- **Cơ chế phục hồi khi bị reject (#82777)**: `is_native_compaction_rejection` (269-303) phân biệt reject THẬT (status 400 + text chứa `context_management`/`compact_threshold` VÀ ngôn ngữ từ chối như "unknown/unsupported/invalid...") với 1 lỗi 5xx/timeout TẠM THỜI mà body chỉ ECHO lại tên field — false positive ở đây sẽ downgrade native compaction VĨNH VIỄN cho cả session dù server chỉ hiccup 1 lần.
- **Merge state qua Codex incomplete-retry**: `merge_interim_reasoning_items` (322-345) — retry cập nhật lại message "trùng hình" bằng payload mới hơn; nhưng checkpoint chỉ tồn tại ở response CŨ (continuation không emit lại), nên rule "mới thắng nhưng checkpoint cũ luôn được PREPEND trừ khi payload mới đã có checkpoint của riêng nó" — bảo toàn compaction đã đạt được.

### 2.7. Ước lượng token — char/4, không dùng tokenizer thật

- `estimate_tokens_rough` (`agent/model_metadata.py:3277-3303`): fast-path ASCII = `(len+3)//4` (ceiling, tránh text ngắn ước lượng 0 token — gây undercount hệ thống khi có nhiều tool result ngắn). CJK/Hangul/Kana đếm ~1 token/codepoint (đậm đặc hơn nhiều so với luật 4-char/token tiếng Anh) — dùng `re.findall` mức C, không loop Python per-char, vì hàm này chạy trên MỌI message của MỌI preflight/compaction walk kể cả tool output cỡ MB.
- `estimate_messages_tokens_rough` (3308-3320): ảnh (base64) tính flat **1500 token/ảnh** (theo giá Anthropic) thay vì đếm ký tự base64 thô — nếu không, 1 screenshot ~1MB sẽ ước lượng ~250K token, kích hoạt nén sớm sai.
- **Memoization theo "identity fingerprint"** (3327-3400) — vì hàm chạy lại trên TOÀN BỘ history mỗi vòng lặp conversation_loop, mỗi lần telemetry compaction, và trong 1 shrink loop O(n²) của moa_loop; fingerprint dựa trên `id()` string (pin giữ tham chiếu mạnh để id không bị tái sử dụng) + giá trị số + đệ quy dict/list giữ thứ tự key — cache LRU tối đa 4096 entry.
- **Vì sao KHÔNG dùng tokenizer thật** (không có câu phát biểu tường minh 1 chỗ, suy ra từ nhiều đoạn nhất quán):
  1. Route đa provider (OpenAI, Anthropic, DashScope/Qwen, local GGUF, OpenRouter...) — mỗi family tokenizer khác nhau, không có 1 tokenizer chung đúng cho tất cả; số thật CHỈ provider mới biết, và Hermes lấy đúng số đó qua `update_from_response()` (real `usage.prompt_tokens`) — rough estimate chỉ tồn tại để RA QUYẾT ĐỊNH TRƯỚC KHI CÓ số thật (preflight, trước request đầu).
  2. `agent/context_breakdown.py:1-6`: hàm UI breakdown dùng "the same rough char/4 heuristic ... so numbers align with compression thresholds — **not exact tokenizer counts**" — mục tiêu là NHẤT QUÁN VỚI CHÍNH NGƯỠNG NÉN (cũng đo bằng rough), không phải đúng tuyệt đối.
  3. Hiệu năng: chạy trên MB tool output mỗi turn — 1 tokenizer thật (BPE) tốn hơn char-count nhiều bậc, trong khi giá trị chỉ dùng để so sánh với 1 ngưỡng (sai số chấp nhận được nếu có backstop).
- **Rough estimate gây bug thật** — 2 case cụ thể:
  - `should_defer_preflight_to_real_usage` (3304-3369): rough có thể **overestimate 2-3x** vì (a) CJK tính ~1.7x chi phí thật theo o200k, (b) Responses-mode reasoning replay blob tính nhiều lần chi phí billed thật → sessions "nặng" bị nén ở 35-55% của window thật, mỗi lần stall vài phút và MẤT DỮ LIỆU không cần thiết. Giải pháp: chiếu (project) real usage từ cặp (rough, real) đồng bộ lần cuối `projected_real = last_real + (rough_now - rough_at_last_real)` — với script non-ASCII không phải CJK (Cyrillic, Greek, Thai, Arabic — chars/4 nhưng thực tế ~2-3 chars/token trên o200k) thì projection này **KHÔNG còn là upper bound chặt** (comment thừa nhận rõ, hướng lỗi giống **#62605**), rủi ro còn lại được chặn bởi 2 backstop: real reading vượt threshold tự clear baseline, và error handler context-overflow của provider tự nén reactive.
  - `_estimate_message_tokens_without_images` bị double-site bug **#73298**: dòng 1350 và 1471 đều tham chiếu cùng issue — một walk khác (budget walk cho tail) đã "silently shrank the surviving tail" vì tính sai chi phí base64 envelope; phải fix ở 2 chỗ riêng vì logic ước lượng bị duplicate.
  - **#55546** (`model_metadata.py:1789`) — lỗi output-cap (`max_tokens` range 65536 của DashScope/Qwen) bị NHẦM LÀ context-overflow → route vào compression loop, compressor gửi lại request với CÙNG max_tokens quá lớn → provider từ chối GIỐNG NHAU → "death-loop" tới khi "cannot compress further". Fix: heuristic phân loại lỗi output-cap khác lỗi input-overflow bằng cách xem lỗi có nói về "INPUT/prompt/context window" hay chỉ về "max_tokens cap/range/limit".

### 2.8. Toàn bộ issue/PR xuất hiện + bài học 1 dòng

| # | File:line (đại diện) | Bài học |
|---|---|---|
| #10896 | context_compressor.py:5971 | Boundary-align lùi có thể kéo lùi quá phạm vi → dùng min() để chặn |
| #11475, #14521 | :337, :7728 | Model có thể lẫn user input cũ trong summary làm input của nó — phải tách rõ |
| #11529 | :3401,3429,3490 | Freeze-loop kinh điển: lỗi LLM phụ → không cooldown → nén lặp mỗi turn |
| #11762 | :1579 | Loop quan sát được khi thiếu 1 guard cụ thể (protect boundary) |
| #11914, #11978 | :4879,4927 | Content rỗng từ proxy 200 OK phải coi là lỗi, không lưu summary rỗng |
| #11996 | :495,5759,5796 | protect_first_n không decay → head phình vô hạn qua session dài |
| #14665 | :1239 | Field đọc sai gây "bogus attachment sends" turn kế tiếp |
| #14690 | :2226,2947 | Floor threshold = cả window → nén không bao giờ chạy, provider từ chối trước |
| #14694 | :2841,2862,3502 | Anti-thrash backoff phải có recovery window, không vĩnh viễn |
| #14695 | :3246 | Sàn không nén được (system+tools) khiến đo "%tiết kiệm" sai lý thuyết |
| #15779 | model_metadata.py:2785 | (context length resolution edge case, không đọc sâu) |
| #18458 | :2718(area) model_metadata | Stream đóng giữa dòng (httpcore) coi như timeout, không phải lỗi vĩnh viễn |
| #22244 | :2718 area | JSON decode lỗi (502 HTML) coi như transient, retry 1 lần trên main model |
| #22523 | :5985,6030,6249 | Nhiều anchor kéo cut_idx lùi phải monotonic, tránh forward push chồng chéo |
| #23767 | :2820 | Model mới sau switch cần gửi field mới ngay lần đầu, không đợi |
| #23975 | :4843,4927 | Nén phải atomic — user message giữa lúc gọi LLM phụ không được abort nó |
| #25585, #29559 | :3198,4517(area),7107,5080 | Lỗi network/streaming: abort giữ session nguyên vẹn > phá middle lấy placeholder |
| #26193 | context_references.py:21 | Plugin API riêng cho @file/@diff — KHÔNG liên quan compaction (context injection) |
| #26981 | conversation_compression.py:1982,3281 | Snapshot cũ tích lũy nếu không dọn |
| #28053 | :1432 | (tham chiếu, không đọc sâu — liên quan budget walk) |
| #29824 | :5866,5913,5957,6234 | Reply cuối bị cuốn vào block compaction → anchor "last assistant" bắt buộc |
| #32106 | nhiều nơi (712,1871,3686,3734,3808,4275,4299,4535,4902) | "Ghost-skill defense" — tóm tắt paraphrase mất chỉ dẫn reload skill |
| #32221 | :2146,2179,3099,3120 | Deferred resolve trong __init__ để tránh side-effect sớm |
| #33256 | :338,7730 | Model có thể "trả lời như chính nó" đoạn văn summary — phải rào rõ |
| #35344 | :495,624,5098 | Prefix cũ có thể "kế thừa" vào lineage resumed — không hợp lệ luôn |
| #36718 | :2826,3252,3354 | Verdict hiệu quả PHẢI đo trên real usage, không đo trên rough (2 phép đo khác nhau/turn) |
| #36801 | conversation_compression.py:2316 | Route compaction đến app server đúng — không lẫn thread khác |
| #38364,#38788,#41607,#42812 | :599,2279 | Lịch sử "carveout era" — fix cũ chỉ clear 1 field, chưa đủ |
| #38763 | conversation_compression.py nhiều | `compression.in_place` default True — bỏ session rotation |
| #40803 | :6191,7123,7211,7348 | Transcript ngắn không có "middle" hợp lý → vòng lặp nén vô ích |
| #43547 | :2795,2826,2959,3065 | max_tokens reserve phải trừ khỏi effective window, không tính full window |
| #44166 | :717 | Check-side và write-side của 1 invariant không được lệch nhau |
| #44439 | :1769 | External engine tự quản policy nén — built-in không can thiệp |
| #46620 | model_metadata.py:1197 | Timeout connect/read ngắn cho host không ping được |
| #47202 | conversation_compression.py:3513,3539 | Flush là DURABLE append vào parent transcript |
| #47274 | :7290,7591 | Multi-fossil scan tương tác với việc "unwrap" nội dung cũ |
| #48013 | conversation_compression.py:4211 | Path nhiều-ảnh 2000px riêng |
| #49874 | conversation_compression.py:2296 | compression_deferred phải thấy field idempotent |
| #50372 | model_metadata.py:3341 | String immutable → value-equality theo id() an toàn |
| #51800 | :1401 | Chỉ tính token phần reasoning TEXT thật, không tính padding |
| #52160, #58753 | :7651,7653 | Guard "zero-user-turn" chỉ fire đúng 1 hướng |
| #54923 | :2392,2472,3150,3518 | Restart KHÔNG được tự tháo 1 guard đã trip trước đó |
| #55546 | model_metadata.py:1789 | Output-cap error bị nhầm context-overflow → death-loop |
| #55572 | :1345,1440 | Session 214 turn giữ 115K token (27%) ở 1 field cụ thể — đo thực nghiệm |
| #57491 | :203,253,6983,7856 | Copy sang child session phải strip marker persistence ở MỌI copy site |
| #57682 | :7921 | Output model có thể lẫn vào "user statements" |
| #57835 | :7240,7248,7327,7354,7502 | Rehydrated state từ session khác bị nhầm cross-session leakage |
| #58630, #69853 | conversation_compression.py:2294 | Stale lock-skip signal từ giá trị cũ |
| #59496 | :7347 | Guard không log ồn ào trên input rỗng |
| #60451 | :1213,1221,2547,2557,3152 | Feasibility skip TRƯỚC gọi LLM khi middle quá nhỏ để đáng nén |
| #61932 | :1160,1221,3594,3625,3782,3808 | Protected tail bị pressure demote — vòng "dead-end" giữa tail đầy và middle rỗng |
| #62452 | :2705,5051 | Cooldown ladder dùng chung logic ở 2 call site, tránh duplicate |
| #62605 | :3325 | Rough char/4 KHÔNG phải upper bound chặt cho non-CJK non-ASCII |
| #63122 | model_metadata.py:2996 | Local endpoint: ưu tiên Modelfile num_ctx hơn GGUF training max (tránh false-safe window) |
| #64650 | :6943,7270 | "Zero-user provenance" cưỡi trên handoff mới nhất |
| #65848 | :569 | Class prefix cũ tương tự #69619 (Jul 2026) |
| #67422 | :1761 | Đổi threshold phải trigger recompute _effective_threshold_percent |
| #68196 | :2865,3516 | Flush skip theo identity — durable prefix boundary |
| #69291 | :6062 | Slot bug class cụ thể trong tool-group split |
| #69292 | conversation_compression.py:3284 | Scaffolding tail giữ nguyên để không phá zero-user provenance |
| #69619 | :536,538,539 | Prefix cũ có section headers đã bị xoá — tương thích ngược |
| #69840, #69870 | conversation_compression.py:1193-1224 | Lock-skip signal type-pinned, tránh type-ahead incident |
| #69872 | :3149,3517 | Tripped counter persist qua restart — bắt đầu lại 1 window đầy |
| #70782 | :7884 | Trim lifecycle rate-limited, an toàn no-op ở chỗ khác |
| #71058 | :253,276,384(area),1384,1442,6169,7862 | Stale replay field từ turn assistant cũ phải bị strip |
| #71569 | conversation_compression.py:479,2655,2827,635 | Lock release logic transplant từ 1 PR ngoài, ghi rõ tác giả |
| #72626 | prompt_caching.py:239,272 | Failover đổi provider phải strip rồi re-apply cache marker khác policy |
| #73298 | :1350,1471,1399 | Base64 envelope tính sai token ở 2 site riêng biệt — bug lặp lại |
| #73624 | :1365,1449,3634,6169 | Charge stale thinking sai làm tail budget bị "ăn" bởi byte không lên wire |
| #74136 | :80,2651 | Pre-agent hygiene pass tách biệt khỏi in-conversation compressor |
| #75170 | :3088,6588 | Sibling call site cùng 1 pop-cursor logic |
| #75316 | conversation_compression.py:2454,2562,3577 | Watermark ranh giới ghi DURABLE, tránh ghi đè lẫn |
| #75588 | :5451 | IndexError guard cho input rỗng |
| #76354 | conversation_compression.py:28,462+ (F1-F6) | Thread-safety contract cho extension point khi nén chạy trên pooled thread |
| #76577 | context_references.py:664 | Tái dùng máy credential_files có sẵn |
| #76905 | :7881 | Trim lifecycle của gateway/TUI khác trim trong-conversation |
| #79017 | prompt_cache_scope.py:8,34 | Cache scope theo session vật lý bị rotation phá — cần lineage root |
| #79161 | prompt_cache_scope.py:5,17,26 | Cache scope ban đầu derive từ session vật lý — đúng cho isolation, sai cho rotation |
| #79193 | prompt_cache_scope.py:13 | Lineage walk fork-aware được hardened |
| #79278 | :5660 | In-flight tool chain protection khi đang nén |
| #80622 | :505,7944,7969,8015 | Handoff phải "actionable", không chỉ reference — sole-handoff case |
| #81867 | prompt_cache_boundary.py:1, prompt_caching.py:266 | Builder khai báo prefix ổn định cho skill/webhook/cron cache split |
| #82001 | conversation_compression.py:1224 | Recovery không thấy direct child đúng hình dạng bị bỏ qua |
| #82777 | native_compaction.py:277 | Phân biệt reject THẬT vs lỗi 5xx/timeout echo field name |
| #83248 | :7245,7327 | Không clear cache dựa trên miss bị bound bởi compress_end |
| #83339 | conversation_compression.py:3382 | In-place compaction commit TRONG method, khác luồng khác |
| #84482, #8731 | model_metadata.py:2771,2772 | models.dev sai context cho 1 số model/custom — cần override |
| #84718 | conversation_compression.py:2006,3267 | Retention-parity: compaction re-inject todo list |
| #84733 | prompt_caching.py:126,140,156 | TTL 1h clamp về 5m cho Qwen/Alibaba — tránh false expectation |
| #86972 | :81,2651 | Hygiene timeout không được block compressor trong-conversation |
| #88197 | conversation_compression.py:3549 | Retry tới khi provider reject hẳn, không tự bỏ giữa đường |
| #88568 | :2525,record_rejected_compaction | Compaction bị reject trước commit vẫn phải tính là 1 strike |
| kilocode#9434 | :1673,1682,7821 | Port trực tiếp từ project khác (Kilo-Org) — kỹ thuật ảnh trong OpenAI-style content |

Ghi chú: nhiều số hiệu (#15779, #28053, #46620, #48013, #50372, #63122, #64650, #69291...) chỉ xuất hiện 1 lần trong comment ngắn, không đọc sâu logic đi kèm — liệt kê theo đúng dòng grep, không suy diễn thêm.

---

## 3. Bài học rút ra (tổng hợp, không lặp mục 2)

1. **Tách "quyết định" khỏi "số liệu thật"**: mọi ngưỡng nén dựa trên estimate rẻ, nhưng verdict "có hiệu quả không" luôn dựa trên số thật từ provider. Nếu trộn 2 nguồn số vào 1 chỗ quyết định (như từng làm, #36718), thrash-guard tự phá.
2. **Cooldown + anti-thrash PHẢI có đường thoát theo thời gian, không theo giá trị**: một guard trip vĩnh viễn (không recovery window) = tính năng tự vô hiệu hoá — đây là failure mode xuất hiện lặp lại nhiều lần trong lịch sử Hermes (#11529, #14694, #54923, #69872) đủ để coi là nguyên tắc thiết kế, không phải patch vụn.
3. **Mọi rewrite nội dung đã gửi lên wire = phá cache prefix** — dedup/prune/compaction đều phải qua "cổng lợi ích" (min reclaim, rearm runway) trước khi commit, vì cái giá không phải "tốn CPU" mà là "mất cache toàn bộ phần sau điểm sửa".
4. **Danh tính logic (lineage) khác danh tính vật lý (session_id)** khi có rotation/fork — cache key, cooldown, mọi state theo-session phải neo vào cái ĐÚNG, và 2 khái niệm (lineage root vs conversation root) không được gộp làm 1 dù trông giống nhau (#79161 vs #79017 vs Portal-attribution).
5. **Docstring có thể trôi khỏi hành vi thật** (mục 2.1, "10%" vs nhị phân threshold) — code review không nên tin docstring khi có mâu thuẫn với logic; luôn đọc implementation.
6. **Ước lượng rough phải có backstop 2 chiều**: (a) không bao giờ để rough estimate là NGUỒN SỰ THẬT duy nhất kích hoạt hành động không hồi phục (mất context), (b) khi rough sai theo hướng nguy hiểm hơn (under-estimate), phải có phản ứng reactive (provider context-overflow handler) làm lưới an toàn cuối.
7. **Nén không nên là "tất cả hoặc không"** — pha rẻ (dedup, prune xác định) tách khỏi pha đắt (LLM summarize) cho phép chạy thường xuyên hơn với rủi ro thấp hơn, đúng lúc pha đắt chưa cần thiết.

---

## 4. Cái gì port được sang `apps/api/src/agent/context.py` và `prompt/contract.py`

Bối cảnh: `context.py` hiện tại (336 dòng) CHỈ có ladder xác định (rung 1-2-3 của docstring riêng nó) — không LLM summarize, không prune tool-result tách biệt khỏi ladder, không cache breakpoint, estimate token bằng `char/3` không hồi chỉnh bởi usage thật. `prompt/contract.py` có `cache_key()` (logic, không phải wire cache_control) — không thấy `cache_control` nào thực sự set trong `core/llm/*` (đã kiểm bằng grep) → hiện là 1 hàm CHƯA ĐƯỢC DÙNG để đặt breakpoint thật.

**Port có giá trị, xếp theo độ ưu tiên:**

1. **Khái niệm "real usage ghi đè rough estimate"** (từ `update_from_response`, `_pending_request_rough_tokens`, `last_real_prompt_tokens`) — `context.py` hiện KHÔNG có đường hồi tiếp từ response thật về `estimate_tokens`. Nếu route LLM (proxy OpenAI-compatible, theo CLAUDE.md) trả `usage.prompt_tokens`, nên thêm 1 hàm kiểu `record_real_usage(prompt_tokens: int) -> None` cập nhật baseline, ít nhất để LOG độ lệch giữa `estimate_tokens` (char/3) và thực tế — bước đầu để phát hiện nếu char/3 sai lệch nặng cho tiếng Việt có dấu (đúng như comment dòng 39-42 của context.py đã lo).
2. **`resolve_model_threshold` (longest-substring-wins per-model override)** — nếu Stock_Massive sau này hỗ trợ nhiều model route (đã có `llm_model_*` theo CLAUDE.md Eval gate), pattern "key dài nhất thắng" là cách gọn để override `ContextBudget.max_tokens`/`summary_threshold_turns` theo model cụ thể mà không if/elif chuỗi.
3. **Ý tưởng "decay protect_first_n sau lần nén đầu" (#11996)** — nếu `context.py` thêm rung 3 thật (LLM summarize, hiện chỉ *report* `summary_needed`), áp dụng ngay từ đầu: đừng bảo vệ cố định N turn đầu qua MỌI lần tóm tắt — turn đầu chỉ cần bảo vệ tới lần đầu bị gói vào summary.
4. **Tách "prune xác định" (rẻ) khỏi "summarize" (đắt, cần LLM)** — `context.py` đã có sẵn cấu trúc này ở rung 2 vs rung 3 (`_reductions`, dòng 256): rung 2 (collapse tool result → 1 dòng) tương đương `prune_tool_results_only` của Hermes, đã tồn tại. Bài học port được KHÔNG phải thêm code mà là: **gate rung 2 bằng ngưỡng RIÊNG, thấp hơn** ngưỡng rung 3 (`summary_threshold_turns`) — hiện `_reductions` chạy CẢ rung 2 và rung 3 trong CÙNG 1 lần gọi `build_messages` khi vượt `max_tokens`, không có cơ chế "prune sớm, trước khi cần summarize" độc lập theo lịch riêng. Nếu muốn giảm tần suất gọi LLM summarize, thêm 1 preflight rẻ kiểu `prune_tool_results_only` chạy MỖI turn (không cần vượt `max_tokens`) để giữ turn dưới ngưỡng summarize lâu hơn.
5. **Anti-thrash / cooldown khi rung 3 (summarize) được implement thật** — hiện `context.py` chỉ *report* `summary_needed=True`, chưa gọi LLM. Khi implement, PHẢI port nguyên khái niệm cooldown + recovery-window (không port code, port thiết kế): (a) lỗi LLM summary → cooldown có bậc thang, không nén lại ngay; (b) verdict "hiệu quả" đo trên optimize thật (turn có xuống dưới ngưỡng không), không đo % giảm số message.
6. **`cache_key()` trong `contract.py`** — đã có sẵn, ĐÚNG design (model + prompt_version + hash + tool_catalog_version), nhưng CHƯA GẮN vào bất cứ cache_control thật nào. Nếu route LLM hỗ trợ Anthropic-style `cache_control` (cần xác nhận — proxy hiện tại là "OpenAI-compatible" theo CLAUDE.md, CHƯA rõ có forward `cache_control` hay không), port ý tưởng `prefix()` (đã có, trả phần ổn định) ghép với logic "đặt marker ở CUỐI phần ổn định + N message cuối" từ `apply_anthropic_cache_control` — vì `prefix()` hiện chỉ trả text, chưa có ai gọi nó để đặt breakpoint trên message thật.
7. **Cảnh giác `#73298`-class bug (double-site token miscount)** — bất cứ khi nào Stock_Massive thêm 1 nhánh tính token thứ 2 (ví dụ ước lượng riêng cho ảnh/base64 nếu sau này hỗ trợ đa phương tiện), PHẢI dùng lại đúng 1 hàm `estimate_tokens`, không viết công thức tính char riêng ở chỗ khác — bài học #73298 là do 2 nơi tính base64 khác công thức.

## 5. Cái gì KHÔNG nên port và vì sao

1. **Toàn bộ `native_compaction.py` (OpenAI Responses native compaction)** — chỉ áp dụng cho gpt-5.6 family qua route TRỰC TIẾP OpenAI. Route của Stock_Massive là 1 proxy OpenAI-compatible (theo CLAUDE.md + memory `llm-route-ccs-codex-luna`) — không phải `api.openai.com` trực tiếp, và model cụ thể chưa xác nhận support field `context_management`. Port cơ chế này vào 1 dự án không kiểm soát được route thật là rủi ro (silent stall 90s×3 nếu model không hỗ trợ, theo đúng cảnh báo trong docstring Hermes).
2. **`prompt_cache_scope.py` (lineage root theo session rotation)** — chỉ có nghĩa khi hệ thống CÓ khái niệm "rotate session_id giữa hội thoại". Stock_Massive's `Transcript`/`ContextBudget` không rotate gì — 1 thread = 1 identity ổn định suốt đời (đúng như Hermes tự nhận `compression.in_place=True` giờ là default vì nó "eliminates the session-rotation bug cluster" — nghĩa là Hermes CHÍNH HỌ cũng đang rời xa design này). Port design đã bị chính upstream deprecate là ngược hướng.
3. **`prompt_cache_boundary.py` (registry stable-prefix cho skill/webhook/cron)** — giải quyết vấn đề của Hermes: skill có body lớn ghép cùng payload biến đổi trong 1 message string. Stock_Massive's Contract (`prefix()` + `render()`) đã tách RÕ phần tĩnh/biến đổi bằng 2 THAM SỐ TYPED (không phải 1 string ghép), theo đúng nguyên tắc ADR-0015 "Nothing but five typed values can reach the prompt" — vấn đề mà registry Hermes giải quyết (không biết đâu là boundary trong 1 string) KHÔNG TỒN TẠI ở đây. Port vào sẽ là giải pháp cho vấn đề không có.
4. **7 tầng fallback lồng nhau của `_generate_summary`** (model-not-found → timeout → JSON-decode → streaming-closed → unknown-error → main-model-retry → cooldown ladder) — độ phức tạp này phản ánh việc Hermes phải chạy trên HÀNG CHỤC provider khác nhau (Alibaba, DashScope, OpenRouter, local GGUF, NVIDIA NIM...). Stock_Massive dùng 1 proxy LLM cố định — port nguyên khối phân loại lỗi 7 tầng là over-engineering; chỉ cần 2-3 tầng (transient retry ngắn, cooldown dài nếu cấu hình sai) là đủ cho 1 route.
5. **Ghost-skill defense (#32106, xuất hiện >10 lần)** — đặc thù hệ thống "skill" runtime-loadable của Hermes (skill_view tool). Stock_Massive không có khái niệm skill động nạp giữa hội thoại — không có gì để port.
6. **`trajectory_compressor.py` (root, 1598 dòng)** — xác nhận qua đọc header: đây là tool OFFLINE xử lý JSONL training data (post-process trajectory cho fine-tuning), không phải runtime context management. Không liên quan.
7. **`context_references.py` (plugin `@file`/`@diff`/`@url` autocomplete)** — là hệ thống context INJECTION (người dùng gõ `@file:x` để nhúng nội dung), khác hoàn toàn compaction/trimming. Không liên quan tới câu hỏi context management của nhiệm vụ này.
8. **Anti-thrash dựa trên "docstring 10%"** — như đã nói ở mục 2.1/3.5, ngay cả Hermes tự nó cũng không dùng đúng con số này (code thật là nhị phân). Không port literal "10%" — port Ý TƯỞNG (đo trên real usage, có strike counter, có recovery window).

## 6. Câu hỏi chưa giải quyết

1. Route LLM hiện tại của Stock_Massive (proxy OpenAI-compatible) có forward `cache_control`/`prompt_cache_key` xuống provider gốc không? Nếu route là Anthropic gốc phía sau, mục 4.6 (gắn cache_control cho `prefix()`) mới có giá trị thực; nếu route luộc qua 1 gateway không hỗ trợ, port sẽ là no-op.
2. `apps/api/src/agent/context.py` báo `summary_needed=True` nhưng ai/đâu THỰC SỰ gọi LLM để sinh summary và ghi `Transcript.summary`/`summarised_turns`? Không đọc phần harness gọi `build_messages` (ngoài phạm vi file được giao) — không rõ rung 3 đã có nửa sau (persist summary) chưa, ảnh hưởng trực tiếp tới mục 4.5.
3. `MAX_ITERATIONS_SUMMARY_REQUEST` (context_compressor.py:189) và cơ chế "iterative summary update" (tóm tắt lại tóm tắt cũ) không đọc sâu — có thể liên quan tới câu hỏi 4 (port ý tưởng "không tóm tắt lại 1 summary đã có" — hiện `context.py` đã tự nhiên tránh việc này qua `covered = summarised_turns`, nhưng chưa xác nhận Hermes có invariant tương tự hay khác).
4. Docs `context-compression-and-caching.md` (qua fetch tóm tắt) nói KHÔNG có issue/PR nào trong docs — nghĩa là toàn bộ bảng issue ở mục 2.8 chỉ đến từ code comment, chưa đối chiếu với CHANGELOG/git log thật của Hermes để xác nhận ngày/context đầy đủ của từng issue (không có quyền truy cập GitHub Issues thật của repo trong nhiệm vụ này).
5. `_MAX_TAIL_MESSAGE_FLOOR` (dòng 1211) — giá trị số cụ thể không được đọc trong phiên này (chỉ thấy tên hằng), cần xác nhận nếu có ai muốn tính chính xác "protect_last_n=20 bị cap xuống bao nhiêu".
