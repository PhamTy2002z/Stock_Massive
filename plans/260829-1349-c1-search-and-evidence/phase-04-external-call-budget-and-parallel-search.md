---
phase: 4
title: "Ngân sách external call và tìm song song"
status: done
priority: P1
effort: "8h"
dependencies: [2, 3]
---

# Phase 4: Ngân sách external call và tìm song song

## Overview

Phase đắt nhất của plan, và là phase duy nhất tiêu tiền thật của người dùng.
Mục tiêu "2–3 truy vấn + 3–4 trang đọc" = **5–7 external call**, trong khi trần
hiện tại là **6** (`loop.py:293`). Trần cắt ngang giữa mục tiêu.

Phase này quyết trần mới **bằng phép đo chi phí**, và thêm câu prompt hướng dẫn
model dùng hết chỗ đó cho việc đúng.

## Requirements

- Functional: `MAX_EXTERNAL_TOOL_CALLS` đổi sang một giá trị **được chứng minh
  bằng chi phí đo được**, không phải một số tròn.
- Functional: một section prompt hướng dẫn gọi tool song song, `PROMPT_VERSION`
  bump từ **2.9.0**.
- Non-functional: chi phí trung bình một Turn web-first nằm trong envelope
  $45/tháng chia theo lane hiện tại.
- Non-functional: **không** đổi `MAX_TOOL_ROUNDS = 4`, không đổi
  `MAX_EXTERNAL_CALLS_PER_ROUND = 8`, không đổi `plan_segments()`.

## Architecture

### Cơ chế song song đã có — đừng dựng lại

Đã đo và xác nhận, mọi mắt xích tồn tại:

| Mắt xích | Ở đâu | Trạng thái |
|---|---|---|
| Fan-out song song | `executor.py:268-278`, `asyncio.gather` | Có |
| Phân đoạn an toàn | `executor.py:156-180`, `plan_segments()` gom `READ + PARALLEL_SAFE` | Có |
| `web_search` khai an toàn | `tools/web.py:339`, `ToolConcurrency.PARALLEL_SAFE` | Có |
| Trần fan-out mỗi round | `executor.py:86`, `MAX_EXTERNAL_CALLS_PER_ROUND = 8` | Có |
| Model thực sự dùng | store: 2/10 round hậu rip có ≥2 search; 21/43 cả lịch sử, max 5 | **Đã dùng** |

Nên việc ở đây **không phải** làm song song chạy được. Nó là: (a) nới trần
Turn để 2–3 search còn chỗ cho 3–4 fetch, và (b) nói với model rằng đọc trang
đáng giá bằng tìm thêm.

Hermes **không** có prompt guidance cho việc này — nó dùng rules engine ở tầng
executor (`docs/hermes/hermes-tools-260820-2352.md:44-62`), thứ ta đã có. Nên
câu prompt ở đây là quyết định của repo này, không phải thứ port từ Hermes.
Ghi vậy để phase sau đừng đi tìm một câu nguyên văn không tồn tại.

### Trần mới là công thức, không phải hằng số chọn sẵn

**Giá đã đo trên `llm_call_usage` thật 2026-08-29** — đọc trước khi tính, vì tên
cột gài bẫy:

| Dữ kiện | Giá trị |
|---|---|
| `input_token_price_usd` | **2,0** — đây là **micro-USD trên token** ($2/triệu), *không* phải USD/token dù tên cột nói vậy |
| `output_token_price_usd` | **10,0** micro-USD/token ($10/triệu) |
| Một Turn thật (9.337 in + 184 out) | 20.514 micro-USD ≈ **$0,021** |
| `reserved_micro_usd` cùng Turn đó | 57.680 ≈ $0,058 — giữ chỗ ~2,8× thực chi |
| `TURN_COST_MICRO_USD` | **500.000** = trần **$0,50** một Turn (`core/llm/admission.py:55`) |

Phép quy đổi ở `admission.py::_micro_usd` — `tokens × price`, `ROUND_CEILING`.
Tự nhất quán, chỉ tên cột gây hiểu nhầm. Đừng "sửa" nó trong phase này.

```
chi phí một external call ≈ token vào × giá vào + token ra × giá ra + latency
trần mới = số call mà chi phí trung bình một Turn web-first còn dưới
           TURN_COST_MICRO_USD và trong phần envelope của lane Turn
```

