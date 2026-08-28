# Red-team: Evidence-Led Chat Surface

Target: `plans/260827-2325-evidence-led-chat-surface/` (plan.md + 12 phase).
Method: đọc plan → xác minh mọi `path:line` bằng grep/sed trên source thật →
đối chiếu `docs/text.md`, plan Study, và ba báo cáo nền. Không chạy test.
Chỉ ghi vấn đề; những chỗ plan làm đúng không liệt kê.

---

## BLOCKER

### B1. `agent_thread` không nằm ở `src/agent/models.py` — file đó không tồn tại

**Plan claim.** Phase 08 §Related Code Files: "Modify: `apps/api/src/agent/models.py`
— 3 cột". `plan.md` §Freeze amendment mở `src/agent/{router,schemas,models,service}.py`.

**Bằng chứng ngược.**
- `apps/api/src/alpha/models.py:35` — `__tablename__ = "agent_thread"`.
- `ls apps/api/src/agent/` → không có `models.py`.
- Chính báo cáo nền ghi đúng: `plans/reports/scout-260827-2318-api-harness.md:41`
  "Tất cả ở `src/alpha/models.py`" và `:45` cho `agent_thread`. Plan **trích sai
  báo cáo của chính nó**.
- `scout-260827-2318-api-harness.md:206` liệt `src/alpha/**` là vùng không đụng
  "trừ `models.py` khi thêm bảng agent" — nên freeze amendment phải nêu tên
  `src/alpha/models.py`; như viết hiện tại nó mở một file không tồn tại và để
  phase 08 vi phạm freeze.

**Sửa.** Trong phase 08 và `plan.md` §Freeze amendment: `src/agent/models.py` →
`src/alpha/models.py`. Thêm dòng freeze cho `src/alpha/models.py` (chỉ bảng
`agent_thread`).

---

### B2. Thread query nằm ở `persistence.py`, không phải `service.py`; và hai đường đọc ở ngoài phạm vi freeze đã mở

**Plan claim.** Phase 08: "Modify: `apps/api/src/agent/service.py` — mọi query qua
`active_threads()`" + success criteria "Test grep: zero query `agent_thread`
bypass `active_threads()`".

**Bằng chứng ngược.** Mọi query thread thật ở `apps/api/src/agent/persistence.py`:
`:378`, `:429-439`, `:452-454`, `:485`, `:516`, `:569`, `:620`, `:695-716`.
Ngoài đó còn **hai đường đọc mà helper không thể bao**:
- `apps/api/src/core/llm/admission.py:900-902` — `join(AgentThread, ...)`.
  `src/core/llm/*` **không** nằm trong freeze amendment của plan.
- `apps/api/src/agent/tools/memory.py:214` — SQL thô `JOIN agent_thread AS thread`.
  Một helper SQLAlchemy `active_threads()` không route được câu này, nên test grep
  ở success criteria sẽ **đỏ vĩnh viễn** hoặc phải nêu ngoại lệ — và nếu nêu ngoại
  lệ mà không lọc `archived_at` thì memory tool vẫn đọc thread đã archive (đúng R2
  cấp plan).

**Sửa.** Phase 08 §Related Code Files: `service.py` → `persistence.py`; thêm
`src/core/llm/admission.py` và `src/agent/tools/memory.py` vào danh sách phải xử lý
và vào freeze amendment; ghi rõ memory.py là SQL thô nên phải sửa tay + có test
riêng, không chỉ dựa vào test grep.

---

### B3. Vòng lặp phụ thuộc thật giữa phase 08 và 09

**Plan claim.** Bảng phases: 09 phụ thuộc 08. Phase 09 §Steps bước 1: "nếu cần cột
mới thì đưa vào revision của phase 08 **trước khi phase 08 merge**".

