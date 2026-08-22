# Hermes Agent (NousResearch, MIT) — MCP / Observability / Hook / Eval / Executor

Nguồn: sparse clone `hermes-agent` tại scratchpad (agent/, tools/, root .py). Đọc trực tiếp code, không đọc README/marketing. File chính: `tools/mcp_tool.py` (8235 dòng), `tools/mcp_oauth*.py`, `agent/monitoring/*`, `agent/shell_hooks.py`, `agent/verify/*`, `tools/environments/*`.

## 1. MCP

### 1.1 Ba transport khác nhau chỗ nào (Q1)

Cả 3 transport đều chạy trong `MCPServerTask.run()` (`tools/mcp_tool.py:3024`), vòng lặp reconnect chung; khác biệt nằm ở `_run_stdio` (dòng 2996) vs `_run_http` (dòng 3379, cả StreamableHTTP và SSE, rẽ nhánh bằng `config.get("transport") == "sse"` ở dòng 3445).

- **stdio**: OSV malware preflight trước khi spawn (`:3025`, timeout riêng `_OSV_MALWARE_CHECK_TIMEOUT_S`, fail-open); bọc command qua `mcp_stdio_watchdog` (`:3057`, xem 1.3); snapshot PID con để force-kill khi cleanup; KHÔNG có OAuth, KHÔNG có preflight content-type (giao thức không qua HTTP nên không có "trang HTML giả MCP").
- **HTTP/StreamableHTTP**: preflight content-type probe trước khi connect thật (`:3782-3799`) — bắt lỗi "URL trỏ vào web-app root trả về HTML, SDK treo tới hết connect_timeout rồi mới báo CancelledError mù mờ"; probe này bị **skip** khi `transport=sse` (SSE tự có client riêng, hợp lệ trả `text/event-stream`) hoặc khi `auth_type=oauth` (chưa có token thì mọi request đều trả 401/HTML, probe sẽ chặn nhầm OAuth flow). Seed header `mcp-protocol-version` bằng `LATEST_HANDSHAKE_VERSION` — phải khớp bản giao thức mà body `initialize()` thực sự gửi, không phải bản mới nhất (`:3405-3413`, nếu lệch server sẽ áp nhánh "per-request envelope" mới và từ chối body cũ).
- **SSE**: rẽ nhánh riêng trong `_run_http` (`:3445`), từ chối `strict_redirect_headers` (Portable Agent Plugin spec §7.2.1 — package đã ký header không thể forward qua redirect sang origin khác, SSE không thể enforce boundary này nên fail closed).
- **Lifecycle chung sau connect**: một session "handshake xong" KHÔNG được coi là khỏe — phải "proven" (sống sót ≥1 keepalive interval hoặc ≥1 tool call thành công, `_mark_session_proven`) mới được reset budget reconnect; nếu không, một transport chập chờn (handshake OK, rớt ngay sau) sẽ tự respawn vô hạn — đúng bug thực tế "#62212, 6212 lần spawn trong 63 giờ" (`:3841-3849`). Lỗi được phân loại "permanent" (bad command, non-MCP URL, 401/403) thì **park ngay**, không đốt backoff ladder (`#65673`).

### 1.2 `mcp_schema_cache.py` — lazy startup (Q2)

`tools/mcp_schema_cache.py` (151 dòng). Cache key = `server_name` + `config_fingerprint()` (sha256 16 hex của command/args/url/transport/tools include-exclude, `:29-42`). File `~/.hermes/cache/mcp_schema_cache.json`, mode 0o600 (cache là "trusted input" trên đường lazy-registration).

- **Invalidate**: 3 cơ chế — (a) fingerprint đổi → cache miss ngay (đổi command/args/url/filter); (b) TTL theo spec MCP 2026-07-28 SEP-2549: server trả `ttlMs` trong `tools/list`, ghi kèm `written_at`; entry cũ hơn TTL bị coi là miss (`get_cached_entry:74-88`); (c) `clear_cache_entry()` xoá thủ công. Entry pre-2026 (không có `ttl_ms`) — **never-expires** theo hành vi cũ.
- **Rủi ro schema cũ**: giữa 2 lần khởi động, server thực tế có thể đã đổi tool schema (thêm/xoá param) nhưng Hermes vẫn hiển thị tool cho model dựa vào cache đĩa — cho tới khi server đó **thực sự connect** (không lazy) mới ghi đè bằng schema mới. Đây là trade-off cố ý: khởi động nhanh (không spawn subprocess) đổi lấy khả năng model gọi tool với schema stale trong khoảng thời gian đó. Không có cơ chế "background refresh" — chỉ có TTL cho server tuân theo SEP-2549.
- Write-through skip khi entry byte-identical để tránh churn (`:118-123`), nhưng entry có TTL luôn ghi lại để `written_at` tiến (nếu không sẽ hết hạn theo mốc ghi gốc dù server vẫn sống).

### 1.3 `mcp_stdio_watchdog.py` — parent-death watchdog (Q3)

157 dòng, standard-library only (chủ đích: khởi động nhanh, tự nó không được là nguồn leak). Vấn đề: macOS không có `prctl(PR_SET_PDEATHSIG)` như Linux, nên nếu Hermes process chết cứng (`kill -9`, crash, force-quit), MCP server con (và cháu, ví dụ `mcp-remote` spawn `node`) bị orphan, chỉ được dọn khi Hermes khởi động lại VÀ có ai gọi `_kill_orphaned_mcp_children()`.

Cơ chế: thay vì exec trực tiếp lệnh MCP, Hermes exec `python3 -m tools.mcp_stdio_watchdog --ppid <ppid_gốc> -- <real_command>`. Watchdog: (1) spawn lệnh thật trong **process group riêng** (`start_new_session=True`) để killpg được cả cây con; (2) relay stdin/stdout/stderr xuyên suốt (không phải proxy đọc-viết — giao thức MCP nói trực tiếp qua pipe, watchdog phải "no-op relay"); (3) thread nền poll `os.getppid()` mỗi 2s, so với ppid gốc; (4) ppid đổi → SIGTERM cả process group, grace 3s, SIGKILL. Vì server nằm trong process-group riêng, watchdog còn phải tự forward SIGTERM/SIGINT sang group con khi nó nhận shutdown bình thường — nếu không, cơ chế fix orphan lại **tạo ra** một lớp orphan mới (server sống sót qua killpg gốc vì đã tách group).

