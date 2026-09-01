---
phase: 5
title: "Một lệnh, gate, Wilson CI"
status: done
priority: P1
dependencies: [3, 4]
---

# Phase 5: Một lệnh, gate, Wilson CI

## Context

- Gate roadmap: "toàn corpus chạy bằng **một lệnh**, artifact in pass/fail theo
  từng dimension; run nửa xanh là `incomplete`"
- promptfoo: ngưỡng và exit code sống ở tầng runner, không trong scorer

## Requirements

- `golden/gate.py`: **nơi duy nhất** có ngưỡng.
  - Hard dimension: 100%, không tuỳ chỉnh, không đọc từ file.
  - Soft dimension: đọc `golden/thresholds.json`; file khởi tạo với mọi giá trị
    `null` kèm trường `why: "no threshold before a distribution"`.
- Wilson score interval 95% cho mọi tỷ lệ pass, mẫu là case × trial.
- `golden/release.py` là một lệnh: run, judge, grade, gate, in bảng và ghi
  `artifacts/<corpus>-<stamp>.json` cùng `<...>-report.json`.
- Exit code: `0` xanh; `1` hard dimension dưới 100% hoặc run không `complete`;
  `2` artifact không chấm được.
- Make entry `golden-release` với `CEILING_USD` bắt buộc, `TRIALS` mặc định 1.

## Steps

1. `wilson(passes, n)` thuần Python, không dependency.
2. Bảng in: dimension · loại · pass/n · tỷ lệ · CI · verdict.
3. Test: gate đỏ khi một hard fail, đỏ khi `incomplete`, xanh khi đủ,
   `2` khi schema sai; Wilson khớp giá trị đã biết.

## Validation

```bash
pytest -q tests/golden/test_gate.py
make golden-release CEILING_USD=0.01 TRIALS=1   # dừng ở ceiling, phải là incomplete
```

## Risk

Một lệnh làm bốn việc dễ thành god-script. Giữ `release.py` mỏng: nó chỉ nối
bốn hàm public, mọi logic nằm ở module sở hữu.

## Rollback

Ba make entry cũ vẫn chạy độc lập.
