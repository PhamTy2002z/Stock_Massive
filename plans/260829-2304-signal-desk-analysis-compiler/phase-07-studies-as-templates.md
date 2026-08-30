---
phase: 7
title: "Studies as templates"
status: complete
priority: P1
effort: "14h"
dependencies: [3, 5]
---

# Phase 7: Studies as templates

## Overview
Bốn Study viết tay thành **template**: một data plan (chuỗi bước query/compute)
+ một board spec v2 viết sẵn, chạy trên **cùng** engine và **cùng** composer.
Một renderer, một đường lưu, một kiểu artifact. `run_study` giữ tên (tiện cho
câu hay gặp) nhưng chỉ còn là "chạy template". Study không còn là điều kiện để
có board.

## Requirements
- Functional:
  - `StudyDefinition` mới: `name · version · question · display_name ·
    params_model · plan: tuple[Step] · board: BoardSpecV2 · requires`.
    `Step ∈ {QueryStep(source, symbols_from_param, …), ComputeStep(code,
    inputs=[step names], constants)}`; `compute`/`view`/`frames`/`widgets` cũ
    **xoá** sau khi fixture khớp.
  - Runner: thực thi plan qua đúng `tools/query` reader và
    `studies/compute/runner` (không đường tắt), frame mỗi bước lưu là artifact
    riêng (để `render_signal_desk` tái trộn), board qua `composer` → artifact
    composition; `headline` ≤ 300 token do template khai (câu mẫu có
    placeholder ref, server resolve — cùng luật caption).
  - Port 4 template: `intraday_liquidity_profile` (query intraday_15m → compute
    bucket/normalise/rank → tiles/profile/heatmap/ranking), `entry_condition_
    review` (query bar_daily 250–500 + statement 1 quý → compute điều kiện →
    checklist/line/range_strip), `volume_at_price` (query bar_daily → compute
    bins → bar/tiles), `earnings_dislocation_screener` (query statement toàn
    Universe kỳ mới nhất + bar_daily 45 ngày + VNINDEX → compute → scatter/
    ranking) — cái cuối kiểm chạy được trên store thật, ghi số.
  - Fixture hồi quy: chụp `frames` của 4 Study **trước** port trên store thật
    (as_of cố định), test frames sau port khớp số (tolerance 1e-9).
  - `list_studies` không đổi shape; catalog thêm `archetype` mỗi template.
  - `code` trong ComputeStep đi qua **cùng** validator literal — template
    không được đặc quyền; hằng khai `constants` (ví dụ `bucket_minutes=15`).
- Non-functional: thời gian chạy mỗi template ≤ hiện tại + 20%; artifact
  count/Turn tăng (n bước + 1) — `MAX_SIGNAL_DESKS_PER_TURN` chỉ đếm
  composition.

## Architecture
```
run_study(name, params) → template.plan → for step: query|compute → frame artifacts
                       → composer(template.board, frames) → composition artifact → {artifactId, headline, provenance}
render_signal_desk có thể tham chiếu "<artifactId>#<stepName>" như trước.
```

## Related Code Files
- Create: `apps/api/src/studies/templates/{__init__,intraday_liquidity,entry_condition_review,volume_at_price,earnings_dislocation}.py`
- Create: `apps/api/tests/studies/fixtures/pre-port/*.json` (frames chụp)
- Modify: `apps/api/src/studies/contracts.py:412-440` (`StudyDefinition`,
  `Step`), `runner.py` (viết lại thành executor plan), `registry.py` (không
  đổi API), `__init__.py:29-34` (đăng ký template)
- Delete (sau khi fixture khớp): `apps/api/src/studies/{intraday_liquidity,
  entry_condition_review,volume_at_price,earnings_dislocation}.py`,
  `reads_daily.py`, `reads_fundamental.py` (nếu không còn importer — kiểm
  `stocks/signals/fundamentals.py` có import không; có → giữ)
- Modify: `apps/api/src/agent/tools/studies.py:456-511` (`run_study` gọi
  executor mới; `study_parameters` giữ luật tham số đồng thuận), `:162-200`
- Tests: `tests/test_agent_study_tools.py`, `tests/test_agent_signal_desk.py`
  (11 test cũ phải xanh), `tests/studies/test_templates_regression.py` (mới)

## Implementation Steps
1. Chụp fixture 4 Study trên store thật (`as_of` 2026-08-27 hoặc phiên mới
   nhất), ghi lệnh vào report phase.
2. `contracts.py`: `Step`, `StudyDefinition` mới; `registry` chấp nhận cả hai
   trong thời gian port (cờ `legacy`).
3. Executor plan trong `runner.py`; test với template giả 2 bước.
4. Port từng template; chạy regression; sai số → sửa code compute, không sửa
   fixture.
5. `earnings_dislocation`: chạy thật; nếu refuse vì thiếu VNINDEX/kỳ → ghi
   đúng mã refusal (không phải lỗi), xác minh mâu thuẫn scout vs roadmap S0.
6. Xoá file Study cũ + `legacy`; `test_agent_signal_desk` xanh.
7. `list_studies` thêm `archetype`; `run_study` headline resolve.

## Success Criteria
- [ ] 4 template frames khớp fixture pre-port.
- [ ] Không còn đường render nào ngoài composer (grep `_presentation` cũ = 0).
- [ ] Template code không có literal lọt validator.
- [ ] `test_agent_signal_desk` 11 + regression mới xanh.

## Risk Assessment
- Study cũ có phép tính đặc thù (Yang-Zhang, bucket ATO/ATC) khó viết bằng
  pandas ngắn → cho phép ComputeStep gọi **hàm thuần đã có** trong
  `stocks/signals/*` qua namespace `lib` được whitelist trong sandbox template
  (không mở cho model) — ghi rõ là đặc quyền template, không phải của
  `compute` tool.
- `reads_fundamental.py` còn importer → giữ, không ép xoá.

## Outcome — 2026-08-30

Done. Bốn Study thành template trên đúng đường ống của compiler; mọi frame còn
sống khớp fixture pre-port ở 1e-9 trên store thật. Chi tiết, ba quyết định đảo
một câu của plan (bước thứ ba `ReadStep` · frame `tiles` bỏ · gate +20% bất khả)
và hai bug tìm ra khi port: `plans/reports/phase-07-260830-studies-as-templates.md`.

- [x] 4 template frames khớp fixture pre-port
- [x] Không còn đường render nào ngoài composer
- [x] Template code không có literal lọt validator — **kiểm lúc import**
- [x] `test_agent_signal_desk` 11 + regression mới xanh — `make test` 2123 passed
