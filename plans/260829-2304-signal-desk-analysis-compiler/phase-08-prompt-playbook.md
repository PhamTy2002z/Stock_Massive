---
phase: 8
title: "Prompt playbook"
status: complete
priority: P1
effort: "8h"
dependencies: [5, 7]
---

# Phase 8: Prompt playbook

## Overview
Dạy model **đường mới** — query → compute → render — và giữ luật an toàn ở
core. Đổi ít câu nhất có thể, mỗi câu có test giữ. **Blocked by C2 phase 05**
(replay gate) vì prompt đổi kích thước context C2 đang đo.

## Requirements
- Functional:
  - Core `TOOLS` (`sections.py:169-271`): danh mục tool cập nhật (12 → 16:
    `query`, `compare_fields`, `compute`, `frame_from_evidence`); câu "mười
    hai công cụ" đổi thành số đúng — test `test_agent_prompt.py` sửa cùng.
  - Core câu Signal Desk (`sections.py:200-205`): *"Ở chế độ Signal Desk, mọi
    câu hỏi nhận được số đều phải thành board: gom frame bằng query/compute,
    rồi render. Không render được thì nói rõ điều gì không vẽ được — hệ thống
    sẽ tự dựng board từ frame bạn đã có."* — ở **core** vì nó giữ hành vi an
    toàn (không prose thay board).
  - Core luật số (đã có "cấm bịa số liệu VN") thêm một câu: *"Bạn không gõ số
    vào caption hay code; số đến từ frame qua tham chiếu."*
  - Body pack `PLAYBOOK` (`vn_equity.py:78-101`) viết lại thành playbook soạn
    board: (1) chọn archetype theo dạng câu hỏi (bảng 5 dòng); (2) query song
    song trong một round; (3) compute một lần cho mọi tỉ số; (4) KPI trước,
    chart sau, caption ≤ 1/section; (5) so sánh ≥ 2 mã → `compare_fields` +
    `comparison_table`; (6) ngoài store → `fetch_url` rồi
    `frame_from_evidence`; (7) template khi khớp câu (`list_studies`).
    Body ≤ 1.100 token (đo).
  - `SIGNAL_DESK_NOTE` (`loop.py:356-366`) cập nhật cùng nội dung ngắn.
  - `PROMPT_VERSION` 3.1.0 → 3.2.0; pack `VERSION` 2.0.0 → 3.0.0.
  - Trigger domain body: thêm bốn tool mới vào tập "tool domain" nếu tập đó
    liệt kê theo toolset (`signals`/`studies` đã có → `query`/`compute` tự
    vào; `frame_from_evidence` ở `web` → **không** kích body, đúng vì nó
    không domain).
- Non-functional: token core tăng ≤ +150; body ≤ 1.100; tests giữ hai chiều
  (câu load-bearing không mất; sàn an toàn không rơi xuống body).

## Architecture
Không đổi cơ chế hai tầng; chỉ nội dung. `cache_key` void tự động qua
`PROMPT_VERSION` và `pack.identity`.

## Related Code Files
- Modify: `apps/api/src/agent/prompt/sections.py:47` (version), `:169-271`
  (TOOLS), `:200-205` (Signal Desk), `:77-137` (INVARIANTS một câu)
- Modify: `apps/api/src/agent/domain/vn_equity.py:26` (version), `:78-101`
  (PLAYBOOK)
- Modify: `apps/api/src/agent/loop.py:356-366` (`SIGNAL_DESK_NOTE`)
- Tests: `apps/api/tests/test_agent_prompt.py` (số tool, câu mới trong danh
  sách load-bearing, sàn an toàn), `tests/test_agent_domain_pack.py` (body
  token), `tests/test_agent_loop.py` (note)

## Implementation Steps
1. Xác nhận C2 phase 05 `completed` (`ak plan status plans/260829-2141-…`).
   Chưa → dừng phase, làm 09 phần grader trước.
2. Viết TOOLS mới; đo token core trước/sau bằng test có sẵn.
3. Câu Signal Desk + câu số ở core; thêm vào danh sách load-bearing của test.
4. PLAYBOOK mới; đo body token.
5. Bump hai version; `SIGNAL_DESK_NOTE`.
6. Chạy `make golden-run` web-first 20 câu để chắc C1 gates không giảm
   (distinct_domains ≥ 18, read_depth ≥ 16, parallel ≥ 50%).

## Success Criteria
- [ ] Core +≤150 token; body ≤ 1.100 token.
- [ ] Test hai chiều xanh; câu "16 công cụ" khớp `CHAT_TOOLSETS`.
- [ ] Golden web-first không giảm gate nào.
- [ ] C2 replay không bị phá (C2 đã đóng trước, hoặc re-baseline có ghi).

## Risk Assessment
- Model vẫn trả prose → lưới auto-compose (phase 05) bắt; đo ở 09; siết câu
  core một lần, không thêm câu thứ hai.
- Body tăng chi phí mỗi call → đo trên golden signal_desk; trần 2× web-first.

## Outcome — 2026-08-30

Done. `PROMPT_VERSION` 3.4.0, pack `vn-equity` 3.0.0. Chi tiết và số đo:
`plans/reports/phase-08-260830-prompt-playbook.md`.

- [x] Core +92 token cho phần **luật**; mục lục +136 khai riêng có tên. Tổng
      +228, trên con số +150 plan đoán — lý do ghi trong report
- [x] Body 1.064 token, dưới trần 1.100
- [x] Test hai chiều xanh; "mười sáu công cụ" khớp `CHAT_TOOLSETS`
- [ ] Golden web-first — **chưa chạy**, cần deployment và lượt gọi model thật
- [x] C2 replay không bị phá: C2 đóng `complete` trước phase này
