---
phase: 3
title: "System Prompt Contract"
status: complete
priority: P1
effort: "1d"
dependencies: [2]
---

# Phase 3: System Prompt Contract

## Overview

Thêm hai khối prose vào tầng ổn định của Contract: chống bịa số, và dạy model gộp
tool call độc lập. Cả hai nằm trong prefix được cache nên chi phí trả một lần.

## Requirements

- Functional: Contract nói thẳng "không bịa số, không chứng minh được thì nói rõ
  vướng gì" — thay vì để validator gánh toàn bộ.
- Functional: Contract dạy model gộp các lời gọi tool độc lập vào một lượt.
- Non-functional: `contract_hash()` đổi; `PROMPT_VERSION` bump. Không được sửa
  prose mà quên bump — `contract_hash` hash chính prose nên nó tự bắt.
- Non-functional: **không** thêm field nào model có thể set để tự khai đã tuân thủ.
- Non-functional: giữ `_assert_no_formatting_hole` — không free-text, không brace.

## Architecture

### G1 — đây là amend một quyết định kiến trúc

`ADR-0015` nói thẳng nó *"refuses to let the Contract be an enforcement
mechanism"*. Thêm khối chống bịa là **sửa quyết định đó**, không phải thêm tính
năng. Phải amend ADR, không lặng lẽ trái.

Luận cứ để amend, từ Hermes: cùng lớp lỗi được xử lý bằng 9 dòng prose trong
prefix cache. `prompt_builder.py:411`, và comment giải thích nó sinh từ đâu:
*"Observed on DeepSeek v4-flash on the same task: pushed through PEP-668 wall,
then returned fabricated listings."* Và vì sao ngắn: *"shipped to every user,
every session, in the cached system prompt — token cost is paid once at install
and then amortised across all sessions via prefix caching."*

Đáng chú ý hơn: khối `OPENAI_MODEL_EXECUTION_GUIDANCE` của Hermes ban đầu chỉ
cho GPT/Codex, sau bỏ hàng rào vì eval trace thấy model khác cùng lỗi — trong đó
có *"doing financial math in prose"*. Đó **đúng** lớp lỗi `grounding.py` được xây
để chặn. Hermes chặn bằng prose; ta chặn bằng 1.302 dòng validator gác mọi câu.

Prose **không thay** validator. Nó gánh phần lớn, validator giữ phần có hậu quả
tài chính (4 mã integrity ở Phase 2).

### Khối 1 — chống bịa

Đặt trong `SECTIONS`, cạnh `INVARIANTS`. Ràng buộc: không brace (assertion của
`contract.py`), ngắn, và nói được ba điều:

1. Số phải đến từ tool, không từ suy luận trong văn.
2. Không trích được thì **không nêu số** — nhưng vẫn trả lời, và nói rõ thiếu gì.
3. Nói thẳng chỗ vướng luôn tốt hơn bịa một con số trông hợp lý.

Điểm 2 là điểm mới so với Contract hiện tại. Contract nay nói *"a figure you
cannot reference is a figure you do not state"* — đúng, nhưng dừng ở đó, nên model
chọn cách im lặng hoặc hedge. Phải nối tiếp: **vẫn trả lời, nêu rõ khoảng trống**.

### Khối 2 — gộp tool call

Mẫu `prompt_builder.py:454`. Lý do nó tồn tại, nguyên văn: *"The hermes-agent
runtime already executes a batch of tool calls concurrently when they are
independent … The missing piece was telling the model to emit those calls
together in the first place."*

Áp đúng vào ta: `loop.py` đã `asyncio.gather` các call trong một round, nhưng
Contract không có câu nào dạy model phát chúng cùng lượt. Với `MAX_TOOL_ROUNDS`
là **4**, mỗi round bị lãng phí là đắt gấp đôi — đây là khối có đòn bẩy cao nhất
trong phase này.

## Related Code Files

- Modify: `apps/api/src/agent/prompt/sections.py` — 2 `PromptSection` mới, bump `PROMPT_VERSION` 1.7.1 → 1.8.0
- Modify: `apps/api/src/agent/prompt/contract.py` — chỉ nếu thứ tự section cần đổi
- Create: `docs/adr/0022-contract-carries-the-no-fabrication-rule.md` — amend `ADR-0015`
- Modify: `docs/adr/0015-*.md` — ghi tham chiếu tới ADR mới
- Modify: `apps/api/tests/test_agent_system_prompt.py` — assert section có mặt, hash đổi, không brace

