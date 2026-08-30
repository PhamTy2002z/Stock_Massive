---
phase: 1
title: "Amendment & roadmap"
status: completed
priority: P1
effort: "4h"
dependencies: []
---

# Phase 1: Amendment & roadmap

## Overview
Mở ranh giới freeze đúng cho plan này, viết lại S1 trong roadmap theo định
nghĩa mới, và nối quan hệ hai chiều với plan C2. Phase này **không sửa code**;
nó là điều kiện để mọi phase sau được phép chạm file.

## Requirements
- Functional: bảng surface trong `CLAUDE.md` liệt kê **mọi** file phase 02–10
  chạm, mỗi dòng một giới hạn; roadmap §4 S1 viết lại Objective/Trước→Sau/
  Checklist/Gate; §3 C4 ghi phase 09 đóng hai mục checklist của nó; §6 cạnh
  C4→S1 giữ nguyên hướng.
- Non-functional: không đụng Track S2/S3, không đụng §3 C1/C2/C5 ngoài một
  dòng tham chiếu, không đổi Objective của C4.

## Architecture
Tiền lệ: bảng surface price-basis và c1-search — "bảng **là** ranh giới, file
ngoài bảng cần amendment mới". Viết theo đúng khuôn đó.

## Related Code Files
- Modify: `CLAUDE.md` — thêm khối "**Mở thêm 2026-08-29** cho plan
  `plans/260829-2304-signal-desk-analysis-compiler/`" sau khối c5-domain-pack,
  với bảng dưới đây.
- Modify: `docs/roadmap.md:494-511` (S1) · `:267-309` (C4 checklist hai mục) ·
  `:581+` (§6 nếu nhãn cạnh đổi).
- Modify: `plans/260829-2141-c2-context-and-cache/plan.md` frontmatter
  `relatedTo` thêm `260829-2304-signal-desk-analysis-compiler`.
- Modify: `plans/260826-2158-study-artifact-canvas/plan.md` — **chỉ** một con
  trỏ kế nhiệm ("Study → template, xem plan 260829-2304"), không viết lại.

### Bảng surface (đưa nguyên vào CLAUDE.md)

| Surface | Giới hạn |
|---|---|
| `src/studies/{frames_buffer,contracts,widgets}.py` | frame kind/role/provenance mới, `store_frame` tổng quát, catalog thêm 6 widget; **không** đổi luật ownership theo Turn, không xoá version cũ |
| `src/studies/{composer,grammar,layout,lint,archetypes,auto_compose}.py` (mới) | Board DSL v2 và luật trực quan; thuần hàm, không đọc DB ngoài `frames_buffer` |
| `src/studies/compute/*` (mới) | sandbox + AST validator; **không** import `stocks`, không mạng |
| `src/studies/templates/*` (mới) + 4 file Study cũ | port thành template; runner cũ xoá sau khi fixture khớp |
| `src/agent/tools/{query,compute,evidence}.py` (mới) · `tools/{studies,signals,web}.py` | đăng ký tool mới; `render_signal_desk` nhận schema v2; **không** đổi SSRF/denylist/`MAX_PAGE_TEXT_CHARS` của web |
| `src/agent/toolsets.py` | bundle `signals` thêm `query`,`compare_fields`; `studies` thêm `compute`; `web` thêm `frame_from_evidence`; `CHAT_TOOLSETS` vẫn literal |
| `src/agent/loop.py` | **đúng một** hook auto-compose cuối Turn trong mode `signal_desk` + cập nhật `SIGNAL_DESK_NOTE`; không đổi ba hằng trần |
| `src/agent/messages.py` | **chỉ** `signal_desk_of` nhận `autoComposed`; không đụng prune/estimate (C2 sở hữu) |
| `src/agent/prompt/sections.py` · `domain/vn_equity.py` | section TOOLS + câu Signal Desk core; body PLAYBOOK soạn board; bump `PROMPT_VERSION`, pack `VERSION`. **Chờ C2 phase 05** |
| `src/stocks/financial/reads.py` | **chỉ import để đọc** từ `tools/query.py`; thêm ≤ 2 hàm đọc nhiều mã/nhiều kỳ, không đổi hàm đang có |
| `src/stocks/financial/{fetch,store}.py` + revision mới | bảng nhãn `financial_statement_item` (item_id → label vi/en), nạp một lần; phase 10 nới `periods` |
| `src/stocks/signals/bars.py` | **một** nhánh: `market_cap_vnd` suy từ `close × reference.shares` khi bar không có; không đổi basis/band |
| `src/stocks/intraday/ingest.py` · `Makefile` | target `backfill-intraday SCOPE=declared`; không đổi shape bar |
| `src/stocks/providers/vnstock_data.py` (mới, phase 10) · `core/quota.py` · `requirements.txt` · `.env.example` · `docker-compose*.yml` | adapter Sponsor sau contract; arbiter 4 cửa sổ; **hỏi user trước** khi thêm dep |
| `src/alpha/models.py` · `alembic/versions/*` (thêm) | `financial_statement_item`; phase 10: `foreign_flow_daily`, `macro_series`; `agent_artifact` **không đổi cột** — spec v2 sống trong `signal_desk_spec` JSONB |
| `apps/web/src/components/signal-desk/**` · `lib/alpha-desk/types.ts` · `lib/signal-issues.ts` · `contracts/signal-desk-widget-catalog.json` | grid, KPI strip, caption, 6 widget, badge nguồn web; không đụng `SignalDeskToggle` |
| `apps/api/golden/*` · `apps/api/Makefile` | corpus `signal_desk.json`, grader mới, target `golden-run MODE=signal_desk` |
| `apps/api/tests/*` · `apps/web/src/**/*.test.*` | test mọi surface trên; **thêm ở cuối file**, không reflow |
| `docs/roadmap.md` · `CLAUDE.md` | §4 S1, §3 C4 (hai mục checklist), §Quy ước |

