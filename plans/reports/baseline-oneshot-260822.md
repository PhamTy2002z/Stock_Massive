# Baseline one-shot lane Analysis — đo trên dữ liệu thật

Ngày đo: 2026-08-22. Plan: `plans/260822-2010-evidence-adjudicating-loop/phase-01-baseline.md`.
Nguồn: DB `stockmassive` trên `stockmassive-db-1`. Mọi con số dưới đây kèm query sinh ra nó.

## Tiền đề của Phase 1 đã sai một nửa

Phase 1 viết *"Lane Analysis chưa từng chạy trên dữ liệu thật"*, suy từ
`core/config.py:220` (`alpha_desk_enabled: bool = False`). Mặc định đó là mặc định **của code**;
`.env` của môi trường nội bộ đã đặt `ALPHA_DESK_ENABLED=true`, và store đã có
**8 Analysis `ready`** trên 2 Trading Day cùng **10 run `failed`** trước đó. Lane đã chạy.

Nên phần "bật cờ" của Phase 1 không có việc gì để làm. Phần còn lại — lấy mốc — có, và dưới đây
là toàn bộ mốc đó.

## Cửa 5 Trading Day chưa đạt, và không thể đạt bằng cách viết code

Validation của Phase 1 đòi **≥5 Trading Day có Analysis `ready`**. Thực tế có **2**: 2026-08-20
và 2026-08-21. Ba phiên còn lại là ba phiên thật phải chờ; không có đường nào rút ngắn nó, và
tự sinh dữ liệu để lấp thì phá đúng cái Phase 1 tồn tại để bảo vệ. Mốc dưới đây vì thế là mốc
**2 phiên, 8 Analysis, 5 mã** (BID · FPT · STB · VCB · VHM), và mỗi con số cần đọc kèm cỡ mẫu đó.

Cái cửa 5 phiên bảo vệ là phương sai theo phiên: một phiên có nhiều mã bị khoá trần sẽ đổi phân
bố `reasonCode`. Kết quả dưới đây **không** phụ thuộc vào phương sai đó — 33/57 refusal là
refusal cấu trúc, không phụ thuộc phiên nào cả (xem §4).

## 1. Run: status × error_code

```sql
select trading_day, status, coalesce(error_code,'-') as error_code, count(*), sum(attempts)
from analysis_run group by 1,2,3 order by 1,2,3;
```

| trading_day | status | error_code | run | attempts |
|---|---|---|---|---|
| 2026-08-14 | failed | `missing_market_snapshot` | 2 | 6 |
| 2026-08-17 | failed | `budget_exhausted` | 4 | 8 |
| 2026-08-18 | failed | `budget_exhausted` | 4 | 12 |
| 2026-08-20 | ready | — | 3 | 3 |
| 2026-08-21 | ready | — | 5 | 5 |

Mọi run `ready` xong ở **attempt đầu tiên**. Cả 10 failure đều là failure hạ tầng — snapshot
thiếu và ngân sách cạn — không failure nào là failure nội dung. `budget_exhausted` ở 08-17/08-18
xảy ra khi tuyến còn trỏ `nvidia/nemotron-3-ultra-550b-a55b:free`; 08-20 trở đi là `gpt-5.6-luna`
và không tái diễn.

## 2. Verdict

```sql
select verdict, count(*) from analysis group by 1 order by 2 desc;
```

`hold` 4 · `reduce` 2 · `watch` 2. Không `avoid`, không `accumulate`. Với 8 quan sát thì đây
chưa phải phân bố, chỉ là ghi nhận rằng cả 8 lượt đều rơi vào nửa trung tính–giảm.

| symbol | day | verdict |
|---|---|---|
| FPT | 08-20 | hold |
| STB | 08-20 | reduce |
| VCB | 08-20 | watch |
| BID | 08-21 | reduce |
| FPT | 08-21 | hold |
| STB | 08-21 | hold |
| VCB | 08-21 | watch |
| VHM | 08-21 | hold |

## 3. Figure `ok` / `degraded` / `refused` mỗi Analysis

```sql
with f as (
  select a.symbol, a.trading_day, fig->>'health' health
  from analysis a,
       jsonb_array_elements(a.payload->'evidence'->'sections') sec,
       jsonb_array_elements(sec->'figures') fig
)
select symbol, trading_day,
       count(*) filter (where health='ok') ok,
       count(*) filter (where health='degraded') degraded,
       count(*) filter (where health='refused') refused,
       count(*) total
from f group by 1,2 order by 2,1;
```

