# Roadmap harness AI — Stock_Massive

Authority cho **thứ tự mở năng lực AI** sau pivot harness-first (2026-08-25).
Thay `docs/harness-roadmap.md` và `docs/system-roadmap.md` đã xoá;
`docs/Harness/` là product contract trước pivot — đọc như evidence, không như
thứ tự thi công. Code và test là authority cho hành vi đang chạy: mục nào code
chưa đạt là gap, không phải lý do mô tả code như đã đạt.

## Hai track, một nền

```
┌──────────────────────────────────────────────────────────────────────┐
│  Track S — SIGNAL DESK (paid)                                        │
│  Study deterministic · artifact có as_of · desk theo mã · thesis     │
│  · human approval · proactive scan                                   │
├──────────────────────────────────────────────────────────────────────┤
│  Track C — CORE HARNESS (mọi user)                                   │
│  reasoning · search & tổng hợp · context · tool plane · guardrails   │
│  · memory · evaluator · domain pack · tenant · delegation            │
└──────────────────────────────────────────────────────────────────────┘
```

- **Track C** là nền: AI phải đủ tốt để **hiểu câu hỏi, tìm đúng, tổng hợp có
  bằng chứng, không bịa, không trắng màn hình** — kể cả khi không vẽ gì. Không
  có track C tốt thì Signal Desk chỉ là chart gắn vào chatbot.
- **Track S** là **moat trả phí**: thư viện Study + artifact có bằng chứng,
  render lại được — thứ chatbot không có. Chạy trên niche chứng khoán VN trước.
  `TurnMode="signal_desk"` (`agent/loop.py`) là công tắc; entitlement gắn vào
  tenant/budget ở C6.
- Mỗi phase S ghi rõ phase C nó cần. Không mở S khi C chưa đạt gate.

## Cách đọc một phase

| Trường | Nghĩa |
|---|---|
| **Objective** | AI làm được gì thêm, nói bằng năng lực, không bằng tên module |
| **Trước → Sau** | trạng thái đo được hôm nay và sau khi tốt nghiệp |
| **Boundary** | vì sao tách phase này — theo luật "chỉ split graph khi có boundary thật" |
| **Checklist** | việc phải làm, trỏ owner file/test thật |
| **Gate** | bằng chứng đo được để đánh Current |

Nhãn: **Current** (owner + test) · **Target** (đã chọn kiến trúc) ·
**Conditional** (mở khi gate trước đạt) · **Rejected** (đảo phải có evidence).

---

## 1. Best of the best — lấy gì từ đâu