**Bằng chứng ngược.** Phase 08 revision chỉ thêm 3 cột trên `agent_thread`
(`archived_at`, `title_source`, `research_tier`). Yêu cầu của phase 09 là ghi
**tier đã dùng thật cho một turn** → cột trên `agent_turn`, không có trong 3 cột đó.
Nên bước 1 của 09 phải chạy trước khi 08 merge, trong khi 09 khai phụ thuộc 08 →
vòng. Fallback plan đề xuất ("dùng cột JSON có sẵn") trỏ vào `agent_turn.draft_content`
— cột checkpoint của reconnect (`scout-260827-2318-api-harness.md:48`); nhét tier
vào đó là làm hỏng chính cột mà phase 10 dựa vào.

**Sửa.** Chuyển quyết định "ghi tier ở đâu" thành **bước 0 của phase 08** (phase 08
tự khai cột `agent_turn.research_tier_used`, nullable). Phase 09 chỉ đọc/ghi cột đã có.
Hoặc tách một revision thứ hai và bỏ lý lẽ "một revision" — nhưng đừng để hai phase
cùng sở hữu một revision.

---

### B4. Phase 02 nối 4 item TopBar vào "handler thật" — chỉ 3/4 tồn tại, và một cái mâu thuẫn với phase 11

**Plan claim.** Phase 02 §Architecture: "`top-bar.tsx:73-85` menu thread | 4 item
disabled | **Nối vào handler thật** | Sidebar đã làm thật đúng bốn việc này
(`sidebar.tsx:344-353` + rename)". Success criteria: "4 hành động thread ở TopBar
**hoạt động thật**".

**Bằng chứng ngược.** Bốn item là Ghim · Đổi tên · **Xuất PDF** · Xoá
(`apps/web/src/components/shell/top-bar.tsx:73,76,79,83`). `ThreadMenu` của sidebar
chỉ có ba: Ghim/Bỏ ghim (`sidebar.tsx:382-393`), Đổi tên (`:394`), Xoá — **không có
export** ở bất kỳ đâu. Và phase 11 làm export **Markdown**, không phải PDF. Nên
phase 02 không thể hoàn thành success criteria của chính nó: item thứ tư không có
handler, và cái sẽ có (ở phase 11) mang định dạng khác.

**Sửa.** Phase 02: nối 3 item, **xoá** "Xuất PDF" (không có handler ở đâu → đúng
luật của chính phase 02), và phase 11 thêm lại item "Xuất Markdown" khi export
thật tồn tại. Sửa success criteria "4 hành động" → "3 hành động".

---

### B5. Phase 05 vẽ ticker chip từ `symbols`, nhưng lane chat **cố ý** không điền `symbols`

**Plan claim.** Phase 05 §Overview: "Metadata mà critique đòi **đã tồn tại trong
DB** — nó chỉ chưa ra tới UI. Nên phase này **không cần migration**". §Risk:
"`symbols` chưa được điền cho thread cũ … Ai điền `symbols` … là câu hỏi của phase 08".

**Bằng chứng ngược.** Cơ chế điền `symbols` **đã có và đang chạy**:
`apps/api/src/agent/persistence.py:391-395` union `symbols` của message vào
`thread.symbols`; nguồn là `CreateTurnRequest.symbols` (`src/agent/schemas.py:178`).
Nhưng FE lane chat **cố ý gửi rỗng**:
`apps/web/src/components/shell/desk-state.tsx:169-170` — "`symbols` stays empty and
the context travels as `active_symbol`. They are different things, and guessing which
symbols a sentence is [about]…". Nên:
1. Chip của phase 05 sẽ trống 100% cho **mọi** thread, cũ và mới, cho tới khi 08 xong
   → phase 05 ship một feature không có dữ liệu (đúng cái "badge giả" plan cấm).
2. Phase 08 §Architecture định "union các mã đã hỏi vào `thread.symbols`" trong
   `loop.py` — **trùng** đường ghi đã có ở `persistence.py:391`, tạo hai nguồn ghi
   cho một cột.

**Sửa.** Chuyển phần "điền `symbols` từ tool call thật" ra khỏi phase 08 thành phần
đầu của phase 05 (đây là API-only, không cần migration, không bị chặn bởi làn
alembic), và ghi qua đường `_insert_message` đã có thay vì thêm đường trong `loop.py`.
Nếu giữ ở 08 thì phase 05 phải khai chip là "chưa có dữ liệu tới sau 08" trong
success criteria.

