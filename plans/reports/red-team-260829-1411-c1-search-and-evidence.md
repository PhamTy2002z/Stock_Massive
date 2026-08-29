# Red-team — plan C1 Search & Evidence

Ngày 2026-08-29. Hai reviewer đối kháng, góc tách rời: **tầng đo lường** và
**hồi quy/ranh giới**. Cả hai `PROCEED_WITH_CHANGES`. 20 finding thô.

Mọi finding dưới đây **đã được kiểm lại trực tiếp** bởi session chính trước khi
nhận — không cái nào nhận trên lời của reviewer.

## Sáu tiền đề của plan bị đảo

Đây là phần giá trị nhất. Bản đầu của plan sai ở sáu chỗ, ba chỗ đủ để đổi hình
dạng phase.

| # | Bản đầu viết | Thật | Ảnh hưởng |
|---|---|---|---|
| 1 | `agent_tool_call.result` không có mảng `results`, nên không replay được | Cột có ba khoá `{text, chars, dispatched}`, nhưng **`text` là chuỗi JSON chứa nguyên payload gồm `results`**. Đo: **77/81** dòng parse ra URL. Trim `SEARCH_RESULT_CHARS = 8_000` (`tools/web.py:76`) hiếm khi chạm | Runner **không cần** bọc `LLMClient`; đọc từ store là đủ. Lý do duy nhất còn đứng cho golden runner là **n = 10 quá nhỏ** |
| 2 | C1 sẽ làm "mỗi số có citation" | Prompt 2.9.0 **cố ý cấm** dẫn nguồn trong văn bản: *"đừng nêu nguồn"* (`sections.py:246-248`), *"Không viết phần dẫn nguồn… Việc đó là của giao diện"* (`:381-383`) | "Citation" = **danh sách nguồn cạnh câu trả lời** phủ được số đã dùng. Chuỗi quan sát: `display_results()` → `ToolCall.results` → `SourceList`. Không cần contract mới |
| 3 | Phase 06 dựng progress event vì rail không hiện query | `summarise_call` dựng `"{display_name}: {query\|url}"` từ `summary_detail_arg`, publish lúc **RUNNING**, và rail **render `{call.summary}` nguyên văn** (`reasoning-timeline.tsx:276,431`). `TOOL_CALL_FIELDS` đã cho `results`, `result_count` | Phase 06 co về **web-only**. Grep `"query"` của bản đầu trượt vì dữ liệu đi qua trường `summary` |
| 4 | Phase 03 "chuyền câu hỏi xuống `_fetch_page()`" | `fetch_url` schema chỉ `{"url"}` (`tools/web.py:358`); `ToolContext` **cấm** trộn nội dung — *"identity arrives here and arguments arrive from the model, and the two are never merged"* (`registry.py:152-182`). Và cache `WebLane` **key theo URL** (`web.py:419`) | Câu hỏi phải vào qua **argument mới do model điền**, và extract phải chạy **sau** điểm cache. Không thì câu hỏi B nhận trích đoạn chọn cho câu hỏi A, im lặng, cross-thread |
| 5 | Phase 04 chỉ đụng `loop.py` + prompt | `same_tool_failure_halt_after = 6` là **cùng một sự thật** với trần, và có test giữ đẳng thức: `assert DEFAULT_THRESHOLDS.same_tool_failure_halt_after == MAX_EXTERNAL_TOOL_CALLS` (`test_agent_guardrails.py:122`) | `guardrails.py` + test vào file list. Thêm ràng buộc trần mới **< 8** (`MAX_EXTERNAL_CALLS_PER_ROUND`), vì 6 < 8 nghĩa là đường per-round **chưa từng binding** trong production |
| 6 | Phase 05/06 "dùng lại `_source_of()` cho phần host" | `_source_of()` trả **giá trị argument thô** — url *hoặc query* hoặc tên tool (`messages.py:557-563`). Phép lấy hostname là `urlsplit(url).hostname` (`web.py:469,:503`) | Dùng nhầm sẽ phát cả câu query làm "domain" |

## Ba chặn cứng phải giải trước khi thi công

**A. Trần ngân sách per-user chặn lượt golden.** `turn_starts_per_day = 20`,
`active_turns_per_user = 1`, `daily_usd = 3.0`, `rolling_30d_usd = 15.0`
(`core/llm/config.py:218-222`). Corpus 20 câu chạm **đúng** trần khởi Turn/ngày;
một lần thử lại là vỡ, và luật "không chấm lượt xanh một nửa" khoá cứng plan.
Tiền thì không phải vấn đề — một Turn đo được **$0,021** so trần
`TURN_COST_MICRO_USD = 500_000` = $0,50.

