# Playbook nạp theo intent — báo cáo thi công

## Sửa gì

- `src/agent/domain/pack.py`
  - `DomainPack` nhận thêm ba trường khai báo: `symbol_shape` (regex source, không
    phải pattern đã compile — pack vẫn là bản khai bằng chuỗi), `topic_markers`,
    `off_topic_markers`. `__post_init__` compile `symbol_shape` một lần để một pack
    có shape hỏng chết lúc import chứ không chết lúc phục vụ.
  - Thêm `DomainPack.body_reason(question) -> (bool, reason)` — trả cả lý do, cùng
    hình dạng `lanes.route_reason`. Thuần: không đồng hồ, không settings, không store.
  - Hằng `BODY_DEFAULT_REASON = "default"`.
- `src/agent/domain/vn_equity.py`: `SYMBOL_SHAPE`, `TOPIC_MARKERS`,
  `OFF_TOPIC_MARKERS` + gắn vào `PACK`. **Không chạm prose, không bump `VERSION`** —
  từ vựng không đi vào `body_text` nên `identity` không đổi, prefix cache không bị void.
- `src/agent/loop.py`
  - `domain_body_reason(question, lane)`: lane `deep` → nạp (`lane:deep`); còn lại hỏi
    pack. Không có heuristic domain nào nằm trong loop.
  - `state.domain_body = True` (vô điều kiện) → `state.domain_body, body_reason =
    domain_body_reason(request.user_text, self._lane)`, đặt ngay đầu `_run` cạnh
    `render()` và trước part `lane_selected`. Ghi `logger.info` **chỉ khi bỏ pack**
    (nạp là chuyện thường, bỏ mới là quyết định đọc ngược lại được từ câu trả lời).
  - Comment `_TurnState.domain_body` đổi từ "sticky once true" (mô tả một trigger đã
    chết) sang "viết một lần trước call đầu".

## Tín hiệu intent — chọn thế nào và vì sao

Thứ tự cố định, first-match, và thứ tự **là** chính sách:

1. `lane == deep` → nạp. Turn được cấp 10 round bằng chứng đã được router đọc là yêu
   cầu memo; trong deployment này memo là về thị trường, và ~680 token là số lẻ so với
   thứ lane đó được phép tiêu.
2. `symbol_shape` khớp (khớp trên **văn bản gốc**, chữ hoa mang nghĩa) → nạp.
   `(?<![0-9A-Za-z])[A-Z][A-Z0-9]{2,7}(?![0-9A-Za-z])` phủ `VNM`, `VN30`, `VN30F1M`,
   `E1VFVN30`, `HOSE`, `UPCOM` bằng một shape thay vì một bảng mã — bảng mã là một phụ
   thuộc market-data, module này không có. Nó over-match (`USD`, `CEO`, `PDF`) và đó là
   hướng sai đúng.
3. `topic_markers` khớp (casefold, substring, không gỡ dấu — giống `lanes.py`) → nạp.
4. `off_topic_markers` khớp → **bỏ**. Đây là bằng chứng duy nhất đủ mạnh để bỏ pack, và
   chỉ được xét khi (2)(3) không nhận. Nên "cách bạn hoạt động khi tôi hỏi về cổ phiếu"
   vẫn nạp, còn "bạn là ai" thì không.
5. Còn lại → nạp, `default`.

Vì sao đặt ở pack chứ không ở loop: ticker viết thế nào, người đọc gọi thị trường bằng
từ gì — đều là fact của domain. Loop giữ đúng nửa thuộc về Turn (lane).

Vì sao **không** dùng `symbols.py`: file đó chỉ có `normalize_symbol` (chuẩn hoá một mã
đã biết ở tầng transport), không có nhận diện trong câu; nhét từ vựng domain vào đó là
đặt tri thức domain sai chỗ. `symbols.py` không đổi một dòng.

## Điều kiện cache

