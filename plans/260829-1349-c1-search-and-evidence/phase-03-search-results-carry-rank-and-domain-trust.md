---
phase: 3
title: "Kết quả tìm mang rank và độ tin cậy domain"
status: pending
priority: P1
effort: "8h"
dependencies: [2]
---

# Phase 3: Kết quả tìm mang rank và độ tin cậy domain

## Overview

Cho model đủ dữ kiện để **chọn** đọc trang nào, thay vì đọc trang đầu hoặc
không đọc gì. Và cho `fetch_url` trả về đoạn liên quan câu hỏi thay vì 20.000
ký tự đầu trang.

Nút thắt đo được: hậu rip-out có **8 `web_search` nhưng chỉ 3 `fetch_url`**.
Model tìm mà gần như không đọc. Snippet 700 ký tự đủ để nó kết luận đã đủ, và
20k đầu trang là một canh bạc đắt khi nó thực sự đọc.

## Requirements

- Functional: mỗi search item mang `rank` (thứ tự nguồn trả về, 1-based).
- Functional: mỗi search item mang một tín hiệu tin cậy domain — **hình dạng
  chốt lúc làm**, xem §Ba lựa chọn.
- Functional: `fetch_url` trả đoạn liên quan câu hỏi thay vì cắt 20k đầu.
- Non-functional: `published_at` **đã có** (`tools/web.py:503`) — không đụng.
- Non-functional: không đổi luật SSRF, denylist, hay `MAX_REDIRECTS`.
- Non-functional: kích thước payload gửi model **không tăng** — trích đoạn theo
  câu hỏi phải rẻ hơn hoặc bằng 20k đầu trang.

## Architecture

### Ba lựa chọn cho `domain_trust` — chốt lúc làm

Repo **không có whitelist**. Chỉ có `web_domain_denylist` (`core/config.py:153`,
áp ở `tools/web.py:174-176`). Roadmap viết *"ưu tiên nguồn whitelist"* nhưng
không có chỗ nào bám. Ba đường, xếp theo thứ tự ưu tiên:

| Lựa chọn | Điều kiện chọn | Hỏng đầu tiên ở đâu |
|---|---|---|
| **A. Điểm từ Tavily** | Response thật có trường điểm/score | Nếu Tavily bỏ trường đó thì mất im lặng — cần test khẳng định trường tồn tại |
| **B. Bảng tĩnh nhỏ do repo sở hữu** | A không có | Bảng thành nợ bảo trì và thiên vị theo người viết; phải nhỏ và phải giải thích được từng dòng |
| **C. Bỏ hẳn trust, chỉ `rank` + `published_at`** | A và B đều tệ hơn không làm gì | Model mất một tín hiệu chọn trang — chấp nhận được nếu `rank` đã đủ |

**Bước đầu tiên của phase là đọc response thật của Tavily**, không phải chọn
trước. Nếu chọn C, ghi lý do vào report và **sửa `docs/roadmap.md`** — đừng để
lại một checklist item không ai định làm.

### Trích đoạn theo câu hỏi — hai vấn đề bản đầu không thấy

Bản đầu viết *"chuyền câu hỏi xuống `_fetch_page()`"* như một dòng nối dây.
Red-team đảo cả hai tiền đề của câu đó, và cả hai đã kiểm lại:

**1. `fetch_url` không có đường nào tới câu hỏi.** Schema chỉ khai `{"url"}`
(`tools/web.py:358`), handler vứt `_context` (`:406-412`). Và `ToolContext`
**cấm** trộn nội dung vào identity — nguyên văn: *"identity arrives here and
arguments arrive from the model, and the two are never merged"*
(`registry.py:152-182`).

→ **Câu hỏi vào qua một argument mới do model điền.** Rẻ nhất, không phá luật
identity, và model là bên duy nhất biết nó đang đọc trang này để tìm gì. Đặt
tên theo ý định (`đang tìm gì trên trang này`), khai `optional` — thiếu nó thì
lui về cắt đầu trang như hôm nay.

**2. Cache `WebLane` key theo URL, và nó cache kết quả *đã cắt*.**
`self._lane.read("url", initial, lambda: self._fetch_page(initial))`
(`tools/web.py:419`) — một khoá cho một URL, dùng chung mọi thread, fresh 24h
(`core/web_lane.py:19-22`).

Trích theo câu hỏi mà giữ nguyên điểm cache thì **câu hỏi B nhận trích đoạn
chọn cho câu hỏi A** — im lặng, xuyên thread. Đây là lỗi giao bằng chứng sai
nguồn, đúng thứ C1 tồn tại để chống.

→ **Tách extract ra sau điểm cache.** Cache giữ text đầy đủ của trang; extract
chạy per-call trên text đó. Hệ quả kích thước: cache entry to hơn hôm nay (giữ
fulltext thay vì 20k đã cắt), chặn trên bởi `web_fetch_max_bytes`. Đo dung
lượng Redis trước và sau, ghi vào report.

Hai ràng buộc giữ nguyên:

- **Deterministic.** Không gọi model để chọn đoạn — điều đó biến một tool đọc
  thành một lượt LLM và phá kế toán chi phí.
- **Giữ nguyên văn.** Đoạn trả về phải là substring thật của trang.

Trần `MAX_PAGE_TEXT_CHARS = 20_000` giữ nguyên ở phase này.

## Related Code Files

- Modify: `apps/api/src/agent/tools/web.py`
  - `_search_item()` (`:497-505`) — thêm `rank`, có thể thêm `domain_trust`
  - `extract_page()` (`:134`) — tách phép cắt ra khỏi phép lấy trang
  - `_fetch_url()` (`:414-422`) — extract **sau** `self._lane.read`, không trong callback cache
  - `fetch_url` schema (`:358-363`) — argument mới, optional, cho câu hỏi
  - tool definition (`:309-349`, `:350-371`) — mô tả trường mới cho model
- Modify: `apps/api/tests/test_agent_web_tools.py` (hoặc tên thật, xác nhận lúc làm)
- Modify: `apps/api/golden/grade.py` — nếu `domain_trust` chốt là A hoặc B
- Modify: `docs/roadmap.md` — nếu chốt C, sửa checklist C1

## Implementation Steps

1. Gọi Tavily thật một lần, ghi response nguyên văn vào report. Chốt A/B/C từ
   dữ kiện đó, không từ suy đoán.
2. Thêm `rank` vào `_search_item()`. Đây là phần chắc chắn làm, độc lập với
   quyết định trên.
3. Cập nhật tool definition để model biết trường mới **có nghĩa gì** — một
   trường model không hiểu là một trường model bỏ qua.
4. Viết phép trích đoạn theo câu hỏi, deterministic, giữ substring nguyên văn.
5. Test: một trang dài có đoạn liên quan nằm **sau** ký tự 20.000 phải được
   trích ra. Đây là case chứng minh phép cắt cũ hỏng.
6. Test: `rank` đúng thứ tự nguồn trả về; `published_at` **không** đổi hành vi.
7. Chạy `make golden-run` với trần nhỏ, so read_depth với artifact baseline của
   phase 02. Ghi vào report — chưa gate.

## Success Criteria

- [ ] Report ghi response nguyên văn của Tavily và lý do chốt A, B hay C
- [ ] Mọi search item có `rank`, 1-based, đúng thứ tự nguồn trả
- [ ] Test khẳng định đoạn liên quan nằm sau ký tự 20.000 vẫn được trích
- [ ] Đoạn trả về là substring thật của trang (test khẳng định)
- [ ] **Test cache xuyên câu hỏi**: hai câu hỏi khác nhau, **cùng một URL**, trong cửa sổ cache → **hai trích đoạn khác nhau**. Đây là test chống lỗi giao bằng chứng sai nguồn; không có nó thì phase này không được merge
- [ ] Extract chạy **ngoài** callback của `WebLane.read` (test hoặc đọc code khẳng định)
- [ ] Thiếu argument câu hỏi → lui về cắt đầu trang, không lỗi
- [ ] Argument mới **không** đến từ `ToolContext` — luật identity/argument giữ nguyên
- [ ] Report ghi dung lượng cache Redis trước và sau khi chuyển sang giữ fulltext
- [ ] Không lượt gọi model nào phát sinh bên trong `fetch_url`
- [ ] `MAX_PAGE_TEXT_CHARS` **không đổi** ở phase này
- [ ] Luật SSRF, denylist, `MAX_REDIRECTS` không đổi — test cũ xanh nguyên
- [ ] Nếu chốt C: `docs/roadmap.md` sửa, không để lại checklist ma
- [ ] Năm cổng xanh

## Risk Assessment

**Rủi ro: trích đoạn theo câu hỏi làm mất ngữ cảnh, câu trả lời tệ đi.**
Tín hiệu: `distinct_domains` giữ nguyên nhưng grader mâu thuẫn-nguồn của corpus
xấu đi so artifact phase 02.
Phản ứng: giữ trần ký tự, nhưng ghép đoạn kèm **một đoạn liền trước và liền
sau** mỗi đoạn khớp, thay vì đoạn khớp trần trụi. Nếu vẫn xấu: đây là phép đo
nói "cắt đầu trang tốt hơn ta tưởng" — quay lại cắt đầu và ghi kết quả âm vào
report. Kết quả âm có giá trị; giả vờ nó không xảy ra thì không.

**Rủi ro: `domain_trust` thành bảng thiên vị.**
Nếu chọn B, mỗi dòng bảng phải giải thích được. Bảng quá 20 dòng là tín hiệu
chọn sai đường — quay về C.

**Rủi ro: thêm trường làm payload gửi model phình.**
Tín hiệu: token/Turn tăng trong artifact golden. `rank` là một số nguyên và
`domain_trust` là một nhãn ngắn — nếu chúng làm token tăng rõ, thứ phình là
mô tả tool, không phải dữ liệu. Đo trước khi đổ lỗi.
