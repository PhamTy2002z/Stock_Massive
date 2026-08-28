# Brainstorm — Signal Desk: ba gap của board

Ngày 2026-08-28 · nhánh `feat/study-canvas-runtime` · trạng thái: **chờ user chốt → /ak-plan**

## Contract

**Outcome**
1. Thread vài chục turn, 10–20 board: người đọc quay lại board cũ trong ≤2 thao tác, không lag, không tab strip dài.
2. Câu "Mức giá được mua nhiều nhất của VCB trong phiên hôm nay là?" ra một board (volume-at-price) thay vì câu trả lời text/né.
3. Widget tô màu theo dữ liệu: nhiều series phân biệt được, vai trò ngữ nghĩa (tăng/giảm/tiêu điểm/nhóm) do engine khai báo — không còn "một xanh cho tất cả".

**Constraints**
- Ba luật cứng giữ nguyên: `frames` không vào message model · widget có name+version, catalog sinh từ `widgets.py`, viewer fallback `data_table` · `as_of` đóng băng, mở lại là render lại.
- Luật màu ở `globals.css:521` giữ: widget không mượn amber brand / violet (đọc là *trần*) cho series; `FOCUS` là **một** phần tử; màu không mang nghĩa một mình (text + data_table nói cùng điều).
- Freeze: chỉ mở `src/studies/*`, `src/stocks/intraday/*`, bundle `studies` trong `src/agent/`, surface Signal Desk trong `apps/web`.
- Không dependency mới; không migration khi chưa backup.
- Symbol **không** là information architecture chính (user chốt). Không dùng hàng chục tab.

**Non-goals**
- Realtime/ live intraday (backlog sau C8). Board "hôm nay" đọc bar 15m đã ingest, không poll.
- Đổi domain pack, tenant, entitlement.
- Gallery board xuyên thread (chỉ trong một thread).
- Cross-check khác của gap 2 ngoài câu ví dụ đã đưa (chỉ có 1 câu; các câu khác chưa nhận được).

**Acceptance**
- G1: thread có 20 board → strip ≤5 (recent + pinned); ⌘K mở switcher: zero-query hiện recent/pinned, gõ tìm theo title/mã/Study, ↑↓ Enter mở, mode "Tất cả" liệt kê đủ 20; chỉ 1 `SignalDeskPanel` mount (đã vậy, test giữ); test shell-state cho pin/unpin/recent-order.
- G2: câu ví dụ → `run_study(volume_at_price, symbol=VCB)` → board `ranked_bars`/`bar_series` mức giá theo khối lượng + `stat_tiles` (mức đỉnh, % tổng KL, phiên as_of); headline nói rõ "giao dịch nhiều nhất" (bar không tách mua/bán); test transcript không thấy frames; catalog test sync.
- G3: frame khai `series[].role` (`series|muted|focus|up|down|category:<n>`); token `--widget-cat-1..6` (dark+light) không trùng amber/violet/up/down; widget đổi version khi nhận role; contrast test ≥3:1 với surface; `dataviz` palette validator pass.

## Evidence đã scout

- `shell-state.tsx:98` `deskViews: SignalDeskTab[]` = tab strip phẳng, không giới hạn, không pin/search. `inspector.tsx:224` chỉ mount **một** panel → lag không do 20 chart cùng mount; thủ phạm là strip dài + mọi `SignalDeskCard` trong transcript + cache frames theo id.
- Payload thread đã có `signal_desks` (`agent/events.py:443`) → nguồn cho switcher, cần thêm `symbol`, `study`, `created_at` vào announcement nếu chưa có.
- `widgets/chart-theme.ts`: một `SERIES`, một `FOCUS`; `--chart-1..5` tồn tại nhưng bị cấm có lý (amber/violet).
- Store: `BarIntraday15m` (o/h/l/c/volume, `phase`, `trading_day`) — đủ dựng volume-at-price xấp xỉ (phân bổ volume bar theo dải high–low hoặc gán vào close). `get_series` chỉ đọc Signal Field **daily** → không trả lời được câu intraday; 3 Study hiện có (intraday_liquidity theo *khung giờ*, entry_condition_review, earnings_dislocation) không có mức giá.
- `frames_buffer.py`: `MAX_SIGNAL_DESKS_PER_TURN = 2`, `MAX_BLOCKS = 6`.

