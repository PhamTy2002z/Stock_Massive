---
title: "Red team — bảo mật dữ liệu & tính trung thực UX"
target: plans/260827-2325-evidence-led-chat-surface/
date: 2026-08-27
scope: đọc-only, 7 trục tấn công
sot: docs/Harness/{investment-intelligence-contract,quality-safety-and-operations,target-architecture}.md
---

# Red team: Evidence-Led Chat Surface

Không có phần khen. Mỗi phát hiện: (a) plan nói gì · (b) bằng chứng ngược ·
(c) sửa cụ thể. Mọi `path:line` đo trên worktree `feat/study-canvas-runtime`
lúc 2026-08-27.

---

## BLOCKER

### B1 — Whitelist export chứa `content`, nên nó fail-OPEN cho đúng hai thứ phase 11 hứa loại

**(a) Plan nói gì.** `phase-11:§Architecture`:

```python
EXPORT_MESSAGE_FIELDS = frozenset({"role", "content", "created_at"})
```

kèm "Không xuất reasoning. `content.delta` có `kind = answer | thought`. Chỉ
`answer` vào export" và success criterion "`kind = thought` **không** có trong
export — test khẳng định".

**(b) Bằng chứng ngược.** `content` là **JSONB tự do**, và shape thật của nó
được quyết ở `apps/api/src/agent/turns.py:248-259`:

```python
return {
    "text": text,                 # toàn bộ prose, gồm narration
    "answer": text if answer is None else answer,
    "thoughts": [dict(t) for t in thoughts],       # reasoning nội bộ
    "tool_calls": [dict(c) for c in tool_calls],   # as_wire(): results[] của web
    "canvases": [...], "status": ..., "elapsed_ms": ...,
}
```

Whitelist field-level cho `content` đi qua **cả cây con**: `thoughts` (đúng cái
phase hứa không xuất), `text` (bản chưa tách narration), và
`tool_calls[].results[]` — bốn chuỗi lấy từ trang ngoài
(`apps/api/src/agent/messages.py:421-428`: `title`, `url` ≤2048 ký tự,
`source`, `snippet`). `frozenset` chặn cột **hàng**, không chặn khoá **JSON**.

Thêm nữa: `kind = answer|thought` chỉ tồn tại trên event SSE `content.delta`,
**không** tồn tại trong store. Store tách bằng hai khoá `answer` và `thoughts`.
Nên test "`kind = thought` không có trong export" là test **rỗng**: nó pass dù
serializer xuất trọn `thoughts`, vì chuỗi `"thought"` không phải khoá nào cả.
Một cổng cứng không kiểm gì.

Ngoài `content`, `EXPORT_TOOL_FIELDS = {"name","outcome","as_of","health"}` cũng
không map được: `agent_tool_call` **không có** cột `as_of` hay `health`
(`apps/api/src/alpha/models.py:157-205`). Lấy chúng buộc phải chọc vào `result`
JSONB, và `result` do `loop.py:1558-1563` ghi là `{"text": stored, "chars",
"dispatched"}` — `text` là **nguyên văn kết quả tool** đã trim, tức nội dung
nguồn ngoài. Chọc vào đó là mở đúng cái cửa whitelist định đóng.

**(c) Sửa.** Whitelist phải **đệ quy theo đường dẫn**, không theo tên cột:

- Khai `EXPORT_CONTENT_PATHS = frozenset({"answer", "canvases", "status"})` và
  serializer chỉ đọc `content[k] for k in EXPORT_CONTENT_PATHS`; `text`,
  `thoughts`, `tool_calls`, `elapsed_ms` **không** có tên trong set.
- Với `canvases`, whitelist tiếp cấp hai (`id`, `title`, `as_of`) — hiện
  `canvases` là `dict` tự do từ `canvas_of`.
- Đổi test: dựng `content` có khoá `thoughts=[{"text":"SECRET"}]` **và** khoá lạ
  `secret_internal_note`, khẳng định **cả hai** không có trong output. Test theo
  `kind` phải xoá — nó kiểm một vốn từ không tồn tại ở tầng store.
- `as_of`/`health` cho tool call: xem B3 — hiện không có nguồn hợp lệ để lấy.
- Bổ sung một test "shape drift": so `set(assistant_message(...).keys())` với
  một hằng số đã khai; thêm khoá vào `turns.py` mà không cập nhật hằng số → đỏ.
  Không có test này thì `turns.py` là đường lách vĩnh viễn.

---

### B2 — Spine "số thật" của phase 03 đọc một bảng **không còn writer nào**

**(a) Plan nói gì.** `phase-03`: "`trading_day.py` có `latest_trading_day` +
`trading_days_before/between` — đủ để biết hôm nay có phiên hay không";
`sessionsBehind` = số phiên giữa `latest` và `latestClosedSession`. Nguyên tắc
plan: "Session state và độ mới dữ liệu đến từ store thật. Không có dữ liệu →
**không render gì**, không bao giờ render số giả."

**(b) Bằng chứng ngược.** `apps/api/src/stocks/trading_day.py:43-54`:

```python
select(func.max(ProviderSnapshot.effective_at)).where(
    ProviderSnapshot.capability == _MARKET
)
```

