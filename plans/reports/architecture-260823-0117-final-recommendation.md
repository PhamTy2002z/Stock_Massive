# Đề xuất kiến trúc cuối — VisgniteAI

Tổng hợp sau khi đối chiếu `plans/GPT/Chat.md` (§1–86) với repo và đo trực tiếp provider.
Mọi số trong tài liệu này là số đo được, không phải số trích từ trang pricing.

Nguyên tắc khung: blueprint là **target state**. Repo đi trước blueprint ở tầng
data/provider/intelligence, đi sau ở tầng context/portfolio/presentation. Nên
kiến trúc cuối không phải "build theo blueprint", mà là:

> **Hardening cái đã có → thêm primitive duy nhất còn thiếu (Context) → chiếu
> state cá nhân lên intelligence dùng chung (Portfolio) → sau cùng mới đến
> transport (Realtime).**

---

## 1. Năm invariant — mọi quyết định sau phải giữ

Đều đã đúng trong repo hôm nay.

1. **Đường phục vụ request là store-only.** Enforce ở runtime bằng
   `core/provider_access.py::store_only_execution()`, không phải quy ước.
2. **Provider chỉ được gọi từ collector/ingestion**, qua đúng một arbiter Redis
   (`core/quota.py`), fail-closed khi Redis chết.
3. **Backend sở hữu mọi số được hiển thị.** `alpha/production.py`: envelope
   verbatim dưới `evidence`; model chỉ góp prose, thứ tự nhấn, danh sách id.
   Không có key nào trong payload để số của model render thành figure.
4. **Stock Intelligence là dùng chung**, keyed `(symbol, trading_day)`, immutable.
   Một Analysis phục vụ mọi người watch mã đó — enforce bằng unique constraint.
5. **Trading Day định nghĩa bằng dữ liệu, không bằng đồng hồ**
   (`alpha/nightly.py`). Mọi tính năng "hôm nay" phải theo mốc này.

---

## 2. Sáu quyết định

### D1 — Context System: resolve server-side, không làm agent tool

Primitive duy nhất thật sự còn thiếu. `Context {type, id}` với
`type ∈ {market, symbol, news, sector, portfolio}`.

Cách làm: chip đi kèm message; API resolve từng chip thành một evidence block
**đọc từ store**; block đưa vào Turn dưới dạng system content. Không thêm tool.

Vì sao không phải tool: tool nghĩa là model tốn token để quyết định fetch gì, và
mỗi fetch là một round trip. Resolve server-side là deterministic, gần như miễn
phí, và phủ 90% trường hợp — user đang xem chính thứ họ hỏi. Nó cũng **đi vòng
qua ADR §79**: không đổi agent contract, nên ship được ngay thay vì chờ quyết định.

Giữ ADR §79 mở cho 10% còn lại (câu hỏi mở kiểu "so sánh STB với MBB", nơi model
phải tự chọn mã). Nhưng đừng để Context bị chặn bởi nó.

### D2 — Portfolio là ledger giao dịch; position là derived

Không lưu position + giá vốn bình quân.

Lý do, theo thứ tự sức nặng:

- **Giá vốn là một phép tính, không phải một dữ kiện.** Lần mua thứ hai là lúc
  cột "avg cost" lưu sẵn không còn dựng lại hay sửa được.
- **Corporate action.** Repo đã thu `corporate_actions`. Một lần chia cổ tức cổ
  phiếu hay split làm giá vốn lưu sẵn sai trên 100%, và AI sẽ kể lại con số sai
  đó một cách tự tin. Áp CA lúc đọc thì đảo được và vẫn đúng khi dữ liệu CA về
  muộn — mà nó sẽ về muộn, vì collector CA chạy nhịp chậm. Mutate số đã lưu là
  phá huỷ và không audit được.
- **Basis giá.** Backfill lấy `adjusted=True`, snapshot market đo được là
  `price_basis: "raw"`, còn giá vốn user nhập là giá danh nghĩa họ đã trả. So
  giá vốn danh nghĩa với chuỗi đã điều chỉnh là sai có hệ thống. **Phải hoà giải
  basis trước khi hiển thị bất kỳ P/L nào.** Derive buộc phải đối diện việc này.