**Ngân sách không phải rào cản, và phép đo nói vậy.** Một Turn ở $0,021 so trần
$0,50 là **24× headroom**. Cả lượt golden 20 câu ≈ $0,60. Nên nếu phép tính ra
"không đủ chỗ để nới trần", thứ sai gần như chắc chắn là phép tính — kiểm lại
đơn vị micro-USD trước khi kết luận.

Envelope: $45/tháng, chia 10 Analysis / 30 Turn / 5 emergency. Lane Analysis
**đã bỏ** (rip-out) và envelope **chưa reweight** — đó là một dữ kiện của phase
này, không phải thứ phase này sửa. Nếu phép tính cần lane Analysis được reweight
mới đủ chỗ, **dừng và hỏi user**; đừng tự reweight envelope.

### Trần không đi một mình — nó là một cặp có test giữ

`guardrails.py:95-111` khai `same_tool_failure_halt_after = 6` và nói thẳng đó
**là cùng một sự thật**: *"the external-call ceiling itself… the two numbers are
one fact and are written as one — change either and change both… the equality is
held by a test"*. Test ở `tests/test_agent_guardrails.py:122`:

```python
assert DEFAULT_THRESHOLDS.same_tool_failure_halt_after == MAX_EXTERNAL_TOOL_CALLS
```

Bản đầu của phase này **bỏ sót cả hai file**. Đổi trần mà không đụng chúng thì
test đỏ, và cách sửa sai là tháo đẳng thức — thang halt lệch khỏi trần mà không
ai quyết.