`grep -rn ProviderSnapshot src/` trả về **chỉ reader**:
`trading_day.py`, `studies/reads_fundamental.py` (capability FUNDAMENTAL),
`stocks/models.py` (định nghĩa). Không một writer capability `MARKET` nào còn
tồn tại — CLAUDE.md §"Không còn tồn tại" đã rip `stocks/collector*`,
`intraday_collector`, `market_index`, `warmup`, `backfill`. Bản thân docstring
`bar_daily` xác nhận sự phân đôi này:
`apps/api/src/stocks/models.py:414-417` — *"a Trading Day is derived from MARKET
… here nothing is derived from the table"*.

Hệ quả đo được, không suy đoán:

1. `latestClosedSession` **đóng băng** ở ngày cuối mà DB còn giữ (trước
   2026-08-25) hoặc `None`.
2. `sessionsBehind` = trading-days giữa `max(bar_daily.trading_day)` (được
   `backfill_daily.py` ghi, còn sống) và một mốc đóng băng → **âm**, hoặc 0 vì
   `trading_days_between` cũng đọc cùng bảng chết.
3. Chip phase 04 và `sessionsBehind` của phase 10 **render một con số sai một
   cách tự tin**. Acceptance #2 của plan ("tắt endpoint → chip biến mất") không
   bắt được ca này: endpoint vẫn 200, vẫn có số, số đó vô nghĩa.

Đây đúng là "badge giả kiểu khác" mà brief nghi ngờ, và nó tệ hơn badge cứng:
badge cứng ai cũng nhận ra, số này thì không.

**(c) Sửa.** Trước khi viết một dòng nào của phase 03:

- Chạy `SELECT capability, max(effective_at), count(*) FROM provider_snapshots
  GROUP BY 1` trên DB thật và **ghi kết quả vào phase**. Nếu MARKET đóng băng →
  phase 03 bị **BLOCKED**, không phải "pending".
- Chọn một trong hai, tường minh: (i) định nghĩa lại `latestClosedSession` từ
  `max(bar_daily.trading_day) WHERE series='equity'` — cùng bảng với `asOf`, nên
  `sessionsBehind` luôn ≥0 và có nghĩa; hoặc (ii) thêm writer MARKET (nằm ngoài
  freeze amendment hiện tại, phải mở tên file).
- Bất kể chọn gì: `sessionsBehind` phải `max(0, …)` **và** hai số phải đến từ
  **một** bảng. Thêm acceptance: "test khẳng định `latestClosedSession` và
  `asOf` đọc cùng một bảng".
- Thêm một acceptance âm: "store không có dữ liệu **mới hơn N phiên** → nhánh
  đó trả `null`", để mốc đóng băng biến thành `null` chứ không thành số.

---

### B3 — Phase 10 aggregate một `Provenance` **không được lưu**, và trộn nguồn ngoài với store

**(a) Plan nói gì.** "`agent_tool_call` đã lưu kết quả mỗi tool call, và Study
đã có vốn từ `Provenance{as_of, health, sessions_used}`". Acceptance #7 toàn
plan: "as-of/freshness/health trên answer bằng đúng giá trị trong `Provenance`
của tool call sinh ra nó". Phase 10 khai `Alembic: —` (không migration).

**(b) Bằng chứng ngược.**

- `agent_tool_call` không có cột `as_of`, `health`, `sessions_used`
  (`src/alpha/models.py:157-205`).
- `result` JSONB do `src/agent/loop.py:1558-1563` ghi là `{"text", "chars",
  "dispatched"}` — **không có** provenance.
- `Provenance` chỉ được persist ở `agent_artifact.provenance`
  (`src/studies/runner.py:117`), tức chỉ cho Study/canvas; `get_field` trả
  `health` trong payload runtime (`src/agent/tools/signals.py:550`) và payload
  đó không vào trace row.
- Nên acceptance #7 ("test so trực tiếp, không so qua chuỗi hiển thị") **không
  thực hiện được** mà không thêm cột — đúng cái phase 10 tuyên bố không làm.

Trục thứ hai, nặng hơn: aggregate đếm `sourceCount` = "số tool call có số thật"
**không phân biệt store và web**. Tool web không có `as_of` và không có `health`
nào cả. Một dòng "3 nguồn · đến phiên 26/08" gộp hai trang web và một store read
thành một mức tin cậy duy nhất. Điều đó phá:

- CLAUDE.md §Quy ước: "tách hai khối bằng chứng" (đã ghim trong prompt
  `PROMPT_VERSION` 2.7.0);
- `quality-safety-and-operations.md:247` §Security model — hàng
  `External content → model | untrusted | delimit, provenance, injection scan`;
- chính `as_wire()` đã cẩn thận giữ khoá `kind = external|store`
  (`src/agent/messages.py:218-220`) *"so a surface cannot draw a read of this
  system's own store the way it draws a stranger's page — the distinction the
  whole evidence boundary rests on"*. Phase 10 xoá đúng phân biệt đó ở tầng
  tóm tắt.

**(c) Sửa.**

- Aggregate **trong turn, từ payload runtime** (loop còn giữ `Provenance` của
  từng call), không từ `agent_tool_call`. Sửa câu "Tính từ đâu" trong phase.
- Nếu vẫn muốn acceptance #7 so với trace: phải thêm cột/khoá provenance vào
  trace row → phase 10 **có** migration, và nó phải vào revision phase 08 (luật
  một-revision của plan). Quyết định này thuộc phase 10, không được để trống.