Ba nguồn: [bài Graph Engineering](https://goonnguyen.substack.com/p/graph-engineering-la-gi),
Hermes (`docs/hermes/hermes-synthesis-260821-0030.md`), OpenCode
(`docs/opencode/opencode-lessons-for-stock-massive.md`). Mỗi dòng đã kiểm trên
code và qua decision filter 4 câu: *sửa failure mode nào · owner nào đổi ·
metric nào chứng minh · lấy invariant nhỏ hơn được không*.

| Nguồn | Bài học | Ta đang ở đâu | Vào phase |
|---|---|---|---|
| Blog | **Node · Edge · State** rõ; loop = graph có cycle | Có: Turn/tool/Study · cycle 4 round · `agent_turn/tool_call/artifact` | C0 |
| Blog | **Contract > free text**; approve vì evidence | Có: `StudyResult.headline/frames`, `outcome_of` | C0 |
| Blog | **Deterministic gate > LLM** | Có cho Study (`runner`), giá (`check_price_claim`). **Thiếu** cho câu trả lời thường: chưa có grader | C4 |
| Blog | **Mỗi node chỉ nhận state nó cần** | Có: frames không vào model, prompt typed | C2 mở rộng |
| Blog | **Coordination cost thật — 1 loop trước, split khi có boundary** | Đúng: 1 loop, không subagent | C7 chỉ mở khi đo được |
| Blog | **Checkpoint · idempotency · retry không duplicate** | Freeze-never-resume có; `ToolIdempotency` khai nhưng nhiều tool `UNKNOWN`, executor chưa dùng | C3 |
| Blog | **Human là một node** | Policy trong prompt; chưa có approval node | S2 |
| Blog | **Evals quyết định graph** | **Một phần, 2026-08-29.** C4-lite ở `apps/api/golden/` — 20 câu web-first, 4 grader deterministic, `make golden-run`/`golden-grade`, ba artifact. Đã quyết hai việc thật bằng số, **không lượt chạy mới nào**: C1 giữ `Target` ở lần chấm đầu, rồi tốt nghiệp `Current` khi authority của `read_depth` chốt về bar từng case — cùng ba artifact, chấm lại miễn phí. Và tiêu chí citation chuyển sang C4 vì đo được là nó bất khả với một grader đọc văn bản. Chưa có LLM judge, chưa fail-closed CI | C4 |
| Hermes | **Guard fail-open**: chậm/rẻ/ồn được, trắng màn hình không | `signal_desk` mode có mã lỗi có tên; lane chat còn cửa `incomplete` | C3 |
| Hermes | **Nudge tổng hợp có trần** thay vì kết thúc Turn | `MAX_EMPTY_NUDGES = 1`, trần theo lần | C3: trần theo tiền + câu backend-authored |
| Hermes | **Progress event mang nội dung thật** (query, số nguồn, domain) | **Đóng 2026-08-29 mà không dựng event nào.** `progress.py` vẫn không tồn tại và `EventType` vẫn đúng 8 member — dữ liệu đã ở trên dây từ trước: query qua `tool.call.summary`, số nguồn + domain trong payload. Việc thật là **vẽ** chúng, và chỗ trống là **branch row** của một round (nơi truy vấn song song rơi vào); `SingleCallRow` đã vẽ sẵn. Đếm **publisher khác nhau**, không đếm kết quả | C1 ✔ |
| Hermes | Quét pattern injection trên nội dung web (lớp duy nhất còn thiếu trong 5 lớp) | **Đóng 2026-08-29.** `untrusted.scan_for_threats` + `threat_patterns.py`: 2 scope (`strict` loại có lý do — nó bảo vệ agent ghi được filesystem), NFKC + 17 ký tự ẩn/bidi, fail-open tuyệt đối, trần 0,25 s, quét ở executor **đúng một lần mỗi kết quả**. Đo trên corpus: **0 `risk: high` / 97 kết quả** trang lành — chứng minh không kêu bậy. Nửa "bắt được injection thật" chứng minh **2026-08-29** bằng 11 test tích hợp đi đúng đường production tới persist/reopen, non-vacuity bằng mutation | C1 ✔ |
| Hermes | **Ký ức đi qua tool**, không chèn free-text vào prompt | Đúng: `remember_fact/recall_facts` | C5 giữ |
| Hermes | **Không copy**: sandbox, TUI, 7 tầng fallback, SQLite, MoA | — | Rejected |
| OpenCode | **Capability resolution plane** một declaration | `ToolEntry` đã gom schema/trust/idempotency/concurrency | C3 hoàn thiện |
| OpenCode | **Deterministic prune trước lossy summary** | Chỉ compaction khi overflow (`MAX_CONTEXT_COMPRESSIONS = 2`) | C2 |
| OpenCode | **Progressive instruction loading** | Prompt nạp mọi domain mọi turn | C5 |
| OpenCode | **Subagent = child session, permission cha không mặc nhiên là của con** | Chưa có | C6 (permission) → C7 |
| OpenCode | **Hidden specialist chỉ cho task phụ có contract nhỏ** | Chưa có | C7 |
| OpenCode | **Typed part/state tại storage** chỉ khi cần resume | Freeze-never-resume | C3 Conditional |
| OpenCode | **Không port**: server thứ hai, coding tools, plugin npm, MCP marketplace | — | Rejected |

---

## 2. Graph hiện tại (Current)

```
user ──▶ TurnService._execute (turns.py) — TurnMode chat|signal_desk, budget admission
           ▼
        AgentLoop (loop.py) ◀──────────────────────┐ cycle ≤ MAX_TOOL_ROUNDS=4
           │ core/llm: typed errors, compact on     │ MAX_EXTERNAL_TOOL_CALLS=7
           │ ContextOverflow, reduce on OutputCap   │ MAX_EMPTY_NUDGES=1
           ▼                                       │
        executor.run_calls — fan-out song song ────┘ one-call-one-result
           ├─ web      web_search (5 kết quả, 700 ký tự/snippet) · fetch_url (1 trang, 20k ký tự)
           ├─ memory   session_search (8) · remember_fact · recall_facts (5)
           ├─ signals  list_fields · get_field · check_price_claim   (store, trusted)
           └─ studies  list_studies · run_study · get_series · render_signal_desk
                 └─ runner gates ─▶ agent_artifact (frames + as_of) ─▶ headline ≤ ~300 token
           ▼
        events.py SSE ─▶ apps/web    ·    _finish / _finish_bare — hai cửa ra duy nhất
```

Edge **chưa có**: prune trước summary · checkpoint giữa round · evaluator ngoài
luồng · fan-in Study → thesis · human-approval node. (*Nhiều truy vấn web song
song có tổng hợp* đã rời danh sách này 2026-08-29: `parallel_rate` 63% ≥ 50%.)

---

## 3. Track C — Core harness

### C0 — Nền lane chat — **Current**

(Baseline — không có Trước→Sau vì đây là điểm đo gốc.)

Rip-out xong 2026-08-25 (`plans/260826-1920-phase-0-cleanup-and-restore-map/`).
Một loop, 4 bundle, 11 tool, budget arithmetic, typed recovery, repetition
ladder `allow→warn→block→halt`, SSE replay, freeze-never-resume. Đây là
baseline mọi "Trước" bên dưới đo từ đó.

### C1 — Search & tổng hợp có bằng chứng — **Current**

**Objective.** AI tìm rộng hơn, đọc nhiều hơn, tổng hợp thành một câu trả lời
có trích dẫn — và nói thẳng chỗ không tìm được.

| | Trước | Sau |
|---|---|---|
| Truy vấn web / Turn | Song song **đã chạy** — `executor.py:268-278` `asyncio.gather`, `web_search` khai `PARALLEL_SAFE`. Đo 2026-08-29: **8/70 round** (11,4%) có ≥2 truy vấn, max 3; theo đơn vị Turn là 21/43. Trần ≤ 6 external call cắt ngang mục tiêu | 2–3 truy vấn **song song** một round, còn ≥ 2 call để đọc trang. **Làm 2026-08-29:** trần Turn 6 → **7** (`loop.py`), `same_tool_failure_halt_after` đi theo, `PROMPT_VERSION` 2.10.0 thêm section §5 về cách tiêu bảy lượt đó |
| Trang đọc / Turn | Đo hậu rip: **0,3 `fetch_url`/Turn chạm web** (3 call / 10 Turn), 0/10 Turn đọc ≥2 trang; cắt 20k **đầu** trang | 3–4 trang, dedup domain, và một tín hiệu tin cậy domain — repo chỉ có denylist, nên hình dạng tín hiệu chốt ở C1 phase 03 (điểm từ nguồn tìm · bảng tĩnh nhỏ · hoặc chỉ `rank` + `published_at`) |
| Kết quả cho model | snippet 700 ký tự; `published_at` **đã có** (`tools/web.py:503`), thiếu đúng `rank` và tín hiệu tin cậy | **Làm 2026-08-29:** `rank` (1-based, thứ tự nguồn trả) + `relevance` (điểm khớp truy vấn của nhà cung cấp, đặt tên đúng thứ nó đo). **`domain_trust` chốt là không làm** — repo không có whitelist, điểm của Tavily là độ khớp truy vấn chứ không phải độ tin cậy publisher, và một bảng tĩnh tự viết là nợ bảo trì kèm thiên vị. `fetch_url` nhận `looking_for` và trả đoạn khớp, giữ nguyên văn, theo thứ tự trang |
| Câu trả lời | có thể "hiểu 10" nhưng chỉ dẫn được 1 nguồn | mâu thuẫn giữa nguồn **đã được nêu** (đo: wf-011 nêu tên hai nguồn và lượng hoá chênh lệch). Tiêu chí *"mỗi con số ngoài store có citation"* **chuyển sang C4** — nó cần một claim-provenance contract, không đo được bằng grader đọc văn bản trả lời; xem Gate |
| Người dùng thấy | "đang tìm…" | **Làm 2026-08-29:** query nguyên văn đã hiện từ trước qua `tool.call.summary`; phần thiếu là **số publisher khác nhau + domain** trên branch row của một round — chỗ các truy vấn song song rơi vào. Đếm publisher khác nhau chứ không đếm kết quả: năm trang từ hai tờ báo là hai nguồn, vẽ năm dấu là nói câu trả lời được đối chứng gấp hai lần rưỡi thực tế |
| Bảo mật | 4 lớp | **Làm 2026-08-29:** 5 lớp — thêm `scan_for_threats` (NFKC + gỡ 17 ký tự ẩn/bidi, hai scope, fail-open tuyệt đối, trần thời gian 0,25s). Cờ lưu trong `TurnToolCall.as_wire()` → `agent_message.content` JSONB: durable, không migration, không cột trên bảng nóng. **Không bao giờ vào text gửi model** |

**Boundary.** *Concurrency* thật: truy vấn độc lập, `executor` đã song song.
Không cần subagent.

**Checklist**
- [x] Section §5 prompt về cách tiêu bảy lượt tra cứu (truy vấn độc lập cùng round + đọc trang khi snippet không đủ); tỉ lệ round có > 1 `web_search` đo bằng grader `parallel_rate` — `agent/prompt/sections.py`, `test_agent_prompt.py`
- [x] `web_search` trả `rank` + `relevance`; `published_at` đã có; **`domain_trust` bỏ có lý do** (xem cột "Sau"). `fetch_url` trích đoạn theo `looking_for` thay vì 20k đầu trang — `agent/tools/web.py`
- [x] Gộp kết quả trùng trong `messages.display_results`, **phạm vi Turn chứ không phải phạm vi call**. Đo trên tape trước khi viết: 0/53 call search trả URL trùng trong cùng payload, nhưng 21/223 URL (9,4%) xuất hiện ở nhiều call — dedup trong một payload sẽ là code không bao giờ chạy. So sánh bằng `dedup_key` (bỏ fragment · `www.` · trailing slash · tracking param · scheme); **link gửi đi và hiển thị vẫn là link gốc** — `agent/messages.py`, `_TurnState.shown_sources`
- [x] Rail vẽ **số publisher khác nhau** + domain đã có trên dây, trên **cả branch row của một round** — đó là chỗ các truy vấn song song rơi vào và là chỗ duy nhất còn trống; `SingleCallRow` đã có sẵn từ trước. Không `EventType` mới, không `agent/progress.py` — `components/alpha/message/reasoning-timeline.tsx`, `lib/alpha-desk/types.ts::distinctDomains`
- [x] Quét pattern injection trên visible text (mẫu Hermes `threat_patterns`), fail-open: gắn cờ, không chặn. Hai scope (`all` + `context`); **`strict` loại có lý do** — nó bảo vệ agent ghi được filesystem, lane này không có tool nào như vậy. Quét ở `executor` **đúng một lần mỗi kết quả**, không trên đường render — `agent/threat_patterns.py`, `agent/untrusted.py::scan_for_threats`, `agent/executor.py`
- [x] Citation retention: rung 2 của thang trim giữ **danh sách URL của kết quả** (trần 5), bỏ title và snippet; `url`/`query` vốn đã sống trong `arguments` nên không dựng lại — `agent/messages.py::_collapsed_result`, test transcript

**Gate — chạy 2026-08-29, C1 tốt nghiệp, nhãn `Current`.**
Ba lượt Golden Set web-first (n = 20 mỗi lượt), chấm bằng cùng một grader.
Ngưỡng chốt ở `apps/api/golden/README.md`; lý lẽ đầy đủ ở
`plans/reports/phase-08-260829-c1-verification.md`.

| Chỉ số | phase 02 | after 03-04 | **cuối 05-07** | Ngưỡng | |
|---|---|---|---|---|---|
| `distinct_domains` đạt bar từng case | 19/20 | 19/20 | **19/20** | ≥ 18/20 | đạt |
| `read_depth` đạt bar từng case | 11/20 | 19/20 | **18/20** | ≥ 16/20 | đạt |
| `read_depth` ≥ 2 phẳng | 6/20 | 16/20 | **14/20** | — | **dưới khởi điểm 15/20** |
| `parallel_rate` (round có > 1 tìm) | 34% | 63% | **63%** | ≥ 50% | đạt |
| latency P50 | 51,0 s | 63,0 s | **52,4 s** | tín hiệu | đạt |
| chi phí/Turn P50 | 45.484 | 60.107 | **58.222** µUSD | < 500.000 | đạt |
| `uncited_external_number` | 11/16 | 12/16 | **11/16** | **không gate** | **công cụ hỏng** |

**Ba gate đạt, tiêu chí thứ tư chuyển chủ.** `distinct_domains` 19/20 (≥18),
`read_depth` 18/20 theo bar của từng case (≥16), `parallel_rate` 63% (≥50%).

`read_depth` có **đúng một** authority: **bar của từng case** (`expect.min_pages_read`).
Phát biểu phẳng `fetch_url ≥ 2` cho 14/20 là **diagnostic**, không phải gate — nó
không đọc bar của case, nên một case khai `min_pages_read: 1` bị nó tính là trượt
dù đúng hợp đồng. Ngưỡng sống một chỗ: `apps/api/golden/README.md`.

**Tiêu chí *"số ngoài store không citation = 0"* chuyển sang C4, không bị bỏ.**
Đo 2026-08-29 (`plans/260829-1945-c1-evidence-graduation/reports/phase-01-260829-derivation-depth.md`):
nó **không đo được bằng một grader đọc văn bản trả lời**, và đó là kết luận số
học chứ không phải thiếu công sức. Tập premise của một case là 109–310 số, và
**sau khi siết ba chiều** (chỉ hệ số độ lớn · toán hạng ≥3 chữ số nghĩa · bỏ ×100)
tập toán hạng vẫn còn **38–221 số**. Một phép `+ − × ÷` trên tập đó chạm
**92,7–100%** toàn bộ không gian giá trị ba chữ số ở **bốn trên năm** case
(`wf-012` 55,2%, tập nhỏ nhất), nên mọi số bịa cũng tìm được "witness":
false-accept **39/40**. Bỏ phép nhị phân thì recall sập còn **3/9**. Muốn
false-accept dưới 5% thì tập toán hạng phải **≤8 số** — bất khả. Đo được nó cần runtime **ghi lại provenance của từng khẳng định**, tức
một hợp đồng mới, và đó là C4.

**Đính chính report cũ:** không phải "5/5 false positive" mà là **4/5**. `wf-012`
là finding **thật** — câu trả lời nói room ngoại HPG tối đa `100%`, và không trang
nào trong bằng chứng của case nói trần room của HPG (kết quả gần nhất là một doanh
nghiệp khác "nới room lên 50%"). Đó là hằng số model tự cấp. 8/9 số bị gắn cờ là
suy diễn hợp lệ, 1/9 là finding thật. Report gốc giữ nguyên, không viết lại.

**Một confound phải đọc kèm mọi delta:** lượt cuối chạy ở `PROMPT_VERSION` 3.0.0
còn lượt trước ở 2.10.0 — chênh lệch đó là của **C5**, không phải của phase
05–07 (không phase nào trong ba phase sửa `prompt/sections.py`). Số duy nhất quy
chắc chắn cho C1 là **nguồn/lượt tìm 5,13 → 3,96 (−22,8%)** ở `MAX_RESULTS = 5`
không đổi — dedup là phép biến đổi cơ học, độc lập prompt. Nghĩa là **1,17 trong
mỗi 5 kết quả** một truy vấn trả về đã được một call trước của cùng Turn vẽ rồi.
Nguồn được vẽ giảm 18,4% mà `distinct_domains` giữ nguyên 19/20 — bỏ bản trùng,
không bỏ phạm vi phủ.

**Lớp quét injection — cả hai nửa, 2026-08-29.** Nửa *"không kêu bậy"*: corpus
cho **0 `risk: high`, 0 `unknown` / 97 kết quả** trang thị trường lành. Nửa *"có
bắt được injection thật không"* **không** chứng minh được bằng corpus — trang thật
model đọc không mang injection, và corpus không dựng được nội dung trang — nên nó
chứng minh bằng **11 test tích hợp** đi đúng đường production: văn bản
tấn công từ handler ngoài → `executor` quét **đúng một lần** dù transcript dựng lại
ba lần → `as_wire` → `agent_message.content` JSONB → mở lại thread và
`golden.run.read_case` đọc ra **cùng một verdict**. Ba trạng thái đều phủ
(`high`/`low`/`unknown` khi scanner hỏng, fail-open, câu trả lời vẫn chạy), và
**không** ký tự nào của kẻ tấn công hay `risk` nào lọt vào transcript gửi model.
Non-vacuity chứng minh bằng mutation: bỏ `scan` khỏi `as_wire` → test đỏ. **0 file
production phải sửa** — chuỗi đã đúng từ trước, thứ thiếu là bằng chứng.

**Việc còn lại, đã chuyển chủ:** claim-provenance contract → **C4** ·
`read_depth` phẳng ở n lớn hơn → diagnostic, không chặn ·
hiển thị cảnh báo quét trên rail → vẫn tắt (0/97 không phân biệt "không kêu bậy"
với "không kêu").

### C2 — Context & cache — **Target**

**Objective.** AI nhớ đúng thứ cần trong một Turn dài, rẻ hơn, không mất trích
dẫn khi bị nén.

| | Trước | Sau |
|---|---|---|
| Khi vượt context | Thang trim deterministic **đã có 4 rung** (`messages.py:958-993`: nguyên vẹn → gộp result cũ → bỏ Turn cũ → gộp result của Turn được bảo vệ), rồi mới `MAX_CONTEXT_COMPRESSIONS = 2` | prune theo layer đo được, summary sau, đo từng bước |
| Cache prefix | `cache_key()` có, `cache_control` chưa bật | bật khi route probe `prompt_cache_control=True` |
| Biết token đi đâu | không | đo theo layer: system · history · tool results · headline |
| Kết quả tool cũ | giữ nguyên văn | thay bằng trace handle, giữ cái đang trích dẫn |

**Boundary.** *Context boundary* (blog G4): owner `messages.py` + `core/llm`,
tách khỏi domain pack để hai owner không đổi cùng lúc.

**Checklist**
- [ ] Instrument input composition theo layer — `agent/messages.py`
- [ ] Prune deterministic: bỏ duplicate snippet, thay old full result bằng handle, bảo vệ user intent gần nhất + result đang trích dẫn
- [ ] `cache_control` thật — `core/llm/config.py::prompt_cache_control`
- [ ] **Nối dây khoá cache của C5**: `prompt.cache_key` đã nhận `pack_identity`
      **bắt buộc** và `DomainPack.identity` đã hash version + prose, nhưng
      **chưa có caller runtime nào** — hai pack khác nhau chưa từng sinh ra hai
      khoá khác nhau ngoài test. Bật cache mà bỏ qua tham số đó là cho Turn của
      pack thứ hai dùng prefix của pack thứ nhất
- [ ] **Chỗ đúng của body pack khi cache bật**: hôm nay body là system note dán
      đuôi mỗi call, nên khi `prompt_cache_control` bật nó trả giá đầy đủ mỗi
      lần. Đường di trú đã ghi sẵn ở `plans/260829-1435-c5-domain-pack/phase-05`:
      block thứ hai ngay sau core, breakpoint mới, body cached từ call thứ hai.
      C2 sở hữu quyết định này, C5 cố ý không dựng sẵn
- [ ] Test replay: citation retention không giảm sau prune

**Gate.** Context token/Turn giảm ≥ 20% trên replay corpus; grounding và
citation retention không giảm.

### C3 — Tool plane, failure boundary, guardrails — **Target / Conditional**

**Objective.** AI sai thì sửa được giữa đường, không đốt tiền lặp lại, không
trắng màn hình; tool nào lặp lại an toàn thì hệ thống biết.

| | Trước | Sau |
|---|---|---|
| Model sai hợp đồng | 1 nudge rồi kết thúc `incomplete` | nudge có trần **theo tiền**; hết trần → trả lời kèm câu backend nêu chỗ không chứng minh được |
| Idempotency | khai `UNKNOWN` phần lớn | mọi tool khai thật; executor không retry `NON_IDEMPOTENT + WRITE` |
| Crash giữa Turn | tính lại từ đầu | artifact/series đã persist được đọc lại (checkpoint trong Turn) |
| Resume sau restart | không (cố ý) | vẫn không — *Conditional*: chỉ khi product cần postmortem |

**Boundary.** *Failure boundary* (blog G6).

**Checklist**
- [ ] Trần nudge theo chi phí, câu backend-authored — `loop.py::MAX_EMPTY_NUDGES`, `agent/grounding`
- [ ] Điền `ToolIdempotency/ToolEffect` thật; executor tôn trọng — `registry.py`, `executor.py`, `test_agent_tool_executor.py`
- [ ] Checkpoint: `get_series` persist như Study — `studies/frames_buffer.py`
- [ ] *Conditional*: typed lifecycle `pending/running/completed/error/interrupted` tại storage owner — ghi quyết định trước

**Gate.** Turn `incomplete` vì sai hợp đồng giảm về ~0 trên Golden Set; không
retry nào chạm tool non-idempotent; replay 100 Turn không có `tool_calls` mồ côi.

### C4 — Evaluator plane — **Target** (cửa vào C7, S1)

**Objective.** Biết AI dở ở đâu bằng số, trước khi thêm node hay bán tính năng.

**C4-lite đã dựng sẵn một phần ở C1 (2026-08-29).** `apps/api/golden/` — corpus 20
câu web-first, grader deterministic bốn chỉ số, `make golden-run`/`golden-grade`,
ba artifact đã chạy. Nó **không phải** C4: không LLM judge, không CI fail-closed,
không replay từ Turn thật. C4 tiếp tục từ đó chứ không dựng lại từ đầu.

**C1 để lại cho C4 một câu hỏi đã đóng và một việc mở.** Đóng: *"grader thấy được
số suy diễn"* là **ngõ cụt đã đo**, đừng thử lại — chi tiết ở
`plans/260829-1945-c1-evidence-graduation/reports/phase-01-260829-derivation-depth.md`.
Mở: đo citation cần đổi **thứ runtime phát ra**, không phải đổi grader.

| | Trước | Sau |
|---|---|---|
| Đo chất lượng | **Có một phần** — C4-lite: 20 câu + 4 grader deterministic, chạy được bằng `make`, chấm lại cho kết quả giống hệt | + LLM judge offline; + corpus ngoài họ web-first |
| Chặn hồi quy | review tay | gate fail-closed trên PR đổi prompt/prune/tool |
| Baseline | **Có cho họ web-first** — `distinct_domains` · `read_depth` · `parallel_rate` · latency P50 · chi phí/Turn, ngưỡng chốt ở `golden/README.md` | + grounding · empty-after-tools · invalid args · warn/block/halt · token |
| Citation | **C4 sở hữu tiêu chí này từ 2026-08-29** (chuyển từ C1). Đo được rồi: một grader đọc văn bản trả lời **không thể** phân biệt số suy diễn thật với số bịa — tập toán hạng sau khi siết vẫn 38–221 số, một phép nhị phân chạm 92,7–100% không gian giá trị ở bốn trên năm case. `uncited_external_number` ở lại như phép đếm, không gate | **claim-provenance contract**: runtime ghi premise + phép biến đổi cho từng khẳng định, grader **verify** thay vì **tìm kiếm** |

**Boundary.** Evaluator là node **ngoài luồng** — không tăng latency người
dùng (blog G3/G8).

**Checklist**
- [x] Golden Question Set — **họ web-first xong** (20 câu, 4 họ, `golden/web_first.json`). Còn: câu về Study/field và refusal mong đợi
- [ ] **Corpus web-first đã chạm store nhiều hơn tưởng**: đo trên
      `web-first-v1-final.json`, **11/20 case** gọi tool domain (`list_fields`,
      `check_price_claim`, `get_field`, `run_study`) dù không câu nào *hỏi* về
      store. Câu "không family nào hỏi store" đúng về đề bài, sai về hành vi —
      nên corpus này **có** đo lượt chạm domain, chỉ là đo tình cờ. Một family
      store-first cố ý vẫn cần, để lượt chạm domain được chấm bằng kỳ vọng chứ
      không phải bằng may rủi
- [ ] **Artifact ghi danh tính pack**: `run.py` ghi `PROMPT_VERSION` trong
      `runtime_constants` (đủ để nhận ra lượt nào chạy dưới prompt hai tầng),
      nhưng **không ghi `DomainPack.identity`** — hai lượt dưới hai pack body
      khác nhau sinh metadata không phân biệt được. Một dòng, cùng chỗ
- [~] Grader deterministic — **bốn cái chạy**; `citation còn?` **cần claim-provenance contract**, không phải grader tốt hơn (xem bảng trên). Chưa có: có desk? đúng Study? `outcome` khớp? frames không lọt?
- [ ] LLM judge chỉ grounding/completeness, có CI
- [ ] Replay từ `agent_turn` thật ẩn danh, không gọi provider — C4-lite tape **web** ở `WebLane.read`, model vẫn live; replay Turn là việc khác
- [~] `make golden-run`/`golden-grade` có, JSON là authority. Còn: **gate policy fail-closed**

**Gate.** Baseline đầu ghi được; một PR cố ý làm giảm grounding bị chặn.

### C5 — Domain pack + progressive instruction — **Current**

**Objective.** AI chỉ mang playbook cần cho câu hỏi; đổi domain không sửa
loop.

| | Trước | Sau |
|---|---|---|
| Prompt | mọi playbook mọi turn (6.097 token) | core 5.449 token luôn nạp; body 685 token nạp theo mode/lịch sử/tool path |
| Domain | `signals`+`studies` hardcode là chứng khoán | pack `vn-equity` `2.0.0`; `web`+`memory` là `CORE_TOOLSETS` |
| Thêm tool/Study | sửa nhiều bảng tên | một declaration, cổng import-time giữ đồng bộ |

**Boundary.** *Context* + *contract* (blog G2/G4; OpenCode progressive
disclosure).

**Checklist**
- [x] `DomainPack`: `name·version·prompt_sections·toolsets·universe·study_names` — `agent/domain/`
- [x] `CHAT_TOOLSETS` sinh từ pack, vẫn viết ra được; `AgentLoop(toolsets=None)` mặc định đúng — `test_agent_domain_pack.py`
- [x] Section domain tách core; `PROMPT_VERSION` `3.0.0`; `render()` vẫn typed — `test_agent_prompt.py`
- [x] Refusal vocabulary theo pack: `alpha/reasons.py` ↔ `apps/web/src/lib/signal-issues.ts`
- [x] Memory vẫn qua tool, không free-text vào prompt (Hermes)

**Gate.** Đổi pack không sửa `loop.py` — **đạt**, chứng minh bằng test đổi pack
giả rồi quan sát tool surface, `CHAT_TOOLSETS` và body prompt đổi theo trong khi
`loop.py` không mang tên pack nào (`test_agent_domain_pack.py`). Input token/Turn
giảm — **đạt, đo end-to-end** trên `golden/artifacts/web-first-v1-final.json`
(20 case, 78 lượt gọi model, chạy dưới `PROMPT_VERSION 3.0.0`): **47 call mang
core-only, 31 call mang core+body** → net **−34.197 token / 20 case = −438
token/call = 7,0%** input của lượt chạy. Trên bản đã kéo một đoạn về core
(xem §Quy ước) là **−376 token/call ≈ 6,0%**.

Con số này **không có confound C1**: nó không so hai artifact, nó suy ra từ chính
cấu trúc call của một lượt chạy — mỗi call trước khi Turn chạm domain tiết kiệm
đúng phần core ngắn đi, mỗi call sau đó trả thêm đúng phần body dài hơn phần đã
cắt.

**Watch chưa phân xử — vế "Golden Set không giảm".** Grader C1 trên cùng hai
artifact: **3 finding mới đỏ** (`wf-005` + `wf-012` `uncited_external_number`,
`wf-012` `read_depth`), **1 xanh lại** (`wf-007`). Cả ba cái mới đi cùng **đọc ít
trang hơn**. Tách theo nhóm: 11 case **chạm** domain (được body bù lại) `fetch_url`
24 → 24 (**±0**); 9 case **không** chạm (mất hẳn đoạn *"web không phải phương án
dự phòng mà là nguồn duy nhất… bỏ phần đó là trả lời thiếu"*) 34 → 29 (**−15%**).
Hướng khớp giả thuyết, nhưng **không kết luận được**: −5 fetch do đúng hai case
kéo (`wf-008` 7→4, `wf-009` 7→3) trong khi hai case khác tăng, và hai lượt lệch
nhau **cả** C5 **lẫn** C1 phase 05-08. Replay (`golden/run.py::ReplayLane`)
**không** cô lập được biến này — đổi hành vi thì đổi truy vấn, đổi truy vấn thì
miss tape, và một artifact replay thiếu bị chính runner đánh dấu không so được.
n=20 với phương sai này không phân xử nổi.

**Phản ứng đã ghim, chưa kích hoạt.** Nếu một corpus lớn hơn (hoặc family
store-first của C4) xác nhận cú giảm: chuyển đoạn *"Nhưng store chỉ có ba trục…
Nên với một mã: đọc field trước, rồi tra web…"* từ `agent/domain/vn_equity.PLAYBOOK`
về core, cùng lý lẽ đã dùng cho *"Bạn KHÔNG đọc được…"* — một câu đẩy hành vi
đọc web là luật chung mặc từ vựng domain. **Không** thêm trigger thứ tư.

**Plan.** `plans/260829-1435-c5-domain-pack/` — 6 phase, xong 6/6.
**Report.** `plans/reports/cook-260829-1717-c5-phases-04-05-06.md`.

### C6 — Tenant, permission, entitlement — **Target**

**Objective.** Ai được đọc gì, ai trả tiền gì, ai được bật Signal Desk.

| | Trước | Sau |
|---|---|---|
| Thread/memory | theo user, `agent_knowledge.user_id` cho phép NULL | theo `(tenant, user)`, cô lập tenant |
| Budget | envelope $45 chưa reweight | ledger khoá `(tenant, user)`; route thuê bao đặt 4 giá trị về 0 |
| Signal Desk | ai cũng bật được | entitlement theo tenant/plan — **đây là ranh giới paid** |

**Boundary.** *Permission boundary* (blog; OpenCode: quyền cha không mặc
nhiên là của con).

**Checklist**
- [ ] Bảng `tenant` + FK `agent_thread`, `agent_knowledge` — revision mới, **backup trước**
- [ ] `ToolContext.tenant_id`; tool store lọc theo tenant — `registry.py`
- [ ] Budget ledger `(tenant, user)` — `agent/budget.py`
- [ ] `TurnMode="signal_desk"` kiểm entitlement ở `turns.py`; từ chối có mã tên
- [ ] SSE/memory không rò chéo tenant — `test_agent_turn_events.py`, `test_agent_memory_tools.py`
- [ ] Hard freeze mở rộng: `src/agent/*` + `src/auth/*` + `src/core/config`

**Gate.** Hai tenant song song, 0 row chéo; user không entitlement gọi
`signal_desk` nhận mã lỗi, không nhận desk.

### C7 — Delegation có điều kiện — **Conditional** (cần C4)

**Objective.** Thêm node chỉ khi đo được nó rẻ hơn hoặc tốt hơn một loop.

| | Trước | Sau (nếu đạt gate) |
|---|---|---|
| Task phụ (title, summary) | model chính | specialist rẻ, contract ≤ 1 KB, fail-open |
| Scout song song | không | chỉ khi C1 fan-out trong một loop không đủ |
| Subagent | không | child Turn, `ToolContext` riêng, `deny` truyền xuống, parent nhận tóm tắt |

**Gate.** Uplift trên Golden Set vượt overhead token+latency với CI đủ; không
đạt → ghi Rejected, giữ một loop.

### C8 — Domain pack thứ hai — **Target** (cần C5)

**Objective.** Chứng minh harness không giả định chứng khoán. Không import
`stocks/*`; ≥ 1 Study + 1 widget mới qua registry; lint chặn import chéo.

**Nợ C5 giao lại, phải trả trước khi pack thứ hai bật:**
- `loop.py` còn **đúng hai** tên tool domain hardcode — `CATALOG_TOOL =
  "list_studies"` và `RUN_TOOL = "run_study"`, cho log "Turn đọc catalog mà
  không chạy Study nào". Nợ có **trước** C5 và thuộc việc khác (bản ghi về
  *recipe còn thiếu*), nhưng nó là thứ duy nhất còn lại làm `loop.py` biết
  domain nào đang chạy. Một test giữ nó ở đúng hai dòng
  (`test_agent_domain_pack.py::test_the_loop_names_no_particular_domain`) —
  mention thứ ba của bất kỳ tool domain nào là đỏ. Chuyển log đó lên pack là
  việc của phase này
- Luật lint "pack không import `stocks/*`" phải là **per-pack, không phải
  per-package**: hôm nay `vn_equity.py` **buộc** phải import `stocks.universe`
  và `stocks.signals.issues` để khai `universe` bằng chính callable tool đang
  dùng, còn `pack.py`/`__init__.py` thì không được import gì. Chốt luật trước
  khi viết pack thứ hai

**Gate.** 100% test pack cũ xanh khi pack mới bật.

---

## 4. Track S — Signal Desk (paid)

### S0 — Runtime qua Study — **Done** (còn đóng nhánh)

**Objective.** Hỏi một câu, nhận một desk có số thật, `as_of` đóng băng, mở
lại không tính lại.

| | Trước (chat thuần) | Sau |
|---|---|---|
| Câu hỏi phân tích | văn xuôi | Study chạy, desk 3–5 block, headline ≤ 300 token cho model |
| Số | model có thể bịa | engine tính, model không thấy `frames` (test transcript giữ) |
| Mở lại thread | tính lại / mất | render lại artifact |

Đã xong: contracts · registry/runner 2 gate · 3 Study (`intraday_liquidity`,
`entry_condition_review`, `earnings_dislocation`) · bundle `studies` ·
`frames_buffer` · widget catalog versioned · `TurnMode=signal_desk` · spine
daily/intraday vnstock · từ vựng `signal_desk` (revision `f8c2d4a96e17`).

**Price basis spine xong 2026-08-29** — plan
`plans/260828-2126-price-basis-and-signal-field-spine/`, 9/9 phase. Signal Field
đã rời giá FiinQuant sang `bar_daily`, và nguồn vi phạm licence đã bị xoá khỏi cả
code lẫn DB (71.773 dòng, revision `a3f7e21b8d54`). Registry 30 → **33 field**
(thêm ba `earnings.*`). Đo thật trên store: VCB 25 phục vụ / 8 từ chối · VNM và
MWG 26/7 — mọi refusal trỏ đúng input thiếu. Chi tiết ở
`plans/reports/phase-0{5,6,7,8,9}-*.md`.

**Hai nợ vận hành đã trả 2026-08-29** (đề xuất ở
`plans/reports/proposal-260829-0034-backfill-schedule-and-band-check.md`):

- **Spine có người nạp.** `backfill_daily` giờ (a) lấy slot từ arbiter hạn mức
  vnstock có sẵn thay vì gọi không giới hạn — nó vốn bỏ qua `core/quota.py` hoàn
  toàn, lane `BACKFILL` đã tồn tại và nhường caller có người chờ; (b) đăng ký vào
  seam scheduler có sẵn, ba scope nối tiếp 16:30 giờ VN, **mặc định tắt**;
  (c) API startup cảnh báo khi spine stale, vì trước đó `spine_freshness` không có
  caller nào ngoài `main()` của chính job.
- **Nhánh BAND của `check_price_claim` sống lại.** Cổng cũ kiểm nhãn `RAW`; thay
  bằng hai cổng giá — lưới bước giá (`price_band.off_tick_grid`) cộng ex-date giữa
  phiên neo và phiên đích. Đo trên store thật: 30/30 mã declared `within_band`
  cho giá đúng và `exceeds_band` cho giá bịa, từ 0/30 `unverified` trước đó.

- [x] Năm cổng xanh — `make test` **1449 passed**, `make lint`, và bốn cổng web (`type-check`, `lint`, `test` **750 passed**, `build`). Đo 2026-08-29; hai con số này còn nhích lên vì việc song song trong cây, cổng là *xanh* chứ không phải con số
- [x] Plan `plans/260826-2158-study-artifact-canvas/` ghi xong — 10/10 phase done; hai mục hoãn 08b/09b giao qua `plans/260828-2126-price-basis-and-signal-field-spine/` (đóng 2026-08-29, 9/9 phase)
- [x] Plan `plans/260828-2126-price-basis-and-signal-field-spine/` ghi xong — Signal Field rời giá FiinQuant sang `bar_daily`; nguồn vi phạm licence xoá khỏi code **và** DB
- [x] Ba Study end-to-end trên store thật + `test_agent_signal_desk` xanh — xem bảng Gate dưới
- [x] `alembic heads` một head duy nhất — `a3f7e21b8d54`

**Việc còn lại không phải tiêu chí của S0.** Đóng nhánh
`feat/study-canvas-runtime` là bước VCS, không phải điều kiện để "runtime qua
Study" chạy được — nó là mục duy nhất trong toàn file roadmap từng gộp một bước
git vào checklist kỹ thuật, nên nó ra khỏi checklist và nằm đây. Trạng thái
2026-08-29: chưa commit, và cây làm việc đang giữ việc chưa xong của hai session
khác, nên commit lúc này sẽ gộp cả phần của họ. Merge là quyết định của người,
sau khi cây sạch.
- [x] Contract test cố định "frames không vào message" ở tầng transcript — `tests/test_agent_study_tools.py::test_the_frames_are_absent_from_the_messages_a_turn_would_send` + `::test_the_frames_stay_out_of_a_signal_desk_turn_too`

**Gate — đạt, đo 2026-08-29 trên store thật (không phải fixture).**

| Study | Kết quả |
|---|---|
| `intraday_liquidity_profile` (VCB) | 4 block · frames `tiles` 4 · `profile` 16 · `heatmap` 30 · `ranking` 16 |
| `entry_condition_review` (VCB) | 5 block · frames `price_context` 250 · `earnings_quarters` 8 · `conditions` 6 |
| `earnings_dislocation_screener` (declared) | 4 block · frames `scatter` 30 · `ranking` 10 · `filters` 12 |

`as_of` phiên 2026-08-27, Universe 30 mã. `test_agent_signal_desk` **11 passed**.

### S1 — Thư viện Study + desk theo mã — **Conditional** (cần C4 — C1 ✔ 2026-08-29)

**Objective.** Một mã → nhiều góc nhìn trong một Turn; Study đủ nhiều để câu
hỏi thường gặp có công thức.

| | Trước | Sau |
|---|---|---|
| Study | 3 | ≥ 10, mỗi cái có Golden question |
| Study / Turn | 1 | fan-out 2–4 Study song song, budget theo Study |
| Desk | một Study một desk | một desk gom nhiều Study cho một mã |

**Checklist**
- [ ] `run_study` nhận nhiều params một round — `agent/tools/studies.py`
- [ ] Widget fan-in versioned; `MAX_SIGNAL_DESKS_PER_TURN` reweight — `studies/widgets.py`, `frames_buffer.py`
- [ ] Mỗi Study mới kèm Golden question (C4) và refusal vocabulary

**Gate.** ≥ 10 Study; Golden Set nhóm `signal_desk` pass ≥ 90% grader
deterministic.

### S2 — Thesis + human approval — **Conditional** (cần S1, C3, C6)

**Objective.** Nhiều Study → một thesis có bằng chứng, `Provenance` trỏ về
từng Study con; khuyến nghị có giá chỉ hiện sau khi người dùng xác nhận đã
đọc bằng chứng; mở lại sau 30 ngày thấy đúng bằng chứng lúc đó.

| | Trước | Sau |
|---|---|---|
| Kết luận | văn xuôi trong chat | artifact thesis, render lại được |
| Khuyến nghị có giá | policy trong prompt | node approval, event SSE riêng |

**Checklist**
- [ ] Row *"Nghiên cứu sâu"* trong `AttachMenu` (`components/shell/composer.tsx`)
      bỏ badge *Sắp ra mắt* và nối vào lane này — plan
      `plans/260829-0010-composer-attachments/` dựng năm row còn lại và để đúng
      row này chờ ở đây. Nó thuộc S2 chứ không phải S1 vì "nghiên cứu sâu" là
      **nhiều bước tổng hợp thành một thesis có `Provenance`**, tức chính
      Objective của phase này; S1 chỉ fan-out Study song song trong một Turn.
      Khác `260827-2325/phase-09` — phase đó là control **độ sâu của một câu trả
      lời** trong một lượt, không phải một chế độ nhiều bước.

**Gate.** 0 Turn phát khuyến nghị có giá thiếu bằng chứng; thesis render lại
sau 30 ngày không tính lại.

### S3 — Proactive scan — **Conditional** (cần S2, C6)

**Objective.** Desk tự quét Universe theo lịch và để sẵn artifact chờ người
xem — người dùng mở app thấy việc đã làm, không phải hỏi mới có.

| | Trước | Sau |
|---|---|---|
| Kích hoạt | chỉ khi người dùng hỏi | job theo `trading_day` sau phiên đóng, quota/tenant |
| Kết quả | trong thread | artifact "chờ xem" gắn tenant, có `as_of`, không push |
| Notification | không | chỉ mở khi có quyết định trigger/quota (câu hỏi mở) |
| Broker/order | không | vẫn không — Rejected |

**Boundary.** *Permission* (quota, ai được scan gì) + *human responsibility*
(máy đề xuất, người mở xem).

**Checklist**
- [ ] Job scan theo lịch trên `trading_day`, idempotent theo `(tenant, symbol, as_of)` — owner mới trong `src/studies/`
- [ ] Quota scan/tenant trong budget ledger — `agent/budget.py`
- [ ] Surface "chờ xem" trong Signal Desk tab; đọc lại artifact, không tính lại
- [ ] Không có đường tới broker/order — test khẳng định không tool nào `WRITE` ra ngoài

**Gate.** Scan chạy đúng lịch 5 phiên liên tiếp, 0 artifact trùng, chi phí
scan/tenant dưới quota; 0 notification khi chưa có quyết định trigger.

---

## 5. Rejected và Conditional

| Mục | Trạng thái | Lý do |
|---|---|---|
| Coding tools, sandbox, TUI, LSP, computer-use | Rejected | ngoài threat model |
| HTTP server + SDK thứ hai | Rejected | FastAPI + SSE đã là product server |
| Plugin npm / host shell | Rejected | supply-chain risk |
| MCP marketplace generic | Conditional | khi có provider cụ thể, data contract rõ |
| Background multi-agent, MoA cho answer chính | Conditional (C7) | chưa có uplift đo được |
| Ký ức free-text vào system prompt | Rejected | phá `_assert_no_formatting_hole` |
| Fallback 7 tầng provider, credential pool | Rejected | route cố định |
| Resume Turn sau restart | Conditional (C3) | freeze-never-resume đang bảo vệ transcript |
| Gửi lệnh tới broker | Rejected | decision support only |
| Realtime path | Conditional | sau C8, chỉ vnstock Diamond |
| DNSE / FiinQuant / CafeF | Rejected | vi phạm điều khoản — đã rip |

---

## 6. Dependency

```
C0 ─▶ C1 ─▶ C2 ─▶ C3 ─┐
                       ├─▶ C4 ─▶ C7
C5 ─▶ C6 ──────────────┘    │
      │                     ▼
      └─▶ C8         S0 ─▶ S1 ─▶ S2 ─▶ S3
                     (C1,C4)  (C3,C6)  (C6)
```

**Trạng thái cạnh C0→C1, 2026-08-29 — đóng.** C1 mang nhãn **`Current`**: ba gate
đo được đều đạt (`distinct_domains` 19/20 · `read_depth` 18/20 · `parallel_rate`
63%), và lớp quét injection đã chứng minh đầu-cuối qua persist/reopen. **C2 mở.**

Tiêu chí citation **chuyển sang C4** thay vì giữ C1 ở `Target`, và lý do là cạnh
trong chính sơ đồ này: **C4 phụ thuộc C1**. Để C1 chờ công cụ mà chỉ C4 dựng được
là khoá chết vòng tròn. Nó không bị bỏ — C4 khai nó thành claim-provenance
contract, và ngõ cụt "grader số suy diễn" đã đo xong nên C4 không phải trả lại
tiền học phí đó.

C1–C3 (owner `tools/web`, `messages`, `executor`) và C5–C6 (owner `prompt`,
`toolsets`, `auth`, `budget`) không giao nhau về file → chạy song song hai
worktree được. C4 cần C1 (câu hỏi web-first) và C5 (pack quyết định Golden
Set). Mọi S fail-closed sau C4.

## 7. Bảo trì

- Cập nhật khi phase đổi nhãn, gate đổi số, hoặc mục Rejected bị đảo bằng
  evidence. Benchmark/incident link ra `plans/reports/`, không ghi vào đây.
- Mỗi checklist khi làm mở plan ở `plans/`; plan trỏ ngược về phase.
- CLAUDE.md thắng cho "đang chạy hôm nay", roadmap thắng cho "làm tiếp gì".
- Ý tưởng mới từ blog/Hermes/OpenCode qua decision filter 4 câu trước khi vào
  checklist.

## Câu hỏi chưa giải quyết

1. Ranh giới paid: Signal Desk là toàn bộ `TurnMode=signal_desk`, hay chat
   thường vẫn được 1 Study/ngày làm mồi?
2. Decision support vĩnh viễn hay có ngày xuất lệnh — định hình S2/S3.
3. Trần nudge theo tiền trên envelope $45/tháng là bao nhiêu?
4. Golden Question Set ai sở hữu/chấm — cần người hiểu thị trường VN.
5. Domain thứ hai cho C8?
6. Turn cũ trong DB còn `agent_tool_call.name="render_canvas"` — migrate dữ
   liệu hay chấp nhận trace cũ không gắn thẻ desk?
