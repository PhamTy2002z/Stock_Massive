# Hermes Agent → Stock_Massive: bản hợp nhất

Nguồn: khảo sát 9 vùng trên `NousResearch/hermes-agent` (MIT), 2026-08-20/21.
Phủ: **365 file / 349.505 dòng, UNASSIGNED = 0** — `hermes-coverage-260820-2352.md`.

Report vùng: `hermes-core-loop`, `hermes-context`, `hermes-tools`,
`hermes-memory`, `hermes-web-security`, `hermes-turn-lifecycle`,
`hermes-route-subagent`, `hermes-orchestrator-state`, `hermes-mcp-ops-eval`
(hậu tố `-260820-2352.md`).

---

## 1. Kết luận

Hermes **không** đáng bê khung: nó là coding agent terminal (7 sandbox backend,
40+ tool shell/file/git, TUI, gateway đa nền tảng), và cái nó giỏi nhất là đúng
thứ `ADR-0011` đã cố tình từ chối. Không có tool nào của nó đọc được store này.

Nhưng nó đáng học một nguyên tắc và một cơ chế:

- **Nguyên tắc**: guard fail-OPEN. Được phép làm chậm, làm rẻ, làm ồn — không
  được phép làm trắng màn hình.
- **Cơ chế**: khi model sai hợp đồng, chèn **nudge tổng hợp có trần** rồi tiếp
  tục, thay vì kết thúc Turn.

Và một điều đối chiếu ngược: **Eval Battery của ta mạnh hơn của Hermes** ở khoản
chấm chất lượng đáp án. `batch_runner.py`/`mini_swe_runner.py` chỉ sinh
trajectory, không có grader; `verify/runner.py` chỉ chấm build/test/boot xanh hay
không. Ta có rubric, category, blind scoring. Đó là tài sản, và nó là lý do
mạnh nhất để không xoá: **cái ta có mà họ không có là khả năng biết mình dở ở
đâu.**

---

## 2. Mười phát hiện đã xác minh trên code CỦA TA

Tất cả đều kiểm bằng đọc file, không suy từ tài liệu.