- Tách hai con số: `store: {sourceCount, asOf, health}` và
  `external: {sourceCount}` — nguồn ngoài **không có** `asOf`/`health`, và nói
  nó có là nói dối. FE render hai cụm, đúng luật prompt.
- Dùng lại `_merged_provenance` (`src/agent/tools/studies.py:628`) thay vì viết
  lại min/worst lần thứ hai.

---

### B4 — Export là bề mặt xuất dữ liệu **không audit, không retention, không phân loại capability**

**(a) Plan nói gì.** `phase-11`: "Không bảng mới, không migration, không route
công khai", "Endpoint đọc, không tạo tài nguyên", "`GET` vì nó không tạo gì và
**không có side effect**". Rollback: "không tài nguyên tồn tại ngoài request".

**(b) Bằng chứng ngược.** SOT `quality-safety-and-operations.md:227` §Trace and
privacy đòi tường minh, cho artifact:

> - explicit purpose và access scope;
> - retention/expiry và deletion path;
> - **audit ai đọc/export artifact**;

và §Security model hàng cuối: `Telemetry → operator | content-light |
redaction, access control **and retention**`. §Autonomy contract:264 (cùng file
contract:177-181): *"Capability mới phải được phân loại read/write,
external/internal, data sensitivity và approval requirement tại registration."*

Export **là** một capability mới với data sensitivity cao nhất trong hệ (toàn bộ
nghiên cứu đầu tư của một user, dạng plaintext, rời khỏi mọi biên kiểm soát).
Plan không có: audit row, rate limit, purpose declaration, retention. Câu "không
có side effect" sai theo nghĩa an ninh: **egress là side effect**. Với bearer
token (`src/auth/dependencies.py:14` `HTTPBearer`) lưu ở FE, một token bị lộ
cộng `GET /threads` (`src/agent/router.py:234`) cho phép duyệt **toàn bộ** thread
rồi export từng cái, và không để lại một dòng nào để phát hiện.

Đối chiếu §Câu hỏi chưa giải quyết của SOT: câu "Output có được dùng như
regulated advice hay chỉ research/education; **legal language và audit retention
phụ thuộc trực tiếp vào lựa chọn này**" **chưa được trả lời**. Plan.md tự ghi
"public share link cần threat model được chấp nhận trước" — nhưng local export
của cùng dữ liệu cũng là egress, và nó không được áp cùng cổng.

**(c) Sửa.**

- Một audit record cho mỗi export: `(user_id, thread_id, exported_at,
  message_count, bytes)`. Đây là bảng mới — chấp nhận nó, hoặc dùng structured
  log có schema và khai retention. "Không bảng mới" không được là ràng buộc
  thắng một yêu cầu SOT.
- Rate limit per-user cho export (ví dụ 30/ngày) — dùng đúng khuôn ceilings đã
  có (`src/core/llm/config.py:212`), không phát minh khuôn mới.
- Ghi vào `docs/Harness/` một mục **Export** (3-5 dòng: purpose, scope, audit,
  retention, redaction) trước khi merge phase 11. Plan sở hữu triển khai, không
  sở hữu contract — nên mục này là điều kiện, không phải phụ lục.
- Bỏ câu "không có side effect" khỏi phase; nó là lập luận biện minh cho việc
  bỏ audit.

---

### B5 — Archive "xoá" thread nhưng model vẫn **nhớ và trích** nó; và phase 11 buộc phải lách chính cổng của phase 08

**(a) Plan nói gì.** `phase-08` requirement: "Thread đã archive **không xuất
hiện ở bất kỳ đường đọc nào**". Cơ chế: helper `active_threads()` trả select đã
lọc + "một test grep khẳng định không file nào query `agent_thread` mà không đi
qua helper". Modify list: `src/agent/service.py`. `phase-11` success criterion:
"Thread archive → export được" (200).

**(b) Bằng chứng ngược.**

1. **Đường đọc nguy hiểm nhất là raw SQL, helper không phủ được.**
   `apps/api/src/agent/tools/memory.py:213-222`:

   ```sql
   FROM agent_message AS message
   JOIN agent_thread AS thread ON thread.id = message.thread_id
   WHERE thread.user_id = :user_id AND to_tsvector(... message.content->>'text' ...)
   ```

   Đây là tool `recall` của bundle `memory` — nó tìm **nội dung message** qua
   mọi thread của user. Một `select()` helper không dùng được bên trong chuỗi
   SQL này. Nếu quên: user "xoá" một thread nghiên cứu, rồi ba ngày sau model
   **trích lại nội dung thread đã xoá** vào một câu trả lời. Đó là failure về
   privacy, không phải về UI, và nó là lỗi im lặng.

2. **Query thật không ở `service.py`.** Chúng ở
   `src/agent/persistence.py`: `_list_threads:429`, `_read_thread:452`,
   `_delete_thread:727`, `_read_artifact:516` (join `AgentThread`),
   `_owned_turn`, `_owned_message`; cộng `src/agent/ops.py:320-341`; cộng
   `src/core/llm/admission.py:900-902` (join `AgentThread` để đếm active turn).
   Modify list của phase 08 nêu `service.py` — sai file cho bước an toàn nhất
   của phase.

3. **`src/core/llm/admission.py` không nằm trong freeze amendment** mà phase 01
   viết ra (`plan.md` §Freeze amendment mở: `src/agent/{router,schemas,models,
   service,loop,messages}.py`, `src/market_context/*`, `src/agent/export/*`,
   web). Nên fix bị chặn bởi chính freeze mà plan này viết.

