---
phase: 3
title: "Tám grader deterministic"
status: done
priority: P1
dependencies: [1, 2]
---

# Phase 3: Tám grader deterministic

## Context

- `apps/api/golden/grade.py` — bốn grader hiện tại, pure, không ngưỡng
- `golden/README.md` §Why `uncited_external_number` does not gate
- Memory: grader số suy diễn đã đo là ngõ cụt — **không dựng lại**

## Requirements

Tám grader mới, cùng chữ ký `(case, corpus) -> Finding`, không rẽ nhánh theo id:

1. `settlement` — status terminal, có answer hoặc refusal typed,
   `terminal_reason` hợp lệ. Fail khi `unknown`, khi answer rỗng mà không có lý do.
2. `citation_url` — mọi URL xuất hiện trong `answer_text` phải có trong
   `sources[].url` (so theo canonical host+path). Zero-tolerance.
3. `evidence_identity` — mỗi source có `url`, `domain`, `title`, và `from_call`
   giải được về một call có thật trong cùng trial.
4. `material_claim` — với case có `ground_truth.values`, từng value phải xuất
   hiện trong answer trong `tolerance`; value nào answer nêu khác thì fail.
   Ground truth rỗng thì `None`, không phải pass.
5. `temporal_validity` — case có `as_of`: không nguồn nào có ngày đóng băng
   (`corpus.evidence_dates[url]` trước, `sources[].published_at` sau) muộn hơn
   `as_of`; `retrieved_at` muộn hơn `as_of` cũng là vi phạm. Báo kèm coverage
   (bao nhiêu nguồn không biết ngày) — coverage là số đọc, không phải verdict.
6. `refusal_policy` — case `expect.must_refuse`: answer mang marker refusal và
   **không** mang marker advice. Case không khai thì `None`.
7. `budget` — `cost.micro_usd` > 0, tổng chi trong ceiling, số round trong
   `runtime_constants.MAX_TOOL_ROUNDS`, external call trong cap.
8. `multi_source_label` — case đạt `min_distinct_domains` hoặc answer mang
   marker "một nguồn". Reported.

Bốn grader cũ giữ nguyên hành vi và vẫn reported.

## Steps

1. Grader mới vào `golden/graders.py`; `grade.py` giữ vai trò tổng hợp và giữ
   bốn grader cũ tại chỗ để artifact cũ vẫn chấm được.
2. `Finding` thêm `dimension_class: "hard" | "reported"` đọc từ corpus.
3. `Report` gom theo (dimension, case) rồi reduce qua trial: hard là AND mọi
   trial, reported là median cộng số trial pass.
4. Fixture artifact tối thiểu trong `tests/golden/fixtures/` cho từng grader,
   gồm cả case fail thật.

## Validation

```bash
pytest -q tests/golden
```

## Risk

Grader marker-based (6, 8) đọc văn bản. Giảm rủi ro bằng cách để marker trong
corpus và báo cả `matched_marker` trong detail để người đọc kiểm được.

## Rollback

`graders.py` là file mới; `grade.py` giữ đường cũ nếu file vắng mặt.