### 1.4 Đặt tên tool + ghi transcript (Q4)

`sanitize_mcp_name_component()` (`:6434`) thay mọi ký tự ngoài `[A-Za-z0-9_]` bằng `_`. `mcp_prefixed_tool_name()` (`:6456`) build `mcp__<server>__<tool>` — convention chia sẻ với Claude Code, Codex, OpenCode (`anomalyco/opencode#33533`). Double-underscore để phân biệt ranh giới server/tool dù thành phần có underscore, và khớp cách model được train để nhận diện tên tool MCP. Tên này là tên **wire** — đăng ký vào registry bằng chính chuỗi này, nên khi model gọi tool, transcript ghi lại đúng `mcp__<server>__<tool>` — không cần bảng map riêng.

Chống trùng: nếu tool tự nhiên của server trùng với utility tool Hermes tự sinh (`read_resource`/`list_resources`/...), native tool thắng, utility bị drop (`#87112`, `:6877`). `toolset_name = f"mcp-{name}"` cho include/exclude filter theo config (`#690`, `:6774`).

### 1.5 OAuth 2.1 + PKCE (Q5)

`tools/mcp_oauth.py` (1956 dòng) không tự implement PKCE — dùng `OAuthClientProvider` (subclass `httpx.Auth`) của MCP Python SDK để lo discovery, PKCE, token exchange/refresh, step-up auth. Hermes chỉ cắm 2 phần: `HermesTokenStorage` (persistence) và callback server loopback ephemeral.

Client identification theo spec MCP 2026-07-28: nếu auth server advertise `client_id_metadata_document_supported` → SDK dùng URL của Client ID Metadata Document (CIMD) do Hermes publish làm `client_id`; ngược lại fallback RFC 7591 dynamic client registration (spec 2026-07-28 đã deprecate DCR).

**Lưu state ở đâu** — `HermesTokenStorage` (`:456`), 4 file JSON dưới `HERMES_HOME/mcp-tokens/<server>.{json,client.json,meta.json,cimd-off}`: token, client info (từ DCR/CIMD), OAuth server metadata (endpoint discovery — cache lại để restart process không phải discovery lại, tránh fallback đoán `{server_url}/token` 404), và cờ "CIMD bị server từ chối ở đây". `set_tokens()` ghi thêm `expires_at` tuyệt đối (không chỉ `expires_in` tương đối) để restart process tính đúng TTL còn lại — nếu không, `is_token_valid()` báo sai True mãi (`:526-540`). Loopback callback server dùng cổng cache lại (`_cached_redirect_uri`) để redirect_uri ổn định qua các lần reconnect (nhiều auth server reject nếu redirect_uri thay đổi).

Không có consent UI riêng cho OAuth — luồng chuẩn: mở browser → user login → redirect vào `http://localhost:<port>/callback` → server ephemeral bắt code → đổi token → lưu như trên.

### 1.6 Hermes tự expose MCP server (Q6)

`mcp_serve.py` (1060 dòng, docstring `:1-27`): `hermes mcp serve` chạy MCP server qua stdio, expose **conversations của Hermes** (không phải tool code) cho client MCP khác (Claude Code, Cursor, Codex) — 9 tool khớp "OpenClaw's 9-tool MCP channel bridge": `conversations_list, conversation_get, messages_read, attachments_fetch, events_poll, events_wait, messages_send, permissions_list_open, permissions_respond`, cộng `channels_list`. Mục đích: biến Hermes thành **hub nhắn tin đa nền tảng** mà agent khác điều khiển được qua MCP — không phải để export tool nghiệp vụ. Đọc trực tiếp `SessionDB` (sqlite) và `state.db` cho session routing (không phải REST call vào Hermes runtime).

## 2. Observability

### 2.1 Event + policy phát/không phát (Q7)

3 dataclass duy nhất trong `agent/monitoring/events.py` (86 dòng, "content-free by construction"): `GatewayHealthEvent`, `GatewayDiagnosticEvent`, `CronExecutionEvent` — không có prompt/message/tool-arg nào trong schema. Policy gate không nằm ở `policy.py` (chỉ quản `install_id` pseudonymous, có thể rotate) mà ở **cấu trúc emitter** (`agent/monitoring/emitter.py`): `get_emitter()` khởi tạo `enabled=False`; **collection opt-in bằng chính hành động subscribe** — khi không ai gọi `subscribe()` (không OTLP endpoint nào cấu hình), `emit()` là no-op. `emit()` là hot-path invariant: `O(microseconds)`, không block I/O, không raise — hàng đợi bounded 10k, đầy thì drop event **cũ nhất** (newest-wins), dispatch qua 1 thread daemon, mỗi subscriber fail-isolated (subscriber lỗi/treo không ảnh hưởng subscriber khác hay hot path).

### 2.2 Redaction ở biên (Q8)

`agent/monitoring/redaction.py` (71 dòng): "một scrub, không mode, không cấu hình để làm yếu". `redact_for_export()` chạy 2 lớp — secret trước (bọc `agent/redact.py::redact_sensitive_text(force=True)` + regex Bearer/token-shape sk-/gh_/xox-, **fail CLOSED**: redactor lỗi → trả `[redaction-unavailable]`, KHÔNG bao giờ export raw), rồi PII (email/phone/UUID → `[email]/[phone]/[id]`). `otlp_exporter.py:_span_attrs` còn cắt string còn lại tối đa 500 ký tự làm defense-in-depth thứ 2.

### 2.3 OTLP export — cái gì thực sự hữu ích (Q9)