4. **Mâu thuẫn cứng giữa hai phase.** Phase 08 acceptance: "test grep: **zero**
   query `agent_thread` bypass `active_threads()`". Phase 11 acceptance: "thread
   archive → export **200**". Hai cái không cùng đúng: export phải đọc thread
   archive, tức phải bypass helper. Một trong hai test sẽ đỏ, hoặc test grep sẽ
   bị nới thành vô nghĩa.

**(c) Sửa.**

- Đổi cơ chế: **filter ở tầng SQL dùng chung**, không phải helper Python.
  Cách rẻ nhất và không lách được: một Postgres **view** `agent_thread_active`
  (`WHERE archived_at IS NULL`) và đổi mọi reader — kể cả raw SQL của
  `memory.py` — sang view. Test grep khi đó kiểm một chuỗi (`FROM agent_thread`
  trần) và bắt được cả raw SQL.
- Khai tường minh **hai** helper: `active_threads()` và
  `any_thread_for_export()`. Sửa test grep thành "mọi query đi qua **một trong
  hai**, và `any_thread_for_export` chỉ có đúng một call site". Không để test
  grep bị nới lỏng.
- Thêm vào phase 08 một acceptance nêu tên `memory.py`: "recall **không** trả
  message của thread đã archive — test có thread archive chứa từ khoá duy nhất".
  Đây là acceptance thiếu nghiêm trọng nhất của phase.
- Đưa `src/core/llm/admission.py` và `src/agent/tools/memory.py` vào danh sách
  file mở của phase 01.

---

## MAJOR

### M1 — Trust line hứa hộ model điều prompt **cấm** model làm

**(a)** `phase-04` đặt nguyên văn dưới composer: *"Câu trả lời nêu **nguồn**,
thời điểm dữ liệu và mức độ không chắc chắn."*

**(b)** `apps/api/src/agent/prompt/sections.py:239-244`:

> "Tra rồi thì **nêu thời điểm, đừng nêu nguồn**. … một dòng dẫn nguồn trong văn
> bản chỉ là bản sao xấu hơn của thứ người đọc đã thấy."

và `:363-365`:

> "**Không viết phần dẫn nguồn.** Không dòng bắt đầu bằng Nguồn, không đường dẫn
> dán vào văn bản, không chú thích đánh số… Việc đó là của giao diện."

Uncertainty cũng là **có điều kiện**, không phải luôn: `:367-368` "**Khi** bạn
không chắc, hãy nói mình không chắc ở chỗ nào". Và
`investment-intelligence-contract.md:156` viết "as-of và freshness **khi thời
gian ảnh hưởng kết luận**" — cũng có điều kiện. Nên trust line phát biểu ba lời
hứa vô điều kiện, hai trong ba bị prompt chủ động cấm hoặc làm điều kiện. Không
một acceptance nào của phase 04 kiểm câu này đúng.

**(c)** Viết lại thành mô tả **cơ chế**, không mô tả hành vi model:

> Mỗi câu trả lời đi kèm thời điểm dữ liệu; nguồn đã tra hiển thị ở tab Nguồn.
> Nội dung hỗ trợ nghiên cứu, không phải khuyến nghị giao dịch.

Câu này đúng với `sections.py:239` (thời điểm ở text, nguồn ở UI) và đúng với
phase 10 (dòng evidence). Nếu vẫn muốn giữ chữ "nguồn" trong text thì phải bump
`PROMPT_VERSION` và sửa `sections.py` — mà `plan.md` §luật 3 cấm.

---

### M2 — Chip phiên nói dối vào mọi ngày nghỉ lễ (Tết là một tuần)

**(a)** `phase-03` §Risk: "Lịch nghỉ lễ không có nguồn… Phản ứng đã định: trước
`SESSION_SETTLED_AT`, `isTradingDay` dựa vào **thứ trong tuần**". Payload trả
`"phase": "ato" | "continuous_am" | …` và `nextTransitionAt`.

**(b)** Nghĩa là 09:15 mùng Hai Tết, endpoint trả `phase: "ato"`,
`isTradingDay: true`, `nextTransitionAt: 09:30` — và chip phase 04 vẽ "ATO ·
còn 15 phút tới liên tục sáng" trong khi sàn đóng. Sai liên tục **tới 15:00**,
trên ~11 ngày lễ cộng tuần Tết mỗi năm. Đây là vi phạm chính nguyên tắc plan
("Không badge trang trí… Không có dữ liệu → không render gì") và acceptance #2,
mà acceptance #2 không bắt được vì endpoint vẫn 200 và vẫn có số.

**(c)** Ba lựa chọn, chọn một và ghi ra:
1. Khai `session.confidence: "clock" | "confirmed"` — `confirmed` chỉ khi phiên
   hôm nay đã có dữ liệu; FE render trạng thái phiên **chỉ khi** `confirmed`,
   còn `clock` thì chỉ render độ mới dữ liệu. Rẻ nhất, honest nhất.
2. Nhập một danh sách nghỉ lễ tĩnh (HOSE công bố hằng năm) vào repo — 1 file,
   ~12 dòng/năm, có test hết hạn.
3. Bỏ hẳn nhánh session khỏi chip; giữ đúng độ mới dữ liệu.

