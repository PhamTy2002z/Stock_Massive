---
phase: 2
title: "Grounding fail-open"
status: complete
priority: P1
effort: "2-3d"
dependencies: [1]
---

# Phase 2: Grounding fail-open

## Overview

Đảo mặc định của Recommendation Validator: guard không chắc thì **nhường đường**,
không chặn. Đây là phase chạm trực tiếp 58% Turn trắng và category B 0/30.

## Requirements

- Functional: một block không chứng minh được **không** kết thúc Turn, trừ khi
  lỗi là lỗi **toàn vẹn** (con số chống lại chính citation của nó).
- Functional: khi hạ cấp, câu trả lời mang một câu **backend-authored** nói rõ
  điều gì không chứng minh được. Không figure, nên không cần citation, nên
  không thể tự fail Gate.
- Functional: nudge có trần. Hết trần thì **thả** block kèm câu trên, không raise.
- Non-functional: giữ bất biến `ADR-0015` cốt lõi — model không có field nào để
  tự khai là đã pass. Không thêm field như vậy.
- Non-functional: block khuyến nghị mua/bán có price zone **vẫn** bị chặn khi
  thiếu điều kiện.

## Architecture

### Con số then chốt

`grounding.py` raise **24 mã lỗi** riêng biệt. `DEGRADABLE_GATE_CODES` chỉ chứa
**8**. Nghĩa là **16 mã kết thúc Turn** — và phần lớn không phải lỗi toàn vẹn:

| Mã | Hiện tại | Đề xuất | Vì sao |
|---|---|---|---|
| `figure_mismatch` | BLOCK | **BLOCK** | Lỗi toàn vẹn thật. `ADR-0018` đã nói: *"A figure that conflicts with the cited Tool Call Trace remains a hard failure in every block."* |
| `trading_day_mismatch` | BLOCK | **BLOCK** | Cùng lớp: số đúng nhưng gán sai ngày |
| `missing_trading_day` | BLOCK | **BLOCK** | Khuyến nghị không có ngày là khuyến nghị không kiểm được |
| `symbol_not_in_universe` | BLOCK | **BLOCK** | Ngoài phạm vi phục vụ (`ADR-0001`) |
| `field_not_registered` | BLOCK | → DEGRADE | Field không đăng ký = không có bảo chứng, không phải nói sai |
| `uncitable_field_path` | BLOCK | → DEGRADE | Đường dẫn không trích được — lỗi hình thức |
| `unknown_field_path` | BLOCK | → DEGRADE | như trên |
| `missing_value` | BLOCK | → DEGRADE | Giá trị không có = thiếu dữ liệu |
| `missing_as_of` | BLOCK | → DEGRADE | Thiếu mốc thời gian — hạ cấp và nói rõ |
| `refused_field` | BLOCK | → DEGRADE | Tool đã từ chối; đó là thiếu dữ liệu |
| `refused_tool_call` | BLOCK | → DEGRADE | như trên |
| `unfinished_tool_call` | BLOCK | → DEGRADE | Vòng chưa xong |
| `unknown_tool_call` | BLOCK | → DEGRADE | Model trích id không tồn tại — lỗi hình thức |
| `incomplete_citation` | BLOCK | → DEGRADE | Marker viết thiếu |
| `malformed_reference` | BLOCK | → DEGRADE | Marker viết sai cú pháp |
| `unclassified_claim` | BLOCK | → DEGRADE | Không xếp được loại bằng chứng |

Kết quả: **4 block / 20 degrade**, đảo từ 16/8.

Ranh giới: **lỗi toàn vẹn** = con số nói khác bằng chứng nó trích. **Lỗi khả
dụng/hình thức** = bằng chứng không có, hoặc marker viết sai. Hermes gọi cùng
tên: `verification_evidence.py` là ledger *"deliberately passive"*, còn
`verification_stop.py` là *"policy-only"* biến thiếu bằng chứng thành
*"bounded follow-up"*.

### Nudge có trần

Hiện `loop.py` cho một block bị chặn **một** lần rewrite (commit `d699345`).
Sau lượt đó, hết. Thêm đường thứ ba:

```
attempt 1: validate → fail (không toàn vẹn) → nudge tổng hợp, continue
attempt 2: validate → fail       → thả block + câu backend-authored
lỗi toàn vẹn (bất kỳ attempt): → chặn block, Turn tiếp tục nếu có block khác
```

Nudge phải mang: mã điều kiện không đạt, và **hành động cụ thể** (gọi tool nào
để có bằng chứng). Mẫu — `verification_stop.py:305`, và câu bản lề của nó:
*"If verification is not possible, explain the concrete blocker instead of
claiming the work is fully verified."*

Cấu trúc message tổng hợp phải hợp lệ. Bài học `conversation_loop.py:7690`:
*"the message sequence stays valid: tool(result) → assistant('(empty)') →
user(nudge). Without this, we'd have tool → user which most APIs reject."*
Đánh dấu message tổng hợp (kiểu `_synthetic: True`) để `persistence.py` không
ghi vào transcript bền.

### Câu backend-authored

`DEGRADED_REASON_TEXT` + `DEGRADED_RECOMMENDATION_NOTICE` đã tồn tại cho 8 mã.
Mở rộng cho 20 mã. Comment hiện có trong `grounding.py:177` giải thích đúng lý
do giữ nó backend-authored: *"a sentence the model writes is a sentence the model
can be talked out of."* Giữ nguyên nguyên tắc đó.

Mức chi tiết: nêu **loại** bằng chứng thiếu, không nêu tên field nội bộ. Xem
câu hỏi mở #4 của `hermes-synthesis`.

## Related Code Files

- Modify: `apps/api/src/agent/grounding.py` — `DEGRADABLE_GATE_CODES`,
  `DEGRADED_REASON_TEXT`, và tách rõ nhóm integrity
- Modify: `apps/api/src/agent/loop.py:1200,1261` — đường `degradable`, thêm nudge
- Modify: `apps/api/src/agent/persistence.py` — bỏ message tổng hợp khỏi transcript bền
- Modify: `apps/api/src/agent/manifest.py` — Evidence Manifest ghi mỗi lần hạ cấp
- Modify: `docs/adr/0018-*.md` — amend: đảo mặc định, nêu 4 mã còn chặn
- Create: `docs/adr/0021-fail-open-grounding.md` — quyết định mới, amend `ADR-0015`
- Modify: `apps/api/tests/test_agent_grounding.py`, `test_agent_loop.py`

## Implementation Steps

1. **Cổng G2**: trình bảng 24 mã cho chủ sản phẩm, chốt ranh giới 4/20 trước khi
   sửa code. Không tự quyết.
2. Tách `INTEGRITY_GATE_CODES` (4 mã) thành hằng số riêng; đổi `degradable`
   thành `code not in INTEGRITY_GATE_CODES` — **đảo mặc định thành fail-open**.
   Mã mới thêm sau này sẽ tự động degrade, đúng hướng an toàn cho người dùng.
3. Viết `DEGRADED_REASON_TEXT` cho 12 mã mới. Mỗi câu: không figure, không tên
   field nội bộ, nói được người đọc phải làm gì.
4. Thêm nudge tổng hợp ở `loop.py`: trần 2, đánh dấu synthetic, chuỗi message
   hợp lệ.
5. `persistence.py`: bỏ message synthetic khỏi transcript bền lúc finalize.
6. `manifest.py`: mỗi hạ cấp là một dòng trong Evidence Manifest.
7. Test: một case cho **mỗi** trong 24 mã, khẳng định block hay degrade.
8. `make test`, rồi chạy tay 12 câu Golden Question Set.
9. Chuẩn bị Eval Report cho PR (bắt buộc — phase này chạm Recommendation Validator).

## Success Criteria

- [x] Cổng G2 được chủ sản phẩm chốt, ghi trong `docs/adr/0021-fail-open-grounding.md`
- [x] `INTEGRITY_GATE_CODES` có **8** mã; mặc định là degrade
- [x] **28/28** mã có test khẳng định block hay degrade (không phải 24 — xem ghi chú)
- [x] Mỗi mã degrade có câu backend-authored, không chứa figure
- [x] Nudge có trần 2, message synthetic không vào transcript bền
- [x] Khuyến nghị mua/bán thiếu zone/reference price **vẫn** bị chặn
- [x] 12 câu Golden Question Set: **0/12 màn hình trắng** — đo trên `gpt-5.6-terra` 2026-08-21, xem `plans/reports/golden-run-260821-2010-fail-open.md`
- [x] `make test` xanh — 2589 passed
- [ ] Eval Report đính vào PR — **chưa chạy `make eval`**

