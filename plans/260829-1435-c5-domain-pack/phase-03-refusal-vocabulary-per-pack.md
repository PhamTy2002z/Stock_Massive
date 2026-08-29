---
phase: 3
title: "Refusal vocabulary theo pack, hai chiều có guard"
status: done
priority: P2
effort: "3h"
dependencies: [2]
---

# Phase 3: Refusal vocabulary theo pack, hai chiều có guard

## Overview

Checklist C5 viết: *"Refusal vocabulary theo pack: `alpha/reasons.py` ↔
`apps/web/src/lib/signal-issues.ts`"* (`docs/roadmap.md:233`). Đo lại thì hai bên
**đang khớp**, nhưng chỉ **một** bên có test giữ — và bên không có test là bên
Python.

Phase này gắn vocabulary vào pack và dựng lại guard đã chết, mà **không đổi một
mã refusal nào** và **không sửa file nào trong `apps/web/`**.

## Requirements

- Functional: `DomainPack.refusal_vocabulary` mang đúng tập mã pack dùng, và một
  test khẳng định nó khớp enum đóng ở `stocks/signals/issues.py`.
- Functional: guard Python sống lại — mọi mã enum có một câu ở `alpha/reasons.py`.
- Functional: docstring `alpha/reasons.py:13-14` trỏ về guard **đang sống**, không
  trỏ về file đã bị xoá.
- Non-functional: **không thêm, không bớt, không sửa** một mã `SignalIssue` nào.
- Non-functional: **không sửa `apps/web/`** — guard bên đó đã sống và mạnh hơn.
- Non-functional: **không đụng `src/stocks/*`** (vùng freeze).

## Architecture

### Đo trước: ai đang giữ ai

```
stocks/signals/issues.py   SignalIssue          42 member   ← tập đóng, freeze
        │
        ├──▶ alpha/reasons.py      SIGNAL_ISSUE_SENTENCES   42/42   guard: KHÔNG CÒN
        └──▶ apps/web/.../signal-issues.ts                  42/42   guard: signal-issues.test.ts
```

`apps/web/src/lib/signal-issues.test.ts:20-36` **đọc thẳng file Python** qua
đường `../api/src/stocks/signals/issues.py`, rút mọi `NAME = "value"` bằng regex,
rồi khẳng định hai chiều: mọi mã backend có câu tiếng Việt, và không câu nào nói
về một mã backend không thể phát ra. Đó là guard tốt, đang chạy trong
`pnpm test`, và phase này **không đụng vào**.

Phía Python thì `alpha/reasons.py:13-14` viết *"A code with no sentence here
fails `tests/test_envelope.py`"* — `ls tests` cho thấy file đó không còn (rip-out
2026-08-25). Guard đã chết **một tuần** mà docstring vẫn khẳng định nó sống. Đúng
loại sai lầm mà `plan.md` §"Mười dữ kiện đo lại" tồn tại để bắt.

Có **hai** test chạm gần: `tests/test_signal_earnings.py:570-577` chỉ kiểm ba mã
`earnings.*`, và `tests/studies/test_volume_at_price.py:462-464` mang cái tên
`test_every_signal_issue_has_a_sentence_for_the_model` nhưng sống trong file của
một Study — sai chỗ, và một người xoá Study đó sẽ xoá luôn guard chung.

### Vocabulary "theo pack" nghĩa là khai, không phải là chuyển nhà

Cám dỗ tự nhiên là chuyển `SIGNAL_ISSUE_SENTENCES` vào `agent/domain/vn_equity.py`
cho "gọn theo pack". **Không làm.** Ba lý do đo được:

1. `alpha/envelope.py:80,656,688` gọi `sentence_for` — chuyển nhà là sửa một
   module ngoài phạm vi C5.
2. Guard web trỏ **đường dẫn tuyệt đối theo cấu trúc thư mục** tới file enum
   Python; đường đó vẫn đúng, nhưng bất kỳ cuộc di chuyển nào cũng kéo theo sửa
   `apps/web/`, thứ plan này khai là không đụng.
3. Enum sống ở `src/stocks/signals/issues.py` — **vùng freeze**.

Nên pack **khai** tập mã nó dùng (`frozenset` các value) và contract test khẳng
định ba tập bằng nhau: pack ↔ enum ↔ câu ở `reasons.py`. Đó chính là "một
declaration, contract test giữ đồng bộ" mà checklist C5 đòi
(`docs/roadmap.md:221`), và nó không di dời một dòng prose nào.

### Guard mới ở đâu

