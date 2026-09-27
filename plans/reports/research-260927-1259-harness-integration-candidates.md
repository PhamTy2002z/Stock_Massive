# Ứng viên tích hợp cho harness — đối chiếu với lỗi đã biết

Ngày: 27/09/2026 (Asia/Saigon) · Nhánh: `feat/host-owned-numbers` (chưa merge) · Model thử: `kiro-glm-5`.
Báo cáo gộp từ ba nghiên cứu chi tiết cùng ngày (nguồn và ngày của từng nguồn nằm trong đó):

- `researcher-260927-1300-grounding-and-reference-free-eval.md` (câu A, E)
- `researcher-260927-1300-vn-market-data-and-financial-calc.md` (câu C, D)
- `researcher-260927-1300-hermes-patterns.md` (câu B)

cộng với việc đọc code và kết quả selftest trên nhánh hiện tại (`evals/ROUNDS.md`, `evals/ITERATIONS.md`,
`plans/reports/delivery-260926-1600-host-owned-numbers.md`).

## 0. Trạng thái thật của 6 lỗi trước khi chọn công cụ

Danh sách lỗi trong đề bài cũ hơn code. Nhánh `feat/host-owned-numbers` (P0–P3, 26/09/2026) đã đóng một
phần lớn. Đề xuất bên dưới nhắm phần **còn hở**, đo được trên selftest vòng 1–2 ngày 27/09/2026.

| # | Lỗi | Đã có trên nhánh | Còn hở (bằng chứng) |
|---|---|---|---|
| 1 | Sai năm | Đuôi prompt có `today`, `market_today`, `previous_trading_day` (`prompt/contract.py:226`); `get_market_data` do host chọn cửa sổ; `web_search` gắn `year_note` khi truy vấn chứa năm cũ (`tools/web.py:322`) | `year_note` chỉ là **lời nhắc**: vòng 1, A3 tìm "tuần 21-25 tháng 9 2025", N6 tìm "… 2024"; vòng 2, A3 gọi `get_market_data` end=2025-06-23 ba lần. Đuôi prompt không có thứ: N8 và A4 nói "27/09/2026 là thứ Bảy" (thật ra là Chủ nhật). Ngày trong prose không được kiểm (delivery report, "Remaining risks") |
| 2 | Số không có trong tool | `grounding.py` kiểm **mọi** số trên **mọi** lane, một vòng sửa, số còn lại bị gắn `chưa kiểm chứng`; `calculate` in công thức; ràng buộc theo mã, theo kỳ, theo cột bảng | Số có thật nhưng **gắn sai ngữ cảnh** thì lọt: N4/N6 "Khối lượng 1,99 triệu [phiên 16/07/2026]" đặt dưới dòng phiên 25/09; N1 "P/B 2,21 (tính theo giá đóng cửa gần nhất)" thực ra là P/B tại 30/06. Khớp theo giá trị vẫn có thể trùng ngẫu nhiên trong nguồn dài |
| 3 | Verifier chỉ ở lane deep | Kiểm số xác định đã chạy ở mọi lane; verifier clean-context vẫn chỉ ở deep | **Đã đóng** cho phần số. Còn: lane deep từng rỗng vì planner trả prose (đã sửa ở vòng 2, `MAX_PLANNING_RETRIES = 1`) |
| 4 | Nguồn cũ / thiếu ngày | Nhãn `phiên dd/mm/yyyy`, `kỳ đến …`, `đăng …`; web > 120 ngày, tin > 30 ngày thành `nguồn cũ` | Trang web không có meta/JSON-LD/`<time>` thành "không rõ ngày" (`tools/web.py:168,205`): vòng 2 A3, N5, N9, A1 đều có số "[n · không rõ ngày]" |
| 5 | NPL/CAR/ROE/P/B từ báo | `get_financial_ratios` qua `FinancialsProvider` (KBS + Vietcap: NPL, coverage, NIM, LDR, CASA, ROE/ROA TTM, CAR khi có); `calculate` cho P/B theo giá hôm nay | CAR chỉ có ở quý ngân hàng công bố; nguồn miễn phí chỉ đủ tầm dev |
| 6 | Eval không golden | `evals/selftest.py` hỏi hệ thống thật, `evals/grade.py` chấm theo bất biến (viết độc lập với `grounding.py`), đối chiếu giá với VCI, replay offline | Bộ câu hỏi viết tay, chấm phần định tính bằng tay; chưa có quan hệ metamorphic, chưa có property test cho `grounding.py` |

