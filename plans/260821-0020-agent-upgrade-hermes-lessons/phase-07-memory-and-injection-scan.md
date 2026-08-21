---
phase: 7
title: "Ký ức và quét injection"
status: pending
priority: P2
effort: "3-4d"
dependencies: [6]
---

# Phase 7: Ký ức và quét injection

## Overview

Hai việc độc lập, gộp vì cả hai chỉ có nghĩa **sau khi** base trả lời được:
ký ức xuyên phiên qua đường tool, và lớp quét pattern injection trên nội dung web.

## Requirements

- Functional: người dùng không phải kể lại danh mục theo dõi, khẩu vị rủi ro, hay
  kết luận phân tích cũ mỗi phiên.
- Functional: nội dung lấy từ web/publisher bị quét pattern injection trước khi
  vào transcript.
- Non-functional: **không** chèn free-text vào system prompt. Giữ
  `contract.py::_assert_no_formatting_hole` và `render()` chỉ nhận 5 giá trị typed.
- Non-functional: quét injection fail-OPEN — không chắc thì để qua kèm nhãn, không chặn.

## Architecture

### 7.1 Ký ức — qua tool, KHÔNG qua prompt

Hermes làm ngược ta: snapshot `MEMORY.md` (2.200 ký tự) + `USER.md` (1.375) đóng
băng vào tầng volatile của prompt, ghi giữa session xuống đĩa nhưng không mutate
prompt đã dựng cho tới compaction.

**Ta không port khuôn đó.** Lý do đã xác minh: `contract.py::_assert_no_formatting_hole`
cấm mọi free-text vào prompt, `render()` chỉ nhận 5 giá trị typed. Docstring của
nó nói rõ đó là chủ đích: *"There is no string field, so there is no hole a figure,
a Watchlist entry, a tool result or user prose could be poured into."*

Đó là hàng rào chống injection **mạnh hơn** Hermes — Hermes phải bù bằng
`_scan_context_content` quét injection trên mọi file context nó nạp. Giữ hàng rào.

Đường đi đúng: mở rộng tool đã có trong `tools/knowledge.py`
(`remember_fact` / `recall_facts`) và bảng `agent_knowledge` đã tồn tại.

| Thứ cần nhớ | Nguồn |
|---|---|
| Danh mục theo dõi | `watchlist_entries` (đã có bảng) |
| Khẩu vị rủi ro, chân trời đầu tư | fact do người dùng nói |
| Mã hay hỏi | dẫn từ `agent_message` |
| Kết luận phân tích cũ | fact + tham chiếu Turn |

`agent_knowledge.user_id` cho phép NULL → đã có chỗ cho fact toàn cục. Thread
thuộc một user (`AgentThread.user_id`, `AgentMessage` cố ý không có `user_id`) →
không có khái niệm thread đa user, nên câu hỏi riêng tư đã có đáp.

Contract cần **một** câu (không phải free-text data, chỉ là hướng dẫn ổn định)
dạy model chủ động gọi `recall_facts` khi người dùng nhắc tới chuyện phiên trước
— mẫu Hermes: *"use session_search to recall it before asking them to repeat
themselves."*

### 7.2 Tìm kiếm phiên cũ

