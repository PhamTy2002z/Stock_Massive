# Đề xuất end-to-end: khoảng trống và thứ tự làm — 2026-09-26

Nguồn: rà soát repo (develop @ 4bc6d81), chẩn đoán trực tiếp các Turn trên DB dev
hôm nay, golden artifact `release-v1-p04-report.json` (01/09), và báo cáo nền tảng
`researcher-260926-1423-global-ai-finance-platforms.md` (chỉ xác minh được ~9/20
nền tảng; phần còn lại dưới đây ghi rõ là hiểu biết chung, chưa xác minh phiên này).

## 1. Chẩn đoán "data ảo" — đã chứng minh trên Turn thật

Turn `f82f272c` ("Phân tích STB", 14:10 hôm nay, model `kiro-glm-5`, lane `light`):

| Bằng chứng | Nguyên nhân gốc |
|---|---|
| Lệnh `get_market_data` đầu tiên xin `2024-01-01 → 2025-01-20`, lệnh thứ hai `2025-01-01 → 2025-09-26`; web_search có query "ngày 26/9/2025" | **R1 — Neo sai năm.** Prompt có `today: 2026-09-26` nhưng model dùng năm trong trí nhớ (2025). Tool bắt model tự chọn `start/end` nên lỗi của model đi thẳng vào dữ liệu. |
| Tool trả STB đóng cửa 26/09/2025 = **56.500đ** (chạy lại xác nhận). Câu trả lời viết "Hiện tại (tháng 9/2025): 35.000–38.000đ". Giá thật 25/09/2026 = **76.500đ** | **R2 — Model viết số không có trong tool output**, và không có gì chặn. Số liệu 181 phiên có sẵn trong context nhưng model vẫn "ước lượng". |
| `agent_claim_ledger` = 0 dòng cho 14/15 Turn gần nhất | **R3 — Bộ kiểm chứng không chạy trên đường chính.** Ledger + verifier + counterevidence chỉ chạy ở lane `deep`, mà lane chọn bằng từ khoá (kiểm chứng, thẩm định, memo…) hoặc câu ≥240 ký tự. "Phân tích STB" → `light` → không ai kiểm số. |
| Vốn hoá "111.228 tỷ" ⇒ ~59.000đ/cp: số của một trang cũ | **R4 — Nguồn cũ không bị đánh dấu.** Kết quả không có ngày công bố chỉ bị lọc khi có `as_of`; câu trả lời không ghi ngày của từng con số. |
| Lần golden trả phí gần nhất: FAIL/incomplete, settlement 0%, evidence_identity 86%, material_claim & temporal_validity BLIND | **R5 — Không có thước đo đúng cho đúng lỗi này.** Corpus chưa hỏi được "số trong câu trả lời có khớp số trong nguồn không, và có đúng năm không". |

Model yếu (GLM-5 qua proxy) làm lỗi lộ rõ hơn, nhưng đổi model **không** sửa R1–R5:
hệ thống hiện tin model về ngày tháng và về con số, trong khi kiến trúc của chính nó
(host sở hữu số — như `visual.py`) đã nói điều ngược lại.

## 2. Sửa ngay (P0 — trong 1 tuần, không cần quyết định sản phẩm)

1. **Host sở hữu khoảng thời gian của `get_market_data`.** `end` mặc định = hôm nay
   (ICT), `start` mặc định = 3 tháng trước; model chỉ ghi đè khi người dùng nêu mốc
   cụ thể. Khi `end` cũ hơn hôm nay quá 7 ngày mà câu hỏi không có mốc, trả kèm
   `note: "hôm nay là 2026-09-26; khoảng bạn xin kết thúc 2025-01-20"`. Loại bỏ R1
   ở nguồn dữ liệu quan trọng nhất.
2. **Tool trả `latest` tách riêng**: phiên gần nhất (ngày, đóng cửa, % thay đổi, KL)
   ở đầu payload, trước 250 dòng. Model yếu đọc dòng đầu, không đọc dòng 181.