- Decision Journal (§65.13) không có gì để gắn vào nếu không có giao dịch.

Kế toán bán: **bình quân gia quyền** (khớp thói quen hiển thị của retail VN;
FIFO đòi lot tracking). Ghi rõ lựa chọn này.

```
portfolio_transactions(user_id, symbol, side, quantity, price,
                       executed_on, fee, note, created_at)
position = derived(transactions + corporate_actions áp theo executed_on)
```

### D3 — Có position thì có watchlist entry

Cohort nightly là union các Watchlist. Nếu position là tập tách riêng, một mã
đang giữ có thể không có Analysis nào — và tiền đề "base intelligence luôn tồn
tại" của §77 sẽ sai âm thầm đúng ở những mã quan trọng nhất.

Cách sửa rẻ nhất: thêm position thì tạo luôn watchlist entry. Không đụng
`nightly.py`.

### D4 — Push phần phát hiện, pull phần văn

Đây là quyết định định đoạt Portfolio AI có khả thi về chi phí hay không.

`config.py`: `llm_budget_analysis_usd = 10.0`/tháng, Budget Validation chặn
startup nếu các lane không cộng đúng envelope. Nightly per-symbol ở ~50 mã × ~21
phiên ≈ 1.050 run → **~$0,0095 mỗi Analysis**. Lane đó đã gần trần khi *chưa* có
tính năng portfolio nào.

Nên văn bản per-user không bao giờ được push nightly — cách đó nhân theo số user
đăng ký, bất kể họ có mở app hay không.

Tách:

- **Phát hiện = arithmetic, miễn phí, push được.** "2 thay đổi đáng chú ý",
  "Portfolio +0,82% vs VNINDEX +1,03%", "1 thesis change", "tỷ trọng vượt 30%".
  Tất cả tính được từ `analysis.verdict` (đã là cột extract, đã có index
  `ix_analysis_symbol_day`) cộng arithmetic vị thế. Đây là §65.2/§65.3 đầy đủ,
  chi phí LLM bằng 0 — và nó chính là hook retention.
- **Văn = LLM, pull, cache theo `(user, trading_day)`.** Sinh khi user mở, và
  chỉ khi phát hiện thật sự có gì.

Giữ nguyên toàn bộ UX §65 nhưng nhân chi phí theo user *hoạt động*.

### D5 — Score chỉ gồm thành phần deterministic

§65.4 cấm "arbitrary AI number" rồi liệt kê `Quality 84 / Valuation 76 /
Momentum 81`. Ở cấp portfolio, ba trục đó chỉ có thể là bình quân các phán đoán
prose của model — đúng cái vừa cấm, khoác áo một metric.

Ship: concentration, sector exposure (`listing_roster.icb_code` đã có), P/L,
phân bố verdict. Giải thích được từng điểm.

Hoãn: correlation, beta, VaR, diversification score, và scenario contribution
(§65.12) — vì dữ liệu chưa có. Đo được:

```
stock_daily_ohlcv: 1.710 mã · 119.525 dòng · 2022-02-23 → 2026-08-07
→ ~70 dòng/mã (correlation 1 năm cần ~250)
→ nến mới nhất cũ 16 ngày
BACKFILL_ENABLED=false · backfill_symbols_per_run=5 → phủ 100 mã ≈ 20 ngày
```

Nên: **độ sâu lịch sử giá cho mã có position là tiền đề tường minh** của phase
Risk/Scenario, xứng đáng một backfill lane riêng ưu tiên trên backfill chung. Và
"Confidence: Medium" của §65.12 phải derive (độ sâu lịch sử, R² của hồi quy),
không được khẳng định suông.

### D6 — Portfolio context và web content không chung một Turn khi chưa có guard

