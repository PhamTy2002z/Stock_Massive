# Phase 04 — Bundle `studies` + event `canvas.ready`

Nhóm A. Phụ thuộc 01, 03.

## Context

Model gặp Study qua hai tool trong bundle mới. Catalog đến qua **schema tool**,
không qua prompt → thêm Study không bump PROMPT_VERSION, không void prefix
cache, không vi phạm `contract.py::_assert_no_formatting_hole`. SSE envelope
v2 có `EventType` enum; client web subscribe theo allowlist tên event nên
event mới là additive an toàn.

## Requirements

**Tool `list_studies`** — không args; trả catalog: name, question,
display_name, params tóm tắt, availability (requires thoả không — vd
`intraday_bar_15m` reachable). Khuôn `list_fields` hiện có.

**Routing để model tìm ra tool trong ≤2 round (audit N2):**
- `run_study.schema.name` là **enum tên study đã đăng ký** (sinh lúc
  registration, đổi theo generation counter — không đụng prompt, không void
  prefix cache ngoài tool signature vốn đã nằm trong `cache_key`).
- Description `run_study` liệt kê per-study: câu hỏi nó trả lời + params tóm
  tắt — model gọi thẳng không cần `list_studies` (giữ list_studies cho
  catalog dài về sau).
- Description `get_field` bổ sung một câu: "trả MỘT con số — không dùng để
  vẽ biểu đồ; biểu đồ/phân tích nhiều điểm dùng run_study".
- Chain mục tiêu: round 1 `run_study` → round 2 prose. Đo bằng smoke script.

**Tool `run_study`** — args `{name, params}`; handler:
1. Validate name → registered; params → schema; symbol → Universe declared.
2. `studies.runner.run(...)` → persist `agent_artifact` (turn_id, thread_id
   từ `ToolContext`, model không tự chọn — tool design rule của SOT).
3. Ingest on-demand: study khai `requires` → runner gọi
   `intraday.ingest.ensure_bars` trước compute (đây là I/O mạng →
   xem "phân loại trust" dưới).
4. Kết quả cho model: `{headline, artifactId, provenance}` — KHÔNG frames.
5. Refusal → `status=ok, outcome=no_value:<reason>` theo vốn từ
   `agent/messages.py::outcome_of`.

**Thực thi không nghẽn loop (audit N3):** handler sync (DB session sync +
vnstock) → đăng ký `is_async=False` — executor đẩy sang worker thread
(registry.py:238-240), không nghẽn SSE user khác. `TOOL_TIMEOUT_SECONDS=30.0`
(loop.py:272): ingest 1 mã 2-3s lọt thoải mái; **luật**: study cần ingest >1
mã trong một call → refuse `no_value:data_warming` kèm reason, không cố chạy
quá timeout. Summary tool.call event phải mang nội dung thật:
"Đang phân tích thanh khoản STB · 30 phiên" (display_name + params).

**Phân loại trust — quyết định cần ghi rõ:** `run_study` đọc store nhưng có
thể kích ingest từ vnstock. Nội dung trả model là **số do engine ta tính**,
không phải văn bản nguồn ngoài → `reads_external=False` (không bọc
untrusted, không tính vào MAX_EXTERNAL_TOOL_CALLS=6). Ranh giới đúng của
untrusted là văn bản ngoài vào context; bar số đã qua validate schema không
phải vector injection. Ghi quyết định này vào docstring registry entry.

**Event `canvas.ready`** — thêm vào `EventType`; payload
`{artifactId, studyName, title, blockCount, round}`; phát sau khi artifact
persist; **restate trong snapshot** (khuôn `thoughts`) để reconnect không mất.
`ENVELOPE_VERSION` giữ 2 (additive).

**Persistence:** message assistant liên kết artifact qua
`agent_artifact.turn_id` — transcript rebuild (`fetchThread`) join để trả
`artifactIds` per turn. Không nhét spec vào `agent_message.content`.

## Files

- `src/agent/tools/studies.py` — hai ToolEntry + handlers (khuôn
  `tools/signals.py`, có `_check_the_catalog_holds` bản studies)
- `src/agent/toolsets.py` — bundle `"studies"`; **`CHAT_TOOLSETS` = `("web",
  "memory", "signals", "studies")`** — viết ra tuple mới + sửa test khẳng
  định tuple (CLAUDE.md: selection duy nhất, phải được viết ra)
- `src/agent/events.py` — EventType + emit + snapshot restate
- `src/agent/persistence.py` / router thread fetch — expose artifactIds
- `src/alpha/…router` — `GET /agent/artifacts/{id}`: auth (artifact →
  thread → user_id = current user), trả `{canvasSpec, frames, provenance,
  studyName, studyVersion, createdAt}`
- Tests: tool handler (mock runner) · event sequence (snapshot chứa
  canvas.ready sau reconnect) · endpoint auth (user khác → 404) · transcript
  test khẳng định **frames không xuất hiện trong messages gửi model**
  (acceptance #2 của plan)

## Steps

1. Bundle + tools + registry checks.
2. Event + snapshot restate + tests sequence.
3. Endpoint artifact + auth test.
4. Cập nhật test `CHAT_TOOLSETS`; chạy toàn bộ `make test`.

## Validation

- `make test` xanh; test mới: 10 tool = 8 cũ + 2 studies.
- Smoke: POST turn hỏi "thanh khoản STB 30 phiên" trên dev → SSE có
  `canvas.ready`, GET artifact trả spec 4 block.
- **`scripts/smoke_canvas.py` (audit N2/N4):** 5 câu hỏi chuẩn (đa dạng cách
  diễn đạt: "thanh khoản", "khung giờ nào volume cao", "vẽ heatmap"...) →
  chấm: run_study được gọi đúng params ≥4/5; in bảng timestamps từ SSE:
  câu hỏi→tool.call→canvas.ready→completed. Đây là thước perf budget của
  plan.md — chạy tay trên dev, không vào CI.

## Risk & rollback

- Model lạm dụng `run_study` lặp: guardrails 4-rung hiện có bắt theo hash
  arguments — đủ, không thêm cơ chế. Rollback: rút `"studies"` khỏi
  `CHAT_TOOLSETS` (một dòng + test), artifact table giữ nguyên.