| # | Phát hiện | Bằng chứng | Tác động |
|---|---|---|---|
| 1 | `except GatewayTimeout:` trần trụi, **không log gì**, terminal ngay — trong khi nhánh `LLMError` ngay dưới có comment dài về việc log là thiết yếu | `loop.py:739-744` vs `:748-758` | `gateway_timeout` là **3/4** lỗi route trong ops 7 ngày, và là nhánh duy nhất không có chẩn đoán. Không sửa được 36% khi không biết nó là gì |
| 2 | `route_error` là hố đen taxonomy: `classify_status()` có 4 nhánh có tên rồi catch-all — **mọi 400** thành `LLMError` vô hình dạng | `core/llm/errors.py:279-294` | 400 là chỗ ở của context overflow, output-cap, content policy, schema sai, model không tồn tại — tức các ca **đáng lẽ tự phục hồi được** |
| 3 | `MAX_TOOL_ROUNDS = 4`, nhưng docstring cùng file nói "Eight tool-call rounds per Turn" | `loop.py:124` vs `loop.py:21,23` | 4 round cho câu cần scope→search→fetch→store→tính là rất chật. Ứng viên nghiêm túc cho câu trả lời cụt |
| 4 | `cache_key()` tồn tại nhưng **không `cache_control` nào được set** trong `core/llm/*` | báo cáo vùng context | Prefix ổn định mà `contract.py::prefix()` cẩn thận tách ra đang không được cache thật. Trả giá đầy đủ mỗi Turn |
| 5 | `.env` đang chứa **hành vi**, không chỉ secret — `LLM_MODEL_SESSION`, các cờ tính năng | `.env` | Đây đúng chỗ model phiên bị hạ xuống `luna` mà không ai thấy. Hermes có luật thành văn: ".env chỉ cho secret" |
| 6 | Chống SSRF của ta **đã chắc**, gọn hơn Hermes: `is_global` trên mọi địa chỉ, socket ghim DNS chống rebinding, kiểm lại từng hop redirect | `tools/web.py:74,124,129,289-300` | Không cần làm gì. *Brief của tôi nói sai điều này.* |
| 7 | Lớp untrusted **đã có**: nhãn `external_claim`, whitelist nguồn + lọc thời gian, trích visible-text có cap, và Contract dạy model coi là dữ liệu không phải chỉ thị | `tools/web.py:1,191,211`; `news.py:172,196`; `_html.py`; `prompt/sections.py:105-109` | Thiếu **đúng một** lớp: quét pattern injection kiểu `threat_patterns.py`. Khoảng trống hẹp, không phải toàn bộ |
| 8 | `progress.py` của ta đã có cấu trúc nguồn (domain/title/snippet) **tốt hơn** tầng agent-core của Hermes | báo cáo vùng turn-lifecycle | Bar 3 ảnh gần hơn tưởng. Thiếu phần phát ra, không phải phần dựng |
| 9 | Tên tool MCP đã khớp quy ước `mcp__server__tool` của Hermes | `agent/mcp/registry.py:177` | Không cần đổi |
| 10 | Thread thuộc một user (`AgentThread.user_id`); `agent_knowledge.user_id` cho phép NULL | `persistence.py:108-119,404-413` | Không có khái niệm thread đa user → câu hỏi riêng tư cho ký ức đã có đáp |
| 11 | `TurnService._execute` gom **mọi** exit path qua đúng 2 cửa `_finish`/`_finish_bare` | `agent/turns.py` | **Tốt hơn Hermes**, nơi `on_turn_complete` tự thừa nhận không phủ hết early-return: *"Some abnormal early-return paths … do not currently emit this hook."* Giữ nguyên, không port |
| 12 | Kiến trúc "freeze, never resume" của persistence | `agent/persistence.py` | Khả năng cao đã tránh sẵn lớp lỗi #49201 mà `replay_cleanup.py` của Hermes phải vá (transcript kết thúc bằng `assistant(tool_calls)` không có `tool` khớp). Cần xác nhận |

---

## 3. Đối chiếu kiến trúc trung tâm

| | Hermes | Stock_Massive | Đo được |
|---|---|---|---|
| Guard không chắc | nhường đường | chặn | |
| Model sai hợp đồng | nudge, `continue`, trần 1–2 | kết thúc Turn `incomplete` | |
| Chống bịa số | 9 dòng prose trong prefix cache | validator 1.302 dòng runtime | |
| Bằng chứng | ledger **thụ động** + policy sinh follow-up | **điều kiện để được nói** | |
| Không chứng minh được | *"explain the concrete blocker"* | màn hình trắng | 58% Turn `grounding_failed`, category B 0/30 |

Trích, `verification_evidence.py:3`: *"deliberately **passive**: it never decides
to run a suite, never blocks completion."*
`verification_stop.py:3`: *"intentionally **policy-only** … turns the passive
verification ledger into a **bounded follow-up**."*
Câu bản lề trong nudge của nó: *"If verification is not possible, explain the
concrete blocker instead of claiming the work is fully verified."*

Ta đã đi nửa đường: `d699345` cho một rewrite, `ADR-0018` hạ cấp prose. Miếng
thiếu là miếng cuối — hết lượt rewrite thì **thả câu trả lời kèm câu nói thẳng
chỗ không chứng minh được**, thay vì kết thúc trắng.

---

## 4. Kế hoạch port, xếp theo triệu chứng

Ba nhóm triệu chứng đã đo: (A) 58% Turn `grounding_failed` → màn hình trắng,
(B) 36% Turn chết vì route, (C) khuôn analysis-first.

### Tầng 0 — chẩn đoán, làm trước mọi thứ

