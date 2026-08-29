---
phase: 6
title: "Nghiệm thu bằng số và đóng phase"
status: completed
priority: P1
effort: "4h"
dependencies: [3, 5]
---

# Phase 6: Nghiệm thu bằng số và đóng phase

## Overview

Gate của C5 là *"Đổi pack không sửa `loop.py`; input token/Turn giảm mà Golden Set
không giảm"* (`docs/roadmap.md:237-238`). Vế đầu đã được phase 02 và 05 chứng minh
bằng test. Phase này lo vế sau, và lo một việc khó hơn: **nói đúng số nào đo được
và số nào không**.

Acceptance signal của chính OpenCode cho bài học này là *"giảm input tokens mà
Golden Question Set không giảm grounding/completeness; **không dựa vào subjective
prompt review**"* (`docs/opencode/opencode-lessons-for-stock-massive.md:83-84`).
Nên phase này không kết thúc bằng một đoạn văn khen prompt gọn hơn.

## Requirements

- Functional: một phép đo **deterministic, miễn phí** cho phần token của prompt —
  đây là gate.
- Functional: một phép đo **end-to-end tốn tiền** trên corpus C1 — đây là tín
  hiệu, kèm khoảng.
- Functional: `docs/roadmap.md` §3 C5 đổi nhãn theo bằng chứng; `CLAUDE.md`
  §Quy ước mang cấu trúc prompt mới.
- Non-functional: **không sửa** `apps/api/golden/*` và `Makefile` — vùng C1
  (`plan.md` §"Luật phối hợp hai worktree" điểm 5).
- Non-functional: không đặt ngưỡng trước khi nhìn phân phối; luật này C1 đã học
  bằng hai lần bộ eval chết.

## Architecture

### Hai phép đo, và vì sao phải là hai

**Phép đo 1 — deterministic, là gate.** Token của core prompt và của body, bằng
`messages.estimate_tokens` (`messages.py:760`) — cùng hàm mà budget, admission và
thang trim đọc. Chạy trong `make test`, không mạng, không tiền, chạy lại cho kết
quả **giống hệt**. Gốc để trừ: **5.498 token**, đo ở phase 01.

Đây là gate vì nó đo đúng thứ C5 thay đổi và **chỉ** thứ đó.

**Phép đo 2 — end-to-end, là tín hiệu.** `cost.input_tokens` mỗi case trong
artifact `apps/api/golden/` (`golden/run.py:238-249` gom từ `llm_call_usage`), so
**trước/sau trên cùng nhánh**, cộng toàn bộ finding của `golden/grade.py` để bắt
hồi quy chất lượng.

