# Việc 5 — gate suite + năm khoản nợ

Nhánh `feat/phase-04-context-engine`, sáu commit từ `ca7b2f5` tới `d6ba5d6`.

## A. Gate suite — `apps/api/tests/test_agent_context_engine.py` (mới, 29 test)

Docstring của file nói rõ gate nào ở đây và gate nào sống ở file nào, để không ai
phải đoán ranh giới lần sau.

| Gate roadmap | Chứng minh ở đâu, bằng cách nào | Kết quả |
|---|---|---|
| Không tách call khỏi result | `test_no_rung_of_the_ladder_separates_a_call_from_its_result[4 shape]` — **duyệt toàn bộ** `_reductions`, không chọn nấc. Với mỗi nấc, đi bộ dọc message list: mỗi ask phải được theo ngay sau bởi đúng các `tool_result` của nó, đúng thứ tự; mỗi `role=tool` phải có ask ngay trước; cuối cùng `asked == answered`. Bốn transcript để tập `aged_results` khác nhau thật (`test_the_ageing_the_ladder_starts_from_is_not_the_same_set_every_time` ghim rằng chúng khác nhau, nếu không thì sweep là một tập lặp bốn lần) | xanh |
| Overflow hội tụ bounded | Hai nửa. (a) `test_no_rung_of_the_ladder_costs_more_than_the_rung_above_it` — chuỗi token của toàn ladder phải giảm đơn điệu; `test_a_ceiling_that_falls_never_hands_back_a_larger_context` — qua cửa công khai `build_messages`, hạ trần dần thì context không to lên, `rung` không lùi, và cặp call/result vẫn nguyên. (b) `test_a_turn_the_ladder_cannot_fit_settles_and_keeps_what_it_said` — nợ B1. Số lần compress ≤ 2 rồi terminal đã có ở `test_agent_loop.py`, không chép lại | xanh |
| Evidence dùng lại không refetch | `test_a_page_one_turn_read_is_reused_by_the_next_with_no_request` — **hai Turn thật** trên Postgres thật: `AgentPersistence` thật, `trace=store.record_tool_call`, `web.register_web_tools` thật, `EvictingLane` (Redis phục vụ lần đầu rồi mất key). Turn 2 → đúng **1** download cho cả hai Turn, `from_record: true`, `retrieved_at` **bằng** của Turn 1. Gate cắn thật: nếu đường bản ghi hỏng, lane ném `WebUnavailable` và payload đổi shape | xanh |
| Giữ cited evidence khi nén | `test_every_url_a_shown_turn_found_survives_its_results_collapsing[4 shape]` — mọi nấc, mọi URL của các Turn **còn hiển thị** phải còn trong text model đọc (Turn bị drop thì model được nói thẳng là không có, đó không phải mất citation). Phần "summary không nuốt protected tail" ở `test_a_span_the_specialist_would_write_never_reaches_the_protected_tail`: nối **producer với consumer** — `plan_compaction` đếm Turn trên message row, `build_messages` đếm trên transcript; test chạy 9 độ dài thread và đòi hai phép đếm khớp | xanh |
| Usage thật quyết định | `test_only_what_the_route_charged_decides_whether_ground_is_given` — cùng transcript, cùng script, cùng trần 12k; chỉ khác con số route trả. Route trung thực (9 800) → **không** part `context_pruned` nào; route tính gấp đôi (19 600) → nhường đất, `turns_dropped > 0`, và mọi `projected ≤ trần`. Ước lượng ký tự giống hệt nhau ở cả hai, nên một vòng lặp quyết theo ký tự sẽ ra cùng kết quả | xanh |
| Summary an toàn | `test_no_failed_summary_changes_a_byte_of_the_next_turns_context[3 lỗi]` — mạnh hơn "Turn sau vẫn chạy": messages của Turn sau phải **byte-identical** với trước khi gọi specialist. Từng đường lỗi riêng lẻ đã ghim ở `test_agent_compaction.py`, không chép lại | xanh |
| Playbook theo intent | `test_the_two_prompts_one_pack_produces_are_told_apart_by_their_key` (nợ B3) và `test_the_prompt_the_two_share_is_shared_byte_for_byte`. Câu "Bạn là ai…" vs "VCB có gì mới…": prefix chung ⊇ `prompt_prefix()`, key khác nhau, và không key nào mang câu hỏi/tên/ngày | xanh |
| Compaction vừa trần admission | `test_no_pass_is_ever_built_larger_than_the_ceiling_it_is_admitted_under`, `test_a_summary_too_long_to_carry_is_abridged_rather_than_abandoned`, `test_the_preferred_reading_budget_is_under_the_ceiling_it_is_bounded_by` (nợ B4) | xanh |

