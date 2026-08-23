# Investment Intelligence contract

Tài liệu này định nghĩa sản phẩm mà AI harness phải phục vụ. Nó là contract về
outcome và truth, không phải đặc tả UI hoặc danh sách feature. Mọi thay đổi model,
tool, memory, subagent hoặc provider phải chứng minh rằng nó làm contract này
tốt hơn mà không phá safety boundary.

## North star

Stock_Massive biến dữ liệu thị trường Việt Nam thành **decision-grade
intelligence**: câu trả lời có thời điểm, nguồn, mức chắc chắn, giả định, yếu tố
phản chứng và hệ quả đối với mục tiêu của người dùng. Hệ thống phải giúp người
dùng hiểu “điều gì đang xảy ra, vì sao, điều gì có thể làm kết luận sai và cần
quan sát gì tiếp theo”, thay vì chỉ sinh một dự đoán hoặc một đoạn văn nghe hợp
lý.

AI chịu trách nhiệm cho những việc cần phán đoán và tổng hợp:

- hiểu câu hỏi và horizon thực sự;
- lập kế hoạch lấy bằng chứng theo nhu cầu;
- chọn capability phù hợp;
- so sánh các giả thuyết và phát hiện mâu thuẫn;
- diễn giải số liệu trong bối cảnh doanh nghiệp, ngành và thị trường;
- tạo kịch bản, trigger phản chứng và follow-up có ích;
- cá nhân hóa cách giải thích theo mục tiêu và risk context đã biết.

Deterministic modules chịu trách nhiệm cho những việc model không được tự xác
nhận:

- identity, authorization và data scope;
- point-in-time selection và freshness;
- phép tính, unit, sign convention và rounding;
- market rules, settlement và price-band mechanics;
- tool execution, budget, persistence và audit;
- policy cho side effect và dữ liệu nhạy cảm.

## Definition of intelligence

Một output chỉ là intelligence khi nó kết nối bằng chứng với quyết định trong
một contract có thể kiểm tra. Nội dung nhiều hoặc reasoning dài không tự tạo ra
intelligence.

Một outcome đạt chuẩn phải trả lời được các câu hỏi sau khi áp dụng:

1. **As of when?** Dữ liệu đúng tại trading session, kỳ báo cáo hoặc thời điểm
   nào?
2. **Based on what?** Figure, source và phép biến đổi nào hỗ trợ từng claim
   trọng yếu?
3. **Compared with what?** Baseline là lịch sử của chính mã, peer group, market
   hay giả định người dùng?
4. **How certain?** Đây là fact, estimate, hypothesis hay scenario; chất lượng
   dữ liệu và uncertainty ra sao?
5. **What could invalidate it?** Dữ liệu thiếu, mâu thuẫn, regime, corporate
   action hoặc event nào làm conclusion đổi?
6. **Why does it matter?** Hệ quả phải gắn với horizon, objective và risk
   context, không phải một CTA chung cho mọi người.

## Epistemic contract

Hệ thống dùng vocabulary cố định để ngăn model trộn dữ liệu, suy luận và hành
động vào cùng một câu không thể audit.

| Loại | Nghĩa | Yêu cầu tối thiểu |
|---|---|---|
| **Observation** | Dữ liệu nhận từ store hoặc nguồn ngoài | source, observed-at, effective/as-of, unit, quality |
| **Derived metric** | Kết quả deterministic từ observation | method/version, inputs, window, unit, uncertainty khi có |
| **Claim** | Phát biểu được evidence hỗ trợ | evidence references, scope, confidence |
| **Hypothesis** | Cách giải thích chưa được chứng minh | supporting và contradicting evidence, falsifier |
| **Scenario** | Kết quả có điều kiện | assumptions, horizon, sensitivity, không gắn probability giả |
| **Judgment** | Tổng hợp phục vụ quyết định | objective/risk context, alternatives, uncertainty |
| **Action proposal** | Bước người dùng có thể cân nhắc | prerequisites, risk, approval; không tự execute |

Model có thể tạo claim, hypothesis, scenario và judgment. Model không được biến
một hypothesis thành observation, tự tạo figure, tự sửa effective date hoặc tự
khai rằng deterministic validation đã pass.

