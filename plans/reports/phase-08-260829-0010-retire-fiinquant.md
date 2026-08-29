# Phase 08 — Xoá FiinQuant và nghiệm thu: báo cáo (HOÀN TẤT)

**Ngày:** 2026-08-29 · **Session:** stock-massive-f0
**Trạng thái:** **hoàn tất 2026-08-29.** User chốt hai lượt: 2026-08-28 "code +
backup, dừng trước DELETE" → báo số → 2026-08-29 "chạy" + "có, thêm alembic
revision".

## Bốn cổng vào — đủ cả bốn

| Cổng | Nguồn | Trạng thái |
|---|---|---|
| Phase 04 xong: 30 field khai projection, 7 field trả ba mã cũ | phase-04 | ✅ done (commit `2cee7f1`) |
| Phase 05 xong **và** mean/median/**p95**/max của `close×volume` đã ghi | `phase-05-260828-2333-derived-traded-value.md` | ✅ p95 = **20,367%** < 25% |
| Phase 06 xong **và** tỉ lệ phiên quyết được theo sàn đã ghi | `phase-06-260829-0010-band-from-exchange-rule.md` | ✅ HOSE 91,52% · HNX 89,33% · UPCOM 0% |
| Backup **theo bảng** restore thử, đếm = 106.007 / 71.773 | phase này, bước 1-3 | ✅ khớp tuyệt đối |

Phase 07 **không** là cổng (R5 sai — 0 dòng `market_index` ở mọi source). Đã xong
luôn dù không cần.

## Backup — R6 đã được tuân thủ tường minh

Mọi lệnh chạm DB đi qua `docker exec stockmassive-db-1`, **không** lệnh nào dựa vào
mặc định của `psql`/`pg_dump`.

| File | Bytes | Nội dung |
|---|---|---|
| `backups/pre-retire-fiinquant-260829.sql.gz` | **17.530.136** | toàn DB |
| `backups/pre-retire-fiinquant-provider-snapshots-260829.sql.gz` | **5.409.887** | `-t provider_snapshots` |

17,5 MB là **đúng bậc độ lớn** (so với `pre-rename-signal-desk-260828.sql.gz`
17.398.824 B), không phải 46 KB của ca lỗi R6 đã xảy ra trên máy này.

### Restore thử — so với số cụ thể, không so với chính nó

Nạp bản theo bảng vào DB tạm `restore_probe` trong container, rồi đếm:

| Phép đếm | Kỳ vọng (viết sẵn trong plan) | Đo được |
|---|---|---|
| tổng `provider_snapshots` | 106.007 | **106.007** ✅ |
| `source='fiinquant'` | 71.773 | **71.773** ✅ |
| fiinquant / `market` | 36.528 | **36.528** ✅ |
| fiinquant / `valuation` | 35.245 | **35.245** ✅ |

`restore_probe` đã drop sau khi đếm. Đường phục hồi tài liệu hoá: nạp lại
`-t provider_snapshots` vào DB đang chạy — **không** restore toàn DB, vì làm thế
sẽ xoá chính `agent_thread`/`agent_turn`/`agent_message`/`agent_tool_call`/
`agent_artifact`/`llm_call_usage` và mọi `bar_daily` đã ingest từ lúc dump, trong
khi tiền LLM đã tiêu thật.

## Code — đã gỡ nguồn khỏi bản đồ ownership

| File | Thay đổi |
|---|---|
| `src/stocks/providers/contracts.py` | `MARKET` và `VALUATION`: `main=VNSTOCK`, **bỏ `cover`** |
| `tests/test_provider_contracts.py` | bảng ownership + `owns_capability` cho mọi Capability |

**Bẫy `validate_distinct_sources` đã tránh đúng cách.** `contracts.py:151-155` raise
khi `cover is main`. Cả MARKET và VALUATION đang `main=FIINQUANT, cover=VNSTOCK`;
đổi `main` sang vnstock mà giữ `cover` sẽ raise **lúc import** — nghĩa là mọi test
vỡ ở collection, không phải một test đỏ đọc được. Đã **bỏ `cover`**, không chỉ đổi
`main`. Đã viết lý do vào code.