**Vì sao không đủ nếu chỉ có phép đo 2:** `input_tokens` là tổng của mọi call
trong Turn và gồm cả history lẫn tool result. C1 đang đồng thời làm số đó **tăng**
(nhiều truy vấn hơn, nhiều trang đọc hơn — `260829-1349/plan.md` §"Nút thắt
thật"). Nếu C5 so với artifact do nhánh C1 sinh, dấu của delta nói về C1 nhiều hơn
về C5. Nên:

> **So trước/sau trên cùng nhánh, cùng corpus, cùng ngày.** Không so với artifact
> baseline của C1 — hai bên khác quần thể và khác cả tập thay đổi.

### Cái corpus này đo được và cái nó không đo được

`web_first.json`: 20 case, 4 family — `fact_as_of`, `multi_source_synthesis`,
`conflicting_or_missing`, `adversarial`. **Không family nào hỏi store.**

| Câu hỏi | Corpus trả lời được? |
|---|---|
| Turn không chạm domain có rẻ đi không | **Có** — gần như toàn bộ 20 case thuộc loại này, đúng loại C5 tiết kiệm |
| Chất lượng web-first có tụt không | **Có** — grader C1 chấm thẳng |
| Deadlock bootstrap (model thôi gọi tool store) | **Yếu** — corpus không có câu nào lẽ ra phải gọi store |
| Chất lượng lượt chạm store có tụt không | **Không** |

Hai chỗ "không" và "yếu" được bù bằng, theo thứ tự ưu tiên: transcript test của
phase 05 (kiểm cơ chế, deterministic); một phép chạy tay **ba câu store-first**
qua lane thật, ghi nguyên văn câu trả lời vào report (kiểm chất lượng, không phải
gate); và một **yêu cầu gửi C1/C4** thêm family store-first vào corpus — đó là
Câu hỏi chưa giải quyết #1 của `plan.md`, không phải một commit của C5.

Ba câu chạy tay không phải là gate và plan nói thẳng vậy. Chúng là thứ ngăn C5
đóng lại mà chưa ai từng nhìn một câu trả lời domain sau khi tách prompt.

### Nếu artifact C1 chưa có

`apps/api/golden/artifacts/` hiện **rỗng** (chỉ `.gitkeep`) và C1 phase 02 chưa
chạy lượt nào. Luật đã quyết trước, ở `plan.md` §"Luật phối hợp hai worktree"
điểm 4: **gate ghi "chờ đo", code vẫn merge được**, vì phép đo 1 và toàn bộ
contract/transcript test không phụ thuộc artifact.

Trạng thái phase khi đó là `completed` cho code và **một dòng nợ ghi rõ trong
`docs/roadmap.md`**: C5 giữ nhãn **Target** cho tới khi có số end-to-end. Không
đánh **Current** bằng phép đo 1 một mình — nhãn Current đòi *"bằng chứng đo được"*
(`docs/roadmap.md:32-45`), và một phép đo trên prompt tĩnh chưa nói gì về câu trả
lời.

### Chi phí của phép đo 2

Một Turn đo được **$0,021**; 20 case ≈ **$0,42–0,60** một lượt, và phép so
trước/sau cần **hai** lượt ≈ **$1,2**. `run.py` đòi một trần chi tiêu và dừng khi
chạm (`golden/run.py:366,403-407`), nên trần đưa vào phải ≥ chi phí dự kiến cộng
biên — đưa thiếu thì lượt chạy dừng giữa chừng và luật "không chấm lượt xanh một
nửa" khoá kết quả.

Trần per-user cũng chặn: `turn_starts_per_day = 20` (`core/llm/config.py:218-222`)
**đúng bằng** số case. C1 phase 02 phải giải nó (identity riêng cho runner);
nếu C1 chưa giải xong thì phép đo 2 **chưa chạy được** — cùng nhánh với "chờ đo",
và là lý do thứ hai để nó không phải gate.

## Related Code Files

- Modify: `apps/api/tests/test_agent_prompt.py` — phép đo 1 thành test có ngưỡng
  (thêm ở cuối file)
- Modify: `docs/roadmap.md` — §3 C5: nhãn, cột "Sau", gate đã đạt/còn nợ
- Modify: `CLAUDE.md` — §Quy ước: prompt hai tầng, ba trigger, `PROMPT_VERSION`
  mới, pack `vn-equity`
- Read-only: `apps/api/golden/run.py`, `apps/api/golden/grade.py`,
  `apps/api/golden/web_first.json`, `apps/api/Makefile` — **chạy, không sửa**

## Implementation Steps

1. Viết phép đo 1 thành test: core ≤ 4.900 token **và** core + body ≥ 5.400 (cận
   dưới bắt việc prose bị mất trong lúc tách, không chỉ bắt việc nó ngắn đi). Hai
   cận đọc thẳng từ số phase 01, và comment tại chỗ ghi ngày đo.
2. Chạy `make golden-run` với trần chi tiêu **trên nhánh C5 đã merge phase 05**,
   rồi `git stash` phần C5 và chạy lại — hoặc chạy lượt "trước" từ commit cha.
   Ghi cả hai artifact.
3. `make golden-grade` cho cả hai; so từng finding. Bất kỳ finding nào xấu đi là
   một mục phải giải thích, không phải một con số để trung bình đi.
4. Chạy tay ba câu store-first qua lane thật (một câu một figure, một câu cần
   `run_study`, một câu hỏi field bị refuse), dán nguyên văn câu trả lời vào
   report. Đọc kỹ ba thứ: có nêu ngày của figure không, có tường thuật refusal
   không, có ra chỉ thị hành động không.
5. Cập nhật `docs/roadmap.md` §3 C5: cột "Sau", nhãn, và **nợ nào còn**.
6. Cập nhật `CLAUDE.md` §Quy ước: prompt hai tầng và ba trigger, `PROMPT_VERSION`
   mới, tên pack. Giữ nguyên mọi luật khác của mục đó.
7. Năm cổng.

## Success Criteria

- [x] **Gate** — test phép đo 1 xanh, ngưỡng dời theo gốc thật (6.097 chứ không
      5.498): core ≤ **5.500** (đo 5.345) và core + body ≥ **6.000** (đo 6.134)
- [x] **Gate** — mọi contract test của phase 02–03 và transcript test của phase 05
      xanh
- [x] **Gate** — không phase nào để lại một test luôn-pass: mỗi guard mới có một
      phép chứng minh nó đỏ được (đã liệt kê ở từng phase)
- [x] **Tín hiệu** — đo được mà không chạy thêm lượt nào: artifact C1
      `web-first-v1-final.json` mang `PROMPT_VERSION 3.0.0`, tức C5 đã sống
      trong lượt đó. Net **−438 token/call (7,0%)**; bản đang ship −376 (6,0%).
      Phép này **không** so hai artifact nên tránh được đúng cái confound mà
      §Architecture của phase này cảnh báo
- [~] **Tín hiệu** — grader: 3 finding mới đỏ, 1 xanh lại; mỗi cái đã giải
      thích chứ không trung bình đi, và kết luận trung thực là **n=20 không phân
      xử được** giữa C5 và C1 phase 05-08. Ghi đầy đủ ở `docs/roadmap.md` §C5
- [~] Ba câu store-first chạy tay: **bỏ qua có chủ ý**, user chốt 2026-08-29.
      Bù một phần ngoài dự kiến: 11/20 case của corpus **có** chạm tool domain,
      nên lượt chạm domain đã được grader chấm — chỉ là tình cờ, không theo kỳ
      vọng. Family cố ý giao C4
- [x] `docs/roadmap.md` §3 C5 mang nhãn đúng bằng chứng — **Current** chỉ khi có
      số end-to-end, ngược lại giữ **Target** kèm dòng nợ
- [x] `CLAUDE.md` §Quy ước mô tả prompt hai tầng và ba trigger
- [x] `git diff --stat` không có file nào dưới `apps/api/golden/` và không có
      `Makefile`
- [x] Năm cổng xanh

## Risk Assessment

**Rủi ro chính: gán công cho C5 một phần giảm token thật ra là của C1 — hoặc
ngược lại, kết luận C5 vô ích vì C1 làm token tăng.**
Tín hiệu: hai lượt so nhau khác nhau nhiều hơn một tập thay đổi.
Phản ứng đã quyết trước: so **trước/sau trên cùng nhánh, cùng ngày, cùng corpus**;
không so với artifact do nhánh khác sinh. Nếu buộc phải so chéo, ghi rõ nó là
tín hiệu bẩn và không dùng nó để đánh gate.

**Rủi ro: corpus không đo được thứ C5 có thể làm hỏng.**
Đây là **rủi ro đã biết và không giải được trong phạm vi C5** (§Architecture).
Phản ứng: transcript test + ba câu chạy tay + một nợ ghi rõ. Không giả vờ corpus
web-first nói về lượt chạm store.

**Rủi ro: cache search làm lượt thứ hai không độc lập.**
`WebLane` cache search 30 phút, URL 24h (`core/web_lane.py:19-22`) — lượt "sau"
chạy trong cùng ngày đọc lại cache của lượt "trước".
Tín hiệu: `read_depth` và `distinct_domains` giống hệt tới mức đáng ngờ.
Phản ứng: với C5 điều này **có lợi** — nội dung web giống nhau thì phần khác biệt
còn lại chính là prompt, tức đúng biến C5 đổi. Ghi ra điều đó trong report thay vì
coi là nhiễu.

**Rủi ro: `turn_starts_per_day = 20` làm lượt chạy hỏng giữa chừng.**
Tín hiệu: case cuối trả `incomplete` vì admission.
Phản ứng: đây là việc C1 phase 02 phải giải; nếu chưa, phép đo 2 ghi "chờ đo".
**Không** nới trần production để chạy được một phép đo.

**Rủi ro: đánh nhãn Current bằng một phép đo tĩnh.**
Tín hiệu: roadmap nói Current mà không có số end-to-end nào.
Phản ứng: luật nhãn ở `docs/roadmap.md:32-45` — Current đòi owner **và** test
**và** bằng chứng đo được. Giữ Target kèm nợ là câu trả lời trung thực.

## Rollback

Phase này chỉ sửa test và tài liệu; `git checkout` là đủ và không chạm hành vi
runtime. Artifact golden nằm trong `apps/api/golden/artifacts/` (gitignore trừ
baseline được chốt) nên không có gì để hoàn nguyên trong repo.

Nếu phép đo cho kết quả xấu — token không giảm, hoặc grader tụt — đường lui
**không** phải sửa gate. Nó là: giữ phase 02–03 (declaration + vocabulary, vô hại
với hành vi) và revert **05 rồi 04** theo đúng thứ tự đã ghi. Kết quả là một pack
đã khai đủ, prompt trở lại một tầng, và C8 vẫn có chỗ bám.