Có **2 module xuất OTLP tách biệt**, không phải 1:
- `otlp_exporter.py` (270 dòng): xuất **span-only** (mỗi event → 1 span khởi tạo và end ngay, không có duration thật) tên `hermes.<event_kind>` (`hermes.gateway_health`, `hermes.gateway_diagnostic`, `hermes.cron_execution`), attribute allowlist cứng theo `keep_by_kind` (`:139-148`) — event field nào không nằm trong danh sách này bị bỏ, không leak field lạ.
- `gateway_health_export.py` (643 dòng): runtime đầy hơn — có **metric provider** (không chỉ span) + **log streamer** riêng cho diagnostic events, snapshot thread định kỳ đọc `read_runtime_status()` + cron health.

Metric/counter cụ thể đáng port: `hermes.cron.scheduler.heartbeat_age_seconds`, `hermes.cron.scheduler.last_success_age_seconds`, `hermes.cron.scheduler.catch_up_occurrences`, `hermes.cron.jobs.enabled`, `hermes.cron.jobs.overdue`, `hermes.cron.jobs.running` (`agent/monitoring/cron_health.py:145-193`) — content-free (job identity bị hash `sha256:<24hex>`, `_job_key:38-40`), và `hermes.gateway.background_work` / `hermes.gateway.background_delegations` (`gateway_health_export.py:304-357`) — 2 metric TÁCH BIỆT có chủ đích: task-granular (N subagent fan-out = N) vs slot-granular (1 batch = 1), vì `active_agents` không đếm subagent nền — thiếu 2 metric này, dashboard fleet sẽ đọc nhầm "active_agents=0" trong khi subagent vẫn chạy.

### 2.4 Health check gateway — tín hiệu "khoẻ" (Q10)

Không có một boolean "healthy" toàn cục hay ngưỡng cứng toàn hệ thống. Thay vào đó: (a) state machine content-free — `_KNOWN_GATEWAY_STATES`/`_KNOWN_PLATFORM_STATES` (`gateway_health.py:31-39`, running/connected/ok/ready = healthy-ish, fatal/degraded/error/failed = unhealthy), lỗi được classify vào 7 nhóm cố định (`classify_gateway_error`: auth_failed/rate_limited/timeout/network_error/invalid_config/startup_failed/platform_fatal/unknown) — free-text lỗi KHÔNG BAO GIỜ export thẳng, luôn quy về nhãn cố định trước; (b) với cron, "khoẻ" là 2 số tuổi (`heartbeat_age_seconds`, `last_success_age_seconds`) + "overdue count" tính theo **grace period riêng của từng job's schedule** (`_compute_grace_seconds`, không phải ngưỡng global) — export số thô, để **operator's collector tự đặt ngưỡng alert**, Hermes không hard-code "quá X giây là chết".

### 2.5 Khác biệt cần phân biệt

`agent/stream_diag.py` (280 dòng) — debug cục bộ (không xuất telemetry ra ngoài), bắt header CF-Ray/x-openrouter-provider khi 1 stream chết giữa response, để post-mortem "Cloudflare edge nào, provider downstream nào, bao nhiêu byte trước khi rớt". `agent/insights.py` (1212 dòng) — phân tích usage/cost cục bộ từ SQLite cho user (không phải operator observability), có 6 issue cost-accounting đáng chú ý (xem mục 6). `agent/trace_upload.py` (404 dòng) — export **transcript đầy đủ** (không content-free) lên HuggingFace Hub dạng Claude-Code-JSONL, private-by-default, redact bắt buộc (không có `--no-redact` mà bỏ qua kiểm tra thất bại — raise `TraceRedactionError`).

## 3. Hook

### 3.1 `pre_llm_call` append user message, không ghi system prompt (Q11)

Bất biến này nằm ở `agent/turn_context.py:1231` (không phải trong 4 file hook được giao đọc, nhưng là site thực thi hook) và giải thích tại `agent/context_engine.py:248-251`: `select_context()` (host hook khác) **có thể** thay cả list message vì engine tự chịu trách nhiệm cache prefix của nó, còn `pre_llm_call` **luôn append vào user message** và **không bao giờ rewrite list** — lý do là giữ **prompt-cache prefix ổn định**. Nếu context từ hook (biến đổi mỗi turn tuỳ input) bị nhồi vào system prompt, mọi provider dùng prompt caching (Anthropic, OpenAI) sẽ cache-miss lại **toàn bộ system prompt** mỗi lần hook chạy — vừa tốn tiền vừa tăng latency đầu turn. Vì user message của turn hiện tại đằng nào cũng luôn mới (không nằm trong cache prefix), append vào đó không phá cache gì cả. Output oversized của 1 hook còn được spill ra đĩa (`hook_output_spill`, port từ `openai/codex#21069`) để 1 plugin runaway không tự phình prompt của mọi turn sau.

### 3.2 Consent cho shell hook (Q12)

`agent/shell_hooks.py` (1155 dòng). Consent theo **từng cặp (event, command)** — lưu tại `~/.hermes/shell-hooks-allowlist.json` (`allowlist_path()`), ghi atomic (`mkstemp` + `os.replace`), khoá race liên-process bằng `fcntl.flock` (POSIX) hoặc lock trong-process (non-POSIX). Không tự động approve: prompt TTY lần đầu mỗi (event, command) mới; các cờ bypass — `--accept-hooks`, `HERMES_ACCEPT_HOOKS=1`, `hooks_auto_accept: true`. `HERMES_SAFE_MODE=1` skip đăng ký hook (cùng cấp với plugin/MCP — coi hook là "user customization" cần tắt hết khi troubleshoot). Exit code 2 = block (Claude-Code/Cursor compatible) dù stdout không có JSON block. Fail semantics: **fail-open mặc định** (lỗi spawn/timeout/stdout không parse được → warning, không cản gì); event có thể opt-in `fail_closed: true` (dùng cho security-gating hook, ví dụ secret scanner) — chỉ hợp lệ với event nằm trong `_BLOCKING_EVENTS = {"pre_tool_call"}`.

Ngoài shell hook (chạy code local, cần consent), còn **outbound webhook** (`agent/outbound_webhooks.py`, 569 dòng) — POST ra URL người dùng tự khai trong config, **không cần consent prompt** vì "không thực thi code trên máy này", chỉ ký HMAC-SHA256 kiểu GitHub. Và `plugin_stream_hooks.py` (176 dòng) — observer bất đồng bộ cho streaming LLM output, mỗi hook 1 queue + 1 thread riêng, callback lỗi chỉ log warning.

