# Phase 08 — Spine dữ liệu market-wide (nhóm D, trả nợ)

Phụ thuộc 02 (khuôn ingest). **Viết lại 2026-08-27** sau khi đo code + DB +
provider: bản cũ có ba chỗ không thi công được, ghi ở "Vì sao bản cũ đổi".

Phase tách hai nửa. **08a (phase này)** dựng nguồn giá daily sạch trong một
bảng typed mới, không đụng serving. **08b (tách file, chưa mở)** là quyết định
đổi luật price basis của core rồi mới xoá dòng fiinquant — nó đổi con số 25
Signal Field báo ra, nên không đi kèm một backfill.

## Context — nợ đo được (2026-08-27, `provider_snapshots`)

| capability | source | basis | rows | syms | tới ngày |
|---|---|---|---|---|---|
| market | fiinquant | **raw** | 36.528 | 32 | 2026-08-23 |
| market | vnstock | adjusted_at_source | 31.160 | 28 | **2021-08-18** |
| valuation | fiinquant | — | 35.245 | 30 | 2026-08-24 |
| fundamental | vnstock | — | 2.854 | 1.343 | 2026-06-29 |
| reference | vnstock | — | 220 | 30 | 2026-08-24 |

`market_index` = 0 dòng. Provider đã tuyên bố vi phạm ToS, code đã rip, **dữ
liệu chưa**.

## Vì sao bản cũ đổi

1. **Ghi vnstock vào `provider_snapshots` capability MARKET rồi đọc bằng
   `signals/bars.py` không chạy.** `bars.py::_basis_of` (dòng 814-827): *"Only
   an all-`raw` window is served"* — window toàn `adjusted_at_source` trả
   `UNADJUSTABLE_PRICE_BASIS`. Và vnstock **không có tuỳ chọn giá chưa điều
   chỉnh** cho thị trường VN (probe bản đang cài: chỉ connector `fmp` có
   `adj_type`). Nên xoá fiinquant rồi thay bằng vnstock trong cùng bảng =
   mọi window bị từ chối, gãy 6 module signals + `alpha/envelope.py` + 25 field.
2. **Cổng verify "lệch >0,5% thì dừng" bất khả thi.** Hai bên khác basis
   (adjusted vs raw), lệch tích luỹ theo mọi cổ tức/chia tách 5 năm → luôn vượt
   ngưỡng, cổng không phân biệt "sai" với "khác basis". Thay bằng **so sánh
   return** (bất biến với adjust, trừ đúng phiên ex-date) + so giá tuyệt đối
   chỉ trên cửa sổ không có ex-date.
3. **`valuation` không nằm trong bản cũ** — mà đó là capability duy nhất **0
   dòng vnstock**. Phase 10 cần nó. Ghi vào 08b cùng quyết định basis, vì
   valuation fiinquant cũng đang là nguồn duy nhất.

Thêm hai số đo đổi cách chia việc:

- **Provider chặn ~2.000 dòng mỗi call, lấp ngược từ `end`.** Đo: STB và
  VNINDEX cùng trả 1.997 dòng bắt đầu 2018-08-29 khi hỏi từ 2016-01-01; hỏi
  `end=2018-08-28` trả tiếp 1.995 dòng từ 2010-08-31. Nên "full depth 8 năm"
  = **1 call**; sâu hơn 2018 = call thứ hai. Không phải 1 call/mã cho mọi độ
  sâu như bản cũ ghi.
- **Số mã thật: 1.523 STOCK đang niêm yết** (HSX 405 · HNX 299 · UPCOM 819) +
  228 DELISTED. Bản cũ ghi ~1.700 vì đếm `all_symbols()` (1.751) gồm cả bond,
  CW, ETF, future.

## Requirements

### 1. Bảng `bar_daily` (typed, mới)

Không ghi vào `provider_snapshots`: bảng đó là snapshot JSON một dòng/mã/ngày
với ngữ nghĩa basis gắn vào ownership contract thời FiinQuant; 1.523 mã × 400
phiên thành ~600k dòng JSON, và mỗi lần đọc phải đi qua luật RAW-only. Bảng
typed đi đúng khuôn `bar_intraday_15m` mà phase 02 đã chứng minh.