**B. Phase 07 không có chỗ chứa cờ.** `agent_tool_call` không có cột metadata
tự do; `outcome` là `String(64)` (`alpha/models.py:201`). `result` JSONB có bất
biến riêng — *"exactly what is needed to debug a wrong answer"* (`:147-150`) —
nhét findings vào đó là làm bẩn nó. Hoặc revision mới + backup, hoặc hạ scope
xuống live-only. Và điểm quét phải là **executor, một lần mỗi kết quả**, không
phải đường render (20k ký tự × mỗi LLM call × ≤5 call/Turn).

**C. Ranh giới freeze — plan thiếu amendment.** Tuyên bố *"surface mới chỉ có
`golden/*` và `progress.py`"* bỏ sót `apps/api/Makefile` và ba file web
(`lib/alpha-desk/types.ts`, `components/alpha/message/reasoning-timeline.tsx`,
`hooks/use-live-turn.ts`). Cả bốn nằm trong bảng surface của
`260829-0010-composer-attachments` — plan **đã đóng 10/10**, và tiền lệ
price-basis là *plan xong thì surface đóng*. C1 cần bảng amendment riêng trong
CLAUDE.md trước phase 01.

## Số học gate — tiêu chí tốt nghiệp của C1 gần như rỗng

Corpus 20 câu, một lượt: `distinct_domains` n=20 · `uncited_external_number`
n=20 · `read_depth` n=20 · latency n=20 · chi phí n=20. **Chỉ `parallel_rate`**
(đơn vị round, ≤4/Turn) chạm n≥30. Luật "n<30 là tín hiệu, không gate" của phase
08 do đó biến năm trong sáu tiêu chí thành phi-gate.

"Chạy thêm lượt" không cứu được: `WebLane` cache search fresh **30 phút**, URL
fresh **24h** (`core/web_lane.py:19-22`), nên lượt hai trong ngày đọc lại cache
— mẫu tương quan, n hiệu dụng vẫn ≈ 20.

**Sửa:** bỏ luật n≥30 dạng blanket. Tiêu chí dạng "0 vi phạm trên 20 case" gate
theo **case pass/fail** — nhị thức trên 20 case là gate hợp lệ.

## Hai vấn đề so sánh baseline

**Web sống phá tính so được.** Artifact phase 02 và phase 08 cách nhau nhiều
tuần; URL fresh 24h. Delta phase 08 = Δcode + Δweb + Δsampling, không tách
được trên n=20. Bộ eval cũ có luật *"no live request in baseline, comparison"*
và plan mới đảo nó im lặng. Sửa: record/replay tại seam `WebLane.read`.

**Golden làm bẩn chính baseline nó phục vụ.** Runner ghi thật vào `agent_turn`/
`agent_tool_call`/`llm_call_usage`; phase 01 đo SQL trên chính các bảng đó.
Sửa: user_id riêng cho golden, mọi SQL baseline `WHERE user_id != <golden>`.

## Finding đã bác

**"Thêm `EventType` member phá consumer exhaustive-match."** Không —
`EVENT_TYPES` phía web là allowlist additive (`use-live-turn.ts:41-50`).
`snapshot_from_draft` **có tồn tại** (`events.py:518`), trái với nghi ngờ rằng
plan trích một luật không kiểm.

## Claim của plan được xác nhận đúng

`MAX_EXTERNAL_TOOL_CALLS=6` (`loop.py:293`) · `MAX_EXTERNAL_CALLS_PER_ROUND=8`
(`executor.py:86`) · `MAX_TOOL_ROUNDS=4` (`loop.py:164`) · `EventType` 8 member,
không progress (`events.py:75-88`) · `progress.py` không tồn tại ·
`PROMPT_VERSION = "2.9.0"` (`sections.py:29`) · năm target `eval-*` chết
(`Makefile:79-99`), `src/eval/` chỉ còn `__pycache__` · thang trim 4 rung
(`messages.py:958-996`), `keep_intact_turns=2` (`:719`) · `wrap_result` một
entry point (`untrusted.py:117-131`) · `src/agent/*` chưa bao giờ freeze ·
`apps/api/golden/` ngoài `src/` là cách ly vật lý thật.

## Bốn test còn thiếu cho đường hỏng

1. Phase 03 — hai câu hỏi khác nhau, cùng một URL, trong cửa sổ cache: phải trả hai trích đoạn khác nhau.
2. Phase 04 — đẳng thức guardrails sau khi đổi trần.
3. Phase 06 — không sinh hai row một call trên rail.
4. Phase 07 — quét đúng **một lần** mỗi kết quả.

## Câu hỏi chưa giải quyết

1. Phase 07: cột JSONB mới (revision + backup) hay hạ xuống live-only? Quyết định của user vì nó đụng schema.
2. Phase 04: `same_tool_failure_halt_after` đi theo trần mới hay đứng yên ở 6?
3. Điều phối với `260827-2325` — ai sở hữu `components/alpha/message/*` và §C1/C2 của `docs/roadmap.md` trong cửa sổ thi công?