## Financial truth model

Financial truth không chỉ là một con số đúng. Nó là một con số đúng với entity,
thời điểm, nguồn, phiên bản và phép biến đổi cụ thể.

Mọi evidence có ảnh hưởng đến kết luận phải bảo toàn các thuộc tính sau ở owner
machine-readable phù hợp:

- entity và market/exchange;
- event time, effective time, publication time và ingestion time khi khác nhau;
- source/provider và retrieval trace;
- raw hoặc derived status;
- unit, currency, scale và sign convention;
- adjustment policy, bao gồm corporate action khi liên quan;
- window, sample size và point-in-time universe;
- freshness/quality/refusal reason;
- method hoặc contract version.

**Target:** answer rendering phải tham chiếu evidence identity thay vì copy số
từ transcript như một chuỗi không có provenance. `apps/api/src/alpha/envelope.py`
và Signal Field contracts là owner hiện tại gần nhất; target architecture mở
rộng invariant này cho mọi intelligence lane.

## Point-in-time và anti-lookahead

Mọi phân tích lịch sử, so sánh và eval phải chỉ dùng thông tin có thể biết tại
thời điểm đang đánh giá. Đây là hard invariant vì lookahead tạo output rất thuyết
phục nhưng vô giá trị đầu tư.

- Dùng trailing window và universe có hiệu lực tại thời điểm đó.
- Không dùng filing theo kỳ nếu publication time đến sau as-of.
- Không dùng classification, adjustment hoặc symbol mapping hiện tại để sửa quá
  khứ mà không version.
- Không tính cross-section từ tập mã sống sót đến hiện tại.
- Không dùng news publication timestamp thay cho event/effective timestamp.
- Không đánh giá recommendation bằng giá mà người dùng không thể giao dịch tại
  thời điểm quyết định.

Các microstructure contract đã nghiên cứu—price band theo sàn/ngày, T+2,
limit-lock, thanh khoản và corporate action—phải nằm trong deterministic data
hoặc calculation owner, không chỉ trong prompt. Xem
[quant methods research](../research/quant-methods-eod-vn.md).

## Evidence hierarchy và conflict

Nguồn không có cùng authority. Hệ thống phải giữ cả provenance lẫn conflict,
không chọn một con số im lặng chỉ vì nó xuất hiện sau.

Thứ tự mặc định là:

1. dữ liệu chính thức từ exchange, regulator hoặc issuer;
2. dữ liệu đã persist và version trong Stock_Massive với provenance đầy đủ;
3. provider có contract và freshness rõ;
4. nguồn web first-party;
5. nguồn thứ cấp uy tín;
6. suy luận của model.

Thứ tự này là default, không phải luật “nguồn trên luôn đúng”. Khi nguồn mâu
thuẫn, outcome phải nêu khác biệt, thời điểm, đơn vị và lý do có thể có; không
được trung bình hóa hoặc chọn theo convenience. Quyết định hiện tại “store
figure thắng web figure” vẫn giữ cho cùng semantic/as-of, nhưng semantic hoặc
as-of khác nhau phải được giải thích thay vì coi là conflict đã giải.

## Investment intelligence axes

AI phải có thể kết hợp nhiều axis thay vì tối ưu một indicator. Mỗi axis là một
evidence family, không phải một agent bắt buộc.

| Axis | Câu hỏi chính | Ràng buộc riêng |
|---|---|---|
| Market and regime | Môi trường chung hỗ trợ hay chống lại thesis? | breadth, liquidity, volatility, market calendar |
| Technical and microstructure | Giá, volume, trend và tradability nói gì? | band, limit-lock, T+2, adjusted history |
| Fundamental and valuation | Chất lượng, tăng trưởng và valuation thay đổi ra sao? | filing publication time, period, accounting comparability |
| Flow and positioning | Dòng tiền và room tạo pressure gì? | persistence, ADTV normalization, ceiling effects |
| News and events | Sự kiện nào mới, material và đã phản ánh vào giá chưa? | event/entity resolution, duplication, source credibility |
| Cross-sectional and peers | Mã đứng đâu trong opportunity set? | point-in-time universe, sample floor, peer definition |
| Portfolio and risk | Claim ảnh hưởng tổng exposure và downside thế nào? | holdings freshness, correlation uncertainty, concentration |
| User objective | Intelligence có phù hợp horizon và constraints không? | explicit typed preferences; không suy đoán profile nhạy cảm |