## Phương án

### G1 — điều hướng board
| | A. Hybrid: strip recent/pinned + ⌘K switcher (có mode "Tất cả") | B. Gallery panel cố định (tab thứ 3 Inspector) | C. Chỉ cắt N tab + menu "Board trước" |
|-|-|-|-|
| Thao tác quay lại board vừa xem | 1 (strip) | 2–3 (mở gallery, cuộn, chọn) | 1–2 |
| Tìm board cách 30 turn | ⌘K gõ 2 ký tự | cuộn/lọc | menu dài |
| Bề mặt mới | 1 overlay + strip sửa | 1 panel + trạng thái tab | 0 |
| Giả định tải trọng | user quen ⌘K (dân desk: có) | user muốn *duyệt* hơn *nhảy* | ≤10 board |
| Gãy trước khi | không có keyboard (mobile) → cần nút mở | 20+ board vẫn cuộn | 20 board |

**Khuyến nghị A.** "Tất cả" là một mode trong switcher, không phải gallery riêng — cùng một list, một search, một keyboard model; gallery chỉ thêm một chỗ phải học. Pin lưu `localStorage` theo threadId (không migration); nếu sau cần đa thiết bị → cột `agent_artifact.pinned_at` PR riêng.

### G2 — câu hỏi chưa handle
Cause: thiếu Study; không phải lỗi routing. Chọn **Study mới `volume_at_price`** (v1, `requires=("intraday_bar_15m",)`, params `symbol`, `sessions=1`, `bins`), phân bổ volume mỗi bar đều trên dải [low, high] theo tick giá VN (bước giá chuẩn của `check_price_claim` dùng lại). Headline: mức giá đỉnh, % KL, mức thứ hai, cảnh báo "bar không tách mua/bán → *giao dịch* nhiều nhất". "Hôm nay" theo luật phiên: nếu phiên chưa đóng và bar có tới bucket cuối → ghi `partial` trong provenance. Không mở `get_series` intraday (rộng hơn cần, và phá luật daily-only).

### G3 — màu
Hai tầng, cùng lúc: (1) token `--widget-cat-1..6` + `chart-theme.ts` export `CATEGORY(n)`; (2) contract frame thêm `role` optional cho series/point → widget tô theo role, default giữ hành vi cũ (không role = SERIES). Không làm: theme per-board, model chọn màu (màu là của engine/registry, không của model).

## Rủi ro chưa đóng
- Volume-at-price từ bar 15m là **xấp xỉ**; phải nói rõ trong headline + provenance, không giả là tape.
- Announcement hiện có `symbol/study` chưa? Nếu không → sửa `messages.signal_desk_of` + schema (contract công khai, test transport).
- Chỉ nhận được 1/6 câu ví dụ cho gap 2; các câu còn lại có thể lộ Study khác → plan G2 nên có bước thu thập câu hỏi lỗi (log `list_studies` miss).

## Quyết định 2026-08-28 22:40 (user chốt: triển khai thẳng, Opus subagent)
- Announcement `SignalDeskAnnouncement` có `studyName/title/round`, **thiếu `symbol`** → G1 thêm qua `messages.signal_desk_of`.
- Thứ tự **G3 → (G1 ∥ G2)**: G2 dùng `role` của G3.
- G1: strip 5 slot (pinned trước, recent sau) · switcher ⌘K một component, rỗng=recent+pinned, gõ=tìm title/mã/Study, "Tất cả"=toàn bộ theo round · pin `localStorage` theo threadId · đóng tab ≠ xoá board.
- G2: Study `volume_at_price` v1 + reason `session_not_ingested` + phễu log "list_studies không dẫn tới run_study".
- Cắt: gallery riêng, tab theo mã, theme per-board, get_series intraday.
