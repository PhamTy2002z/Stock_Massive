# Phase 01 — audit năm finding và đo độ sâu suy diễn

**Ngày:** 2026-08-29 · **Artifact:** `apps/api/golden/artifacts/web-first-v1-final.json`
· **Grader:** `golden/grade.py` chưa sửa · Worktree `develop` @ `027daa0`, sạch.

**Kết luận: bốn trong năm finding là suy diễn hợp lệ, một là finding thật. Nhưng
độ sâu cần để bắt được bốn cái đó cũng đủ để bắt gần như mọi con số — đo được,
không phải suy đoán. Phase 02 như đang viết là bất khả.**

---

## 0. Điều kiện tiên quyết — đã sạch, không cần dàn xếp

Rủi ro lớn nhất của phase này ("prerequisite không cô lập được") không xảy ra:

```
branch develop · worktree list = 1 · git status = clean
027daa0 docs: record the C1 and C5 surfaces and retire the plans that closed
```

C1 (`07ac320`, `c8af5ac`, `8337d04`) và C5 (`d8d3de8`, `965b9e7`) đều đã commit.
Không stash, không reset, không hấp thụ thay đổi lạ. Bước 1–2 của phase đóng.

## 1. Regrade artifact cuối — tái lập chính xác

Chấm lại bằng grader chưa sửa cho đúng năm case, đúng những con số report cũ ghi:

| Case | Số bị gắn cờ | `value` |
|---|---|---|
| wf-005 | 15,47 · 17,4 | 2 |
| wf-011 | 110,7 · 552 | 2 |
| wf-012 | 100 | 1 |
| wf-015 | 1,4 · 294 | 2 |
| wf-018 | 30,6 · 275 · 625 | 3 |

Phân phối: `distinct_domains` 19/20 · `read_depth` 18/20 · `parallel_rate` median
1,0 · `uncited_external_number` 11/16. Khớp `phase-08-260829-c1-verification.md`.

## 2. Audit từng số từ chính văn bản artifact

Đọc thẳng `answer_text` và `external_evidence_text`/`store_evidence_text` của
từng case. Phân loại theo yêu cầu bước 5 của phase.

| Case | Số | Phân loại | Phép tính, từ premise thật |
|---|---|---|---|
| wf-005 | 15,47 | đổi đơn vị + làm tròn | trang: `15.468,4 tỷ` → ×10⁻³ = 15,4684 → 15,47 |
| wf-005 | 17,4 | đổi đơn vị | trang: `17.400 tỷ` → ×10⁻³ = 17,4 |
| wf-011 | 110,7 | đổi đơn vị + làm tròn | trang: `110.682 tỷ` → ×10⁻³ = 110,682 → 110,7 |
| wf-011 | 552 | **suy diễn, 2 bậc** | `110.682` − (`110.13T` ×10³) = 552 |
| wf-012 | 100 | **không có nguồn** | xem §3 |
| wf-015 | 294 | **suy diễn, 2 bậc** | (`21.467.886` − `21.173.492`) ×10⁻³ = 294,394 → 294 |
| wf-015 | 1,4 | **suy diễn, 3 bậc** | 294.394 / `21.173.492` ×100 = 1,390 → 1,4 |
| wf-018 | 625 | **suy diễn, 2 bậc** | (`10.000`ᑫ × `62.500`ˢ) ×10⁻⁶ = 625 |
| wf-018 | 275 | **suy diễn, 3 bậc** | 900 − 625, với 900 = (`10.000`ᑫ × `90.000`ᑫ) ×10⁻⁶ |
| wf-018 | 30,6 | **suy diễn, 4 bậc** | 275 / 900 ×100 = 30,555 → 30,6 |

ᑫ = số câu hỏi cấp · ˢ = số của store · còn lại là trang ngoài.

Tám trong chín số là suy diễn hợp lệ, truy được về premise thật. Report cũ đúng
về bản chất. **Nhưng "5/5 false positive" thì sai** — xem §3.

## 3. `wf-012` không phải false positive — nó là finding thật

Report cũ xếp `100` của wf-012 vào "đổi đơn vị / số học", với ghi chú *"room ngoại
tối đa theo định nghĩa"*. Đọc lại artifact thì không đỡ được cách xếp đó:

- `answer_text`: *"HPG không bị giới hạn sở hữu nước ngoài theo mức 49%; về nguyên
  tắc room ngoại tối đa là **100%**."*
