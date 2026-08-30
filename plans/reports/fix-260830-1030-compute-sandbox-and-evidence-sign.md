# Hai blocker của review phase 03–04 — đã vá và đo lại

`plans/260829-2304-signal-desk-analysis-compiler` · 2026-08-30 · `develop`
(chưa commit)

## Tình trạng

| Blocker | Trước | Sau |
|---|---|---|
| Thoát sandbox `compute` | tái hiện được, chạy lệnh + đọc `/etc/passwd` với quyền root trong `stockmassive-api:latest` | 12/12 đường thoát đóng, đo lại trong chính image đó |
| `frame_from_evidence` nhận sai dấu | trang in **lãi** 1.234 tỷ xác nhận claim **lỗ** 1.234 tỷ | không còn `MATCHED`; trả `AMBIGUOUS` |

Năm cổng xanh: `make test` **2.101 passed** (+11) · `make lint` · `pnpm
type-check/lint/test` (885) .

## Blocker 2 — dấu của số

`numbers.py` so bằng trị tuyệt đối ở cả hai vế (`wanted = target.copy_abs()`, và
`_NUMBER` không bắt dấu trừ). Dấu là **chữ số có hệ quả lớn nhất** trong một con
số tài chính — lãi/lỗ, tăng/giảm — và là thứ người đọc không suy lại được từ
phần còn lại của câu.

Đã sửa: `Occurrence.written`/`scaled` mang dấu trang in. Ba cách viết được đọc:

- `-12,4` (dấu trừ, và `−` của nhà in);
- `(1.234)` — quy ước kế toán, đúng thứ BCTC Việt Nam dùng;
- `100-200` **không** phải số âm — chốt chặn là ký tự trước dấu trừ: một chữ số
  nghĩa là khoảng, thứ khác nghĩa là dấu.

Chữ số có trên trang mà dấu không có → `AMBIGUOUS`, không phải `NOT_ON_PAGE`:
"trang không in số này" và "trang in các chữ số này chứ không in dấu này" là hai
sự thật khác nhau, và người đọc nghe cái thứ hai thì mở trang ra kiểm được.

**Test cũ không thể đỏ.** `test_a_negative_value_matches_the_number_the_page_printed`
khẳng định trang in `-12,4` khớp claim `-12.4` — đúng dù có đọc dấu hay không.
Giữ nguyên nó, thêm 5 test chỉ pass được một chiều.

## Blocker 1 — thoát sandbox

**Nguyên nhân:** validator suy luận về *import*, còn pandas/numpy phát ra module
thật dưới dạng attribute thường. `pd.io.common.os` **là** `sys.modules['os']`.
Không có chữ `import` nào để đọc, nên validator báo 0 vi phạm.

**Chỗ vá là tiến trình con, không phải AST.** Bề mặt attribute của một module
singleton là vô hạn — nên câu trả lời không phải danh sách tên dài hơn. Nó là:
trong tiến trình chỉ có **một** đối tượng `os`, gỡ lời gọi nguy hiểm khỏi chính
nó là đóng mọi đường tới nó cùng lúc, kể cả đường chưa ai tìm ra và đường bản
pandas sau sẽ thêm.

Bốn tầng, xếp theo **năng lực** chứ không theo tên module:

| Năng lực | Đóng ở |
|---|---|
| Sinh tiến trình | `os`/`posix`/`nt` (spawn/exec/system/popen), `subprocess` |
| Nạp mã máy | `ctypes` |
| Với tới đối tượng ngoài tầm | `sys._getframe/settrace/setprofile`, `gc.get_objects/get_referrers/get_referents` |
| Giải tuần tự thành lời gọi | `pickle.load/loads/Unpickler` |

Mở file thì **thu hẹp** chứ không chặn (`_SOURCE_ONLY`: chỉ `.py/.pyc/.so`), vì
máy import là một người đọc file hợp pháp. Cái còn với tới được qua đó là mã
Python trên đĩa — không phải bí mật; cái hết với tới được là mọi file là bí mật.

Cổng import thứ ba bọc `builtins.__import__` và `importlib.import_module` **thật**
với một denylist các module *năng lực thô* chưa nạp (`_posixsubprocess`, `_socket`,
`ctypes`, `mmap`, …) — module chưa nạp thì không có đối tượng nào để vô hiệu.

Con **hạ quyền xuống nobody** sau khi import xong. Đo trong container:
`uid=65534`, `limitsApplied` có `privileges`, `/proc/1/environ` — nơi
`DATABASE_URL` và khoá provider sống — không đọc được nữa.