| Việc | File | Vì sao trước |
|---|---|---|
| Log `GatewayTimeout` như đã log `route_error`: route, attempt, elapsed, status, bytes nhận | `loop.py:739` | 3/4 lỗi route đang im lặng. Mọi con số về nhóm B hiện là phỏng đoán |
| Mở rộng `classify_status` cho nhánh 400: context_overflow, output_cap, content_policy, model_not_found, invalid_schema | `core/llm/errors.py:294` | Không phân loại được thì không phục hồi được |

### Tầng 1 — nhóm A, màn hình trắng

| Việc | File |
|---|---|
| Thay `raise` bằng nudge tổng hợp có trần; hết trần thì **thả block** kèm câu backend-authored nói rõ figure nào không chứng minh được | `agent/grounding.py`, `loop.py` |
| Khối prose chống bịa vào tầng stable của Contract (mẫu: `prompt_builder.py:411`) | `agent/prompt/sections.py` |
| Xác minh `MAX_TOOL_ROUNDS = 4` có đủ cho câu web-first; sửa docstring đã trôi | `loop.py:21,124` |
| Thang `allow → warn → block → halt`, halt rất muộn (Hermes: lần 8) | `loop.py` |

### Tầng 2 — nhóm B, route

| Việc | File |
|---|---|
| Cross-process rate-limit breaker cho tuyến LLM, **trên Redis** theo khuôn `core/quota.py` (không bắt chước file chia sẻ của Hermes) | `core/llm/`, `core/quota.py` |
| Jittered backoff thay backoff cố định | `core/llm/client.py` |
| Guard empty deterministic: 2 lần rỗng cùng signature → đổi model, đừng retry | `core/llm/client.py` |
| Tách "deadline của ta" khỏi "timeout của provider", classify khác nhau | `core/llm/transport.py` |
| Bound việc đọc thân lỗi streaming (mẫu: `bounded_response.py`) | `core/llm/transport.py` |
| Gắn `cache_key()` vào `cache_control` thật nếu route hỗ trợ | `core/llm/` |

### Tầng 3 — nhóm C, trình bày

| Việc | File |
|---|---|
| Phát event tiến trình mang nội dung thật: query nguyên văn, số nguồn, domain | `agent/progress.py`, `events.py` |
| Timeline gập được + citation chip + 3 follow-up + footer "N nguồn" | `apps/web` |
| Lane hội thoại nhẹ: câu thường trả lời văn xuôi, Gate chỉ bật cho khuyến nghị có giá | `loop.py`, `prompt/sections.py` |
| `PARALLEL_TOOL_CALL_GUIDANCE` vào Contract | `prompt/sections.py` |

### Tầng 4 — sau khi base chạy

Ký ức xuyên phiên **qua đường tool** (mở rộng `remember_fact`/`recall_facts`
trong `tools/knowledge.py`), quét pattern injection trên nội dung web, ba tầng
chống overflow tool-result, sinh tiêu đề thread, `select_context()` tách khỏi nén.

---

## 5. Không port

- Kiến trúc lớn: coding agent terminal, sandbox, browser, TUI, gateway đa nền
  tảng, LSP, computer-use. `ADR-0011` đã từ chối lớp đó.
- **Chèn ký ức free-text vào system prompt.** Va vào bất biến có chủ đích:
  `contract.py::_assert_no_formatting_hole` cấm mọi free-text, `render()` chỉ
  nhận 5 giá trị typed. Đó là hàng rào chống injection mà Hermes phải bù bằng
  `_scan_context_content`. Giữ hàng rào, đi qua tool.
- Native compaction: chỉ gpt-5.6 trên route OpenAI trực tiếp.
- Fallback 7 tầng provider, credential pool/rotation: over-engineering cho một
  route cố định.
- `_ra()` lazy-module-reference, constructor 60 tham số, tầng SQLite
  WAL/FTS5/pool, session lineage 4 loại, export/import, eventing kiểu callback:
  lệch kiến trúc (ta dùng Postgres + DI + SSE, không resume-after-restart).
