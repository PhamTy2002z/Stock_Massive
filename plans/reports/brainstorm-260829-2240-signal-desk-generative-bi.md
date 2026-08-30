---
title: Signal Desk → generative BI board, giữ tầng deterministic
date: 2026-08-29
type: brainstorm
status: proposal — chờ chốt hướng trước khi plan
inputs:
  - scout code Signal Desk (studies/*, agent/tools/{studies,signals}.py, web/signal-desk/*)
  - research landscape generative-UI · BI copilot · finance copilot (agent researcher, 2026-08-29)
  - docs/roadmap.md §4 Track S · docs/idea.md
---

# Tóm tắt một đoạn

Câu "khung giờ thanh khoản VIC 30 phiên" ra board **tạm được** vì có đúng một
Study viết sẵn cho nó. Câu "BCTC VIC vs VCB, mã nào nền tảng tốt hơn" **tệ** vì
thiếu **hai tầng rưỡi**: (1) dữ liệu — **đính chính 22:55**: store *có* kho
BCTC đầy đủ (`financial_statement_line` 302.528 dòng · 1.235 mã · VCB 155 / VIC
174 chỉ tiêu · 8 quý) nhưng chỉ `earnings_dislocation` đọc; agent chỉ thấy 7
field nền tảng qua `reads_fundamental.py` — nợ **nối dây**, không phải nợ nạp;
(2) phép tính — không tool nào trả *một frame hai
mã cạnh nhau*, `get_series` là 1 field × 1 mã × thời gian; (3) trình bày —
`render_signal_desk` chỉ nhận `title + ≤6 × {widget, frame_id}`, không layout,
không KPI card có nội dung, không khối narrative, catalog 9 widget không có so
sánh theo entity, không pie/grouped bar. Prompt không phải nguyên nhân.

Hướng đề xuất: **giữ tầng "engine tính, model chỉ chọn cấu trúc"** (đã là
state-of-the-art theo research — Rogo, Kensho Grounding, claim-locked reporting
arXiv 2608.25336), nhưng đổi **đơn vị sáng tác** từ *Study = cả board viết sẵn*
sang *Board DSL = model soạn cấu trúc từ frame đã tính*, và biến Study thành
**template board** chạy trên cùng DSL. Không đi đường Lovable/v0 sinh code hay
Vega-Lite tự do.

# Hợp đồng brainstorm

**Outcome.** Một câu hỏi phân tích bất kỳ trong phạm vi dữ liệu store (một mã ·
nhiều mã · toàn Universe · chuỗi thời gian · cấu trúc BCTC) → một board Signal
Desk có layout (grid), KPI card, chart đúng loại, bảng so sánh, và narrative —
trong đó **mọi con số trên board và trong narrative đều là tham chiếu tới một ô
đã tính**, model không gõ số nào. Mở lại sau 30 ngày render y hệt.

**Constraints.**
- Bất biến S0 giữ nguyên: `frames` không vào transcript · `as_of` đóng băng ·
  widget name+version + fallback `data_table` · headline ≤300 token.
- Nguồn dữ liệu duy nhất vnstock (Bronze dev / Diamond prod).
- `src/stocks/*` freeze — nạp thêm dòng BCTC cần **amendment** riêng.
- Trần chi phí `TURN_COST_MICRO_USD = 500.000`, `MAX_TOOL_ROUNDS = 4`.
- Track S mở sau gate C4; đề xuất này **định nghĩa lại S1**, không nhảy gate.

**Non-goals.** Sinh code React/HTML runtime · Vega-Lite/ECharts JSON do model
viết · realtime · khuyến nghị có giá (S2) · proactive scan (S3) · MCP Apps/A2UI
interop (chỉ theo dõi).

**Acceptance (đo được).**
1. Hai câu ví dụ của user đều ra board: câu BCTC → ≥1 bảng so sánh 2 mã, ≥1
   grouped bar, ≥3 KPI card có `role` thắng/thua, 1 khối narrative.
2. **100% số** trong KPI card và narrative resolve về `(frame_id, row, col)`;
   grader deterministic (không cần LLM judge) — đây là chỗ giải bài toán
   citation mà C1 đo là bất khả khi quét text hậu kiểm: **bind lúc sinh, không
   quét sau**.
3. Replay artifact sau 30 ngày byte-identical (test có sẵn mở rộng).
4. Golden set nhóm `signal_desk` ≥ 50 câu **random do người ngoài team viết,
   không lộ trước cho dev**; pass = board ra + 100% số resolve + 0 số bịa.
   Câu fail → thêm vào set, **không** thêm Study. Đo scale, không đo danh sách.
5. Chi phí/Turn Signal Desk ≤ 2× Turn web-first đo được (42.181 µUSD).

# Hiện trạng đã xác minh (file:line)

| Tầng | Có | Thiếu |
|---|---|---|
| Data ops | `get_series` 1 field×1 mã (`tools/signals.py:486`) · `run_study` 4 Study · `reads_fundamental.py` 5 dòng/quý, 8 quý cho 30 mã declared | frame **entity × metric** (nhiều mã) · dòng BCTC (DT, LN gộp, nợ, CFO, NIM/CIR/NPL) · phép suy diễn deterministic (ratio, YoY, share-of-total, rank) trên frame |
| Compose | `render_signal_desk` title + ≤6 `{widget, frame_id}` (`tools/studies.py:94-135`) · gom frame nhiều artifact cùng Turn được (`frames_buffer.read_frame`) | layout/grid · section · KPI card bind ô · narrative block · chọn cột trong frame · `MAX_BLOCKS=6` |
| Widget | 9 loại/14 version (`contracts/signal-desk-widget-catalog.json`) | grouped/stacked bar theo entity · pie/donut · comparison table có role · waterfall · bullet/gauge · text card |
| FE | panel một cột 1120px, block xếp dọc (`signal-desk-panel.tsx`) | grid 12 cột, section header, card group |
| Đo | `test_agent_signal_desk` 11 pass; golden chưa có nhóm `signal_desk` | grader "số resolve về ô" |

Lưu ý: scout nói `earnings_dislocation_screener` không chạy vì thiếu
`market_index` — **mâu thuẫn** roadmap S0 gate (chạy thật 2026-08-29). Chưa
xác minh, không dựa vào.

# Ba hướng

## A — Tiếp tục S1 như roadmap: thêm Study tới ≥10

Mỗi dạng câu hỏi = một Study Python viết tay.
- Giả định gánh: tập câu hỏi thường gặp **hữu hạn và đoán được**.
- Đổ đầu tiên khi: câu hỏi ghép ("so sánh A với B **rồi** xem thanh khoản") —
  tổ hợp mã × metric × khung × phép so tăng theo tích, không cộng. Chính là lý
  do câu BCTC hôm nay tệ, và 10 Study không đổi bản chất.
- Worst case: 10 Study, vẫn 80% câu hỏi rơi vào prose.

## B — Lovable/v0-style: model sinh code hoặc spec chart tự do

- Giả định gánh: model tạo spec đúng và không nhúng số.
- Đổ đầu tiên khi: model gõ số vào spec (bịa hoặc làm tròn) — không có cổng nào
  bắt được vì spec là code. Research: GPT-4o ~70% Vega-Lite hợp lệ, Gemini 24%
  (arXiv 2601.15385); Lovable chạy sandbox Modal, mỗi lần regen khác nhau → phá
  bất biến replay `as_of`.
- Worst case: board đẹp, số sai, không truy được. **Đúng thứ moat này cấm.**

## C — Board DSL trên frame đã tính + Study thành template *(đề xuất)*

Cùng tầng an toàn với json-render (Vercel), A2UI (Google), OpenAI Apps SDK
"data tool tách render tool", Rogo/Kensho "số từ data pull, không từ model".

Ba lớp, mỗi lớp một owner:

1. **Data ops (engine, deterministic)** — tool trả `frame_id`, không trả số:
   - `compare_fields(symbols[], field_ids[])` → frame `table` hàng = mã, cột =
     field, `point_roles` thắng/thua do engine gán theo hướng tốt của field.
   - `get_statement(symbol, lines[], quarters)` → frame `table` quý × dòng
     (cần data — xem nợ dữ liệu).
   - `query(table, symbols[], cols[], window)` → frame thô từ `bar_daily`,
     intraday 15m, statements, foreign flow, corporate actions. 33 Signal
     Field là **shortcut đáng tin**, không phải trần dữ liệu.
   - `compute(code, inputs=[frame_ids])` → frame mới. Model viết pandas/SQL
     **trên frame đầu vào**, chạy sandbox; **số chỉ vào qua frame** — validator
     từ chối literal số trong code (trừ hằng cấu trúc 100/4/252…) hoặc gắn cờ
     provenance "có hằng k". Replay lưu code + `as_of`. Đây là tầng làm hệ
     **tổng quát**: một enum op đóng chỉ là đoán trước câu hỏi ở tầng thấp hơn.
   - `frame_from_evidence(url, rows)` → frame provenance `web`, cho câu ngoài
     store (vĩ mô, tin, công ty chưa niêm yết); board vẽ khác màu store.
   - `get_series` giữ nguyên; thêm `symbols[]` để ra frame nhiều cột.
2. **Board DSL v2 (model soạn cấu trúc, không soạn số)** — `render_signal_desk`
   nhận:
   ```
   { title, sections: [ { heading?, columns: 1|2|3,
       blocks: [ { widget, frame_id, columns?: [..], options? }
               | { kind: "kpi", label, value: {ref}, delta?: {ref}, role?: {ref} }
               | { kind: "narrative", template: "VCB ROE {a} so với VIC {b}…",
                   refs: { a: {frame_id,row,col}, b: … } } ] } ] }
   ```
   Server resolve mọi `{ref}`; ref sai → block đó thành `data_table` + lý do
   (mở rộng luật fallback đã có). Narrative **không được chứa chữ số** ngoài
   placeholder — validator từ chối, model sửa (đây là "provenance-before-prose").
3. **Catalog mở rộng, có luật chọn** — thêm `grouped_bar` · `comparison_table`
   · `donut` (≤5 phần, Draco/Cleveland-McGill: từ chối >5 → `ranked_bars`) ·
   `waterfall` · `bullet` · `text_card`. Frame kind + số hàng/cột quyết widget
   hợp lệ; enum vẫn do server kiểm.

**Nguyên lý scale**: không gian câu hỏi = dữ liệu × phép tính × trình bày; ba
trục làm **độc lập và tổng quát**, không ai liệt kê giao của chúng. Câu lạ đi
thẳng `query → compute → render`; thất bại chỉ vì một lý do đo được (dữ liệu
không có), và board vẫn ra với block "không có dữ liệu X". Là Hex/Julius (code
trên dataframe) **cộng** Rogo/Kensho (số từ data pull) — research chưa thấy ai
ghép hai cái này.

**Study = template (cache chất lượng, không phải đường chính)**: một Study khai *data plan* (chuỗi data ops) + *board spec*
v2 viết sẵn. Ba Study hiện tại port sang, vẫn deterministic, vẫn có version.
Model chọn template khi khớp, còn không thì tự soạn — cùng một renderer, không
hai hệ.

- Giả định gánh: model soạn được cấu trúc tốt khi được cho đúng frame và enum.
  Research ủng hộ: catalog-constrained JSON là tầng "high determinism, low
  fabrication"; không cần model viết encoding.
- Đổ đầu tiên khi: **dữ liệu không có**. DSL không cứu được câu BCTC nếu store
  chỉ có 5 dòng/quý. Nợ dữ liệu là điều kiện tiên quyết, tách riêng dưới.
- Worst case: board xấu về thẩm mỹ nhưng **không sai số** — chấp nhận được, và
  đo được để sửa.

# Nợ dữ liệu — kiểm kê DB thật 2026-08-29 22:55

| Có | Thiếu (Bronze giải) | Thiếu (0đ, nối dây) |
|---|---|---|
| `bar_daily` 1.523 mã 2010→2026-08-27, VNINDEX có · `financial_statement_line` 8 quý 1.235 mã · `financial_ratio_snapshot` 30 mã · `reference.shares` 30 mã · intraday 15m 4 mã | BCTC >8 quý · ratio ngân hàng chuẩn · khối ngoại (0 dòng) · sổ lệnh/tự doanh/volume profile · vĩ mô · cổ đông/sự kiện · scan 3× | nối `financial_statement_line` vào `query` · market cap = close×shares · backfill intraday 30 mã |

Bronze **không** giải: licence phân phối, WebSocket, news, device-id Docker/CI
(chưa xác nhận). Chi tiết + 9 câu go/no-go:
`research-260829-2015-vnstock-bronze-full-power.md`.

## Nạp thêm (khi tới foreign flow / depth — cần amendment freeze)

`Capability.FUNDAMENTAL` hiện ghi 5 dòng. Câu BCTC đòi thêm: doanh thu, LN
gộp, LN HĐKD, CFO, tổng tài sản, nợ vay, vốn CSH; ngân hàng: NIM, CIR, NPL, CASA,
LDR (vnstock `Finance` ratio/income/balance). Nạp **toàn bộ bảng thô** income/balance/cashflow/ratio của vnstock, không chọn
dòng theo câu hỏi — cùng nguyên lý scale. Surface: `providers/vnstock_daily.py`
hoặc collector fundamental mới + `providers/contracts.FundamentalSnapshot`
+ backfill. Ước 30 mã × 8 quý, Bronze pacing được. **Đây là surface freeze** →
amendment CLAUDE.md riêng, không nằm trong plan DSL. Không có nó, C chỉ chứng
minh được trên câu thanh khoản/giá/earnings.

# Vị thế sản phẩm (từ research)

- VN chưa ai làm generative board: DNSE Ensa = chatbot + gợi ý; Simplize =
  định giá AI; FireAnt/SSI/TCBS = chart truyền thống. **Whitespace thật.**
- Moat không phải "AI vẽ chart" (ai cũng làm được với Vega-Lite) mà là
  **semantic layer VN** — Signal Field registry + refusal vocabulary + basis/band
  rules — đúng bài học Power BI/ThoughtSpot/Genie: semantic layer là cần gạt
  chính xác, không phải model. Đầu tư mở rộng registry > đầu tư chart engine.
- "Copilot cho broker vs investor" ở tầng này = **template khác nhau trên cùng
  DSL** (broker: peer comparison, screener, desk theo danh mục khách; investor:
  condition review, thesis). Persona là bộ template + entitlement (C6), không
  phải kiến trúc khác.

# Ảnh hưởng roadmap (đề xuất sửa, chưa sửa)

- **S1 viết lại**: Objective "nhiều Study" → "board composer + data ops +
  template; Study cũ port sang template". Gate giữ ≥90% golden `signal_desk`,
  thêm tiêu chí "100% số resolve về ô".
- **C4 nhận một grader mới rẻ**: cho lane Signal Desk, citation là bài toán
  đóng (ref → cell), khác lane web-first. Có thể là grader deterministic đầu
  tiên của C4 cho câu trả lời có số.
- Thứ tự thi công gợi ý: (0) amendment + nạp dòng BCTC → (1) data ops
  `compare_fields`/`derive` → (2) DSL v2 + validator + fallback → (3) FE grid +
  6 widget mới → (4) port 3 Study thành template → (5) golden `signal_desk` 20
  câu + grader → (6) prompt body pack: playbook soạn board.

# Rủi ro còn mở

- Token: DSL v2 dài hơn schema hiện tại; đo trước khi chốt `MAX_BLOCKS`. Cấu trúc
  ref chỉ tốn ~15 token/số, rẻ hơn model gõ narrative có số.
- Model "lười" soạn board và trả prose — cần trigger giống C5 (mode
  `signal_desk` → bắt buộc ít nhất một `render_signal_desk` hoặc nêu lý do
  không vẽ, đã có sẵn câu trong prompt).
- `MAX_TOOL_ROUNDS = 4`: data ops song song một round + derive một round +
  render một round là 3; vừa đủ, không dư.

# Câu hỏi chưa chốt (cần user)

1. Chấp nhận **định nghĩa lại S1** như trên (thay "≥10 Study") không?
2. Amendment freeze cho nạp dòng BCTC: làm **trước** plan DSL, hay chứng minh
   DSL trên câu giá/thanh khoản trước rồi mới nạp BCTC?
3. Narrative trên board: model viết template có placeholder (đề xuất) hay backend
   viết câu từ template Study (an toàn hơn, cứng hơn)?