| symbol | day | ok | degraded | refused | total |
|---|---|---|---|---|---|
| FPT | 08-20 | 10 | 0 | 5 | 15 |
| STB | 08-20 | 10 | 0 | 8 | 18 |
| VCB | 08-20 | 10 | 0 | 8 | 18 |
| BID | 08-21 | 10 | 0 | 8 | 18 |
| FPT | 08-21 | 10 | 0 | 5 | 15 |
| STB | 08-21 | 10 | 0 | 8 | 18 |
| VCB | 08-21 | 10 | 0 | 8 | 18 |
| VHM | 08-21 | 9 | 1 | 7 | 17 |
| **tổng** | | **79** | **1** | **57** | **137** |

**41,6 % figure đưa cho model là `refused`.** Và con số `ok` cực kỳ đều: đúng **10** ở 7/8
Analysis, 9 ở lượt còn lại.

Bảng trên đếm `payload.evidence.sections` thôi. Có **một figure thứ 11 nằm ngoài `sections`** —
`payload.evidence.priceZone`, `price_zone.ordinary_range_pct`, `health='ok'` ở cả 8 lượt, mà
`alpha/field_profile.py:55` gọi là *core evidence* và miễn cho nó khỏi cap 6 field/trục. Nên vốn
định lượng thật của một Analysis hôm nay là **11 figure**, và tổng dùng được là **88**, không phải 80.

Theo trục:

```sql
select sec->>'axis' axis, ... from analysis a, jsonb_array_elements(a.payload->'evidence'->'sections') sec,
       jsonb_array_elements(sec->'figures') fig group by 1;
```

| axis | ok | degraded | refused |
|---|---|---|---|
| money_flow | 32 | 0 | 0 |
| technical | 39 | 1 | 8 |
| fundamental | 8 | 0 | 33 |
| news | 0 | 0 | 16 |

Trục `news` **rỗng hoàn toàn** ở cả 8 lượt. Trục `fundamental` có 8/41 figure dùng được, và cả 8
là `factor_percentiles.roe_percentile`.

## 4. `reasonCode`: con số quan trọng nhất của Phase 1

```sql
select coalesce(fig->>'reasonCode','(null)') rc, fig->>'health' h, sec->>'axis' axis,
       fig->>'fieldId' fid, count(*)
from analysis a, jsonb_array_elements(a.payload->'evidence'->'sections') sec,
     jsonb_array_elements(sec->'figures') fig
where fig->>'health' <> 'ok' group by 1,2,3,4 order by 5 desc;
```

| reasonCode | health | axis | fieldId | n |
|---|---|---|---|---|
| `fundamental_not_stored` | refused | fundamental | `factor_percentiles.book_yield_percentile` | 8 |
| `fundamental_not_stored` | refused | fundamental | `factor_percentiles.earnings_yield_percentile` | 8 |
| `unavailable` | refused | news | `news_flow.approved_item_count_7_sessions` | 8 |
| `unavailable` | refused | news | `news_flow.approved_item_count_30_sessions` | 8 |
| `unavailable` | refused | fundamental | `bank_metrics.nim_pct` | 5 |
| `unavailable` | refused | fundamental | `bank_metrics.npl_ratio_pct` | 5 |
| `unavailable` | refused | fundamental | `bank_metrics.llr_coverage_pct` | 5 |
| `unavailable` | refused | fundamental | `developer_metrics.net_debt_to_ebitda` | 1 |
| `unavailable` | refused | fundamental | `developer_metrics.inventory_share_of_assets_pct` | 1 |
| `insufficient_cross_section` | refused | technical | `momentum_rank.percentile_12_2` | 8 |
| `price_move_exceeds_band` | degraded | technical | `band_pressure.limit_days_in_window` | 1 |

**Chỉ 4 mã issue xuất hiện trên 36 mã đã dựng.** Và chúng chia làm hai loại khác nhau về bản chất:

- **Refusal cấu trúc — 49/57 (86 %).** `fundamental_not_stored` (16) và `unavailable` (33) nói
  *store không có dữ liệu này, cho mã nào cũng vậy*: BCTC chưa persist, trục news chưa dựng.
  Một vòng lặp **không đi quanh được** cái này — không có figure nào khác trong store để với
  tới. Cả hai đều nằm trong `Non-goals` của plan (*persist BCTC · axis news*).
- **Refusal theo dữ liệu — 8/57 (14 %).** `insufficient_cross_section` trên
  `momentum_rank.percentile_12_2`: phép xếp hạng cần cross-section đủ rộng, và Universe phiên đó
  không đủ. Đây là loại refusal mà substitution nói được điều gì.