**Không reader nào bị ảnh hưởng.** Grep `main_source|cover_source|owns_capability`
toàn `src/`: chỉ ba call site, và cả ba đọc Capability **khác**:
`studies/reads_fundamental.py:111` và `signals/fundamentals.py:89` đọc FUNDAMENTAL,
`signals/reference.py:156` đọc REFERENCE — cả hai đã là vnstock từ trước. Không ai
đọc `main_source(MARKET)` hay `main_source(VALUATION)`. Nên thay đổi này đúng nghĩa
là **sửa một lời khai**, không đổi hành vi runtime.

### `schemas/snapshot.py` — không có gì để gỡ

Plan xếp file này vào bảng surface với giới hạn "gỡ echo REST của nguồn đã xoá".
Đo lại: `grep -i fiinquant src/stocks/schemas/snapshot.py` → **0 hit**. Các field
là `source: str` chung, không nêu tên nhà cung cấp nào. Thêm nữa, **cả package
`src/stocks/schemas/` không còn importer nào** (router REST đã rip 2026-08-25) —
`grep -rn "stocks.schemas" src/ tests/` chỉ còn một dòng docstring ở
`providers/contracts.py:4`. Không sửa gì, và ghi ra đây để không ai đi tìm.

## Gỡ tên — 8 file còn lại, và vì sao chúng CHƯA gỡ

`grep -ric fiinquant src/ tests/` sau các thay đổi trên:

| File | Hit | Loại | Quyết định |
|---|---|---|---|
| `tests/test_provider_contracts.py` | 25 | fixture dựng `MarketSnapshot` với `source=FIINQUANT` + `basis=RAW` | **giữ** — cần enum member |
| `src/stocks/providers/contracts.py` | 1 | `FIINQUANT = "fiinquant"` enum member | **giữ tới sau DELETE** |
| `tests/conftest.py` | 2 | `basis_of()` rẽ nhánh trên enum member | **giữ** — cần enum member |
| `src/stocks/realtime/policy.py` | 2 | `MarketDataSource.FIINQUANT` — enum **song song**, khác `ProviderSource` | **giữ** — `realtime/*` freeze, 0 reader sống |
| `src/stocks/realtime/contracts.py` | 1 | `FIINQUANT = "fiinquant"` của enum song song | **giữ** — cùng lý do |
| `src/stocks/providers/normalize.py` | 1 | **docstring** | **giữ** — surface FREEZE, plan nói đụng nó là tín hiệu dừng |
| `src/stocks/providers/__init__.py` | 1 | docstring lịch sử "adapters ... were dropped when" | **giữ** — câu đúng về quá khứ |
| `src/studies/entry_condition_review.py` | 1 | docstring, địa phận plan Study | **giữ** — không phải của phase này |

**Lý do sắp xếp lại thứ tự so với phase file.** Phase file đặt bước 8 (gỡ tên) sau
bước 6 (DELETE). Vì DELETE bị hoãn, gỡ `ProviderSource.FIINQUANT` **bây giờ là
sai**: 71.773 dòng vẫn mang `source='fiinquant'`, và bỏ member khỏi enum sẽ khiến
mọi `ProviderSource(row.source)` trên các dòng đó **raise** thay vì đọc được. Đúng
thứ tự là: xoá dòng trước, gỡ tên sau. Đã giữ nguyên trật tự an toàn đó.

`realtime/{contracts,policy}.py`: enum **song play** `MarketDataSource`, không phải
`ProviderSource`, nên không dính DELETE. Nhưng `realtime/*` vẫn freeze và gỡ nó
không mua được gì lúc này → để lại, ghi lý do, đúng như phase file cho phép.

## Nghiệm thu

| Cổng | Kết quả |
|---|---|
| `make test` (api, chạy trên host) | ✅ **1405 passed** |
| `tests/studies/` | ✅ trong 1405, không đỏ |
| `pnpm type-check` | ✅ |
| `pnpm lint` | ✅ |
| `pnpm test` | ✅ 59 file / **736 test** |
| `pnpm build` | ✅ (cổng 3000 rảnh, không đụng `.next` của dev) |

## CHƯA LÀM — chờ user

### 1. Phép xoá 71.773 dòng

Lệnh đã soạn, **chưa chạy**, có abort tự động nếu số dòng không khớp:

```sql
BEGIN;
DELETE FROM provider_snapshots WHERE source='fiinquant';
-- kiểm ROW_COUNT = 71773; khác → ROLLBACK
COMMIT;
```