### Ba thứ cố ý để nguyên, và cả ba đều đo trước khi để

`builtins.exec`, `builtins.compile`, `marshal.loads`. Cả ba là đường máy import
nạp một module: đóng chúng là đóng chính pandas. `np.rec` được nạp ở lần
`pct_change` **đầu tiên** của một Turn, nên mọi bản hardening đầu tiên đều làm
gãy `pct_change`, `describe`, `rank`, `groupby`. Chúng không phải lỗ hổng: thứ
`exec` với tới vẫn nằm trong bảng, và `marshal` trả về code object — trơ cho tới
khi có thứ chạy nó.

Đối xứng, `posix`, `_io`, `_thread`, `signal`, `resource` **không** vào denylist
dù là năng lực: interpreter nạp cả năm trước dòng đầu tiên của tiến trình, nên
bảng vô hiệu đã phủ chúng — và chặn import của chúng làm gãy việc lành
(`numpy.rec` import `_io`).

### Đo lại

12 đường thoát (`os.popen`, `os.open`+`read`, `posix.open`, `builtins.open`,
`sys._getframe`, `gc.get_objects`, `ctypes.CDLL`, `subprocess.run`, `pickle.loads`,
`importlib.import_module('_posixsubprocess')`, và `exec` **có tiêm builtins thật**
tới cả `import os` lẫn `open`) → **tất cả ok=False**, thông điệp model đọc được.

9 phép tính lành (`assign`, `pct_change`, `describe`, `to_datetime`, `resample`,
`np.log`, `rank+sort`, `groupby agg`, `corr`) → **tất cả ok=True**.

Cùng ma trận chạy lại trong `stockmassive-api:latest` bằng root: kết quả y hệt,
cộng `privileges` trong `limitsApplied`.

### Lớp validator vẫn thêm, nhưng đúng vai

`ESCAPE_ATTRIBUTES` cho model một câu tiếng Việt **trước khi chạy** thay vì một
`PermissionError` từ thư viện nó không biết mình đang gọi. Đây là **thiết bị đọc
được**, không phải ranh giới — file tự nói ra điều đó.

## Đây là hardening có đo, không phải chứng minh

Ranh giới đầy đủ là một hộp OS. Phần không cần dependency mới đã làm: hạ quyền
trong con. Phần **chưa** làm và nên làm, ở tầng compose:

- `user:` non-root cho service `api`;
- `cap_drop: [ALL]` + `security_opt: [no-new-privileges:true]`;
- `read_only: true` cho rootfs (cần kiểm alembic/log trước).

Không làm trong lượt này vì cần dựng cả stack để nghiệm thu, và stack của bạn
đang chạy. Đây là khuyến nghị, không phải việc đã xong.

## File đã sửa

- `src/agent/evidence/numbers.py` — dấu.
- `src/studies/compute/worker.py` — 4 tầng vô hiệu, thu hẹp mở file, cổng import
  thứ ba, hạ quyền.
- `src/studies/compute/validator.py` — `ESCAPE_ATTRIBUTES` (refusal đọc được).
- `tests/studies/test_compute_runner.py` — 6 test hồi quy, PoC viết y nguyên.
- `tests/test_evidence_numbers.py` — 5 test dấu chỉ pass được một chiều.
- `CLAUDE.md` — hai đoạn bị thay đổi này làm sai sự thật.

## Chưa xử lý (không phải blocker, từ cùng review)

- **#3** `MAX_COMPUTE_PER_TURN` đếm frame *đã lưu*, nên một calculation bị từ chối
  là miễn phí; `frame_from_evidence` không có trần per-Turn nào.
- **#4** `_page_read_this_turn`: `dedup_key("asdf") == ""` làm bộ lọc URL bị bỏ
  qua, và trang fetch gần nhất bị dùng + trích dẫn thay.
- **#5** ba đường literal còn mở (`len` của chuỗi, ép kiểu gián tiếp,
  `pd.Timedelta('37 days').days`); prose "AST enforces" nên hạ giọng.
- **#6** số web mất nhãn `web` khi đi qua `compute`.
- **#7** `columnRanges` trao model giá trị ô chính xác trên kết quả một hàng.

## Câu chưa chốt

1. Có muốn tôi làm phần compose (non-root + `cap_drop`) và nghiệm thu bằng cách
   dựng stack không?
2. Năm mục medium ở trên — làm luôn, hay để sau phase 07?
