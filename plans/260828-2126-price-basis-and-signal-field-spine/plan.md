---
title: "Price Basis And Signal Field Spine"
description: "Chuyển 30 Signal Field khỏi giá FiinQuant sang bar_daily của vnstock, đổi luật price basis cho đúng, rồi xoá nguồn vi phạm điều khoản."
status: done
priority: P1
effort: "9 phase"
tags: [signals, price-basis, compliance, vnstock, api]
created: 2026-08-28
relatedTo: [260826-2158-study-artifact-canvas]
blocks: [260827-2325-evidence-led-chat-surface]
---

# Plan: Price Basis And Signal Field Spine

Kế thừa hai mục còn nợ của `plans/260826-2158-study-artifact-canvas/` — **08b**
(luật price basis + xoá dòng fiinquant) và **09b** (Signal Field `earnings.*`).
Hai mục đó ở lại bảng phase của plan cũ như con trỏ; **đặc tả sống ở đây**.

> **Bản này là bản sau red-team (2026-08-28).** Bốn reviewer đều trả BLOCKED,
> tổng 6 Critical. Bản đầu đã sai ở bốn chỗ nền và chúng được sửa tại chỗ, không
> giấu — xem §Red Team Review cuối file. Đọc mục "Đo lại" bên dưới với đúng giới
> hạn của từng phép đo: mỗi số đều kèm mẫu và truy vấn.

## Vì sao có plan này

`get_field` — tool lane chat dùng để trả số — phục vụ 30 Signal Field. Cả 30 đọc
`signals/bars.py`, và `bars.py` chỉ nhận cửa sổ có `price_basis = raw`. Dòng
`raw` duy nhất trong store là **36.528 dòng FiinQuant**, nguồn vi phạm điều khoản
SaaS, đã bị rip khỏi code từ 2026-08-25. vnstock có gói thương mại hợp lệ
(user xác nhận 2026-08-28) nên nó là đích đến đúng.

Hai lý do cộng dồn, đều đo được:

1. **Compliance** — hôm nay hệ thống trả số cho người dùng từ nguồn không được
   phép phân phối.
2. **Nguồn đã chết** — `provider_snapshots` **không còn writer nào** trong `src/`
   (grep `ProviderSnapshot(`, `insert(ProviderSnapshot`, `add(ProviderSnapshot`:
   chỉ còn định nghĩa model). Lịch đứng ở 2026-08-24 vĩnh viễn. `bar_daily` thì
   tươi tới 2026-08-27, 1.522 mã, 15 năm sâu.

## Đo lại 2026-08-28 — hai câu của red-team cũ bị đảo, một câu thì không

Red-team 2026-08-27 ghi ba phát hiện vào `phase-08:140-151`, đo trong session
Postgres `TimeZone = UTC`.

| Claim cũ | Đo lại | Kết luận |
|---|---|---|
| `latest_trading_day` "báo sớm một ngày, báo được cả Chủ nhật" | chạy thật trong container: `-> 2026-08-24 Monday`; 8 phiên trước đều ngày thường | **Đảo.** `providers/normalize.py:23-36 day_in_vn` đã `astimezone(VN_TZ)` |
| "17/80 dòng fiinquant rơi vào cuối tuần" | đếm theo `AT TIME ZONE 'Asia/Ho_Chi_Minh'`: **0** dòng cuối tuần trên `market`, `valuation`, `reference`, mọi source | **Đảo.** 19,6% ở phép đếm UTC ≈ đúng 1/5: thứ Hai rơi về Chủ nhật |
| "khớp cùng ngày 3/80" | **30 mã declared**, từ 2026-05-01, join theo local date: **1.367/2.256 = 60,59%**, 20/30 mã có lệch | **KHÔNG đảo.** Con số cũ sai, nhưng kết luận "hai nguồn lệch nhau" thì đúng |

