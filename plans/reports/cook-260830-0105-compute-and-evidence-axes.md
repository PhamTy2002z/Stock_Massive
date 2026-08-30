# Phase 03 + 04 — trục phép tính và trục bằng chứng

**Ngày:** 2026-08-30 · **Plan:** `260829-2304-signal-desk-analysis-compiler`
**Nhánh:** `develop`, chưa commit · **Cổng:** `make test` **1930 passed** ·
năm cổng web xanh (837 test).

## Cái gì đã đi từ đâu tới đâu

Trước: một câu hỏi phân tích ra board khi có đúng một Study viết sẵn cho nó, và
mọi con số phải là thứ store đọc thẳng ra được. Sau: model **soạn phép tính**
trên các frame nó đã lấy (`compute`), và **chép được số từ một trang web** với
điều kiện server tìm thấy số đó trên trang (`frame_from_evidence`). Hai trục
độc lập của cùng một compiler; trục thứ ba — trình bày — là phase 05.

Lane chat đi từ 14 lên **16 tool**.

## Trục phép tính — tại sao là code chứ không phải một enum

Một danh sách đóng các phép (`yoy`, `share_of_total`, `rank`) là chính sai lầm
của "thêm Study tới ≥10", làm ở tầng thấp hơn: nó đoán câu hỏi trước, và trả
lời câu thứ mười một bằng văn xuôi. Nên phép tính là **code**, viết theo từng
câu hỏi, trên frame.

Điều đó dồn toàn bộ sức nặng lên một bất biến: **model không bao giờ gõ một con
số thị trường**. Với enum thì đúng theo cấu tạo; với code tự do thì phải đúng
theo **kiểm tra**, và đó là `studies/compute/validator.py`. Số cấu trúc được
viết thẳng: `0–12` (vị trí, đếm nhỏ, mười hai tháng) · `100` (một tỉ lệ thành
phần trăm) · `252` (phiên một năm) · `365` · `1e3`/`1e6`/`1e9` (nghìn/triệu/tỷ).
Ngoài đó, mọi literal số là một **figure**, và một figure phải khai ở
`constants` kèm lý do — lý do được ghi vào artifact, nên người đọc thấy nó được
*nêu ra* chứ không tìm thấy nó bên trong một biểu thức.

`rolling(20)` bị từ chối; `head(50)`, `round(3)`, `iloc[:, 37]` thì không. Ranh
giới là **vị trí và độ chính xác** so với **phán đoán về thị trường**.

## Hộp chạy, và ba trần trong đó chỉ hai chạy khắp nơi

`RLIMIT_CPU` (5 s) và `RLIMIT_FSIZE` (0) áp được ở mọi nền. `RLIMIT_AS`
(512 MB) **chỉ Linux** — macOS trả thẳng `ValueError`. Nên `_apply_limits` trả
về danh sách trần *thật sự* áp được, và đồng hồ của tiến trình cha là sàn ở mọi
nền. Test khẳng định một cấp phát khổng lồ chết bằng **một mã có tên**, không
khẳng định *mã nào*: trên máy dev nó là đồng hồ, trong container là bộ nhớ. Một
test giấu khác biệt đó sẽ nói với người đọc rằng laptop có hộp của container.

512 MB là số đo, không phải số tròn: image này sau khi import pandas + numpy
chiếm **195 MB** address space.

Ba thứ xảy ra trước khi code của model chạy, và thứ tự là quan trọng: đặt trần
→ **đóng mạng** → **dời stdout**. Mạng phải đóng dù validator đã cấm
`import socket`, vì `pd` đã ở trong namespace và pandas đọc được URL. Stdout
phải dời vì stdout **là** giao thức, và cấm `print` rồi hy vọng không có đường
thứ hai là sai hình dạng — `f0.info()` ghi thẳng ra đó.

## Trục bằng chứng — luật của C1 học lại một lần nữa

C1 đã đo và bỏ phép "witness suy diễn": một trang 200 số đỡ được gần như mọi
số dưới bốn phép tính, nên một checker cho phép **suy diễn** nhận số bịa gần
bằng tỉ lệ nó nhận sự thật (`plans/260829-1945-c1-evidence-graduation`). Nên ở
đây **không suy diễn gì**. Một giá trị khớp khi nó **in trên trang** — như trang
viết, hoặc như từ chỉ hệ số bên cạnh nhân nó lên.

Ba nhánh, và nhánh thứ ba là thứ chặn trùng hợp: số dưới **3 chữ số nghĩa** chỉ
được nhận khi **đơn vị của chính hàng đó** in ngay sau nó. `5` có trên mọi trang
từng xuất bản; nhận nó không đơn vị là nhận một trùng hợp làm trích dẫn. Không
nhánh nào khớp mà số có mặt → `evidence_number_ambiguous`; không có mặt →
`evidence_number_not_on_page`. Hai sự thật khác nhau, hai refusal khác nhau.