Test **không** chép lại từ việc 1-4: đường lỗi compaction từng cái một, ladder
rung-by-rung ở mức unit, freshness window / excerpt / denylist của `fetch_url`,
`recorded_result` scope theo thread, từ vựng domain, tính thuần của replay.

## B. Năm khoản nợ

### B1 — `ConstructedContextTooLarge` thoát khỏi `_call` — **xong** (`b0e5925`)

`_run` bắt nó cạnh nhánh `LLMError` và settle `INCOMPLETE` /
`context_overflow`, không phải reason thứ hai: route báo đúng điều kiện đó dưới
tên ấy, và tách làm hai sẽ chẻ một sự kiện thành hai dòng trong ops tally.
`_ended` giữ `state.text`, nên phần trả lời dở còn nguyên; `_attempt` đóng bằng
`error` + reason nên trail đọc được.

Test dựng đúng điều kiện việc 1 cảnh báo: route tính 500k token cho call đầu →
projection vượt trần ở **mọi** nấc → ladder hết đường. Trước sửa: exception bay
lên `TurnService`, Turn thành `turn_failed`, mất narration. Sau: `INCOMPLETE`,
`context_overflow`, `"Để tôi tra đã."` vẫn là của người đọc, call thứ hai không
bị mua.

### B2 — replay hard-code `system_body` — **xong** (`24b9e4d`)

`replay_case` dựng lại đúng hai quyết định runtime đã lấy, từ đúng thứ corpus đã
ghi: `route_intent(question)` rồi `domain_body_reason(question, lane)`. Cả hai
thuần theo câu hỏi, nên **không cần trường mới trong corpus** và corpus cũ replay
được nguyên (`CORPUS_SCHEMA` không đổi). Report thêm `domain_body` +
`domain_body_reason` mỗi case và `cases_carrying_the_pack_body` trong totals;
`REPORT_SCHEMA` lên `@2` vì report cũ đo mọi case như thể có body.

Tính thuần giữ nguyên: không mạng, không model, không đồng hồ, `REPLAY_DATE` vẫn
ghim (test `test_the_replay_reads_no_clock` vẫn xanh).

### B3 — `cache_identity` không phân biệt hai đầu prompt — **xong** (`daf0891`)

`cache_key(model, tool_signature, pack_identity, *, domain_body: bool)` —
keyword bắt buộc, không default, cùng lý lẽ `pack_identity` không có default.
Key kết thúc bằng `body` / `no-body` (chữ, không phải cờ, vì người đọc metadata
của một call sẽ thấy nó).

`state.cache_identity` chuyển xuống **sau** quyết định body trong `_run` — key
gọi tên prompt đi ra, nên nó phải biết prompt nào. Không có gì khác về Turn lọt
vào: `test_nothing_about_one_turn_reaches_the_identity_of_its_head` (có sẵn) vẫn
xanh, và gate mới ghim thêm rằng hai câu hỏi khác nhau nhưng **cùng** quyết định
body vẫn cho cùng key.

### B4 — compaction có thể bị từ chối im lặng — **xong** (`0513557`)

Đo trước khi sửa: đường duy nhất vượt `ANALYSIS_INPUT_PER_CALL` là `head` —
`previous.text` đọc **từ store**, tức độ dài không thuộc quyền module này.
`MAX_MESSAGE_CHARS` chặn prose từng message, `MAX_SOURCE_CHARS` chặn span, nhưng
vòng `while` dừng ở `len(fresh) > 1`, nên một Turn + một head khổng lồ đi thẳng
tới admission và bị từ chối lặng.