Cột: `symbol` + `trading_day` (PK) · `series` (`equity` | `index`) ·
`open/high/low/close` `Numeric(20,4)` · `volume` `BigInteger` · `price_basis`
`String(20)` · `source` `String(32)` · `observed_at`.

- `price_basis` là **cột, không hằng số** — hôm nay mọi dòng là
  `adjusted_at_source`, và ghi ra để không lặp lại chuyện đọc một cửa sổ mà
  không biết giá của nó nghĩa gì. Đây cũng là chỗ 08b đọc để phân loại.
- `series` thay vì bảng riêng cho index: VNINDEX cùng hình dạng, và screener
  cần relative-return đọc cùng một đường. Khác `provider_snapshots`, nơi
  MARKET_INDEX là capability riêng vì Trading Day suy từ MARKET.
- Giá: **equity ×1000** (provider trả nghìn VND — STB 74,5), **index không
  scale** (1.821 điểm). Scale một lần ở ingest, cùng luật phase 02.
- Index: `(symbol, trading_day DESC)` cho một mã; `(trading_day, series)` cho
  ảnh cắt ngang market-wide của screener.

### 2. Fetch + normalize

`src/stocks/providers/vnstock_daily.py`:
- `fetch_daily(symbol, *, end, sessions)` qua `Quote(symbol, source="VCI")
  .history(start, end, interval="1D")`, bọc `core/vnstock_wrapper.
  safe_vnstock_call`.
- Kiểm cột trả về `("time","open","high","low","close","volume")` — thiếu thì
  `DailyIngestError` nêu tên cột nhận được, khuôn `intraday/ingest.py::
  _rows_from`. **Không có cột giá trị giao dịch**; amount suy ra
  `close × volume` ở chỗ dùng, không ghi thành cột.
- `ensure_daily_bars(session, symbol, *, sessions, series)` idempotent: upsert
  `ON CONFLICT (symbol, trading_day) DO UPDATE`, dedup trong values **trước**
  khi dựng statement (`CardinalityViolation` abort cả transaction — phase 03 đã
  trả giá cho bài này).
- Độ sâu > 2.000 phiên: gọi lại với `end = min(trading_day đã nhận) - 1 ngày`,
  dừng khi call trả rỗng hoặc đủ `sessions`.

### 3. Job backfill resumable

`src/stocks/backfill_daily.py` — CLI `python -m src.stocks.backfill_daily
--scope declared|market|index [--sessions N]`.

**Không có bảng checkpoint.** Tiến độ suy từ chính store: mã đã có
`count(trading_day) ≥ sessions` và `max(trading_day)` ở phiên gần nhất thì bỏ
qua. Upsert idempotent + điều kiện bỏ qua = resume miễn phí, và không thêm một
bảng phải giữ đồng bộ với sự thật nằm ngay cạnh nó.

- `declared`: 30 mã, `sessions=2000` (~8 năm, 1 call/mã).
- `index`: VNINDEX, `series="index"`, `sessions=2000`.
- `market`: 1.523 mã listed, `sessions=400` (52w + đệm cho phase 10).
- Log mỗi mã một dòng: symbol · rows_written · sessions_stored · lỗi (nếu có,
  **không** dừng cả job — một mã hỏng không được chặn 1.522 mã còn lại).

### 4. Roster + ICB

Ghi vào `src/stocks/listing_roster.py` (đã có reader `ListingRosterStore`):
`refresh_roster(session)`.
- Nguồn: `Listing(source="VCI").symbols_by_exchange()` — một call trả
  `symbol, exchange, type, icb_code2, organ_name`. Lọc `type == "STOCK"`.
- Map sàn: `HSX → HOSE` (provider gọi HSX, bảng dùng HOSE) · `HNX` · `UPCOM` ·
  `DELISTED → is_listed=False` giữ dòng, không xoá (model đã ghi lý do).
- `icb_name`: join `industries_icb()` (177 dòng) trên `icb_code == icb_code2`
  ở `level == 2`. Best-effort — `icb_code`/`icb_name` nullable là dòng bình
  thường, không phải dòng hỏng.

### 5. Universe hai nửa

`src/stocks/universe.py`: giữ chữ ký `build_universe(session, settings=None)`.
Thêm `Universe.market` (roster listed) cạnh 30 mã declared. `get_field` giữ
**luật declared-only** cho field khai vậy — test khẳng định một mã chỉ có ở
nửa `market` vẫn bị từ chối đúng mã refusal cũ.

