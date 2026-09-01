---
phase: 1
title: "Release corpus và hợp đồng dimension"
status: done
priority: P1
dependencies: []
---

# Phase 1: Release corpus và hợp đồng dimension

## Context

- `docs/roadmap.md` §10 Phase 1 checklist (case family, elicitation, material-claim)
- `apps/api/golden/web_first.json` — corpus 20 case hiện có, 4 family
- `apps/api/golden/README.md` §Anti-repeat contract

## Requirements

- `golden/release.json`, schema `golden.corpus@1`, đủ mười một family:
  bốn job §1 (`thesis_check`, `event_memo`, `fact_verification`, `source_conflict`),
  cộng `fact_lookup`, `weekly_movement`, `outlook`, `missing_data`,
  `recommendation`, `elicitation_quality`, `material_claim_accuracy`.
- Mỗi case đóng băng: `question`, `family`, `as_of` (nullable), `expect`,
  `traps[]`, `why_a_fluent_answer_fails`; **không** đóng băng trajectory,
  **không** transcript mẫu.
- `material_claim_accuracy` có `ground_truth.values[]` — mỗi value là
  `{key, value, unit, tolerance, source_url, as_of}`. Giá trị **để trống ở
  commit này** và được điền từ record run của phase 6; một case ground-truth
  rỗng bị grader trả `None`, không bao giờ trả pass.
- `elicitation_quality` khai `must_ask` / `must_not_ask` là **thuộc tính**
  (discoverable hay không, có rẽ nhánh kết luận hay không), không phải câu chữ.
- Corpus khai `markers` dùng chung: từ vựng nhận diện refusal, nhãn một nguồn,
  nhãn giả định. Marker là dữ liệu của corpus, không phải hằng số của grader.
- Corpus khai `dimensions`: tên, `hard|reported`, một câu nói dimension đo gì.
- `web_first.json` giữ nguyên byte — đường đo cũ không được gãy.

## Steps

1. Viết `release.json` với `corpus_id: "release-v1"`, `families`, `markers`,
   `dimensions`, `cases`.
2. Mỗi family ≥ 3 case; tổng 36–40 case; mỗi case một `trap` cụ thể.
3. Cases pin `as_of` **trong quá khứ** cho family cần temporal (fact_lookup,
   fact_verification, event_memo) để `temporal_validity` có thể fail thật.
4. Test: corpus load được, id duy nhất, mọi family có case, mọi `expect` key
   nằm trong tập đã khai, mọi marker được ít nhất một case dùng.

## Validation

```bash
pytest -q tests/golden/test_release_corpus.py
```

## Risk

Corpus quá lớn thì một trial vượt envelope. Giới hạn 40 case và ceiling bắt buộc.

## Rollback

Xoá `release.json`; `web_first.json` và ba make entry cũ không đổi.