Hermes: FTS5, **4 mode suy từ args, không có tham số mode**, zero LLM cost — họ
cố tình bỏ nhánh LLM-summary (PR #20238 → #26419).

Ta trên Postgres: full-text search trên `agent_message`. Bài học chuyển được:
**không gọi LLM để tóm tắt trong đường tìm kiếm** — mỗi lần gọi là một lần đắt và
một lần có thể sai. Và tokenizer mặc định thất bại với chữ không phải Latin;
Hermes phải bật trigram cho CJK. Với tiếng Việt có dấu, cấu hình mặc định của
Postgres sẽ âm thầm không khớp — phải chọn config rõ ràng.

Một tool, các mode suy từ args: `query` → tìm; `thread_id` + `anchor` → cửa sổ
quanh điểm neo; `thread_id` → cả thread; không args → thread gần đây.

### 7.3 Quét pattern injection

Ta **đã có 4 lớp**, đã xác minh — nên phase này chỉ thêm lớp thứ năm:

| Lớp | Ở đâu | Có |
|---|---|---|
| Nhãn untrusted trong kết quả tool | `web.py:1,191,211` | ✅ |
| Whitelist nguồn + lọc thời gian | `news.py:172,196` | ✅ |
| Trích visible-text có cap | `_html.py` | ✅ |
| Contract dạy coi là dữ liệu không phải chỉ thị | `sections.py:105-109` | ✅ |
| **Quét pattern injection** | — | ❌ |

Mẫu `threat_patterns.py` — *"single source of truth for prompt-injection /
promptware"*. Các lớp pattern cần: unicode vô hình / zero-width, "ignore previous
instructions" và biến thể, mưu toan rút credential, chỉ thị giả dạng system.

Quan trọng: **fail-open**. Trúng pattern thì **gắn nhãn và ghi log**, không chặn
câu trả lời. Nội dung web đã bị Contract coi là dữ liệu; nhãn thêm là phòng thủ
theo lớp, không phải cổng. Chặn nội dung web là quay lại đúng sai lầm đã sửa ở
Phase 2.

Đối chiếu: bộ eval của ta đã có check `injection_hold` và `prompt_disclosure` —
tức đã có bài kiểm, chỉ chưa có lớp phòng thủ tương ứng.

Ta **không** cần port SSRF: `web.py` đã có socket ghim DNS, `is_global` mọi địa
chỉ, kiểm lại từng hop redirect — chắc hơn Hermes.

## Related Code Files

- Modify: `apps/api/src/agent/tools/knowledge.py` — nới `remember_fact`/`recall_facts`
- Create: `apps/api/src/agent/tools/session_search.py` — một tool, mode suy từ args
- Create: `apps/api/src/agent/tools/threat_patterns.py` — thư viện pattern, hàm thuần
- Modify: `apps/api/src/agent/tools/web.py`, `news.py` — gọi quét, gắn nhãn
- Modify: `apps/api/src/agent/prompt/sections.py` — một câu dạy dùng `recall_facts`
- Modify: `apps/api/alembic/versions/` — index full-text trên `agent_message`
- Modify: `apps/api/src/agent/ops.py` — đếm số lần trúng pattern

## Implementation Steps

1. **Backup DB** trước migration index.
2. `threat_patterns.py`: hàm thuần, không I/O, có test cho từng lớp pattern.
   Gắn nhãn + log, **không** chặn.
3. Nối vào `web.py` và `news.py`; `ops.py` đếm.
4. Nới `remember_fact`/`recall_facts`: loại fact, thời hạn, nguồn (người dùng nói
   vs hệ thống dẫn).
5. Migration index full-text, **chọn text search config rõ ràng cho tiếng Việt**,
   không dùng mặc định.
6. `session_search.py`: mode suy từ args, **không gọi LLM**.
7. Một câu vào Contract dạy dùng `recall_facts`; bump version. **Eval Report**.
8. `make test`.

## Success Criteria

- [ ] DB đã backup trước migration
- [ ] Trang publisher chứa "ignore previous instructions" → bị gắn nhãn, ghi log,
      và câu trả lời **vẫn** ra bình thường
- [ ] Unicode zero-width bị phát hiện
- [ ] Quét fail-open: pattern lỗi/không chắc → nội dung vẫn qua (test)
- [ ] `recall_facts` trả đúng fact của user đó; fact toàn cục (`user_id` NULL) dùng chung
- [ ] `session_search` không gọi LLM (test đếm số lời gọi = 0)
- [ ] Tìm kiếm khớp được câu tiếng Việt có dấu (test có "cổ phiếu", "tăng trưởng")
- [ ] Hỏi lại chuyện phiên trước → model tự gọi `recall_facts`, không bắt kể lại
- [ ] `prompt/contract.py` vẫn chỉ nhận 5 giá trị typed — bất biến không đổi (test)
- [ ] `make test` xanh + Eval Report

## Risk Assessment

**Rủi ro**: quét pattern dương tính giả trên tin tài chính bình thường ("bỏ qua
khuyến nghị trước đó" là câu hợp lệ trong bản tin). **Tín hiệu**: tỉ lệ trúng
pattern cao bất thường. **Phản ứng**: vì fail-open nên hậu quả chỉ là nhãn sai,
không phải câu trả lời mất — đó là lý do chọn fail-open. Siết pattern sau.

**Rủi ro**: text search config tiếng Việt chọn sai → tìm kiếm im lặng không khớp.
**Tín hiệu**: `session_search` luôn trả rỗng. **Phản ứng**: test có dấu là điều
kiện nghiệm thu, không phải khuyến nghị.

**Rủi ro**: ký ức nhớ sai rồi khẳng định như thật ở phiên sau. **Tín hiệu**: người
dùng phản hồi. **Phản ứng**: fact mang nguồn và thời điểm; model phải nêu "theo
ghi nhận trước đó" chứ không nêu như dữ liệu store.

**Assumption có thể vỡ**: giả định người dùng muốn agent nhớ. Nếu chủ sản phẩm
thấy nhớ sai tệ hơn không nhớ, cắt 7.1/7.2 và giữ 7.3.

## Rollback

Mỗi mục một cờ. Index migration là thuần cộng thêm, drop được.