3. **Kiểm số tất định trên MỌI lane lúc settle.** Dùng lại
   `evidence/validation.py::validate_claims` + `numbers.contains` (đã có, đã test)
   đối chiếu mọi số trong câu trả lời với tool output của Turn. Số không có nhân
   chứng → một vòng sửa ("các số sau không có trong nguồn: …, sửa hoặc bỏ"), vẫn
   còn thì gắn nhãn "chưa kiểm chứng" trong UI. Không tốn LLM ở bước kiểm; tối đa
   thêm 1 vòng. Giới hạn đã biết: số suy diễn (%, trung bình) có thể "trùng" nhân
   chứng ngẫu nhiên (xem memory grader số suy diễn) — bắt được số bịa trắng trợn
   như 35.000 vs 56.500, không bắt được mọi số tính sai.
4. **Neo năm cho web_search.** Query chứa năm < năm hiện tại mà câu hỏi người dùng
   không nhắc năm đó → trả warning trong tool result (không tự sửa query). Mỗi kết
   quả hiển thị `publishedAt`; prompt yêu cầu ghi "(theo X, ngày dd/mm/yyyy)" cạnh
   mỗi con số tài chính.
5. **Golden case cho đúng lỗi này**: 5–8 case "giá/định giá mã X hiện tại" chấm
   bằng (a) số khớp tool output, (b) năm được nhắc = năm hiện tại. Chạy tape-replay
   miễn phí trước, 1 lần trả phí sau.

Tiêu chí nghiệm thu P0: chạy lại đúng 4 câu đã test ("Phân tích STB", "STB hôm nay",
"Phân tích thị trường tuần qua", "VIC hôm nay") — 0 số giá sai năm, 0 số giá không
có trong tool output, mỗi số tài chính có ngày nguồn.

## 3. Năng lực AI còn thiếu (so với chuẩn ngành)

| Hạng mục | Hiện có | Chuẩn ngành (AlphaSense, Hebbia, Rogo, Fiscal.ai, Perplexity Finance*) | Mức |
|---|---|---|---|
| Dữ liệu giá | OHLCV 1D/15m, 1 mã/lệnh | Giá + chỉ số + ngành, nhiều mã | Có, đủ dùng |
| **BCTC có cấu trúc** | Không (chỉ đọc PDF/web) | Bảng KQKD/CĐKT/LCTT theo quý, chỉ số tính sẵn | **Cần** — nguồn gốc của hầu hết số NPL/CAR/ROE bị ảo |
| Sự kiện DN (cổ tức, phát hành, ĐHCĐ) | Không | Có | Cần |
| Tin tức có ngày, có nguồn | web_search chung | Feed tin + lọc theo mã/ngày | Nên |
| Tính toán minh bạch | Model tự tính trong đầu | Công cụ tính, hiện công thức (P/E = giá/EPS) | **Cần** — cùng họ lỗi R2 |
| Kiểm chứng claim | Chỉ lane deep | Trích dẫn cấp câu trên mọi câu trả lời | **Cần** (P0.3 là bước đầu) |
| Bộ lọc cổ phiếu bằng ngôn ngữ tự nhiên | Không | Table stakes | Nên (cần BCTC trước) |
| Theo dõi/alert, tác vụ định kỳ | Không (đã retire watchlist) | Có ở hầu hết | Nên, sau khi độ đúng ổn |
| Phân tích nhiều tài liệu dạng bảng (Matrix) | Không | Khác biệt của Hebbia | Chưa cần |
| Xuất Excel/memo/deck | Không | Khác biệt của Rogo | Chưa cần |
| Chống prompt injection | Có (`untrusted.py`) | Không vendor nào công bố | **Lợi thế** |
| Chart host dựng, model không gửi số | Có (`visual.py`) | Hiếm | **Lợi thế** — mở rộng nguyên tắc này sang câu chữ |

