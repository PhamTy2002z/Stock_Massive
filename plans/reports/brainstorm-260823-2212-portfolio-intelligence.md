# Brainstorm — Portfolio Intelligence

Ngày: 2026-08-23 · Nhánh: `develop` · Trạng thái: **draft, chờ quyết định của product owner**

Phạm vi được yêu cầu: (1) quản lý danh mục đầu tư — chart/table; (2) AI phân tích
danh mục, hỏi đáp trực tiếp trong danh mục, "có khả năng quản lí danh mục"; (3)
quant engine thu thập dữ liệu, đánh giá, đưa ra nhận định/đề xuất cho danh mục.
Đây là feature core và nguồn ARR chính.

Tài liệu này là **brainstorm contract + evidence**, không phải plan. Nó dừng ở
hướng được chọn và các quyết định user phải ra trước khi có plan.

---

## 1. Hiện trạng đo được, không suy đoán

Mọi số dưới đây đo trực tiếp trên repo tại `develop` và trên database dev đang
chạy (`stockmassive`, alembic `b7f4e9c21a08`). Nơi nào tôi không kiểm được, tôi
nói rõ.

### 1.1 Nền tảng đã có và dùng được ngay

| Thành phần | Trạng thái | Owner |
|---|---|---|
| Lịch sử EOD durable, đã xử lý quyền | Có | `stock_daily_ohlcv`, `corporate_actions` (`stocks/models.py:197`), read-time adjustment theo `docs/adr/0006` |
| `price_basis` raw/adjusted, cờ `mixed` khi một bar vắt qua seam | Có | `stocks/series_view.py:26,56` |
| 30 Signal Field cấp **mã**, có contract thống kê cưỡng chế ở compile-time | Có | `stocks/signals/registry.py`, `fields.py` |
| Evidence envelope: health 3 trạng thái + reason code, section health tính chứ không nhận, fingerprint | Có | `alpha/envelope.py` |
| Analysis lane là vòng lặp 6 round trên `(symbol, trading_day)`, mọi tool call ghi trace | Có | `alpha/analysis_loop.py`, bảng `analysis_tool_call` |
| Chat lane: 8 tool / 3 bundle, 4 round, `MAX_EXTERNAL_TOOL_CALLS=6` | Có | `agent/toolsets.py:79` |
| Watchlist per-user, tối đa 10 mã, chỉ trong Universe | Có | `alpha/watchlist.py:39` |
| Chuỗi phiên của index đã lưu durable, chung gateway bar với mã | Có | `signals/registry.py:779` (ghi trong interpretation của `relative_strength`) |
| Web: shell 3 vùng, 4 view, SSE streaming có tool call + reasoning rail, react-query | Có | `components/shell/shell-state.tsx:29` |

Điều này quan trọng: **`docs/research/data-coverage-audit.md` đã lạc hậu** ở
điểm nặng nhất. Audit đó chốt tại `426c23b` (10/08) và kết luận "no adjusted
close / corporate-action adjustment anywhere". Nay đã có bảng `corporate_actions`
với cột `confirmation` làm cổng — chỉ action đã confirmed mới được phép chi phối
số học, action chưa confirmed để cửa sổ ở trạng thái degraded thay vì adjusted.
Đó chính là tiền đề bắt buộc để tính lợi nhuận danh mục cho đúng, và nó đã có.

### 1.2 Portfolio: chưa có gì

Không có bảng, model hay endpoint nào cho portfolio, holding, position,
transaction hay cost basis. `watchlist_entries` là danh sách mã được theo dõi —
không mang số lượng, giá vào, ngày mua, hay quyền sở hữu. Chữ "position" trong
code hiện tại thuộc ngữ cảnh khác (con trỏ stream, transaction của database).

Phải xây từ đầu: ledger giao dịch, holdings phái sinh từ ledger, cost basis,
số học cấp danh mục, và một lane cho AI đọc nó.

### 1.3 Độ sâu lịch sử — **mục này đã bị hiệu chỉnh, đọc 1.3b trước**

> **Hiệu chỉnh 2026-08-24.** Kết luận gốc của §1.3 và §1.4 là **sai**: nó đo
> `stock_daily_ohlcv`, nhưng Signal field không đọc bảng đó. `signals/sessions.py:41,108`
> đọc `ProviderSnapshot`, và bảng đó có **2.527 phiên/mã**, với **28 trong 30 mã
> Universe đạt ≥970 phiên**. Nhóm risk/performance **không bị chặn**. Chi tiết và
> số đo ở `docs/research/vnstock-sponsor-tiers.md` §4.1. Phần dưới giữ lại vì
> phép tính về sàn mẫu vẫn đúng và vì bản ghi một kết luận sai có ích hơn một
> đoạn bị xoá.

Đây là phát hiện quyết định thứ tự thực hiện của toàn bộ feature.

Sàn lịch sử mà chính các field đã khai:

| Hằng số | Giá trị | Field phụ thuộc |
|---|---|---|
| `RISK_ADJUSTED_SESSIONS` (`signals/risk.py:154`) | **250** | Sharpe, Sortino |
| `DRAWDOWN_SESSIONS` (`signals/risk.py:151`) | **250** | max/current drawdown, days underwater, drawdown vs benchmark |
| `RELATIVE_STRENGTH_MIN_SESSIONS` (`signals/cross_sectional.py:153`) | **250** | beta và correlation vs index |
| `MOMENTUM_FORMATION_SESSIONS + SKIP` (`cross_sectional.py:127`) | **252** | momentum rank 12-2 |
| `REALIZED_VOLATILITY_SESSIONS` (`risk.py:142`) | 60 | realized vol, vol regime |

Store dev thực tế có:

```
stock_daily_ohlcv : 119.525 dòng · 1.710 mã · 2022-02-23 → 2026-08-07
độ sâu/mã         : max 80 phiên · trung bình 70 · KHÔNG mã nào ≥ 250
liên tục          : không — FPT nhảy từ 2025-12-23 sang 2026-07-31
`backfill_enabled`: False  (src/core/config.py:121)
```

Hệ quả: ở store hiện tại, **toàn bộ nhóm risk/performance refuse
`insufficient_history`** — Sharpe, Sortino, cả bốn field drawdown, beta,
correlation, momentum 12-2. Đó là 9 trong 30 field không trả số. Chín field đó
lại đúng là những field mà một danh mục cần nhất.

Cần xác nhận: đây là DB **dev** và nó đang chạy schema cũ hơn repo (DB ở
`b7f4e9c21a08`, repo có 25 migration với head `a4c71d9e5b28`). Production có thể
sâu hơn. Nhưng `backfill_enabled: bool = False` là default trong code, nên
khả năng cao production cũng thiếu.

### 1.4 Con số làm thay đổi cách bán feature này

Từ Lo (2002) — đã được `docs/research/quant-methods-eod-vn.md` xác minh full
text và đã cưỡng chế trong `FieldKind.ESTIMATOR`: `SE(SR) ≈ √((1+SR²/2)/T)`.

Để một Sharpe **thật sự bằng 1,0** có khoảng tin cậy 95% **không chứa 0**, cần
khoảng **970 phiên — gần 4 năm**. Ở 250 phiên, CI của Sharpe 1,0 vẫn trải từ
âm sang dương. Ở 75 phiên như store hiện tại, CI rộng đến mức vô nghĩa.

Điều đó không có nghĩa là bỏ Sharpe. Nó có nghĩa là **"Sharpe danh mục của bạn
là 1,2" không phải một feature bán được** — con số đi kèm CI của nó là một câu
trung thực, và câu trung thực đó thường là "không phân biệt được với 0".

Tương tự với ma trận tương quan: 30 mã trên ~250 phiên nằm đúng trong vùng
ill-conditioned mà Ledoit-Wolf mô tả; cường độ shrinkage `δ̂` tiến gần 1 chính
là thông điệp "dữ liệu không đỡ được ma trận này". Mọi optimizer mean-variance
đặt trên input đó sẽ bám vào cực trị của nhiễu.

### 1.4b Số đo đúng, và nó đổi thứ tự thực hiện

Đo trên `provider_snapshots`, capability `market`, ngày 2026-08-24:

```
FPT · HPG · VCB · VNM : 2.521 phiên, 2016-07-20 → 2026-08-20
trung bình toàn bộ     : 2.109 phiên/mã   (min 7 · max 2.521)
FPT chi tiết           : last_price 2.527/2.527 · volume 2.527/2.527
```

Trên đúng 30 mã Universe: **28 mã ≥970 phiên** — ngưỡng để CI của Sharpe không
chứa 0 theo phép tính ở §1.4. Hai mã còn lại là TCX và VPL (mới, 1–59 phiên), và
chúng sẽ `refused` — đó là hành vi đúng của contract, không phải trạng thái chung
của hệ thống.

Nhất quán với thiết kế đã ghi: `backfill_main_source_days = 5 * 365` với comment
*"đo thực tế: FiinQuant free trả ~5 năm nến ngày"*, `backfill_depth_days = 10 *
365`, và `backfill.py:1-6` nói vnstock là **Cover Source** chỉ dùng cho phần sâu
hơn 5 năm.

**Hệ quả:** Phase 0 trong §4 — "backfill lịch sử ≥250 phiên" — **đã xong**. Nhóm
risk/performance của portfolio có số thật ngay khi PortfolioField được viết. Cái
còn thiếu không phải lịch sử giá mà là:

- `market_cap_vnd` chỉ **5/2.527 phiên** → nguồn của `stale_market_cap` và cửa sổ
  21 phiên của bốn factor percentile;
- `foreign_net_value_vnd` chỉ **1.258/2.527 phiên**;
- `foreign_buy_volume` / `foreign_sell_volume` **0/2.527** — key có trong payload,
  không adapter nào ghi, và đó là lý do `FOREIGN_FLOW_SHARE_PRESSURE` chết.

Ba dòng đó thuộc trục money flow, không thuộc portfolio analytics.

### 1.5 Universe là ràng buộc policy, không phải ràng buộc dữ liệu

