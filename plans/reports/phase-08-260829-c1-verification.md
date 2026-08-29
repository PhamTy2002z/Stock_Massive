# C1 — nghiệm thu so baseline (phase 08)

**Ngày:** 2026-08-29 · **Artifact:** `apps/api/golden/artifacts/web-first-v1-final.json`
(`git_sha: WORKTREE-c1-phase-05-08`, `status: complete`, 20/20 case, 1.292.776 µUSD)

**Kết luận: C1 KHÔNG tốt nghiệp. Nhãn giữ nguyên `Target`.**
Hai lý do, cả hai đo được, không cái nào là "gần đạt":

1. Tiêu chí *"số ngoài store không có citation = 0"* **không có công cụ đo hợp lệ**.
   Grader `uncited_external_number` sai **5/5** — mọi case nó đánh trượt đều là câu
   trả lời trung thực, có nguồn. Xem §4.
2. `read_depth` phát biểu phẳng (`fetch_url ≥ 2`) cho **14/20**, dưới giá trị khởi
   điểm 15/20 và **giảm 2 case** so lượt trước. Xem §3.

Ba tiêu chí còn lại đạt rõ ràng, và hiệu ứng dedup của phase 05 đo được sạch.

---

## 1. Một confound phải nói trước mọi con số

`PROMPT_VERSION` của lượt cuối là **3.0.0**; lượt `after-03-04` là **2.10.0**.
Chênh lệch đó **không phải** của phase 05–07 — không phase nào trong ba phase này
sửa `prompt/sections.py`. Nó là plan C5 (`260829-1435-c5-domain-pack`) sống cùng
worktree.

Nên: mọi delta ở đây là **C1 phase 05–07 cộng C5 progressive instruction**, không
phải riêng C1. Chỉ một số liệu trong báo cáo này là quy được cho C1 một cách chắc
chắn — **nguồn/lượt tìm** (§2), vì dedup là phép biến đổi cơ học trên payload, độc
lập với prompt.

Ghi ra vì đây đúng là loại nhầm lẫn giết bộ eval trước: đọc một delta là bằng chứng
cho thứ mình vừa làm, khi trong cùng cây làm việc còn thứ khác đã đổi.

## 2. Dedup của phase 05 — đo được, quy được, đúng như thiết kế

| | phase 02 baseline | after 03-04 | **final 05-07** |
|---|---|---|---|
| `web_search` call | 53 | 54 | **57** |
| Nguồn được vẽ (tổng) | 249 | 277 | **226** |
| **Nguồn / một lượt tìm** | 4,70 | 5,13 | **3,96** |
| `distinct_domains` pass | 19/20 | 19/20 | **19/20** |

`MAX_RESULTS = 5` không đổi ở cả ba lượt. Nên 5,13 → 3,96 (**−22,8%**) nghĩa là:
trung bình **1,17 trong mỗi 5 kết quả** một truy vấn trả về **đã được một call
trước đó của cùng Turn vẽ rồi**.

Đó chính là trùng lặp mà phép đo trên tape dự đoán trước khi viết code (21/223 URL
= 9,4% xuất hiện ở nhiều call), và nó xuất hiện ở đây to hơn vì đo trên nguồn *được
vẽ* chứ không phải trên URL *khác nhau*.

**Số nguồn giảm 18,4% mà `distinct_domains` pass giữ nguyên 19/20.** Đó là tính chất
dedup được thiết kế để có: bỏ bản trùng, không bỏ phạm vi phủ. Rủi ro phase 05 ghi
là *"dedup quá tay, bóp số nguồn xuống dưới 3"* — không xảy ra, và về mặt số học
không thể xảy ra: grader lấy **set** domain, nên bỏ một URL trùng không bao giờ hạ
được số domain khác nhau.

## 3. Bốn grader, cùng một phiên bản, trên cả ba artifact

Chấm bằng grader **hiện tại** trên cả ba file — phép so duy nhất có nghĩa.

| Chỉ số | Loại | phase 02 | after 03-04 | **final** | Đánh giá |
|---|---|---|---|---|---|
| `distinct_domains` (bar của từng case) | gate | 19/20 | 19/20 | **19/20** | **đạt** |
| `distinct_domains` ≥ 3 phẳng | gate | 19/20 | 19/20 | **19/20** | **đạt** |
| `read_depth` (bar của từng case) | gate | 11/20 | 19/20 | **18/20** | đạt |
| `read_depth` ≥ 2 phẳng | gate | 6/20 | 16/20 | **14/20** | **dưới khởi điểm 15/20** |
| `parallel_rate` (round có > 1 tìm) | gate | 11/32 = 34% | 17/27 = 63% | **17/27 = 63%** | **đạt** (không giảm) |
| `uncited_external_number` | *gỡ khỏi gate* | 11/16 | 12/16 | **11/16** | **công cụ hỏng — §4** |
| latency P50 | tín hiệu | 51,0 s | 63,0 s | **52,4 s** | **đạt** (−16,9% so lượt trước) |
| chi phí/Turn P50 | tín hiệu | 45.484 | 60.107 | **58.222** µUSD | **đạt** (trần 500.000) |

