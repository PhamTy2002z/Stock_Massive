---
plan: 260901-1643-phase-04-context-engine
title: "Phase 4 — Context Engine"
status: ready — preflight §9 đạt, chờ ngân sách golden cho gate chất lượng
roadmap: "docs/roadmap.md §10 Phase 4"
branch: feat/phase-04-context-engine
---

# Phase 4 — Context Engine

Roadmap authority: [`docs/roadmap.md`](../../docs/roadmap.md) §10 Phase 4,
§6 (kiến trúc + quy tắc dependency 6: evidence identity/publication time/
retrieval time không mất khi trim, summary, persist hay render), §7 (Hermes
context layering + usage feedback; OpenCode prune-trước-summary và progressive
loading theo intent), §9 (nguyên tắc thi công).

## Outcome

Model nhận đúng context cho step hiện tại. Mục tiêu là **chất lượng suy luận**
— context dài làm model xuống cấp — và tiết kiệm token là phụ phẩm, không phải
mục tiêu. Hội thoại dài (dossier nhiều memo) giữ được intent, citation và
evidence.

## Non-goals

- **Không** xây evidence store hai tầng, claim ledger, hay bảng evidence nào —
  đó là Phase 6. Phase này chỉ dùng **con trỏ tới trace đã tồn tại**
  (`agent_tool_call.result`), không tạo tầng lưu trữ mới.
- **Không** thêm tool vào catalog. Năm capability giữ nguyên; "recovery search"
  của checklist được đáp bằng `session_search` đã có, không phải tool thứ sáu.
- Không đổi truth contract §2, không đổi permission plane (P5), không đổi
  public HTTP/SSE contract ngoài phần additive.
- Không làm UX context/timeline (P7), không đo chất lượng routing intent (P6).
- Không bật `llm_prompt_cache_control_enabled`: route **tự** cache prefix, đã
  đo; bật cờ là một quyết định đã kiểm chứng riêng, phép đo này không đảo nó.

## Gap analysis — verify trong code thật (2026-09-01)

Không tin nhãn Done. Đọc trực tiếp `messages.py`, `loop.py`, `turns.py`,
`router.py`, `persistence.py`, `prompt/`, `domain/`, `core/llm/transport.py`,
`core/llm/admission.py`, `core/web_lane.py`, `tools/memory.py`,
`golden/context_replay.py`, `apps/api/Makefile`,
`plans/reports/probe-260830-prompt-cache.md`.