**Lưu ý về phép đo thứ ba** — đây là chỗ bản đầu của plan này sai. Bản đầu đo
**một mã (STB), 80/80 khớp tuyệt đối**, rồi kết luận "giá đã điều chỉnh bằng đúng
giá công bố ở phiên gần đây". STB là ngoại lệ: 10/30 mã khớp hoàn toàn, còn
`SSI 5/80` (lệch tối đa 20,1%), `VHM 12/80` (51,9%), `MBB 9/80` (19,9%),
`BID 5/80` (7,5%). Toàn bộ Phase 06 của bản đầu dựng trên kết luận sai đó.

```sql
WITH f AS (SELECT symbol,(effective_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date d,
                  (payload->>'last_price')::numeric px
           FROM provider_snapshots WHERE source='fiinquant' AND capability='market'
             AND (effective_at AT TIME ZONE 'Asia/Ho_Chi_Minh')::date>='2026-05-01')
SELECT count(*), count(*) FILTER (WHERE b.close=f.px)
FROM f JOIN bar_daily b ON b.symbol=f.symbol AND b.trading_day=f.d AND b.series='equity';
```

## Bốn thứ hỏng, đo được

**1. Lịch giao dịch đứng yên.** Đã nêu trên. `bar_daily` là nguồn thay.

**2. Hai nhãn basis đều đúng, và lệch nhau thật.** So toàn vùng chồng lấn:

| Năm | Cặp so | Khớp tuyệt đối | Lệch tối đa |
|---|---|---|---|
| 2021 | 2.860 | 3,5 % | **68,5 %** |
| 2023 | 6.972 | 7,1 % | 62,1 % |
| 2025 | 6.959 | 9,3 % | 51,9 % |
| 2026 | 4.412 | 41,9 % | 51,9 % |

Chữ ký adjustment: hệ số tích luỹ ngược, phiên cũ lệch nhiều hơn phiên mới.

**3. `bars.py` tự điều chỉnh corporate action từ input raw** (`bars.py:914-1002`
`_factors`), và `Bar.raw_close` (`bars.py:295-305`) chia ngược hệ số ra. "Field
cần adjusted" thật ra là "field cần **input raw** để gateway tự adjust". Đổ
`adjusted_at_source` vào mà không tắt máy đó = điều chỉnh hai lần, sai **im lặng**.

**4. `bar_daily` chưa có đường vào `bars.py`.** Chỉ `studies/reads_daily.py:103`
và `studies/earnings_dislocation.py:580,617` đọc nó. Zero hit dưới `signals/`.

## Hai cổng basis, không phải một

Bản đầu chỉ biết một. Có **hai**, và cả hai đều từ chối cửa sổ toàn
`adjusted_at_source`:

| Cổng | Vị trí | Gọi từ | Chặn cái gì |
|---|---|---|---|
| `_basis_of` | `bars.py:814-826` | `bars.py:684`, khi `projection is PRICE` | toàn bộ cửa sổ → 20 field PRICE |
| `_basis_of_the_pair` | `price_band.py:500-518` | `price_band.py:431` trong `measure_band` | phán quyết band từng phiên |

Cổng thứ hai nguy hiểm hơn vì nó **không** trả refusal lên trên: nó đặt
`LimitLock.INDETERMINATE`, khiến `Bar.limit_locked` là `False` cho mọi bar,
`BarFrame.without_limit_locks()` (`bars.py:322-333`) không loại gì, và baseline
volatility tính trên cửa sổ còn nguyên phiên trần/sàn `H=L=O=C` — đúng cái
docstring nói "none may skip". Kèm theo, `UNEXPLAINED_PRICE_GAP` (`bars.py:879`)
trở nên **bất khả đạt** vì nó nằm sau `PRICE_MOVE_EXCEEDS_BAND` (`price_band.py:451`).

**Luật mới phải viết ra tường minh, ở Phase 03:** cửa sổ toàn
`adjusted_at_source` **được phục vụ** trên projection PRICE khi máy `_factors` đã
tắt; cửa sổ trộn hai basis vẫn là `MIXED_PRICE_BASIS`; `UNADJUSTABLE_PRICE_BASIS`
được thu hẹp lại chứ không giữ nguyên nghĩa cũ.

