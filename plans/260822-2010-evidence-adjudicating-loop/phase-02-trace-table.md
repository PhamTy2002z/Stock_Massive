---
phase: 2
title: "Trace: bảng analysis_tool_call"
status: done
---

# Phase 2 — Trace: bảng `analysis_tool_call`

## Kết quả (2026-08-22)

Đã land. `AnalysisToolCall` trong `src/alpha/models.py`; revision
`a3c7e21b8f65_add_the_analysis_tool_call_trace_table.py` (`down_revision = f1a2b7c39d40` như
plan). Bảng đúng cột đã thiết kế, `UNIQUE(run_id, round_index, seq)`, FK `analysis_run`
`ON DELETE CASCADE`, không index nào khác.

Xác thực: chuỗi alembic đầy-đủ trên DB nháp → `downgrade -1` → `upgrade` lại, bảng biến mất và
trở lại; `revision --autogenerate` không phát hiện drift nào cho bảng mới; 8 test mới trong
`tests/test_alpha_persistence.py` (UNIQUE, thứ tự không dựa vào đồng hồ, round sau dùng lại
`seq=1`, FK từ chối `run_id` không tồn tại, cascade xoá trace, run chết giữa đường vẫn giữ
trace). Đã apply lên DB nội bộ sau khi `pg_dump` — `alembic_version = a3c7e21b8f65`.

Một điều chỉnh so với plan: docstring module `models.py` nói *"nine tables ... declared
together"*. Bảng thứ mười tới sau và một mình, nên đoạn đó được viết lại thay vì để nó thành câu
sai; bất biến số 3 cũng được nới để nói cả hai loại neo (message của người dùng cho chat, run
cho Analysis).

## Lớp lỗi đang mở

Vòng lặp phá tính tái lập. `alpha/envelope.py:6-10` nói rõ cái đang bị đổi:

> *"an Analysis rebuilt tomorrow from the same store has to say the same thing, and a live
> call is a number nobody can rebuild."*

Không có gì thay thế thì đây là downgrade thuần. Cái mua lại tính tái lập là **audit**: đọc
được đúng vòng lặp đã hỏi gì, nhận gì, theo thứ tự nào. Nên bảng trace không phải chi tiết
kỹ thuật — nó là giá của Phase 4, và phải land **trước** Phase 4.

Bảng chat có sẵn không dùng được. `alpha/models.py:341-350` — `agent_tool_call` có
`thread_id` **NOT NULL** và `request_message_id` **NOT NULL**, cả hai FK sang `agent_thread`
/ `agent_message`. Một Analysis Run không có thread và không có message.

## Quyết định: bảng riêng, không nới bảng chat

| | Nới `agent_tool_call` | Bảng `analysis_tool_call` |
|---|---|---|
| Migration | 2 cột nullable + 1 cột phân biệt owner | 1 bảng mới |
| Hệ quả | Mọi reader hiện tại phải học rằng hai cột NOT NULL giờ có thể null; `ix_agent_tool_call_request_message` phục vụ hai loại owner | Reader hiện tại không đổi |
| Retention | Bảng chat giữ 90 ngày, job cleanup quét theo tuổi | Trace của Analysis nên sống bằng tuổi Analysis, không phải 90 ngày |
| Owner | Hai owner khác nhau hoàn toàn trong một bảng | Một owner một bảng |

Chọn **bảng riêng**. Hai retention khác nhau trong một bảng là hai chính sách xoá tranh nhau
một cột `started_at`.

## Thay đổi

### `alpha/models.py`

```
analysis_tool_call
  id              BigInteger PK
  run_id          FK analysis_run(id) ON DELETE CASCADE, NOT NULL
  round_index     Integer NOT NULL      -- round nào của loop
  seq             Integer NOT NULL      -- thứ tự trong round; UNIQUE(run_id, round_index, seq)
  tool_name       String(64) NOT NULL
  tool_call_id    String(128) NULL      -- id route cấp, additive như bảng chat
  arguments       JSONB NOT NULL
  result          JSONB NULL
  status          String(16) NOT NULL   -- ok | tool_error | timeout | unknown_tool | blocked
  error           String(500) NULL
  latency_ms      Integer NULL
  started_at      timestamptz NOT NULL server_default now()
```

Neo vào `run_id`, không vào `analysis.id`: run tồn tại **trước** khi Analysis được ghi
(`alpha/analysis_run.py` — *"A row in `analysis` existing means it is complete"*), nên
`analysis.id` chưa có lúc tool call đầu tiên chạy. Neo vào `analysis` sẽ orphan đúng lúc một
run chết giữa đường và trace là thứ đáng giá nhất.

`UNIQUE(run_id, round_index, seq)` giữ thứ tự, không dùng timestamp — cùng lý do
`agent_message` dùng `UNIQUE(thread_id, seq)`: hai call song song trong một round chia nhau
một millisecond, và timestamp không diễn đạt được "chèn giữa hai dòng".

`ON DELETE CASCADE` từ `analysis_run`: retry ba lần của cùng `(symbol, trading_day)` dùng
cùng một run row (`MAX_ATTEMPTS_PER_SESSION`), nên trace của cả ba attempt nằm cùng run —
`round_index` không reset giữa các attempt, nó tiếp tục tăng. Điều đó phải ghi vào docstring,
vì nó là chỗ người đọc sẽ giả định sai.

Index: `(run_id, round_index, seq)` là UNIQUE nên đã đủ cho mọi đọc theo run. Không thêm
index theo `started_at` — không có job cleanup theo tuổi ở bảng này.

### Migration

`down_revision = "f1a2b7c39d40"` (head hiện tại,
`f1a2b7c39d40_drop_the_eval_run_table.py`). Additive thuần: một `CREATE TABLE`, không đụng
bảng nào đang có, không backfill.

## Validation

- `pnpm db:migrate` chạy được và `alembic downgrade -1` gỡ sạch.
- Test: chèn hai row cùng `(run_id, round_index, seq)` phải vi phạm UNIQUE.
- Test: xoá `analysis_run` xoá theo trace.
- `make test` pass.

## Risk / rollback

`downgrade` là `DROP TABLE`. Không dữ liệu nào của bảng khác bị chạm.

Rủi ro duy nhất: nếu Phase 4 sau đó cần một cột nữa (ví dụ `spilled_bytes` như bảng chat),
đó là migration thứ hai chứ không phải sửa revision này — `apps/api/alembic/versions/**` đã
commit thì không sửa.