Chạy qua `docker exec stockmassive-db-1` để ghim host. Trước khi COMMIT sẽ ghi số
trước/sau theo `(source, capability)` vào report này.

Sau khi xoá xong mới làm được: gỡ `ProviderSource.FIINQUANT` + 28 tham chiếu test,
rồi `make test` lại, rồi smoke lane chat thật (bước 9), rồi cập nhật `CLAUDE.md`
và `docs/roadmap.md`.

### 2. Smoke lane chat thật (bước 9)

Chưa chạy — nó có nghĩa nhất **sau** khi xoá, vì mục đích của nó là bắt reader bị
bỏ sót. Chạy trước khi xoá thì mọi field vẫn đọc được nguồn cũ và smoke sẽ xanh
một cách vô nghĩa.

### 3. Quyết định về data revision (rủi ro phase file nêu)

Phép xoá này **không có bản ghi replay được**: không alembic revision, nên không
môi trường nào khác tái hiện được và không ai review được nó như review một
migration. Đánh đổi với luật "alembic đã commit thì không sửa" (thêm revision mới
thì không vi phạm luật đó). Phase file nói đây phải là **quyết định**, không phải
mặc định — nên nó đang chờ user, chưa chọn.

### 4. Dòng vnstock/market 2016-2021 (31.160 dòng)

**Mặc định giữ**, đúng plan: không ai đọc sau Phase 03, nhưng cũng **không vi phạm
gì**. Không xoá.

## Success Criteria — trạng thái

- [ ] `count(*) WHERE source='fiinquant'` = 0 trên DB container — **chờ DELETE**
- [ ] `grep -ril fiinquant` không còn ở đường phục vụ — **một phần**: đã gỡ khỏi bản
      đồ ownership (đường phục vụ thật sự); enum + fixture giữ tới sau DELETE
- [ ] 22 field ra số / 8 field refusal trên smoke lane chat thật — **chờ**, có nghĩa sau DELETE
- [x] Backup theo bảng đã restore thử, đếm khớp **106.007 / 71.773**, đường dẫn ghi ở trên
- [x] `make test` + `tests/studies/` + bốn cổng web xanh
- [ ] `CLAUDE.md` ghi dòng dữ liệu đã xoá — **chờ DELETE**


---

# Bổ sung 2026-08-29 — phép xoá đã chạy

## Đóng gói thành revision, không phải SQL một lần

User chốt **có** data revision. Nên phép xoá chạy **qua** alembic, không phải qua
`psql` — như thế nó replay được và review được như một diff.

`alembic/versions/a3f7e21b8d54_delete_the_retired_quote_source_rows.py`
(revises `f8c2d4a96e17`). Ba tính chất:

1. **Cổng đếm theo capability, so với số viết sẵn**, không so với chính nó:
   `{market: 36528, valuation: 35245}`. Lệch → `RuntimeError`, transaction bỏ.
2. **Idempotent**: DB không có dòng nào của nguồn đó thì `return` sớm, không raise —
   một migration chạy lại không được là lỗi.
3. **Cổng thứ hai sau khi xoá**: `rowcount != 71773` → raise trước `COMMIT`.
4. `downgrade` raise `NotImplementedError`, trỏ vào **bản backup theo bảng** và nói
   rõ vì sao đừng restore toàn DB.

Không sửa file revision cũ nào — chỉ thêm revision mới, nên không vi phạm luật
"alembic đã commit thì không sửa".

## Kết quả

```
alembic upgrade head → f8c2d4a96e17 -> a3f7e21b8d54
```

| Sau khi xoá | |
|---|---|
| `source='fiinquant'` | **0** ✅ |
| tổng `provider_snapshots` | 34.234 = 106.007 − 71.773 ✅ |
| còn lại | `vnstock`: fundamental 2.854 · market 31.160 · reference 220 |

## Gỡ tên — đã gỡ những gì

| Chỗ | Việc |
|---|---|
| `providers/contracts.py` | **gỡ `ProviderSource.FIINQUANT`**. Enum còn một member. `ProviderSource("fiinquant")` giờ raise — đó là mục đích |
| `tests/conftest.py` | `basis_of()` bỏ nhánh, giữ chữ ký (nó là chỗ ghi câu "source nào mang basis nào") |
| `tests/test_provider_contracts.py` | 21 tham chiếu → `VNSTOCK`; hai assertion nêu tên nguồn cũ thay bằng vòng lặp trên `Capability` |
| `studies/entry_condition_review.py` | docstring **sai sự thật** sau Phase 03 (nói ba field đọc `provider_snapshots`) — sửa: lý do provenance đã hết hiệu lực, lý do giữ tính cục bộ giờ là "đã có sẵn chuỗi close, đọc field là ba lần dựng cửa sổ cho số đã nắm trong tay" |

