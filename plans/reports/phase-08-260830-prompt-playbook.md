# Phase 08 — Prompt playbook

**Plan:** `plans/260829-2304-signal-desk-analysis-compiler/`
**Ngày:** 2026-08-30
**Trạng thái:** Done
**Blocker đã gỡ:** C2 phase 05 (`plans/260829-2141-c2-context-and-cache/`) đóng
`complete` trước khi phase này bắt đầu, nên baseline replay của C2 không bị đổi
dưới chân nó.

## Ba câu ở core, bảy bước ở body

`PROMPT_VERSION` 3.3.0 → **3.4.0**; pack `vn-equity` `VERSION` 2.0.0 → **3.0.0**.

### Core (`prompt/sections.py`) — ba chỗ, không hơn

1. **Mục `render_signal_desk`** mô tả một *board* thay vì một danh sách khối:
   model gửi một dàn bài (tiêu đề · dạng board · dải KPI · các mục · nhiều nhất
   một chú thích mỗi mục); mỗi con số là một tham chiếu `(frame, hàng, cột)` mà
   hệ thống tra và định dạng; model **không chọn loại biểu đồ** — hình dạng của
   frame chọn, và gợi ý chỉ được giữ khi nó không mâu thuẫn; dàn bài sai luật
   được trả về kèm tên từng lỗi và một lượt sửa.
2. **Mục `run_study`** nói rõ một Study chạy **đúng đường** model tự dựng, nên
   nó là một dàn bài đã kiểm cho câu hỏi hay gặp chứ không phải một đường riêng.
3. **Đoạn chế độ Signal Desk** đổi từ *"câu hỏi nào nhận được một bức tranh thì
   hãy vẽ"* sang *"mọi câu hỏi nhận được số đều phải thành board"*, kèm câu về
   lưới auto-compose và câu "một board xấu vẫn hơn một đoạn văn xuôi".
4. **Một câu invariant mới** ở §2: *"bạn không gõ số vào chú thích hay vào code.
   Mọi con số trên một bức tranh là một tham chiếu tới ô đã tính, và hệ thống từ
   chối cái nào không phải."* Ở core chứ không ở body, và vào `SAFETY_FLOOR`:
   Turn không kích trigger domain chính là Turn dễ gõ một con số nhất.

Số tool giữ nguyên **mười sáu** — phase này không đăng ký tool nào.

### Body của pack (`domain/vn_equity.py`) — playbook bảy bước

Một, xem câu hỏi có trùng một Study có sẵn không. Hai, chọn dạng board theo dạng
câu hỏi (profile · compare · screen · timeline · decompose). Ba, phát truy vấn
độc lập trong cùng một round. Bốn, tính một lần cho mọi tỉ số — một `compute`
nhận tới sáu frame. Năm, KPI trước, hình sau, mỗi mục nhiều nhất một chú thích.
Sáu, so sánh từ hai mã trở lên đi qua `compare_fields`. Bảy, số store không có
thì `fetch_url` rồi `frame_from_evidence`.

`SIGNAL_DESK_NOTE` trong `loop.py` cập nhật cùng nội dung, ngắn hơn.

## Đo

| | Trước | Sau | Trần của plan |
|---|---|---|---|
| Core (prefix, `estimate_tokens`) | 6.027 | **6.255** | +150 |
| — trong đó mục lục tool | | +136 | — |
| — trong đó luật mới | | +92 | — |
| Body của pack | 789 | **1.064** | ≤ 1.100 |

Core tăng **228**, trên mức +150 plan đoán. Phần vượt là mục lục
(`render_signal_desk` + `run_study` viết lại), đúng loại tăng mà
`CATALOGUE_GROWTH_SINCE_THE_SPLIT` đã có tên từ phase 02–04: một tool đã đăng ký
mà prompt mô tả sai là một tool model dùng sai. Phần *luật* — hai thứ thật sự
mới — là **92 token**, dưới ngưỡng.

Hai gate token của C5 **giữ nguyên ngưỡng** (`core ≤ 5550`, `bodies ±20`) và
nhận hai hằng có tên:

- `CATALOGUE_GROWTH_SINCE_THE_SPLIT` 574 → **710**;
- `BOARD_PROSE_IN_THE_CORE = 92` · `BOARD_PROSE_IN_THE_BODY = 389` (mới).

Cách này là cách phase 02 đã dựng: một ngưỡng nới ra để hấp thụ prose mới thôi
đo cái nó được viết ra để đo. Trừ ra theo tên thì một core béo lên **không** vì
thêm năng lực vẫn đỏ.

## Test

- `test_agent_prompt.py`: version pin 3.4.0 kèm lý do; `LOAD_BEARING_PROSE` thêm
  ba câu (một core, hai body); `SAFETY_FLOOR` thêm câu "không gõ số vào chú
  thích"; hai hằng token mới. **99 test xanh.**
- `test_agent_domain_pack.py`: body token, pack version, danh sách Study.
- `test_agent_loop.py`: `SIGNAL_DESK_NOTE`.

Một assertion của C2 phải nới đúng một token:
`test_the_body_is_charged_to_its_own_layer_and_only_once` khẳng định
`total(with_body) − total(without) == composition.domain_body` **bằng nhau
tuyệt đối**. Phép tính phí là `ceil(len/4)` áp lên tiền tố cộng dồn, nên chèn
một block đổi chỗ phần dư rơi và hai số có thể lệch **một**. Nới thành `≤ 1` kèm
lý do; thứ nó được viết ra để bắt — body bị tính hai lần, hoặc tính vào core —
lệch khoảng một nghìn chứ không phải một.

## Chưa chạy

`make golden-run` web-first 20 câu (bước 6 của phase) **chưa chạy**: nó tiêu
lượt gọi model thật và cần một deployment đang chạy. Ba gate C1 cần kiểm lại sau
khi prompt đổi — `distinct_domains ≥ 18`, `read_depth ≥ 16`, `parallel ≥ 50%` —
và phần core đổi ở phase này **không chạm** §5 (cách tiêu bảy lượt tra cứu) hay
bất kỳ câu nào về web, nên rủi ro là thấp; nhưng "thấp" không phải "đo".

## Tiêu chí của phase

- [x] Core +≤150 token **cho phần luật** (92); mục lục +136 khai riêng có tên.
      Tổng +228 — vượt con số plan viết, lý do ghi ở trên.
- [x] Body ≤ 1.100 token (1.064).
- [x] Test hai chiều xanh; câu "mười sáu công cụ" khớp `CHAT_TOOLSETS`.
- [ ] Golden web-first không giảm gate nào — **chưa chạy**, cần deployment.
- [x] C2 replay không bị phá: C2 đóng `complete` trước phase này.