## 4. Eval harness

**Lưu ý naming trùng**: `agent/battery.py` (131 dòng) mà đề bài liệt kê **KHÔNG PHẢI** eval harness — đó là bộ đọc **pin laptop** (`psutil.sensors_battery`) cho status bar CLI/TUI, không liên quan gì tới batch eval. Harness thật nằm ở `batch_runner.py`, `mini_swe_runner.py`, `agent/verify/*`.

### 4.1 Batch run — input/output/chấm điểm (Q13)

`batch_runner.py` (1330 dòng): input = dataset JSONL, mỗi dòng `{"prompt": ..., "image"/"docker_image": ..., "cwd": ...}` (tự pull/verify docker image trước khi tốn token nếu backend là Docker). `_process_single_prompt()` (`:244`) khởi `AIAgent` với toolset sample từ 1 "distribution" (`toolset_distributions.py`), chạy `agent.run_conversation()`, output = `{trajectory, tool_stats, reasoning_stats, completed, partial, api_calls, toolsets_used, metadata}`. **Không tự chấm đúng/sai** — đây là bộ sinh trajectory + thống kê tool-usage (đếm success/failure per tool qua `_extract_tool_stats`), không phải grading tự động; checkpoint (`checkpoint.json`, atomic write) cho phép `--resume` sau crash, ghi incremental sau mỗi batch. `mini_swe_runner.py` (732 dòng) là biến thể nhẹ hơn (tool surface tối giản, single-tool `terminal`), tương thích ngược với format trajectory của `batch_runner.py` — cả 2 đều KHÔNG chứa oracle/grader, chỉ sinh dữ liệu cho pipeline benchmark bên ngoài (SWE-bench-style) chấm điểm.

### 4.2 `verify/recipes.py` — "runnable verification recipe" (Q14)

`agent/verify/recipes.py` (477 dòng, port gần 1:1 từ `superagent-ai/grok-cli`). `Recipe` dataclass: `name, kind, bootstrap[], build[], test[], start, port, readiness_path, evidence[]` — tách biệt tường minh với `agent.coding_context.detect_project_facts` (facts rẻ, tức thời, đưa vào system-prompt) — recipe là "deep runtime recipe": nhận diện framework (Node lockfile+framework, Python Django/FastAPI/uv/poetry/pipenv, Go, Rust, Java Maven/Gradle, Makefile fallback, docker-compose) rồi suy ra lệnh bootstrap/build/test **và quan trọng nhất: start command + port + readiness_path** để `hermes verify` thực sự **boot app lên và chứng minh nó serve HTTP** — không chỉ chạy test đơn vị.

Thực thi ở `agent/verify/runner.py` (279 dòng): pha `bootstrap → build → test` chạy tuần tự (`PHASE_ORDER`), mỗi `PhaseResult.ok = exit_code==0 and not timed_out`; sau đó `_run_start_phase()` start app **background** rồi `_poll_readiness(url, timeout, interval=1.0)` — GET lặp lại `http://127.0.0.1:<port><readiness_path>` tới khi 2xx hoặc hết `DEFAULT_READY_TIMEOUT=60s`, rồi teardown process group. `agent/verify/environment.py` (75 dòng): recipe được cache tại `<project>/.hermes/environment.json` — nếu file này tồn tại và hợp lệ, nó **thắng** static detection mỗi lần (`load_or_detect`), user tự sửa tay được; file hỏng → fallback về detect lại, không raise.

## 5. Executor cách ly

### 5.1 ABC contract + 7 backend (Q15)

`tools/environments/base.py` (1478 dòng): `BaseEnvironment(ABC)` chỉ có **1 abstractmethod thật** — `cleanup()`; `_run_bash()` là "phải override nhưng không đánh dấu `@abstractmethod`" (raise `NotImplementedError` nếu quên). Model thống nhất: **spawn-per-call** — mỗi command là 1 `bash -c` process mới, session snapshot (env/function/alias) chụp 1 lần lúc init rồi re-source trước mỗi lệnh, CWD track qua stdout marker (remote) hoặc temp file (local). `execute()` ở base lo: source snapshot, CWD tracking, interrupt handling, timeout enforcement — **dùng chung cho cả 7 backend**, mỗi backend chỉ khác ở tầng spawn process thật.

7 backend: `local.py` (host trực tiếp), `docker.py` (container, security-hardened), `ssh.py` (remote qua SSH ControlMaster), `modal.py`/`managed_modal.py` (Modal Sandbox SDK), `daytona.py` (Daytona cloud SDK, sandbox pause/resume), `vercel_sandbox.py` (Vercel SDK, snapshot metadata phục hồi), `singularity.py` (Apptainer, `--containall --no-home`, overlay ghi). Phân loại theo cách đưa file vào sandbox: **bind-mount** (docker, singularity — filesystem host nhìn thấy trực tiếp, không cần sync) vs **remote sync** (ssh, modal, daytona, vercel_sandbox — dùng `file_sync.py` chung) vs **cùng máy** (local — không cần gì cả).

### 5.2 `file_sync.py` — chiến lược & giới hạn (Q16)

484 dòng, dùng chung cho ssh/modal/daytona (không phải docker/singularity — 2 backend này bind-mount). Detect thay đổi bằng **mtime+size** (không hash toàn bộ mỗi lần — `_file_mtime_key`), phát hiện xoá file, sync transactional. Upload/download qua tar (`tarfile`), không phải file-by-file. Giới hạn cứng: **2 GiB** (`_SYNC_BACK_MAX_BYTES`, `:131`) — refuse extract tar vượt ngưỡng này (chống 1 sandbox tự phình disk rồi đẩy hết ngược về host làm OOM); sync-back retry tối đa 3 lần (`_SYNC_BACK_MAX_RETRIES`). File credential/skill/cache được remap path (`/root/.hermes` → home thật của remote user, ví dụ `/home/daytona`).

