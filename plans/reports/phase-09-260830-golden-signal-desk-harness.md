# Phase 09 — bộ đo `signal_desk` dựng xong, corpus chưa mở

**Ngày:** 2026-08-30 · **Plan:** `260829-2304-signal-desk-analysis-compiler`
**Trạng thái phase:** `blocked` — bước 2 và 3 xong, bước 1 và 4–7 chờ 50 câu
của người ngoài repo.

## Đã làm

| Thứ | Chỗ | Ghi chú |
|---|---|---|
| 18 grader | `apps/api/golden/graders_signal_desk.py` | 6 bất biến · 4 kỳ vọng theo case · 8 phép đo chưa gate |
| Mode chạy | `golden/run.py` | `--mode signal_desk` map sang mode Turn production; corpus mặc định đổi theo mode |
| Trường artifact | `golden/run.py::read_case` | spec v2 · frames · `frame_metadata` · `ref_proof` · `replay_proof` · `model_visible_text` · `arguments` · `external_calls` |
| Danh tính runtime | `golden/run.py::runtime_constants` | thêm `domain_pack {name, version, identity}` — mục C4 đòi |
| Cổng S1 | `golden/grade.py` | dispatch theo `run.mode`; `signal_desk_gate` = 6 bất biến 100% ∧ case ≥ 90% ∧ cost p50 ≤ 84.362 µUSD |
| Rút mẫu corpus | `golden/signal_desk_corpus.py` (mới) | seed · sàn family · validate · digest submissions · CLI |
| Hash corpus | `golden/run.py` | `corpus_sha256` + `corpus_selection` vào block `run` |
| Lệnh | `apps/api/Makefile` | `golden-run MODE=` · `golden-corpus-select` · `golden-corpus-validate` |
| Tài liệu | `golden/README.md` | mode signal_desk · quy trình thu câu · mẫu câu form · luật sàn family |
| Test | `tests/golden/` | 69 xanh (52 có sẵn + 17 mới) |

Sáu bất biến, mỗi cái một hàm, không hàm nào branch theo case id:
`board_present` · `refs_resolve` · `frames_absent` · `compute_literal_free` ·
`evidence_on_page` · `replay_identical`.

## Hai lỗ hổng đã đóng trong lượt này

**1. Artifact không nói nó chạy câu nào.** Block `run` có `corpus_id` và
`corpus_cases`, không có hash. Giữa lượt 1 và lượt 2 corpus **sẽ** đổi — một câu
được viết lại, một family được bù thêm — và hai artifact cùng `corpus_id` khi đó
không phân biệt được với hai lượt chạy cùng bộ câu. `corpus_sha256` băm nội dung
đã canonical hoá, nên định dạng file không phải là danh tính.

**2. Ai chọn 50 câu trong 60.** Nếu một người trong repo chọn thì tính "người
ngoài viết" mất sạch giá trị ở chính bước cuối. `signal_desk_corpus.select` xáo
theo seed, lấp sàn từng family trước rồi lấy phần còn lại theo thứ tự đã xáo;
corpus ghi lại seed, số câu rút ra từ bao nhiêu, và digest của tập submissions.
Cùng seed + cùng submissions = cùng corpus, ai cũng kiểm lại được.

Sàn family: `compare` ≥ 12, năm family còn lại ≥ 6 mỗi cái. Đây là **sàn, không
phải hạn ngạch** — một lượt chạy 40 câu so sánh đo đường so sánh rồi báo cáo như
thể đã đo cả desk.

## Một sai lệch so với plan, có lý do

Plan ghi non-functional *"artifact không chứa số frame"*. Artifact **có** chứa
`composition.frames`, và ba grader bất biến không tồn tại được nếu thiếu:

- `frames_absent` phải có literal của frame mới tìm được nó trong text model đọc;
- `refs_resolve` phải tra lại ô để so với giá trị đã lưu;
- `replay_identical` phải dựng lại board từ chính frames đó qua composer thật.

Bỏ frames đi thì cả ba chỉ còn so hash do `run.py` tự tính — grader tự chấm
chính mình. Luật S0 *"frames không vào transcript"* vẫn nguyên vẹn: nó nói về
**message gửi model**, và đó đúng là thứ `frames_absent` đo.

Hệ quả phải biết trước: file artifact mang số thị trường thật, nên bước 7 của
plan (`git add -f`) là đưa chúng vào repo. Repo private và nguồn là vnstock, nên
không vi phạm gì đã ghi — nhưng đó là một quyết định, không phải một mặc định.

## Code review — hai phát hiện High, đã sửa

Reviewer đo trực tiếp thuật toán rút mẫu (2.000 seed trên pool 80): tỉ lệ được
chọn 0,599–0,686, phẳng **trong từng family** — không ưu tiên vị trí trong file
hay vị trí trong family. Lỗi nằm ở **hàng rào quanh** phép rút, không ở phép rút.

