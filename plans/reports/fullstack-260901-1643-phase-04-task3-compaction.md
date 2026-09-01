# Việc 3 — lossy summary có producer

Nhánh `feat/phase-04-context-engine`, commit `43028af`.

## Sửa gì

- **`apps/api/src/agent/compaction.py` (mới)** — specialist ẩn `ThreadCompactor`:
  một lượt `Workload.BATCH`, `tools=()`, `tool_choice="none"`, `stream=False`,
  timeout 120s. `plan_compaction()` là hàm thuần quyết định span trước khi tiêu
  tiền; `ThreadCompactor.compact()` đọc thread → plan → gọi model → ghi một
  message `role="summary"`.
- **`turns.py`** — `TurnService(compactor=…)` + `_compact_later()`: chạy **sau**
  `_finish` (sau transaction terminal và sau terminal event), bằng
  `asyncio.create_task`, không await. `shutdown()` huỷ thẳng các task compaction
  trước khi cho Turn cửa sổ checkpoint. Done-callback nuốt và log exception để
  không có task nào chết im.
- **`persistence.py`** — `SummaryRecord` + `latest_summary(messages)`: đọc từ các
  row `read_thread` đã trả về, không thêm truy vấn. Row nào span không đọc được
  thì bỏ qua và lùi về summary cũ hơn (hoặc không có summary).
- **`router.py`** — `create_turn` truyền `summary` + `summarised_turns` vào
  `TurnService.create`; `_applicable_summary()` từ chối span phủ hết hội thoại.
  `GET /threads/{id}` **lọc** row `summary` khỏi transcript trả về → hợp đồng
  HTTP không đổi một byte, web không phải biết vai trò mới.
- **`messages.py`** — chỉ `SUMMARY_LABEL`: thêm một câu nói với model rằng các
  lượt sau summary vẫn còn nguyên và `session_search` tìm lại được. Không tool
  thứ sáu, catalog vẫn đúng 5.
- **`service.py`** (ngoài danh sách file được giao — xem "quyết định") — wiring
  `ThreadCompactor(client, config, store).compact` vào `TurnService`.
- **`tests/test_agent_compaction.py` (mới)** — 24 test.

## Khuôn specialist đã theo

Repo **không có** specialist LLM ẩn nào trong `src/agent/`: `thread_title_from`
(`persistence.py:417`) là hàm thuần cắt chuỗi, không gọi model. Khuôn gần nhất
là **`golden/judge.py`** (một lượt, không tool, `stream=False`, owner + lane
riêng, mọi lỗi thành dữ liệu chứ không phải exception) — đó là khuôn đã theo,
cộng thêm phần fail-open và cooldown mà judge không cần.

## Test trước / sau

| | |
|---|---|
| Trước | `pytest -q` → **1320 passed** |
| Sau | `pytest -q` → **1344 passed**, 3 deselected (+24, không sửa test cũ) |
| `python3 -m compileall -q src golden tests` | sạch |
| `git diff --check` | sạch |

Acceptance ghim ở đâu:

- (a) protected tail — `test_the_newest_turns_are_never_inside_the_span`,
  `test_a_thread_no_longer_than_its_protected_tail_is_left_alone`
- (b) span đơn điệu — `test_a_second_pass_never_covers_less_than_the_first`
- (c) lỗi → không ghi gì —
  `test_a_failed_pass_writes_nothing_at_all` (provider error / timeout / output
  rỗng / output toàn khoảng trắng), `test_a_call_that_never_answers_is_given_up_on`,
  `test_a_store_that_refuses_the_write_leaves_the_thread_untouched`,
  `test_a_thread_whose_compaction_failed_still_builds_its_context`,
  `test_a_summary_whose_span_cannot_be_read_is_ignored`,
  `test_a_span_that_would_leave_no_live_turn_is_not_applied`
- (d) cooldown — `test_a_failure_stops_the_next_settled_turn_from_asking_again`
- (e) Turn sau đọc đúng — `test_the_next_turn_applies_the_summary_and_drops_what_it_covers`,
  `test_the_summary_row_survives_a_write_and_stays_off_the_transcript` (round-trip
  qua Postgres thật)