- **Degradation — 1.** `price_move_exceeds_band` là đúng loại mà `alpha/reasons.py` viết câu giải
  thích cho: số vẫn tính được, chỉ cách đọc phải đổi.

### Cửa của Phase 1 không đóng plan, nhưng đổi lý do của Phase 4

Phase 1 viết: *"Nếu baseline cho thấy `refused` gần như không xảy ra, giá trị của Phase 4 sụp."*
`refused` xảy ra ở **41,6 %** — cửa đó không đóng. Nhưng **lý do** thì phải viết lại: giá trị của
vòng lặp gần như **không** đến từ việc đi quanh 8 refusal cấu trúc, vì 86 % refusal không có
đường quanh. Nó đến từ chỗ khác, và chỗ đó đo được:

```sql
select distinct fig->>'fieldId' from analysis a,
  jsonb_array_elements(a.payload->'evidence'->'sections') sec, jsonb_array_elements(sec->'figures') fig;
```

**21 fieldId** từng xuất hiện trong một Analysis (20 trong `sections` + `price_zone`). Catalog
`stocks/signals/registry.py` khai báo **30 `SignalField`**, và `alpha/field_profile.py` chọn ra
một Field Profile cố định với cap `MAX_FIELDS_PER_AXIS = 6`. Nghĩa là **16 field** đã dựng, đã có
`interpretation`, đã qua bar thống kê — và **chưa bao giờ tới được một Analysis nào**, vì Profile
không gọi tên chúng: `liquidity_profile.adtv_percentile`,
`liquidity_profile.amihud_illiq`, `mean_reversion.trailing_z`,
`mean_reversion.half_life_sessions`, `risk_adjusted.sharpe_annualized`,
`risk_adjusted.sortino_annualized`, `relative_strength.beta_vs_market_index`,
`price_zone.ordinary_range_pct`, `trend_signal.total_return_12m_pct`,
`indicator_pack.macd_12_26_vnd`, `indicator_pack.bollinger_percent_b_20`,
`drawdown_stats.max_drawdown_pct`, `drawdown_stats.days_underwater`,
`drawdown_stats.mdd_over_expected`, `factor_percentiles.size_percentile`,
`foreign_flow_pressure.net_volume_over_adtv`, `liquidity_profile.adtv_shares`.

One-shot gói **cùng một Field Profile** cho mọi mã, mọi phiên: `fieldProfileVersion='v1'` ở cả 8
Analysis. Cái vòng lặp mua được không phải "đi quanh chỗ trống" — mà là **với tới 16 field còn lại
khi 11 field của Profile không trả lời được câu hỏi của mã đó**. Phase 4 phải được viết theo hình
dạng đó, và đó cũng là chỗ ngữ nghĩa `fieldProfileVersion` đổi.

## 5. Trích dẫn: bao nhiêu figure dùng được thực sự được dẫn

```sql
with usable as (
  select a.id, a.symbol, a.trading_day, fig->>'fieldId' field_id
  from analysis a, jsonb_array_elements(a.payload->'evidence'->'sections') sec,
       jsonb_array_elements(sec->'figures') fig
  where fig->>'health' in ('ok','degraded')
), cited as (
  select a.id, c #>> '{}' field_id from analysis a, jsonb_array_elements(a.payload->'citedFieldIds') c
)
select u.symbol, u.trading_day, count(distinct u.field_id) usable,
       (select count(distinct field_id) from cited where cited.id=u.id) cited
from usable u group by u.id, u.symbol, u.trading_day order by u.trading_day, u.symbol;
```

| symbol | day | usable | cited |
|---|---|---|---|
| FPT | 08-20 | 10 | 7 |
| STB | 08-20 | 10 | 5 |
| VCB | 08-20 | 10 | 5 |
| BID | 08-21 | 10 | 5 |
| FPT | 08-21 | 10 | 5 |
| STB | 08-21 | 10 | 5 |
| VCB | 08-21 | 10 | 6 |
| VHM | 08-21 | 10 | 4 |

Cộng `priceZone` vào mẫu số (11 figure dùng được mỗi Analysis, 88 tổng): **42/88 = 47,7 %.**
Hơn một nửa số figure dùng được không được dẫn ở bất kỳ nhận định nào — và
`price_zone.ordinary_range_pct`, thứ mà `field_profile.py` gọi là *core evidence*, **không được
dẫn ở lượt nào trong 8**. Không Analysis nào dẫn một field `refused`:

```sql
-- cited field ids không nằm trong tập usable của cùng Analysis
select c.field_id, count(*) from cited c
where not exists (select 1 from usable u where u.id=c.id and u.field_id=c.field_id) group by 1;
-- (0 rows)
```

