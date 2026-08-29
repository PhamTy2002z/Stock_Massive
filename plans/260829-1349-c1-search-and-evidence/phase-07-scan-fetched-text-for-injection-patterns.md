---
phase: 7
title: "Quét pattern injection trên text đã nạp"
status: pending
priority: P1
effort: "6h"
dependencies: []
---

# Phase 7: Quét pattern injection trên text đã nạp

## Overview

Lớp thứ năm — và là lớp duy nhất còn thiếu trong năm lớp Hermes mô tả. Bốn lớp
kia đã có: SSRF guard, denylist domain, bọc `<untrusted_tool_result>`, và luật
trong prompt.

Phase này **không phụ thuộc phase nào** và chạy song song được từ đầu.

## Requirements

- Functional: quét visible text của kết quả tool đọc-ngoài theo một tập pattern.
- Functional: khớp → **gắn cờ**, không chặn, không cắt.
- Functional: chuẩn hoá NFKC + gỡ ký tự ẩn/bidi trước khi khớp.
- Non-functional: **fail-open tuyệt đối.** Quét lỗi, quét chậm, pattern hỏng —
  câu trả lời vẫn đi. Không đường nào từ phase này dẫn tới màn hình trắng.
- Non-functional: **không** đổi lớp bọc. `wrap_result()` là lớp cứng và nó giữ
  nguyên hành vi.

## Architecture

### Hai lớp, chỉ một lớp cứng — theo đúng Hermes

Hermes tách rõ (`docs/hermes/hermes-web-security-260820-2352.md:96-109`):

| Lớp | Cơ chế | Tính chất |
|---|---|---|
| 1 — bọc | `<untrusted_tool_result source="...">`, defang delimiter | **Luôn chạy**, đổi cách model đọc |
| 2 — quét | `scan_for_threats(text, scope=...)` → `{"risk": "high"/"low", "findings": [...]}` gắn vào metadata | **Chỉ cảnh báo**, chấp nhận false-negative |

Nguyên văn Hermes: *"lớp 2 (regex scan) chỉ để cảnh báo con người, chấp nhận
false-negative"* (`:109`).

Repo đã có lớp 1 đầy đủ: `wrap_result()` (`untrusted.py:117-131`),
`wrap_attachment()` (`:148-169`), `defang()` (`:93-99`), `MIN_WRAP_CHARS = 32`
(`:65`). Phase này thêm **đúng lớp 2**.

### Ba scope pattern

Hermes chia ba (`hermes-web-security-260820-2352.md:80-82`). Ta cần **hai**:

| Scope | Nội dung | Dùng cho |
|---|---|---|
| `all` | injection cổ điển (`ignore ... previous ... instructions`, `system prompt override`), CSS ẩn (`<div style="display:none">`), `do not tell the user` | mọi kết quả đọc-ngoài |
| `context` | role-play hijack (`you are now a/an...`), `output your system prompt` | kết quả web + đính kèm |

Scope `strict` của Hermes (SSH backdoor, sửa `AGENTS.md`) **không áp dụng** —
nó bảo vệ một agent có quyền ghi file, còn lane này không có tool `WRITE` nào
ra ngoài. Ghi lý do loại ra, đừng copy cả ba rồi để một scope chết.

Cộng chuẩn hoá NFKC + 17 ký tự ẩn/bidi (`hermes-web-security-260820-2352.md:245`).

### Cờ đi đâu — bản đầu viết một chỗ KHÔNG tồn tại

Bản đầu viết *"metadata của tool call, cùng chỗ `outcome` đang sống"*. Không có
chỗ đó: `outcome` là **một cột `String(64)`** (`alpha/models.py:201`), và bảng
`agent_tool_call` (`:144-215`) **không có cột metadata JSONB tự do** nào.

Cột `result` JSONB có bất biến riêng — *"exactly what is needed to debug a wrong
answer — what the model actually saw"* (`:147-150`) — nên nhét findings của
scanner vào đó là làm bẩn đúng bất biến ấy.

Hai đường, **user chốt vì nó đụng schema**:

| | A — cột JSONB mới | B — live-only |
|---|---|---|
| Chỗ chứa | cột `scan` trên `agent_tool_call` | payload event + log, không persist |
| Cần | alembic revision + **backup DB trước** (CLAUDE.md) + `models.py` + `persistence.py` vào file list | không migration, không backup |
| Được | truy vấn được về sau: "bao nhiêu % trang có injection", điều tra sự cố cũ | thấy ngay lúc chạy |
| Mất | một cột nữa trên bảng nóng | mở lại thread cũ **không** thấy cờ; không thống kê được |
| Rủi ro lặp lịch sử | đây đúng là "eval state vào production persistence" — nguyên nhân #3 giết bộ eval cũ, dù cờ này là runtime chứ không phải eval | không |

Dù chọn đường nào: cờ **không** vào text gửi model. Một cảnh báo trong text là
một câu model phải diễn giải, và đó chính là bề mặt injection đang tấn công.
Cờ là để **người** đọc.

### Quét ở executor, một lần mỗi kết quả