## 1. Bảng ứng viên

Cột "Công sức" tính cho harness Python hiện tại. "Chưa xác minh" nghĩa là nghiên cứu không truy cập được
nguồn gốc (sandbox lỗi TLS với hầu hết domain `.vn`; một repo 404).

| Tên | Loại | Lỗi | Bằng chứng hiệu quả (ngày nguồn) | Trưởng thành | Rủi ro | Công sức | Link |
|---|---|---|---|---|---|---|---|
| Host tra ngày, cấm model tự nhớ năm; kiểm tham số tool | Pattern (Hermes) | 1 | `agent/prompt_builder.py:433-460`, sửa 26/09/2026: mở rộng sang DeepSeek/Kimi **sau khi eval đo được cùng lỗi**. Có code, chưa có số liệu công bố | Code production, MIT | Thấp. Không port tool terminal: thêm tool thực thi là quyết định scope | Thấp | github.com/NousResearch/hermes-agent |
| ID trích dẫn do host cấp, model chỉ echo số nguyên | Pattern (Hermes, Anthropic Citations) | 2, 4 | Hermes `skills/research/grounded-citations` (08/09/2026), `scripts/sources.py` (02/08/2026); Anthropic Citations API (blog chính thức, 24/01/2025). Chưa có số liệu độc lập | Code thật (Hermes); tính năng production (Anthropic, chỉ cho Claude) | Thấp; chỉ mượn pattern | Vừa–cao | claude.com/blog/introducing-citations-api |
| Probe hành vi tất định theo từng sự cố | Pattern (Hermes) | 6 | `evals/provider_fallback/probe_104120.py` (07/09/2026): server giả cục bộ, chặn egress, assert thứ tự/số lần gọi, không LLM chấm | Code thật | Thấp | Vừa | như trên |
| Kiểm số/ngày xác định với nguồn | Pattern học thuật (AIS; table-to-text faithfulness) | 2, 4 | AIS, Computational Linguistics 2023; khảo sát table-to-text 2021–2024. Xác nhận hướng `grounding.py` là chuẩn tham chiếu | Cao | Không | Đã có | github.com/google-research-datasets/AIS |
| FinGround (verify-then-ground, "formula reconstruction") | Paper | 2 | arXiv 2604.23588 (26/04/2026, ACL 2026 Industry): **tự công bố** giảm 68–78% hallucination tài chính. Repo `bettyguo/FinGround` **404** ngày 27/09/2026 | Paper tốt, code chưa công khai | Giấy phép không rõ | Chỉ mượn ý | arxiv.org/abs/2604.23588 |
| CoVe (câu hỏi kiểm chứng trả lời độc lập) | Pattern prompt | 2 | arXiv 2309.11495 (ACL Findings 2024): F1 0,39 → 0,48 trên MultiSpanQA | Cao | Không; nhưng vẫn là model tự kiểm | Vừa | arxiv.org/abs/2309.11495 |
| FreshQA (phân loại never/slow/fast-changing) | Benchmark, khung phân loại | 1, 4 | arXiv 2310.03214 (ACL Findings 2024): mọi LLM yếu ở câu fast-changing. Chỉ tiếng Anh | Cao | Không | Thấp (chỉ lấy khung ngưỡng) | arxiv.org/abs/2310.03214 |
| htmldate | Thư viện (trích ngày đăng từ HTML: meta, URL, văn bản) | 4 | Apache-2.0, push 25/09/2026 (gh api). **Chưa xác minh** nhận được định dạng byline báo Việt | Ổn định, cùng tác giả trafilatura | Thêm lxml | Thấp | github.com/adbar/htmldate |
| Hypothesis | Thư viện property-based test | 6 | MIT/MPL, chuẩn trong hệ pytest; bài hướng dẫn metamorphic cho LLM 12/04 và 18/04/2026 (định tính, không benchmark) | Rất cao | Không | Thấp | pypi.org/project/hypothesis |
| Metamorphic testing cho LLM | Phương pháp | 6 | arXiv 2605.13898 (05/2026): 191 quan hệ; arXiv 2511.02108 (ICSME 2025): 36 MR × 3 LLM ≈ 560 nghìn test | Cao (nhiều khảo sát đồng thuận) | Không | Thấp–vừa | arxiv.org/abs/2605.13898 |
| promptfoo (assertion xác định) | CLI + thư viện | 6 | MIT, push 27/09/2026, ~25,5 nghìn sao; local-first, cloud mặc định tắt | Rất cao | Thấp nếu tắt cloud | Thấp | github.com/promptfoo/promptfoo |
| Inspect AI (UK AISI) | Framework eval | 6 | MIT, push 26/09/2026; scorer viết bằng Python thuần được | Cao | Thấp | Vừa | github.com/UKGovernmentBEIS/inspect_ai |
| vnstock (đang dùng) | Thư viện | 5 | `LICENSE.md` bản 2026.09 đọc trực tiếp: dùng trong sản phẩm có doanh thu được, trong hạn mức; bán lại/cấp quyền truy xuất dữ liệu thì cần thỏa thuận | Cao, push 27/09/2026 | Source-available, không phải OSI | Đã có | github.com/thinh-vu/vnstock |
| FiinQuant / FiinQuantMCP | Vendor + MCP chính chủ | 5 | Thông cáo FiinGroup (khoảng 06/2026). Trường NPL/CAR, giá, điều khoản dữ liệu: **chưa xác minh** | Công ty lâu năm, MCP mới khoảng 3 tháng | Phải mua dữ liệu (đang là non-goal) | Cao | fiingroup.vn (thông cáo id2831997) |
| SSI FastConnect Data | API chính thức của công ty chứng khoán | 4, 5 (giá, không có chỉ số ngân hàng) | Tài liệu chính thức guide.ssi.com.vn; ngày cập nhật chưa xác minh | Cao | Cần tài khoản SSI; chạy trực tiếp với SSI | Vừa | guide.ssi.com.vn/ssi-products/fastconnect-data |
| Cổng công bố thông tin HOSE, HNX, UBCKNN | Nguồn chính thức | 4, 5 | Truy cập được ngày 27/09/2026; chỉ có HTML/PDF, không có XBRL (kết luận tạm vì tìm không ra) | Cao | Không | Cao (phải parse PDF) | hsx.vn, hnx.vn, congbothongtin.ssc.gov.vn |