## Implementation Steps

1. **Cổng G1**: trình luận cứ amend `ADR-0015` cho chủ sản phẩm. Không viết code
   trước khi chốt.
2. Viết ADR-0022: nêu quyết định, lý do, và ranh giới — prose gánh phần lớn,
   validator giữ 4 mã integrity.
3. Viết khối chống bịa. Kiểm: không brace, không format hole, ngắn.
4. Viết khối gộp tool call.
5. Bump `PROMPT_VERSION` → 1.8.0. Xác nhận `contract_hash()` đổi.
6. Test: section có trong render, hash khác trước, `prefix()` vẫn ổn định giữa
   các Turn, không giá trị runtime nào lọt vào phần stable.
7. `make test`.
8. Đóng băng lại Eval Fixture nếu tool catalog không đổi (chỉ contract đổi thì
   fixture giữ được — xác nhận theo `docs/agents/eval-battery.md`).
9. Eval Report cho PR (bắt buộc — chạm System Prompt Contract).

## Success Criteria

- [x] Cổng G1 chốt; ADR-0022 viết xong và `ADR-0015` trỏ tới nó
- [x] Hai section mới có trong `SECTIONS`, không chứa brace — `figures` (mục 3) và
      `batched_lookups` (mục 6), mỗi cái đặt cạnh section nó mở rộng
- [x] `PROMPT_VERSION` = 1.8.0, `contract_hash()` khác 1.7.1
- [x] `prefix()` byte-identical giữa hai Turn khác nhau (test cũ vẫn giữ)
- [x] Không field mới nào model có thể set để tự khai tuân thủ — có test riêng
      quét cả vốn từ marker
- [ ] Chạy tay: câu không đủ dữ liệu → trả lời có nội dung + nêu rõ khoảng trống.
      **Chưa chạy**: cần một tuyến LLM thật; để chung với gate run Phase 8
- [x] `make test` xanh (2686 passed)
- [ ] Eval Report — **nợ**, gộp vào Phase 8. Commit thẳng `develop` nên không có
      PR body để đính; fixture không phải đóng băng lại

## Ghi chú thực thi

- Câu *"Call tools in parallel when their answers do not depend on each other"*
  đã bị **bỏ khỏi** `TOOL_USE`: section mới nói đủ và nói kỹ hơn, giữ cả hai là
  lặp trong prefix trả tiền một lần nhưng đọc hai lần.
- Số mục của mọi section sau mục 2 dịch lên: `runtime_context` từ 8 → 10. Hai
  docstring trỏ "section 7" (`contract.py`, `widgets.py`) vốn đã lệch một bậc từ
  trước, nay trỏ theo **tên** section.
- Prompt tăng ~600 token estimate (6.518 token cho `prefix()` ở
  `CHARS_PER_TOKEN=3`, trên trần 32.000 mỗi call). Test trần constructed-context
  giờ suy ra trần từ Contract đã render thay vì hằng số viết tay.

## Risk Assessment

**Rủi ro**: prose làm model quá tự tin, nêu số không trích được rồi tự thêm caveat.
**Tín hiệu**: `unverified_figures` tăng; rubric blind-score bắt figure không nguồn.
**Phản ứng**: Contract 1.6.0 đã từng thêm luật *"forbid provenance caveats in
prose"* (commit `1aa9f31`) — giữ luật đó, và nếu vẫn vỡ thì đưa mã tương ứng về
`INTEGRITY_GATE_CODES`.

**Rủi ro**: khối gộp tool call làm model phát cả 4 round vào một lượt rồi hết
budget. **Tín hiệu**: `MalformedArguments` hoặc round đầu quá lớn. **Phản ứng**:
thêm câu giới hạn "chỉ gộp cái độc lập", đúng như Hermes: *"Only serialize calls
when a later call genuinely depends on an earlier call's result."*

**Assumption có thể vỡ**: prose đủ để thay phần lớn validator. Nếu Phase 8 cho
thấy tỉ lệ figure sai tăng, giả định sai và phải đưa ranh giới Phase 2 về phía
chặt hơn — prose giữ, nhưng nhóm integrity rộng ra.

## Rollback

Xoá hai section, hạ `PROMPT_VERSION` về 1.7.1. Không có state nào để dọn.
