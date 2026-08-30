# Research: khoảng trống của sản phẩm theo dõi luận điểm trên thị trường

Ngày kiểm tra nguồn: **2026-08-30**  
Persona: nhà đầu tư tự quyết định tại Việt Nam, theo dõi 5–30 mã, horizon vài
tuần đến vài tháng.  
Phạm vi đề xuất dùng để đối chiếu: một **Delta Inbox** sau phiên hoặc theo sự
kiện, chỉ chứa *Material Changes* liên quan tới luận điểm do người dùng viết;
deterministic detection, AI diễn giải; không buy/sell, broker sync, realtime,
push/email trong V1.

## Kết luận trực tiếp

**“Watchlist + cảnh báo + AI tóm tắt” và cả “AI tự chạy theo lịch/sự kiện” không
phải khoảng trống.** FireAnt và FiinTrade đã mạnh ở cảnh báo realtime tùy biến
cho mã/danh mục Việt Nam; Seeking Alpha và Koyfin đã ghép portfolio/watchlist
với news, filing, rating và nhiều kênh giao; Quartr Pro đã cho người dùng viết
prompt một lần, chạy theo tài liệu mới hoặc lịch ngày/tuần/tháng trên cả
watchlist, rồi trả kết quả kèm citation tới đúng trang nguồn. Fiscal.ai còn cung
cấp một `watchlist-monitor` source-linked cho generic LLM, đúng quy mô tối đa 25
mã của persona này.

Phần chưa được chứng minh là khoảng trống sản phẩm, nhưng đủ rõ để **đưa vào
thử nghiệm**, gồm:

1. luận điểm có cấu trúc, version, falsifier và horizon thực sự chi phối việc
   xếp hạng thay đổi nào đáng đọc;
2. materiality gate deterministic dành cho dữ liệu/sự kiện/microstructure Việt
   Nam, trước khi AI giải thích implication;
3. inbox delta có ngân sách chú ý và dấu vết “vì sao xuất hiện / vì sao bị bỏ”,
   thay vì thêm một luồng notification.

Đây không phải quyết định build. Quartr là bằng chứng mới đủ mạnh để bác mọi
định vị rộng kiểu “proactive, personalized, evidence-backed monitoring”.

## Phương pháp và cách đọc bằng chứng

- Chỉ dùng trang sản phẩm, pricing, help/docs, release note hoặc demo first-party;
  không dùng review, listicle hay bảng so sánh của bên thứ ba.
- **Fact** nằm trong hai ma trận dưới và có link trực tiếp gần claim.
- `CXN` nghĩa là **chưa xác minh được từ nguồn công khai đã đọc**, không có nghĩa
  sản phẩm chắc chắn không có.
- **Inference** chỉ nằm ở mục “Điều thị trường cho phép suy ra”. Không suy từ
  việc thiếu tài liệu thành khẳng định feature không tồn tại.
- Giá là giá niêm yết thấy được ngày kiểm tra, chưa gồm khuyến mại/thuế nếu trang
  không nói rõ.

## Ma trận fact — job, trigger và context được lưu