Context Stack §64.3 đặt `[Portfolio] [STB] [Tin NHNN]` vào một Turn — nghĩa là
holdings và tổng tài sản nằm cùng context với text trang web do người ngoài kiểm
soát, trong khi `fetch_url` đang bật. Injection trong bài fetch được có thể khiến
holdings bị nhét vào URL kế tiếp.

`untrusted.py` và `guardrails.py` đã có; chỗ này cần một luật tường minh, không
cần cơ chế mới: khi có portfolio context thì hoặc tắt web tool cho Turn đó, hoặc
allowlist target của `fetch_url`.

---

## 3. Realtime — đã mở, nhưng phải đóng khung chặt

Đo tối 23/08 (thị trường đóng):

| Hạng mục | Kết quả |
|---|---|
| Thư viện | `signalrcore 1.0.x` fail negotiate (bắt buộc `negotiateVersion`); hub FiinQuant trả negotiate v0 không có key đó. **`0.9.5` chạy được** |
| Hub | `Connection established` → `Joined group: Realtime.Ticker.STB`, `Realtime.Index.VN30` |
| Tick | 0 — ngoài giờ giao dịch |
| Stream + REST | **Cùng tồn tại.** 4/4 lần `fetch_market` OK, kể cả khi stream đang join group → **không cần arbitration với collector** |
| `start()` | Non-blocking, tự spawn thread |
| Payload | `RealTimeData` có sẵn foreign flow **và market breadth** (`TotalStockUpPrice/Down/NoChange/OverCeiling/UnderFloor`) → subscribe index là có breadth luôn |
| Ngoài giờ | Server đóng (`{"type":7,"error":"Connection closed with an error."}`), client tự reconnect + rejoin ~7s/lần |

Hình dạng đề xuất — đúng §82.1 nhưng đã xoá nhánh arbitration:

```
FiinQuant SignalR hub
   │ một connection dài, universe TĨNH (VN30 + indices)
   ▼
Stream Worker ──► Redis hot keys (quote:*, market:*)
                        │
                        ▼
                  SSE gateway ──► browsers (fan-out)
```

**SSE, không WebSocket.** Feed một chiều, repo đã stream SSE (`agent/sse.py`),
và SSE cho reconnect semantics miễn phí qua proxy. Dựng WS stack cho feed một
chiều là phức tạp không cần thiết.

**Universe tĩnh.** Free tier một connection; hành vi reconnect quan sát được ở
ngoài giờ cho thấy subscribe/unsubscribe động đặt churn lên đúng cái connection
không được phép mất. §82.2 đúng khi gate subscription manager theo telemetry.

**Realtime không thay collector.** Stream nuôi bảng giá live (Redis, ephemeral);
collector vẫn ghi `ProviderSnapshot` canonical. Hai class freshness, hai store —
cũng là lý do freshness contract §75 phải phủ **cả hai** (hiện chỉ mô tả một nguồn).

**Một phép đo gate toàn bộ thiết kế** — trong giờ giao dịch (thứ Hai 24/08,
09:00–15:00): tick rate mỗi mã, vòng reconnect có còn trong phiên hay không,
breadth có về khi subscribe index hay không. Ba số đó quyết định buffer, backoff,
và việc có bỏ được phần tự tính breadth. Thiết kế worker trước khi có chúng là đoán.

---

## 4. Chương còn thiếu: Entitlement lifecycle

§73/§74 model **quota exhaustion** (429). Sự cố tối nay là **entitlement expiry**
(401) — không degradation policy nào chữa, và nó sẽ **lặp lại 06/09** vì cả hai
tài khoản đều là `FiinQuant.Trial` 14 ngày, không phải free tier.

| Account | Trial | Data |
|---|---|---|
| `typ00448@…` | 09/08 → 23/08 | 401 toàn bộ |
| `ty.pham.glm@…` | 23/08 → **06/09** | OK |

Cần thêm: đọc `end_date` và `enabled` từ JWT lúc login, alert khi tới gần, và
coi 401-từ-provider là một state khác quota exhaustion.

