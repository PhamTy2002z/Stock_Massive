---
phase: 2
title: "Multi-trial runner, provenance, retrieved_at"
status: done
priority: P1
dependencies: [1]
---

# Phase 2: Multi-trial runner, provenance, retrieved_at

## Context

- `apps/api/golden/run.py` — solver hiện tại, một trial, schema `golden.artifact@1`
- Inspect AI: epochs = multi-trial mặc định, log ghi spec đọc lại được
- Preflight §2: artifact mới nhất **trước teardown**, không dùng làm baseline

## Requirements

- `--trials N` (mặc định 1). Trial 1 **record** tape, trial 2..N **replay**
  cùng tape trong cùng một lần chạy, nên chỉ model biến thiên giữa các trial.
- Schema lên `golden.artifact@2`. Mỗi entry trong `cases[]` mang thêm `trial`
  (1-based). `run.trials` ghi số trial đã chạy.
- `sources[].retrieved_at` gắn từ tape (`kind`,`key`) sang `fetched_at`, khớp
  qua `from_call` sang `arguments.url` / `arguments.query`. Không có thì `None`.
- Provenance `run.provenance`: `git_sha`, `PROMPT_VERSION`, `tool_catalog`
  (tên đã resolve + sha), `model`, `judge_model` (do phase 4 điền),
  `runtime_constants`, `corpus_sha256`, `tape_sha256`, `trials`, `schema`.
- Ceiling áp cho **toàn bộ** lần chạy, không phải mỗi trial.
- `grade.py` từ chối `@1` như hiện tại (`unusable`) — artifact tiền-teardown
  không được lẫn vào baseline mới.

## Steps

1. `run_corpus(..., trials=N)`: vòng ngoài trial, vòng trong case; sau trial 1
   bật replay trên lane.
2. `read_case(...)` nhận `trial`, `retrieved_at_by_key`.
3. `runtime_constants` thêm tool catalog qua `resolve_toolset(CHAT_TOOLSETS)`.
4. `corpus_digest` tái dùng cho tape sha.
5. Test trên fake store/lane: hai trial cùng case cho hai entry, trial 2 không
   ghi thêm tape, ceiling tính cộng dồn, `retrieved_at` khớp đúng nguồn.

## Validation

```bash
pytest -q tests/golden/test_run.py tests/golden/test_replay_lane.py
```

## Risk

Trial 2 miss tape vì model tìm query khác thì run thành `incomplete`. Đó là
hành vi đúng và đã có sẵn; report phải nói rõ để người đọc không tưởng là bug.

## Rollback

`--trials` mặc định 1 nên đường cũ giữ nguyên hành vi; revert file là đủ.