| Sản phẩm | Recurring monitoring job | Trigger / cadence | Watchlist / thesis context được lưu | Personalization |
|---|---|---|---|---|
| **FireAnt (VN)** | Cảnh báo điều kiện cho mã; Watchlist được dùng làm đối tượng cảnh báo và theo dõi xuyên các màn hình ([Watchlist guide](https://www.fireant.vn/Guide/Detail/304), [help 2026](https://help.fireant.vn/projects/fireant-mobile/features/ma-chung-khoan/canh-bao/)). | Chạm ngưỡng giá/khối lượng, vượt/thủng 52 tuần, giá cắt SMA; chạy để báo khi điều kiện xảy ra, thiên realtime/intraday. | Lưu watchlist và từng điều kiện. `CXN`: thesis/horizon/falsifier có cấu trúc. | Người dùng chọn mã, loại tín hiệu, ngưỡng; gói cao mở nhiều cảnh báo và chỉnh sâu hơn. |
| **FiinTrade Signal (VN)** | Market Signal quét thay đổi bất thường; cảnh báo áp vào danh mục riêng và gửi khi vượt ngưỡng ([Market Signal](https://docs.fiintrade.vn/fiintrade-signal/tin-hieu-thi-truong), [Danh mục](https://docs.fiintrade.vn/tinh-nang-danh-muc)). | Dữ liệu lũy tiến realtime; bộ lọc theo 1m/5m/15m/1h/4h, giá, khối lượng, mua/bán chủ động, khối ngoại và tham số do user đặt ([Bộ lọc/cảnh báo](https://docs.fiintrade.vn/fiintrade-signal/tinh-nang-bo-loc-co-phieu)). | Nhiều danh mục có thể đặt theo chiến lược/ngành/horizon; lưu tiêu chí lọc. `CXN`: hệ thống lưu và đánh giá nội dung luận điểm/falsifier. | Tự cấu hình tham số, timeframe, mã/ngành/index/danh mục riêng. |
| **Simplize (VN)** | `CXN` recurring job. Fact công khai xác nhận theo dõi cổ phiếu, quản lý portfolio, watchlist và AI assistant, nhưng không mô tả job chủ động ([pricing](https://simplize.vn/pricing), [trang mã có watchlist/ghi chú/AI](https://simplize.vn/co-phieu/HVN)). | `CXN` trigger/cadence. | Basic có 1 watchlist, Professional không giới hạn; trang mã có ghi chú. `CXN`: ghi chú được dùng làm context cho AI/monitor. | Chọn watchlist, danh mục và dữ liệu phân tích; quan hệ giữa personalization và notification `CXN`. |
| **Seeking Alpha** | Alert realtime theo portfolio cho content/news/filing/price/rating; Portfolio Digest tổng hợp hàng ngày ([alert guide](https://help.seekingalpha.com/basic/how-do-i-manage-my-email-alerts), [portfolio setup](https://help.seekingalpha.com/how-do-i-set-up-real-time-alerts-for-my-seeking-alpha-portfolio)). | Event khi có content/news/filing, vượt giá, đổi rating; digest mỗi ngày. | Portfolio/watchlist/holdings và note theo từng mã được lưu ([portfolio notes](https://help.seekingalpha.com/basic/how-do-i-add-notes-to-my-portfolio-on-the-app)). `CXN`: notes trở thành thesis context của alert/AI. | Chọn portfolio/mã, loại nội dung, tác giả, giá/rating và kênh cho từng loại. |
| **Koyfin** | Alert theo mã, watchlist và portfolio cho tài liệu, giá, valuation và technicals ([Desktop Alerts](https://www.koyfin.com/help/release-notes/v3-66-desktop-alerts/)). | New press release/news/filing/transcript hoặc condition; user đặt frequency cho price/technical/valuation. | Lưu watchlist, portfolio và optional note trong alert. `CXN`: thesis/falsifier có cấu trúc hoặc note chi phối interpretation. | Scope là mã/list/portfolio; chọn document/condition/frequency và kênh. |
| **Fiscal.ai** | Dashboard có notification theo watchlist/portfolio; skill `watchlist-monitor` tạo what-changed dashboard tối đa 25 mã nhưng là một lần chạy theo yêu cầu; API có webhook khi dữ liệu đổi ([platform](https://fiscal.ai/), [MCP Skills](https://docs.fiscal.ai/docs/guides/mcp-skills), [webhooks](https://docs.fiscal.ai/docs/guides/webhooks)). | Press release, filing, call/news update; webhook khi financial data update; cadence tự động cho `watchlist-monitor` `CXN`. | Lưu dashboard/watchlist/portfolio. MCP có thể dùng memory của client, nhưng nguồn không mô tả thesis object của Fiscal ([MCP integration](https://docs.fiscal.ai/docs/guides/mcp-integration)). | User chọn mã, dashboard rows/metrics; prompt tự nhiên định nghĩa lần phân tích. |
| **Quartr Pro** | Automation chạy nghiên cứu khi công ty công bố tài liệu hoặc theo lịch; scope một công ty hay cả watchlist ([Automations](https://quartr.com/features/automations)). | Event: first document, transcript, slide hoặc report; schedule: daily/weekly/monthly. | Lưu nhiều watchlist và prompt tái sử dụng; prompt định nghĩa phân tích và có thể yêu cầu “flag what changed”. `CXN`: typed thesis/version/falsifier riêng ngoài prompt ([Watchlists](https://quartr.com/features/watchlists), [AI chat](https://quartr.com/features/ai-chat)). | Tùy biến prompt, watchlist/company, event/document, cadence và delivery; có thể tham chiếu peer/holdings watchlist. |

## Ma trận fact — evidence, delivery, AI và paywall

| Sản phẩm | Evidence / provenance | Notification / delivery | AI thực sự làm gì trong flow đã xác minh | Pricing / paywall |
|---|---|---|---|---|
| **FireAnt** | Alert nêu condition trên dữ liệu mã. `CXN`: citation tới nguồn gốc figure/document, as-of và evidence identity trong alert. | Mobile notification; cần bật quyền thông báo ([help](https://help.fireant.vn/projects/fireant-mobile/features/ma-chung-khoan/canh-bao/)). | Copilot, Answer Engine và Report là feature tier; AI Prediction phân tích lịch sử để dự báo MA/xu hướng. `CXN`: AI diễn giải alert theo thesis ([bảng gói](https://help.fireant.vn/projects/fireant-membership/so-sanh-goi/), [AI Prediction](https://aiprediction.fireant.vn/vi)). | Free: tối đa 5 cảnh báo mobile. Professional 299k/tháng có nhiều cảnh báo, Copilot/Answer Engine; Cao cấp 599k/tháng thêm Report. |
| **FiinTrade Signal** | Dòng alert có thời gian, mã, nội dung, giá và % biến động; tham số tính lũy tiến được mô tả ([docs](https://docs.fiintrade.vn/fiintrade-signal/tinh-nang-bo-loc-co-phieu)). `CXN`: citation/source identity tới filing/news và uncertainty. | Alert hiện trong module; email được gửi khi vượt ngưỡng ([Market Signal](https://docs.fiintrade.vn/fiintrade-signal/tin-hieu-thi-truong)). | Fact công khai mô tả rule/filter và dữ liệu realtime. `CXN`: generative AI tham gia detection hoặc interpretation. | Trial/paid; trang giá hiện tại xác nhận Alert Tools/Market Signal là quyền gói nhưng giá số render động, không đọc được ổn định từ trang công khai ([pricing](https://web.fiintrade.vn/chinh-sach-gia)). |
| **Simplize** | Trang mã gắn báo cáo phân tích với nguồn/ngày; `CXN`: per-claim provenance trong AI answer hay monitor ([ví dụ trang mã](https://simplize.vn/co-phieu/HVN)). | `CXN` notification/delivery cho watchlist. | “Simplize AI” được quảng bá là trợ lý; tài liệu công khai đã đọc không giải thích input, trigger, audit hay quan hệ với watchlist. | Basic miễn phí: 1 watchlist. Professional: 599k/tháng hoặc 5,988 triệu/năm, không giới hạn watchlist và thêm forecast/risk/valuation/research ([pricing](https://simplize.vn/pricing)). |
| **Seeking Alpha** | Summary Report ghi ngày tạo, dùng content trên SA, Quant rating và company report; không independent analysis ([inputs](https://help.seekingalpha.com/what-content-is-the-virtual-analyst-report-based-on)). `CXN`: per-claim exact-source citation trong alert/AI report. | Email, mobile push; digest email theo portfolio ([alerts](https://help.seekingalpha.com/basic/how-do-i-manage-my-email-alerts)). | LLM tạo Summary Reports, không editor review và có thể sai; Earnings Call Insights tóm tắt transcript hiện tại + quý trước ([AI disclosure](https://help.seekingalpha.com/does-seeking-alpha-use-ai-to-generate-these-reports), [call inputs](https://help.seekingalpha.com/what-content-are-the-earnings-calls-insights-articles-based-on)). | Free account tạo portfolio và realtime alerts. Premium $299/năm mở AI research, full analysis và advanced portfolio tools ([free access](https://help.seekingalpha.com/can-i-access-seeking-alphas-content-without-a-subscription), [Premium](https://help.seekingalpha.com/what-is-seeking-alpha-premium)). |
| **Koyfin** | Alert document mở thẳng tài liệu; fundamentals có vendor nguồn công khai (S&P Capital IQ, Morningstar...). Không thấy per-claim citation cho summary ([alerts](https://www.koyfin.com/help/release-notes/v3-66-desktop-alerts/), [data sources](https://www.koyfin.com/help/faq/where-do-you-get-your-data/)). | Desktop bell, email, mobile push. | Transcript Summary tự động rút KPI, guidance, risks và Q&A; chỉ dựa trên transcript. Nguồn không gọi rõ công nghệ này là LLM/AI ([Transcript Summaries](https://www.koyfin.com/help/release-notes/v3-69-transcript-summaries/)). | Free: 5 alerts; Plus: 50; Premium: 500 và mới có watchlist/portfolio alerts. Giá niêm yết lần lượt $0/$39/$79 mỗi tháng ([alerts](https://www.koyfin.com/help/release-notes/v3-66-desktop-alerts/), [pricing](https://www.koyfin.com/pricing/)). |
| **Fiscal.ai** | Filing-backed figures có click-through audit tới đúng trang PDF; `watchlist-monitor` gắn source link cho từng tên bị flag ([MCP Skills](https://docs.fiscal.ai/docs/guides/mcp-skills)). | Monitor trả chat summary và HTML dashboard; sản phẩm có notification tab, API có webhook tới endpoint của khách hàng ([dashboard guide](https://fiscal.ai/blog/how-to-use-finchat/), [webhooks](https://docs.fiscal.ai/docs/guides/webhooks)). | AI skill điều phối endpoint, tạo dashboard “who reported / what moved / what filed / why”; dữ liệu và số giữ source link. Đây là bằng chứng trực tiếp generic LLM + financial data có thể làm what-changed scan. | Pro $39/tháng có Portfolio Stats và Curated News & Notifications; click-through filing auditability được bảng giá xếp ở Enterprise; MCP không vượt entitlement của plan ([pricing](https://fiscal.ai/pricing/), [MCP plan enforcement](https://docs.fiscal.ai/docs/guides/mcp-integration)). |
| **Quartr Pro** | Chỉ chạy trên first-party IR material; mỗi citation mở đúng trang nguồn cạnh output ([Automations](https://quartr.com/features/automations), [AI chat](https://quartr.com/features/ai-chat)). | Luôn vào chat; tùy chọn email, activity feed, mobile push; chạy cả khi logout. | AI thực thi prompt đã lưu, so sánh event trước, flag delta/theme/read-through và cho follow-up. User có thể chọn Claude/GPT/Gemini ở chat. | Automations thuộc Quartr Pro; giá “contact sales”, không có giá self-serve công khai ([pricing](https://quartr.com/pricing)). |

## Điều thị trường cho phép suy ra — không phải fact sản phẩm

1. **Khoảng trống rộng đã đóng.** Quartr bao phủ gần toàn bộ mô tả “proactive,
   personalized, evidence-backed watchlist monitoring”: prompt riêng, event và
   cadence, watchlist, delta vs prior event, citation exact-page, chat/email/feed/
   push. Vì vậy “AI theo dõi watchlist và nói điều gì đổi” không đủ khác biệt.
2. **Generic LLM nối data là đối thủ thật, không phải giả thuyết.** Fiscal.ai đã
   đóng gói `watchlist-monitor` source-linked đúng 25 mã, còn Quartr cho chọn
   model. Giá trị không thể chỉ là prompt tốt, summary hoặc tool call tới data.
3. **Nhóm VN hiện thiên về alert tín hiệu, nhóm quốc tế mạnh về IR document.**
   Tài liệu công khai của FireAnt/FiinTrade nhấn realtime price/volume/flow/TA;
   Quartr/Fiscal nhấn first-party filings/transcripts và audit links. Chưa có
   bằng chứng công khai rằng một bên kết hợp tốt cả VN-specific deterministic
   truth lẫn thesis-aware implication cho horizon vài tuần–tháng.
4. **Persistence không đồng nghĩa thesis.** Watchlist, portfolio, note, saved
   alert và saved prompt đều phổ biến. Qua nguồn đã đọc, chưa xác minh sản phẩm
   nào quản lý một object gồm hypothesis, supporting/contradicting evidence,
   falsifier, horizon, version rồi dùng object đó làm materiality policy. Đây là
   *unverified gap*, không phải claim “không đối thủ nào có”.
5. **Không push/email ở V1 là trade-off, không phải wedge tự thân.** Các đối thủ
   bán khả năng giao nhanh qua nhiều kênh. Inbox chỉ đáng thử nếu giảm nhiễu và
   tăng tỷ lệ thay đổi hữu ích đủ để bù việc người dùng phải chủ động mở app.

## Ba whitespace wedge có thể kiểm chứng

### W1 — Thesis object điều khiển relevance, không chỉ saved prompt/note

**Giả thuyết.** Với cùng 5–30 mã và cùng event stream, một thesis có typed
horizon, claim, evidence, falsifier và user objective sẽ tạo top delta phù hợp
hơn alert theo mã/keyword và automation bằng prompt tự do.

**Test tối thiểu.** 10–15 nhà đầu tư viết luận điểm thật cho 3–5 mã; replay 8–12
tuần event EOD. So blind top-3/day giữa (a) ticker/keyword rules, (b) saved
natural-language prompt, (c) typed thesis. Đo precision “material với luận
điểm”, recall event mà user cho là quan trọng, thời gian triage và tỷ lệ mở lại
sau 7 ngày.

**Falsifier.** Saved prompt hoặc note đạt precision/recall không kém đáng kể;
hoặc hơn 40% user không hoàn thành/duy trì thesis sau hai tuần; hoặc reviewer
không đồng thuận đủ để định nghĩa materiality ổn định.

### W2 — VN deterministic materiality trước AI interpretation

**Giả thuyết.** Gate deterministic kết hợp as-of, filing/event, price/volume,
flow và microstructure VN sẽ giảm false positive và tăng trust so với alert
realtime đơn trục hoặc LLM tự chọn “important”. AI chỉ nối delta đã kiểm chứng
với luận điểm và nêu uncertainty/falsifier.

**Test tối thiểu.** Tạo corpus point-in-time của 20 mã qua 3 tháng, có corporate
action, report, tin lặp, limit-lock và flow spike. So (a) incumbent-style rules,
(b) LLM-only ranking trên cùng evidence, (c) deterministic candidate/materiality
gate + AI interpretation. Chấm precision/recall material change, citation/as-of
correctness, duplicate rate, latency và cost trên một delta được chấp nhận.

**Falsifier.** LLM-only đạt cùng hoặc tốt hơn về precision, recall, provenance
và cost; deterministic gate bỏ sót nhiều event hữu ích hơn số nhiễu nó loại;
hoặc FireAnt/FiinTrade trong thử nghiệm sản phẩm thật đã cung cấp bundle tương
đương với nguồn/as-of/implication theo context.

### W3 — Quiet Delta Inbox có budget chú ý và lý do xếp hạng

**Giả thuyết.** Với horizon tuần–tháng, một inbox sau phiên chỉ hiện delta vượt
materiality budget, có “why now / evidence / contradicts-or-supports / watch
next”, sẽ giảm alert fatigue mà vẫn giữ recall tốt hơn stream realtime và digest
theo ticker.

**Test tối thiểu.** Crossover 4 tuần giữa notification stream và post-close
inbox, cùng evidence và user. Đo số item phải đọc, precision, event quan trọng
bị bỏ, thời gian tới lần mở đầu tiên, 7-day recall và hành động “giữ/đổi luận
điểm” (không đo buy/sell).

**Falsifier.** Time-to-awareness làm user bỏ lỡ event họ coi là material; weekly
retention hoặc recall thấp hơn stream; user vẫn cần push cho đa số delta; hoặc
digest/watchlist hiện có đạt cùng hiệu quả mà không cần thesis state.

## Điều không nên dùng làm claim khác biệt

- “Theo dõi tự động”, “cá nhân hóa”, “AI đọc earnings”, “watchlist alerts”,
  “source-linked answer”, “what changed” hoặc “daily/weekly summary” đứng riêng.
- Số kênh notification: V1 chủ động không cạnh tranh ở đây.
- “AI tốt hơn”: Quartr cho chọn model, còn Fiscal MCP có thể chạy trong nhiều AI
  client; model choice dễ bị sao chép.
- Mua/bán, target price, broker sync, realtime hoặc execution: ngoài product
  boundary hiện tại và đã có đối thủ tối ưu cho chúng.

## Đối chiếu contract nội bộ

Ba wedge chỉ đáng tiếp tục nếu giữ được contract hiện tại: figure/source/as-of,
phân biệt observation–hypothesis–judgment, supporting và contradicting evidence,
falsifier, implication theo horizon/risk context; deterministic module sở hữu
calculation, freshness và persistence; AI sở hữu interpretation. Điều này khớp
[Investment Intelligence contract](../../docs/Harness/investment-intelligence-contract.md)
và A2 Monitor, nhưng nghiên cứu thị trường không chứng minh demand hay willingness
to pay.

## Câu hỏi chưa giải quyết

1. Người dùng VN có sẵn sàng viết và duy trì thesis/falsifier, hay hệ thống phải
   suy ra draft rồi xin xác nhận?
2. “Material” do user, deterministic policy hay reviewer domain định nghĩa; mức
   đồng thuận tối thiểu nào đủ làm ground truth?
3. Data entitlement nào cho phép lưu/replay filing, news và flow VN với
   publication/effective time cùng provenance đủ sâu?
4. Quartr Pro thực tế có typed portfolio notes/thesis hoặc automation quota nào
   không xuất hiện trong tài liệu công khai?
5. Mức willingness-to-pay cho inbox thesis-aware là bao nhiêu khi FireAnt Pro là
   299k VNĐ/tháng, Simplize Pro 599k VNĐ/tháng và generic LLM/data tools đã tồn
   tại?
6. Không push/email V1 có làm hỏng time-to-awareness cho event-driven case hay
   chỉ phù hợp post-close changes?