Thêm acceptance: "ngày lễ trong tuần → chip **không** khẳng định trạng thái
phiên". 14 mốc golden hiện tại không có mốc này (chỉ có "ngày nghỉ lễ" ở nhánh
`closed`, tức sau 15:00).

---

### M3 — `/market/context` không có acceptance nào về auth, và router pattern khiến thiếu auth là lỗi im lặng

**(a)** `phase-03`: "Auth như các route khác." Success Criteria: 9 gạch đầu
dòng, **không có một dòng nào** về auth.

**(b)** Auth ở repo này là **per-handler**, không per-router:
`src/main.py:116-119` gọi `include_router` **không** `dependencies=[...]`, và
mỗi handler tự khai `current_user: CurrentUser` (`src/agent/router.py:226, 235,
244, 266, 294, 341, 448, 467, 503`). Nên một `market_context/router.py` viết
thiếu tham số đó là **public**, và không test nào đỏ.

Nếu public, nó rò: (i) thành phần Universe declared (30 mã) — dữ liệu sản phẩm;
(ii) trạng thái ingest của store (`asOf`, `sessionsBehind`, `health`) cho từng
nguồn — tức một kênh giám sát miễn phí vào một kho dữ liệu bị ràng buộc licence
vnstock (memory: `vnstock-licence-blocks-commercial`), và một tín hiệu cho đối
thủ biết pipeline chết lúc nào.

**(c)** Thêm hai acceptance vào phase 03: (1) "`GET /market/context` không có
bearer → **401**"; (2) một test contract quét **mọi** route đã đăng ký và khẳng
định mỗi cái có `CurrentUser` hoặc nằm trong allowlist tường minh (health,
auth). Test thứ hai là cái duy nhất chặn được lỗi này tái diễn ở phase sau.

---

### M4 — Tier `deep` route sang một workload **chưa từng được probe và chưa từng chạy**

**(a)** `phase-09`: `deep` → `llm_model_batch`; "Tier không đổi quyền" có test.

**(b)** Capability Probe chỉ chạy trên SESSION: `src/main.py:52-56`

```python
result = await CapabilityProbe(client, model=config.model_for(Workload.SESSION), ...)
```

và `grep -rn "Workload.BATCH" src/` chỉ trả về **config + pricing + budget
validation** (`core/llm/config.py:320,327`, `core/llm/budget.py:171,272`) —
**không một call site runtime nào**. Bốn check mà loop phụ thuộc —
`forced_tool_choice`, `parallel_tool_calls`, `strict_json_schema`,
`closed_tool_loop` (`src/core/llm/probe.py:127-138`) — chưa bao giờ được xác
minh cho `gpt-5.6-luna`. Memory `strict-tools-stack-shares-db` ghi một model đã
bị proxy trả `400 model_not_found`. Nên `deep` có thể vỡ **ở request của user**,
không ở boot — và nó vỡ theo cách khó chẩn đoán (tool loop không đóng).

Biên quyền theo nghĩa hẹp (tool allowlist) thì plan đúng. Biên **capability**
thì không: tier mở một route chưa được chứng minh, và §Reliability của SOT đòi
"Circuit breaker và fallback scope phải phân biệt credential, endpoint, model và
provider" — phase 09 không nói breaker phân biệt hai route.

Thêm: `quality-safety-and-operations.md:242` — "Route selection phải tôn trọng
data handling contract; fallback không được đổi data residency hoặc retention
posture một cách im lặng". Đổi model theo tier **là** route selection, và phase
không đối chiếu contract này.

**(c)**
- Bước 2 của phase 09 phải bao gồm: chạy `CapabilityProbe` với
  `model_for(Workload.BATCH)` và ghi 5 check vào phase. Nếu một check đỏ →
  `deep` **không được** dùng route đó.
- Thêm acceptance: "probe BATCH pass 5/5 trước khi `deep` `enabled = True`", và
  "breaker mở trên BATCH không làm SESSION mở".
- Thêm một dòng đối chiếu data handling: hai route cùng base_url cùng provider →
  ghi ra là **không** đổi posture; nếu khác, phase phải dừng.

---

### M5 — `deep` cho một user tiêu envelope chung, và ceiling per-user là **số lượt**, không phải tiền

**(a)** `phase-09` §Risk: "Ngân sách: `deep` cho phép user tự tiêu envelope…
Phản ứng: `deep` khai `status` riêng và **tắt được ở server bằng một dòng**."

**(b)** Ceiling per-user duy nhất tồn tại là **đếm**:
`src/core/config.py:161` `llm_user_turn_starts_per_day: int = 20`,
`src/core/llm/config.py:212 → 276`, enforce ở
`src/core/llm/admission.py:567-578` (cộng `active_turns_per_user`). Không có một
trần **chi tiêu** per-user nào: lane là toàn hệ thống
(`llm_budget_turn_usd`, `admission.py:65-68`). Nên 20 lượt `deep` (route batch,
6 vòng tool, 8 external call) của **một** user rút cạn lane Turn của **mọi**
user, và phản ứng duy nhất plan có là kill switch toàn cục — tức hình phạt tập
thể.

SOT `quality-safety-and-operations.md:305` §Cost governance đòi budget hierarchy
gồm: "envelope toàn hệ thống; **lane và user ceiling**; root task reservation;
**model/tool/data sub-budget**". Phase 09 thêm một trục làm chi phí/lượt tăng
gấp bội mà không thêm một tầng nào trong hierarchy đó.