## Phát hiện khi nghiệm thu 08a — dòng fiinquant lệch một ngày

Đối chiếu `bar_daily` (vnstock, mới) với `provider_snapshots` fiinquant trên
STB từ 2026-05-01: khớp **cùng ngày 3/80**, khớp khi dòng fiinquant lệch **sớm
một ngày 80/80**. Kiểm lại trên ACB · CTG · FPT · GAS · GVR · HDB: cùng một
hướng. Và **17/80 dòng fiinquant rơi vào cuối tuần** — ngày không có phiên.

`bar_daily` khớp đúng số provider trả live (STB 2026-08-27 close 73.500,
08-26 74.600) và không có dòng cuối tuần, nên lệch nằm ở dữ liệu cũ, không ở
ingest mới.

> **ĐÃ ĐẢO 2026-08-28.** Ba đoạn ngay trên và ba gạch đầu dòng ngay dưới dựa
> trên phép đo chạy trong session Postgres `TimeZone = UTC`, và cả ba đều sai.
> Đo lại: `latest_trading_day()` trả `2026-08-24 Monday` (đúng, `day_in_vn` đã
> `astimezone(VN_TZ)`); **0** dòng cuối tuần trên mọi source khi đếm theo
> `Asia/Ho_Chi_Minh`; STB 80 phiên khớp `bar_daily` **80/80 tuyệt đối, 0,000%**.
> Lỗi thật là `provider_snapshots` không còn writer nên lịch đứng ở 2026-08-24.
> Đặc tả thay thế: `plans/260828-2126-price-basis-and-signal-field-spine/`.

Hệ quả cho 08b, cần quyết trước khi xoá:

- `trading_day.latest_trading_day` = `date(max(effective_at))` trên capability
  MARKET → **báo sớm một ngày, và báo được cả ngày Chủ nhật**.
- Cửa sổ "N phiên đã đóng gần nhất" của Signal Field bị dịch một phiên; join
  theo `effective_at` giữa MARKET và các capability khác lệch theo.
- Cổng verify "so vnstock với fiinquant" của bản plan cũ vì thế còn sai một
  lần nữa: lệch ngày cộng lệch basis.

Đây là khiếm khuyết của mặt phẳng serving đang freeze, phát hiện 2026-08-27,
**chưa sửa** — sửa nó là đổi ngữ nghĩa `effective_at` của dữ liệu đã ghi, phải
đi cùng quyết định basis ở 08b.

## Không thuộc phase này (chuyển 08b)

- **DELETE 71.773 dòng fiinquant.** Xoá bây giờ = signals mất nguồn `raw` duy
  nhất → mọi window `UNADJUSTABLE_PRICE_BASIS`. Phải quyết luật basis trước.
- **Backfill `valuation` từ vnstock.**
- **Acceptance #6 của plan.md** vì thế **chưa đạt sau 08a** — nêu thẳng, không
  đánh dấu done.

08b sẽ mang: bảng phân loại 25 Signal Field × basis nó thật sự cần (return /
drawdown / RSI đúng với adjusted; band / limit-lock / corporate-action cần
raw) → quyết flip `_basis_of` theo nhóm, hoặc giữ raw cho nhóm cần và bỏ field
không có nguồn. Rồi verify bằng return + xoá.

## Kết quả nghiệm thu 08a (2026-08-27)

- `make test` (host): **1118 pass** (baseline 1060, +58 test offline).
- Alembic: một head `d4a71c9e5b82`, đã apply; `make lint` xanh sau khi vá target
  hardcode `python` (nay dùng `$(PYTHON)` nên chạy trong `.venv`).
- Roster: **1.523 mã STOCK listed**, 0 mã thiếu ICB, 228 mã DELISTED giữ dòng.
- `declared`: 30/30 mã, 87.444 dòng, sâu tới 2010-08-31 (2 call/mã — paging
  đúng như đo).
