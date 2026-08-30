---
phase: 9
title: "Golden signal_desk gate — S1 Current"
status: blocked
priority: P1
effort: "16h"
dependencies: [4, 6, 7, 8]
---

# Phase 9: Golden `signal_desk` gate — S1 Current

## Overview
Đo scale, không đo danh sách: 50 câu hỏi random do **người ngoài team** viết,
dev không thấy trước, chạy mode `signal_desk`, chấm bằng grader deterministic.
Đây là bằng chứng tốt nghiệp S1 **và** là phần C4 ghi "chưa có: có desk? frames
không lọt?". Câu fail → vào set; không thêm Study.

## Requirements
- Functional:
  - Corpus `golden/signal_desk.json`: 50 case `{id, question, family ∈
    {single, compare, screen, timeline, decompose, off_store}, expect: {board:
    true, min_kpi: 3, archetype?: …, refusal?: code}}`. Quy trình thu: form
    (Google Form/issue template) tới ≥ 3 người không trong repo; dev chỉ thấy
    sau khi đóng form; hash corpus ghi vào artifact.
  - `run.py` nhận `--mode signal_desk`, ghi vào artifact per case: spec v2,
    `lint`, danh sách frame (không số), transcript đã có, `autoComposed`,
    chi phí, latency, `PROMPT_VERSION`, `DomainPack.identity` (đóng mục C4).
  - Grader mới (`grade.py`), mỗi cái một hàm, đọc artifact:
    - `board_present` — mode signal_desk → 100% có composition (kể cả auto).
    - `refs_resolve` — 100% KPI/caption ref trỏ ô tồn tại; giá trị lưu ==
      giá trị frame (re-resolve).
    - `frames_absent` — không giá trị nào của frame xuất hiện trong message
      gửi model (≥ 3 chữ số nghĩa; chuỗi chính xác).
    - `compute_literal_free` — mọi `compute` call trong trace không có
      violation.
    - `evidence_on_page` — mọi evidence frame: 100% row matched.
    - `visual_ratio`, `narrative_chars`, `kpi_count`, `widget_variety`,
      `auto_composed_rate` — **đếm, chưa gate**, ngưỡng đặt sau phân bố.
    - `replay_identical` — render lại artifact bằng composer từ frames đã lưu
      → spec byte-identical.
    - `cost_micro_usd`, `latency_p50`, `external_calls`.
  - Gate S1: `board_present` = 100% · `refs_resolve` = 100% · `frames_absent`
    = 100% · `compute_literal_free` = 100% · `evidence_on_page` = 100% ·
    `replay_identical` = 100% · pass tổng ≥ 90% (case pass = mọi grader gate
    pass + expect khớp) · cost p50 ≤ 84.362 µUSD.
  - Sau lượt 1: đọc phân bố `visual_ratio`/`narrative_chars`/`kpi_count`,
    **đặt ngưỡng** vào `lint.py` (phase 05) và bật hai grader đó thành gate ở
    lượt 2 — quy trình ghi trong `golden/README.md`.
  - Roadmap: S1 → `Current` với bảng gate đo; C4 checklist hai mục `[x]`.
- Non-functional: `make golden-run MODE=signal_desk CEILING_USD=…`; artifact
  không chứa số frame; hai lượt ≤ ngân sách lane 30 Turn.

## Architecture
Tái dùng `ReplayLane` (tape web) và `read_case`; thêm reader artifact
composition qua `frames_buffer`/DB như `run.py` đã đọc `agent_message.content`.

## Related Code Files
- Create: `apps/api/golden/signal_desk.json`, `golden/graders_signal_desk.py`
  (hoặc mở rộng `grade.py:28-33` `GRADERS`), `golden/artifacts/signal-desk-*/`
- Modify: `apps/api/golden/run.py` (mode, artifact fields, pack identity),
  `golden/grade.py`, `golden/README.md`, `apps/api/Makefile`
- Modify: `apps/api/src/studies/lint.py` (ngưỡng đặt lại — chỉ hằng)
- Modify: `docs/roadmap.md` §4 S1 → Current, §3 C4 hai mục; `CLAUDE.md` đoạn
  Roadmap tóm tắt
- Tests: `apps/api/tests/golden/test_graders_signal_desk.py` (fixture
  artifact tổng hợp: pass/fail từng grader)

## Implementation Steps
1. Mở form thu câu; tiêu chí: câu phân tích chứng khoán VN bất kỳ, không ràng
   buộc dạng; ≥ 60 câu thu, chọn 50 ngẫu nhiên có seed ghi lại.