**(c)**
- Trần per-user theo **tiền**, không theo lượt: thêm `user_monthly_usd` vào
  ceilings và enforce trong cùng transaction admission đã lock
  (`_read_turn_state` đã đọc `llm_call_usage` theo `user_id` — nền có sẵn, chỉ
  đổi `count(distinct owner_id)` thành `sum(actual_micro_usd)`).
- Hoặc, nếu không làm: trần lượt **riêng cho `deep`** (ví dụ 3/ngày) trong cùng
  cơ chế `turn_starts_per_day`. Một dòng config, và nó chặn đúng blast radius.
- Acceptance: "user A tiêu hết trần của mình → user B vẫn gửi được turn". Không
  có test này thì R1/kill-switch là biện pháp duy nhất và nó phá cả sản phẩm.

---

### M6 — Title generator không có owner type, nên "không chi ngoài sổ" không thực hiện được như viết

**(a)** `phase-08`: "Usage của title generator vào ledger… Ghi vào **cùng owner
key của turn** sinh ra nó." Acceptance: "Usage title generator có trong
ledger — test đếm".

**(b)** `OwnerType` chỉ có ba giá trị (`src/core/llm/admission.py:71-74`):
`ANALYSIS_RUN`, `TURN_REQUEST_MESSAGE`, `CAPABILITY_PROBE`. Ghi title vào cùng
`owner_id` của turn có hai hệ quả:

1. **Không phân biệt được** chi phí title với chi phí answer trong ledger — đúng
   cái phase muốn tránh ("một lane LLM ẩn không được chi ngoài sổ"). Test "đếm
   usage" sẽ pass mà không chứng minh được tách bạch.
2. `_read_turn_state` đếm `count(distinct owner_id)` cho
   `TURN_REQUEST_MESSAGE` (`admission.py:888-895`) để áp `turn_starts_per_day`.
   Reuse owner_id giữ đúng phép đếm (tốt), nhưng nghĩa của "một start" trở
   thành "một turn + có thể một title", và bất kỳ ai đọc ledger sau này sẽ trừ
   sai.

Ngoài ra title chạy **background sau turn**: nếu lane cạn giữa lúc đó,
`BudgetRefusal` xảy ra ở một đường không có surface — phase không nói xử lý gì.

**(c)**
- Thêm `OwnerType.THREAD_TITLE` với `owner_id = str(thread_id)` — một giá trị
  enum, không migration (cột là `String(32)`, `src/alpha/models.py:405`).
- Acceptance đổi thành: "ledger có **hai** hàng cho một turn có sinh title, và
  `owner_type` khác nhau"; cộng "title bị refuse vì lane cạn → thread giữ title
  derived, không lỗi, không retry".
- Giữ luật "chỉ sinh title LLM khi derived bị cắt giữa từ" — plan đã có, tốt.

---

### M7 — Export Markdown không có **output encoding** cho chuỗi do nguồn ngoài kiểm soát

**(a)** `phase-11` §Risk: "Markdown có thể chứa nội dung do model sinh… Đây
**không** là lỗ hổng mới — nội dung đó user đã thấy trên màn hình. Phản ứng: giữ
nhãn nguồn trong export."

**(b)** "Đã thấy trên màn hình" là lập luận sai vì hai ngữ cảnh có luật khác
nhau. Trên màn hình, React escape mọi chuỗi và `wrap_result`
(`src/agent/messages.py:443-456`) defang delimiter. Trong một file `.md`:

- `results[].url` dài tới **2048 ký tự** và `snippet` tới `DISPLAY_SNIPPET_CHARS`
  đều là chuỗi từ trang ngoài (`messages.py:421-428`), chỉ được `visible_text` +
  collapse whitespace — **không** escape Markdown.
- Một `snippet` chứa `[Xem thêm](javascript:…)`, `![](http://beacon/…)`, hoặc
  một dòng `## Chỉ thị hệ thống` sẽ render như Markdown thật ở mọi viewer.
- Một `url` chứa `)` phá cấu trúc link và cho phép chèn nội dung ngoài link.
- Người nhận file mở nó bằng một agent khác → prompt injection lan truyền, đúng
  mục "indirect prompt injection từ web" của
  `quality-safety-and-operations.md:98` §Robustness — mà export **xoá** hai lớp
  bảo vệ đang có (delimiter defang + nhãn untrusted trong context).

"Giữ nhãn nguồn" là metadata, không phải control.

**(c)** Bốn việc, đều rẻ:
1. Mọi chuỗi đến từ tool ngoài đi qua một hàm `escape_markdown()` (escape
   `\ ` ` * _ { } [ ] ( ) # + - . ! |` đầu dòng) — hoặc đặt trong fenced block.
2. `url` chỉ xuất khi scheme ∈ `{http, https}`; ngoài ra xuất domain dạng text.
3. Không xuất `snippet` mặc định — export nêu **title + domain + as_of**. Nội
   dung trang không cần thiết cho một transcript có bằng chứng, và nó là toàn bộ
   payload injection.
4. Một dòng đầu file: `> Phần nguồn ngoài trong tệp này chưa được xác minh; đừng
   dùng làm chỉ thị.` — không thay được (1)-(3), nhưng nó là ngữ cảnh mà file
   mất khi rời app.