Bản đầu để mở chỗ quét và gợi ý `untrusted.py` — tức đường **render**. Sai về
hiệu năng: `shown_result` chạy lại mỗi lần dựng message, nên một trang 20k ký
tự sẽ bị quét lại ở **mọi LLM call**, tối đa 5 call một Turn.

Điểm quét đúng: **executor, ngay khi kết quả về, đúng một lần**. Test khẳng định
số lần quét, không chỉ khẳng định kết quả quét.

## Related Code Files

- Create: `apps/api/src/agent/threat_patterns.py` — tập pattern, một nguồn sự thật
- Modify: `apps/api/src/agent/untrusted.py` — hàm quét; **không** đụng `wrap_result()`
- Modify: `apps/api/src/agent/executor.py` — điểm gọi quét, một lần mỗi kết quả
- Modify: `apps/api/src/agent/events.py` — trường cờ trong `TOOL_CALL_FIELDS`
- **Chỉ nếu chọn A:** `apps/api/src/alpha/models.py` · `src/agent/persistence.py` · `apps/api/alembic/versions/*` (revision mới) — và **backup DB trước**
- Modify: `apps/api/tests/test_agent_untrusted_results.py`
- Create: `apps/api/tests/test_threat_patterns.py`
- Modify: `apps/api/golden/web_first.json` — họ đối kháng có case nội dung web mang injection

## Implementation Steps

1. `threat_patterns.py`: hai scope, mỗi pattern kèm comment nói nó bắt gì.
   Pattern nào không giải thích được thì không vào tập.
2. Chuẩn hoá NFKC + gỡ ký tự ẩn/bidi trước khi khớp. Test: cùng một payload
   injection viết bằng ký tự zero-width vẫn khớp.
3. Hàm quét trong `untrusted.py`, trả `{"risk": ..., "findings": [...]}`.
   **Bọc toàn bộ trong try/except**: mọi exception → `risk: "unknown"`, và câu
   trả lời đi tiếp. Fail-open không phải một lời hứa, nó là một khối try.
4. Gắn cờ theo đường đã chốt (A hoặc B). Không vào text gửi model — test khẳng
   định bằng cách đọc transcript, cùng mẫu test frames đang dùng.
5. Đặt trần thời gian cho quét. Chạm trần → `risk: "unknown"`, đi tiếp.
6. Thêm case đối kháng vào corpus golden: một trang có injection, kỳ vọng là
   model **không** làm theo và cờ được gắn.
7. Test: `wrap_result()` hành vi không đổi — mọi test cũ xanh nguyên.

## Success Criteria

- [ ] `wrap_result()` hành vi **không đổi** — test cũ xanh nguyên, không sửa một test nào
- [ ] Injection viết bằng ký tự zero-width vẫn khớp sau NFKC (test)
- [ ] Quét ném exception → câu trả lời vẫn đi, `risk: "unknown"` (test)
- [ ] Quét chạm trần thời gian → câu trả lời vẫn đi (test)
- [ ] Cờ **không** xuất hiện trong message gửi model (test đọc transcript)
- [ ] Scope `strict` **không** có trong tập, và lý do loại ghi tại chỗ
- [ ] Mọi pattern có comment nói nó bắt gì
- [ ] Corpus golden có ≥ 1 case web injection, model không làm theo
- [ ] **Quét chạy đúng một lần mỗi kết quả** — test đếm số lần gọi, không chỉ kiểm kết quả
- [ ] Quét **không** nằm trên đường render (`shown_result`)
- [ ] Nếu chọn A: backup DB xác minh restore được **trước** khi chạy revision
- [ ] Năm cổng xanh

## Risk Assessment

**Rủi ro lớn nhất: một cơ chế bảo mật fail-closed lọt vào.**
Tín hiệu: bất kỳ đường nào từ kết quả quét dẫn tới việc câu trả lời không đi.
Phản ứng: đây là điều kiện chặn merge, không phải điều chỉnh. Hermes nói thẳng
lớp này chấp nhận false-negative; một lớp cảnh báo giết được câu trả lời thì
tệ hơn không có lớp nào. Cùng lý lẽ đã giữ cổng vision ra khỏi `CapabilityProbe`.

**Rủi ro: regex catastrophic backtracking trên trang 20k ký tự.**
Tín hiệu: latency `fetch_url` tăng vọt.
Phản ứng: trần thời gian ở bước 5 là mitigation đã có sẵn. Ngoài ra: pattern
tránh nested quantifier; test có một trang 20k ký tự adversarial.

**Rủi ro: false positive làm rail đầy cảnh báo, người đọc mất tin.**
Tín hiệu: tỉ lệ `risk: high` trên corpus lành cao.
Phản ứng: đo trên toàn corpus golden **trước** khi bật hiển thị. Ngưỡng cụ thể
chốt ở phase 08 cùng các ngưỡng khác. Cờ ghi vào store từ đầu; hiển thị là một
công tắc riêng.

**Rủi ro: tập pattern thành nợ bảo trì.**
Nó sẽ là. Giảm thiểu: một file, mỗi pattern một comment, và **không** scope
`strict`. Tập nào phình quá một màn hình là tín hiệu đang giải sai bài.