## Hai quyết định đã chốt với user 2026-08-28

1. **Thu hẹp có danh, suy ra cái suy được.** `vnstock_daily.py:89` chỉ trả
   `time, open, high, low, close, volume`. Suy `traded_value = close × volume`
   (đúng điều `vnstock_daily.py:33-34` bảo caller làm) để cứu ba field liquidity.
   Bảy field không còn nguồn nhận refusal có tên.
2. **`band_pressure` tự tính band từ luật sàn.** Quyết định giữ; **cách làm đổi**
   vì tiền đề của nó (60,59%, không phải 100%) đã sai. Phép thử quyết định giờ là
   **lưới bước giá**, không phải "vắng ex-date" — xem Phase 06.

## 30 Signal Field sau khi chuyển nguồn

| Nhóm | Số | Projection | Sau plan |
|---|---|---|---|
| return · drawdown · volatility · price_zone · risk_adjusted · mean-reversion · momentum · trend · RSI/MACD/Bollinger | 17 | PRICE | ✅ thuần OHLCV |
| `liquidity_profile.{adtv_vnd, amihud_illiq, adtv_percentile}` | 3 | **PRICE** | ✅ qua `traded_value` suy diễn |
| `liquidity_profile.adtv_shares` | 1 | VOLUME | ✅ chỉ đọc `volume` |
| `factor_percentiles.roe_percentile` | 1 | VOLUME | ✅ không chạm giá, đọc BCTC |
| `band_pressure.limit_days_in_window` | 1 | PRICE | ⚠️ chỉ quyết được ở phiên trên lưới bước giá (~93% HOSE); UPCOM **không bao giờ** |
| `factor_percentiles.{earnings_yield, book_yield, size}_percentile` | 3 | — | ⛔ `market_cap_absent` |
| `foreign_flow_pressure.*` | 3 | — | ⛔ `foreign_flow_not_stored` |
| `company_profile.foreign_room_pct` | 1 | — | ⛔ `foreign_room_not_stored` |
| `relative_strength.beta_vs_market_index` | 1 | — | ⛔ giữ `UNAVAILABLE` — estimator chưa viết (`cross_sectional.py:316-325`) |
| **Tổng** | **30** | 20 PRICE · 2 VOLUME | **22 sống · 8 từ chối** |

`liquidity_profile.adtv_vnd`, `amihud_illiq`, `adtv_percentile` **phải ở PRICE**,
không phải VOLUME: sau Phase 05 chúng làm số học trên `close`, và
`WindowHealth.adtv` chỉ được tính khi `projection is PRICE`
(`bars.py:757-765`) — đẩy `adtv_percentile` sang VOLUME là khoá nó vào
`RANKING_UNAVAILABLE` vĩnh viễn.

**Không thêm mã refusal mới.** Bảy field mất nguồn dùng ba mã **đã có**:
`MARKET_CAP_ABSENT` (`issues.py:232`), `FOREIGN_FLOW_NOT_STORED` (`:183`),
`FOREIGN_ROOM_NOT_STORED` (`:190`). CLAUDE.md đòi "mã refusal phải trỏ đúng input
thiếu"; một mã `source_retired` đặt tên cho *chuỗi cung*, không cho input, và sẽ
thành thùng rác. Nếu cần diễn đạt tính vĩnh viễn thì đó là **thuộc tính của
declaration** (kiểu `requires_foreign_share_flow`), không phải mã refusal cạnh tranh.

## Trạng thái & phases