Thứ tự khối đúng như mô tả — `messages.py:1324-1328` dựng `SYSTEM_CORE →
DOMAIN_BODY → SYSTEM_DYNAMIC` trong **một** system message, `SYSTEM_CORE` là tiền tố
chung. Không đảo gì. Ghim bằng test byte-level: hai Turn (có/không body) so bằng
`os.path.commonprefix` trên nội dung message[0], `len(shared) >= len(prompt_prefix())`.

## Test trước/sau

- Trước: `pytest -q` → **1295 passed**.
- Sau: `pytest -q` → **1308 passed, 3 deselected** (39s). +13 test.
- `compileall -q apps/api/src apps/api/tests` sạch; `git diff --check` sạch.
- Mới trong `tests/test_agent_domain_pack.py` (7): nhận symbol/topic; chỉ câu về chính
  assistant mới bị bỏ; câu mơ hồ và câu rỗng vẫn nạp; domain thắng off-topic khi cả hai
  cùng có; reason luôn gọi tên marker khai báo đầu tiên qua 3 lần gọi; shape hỏng bị từ
  chối lúc khai báo; từ vựng **không** đi vào `identity`.
- Mới trong `tests/test_agent_loop.py` (6): "Bạn là ai?" → 0 body; "VCB có gì mới?" →
  1 body; lane `deep` nạp bất kể câu hỏi; Turn bắt đầu không body thì round sau vẫn
  không body (quyết một lần); `domain_body_reason` tất định trên 3 vòng lặp; core
  byte-identical giữa hai trường hợp.
- **Sửa hai test hoá thạch** (không làm yếu): `test_a_thread_whose_last_turn_stayed_
  outside_the_domain_does_not` và `test_a_thread_that_only_read_the_web_does_not_bring_
  the_body` có tên nói "does not" nhưng assert `[1]`, docstring mô tả "trigger three" /
  "looks one Turn back" — cơ chế đã chết từ khi cờ thành vô điều kiện. Nay đổi tên và
  docstring cho khớp hành vi thật: câu "Cảm ơn." cuối một thread domain → `[0]`; câu
  "Còn gì nữa không?" (mơ hồ) → `[1]`. Docstring của
  `test_a_follow_up_in_a_thread_that_touched_the_domain_starts_with_it` cũng bỏ tham
  chiếu tới trigger đã chết; assertion giữ nguyên `[1]` (giờ vì ticker trong câu).

## Câu hỏi mở

1. **`state.cache_identity` chưa phân biệt hai đầu prompt.** `loop.py:1233` vẫn ghép
   `active_pack().identity` vô điều kiện, nên một Turn không nạp body mang cùng key với
   Turn có nạp — trong khi docstring `cache_key` nói rõ "hai Turn cùng model cùng tool
   dưới hai pack khác nhau **không** là cùng prompt". Chưa sửa vì: (a) prompt caching
   đang OFF và key không lên wire, route cache theo bytes tiền tố thật; (b) sửa nó là
   quyết định thuộc phase sở hữu cache boundary; (c) test
   `test_nothing_about_one_turn_reaches_the_identity_of_its_head` nói key không được
   mang thứ suy từ câu hỏi. Nếu bật `llm_prompt_cache_control_enabled`, đây là chỗ phải
   xử lý trước.
2. **Progress không nói pack.** Allowlist `parts.py:132` cho `lane_selected` là
   `("lane", "reason")`; thêm khoá `pack` phải sửa `parts.py`, ngoài quyền sở hữu file
   của việc này. Task ghi mục này là tuỳ chọn nên bỏ. Nếu muốn, chi phí là một khoá
   trong allowlist + payload.
3. **`golden/context_replay.py:375` hard-code `system_body=pack.body_text`.** Replay vì
   vậy luôn tính body kể cả với câu off-topic, tức số composition của replay là cận
   trên. Ngoài quyền sở hữu; đáng đồng bộ ở việc 5 nếu muốn số trước/sau khớp production.
4. **Từ vựng chưa được đo trên corpus thật.** Bộ marker chọn theo lý lẽ, không theo tần
   suất câu hỏi thật. Hướng sai đã chọn là an toàn (mơ hồ → nạp), nhưng "bao nhiêu %
   Turn thật sự bỏ body" chỉ trả lời được bằng log của trường `off_topic:*`.