| Trục roadmap P4 | Thực tế trong code |
|---|---|
| Tách stable/scoped/transcript-evidence/volatile | ✅ bảy layer có tên và có kế toán: `SYSTEM_CORE`, `DOMAIN_BODY`, `SYSTEM_DYNAMIC`, `HISTORY`, `USER_INTENT`, `ATTACHMENTS`, `TOOL_RESULTS` (`messages.py:184-199`); `ContextComposition.total == estimated_tokens` bởi cấu tạo (`messages.py:1619`) |
| Prune deterministic | ✅ ladder bốn rung (`messages.py:1543-1578`); `aged_results` collapse theo tuổi call, `web_search` 1 call / tool khác 2 call (`messages.py:1490-1540`); dedup URL trong Turn qua `seen` + `context_projection` |
| Không tách call khỏi result | ✅ render theo cặp ask+result (`messages.py:1351-1426`) — **chưa có test ghim** bất biến này qua mọi rung |
| Overflow hội tụ bounded | ✅ `_compress` nhân 0.6 tối đa 2 lần rồi terminal `context_overflow` (`loop.py:1694-1762`) |
| Handle giữ identity khi collapse | ✅ một phần: giữ arguments + tối đa N link (`messages.py:889-925`); đo được 13.8% giảm token, 0 URL mất (docstring `messages.py:1500-1508`) |
| **Usage token thật từ provider** | ❌ năm trường usage được parse (`transport.py:600`) và persist (`LlmCallUsage`, reconcile `admission.py:519`) nhưng **không quay lại quyết định nào**. Mọi quyết định trim chạy trên ước lượng ký tự `CHARS_PER_TOKEN = 3` (`messages.py:231`) |
| **Lossy summary — producer** | ❌ **consumer đủ, producer không tồn tại**: `_render_messages` dựng system message summary và tính `summary_needed` (`messages.py:1447-1453,1613-1615`), `TurnService.create` nhận `summary=None` (`turns.py:424`), và `router.py:526` **không truyền gì** — không dòng code nào sinh hay đọc summary |
| Summary provenance / protected tail / cooldown / recovery search / fail-open | ❌ chưa có gì; `summarised_turns` là mầm provenance duy nhất. `agent_message` **đã** hợp lệ hoá role `summary` (`persistence.py:865`) — nền persist có sẵn, chưa ai dùng |
| **Playbook nạp theo intent** | ❌ `state.domain_body = True` vô điều kiện (`loop.py:1190`) — pack `vn_equity` nạp vào **mọi** Turn, kể cả câu không chạm thị trường |
| Cache boundary theo prefix ổn định | ✅ điều kiện đã đủ và **đã đo**: prefix `core → domain_body → dynamic` trong một system message; probe 2026-08-30 trên route thật cho cached read 54.2% tổng, 82.4% trên prefix dài ([`plans/reports/probe-260830-prompt-cache.md`](../reports/probe-260830-prompt-cache.md)). `cache_control` OFF là đúng: route tự cache theo tiền tố |
| **Evidence Turn trước dùng lại không refetch** | ❌ collapse giữ URL nhưng bỏ nội dung, và `TRACE_HANDLE_PREFIX` **nói thẳng với model rằng không có đường lấy lại** (`messages.py:878-887`). `session_search` chỉ đọc `agent_message.content->>'text'` (`tools/memory.py:199-250`) — không chạm tool result. `WebLane` Redis cache URL fresh 24h / stale 7 ngày (`core/web_lane.py:20-23`) là cache ephemeral, không phải bản ghi bền |
| Replay corpus | ✅ `golden/context_replay.py` export (đọc store một lần) + replay (thuần: không mạng, không model, không đồng hồ, ngày ghim `REPLAY_DATE`); hai target Make đã có |

Kết luận gap: **tầng lắp ráp và prune đã chín; thứ thiếu là bốn mảnh** — số
token thật không quay lại vòng lặp, summary không có ai sinh, evidence không
sống qua ranh giới Turn, và playbook nạp bất kể intent.

## Thiết kế

### 1. Usage feedback thật (`agent/loop.py` + `agent/messages.py`)

Hai phép đo, hai vai trò khác nhau — đúng pattern Hermes, không thêm runtime:

- **Ước lượng ký tự** giữ nguyên vai trò *backstop preflight*: call đầu của
  Turn chưa có số thật nào, và admission vẫn reserve trên nó.
- **Số thật** trở thành *cái quyết định*: sau mỗi model call, `_TurnState` ghi
  `last_real_input_tokens = usage.input_tokens + usage.cached_input_tokens`
  (tổng prompt provider thật sự đọc — cached vẫn là token model thấy) cùng
  `estimate_at_last_real`.
- Lần construct kế tiếp dùng **projection**:
  `projected = last_real + (estimate_now − estimate_at_last_real)`. Ceiling so
  với projection thay vì ước lượng thuần. Chưa có số thật → projection *là*
  ước lượng, nên đường code một nhánh.
- `ContextComposition` mang thêm `projected_tokens` và `estimate_bias`
  (`last_real / estimate_at_last_real`) để P9 đọc được sai số của ước lượng
  trên dữ liệu thật thay vì đoán.
- Progress part kind mới `context_pruned {rung, turns_dropped,
  results_collapsed, estimated, projected, layers: {...}}` — số thuần,
  content-light, đi qua allowlist `parts.py` đã có. Map 1-1 với một lần
  construct thật, không phải stage bấm giờ (§6.9).

### 2. Evidence sống qua ranh giới Turn (`agent/tools/web.py` + `messages.py`)

Gate đòi: evidence Turn trước dùng lại được ở Turn sau **không refetch**. Đạt
bằng hai lớp, không lớp nào thêm capability:

**2a. Phục vụ từ bản ghi của chính thread.** `fetch_url` tra trace của thread
hiện tại trước khi chạm `WebLane`: nếu URL đã được fetch trong thread này và
`agent_tool_call.result` còn giữ nội dung, trả từ đó, **0 HTTP request**.
Redis đã che 24h đầu; đường này là bản bền khi cache evict hoặc hết hạn.

Bất biến bắt buộc (§6.6): kết quả phục vụ lại mang `fetched_at` **gốc** và cờ
`from_record: true`. Không bao giờ đóng dấu thời gian mới lên nội dung cũ —
temporal validity của §2 phụ thuộc đúng chỗ này.

**2b. Handle nói đúng sự thật.** `TRACE_HANDLE_PREFIX` hiện nói với model rằng
kết quả "không thể xin lại được". Sau 2a câu đó **sai**: gọi lại cùng URL là
một round không tốn mạng. Sửa câu chữ để model biết chi phí thật, và giữ
nguyên kỷ luật cũ — không hứa một tool không tồn tại.

Không bảng mới, không evidence store, không claim ledger: handle là con trỏ
`(request_message_id, tool_call_id)` vào trace đã có. Phase 6 nâng nó thành
evidence store hai tầng; phase này không đi trước.

### 3. Lossy summary có producer (`agent/compaction.py` — file mới)

Chạy **sau khi Turn settle**, không trong đường phản hồi người dùng. Lý do:
prune deterministic đã đủ cứu Turn đang chạy (ladder + compress bounded), còn
thứ Turn đang chạy *không* cứu được là hội thoại đã dài từ trước. Summary vì
vậy phục vụ **Turn sau**, và một lượt model phụ không bao giờ làm chậm câu trả
lời người dùng đang chờ.

- **Trigger:** `composition.summary_needed` (đã tính sẵn) và ngoài cooldown.
- **Specialist ẩn** (§7 OpenCode: verifier/title/compaction là hidden
  specialist contract nhỏ): một lượt `Workload.BATCH`, không tool, input là
  transcript các Turn **ngoài protected tail**.
- **Provenance bắt buộc:** message `role="summary"` (`persistence.py:865` đã
  hợp lệ hoá) với content `{text, covers_from_seq, covers_to_seq,
  summarised_turns, source_message_ids, model, created_at}`. Summary không có
  span thì không được dùng — `messages.py:1591-1593` đã từ chối đúng như vậy.
- **Protected tail:** summary chỉ bao Turn cũ hơn `keep_intact_turns`; N Turn
  gần nhất không bao giờ bị nén. Neo đơn điệu: `covers_to_seq` chỉ tiến.
- **Cooldown:** lỗi → không thử lại cho tới khi qua ngưỡng (in-process theo
  thread; mất khi restart, và mất theo hướng an toàn = thử lại).
- **Fail-open:** mọi lỗi (provider, timeout, output rỗng, span không hợp lệ) →
  **không** ghi summary; Turn sau chạy trên context hợp lệ gần nhất, tức đúng
  ladder hôm nay. Không đường nào để compaction làm hỏng một Turn.
- **Recovery search:** chi tiết bị nén vẫn tra được bằng `session_search` —
  các message gốc không bị xoá. `SUMMARY_LABEL` nói cho model biết điều đó
  bằng một dòng, thay vì thêm tool.
- **Đọc lại:** `router.py:526` truyền `summary`/`summarised_turns` mới nhất
  của thread vào `TurnService.create` bên cạnh `history_of(...)`.

### 4. Playbook nạp theo intent (`agent/loop.py`)

`state.domain_body = True` vô điều kiện thành quyết định theo intent: pack chỉ
nạp khi Turn chạm domain (symbol nhận diện được, lane `deep`, hoặc pack tự
nhận câu hỏi qua `domain/pack.py`). Quyết định một lần đầu Turn, như lane —
pack đổi giữa Turn sẽ làm "Turn này chạy với playbook nào" thành câu hỏi không
có câu trả lời.

Thứ tự khối trong system message **không đổi** và đó là điều kiện cache:
`SYSTEM_CORE` luôn là tiền tố chung, nên một Turn không nạp domain body vẫn
khớp prefix core của Turn có nạp. Ghim bằng test byte-level.

### 5. Gate suite (`tests/test_agent_context_engine.py` — mới)