Sửa: `COMPACTION_INPUT_TOKENS = ANALYSIS_INPUT_PER_CALL * 4 // 5` (**dẫn xuất**,
không chọn tay — một hằng gõ tay ở đây là hằng sẽ trôi khỏi cái đang từ chối);
`_SOURCE_CEILING_CHARS` là số học của `_estimated_input_tokens` chạy ngược.
Thứ tự nhường: **span hẹp trước** (phủ ít Turn hơn là claim nhỏ hơn, không phải
claim sai) → chỉ khi còn đúng một Turn thì **head bị cắt** → nếu vẫn không đủ thì
**không viết gì**. Không bao giờ cắt prose của Turn rồi vẫn claim nó, vì span nói
dối tệ hơn không có summary.

`MAX_SOURCE_CHARS = 15_000` giữ nguyên vai trò "ngân sách mong muốn" (chi phí),
`COMPACTION_INPUT_TOKENS` là "bảo đảm" (được nạp tiền). Test ghim cả ba: mọi plan
module có thể sinh đều `≤ COMPACTION_INPUT_TOKENS`; head 120k ký tự → vẫn gọi
được, `summarised_turns == 2`, `covers_to_seq == 4`, `covers_from_seq` không lùi,
Turn được claim vẫn nằm trong body; và ngân sách mong muốn luôn dưới trần.

Về $0.015/owner: giữ nguyên, không đụng. Với input tự bound ở 15k ký tự (~5k
token) và output 700, worst case ở giá batch $0.5/$1.0 per Mtok là ~$0.003 —
cách mép một bậc độ lớn. Rủi ro còn lại là giá batch cao hơn nhiều so với giả
định; đó là câu hỏi mở, không phải khoản nợ đã đo.

### B4b — ladder có thể **leo lên** (phát hiện khi viết gate, đã sửa: `0e166a4`)

Gate "token không tăng giữa hai nấc" **sai** trên code cũ, và đo được:

```
kết quả 4 ký tự, 4 Turn, mỗi Turn 1 call
rung 0: 129 token
rung 1: 182   <-- to hơn
rung 2: 235   <-- to hơn
```

Handle (`TRACE_HANDLE_PREFIX` + tên + arguments + link) dài hơn chính kết quả khi
kết quả ngắn — một mức lãi suất, một search rỗng, một refusal một dòng. Turn đang
vượt trần sẽ được đưa cho một nấc **làm nó tệ hơn**, và mất luôn nội dung.

Sửa: `worth_collapsing(turns)` quyết định một lần, trên đúng text hai bên render
ra, và lọc **cả** `aged_results` lẫn mọi nấc. Nấc không có gì để đổi thì lặp lại
nấc trước (plateau), ladder đơn điệu, và `results_collapsed` đếm collapse **đã
xảy ra** thay vì collapse được yêu cầu. Sau sửa, cùng fixture: 129 / 129 / 129 /
98 / 67.

Đây là sửa hướng-nguyên-nhân cho một gate roadmap đã đòi, nằm trong tầng prune
mà phase này sở hữu — không phải quyết định roadmap mới.

### B5 — đo composition — **xong**

Cùng corpus `golden/artifacts/context-replay-v1.json`, cùng lệnh, replay thuần
miễn phí:

| Mốc | case | model call | constructed token | median/Turn |
|---|---|---|---|---|
| Trước bốn việc (số của đề bài) | 20 | 78 | 377 434 | 18 108 |
| Sau bốn việc (`ca7b2f5`) | 20 | 78 | **377 534** | 18 118 |
| Sau việc 5 (`d6ba5d6`) | 20 | 78 | **377 495** | 18 118 |

Phân rã ba mốc:

- **+100** ở mốc 2 là `REREAD_COSTS_NOTHING` của việc 2: một câu thêm vào mỗi
  dòng collapse của `fetch_url` thành công. Nói cho model biết đọc lại không tốn
  request là thứ đổi được một round tool lấy 100 token trên 78 call.