| # | Phase | Lớp | Phụ thuộc | Trạng thái |
|---|---|---|---|---|
| 01 | [Mở freeze và chốt nền](./phase-01-green-baseline.md) | docs + web | — | **done** |
| 02 | [Lịch giao dịch chuyển sang bar_daily](./phase-02-trading-day-on-bar-daily.md) | api | 01 | **done** |
| 03 | [Cầu bar_daily → bars.py + luật basis mới](./phase-03-bar-daily-into-bars.md) | api | 02 | **done** |
| 04 | [Projection cho 30 field + refusal đúng input](./phase-04-basis-law-and-retired-source.md) | api + web | 03 | **done** |
| 05 | [traded_value suy diễn — ba field liquidity](./phase-05-derived-traded-value.md) | api | 04 | **done** |
| 06 | [band_pressure trên lưới bước giá](./phase-06-band-from-exchange-rule.md) | api | 05 | **done** |
| 07 | [MARKET_INDEX từ bar_daily series=index](./phase-07-index-series-from-bar-daily.md) | api | 03 | **done** |
| 08 | [Xoá FiinQuant và nghiệm thu](./phase-08-retire-fiinquant.md) | api + db | 04, 05, 06 | **done** |
| 09 | [Signal Field earnings.*](./phase-09-earnings-signal-fields.md) | api | 01 | **done** |

**Đường tới hạn: `01 → 02 → 03 → 04 → 05 → 06 → 08`.**

Hai nhánh chạy song song thật:
- **09** chỉ cần 01 — nó đọc `financial_statement_line`, không chạm
  `provider_snapshots`, `bars.py`, hay price basis. Không có lý do kỹ thuật nào
  bắt nó chờ phép xoá.
- **07** chỉ cần 03, và **không còn chặn 08** (xem R5 đã sửa).

**04 → 05 → 06 phải nối tiếp, không song song.** Bản đầu ghi "bốn phase giữa chạy
song song được — khác owner file"; sai. Cả ba cùng sửa `signals/bars.py`,
`signals/registry.py` và `signals/market_behavior.py`. Chạy song song là để ba ý
đồ khác nhau tranh nhau cùng một vùng 500 dòng của file giữ mọi con số sản phẩm —
và golden test của R1 chỉ tồn tại trên nhánh 03.

## Biên với hai plan khác

**`260827-2325-evidence-led-chat-surface` bị plan này chặn.** Phase 03 của nó
cũng định sửa `trading_day.py` và dựa trên ba claim red-team cũ. Đã đánh
`blockedBy`, sửa R6, treo banner "phải viết lại" lên phase file của nó.

**`260826-2158-study-artifact-canvas` CÓ bị đụng — ba điểm tiếp xúc.** Bản đầu
ghi "không đụng"; sai:

1. `studies/reads_fundamental.py:37,107-115` đọc `ProviderSnapshot` và gọi
   `main_source(Capability.FUNDAMENTAL)` — bản đồ ownership mà Phase 08 viết lại.
2. Năm module `studies/*` import `SignalIssue` từ `signals/issues.py`;
   `studies/entry_condition_review.py:258` rẽ nhánh trên `MIXED_PRICE_BASIS`.
3. Phase 04 sửa `apps/web/src/lib/signal-issues.ts`, surface Signal Desk đọc nó.

**Hệ quả:** Phase 04 và Phase 08 phải chạy `tests/studies/` trong bước verify.

`PROMPT_VERSION` không bump. Vòng tool của `loop.py` không đổi.

## Nguyên tắc xuyên suốt

- **Không có nguồn thì từ chối có tên, không bao giờ suy số.** Mã refusal trỏ vào
  **input thiếu**, không vào nhà cung cấp.
- **Suy diễn phải khai là suy diễn**, và phải trả `None` khi không suy được —
  không bao giờ trả `0`.
- **Mọi lệnh chạm DB phải ghim host tường minh.** Xem R6.
- Trước mọi bulk delete: `pg_dump` vào `backups/`, xác minh bằng **số dòng cụ
  thể**, không commit.

## Rủi ro cấp plan

- **R1 — điều chỉnh hai lần.** `bars.py:914-1002` tự adjust từ raw. Quên tắt =
  mọi số lịch sử sai im lặng. Cổng: golden test trên mã có corporate action.
- **R2 — lịch lại chết.** `backfill_daily.py` **không có caller nào**. Phase 02
  phải giải. *Tín hiệu sớm không dùng được `market_generation`* — hàm đó có **0
  caller** trong `src/`; phải chọn tín hiệu khác, ví dụ tuổi của
  `max(bar_daily.observed_at)`.