**Quyết định phải viết ra, không được để mặc định:** `same_tool_failure_halt_after`
đi theo trần mới, hay đứng yên ở 6? Đi theo là giữ nguyên ý nghĩa gốc ("một tool
hỏng nhiều bằng cả ngân sách thì dừng"); đứng yên là tách hai khái niệm và phải
viết lại docstring cho khỏi nói dối. Chốt ở bước 4, ghi lý do.

### Trần mới phải nhỏ hơn 8

Hôm nay 6 < `MAX_EXTERNAL_CALLS_PER_ROUND = 8`, nên cổng Turn (`loop.py:1493`)
**luôn bắn trước** và đường per-round **chưa từng binding trong production**.
Nới trần Turn lên ≥ 8 kích hoạt lần đầu một code path chưa ai chạy thật.

Mục tiêu 5–7 call vẫn nằm dưới 8, nên đây là **ràng buộc rẻ**: trần mới **< 8**.
Nếu phép tính chi phí đòi ≥ 8, đó là scope khác — dừng và ghi, đừng lặng lẽ mở
một đường chưa test.

Kèm theo: `assert len(refused) == MAX_TOOL_ROUNDS * 2 - MAX_EXTERNAL_TOOL_CALLS`
(`tests/test_agent_loop.py:890`) âm nếu trần > 8. Một dấu hiệu nữa rằng 8 là biên.

### Con số 8 được biện minh bằng con số 6

`plans/260827-2325-evidence-led-chat-surface/phase-09:39` ghi:
*"`MAX_EXTERNAL_CALLS_PER_ROUND = 8` biện minh bằng con số 6"*. Nghĩa là hai trần
không độc lập — đổi 6 làm lời giải thích của 8 hết đúng.

Phase này **không đổi 8**, nhưng **phải** cập nhật comment biện minh tại
`executor.py:86` cho khớp trần mới. Bỏ qua bước này để lại một comment nói dối,
và phase 09 của plan kia đọc chính comment đó.

## Related Code Files

- Modify: `apps/api/src/agent/loop.py` — `MAX_EXTERNAL_TOOL_CALLS` (`:293`), kèm comment giải thích **phép đo** ra con số, không chỉ con số
- Modify: `apps/api/src/agent/guardrails.py` — `same_tool_failure_halt_after` (`:111`) + docstring (`:95-111`) nếu quyết định tách hai khái niệm
- Modify: `apps/api/tests/test_agent_guardrails.py` — đẳng thức ở `:122`
- Modify: `apps/api/src/agent/executor.py` — **chỉ comment** biện minh ở `:86-91`; giá trị 8 không đổi
- Modify: `apps/api/src/agent/prompt/sections.py` — section mới cạnh `TOOLS` (`:165+`); `PROMPT_VERSION` (`:29`) 2.9.0 → 2.10.0
- Modify: `apps/api/tests/test_agent_prompt.py` — section mới có mặt, `render()` vẫn typed
- Modify: `apps/api/tests/test_agent_loop.py` — trần mới
- Modify: `CLAUDE.md` — hai con số ở §Quy ước
- Modify: `docs/roadmap.md` — cột "Sau" của C1

## Implementation Steps

1. Đọc artifact golden phase 03: token và giá thật một Turn web-first, phân tách
   theo external call.
2. Tính trần từ envelope. Ghi **cả phép tính** vào report, không chỉ kết quả.
3. Nếu phép tính đòi reweight envelope → **dừng, hỏi user.** Không tự quyết.
4. Đổi `MAX_EXTERNAL_TOOL_CALLS`. Comment tại chỗ ghi phép đo và ngày đo, để
   người sau biết con số này đến từ đâu và khi nào nó hết hạn.
5. Viết section prompt. Nội dung: khi câu hỏi cần nguồn ngoài, phát nhiều truy
   vấn **độc lập** trong một round thay vì nối tiếp; và **đọc trang** khi
   snippet không đủ để trả lời — nói rõ snippet 700 ký tự là trích dẫn, không
   phải bằng chứng.
6. Bump `PROMPT_VERSION`. Kiểm `_assert_no_formatting_hole` (`prompt/contract.py:97-109`)
   vẫn pass — section mới không được chứa `{` hay `}`.
7. Chạy `make golden-run`, so `read_depth` và `parallel_rate` với artifact phase 03.

## Success Criteria

- [ ] Report ghi **phép tính** ra trần mới, gồm token/giá thật và phần envelope dùng
- [ ] Comment tại `loop.py` ghi phép đo và ngày đo, không chỉ con số
- [ ] Comment biện minh `MAX_EXTERNAL_CALLS_PER_ROUND = 8` tại `executor.py:86` cập nhật theo trần mới (giá trị 8 **không** đổi)
- [ ] **Trần mới < 8** — nếu phép tính đòi ≥ 8, dừng và ghi, không tự mở
- [ ] Quyết định `same_tool_failure_halt_after` (đi theo trần / đứng yên) **viết ra kèm lý do**; docstring `guardrails.py:95-111` khớp quyết định đó
- [ ] `test_agent_guardrails.py:122` xanh mà **không** bị tháo đẳng thức để cho xanh
- [ ] `tests/test_agent_loop.py:890` xanh (biểu thức `MAX_TOOL_ROUNDS * 2 - MAX_EXTERNAL_TOOL_CALLS` không âm)
- [ ] `PROMPT_VERSION` bump; `_assert_no_formatting_hole` pass
- [ ] `MAX_TOOL_ROUNDS`, `MAX_EXTERNAL_CALLS_PER_ROUND`, `plan_segments()` **không đổi** — test cũ xanh nguyên
- [ ] `read_depth` trên artifact golden tăng so phase 03
- [ ] `parallel_rate` **không giảm**
- [ ] Chi phí trung bình một Turn web-first ghi vào report và nằm trong envelope
- [ ] `CLAUDE.md` và `docs/roadmap.md` mang con số mới
- [ ] Năm cổng xanh

## Risk Assessment

**Rủi ro chính: nới trần làm chi phí vượt envelope.**
Tín hiệu: chi phí/Turn trong artifact vượt phần lane Turn.
Phản ứng **đã quyết trước**: giữ trần cũ và đổi cách tiêu thay vì đổi trần —
cụ thể, giảm `MAX_RESULTS` từ 5 xuống 3 để mỗi search rẻ hơn, lấy chỗ đó cho
fetch. Đó là đánh đổi *rộng đổi lấy sâu*, và corpus golden là thứ nói nó có
đáng không. **Không** nới envelope.

**Rủi ro: nới trần nhưng model không dùng thêm chỗ để đọc trang.**
Tín hiệu: `read_depth` không tăng dù trần tăng.
Phản ứng: đây là vấn đề prompt, không phải trần — hoàn nguyên trần về 6, giữ
câu prompt, đo lại. Thứ tự này quan trọng: nới trần mà không tăng đọc là tiêu
tiền không mua được gì.

**Rủi ro: section prompt mới làm hồi quy hành vi khác.**
Tín hiệu: golden họ khác (fact có as-of, đối kháng) xấu đi.
Phản ứng: câu prompt phải nói về **khi nào** đọc, không phải **luôn** đọc. Một
câu hỏi trả lời được từ store không nên sinh ra bốn lượt fetch.

**Rủi ro: envelope chưa reweight sau khi bỏ lane Analysis chặn phép tính.**
Đây là điều kiện dừng-và-hỏi đã ghi ở bước 3, không phải thứ tự xử lý được.