`UNIVERSE_SYMBOLS` hiện đúng 30 mã VN30. Cổng Universe nằm ở **tool layer**
(`agent/tools/signals.py:448`), không nằm trong engine — `bars.py:1081` cho phép
truyền `peers` thay cho Universe. Store lại có OHLCV của 1.710 mã.

Nghĩa là: mã ngoài VN30 hiện bị từ chối bởi một quyết định ở tầng tool, không
phải vì không có dữ liệu. Đây là điểm mở được, và nó quan trọng với ARR: một
người dùng trả tiền mà nửa danh mục của họ trả về "ngoài phạm vi" thì sẽ không
trả tiếp. Cần phân biệt rõ nhóm field chỉ cần bar của chính mã (vol, drawdown,
ADTV, band, mean reversion — mở được) với nhóm percentile cross-section (cần một
Universe có định nghĩa point-in-time — không mở được bằng cách nới danh sách).

### 1.6 Ba lớp phòng vệ độc lập đều cấm "đề xuất hành động"

Yêu cầu số 2 và 3 của bạn — "AI có khả năng quản lí danh mục", "đưa ra đề xuất
cho danh mục" — gặp ba cơ chế độc lập, mỗi cái đủ để chặn:

1. **Prompt contract** (`agent/prompt/sections.py:92-97`): được nói ra mức và hệ
   quả; **không** ra chỉ thị cho một vị thế cụ thể — không "bán đi", không "chốt
   một phần", không tỷ trọng mục tiêu, không mức vào/ra. Và câu ngay sau đó:
   *"Số liệu thật làm một lời khuyên nghe đáng tin hơn mà không trở nên đáng tin
   hơn. Đó chính là lý do ranh giới này chặt hơn khi bạn đọc được store."*
2. **Autonomy contract** (SOT `investment-intelligence-contract.md`): A3 —
   Propose — là **Conditional**, chỉ mở sau quyết định product/legal về
   research-versus-advice và UX phê duyệt của con người. A4 — Execute — là
   **Rejected**.
3. **Field claim schema** (`signals/fields.py`): trong v1 **mọi** field là
   `descriptive`, và `descriptive` là ràng buộc schema — không được trả key
   mang hướng: không `direction`, không `signal: buy|sell`, không
   `expected_return`. `predictive` chỉ mở sau một harness đo forward-return
   net-of-cost.

Ba cơ chế này không phải rào cản hành chính; chúng là cùng một kết luận được
viết ở ba tầng. Muốn có "đề xuất", phải đổi cả ba — và đó là quyết định
product/legal của bạn, không phải quyết định kỹ thuật của tôi.

### 1.7 Hai ràng buộc vận hành

- **Ngân sách LLM**: envelope $45/tháng hard-coded (`core/llm/budget.py:61`),
  chia ba lane, và Budget Validation **chặn startup** nếu các lane không cộng
  đúng bằng envelope. Thêm một lane portfolio nghĩa là hoặc nâng envelope, hoặc
  lấy phần từ lane hiện có. Không có đường thứ ba.
- **Web chưa có chart library**: `components/charts/` trống, không Recharts,
  không visx; chart duy nhất là một `Sparkline` SVG viết tay trong
  `inspector.tsx:699`, viewBox 320×100. Equity curve, allocation, drawdown đều
  cần thứ mới → **cần hỏi trước khi thêm dependency**.

### 1.8 Vị trí trong roadmap SOT

SOT đặt "Portfolio intelligence" là một **lane có tên** trong target
architecture (không bị reject) và đặt nội dung của nó ở **Stage 3**, sau Stage 0
(measurement authority) → Stage 1 (unified contracts) → Stage 2 (deep financial
intelligence).

Trạng thái thực tế: Stage 0 đang `in-progress`
(`plans/260823-1744-investment-intelligence-eval-replay-harness`), Stage 1 đã có
plan ở trạng thái `pending` (`plans/260823-2104-resolved-capability-contract-v1`,
blockedBy Stage 0). Stage 2 chưa có plan.

Và SOT tự đặt đúng câu hỏi này trong phần "Câu hỏi chưa giải quyết" của roadmap:
*"Portfolio intelligence hay proactive thesis monitoring tạo giá trị cao hơn cho
nhóm người dùng đầu tiên?"* — nó chưa được trả lời. Yêu cầu của bạn hôm nay
chính là câu trả lời, nhưng nó cần được ghi vào SOT như một quyết định, không
lặng lẽ nhảy hàng.

---

## 2. Điều research bên ngoài xác nhận và điều nó bác

Chi tiết + URL ở `plans/reports/research-260823-2212-portfolio-intelligence-landscape.md`.
Bốn kết luận đổi thiết kế:

**Nhóm metric rẻ nhất lại là nhóm đáng tin nhất.** Trọng số, contribution
(`w_i × r_i`), HHI + effective N, cost basis, P/L, TWR — không cái nào phụ thuộc
sample size lịch sử. Chúng đúng với đúng một phiên dữ liệu. Đây là chỗ giá trị
chắc chắn của feature, và cũng là chỗ người dùng phát hiện sai ngay nếu tính sai.