- **−39** ở mốc 3 là B4b: 39 token từng bị tiêu để **mất** nội dung.
- **0** từ B2. Lý do là số đo, không phải suy đoán:
  `cases_carrying_the_pack_body = 20/20`. Cả 20 case của corpus release đều là
  câu hỏi thị trường, nên playbook-theo-intent không tiết kiệm được gì **trên
  corpus này** — và không thể tiết kiệm, vì không có case nào ngoài domain. Đây
  là câu trả lời trực tiếp cho câu hỏi mở #4 của việc 4: tiết kiệm chỉ xuất hiện
  trên Turn không chạm domain, và corpus release không chứa cái nào. Thêm case
  off-domain vào corpus là quyết định của người sở hữu golden.

Bất biến khác của báo cáo, không đổi: `urls_reachable == urls_offered == 536`,
`intent_kept: true`. Layer: `system_core` 117 000 (31,0%), `tool_results`
236 058 (62,5%), `domain_body` 18 798 (5,0%), `system_dynamic` 2 910,
`user_intent` 2 729, `history` 0, `attachments` 0.

Chứng minh phép đo **nhạy** với quyết định (nếu không thì mốc "0" là vô nghĩa):
`test_a_question_off_the_domain_is_replayed_without_the_playbook` — câu "Bạn là
ai?" replay ra `domain_body == 0` ở mọi call và context nhỏ hơn thật.

## Kiểm tra

| Lệnh | Kết quả |
|---|---|
| `cd apps/api && pytest -q` | **1375 passed**, 3 deselected (baseline 1344, +31; không test nào bị nới hay xoá) |
| `pytest tests/test_agent_context_engine.py -q` | 29 passed |
| `python3 -m compileall -q apps/api/src apps/api/golden apps/api/tests` | sạch |
| `git diff --check` | sạch |
| `pnpm --dir apps/web lint` / `type-check` / `test` | xanh (458 test) |
| `E2E_NEXT_DIST_DIR=.next-verify pnpm --dir apps/web build` | xanh; `.next-verify` đã xoá, `next-env.d.ts` đã revert |
| `make golden-context-replay` | 20 case / 78 call / 377 495 token |

Không migration, không bảng, không cột. Không tool mới, catalog vẫn đúng năm.
Không đổi hợp đồng HTTP/SSE. Không tham chiếu Signal Desk/Study mới.

Commit: `b0e5925` (B1) → `daf0891` (B3) → `0513557` (B4) → `0e166a4` (B4b) →
`24b9e4d` (B2) → `d6ba5d6` (gate suite).

## Câu hỏi mở, kèm chủ sở hữu

1. **Corpus replay không có case nào ngoài domain**, nên playbook-theo-intent đo
   ra 0. Muốn có số thật thì phải thêm case off-domain vào corpus release và
   export lại. *Chủ: người sở hữu golden corpus (Phase 9 / product owner).*
2. **`agent_tool_call` không có index trên `thread_id`.** Cố ý để nguyên theo
   yêu cầu; mỗi `fetch_url` thêm một query lọc theo thread. Cần một phép đo trên
   bảng thật trước khi đổi. *Chủ: phase sở hữu evidence store (Phase 6).*
3. **Giá batch thật vs trần $0.015/owner của lane analysis.** Deployment hiện để
   `llm_price_batch_* = 0.0`, nên trần chưa bao giờ bị chạm. Input nay tự bound
   nên phía token an toàn; phía tiền vẫn chưa đo. *Chủ: Phase 9 (budget).*
4. **`estimate_bias` chưa được đọc bởi ai.** Nó nằm trong `ContextComposition`
   để P9 đọc sai số ước lượng trên dữ liệu thật; hôm nay chưa có surface hay log
   nào tổng hợp nó. *Chủ: Phase 9.*
5. **`REPORT_SCHEMA@2`**: report replay cũ (@1) không so sánh case-by-case được
   với @2. Không có consumer nào hôm nay; gate đọc số này là Phase 5.
   *Chủ: Phase 5.*
6. **`worth_collapsing` chạy `_collapsed_result` + `shown_result` cho mọi call ở
   mỗi lần construct.** Chi phí là hai lần dựng chuỗi mỗi call mỗi construct;
   trên corpus hiện tại không đo được khác biệt, nhưng nếu một Turn có rất nhiều
   call thì đây là chỗ để memo hoá. Chưa làm vì chưa có số chứng minh cần.