---

## MAJOR

### M1. `message-shell.tsx`, `message-actions.tsx`, `assistant-message.tsx` không ở `components/shell/`

**Plan claim.** Phase 01 modify `apps/web/src/components/shell/message-shell.tsx:29`;
phase 06 modify `apps/web/src/components/shell/message-actions.tsx:64-67`; phase 10
modify `apps/web/src/components/shell/assistant-message.tsx`.

**Bằng chứng ngược.** Cả ba ở `apps/web/src/components/alpha/message/`
(`message-shell.tsx`, `message-actions.tsx`, `assistant-message.tsx`). Báo cáo nền
ghi đúng: `scout-260827-2318-web-chat-shell.md:296` (`alpha/message/message-shell.tsx:29`),
`:198` (`alpha/message/message-actions.tsx:64-67`), `:232`. Hệ quả freeze:
`plan.md` §Freeze amendment mở `apps/web/src/components/shell/*` + `lib/*` —
**không** mở `components/alpha/message/*`, nhưng phase 06 và 10 buộc phải sửa nó
(dòng evidence nằm dưới answer; nút copy nằm ở `message-actions`).

**Sửa.** Sửa ba đường dẫn; thêm `apps/web/src/components/alpha/message/*` vào freeze
amendment.

### M2. Phase 09 parameter hoá `loop.py` nhưng bỏ qua hai module được hiệu chỉnh theo hằng số cũ

**Plan claim.** Phase 09: "hai hằng số thành tham số có default bằng đúng giá trị
hiện tại"; luật 3 của plan: "chỉ đổi **trần** qua tham số".

**Bằng chứng ngược.** Hai hằng số không đứng một mình:
- `apps/api/src/agent/guardrails.py:82-95` — bậc thang cảnh báo là **số học suy ra**
  từ `MAX_TOOL_ROUNDS`/`MAX_EXTERNAL_TOOL_CALLS`: "a rung set above either of those
  is a rung nothing can ring"; `exact_failure_block_after=3` được biện minh bằng
  "round budget" = 4; `same_tool_failure_halt_after=6` = "the external-call ceiling
  itself".
- `apps/api/src/agent/executor.py:88-92` — `MAX_EXTERNAL_CALLS_PER_ROUND = 8` được
  biện minh là "more than the whole Turn can fund" (6).

Ở tier `quick` (1 vòng / 2 external) hai rung dưới không bao giờ ngân; ở `deep`
(6 vòng / 8 external) `same_tool_failure_halt_after=6` và cận 8/round mất ý nghĩa
thiết kế và có thể halt giữa turn. Nên "chỉ đổi trần" không đúng: đổi trần là đổi
cả ladder.

**Sửa.** Phase 09 phải khai `guardrails` rungs và `MAX_EXTERNAL_CALLS_PER_ROUND` là
hàm của `TierConfig`, hoặc chốt rằng `quick`/`deep` chỉ đổi **một** trong hai trần
và giữ ladder. Thêm test: mỗi tier, mọi rung còn ngân được.

### M3. Phase 09 tự sửa acceptance của plan Study mà không sửa plan Study

**Plan claim.** Phase 09 §Risk: "mốc 8s là **của `balanced`**, không phải của mọi tier."

**Bằng chứng ngược.** `plans/260826-2158-study-artifact-canvas/plan.md:209` đặt mốc
"Câu hỏi → `canvas.ready` ≤ 8s" **không điều kiện**, và `:215` nói tiền đề latency
route LLM **chưa đo**. `deep` route sang `llm_model_batch` (route chưa đo) + 6 vòng.
Plan này diễn giải lại acceptance của plan khác trong file của mình — plan Study
không biết.

**Sửa.** Hoặc phase 09 ghi một dòng vào `plans/260826-2158-study-artifact-canvas/plan.md`
§Perf budget ("mốc áp cho tier `balanced`"), hoặc `deep` giữ nguyên route
`llm_model_session`. Không để hai plan mang hai phiên bản của một mốc.

### M4. Pin/unpin đã hoạt động; contract PATCH là `pinned: bool`, không phải `pinned_at: null`

