# Phase 06 — `get_series` + composition `render_canvas` (nhóm B)

Phụ thuộc 05. Đây là tầng chống "vách đá recipe": câu hỏi không có Study vẫn
vẽ được.

## Context

Evidence plane hiện tại: 25 Signal Field đều trả **một scalar** qua
`get_field`. Chart cần dãy. Thiếu đúng một primitive: đọc một field qua
nhiều phiên thành series, với cùng bộ provenance như `EvidenceFigure`.

## Requirements

**Tool `get_series`** (bundle `signals`, `reads_external=False`):
- Args: `field_id` (registered), `symbol` (declared), `sessions` (clamp ≤120).
- Trả model: summary thống kê nhỏ (`first/last/min/max/median`, sessionsUsed,
  health) + `frameId` — dãy đầy đủ ghi thành Frame vào một
  `agent_artifact` kind composition-buffer của turn. Dãy KHÔNG vào context.
- Tôn trọng luật hiện có: chỉ Signal Field đã đăng ký · mã trong Universe ·
  phiên gần nhất đã đóng · `min_sample_for` áp trên từng điểm; điểm refused
  → null + reason đếm trong provenance.
- Compute: gọi `reading` của field trên cửa sổ trượt. **Cẩn trọng chi phí**:
  field O(window) × sessions — clamp tổng phép đọc, timeout theo registry
  `max_result_size_chars`/deadline hiện có.

**Tool `render_canvas`** (bundle `studies`):
- Args: `{title, blocks: [{widget, frame_id, options?}]}` — model soạn canvas
  từ frame đã tạo bởi `get_series`/`run_study` **trong chính turn này**
  (server kiểm frame ownership qua turn_id — data binding rule của #34 giữ).
- Server chọn widget_version + presentation defaults; validate widget name
  thuộc danh mục; block hỏng → loại block đó, giữ block lành (degrade từng
  phần); persist artifact + phát `canvas.ready`.
- Trần: ≤6 block/canvas, ≤2 canvas/turn.

**Widget mới (web):** `line_series` (recharts; hỗ trợ 2 trục độc lập theo
khuôn StockValuationHistory cũ) · `scatter_quadrant` (recharts Scatter +
đường chia quadrant + nhãn vùng) · `data_table` (nâng từ fallback lên
selectable).

## Files

- `src/agent/tools/signals.py` — `get_series` (cùng file với get_field, cùng
  registration khuôn hai chữ ký nếu cần symbol-context)
- `src/agent/tools/studies.py` — `render_canvas`
- `src/studies/frames_buffer.py` — tạo/đọc frame theo turn, ownership check
- web: 3 widget + registry entries + tests
- Tests API: series đúng luật refusal per-point · frame ownership (frame turn
  khác → refused) · render_canvas degrade từng block

## Steps

1. `get_series` + tests luật.
2. Frame buffer + ownership.
3. `render_canvas` + degrade + event.
4. Widgets web + gates.

## Validation

- Câu hỏi chưa có Study ("vẽ RSI của FPT 60 phiên cạnh ADTV") ra canvas 2
  block qua đường composition, không sửa backend nào thêm.
- `MAX_TOOL_ROUNDS=4` đủ cho chuỗi list→series×2→render? Đo thật 5 câu; nếu
  chật, đề xuất riêng (đổi hằng = quyết định đã ghi, không sửa lặng lẽ).

## Risk & rollback

- Model soạn canvas xấu (widget sai kiểu dữ liệu): validator server từ chối
  block kèm reason model-visible → model sửa trong round sau. Rollback: rút
  hai tool khỏi bundle; Study path (phase 03–05) không ảnh hưởng.