- `index`: VNINDEX **3.991 phiên** từ 2010-08-31 (15 năm, vượt mốc ≥5 năm).
- `market` sau ba lượt: **1.522/1.523 mã · 809.085 dòng equity · 189 MB**.
  Coverage ≥380 phiên: **1.476 = 96,9%** — đạt mốc 95%. Trong 46 mã ngắn,
  **41 mã lên sàn từ 2025** (DDB 2025-01-15 · VPL 2025-05-13 · F88 2025-08-08…),
  tức mới thật, không phải lỗ dữ liệu.
- Lỗi mỗi lượt 25-53 mã nhưng **tập mã khác nhau mỗi lượt**, và retry tay
  (VSC · SAM · OGC) OK ngay → transient/rate-limit, không phải lỗi mã. Job
  idempotent nên vét bằng cách chạy lại.

### Sửa sau nghiệm thu: điều kiện bỏ qua đọc `observed_at`, không đọc phiên cuối

`is_deep_enough` ban đầu so phiên cuối của mã với phiên mới nhất toàn sàn. Đo
2026-08-27: **677/1.522 mã không có phiên nào hôm nay** (303 mã không có quá
một tuần) — sàn UPCOM thanh khoản mỏng. Nhóm đó **không bao giờ** thoả điều
kiện, nên mỗi lượt market-wide gọi lại provider cho tất cả: lượt đo được
711 mã thử / 812 bỏ qua.

Sửa: currency là **"đã hỏi provider sau phiên mới nhất chưa"** (`observed_at`),
không phải "mã có giao dịch hôm nay chưa". Sau sửa: **48 thử / 1.475 bỏ qua**,
vẫn viết đủ 7.347 dòng cho 48 mã thật sự còn thiếu. Đánh đổi đã ghi trong
docstring: nếu một lượt fetch trả lịch sử bị cắt ngắn trong khi sàn có giao
dịch, mã đó phải chờ lượt hôm sau — rẻ hơn 44% call vô ích mỗi lượt.

## Files

- Alembic: một revision mới trên head `c2e94a7b1f30` — thêm `bar_daily`.
  Downgrade = drop (bảng mới, được phép).
- `src/stocks/models.py` — `BarDaily`.
- `src/stocks/providers/vnstock_daily.py` (mới)
- `src/stocks/backfill_daily.py` (mới)
- `src/stocks/listing_roster.py` — thêm writer
- `src/stocks/universe.py` — hai nửa
- Tests: normalize trên fixture response thật · scale equity/index · dedup
  bucket trùng · paging quá 2.000 phiên · skip-when-deep-enough của job · một
  mã lỗi không dừng job · roster map HSX→HOSE + delisted giữ dòng + ICB join ·
  universe hai nửa + `get_field` declared-only.

## Steps

1. Backup DB — **đã xong**: `backups/pre-daily-spine-260827.sql.gz` (5,9M,
   `gzip -t` pass).
2. Migration + model + tests.
3. Fetcher/normalize + `ensure_daily_bars` + tests (offline fixture).
4. Roster writer + universe hai nửa + tests.
5. Job + tests, rồi chạy thật: `declared` → `index` → `market` (nền).
6. Cổng: `make test` xanh; signal smoke 25 field **không đổi** (08a không đụng
   đường đọc của signals — nếu đổi là có lỗi).

## Validation

- `bar_daily` có ≥ 2.000 phiên cho 30 mã declared, ≥ 1.900 cho VNINDEX,
  ≥ 380 phiên cho ≥ 95% của 1.523 mã listed (mã mới lên sàn không đủ 400 phiên
  là bình thường — đếm riêng, không tính là lỗi).
- Chạy job lần hai: row count không đổi (idempotent), và nó bỏ qua mã đã đủ.
- `make test` (host) xanh; `trading_day.latest_trading_day` không đổi giá trị.

## Risk & rollback

- **DB phình**: ~600k dòng typed (`bar_daily`). Đo kích thước trước/sau, ghi
  vào report.
- **Provider không SLA**: job bỏ qua mã lỗi và chạy lại được; không có
  checkpoint nào để hỏng.
- **Rate limit**: 1.523 call cho scope market. Bronze 180/phút là trần, nhưng
  provider in cảnh báo quảng cáo mỗi call — chạy nền, một luồng, không song
  song hoá.
- Rollback: `alembic downgrade -1` (drop `bar_daily`) — không dòng nào của
  serving hiện tại bị đụng, nên rollback không cần restore backup.