**Plan claim.** Phase 02: "`pinned_at` là cột thật … **nhưng UI chưa pin/unpin
được**". Phase 05: "Pin/unpin thật (cột `pinned_at` đã có)" là hạng mục mới; "unpin
là set `null`"; success criteria "unpin = `null`".

**Bằng chứng ngược.** UI **đã** pin/unpin: `sidebar.tsx:340-343`
`update.mutate({ threadId: row.id, pinned: !pinned })`; menu có "Ghim/Bỏ ghim"
(`sidebar.tsx:382-393`); có `thread-menu.test.tsx`. Contract API là
`src/agent/schemas.py:57` `pinned: bool | None`, và server tự
`coalesce(pinned_at, now())` (`persistence.py:703`). Nên "unpin = gửi `null`" là
contract **không tồn tại**; đạt success criteria đó = đổi public contract mà plan
tuyên bố không đổi.

**Sửa.** Phase 05: gỡ "pin/unpin thật" khỏi scope (chỉ còn: nhóm ghim chịu luật
"Xem thêm" + không trùng nhóm recency); sửa success criteria thành "unpin gửi
`pinned: false`".

### M5. Phase 03 dùng tên cột không tồn tại và mô tả sai index

**Plan claim.** Phase 03 §Architecture:
```sql
SELECT max(session_date) AS latest, max(observed_at) AS observed
FROM bar_daily WHERE symbol = ANY(:symbols)
```
kèm chú thích "dùng index sẵn có trên (symbol, session_date)".

**Bằng chứng ngược.** `apps/api/src/stocks/models.py:436-453`: cột là
`trading_day` (PK `(symbol, trading_day)`), index là
`ix_bar_daily_symbol_day (symbol, trading_day desc)` và
`ix_bar_daily_day_series (trading_day, series)`. Không có `session_date`.
Thêm nữa: `bar_daily` giữ **cả hai** series trong một bảng (`series` = `equity|index`,
`models.py:410-418`), nên aggregate không lọc `series` sẽ trộn VNINDEX vào nhánh
`daily` và làm nhánh `index` trùng nhánh `daily`.

**Sửa.** Đổi `session_date` → `trading_day` ở cả SQL và chú thích index; thêm
`AND series = 'equity'` cho nhánh daily và `series = 'index'` cho nhánh index.

### M6. Phase 03 trích sai đường dẫn `session_window.py` và `SESSION_SETTLED_AT`

**Plan claim.** Phase 03 §Related Code Files, Read-only: "`apps/api/src/stocks/session_window.py`,
`trading_day.py`"; §Architecture "Sau `SESSION_SETTLED_AT` (15:00, đã có hằng số)"
ngụ ý cùng module; `plan.md` §luật 2 cũng ghi `session_window.py`.

**Bằng chứng ngược.** `phase_of` ở `apps/api/src/stocks/intraday/session_window.py:93`;
`SESSION_SETTLED_AT = time(15, 0)` ở `apps/api/src/stocks/intraday/reads.py:34`.
`apps/api/src/stocks/session_window.py` **không tồn tại**. Quan trọng vì
`src/stocks/intraday/*` là vùng plan Study đang sở hữu — import từ đó là một điểm
tiếp xúc giữa hai plan mà "làn tách" hiện không nêu.

**Sửa.** Sửa hai đường dẫn; ghi vào `plan.md` §luật 2 rằng phase 03 **import** từ
`src/stocks/intraday/{session_window,reads}.py` (chỉ đọc), và thêm một test khẳng
định `session.py` không hard-code lại giờ (plan đã định, chỉ sai chỗ trỏ).

### M7. Acceptance không test được như đã viết (4 chỗ cụ thể)

1. **"hit area ≥44px, kích thước thị giác không đổi"** (phase 01) — cơ chế là
   `::after` với `inset: 50%; width/height 44px`. jsdom/vitest không tính layout,
   `getBoundingClientRect()` trả 0; pseudo-element không có trong DOM API. Test như
   viết chỉ kiểm **được sự hiện diện của class**, không kiểm 44px. Success criteria
   "so ảnh trước/sau ở 1440px" là kiểm bằng mắt → không phải test.
   *Sửa:* hạ xuống "test khẳng định class `hit-44` + khoảng cách ≥8px giữa control
   liền kề (đọc từ token gap)" và một e2e Playwright đo `boundingBox()` thật cho
   3 control tiêu biểu.