**Giữ, có lý do ghi ra:**

- `realtime/{contracts,policy}.py` — `MarketDataSource.FIINQUANT` là enum **song
  song**, không phải `ProviderSource`. Member đó không có reader (`foreign_share_flow.py`
  chỉ đọc `MarketDataSource.DNSE`). Nhưng gỡ nó **kéo theo viết lại
  `SOURCE_OWNERSHIP`** của `realtime/policy.py` cho `HISTORICAL_EOD` và `VALUATION`
  — tức sửa logic trong module vẫn **freeze**. Phase file cho phép đúng lựa chọn
  này: "gỡ nếu sạch; nếu kéo theo gì thì để lại và ghi lý do".
- `providers/normalize.py` — docstring, surface **FREEZE**. Phase file: đụng nó là
  tín hiệu dừng.
- `providers/__init__.py` — docstring lịch sử, câu đúng về quá khứ.

## Bước 9 — smoke lane chat thật, sau khi xoá

Phục vụ **cả 33 field đã đăng ký** qua `serve_field`/`serve_cross_section` trên DB
container, Universe declared làm peer:

| Mã | Phục vụ | Từ chối |
|---|---|---|
| VCB (ngân hàng) | **25** | 8 |
| VNM (sản xuất) | **26** | 7 |
| MWG (bán lẻ) | **26** | 7 |
| HPG (sản xuất) | **25** | 8 |

Tám refusal của VCB, không mã nào ngoài dự kiến:

| Mã refusal | Số | Field |
|---|---|---|
| `market_cap_absent` | 3 | `factor_percentiles.{book_yield,earnings_yield,size}_percentile` |
| `foreign_flow_not_stored` | 3 | `foreign_flow_pressure.*` |
| `unavailable` | 1 | `relative_strength.beta_vs_market_index` (estimator chưa viết) |
| `statement_line_missing` | 1 | `earnings.gross_profit_trend` — **VCB là ngân hàng**, không khai dòng lãi gộp |

**Không reader nào bị bỏ sót** — đó là việc bước 9 tồn tại để bắt. Đáng chú ý,
`company_profile.foreign_room_pct` **trả số** (33,05) chứ không refuse như plan dự:
220 dòng `reference` của vnstock còn nguyên. Tốt hơn dự đoán một field.

`earnings.*` trên mã không phải ngân hàng: VNM `eps +30,88%` · `net_profit +27,96%`
· `gross_profit_trend +4,62%`. HPG `eps` refuse `statement_line_missing` — đúng
luật "số 0 tuyệt đối là dòng chưa khai", HPG khai EPS bằng 0.

## Docs

- `CLAUDE.md` — mục "Không còn tồn tại" ghi phép xoá + thứ tự bắt buộc (xoá dòng
  trước, gỡ enum sau); bảng freeze đánh dấu **tám surface đóng lại**; sửa một **mâu
  thuẫn**: bảng ghi "không thêm mã refusal mới" trong khi Phase 06 của chính plan
  yêu cầu thêm `price_off_tick_grid` — đã ghi rõ giới hạn thật; thêm sáu dòng
  Quy ước (33 field · `projection` · luật basis hai cổng · band theo lưới ·
  `traded_value` suy diễn · nợ BAND của `check_price_claim`).
- `docs/roadmap.md` — S0 ghi price-basis spine xong + nợ BAND.

## Success Criteria — đóng

- [x] `count(*) WHERE source='fiinquant'` = **0** trên DB container, lệnh ghim host
- [x] `grep -ril fiinquant` không còn ở đường phục vụ (còn 3 docstring + 1 enum song
      song trong module freeze, mỗi cái ghi lý do)
- [x] 25–26 field ra số / 7–8 field refusal đúng mã, trên smoke lane chat thật
- [x] Backup theo bảng đã restore thử, đếm khớp 106.007 / 71.773
- [x] `make test` (1423) + `tests/studies/` + bốn cổng web xanh
- [x] `CLAUDE.md` ghi dòng dữ liệu đã xoá
