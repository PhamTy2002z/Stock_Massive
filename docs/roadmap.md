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
| Blog | **Evals quyết định graph** | Đã rip 2026-08-22, chưa dựng lại | C4 |
| Hermes | **Guard fail-open**: chậm/rẻ/ồn được, trắng màn hình không | `signal_desk` mode có mã lỗi có tên; lane chat còn cửa `incomplete` | C3 |
| Hermes | **Nudge tổng hợp có trần** thay vì kết thúc Turn | `MAX_EMPTY_NUDGES = 1`, trần theo lần | C3: trần theo tiền + câu backend-authored |
| Hermes | **Progress event mang nội dung thật** (query, số nguồn, domain) | `progress.py` dựng được, phát ra chưa đủ | C1 |
| Hermes | Quét pattern injection trên nội dung web (lớp duy nhất còn thiếu trong 5 lớp) | 4 lớp có: SSRF, whitelist, untrusted wrapper, prompt | C1 |
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
           │ core/llm: typed errors, compact on     │ MAX_EXTERNAL_TOOL_CALLS=6
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

Edge **chưa có**: nhiều truy vấn web song song có tổng hợp · prune trước
summary · checkpoint giữa round · evaluator ngoài luồng · fan-in Study → thesis
· human-approval node.

---

## 3. Track C — Core harness

### C0 — Nền lane chat — **Current**

(Baseline — không có Trước→Sau vì đây là điểm đo gốc.)

Rip-out xong 2026-08-25 (`plans/260826-1920-phase-0-cleanup-and-restore-map/`).
Một loop, 4 bundle, 11 tool, budget arithmetic, typed recovery, repetition
ladder `allow→warn→block→halt`, SSE replay, freeze-never-resume. Đây là
baseline mọi "Trước" bên dưới đo từ đó.

### C1 — Search & tổng hợp có bằng chứng — **Target**

**Objective.** AI tìm rộng hơn, đọc nhiều hơn, tổng hợp thành một câu trả lời
có trích dẫn — và nói thẳng chỗ không tìm được.

| | Trước | Sau |
|---|---|---|
| Truy vấn web / Turn | 1 truy vấn mỗi round, ≤ 6 external call | 2–3 truy vấn **song song** một round, còn ≥ 2 call để đọc trang |
| Trang đọc / Turn | 1 trang, 20k ký tự | 3–4 trang, dedup domain, ưu tiên nguồn whitelist |
| Kết quả cho model | snippet 700 ký tự, không xếp hạng | xếp theo tin cậy + mới, trích đoạn liên quan câu hỏi |
| Câu trả lời | có thể "hiểu 10" nhưng chỉ dẫn được 1 nguồn | mỗi con số ngoài store có citation; mâu thuẫn giữa nguồn được nêu |
| Người dùng thấy | "đang tìm…" | query nguyên văn, số nguồn, domain (Hermes progress) |
| Bảo mật | 4 lớp | 5 lớp: + quét pattern injection trên text web |

**Boundary.** *Concurrency* thật: truy vấn độc lập, `executor` đã song song.
Không cần subagent.

**Checklist**
- [ ] `PARALLEL_TOOL_CALL_GUIDANCE` vào Contract; đo tỉ lệ round có > 1 `web_search` — `agent/prompt/sections.py`, `test_agent_prompt.py`
- [ ] `web_search` trả `rank`, `published_at`, `domain_trust`; `fetch_url` trích đoạn theo câu hỏi thay vì 20k đầu trang — `agent/tools/web.py`
- [ ] Dedup domain + gộp kết quả trùng trong `messages.display_results`
- [ ] Progress event mang query/nguồn/domain — `agent/progress.py`, `events.py`; web hiển thị timeline gập
- [ ] Quét pattern injection trên visible text (mẫu Hermes `threat_patterns`), fail-open: gắn cờ, không chặn — `agent/untrusted.py`
- [ ] Citation retention: câu trả lời cuối giữ được nguồn đã dùng sau trim — test transcript

**Gate.** Trên Golden Question Set (C4) nhóm web-first: số nguồn khác nhau
được trích/câu trả lời ≥ 3; câu có số ngoài store mà không citation = 0;
latency P50 không tăng > 20%.

### C2 — Context & cache — **Target**

**Objective.** AI nhớ đúng thứ cần trong một Turn dài, rẻ hơn, không mất trích
dẫn khi bị nén.