## Đã làm khác plan

**`persistence.py` không sửa một dòng.** Nudge được ghép vào list `messages` ngay trước
`_complete()` và không bao giờ đi qua `append_message`. Bản ghi bền là `draft_content` =
blocks + widgets + tool_calls + progress; `text` cố tình vắng mặt. Message synthetic **đã**
không vào transcript theo cấu trúc, nên không cần cờ `_synthetic`. Thay vào đó thêm
`test_the_nudge_is_spent_on_its_call_and_never_becomes_transcript`.

**Chuỗi message đã hợp lệ sẵn.** Plan lo trường hợp `tool → user` mà API từ chối. Ở đây
nudge là `Message(role=SYSTEM)` append sau `build_messages`, và draft lỗi không nằm trong
messages — không có vấn đề đó.

**Hai frame cho câu hạ cấp.** Phần lớn trong 20 mã phát ra khi đang resolve marker, tức
*trước* khi biết block định làm khuyến nghị hay không (`validate()` chỉ tìm marker `rec`
sau vòng `_cite`). `DEGRADED_RECOMMENDATION_NOTICE` nói "chưa đưa ra khuyến nghị vùng giá"
— sai với người hỏi tình hình thị trường. Thêm `DEGRADED_PROSE_NOTICE`, chọn frame bằng
`is_recommendation_draft(raw)` đọc từ chính draft.

**`DEGRADED_REASON_FALLBACK`.** Mặc định giờ là degrade, nên một mã viết tháng sau sẽ
degrade ngay — không có fallback thì nó degrade thành notice **rỗng**, tức màn hình trắng
đi vào bằng cửa khác.

**`degraded_recommendation_code` → `degraded_codes`.** Một answer có nhiều block, mỗi
block hạ cấp vì lý do riêng; một field đơn báo cái cuối như thể là cái duy nhất. Giữ
`degraded_recommendation_code` làm property đọc phần tử đầu cho các reader chỉ nhận một
giá trị. `GateOutcome` thêm `downgrades` (additive, không bump `MANIFEST_SCHEMA_VERSION`
theo đúng luật ghi ở `manifest.py:49`).

**Nudge cho cả block bị hạ cấp.** Trước khi đảo, mã degradable *raise*, nên chúng đi qua
nhánh refusal và vẫn được rewrite. Sau khi đảo chúng không raise nữa — không thêm nhánh
thứ hai trong `_repair` thì model không bao giờ còn được yêu cầu sửa marker đặt sai, và
câu trả lời âm thầm thành câu xin lỗi của backend.

**5 test cũ khẳng định hành vi fail-closed đã viết lại.** `unknown_tool_call` giờ hạ cấp
thay vì kết thúc Turn. Thay vì nới assert, mỗi test được thay bằng draft lỗi *integrity*
(`INTEGRITY_DRAFT` = `[rec:XYZ@2026-08-14]`, `symbol_not_in_universe`) để vẫn kiểm đúng
tính chất "chặn", cộng test mới khẳng định hành vi hạ cấp.

## Risk Assessment

**Rủi ro chính**: hạ cấp quá tay → con số bịa lọt tới người đọc, đúng thứ
validator được xây để chặn. **Tín hiệu**: `downgraded_blocks` tăng vọt; rubric
blind-score ở Phase 8 bắt được figure sai. **Phản ứng đã định**: đưa mã đó về
`INTEGRITY_GATE_CODES`. Đây là lý do Phase 8 không phải tuỳ chọn.

**Rủi ro**: nudge tiêu một lời gọi model; Turn xấu tốn tới 3 lời gọi. **Tín
hiệu**: chi phí mỗi Turn trong `llm_call_usage` tăng. **Phản ứng**: hạ trần về 1.

**Assumption có thể vỡ**: giả định 20 mã kia thật sự là lỗi khả dụng/hình thức
chứ không phải model nói sai. Nếu Phase 8 cho thấy figure sai lọt qua nhiều mã
trong số đó, ranh giới 4/20 sai và phải chia lại theo bằng chứng, không theo
suy luận.