\* Perplexity Finance, Fiscal.ai, Bloomberg, LSEG, CapIQ: không truy cập được trong
phiên research; cột này dựa trên hiểu biết chung, cần xác minh lại trước khi trích.

## 4. Chức năng app còn thiếu

| Cần (ảnh hưởng niềm tin/giữ chân) | Nên | Chưa cần |
|---|---|---|
| Hiển thị trích dẫn inline + ngày nguồn cạnh số | Watchlist cá nhân (không phải global đã retire) | Mobile app native |
| Nhãn "chưa kiểm chứng" trên số không có nhân chứng | Alert giá/sự kiện qua email | Chia sẻ công khai |
| Thẻ "dữ liệu tới phiên dd/mm" trên mỗi câu trả lời có giá | Xuất câu trả lời ra PDF/Markdown | Portfolio tracking |
| Nút báo sai trên từng câu trả lời → vào corpus golden | Lịch sử câu hỏi theo mã | Đặt lệnh |
| Disclaimer rõ ranh giới nghiên cứu/tư vấn (mẫu Public.com Alpha) — Turn "có nên mua DCA STB" cần kiểm | | |

## 5. Lộ trình đề xuất

| Giai đoạn | Nội dung | Phụ thuộc | Nghiệm thu |
|---|---|---|---|
| **P0 (tuần này)** | Mục 2 | Không | 4 câu test sạch; golden case mới xanh trên tape |
| **P1 (2–3 tuần)** | Tool BCTC có cấu trúc (vnstock `Finance` — cùng giấy phép cá nhân) + tool tính toán có công thức; kiểm số mở rộng sang số BCTC | Chủ sản phẩm chọn nguồn BCTC | NPL/CAR/ROE/P/B trong câu trả lời khớp bảng nguồn 100% |
| **P2 (2 tuần)** | UI trích dẫn inline, nhãn chưa kiểm chứng, nút báo sai | P0 | Người dùng thấy nguồn + ngày của mọi số |
| **P3** | Sự kiện DN, tin theo mã, screener NL | P1 | Golden corpus mở rộng |
| **P4** | Watchlist cá nhân + alert/tác vụ định kỳ | Quyết định sản phẩm (đã từng retire) | — |

Plan `260906-1557-financial-research-agent` đã có khung cho P1/P3 (phase 3–5). Đề
xuất: **chèn P0 lên trước**, không chờ Signal Desk graduation, vì Chat giờ là toàn
bộ sản phẩm và lỗi đang ở Chat.

## Trade-offs

- **Kiểm số tất định (chọn) vs chạy lane deep cho mọi Turn**: deep tốn thêm 3–4 lượt
  model mỗi Turn và vẫn dựa vào verifier là model; kiểm tất định rẻ và không bị ảo,
  nhưng hỏng đầu tiên ở số suy diễn.
- **Host đặt khoảng ngày (chọn) vs chỉ sửa prompt**: prompt đã nói đúng và model vẫn
  sai — prompt là giả định đã thất bại trên dữ liệu thật.
- **Đổi model mạnh hơn**: giảm tần suất nhưng không đóng R2–R5; làm song song được,
  không thay thế.

Better approaches: không có hướng tốt hơn ngoài chính nguyên tắc sẵn có của repo
("host sở hữu số") — đề xuất chỉ mở rộng nó từ chart sang câu chữ.

## Câu hỏi còn mở

1. Kiểm số không đạt sau 1 vòng sửa: gắn nhãn "chưa kiểm chứng" (đề xuất) hay xoá số?
2. Nguồn BCTC có cấu trúc cho P1: vnstock Finance (giấy phép cá nhân) hay mua vendor?
3. Có giữ `kiro-glm-5` làm route dev không, hay chuyển model mạnh hơn cho test UI?
4. Watchlist/alert từng bị retire — có mở lại dạng cá nhân ở P4 không?
