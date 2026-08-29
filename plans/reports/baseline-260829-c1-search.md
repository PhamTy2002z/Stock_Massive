# Baseline C1 — search & evidence, đo trước khi sửa

Nguồn số: `plans/reports/baseline-260829-c1-search.json` (authority máy đọc).
File này là chiếu người đọc của **cùng** bộ số — không thêm số nào.

- Đo lúc: 2026-08-29, `git_sha` ghi trong JSON
- Quần thể: **traffic organic** của lane chat trên DB `stockmassive`, mọi SQL kèm
  mệnh đề loại traffic golden (`users.email LIKE 'golden-runner%'`) ngay từ đầu,
  kể cả khi identity đó chưa tồn tại
- Không tốn tiền model, không gọi provider — đọc store

## Số

| Chỉ số | Giá trị | n | Cửa sổ |
|---|---|---|---|
| Turn có ≥2 `web_search` | **2/10** (20,0%) | 10 turn | hậu rip 2026-08-25 |
| Turn có ≥2 `web_search`, cả lịch sử | **21/43** (48,8%), max 5 | 43 turn | toàn bộ |
| **Round** có ≥2 `web_search`, cả lịch sử | **8/70** (11,4%), max 3 | 70 round | toàn bộ |
| `fetch_url`/Turn chạm web | **0,3** (3 call / 10 turn) | 10 turn | hậu rip |
| Turn có `fetch_url` ≥ 2 | **0/10** | 10 turn | hậu rip |
| `web_search` call | 12 | — | hậu rip |
| Latency `web_search` | mean 2.600 ms · p50 2.346 · max 4.843 | 12 | hậu rip |
| Latency `fetch_url` | mean 700 ms · p50 477 · max 1.198 | 3 | hậu rip |
| Domain khác nhau một `web_search` **trả về** | mean 4,50 · p50 5 · [1;5] | 76 call | toàn bộ |
| Domain khác nhau một Turn **trả về** | mean 5,70 · p50 5 · [4;10] | 10 turn | hậu rip |
| Payload search parse được | **77/81** dòng | 81 | toàn bộ |
| **Chi phí một Turn chạm web** | mean **42.002** µUSD ≈ **$0,042** · p50 34.447 · max 70.694 | 10 turn | hậu rip |
| Token một Turn chạm web | mean 14.178 in / 701 out, 3,60 lượt LLM | 10 turn | hậu rip |
| Chi phí một Turn mọi loại | mean 34.362 µUSD · p50 33.460 | 22 turn | hậu rip |
| Số ngoài store không có nguồn | **null** | — | xem dưới |

## Ba đính chính so với bảng "Bảy dữ kiện" của plan

**1. Tỉ lệ song song phụ thuộc đơn vị, và plan trích đơn vị rộng nhất.**
`request_message_id` là **một Turn**, không phải một round — một Turn chạy tới
`MAX_TOOL_ROUNDS = 4` round. Nhóm theo giây phát lệnh (proxy gần nhất cho một
lượt `asyncio.gather`) cho **8/70 round = 11,4%**, không phải 48,8%. Cơ chế
song song vẫn có thật và vẫn chạy; nhưng "gần một nửa" là con số đơn vị Turn.
Mọi lần trích tỉ lệ này phải kèm đơn vị.

**2. Chi phí một Turn là $0,042, không phải $0,021.**
Plan đọc **một** dòng `llm_call_usage` (9.337 in + 184 out = 20.514 µUSD). Một
Turn chạm web trung bình có **3,6** lượt LLM. Số đúng cho phép tính trần ở phase
04 là **42.002 µUSD/Turn**, max quan sát 70.694. Vẫn còn **~12× headroom** dưới
`TURN_COST_MICRO_USD = 500.000`, nên kết luận "ngân sách không phải rào cản"
không đổi — chỉ hệ số đổi.

**3. Con số hậu rip đã trôi từ lúc plan viết.** Plan ghi 8 `web_search` / 3
`fetch_url`; đo lại cùng ngày cho **12** / **3**. Khoảng cách tìm-so-đọc rộng
hơn plan viết, không hẹp hơn.

## Vì sao "số ngoài store không có nguồn" là `null`

Không phải thiếu persistence — mảng `results` **có** trong store (77/81 dòng
parse ra URL). Nó thiếu **định nghĩa**: "có nguồn" là một quan hệ giữa văn bản
câu trả lời và tập `display_results()` của chính Turn đó, và định nghĩa quan sát
được ấy do phase 02 chốt. Đo trước khi chốt định nghĩa là đúng lỗi đã giết bộ
eval cũ.

## Quần thể này KHÔNG phải mẫu so của phase 08

Phase 08 so với **artifact phase 02**. Số ở đây là bối cảnh: khác quần thể
(organic vs corpus web-first), khác đơn vị, và n=10 ở nhánh hậu rip.

## Dọn kèm phase này

- Năm target `eval-*` gọi `python -m src.eval` — module không còn — đã gỡ khỏi
  `apps/api/Makefile`
- `apps/api/src/eval/` (chỉ còn `__pycache__`) đã xoá khỏi disk
- Bảy dữ kiện sai sửa tại chỗ trong `docs/roadmap.md` và `CLAUDE.md`
