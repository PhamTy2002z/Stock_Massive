# Research: Portfolio Intelligence — feature landscape, quant engine, AI pattern, monetization

Ngày: 2026-08-23. Bối cảnh: Stock_Massive, EOD-only, universe ~30 mã VN, AI không ra chỉ thị hành động.

## Khuyến nghị (đọc trước, chi tiết ở mục 5-7)

1. **Metric tier 1 (build trước)**: TWR, volatility, max drawdown, HHI concentration, beta vs VNINDEX (rolling, gắn CI rộng), historical VaR/CVaR có cảnh báo sample size. Đây là nhóm có evidence mạnh + tính được đáng tin với N=30, T ngắn.
2. **Không build**: Brinson attribution multi-factor, factor model exposure kiểu Fama-French, MWR/IRR làm số chính (chỉ phụ), correlation matrix "chính xác" cho optimizer không shrinkage.
3. **Optimizer**: **HRP** (Hierarchical Risk Parity) là lựa chọn duy nhất chịu được N=30/T ngắn mà không cần return forecast. Mean-variance thô = "error maximizer" (Michaud 1989) — cấm dùng trực tiếp; nếu dùng, bắt buộc Ledoit-Wolf shrinkage + constraint. Black-Litterman cần input "views" con người mà app không có — loại.
4. **AI layer**: tool-calling vào deterministic engine, **không** cho LLM tự tính số (evidence FinVerBench: multivariate calc accuracy → gần 0%). Đây khớp 100% với pattern đã ghim trong `CLAUDE.md` hiện tại (get_field, `_FIGURE_TOOLS`) — tiếp tục theo, không lệch.
5. **Ngôn ngữ tránh advice**: theo pattern Robinhood Cortex/Public Alpha — "explain what happened", không "should", không target weight/entry/exit. Disclaimer text không đủ theo FINRA/SEC — pattern ngôn ngữ (framing) mới đủ.
6. **Monetization**: gate theo **số lượng portfolio + advanced analytics** (Sharesight/Koyfin pattern) là mô hình có evidence pricing-page rõ nhất; KHÔNG gate theo "AI chat" riêng vì Koyfin Premium ($79/mo) gate "advanced analytics" không phải AI, còn Ziggma gate "Optimizer" ở tier giữa ($10-15/mo).

---

## 1. Feature taxonomy — cái gì đáng có, cái gì vanity với EOD + 30 mã

### 1.1 Performance & attribution