Điều chỉnh so với đề xuất trước của tôi: **đừng đọc *capacity* từ token.** Cả hai
trial đều báo `per_minute/hour/day/month = 0` và `hitcount_permonth = 0`, nên các
claim đó vô dụng. Chỉ `end_date` / `enabled` là dùng được.

---

## 5. Build order cuối

**P0 — correctness, độc lập mọi thứ khác**

1. ~~Trần theo giờ cho vnstock~~ — **đã làm.** `ACCOUNT_SPACING_*` giờ derive từ
   cả hai cửa sổ vnstock công bố (20/60 rpm theo phút, 3.000/giờ cả hai tier),
   cửa sổ chặt hơn thắng, safety factor 0.9. Guest 3,33s (18 rpm · 1.080/giờ),
   keyed 1,33s (45 rpm · 2.700/giờ). Trước đó keyed là 1,0s → 3.600/giờ, vượt
   trần 20%. Test mới khoá cả hai cửa sổ theo *rate*, không theo hằng số — vì
   mọi test cũ đều gọi tên hằng số nên xanh ở cả hai giá trị.
2. ~~Chặn `SystemExit` tại biên adapter~~ — **đã có sẵn từ trước.** Tôi báo sai ở
   bản đầu: `core/vnstock_client.py:152` đã bắt `BaseException`, nhận diện
   `SystemExit` và đổi thành `VnstockUnavailable`; `vnstock_wrapper.py:76` cũng
   bắt. Cả hai đã được `vnstock_provider.py` xử lý. Không có việc gì phải làm.
3. Monitor entitlement expiry — **còn lại.**

**P1** Provider budget observability + degradation states (§73/§74) — mở rộng lane priority đã có.
**P2** Freshness contract tới biên AI, phủ cả snapshot store và OHLCV.
**P3** **Context System** (D1). Đòn bẩy sản phẩm lớn nhất trên mỗi đơn vị công việc.
**P4** **Thesis delta.** So `analysis.verdict` ngày N vs N−1; một enveloped call chỉ khi đổi. Chuỗi và cột đã có. Retention cao nhất trên mỗi đồng.
**P5** **Portfolio** — ledger (D2) → position derived có áp CA → projection deterministic trên Analysis dùng chung (D3, D5) → push detection / pull prose (D4). Bước đầu phải dùng được khi không có AI.
**P6** **Realtime transport** — sau phép đo thứ Hai.
**P7** News story clustering + entity tagging. Độc lập, song song lúc nào cũng được.

**Hoãn / từ chối:** dynamic subscription manager, scenario engine, decision
journal, multi-agent split, model modes (Deep Research §64.8 không có lane nào
trong envelope $45 chia 3), LLM tự quyết fetch làm path chính, block không có
evidence inline, daily brief theo đồng hồ.

---

## 6. UI: giữ một màn hình

CLAUDE.md chốt một màn hình; blueprint muốn Stock Detail page + 3-tab nav.

Hoà giải: **Stock Detail vào inspector rail** (`components/shell/inspector.tsx`
đã có), không phải route. Portfolio thành view thứ năm cạnh
`chat`/`board`/`new`/`news`. Vừa giữ invariant, vừa phục vụ blueprint tốt hơn —
context vẫn sống khi soi mã, và câu đang gõ dở không mất.

---

## Câu hỏi chưa giải quyết

1. FiinQuant sau 06/09: đăng ký free tier thật (90 rpm / 100k tháng / 33 mã
   realtime) hay lên gói trả phí? Quyết định này chặn cả collector và realtime.
2. Trần 5 mã mỗi danh mục — ràng buộc sản phẩm hay ràng buộc dẫn xuất từ ngân
   sách? Nâng lên 10 là nhân đôi cohort và lane Analysis.
3. ADR §79 (agent đọc first-party stock data): mở hạn chế cho câu hỏi mở, hay
   giữ đóng và chỉ dùng Context resolve server-side?
4. Basis giá cho P/L: quy giá vốn về adjusted, hay giữ nominal và so với chuỗi raw?
5. `docker compose restart api` không đọc lại `.env` (phải `up -d
   --force-recreate`) — có bổ sung vào CLAUDE.md không?