Trang được đọc lại từ **Tool Call Trace**, không fetch lại: trace giữ đúng thứ
model đã thấy, và một lần fetch thứ hai có thể trả về trang khác — rồi phép
kiểm sẽ kiểm một trang mà câu trả lời không được viết từ đó.

## Sáu chỗ code thật khác plan, và tại sao

1. **Role của so sánh là `cell_roles`, không `point_roles`.** Plan viết
   `point_roles`. Một bảng mã × chỉ tiêu có mã thắng theo **cột**;
   `point_roles` sẽ nói cả *hàng* thắng — đúng câu mà một so sánh sinh ra để
   tránh. Luật ba mức đã viết ra ở `studies/contracts.py` từ trước.
2. **`__import__` phải có, được bọc.** Bản đầu bỏ nó khỏi builtins an toàn, và
   `import math` — thứ validator **cho phép** — chết lúc chạy. Hai cổng phải nói
   cùng một câu; một test giữ đẳng thức.
3. **`socket.socket` bị thay bằng một class, không phải một hàm.** Hàm vẫn chặn
   được kết nối, nhưng refusal ra thành `TypeError` về kiểu đối số — model không
   đọc được gì để sửa.
4. **Index đếm bị bỏ, không chỉ `RangeIndex`.** `pd.concat` sinh Int64Index
   trùng lặp không tên; giữ nó thành một cột số 0 đứng trước con số đầu tiên.
5. **`preexec_fn` không dùng.** Handler chạy trong `asyncio.to_thread` của
   server đa luồng; `preexec_fn` giữa `fork` và `exec` ở đó deadlock được. Con
   tự đặt trần, dòng đầu, trước khi import gì.
6. **Traceback lọc theo frame, không theo dòng.** Bản đầu bỏ dòng `File …`
   nhưng giữ dòng code dưới nó, nên nội tạng của worker lọt vào refusal.

## Đo được

| | |
|---|---|
| 20 phép tính mẫu | 20/20 đúng **kết quả số**, không chỉ `ok` |
| p50 / p95 | **0,261 s** / 0,271 s (macOS, pandas 2.3.3, numpy 2.2.6) |
| Escape test | 6 đường, mỗi đường một mã có tên |
| Bảng số của `numbers.py` | **58 case** (21 tách dấu · 11 chữ số nghĩa · 8 hệ số · 18 verdict) |
| Test mới | 26 + 40 + 18 + 58 + 17 = **159** |
| `make test` | **1935 passed** (từ 1776) |
| Cổng web | type-check · lint · 837 test · build — xanh |
| Dependency mới | **0** |
| File `src/stocks/*` chạm | **0** |

## Hai lỗ tự tìm ra, đóng trước review

`_positions_that_are_not_figures` miễn trừ **mọi** hằng dưới một `Subscript`,
nên `f0[f0['roe'] > 0.05]` đi lọt — một *bộ lọc* đội lốt chỉ số, và là cách tự
nhiên nhất để viết một ngưỡng. Giờ chỉ **vị trí thật** được miễn: chỉ số, biên
`Slice`, tuple của chúng. Lỗ hai: `float('0.07')` đọc đúng như gõ `0.07`, nên
chuỗi giao cho một lời gọi ép kiểu số được đọc là con số nó sắp thành — chỉ ở
vị trí đó, vì chuỗi trông như số ở chỗ khác là một **nhãn**.

Và validator **không phải một chứng minh**: `7 / 100` là hai số cấu trúc và
cũng là `0.07`. Số học trên tập cấu trúc với tới mọi số. Thứ đóng lại là mọi
đường **hiển nhiên**, mỗi đường một tên. Điều đó viết trong docstring của
validator và có một test khẳng định nó, để không ai phát hiện nó như một bất ngờ.

## Còn mở

- Đọc **file** từ trong sandbox chỉ chặn ở validator (`open`, `pd.read_*` bị
  cấm theo tên/hình dạng), không chặn ở tầng OS: `RLIMIT_FSIZE = 0` chặn ghi,
  không chặn đọc. Đúng thiết kế plan khai ("AST allowlist + subprocess không
  mạng + rlimit"), nhưng nó là hàng rào **một lớp** trong khi mạng có hai.
- `frame_from_evidence` giữ đúng hai cột `label, value` như plan khai, nên một
  bảng lẫn đơn vị mất đơn vị của từng hàng (`frame.unit` chỉ đặt khi mọi hàng
  đồng ý). Nếu phase 06 thấy điều đó vỡ trên board thì đó là một dòng amendment,
  không phải một sửa lặng.
- Badge `source="web"` mới xong ở backend; vẽ nó là phase 06.