## 2. Top 5 đề xuất theo thứ tự ưu tiên

Xếp theo mức lỗi còn đo được trên selftest ngày 27/09/2026, rồi đến công sức. Bốn trong năm mục là **tự
xây**: không có công cụ nào làm sẵn tốt hơn phần mở rộng nhỏ trên `grounding.py` và `executor.py` hiện có.

**1. Host chặn năm sai ở tham số tool và ghi thứ trong tuần vào đuôi prompt (đóng lỗi 1).**
Nâng `year_note` từ lời nhắc thành lỗi tham số: khi `web_search` chứa năm cũ, hoặc `start`/`end` của
`get_market_data` nằm hẳn trong năm cũ, mà câu hỏi của người dùng không nêu năm đó, executor trả lỗi kiểu
`INVALID_ARGUMENTS` kèm ngày hôm nay (đúng khuôn lỗi schema đã có) để model gọi lại. Thêm một dòng
`today_weekday` (ví dụ "Chủ nhật") vào `render()`.
Lý do: vòng 1 và vòng 2 cho thấy model yếu bỏ qua lời nhắc; chặn trước khi gọi thì không tốn quota
vnstock và không để lọt truy vấn sai. Hermes làm đúng việc này và mở rộng nó dựa trên eval đo được.
Công sức thấp. Cần chốt: chặn hay tự sửa lặng lẽ. Tôi đề xuất chặn, vì sửa lặng lẽ che mất lỗi của model
khỏi trace.

**2. Mở rộng `grounding.py` sang ngày trong prose (đóng lỗi 1 và 4).**
Ba luật xác định. (a) "dd/mm/yyyy là thứ X" phải đúng lịch. (b) Một ngày hoặc khoảng "tuần 21-25/9/2025"
có năm khác năm hiện tại, câu hỏi không nêu năm đó, và không nguồn nào trong Turn mang ngày đó, thì gắn
nhãn. (c) "hôm nay/phiên hôm nay" khi `market_today` không phải `open` thì gắn nhãn (vòng 1–2: A2, N8 nói
phiên 27/09 "chưa đóng cửa").
Lý do: delivery report ghi rõ "Prose dates are not checked". Công sức thấp–vừa, dùng lại
`periods()`/`_context` đã có.

