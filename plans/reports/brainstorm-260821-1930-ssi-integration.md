# Brainstorm — tích hợp SSI FastConnect Data vào Stock_Massive

> **Hợp đồng này không còn hiệu lực (2026-08-21).** Hai trụ của nó đã đổ sau khi khảo
> sát v3 và đọc nguyên văn điều khoản:
> 1. **Cổng lọc theo source không đạt compliance.** Điều khoản cấm cấp cho bên thứ ba
>    thông tin "nguyên gốc **hay đã được xử lý**" (`developers.ssi.com.vn/term-condition`),
>    nên signal phái sinh cũng bị cấm — không phải vùng xám như đã viết dưới đây.
> 2. **Lý do làm Cover Source biến mất trên v3.** `closepriceadjusted` là toàn bộ luận
>    cứ; v3 không có field điều chỉnh nào. v2 có, nhưng v2 đóng băng trước KRX.
>
> Xem `docs/research/ssi-fastconnect-capabilities.md`. Giữ lại tài liệu này vì phần đo
> lường store (5 năm lịch sử rỗng field) vẫn đúng và vẫn là vấn đề cần giải.

Ngày: 2026-08-21 · Nhánh: `develop`
Tiền đề: `plans/reports/research-260821-1920-ssi-fastconnect-fitness.md` (khảo sát
năng lực API). Tài liệu này chốt **vai** của SSI trong hệ thống và hợp đồng giao
việc, không lặp lại đặc tả field.

## Bằng chứng mở đầu — vì sao đáng làm

Đo `provider_snapshots` trên DB dev (2026-08-21):

| capability | source | rows | từ | đến |
|---|---|---|---|---|
| market | vnstock | 31 160 | 2016-06-20 | 2021-08-18 |
| market | fiinquant | 36 468 | 2021-08-04 | 2026-08-19 |
| valuation | fiinquant | 35 185 | 2021-08-04 | 2026-08-20 |
| fundamental | vnstock | 2 842 | 2018-03-30 | 2026-06-29 |
| reference | vnstock | 190 | 2026-08-09 | 2026-08-20 |

Vùng vnstock là `adjusted_at_source`. Theo `src/stocks/signals/bars.py:76-77`:

- window nằm trọn 2016→2021 → từ chối `unadjustable_price_basis`;
- window bắc qua mối nối 2021-08 → từ chối `mixed_price_basis`.

Nghĩa là **5 năm lịch sử đã nằm trong store nhưng không phân tích được**, và hệ
thống thực tế chỉ dùng được ~4 năm gần nhất. `DailyStockPrice` của SSI là nguồn
duy nhất khảo sát được trả `closeprice` (thô) cùng `closepriceadjusted` trên một
dòng, nên nó xoá được cả hai verdict trên — cộng thêm trần/sàn/tham chiếu và khối
ngoại đủ vol+val+net cho chính vùng lịch sử mà vnstock không có.

Hai chỗ hỏng khác mà SSI chạm tới, nhưng **để lần sau**: `reference` chỉ có 190
dòng của hai tuần trong khi `signals/foreign_flow.py` mang room state đi cùng mọi
flow reading; `stock_intraday_bars` có **17 dòng**, tức đường intraday đã chết.

## Quyết định phạm vi — hai câu trả lời của người dùng và chỗ chúng đụng nhau

Người dùng chốt: (1) Stock_Massive **sẽ có user ngoài**; (2) 31.160 dòng vnstock
**xoá sau khi đối chiếu**.

Hai điều này kéo ngược nhau: có user ngoài thì điều khoản SSI (cấm cấp dữ liệu
cho bên thứ ba) đẩy SSI về vai cross-check, mà cross-check thì không nạp lại dòng
nào để đối chiếu rồi xoá.

Gỡ bằng kiến trúc đã có: `docs/adr/0002` quy định mỗi điểm của `SnapshotStore.series()`
mang `metadata.source` của chính nó ra tới wire. Vậy **một cổng lọc theo source ở
lớp phục vụ** là mở rộng tự nhiên, không phải miếng chắp: dữ liệu SSI vào store,
phục vụ phân tích và kiểm định nội bộ, không rời hệ thống tới user ngoài.

Ba điều phải nói thẳng kèm quyết định này:

1. **Nợ redistribution đã có sẵn ở đúng vùng đó.** 31.160 dòng hiện tại là vnstock,
   mà license vnstock cấm dùng thương mại không có phép tác giả. Đổi sang SSI
   không làm xấu thêm về nguyên tắc — nó đổi sang một chủ nợ có hợp đồng ghi tên
   khách hàng, nên khả năng bị đòi cao hơn.
2. **Signal phái sinh là vùng xám.** Cổng lọc chặn được chuỗi giá thô, không chặn
   được việc một chỉ báo tính từ dữ liệu SSI đi tới user. ToS SSI viết chặt hơn
   thông lệ ("chỉ phục vụ giao dịch của chính khách hàng"). Đây là rủi ro tồn
   đọng, không phải rủi ro đã xử lý.
3. **Đường sạch vẫn là FiinQuant tier trả tiền** (dữ liệu có license, rate limit
   công bố), đúng xếp hạng của `docs/research/vn-market-data-sources.md`. SSI là
   bước đi được ngay với chi phí bằng không, không phải đích đến.

## Hợp đồng giao việc

**Outcome** — SSI FCData vào repo ở đúng một vai: **Cover Source của
`Capability.MARKET`**, thay vnstock ở vai đó. Sau khi chạy: lịch sử sâu của
Universe mang `source=ssi`, `price_basis=raw`; một window 5 năm không còn bị từ
chối vì basis; và dữ liệu `source=ssi` không được phục vụ ra ngoài cho người dùng
không phải chủ hệ thống.

**Constraints**
- ToS SSI cấm cấp dữ liệu cho bên thứ ba → bắt buộc có cổng lọc theo source ở lớp
  phục vụ; đây là phần của scope, không phải tuỳ chọn.
- Rate limit không công bố, tính theo connection key → bộ điều tiết riêng cho SSI.
  **Không** đi qua `VnstockQuotaArbiter` (`src/core/quota.py:197`): đó là hạn mức
  của tài khoản vnstock, trộn vào là làm sai cả hai.
- `SourceOwnership` cho tối đa một cover mỗi capability → SSI vào là vnstock ra ở
  vai cover của `market`. Cần **ADR mới**; `docs/adr/0002` không tự đúng sau thay
  đổi này.
- `metadata.source` nằm trong `uq_provider_snapshot_identity` → dòng vnstock cũ
  không bị ghi đè, chúng tồn tại song song cho tới khi bị xoá có chủ đích.
- **Backup trước khi xoá** 31.160 dòng, theo quy tắc DB của repo. Xoá xong mà sau
  này phải bỏ SSI vì ToS thì mất cả hai nguồn và phải backfill lại qua hạn mức
  vnstock 20 req/phút.
- Credential (`ConsumerID` / `ConsumerSecret` / `PrivateKey`) chưa có trong `.env`
  → chặn thực thi, không chặn thiết kế.
- Không dùng SDK `ssi-fc-data` (2.2.2, upload 2024-06-05, `requires_dist: None`);
  gọi REST trực tiếp bằng `requests`, theo lối `vnstock_provider.py` đã tự dựng.

**Non-goals**
- Không thay FiinQuant làm Main của `market`: SSI không có vốn hoá, không có
  P/E, P/B.
- Không chạm `fundamental`, `valuation`, listing roster (SSI không có ICB), hay
  `CorporateActionProvider`.
- Không streaming, không intraday lần này. `SnapshotStore` khoá theo `effective_at`
  cấp phiên, nhận tick đòi một đường ghi mới — đó là hạng mục riêng.
- Không mở cover cho `reference` lần này (room lịch sử, `ListedShare`) dù SSI cấp
  được: đó là ADR thứ hai.

**Acceptance criteria**
1. `provider_snapshots` có `source=ssi`, `capability=market`, `price_basis=raw`
   phủ dải SSI trả được, cho toàn Universe.
2. `prepare_bars()` trên window 2019→2026 không trả `mixed_price_basis` hay
   `unadjustable_price_basis`.
3. Một request của user ngoài không nhận được điểm nào mang `source=ssi`; có test
   khẳng định điều đó.
4. Đối chiếu SSI ↔ vnstock trên vùng chồng lấn cho ra sai số đo được và ghi lại,
   **trước** khi xoá dòng nào; có dump backup.
5. `make test` xanh tại `apps/api`.
6. Số request thật của một lần backfill Universe được đo và ghi lại.

## Hướng đã chọn và hai hướng bị loại

