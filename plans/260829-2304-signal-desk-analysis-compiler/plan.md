---
title: "Signal Desk Analysis Compiler"
description: "Đưa Signal Desk từ 'chọn một Study viết sẵn' sang 'analysis compiler': model soạn kế hoạch tính và cấu trúc trình bày, engine tính mọi con số, board là artifact có bằng chứng render lại được — trả lời được câu hỏi phân tích chưa ai đoán trước."
status: in_progress
priority: P1
effort: "150h"
branch: "develop"
tags: [signal-desk, track-s, generative-ui, evaluator, backend, frontend, data]
blockedBy: []
blocks: []
relatedTo:
  - 260829-2141-c2-context-and-cache
  - 260826-2158-study-artifact-canvas
  - 260829-1349-c1-search-and-evidence
created: 2026-08-29
---

# Signal Desk Analysis Compiler

## Overview

Hôm nay một câu hỏi phân tích chỉ ra board khi **có đúng một Study viết sẵn cho
nó**. Bốn Study phủ bốn dạng câu; câu thứ năm ("so sánh BCTC VIC vs VCB, mã nào
nền tảng tốt hơn") rơi về văn xuôi, dù store **đã có** 302.528 dòng BCTC cho
1.235 mã. Nguyên nhân đo được trong code, không phải prompt:
`get_series` là 1 field × 1 mã × thời gian (`agent/tools/signals.py:486`);
`render_signal_desk` chỉ nhận `title + ≤6 × {widget, frame_id}`
(`agent/tools/studies.py:94-135`); catalog 8 widget không có so sánh theo
entity; panel một cột (`signal-desk-panel.tsx:137`); kho BCTC
(`stocks/financial/reads.py`) chỉ một Study đọc.

Plan này đổi **đơn vị sáng tác**. Model không chọn Study nữa; model soạn một
*kế hoạch phân tích* (query → compute → render) trên ba trục **độc lập và tổng
quát** — dữ liệu, phép tính, trình bày — và không trục nào liệt kê trước câu
hỏi. Study cũ trở thành *template* chạy trên cùng đường ống, là cache chất
lượng, không phải đường chính. Bất biến S0 giữ nguyên và được siết thêm một
bậc: **model không bao giờ gõ một con số thị trường** — không trong code,
không trong KPI, không trong narrative; mọi số là tham chiếu `(frame, row,
col)` server resolve.

Nguồn quyết định: `plans/reports/brainstorm-260829-2240-signal-desk-generative-bi.md`
(hợp đồng, ba hướng, research landscape, kiểm kê DB 22:55).

## Delivery Contract

- **Outcome.** Một câu hỏi phân tích bất kỳ trong phạm vi dữ liệu store (một
  mã · nhiều mã · toàn Universe · chuỗi thời gian · cấu trúc BCTC · kết hợp)
  → một board có KPI strip, chart đúng loại theo hình dạng dữ liệu, bảng so
  sánh, caption ngắn — trong đó 100% con số resolve về một ô đã tính, model
  không gõ số nào. Câu ngoài store → số từ trang web đã đọc, chứng minh được
  là có trên trang. Mở lại sau 30 ngày render y hệt. Trong mode `signal_desk`
  **không bao giờ** trả prose thay board: board xấu-nhưng-đúng luôn thắng.
- **Constraints.** Bất biến S0: `frames` không vào transcript · `as_of` đóng
  băng · widget name+version + fallback `data_table` · headline ≤ 300 token.
  Nguồn dữ liệu duy nhất vnstock. `src/stocks/*` freeze — mọi file chạm ghi
  trong bảng surface của phase 01, không nới bằng một dòng. Trần
  `TURN_COST_MICRO_USD = 500.000`, `MAX_TOOL_ROUNDS = 4`,
  `MAX_EXTERNAL_TOOL_CALLS = 7` **không đổi**. Không dependency mới khi chưa
  hỏi (phase 03 và 10 có điểm phải hỏi, ghi rõ). Không migration khi chưa
  backup.
- **Non-goals.** Sinh code React/HTML runtime · Vega-Lite/ECharts do model
  viết · realtime/WebSocket · khuyến nghị có giá (S2) · proactive scan (S3) ·
  MCP Apps/A2UI interop · panel toàn màn hình (chưa bàn) · domain pack thứ hai.
- **Acceptance.** Xem *Success Criteria* — mỗi dòng trỏ về một gate đo được
  của một phase.

## Evidence And Decisions

- **Tầng an toàn giữ nguyên, đổi độ biểu đạt.** Research 2026-08-29: hệ hiện
  tại đã ở tầng "engine tính, model chọn cấu trúc" — cùng tầng Rogo, Kensho
  Grounding, Vercel `json-render`, Google A2UI. Lovable/v0 (sinh code) và
  Vega-Lite tự do (GPT-4o ~70% spec hợp lệ, arXiv 2601.15385) là bước lùi với
  ràng buộc không bịa số. **Rejected: B (sinh code/spec tự do).**
- **Enum phép tính đóng là đoán trước câu hỏi ở tầng thấp hơn.** Tính tổng
  quát đến từ `compute(code, frames)`: model viết pandas **trên frame**, số chỉ
  vào qua frame, validator chặn literal. Là Hex/Julius (code trên dataframe)
  ghép Rogo/Kensho (số từ data pull). **Rejected: A (thêm Study tới ≥10).**
- **Trực quan là thứ schema cho phép và server ép, không phải lời dặn.** Ngữ
  pháp board (KPI strip bắt buộc, caption ≤ 280 ký tự, `data_table` chỉ ở
  appendix), chọn widget theo hình dạng frame (Draco/Cleveland-McGill), màu
  theo role do engine gán, layout 12 cột do server tính, 5 archetype có slot
  kiểu, lint điểm trực quan + auto-compose khi model bỏ cuộc.
- **Đính chính dữ liệu 22:55.** Kho BCTC đã có (`financial_statement_line`
  302.528 dòng · VCB 155 / VIC 174 chỉ tiêu · 8 quý · `vnstock.VCI`);
  `financial_ratio_snapshot` 30 mã; `reference.shares` 30 mã; `bar_daily`
  1.523 mã + VNINDEX; intraday 15m **4 mã**; khối ngoại **0 dòng**. Câu BCTC
  tệ là nợ **nối dây**, không phải nợ nạp. Bronze giải khối ngoại, độ sâu BCTC,
  sổ lệnh/vĩ mô — là chiều rộng, xếp phase cuối, **conditional** trên 9 câu
  go/no-go của `plans/reports/research-260829-2015-vnstock-bronze-full-power.md`.
- **Ba quyết định chốt 2026-08-29 23:00 (đảo được, cần user):** (1) S1 định
  nghĩa lại = query + compute + Board DSL + template, không "≥10 Study";
  (2) nối data có sẵn trước, Bronze sau; (3) caption do model viết template có
  placeholder, server resolve — backend sinh câu là quay về Study cứng.
- **Không gate hai lần một sự thật.** Ngưỡng trực quan (`visual_ratio` 0,7,
  caption 280 ký tự) là *đoán hợp lý*, đặt lại từ phân bố 50 câu đầu ở phase
  09 — đúng luật "không có ngưỡng trước khi có phân bố" của C2. Hai bất biến
  **không** chờ phân bố: refs resolve 100%, frames không vào transcript 100%.
- **Quan hệ với C2 (`260829-2141`, in_progress).** C2 đo context theo layer và
  chuyển domain body vào prefix; phase 08 của plan này đổi prompt core + body
  pack → làm lệch baseline replay của C2. **Phase 08 blockedBy C2 phase 05**
  (replay gate). Các phase khác không chạm `messages.py`/prune.
- **Gate C4 mở cho S1 vẫn đứng.** Phase 09 dựng grader deterministic cho họ
  `signal_desk` — chính là phần C4 ghi "chưa có: có desk? frames không lọt?" —
  nên S1 và C4 tốt nghiệp **cùng một bằng chứng**, không phải S1 vượt gate.

## Phases

| # | Phase | Status | Effort | Dependency |
|---|---|---|---|---|
| 1 | [Amendment & roadmap](./phase-01-amendment-and-roadmap.md) | Done | 4h | — |
| 2 | [Query layer — frame từ store](./phase-02-query-layer.md) | Done | 20h | 1 |
| 3 | [Compute sandbox — phép tính tổng quát](./phase-03-compute-sandbox.md) | Done | 22h | 2 |
| 4 | [Evidence frames — số web có chứng](./phase-04-evidence-frames.md) | Done | 10h | 2 |
| 5 | [Board grammar & composer](./phase-05-board-grammar-and-composer.md) | Done | 24h | 2, 3 |
| 6 | [Web grid & widgets](./phase-06-web-grid-and-widgets.md) | Done | 22h | 5 |
| 7 | [Studies as templates](./phase-07-studies-as-templates.md) | Done | 14h | 3, 5 |
| 8 | [Prompt playbook](./phase-08-prompt-playbook.md) | Done | 8h | 5, 7; **C2 phase 05** |
| 9 | [Golden `signal_desk` gate — S1 Current](./phase-09-golden-signal-desk-gate.md) | Blocked — harness xong, chờ corpus | 16h | 4, 6, 7, 8 |
| 10 | [Bronze data breadth](./phase-10-bronze-data-breadth.md) | Blocked — chờ văn bản Vnstock | 10h+ | 2; go/no-go Bronze |

Song song được: 3 ∥ 4 (khác file) · 6 ∥ 7 (FE ∥ BE, chung contract JSON đã
chốt ở 5) · 10 độc lập sau 2.

## Success Criteria

- [x] Câu BCTC VIC vs VCB (tự soạn) ra board: `comparison_table` có role
      winner/loser theo **ô**, `grouped_bar` companion, KPI strip 4 ô,
      1 caption/section, appendix một bảng. *(phase 05 + 06 — API
      `test_vic_against_vcb_compiles_into_the_board_the_plan_describes`, web
      `signal-desk-board.test.tsx`)*. Câu thanh khoản VIC qua template là
      **phase 07**.
- [x] 100% số trên board (KPI, caption) resolve về `(frame, row, col)` — cơ chế
      xong ở 05: mọi số là một `Ref` server tra, `caption_has_digit` từ chối
      chữ số model tự gõ **kể cả năm**, và spec lưu giá trị đã resolve. Corpus
      là 09. *(phase 05, đo ở 09)*
- [x] `compute` từ chối mọi literal số ngoài hằng cấu trúc khai báo; 0 literal
      lọt trên corpus. *(phase 03, đo ở 09)* — **cơ chế xong ở 03**: validator
      AST, 21 test; corpus là 09.
- [x] Số từ web chỉ vào frame khi **có mặt trong text trang đã fetch cùng
      Turn**; row không tìm thấy bị từ chối có tên. *(phase 04)* — 58 test bảng
      số + 17 test tool; ba verdict `matched`/`not_on_page`/`ambiguous`.
- [ ] Replay artifact sau khi đổi code/prompt: frames byte-identical, board
      render y hệt; test transcript "frames không vào message" mở rộng cho
      `query`/`compute`/`frame_from_evidence`. *(phase 02–05)*
- [x] Bốn Study cũ chạy qua template trên cùng composer; frames số học khớp
      fixture chụp từ store trước khi port. *(phase 07)* — 1e-9 trên store thật,
      cho mọi frame còn sống. Frame `tiles` của cả bốn **bỏ**: dải KPI của board
      v2 thay nó và mỗi ô là một `Ref` server tra, nên phép so mạnh hơn. Gate
      *"thời gian chạy ≤ hiện tại + 20%"* **không đạt được và đó là số học** —
      một lượt gọi sandbox tốn 260 ms đo được, một plan có 4–8 bước, nên sàn đã
      là 5× Study nhanh nhất. Đo: 1,12–2,20 s mỗi template.
      `plans/reports/phase-07-260830-studies-as-templates.md`
- [ ] Golden `signal_desk` ≥ 50 câu do người ngoài team viết, dev không thấy
      trước; pass ≥ 90% grader deterministic; câu fail vào set, **không** thêm
      Study. Roadmap S1 → `Current`. *(phase 09)* — **bộ đo xong 2026-08-30**
      (18 grader, mode chạy, hash corpus, rút mẫu theo seed có sàn family, 60
      test xanh); corpus chờ ≥ 60 câu từ ≥ 3 người ngoài repo.
      `plans/reports/phase-09-260830-golden-signal-desk-harness.md`
- [ ] Chi phí/Turn Signal Desk ≤ 2 × Turn web-first đo được (≤ 84.362 µUSD);
      `MAX_TOOL_ROUNDS`/`MAX_EXTERNAL_TOOL_CALLS` không đổi. *(phase 09)*
- [x] Năm cổng xanh: `make test` (2.123 passed) · `pnpm type-check` · `pnpm lint`
      · `pnpm test` (885 passed) · `pnpm build`. Đo 2026-08-30 sau phase 08.
      Đo lại sau bộ đo phase 09 và vòng code review của nó: `make test`
      **2.150 passed / 8 skipped** (3:22); bốn cổng web không chạy lại vì lượt
      này không sửa file nào trong `apps/web`.
- [ ] Bronze (nếu GO): `foreign_flow_not_stored` VCB 3 → 0; BCTC ≥ 20 quý cho
      30 mã declared; mọi nguồn mới chỉ là một member enum `source` của
      `query`, không đổi tầng trên. *(phase 10)*

## Risk Register

| Rủi ro | Tín hiệu | Phản ứng định trước |
|---|---|---|
| Model "lười" soạn board, trả prose | grader `board_present` < 100% trong mode `signal_desk` | auto-compose ở loop (phase 05) là tấm lưới; nếu vẫn hụt → siết câu core ở phase 08, không nới grammar |
| `compute` sandbox thoát (network, fs) | test escape fail | AST allowlist + subprocess không mạng + rlimit; không đủ → hạ về whitelist hàm pandas, ghi là quyết định |
| Bảng shape → widget chọn sai | review 50 board đầu | luật là bảng deterministic — sửa một dòng, có test fixture; không mở tham số cho model |
| Ngữ pháp quá chặt, model bỏ caption cần thiết | tỉ lệ lỗi `caption_too_long` cao ở phase 09 | đặt lại trần từ phân bố, không bỏ trần |
| Phase 08 va C2 replay | C2 phase 05 chưa đóng khi 08 sẵn sàng | 08 chờ; các phase khác không phụ thuộc 08 trừ 09 |
| pandas không có trong `requirements.txt` | kiểm ở phase 03 bước 0 | **hỏi user** trước khi thêm — DoD #4 |
| Bronze không xác nhận device-id/quota page | support không trả lời văn bản | phase 10 giữ `Conditional`; plan đóng được không cần nó |
| Panel inspector quá hẹp cho grid | board 3 cột vỡ ở 1120px | layout engine hạ về 2 cột dưới breakpoint; toàn màn hình là non-goal, ghi backlog |

## Câu hỏi chưa chốt

1. Xác nhận ba quyết định ở *Evidence And Decisions* (S1 định nghĩa lại · data
   trước · caption do model template).
2. ~~pandas/numpy có được phép là dependency runtime của API không?~~
   **Trả lời 2026-08-30 bằng cách đọc:** cả hai đã ở `requirements.txt` từ
   trước (pandas 2.3.3 · numpy 2.2.6). Không thêm dependency nào.
3. Ai viết 50 câu golden ngoài team, và kênh thu nào để dev không thấy trước?
   **Còn mở, và là thứ duy nhất chặn phase 09.** Mẫu câu form + lệnh rút mẫu đã
   sẵn (`apps/api/golden/README.md`); cần file submissions ≥ 60 câu.
4. Bronze: gửi 9 câu go/no-go khi nào; phase 10 mở khi có văn bản trả lời.
   **Còn mở** — mẫu tin nhắn đã soạn trong report research.

<!-- slug: signal-desk-analysis-compiler -->