- Subagent / MoA: **không đáng ở quy mô hiện tại.**
- Skills tự sinh: chỉ có nghĩa sau khi base trả lời được.

**Không commit nào nên là "copy từ Hermes."** Mỗi bài học phải viết lại cho hình
dạng của ta.

---

## 6. Bài học meta

Mỗi module nhỏ của Hermes mở đầu bằng số hiệu sự cố: NS-503 (*"charged ~$2.33
for an empty answer"*), #86581 (*"a single turn produced a 60,698-char response
delivered as 31 Discord messages"*), #85125 (*"at least six site-local deadline
mechanisms, each built for one incident, none shared"*), #83220, #84047, #9400,
#32421, #62625, #79161, #81867, #50233. `terminal_hints.py` đào tần suất từ **DB
sản xuất**: *"a 250k-terminal-result window … ~9,175x: gh CLI version drift."*

Họ không thiết kế trước cho đúng. Họ thả cho chạy, hứng sự cố, đóng từng cái
thành một module nhỏ fail-open, ghi số hiệu vào docstring.

Ta làm ngược: 20 ADR và một validator 1.302 dòng dựng **trước** khi có người
dùng, để chặn một lớp lỗi chưa từng đo tần suất — và lớp bảo vệ đó tự trở thành
sự cố lớn nhất.

**Cảnh báo về nguồn**: docstring của Hermes giàu thông tin nhưng **không phải
chân lý**. Vùng context tìm thấy một docstring nói "10% savings" trong khi hành
vi thật là quyết định nhị phân. Ta có lỗi cùng loại: `loop.py` nói 8 round, code
là 4. Chỗ nào quan trọng thì đọc code, đừng đọc lời tự thuật.

**Cảnh báo về độ phủ**: vùng orchestrator đếm được **300 số hiệu issue duy nhất**
nhưng chỉ gán bài học cho **~13 cái** đọc đủ ngữ cảnh. Bản này **không** tuyên
bố có danh mục sự cố đầy đủ.

---

## 7. Sổ sửa lỗi của chính đợt khảo sát

Ghi lại để không ai đọc lại các khẳng định đã bị bác.

| Đã nói | Thực tế | Ai bác |
|---|---|---|
| 8 round tool-call mỗi Turn | `MAX_TOOL_ROUNDS = 4`; docstring trôi | vùng tools |
| Stock_Massive thiếu chống SSRF | Đã có, chắc hơn Hermes | vùng web |
| `agent/battery.py` là eval harness | Là bộ đọc pin laptop | vùng mcp-ops-eval |
| Nên thêm tầng volatile chèn ký ức vào prompt | Va vào bất biến chống injection; đi qua tool | vùng memory |
| "Hoàn toàn không có lớp chống injection" (vùng web nói) | Có 4 lớp; thiếu đúng một lớp quét pattern | kiểm chứng trực tiếp |

---

## Câu hỏi chưa giải quyết

1. `route_error` **thật sự** chứa gì? Chỉ trả lời được sau khi tầng 0 chạy. Mọi
   ước lượng về nhóm B trước đó là phỏng đoán.
2. `MAX_TOOL_ROUNDS = 4` là quyết định có chủ đích (`docs/specs/0003` §6) hay đã
   lạc hậu so với lane web-first? Đổi nó là đổi một quyết định đã ghi.
3. `ADR-0015` nói thẳng "prompt không phải cơ chế thực thi". Đưa khối prose
   chống bịa vào là **sửa một quyết định kiến trúc đã ghi** — cần amend ADR,
   không lặng lẽ trái.
4. Sau khi hết lượt rewrite, câu "không chứng minh được" do backend viết nên nói
   đến mức nào? Nêu tên field thì rõ nhưng rò cấu trúc nội bộ; nói chung chung
   thì người đọc không hành động được.
5. Nudge tiêu một lời gọi model. Trần theo số lần hay theo tiền?
