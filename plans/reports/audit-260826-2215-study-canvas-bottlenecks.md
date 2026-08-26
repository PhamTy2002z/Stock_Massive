# Audit: điểm nghẽn plan Study→Artifact→Canvas + enhancement đã vá

Đối tượng: `plans/260826-2158-study-artifact-canvas/`. Phương pháp: chạy "movie"
một câu hỏi thật từ POST /turns tới pixel, đối chiếu code OBSERVED trong session
(loop.py, registry.py, executor.py, globals.css, layout.tsx, alembic heads).
Mọi fix dưới đã được vá thẳng vào phase files (cột "Vá ở").

## Xếp hạng theo tác động lên "start lên test là mượt"

| # | Điểm nghẽn | Bằng chứng | Fix | Vá ở |
|---|---|---|---|---|
| **N1** | **Critical path quá dài tới pixel đầu tiên**: 01→02→03→04→05 tuần tự, widget bug lộ CUỐI CÙNG — đúng phần user muốn mượt lại test muộn nhất | dependency table plan.md bản đầu | Contract-first: phase 01 phát hành fixture JSON (`CanvasSpec` + artifact mẫu + widget catalog); phase 05 tách **bước 0 — fixture dev page** build 5 widget trên fixture, KHÔNG chờ backend. FE bắt đầu ngày 1, nhìn thấy chart ngay | plan.md deps, 01, 05 |
| **N2** | **Model không tìm ra `run_study` / tốn round**: prompt cố tình không nhắc studies; 10 tool cạnh tranh; chain lý tưởng 2 round, chain lạc đường ăn hết MAX_TOOL_ROUNDS=4 | thiết kế catalog-qua-tool | `run_study.schema.name` = **enum tên study đã đăng ký** + per-study params doc trong description (sinh từ registry, đổi theo generation — không đụng prompt); description `get_field` nói rõ "một con số — không dùng để vẽ chart"; smoke script 5 câu chấm tool-choice ≥4/5 | 04 |
| **N3** | **Blocking event loop**: vnstock sync + pandas trong handler; đăng ký sai `is_async` → nghẽn SSE mọi user | registry.py:238-240 (False → worker thread); TOOL_TIMEOUT_SECONDS=30.0 (loop.py:272) | `run_study` đăng ký `is_async=False`; ingest 1 mã 2-3s lọt 30s; **luật**: study cần ingest >1 mã trong 1 call → refuse `no_value:data_warming` (không cố chạy quá timeout) | 04 |
| **N4** | **Khoảnh khắc canvas trắng**: `canvas.ready` phát sau persist, TRƯỚC prose round cuối — tốt (render song song lúc model viết), nhưng thiếu skeleton → panel nhảy layout | events flow phase 04 | Skeleton theo `blockCount` render <1s sau event; fetch artifact song song; **perf budget đo được**: P50 câu hỏi→canvas.ready ≤8s (store ấm) / ≤12s (1 ingest lạnh); widgets interactive ≤2,5s sau fetch | plan.md, 05 |
| **N5** | **Resize jank**: inspector resizable × 4 ResponsiveContainer recharts re-render mỗi px kéo | app-shell drag handle + bài học React.memo/isEqual trong web-viz-inventory | Trong lúc drag (shell-state đã có drag flag): đóng băng width canvas, chỉ re-measure khi thả; `React.memo` theo `(artifactId, blockIndex)` — cấm deep-compare series | 05 |
| **N6** | **Theme dark là mặc định** — không còn `forcedTheme="light"`; chart đầu tiên user thấy là nền tối | layout.tsx:86 `defaultTheme="dark"`; tokens `--chart-1..5`/`--positive/--negative` có cả hai theme (globals.css:107-175) | Widget chỉ lấy màu qua token; heatmap SVG thang 4 mức phải đạt contrast trên nền tối; test render cả hai theme là gate, không phải nice-to-have | 05 |
| **N7** | **Version skew BE↔FE widget catalog**: 2 codebase không chung workspace → lệch tên/version → fallback bảng toàn màn — "xấu mà không báo lỗi" | repo không phải pnpm workspace (CLAUDE.md) | `contracts/canvas-widget-catalog.json` ở repo root; pytest và vitest cùng đọc file này, lệch → test đỏ; server pin version từ catalog | 01, 05 |
| **N8** | **Validate params bằng gì**: jsonschema KHÔNG có trong requirements; hai bản schema (model-facing + server) sẽ trôi nhau | requirements.txt chỉ pydantic 2 | Một nguồn: pydantic model per-study; JSON schema model-facing sinh bằng `model_json_schema()`; server validate bằng chính model đó. Không thêm dep | 01 |
| **N9** | **Missing buckets làm heatmap nói dối**: dữ liệu thật có phiên chỉ 56/96 bucket raw; null vẽ thành 0 = "không ai giao dịch" (sai) | probe STB per-session min 56 | Chốt policy: cột heatmap align theo grid phiên chuẩn, thiếu = ô "không có dữ liệu" (màu riêng), KHÔNG phải 0; liquidity share normalize theo tổng thực có | 03 |
| **N10** | **e2e đỏ vì server fixture thiếu**: `tests/e2e/server.py` không biết endpoint artifact + event mới | bài học e2e-blocked đã ghi memory | Bước riêng trong phase 05: thêm artifact endpoint + `canvas.ready` vào stream fixture của server e2e | 05 |
| **N11** | Import pandas lạnh trong handler đầu tiên | container mount src/ | Import ở module load (container start), không trong handler | 02 |
| **N12** | **Shared DB nhiều stack**: strict stack 8001 + worktree evidence-loop dùng chung DB; revision mới trên nhánh này upgrade DB chung | memory strict-tools-stack-shares-db; alembic heads hiện sạch: `905ca5a8c2f7` duy nhất | Trước mỗi revision: `alembic heads` phải 1 head; bảng mới toàn additive nên stack kia an toàn; ghi thành step bắt buộc | 01 |

## Điều KHÔNG phải nghẽn (đã kiểm, khỏi lo)

- Tokens đồ hoạ web còn nguyên hai theme — giả định "có thể đã mất" trong
  audit nháp là sai.
- Frames 70×17 JSONB: ~35KB — persist + fetch không đáng đo.
- Guardrails/budget plane: `run_study` reads_external=False → không ăn quota
  external, không bị wrap untrusted; repetition ladder hiện có đủ.
- Turn deadline 600s, LLM call 120s — không phải ràng buộc thực tế của flow này.

## Perf budget (đưa vào acceptance plan.md)

| Mốc | Target P50 |
|---|---|
| Câu hỏi → `canvas.ready` (store ấm) | ≤ 8s |
| Câu hỏi → `canvas.ready` (ingest lạnh 1 mã) | ≤ 12s |
| `canvas.ready` → skeleton hiển thị | ≤ 1s |
| Fetch artifact → widgets interactive | ≤ 2,5s |
| Tool-choice smoke (5 câu chuẩn) | run_study đúng params ≥ 4/5 |

Đo bằng `scripts/smoke_canvas.py` (phase 04) — chạy tay trên dev, in bảng thời
gian từng mốc từ SSE timestamps.

## Unresolved

- Latency thật của route LLM (gpt-5.6-luna qua proxy 8317) cho 2 round — chưa
  đo; nếu P50 một call >6s thì budget 8s không đạt được bằng tối ưu phía ta,
  phải đo trước khi cam kết số.
- `render_canvas` (phase 06) chưa audit sâu bằng flow Study — lặp lại audit này
  khi bắt đầu nhóm B.
