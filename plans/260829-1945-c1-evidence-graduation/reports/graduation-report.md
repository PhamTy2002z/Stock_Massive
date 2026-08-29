# C1 — báo cáo tốt nghiệp

**Ngày:** 2026-08-29 · **Nhánh:** `develop` @ `027daa0` (worktree sạch lúc bắt đầu)
· **Grader:** `golden/grade.py`, **không sửa một dòng nào** trong plan này.

**Kết luận: C1 đổi `Target` → `Current`.** Ba gate đo được đều đạt, lớp bảo mật
thứ năm chứng minh xong đầu-cuối, và tiêu chí thứ tư **chuyển chủ sang C4** kèm
bằng chứng nó không thuộc về C1.

---

## 1. Bảng tốt nghiệp — mẫu số thật

Cả ba artifact chấm bằng **cùng một revision grader**, mỗi file chấm **hai lần**,
JSON tuần tự hoá **trùng khít từng byte**. Không lượt chạy mới, không gọi model,
không chạm mạng hay DB. Chi phí: **0 USD**.

| Chỉ số | phase 02 | after 03-04 | **cuối 05-07** | Ngưỡng | Mẫu số | |
|---|---|---|---|---|---|---|
| `distinct_domains` đạt bar từng case | 19/20 | 19/20 | **19/20** | ≥ 18/20 | 20 | **đạt** |
| `read_depth` đạt bar từng case | 11/20 | 19/20 | **18/20** | ≥ 16/20 | 20 | **đạt** |
| `parallel_rate` (round có > 1 tìm) | 11/32 = 34% | 17/27 = 63% | **17/27 = 63%** | ≥ 50% | round | **đạt** |
| `uncited_external_number` | 11/16 | 12/16 | **11/16** | **chuyển sang C4** | 16 | — |
| `read_depth ≥ 2` phẳng | 6/20 | 16/20 | **14/20** | **diagnostic** | 20 | — |
| latency P50 | 51,0 s | 63,0 s | **52,4 s** | tín hiệu | 20 | đạt |
| chi phí/Turn P50 | 45.484 | 60.107 | **58.222** µUSD | < 500.000 | 20 | đạt |

**`read_depth` có đúng một authority: bar của từng case** (`expect.min_pages_read`).
Phát biểu phẳng `fetch_url ≥ 2` không đọc bar của case, nên nó đánh trượt một case
khai `min_pages_read: 1` dù case đó làm đúng hợp đồng. Nó ở lại report để thấy
drift, và **không phủ định** gate. Mâu thuẫn hai công thức mà plan mở ra: đã đóng,
ngưỡng sống một chỗ (`apps/api/golden/README.md`).

**Confound phải đọc kèm:** lượt cuối chạy `PROMPT_VERSION` 3.0.0, lượt trước
2.10.0 — chênh đó là của **C5**, không phải C1 phase 05-07. Số duy nhất quy chắc
chắn cho C1 vẫn là **nguồn/lượt tìm 5,13 → 3,96 (−22,8%)**: dedup là phép biến
đổi cơ học trên payload, độc lập prompt. Không dùng delta nào khác để ghi công
cho C1, và **không đổi trạng thái C5** trong plan này.

## 2. Vì sao tiêu chí citation chuyển sang C4 chứ không giữ C1 ở `Target`

Đây là thay đổi hợp đồng, nên nó phải đứng được bằng bằng chứng chứ không bằng
tiện lợi.

**Nó không đo được, và đó là kết luận số học.** Đo đầy đủ ở
[`phase-01-260829-derivation-depth.md`](./phase-01-260829-derivation-depth.md):

- Tập premise một case: **109–310 số** ở năm case liên quan (median toàn corpus
  184, max 504).
- Siết ba chiều cùng lúc — chỉ hệ số độ lớn · toán hạng ≥3 chữ số nghĩa · bỏ ×100
  — vẫn để lại **38–221 toán hạng**.
- **Một** phép `+ − × ÷` trên tập đã siết đó chạm **92,7–100%** toàn bộ không gian
  giá trị ba chữ số ở **bốn trên năm** case (`wf-012` 55,2%, tập nhỏ nhất). Một
  grader nhận 92,7–100% mọi giá trị có thể không phải phép đo — và nó vẫn cho
  **39/40** mutation bịa tìm được witness.
- Bỏ phép nhị phân thì recall sập còn **3/9**.
- Muốn false-accept dưới 5% thì tập toán hạng phải **≤8 số**. Thật là 38–221.
- Thiết kế thứ ba (toán hạng chỉ lấy từ số câu trả lời đã tự có nguồn) hạ phủ
  xuống 1,4–25,7% nhưng recall còn **6/9**, false-accept **28%**, và sinh witness
  vòng tròn: `wf-012`'s `100` được đỡ bằng `25 + 75`, mà `75` sinh ra *từ* `100`.