**3. Trích ngày đăng cho trang web thiếu meta (đóng lỗi 4).**
Thứ tự fallback: ngày trong URL (`/2026/09/25/`, `-20260925`), byline tiếng Việt ("Thứ năm, 25/09/2026
14:30", "25/09/2026 - 14:30") trong phần đầu trang, rồi đến `htmldate` nếu hai bước trên không đủ.
Lý do: phần lớn nhãn "không rõ ngày" ở vòng 2 đến từ trang web. Mọi báo lớn ở Việt Nam đều in byline
trong HTML. Công sức thấp. Nên thử vài regex trong parser stdlib hiện có trước khi thêm `htmldate` + lxml.

**4. Con số do host cấp ID, host in số (đóng phần còn lại của lỗi 2).**
Mỗi giá trị trong kết quả tool mang một ID ngắn do host phát, gắn sẵn trường, kỳ và mã. Model viết tham
chiếu (ví dụ `⟦f12⟧`) thay vì gõ chữ số; host thay bằng số, định dạng và nhãn ngày. Số model tự gõ vẫn đi
qua kiểm literal như hiện nay (fallback, không bỏ).
Lý do: đây là cùng luật "host giữ số" của chart, mở rộng sang prose. Nó đóng được lớp lỗi mà khớp theo giá
trị không bắt được: số thật gắn sai phiên hoặc sai chỉ tiêu (N1, N4, N6), và số trùng ngẫu nhiên trong
nguồn dài. Memory dự án `derived-number-grader-impossible` đã kết luận cần claim-provenance cho việc này.
Hermes `grounded-citations` và Anthropic Citations dùng cùng nguyên tắc: model chỉ echo định danh.
Công sức vừa–cao. Rủi ro: model yếu có thể không dùng tham chiếu. Nên đo tỉ lệ dùng trên selftest trước
khi coi là đường chính.

**5. Bộ eval bất biến: metamorphic + property test (đóng lỗi 6).**
Giữ `evals/selftest.py` và `grade.py` làm lõi, thêm hai lớp.
(a) Metamorphic trên Turn thật: cùng câu hỏi đổi cách viết thì cùng tập số và cùng ngày nguồn; dời
`today` qua `RuntimeContext` (ví dụ sang một thứ Hai có phiên) thì năm trong tham số tool phải đi theo;
thêm "năm 2024" vào câu hỏi thì tool phải dùng 2024.
(b) Hypothesis cho `grounding.py`: sinh câu trả lời có số lấy ngẫu nhiên, ngoài nguồn, hoặc đổi đơn vị,
rồi assert mọi số không có trong nguồn đều bị gắn nhãn và không số nào được gắn nhãn sai kỳ.
Lý do: không cần golden, chạy xác định, không tốn model ở lớp (b). Hermes làm probe tất định theo từng sự
cố. promptfoo và Inspect AI chỉ đáng thêm khi bộ câu hỏi vượt khả năng hai script hiện có. Công sức thấp.

Không vào top 5, chờ product owner: **nguồn BCTC trả phí** (FiinQuant hoặc Vietstock DataFeed) cho CAR
đầy đủ. Đây là mua dữ liệu, đang là non-goal, và trường dữ liệu chưa xác minh được.

## 3. Phổ biến nhưng KHÔNG nên dùng cho hệ thống này

- **Ragas / DeepEval / TruLens làm cổng chặn "faithfulness/groundedness".** Lõi các metric này là LLM
  chấm. Một model chấm cho model yếu không thêm sự thật, chỉ thêm một điểm lỗi và chi phí; trái nguyên
  tắc "không tin model". Chỉ mượn được các metric con tất định.
- **FActScore / SAFE chạy lúc runtime.** Cần Google Search cộng LLM chấm cho từng atomic fact. SAFE đạt
  khoảng 72% đồng thuận với người, nhưng đo trên văn bách khoa tiếng Anh. Quá chậm để chạy mọi lane.
- **SelfCheckGPT.** Phải lấy mẫu nhiều lần cùng một câu hỏi. Route kiro có throttle và hạn mức (vòng 1
  đã dính 402), và số bịa lặp lại nhất quán vẫn qua được.
- **RARR, ALCE.** Repo dừng cập nhật (06/2023, 10/2024); RARR không có LICENSE.
- **MCP vnstock của cộng đồng** (`mrgoonie/vnstock-agent`, `gahoccode/vnstock-mcp`,
  `thieung/vnstock-plus-mcp` và các repo tương tự). Phần lớn 0–4 sao, nhiều repo không có LICENSE, chỉ
  bọc lại vnstock. Harness đã gọi vnstock qua một cửa có gate quota; thêm MCP là thêm một tầng gọi ngoài
  gate và một chỗ giữ khóa chưa audit. `archiephan78/ssi-stock-mcp-server` còn đòi nhập secret SSI.
- **Gọi thẳng endpoint ngầm** (`finfo-api.vndirect.com.vn`, TCBS nội bộ, `api.vietstock.vn`, scrape
  CafeF). Không có cam kết ổn định hay ToS cho phép; vnstock đã bọc phần hợp lệ.
- **Gói `vnstock-data` 0.0.1 trên PyPI.** Nhiều khả năng không phải kênh premium thật, có nguy cơ nhầm
  gói hoặc typosquat.
- **vietfin** (bỏ hoang từ 04/2024, tự giới hạn dùng cá nhân) và **empyrical / pyfolio** (bỏ hoang, lại
  đo lợi nhuận danh mục chứ không phải chỉ số BCTC).
- **FinanceToolkit, QuantLib.** FinanceToolkit (MIT, push 10/09/2026) có công thức rõ ràng nhưng không có
  NPL/CAR/NIM/LDR (đã grep mã nguồn), còn `calculate` đã bao các tỉ số phổ quát. QuantLib sai miền.
- **BloombergGPT/ASKB, Hebbia, Rogo, AlphaSense làm khuôn để chép.** Hệ đóng, số liệu hiệu quả chỉ đến từ
  blog của chính họ: đó là quảng cáo, chưa được chứng minh độc lập.
- **Pattern Hermes: skill tự sinh hoặc marketplace plugin, memory ghi free-text, tool terminal để lấy
  ngày.** Hai cái đầu đã bị bác trong synthesis cũ. Cái thứ ba là thêm tool thực thi, một quyết định scope;
  đồng hồ host cộng với kiểm ở executor cho cùng kết quả.

## 4. Phải tự xây (không có giải pháp sẵn)

1. **Luật năm và ngày ở executor và trong prose** (đề xuất 1, 2). Không có thư viện nào làm cho tiếng Việt
   và lịch giao dịch Việt Nam. Văn liệu (FreshQA, bài kỹ thuật 04/2026) chỉ xác nhận "đưa ngày vào prompt
   là chưa đủ".
2. **Figure-ID do host cấp** (đề xuất 4). Pattern có sẵn ở Hermes và Anthropic nhưng cho trích dẫn văn
   bản, chưa ai làm cho giá trị số có trường, kỳ và mã. FinGround gần nhất nhưng chưa công khai code.
3. **Byline tiếng Việt** (đề xuất 3). `htmldate` có thể bao một phần, chưa xác minh.
4. **Chỉ số an toàn vốn ngân hàng đầy đủ** (CAR mọi quý; nhóm nợ 1–5 để tự tính NPL). Không thư viện hay
   vendor nào được xác nhận có sẵn. Nếu không mua dữ liệu thì phải parse thuyết minh BCTC (phân loại nợ
   theo Thông tư 31/2024/TT-NHNN; tỷ lệ an toàn vốn theo Thông tư 41/2016/TT-NHNN) từ PDF trên cổng công bố
   thông tin, rồi tính trong provider theo đúng khuôn `calculate`.
5. **Bộ quan hệ metamorphic cho chứng khoán Việt Nam** (đề xuất 5). Không có benchmark tiếng Việt nào về
   độ mới hay độ trung thực của số; mọi ngưỡng (120 ngày, 30 ngày) là tự đặt, phải tự đo.
6. **Số đúng giá trị nhưng sai đơn vị** (tỷ và triệu trùng nhau). FAITH (arXiv 2508.05201) gọi đây là lỗi
   khó nhất, và cách phát hiện đã công bố vẫn cần LLM. Figure-ID (mục 2) né được lỗi này cho số lấy từ
   tool; số model tự gõ thì chưa có lời giải xác định.

## Câu hỏi chưa giải quyết

1. Luật năm ở executor nên **chặn** (tốn một round, lỗi hiện trong trace) hay **tự sửa** (rẻ, che lỗi)?
   Đề xuất: chặn.
2. Figure-ID thay đổi cách model viết câu trả lời. Có chấp nhận thử trên kiro-glm-5 với chỉ tiêu tỉ lệ
   dùng, và giữ kiểm literal làm fallback, không?
3. FiinQuantMCP, Vietstock DataFeed: có muốn liên hệ sales để xác minh trường NPL/CAR không? Sandbox không
   đọc được trang chính chủ, và việc này đụng quyết định "không mua dữ liệu".