## Rollback

Đảo `INTEGRITY_GATE_CODES` về chứa cả 16 mã cũ — một hằng số, một commit revert.
Hành vi trở về nguyên trạng, không mất dữ liệu.

## Sửa sau review

`code-reviewer` tìm ba lỗi nặng, đã sửa hết.

**`grounding.py` raise 28 mã, không phải 24.** Bốn mã dựng bằng f-string
(`f"{key}_mismatch"` → `unit_mismatch`, `claim_mismatch`, `source_mismatch`,
`interpretation_mismatch`) nên không xuất hiện dưới dạng literal ở đâu. Bảng 24 mã của
plan bỏ sót cả bốn, và vì `degradable` là phép loại trừ, cả bốn **âm thầm chuyển từ block
sang degrade** — ngoài phạm vi G2 đã chốt. Cả bốn là bất đồng với Signal Registry, tức
integrity theo đúng định nghĩa `ADR-0021`, nên đã thêm vào `INTEGRITY_GATE_CODES`: giữ
đúng hành vi trước Phase 2. Ranh giới thật là **8 block / 20 degrade**.

Test guard tôi viết dùng regex tìm literal nên **không thể** thấy bốn mã đó — nó báo
"đủ 24/24" trong khi thiếu. Đã đổi sang đọc AST, cộng một test khẳng định guard thấy được
mã không phải literal.

**Marker 400 nhận dạng sai body mà route thật gửi.** Ba ca thành `OutputCapExceeded`
oan: `"Unsupported parameter: 'max_tokens' is not supported"` (lỗi request builder),
`"Invalid value for max_tokens"`, và mọi route vọng lại request nó từ chối — chính tiền
đề `redact` tồn tại, nên là ca thường chứ không phải ca lạ. Thêm hai ca nữa:
`"parameter temperature has been deprecated for this model"` → `ModelUnavailable`, và
`tool_use_failed` (model sinh tool call sai) → `SchemaRejected` log ở ERROR như thể lỗi
của repo. Đã thắt: cap cần **từ chỉ kích thước** bên cạnh tên tham số; `deprecated` phải
có `model` làm **chủ ngữ** (regex); `"invalid tool"` → `"invalid tool schema"`.

**`redact` để lọt mọi scheme không phải Bearer.** `\S+` dừng ở dấu cách đầu tiên nên với
`Basic`/`Token`/`ApiKey` nó xoá **tên scheme** và giữ credential — dòng log đọc như đã
được che, tệ hơn không che. Đã sửa, thêm JWT/`?key=`/`session=`/`ghp_`, và áp `redact`
cho cả năm dòng log trong `LLMMetrics` — nhánh 401 là nơi route hay vọng lại đúng khoá
nó vừa từ chối.

**Nudge có thể biến câu trả lời đã phát được thành Turn chết.** Attempt 1 chỉ lỗi
degradable ⇒ đã phát được. Nudge ép model gắn reference cho mọi số; reference gắn sai call
là `figure_mismatch` — integrity, kết thúc Turn. Người đọc mất câu trả lời họ *đã* có được
một lời gọi trước đó. Thêm `_fall_back_to_pre_nudge_draft`: giữ draft trước nudge và
prove lại. Nudge giờ chỉ có thể làm tốt hơn.

**`gate_outcomes` báo lỗi dấu câu ở prose thành "khuyến nghị bị chặn".** 20 mã hạ cấp trên
*mọi* block, nên một đoạn tổng quan thị trường với một dấu ngoặc lệch cũng đặt
`recommendation="blocked"` — đúng chiều mà baseline Phase 8 sẽ đọc. Thêm
`degraded_recommendations`, đếm theo `is_recommendation_draft` (kết quả trước đây bị bỏ đi).

Ba mục nhỏ: `bytes_received` đếm ký tự thay vì byte (tiếng Việt lệch 2-3×); `GatewayTimeout`
từ 5xx log "0 byte received" trong khi route *có* trả lời (thêm `RouteAttempt.measured`);
notice giống nhau lặp mỗi block (dedupe — G1 từ 11 block xuống 2).