Ghi chú mẫu số: `read_depth` và `distinct_domains` có `decided = 20`;
`uncited_external_number` chỉ có **`decided = 16`** (bốn case cố ý không đòi:
wf-009, wf-013, wf-017, wf-019). Xem §5.

**Về `read_depth` phẳng 16/20 → 14/20.** Hai case, trên n = 20, với model live và
web live: nằm trong dao động giữa hai lượt và **không** phải bằng chứng phase 05–07
làm xấu đi. Nhưng nó cũng **không** phải bằng chứng cải thiện, và nó **dưới** giá trị
khởi điểm 15/20 mà plan viết. Phát biểu đúng là: *chưa chứng minh được ở n = 20*.
Bước tăng thật thuộc về phase 03-04 (6/20 → 16/20), không thuộc ba phase này.

## 4. Vì sao `uncited_external_number` ra khỏi bộ gate

Phase 05 đã ghi trước điều kiện gỡ nó: *"nếu tách số của store khỏi số ngoài store
vẫn nhập nhằng, grader này ra khỏi bộ và tiêu chí hạ xuống thành một phép đếm được
báo cáo"*. Điều kiện đã xảy ra, và nặng hơn dự đoán.

**Đọc cả năm case nó đánh trượt ở lượt cuối. Không case nào bịa số.**

| Case | Số bị gắn cờ | Thật ra là gì |
|---|---|---|
| wf-005 | 15,47 · 17,4 | **Đổi đơn vị** — trang viết "tỷ", câu trả lời viết "nghìn tỷ" |
| wf-011 | 110,7 · 552 | 110,7 là làm tròn của 110.682 sang nghìn tỷ; **552 = 110.682 − 110.130**, chính là chênh lệch giữa hai nguồn mà câu hỏi yêu cầu nêu |
| wf-012 | 100 | Room ngoại tối đa theo **định nghĩa**, không phải số đọc từ trang |
| wf-015 | 294 · 1,4 | **21.467.886 − 21.173.492 = 294.394**; 1,4% là tỷ lệ của chính hiệu đó |
| wf-018 | 625 · 275 · 30,6 | **10.000 × 62.500 = 625 triệu**; 275 = 900 − 625; 30,6% = 275/900 |

Sai số 5/5. Grader hỏi *"con số này có xuất hiện nguyên văn trong bằng chứng
không"*, còn tiêu chí hỏi *"con số này có được bằng chứng đỡ không"*. Hai câu hỏi
đó trùng nhau cho một câu trả lời chỉ chép lại, và tách ra ngay khi câu trả lời làm
**số học** — trừ hai nguồn, đổi đơn vị, tính phần trăm. Mà đó chính là thứ câu hỏi
họ `conflicting_or_missing` **yêu cầu** làm.

Trớ trêu: wf-011 và wf-018 là hai câu trả lời **tốt nhất** của lượt chạy. wf-011 nêu
tên cả hai nguồn, lượng hoá chênh lệch, nói rõ chỗ không mở được trang để đối chiếu.
wf-018 từ chối ra quyết định vị thế đúng như case đối kháng muốn. Cả hai bị đánh
trượt vì đã tính một phép trừ.

**Quyết định:** `uncited_external_number` **không gate**. Nó ở lại bộ như một **phép
đếm được báo cáo** — max giảm 8 → 3 giữa hai lượt vẫn là tín hiệu có ích — nhưng
không được dùng để phán C1 đạt hay không. Và vì nó là công cụ duy nhất cho tiêu chí
roadmap *"số ngoài store không citation = 0"*, **tiêu chí đó hiện chưa đo được**.

Không hạ ngưỡng để vừa kết quả. Cách sửa thật là để grader thấy được số suy diễn
(cho phép hiệu · tích · thương · bội số thập phân của các số đã phủ), và đó là việc
của một phase riêng, không phải một dòng nới ở đây.

## 5. Hai ngưỡng của plan phát biểu sai mẫu số

Tìm ra khi đọc corpus, **trước** khi chấm — không phải sau khi thấy kết quả.

1. **`uncited_external_number` "≥ 18/20"** là bất khả về số học. Corpus chỉ có **16**
   case khai `must_cite_external_numbers: true`; bốn case cố ý không, và grader trả
   `passed=None` cho chúng. Mẫu số là 16.
2. **`distinct_domains` "≥ 3 domain"** chỉ mô tả nửa corpus. Corpus khai bar **2**
   cho mười case và **3** cho mười case; grader chấm từng case theo bar của chính nó.