| | Vấn đề | Sửa |
|---|---|---|
| H1 | `select` nhận pool đúng bằng 50 → rút 50 lấy cả pool, seed thành trang trí mà vẫn ghi `seed` + `drawn_from` như thể đã rút | Sàn pool `max(target, ceil(target × 1,2))` = 60 ở mặc định, và scale khi `--target` nhỏ hơn |
| H2 | `validate` không đòi khối `selection` → một corpus dev tự viết, không có draw nào phía sau, **pass** `golden-corpus-validate` exit 0 | `_provenance_errors`: thiếu `selection` là lỗi; `seed` phải là int, `submissions_sha256` phải 64 ký tự, `drawn` phải khớp số case, `drawn_from` phải lớn hơn số đã rút |
| M1 | Chỉ nêu family thiếu **đầu tiên** — mỗi thiếu sót bị giấu là một vòng thu form nữa | Gom mọi family thiếu, raise một lần |
| M2 | `dict(case)` là copy nông → caller sửa `expect` là sửa luôn submission mà digest đã băm | `copy.deepcopy` |
| M3 | CLI ném traceback cho lỗi vận hành; file submissions sai khoá bị báo là "thiếu câu" | Bắt `OSError`/`JSONDecodeError`/`ValueError`, gọi đúng tên lỗi khoá |
| M4 | `golden-corpus-select` ghi đè corpus im lặng → mọi artifact đã viết mang `corpus_sha256` không file nào tái tạo được | Từ chối khi file đã tồn tại, trừ `--force` |
| L1,L2,L4 | Nhãn `case[i]` cho submission · id rỗng thành "duplicate" giả · comment Makefile lạc chỗ | Sửa từng dòng |
| L6,L7 | Không test nào bắt được thiên lệch (fixture xếp family theo khối id liền nhau) · một assertion chép lại chính dòng code | Test 40 seed phủ hết pool + test hash bất biến theo thứ tự file, đổi theo chữ |

Thêm một cổng ngoài danh sách, trả lời câu hỏi mở của reviewer: `validate` trên
corpus **sai lane** (`web_first`) trước đây in ~100 dòng lỗi về từng case; giờ
trả đúng một dòng *"not a signal_desk corpus"*.

L3 (lazy import thừa) sửa theo: `signal_desk_corpus` chỉ dùng stdlib nên nó lên
đầu file cùng các import khác — luật hoãn import trong `run.py` chỉ áp cho `src`.
L5/L8 vào README: `corpus_sha256` băm cả corpus chứ không riêng câu hỏi (nhạy
quá mức, không phải thiếu nhạy), và người gán nhãn chỉ giữ bốn khoá
`id`/`question`/`family`/`expect` — tên hay email người gửi mà lọt vào là nó
được commit cùng corpus và băm vào mọi artifact.

Sau sửa: **69 test** trong `tests/golden/` (52 có sẵn + 17 mới).

## Chưa làm, và vì sao

| Bước | Chặn bởi |
|---|---|
| 1 — thu ≥ 60 câu, rút 50 | **User**: cần ≥ 3 người ngoài repo. Plan cấm dev tự viết; README ghi lại lệnh cấm đó |
| 4 — lượt 1 (n=50) | Corpus + tiền thật + deployment chạy được |
| 5 — đặt ngưỡng lint từ phân bố | Cần phân bố của lượt 1 |
| 6 — lượt 2, gate ≥ 90% | Sau bước 5 |
| 7 — roadmap S1 → `Current`, C4 hai mục | Sau khi gate đạt |

Bước 2 của plan có ghi "chạy 3 case thử". Chưa chạy: nó cần lượt gọi model thật
và một trần chi tiêu, cả hai là quyết định của user. Đường code đã có test giữ
(`test_runner_maps_signal_desk_to_the_persisted_turn_mode`,
`test_signal_desk_projection_reads_public_persisted_seams`).

## Phase 10 — không mở được

`Conditional` theo đúng plan: cần Vnstock trả lời **bằng văn bản** 9 câu go/no-go
và user quyết mua. Mẫu tin nhắn đã sẵn ở
`plans/reports/research-260829-2015-vnstock-bronze-full-power.md` §"Mẫu tin nhắn
gửi support". Không có câu trả lời thì mọi bước của phase 10 đều là đoán: câu 3
(quota tính theo page hay theo lời gọi) quyết cả thiết kế arbiter, câu 4
(device-id khi rebuild container) quyết chạy backfill ở host hay trong container.
Không viết code trước cho một trong hai giả thiết.

## Cần user quyết

1. **Corpus 50 câu**: gửi form cho ai, thu về kênh nào. Mẫu câu hỏi form đã có
   trong `golden/README.md`; khi có file submissions đã gán nhãn family thì
   `make golden-corpus-select SUBMISSIONS=… SEED=…` là xong bước 1.
2. **Trần chi tiêu lượt 1** (`CEILING_USD`) và deployment nào chạy.
3. **Bronze**: gửi 9 câu go/no-go chưa, và có mua không.
