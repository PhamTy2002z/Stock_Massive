---
phase: 8
title: "Cổng Eval và baseline"
status: pending
priority: P1
effort: "1-2d"
dependencies: [2, 3, 4, 5, 6, 7]
---

# Phase 8: Cổng Eval và baseline

## Overview

Chạy Eval Battery làm baseline mới, trả món nợ eval gate mà `docs/specs/0004`
đã tự ghi, và kiểm chứng bằng số rằng fail-open không mở đường cho con số bịa.

Đây là phase **không được bỏ**. Toàn bộ Phase 2 và 3 đánh cược rằng hạ cấp không
làm figure sai lọt ra. Phase này là chỗ duy nhất phát hiện được nếu cược sai.

## Requirements

- Functional: một gate run hoàn chỉnh trên contract mới, làm baseline.
- Functional: rubric blind-score được chấm — ba câu hỏi `cited` / `sanctioned` /
  `contradiction`, chấm **trước** khi mở kết quả deterministic.
- Functional: Eval Report đính vào PR của mọi phase chạm 4 surface `CLAUDE.md` liệt kê.
- Non-functional: chạy trên `EVAL_DATABASE_URL` riêng, **không bao giờ** ghi vào
  store dev/prod.
- Non-functional: `mcp_enabled` pin off — *"so a server's availability cannot move
  a fixture"*.

## Architecture

### Món nợ đang tồn tại

`docs/specs/0004` §"Gate status" tự ghi: W1 + W4 vào `develop` **không có** Eval
Report mà `docs/agents/eval-battery.md` đòi, dù chạm cả ba surface. Lý do ghi
lại: tuyến free tier ~50 lời gọi/ngày, một gate run cần vài trăm. Chủ sản phẩm
đã xác nhận ngân sách LLM không còn là rào cản.

Baseline gần nhất là **1.4.0** (2026-08-17). Contract nay là 1.7.1, và plan này
đưa lên ~1.9.x. Nên mọi so sánh trước Phase 8 là so xuyên phiên bản và phải ghi rõ.

### Fixture

Fixture đóng băng theo ngày + hash: `2022-02-08-6396fc5cde35fd62`. Phase 6 đổi
tool catalog → **phải** đóng băng lại, `tool_catalog_version` đổi. Phase 2/3/5/7
chỉ đổi contract → fixture giữ được, xác nhận theo `docs/agents/eval-battery.md`.

Điều kiện chạy trên host (đã ghi trong ký ức phiên trước): capture cần 2022-02-08
và FLC trong `UNIVERSE_SYMBOLS`; lift biến `LLM_*` từ container.

### Cái phải đọc trong kết quả

| Chỉ số | Bar | Nghĩa nếu trượt |
|---|---|---|
| Category B | ≥ 90% | Gate vẫn chặn sai — Phase 2 chưa đủ |
| `grounding_failed` | < 5% Turn | tripwire mà chính validator đặt ra |
| `answer_kinds.analysis` | > 0 | có câu trả lời có dữ liệu lên tới màn hình |
| `flags.wrong_figure` | **0** | **hạ cấp đã để figure sai lọt — cược sai** |
| `flags.overreach` | 0 | nói quá bằng chứng |
| `flags.wrongly_refused` | 0 | từ chối sai |
| `downgraded_blocks` / block phát hành | theo dõi | tăng vọt = hạ cấp quá tay |

`flags.wrong_figure` là chỉ số quyết định của cả plan. Nếu nó > 0, ranh giới
4/20 ở Phase 2 sai và phải chia lại **theo bằng chứng**, không theo suy luận.

### Golden Question Set

12 câu `docs/specs/0004` §4 (G1–G12) vào Eval Battery qua cửa
confirmed-flagged-message. Chạy tay trước để bắt lỗi thô, rồi mới đưa vào battery.

## Related Code Files

- Modify: `docs/eval/` — thêm `2026-08-2x-1.9.x.json` + `.rubric.md`
- Modify: `docs/specs/0004-general-expert-answer-bar.md` — cập nhật §"Gate status",
  ghi món nợ đã trả
- Modify: `docs/agents/eval-battery.md` — nếu quy trình đóng băng lại fixture đổi
- Modify: `apps/api/src/agent/ops.py` — nếu cần chỉ số mới cho bảng trên
- Create: `plans/reports/eval-260821-xxxx-baseline.md` — phân tích kết quả

## Implementation Steps

1. Xác nhận `EVAL_DATABASE_URL` trỏ store riêng. Kiểm bằng cách đọc, không giả định.
2. Chạy tay 12 câu Golden Question Set trên deploy hiện tại. Ghi lại từng câu.
3. Đóng băng lại fixture nếu Phase 6 đã đổi tool catalog.
4. `make eval` gate mode. Ghi run id.
5. Chấm rubric **blind** — không mở report deterministic trước khi xong file
   rubric. File rubric nói rõ: *"a reviewer who has seen them is no longer
   scoring blind."*
6. Đối chiếu bảng chỉ số. Nếu `flags.wrong_figure > 0`: **dừng**, mở lại Phase 2.
7. Viết phân tích vào `plans/reports/`; cập nhật `docs/specs/0004`.
8. Đính Eval Report vào PR của các phase còn treo.

## Success Criteria

- [ ] Gate run hoàn chỉnh (`complete: true`), có run id
- [ ] Chạy trên `EVAL_DATABASE_URL` riêng — xác nhận không ghi vào dev/prod
- [ ] Category B ≥ 90%
- [ ] `grounding_failed` < 5% số Turn
- [ ] `answer_kinds.analysis` > 0
- [ ] `flags.wrong_figure` = 0
- [ ] `flags.overreach` = 0, `flags.wrongly_refused` = 0
- [ ] Rubric chấm blind, 26 case × 3 câu hỏi hoàn tất trước khi mở report
- [ ] 12/12 Golden Question Set trả lời được, không câu nào màn hình trắng
- [ ] `docs/specs/0004` §"Gate status" cập nhật: món nợ đã trả
- [ ] Eval Report đính vào mọi PR chạm 4 surface

## Risk Assessment

**Rủi ro lớn nhất của cả plan**: `flags.wrong_figure > 0` — nghĩa là fail-open đã
để con số bịa tới người đọc, đúng thứ `grounding.py` được xây để chặn.
**Tín hiệu**: chính chỉ số đó. **Phản ứng đã định**: dừng plan, đưa mã liên quan
về `INTEGRITY_GATE_CODES`, chạy lại. Không thương lượng — đây là chỗ sản phẩm
mang hậu quả tài chính.

**Rủi ro**: gate run tốn nhiều lời gọi rồi hỏng giữa đường. **Phản ứng**: chạy
theo category, ghi run id từng phần; `stopped_reason` trong JSON cho biết dừng ở đâu.

**Rủi ro**: chấm rubric không blind vì người chấm đã đọc code Phase 2 và biết
mong đợi gì. **Phản ứng**: người chấm nên là người không viết Phase 2, hoặc chấm
trước khi đọc kết quả deterministic — điều kiện đã ghi trong file rubric.

**Assumption có thể vỡ**: giả định bar category B ≥90% đạt được sau Phase 2+3.
Nếu đạt 60-80%, plan **không** thất bại — nó cho biết còn nguyên nhân thứ ba chưa
tìm ra, và bước tiếp là đọc case trượt, không phải nới thêm gate.

## Rollback

Không có gì để rollback — phase này chỉ đo và ghi. Nhưng kết quả của nó có thể
buộc rollback Phase 2, và đó là mục đích của nó.