**Brinson attribution và factor exposure kiểu Fama-French là vanity ở scale này.**
Brinson "less accurate for concentrated strategies" và số term nổ theo số
category; với dưới 15 vị thế, allocation effect chủ yếu là nhiễu từ một hai vị
thế lớn. Factor construction gốc đặt breakpoint trên toàn NYSE — hàng nghìn mã;
30 mã không tách được factor return khỏi nhiễu idiosyncratic. Không làm.

**Optimizer: chỉ HRP hoặc risk-parity decomposition, và chỉ để đọc.**
Mean-variance thô là "error maximizer" (Michaud 1989) — nó khuếch đại chính
những chỗ ước lượng sai nhất, và unconstrained MV có thể thua equal-weight.
Black-Litterman phải **loại**, không vì độ chín mà vì input: nó cần "investor
views" có confidence, và nếu AI tự sinh view thì đó là khuyến nghị đầu tư trá
hình — vi phạm cùng lúc cả ba lớp ở §1.6. HRP không cần return forecast và không
nghịch đảo covariance, nên nó là thứ duy nhất chịu được input nhiễu ở đây.

**LLM tự tính số là failure mode đã đo được.** FinVerBench: accuracy rơi từ
95,6% ở tra cứu đơn giản xuống **gần 0%** ở phép tính đa biến. Kết luận này xác
nhận đúng pattern repo đang có (`get_field`, `_FIGURE_TOOLS`, "chạy và trả về số
là hai việc") — không cần đổi hướng, cần mở rộng nó sang portfolio.

**Về cách bán:** paywall có evidence chéo ở ≥3 sản phẩm độc lập là (1) số lượng
portfolio/holdings, (2) optimizer/rebalance nâng cao, (3) "advanced analytics"
như một bậc riêng — Koyfin đặt nó ở $79/tháng, trên cả bậc $39. Đáng chú ý: **AI
không xuất hiện như một dòng giá riêng** ở bất kỳ sản phẩm nào đã kiểm được trang
giá. Nó được bọc trong bậc đã có lý do khác để trả tiền. Nếu ARR đặt cược vào
"AI chat trong danh mục" như dòng giá độc lập, đó là cược không có tiền lệ trong
dữ liệu tìm được.

---

## 3. Brainstorm contract

### Outcome

Một người dùng nhập danh mục thật của họ, thấy nó được mô tả đúng — trọng số,
giá vốn, lãi/lỗ, tập trung, thanh khoản để thoát — và hỏi được AI về chính danh
mục đó, nhận lại câu trả lời có as-of, có nguồn, có mức không chắc chắn, và có
nói ra chỗ dữ liệu không đỡ được kết luận. Quant engine trả các chỉ số rủi ro
cấp danh mục kèm điều kiện hiệu lực của chúng, và **từ chối rõ ràng** khi mẫu
không đủ thay vì in ra một con số trông như thật.

### Constraints

1. **Số học cấp danh mục là deterministic, model không được tự tính.** Mọi
   figure đi qua tool trả structured result có unit, sign, kind, health,
   reason code — cùng khuôn `SignalField`, không phải khuôn thứ hai.
2. **Không chỉ thị hành động cho vị thế cụ thể** cho đến khi có quyết định
   product/legal đảo ba lớp ở §1.6. Nghĩa là: không tỷ trọng mục tiêu, không mức
   vào/ra, không "bán đi", không rebalance proposal.
3. **Sàn mẫu là hàm của mẫu, không phải hằng số** — theo đúng
   `signals/fields.py::min_sample_for` đã có. Chỉ số nào không đạt sàn thì
   `refused` với reason code, không im lặng dùng cửa sổ ngắn hơn.
4. **Point-in-time.** `trading_day` không bao giờ là argument của tool; holdings
   được version, và một câu trả lời về hôm qua không được dùng holdings hôm nay.
5. **Corporate action đã confirmed mới được chi phối số học** — cổng
   `CorporateAction.confirmation` đã có, portfolio return phải đi qua nó.
6. **Ngân sách $45/tháng và Budget Validation chặn startup.** Lane portfolio
   phải lấy phần từ envelope hiện có hoặc envelope phải đổi — có chủ đích.
7. **Portfolio là PII tài chính.** Model thấy figure đã tính, không thấy
   transaction-level detail, trừ khi có quyết định ngược lại.
8. **Không đổi public contract của lane chat/Analysis** trong các phase đầu.

### Non-goals

- Broker execution, auto-rebalance, order ticket (A4 — Rejected trong SOT).
- Mean-variance optimizer, Black-Litterman, sinh tỷ trọng mục tiêu.
- Brinson attribution, factor exposure kiểu Fama-French.
- Sentiment score, news pipeline, proactive alert (Stage 4 — lane khác).
- Multi-currency, tài sản ngoài cổ phiếu VN, phái sinh, trái phiếu.
- Specialist subagent cho portfolio (Stage 5 — cần đo bottleneck trước).
- Realtime/intraday P&L — store là EOD, và feature này không đổi điều đó.

### Acceptance criteria

| # | Bằng chứng |
|---|---|
| 1 | Một ledger giao dịch nạp vào cho ra trọng số, giá vốn và lãi/lỗ khớp với tính tay trên một case có chia cổ tức và một case có cổ phiếu thưởng |
| 2 | TWR của danh mục qua một ex-date khớp số tính tay; `price_basis` mixed hiện ra thay vì bị làm phẳng |
| 3 | Mọi chỉ số statistical trả `refused` + reason code khi lịch sử dưới sàn — và web hiện đúng câu tương ứng, không hiện `0` hay `—` |
| 4 | Cùng một danh mục, hai `portfolio_version` khác nhau cho hai kết quả khác nhau và trace nói ra sự khác biệt |
| 5 | Chat lane trả lời được câu về danh mục và **không** phát ra một chỉ thị hành động nào trên bộ case đối kháng cố tình dụ nó |
| 6 | Không figure nào trong câu trả lời không truy được về một tool call trong trace |
| 7 | Chi phí một Portfolio Study nằm trong trần lane đã khai; Budget Validation vẫn pass |
| 8 | `make test` và bốn cổng web pass |

---

## 4. Ba hướng, và hướng tôi chọn

### Hướng A — Ledger + deterministic analytics trước, AI đọc qua tool

Xây theo lớp yêu cầu thống kê, không theo lớp giao diện.

```
Phase 0  Backfill lịch sử ≥ 250 phiên cho Universe + mã người dùng nắm giữ
Phase 1  Ledger giao dịch → holdings → số học arithmetic + view web + chart
Phase 2  PortfolioField cho nhóm statistical, có sàn mẫu và reason code
Phase 3  Bundle tool `portfolio` cho chat lane + PROMPT_VERSION mới
Phase 4  Portfolio Study lane (versioned, kiểu Analysis) + scenario deterministic
```

Điểm mạnh: mỗi phase tự đứng được. Phase 1 là một sản phẩm hoàn chỉnh cho người
dùng ngay cả khi Phase 2 chưa có, vì nhóm arithmetic không phụ thuộc độ sâu lịch
sử. Phase 1–2 **không chạm** agent loop, prompt hay tool schema, nên chúng không
cần Stage 0 eval gate để an toàn.

Giả định nó phụ thuộc nhất: rằng nhóm arithmetic đủ để người dùng trả tiền trong
khi nhóm statistical còn đang chờ dữ liệu. Nó sai đầu tiên nếu người dùng coi
"portfolio tracker" là thứ miễn phí ở mọi nơi — mà research nói **đúng là như
vậy**: tracker cơ bản miễn phí ở mọi sản phẩm kiểm được. Nên Phase 1 một mình
không phải ARR; nó là điều kiện cần.

### Hướng B — Full Stage 3 theo SOT

Làm đủ những gì roadmap ghi cho Stage 3: typed user objective, portfolio
snapshot có provenance, thesis record versioned, cross-position exposure,
scenario/stress engine, decision journal, memory review UI, clarification policy.

Điểm mạnh: đúng SOT, và graduation gate của Stage 3 là một bar thật ("cùng một
market evidence tạo implication khác nhau đúng theo hai frozen user context").
Điểm yếu: thesis record, decision journal và memory UI là ba subsystem mà bạn
**không** hỏi tới, và chúng đứng chắn giữa hôm nay và cái bạn hỏi. Nó cũng vẫn
bị chặn bởi cùng một vấn đề dữ liệu ở §1.3 mà không giải quyết nó.

### Hướng C — Quant engine batch, AI chỉ narrate

Nightly job tính sẵn một Portfolio Study cho mỗi danh mục; AI đọc artifact đó.
Rẻ nhất về LLM và tái lập tốt nhất. Nhưng nó không đáp ứng "hỏi đáp trực tiếp
trong danh mục" — một câu hỏi ngoài những gì job đã tính sẵn thì không có đường
trả lời.

### Chọn: A, mượn cấu trúc của C cho phần tính, mượn phần nhỏ nhất của B

Cụ thể:

- **Khuôn dữ liệu là Portfolio Envelope**, đối xứng với `alpha/envelope.py`: mọi
  fact về một danh mục tại một trading day, assembled từ store trước khi model
  thấy bất cứ thứ gì, có fingerprint để tái lập. Khoá đổi từ `(symbol, day)`
  sang `(portfolio_version, day)`. Đây là chỗ cấu trúc của C nằm.
- **PortfolioField dùng lại nguyên `SignalField` contract** — `FieldKind`,
  `Sign`, `Unit`, `SignalIssue`, health ba trạng thái. Không có khuôn thứ hai.
  Một `estimator` không kèm CI là `TypeError` lúc import, y như hiện nay.
- **Từ B chỉ lấy hai trường**: horizon và drawdown tolerance, và chỉ khi cần
  diễn giải hệ quả. Thesis record, decision journal, memory UI để lại Stage 3
  đầy đủ.
- **Không optimizer sinh tỷ trọng.** Có risk decomposition: mỗi vị thế đóng góp
  bao nhiêu vào biến động của danh mục. Đó là số đọc về hiện trạng, không phải
  đề xuất về tương lai — và biên compliance nằm ở chỗ đó, không nằm ở toán.

### Vì sao không chờ Stage 0 → 1 → 2 xong

SOT đặt Portfolio ở Stage 3 và thứ tự đó có lý do thật: đừng mở autonomy trước
khi đo được. Nhưng "Stage là dependency boundary, không nhất thiết là một
project duy nhất" — chính roadmap viết vậy. Và dependency thật ở đây không đều
nhau giữa các phase:

| Phase | Chạm agent loop / prompt / tool schema? | Cần Stage 0 eval gate? |
|---|---|---|
| 0 — backfill | Không | Không |
| 1 — ledger + arithmetic + web | Không | Không |
| 2 — PortfolioField | Không (chưa expose ra model) | Không |
| 3 — tool bundle + prompt | **Có** | **Có** — và cả Stage 1 capability contract |
| 4 — Portfolio Study lane | **Có** | **Có** |

Nên đề xuất: **Phase 0–2 chạy song song với Stage 0/1 đang làm. Phase 3–4 chờ
Stage 0 tốt nghiệp.** Điều này không nhảy hàng — nó tách phần deterministic
(không cần cổng đo vì không có model trong đường đi) khỏi phần có model. Và nó
biến Stage 0 từ vật cản thành thứ Phase 3 cần: khi Phase 3 tới, đã có bộ case
đối kháng để chứng minh AI không phát ra chỉ thị hành động — đó chính là
acceptance criteria #5, và không có Stage 0 thì không chứng minh được.

Điều phải ghi vào SOT trước khi bắt đầu: roadmap đang để ngỏ câu *"Portfolio
intelligence hay proactive thesis monitoring tạo giá trị cao hơn cho nhóm người
dùng đầu tiên?"*. Yêu cầu hôm nay trả lời câu đó. Nó cần được ghi là một quyết
định trong `docs/Harness/ai-capability-roadmap.md`, không lặng lẽ bỏ qua.

---

## 5. Phạm vi feature, xếp theo lớp yêu cầu thống kê

Đây là cách xếp quan trọng nhất trong tài liệu này. Nó quyết định cái gì bán
được ngay, cái gì phải chờ dữ liệu, và cái gì không nên làm.

### Lớp 1 — Đúng với một phiên dữ liệu (không phụ thuộc độ sâu lịch sử)

Nhóm này không thể "chưa đủ mẫu". Nó là số học trên ledger + giá đóng phiên gần
nhất. Đây là nền của feature.

| Nhóm | Nội dung |
|---|---|
| Vị thế | số lượng, giá vốn bình quân, giá hiện tại, giá trị, lãi/lỗ chưa thực hiện, lãi/lỗ đã thực hiện, cổ tức đã nhận |
| Cấu trúc | trọng số từng mã, HHI + effective N (số vị thế "hiệu dụng"), phân bổ theo ngành ICB, phân bổ theo sàn |
| Đóng góp | `w_i × r_i` — mã nào đóng bao nhiêu vào biến động của danh mục kỳ này |
| Hiệu suất | TWR theo kỳ, MWR/XIRR (số phụ), so với VNINDEX |
| Khả năng thoát | giá trị vị thế / ADTV 20 phiên = bao nhiêu phiên để thoát; đã có `ADTV_MONEY`, `AMIHUD_ILLIQUIDITY` |
| Trạng thái giao dịch | khoảng cách tới trần/sàn hôm nay, mã đang limit-lock, room ngoại còn lại — đã có `BAND_PRESSURE`, `FOREIGN_ROOM_PCT` |

### Lớp 2 — Cần mẫu, phải mang điều kiện hiệu lực

Nhóm này chỉ trả số khi đạt sàn, và khi trả thì mang theo CI hoặc `δ̂`. Ở store
hiện tại, **phần lớn nhóm này refuse** — xem §1.3.

| Chỉ số | Sàn | Ghi chú |
|---|---|---|
| Biến động danh mục (annualized) | 60 phiên | tái dùng `REALIZED_VOLATILITY_SESSIONS` |
| Max drawdown, days underwater, so với `E[MDD] ≈ 1,25σ√T` | 250 phiên | benchmark Brownian làm cho drawdown có bối cảnh thay vì kịch tính |
| Beta và correlation vs VNINDEX | 250 phiên | **estimator chưa tồn tại** — dữ liệu index đã có, cần viết; Ledoit-Wolf, báo cáo `δ̂` |
| Ma trận tương quan trong danh mục | T/N ≈ 10 → **~300 phiên** cho 30 mã | bắt buộc shrinkage; `δ̂` gần 1 chính là câu "dữ liệu không đỡ được ma trận này" |
| Risk contribution mỗi vị thế | như ma trận | đây là thay thế của optimizer, và nó chỉ đọc |
| Sharpe / Sortino danh mục | 250 phiên để tính, **~970 phiên để CI không chứa 0** | trình bày kèm CI, hoặc không trình bày |
| VaR/CVaR historical | 250 phiên tối thiểu, 500–1000 để inference đáng tin | phải hiện N; dưới 100 "hit" thì test mất lực |

### Lớp 3 — Scenario, deterministic, có giả định nêu rõ

Không gắn probability giả — SOT cấm điều đó trong `Scenario`.

- Shock đồng loạt: "nếu toàn danh mục giảm X%", có tính đến bước giá và biên độ.
- Historical replay: "nếu lặp lại đoạn từ ngày A đến ngày B", dùng đúng return
  đã xảy ra của chính các mã đang nắm.
- Sensitivity một vị thế: "nếu mã lớn nhất mất X%, danh mục mất bao nhiêu".
- Thời gian thoát dưới áp lực: ADTV giảm một nửa thì cần bao nhiêu phiên.

Ràng buộc từ research và từ quant methods: khi một mã đang limit-lock,
**không** được tính như thể khớp được ở giá đóng cửa. Engine phải đánh dấu
"không thể giao dịch", vì không có đối ứng. Và mọi kịch bản có bán phải nói T+2:
bán hôm nay không có tiền hôm nay.

### Không làm

Brinson attribution · factor exposure kiểu Fama-French · mean-variance optimizer
· Black-Litterman · tỷ trọng mục tiêu · rebalance proposal · sentiment · dự báo
giá · probability gắn vào scenario.

---

## 6. Chỗ phải chạm trong code

Không có subsystem mới. Portfolio là instance thứ hai của những khuôn đã có.

| Việc | Chạm gì | Ghi chú |
|---|---|---|
| Ledger + holdings | bảng mới: `portfolio`, `portfolio_transaction`, `portfolio_version`; `src/stocks/portfolio/` theo pattern `router.py` mỏng + `service.py` | holdings là **phái sinh** từ transaction, không lưu song song — nếu lưu cả hai thì hai nguồn sự thật sẽ lệch |
| Số học arithmetic | `portfolio/service.py` + module tính riêng | không gọi model, theo dependency rule #5 của target architecture |
| PortfolioField | mở rộng `stocks/signals/` — cùng `FieldKind`/`Unit`/`Sign`/`SignalIssue` | reason code mới phải thêm câu ở **cả** `alpha/reasons.py` và `apps/web/src/lib/signal-issues.ts` |
| Beta/correlation estimator | `signals/cross_sectional.py` — `RELATIVE_STRENGTH` đang registered là unavailable | dữ liệu index đã có; thiếu estimator, không thiếu dữ liệu |
| Portfolio Envelope | `src/portfolio/envelope.py` đối xứng `alpha/envelope.py` | fingerprint + `portfolio_version` |
| Tool bundle | `agent/registry.py` + `toolsets.py` + `definitions.py`; thêm `"portfolio"` vào `CHAT_TOOLSETS` | `reads_external=False` (đọc Postgres) → không bị bọc `<untrusted_tool_result>`; thêm tên vào `_FIGURE_TOOLS` |
| Prompt | `PROMPT_VERSION` mới ở `agent/prompt/sections.py` | phần "Bạn KHÔNG đọc được... danh mục theo dõi của họ" ở dòng ~113 **phải** đổi; ranh giới hành động ở dòng 92–97 **giữ và làm chặt hơn** |
| Ngân sách | `core/llm/budget.py`, `admission.py` | lane mới phải cộng đúng envelope, nếu không startup fail |
| Web | `shell-state.tsx:29` (`ShellView`), `app-shell.tsx` switch, view mới, inspector tab | **cần chart library** — hiện chỉ có `Sparkline` SVG viết tay |
| Backfill | `config.py:121` `backfill_enabled=False` + `symbol_backfill` | quota vnstock 20–60 req/phút là ràng buộc chặn thời gian |

---

## 7. Rủi ro, xếp theo mức chặn

1. ~~**Độ sâu lịch sử (§1.3).** Chặn toàn bộ Lớp 2.~~ **Đã bác — xem §1.4b.**
   Lịch sử giá đủ trên 28/30 mã. Rủi ro còn lại hẹp hơn nhiều: `market_cap_vnd`
   thưa (5/2.527 phiên) làm bốn factor percentile phụ thuộc cửa sổ 21 phiên, và
   hai mã mới trong Universe sẽ `refused` — UI phải xử lý được việc một phần
   danh mục có số và một phần không, trong cùng một bảng.
2. **Universe 30 mã.** Danh mục thật gần như chắc chắn có mã ngoài VN30. Nếu để
   nguyên cổng ở `signals.py:448`, người dùng thấy "ngoài phạm vi" trên chính
   cổ phiếu họ đang giữ. Cần tách: field chỉ cần bar của chính mã thì mở được;
   percentile cross-section thì không mở bằng cách nới danh sách, vì
   `min_sample_for` tính trên mẫu **được hỏi**.
3. **Ngôn ngữ trôi.** Có số liệu thật về vị thế thật của người dùng làm áp lực
   đưa ra chỉ thị tăng lên, đúng như prompt đã cảnh báo. Cần bộ case đối kháng
   trong Stage 0, không phải một dòng thêm vào prompt.
4. **Privacy.** Chuyển transaction-level detail vào context model là một quyết
   định compliance, không phải quyết định kỹ thuật. Ngành ngân hàng có tiền lệ
   chặn hẳn LLM bên thứ ba.
5. **Ngân sách.** Lane thứ tư trên envelope $45 nghĩa là lane khác phải nhường.
6. **Chart library.** Dependency mới — cần đồng ý trước.
7. **DB dev lệch schema so với repo** (`b7f4e9c21a08` vs 25 migration). Cần dọn
   trước khi đo lại bất cứ điều gì trên nó.

---

## 8. Quyết định đã chốt (2026-08-23)

Bốn quyết định phạm vi đã được product owner chọn. Chúng là ràng buộc cho plan,
không phải đề xuất.

| # | Quyết định | Hệ quả trực tiếp |
|---|---|---|
| 1 | **Research-only.** AI nói mức và hệ quả; không tỷ trọng mục tiêu, không mức vào/ra, không rebalance proposal. A3 không mở. | Ba lớp phòng vệ ở §1.6 **giữ nguyên và làm chặt hơn**. Không cần legal sign-off. Quant engine chỉ làm risk decomposition — HRP nếu cần cấu trúc cluster, nhưng **không** sinh tỷ trọng. Black-Litterman và mean-variance ra khỏi scope vĩnh viễn ở v1. Mọi field vẫn là `descriptive`; không mở `predictive`. |
| 2 | **Nhập tay từng giao dịch.** Ledger là nguồn sự thật duy nhất; holdings phái sinh. | Không parser CSV, không broker adapter, không Stage 6 security review trong v1. Cost basis đúng qua ex-date là kiểm được. Ma sát nhập lần đầu là nợ UX đã biết — giải bằng UX nhập nhanh, không bằng import. |
| 3 | **Mở theo lớp.** Field chỉ cần bar của chính mã: mở cho mọi mã có OHLCV trong store. Percentile cross-section: giữ trong Universe. | Cổng ở `agent/tools/signals.py:448` phải tách theo `FieldKind` thay vì chặn cả gói theo symbol. `min_sample_for` không đổi — nó vẫn tính trên mẫu **được hỏi**. Người dùng thấy số cho mọi mã họ giữ, và thấy rõ cái gì không xếp hạng được, kèm reason code riêng. |
| 4 | **Model chỉ thấy figure đã tính.** Không transaction-level detail trong context. | Tool portfolio trả figure cấp danh mục, không trả sổ giao dịch. Data minimization giữ đúng contract "closed prompt". Câu hỏi kiểu "lô mua tháng 3 của tôi thế nào" sẽ **không** trả lời được — đó là đánh đổi đã chấp nhận, và AI phải nói ra giới hạn đó chứ không đoán. |

### Ba quyết định còn để ngỏ

Chúng đổi chi tiết, không đổi phạm vi, và có thể quyết trong lúc lập plan.

1. **Chart library.** Web chỉ có `Sparkline` SVG viết tay (`inspector.tsx:699`,
   viewBox 320×100). Equity curve, allocation, drawdown cần thứ khác. Đây là
   dependency mới → cần đồng ý trước khi thêm.
2. **Lane nào nhường phần trong envelope $45.** Budget Validation chặn startup
   nếu các lane không cộng đúng envelope, nên không có đường tránh.
3. **Multi-portfolio ngay hay không.** Số lượng portfolio/holdings là paywall có
   evidence chéo mạnh nhất trong research (Sharesight, Snowball, Simply Wall St).
   Nếu ARR dựa vào nó thì schema phải mang `portfolio_id` từ migration đầu —
   thêm sau là migration đau.

---

## 9. Handoff

Hướng đã chốt: **A**, với Portfolio Envelope làm khuôn dữ liệu và `SignalField`
làm khuôn field. Thứ tự: Phase 0–2 song song với Stage 0/1 đang chạy; Phase 3–4
chờ Stage 0 tốt nghiệp.

Việc phải làm trước khi viết plan:

1. ~~Xác nhận độ sâu lịch sử~~ **Đã làm, xem §1.4b.** 28/30 mã ≥970 phiên.
   **Phase 0 không còn cần thiết** — kế hoạch bắt đầu thẳng ở Phase 1 (ledger +
   arithmetic + web). Thay vào đó, thêm một việc nhỏ vào Phase 2: quyết định UI
   xử lý thế nào khi một phần danh mục có số và một phần `refused`.
2. **Dọn lệch schema DB dev** (`b7f4e9c21a08` so với 25 migration trong repo)
   trước khi đo lại bất cứ gì trên nó.
3. **Ghi quyết định vào SOT**: roadmap đang để ngỏ câu "Portfolio intelligence
   hay proactive thesis monitoring tạo giá trị cao hơn cho nhóm người dùng đầu
   tiên?" — quyết định hôm nay trả lời nó, và bốn quyết định ở §8 thuộc product
   contract chứ không thuộc plan.