### 5.3 `docker.py` — mạng, mount, lifecycle, dọn dẹp (Q17)

2050 dòng. **Mạng**: mặc định `network=True` (container có mạng); `network=False` → `--network=none` (air-gapped), có kiểm tra double-check network mode thực tế của container khi reuse để không "âm thầm" cho 1 container cũ networked chạy dưới config mới yêu cầu air-gapped (`:1412-1429`). **Security**: `--cap-drop ALL` + add lại đúng 3 cap cần cho package manager/privilege-drop (`DAC_OVERRIDE, CHOWN, FOWNER`), `--security-opt no-new-privileges`, `--pids-limit 256` (chỉ áp khi cgroup `pids` controller có sẵn — tránh lỗi trên LXC không có delegation), `--tmpfs /tmp:rw,nosuid,size=512m` + `/var/tmp` riêng, `--shm-size 1g` (default Docker 64MB quá nhỏ, làm Chromium/PyTorch DataLoader crash — `#2748`). **Mount**: bind-mount workspace (host cwd → `/workspace`), credential files (OAuth token...), skill dirs, cache dirs — tất cả qua host path thật, không copy.

**Lifecycle/cleanup** (`cleanup()`, `:1918`): mặc định **persist-mode** — container sống xuyên suốt process Hermes (không stop khi `/quit`), vì "1 container dài hạn chia sẻ session" nghĩa là background process (`npm run dev`, watcher) phải sống sót; opt-out mode thì stop+rm mỗi lần cleanup như cũ. Rác của persist-mode được dọn bởi `reap_orphan_containers()` chạy lúc Hermes khởi động: container có label mà không ai đụng tới trong `2 × lifetime_seconds` bị `docker rm -f` — cover trường hợp SIGKILL/OOM/laptop gập màn hình bỏ đi. Cleanup thật chạy trên daemon thread với `subprocess.run` có bound (không phải `Popen(...&)` race — `#33645`), atexit hook đợi tối đa 15s cho thread này.

## 6. Bài học từ số hiệu issue/PR (docstring + comment quan trọng)

Bảng dưới liệt kê MỌI số hiệu tìm thấy trong các file được giao đọc, gộp theo file. "Nguồn" ghi repo gốc khi comment ghi rõ port từ đâu (không phải bug riêng của Hermes).

### `tools/mcp_tool.py` (43 số)

| # | file:line | Bài học 1 dòng |
|---|---|---|
| #62212 | 2393,2835,2937,3164,3533,3598,3645,3847,5835 | Handshake xong ≠ khoẻ; phải "proven" (sống sót 1 keepalive/1 tool call) mới reset budget reconnect, tránh respawn vô hạn (case thực: 6212 lần/63h). |
| #65673 | 3931 | Lỗi permanent (bad command/401/403) phải park ngay, không đốt backoff ladder rồi spam N warning giống nhau. |
| #66092 | 3345 | Backoff+park mặc định biến 1 glitch sub-giây (POST vẫn khoẻ) thành outage nhiều phút — cần đường riêng cho lỗi thoáng qua. |
| #9930 | 3357,3901 | `CancelledError` kế thừa `BaseException` (Py3.11+) — `except Exception` rộng KHÔNG bắt được, phải re-raise tường minh hoặc task cancel không propagate. |
| #59349 | 3147,3520 | Handshake không có timeout riêng → hang vô hạn, `finally` cleanup không chạy → leak fd/pidfd tới khi EMFILE. |
| #57228/#57355 | 3085 | Không reap orphan trước khi spawn lại → mỗi retry đẻ thêm 1 cặp process zombie. |
| #56832 | 4218,5640,5722,6270,6739,6973,7027,7257,7294 | Lazy MCP startup (đọc cache đĩa, không spawn) cần track riêng "server nào chưa từng connect thật" để không báo failed nhầm. |
| #56059/#56060/#56072/#56511 | 129,134,137,142,5908,5930 | Cap kết quả text MCP ở 2M ký tự PHẢI nằm trên ngưỡng spillover (50K) — nếu cap dưới ngưỡng spillover, dữ liệu lớn hợp lệ bị cắt trước khi spillover kịp lưu full ra đĩa. |
| #16788 | 3160,4080,5805 | Sau khi phục hồi kết nối phải xoá breaker-state cũ, nếu không lần gọi đầu sau recovery bị chặn oan bởi consecutive-failure count cũ. |
| #62771 | 4995 | Nhiều process Hermes (gateway+CLI+TUI) cùng discover MCP song song → cần file lock advisory liên-process. |
| #29184 | 162,166,3027 | OSV malware preflight (HTTPS blocking call) phải bound bằng timeout wall-clock RIÊNG — timeout của lib không chặn được SSL handshake treo. |
| #47134 | 8061 | `killpg` khi MCP child share process-group với gateway → giết luôn gateway; phải kill theo pid khi phát hiện trùng group. |
| #60197 | 8190 | Đóng event loop khi còn task suspended → GC finalizer resume coroutine trên loop đã closed → "Event loop is closed". |
| #17915/#10848 | 5866,5867 | 2 nguồn cộng đồng cùng fix "image block bị silently drop" nhưng đều quá cũ để cherry-pick thẳng — phải distill lại logic. |
| #33533 | 6447,6650 | Convention `mcp__server__tool` dùng chung với Claude Code/Codex/OpenCode — không tự đặt format riêng, giữ để model nhận diện tốt hơn. |
| #690 | 6774 | Spec include/exclude tool theo tên, mở rộng thêm glob. |
| #87112 | 6877 | Tool tự nhiên của server và utility tool tự sinh trùng tên → giữ native, bỏ utility. |
| #34529 | 538 | Map MCP log level (RFC 5424) sang Python logging — port từ opencode. |
| #31271 | 2458 | Server không hỗ trợ `tools/list` (resource-only) từng làm chết cả kết nối lúc discovery — phải coi -32601 là "không có", không phải lỗi. |
| #18051 | 2435 | Lưu `initialize_result` để code sau kiểm tra capability thật của server, không giả định method nào cũng được hỗ trợ. |
| #25019 | 1335,3768 | Validate URL 1 lần lúc startup — fail fast, không đốt reconnect-backoff loop vì lỗi cấu hình tĩnh (typo URL). |
| #4651 | 6297 | `required` array phải được prune theo `properties` thật — Gemini 400 "property is not defined" nếu không. |
| #4897 | 6292 | Node object thiếu `type`/`properties` phải được vá đệ quy trước khi gửi cho model. |
| #4977 | 1022 | `/usr/local/bin` là nơi Node thường nằm trên Linux from-source + base image Docker — thêm vào candidate path resolve command. |
| #50028 | 812 | Không phải server nào cũng trả lỗi `-32601` chuẩn — một số trả string "Unknown method" khiến keepalive fallback không khớp, reconnect-loop mãi. |
| #50170 | 7272 | Server bị deregister tools thì không còn đường nào signal reconnect — phải chủ động "nudge" thay vì chờ tới self-probe interval. |
| #50394 | 4239,7263,7362,7928,7953,7975 | Thiếu cooldown sau lỗi kết nối → MỌI worker session (mỗi vài giây) đều thấy "chưa kết nối" và respawn lại — restart storm. |
| #5544 | 7890 | Toolset "context_engine" trống có chủ đích — tool chỉ tồn tại qua append này, phải tôn trọng cùng gate `enabled_toolsets`. |
| #56536 | 991 | `shutil.which(path=...)` đọc PATHEXT của process cha, không phải env config — phải retry thủ công với PATHEXT từ config. |
| #57129 | 4085 | Server bị park (mất hết tool) không còn ai gọi được để trigger reconnect — cần vòng self-probe theo thời gian cố định. |
| #58862 | 7248 | Nhiều entry-point gọi `discover_mcp_tools()` cùng lúc → cần set `_server_connecting` chống double-spawn. |
| #5981 | 3468 | Server SSE gửi event cách nhau vài phút — timeout đọc 60s quá ngắn, phải khớp 300s như path Streamable HTTP. |
| #26892 | 5796 | Transport đang swap session mới (async) — đợi ngắn trước khi coi là fail, tránh đốt oan 1 strike circuit-breaker. |
| #2596/#2600 | 5918,1084 | Port 2 fix nhỏ từ `MoonshotAI/kimi-code`: expose `_meta` server-level, và không nhầm namespace hợp lệ (`com.example.mcp/...`) là reserved word. |

