# Evidence across Turn boundaries — reuse without refetch

Ngày 2026-09-01. Nhánh `feat/phase-04-context-engine`, đi sau `9f6073d`.

## Sửa gì

- `src/agent/persistence.py` — thêm `AgentPersistence.recorded_result(thread_id,
  tool_name, arguments)`: kết quả **thành công mới nhất** của một call trong
  **chính thread đó**, khớp bằng JSONB containment trên `arguments` (nên
  `{"url": u}` khớp cả row có thêm `looking_for`). Trả về payload của tool đã
  decode từ `result->>'text'` (envelope trace của loop), `None` khi row bị trim
  → JSON không đóng. Không bảng mới, không cột mới, không migration.
- `src/agent/tools/web.py` — `fetch_url` tra bản ghi thread trước lane:
  - thứ tự: **validate → bản ghi thread (bền) → WebLane (Redis) → mạng**;
    validate_public_url chạy trước cả ba nên denylist/SSRF/DNS vẫn áp cho URL
    ngay cả khi có bản ghi (test ghim);
  - payload phục vụ lại giữ `retrieved_at` **gốc**, thêm `from_record: true`;
    `stale`/`age_seconds` tính từ mốc gốc theo đúng cửa sổ `URL_FRESH_SECONDS`
    của lane; đường mạng nay nói `from_record: false` để cờ luôn có mặt;
  - bản ghi không nói được thời điểm đọc → **không phục vụ**, đọc lại thật;
  - bản ghi là excerpt của câu hỏi khác → **không phục vụ** (chỉ dùng lại khi
    giữ cả trang, hoặc `looking_for` trùng); tránh citation trỏ vào nửa trang
    không trả lời câu này;
  - store lỗi → log + đi đường mạng (fail-open), không làm chết capability;
  - lookup chạy ở nửa async, `_fetch_url` nhận `recorded` xuống thread.
- `src/agent/messages.py` — `TRACE_HANDLE_PREFIX` giữ nguyên chuỗi (câu chữ của
  nó vẫn đúng: đã ghi lại, không lặp ở đây, và ba khả năng vẫn được nói rõ);
  docstring viết lại cho đúng sự thật mới. Thêm `REREAD_COSTS_NOTHING` chỉ nối
  vào dòng collapse của `fetch_url` **status OK** — đúng một tool có chi phí
  đọc lại bằng 0, và chỉ khi có bản ghi để phục vụ.

## Test

- Trước: `pytest -q` = 1295 passed (đo trước commit `9f6073d`).
- Sau: **1320 passed, 3 deselected**. `compileall src golden tests` sạch,
  `git diff --check` sạch.
- Mới (12): 9 trong `tests/test_agent_web_tools.py` (0 request với lane đóng;
  `retrieved_at` gốc + age/stale; URL lạ đi đường cũ; không thread → không hỏi
  store; excerpt câu khác không phục vụ; cùng câu hỏi thì phục vụ; thiếu mốc
  thời gian → đọc lại; denylist vẫn chặn; store hỏng vẫn đọc được),
  2 trong `tests/test_agent_persistence_paths.py` (mới nhất thắng, thread khác
  không xuyên qua, status lỗi bị bỏ, tool khác không khớp; body bị trim → no
  record), 1 trong `tests/test_agent_loop.py` (chỉ page read OK mới mang câu
  "đọc lại không tốn request").

## Quyết định đáng giữ

- **Scope thread, không scope request_message**: `tool_result()` hẹp vì nó phục
  vụ *citation by call id*; đường mới trả lời câu khác — "hội thoại này đã đọc
  trang đó chưa" — nên thread là ranh giới đúng (một user, một dòng câu hỏi,
  một phạm vi quyền). Không bao giờ vượt thread nên không bao giờ vượt user.
- **Không đóng dấu thời gian mới** là bất biến, không phải tuỳ chọn: bản ghi
  không nói được `retrieved_at` thì không được phục vụ.
- **Prefix chung không dài thêm**: nó bị trả giá bởi *mọi* dòng collapse đúng
  lúc context đã vượt trần; lời hứa "đọc lại miễn phí" chỉ đúng với `fetch_url`
  nên nó đi kèm dòng của `fetch_url`, không nằm trong prefix chung.
- **Callable thay vì truyền cả store vào WebTools**: web.py chỉ cần một câu trả
  lời; phụ thuộc cả store sẽ bắt mọi test đọc trang phải có database.

## Câu hỏi mở

1. `agent_tool_call` **không có index trên `thread_id`** (chỉ có
   `request_message_id` và `started_at`). Mỗi `fetch_url` nay thêm một query lọc
   theo thread → seq scan khi bảng lớn. Thêm index là một migration, ngoài phạm
   vi việc này. Cần quyết định riêng.
2. Khớp URL bằng `arguments->>'url'` là chuỗi model gõ, không phải URL đã
   normalize. Cùng trang gọi bằng hai dạng chuỗi khác nhau (http/https, có/không
   dấu `/` cuối) sẽ trượt bản ghi và đọc lại qua mạng — an toàn nhưng bỏ lỡ.
   Sửa đúng cần lưu URL đã validate trong trace (đổi shape row) hoặc index biểu
   thức: cả hai là quyết định của Phase 6 evidence store.
3. Bản ghi hiện chỉ giữ thứ call trước **trả về**, không phải cả trang. Trang
   lớn đọc kèm câu hỏi vẫn phải fetch lại cho câu hỏi khác. Muốn hết hẳn refetch
   thì phải lưu trang đầy đủ ở tầng bền — đúng là evidence store hai tầng của
   Phase 6, cố tình không làm trước.