- (f) không nằm trên đường phản hồi —
  `test_a_turn_settles_without_waiting_for_its_summary` (Turn terminal + message
  đã commit trong khi compaction còn đang chờ), `test_a_short_thread_settles_without_asking_for_a_summary`

## Quyết định đáng giữ

1. **Summary luôn phủ một *tiền tố* Turn, và nối chuỗi.** Consumer
   (`build_messages`) áp summary bằng `live = turns[summarised_turns:]`, nên span
   buộc phải là tiền tố. Lượt sau nhận **summary cũ + prose các Turn mới**, không
   đọc lại từ đầu → input bị chặn, và `covers_from_seq` giữ nguyên qua các lần.
2. **Prose lưu dưới key `summary`, không phải `text`.** `session_search` đọc
   `content->>'text'`; nếu summary nằm ở key đó thì recovery search trả về chính
   bản nén thay vì Turn gốc. Ghim bằng test (cả ở tầng nội dung lẫn ở DB).
3. **Cắt span thay vì cắt phần đọc** khi hội thoại quá dài cho một lượt: summary
   không bao giờ tuyên bố phủ Turn mà nó chưa đọc; lần settle sau đẩy neo đi tiếp.
4. **Row `summary` bị lọc khỏi `GET /threads/{id}`.** Không lượt nào bị xoá, nên
   vẽ thêm summary là vẽ hội thoại hai lần. Giữ hợp đồng HTTP/SSE y nguyên và
   frontend không phải đổi.
5. **`_applicable_summary` ở phía đọc.** Compactor không bao giờ ghi span phủ hết
   thread, nhưng hai phép đếm do hai đoạn code khác nhau tính; phía đọc từ chối
   để một row lệch không thể biến Thread thành bản tóm tắt của chính nó.
6. **Cooldown in-process, chỉ khi lỗi.** Thành công không cần cooldown: điều kiện
   "neo phải tiến" đã tự giới hạn nhịp. Mất khi restart = thử lại, ghi trong
   docstring.
7. **Owner ngân sách = `OwnerType.ANALYSIS_RUN`, lane `ANALYSIS`, id duy nhất mỗi
   lần thử.** `TURN_REQUEST_MESSAGE` bị loại: trần tổng của Turn (`turn_input_total`,
   `turn_cost`) đã bị chính Turn dài tiêu gần hết — đúng những hội thoại cần nén
   nhất sẽ bị từ chối. `CAPABILITY_PROBE` dùng chung $0.25/ngày với probe lúc
   boot. Id duy nhất mỗi lần thử vì trần theo owner tính cả reservation của call
   *hỏng*; dùng id cố định theo span thì một lần thất bại sẽ khoá vĩnh viễn span
   đó.

## Câu hỏi mở

1. **Compaction có đáng có `OwnerType` riêng không?** Hôm nay row ledger mang
   `owner_type='analysis_run'` với `owner_id` tiền tố `thread-compaction:` — tra
   cứu được, nhưng nhãn là khái niệm sản phẩm đã nghỉ hưu. Thêm enum mới là sửa
   `core/llm/admission.py` (ngoài phạm vi file được giao) và phải quyết trần cho
   nó. Đảo chiều = một dòng.
2. **Trần `$0.015`/owner của lane analysis đã đủ chưa khi giá batch được set
   thật?** Deployment hiện tại để `llm_price_batch_* = 0.0`. `MAX_SOURCE_CHARS =
   15_000` (~5k token) và `COMPACTION_OUTPUT_TOKENS = 700` được chọn để vừa trần
   đó ở mức giá kiểu $1.25/$8 per Mtok. Nếu giá thật cao hơn, compaction sẽ bị
   `analysis_cost` từ chối — fail-open, tức là **không bao giờ có summary** mà
   không có tín hiệu nào ngoài log warning. Đo được bằng golden khi có ngân sách.
3. **`service.py` nằm ngoài danh sách file được giao** nhưng là composition root
   duy nhất có `client`; không sửa nó thì compactor là code chết. Đã sửa tối
   thiểu (một tham số). Báo lại để nắm.
4. Chất lượng bản tóm tắt (A2 trong plan) chưa đo — cần golden. Đường lùi vẫn là
   không truyền `compactor` khi build service.