Bất biến sở hữu figure (`alpha/production.py`) giữ đúng: **0 vi phạm**.

Field được dẫn nhiều nhất — cả 4 field đầu đều 8/8 lượt:

| fieldId | lượt dẫn |
|---|---|
| `foreign_flow_pressure.net_value_over_adtv` | 8 |
| `factor_percentiles.roe_percentile` | 8 |
| `indicator_pack.rsi_14` | 8 |
| `drawdown_stats.current_drawdown_pct` | 8 |
| `foreign_flow_pressure.persistence_run_days` | 7 |
| `volatility_regime.gk_variance_robust_z` | 2 |
| `company_profile.foreign_room_pct` | 1 |

Bảy field đỡ toàn bộ 8 Analysis, bốn trong số đó ở mọi lượt. Đây là mốc thứ hai cho Phase 5: nếu
vòng lặp không mở rộng được tập field được dẫn, nó chỉ tốn tiền.

## 6. Token và giá thật mỗi Analysis

```sql
select count(*), sum(l.input_tokens), sum(l.output_tokens), sum(l.reasoning_tokens),
       sum(l.actual_micro_usd)/1e6, round(avg(l.input_tokens)), round(avg(l.output_tokens))
from llm_call_usage l join analysis_run r on r.id = l.owner_id::bigint
where l.owner_type='analysis_run' and r.status='ready';
```

| | giá trị |
|---|---|
| lời gọi | 8 (đúng 1 mỗi Analysis — one-shot) |
| input token | 40 345 · **avg 5 043** |
| cached read token | 0 (`llm_prompt_cache_control_enabled=false`) |
| output token | 3 934 · **avg 492** |
| reasoning token | 2 118 · avg 265 |
| chi phí | $0,026227 · **avg $0,003278/Analysis** |
| ledger `usage_unknown` | 0/8 |

Giá theo `LLM_PRICING_VERSION=2026-08-dev-cliproxy` ($0,5/$1,0 per Mtok batch in/out) — **giá lane
dev, không phải giá production**. Con số so sánh của Phase 5 là **token**, không phải USD.

Ba mốc phụ, để Phase 4 biết mình làm hồi quy cái gì:

| | giá trị |
|---|---|
| thời lượng run `ready` | 14,3–33,7 s · trung vị ~15,6 s |
| attempts | 1/1 ở cả 8 |
| payload | 17,0–18,4 KB |

## Cái Phase 2–5 phải mang theo từ đây

1. **`refused` 41,6 %, nhưng 86 % là cấu trúc.** Phase 4 không được bán mình bằng "đi quanh
   refusal". Giá trị đo được là **16 field chưa bao giờ tới được Analysis**.
2. **Trục news rỗng 16/16 và fundamental 8/41.** Hai trục này là chỗ prose thay số, và đó là lý
   do Phase 7 (cổng kiểm số) không phải phòng xa.
3. **47,7 % figure dùng được không được dẫn**, kể cả `price_zone.ordinary_range_pct` — 0/8 lượt
   dẫn tới *core evidence*. Bar của Phase 5 là tỷ lệ này, cạnh substitution rate.
4. **1 call · 5 043 in · 492 out · ~15,6 s một Analysis.** Trần lane $10 với cohort ≤30 mã: một
   vòng lặp 4 round sẽ nhân input lên ~4× trước cache — đúng chỗ
   `llm_prompt_cache_control_enabled` trở thành việc trước-prod, như plan đã ghi.
5. **Chỉ 4/36 mã issue từng xuất hiện.** 32 nhánh còn lại chưa có bằng chứng nào là chúng xảy ra
   trên Universe thật. Đừng thiết kế vòng lặp quanh 36 nhánh; thiết kế quanh 4 mã đã đo, cộng
   đường tổng quát cho phần còn lại.

## Câu chưa trả lời

1. Ba Trading Day còn thiếu để đóng cửa 5 phiên — chờ phiên thật, hay chấp nhận mốc 2 phiên và
   đi tiếp? (Mốc 2 phiên đã đủ để trả lời cửa của Phase 1: `refused` xảy ra nhiều.)
2. Cohort chỉ 5 mã (BID · FPT · STB · VCB · VHM), toàn large-cap. Refusal `insufficient_cross_section`
   và các mã issue liên quan thanh khoản gần như chắc chắn có tần suất khác trên mid/small-cap.
   Có nên thêm mã vào Watchlist nội bộ trước khi Phase 4 chốt ngưỡng?