- Bằng chứng ngoài của chính case: không trang nào nói trần room của HPG. Kết quả
  tìm gần nhất là tiêu đề *"Một công ty tài chính nới room ngoại lên 50%"* — một
  doanh nghiệp khác.

Nên `100` là **hằng số ngữ nghĩa model tự cấp**, không phải số đọc được. Nó có
thể đúng về luật, nhưng tiêu chí đang đo là *"có bằng chứng đỡ không"*, và nó
không có. Yêu cầu của phase — *"`wf-012` phải giữ `100%` unsupported nếu artifact
không có evidence cho trần room đó"* — **đã thoả, và nó phải ở lại là finding.**

Phát biểu đúng thay cho "5/5 sai": **4/5 case sai, 8/9 số bị gắn cờ là suy diễn
hợp lệ, 1/9 là finding thật.** Report cũ giữ nguyên (không viết lại lịch sử);
đính chính ghi ở đây và ở plan kế nhiệm.

## 4. Đo độ sâu — và đo luôn cái giá của độ sâu

Bước 6 của phase yêu cầu đo độ sâu nhỏ nhất mà suy diễn hợp lệ cần, **không**
chọn độ sâu theo tỉ lệ pass mong muốn. Đo cả hai chiều: bắt được bao nhiêu, và
bỏ lọt bao nhiêu.

### 4.1 Kích thước tập premise

Số khác nhau trong `question` + `external_evidence_text` + `store_evidence_text`:

| | wf-005 | wf-011 | wf-012 | wf-015 | wf-018 | toàn corpus |
|---|---|---|---|---|---|---|
| premise | 134 | 310 | 109 | 141 | 225 | median 184, max 504 |

### 4.2 Recall theo bậc

Với `L0` = khớp thẳng/làm tròn (grader hiện tại) · `L1` = thêm đổi đơn vị ×10ᵏ ·
`L2` = thêm một phép `+ − × ÷` trên hai premise:

| | L0 | L1 | L2 | trượt |
|---|---|---|---|---|
| 9 suy diễn hợp lệ | 0 | 4 | 9 | 0 |

**L2 đủ cho cả chín.** Đó là câu trả lời cho bước 6 nếu chỉ hỏi recall.

### 4.3 Cái giá: L2 phủ gần hết không gian giá trị