- **R3 — xoá là một chiều.** 71.773 dòng FiinQuant không lấy lại được.
- **R4 — `_session_low` hỏng hai lớp.** `corporate_actions.py:720` order theo
  `ProviderSnapshot.written_at` (cột không tồn tại → `AttributeError`), **và**
  `:709-710` dựng cửa sổ ngày bằng **UTC** trong khi phiên đóng dấu nửa đêm VN.
  Vá mỗi cột tên = thay lỗi ồn bằng lỗi câm trả `None` cho mọi phiên.
- **R5 — ~~MARKET_INDEX mất nguồn~~ → SAI, đã sửa.** `provider_snapshots` có
  **0 dòng** capability `market_index` ở mọi source. Không có chuỗi chỉ số nào để
  mất. Phase 07 vì thế **không chặn** Phase 08. Nếu vẫn làm 07 thì nó phải tranh
  luận thẳng với `providers/contracts.py:172-179`, chỗ ghi rõ vì sao vnstock
  **cố ý** không được làm cover cho index.
- **R6 — hai Postgres cùng tên `stockmassive`.** Brew ở `127.0.0.1:5432` có
  `provider_snapshots` **rỗng**; DB thật ở container `stockmassive-db-1`. Lỗi này
  **đã xảy ra rồi**: `backups/pre-rename-signal-desk-hostdb-260828.sql.gz` nặng
  **46 KB** nằm cạnh `pre-rename-signal-desk-260828.sql.gz` **17 MB** cùng ngày.
  Một backup rỗng trước một phép xoá một chiều là mất dữ liệu vĩnh viễn.
- **R7 — `check_price_claim` mất 2/3 nhánh.** `price_check.py:337,411` trả
  `unverified` khi basis không phải RAW. Sau Phase 03 không còn RAW, nên nhánh
  BAND và STORE chết vĩnh viễn, chỉ còn TICK. Đây là **control an ninh** kiểm giá
  từ nội dung web không tin cậy, bị tắt như tác dụng phụ. Phải có quyết định ghi
  ra, không phải một dòng ghi chú.

## Success Criteria

Đo 2026-08-29 trên store thật, sau phép xoá.

- [x] 22 Signal Field trả số thật từ `bar_daily`, 8 field trả refusal đúng input —
      **vượt**: 23/30 field gốc trả số (`foreign_room_pct` sống nhờ 220 dòng
      reference vnstock, plan dự là chết), cộng ba field `earnings.*` mới ⇒ VCB
      **25/33**, VNM và MWG **26/33**
- [x] Cả **20** field PRICE trả số — không chỉ nhóm VOLUME
- [x] Luật basis mới viết thành câu trong `bars.py` và `price_band.py`, có test
- [x] `limit_lock_days > 0` trên fixture có phiên trần — cổng thứ hai không bị tắt câm
- [x] 0 dòng `source = 'fiinquant'` trong `provider_snapshots` **của DB container**
- [x] Backup đã restore thử và đếm khớp 106.007 / 71.773 trước khi xoá
- [x] Golden test: 17 field OHLCV không đổi quá dung sai đã khai
- [x] `make test` (**1423 passed**) + bốn cổng web xanh, gồm `tests/studies/`

## Câu hỏi chưa giải quyết — trạng thái 2026-08-29

1. **Ai chạy `backfill_daily`?** — **đã trả 2026-08-29.** Đăng ký vào seam
   scheduler có sẵn (`core/scheduler.py`, vốn tự ghi "add it here"), ba scope nối
   tiếp 16:30 giờ VN, `index` đi đầu vì VNINDEX định nghĩa Trading Day calendar.
   **Mặc định tắt** (`BACKFILL_DAILY_SCHEDULED`) vì `scheduler_enabled` mặc định
   `True` — một job vô điều kiện sẽ tự gọi provider ngoài trên mọi máy dựng stack.
   Kèm hai việc phát hiện khi làm: job **bỏ qua arbiter hạn mức hoàn toàn**, nay
   lấy slot qua `QuotaLane.BACKFILL` đã có sẵn; và `spine_freshness` không có
   caller nào ngoài `main()` của chính job, nay API startup cảnh báo khi stale.
   Chi tiết: `plans/reports/proposal-260829-0034-backfill-schedule-and-band-check.md`.
