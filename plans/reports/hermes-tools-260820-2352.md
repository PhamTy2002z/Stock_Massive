# Kiến trúc tool của Hermes Agent (NousResearch/hermes-agent) — đọc code thật

Nguồn: clone sparse tại `/private/tmp/.../scratchpad/hermes-agent` (đủ `agent/`, `tools/`, root `.py`, không cần fetch thêm). Toàn bộ trích dẫn dưới dạng `path:line` theo repo clone đó. Không sửa code Hermes, không chạy test.

## 1. Kiến trúc tool tổng quan

Hermes có 4 lớp tách biệt rõ:

1. **`tools/registry.py`** — nguồn sự thật duy nhất cho mọi tool: tên, schema, handler, toolset, check_fn, giới hạn kích thước, override policy cho plugin. Tool tự đăng ký bằng `registry.register(...)` ở module level; `tools/registry.py::discover_builtin_tools` quét AST (`registry.py:96-145`) để tìm file nào gọi `registry.register(` ở top-level, cache verdict theo `(mtime_ns, size)` để tránh quét lại (~145ms/100 file nếu cold).
2. **`toolsets.py`** — nhóm tool thành "toolset" (vd `web`, `terminal`, `file`, `coding`…), có thể compose lồng nhau qua `includes`. `_HERMES_CORE_TOOLS` (`toolsets.py:29-92`) là danh sách tool luôn hiện diện trên mọi client CLI/messaging.
3. **`model_tools.py::get_tool_definitions`** — điểm duy nhất build danh sách schema cuối cùng gửi cho model: resolve toolset → hỏi registry lấy schema (chỉ tool có `check_fn()` pass) → rebuild schema động cho vài tool đặc biệt (execute_code, discord) → sanitize schema cho backend → (tuỳ chọn) áp Tool Search progressive disclosure. Có cache theo `(scope, toolsets, registry generation, config fingerprint, ...)` LRU 
   bound để tránh phình bộ nhớ trên gateway sống lâu (`model_tools.py:398-407`, issue #17335, #19251).
4. **`agent/tool_executor.py` + `agent/tool_dispatch_helpers.py`** — dispatch thật: parse args, guardrail, lập kế hoạch song song/tuần tự, chạy qua `DaemonThreadPoolExecutor`, chuẩn hoá kết quả, ghi trace.

Không có khái niệm "toolset phân phối theo model" trong runtime sống — điều duy nhất khoá theo **model identity** là schema sanitizer (Gemini/Moonshot/llama.cpp, mục 4). `toolset_distributions.py` (100% xác nhận bằng `grep -rln toolset_distributions` chỉ ra 2 file: chính nó và `batch_runner.py`) **chỉ dùng để sinh dữ liệu training** (random sample toolset theo % xác suất cho mỗi prompt trong batch run) — KHÔNG chạy trong agent loop thật. Đây là điểm dễ hiểu lầm nếu chỉ đọc tên file.

## 2. Từng cơ chế, chi tiết + số hiệu sự cố

### 2.1. Metadata một tool khi đăng ký (Q1)

`ToolEntry.__slots__` (`tools/registry.py:206-232`):
```
name, toolset, schema, handler, check_fn, requires_env, is_async,
description, emoji, max_result_size_chars, dynamic_schema_overrides
```
`register()` (`tools/registry.py:737-857`) nhận đủ các field trên qua kwargs, cộng thêm `override: bool` và `scope: Optional[str]` (cho MCP/plugin). Logic quan trọng:
- **Chống shadow tool ẩn ý**: nếu tool mới trùng tên nhưng khác `toolset` với tool cũ, đăng ký bị **REJECT** trừ khi `override=True` — và nếu caller là plugin, còn cần `allow_tool_override` opt-in ở `config.yaml` (`registry.py:800-855`, `PermissionError` khi vi phạm).
- `dynamic_schema_overrides`: callable không tham số trả `dict`, được gọi lại **mỗi lần** `get_definitions()` — dùng khi mô tả schema phải phản ánh config runtime (ví dụ mô tả `delegate_task` phải in đúng `max_concurrent_children` hiện tại, không phải số cứng) (`registry.py:222-231`, `1018-1062`).
- `check_fn` kết quả cache TTL 30s (`_check_fn_cached`, dùng ở `get_definitions`) để không probe Docker/Playwright mỗi lần build schema — chỉ chấp nhận rớt tool tạm thời do "issue #21658/#5304: probe transient-failure suppression" (`registry.py:256-266`): một `docker version` timeout 1 lần không được phép âm thầm rút cả toolset `terminal+file` khỏi 1 subagent.
- `get_max_result_size(name, default)` (`registry.py:1148-1156`) trả `max_result_size_chars` đã đăng ký, hoặc default, hoặc `DEFAULT_RESULT_SIZE_CHARS` — nguồn cấp 3 (registry) trong resolve chain ở mục 2.3.
- Ownership/plugin: `deregister()` phân biệt "cùng plugin" theo **package root** (`hermes_plugins.{name}`), không so chuỗi module chính xác — sửa vì review thấy submodule của cùng plugin không được coi là "khác chủ" (`registry.py:895-910`, PR #55840).

**Toolset** (`toolsets.py`): dict `{description, tools, includes}`, `resolve_toolset()` (`toolsets.py:769-878`) đệ quy include, có memo theo `(name, include_registry, registry_id, generation)` giới hạn 256 entry. `bundle_non_core_tools()` (`toolsets.py:728-747`) tách phần tool "riêng của bundle" khỏi core — cần cho việc disable một toolset kiểu `hermes-*` (platform bundle) mà không vô tình xoá core tool dùng chung (issue #33924, #57315 — bug thật: disable `hermes-cli` từng làm rỗng tool list vì core tool bị trừ hai lần).

**"Phân phối theo model"**: Không tồn tại theo nghĩa runtime. Thứ **có** khoá theo model là:
- `model_tools.py::_compute_tool_definitions` gọi sanitizer theo backend (không theo "model" cụ thể mà theo **transport/provider** đang dùng) — xem mục 2.4.
- `toolset_distributions.py::DISTRIBUTIONS` (`toolset_distributions.py:27-120`) là bộ % xác suất **chọn toolset khi sinh dữ liệu huấn luyện** (`image_gen`, `research`, `science`, `development`, `safe`, `balanced`, `minimal`…) — dùng bởi `batch_runner.py`, không đụng runtime agent thật.

### 2.2. Rules engine song song hoá (Q2)

File: `agent/tool_dispatch_helpers.py`. Không phải "song song cả batch hoặc không" nữa — có **planner phân đoạn** `_plan_tool_batch_segments()` (`tool_dispatch_helpers.py:117-235`) chia 1 batch tool-call thành các segment `("parallel", [...])` / `("sequential", [...])` theo đúng thứ tự model phát ra (không bao giờ đảo thứ tự).

Quy tắc từng tool trong batch, theo thứ tự áp dụng:

1. `_NEVER_PARALLEL_TOOLS = frozenset({"clarify"})` (`:45`) — tool tương tác người dùng, luôn tạo sequential barrier. Lý do: hỏi 2 câu clarify song song sẽ đá lẫn UI.
2. Args không parse được / không phải `dict` → barrier tuần tự (an toàn khi không hiểu được scope).
3. **`_PATH_SCOPED_TOOLS`** = `_PATH_SCOPED_READERS {"read_file", "search_files"}` ∪ `_PATH_SCOPED_WRITERS {"write_file", "patch"}` (`:69-73`): các tool file được xét theo **overlap đường dẫn**, có vai trò reader/writer:
   - reader↔reader overlap → **không xung đột** (đọc đồng thời commut), giữ song song.
   - bất kỳ overlap có **writer** tham gia (writer↔writer hoặc writer↔reader) → đóng run hiện tại, call xung đột bắt đầu run MỚI *sau* khi run cũ hoàn tất — chặn race "model batch `patch` + `read_file` cùng file trong 1 lượt" (`:196-217`).
   - `search_files` không có `path` explicit → mặc định reserve `"."` làm reader (không rơi về sequential, giữ song song cho search trần) (`_extract_parallel_scope_paths`, `:294-300`).
   - Với `patch(mode="patch")` (V4A patch), scope KHÔNG lấy từ `path=` (có thể là decoy) mà parse header `*** Update/Add/Delete/Move File:` trong nội dung patch (`:279-289`, `_extract_file_mutation_targets` `:409-454`).
   - Path canonical hoá qua `os.path.realpath` + `normcase` (Windows-safe) trước khi so overlap theo tiền tố `Path.parts` (`_paths_overlap`, `:333-346`).
4. **`_PARALLEL_SAFE_TOOLS`** — frozenset 12 tool đọc-thuần, không có state mutable chung (`:48-61`):
   ```
   ha_get_state, ha_list_entities, ha_list_services, image_generate,
   read_file, search_files, session_search, skill_view, skills_list,
   vision_analyze, web_extract, web_search
   ```
   (chú ý: `read_file`/`search_files` xuất hiện ở CẢ path-scoped VÀ parallel-safe — path-scoped check chạy trước và có nhánh riêng, safe-set chỉ áp dụng cho tool không cần scope path).
5. Tool MCP: `_is_mcp_tool_parallel_safe()` hỏi `tools.mcp_tool.is_mcp_tool_parallel_safe()` — server MCP phải khai báo opt-in "parallel tool calls enabled" mới được coi an toàn (`:104-114`).
6. Bất cứ tool nào không khớp 4 nhóm trên → sequential barrier (an toàn theo default — "unknown = không song song").

Sau khi phân đoạn: run song song có < 2 call bị hạ về sequential (không có lợi ích concurrency); 2 segment sequential liền kề bị merge (`:227-235`). `_should_parallelize_tool_batch()` (`:238-248`) chỉ còn là view mỏng cho case đồng nhất (đúng 1 segment và segment đó là "parallel") — dùng cho test cũ.

**Thực thi thật**: `agent/tool_executor.py::execute_tool_calls_concurrent` dùng `DaemonThreadPoolExecutor(max_workers=min(len(calls), 8))` (`tool_executor.py:118, 257-266, 1479-1486`) — **thread pool**, không phải `asyncio.gather`. `max_workers` bị siết thêm nếu batch có `image_generate` (giới hạn API ảnh riêng). Batch hỗn hợp (nhiều segment) chạy qua `execute_tool_calls_segmented` — mỗi segment tuần tự theo đúng thứ tự, segment "parallel" bên trong nó vẫn dùng thread pool.

Bên cạnh đó có **defense-in-depth** cho nội dung không tin cậy: `make_tool_result_message()` (`tool_dispatch_helpers.py:534-581`) bọc kết quả của `web_extract`, `web_search`, và mọi tool tiền tố `browser_`/`mcp_` trong khối `<untrusted_tool_result source="...">...</untrusted_tool_result>` (chỉ khi > 32 ký tự), có defang token delimiter lồng trong nội dung tấn công (`_neutralize_delimiters`, `:715-725`) để chống prompt injection kiểu "đóng sớm thẻ untrusted rồi viết chỉ dẫn giả". Ngoài ra phát hiện **upstream elision** (MCP server tự cắt dữ liệu và chỉ đánh dấu `"...N more items"` / `has_more:true` / `saved to sandbox`) và chèn cảnh báo "dữ liệu chưa đầy đủ" (`:615-676`) — nếu không, model tưởng danh sách nhìn thấy là toàn bộ.

### 2.3. Ngân sách output tool — 3 tầng chống overflow (Q3)

**Thứ tự resolve threshold** (`tools/budget_config.py::BudgetConfig.resolve_threshold`, `:82-112`):
```
pinned (PINNED_THRESHOLDS) > tool_overrides (config.yaml) >
mcp_ prefix cap (min(mcp_result_size, default_result_size)) >
registry per-tool (min(registry_value, default_result_size)) >
default_result_size
```
Ghi chú đúng theo yêu cầu task: thứ tự **là** `pinned > config > registry > default`, nhưng có một nhánh chèn giữa "config" và "registry": tool tiền tố `mcp_` luôn bị cap riêng (`DEFAULT_MCP_RESULT_SIZE_CHARS = 50_000`, nhỏ hơn default 100K) vì MCP server hay trả payload không phân trang 20-50K char không có entry registry để chặn (`:21-32`).

Ngưỡng cụ thể (`budget_config.py:9-36`):
- `PINNED_THRESHOLDS = {"read_file": inf}` — chống loop persist→read→persist vô hạn.
- `DEFAULT_RESULT_SIZE_CHARS = 100_000`
- `DEFAULT_TURN_BUDGET_CHARS = 200_000`
- `DEFAULT_PREVIEW_SIZE_CHARS = 1_500`
- `DEFAULT_MCP_RESULT_SIZE_CHARS = 50_000` — so sánh cạnh tranh: "OpenCode 50KB, pi 50KB, Claude Code 30K chars, Codex ~10K tokens" (comment `:22-31`).

**Scale theo context window** (`budget_for_context_window`, `:139-174`): `window_chars = context_length * 4` (4 char/token, thiên về under-estimate cho an toàn); `per_result = clamp(window_chars*0.15, [8_000, 100_000])`; `per_turn = clamp(window_chars*0.30, [16_000, 200_000])`. Lớn thì clamp về default cũ (không đổi hành vi model lớn), nhỏ thì scale xuống + floor — sửa bug thật (issue #23767): model 65K-token có thể tự overflow window chỉ bằng 1 turn_budget 200K-char (~50K token).

**3 tầng chống overflow** (`tools/tool_result_storage.py`, docstring `:1-43`):
1. **Per-tool cap tự thân** (trong chính handler, ví dụ `search_files` tự cắt trước khi return) — tầng duy nhất tool author kiểm soát.
2. **Per-result persistence** (`maybe_persist_tool_result`, `:314-396`): nếu `len(content) > threshold`, ghi full content ra `$HERMES_HOME/cache/spillover/{tool_use_id}.txt` (host-side LUÔN LUÔN, bất kể backend), trả về preview (cắt tại newline gần `preview_size`) + đường dẫn. Với backend remote (docker/ssh/modal/daytona), thử dịch path sang path nhìn thấy trong sandbox (`_sandbox_visible_spillover_path`, probe readability trước khi tin) — container cũ không có mount thì fallback ghi thẳng vào sandbox temp qua stdin (không qua argv, vì Linux `MAX_ARG_STRLEN` ~128KB làm heredoc-trong-argv chết với payload lớn, `:249-266`). Nếu cả 2 cách ghi đều fail → inline-truncate với cảnh báo "không lưu được".
3. **Per-turn aggregate budget** (`enforce_turn_budget`, `:399-449`): sau khi mọi tool result trong 1 turn gộp lại, nếu tổng > `turn_budget`, sort giảm dần theo size, spill từng cái (persist với `threshold=0` ép buộc) tới khi dưới ngân sách — bắt case "nhiều kết quả cỡ vừa cộng lại tràn context" mà layer 2 không bắt được (mỗi cái riêng lẻ dưới ngưỡng).

Ngoài ra còn `tools/tool_output_limits.py` — tầng RIÊNG, khác mục đích: giới hạn **truncate cứng** (không phải persist) cho terminal stdout (`max_bytes=50_000`) và pagination `read_file` (`max_lines=2000`, `max_line_length=2000`), port từ `anomalyco/opencode` PR #23770, đọc từ `config.yaml.tool_output`, cache process-lifetime.

### 2.4. Schema sanitize theo backend (Q4)

3 module riêng, mỗi module trả lời một lỗi HTTP 400 thật khác nhau:

**`tools/schema_sanitizer.py`** — universal, chạy cho MỌI backend qua `model_tools.py:598-600` (bọc try/except, log warning nếu fail, không chặn agent). Sửa các dạng schema mà **llama.cpp** (`json-schema-to-grammar`) từ chối:
> `"HTTP 400: Unable to generate parser for this template. Automatic parser generation failed: JSON schema conversion failed: Unrecognized schema: \"object\""` (docstring `:1-14`)

Cụ thể: `{"type":"object"}` không có `properties` → tự chèn `properties: {}` (`_sanitize_node`, `:527-529`); schema là string trần (`"object"`) do MCP server hỏng → convert thành dict; `"type": ["string","null"]` (array-type) → tách `type` đơn + `nullable: true`, hoặc `anyOf` nếu ≥2 non-null type (KHÔNG bỏ nhánh nào, port từ `anomalyco/opencode#31877`); `anyOf`/`oneOf` chỉ để cho phép null → collapse về nhánh non-null (Anthropic reject union-null ở input_schema); `default` cạnh `$ref` → strip (Fireworks/Kimi draft-07-strict báo `"keyword(s) ['default'] not allowed at the same level as $ref"`); combinator top-level (`allOf/anyOf/oneOf/enum/not`) → strip riêng cho OpenAI Codex backend (`chatgpt.com/backend-api/codex`) báo `"schema must have type 'object' and not have 'oneOf'/'anyOf'/'allOf'/'enum'/'not' at the top level"`. Cũng rename property key không khớp `^[a-zA-Z0-9_.-]{1,64}$` — Anthropic/Bedrock/Vertex/Azure reject key lạ (case thật: Cloudflare MCP có 61 key kiểu `issue_class~neq`).

Có 2 hàm **reactive** (chỉ chạy SAU khi provider đã 400 một lần, không chạy mặc định): `strip_pattern_and_format()` — bỏ `pattern`/`format` vì llama.cpp regex engine chỉ hiểu ECMAScript con (không hiểu `\d`, `\w`, `\s`); `strip_slash_enum()` — bỏ enum chứa `/` vì xAI `/v1/responses` compile-grammar 400 với message `"Invalid arguments passed to the model"` khi enum có `Qwen/Qwen3.5-0.8B` kiểu HuggingFace ID.

**`agent/gemini_schema.py`** — allowlist cứng 27 key Gemini `Schema` object chấp nhận (`_GEMINI_SCHEMA_ALLOWED_KEYS`, `:11-34`), bỏ mọi key khác (`$schema`, `additionalProperties`...). Ép `enum` values thành string dù `type` là `integer/number/boolean` (Gemini enum bắt buộc string). Lọc `required` chỉ giữ tên có trong `properties` cùng node — nếu không Gemini 400 `"...items.required[0]: property is not defined"` (port từ `Kilo-Org/kilocode#11955`) — và **một tool schema lỗi làm chết cả request** (không chỉ tool đó).

**`agent/moonshot_schema.py`** — 3 luật bắt buộc của Moonshot/Kimi (docstring `:9-24`, tham chiếu `forum.moonshot.ai/.../102` và `MoonshotAI/kimi-cli#1595`):
1. Property schema PHẢI có `type` (JSON Schema thường cho phép bỏ) — thiếu thì Moonshot 400.
2. `anyOf` có `type` ở cả parent và children → lỗi `"type should be defined in anyOf items instead of the parent schema"` — nên pop `type` khỏi parent, đồng thời Moonshot còn reject nhánh `null` trong `anyOf` (`"enum value (<nil>) does not match any type in [string]"`) nên collapse về nhánh non-null.
3. Object schema PHẢI có `required` (dù rỗng `[]`) — thiếu thì lỗi `"required must be an array"`.

Wiring điểm gọi thật: `agent/transports/chat_completions.py:545,761` — `if is_moonshot_model(model): tools = sanitize_moonshot_tools(tools)`. `is_moonshot_model()` nhận diện qua **tên model string** (đuôi `kimi-*`, `k3*`, chứa `moonshot`), không quan tâm aggregator prefix (OpenRouter/Nous route tới Moonshot vẫn nhận diện đúng) — đây chính là "phân phối schema theo model" thật sự trong Hermes, không phải toolset.

### 2.5. Progressive tool disclosure — Tool Search (Q5)

`tools/tool_search.py`. Bật khi (`should_activate`, `:288-306`): config không phải `"off"` **và** tồn tại ≥1 "deferrable tool" (MCP hoặc plugin, không phải core). Điều kiện quan trọng (thiết kế tháng 7/2026, "tiered disclosure"): **activation không còn phụ thuộc kích thước** — bất kỳ tool MCP/plugin nào tồn tại là bridge kích hoạt ngay; threshold chỉ còn quyết định **listing budget** (mức độ chi tiết catalog nhúng trong description bridge), KHÔNG quyết định có defer hay không.

3 tier (`:17-27`, `assemble_tool_defs` `:834-838`):
- **Tier 0** — không có deferrable tool → passthrough, mọi thứ eager.
- **Tier 1** — catalog fit trong `listing_token_budget = min(listing_max_tokens=4000, threshold_pct% * context)` (default `threshold_pct=5.0` → fallback 10K token nếu không biết context) → nhúng listing "tên + mô tả ngắn" (form `full`), degrade dần sang chỉ-tên (`names`) rồi `mixed` (server lớn quá thì tóm tắt server, còn lại full).
- **Tier 2** — catalog quá lớn dù chỉ-tên (case thật: Cloudflare flat API ~3,300 tool, tên thôi đã ~32K token) → bare bridge + tóm tắt 1 dòng/server (form `groups`), tool cụ thể chỉ khám phá qua `tool_search`.

3 bridge tool cố định tên (`BRIDGE_TOOL_NAMES`): `tool_search(query, limit)` → BM25 retrieval trên catalog (`search_catalog`, `_bm25_score`); `tool_describe(name)` → trả full JSON schema 1 tool; `tool_call(name, arguments)` → dispatch qua đúng pipeline `model_tools.handle_function_call` như gọi trực tiếp (guardrail/hook/approval/truncation áp dụng y hệt — `bridge_tool_schemas` docstring `:658-660`).

Never-defer bất biến (`is_deferrable_tool_name`, `:214-238`): `_HERMES_CORE_TOOLS` và toolset session-gated GUI (`desktop_ui`, `project`) KHÔNG BAO GIỜ bị defer dù kỹ thuật đến từ plugin — tránh shadow. Catalog **stateless mỗi lần build lại từ tool-defs hiện tại** (không cache theo session) — bài học rút từ hồi quy thật: `openclaw/openclaw#84141`, catalog cache theo session lệch pha với registry sống → tool biến mất âm thầm (`:33-36`).

**Đánh đổi**: (a) mọi lệnh gọi MCP tool giờ tốn 2-3 round trip (`search`→`describe`→`call`) thay vì 1 round trip trực tiếp — độ trễ + token overhead cho mỗi lần dùng lần đầu; (b) model có thể "quên" tồn tại 1 tool nếu listing bị degrade xuống tier 2 (chỉ thấy tên server, không thấy tên tool) — mô tả bridge phải viết rất mạnh ("KHÔNG được nói capability không tồn tại mà chưa search") để chống model tự tin sai; (c) ước lượng token bằng `chars/4` (`CHARS_PER_TOKEN=4.0`, `:73-78`) — xấp xỉ, không chính xác theo tokenizer thật, thiên về under-estimate (an toàn hơn: kích hoạt sớm còn hơn không kích hoạt khi cần).

### 2.6. `agent/tool_guardrails.py` — thang allow → warn → block → halt (Q6)

`ToolGuardrailDecision.action ∈ {allow, warn, block, halt}` (`:256-282`). Hai property tổng hợp: `allows_execution` = `action in {allow, warn}`; `should_halt` = `action in {block, halt}`.

**Trước khi chạy** — `before_call()` (`:373-430`): kiểm tra loop-cap cứng trước tiên (không phụ thuộc `hard_stop_enabled`): `LoopCapConfig` (`:172-206`, lấy cảm hứng từ "Claude Code v2.1.212, Week 29 July 2026") — `max_web_searches=50`, `max_subagents=50` mỗi TURN (reset ở `reset_for_turn`), value `0` = unlimited. Nếu `hard_stop_enabled=False` (default) thì dừng ở đây — mọi call được allow. Nếu bật: `exact_failure_block_after=5` (cùng tool + cùng args hash liên tiếp fail 5 lần) → `action="block"` NGAY TRƯỚC KHI CHẠY (không tốn 1 lần gọi tool nữa); idempotent tool lặp cùng result `no_progress_block_after=5` lần → block tương tự.

**Sau khi chạy** — `after_call()` (`:431-518`): tính lại chữ ký `(tool_name, sha256(canonical_json(args)))`. Ngưỡng warn (không chặn, chỉ gắn guidance vào tool result):
- `exact_failure_warn_after=2` (cùng args fail 2 lần) → warn.
- `same_tool_failure_warn_after=3` (cùng TOOL name fail 3 lần, args khác nhau cũng tính) → warn.
- `no_progress_warn_after=2` (idempotent tool trả cùng result 2 lần) → warn.
- Ngưỡng halt: `same_tool_failure_halt_after=8` → `action="halt"`, set `self._halt_decision` — đây là NGƯỜI DUY NHẤT tạo halt action.

**Ai biến decision thành hành động**: `run_agent.py::_append_guardrail_observation` (`run_agent.py:8237-8286`):
- `decision.action in {"warn","halt"}` → `function_result = append_toolguard_guidance(function_result, decision)` (nối text guidance vào NGAY tool result, model đọc được trong context).
- `decision.should_halt` → `self._set_tool_guardrail_halt(decision)` ghi `self._tool_guardrail_halt_decision` (chỉ ghi lần ĐẦU tiên trong turn, `run_agent.py:8223-8225`).
- Vòng `conversation_loop.py:7362-7379` sau MỖI batch tool-call kiểm `agent._tool_guardrail_halt_decision is not None` → nếu có, DỪNG HẲN turn (không gọi model thêm lần nào nữa), tự viết 1 câu giải thích qua `_toolguard_controlled_halt_response()` (`run_agent.py:8228-8235`) và append như assistant message.
- `action == "block"` (từ `before_call`) được `tool_executor.py:655-671` chặn TRƯỚC dispatch, trả `agent._guardrail_block_result(decision)` (synthetic error JSON) làm tool result, KHÔNG chạy tool thật, KHÔNG halt turn — model còn cơ hội đổi chiến lược trong turn đó.

Vậy ladder thật là: `warn` = chèn guidance, tool vẫn chạy tiếp bình thường; `block` = chặn TRƯỚC lần gọi tiếp theo (không lãng phí round tool call), turn tiếp tục; `halt` = dừng cả turn ngay sau batch hiện tại. Còn 1 cơ chế riêng, không thuộc ladder trên nhưng cùng file: **stall guard / identical-call stub** (`observe_call`, `:528-618`) — từ lần gọi giống hệt thứ 3 liên tiếp (`STALL_GUARD_IDENTICAL_CALL_THRESHOLD=3`) chèn 1 notice; từ lần thứ 2 mà RESULT MỚI byte-giống result cũ, thay payload bằng 1 stub tham chiếu ngắn (chỉ khi payload > `IDENTICAL_RESULT_STUB_MIN_CHARS=512` và không phải lỗi) — tiết kiệm context mà không giả lập cache (tool vẫn thực thi thật mỗi lần). Có PR mở `#85352` theo dõi phát hiện no-progress **xuyên turn** (khác cơ chế per-turn ở đây) — một hướng mở chưa merge.

### 2.7. Programmatic Tool Calling — `tools/code_execution_tool.py` (Q7)

Cơ chế: model viết 1 script Python, script đó gọi lại các tool Hermes qua RPC, toàn bộ vòng lặp tool-nội-bộ chạy NGOÀI context của model — model chỉ nhận **stdout cuối cùng** của script (`code_execution_tool.py:1-27`, docstring). 2 transport:
- **Local (UDS)**: cha mở Unix domain socket + thread RPC server (`_rpc_server_loop`, `:652-760`), sinh module stub `hermes_tools.py`, spawn tiến trình con chạy script model; mỗi lần script gọi `web_search(...)` là 1 message JSON qua socket, cha dispatch bằng `model_tools.handle_function_call` (đúng pipeline, KHÔNG bypass guardrail/hook/approval) rồi trả kết quả qua socket.
- **Remote (docker/ssh/modal/daytona)**: không có UDS xuyên container → dùng file-based RPC (poll request/response file qua `env.execute()`).

Vì sao "không tốn context giữa các bước": intermediate tool result (có thể hàng chục KB mỗi cái) không bao giờ vào message history — chỉ output cuối vào. Đánh đổi ngược: model **không nhìn thấy** intermediate result để tự sửa chiến lược giữa các bước — toàn bộ logic rẽ nhánh/lặp phải nằm trong chính script Python nó viết ra (schema mô tả rõ: "Use when you need 3+ tool calls with logic between them", `:2126-2131`).

**Giới hạn cứng**: `DEFAULT_TIMEOUT=300s`, `DEFAULT_MAX_TOOL_CALLS=50`, `MAX_STDOUT_BYTES=50_000`, `MAX_STDERR_BYTES=10_000` (`:69-73`). Chỉ 7 tool được whitelist gọi từ trong sandbox — `SANDBOX_ALLOWED_TOOLS` (`:56-64`): `web_search, web_extract, read_file, write_file, search_files, patch, terminal`. RPC server enforce allowlist + đếm tool-call cap TẠI SERVER (không tin script), có token auth so bằng `secrets.compare_digest` (constant-time, `:706-712`) — script không đoán được token qua timing.

**Rủi ro bảo mật + cách Hermes giảm**:
- Script Python chạy = thực thi mã tuỳ ý trên host/sandbox → chặn bằng: allowlist tool cứng, cap số lần gọi, cap thời gian, cap stdout; `terminal` bên trong sandbox bị strip tham số nguy hiểm (`_TERMINAL_BLOCKED_PARAMS`, dùng ở `:733-735`) và **foreground-only** (không background/pty, theo mô tả schema `:2129`).
- Rò rỉ biến môi trường bí mật vào child process: `_scrub_child_env()` (`:207-290`) — chặn theo substring bí mật (`KEY, TOKEN, SECRET, PASSWORD, CREDENTIAL, PASSWD, AUTH, DSN, WEBHOOK, CREDS, BEARER, APIKEY`), chỉ cho qua theo allowlist prefix an toàn (`PATH, HOME, LANG,...`) hoặc allowlist tên chính xác (`_HERMES_CHILD_ALLOWED` — 5 biến vận hành non-secret). Có sự cố thật đã sửa: prefix rộng `"HERMES_"` từng cho qua cả biến không có substring bí mật nhưng vẫn nhạy cảm (`HERMES_BASE_URL, HERMES_KANBAN_DB, HERMES_*_WEBHOOK`) — issue **#27303**, giờ chỉ allowlist đích danh, phần còn lại bị drop có log.
- RPC không token → `"Unauthorized RPC request"` (`:707-712`) — chống script bên thứ 3 (nếu injection tạo thêm process) gọi thẳng vào RPC listener của session khác.
- delegate_task context: nếu là con của 1 subagent bị delegate, biến đánh dấu context đó phải bridge qua process boundary sau khi scrub, để không mất "guard chặn mutation Kanban của DB layer" nhưng cũng không cho một explicit passthrough nào re-grant quyền mutation board của cha (`:290-300`).

### 2.8. `clarify` và `todo` (Q8)

**`clarify`** (`tools/clarify_tool.py`) — agent tự hỏi lại user. Schema (`CLARIFY_SCHEMA`, `:437-546`) hỗ trợ 3 mode: single-select (radio, tối đa `MAX_CHOICES=4` + auto "Other"), multi-select (`multi_select=true`), open-ended (bỏ `choices`). Có **batch**: `questions` (tối đa `MAX_QUESTIONS=5`) hỏi nhiều câu ĐỘC LẬP trong 1 lần gọi, trả `{"responses":[...]}` (issue #18450). Giới hạn/validate: `_flatten_choice()` chống model gửi choice dạng dict (`[{"description":"..."}]`) → chỉ lấy field hiển thị theo thứ tự ưu tiên `label→description→text→title`, KHÔNG lấy `name/value` (tránh leak identifier thô làm label) (`:43-73`). `mark_recommended()`/`strip_recommended()` gắn/gỡ nhãn `"(Recommended)"` vào choice đầu tiên — chỉ đúng 1 điểm chèn nhãn platform-agnostic để mọi UI (CLI, Discord, Telegram) hiển thị giống nhau, và gỡ nhãn trước khi trả `user_response` để không leak presentation vào answer model đọc lại (`:76-109`). Timeout: callback trả `None` hoặc đúng câu `TIMEOUT_RESPONSE` → với batch legacy-loop thì DỪNG hỏi tiếp (không làm phiền tiếp), các câu đã trả lời vẫn giữ (`_run_batch`, `:279-326`). Render: CLI dùng arrow-key navigable, platform messaging render numbered list — logic UI thật nằm ngoài module này (cli.py / gateway), module chỉ định nghĩa schema + validate + dispatch qua callback được platform tiêm vào runtime.

**`todo`** (`tools/todo_tool.py`) — agent tự chia việc, KHÔNG có UI riêng, chỉ 1 tool `todo(todos?, merge?)`, đọc nếu bỏ `todos`. State sống trên `TodoStore` instance gắn theo AIAgent (1 session = 1 store), KHÔNG lưu DB — nhưng được re-inject vào history sau mỗi lần context-compression qua `format_for_injection()` (chỉ item `pending`/`in_progress`, bỏ qua `completed`/`cancelled` để model không làm lại việc đã xong, `:118-150`). Giới hạn chống injection/replay: `MAX_TODO_CONTENT_CHARS=4000` (cắt nội dung 1 item), `MAX_TODO_ITEMS=256` (cắt cả list, giữ đầu vì "list order = priority"), `MAX_TODO_RESULT_CHARS=512_000` (bound khi hydrate lại store từ history do caller gửi lên — gateway/API server replay history của người dùng CÓ THỂ giả tool result todo để bơm state, nên phải cap trước khi parse). `merge=true` update theo `id`, giữ nguyên thứ tự cũ + thêm mới cuối; luôn có `_normalize_order()` đẩy item `in_progress` lên trước item `pending` gần nhất để hiển thị đúng độ ưu tiên đang làm.

### 2.9. Danh sách issue/PR đã xác nhận trong docstring + bài học (Q9)

| Số hiệu | File | Bài học rút ra |
|---|---|---|
| #21658 / #5304 | `tools/registry.py:256` | check_fn probe (docker/playwright) bị flap 1 lần KHÔNG được rút cả toolset — phải cache + coi transient failure khác disable thật |
| #55840 | `tools/registry.py:906` | Ownership check plugin phải theo package root, không theo chuỗi module chính xác, nếu không code cleanup của submodule tự bị chặn xoá tool của chính nó |
| #23767 | `agent/tool_executor.py:104`, `budget_config.py:100,146` | Budget cố định (100K/200K char) là "đúng" cho model 200K+ token nhưng có thể tự vượt window của model nhỏ — phải scale theo context length, có floor |
| #79719 | `agent/tool_executor.py:145,444`, `tools/approval.py` (5 chỗ), `code_execution_tool.py:1297` | Thời gian CHỜ NGƯỜI (approval prompt) phải đo tại nguồn và loại khỏi deadline batch — nếu đo bằng "đang chiếm authorization gate" (mã tuỳ ý) thì 1 hook treo vô hạn hoặc client chết sẽ vô tình vô hiệu hoá deadline |
| #85125 | `tool_executor.py:186,777` | Timeout resolve phải qua 1 resolver thống nhất (config field mới thắng, env var cũ giữ back-compat) — tránh nhiều nguồn timeout xung đột |
| #84491 | `tool_executor.py:698` | Tool chạy im lặng lâu (không tự log) làm gateway watchdog coi turn "chết" — phải có heartbeat riêng đập activity định kỳ trong lúc tool chạy |
| #5149 (ironclaw) | `tool_executor.py:1166,2015`, `tool_search.py:989` | Bridge `tool_call` phải validate arg THIẾU trước khi unwrap — nếu không lỗi hiện ra như "tool call thất bại mù" thay vì show đúng schema tham số còn thiếu |
| GHSA-qg5c-hvr5-hjgr / #13617 | `tool_executor.py:1315` | Context approval/sudo (thread-local) phải được propagate tường minh sang worker thread khi submit — nếu không, tool chạy trong thread pool "quên" phiên đã được approve, có thể bị hỏi lại HOẶC (rủi ro ngược) chạy dưới quyền sai |
| #84141 (openclaw) | `tool_search.py:32` | Catalog progressive-disclosure không được cache theo session — cache lệch pha registry sống làm tool "biến mất" âm thầm giữa các turn |
| #80508 | `budget_config.py:47` | Đặt tên config block `tool_budget:` trùng với 1 đề xuất cấu hình giới hạn rộng hơn đang mở, để 2 nhánh sau này merge không phải rename key |
| #23770 (opencode) | `tool_output_limits.py:3` | Hard-code 2 chỗ khác nhau (`terminal_tool.py`, `file_operations.py`) cho cùng khái niệm "giới hạn output" nên gộp về 1 config section |
| #31877 (opencode) | `schema_sanitizer.py:410,465` | `type` dạng array `["number","string"]` không nên chỉ giữ nhánh đầu (rơi mất 1 type) — phải convert thành `anyOf` giữ đủ nhánh |
| #11955 (kilocode) | `agent/gemini_schema.py:117` | `required` phải lọc theo `properties` CÙNG NODE trước khi gửi Gemini — 1 tool sai làm 400 CẢ request, không riêng tool đó |
| #1595 (kimi-cli) | `agent/moonshot_schema.py:11` | Moonshot strict hơn JSON Schema chuẩn ở 3 điểm cụ thể (type bắt buộc, anyOf không cho type ở parent, required bắt buộc tồn tại) — cần adapter riêng, không dùng chung sanitizer generic |
| GHSA-96vc-wcxf-jjff | `tools/approval.py:71` | Cờ interactive-mode không được là biến process-global khi có concurrent session (ThreadPoolExecutor) — phải contextvar theo thread/task, nếu không session A "mượn" trạng thái approve của session B |
| issue #18450 | `tools/clarify_tool.py:166,348` | Hỏi nhiều câu độc lập nên gộp 1 lần gọi (UX 1 form) thay vì clarify tuần tự nhiều round — giảm round trip |
| #33924 / #57315 | `toolsets.py:734`, `model_tools.py:60,473,486` | Disable 1 "platform bundle" toolset (`hermes-*`) không được trừ luôn core tool nó re-list — chỉ trừ phần riêng của bundle, nếu không disable 1 bundle làm rỗng cả tool list |
| #17335 / #19251 | `model_tools.py:311,398,401` | Cache schema tool phải có LRU bound trên gateway sống lâu — không bound thì tích tụ entry theo mọi tổ hợp toolset/config từng thấy, phình bộ nhớ vô hạn |
| #17309 | `model_tools.py:463` | `disabled_toolsets` phải là bước TRỪ áp dụng SAU CÙNG, không phụ thuộc thứ tự enabled/include — nếu không 1 toolset composite bật lại đúng tool vừa bị tắt |
| #560 (discord) | `model_tools.py:521` | Schema động (execute_code liệt kê "tool nào dùng được trong sandbox") phải build theo tool THỰC SỰ available sau check_fn, không theo config tĩnh — nếu không model tin nhầm 1 tool tồn tại |
| #85352 (patrykkopycinski, mở) | `agent/tool_guardrails.py:351` | No-progress loop XUYÊN NHIỀU TURN là vấn đề khác với lặp trong 1 turn — cần cơ chế detection window riêng, chưa merge, cần theo dõi tiếp |
| #27303 | `code_execution_tool.py:144,245,277` | Allowlist theo PREFIX rộng (`HERMES_*`) rò rỉ biến không-bí-mật-nhưng-nhạy-cảm — phải siết về allowlist tên chính xác, phần bị drop phải LOG để còn debug được |
| #10807 | `code_execution_tool.py:1231,1621,1686` | Theo dõi tiến trình con (heartbeat/print) cần đề phòng gateway stream consumer im lặng "drop" event — không log 1 chỗ là đủ |
| #30882 | `code_execution_tool.py:1297,1413` | Auto-approve lệnh nguy hiểm bên trong sandbox phải chạy đúng thread giữ session context — nếu không context bị "mù" phiên đang chạy |
| #33057 | `code_execution_tool.py:1133,1413` | Cùng 1 root cause với #30882 — routing + auto-approve dangerous command gắn liền, sửa 1 không sửa hết phải fix cả 2 nơi |
| #74817 | `code_execution_tool.py:1492` | sys.path của tiến trình con KHÔNG được kế thừa/đè `sys.path` của tiến trình cha khi import module cha — poison path là lỗi khó tìm |
| #56047 | `code_execution_tool.py:2010` | Nhiều path trong 1 session (host/sandbox/execute_code) phải đồng thuận cùng 1 khái niệm "working directory", không thì file tool tạo/đọc lệch thư mục với terminal |

## 3. Bài học tổng hợp (cho bất kỳ agent tool nào, không riêng Hermes)

1. **Song song hoá không nên là quyết định nhị phân toàn-batch**: chia đoạn theo an toàn từng cặp call (path overlap, reader/writer, tool tương tác) cho phép giữ song song phần an toàn của 1 batch hỗn hợp mà vẫn tuần tự đúng phần cần tuần tự, thay vì tất cả rơi về tuần tự chỉ vì 1 call "khả nghi".
2. **Ngân sách output không nên cố định theo char/byte tuyệt đối** khi hệ thống support nhiều model có context window khác xa nhau — phải scale + clamp theo model đang chạy, và luôn có floor để model nhỏ vẫn dùng được.
3. **Truncate và persist là 2 chiến lược khác mục đích**: truncate mất dữ liệu vĩnh viễn (chấp nhận được cho log/preview), persist giữ dữ liệu đầy đủ trên đĩa và chỉ cắt cái model NHÌN THẤY — quan trọng khi model cần quay lại đọc phần đã bị "ẩn" (`read_file` + offset/limit).
4. **Sanitizer schema phải tách theo NGUYÊN NHÂN lỗi cụ thể của backend**, không viết 1 sanitizer chung "cho chắc" — mỗi backend (llama.cpp, Gemini, Moonshot, xAI, OpenAI Codex, Fireworks) có message lỗi và luật khác nhau, gộp chung dễ sai cho backend còn lại.
5. **Progressive disclosure (tool search) đánh đổi round-trip lấy context budget** — chỉ nên bật khi catalog tool đủ lớn để việc này đáng giá (Hermes chọn "bất kỳ non-core tool nào cũng defer" một khi đã bật, không đo kích thước để quyết định activate — chỉ đo để quyết định listing form).
6. **Guardrail cần tách "trước khi chạy" (block, tiết kiệm 1 round tool call) và "sau khi chạy" (halt, dừng cả turn)** — 2 điểm can thiệp khác nhau trong vòng lặp, không thể gộp làm 1 quyết định duy nhất.
7. **Code-execution-as-tool (PTC) chỉ an toàn khi RPC server tự enforce allowlist + cap tại chính server, không tin script con** — token auth constant-time + env scrubbing theo allowlist tên chính xác (không theo prefix rộng) là 2 lớp bắt buộc.
8. **Mọi tool nhận nội dung không tin cậy (web/browser/MCP) nên được đánh dấu ranh giới dữ liệu-vs-chỉ dẫn tại tầng dựng message, không tại tầng prompt** — và phải defang chính cái delimiter đó khỏi nội dung tấn công, nếu không delimiter bị forge để thoát khối.

## 4. Port được gì sang `apps/api/src/agent/tools/` và `loop.py`

Đối chiếu với thực tế Stock_Massive: 12 tool ĐỀU là đọc store/API ngoài (`get_analysis`, `get_price_series`, `get_financials`, `get_company_profile`, news, web, knowledge, mcp, `run_python` (executor), `screen_universe`, computations, `get_watchlist` — xem `apps/api/src/agent/tools/suite.py:75-89`), KHÔNG có `write_file`/`patch`/`terminal`. `loop.py` dùng `asyncio.gather` KHÔNG điều kiện cho mọi round (`loop.py:937-941`), `MAX_TOOL_ROUNDS=4` (không phải 8 — xác nhận lại: `loop.py:124`), `MAX_TOOL_RESULT_BYTES=4*1024` cứng, không spillover (`catalog.py:33,201-207` raise `ToolResultTooLarge`).

Port có giá trị thật, xếp theo ROI:

1. **3-tầng ngân sách + spillover** (`tool_result_storage.py`) — ROI cao nhất. Hiện `MAX_TOOL_RESULT_BYTES=4KB` cứng làm tool bị RAISE lỗi cứng khi vượt (không có đường thoát cho model), khác hẳn Hermes "degrade thành preview + path". Với domain chứng khoán, `get_price_series`/`screen_universe` trả list dài là ứng viên tự nhiên overflow 4KB khi user hỏi nhiều mã/nhiều kỳ. Port ý tưởng — KHÔNG cần full complexity multi-backend (docker/ssh/modal) vì Stock_Massive chỉ có 1 backend Postgres, chỉ cần: preview + spillover file trên đĩa local (hoặc trả `next_cursor`/pagination thay vì file path, hợp với REST hơn) + per-turn aggregate budget cộng dồn qua nhiều tool call trong 1 round.
2. **Thang `allow → warn` cho lặp gọi vô nghĩa** (từ `tool_guardrails.py`) — nếu model lặp gọi `get_price_series` cùng symbol/cùng khoảng ngày (idempotent, `IDEMPOTENT_TOOL_NAMES` tương tự) mà không tiến triển, chèn 1 câu guidance vào tool result thay vì để model tự loop tới hết `MAX_TOOL_ROUNDS=4`. Đây rẻ để port (1 dict đếm theo `(tool_name, args_hash)` mỗi turn) và trực tiếp bảo vệ ngân sách round đang RẤT hẹp (4 round) của Stock_Massive — mỗi round lãng phí là 25% ngân sách turn.
3. **Loop cap cứng cho tool tốn tiền** (`LoopCapConfig`) — Stock_Massive đã có `MAX_EXTERNAL_TOOL_CALLS` riêng cho `ToolDataAccess.EXTERNAL` (`loop.py` xác nhận có biến `state.external_tool_calls`/`MAX_EXTERNAL_TOOL_CALLS`) — tức ý tưởng NÀY ĐÃ CÓ, không cần port, chỉ ghi nhận Hermes làm y hệt (đặt cap cứng theo per-turn count cho tool tốn tài nguyên, ví dụ `web_search`).
4. **`admit_round` 2-attempt cap** trong `loop.py:579-599` đã tự làm được việc tương đương "block sau N lần fail liên tiếp" của Hermes (`exact_failure_block_after`) — ý tưởng đã port tự nhiên/độc lập, không cần đọc thêm từ Hermes.
5. **Chống prompt injection cho `search_news`/`web` tool** (untrusted-wrap từ `make_tool_result_message`) — Stock_Massive có `news.py`, `web.py` lấy dữ liệu ngoài (VCI news, web lane) — nội dung này CÓ THỂ chứa chỉ dẫn injection. Port ý tưởng bọc `<untrusted_tool_result>` cho riêng 2 nhóm tool này trước khi đưa vào message history, kèm defang delimiter — chi phí thấp, rủi ro injection với dữ liệu tin tức/web là thật.
6. **Idempotent-result stub** (dedupe payload giống hệt liên tiếp) — có giá trị nếu model hỏi lại đúng `get_analysis(symbol, day)` 2 lần trong 1 turn (context bị nhân đôi payload) — nhưng ROI thấp hơn 1-2 vì round budget đã chặn trước khi kịp lặp nhiều.

Không cần port cấu trúc `registry.py`/`toolsets.py`/`model_tools.py` — Stock_Massive đã có kiến trúc tương đương ĐÚNG với KISS hơn (catalog đóng 12 tool, versioned bằng hash, không cần discovery/plugin/override runtime).

## 5. Không port gì + vì sao

- **Rules engine song song theo path overlap** (`_plan_tool_batch_segments`, path reader/writer) — không áp dụng: không có tool `write_file`/`patch`/`terminal` trong catalog Stock_Massive, mọi tool đều đọc store qua session Postgres riêng biệt theo mỗi call (không chia sẻ state mutable). `asyncio.gather` không điều kiện hiện tại là ĐÚNG cho domain này, không phải thiếu sót.
- **Progressive tool disclosure (Tool Search)** — catalog Stock_Massive CỐ Ý đóng ở 12 tool (theo CLAUDE.md: "Tool catalog ĐÓNG"), không có MCP dynamic hay plugin mở rộng runtime — không có "catalog phình" để cần defer. Nếu tương lai mở MCP registry (`apps/api/src/agent/mcp/registry.py` đã tồn tại, hiện `mcp_enabled` cấu hình được) và số server MCP tăng, ý tưởng tier 1/2 mới đáng xét lại.
- **Schema sanitizer theo backend (Gemini/Moonshot/llama.cpp)** — Stock_Massive dùng 1 route LLM duy nhất qua proxy OpenAI-compatible (`llm_base_url`, xem `apps/api/src/core/llm/config.py:115,199`; theo memory người dùng: proxy `ccs codex / gpt-5.6-luna`), strict JSON schema (`core.llm.protocol.strict_parameters`) — không có multi-backend nào để cần sanitize khác nhau. Port bây giờ là giải quyết vấn đề chưa tồn tại (YAGNI).
- **Programmatic Tool Calling đầy đủ (RPC gọi lại tool khác từ trong sandbox)** — `compute.py::run_python` ĐÃ có sandbox execution (file-queue, networkless, timeout, size cap) nhưng CỐ Ý không cho gọi lại tool khác (chỉ "bounded Python arithmetic over explicit JSON inputs", `compute.py:88-90`) — mở RPC gọi tool khác từ trong sandbox sẽ phá vỡ ràng buộc `ToolDataAccess.STORE_ONLY`/`EXTERNAL` và toàn bộ trace/budget theo-tool hiện có (mỗi dispatch qua `ToolCatalog.dispatch` mới được trace và tính budget); Programmatic Tool Calling của Hermes coi nhẹ việc này vì Hermes không có ngân sách per-tool-call nghiêm ngặt như `catalog.py`.
- **`clarify` tool (hỏi lại user giữa turn)** — kiến trúc Stock_Massive là request/response 1 Turn (`AgentLoop._round`, không có kênh interactive giữa chừng 1 turn) — thêm `clarify` cần thiết kế lại giao thức turn (tạm dừng, chờ, resume) — chi phí kiến trúc lớn hơn giá trị hiện tại (chưa có yêu cầu UX "agent tự hỏi lại").
- **`todo` tool (agent tự chia việc)** — Stock_Massive KHÔNG PHẢI coding agent nhiều bước dài hơi (max 4 round/turn), không có "task nhiều bước cần theo dõi qua nhiều turn" — todo giải quyết vấn đề của agent loop dài, không phải vấn đề của Stock_Massive.
- **`tool_guardrails` loop-cap style + full ladder allow/warn/block/halt** — chỉ port "warn" nhẹ (mục 4.2); KHÔNG port `block`/`halt` đầy đủ vì Stock_Massive đã có ranh giới cứng hơn và đơn giản hơn (`admit_round` 2-attempt, `MAX_TOOL_ROUNDS=4`, `MAX_EXTERNAL_TOOL_CALLS`) — thêm 1 state machine guardrail song song dễ VI PHẠM DRY và tạo 2 nguồn sự thật về "khi nào dừng".

## 6. Câu hỏi chưa giải quyết

- `MAX_TOOL_ROUNDS` trong `loop.py:124` đọc được là **4**, không phải **8** như mô tả trong task gốc ("ceiling 8 round tool-call"). Chưa rõ 8 có phải là con số ở 1 phiên bản khác/nhánh khác của `loop.py` hay là hiểu nhầm ban đầu — cần người giao việc xác nhận lại số round thật đang chạy production.
- Chưa đọc `agent/agent_runtime_helpers.py` (208KB) và `agent/conversation_loop.py` (472KB) đầy đủ — chỉ đọc đủ đoạn liên quan `_tool_guardrail_halt_decision`. Có thể còn cơ chế dispatch/hook khác chưa nắm hết trong 2 file khổng lồ này.
- `toolset_distributions.py` xác nhận không dùng trong runtime (`grep -rln` chỉ ra 2 file), nhưng chưa kiểm tra `hermes_state*.py` (rất lớn, > 500KB tổng) có đường dẫn gọi gián tiếp nào khác không — độ tin cậy của khẳng định "không phải per-model runtime" cao nhưng không phải 100%.
- Chưa xác nhận thực nghiệm (chạy code) bất kỳ hành vi nào — toàn bộ phân tích dựa trên đọc tĩnh + docstring. Số liệu lỗi HTTP 400 trích trong docstring là lời khai của tác giả Hermes, chưa tự tái lập.