| Gate roadmap | Cách chứng minh |
|---|---|
| Không tách call khỏi result | Với **mọi** rung của `_reductions` và mọi tập `aged`, mọi `tool_call` render ra đều có `tool_result` kề và ngược lại |
| Overflow hội tụ bounded | Ceiling nhỏ dần → số lần compress ≤ 2 rồi terminal `context_overflow`; không vòng lặp, không tăng token giữa hai rung |
| Evidence dùng lại không refetch | Turn 1 fetch U; Turn 2 cùng thread cần U với Redis rỗng → 0 HTTP request, `fetched_at` giữ giá trị gốc |
| Giữ cited evidence khi nén | Mọi URL từng xuất hiện trong kết quả còn tra được sau collapse; summary không bao giờ nuốt Turn trong protected tail |
| Usage thật quyết định | Projection dùng số provider; ước lượng lệch không kéo quyết định lệch theo |
| Summary an toàn | Provider lỗi/timeout/output rỗng/span hỏng → không summary nào ghi, Turn sau vẫn dựng context hợp lệ; cooldown chặn thử lại ngay |
| Playbook theo intent | Câu không chạm domain không nạp body; prefix core byte-identical giữa hai trường hợp |
| Token composition trước/sau | `make golden-context-export` + `golden-context-replay` (thuần, miễn phí) trên artifact release có sẵn |

## Preflight §9

### 1. Mỗi gate đã có lệnh chạy được chưa?

```bash
# gate phase
cd apps/api && pytest tests/test_agent_context_engine.py \
  tests/test_agent_messages.py tests/test_agent_loop.py \
  tests/test_agent_prompt.py tests/test_agent_fault_injection.py -q
# hồi quy
cd apps/api && pytest -q
python -m compileall -q apps/api/src apps/api/golden apps/api/tests
pnpm --dir apps/web lint && pnpm --dir apps/web type-check \
  && pnpm --dir apps/web test && pnpm --dir apps/web build
# composition token trước/sau, thuần và miễn phí
cd apps/api && make golden-context-export ARTIFACT=golden/artifacts/<release>.json \
  CORPUS=golden/artifacts/context-corpus.json
cd apps/api && make golden-context-replay CORPUS=golden/artifacts/context-corpus.json \
  OUT=golden/artifacts/context-report-<before|after>.json
```

**Một gate chưa có lệnh chạy được bằng tiền đã cấp:** "replay corpus giữ task
success". Task success chỉ đo được bằng `make golden-release`, và lệnh đó tiêu
tiền thật (baseline P1: 3 trial = $3,47 trong envelope $45/tháng). Replay
thuần đo *token và cấu tạo*, không đo *chất lượng*. Đây không phải bug của
roadmap — gate quy được về một lệnh và một ngưỡng — mà là một khoản chi cần
product owner cấp. Cho tới khi cấp: phase chạy được toàn bộ phần còn lại, và
mục này ghi **BLIND** thay vì xanh, đúng tiền lệ hard-dimension của P1.

### 2. Thứ phase trước để lại — verify trong code thật

Bảng gap-analysis trên, đọc 2026-09-01 trên nhánh
`feat/phase-04-context-engine` (HEAD `c6bc555`). Hand-off P3 dùng ở phase này,
đã xác minh có mặt: `LaneProfile` + `route_reason` (`lanes.py:96-187`,
`turns.py:469`) cho quyết định pack theo lane; progress part + allowlist
(`parts.py`) cho `context_pruned`; `_TurnState` mang được state mới
(`loop.py:960-990`); hai cửa terminal và idempotent write không đổi.

### 3. Named assumptions (unknown không discoverable)