| | Trước | Sau |
|---|---|---|
| Khi vượt context | LLM summary 2 lần rồi bó tay | prune deterministic trước, summary sau, đo từng bước |
| Cache prefix | `cache_key()` có, `cache_control` chưa bật | bật khi route probe `prompt_cache_control=True` |
| Biết token đi đâu | không | đo theo layer: system · history · tool results · headline |
| Kết quả tool cũ | giữ nguyên văn | thay bằng trace handle, giữ cái đang trích dẫn |

**Boundary.** *Context boundary* (blog G4): owner `messages.py` + `core/llm`,
tách khỏi domain pack để hai owner không đổi cùng lúc.

**Checklist**
- [ ] Instrument input composition theo layer — `agent/messages.py`
- [ ] Prune deterministic: bỏ duplicate snippet, thay old full result bằng handle, bảo vệ user intent gần nhất + result đang trích dẫn
- [ ] `cache_control` thật — `core/llm/config.py::prompt_cache_control`
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

| | Trước | Sau |
|---|---|---|
| Đo chất lượng | không có (bộ eval đã rip; Hermes không có grader để port) | Golden Question Set + grader deterministic + LLM judge offline |
| Chặn hồi quy | review tay | gate fail-closed trên PR đổi prompt/prune/tool |
| Baseline | không | grounding · citation · empty-after-tools · invalid args · warn/block/halt · token · latency · cost/Turn |

**Boundary.** Evaluator là node **ngoài luồng** — không tăng latency người
dùng (blog G3/G8).

**Checklist**
- [ ] Golden Question Set `vn-equity`: câu · Study/field mong đợi · refusal mong đợi — JSON
- [ ] Grader deterministic trước: có desk? đúng Study? `outcome` khớp? frames không lọt? citation còn?
- [ ] LLM judge chỉ grounding/completeness, có CI
- [ ] Replay từ `agent_turn` thật ẩn danh, không gọi provider
- [ ] `make` target + gate policy fail-closed; JSON là authority

**Gate.** Baseline đầu ghi được; một PR cố ý làm giảm grounding bị chặn.

### C5 — Domain pack + progressive instruction — **Target**

**Objective.** AI chỉ mang playbook cần cho câu hỏi; đổi domain không sửa
loop.

| | Trước | Sau |
|---|---|---|
| Prompt | mọi playbook mọi turn | catalog ngắn luôn nạp, body nạp theo intent/tool path |
| Domain | `signals`+`studies` hardcode là chứng khoán | pack `vn-equity` có version; `web`+`memory` là core |
| Thêm tool/Study | sửa nhiều bảng tên | một declaration, contract test giữ đồng bộ |

**Boundary.** *Context* + *contract* (blog G2/G4; OpenCode progressive
disclosure).

**Checklist**
- [ ] `DomainPack`: `name·version·prompt_sections·toolsets·universe·study_names` — `agent/domain/`
- [ ] `CHAT_TOOLSETS` sinh từ pack, vẫn viết ra được; `AgentLoop(toolsets=None)` mặc định đúng — `test_agent_toolsets.py`
- [ ] Section domain tách core; `PROMPT_VERSION` bump; `render()` vẫn typed — `test_agent_prompt.py`
- [ ] Refusal vocabulary theo pack: `alpha/reasons.py` ↔ `apps/web/src/lib/signal-issues.ts`
- [ ] Memory vẫn qua tool, không free-text vào prompt (Hermes)

**Gate.** Đổi pack không sửa `loop.py`; input token/Turn giảm mà Golden Set
không giảm.

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
**Gate.** 100% test pack cũ xanh khi pack mới bật.

---

## 4. Track S — Signal Desk (paid)

### S0 — Runtime qua Study — **Current / đang đóng**

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

- [ ] Đóng nhánh `feat/study-canvas-runtime`: `make test` + bốn cổng web; plan `plans/260826-2158-study-artifact-canvas/` ghi xong
- [x] Contract test cố định "frames không vào message" ở tầng transcript — `tests/test_agent_study_tools.py::test_the_frames_are_absent_from_the_messages_a_turn_would_send` + `::test_the_frames_stay_out_of_a_signal_desk_turn_too`

**Gate.** 3 Study end-to-end với vnstock thật; `test_agent_signal_desk` xanh.

### S1 — Thư viện Study + desk theo mã — **Conditional** (cần C1, C4)

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