## Output contract

Một answer không bắt buộc theo template cứng, nhưng semantic contract phải tồn
tại trong trace và phần trình bày phải giúp người dùng nhận ra nó.

Outcome hoàn chỉnh cần có:

- direct answer hoặc verdict có scope;
- as-of và freshness khi thời gian ảnh hưởng kết luận;
- evidence trọng yếu và citation/provenance;
- uncertainty, missing data và conflict có ý nghĩa;
- bull/base/bear hoặc alternative hypotheses khi câu hỏi có tính dự báo;
- falsifier hoặc trigger cần theo dõi;
- implication theo horizon/risk context;
- concrete next step, nếu người dùng cần, nhưng không vượt autonomy level.

Khi evidence không đủ, hệ thống trả phần đã biết và concrete blocker. Nó không
được tạo màn hình trắng, nhưng cũng không được biến fail-open thành quyền bịa.
Guardrail vận hành fail-open cho presentation; truth-critical computation và
authorization fail-closed tại deterministic owner.

## Autonomy contract

Năng lực suy luận và quyền tạo side effect là hai trục độc lập. Model mạnh hơn
không tự nhận thêm quyền.

| Cấp | AI được làm | Trạng thái |
|---|---|---|
| A0 — Explain | Đọc evidence đã cấp và giải thích | **Current** |
| A1 — Investigate | Tự lập kế hoạch, gọi read-only tools, kiểm chứng và tạo artifact | **Target** |
| A2 — Monitor | Duy trì thesis/watch condition và chủ động báo thay đổi trong quota | **Target** |
| A3 — Propose | Soạn action hoặc rebalance proposal có risk/sensitivity | **Conditional** |
| A4 — Execute | Gửi lệnh hoặc thay đổi tài sản | **Rejected** cho đến khi có quyết định product, legal, broker và approval riêng |

Không dùng broad shell, arbitrary code, remote instruction hoặc generic MCP để
đi vòng qua autonomy level. Capability mới phải được phân loại read/write,
external/internal, data sensitivity và approval requirement tại registration.

## Non-goals

Các mục dưới đây không thuộc product contract hiện tại dù có thể xuất hiện ở
harness tham khảo.

- Trở thành coding agent hoặc general-purpose desktop operator.
- Hỗ trợ mọi provider/model chỉ để có portability checklist.
- Tạo prediction chắc chắn hoặc cam kết alpha từ LLM reasoning.
- Thay deterministic financial calculation bằng chain-of-thought.
- Dùng multi-agent như feature trình diễn khi single-agent chưa có baseline.
- Cho memory hoặc skill tự sửa trở thành policy đặc quyền.
- Tối ưu engagement bằng cảnh báo hoặc khuyến nghị không có materiality gate.

## Acceptance criteria

Một thay đổi lớn của AI harness chỉ phù hợp contract khi trả lời được tất cả các
câu hỏi sau bằng test, eval hoặc trace.

1. Outcome tài chính nào tốt hơn và bằng metric nào?
2. Evidence identity, as-of và uncertainty được bảo toàn ở đâu?
3. Failure mode mới là gì và fallback có làm giảm truth không?
4. Cost, latency và context pressure thay đổi thế nào trên successful outcome?
5. Capability hoặc dữ liệu nào model nhận thêm, và policy nào chặn escalation?
6. Có thể lấy một invariant nhỏ hơn thay vì nhập cả subsystem không?

## Câu hỏi chưa giải quyết

Các câu hỏi này thuộc product contract và phải được quyết định trước capability
tương ứng.

- “Investment Intelligence” phục vụ single-symbol research trước hay portfolio
  decision trước khi mở proactive monitoring?
- User risk context tối thiểu gồm horizon, drawdown tolerance và liquidity need
  hay cần suitability profile đầy đủ hơn?
- Output có được dùng như regulated advice hay chỉ là research/education; legal
  language và audit retention phụ thuộc trực tiếp vào lựa chọn này?