2. **"cụm nằm trên optical center"** (phase 04, `getBoundingClientRect().top <
   viewportHeight/2`) — cùng lý do: jsdom trả 0 cho mọi rect, và điều kiện `0 < h/2`
   luôn đúng → test **luôn xanh, không kiểm gì**.
   *Sửa:* chuyển sang e2e, hoặc kiểm class/style tường minh (`justify-*` + offset).
3. **"kiểm thật trên Safari iOS"** (phase 07) — không phải test. Phase đã tự thừa
   nhận ("nếu không kiểm được thì nói rõ là chưa kiểm") nhưng nó vẫn nằm trong
   success criteria dạng checkbox.
   *Sửa:* tách thành "manual verification log", không phải success criterion.
4. **"Một request = một truy vấn/nguồn (test đếm query)" + "Cache 30s hoạt động"**
   (phase 03) — hai criteria xung đột: nếu cache bật, lần gọi thứ hai có 0 truy vấn,
   nên test "một truy vấn/nguồn" phải chạy với cache tắt; plan không nói cache có
   cửa tắt cho test. Thêm nữa cache in-process 30s × nhiều uvicorn worker → mỗi
   worker một cache, "hai lần gọi liên tiếp chỉ một lần truy vấn" **sai** trong
   production nhiều worker.
   *Sửa:* cache nhận TTL/clock qua tham số (như `session.py` đã định), test tắt
   cache cho criteria đếm query, và ghi rõ cache là per-worker.

### M8. Cognitive load "minimal choices" không thể pass sau phase 05

**Plan claim.** Acceptance #10: "cognitive load ≤1 checklist fail". Phase 05 success
criteria: "Số quyết định thấy được cùng lúc trong sidebar ≤ 7 + 1 nút mỗi nhóm".

**Bằng chứng ngược.** `docs/text.md:177,185` định nghĩa fail này theo **toàn sidebar**
(~18 item), không theo nhóm. Sau plan: 4 nav item còn lại + nhóm ghim (≤5 + nút) +
3 nhóm recency (7/5/5 + 3 nút) = **có thể >20 item** khi user có nhiều thread — cao
hơn baseline. Hai criteria đo hai thứ khác nhau và cái của phase 05 không kéo được
cái của plan.

**Sửa.** Hoặc mặc định collapse hai nhóm dưới (chỉ "Hôm nay" mở), hoặc chấp nhận
"minimal choices" là 1 fail được phép của acceptance #10 và nói ra trong `plan.md`.

### M9. Phase 06 success criteria bỏ sót một caller `navigator.clipboard`

**Plan claim.** "grep `navigator.clipboard` trong `components/` chỉ còn trong helper".

**Bằng chứng ngược.** Ba caller plan liệt kê đúng, nhưng còn caller thứ tư:
`apps/web/src/components/settings/account-section.tsx:28`
`await navigator.clipboard.writeText(value)`. Criteria như viết sẽ đỏ.

**Sửa.** Thêm `components/settings/account-section.tsx` vào danh sách modify, hoặc
giới hạn grep vào `components/shell/` + `components/alpha/`.

### M10. Rủi ro chưa nêu

Sáu rủi ro thật không có ở đâu trong plan (kể cả risk từng phase):