Đây là phép đo phase 08 đã báo trước là phải làm (*"nới thêm một bậc thì gần như
mọi số đều suy ra được"*). Siết trước khi đo: operand phải là `is_claim`, phải có
≥3 chữ số nghĩa; hệ số quy đổi chỉ lấy từ từ chỉ độ lớn (10⁻⁹…10⁹), bỏ ×100.

Rồi đếm: trong 900 giá trị nguyên ba chữ số, L2 chạm được bao nhiêu?

| Case | operand sau khi siết | phủ không gian 3 chữ số |
|---|---|---|
| wf-005 | 72 | **92,7%** |
| wf-011 | 221 | **100,0%** |
| wf-012 | 38 | 55,2% |
| wf-015 | 88 | **97,4%** |
| wf-018 | 126 | **99,9%** |

Bốn trên năm case cho 92,7–100%. `wf-012` dừng ở 55,2% vì tập của nó nhỏ nhất —
và đó chính là case duy nhất có finding thật, nên nó không cứu được thiết kế. Một
grader nhận 92,7–100% mọi giá trị có thể **không phải phép đo**. Kiểm chứng
bằng mutation như phase 02 yêu cầu — bóp méo chín số hợp lệ ±7%/±31%/±38%:

| Chính sách | recall | `wf-012` 100 | mutation bịa tìm được witness |
|---|---|---|---|
| A — hệ số đầy đủ, L2 | 9/9 | **nhận sai ở L1** | **40/40** |
| B — chỉ hệ số độ lớn, L2 | 9/9 | nhận sai | **40/40** |
| C — thêm ≥2 chữ số nghĩa | 9/9 | nhận sai | **39/40** |
| D — thêm ≥3 chữ số nghĩa | 9/9 | nhận sai | **39/40** |
| E — bỏ L2, chỉ L1 | **3/9** | đúng: không nhận | 6/40 |

Siết ba chiều (hệ số · chữ số nghĩa · phép toán) không hạ được false accept khỏi
~100%. Bỏ L2 thì recall sập còn 3/9. **Hai mục tiêu này loại trừ nhau ở kích
thước tập premise thật.**

### 4.4 Vì sao không phải chuyện tinh chỉnh

Đo độ phủ theo cỡ tập operand (wf-018, lấy mẫu ngẫu nhiên):

| operand | 3 | 5 | 8 | 12 | 20 | 40 | 80 | 126 |
|---|---|---|---|---|---|---|---|---|
| phủ | 0,4% | 1,6% | 3,8% | 8,4% | 22,5% | 62,0% | 96,9% | 99,9% |

Muốn false accept dưới ~5% thì tập operand phải **≤ 8 số**. Tập thật là 38–221.
Đây là số học, không phải ngưỡng: n operand với 4 phép sinh ~4n² giá trị ứng
viên; khi 4n² vượt xa 900 thì phủ kín. Không có cách chọn ngưỡng nào thoát.

## 5. Đã thử một thiết kế khác về chất — vẫn không đạt

Trước khi kết luận, thử thiết kế **không** nằm trong phase 02: operand chỉ lấy từ
số mà **chính câu trả lời đã nêu và đã tự có nguồn** (L0/L1) — "câu trả lời phải
trưng phép tính của nó". Tập operand tụt xuống 5–21.

| Case | operand | phủ | |
|---|---|---|---|
| wf-005 | 5 | 1,7% | |
| wf-011 | 9 | 3,6% | |
| wf-012 | 5 | 1,4% | |
| wf-015 | 8 | 3,7% | |
| wf-018 | 21 | 25,7% | |

Phủ tốt hơn hẳn. Nhưng ba lỗi giết nó:

1. **Recall 6/9.** `552`, `275`, `30,6` trượt — operand của chúng (110.130 · 900)
   bản thân là số suy diễn, không có nguồn trực tiếp. Muốn bắt phải cho phép
   đóng gói nhiều tầng, mà mỗi tầng lại bơm tập operand to lên.
2. **`wf-012` bị nhận sai bằng `25 + 75`** — trong đó `75` chính là số câu trả lời
   suy ra *từ* 100. Witness vòng tròn: 100 được đỡ bởi thứ nó vừa sinh ra.
3. **`wf-015` 1,4 được nhận bằng `27 / 20` = 1,35** — không phải phép tính thật.
   Kể cả khi verdict đúng, witness vẫn sai. 10/36 mutation bịa vẫn qua (28%).

## 6. Kết luận cho Phase 02

| Thiết kế | recall | false accept | phủ không gian |
|---|---|---|---|
| Tập thô + một phép nhị phân (đúng như phase 02 viết) | 9/9 | ~100% | 92,7–100%¹ |
| Trên, đã siết ba chiều | 9/9 | 39/40 | 92,7–100%¹ |
| Operand phải là số đã nêu & đã có nguồn | 6/9 | 28% | 1,4–25,7% |

¹ Bốn trên năm case; `wf-012` 55,2% vì tập toán hạng của nó nhỏ nhất.

Không cái nào là công cụ đo hợp lệ. Điều khoản dừng của chính phase 02 nói đúng
tình huống này:

> **Combinatorial false accepts.** Signal: any fabricated mutation finds a witness.
> Response: tighten unit/context/cap; **if still non-zero, stop and replan** toward
> an explicit claim-provenance contract in C4. **Never raise depth to make cases green.**

Đã siết, vẫn ~100%. Và hợp đồng giao hàng của plan nói cùng một câu:

> nếu calibration không đủ chính xác, **dừng và replan thay vì nới grader**.

**Phase 02 dừng.** Không viết `numeric_evidence.py`. Không nới grader.

## 7. Hệ quả cho `read_depth` — authority chốt một chỗ

Bước còn lại của phase (mâu thuẫn `read_depth`) không phụ thuộc §4–6 và đóng được:

- **Authority duy nhất:** ≥16/20 case đạt `expect.min_pages_read` của chính nó.
  Đo trên artifact cuối: **18/20 — đạt.**
- **`fetch_url >= 2` phẳng (14/20) là diagnostic, không gate.** Nó không đọc bar
  của case, nên một case khai `min_pages_read: 1` bị nó tính là trượt dù đúng hợp đồng.

**Chỗ duy nhất được đặt ngưỡng** vẫn là `apps/api/golden/README.md` §The thresholds
— đã viết đúng dạng này từ trước. Roadmap, plan và report có nhắc lại con số để đọc
được tại chỗ, nhưng **không nơi nào đặt ngưỡng mới**; lệch số thì README thắng.

## 8. Câu hỏi cho người quyết

Không phải câu hỏi kỹ thuật — là ranh giới hợp đồng của C1, và nó thuộc về người
sở hữu roadmap. Xem §Unresolved của báo cáo tốt nghiệp.