## Implementation Steps
1. Đọc `CLAUDE.md:8-228` để đặt khối mới đúng vị trí và đúng giọng; chèn bảng.
2. Viết lại `docs/roadmap.md` S1: Objective *"Một câu hỏi phân tích chưa đoán
   trước → board có bằng chứng; Study là template, không phải điều kiện"*;
   bảng Trước→Sau (4 Study → query/compute/render + 4 template · 1 board/Turn
   cứng → ≤ 2 board, ≤ 14 block · số trong prose không kiểm được → 100% ref);
   Checklist = 9 gate của phase 02–09; Gate = golden `signal_desk` ≥ 90% + hai
   bất biến 100%.
3. C4: đổi `[~] Grader deterministic — … Chưa có: có desk? đúng Study? outcome
   khớp? frames không lọt?` → ghi hai mục "có desk?" và "frames không lọt?"
   thuộc phase 09 plan này; giữ nguyên phần còn lại.
4. Cập nhật frontmatter C2 và con trỏ kế nhiệm ở study-artifact-canvas.
5. `ak plan validate plans/260829-2304-signal-desk-analysis-compiler`.

## Success Criteria
- [x] Mọi file trong `Related Code Files` của phase 02–10 có dòng trong bảng.
- [x] Roadmap S1 không còn câu "≥ 10 Study"; Objective nói bằng năng lực.
- [x] C2 `relatedTo` và plan này `relatedTo` trỏ nhau.
- [x] Không đụng Track S2/S3, C1/C5.

## Evidence — thi công 2026-08-29

- **Khối amendment ở `CLAUDE.md`** đặt **sau** khối C2 (`260829-2141`), không
  phải sau khối c5 như bước 1 viết: các khối "Mở thêm" xếp theo thời gian, và
  C2 là khối cuối trước `Nguồn data ngoài duy nhất`.
- **Bảng chèn vào `CLAUDE.md` rộng hơn bảng dự kiến ba dòng**, vì ba file có
  trong `Related Code Files` của phase 02 mà bảng dự kiến bỏ sót:
  `src/stocks/signals/registry.py` (trường `SignalField.better`),
  `apps/api/scripts/seed_statement_item_labels.py`, và giới hạn "không đụng
  Track S2/S3" gộp vào dòng `docs/roadmap.md · CLAUDE.md`.
- **Hai đính chính với code thật**, ghi vào chính khối amendment:
  head alembic là **`b5d1c7e04a83`** (một head duy nhất, 35 revision — plan
  đoán `a3f7e21b8d54` và nghi có hai head; không có); **`pandas>=2.0.0`** và
  **`numpy>=1.24.0`** đã ở `requirements.txt:50-51`, `intraday/ingest.py` đã
  import pandas — câu hỏi mở #2 của plan đã có trả lời.
- **Reader `reference` chốt ở `stocks/signals/bars.py`**, không ở
  `tools/query.py`: cùng một phép đọc phục vụ nhánh market cap của `bars.py`
  và source `reference` của `query`, và `src/stocks/*` không được import
  `src/agent/*` — nên chiều import duy nhất hợp lệ là `query.py` gọi sang.
  Ghi trong khối amendment để không phải suy lại ở phase 02.
- **`plans/260826-2158-study-artifact-canvas/` không còn tồn tại** (đã retire ở
  commit "retire the plans that closed"), nên con trỏ kế nhiệm của bước 4
  không có đích. `relatedTo` của plan này vẫn giữ tên đó như một bản ghi lịch
  sử; `ak plan validate` xanh.
- **`plans/260829-2141-c2-context-and-cache/plan.md` đã có** dòng `relatedTo`
  trỏ về plan này từ trước — không phải sửa.
- `ak plan validate plans/260829-2304-signal-desk-analysis-compiler` → **OK**.

## Risk Assessment
Bảng thiếu một file → phase sau phải quay lại amendment (tín hiệu: reviewer
tìm file ngoài bảng). Phản ứng: thêm dòng có ngày, không sửa lại lịch sử.