1. **`archived_at` và FK cascade.** Bốn bảng `ondelete="CASCADE"` trỏ
   `agent_thread.id` (`src/alpha/models.py:111,160,344,476`). Soft-delete nghĩa là
   cascade **không còn chạy** — thread archive giữ nguyên message/turn/artifact.
   Không có phase nào quyết: quota, dung lượng, và "purge thật" (plan đẩy sang "quyết
   định vận hành riêng") giờ là nợ không chủ. Ít nhất phải nêu: sau plan này, xoá
   thread **không** giải phóng dữ liệu nào.
2. **Export Markdown và `<untrusted_tool_result>`.** Phase 11 §Risk nói "giữ nhãn
   nguồn" nhưng bỏ nhánh ngược: nội dung do web tool trả về có thể chứa **Markdown
   /HTML/link** do nguồn ngoài viết. File `.md` mở trong một viewer khác là một bề
   mặt injection mới (link, image beacon, `[text](javascript:…)`). Phản ứng tối
   thiểu: escape/fence nội dung untrusted trong export, không chỉ dán nhãn.
3. **`research_tier` cho user tự tiêu envelope** được nêu ở phase 09 nhưng **không
   có cổng**: `deep` chỉ tắt được toàn cục bằng `status`. Không có trần per-user,
   không có "hạ tier khi ledger gần cạn" — mà chính phase 09 lại đòi test "ca hạ
   tier". Cơ chế hạ chưa ai sở hữu.
4. **Title generator ghi ledger — chưa biết ledger ở đâu.** Phase 08 tự thừa nhận
   "tìm đúng chỗ trước khi ghi" và cảnh báo `agent/budget.py` là ngân sách ký tự.
   Đây là **unknown chưa giải quyết trong một success criterion** ("Usage title
   generator có trong ledger — test đếm"). Rủi ro: phase 08 phải sửa
   `src/core/llm/*` (ngoài freeze amendment) để ghi được.
5. **`GET /market/context` chưa khai auth cụ thể.** Plan chỉ nói "auth như các route
   khác". Nhưng payload này là **độ mới store cho toàn Universe** — thông tin vận
   hành. Nếu để public (dễ xảy ra vì nó là chip trên empty state, và empty state
   render trước khi biết user), nó thành kênh dò trạng thái ingest. Chốt tường minh.
6. **Test capability contract khi tier đổi hành vi.** `apps/api/tests/test_agent_capability_contract.py`
   khoá 12 tool × 6 thuộc tính (đã xác minh: đúng 12 tên, đúng 6 phần tử tuple).
   Không phase nào thêm/bỏ tool → test này an toàn. **Nhưng** nó cũng import
   `messages.summarise_call`/`STORE_KIND` và `prompt/contract.py:172` gộp
   `tool_signature` vào cache key; phase 10 sửa `messages.py` và phase 09 sửa
   `loop.py` → cần một dòng trong hai phase đó nói "không đổi tool signature,
   không đổi `summarise_call`". Hiện không có.

---

## MINOR (11, không mở rộng)

1. `plan.md` §Authority trích `target-architecture.md:264/366/191/215` và
   `investment-intelligence-contract.md:156/177/194` — các dòng đó là **tiêu đề mục**
   ("## Model gateway and routing", "## Non-goals", "## Output contract"…), không
   phải câu được trích. Trích theo mục, không theo dòng.
2. Phase 02 ghi 3 item sidebar disabled ở `sidebar.tsx:191,199`; thực tế ở `:101`
   ("Bộ lọc cổ phiếu"), `:104` ("Báo cáo đã lưu"), `:191` ("Danh mục theo dõi").
   `:199` là `SectionLabel "Hội thoại"`.
3. Phase 02 ghi dev tooling là `dev/canvas-fixture.tsx`; component được mount ở
   `layout.tsx:109` là `dev/canvas-fixture-toolbar.tsx` (ba file trong `components/dev/`).
4. Phase 07 ghi "Inspector đã là `fixed` (`app-shell.tsx:49`, `right-0`)"; `:49` là
   `main`'s `paddingRight`, không phải khai báo fixed của inspector.
5. Phase 01 nói `IconButton` "tự viết" focus ring — nó **đã có**
   `focus-visible:ring-2 focus-visible:ring-ring` (`primitives.tsx:94`); vấn đề là
   trùng lặp, không phải thiếu. Câu "9 control thiếu focus ring" đúng theo scout §12
   nhưng không bao gồm `IconButton`.
6. `docs/text.md:214` nói control "28–34px"; plan.md §Baseline chỉ ghi 28/30px.
   Có thể còn một cỡ 34px chưa kiểm kê.
7. Phase 05 §Overview nói "không cần migration, không bị chặn bởi làn migration"
   nhưng lại là dependency của phase 08 (blocked) → đường tới hạn `01→02→05→08→09`
   khiến 05 đứng trước một phase blocked; không sai nhưng nên nói rõ 05 không bị
   chặn bởi 08.
8. Phase 12 §Architecture nói "bốn luồng × ba viewport… đã cắt xuống 4+4+1 = 9"
   nhưng success criteria viết "Bốn luồng e2e xanh ở 390 · 430" (= 8) "một luồng
   xanh ở 834" (= 9) — trong khi §Requirements nói "e2e phủ 4 luồng chính ở 3
   viewport". Ba cách đếm.
9. Phase 12 tạo 3 spec nhưng đòi 4 luồng; luồng thứ tư (`mobile-drawer`) do phase 07
   tạo. Nêu ra để cổng của 12 không phụ thuộc một file nó không sở hữu.
10. `apps/api/src/agent/router.py` docstring của `DELETE /threads/{id}` (`:297-303`)
    nói "the menu asks the user to confirm" — FE **không** confirm
    (`sidebar.tsx:345-353`). Phase 08 sửa route nên sửa cả docstring, chưa ghi.
11. Research §F (permission/approval + abort) không có phase nào tiếp nhận; báo cáo
    khuyến nghị "chốt trước hình dạng". Không chặn plan, nhưng là mục đã nghiên cứu
    rồi bỏ rơi.

---

## Kiểm chứng đã pass (không tính là phát hiện, ghi để người sau không kiểm lại)

Đúng: alembic một head `e6b3d90c41af` (32 revision, một head) · `PROMPT_VERSION = "2.7.0"`
(`prompt/sections.py:29`) · `CHAT_TOOLSETS = ("web","memory","signals","studies")`
+ 12 tool × 6 thuộc tính · `MAX_TOOL_ROUNDS = 4` (`loop.py:160`),
`MAX_EXTERNAL_TOOL_CALLS = 6` (`:289`) · `llm_model_batch/session`
(`core/config.py:80-81`) · 4 cột `agent_thread` (`alpha/models.py:44-55`) ·
`TOOL_CALL_FIELDS`/`CANVAS_FIELDS`/`snapshot_from_draft` (`agent/events.py:117,135,510`) ·
`outcome_of`/`canvas_of` (`messages.py:359,398`) · `composer.tsx:35`
(WaveformIcon), `:113-118` (Enter), `:183` (Visgnite Pro), `:236` (AttachMenu) ·
`primitives.tsx:96` (`size-7`/`size-[30px]`), `:301` (`UnavailableNote`) ·
`view-chat.tsx:28-30`, `:306-317`, `:506-515` · `overlays.tsx:203,250-252` ·
`shell-state.tsx:141,145,188-195,289,351` · `sidebar.tsx:42-55` (flex wrapper co width),
`:49` (`aria-hidden={!open}` với button vẫn focusable) · `inspector.tsx:68,79,100,120`
+ `alpha/message/message-shell.tsx:29` = đúng 5 nhãn ARIA tiếng Anh ·
`greeting.ts:42-67` hardcode tiếng Anh, `:37-38` docstring stale trỏ `shell/view-new` ·
`market-session.ts:134-139` · `hooks/use-mobile.tsx` zero importer ·
`globals.css` `.light` ~`:135-181` · `e2e/market-monitor.spec.ts` tồn tại,
`e2e/desk.ts:26` `CANONICAL_MARK` · `tests/test_agent_study_tools.py:155,178`
(hai test transcript) · 10/10 vùng bảng "Những phần còn thiếu" đều có phase phụ trách.

Vùng critique **không** có phase: persona Alex "path nhanh theo mã" — phase 05 tường
minh từ chối ("ghi lại, không làm") và không phase nào nhận. Đây là gap scope duy
nhất còn lại so với `docs/text.md`; nếu user yêu cầu "toàn bộ đề xuất" thì cần một
phase 13 (ticker chip → filter theo mã) hoặc một dòng chấp nhận cắt.