`apps/api/tests/test_agent_domain_pack.py` (file phase 02 tạo) — vì câu hỏi nó
trả lời là *"pack này khai đúng vocabulary của nó chưa"*, không phải *"Study
volume-at-price có chạy không"*. Test cũ ở
`tests/studies/test_volume_at_price.py:462` giữ nguyên hay xoá? **Giữ**, và không
đụng: xoá nó là một thay đổi ở file của phase khác đổi lấy DRY hình thức, còn hai
test cùng khẳng định một sự thật thì cái thừa là cái vô hại nhất trong hai.

## Related Code Files

- Modify: `apps/api/src/agent/domain/vn_equity.py` — điền `refusal_vocabulary`
- Modify: `apps/api/src/alpha/reasons.py` — **chỉ docstring** `:13-14`, trỏ về
  guard đang sống (test của pack + `apps/web/src/lib/signal-issues.test.ts`)
- Modify: `apps/api/tests/test_agent_domain_pack.py` — ba tập bằng nhau
- Read-only: `apps/api/src/stocks/signals/issues.py` (freeze),
  `apps/web/src/lib/signal-issues.ts`, `apps/web/src/lib/signal-issues.test.ts`

## Implementation Steps

1. Đọc `stocks/signals/issues.py` và lấy tập value hiện tại (42 mã, đo
   2026-08-29).
2. Điền `refusal_vocabulary` cho pack `vn-equity`. Khai **bằng enum**
   (`frozenset(issue.value for issue in SignalIssue)`) chứ không chép 42 chuỗi:
   chép là dựng một bản sao thứ ba để đồng bộ, tức thêm việc chính phase này tồn
   tại để bớt.
3. Viết ba assert trong `test_agent_domain_pack.py`:
   - `PACK.refusal_vocabulary == {i.value for i in SignalIssue}`;
   - mọi `SignalIssue` có khoá trong `SIGNAL_ISSUE_SENTENCES` (guard sống lại);
   - mọi câu **không** chứa động từ khuyên (`nên mua|nên bán|khuyến nghị|should
     buy|should sell`) — đúng luật đã ghi ở `reasons.py:16-18` và đã được bên web
     kiểm (`signal-issues.test.ts:70-78`); đây là chỗ duy nhất phase này *thêm*
     một phép kiểm, và nó kiểm một luật đã viết ra chứ không phát minh luật mới.
4. Sửa docstring `reasons.py:13-14`: nêu **hai** guard đang sống và nói rõ tập
   đóng vẫn ở `stocks/signals/issues.py`.
5. Chạy `make test` (api) và `pnpm test` (web) — bên web phải xanh **mà không có
   thay đổi nào**, đó là bằng chứng phase này không chạm nó.

## Success Criteria

- [x] `PACK.refusal_vocabulary` khai bằng enum, không phải bản chép
- [x] Guard Python sống lại: thêm một member enum giả trong test làm test đỏ
      (chứng minh guard thật sự bắt, không phải luôn-pass)
- [x] Docstring `reasons.py` không còn viện dẫn `tests/test_envelope.py`
- [x] `git diff --stat` **không có file nào dưới `apps/web/`** và không có file
      nào dưới `src/stocks/`
- [x] 42 mã trước = 42 mã sau; `git diff src/stocks/signals/issues.py` rỗng
- [x] `make test` xanh; `pnpm test` xanh không cần sửa gì bên web
- [x] Năm cổng xanh

## Risk Assessment

**Rủi ro chính: guard mới luôn-pass.**
Một test so hai tập cùng dựng từ một nguồn là một test không bao giờ đỏ.
Tín hiệu: assert kiểu `set(x) == set(x)`.
Phản ứng đã quyết trước: assert phải bắc cầu giữa **hai nguồn khác nhau** — enum
(`stocks/`) và prose (`alpha/`). Phép chứng minh bắt buộc ở Success Criteria là
làm test đỏ bằng một member giả; không làm được nghĩa là test vô nghĩa.

**Rủi ro: ai đó "gọn hoá" bằng cách chuyển câu prose vào pack.**
Tín hiệu: `alpha/envelope.py` phải sửa import.
Phản ứng: dừng. Ba lý do đã ghi ở §Architecture, và cái thứ ba là vùng freeze.

**Rủi ro: một mã refusal mới được thêm cùng lúc ở nhánh khác.**
C1 không chạm vocabulary này; nhưng Track S thì có thể.
Tín hiệu: `make test` đỏ ở guard mới ngay sau merge.
Phản ứng: đó **đúng là việc của guard** — thêm câu ở `alpha/reasons.py` và
`apps/web/src/lib/signal-issues.ts`, theo đúng luật đã ghi ở `CLAUDE.md`.

## Rollback

`git checkout -- src/agent/domain/vn_equity.py src/alpha/reasons.py
tests/test_agent_domain_pack.py`. Không có dữ liệu, không có schema, không có
file sinh ra. Sau rollback, tập 42 mã và cả hai file prose y nguyên — phase này
không bao giờ ghi vào chúng.