### `tools/mcp_oauth.py` + `mcp_oauth_manager.py` (13 số, 1 trùng)

| # | file:line | Bài học 1 dòng |
|---|---|---|
| #22161/#44590 | mcp_oauth.py:220,982,985 | TOCTOU giữa chọn cổng free và bind HTTPServer thật — phải giữ socket đã probe, không đóng rồi mở lại; `allow_reuse_address` phải set TRƯỚC constructor bind. |
| #34260/#44588 | 902,930,1928,804 | Nhiều OAuth flow chạy đồng thời (nhiều MCP server) không được share state global qua port — dùng closure per-flow, không module-level `_oauth_port`. |
| #5344 | 1558 | Global `_oauth_port` là root cause của port-collision khi 2 flow OAuth chạy cùng lúc — thay bằng ContextVar. |
| #35927 | 162,359,375 | `asyncio.run_coroutine_threadsafe` copy calling-context, không copy `threading.local` — phải dùng `contextvars.ContextVar` để cờ interactive-enabled xuyên qua boundary thread. |
| #19673 | 422 | `chmod` sau khi tạo file mở TOCTOU window — file tạm ngắn hạn kế thừa umask world-readable, lộ OAuth token. |
| #25821 | 427 | `secure_parent_dir` phải tự chối chmod thư mục root/top-level để tránh phá quyền hệ thống khi gọi nhầm. |
| #12983 | 1758 | Đổi OAuth client → phải invalidate token cũ NGAY, so sánh identity trước khi ghi đè — port từ `cline/cline#12983`. |
| #57836 | 342,833,969 | Câu hướng dẫn "next step" khi OAuth non-interactive phải viết 1 chỗ dùng chung, không lặp lại rải rác. |
| #75576 | 1185,804(oauth_manager) | Một số auth server/WAF chặn User-Agent mặc định của httpx — phải cho phép stamp UA riêng lên request token-endpoint. |
| #24317 | oauth_manager.py:26 | Cùng lớp bug với Claude Code's `invalidateOAuthCacheIfDiskChanged` — token bị refresh bởi process khác (CLI) không được cache stale ở process khác (gateway). |
| #36767 | oauth_manager.py:424 | Token-endpoint reject có thể tự phát hiện (auto-detectable) → tự xoá client info để trigger DCR lại; case "Redirect URI Mismatch" thì không có signal HTTP, phải đợi user reset tay. |
| #11383 | oauth_manager.py:531 | Generator 2 chiều (`asend`) — bridge phải forward đúng giá trị nhận được vào generator trong, không phá contract bidirectional. |

### `mcp_serve.py` (3 số)

| #9006 | 106 | Đọc routing metadata trực tiếp từ `state.db` thay vì phụ thuộc file `sessions.json` song song — giảm 1 nguồn race. |
| #8925 | 546 | Conversation mới + message đầu tiên nằm CÙNG 1 file/mtime — tránh race "drop mất conversation mới tạo" giữa 2 file riêng biệt cũ. |
| #13414 | 362,484 | Snapshot lịch sử hiện có TRƯỚC khi bắt đầu poll loop — tránh replay message cũ như event mới lúc mới start server. |

### Executor + hook (đã trích trong mục 3, 5) — liệt kê nốt số còn lại

`tools/environments/base.py`: #8340 (pipe từ grandchild giữ mở qua `setsid ... & disown` → tool hang vô hạn — bash chết mà pipe vẫn mở); #15459 (bash 3.2/Homebrew leak `declare -x` ra stdout khi source snapshot, phải redirect /dev/null); #38249 (atomic snapshot write bằng `mv` để tránh source() đọc file nửa-ghi); #63255 (mọi backend kể cả local đều đọc CWD qua stdout marker, không cần temp file riêng nữa); #64435 (bounded head/tail capture chỉ cho path foreground, path nội bộ vẫn full-fidelity); #71296 (whitelist prefix biến môi trường bridge phải khớp `gateway.session_context._VAR_MAP`, test làm contract Python-side); #76502 (activity callback thread-local không đọc lại được từ thread mới spawn — cần accessor public).