Cả hai là lỗi phát biểu ngưỡng trong plan, không phải lỗi grader — grader làm đúng
thứ corpus khai. Ngưỡng chốt ở §6 phát biểu trên mẫu số thật.

## 6. Ngưỡng chốt

Đặt **sau** khi nhìn phân phối, như luật của plan. Sống ở `apps/api/golden/README.md`
— một chỗ, là authority; không rải vào code grader.

| Chỉ số | Ngưỡng | Lý do |
|---|---|---|
| `distinct_domains` | **≥ 18/20** case đạt bar của chính nó | Ba lượt liên tiếp cho 19/20; case duy nhất trượt là một Turn không tìm gì. 18 để một case hỏng không giết lượt chạy |
| `read_depth` | **≥ 16/20** case đạt bar của chính nó | Quan sát 11 → 19 → 18. Đặt ở 16 vì hai lượt gần nhất đều ≥ 18 và biên độ hai case là dao động thật đã quan sát được |
| `parallel_rate` | **≥ 50%** round có > 1 truy vấn | Đo 34% → 63% → 63%. 50% nằm giữa mức trước và mức sau, và nằm dưới hai lần đo gần nhất đủ để chịu một lượt kém |
| latency P50 | tín hiệu, tăng > 20% phải giải thích | 51,0 → 63,0 → 52,4 s. Biên độ giữa các lượt tự nó là ±23%, nên ngưỡng cứng ở đây sẽ là tiếng ồn |
| chi phí/Turn P50 | tín hiệu, dưới `TURN_COST_MICRO_USD` | 58.222 so trần 500.000 — dư 8,6 lần |
| `uncited_external_number` | **không gate** | §4 |
| `scan` risk=high trên corpus lành | **báo cáo**, chưa gate | §7 |

## 7. Lớp quét injection — tỉ lệ báo động giả đo được là 0

97 kết quả đọc-ngoài được quét trong lượt cuối:

| | Số |
|---|---|
| Kết quả được quét | **97** |
| `risk: high` | **0** |
| `risk: unknown` (quét lỗi hoặc chạm trần thời gian) | **0** |

Rủi ro phase 07 ghi là *"false positive làm rail đầy cảnh báo, người đọc mất tin"*,
kèm chỉ dẫn *"đo trên toàn corpus golden trước khi bật hiển thị"*. Đã đo: **0/97**.
Không có case nào của corpus chạm pattern — kể cả họ đối kháng, vì trang thật mà
model đọc được không mang injection; corpus không dựng được nội dung trang.

Nên số này chứng minh **một nửa**: lớp quét không kêu bậy trên trang thị trường
lành. Nửa còn lại — nó có bắt được injection thật không — chứng minh bằng test
(`tests/test_threat_patterns.py`, gồm biến thể zero-width và full-width), không bằng
corpus. Ghi rõ vì đây là giới hạn của phép đo, không phải kết quả.

Hệ quả cho hiển thị: **chưa có dữ liệu để bật cảnh báo trên rail**. 0/97 không phân
biệt được "không bao giờ kêu bậy" với "không bao giờ kêu". Cờ vẫn ghi vào store từ
đầu, đúng như phase 07 định; hiển thị vẫn là một công tắc riêng, và nó chưa bật.

## 8. Việc còn lại của C1

- **Grader số suy diễn.** Điều kiện để tiêu chí citation của roadmap đo được. Là
  phase kế của C1, không phải nợ mơ hồ.
- **`read_depth` phẳng chưa chứng minh ở n = 20.** Cần thêm lượt hoặc corpus rộng
  hơn; cache của `WebLane` khiến "chạy thêm lượt trong ngày" không tăng n hiệu dụng.
- **Chưa đo được lớp quét trên nội dung có injection thật.** Corpus không dựng được
  nội dung trang.

## Câu hỏi chưa giải quyết

1. **Grader số suy diễn sâu tới đâu.** Cho phép hiệu · tích · thương của các số đã
   phủ là đủ cho cả năm case ở §4. Nhưng nới thêm một bậc nữa thì gần như mọi số đều
   "suy ra được" từ một tập đủ lớn, và grader thành luôn-pass — đúng thứ plan cấm.
   Ranh giới phải chốt bằng cách chạy trên artifact đã có, không bằng suy luận.
2. **Corpus có nên dựng được nội dung trang không.** Cách duy nhất để đo lớp quét
   đầu-cuối. Nhưng tape phục vụ `WebLane.read`, còn một trang bịa nội dung sẽ làm
   corpus không còn đo hành vi thật của model trên web thật. Có thể là hai bộ khác
   nhau chứ không phải một bộ mở rộng.
3. **Ai sở hữu và chấm Golden Set** — nợ cũ của plan, chưa trả. Corpus vẫn do
   C4-lite tự viết.