| Assumption | Nếu sai thì làm gì |
|---|---|
| **A1.** `input_tokens + cached_input_tokens` của route là tổng prompt thật model đọc | Sai số làm projection lệch **một chiều an toàn** (nén sớm hơn cần). `estimate_bias` ghi lại trong composition nên phát hiện được bằng số, không bằng cảm giác; sửa là đổi công thức một chỗ |
| **A2.** Một lượt BATCH đủ để nén một hội thoại dài mà không mất intent | Fail-open là mặc định: summary tồi vẫn phải qua span check, và Turn sau luôn dựng được context không cần summary. Nếu chất lượng tồi lộ ra ở golden, đường lùi là tắt trigger — một cờ, không phải một refactor |
| **A3.** Nội dung trang trong `agent_tool_call.result` đủ để phục vụ lại | Miss → rơi về `WebLane` như hôm nay (Redis, rồi mạng). Đường 2a là *thêm* một lớp bền trước cache, không thay đường nào |
| **A4.** Bật/tắt domain body không phá cache prefix của core | Đã suy ra từ cấu trúc (core là tiền tố chung) và ghim bằng test byte-level; nếu route cache theo toàn message thay vì tiền tố, chi phí là ~680 token/call trên Turn không chạm domain — nhỏ hơn cái nó tiết kiệm, và probe chạy lại đo được |
| **A5.** Compaction sau-settle không tạo đường ghi đua với Turn kế tiếp | Summary là một message append, `seq` cấp trong transaction với retry sẵn có (`persistence.py:_with_sequence_retry`); Turn kế tiếp đọc summary mới nhất tại thời điểm create — trễ một Turn là đúng, không phải lỗi |

### 4. Đường lùi

Không migration, không bảng mới, không cột mới — `agent_message.role`
`summary` đã hợp lệ từ trước. Dừng giữa phase = revert nhánh
`feat/phase-04-context-engine`; các message role `summary` đã ghi trở thành
row vô hại mà reader cũ bỏ qua (`history_of` lọc theo role). Không dữ liệu nào
bị drop hay đổi shape; mọi thay đổi content là **thêm key**.

## Cửa một chiều — kiểm tra

- **Public HTTP/SSE contract:** additive — một progress kind mới trên event
  `part.progress` đã tồn tại. Không endpoint mới, không event type mới.
- **Tool catalog:** **không đổi**. Năm capability giữ nguyên; `fetch_url`
  không đổi schema, chỉ đổi nơi lấy dữ liệu và thêm một cờ trung thực trong
  result. `session_search` không đổi gì.
- **Data:** không drop, không migrate, không bảng mới.
- **Truth contract §2:** không chạm — và một bất biến của nó được *củng cố*:
  retrieval time gốc theo nội dung phục vụ lại.
- **Default permission, legal boundary:** không chạm.

## Việc

| # | Việc | File chính | Giao |
|---|---|---|---|
| 1 | Usage feedback thật + projection + `context_pruned` progress | `agent/loop.py`, `agent/messages.py`, `agent/parts.py` | opus |
| 2 | Phục vụ evidence từ bản ghi thread + handle nói đúng sự thật | `agent/tools/web.py`, `agent/messages.py`, `agent/persistence.py` | opus |
| 3 | Compaction specialist + persist summary + đọc lại ở router | `agent/compaction.py` (mới), `agent/turns.py`, `agent/router.py`, `agent/persistence.py`, `agent/messages.py` | opus |
| 4 | Playbook nạp theo intent + ghim prefix core | `agent/loop.py`, `agent/domain/pack.py` | opus |
| 5 | Gate suite + composition trước/sau | `tests/test_agent_context_engine.py` (mới), mở rộng test hiện có | opus |

Thứ tự: 1 → 2 → 4 (độc lập nhau, cùng chạm `loop.py`/`messages.py` nên tuần
tự) → 3 → 5. Việc 5 viết xen kẽ theo từng việc, gom gate cuối.

## Nghiệm thu

1. Gate suite + toàn `pytest -q` xanh; `compileall` sạch; bốn lệnh web xanh.
2. Mọi rung ladder giữ cặp call/result; overflow hội tụ ≤ 2 lần compress.
3. Turn sau dùng lại evidence Turn trước với **0 HTTP request** và
   `fetched_at` gốc.
4. Không đường nào để compaction làm hỏng một Turn (mọi lỗi fail-open).
5. Câu không chạm domain không nạp playbook; prefix core byte-identical.
6. Composition token trước/sau ghi thành số trong report; task success chờ
   ngân sách golden, ghi BLIND cho tới khi có.
7. `git diff --check` sạch; không tham chiếu Signal Desk/Study mới.