`tools/environments/docker.py`: #20561 (container "Created" nhưng chưa chạy leak vĩnh viễn nếu reaper chỉ lọc status=exited — #7439 là case cụ thể của bug này); #2748 (shm-size 64MB default vỡ Chromium/PyTorch); #33645 (cleanup qua `Popen(...&)` race — chuyển sang `subprocess.run` bounded trên thread riêng); #34628 (image dùng s6-init phải bỏ `--init` và mount `/run` exec, không noexec); #36266 ("No such container" cần logic recovery riêng khi container biến mất ngoài ý Hermes).

`tools/environments/local.py`: #17558/#65583 (cwd/`/root` cấu hình bị xoá hoặc leak quyền từ session khác vào cron job không-root — mọi lệnh sau đó fail vĩnh viễn); #23473 (`.venv` marker bị strip để tránh cross-project clobber môi trường Hermes chính nó); #31420 (Windows subprocess cần `PYTHONUTF8=1` ép buộc); #32314 (blocklist biến môi trường AWS SDK KHÔNG được phép re-allow lại — security bulletin GHSA-rhgp-j443-p4rf); #42203 (chỉ 6 shell họ POSIX-sh được dùng cú pháp `-lic`, còn lại fallback bash); #55878 (không được strip biến path credential Anthropic — nếu không CLI con rơi vào Keychain rồi tự logout user thật); #56147/#56700 (Windows MSYS path-conversion cần opt-out bằng 2 biến môi trường khác nhau tuỳ shim); #74817/#75018 (`PYTHONHOME` là chất gây ô nhiễm chéo phiên bản Python con — phải strip, chỉ giữ path theo "provenance" không theo heuristic phiên bản).

`tools/environments/ssh.py`: #73927 (Windows OpenSSH không có ControlMaster qua Unix socket — phải tắt multiplexing trên Windows, mỗi lệnh trả giá kết nối mới).

`agent/shell_hooks.py`: #37527 (hook timeout phải kill cả process tree, trừ tiến trình tự detach thành công); #60036/#60267/#64178/#64188 (1 chuỗi fix nối tiếp nhau cho cùng 1 bug: reload plugin force=True xoá luôn hook config-owned — vá đi vá lại nhiều PR mới ổn); #78293 (Windows: `shlex.split` ăn mất backslash trong path, cần splitter riêng).

`agent/insights.py`: #23270/#58592/#9979 (breakdown per-model phải cộng cả usage phụ — vision/compression/title — nếu không tổng "hermes insights" bị thiếu); #51607 (model đổi giữa session qua `/model` phải phân bổ token/cost theo TỪNG model đã dùng, không dồn hết cho model đầu); #77223/#79220 (chi phí dưới 1 cent hiển thị "~$0.00" là dishonest — phải format 4 chữ số thập phân).

## 7. Port được gì cho Stock_Massive

Stock_Massive đã đúng ở nhiều điểm mà Hermes phải vá lại bằng issue thật:

- **ADR-0019 (executor networkless, chỉ chia sẻ named-volume queue, không Docker socket, không source tree)** — đúng hướng và **an toàn hơn** cách Hermes làm: Hermes chấp nhận rủi ro lớn hơn (bind-mount source thật, `--cap-add DAC_OVERRIDE/CHOWN/FOWNER`, network bật mặc định) để đổi lấy trải nghiệm dev tương tác — hợp lý cho 1 coding agent, KHÔNG hợp lý cho executor sinh evidence tài chính. Giữ nguyên ADR-0019; không cần "học" gì từ `docker.py` ở phần network/mount.
- **Từ `agent/verify/recipes.py` + `runner.py`**: nếu tương lai Stock_Massive cần tool tự-verify sau khi sinh code (không phải bây giờ), pattern "Recipe tách biệt static facts (đã có trong `docs/`) vs deep runtime recipe (bootstrap→build→test→start→poll readiness)" đáng tham khảo cho 1 CI/dev-loop nội bộ — không liên quan tới executor cách ly hiện có.
- **Từ `tools/environments/base.py` — ABC 1-abstractmethod**: nếu Stock_Massive executor cần thêm backend (hiện chỉ 1 dạng container), pattern "base lo hết lifecycle chung (timeout, interrupt, cwd), backend chỉ override điểm spawn" giảm trùng lặp — nhưng hiện `executor_enabled` chỉ có 1 backend nên chưa cần.
- **Từ `agent/monitoring/emitter.py` + `events.py` + `redaction.py`**: đây là phần đáng port THẬT nhất. `ops.py` (443 dòng) hiện chỉ đếm counter nội bộ (`grounding_failed`, `gateway_timeout`, `route_error`, `downgraded_blocks`, `answer_kinds`) — không có đường xuất OTLP, không redaction tầng export. Nếu tương lai cần xuất metric ra Grafana/Datadog: copy nguyên khối "content-free dataclass event + emitter hot-path never-block/never-raise + redact_for_export fail-closed + subscribe-to-enable" — 3 file `events.py`+`emitter.py`+`redaction.py` (~370 dòng) là 1 pattern độc lập, không kéo theo dependency OTel SDK nếu chưa cần (`otlp_exporter.py` optional extra, lazy-installed).
- **Từ `agent/monitoring/policy.py::ensure_install_id`**: pattern install-id pseudonymous rotatable — nếu Stock_Massive cần phân biệt instance trên dashboard fleet (nhiều worktree/deployment) mà không gắn identity thật, đây là 12 dòng code đáng chép thẳng.
- **Từ MCP naming**: `mcp_prefixed_tool_name()` (`mcp__server__tool`, double underscore) — Stock_Massive's `mcp/registry.py` (221 dòng, ghi tên server ổn định vào tên tool + Evidence Manifest) nên kiểm tra có cùng convention `mcp__` với Claude Code/Codex/OpenCode hay không; nếu registry hiện dùng prefix khác, xét đổi để tương thích khi model được train trên convention chuẩn này (cần đọc `registry.py` để xác nhận — không có trong scope đọc-chỉ của task này).
- **Từ `mcp_schema_cache.py`**: nếu `mcp_enabled` được bật trong tương lai (hiện tắt), pattern "cache manifest tool trên đĩa theo fingerprint(config) + TTL theo SEP-2549, để lazy-register mà không spawn subprocess lúc dashboard khởi động" giải quyết đúng vấn đề "một bộ chấm hồi quy phải pin MCP off vì availability của server có thể xê dịch input" — cache lazy này KHÔNG che được vấn đề đó (input vẫn phụ thuộc server thật lúc gọi), nhưng giúp UI/registry hiển thị tool list nhanh mà không tốn network mỗi lần mở app.
- **`batch_runner.py` không phải một bộ chấm**: `batch_runner.py`/`mini_swe_runner.py` KHÔNG có oracle/grader — chỉ sinh trajectory, chấm điểm nằm ngoài hoàn toàn (phải nối vào 1 harness khác). Nên nếu Stock_Massive muốn một cổng hồi quy trước merge, port `batch_runner.py` không đủ: phần đắt là bộ chấm, và phần đó không có ở đây.