| Metric | Evidence | Đáng có với EOD+30 mã? |
|---|---|---|
| TWR (Time-Weighted Return) | Chuẩn GIPS, dùng bởi mọi performance system tổ chức [[finpension]](https://finpension.ch/en/knowledge/twr-vs-mwr/) | Có — không phụ thuộc số mã, chỉ cần giá đóng cửa phiên |
| MWR/IRR (XIRR) | Đo return "trải nghiệm" của NĐT có nạp/rút tiền [[IBKR whitepaper]](https://www.interactivebrokers.com/images/common/Statements/MWR-TWR_white_paper.pdf) | Có, nhưng **phụ**, không phải số chính — TWR mới so được với benchmark |
| Benchmark-relative (vs VNINDEX) | Tiêu chuẩn ở mọi sản phẩm portfolio tracker | Có — nhưng benchmark phải cùng cấp thanh khoản; VNINDEX cap-weighted lệch nhóm vốn hoá lớn |
| Contribution (per-position % góp vào return tổng) | Toán đơn giản: `w_i × r_i`, không cần model | Có — rẻ, không noisy, không cần Brinson |
| Brinson attribution (allocation/selection/interaction) | Model tổ chức chuẩn cho so benchmark theo sector [[CFA Institute lit review]](https://rpc.cfainstitute.org/sites/default/files/-/media/documents/book/rf-lit-review/2019/rflr-performance-attribution.pdf) | **Vanity ở đây.** Model "less accurate for concentrated strategies", không risk-adjust, số term nổ theo số category (curse of dimensionality) [[Ryan O'Connell CFA]](https://ryanoconnellfinance.com/brinson-attribution-model/); với <15 holding và universe 30 mã ít sector, allocation effect chủ yếu là noise từ 1-2 vị thế lớn |

### 1.2 Risk

| Metric | Evidence | Đáng có? |
|---|---|---|
| Volatility (std dev return) | Chuẩn quantstats/empyrical [[quantstats README]](https://github.com/ranaroussi/quantstats) | Có |
| Max drawdown | Chuẩn, không cần model thống kê, chỉ cần path giá | Có — dễ hiểu nhất với non-quant user |
| Historical VaR/CVaR | Regulatory minimum 250 quan sát (1 năm), 500-1000 cho inference tin cậy [[FRM backtesting notes]](https://analystprep.com/study-notes/frm/part-2/market-risk-measurement-and-management/backtesting-var/); dưới 100 "hit" thì test có "low power" | **Có điều kiện** — phải hiện rõ N và cảnh báo khi lịch sử portfolio <1 năm hoặc mã mới list. Không tự tin trình bày như con số chính xác |
| Beta vs VNINDEX | Rolling regression; "rule of thumb 5 năm" cho ước lượng ổn định, tối thiểu ~24 quan sát cho window 60-tháng ở nghiên cứu học thuật [[ResearchGate — Five-Year Rule]](https://www.researchgate.net/publication/4911094_Forecasting_Beta_How_Well_Does_the_'Five-Year_Rule_of_Thumb'_Do) | Có, nhưng phải gắn confidence interval / min-sample rule tương tự pattern đã có ở `signals/fields.py::min_sample_for` trong repo này |
| HHI concentration (Σw²) + effective N | Metric đơn số, không cần lịch sử giá, chỉ cần weight hiện tại [[QuanterLab]](https://quanterlab.com/articles/diagnostics-concentration-hhi) | **Có — rẻ nhất, đáng tin nhất.** Không phụ thuộc sample size lịch sử |
| Factor exposure (value/momentum/size...) | Cần factor return series đủ dài + universe đủ rộng để tách factor khỏi noise; không tìm được rule số cụ thể tối thiểu bao nhiêu mã cho Fama-French factor construction trong search — đây là **gap chưa xác nhận được**, nhưng factor construction gốc dùng breakpoint trên toàn NYSE (hàng nghìn mã) [[Fama-French methodology]](https://www.hhs.se/globalassets/swedish-house-of-finance/data-center/fama_french_methodology.pdf) | **Vanity/không làm được** — 30 mã không đủ để tách factor return khỏi idiosyncratic noise; nếu làm, chỉ nên factor "tự chế" đơn giản (ví dụ size-tercile trong universe) và ghi rõ giới hạn |

### 1.3 Cái EOD + 30 mã KHÔNG cung cấp đủ

- **Covariance/correlation "sạch"**: nguyên tắc chung — cần T (số quan sát) lớn hơn N (số mã) khoảng **1 order of magnitude**; ví dụ 50 tài sản cần ít nhất 5 năm dữ liệu ngày [[QuantRocket lecture]](https://www.quantrocket.com/codeload/quant-finance-lectures/quant_finance_lectures/Lecture26-Estimating-Covariance-Matrices.ipynb.html). Với N=30, muốn T/N ≈ 10 cần **~300 phiên** tối thiểu (~14 tháng), và đó vẫn chỉ là ngưỡng tối thiểu, chưa "tốt". Nhiều mã VN mới list hoặc thanh khoản mỏng sẽ không đạt.
- **Brinson multi-period, multi-category**: nổ theo tổ hợp, không hợp với concentrated <15 holding thực tế của user.
- **Factor exposure kiểu học thuật**: không đủ breadth.
- **VaR/CVaR intraday hoặc tail risk chính xác**: chỉ có EOD, không có tick — CVaR ở đây là ước lượng thô, không phải risk-management-grade.

---

## 2. Quant engine ở scale nhỏ

### 2.1 Covariance estimation

- **Sample covariance thô**: khi N gần T, ma trận **singular hoặc gần singular** — không nghịch đảo được ổn định. Ngưỡng cứng: q = N/T > 1 → ma trận sample covariance chắc chắn singular [[cov-pred-finance, Stanford]](https://web.stanford.edu/~boyd/papers/pdf/cov_pred_finance.pdf).
- **Ledoit-Wolf shrinkage** (Ledoit & Wolf 2004): co ma trận sample về constant-correlation target, `Σ̂ = δF̂ + (1-δ)S`; well-conditioned, distribution-free, closed-form — chính là default khuyến nghị trong PyPortfolioOpt docs ("Ledoit Wolf shrinkage estimate... sensible default") [[PyPortfolioOpt UserGuide]](https://pyportfolioopt.readthedocs.io/en/latest/UserGuide.html), gốc lý thuyết ở [[SSRN Honey I Shrunk]](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=433840). **Kết luận cho Stock_Massive: bắt buộc dùng shrinkage, không dùng sample covariance thô cho N=30/T ngắn.**

### 2.2 Optimizer — cái nào chịu được noisy input

| Optimizer | Input cần | Điều kiện fail đầu tiên | Nguồn |
|---|---|---|---|
| Mean-variance (Markowitz) | Expected return + covariance | Michaud (1989): "error maximizer" — optimizer khuếch đại chính xác những chỗ estimate sai nhất; unconstrained MV có thể **thua** equal-weight [[SSRN Michaud]](https://papers.ssrn.com/sol3/papers.cfm?abstract_id=2387669) | Fail ngay khi return forecast noisy — mà với EOD 30 mã, return forecast luôn noisy |
| HRP (Hierarchical Risk Parity) | Chỉ covariance, **không cần return estimate** | Không invert covariance (tránh fragility từ ill-conditioned matrix); recursive bisection theo cluster [[Hudson & Thames]](https://hudsonthames.org/portfolio-optimisation-with-portfoliolab-hierarchical-risk-parity/); PyPortfolioOpt docs xác nhận "robustly outperform mean-variance out of sample" [[PyPortfolioOpt UserGuide]](https://pyportfolioopt.readthedocs.io/en/latest/UserGuide.html) | Fail khi cluster structure không ổn định (correlation regime shift mạnh) — nhưng vẫn tốt hơn MV trong noisy regime |
| Risk parity (equal risk contribution, không hierarchical) | Covariance + thường leverage | Phụ thuộc correlation cổ phiếu/tài sản **ổn định** — COVID Q1 2020 cho thấy risk parity underperform mạnh khi correlation regime đổi đột ngột, đặc biệt khi có leverage [[CAIA blog]](https://caia.org/blog/2024/01/02/risk-parity-not-performing-blame-weather) | Với universe 30 mã cổ phiếu cùng thị trường VN (không đa tài sản), risk parity không có đòn bẩy chỉ ~ equal-vol weighting — ít rủi ro hơn version có leverage nhưng cũng ít lợi ích hơn |
| Black-Litterman | Market equilibrium prior + investor "views" + confidence | Không có view → không lệch khỏi market-cap weight (vô dụng); có view → **nhạy input cực mạnh**, tăng belief 1% có thể đổi toàn bộ allocation [[SimTrade]](https://www.simtrade.fr/blog_simtrade/black-litterman-model/) | **Loại khỏi scope** — app không có cơ chế thu "investor views" có confidence score; nếu AI tự sinh view = đưa quan điểm đầu tư trá hình, vi phạm ràng buộc "không ra chỉ thị hành động" |

**Kết luận**: HRP là lựa chọn phù hợp nhất cho engine "nhận định danh mục" (không phải "tối ưu hoá đề xuất tỷ trọng mới" — điều đó lại gần với action instruction, cần cân nhắc compliance riêng). Nếu chỉ dùng để tính risk contribution hiện tại (không đề xuất tỷ trọng mới), risk parity decomposition (không cần optimize) là an toàn nhất về compliance.

### 2.3 Backtest / scenario — pitfall

- **Historical replay vs parametric shock**: MSCI RiskMetrics dùng cả 3 — Monte Carlo, historical, parametric [[MSCI stress testing]](https://www.msci.com/documents/10199/1637462/Stress_Testing_in_the_Investment_Process_Aug2010.pdf/b98c0ccd-b7bc-4ffc-b220-112fcdbe2130). Với universe VN 30 mã lịch sử ngắn, **historical replay** (ví dụ "nếu lặp lại tuần crash tháng X") dễ giải thích hơn cho non-quant user và không cần giả định phân phối; parametric shock (X% giảm đồng loạt) đơn giản hơn để tính nhưng bỏ qua correlation thực tế lúc stress.
- **Survivorship bias**: backtest chỉ trên universe hiện tại bỏ qua mã đã delist/huỷ niêm yết — overstate return ~0.9%/năm theo nghiên cứu mutual fund (Elton/Gruber/Blake) [[Taxonomy of Backtest Lies]](https://www.susanpotter.net/quant/backtest-bias-taxonomy/). Với universe 30 mã "đã chọn sẵn" của Stock_Massive, nguy cơ survivorship cao nếu universe được cập nhật loại mã yếu ra.
- **Lookahead bias**: phải dùng dữ liệu point-in-time — trùng đúng nguyên tắc đã ghim trong CLAUDE.md hiện tại ("`trading_day` không bao giờ là argument", giá đóng phiên gần nhất đã đóng).
- **Transaction cost VN**: 25bps/trade là giả định "an toàn" cho một lệnh ở VN, cao so với thị trường phát triển [[risk-return VN paper]](https://www.science-gate.com/IJAAS/Articles/2025/2025-12-09/1021833ijaas202509022.pdf) — cộng với price-band lock (±7% HOSE, ±10% HNX) khiến backtest rebalancing giả định "khớp giá đóng cửa" là **sai lệch lạc quan** khi mã đang bị limit-lock (không có counterparty).

### 2.4 Rebalancing

- Vanguard: **threshold-based rebalancing (band, ví dụ ±20%/±5%) vượt trội calendar-based** 11-18 bps/năm nhờ giảm transaction cost; annual rebalancing thường là "optimal" so với monthly/quarterly cho hầu hết NĐT [[Vanguard research]](https://corporate.vanguard.com/content/corporatesite/us/en/corp/articles/tuning-frequency-for-rebalancing.html/1000).
- **T+2 impact**: rebalancing đề xuất phải aware là lệnh bán hôm nay chỉ nhận tiền T+2 — nếu app đề xuất "bán A mua B cùng ngày" mà không có margin, thực tế không thực hiện được ngay. Không tìm được paper định lượng riêng cho VN T+2 × rebalancing; đây là suy luận từ market structure, không phải citation trực tiếp — **gap, cần domain expert VN xác nhận** thay vì đưa vào engine như luật cứng.
- **Price band lock**: nếu mã trong danh mục đang limit-lock, "threshold rebalance" tính toán trên giá đóng cửa lý thuyết nhưng không thể thực thi — engine nên đánh dấu tình trạng này là "không thể rebalance", không nên âm thầm tính coi như đã khớp.

---

## 3. AI + portfolio — pattern đã chứng minh và cạm bẫy

### 3.1 Tool-calling vs feed số vào prompt

- Evidence trực tiếp về accuracy giữa prompt-mode và function-calling-mode cho financial task: **tương đương ở mức benchmark tổng** (~70-71%) khi model tự làm cả reasoning+calc [[FinTrace/related surveys]](https://arxiv.org/html/2605.00737v1) — nhưng khi **tách reasoning khỏi calculation** (LLM chỉ định cái cần tính, hệ thống deterministic tính) thì accuracy cải thiện có ý nghĩa trên complex financial reasoning.
- Bằng chứng cụ thể về LLM tự tính sai: **FinVerBench** — model rơi từ 95.6% accuracy ở lookup đơn giản xuống **gần 0%** ở multivariate calculation; perturb statement khiến accuracy rơi về random chance → gợi ý model đang pattern-match/memorize, không thực sự tính [[FinVerBench]](https://arxiv.org/pdf/2605.29586) (search snippet dẫn qua truy vấn "large language models arithmetic errors financial data").
- **Kết luận có evidence rõ**: KHÔNG để LLM tự cộng/trừ tỷ trọng, return, hay bất kỳ số nào — bắt buộc tool-calling vào engine deterministic để trả số, LLM chỉ diễn giải. Đây **đã đúng với pattern hiện tại trong CLAUDE.md** (get_field, `_FIGURE_TOOLS`, "Chạy và trả về số là hai việc") — nghiên cứu này xác nhận hướng đã chọn, không đề xuất đổi.

### 3.2 Ngôn ngữ tránh trở thành investment advice

- **Không đủ chỉ dán disclaimer**: cả stakeholder pháp lý (Sidley, Smarsh) đều nói disclaimer "boilerplate" không chắn được liability nếu overall messaging overstate capability; omit limitation = "half-truth" có thể coi là deceptive [[Sidley]](https://www.sidley.com/en/insights/newsupdates/2025/02/artificial-intelligence-us-financial-regulator-guidelines-for-responsible-use), [[Smarsh]](https://www.smarsh.com/blog/thought-leadership/ai-governance-expectations-are-rising-even-without-rules). FINRA investor alert: "AI-generated content may appear authoritative but may lack rigor of professionally vetted financial analysis" (paraphrase từ search, chưa lấy được văn bản gốc investor alert để quote chính xác — **cần verify trực tiếp finra.org trước khi trích dẫn chính thức**).
- **Pattern ngôn ngữ sản phẩm sống**:
  - Robinhood Cortex: "not a research report, a recommendation, or investment advice... generated from sources deemed reliable, but accuracy is not guaranteed"; Cortex Assistant: "not an investment advisor... information and responses generated solely for informational and educational purposes... not a recommendation to buy, sell, or hold" [[Cortex Digests support]](https://www.robinhood.com/us/en/support/articles/cortex-digests) — pattern: mô tả nguồn dữ liệu + giới hạn accuracy + phủ định trực tiếp "recommendation" bằng động từ hành động cụ thể (buy/sell/hold), không chỉ nói chung "not advice".
  - Public.com Alpha: "does not provide financial advice. Instead, Alpha offers... insights... to help you reach your own conclusions"; "absent context and does not account for your personal circumstances" [[help.public.com]](https://help.public.com/en/articles/9354354-what-is-alpha) — pattern: định vị lại vai trò AI là "nghiên cứu nền", nói rõ **thiếu personalization** như một giới hạn kỹ thuật, không chỉ pháp lý.
  - Cả hai đều tránh động từ mệnh lệnh ("nên", "hãy") và tránh gắn số cụ thể (entry/exit/target weight) với khuyến nghị hành động — khớp với luật đã ghim trong CLAUDE.md hiện tại ("không ra chỉ thị hành động... không tỷ trọng mục tiêu, không mức vào/ra").
  - Chưa lấy được ngôn ngữ cụ thể của Bloomberg/Koyfin AI-feature (Koyfin cho phép "pick your favorite AI" nhưng không tìm thấy disclosure text riêng) — **gap, không suy đoán.**

### 3.3 Privacy — portfolio là PII tài chính

- Best practice chung (không tìm được case study định lượng riêng cho brokerage/portfolio app, chỉ có nguyên tắc): **data minimization** — không gửi hơn mức cần cho model call; redact/anonymize trước khi gửi nếu field không cần thiết cho task [[rohan-paul.com]](https://www.rohan-paul.com/p/data-security-and-privacy-precautions).
- Ngành ngân hàng có xu hướng ban/hạn chế LLM bên thứ 3 (Goldman Sachs, Deutsche Bank từng chặn ChatGPT) — tín hiệu rằng gửi dữ liệu portfolio thật ra LLM provider ngoài (OpenAI/Anthropic API) là quyết định rủi ro cần compliance sign-off, không phải quyết định kỹ thuật đơn thuần.
- Đối chiếu với repo: `CLAUDE.md` đã có contract "closed prompt" — agent memory chỉ qua tool-call, không auto-inject free text — đây là pattern nhất quán với "data minimization"; giữ nguyên hướng, không mở rộng free-text injection cho portfolio data.
- **Không tìm được** primary-source case study cụ thể nào ("công ty X đã làm gì với PII tài chính khi gọi LLM API") — chỉ có nguyên tắc chung. Nêu rõ đây là khuyến nghị dựa trên best-practice, không phải case đã kiểm chứng.

---

## 4. Monetization — ai bán gì, giá nào, gate gì

| Sản phẩm | Free | Tier trả phí thấp nhất | Feature gate chính | Nguồn |
|---|---|---|---|---|
| Sharesight | 1 portfolio, 10 holdings, không tax report, không "Diversity/Exposure reports" | Starter $7/mo: 30 holdings, thêm Diversity+Exposure reports | Số holding + loại report (tax, multi-currency, contribution analysis ở tier cao hơn); Premium mới có "Multi-Period reporting" | [[sharesight.com/pricing]](https://www.sharesight.com/pricing/) |
| Snowball Analytics | 1 portfolio, 10 holdings, "Limited Benchmarking" (chỉ index), "Limited Rebalance Tool" | Starter free/$79.99-năm: unlimited holdings, "Advanced Rebalance Tool", link brokerage | **Rebalance tool** và **full benchmarking (any asset)** là paywall rõ; portfolio count cũng gate | [[snowball-analytics.com/pricing]](https://snowball-analytics.com/pricing) |
| Ziggma | Portfolio Tracker, Portfolio Insights, Dividend Tracker (miễn phí) | Starter $6.99/mo: "Portfolio Checkup", Stock Scores | **"Portfolio Optimizer"** chỉ có ở tier Investor ($10.49/mo) — xác nhận optimizer là premium feature thật, không miễn phí ở đâu trong nhóm này | [[ziggma.com/pricing]](https://ziggma.com/pricing/) |
| Simply Wall St | 5 company reports/tháng, phân tích 5 mã/tháng | Premium $10/mo: 30 mã/tháng, "personalized portfolio recommendations", stock screener | Số lượng mã phân tích/tháng là cơ chế gate chính (usage-based, không phải feature-based) | [[search kết hợp bmmagazine/simplywall.st]](https://simplywall.st/plans) |
| Koyfin | "My Portfolios" cơ bản có ở Free | Premium $79/mo: **"My Portfolio advanced analytics"** | Advanced portfolio analytics là **riêng một bậc cao** ($79/mo, trên cả Plus $39/mo) — không phải feature rẻ; không có AI feature riêng biệt xuất hiện trên trang giá | [[koyfin.com/pricing]](https://www.koyfin.com/pricing/) |
| VN market (Vietstock/FiinTrade/TCBS/DNSE) | — | — | Nhiều công ty chứng khoán VN đã ra AI chatbot riêng (TCBS "Mập Thông Thái", DNSE "Ensa", MBS "Dolphin AI", VDSC "hiDragon") nhưng **không tìm được trang giá/feature-gate cụ thể** cho các AI này trong search — hầu hết đi kèm miễn phí trong app brokerage để giữ khách, không phải SaaS riêng | [[Vietstock bài báo]](https://vietstock.vn/2025/09/cuoc-dua-cong-nghe-cua-cac-cong-ty-chung-khoan-737-1347079.htm) — **thứ cấp, chưa verify primary pricing page** |

### Rút ra

- **Feature luôn miễn phí ở mọi nơi tìm được**: portfolio tracker cơ bản, watchlist, dividend tracking cơ bản, 1 portfolio/số holding nhỏ.
- **Feature paywall thật** (xuất hiện lặp lại ở ≥3 sản phẩm độc lập → đủ evidence chéo): (1) **số lượng portfolio/holdings** (Sharesight, Snowball, Simply Wall St), (2) **optimizer/rebalance tool nâng cao** (Ziggma "Portfolio Optimizer", Snowball "Advanced Rebalance Tool"), (3) **"advanced analytics"** như một cụm riêng đắt hơn cả AI feature (Koyfin $79 tier).
- **AI riêng không phải paywall độc lập** trong dữ liệu tìm được — nó thường bọc trong tier "advanced" đã có sẵn lý do khác để trả tiền (Koyfin không quảng cáo AI như một dòng giá riêng biệt). VN brokerage cho AI chatbot free-in-app để giữ khách, không bán riêng — nhưng đây là claim thứ cấp, độ tin cậy thấp hơn nhóm US/EU đã verify trực tiếp trang giá.

---

## 5. Trade-off matrix tổng hợp (quant engine)

| | Cần return forecast? | Chịu noisy input? | Compliance risk (VN, "không action instruction") | Effort implement |
|---|---|---|---|---|
| Mean-variance thô | Có | Kém (error maximizer) | Trung — dễ vô tình sinh ra "tỷ trọng đề xuất" | Thấp |
| MV + Ledoit-Wolf shrinkage | Có | Trung | Trung | Trung |
| HRP | Không | Tốt | Thấp nếu chỉ show risk decomposition, Trung nếu show "target weight" | Trung (cần linkage/clustering) |
| Risk parity (không lever) | Không (chỉ cov) | Trung-tốt | Thấp nếu dùng để show risk contribution, không đề xuất | Thấp-trung |
| Black-Litterman | Có (+ views) | Kém nếu view sai, nhạy input | **Cao** — view do đâu ra nếu không phải AI "khuyến nghị"? | Cao, không nên làm |

## 6. Adoption risk / maturity của các thư viện tham chiếu

- **PyPortfolioOpt**: doc chính thức còn duy trì, khuyến nghị rõ Ledoit-Wolf + HRP; nhưng đây là thư viện community, không phải chuẩn công nghiệp bắt buộc — dùng làm tham chiếu thiết kế, không nhất thiết import trực tiếp vào production Python stack FastAPI hiện tại mà không audit.
- **quantstats/empyrical/pyfolio**: chuẩn de-facto cho performance/risk reporting Python, nhưng README-level docs không nói rõ minimum-sample-size cho từng metric — team tự phải áp rule (như `min_sample_for` đã có sẵn trong repo cho signal field) cho VaR/beta.
- **HRP, Ledoit-Wolf**: nền lý thuyết academic 2001-2016, đã production-tested rộng (Lopez de Prado là industry practitioner, không chỉ academic) — rủi ro abandon thấp, đây là toán học ổn định không phải library có thể "breaking change".
- **Black-Litterman**: chuẩn academic 1990s, ổn định về lý thuyết nhưng loại khỏi scope vì lý do compliance/input-availability, không vì maturity.

## 7. Kiến trúc fit cho Stock_Massive

- Engine metric (TWR, vol, drawdown, HHI, beta, VaR/CVaR có cảnh báo N) nên nằm như **deterministic service** riêng (kiểu `src/stocks/<domain>/service.py` pattern đã có), expose qua tool trong `registry`/`toolsets` giống cách `signals` bundle đang làm — không có lý do lệch pattern đã có trong CLAUDE.md.
- AI hỏi đáp trên danh mục nên tái dùng đúng contract "closed prompt" + `reads_external=False` cho tool đọc portfolio nội bộ (Postgres), theo đúng luật `untrusted.py` đã ghi.
- Ngôn ngữ output nên đưa vào `PROMPT_VERSION` mới (không sửa ngầm 2.3.0) theo đúng pattern Robinhood/Public: mô tả hiện trạng + giới hạn kỹ thuật, cấm động từ hành động cụ thể — mở rộng đúng luật đã có, không đối chọi.
- Optimizer/HRP nếu làm, nên định vị là "risk decomposition hiện tại" (đọc), không phải "đề xuất tỷ trọng mới" (viết/action) — biên compliance ở output framing, không ở toán.

## Hạn chế nghiên cứu (không suy đoán thêm)

- **VN market microstructure × rebalancing/backtest**: không tìm được paper/case định lượng riêng cho T+2 + price-band interaction với rebalancing hoặc backtest transaction cost — phần này trong báo cáo là suy luận từ market rule, cần domain expert VN hoặc dữ liệu thực nghiệm xác nhận trước khi đưa vào engine như hard rule.
- **Factor exposure minimum universe size**: không tìm được số cụ thể tối thiểu bao nhiêu mã cho factor model — chỉ có bằng chứng gián tiếp (Fama-French dùng breakpoint toàn NYSE hàng nghìn mã) để suy ra 30 mã không đủ; chưa có ngưỡng chính xác.
- **Koyfin/Bloomberg AI disclosure text cụ thể**: không lấy được văn bản disclosure chính xác cho AI feature của hai sản phẩm này — chỉ có Robinhood + Public.com đã verify trực tiếp.
- **VN brokerage AI (TCBS/DNSE/MBS) pricing/gate**: chỉ có nguồn thứ cấp (bài báo Vietstock), chưa verify trực tiếp trang sản phẩm — không nên trích dẫn như fact cứng.
- **FINRA investor alert text**: câu quote về AI content "appear authoritative" lấy từ search snippet, chưa fetch trực tiếp finra.org để xác nhận nguyên văn — cần verify trước khi dùng trong tài liệu chính thức/pháp lý.
- Không đánh giá chi phí LLM cụ thể cho feature portfolio AI này (ngoài scope 4 phần được giao) — nếu build, cần chiếu vào envelope $45/tháng đã có trong CLAUDE.md.

## Câu hỏi mở

1. App có cần tự tính "target weight đề xuất" (gần action instruction) hay chỉ risk decomposition hiện tại (an toàn compliance hơn)? Quyết định này đổi hẳn optimizer nào hợp lệ.
2. Portfolio data (holdings, cost basis) có buộc phải qua LLM provider ngoài, hay có thể giữ toàn bộ số học ở tool-call kết quả (LLM chỉ thấy số đã tính, không thấy transaction-level detail)? Ảnh hưởng trực tiếp privacy posture.
3. VaR/CVaR hiển thị cho user retail non-quant — có cần UI cảnh báo "N phiên chưa đủ" như một first-class trạng thái (giống pattern `no_value:<signal issue>` đã có), hay chỉ ẩn metric khi dưới ngưỡng?