**Chọn: Cover Source cho market history, kèm cổng phục vụ theo source.**
Nhỏ nhất đạt Outcome, và rẻ để bỏ — nếu probe cho thấy SSI chỉ có lịch sử từ
2020, adapter vẫn dùng cho vùng đó và quyết định cover đảo lại bằng một dòng
trong `SOURCE_OWNERSHIP_BY_CAPABILITY`.

Giả định gánh nặng nhất: **SSI trả được lịch sử tới 2016**. Chưa ai biết; spec
không nói. Vỡ trước ở đây, và đó là lý do probe đứng trước mọi thứ khác.

Con số làm hướng này khả thi: `DailyStockPrice` **không** ràng 30 ngày mỗi request
như `DailyOhlc`, chỉ `pageSize ≤ 100`. 5 năm một mã ≈ 13 request; Universe 30 mã
≈ 390 request; cả 1.710 mã ≈ 22.000.

- **Loại: chỉ cross-check, không đổi ownership.** Rẻ nhất, không cần ADR, xác thực
  được Adjustment Factor của `ADR-0006` bằng nguồn độc lập — nhưng không mở được
  5 năm lịch sử, tức không giải quyết cái đau đã đo. Giữ lại như **bước 1** của
  hướng đã chọn thay vì một hướng riêng.
- **Loại: gộp luôn room lịch sử và intraday.** Hai ADR và một đường ghi mới trong
  một lần thay đổi; `reference` đang `main=vnstock, cover=None` nên mở cover ở đó
  là quyết định riêng đáng có bằng chứng riêng.

## Thứ tự thực thi

1. **Đăng ký FastConnect, lấy credential, probe.** Đo bốn ẩn số không suy ra được
   từ spec 2022: (a) rate limit thật; (b) `DailyStockPrice` có lịch sử từ năm nào;
   (c) `totalbuytradevol`/`totalselltradevol` có số thật hay luôn `0` — spec trả
   `0`, đúng bẫy `bu`/`sd` mà `ADR-0002` đã gặp ở FiinQuant; (d) field nào còn
   sống sau KRX (spec V2.0 changelog dừng 05/2022).
2. **ADR mới**: đổi cover của `market` sang SSI, và ghi cổng phục vụ theo source.
3. **Adapter** `src/stocks/providers/ssi_fcdata.py`: `SsiMarketHistoryProvider`
   implement `MarketHistoryProvider`, dùng lại `ProviderCircuitBreaker`
   (`providers/fiinquant.py:132`) nguyên vẹn, thêm bộ điều tiết riêng.
4. **Cổng phục vụ theo source** ở lớp đọc, kèm test của criteria 3.
5. **Backfill + đối chiếu** vùng chồng lấn, ghi sai số; dump backup; rồi mới xoá
   dòng vnstock.

Điểm cắm không phải sửa kiến trúc: `ProviderSource` (`providers/contracts.py:33`),
`SOURCE_OWNERSHIP_BY_CAPABILITY` (`:157`), `build_collector()`
(`stocks/collector.py:284`), `Settings` (`core/config.py:45`).

**Eval gate**: thay đổi này không chạm System Prompt Contract, tool schema, Signal
Registry, Analysis Field Profile, `llm_model_*`, agent loop hay Recommendation
Validator → theo `CLAUDE.md` **không cần** Eval Report. Cần kiểm một điều:
`src/eval/roles.py:225` và `src/eval/categories/safety.py:112` khẳng định
`prepare_bars()` từ chối `mixed_price_basis`; Eval Fixture đóng băng trên
`EVAL_DATABASE_URL` riêng nên về nguyên tắc không bị ảnh hưởng, nhưng phải xác
nhận thay vì giả định.

## Câu hỏi còn treo

- Có tài khoản SSI để đăng ký FastConnect chưa? Không có credential thì bước 1
  không chạy được và mọi bước sau vẫn là giả định.
- Cổng phục vụ theo source đặt ở đâu: `SnapshotStore.series()`, lớp
  `series_view.py`, hay biên router? Quyết định này cần đọc đường đọc hiện tại,
  chưa làm trong phiên này.
- Lịch sử sâu phục vụ user ngoài lấy ở đâu về lâu dài? FiinQuant hiện chỉ có từ
  2021-08 trong store; tier trả tiền có sâu hơn hay không thì chưa ai hỏi bán
  hàng.