2. `run.py` mode + artifact fields; chạy 3 case thử.
3. Grader + test fixture.
4. Lượt 1 (n=50): ghi report `reports/phase-09-golden-signal-desk-round-1.md`
   — pass rate, phân bố, top lỗi validator/lint, danh sách fail.
5. Sửa theo lỗi **hệ thống** (grammar/shape/prompt), không theo từng câu; đặt
   ngưỡng lint từ phân bố.
6. Lượt 2: pass ≥ 90% → roadmap S1 Current; < 90% → lượt 3 sau sửa hệ
   thống, tối đa 3 lượt trong phase; vẫn < 90% → report và dừng, không hạ bar.
7. Cập nhật roadmap/CLAUDE.md; commit artifact bằng `git add -f`.

## Success Criteria
- [ ] Corpus 50 câu, hash ghi, dev không thấy trước (ghi quy trình).
- [ ] Sáu grader bất biến 100%; pass tổng ≥ 90%; cost p50 ≤ 84.362 µUSD.
- [ ] Ngưỡng lint đặt từ phân bố, ghi report.
- [ ] Roadmap S1 `Current`; C4 hai mục đóng; Track S2/S3 không đụng.

## Risk Assessment
- `off_store` family kéo pass rate xuống vì web tape thiếu → tape thu ở lượt 1
  và replay ở lượt 2 (như C1); không loại family.
- Pass rate cao vì câu quá dễ → family phân bố bắt buộc ≥ 6 câu/family; câu
  compare ≥ 12.
- Không ai ngoài team → **hỏi user** (câu 3 plan); không tự viết.

## Outcome — 2026-08-30

**Harness xong, corpus chưa mở. Phase dừng ở đúng chỗ plan nói dừng.**

Bước 2 và 3 hoàn tất; bước 1 và 4–7 chờ 50 câu của người ngoài team. Chi tiết:
`plans/reports/phase-09-260830-golden-signal-desk-harness.md`.

- [x] `golden/graders_signal_desk.py` — 18 grader (6 bất biến · 4 kỳ vọng ·
      8 phép đo), `grade_case` thuần, không branch theo case id
- [x] `run.py --mode signal_desk` — Turn chạy đúng mode production, artifact
      mang spec v2, frames, `frame_metadata`, `ref_proof`, `replay_proof`,
      `model_visible_text`, `arguments`, `PROMPT_VERSION` + `DomainPack.identity`
- [x] `grade.py` dispatch theo `run.mode` + cổng S1 (6 bất biến 100% · case
      ≥ 90% · cost p50 ≤ 84.362 µUSD)
- [x] `golden/signal_desk_corpus.py` — rút mẫu theo seed, sàn family
      (`compare` ≥ 12, năm family còn lại ≥ 6), validate, digest submissions
- [x] `run.py` ghi `corpus_sha256` + `corpus_selection` vào artifact — plan đòi
      "hash corpus ghi vào artifact", trước đó artifact chỉ có `corpus_id`
- [x] `Makefile`: `golden-run MODE=`, `golden-corpus-select`,
      `golden-corpus-validate`; README ghi quy trình thu + mẫu câu form
- [x] 69 test `tests/golden/` xanh (52 có sẵn + 17 mới cho corpus, sau code review)
- [ ] Corpus 50 câu — **chờ user**: cần ≥ 60 câu từ ≥ 3 người ngoài repo
- [ ] Lượt 1 / lượt 2, ngưỡng lint từ phân bố, roadmap S1 → `Current` — tất cả
      nằm sau corpus

**Một sai lệch so với plan, có lý do.** Plan ghi non-functional "artifact không
chứa số frame"; artifact **có** chứa `composition.frames`. Ba grader bất biến
không tồn tại được nếu thiếu nó: `frames_absent` phải có literal của frame mới
tìm được nó trong text model đọc, `refs_resolve` phải tra lại ô, và
`replay_identical` phải dựng lại board từ chính frames đó. Bỏ frames đi thì cả
ba chỉ còn so hash do `run.py` tự tính — tức grader tự chấm chính mình. Luật
"frames không vào transcript" vẫn nguyên: nó nói về **message gửi model**, và
đó chính là thứ `frames_absent` đo. Hệ quả cần biết trước khi commit artifact:
file artifact mang số thị trường thật, `git add -f` là đưa chúng vào repo.