2. **`market_cap_vnd` có dựng lại không?** — **đã trả lời bằng phép đo, không cần
   quyết.** Nguồn cũ null `market_cap_vnd` ở 99,48% dòng, nên ba field
   `factor_percentiles` gần như đã chết từ trước; xoá nguồn không đổi gì cho chúng.
   Ba field đó trả `market_cap_absent` trên store thật, đúng như khai. Dựng lại từ
   `charter_capital` là **feature mới**, không phải nợ của plan này.
3. **Dung sai golden test cho 17 field OHLCV** — **đã trả lời.** Bằng **0**, và
   không cần dung sai: `test_every_ratio_a_field_reads_survives_the_window_being_rescaled`
   phục vụ cùng cửa sổ nhân 2,5 và đòi **cùng một số** ra
   (`pytest.approx` mặc định). Số học của cả 17 field là tỷ số nên hằng số chia
   hết. Không có chỗ nào cần chấp nhận lệch do provider làm tròn.
4. **R7 — `check_price_claim`** — **đã trả 2026-08-29**, và phép đo cũ sai một
   nửa: **chỉ nhánh BAND chết**, không phải hai. Nhánh STORE vẫn chạy (`:461` đòi
   cả `rescaled_since` nên chỉ suy giảm quanh phiên có rescaling); TICK không dính.
   Sửa bằng **hai cổng giá** thay cổng nhãn `RAW`:
   `price_band.off_tick_grid(exchange, anchor)` — giá sàn công bố luôn nằm trên
   lưới bước giá — **và** ex-date giữa phiên neo và phiên đích. Không dùng cổng thứ
   hai một mình: bảng corporate action phủ một phần nhỏ thị trường nên "không có
   dòng" đọc thành "không có ex-date". Nghiệm thu trên store thật: 30/30 mã
   declared `within_band` cho giá đúng (trước 0/30 `unverified`) và `exceeds_band`
   cho giá bịa ±9% / −12% / ×10.
5. **Lịch định nghĩa trên tập nào?** — **đã trả lời, Phase 02 chốt.**
   `series='index'` (VNINDEX). Đo xác nhận: 3.991 phiên liên tục 2010-08-31 →
   2026-08-27, một mã, một source, một basis. Không dùng hợp của 1.522 mã.

**Còn mở: không câu nào.** Năm câu đều đã trả — ba bằng phép đo trong plan, hai
bằng phần thi công 2026-08-29 ở trên. Plan đóng.

---

## Red Team Review

### Session — 2026-08-28

**Reviewer:** 4 (Security Adversary · Failure Mode Analyst · Assumption Destroyer
· Scope & Complexity Critic). Cả bốn trả **BLOCKED**.
**Findings:** 19 sau khi gộp trùng (6 Critical, 10 High, 3 Medium).
**Disposition:** 18 Accept, 1 Reject.