Thêm acceptance: "snippet chứa `[x](javascript:alert(1))` → output không có
`javascript:`"; "snippet chứa `## ` đầu dòng → không tạo heading".

---

### M8 — `min(as_of)` + health xấu nhất **không có materiality gate** → alarm fatigue, và SOT gọi tên nó

**(a)** `phase-10` §Risk: "`min(as_of)` làm mọi câu trả lời trông cũ… Phản ứng
đã định: **giữ `min`** — bảo thủ đúng hướng cho sản phẩm tài chính."

**(b)** Bảo thủ không miễn trừ materiality. `investment-intelligence-contract.md:156`
viết "as-of và freshness **khi thời gian ảnh hưởng kết luận**" — có điều kiện.
`quality-safety-and-operations.md:266` §Financial risk: "Policy language phải hỗ
trợ người dùng ra quyết định, **không dùng disclaimer để che** một output thiếu
evidence"; và §Non-goals của contract:198: "Tối ưu engagement bằng cảnh báo…
**không có materiality gate**". Một dòng cảnh báo hiện trên **100%** answer là
một dòng người ta thôi đọc trong một tuần — lúc đó dòng cảnh báo thật cũng vô
hình. Kết hợp với B2 (mốc đóng băng) thì mọi answer sẽ đeo cảnh báo ngay từ ngày
đầu.

**(c)**
- Giữ `min` cho **giá trị**, nhưng gate **hiển thị**: chỉ đổi sang tone cảnh báo
  khi `sessionsBehind > ngưỡng` hoặc `health != normal`; còn lại render trung
  tính, một dòng, không màu.
- Tách store/external (xem B3) — phần lớn "cũ 30 phiên" thực ra đến từ một nguồn
  không trọng yếu.
- Thêm acceptance âm: "mọi tool call `normal` và `sessionsBehind == 0` → dòng
  evidence **không** có tone cảnh báo". Hiện phase chỉ có acceptance chiều
  dương ("`noValueCount > 0` → có tone cảnh báo").

---

### M9 — Undo 8s ở FE là lối duy nhất, và "chấp nhận" không phù hợp với dữ liệu nghiên cứu

**(a)** `phase-08`: "Cửa sổ undo là ở FE, không ở server… Sau 8s thread vẫn
archive, chỉ là lối hoàn tác biến khỏi màn hình… **Cửa sổ undo ở FE nghĩa là
reload mất lối hoàn tác. Đúng, và chấp nhận**". Không có thùng rác.

**(b)** Ba điểm ngược:
1. `PATCH /threads/{id}` **có** kiểm quyền owner
   (`src/agent/router.py:279` → `persistence.update_thread(user_id, …)`, và
   `_delete_thread:727` cũng filter `user_id`), nên undo là an toàn — không có
   lỗ hổng ở đây. Chi phí để hiện một danh sách "Đã xoá" vì thế là **một filter
   đảo dấu**, không phải một feature.
2. Không có confirm dialog trong phase (`sidebar.tsx:344-353` hiện không confirm
   — scout web §7 theo plan). Nên đường mất dữ liệu là: một click sai + một
   reload trong 8s = thread nghiên cứu **không có lối lấy lại nào cho user**.
3. `downgrade -1` của chính revision này làm **mọi thread archive hiện trở lại**
   (phase tự ghi). Nên trạng thái archive là phần **kém bền nhất** của bản ghi:
   nó biến mất khi rollback, và không truy cập được khi không rollback.

Với "nghiên cứu đầu tư" — nơi một thread là hàng giờ suy luận và bằng chứng —
"chấp nhận" ở đây là chấp nhận thay user.

**(c)** Rẻ và đủ, chọn một:
- Một mục sidebar "Đã xoá" đọc `archived_at IS NOT NULL`, chỉ hai hành động
  (Khôi phục, Xoá vĩnh viễn). Dùng `any_thread_for_export()`/helper thứ hai đã
  cần cho B5, nên chi phí gần bằng 0.
- Hoặc tối thiểu: confirm dialog cho xoá **và** giữ toast undo. Confirm là cái
  phase đang bỏ đi mà không nêu lý do.

---

## MINOR — 12 phát hiện

Danh sách đầy đủ (mỗi cái một dòng, đủ để hành động):

1. **Export qua `GET` + query param** → thread id vào access log, browser
   history, và `Referer` nếu FE điều hướng. Dùng `POST` (hoặc bỏ `?format=`) và
   khai `Cache-Control: no-store`.
2. **Cache 30s in-process**: hiện chỉ một worker (`apps/api/Dockerfile:37`
   `uvicorn … ` không có `--workers`), nên acceptance "test đếm query" đúng hôm
   nay và **im lặng sai** ngày ai đó thêm workers. Ghi giả định vào phase; thêm
   lock để tránh thundering herd; ghi rõ cache key **không bao giờ** được chứa
   `user_id`.
3. **Tier bị hạ thì user không biết**: `phase-09` ghi tier đã dùng vào trace,
   nhưng UI vẫn hiện tier đã chọn. User trả tiền cho `deep`, nhận `balanced`.
   Trả tier đã dùng trên `turn.completed` và hiện nó.
4. **`?format=markdown` chỉ có một giá trị** — tham số chết, và là chỗ để một
   `format` mới lọt vào sau này mà không đi qua whitelist. Bỏ tham số.