n toán hạng với 4 phép sinh ~4n² ứng viên; khi 4n² vượt xa 900 thì phủ kín. Không
ngưỡng nào thoát được.

**Vì sao là C4 chứ không phải "C1 chờ".** Đo được nó cần runtime **ghi lại
provenance của từng khẳng định** — grader **verify** thay vì **tìm kiếm**. Đó là
một hợp đồng mới, và phase 02 tự chỉ định nó cho C4 từ đầu ("*replan toward an
explicit claim-provenance contract in C4*"). Mà **§6 roadmap ghi C4 phụ thuộc
C1**: để C1 chờ công cụ mà chỉ C4 dựng được là **khoá chết vòng tròn**. Chuyển
chủ phá vòng đó mà không bỏ tiêu chí — C4 nhận nó tường minh, kèm ngõ cụt đã đo
để không trả lại tiền học phí.

**Phase 02 dừng đúng điều khoản dừng của chính nó**, không phải vì hết giờ:

> *if still non-zero, stop and replan toward an explicit claim-provenance contract
> in C4. **Never raise depth to make cases green.***

`golden/numeric_evidence.py` **không được viết**. Grader **không** bị nới một dòng.

## 3. Đính chính report cũ — 4/5, không phải 5/5

`phase-08-260829-c1-verification.md` ghi grader sai "5/5". Audit từ chính văn bản
artifact cho **4/5**:

| Case | Số | Thực chất |
|---|---|---|
| wf-005 | 15,47 · 17,4 | đổi đơn vị hợp lệ (`15.468,4 tỷ` ×10⁻³) |
| wf-011 | 110,7 · 552 | đổi đơn vị · hiệu hai nguồn (`110.682` − `110,13T`×10³) |
| **wf-012** | **100** | **finding thật** — xem dưới |
| wf-015 | 294 · 1,4 | hiệu hai nguồn · phần trăm của hiệu đó |
| wf-018 | 625 · 275 · 30,6 | tích · hiệu · phần trăm, từ số câu hỏi + store |

`wf-012` nói *"room ngoại tối đa là **100%**"*, và **không trang nào** trong bằng
chứng của case nói trần room của HPG — kết quả gần nhất là tiêu đề về một doanh
nghiệp **khác** "nới room lên 50%". Đó là hằng số model tự cấp. Có thể đúng về
luật, nhưng tiêu chí hỏi *"có bằng chứng đỡ không"*, và nó không có.

Phát biểu đúng: **8/9 số bị gắn cờ là suy diễn hợp lệ, 1/9 là finding thật.**
Report gốc **giữ nguyên** — nó đúng tại thời điểm chạy; đính chính ghi ở đây, ở
roadmap, và ở con trỏ kế nhiệm trong plan cũ.

## 4. Lớp quét injection — nửa còn lại đã chứng minh

Trước plan này: corpus cho **0 `risk: high` / 97 kết quả** trang lành. Đó chứng
minh **không kêu bậy**; nó **không** chứng minh **bắt được**.

Nửa còn lại giờ có bằng chứng, bằng **11 test tích hợp** đi đúng đường production
— không mock verdict, bắt đầu từ văn bản handler ngoài:

| Điều phải đúng | Bằng chứng |
|---|---|
| Văn bản tấn công → `risk: high`, tên pattern ổn định | 4 finding đúng thứ tự bảng pattern, text trang nguyên vẹn |
| Quét **đúng một lần** mỗi kết quả | đếm tại `threat_patterns.normalise` (nếp gấp **mọi** lượt quét đi qua, nên một lượt quét lạc lên đường render vẫn bị đếm); dispatch 1 lần rồi dựng lại transcript **3 lần** → vẫn **1** |
| Verdict **không** vào transcript gửi model | so trên `repr(context.messages)` cả `arguments`: có wrapper + dòng tấn công; **không** có `risk`/`high`/`unknown`/`scan`/tên finding nào |
| Không chữ nào của kẻ tấn công trong `scan` | verdict đúng `{risk, findings}`, không span |
| `low` cho trang lành · `unknown` khi scanner hỏng | pattern raise **và** cạn `SCAN_BUDGET_SECONDS`; cả hai `ok`, text nguyên vẹn, fail-open |
| Sống qua persist → mở lại thread | `as_wire` → `turns.assistant_message` → `append_message` → `read_thread`: cùng verdict |
| `golden.run.read_case` đọc ra đúng thứ đó | round trip `AgentPersistence` thật; payload cũ chưa có khoá → `None`, không raise |
| Phân biệt `None` với `low` | tool đọc store persist `scan: None` |

**Non-vacuity chứng minh bằng mutation** (mỗi cái revert lại, `src/` sạch):

| Mutation | Hệ quả |
|---|---|
| `as_wire` phát `"scan": None` | test persist + golden projection **đỏ** |
| `shown_result` nối verdict vào body | cả hai test cô lập transcript **đỏ** |
| `executor` đặt `scan = None` | 8 test scan **đỏ** |

**0 file production sửa.** Chuỗi đã đúng từ phase 07; thứ thiếu là bằng chứng.
Không migration, không schema, `golden/web_first.json` và `golden/artifacts/*`
nguyên vẹn.

**Hiển thị cảnh báo trên rail vẫn TẮT.** 0/97 không phân biệt "không kêu bậy" với
"không kêu", và test chứng minh scanner bắt được **payload dựng sẵn**, không phải
trang thật có injection. Bật hiển thị cần dữ liệu chưa có.

## 5. Cổng chất lượng

| Cổng | Kết quả |
|---|---|
| `make test` (apps/api) | **1690 passed**, 3 deselected, 0 failed, 47s |
| `make lint` (apps/api) | sạch |
| Focused (executor · untrusted · persistence · golden) | 107 passed |
| Regrade × 2, ba artifact | byte-identical |
| Web `type-check`/`lint`/`test`/`build` | **không áp dụng** — xem dưới |

**Vì sao không chạy cổng web:** plan cho phép bỏ khi wire shape không đổi. Đã
kiểm bằng `git status`: **không file nào dưới `src/` hay `apps/web/` bị sửa**.
Thay đổi chỉ ở test, tài liệu và plan. Không có shape nào để FE lệch theo.

## 6. Hệ quả trạng thái

| | Trước | Sau |
|---|---|---|
| C1 | `Target` | **`Current`** |
| C2 | chặn bởi "gate citation hợp lệ" | **mở** — C2 sở hữu `messages`/`core/llm`, không phụ thuộc kết quả đo C1 |
| C4 | thiếu tiêu chí citation | **nhận** claim-provenance contract, kèm ngõ cụt đã đo |
| C5 | `Target` | **không đổi** — plan này không chạm |
| S1 | chặn bởi C1, C4 | vẫn chặn bởi **C4** |
| Track S | — | **không đụng** |

## 7. Hai concern của phase 03 — đã đóng lúc đóng plan

**`ADVERSARIAL_PAGE` chép ở bốn file → gom về `tests/agent_tool_world.py`.** Bốn
test khẳng định trên verdict của **chính** văn bản đó; một bản trôi đi sẽ để một
file pass trên trang không ai quét. Module scaffolding đã có sẵn, chỉ thêm một
hằng. Surface nới trong `CLAUDE.md`, không phải một dòng lách.

**`executor._dispatch` không bọc `try` quanh `scan_for_threats` — đúng, giữ nguyên.**
Kiểm lại `untrusted.py:188`: hàm có `except Exception` bao trùm trả
`risk: "unknown"`, và docstring của nó viết ra rằng *"mọi đường ra khỏi nó là một
verdict… không exception nào thoát"*. Guard ở executor sẽ là nhánh **không bao giờ
chạy**, và nó dời luật "fail-open tuyệt đối" ra khỏi chỗ luật đó thuộc về. Không
sửa — đây là phán đoán được xác minh, không phải nợ.

## 8. Câu hỏi chưa giải quyết

1. **Claim-provenance contract có hình dạng gì.** Hai hướng: runtime suy provenance
   lúc dựng câu trả lời, hay prompt buộc model trưng premise + phép tính rồi grader
   chỉ verify. Hướng hai đo được và sạch, nhưng đổi prompt — thuộc plan của C4,
   không phải một dòng nới ở đâu đó.
2. **`read_depth` phẳng chưa chứng minh ở n = 20.** Không chặn (nó là diagnostic),
   nhưng cache `WebLane` khiến "chạy thêm lượt trong ngày" không tăng n hiệu dụng.
3. **Chưa đo lớp quét trên trang thật mang injection.** Test dùng payload dựng
   sẵn. Corpus không dựng được nội dung trang, và trộn trang bịa vào corpus web-first
   sẽ làm nó không còn đo hành vi thật trên web thật.
4. **Ai sở hữu và chấm Golden Set** — nợ cũ chưa trả, corpus vẫn do C4-lite tự viết.