| # | Finding | Sev | Disposition | Áp vào |
|---|---|---|---|---|
| 1 | Luật `_basis_of` chưa bao giờ được viết thành bước → 20 field PRICE từ chối im lặng | Critical | Accept | Phase 03 |
| 2 | Cổng basis thứ hai `_basis_of_the_pair` không phase nào nhắc; tắt câm việc loại phiên trần/sàn | Critical | Accept | Phase 03, 06 |
| 3 | Phép đo "80/80" là một mã; toàn bộ 30 mã cho 60,59% | Critical | Accept | plan.md, Phase 06 |
| 4 | `net_revenue`/`net_margin` có **0 dòng** trong `financial_statement_line` | Critical | Accept | Phase 09 |
| 5 | Backup không ghim host; brew Postgres rỗng đã tạo dump 46 KB | Critical | Accept | Phase 08, R6 |
| 6 | Phase 01 xây trên lỗi đã hết; `plain()` không tồn tại, `plainLocale` đang sống | Critical | Accept | Phase 01 |
| 7 | Lịch thiếu lọc `series`; 846/1522 mã có dòng ngày mới nhất | High | Accept | Phase 02 |
| 8 | R5 sai — 0 dòng `market_index`; Phase 07 chặn 08 vô cớ | High | Accept | plan.md, Phase 07, 08 |
| 9 | Phase 05 suy diễn sai tầng — `_adtv_standing` đọc `SessionSnapshot` | High | Accept | Phase 05 |
| 10 | `close×volume` p95 20,4% / max 53%; 24,4% dòng `volume=0` → suy ra `0.0` phá refusal | High | Accept | Phase 05 |
| 11 | Phase 06 dựng lại máy đã có; UPCOM neo VWAP phiên trước | High | Accept | Phase 06 |
| 12 | Chuỗi corporate action cũng chết — `save()` 0 caller, 29/1522 mã | High | Accept | Phase 06 |
| 13 | Cổng đo của Phase 06 bất khả thi — FiinQuant 99,93% null band | High | Accept | Phase 06, 08 |
| 14 | `SOURCE_RETIRED` trùng 3 mã đã có, trái luật CLAUDE.md | High | Accept | plan.md, Phase 04 |
| 15 | Plan mở 7 surface freeze, amendment chỉ ở phase cuối | High | Accept | Phase 01 |
| 16 | "Chạy song song" sai — 04-07 cùng sửa `bars.py` | High | Accept | plan.md |
| 17 | `check_price_claim` mất vĩnh viễn nhánh BAND + STORE | High | Accept | R7, Phase 03 |
| 18 | Phase 08 bỏ sót 47 tham chiếu/11 file gồm `tests/conftest.py:28` | High | Accept | Phase 08 |
| 19 | vnstock licence cấm thương mại mọi tier | Critical | **Reject** | — |

**Rationale cho Reject #19.** Reviewer trích `LICENSE.md` trong
`vnstock-4.0.7.dist-info/licenses/` — điều khoản của **bản phân phối miễn phí qua
pip**. User xác nhận 2026-08-28 rằng vnstock **có gói thương mại**, với điều khoản
riêng không nằm trong artifact đã cài. Finding trích dẫn đúng một tài liệu sai
phạm vi. Memory dự án đã được sửa theo.

**Ba Medium đã gộp vào các mục trên:** `_session_low` còn lỗi UTC ngoài lỗi tên
cột (→ R4) · bảng projection phủ 24/30 field, thiếu `adtv_shares` (→ #1, bảng 30
field) · `registry_version()` là hash dẫn xuất, không bump tay (→ Phase 04, 09).

### Whole-Plan Consistency Sweep

Đã quét lại `plan.md` + 9 phase file sau khi áp finding. Đối chiếu:

- Bảng 30 field: tổng đúng 30, có `adtv_shares`, `roe_percentile` chuyển khỏi
  nhóm "thuần OHLCV" (nó đọc `FundamentalStanding`, `cross_sectional.py:491`).
- "21 field sống" → **22**, khớp bảng và Success Criteria.
- Mọi chỗ nói "13 field VOLUME" đã sửa: thực tế **2** field VOLUME.
- Mọi chỗ nói `source_retired` đã gỡ; thay bằng ba mã có sẵn.
- R5 sửa; Phase 07 gỡ khỏi `dependencies` của Phase 08; Phase 09 chuyển về
  `dependencies: [1]`.
- Claim "chạy song song" gỡ khỏi plan.md và khỏi mô tả đường tới hạn.
- Claim "không đụng plan Study" thay bằng ba điểm tiếp xúc có `file:line`.
- Ba số stale sửa: 168→174 file, "năm hàm công khai"→bốn, "2026-08-19 thiếu dòng
  STB"→dòng tồn tại (close 74.800, volume 4.934.700).

**Mâu thuẫn còn lại: 0.** Bốn câu hỏi mở ở trên là quyết định chờ người, không
phải mâu thuẫn trong plan.