5. **`phase-12` không có lane bảo mật nào**: 0 test authz, 0 case injection, dù
   `quality-safety-and-operations.md:98` liệt kê "indirect prompt injection từ
   web" là bộ adversarial bắt buộc. Thêm một mục §Security sweep.
6. **`downgrade -1` un-archive** (phase tự ghi) — thêm vào docstring revision
   **và** vào runbook rollback, không chỉ docstring.
7. **Trùng logic aggregate**: `_merged_provenance`
   (`src/agent/tools/studies.py:628`) đã làm min/worst. Phase 10 viết lại lần
   hai ở `messages.py` → hai định nghĩa "health xấu nhất".
8. **Starter hard-code "HPG"** (`phase-04`) — trong một sản phẩm tài chính, một
   mã cụ thể trong CTA đọc như gợi ý. Dùng mã trong câu mô tả, không trong
   nhãn button; hoặc để lane hỏi lại mã.
9. **Title do LLM sinh render ở sidebar** không có trần độ dài/lọc ký tự điều
   khiển. `title` là `String(255)`; thêm clamp + strip newline trước khi ghi.
10. **Freeze amendment thiếu file**: `phase-01` mở
    `src/agent/{router,schemas,models,service,loop,messages}.py` +
    `src/market_context/*` + `src/agent/export/*` + web — nhưng phase 03 sửa
    `src/main.py`, phase 08 phải sửa `src/agent/persistence.py`,
    `src/agent/ops.py`, `src/agent/tools/memory.py`, và
    `src/core/llm/admission.py`. Bốn cái sau chưa được mở.
11. **Retention/deletion path cho cả thread store chưa tồn tại** (SOT §Trace and
    privacy đòi). Archive không phải deletion. Ghi thành câu hỏi chưa giải quyết
    ở `plan.md`, đừng để phase 08 ngụ ý đã giải.
12. **`sessionsBehind` có thể âm** (bar_daily mới hơn provider_snapshot, xem B2)
    — không có clamp nào được đặc tả.

---

## Đối chiếu SOT — vi phạm theo file

| SOT | Điều | Phase vi phạm |
|---|---|---|
| `quality-safety-and-operations.md:227` §Trace and privacy | "audit ai đọc/**export** artifact"; "retention/expiry và deletion path" | 11 (B4) |
| `quality-safety-and-operations.md:242` | "Route selection phải tôn trọng data handling contract" | 09 (M4) |
| `quality-safety-and-operations.md:247` §Security model | `External content → model \| untrusted \| delimit, provenance` | 10 (B3), 11 (M7) |
| `quality-safety-and-operations.md:98` §Robustness | "indirect prompt injection từ web" là bộ eval bắt buộc | 11, 12 (M7, MINOR 5) |
| `quality-safety-and-operations.md:305` §Cost governance | "lane và **user ceiling**"; "model/tool/data sub-budget" | 09 (M5), 08 (M6) |
| `investment-intelligence-contract.md:177-181` §Autonomy | "Capability mới phải được phân loại … data sensitivity và approval requirement tại registration" | 11 (B4) |
| `investment-intelligence-contract.md:156` §Output contract | as-of/freshness "**khi** thời gian ảnh hưởng kết luận" | 10 (M8), 04 (M1) |
| `investment-intelligence-contract.md:198` §Non-goals | "cảnh báo … không có materiality gate" | 10 (M8) |
| `investment-intelligence-contract.md:229` §Câu hỏi chưa giải quyết | "regulated advice hay research; **audit retention** phụ thuộc lựa chọn này" — chưa trả lời | 11 mở egress trước khi câu này được chốt |

**Về câu hỏi trong brief — export có thuộc "user-approved export" mà SOT nêu?**
Không. SOT không có mục nào về share/export ngoài §Trace and privacy (nói về
**trajectory artifact** của operator, không về transcript của user) và câu hỏi
chưa giải quyết về audit retention. `plan.md` §Quyết định 2 tự ghi
"`docs/Harness/` **không có một dòng nào** về share" và dùng đó làm lý do **hoãn
public link** — nhưng rồi dùng cùng khoảng trống đó để **cho phép** local export
mà không viết contract. Hai kết luận trái nhau từ một tiền đề. Local export ít
blast radius hơn public link, không phải bằng 0: nó vẫn là egress plaintext của
toàn bộ nghiên cứu, và nó vẫn cần audit + retention + phân loại capability.

---

## Ba thứ nên đổi ở `plan.md` trước khi thi công

1. **Acceptance #2 không đo được cái nó nói.** "Tắt endpoint → chip biến mất"
   không bắt được B2 (endpoint sống, số vô nghĩa) hay M2 (số đúng cú pháp, sai
   sự thật). Bổ sung: "nguồn của một con số đóng băng → nhánh đó trả `null`" và
   "ngày lễ → không khẳng định trạng thái phiên".
2. **Acceptance #8 ("Export fail-closed") sai tầng.** "Field không nằm trong
   whitelist" nói về **cột**; rủi ro thật ở **khoá JSON** và ở **encoding**.
   Viết lại thành: "khoá JSON không khai không ra output" + "chuỗi từ nguồn
   ngoài được escape" + "mỗi export có audit row".
3. **Thêm acceptance #13.** "Mọi route đã đăng ký có auth hoặc nằm trong
   allowlist tường minh" — một test contract, và nó là cái duy nhất chặn M3 tái
   diễn ở mọi phase sau.
