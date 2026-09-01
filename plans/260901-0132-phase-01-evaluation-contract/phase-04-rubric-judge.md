---
phase: 4
title: "Rubric judge pass"
status: done
priority: P1
dependencies: [2]
---

# Phase 4: Rubric judge pass

## Context

- `docs/roadmap.md` §3 rubric, §10 P1 "judge không chấm số backend kiểm được"
- OpenCode pattern: hidden specialist cho tác vụ phụ có contract nhỏ

## Requirements

- `golden/judge.py`: đọc một artifact, gọi model một lượt cho mỗi (case, trial),
  ghi `cases[].judge` **vào chính artifact đó**, để `grade.py` vẫn pure.
- Context sạch: judge chỉ thấy `question`, `answer_text`, `family`, mô tả
  family. **Không** thấy evidence, không thấy điểm grader, không thấy tool call.
- Năm trục §3, thang 1–5, mỗi trục kèm một câu lý do: `synthesis`,
  `structure_for_intent`, `counterargument`, `uncertainty`, `decision_utility`.
- Prompt cấm tường minh: không chấm đúng/sai của số, không chấm citation.
- Output JSON strict. Parse fail hoặc provider lỗi thì `judge.status =
  "unavailable"` kèm lý do; không bao giờ thành điểm ngầm, không làm hỏng run.
- `--ceiling-usd` riêng cho judge pass; ghi `run.provenance.judge_model`.

## Steps

1. Dựng prompt, parser, và một lần retry cho JSON hỏng.
2. Gọi qua gateway sẵn có (cùng đường `src.core.llm` mà runner dùng).
3. `grade.py` đọc `case["judge"]` nếu có, phát findings reported cho từng trục.
4. Test với model giả: JSON đúng, JSON hỏng, provider ném lỗi.

## Validation

```bash
pytest -q tests/golden/test_judge.py
```

## Risk

Judge tốn thêm một lượt model mỗi (case, trial). Ceiling riêng cộng `--no-judge`.

## Rollback

Bỏ cờ judge; gate không phụ thuộc điểm judge nên verdict không đổi.