## 8. Không port gì + vì sao

- **KHÔNG port shell hooks / outbound webhooks / MCP-as-plugin-hook system**: Stock_Massive hiện KHÔNG có hệ hook nào, và kiến trúc hiện tại (API phục vụ dữ liệu, không phải coding agent tương tác) không có "tool call" nào cần user customize qua shell script. Thêm hệ hook (consent, allowlist, wire protocol JSON stdin/stdout) là scope creep không ai yêu cầu — vi phạm YAGNI. Nếu tương lai Stock_Massive có agent loop tương tác thật (không chỉ recommendation validator), xem lại.
- **KHÔNG port OAuth 2.1 MCP client đầy đủ (browser flow, loopback callback server)**: `apps/api/src/agent/mcp/client.py` (141 dòng) hiện assume server MCP đã có cách auth riêng (hoặc chưa cần OAuth vì `mcp_enabled` mặc định tắt). Xây browser-based OAuth callback server là hạ tầng nặng (1956 dòng ở Hermes) cho use-case chưa xuất hiện.
- **KHÔNG port 7-backend executor (Modal/Daytona/Vercel Sandbox/Singularity/SSH)**: ADR-0011 đã từ chối sandboxed code execution ở v1 một cách tường minh; ADR-0019 chọn đúng 1 backend networkless. Thêm nhiều backend cloud-sandbox là giải pháp cho vấn đề Stock_Massive không có (chạy code người dùng gửi lên) — Hermes cần đa backend vì nó LÀ 1 coding agent chạy trên nhiều môi trường người dùng.
- **KHÔNG port `mcp_stdio_watchdog.py` (parent-death watchdog cho subprocess MCP)**: chỉ có giá trị khi Hermes spawn subprocess MCP dài hạn trên máy người dùng (đa dạng OS, không kiểm soát được uptime). Stock_Massive's executor chạy trong container do mình kiểm soát lifecycle (ADR-0019), không spawn subprocess MCP con qua stdio.
- **KHÔNG port `agent/insights.py`/`agent/trace_upload.py`**: đây là tính năng UX cho end-user vận hành CLI cá nhân (cost tracking, chia sẻ transcript debug) — không khớp mô hình sản phẩm Stock_Massive (dịch vụ dữ liệu, không phải agent CLI cá nhân của từng người dùng).
- **KHÔNG port toàn bộ `otlp_exporter.py`/`gateway_health_export.py` (metric+log+span provider đầy đủ)**: 2 file này (~900 dòng) kéo theo `opentelemetry-sdk` optional dependency và giả định mô hình "gateway đa nền tảng nhắn tin" (platform_count, fatal_platform_count) không tồn tại ở Stock_Massive. Chỉ nên port PATTERN (mục 7), không port CODE.

## 9. Câu hỏi chưa giải quyết

- Chưa đọc `apps/api/src/agent/mcp/registry.py` và `client.py` thật trong task này (ngoài scope chỉ-đọc Hermes) để xác nhận convention tên tool hiện tại của Stock_Massive có xung đột với `mcp__server__tool` hay không — cần đọc riêng nếu quyết định đổi.
- `mcp_dashboard_oauth.py` (145 dòng) và `setup_mcp_tool.py` (134 dòng) chỉ được lướt qua bằng grep issue-number (không có số hiệu nào) — chưa đọc kỹ nội dung, có thể còn context về UX cài đặt MCP không nằm trong 17 câu hỏi.
- `tools/environments/modal.py`/`managed_modal.py`/`modal_utils.py`/`daytona.py`/`vercel_sandbox.py`/`singularity.py` chỉ đọc header — chưa xác nhận chi tiết lifecycle mount/network của 4 backend cloud này (không cần thiết cho phần "không port" ở mục 8, nhưng nếu sau này Stock_Massive cân nhắc cloud sandbox, cần đọc kỹ hơn).
- Không xác nhận được bằng test/runtime thật (chỉ đọc code) — mọi nhận định về hành vi (ví dụ "respawn 6212 lần/63h") lấy nguyên văn từ comment tác giả Hermes, không tự verify lại.

Status: DONE
Summary: Đọc đầy đủ 5 phần (MCP/Observability/Hook/Eval/Executor) của Hermes Agent qua code thật, trích ~98 số hiệu issue/PR kèm bài học, phát hiện `agent/battery.py` không phải eval harness (là bộ đọc pin), và map cụ thể phần nào nên/không nên port sang Stock_Massive.
Concerns/Blockers: Không đọc `apps/api/src/agent/mcp/registry.py`/`client.py` thật trong task này (out of scope chỉ-đọc Hermes) nên khuyến nghị đổi tên tool MCP ở mục 7 chưa được verify chéo với code Stock_Massive hiện tại.
