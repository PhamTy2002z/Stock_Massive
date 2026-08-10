# Main/Cover cắt ngang Capability, tách `valuation` khỏi `fundamental`

Đo thực tế gói FiinQuant free cho thấy hai nhà cung cấp không chia nhau gọn theo ba Capability mà `providers/contracts.py` giả định. FiinQuant có giá, khối lượng, giá trị, dòng tiền chủ động, khối ngoại, giá trần sàn, vốn hoá và **P/E, P/B** — nhưng **không** có báo cáo tài chính (`get_financial_statement` rỗng ở mọi tổ hợp tham số, `valid_fields` rỗng), **không** có freefloat hay số cổ phiếu lưu hành (cột có, giá trị `nan`), và bị 403 ở room NĐTNN, giao dịch theo nhà đầu tư, độ rộng thị trường, danh sách mã theo ngành.

Vì P/E, P/B thuộc FiinQuant còn báo cáo tài chính thuộc vnstock, ta **tách `fundamental` thành hai Capability**: `valuation` (P/E, P/B — Main là FiinQuant) và `fundamental` (báo cáo tài chính — Main là vnstock). Bảng Main/Cover sau khi đo:

| Capability | Main Source | Cover Source |
|---|---|---|
| `market` — giá, khối lượng, giá trị, `bu`/`sd`, `fb`/`fs`/`fn`, trần sàn, vốn hoá | fiinquant | vnstock cho mã ngoài Universe và lịch sử sâu hơn ~5 năm |
| `valuation` — P/E, P/B | fiinquant | vnstock |
| `reference` — số cổ phiếu lưu hành, room NĐTNN, freefloat | vnstock | — |
| `fundamental` — báo cáo tài chính | vnstock | — |

Lịch sử được nạp nền **một lần** từ vnstock cho phần sâu hơn khả năng của FiinQuant, sau đó FiinQuant nối tiếp mỗi ngày. Mối nối được ghi lại qua `Snapshot.metadata.source`.

### Nhịp công bố của chuỗi `market` (đo 2026-08-10)

Bốn lời gọi của FiinQuant không cùng nhịp, và độ lệch đủ lớn để đọc nhầm thành "thiếu dữ liệu". Đo tối thứ Hai 10/08, sau khi thị trường đã đóng nhiều giờ:

- `Fetch_Trading_Data(realtime=False, by="1d")` lúc 21:48 vẫn dừng ở phiên trước (07/08); tới 22:47 mới có phiên 10/08, và có dưới dạng **một dòng stamp theo tick cuối** (`2026-08-10 14:46`) chứ không phải nửa đêm như các phiên đã chốt. `bu`/`sd` của dòng đó bằng 0 dù khối lượng khớp hàng triệu cổ phiếu.
- `get_stock_valuation` đã có phiên 10/08, stamp nửa đêm.
- `get_ceilingfloor` đã có phiên 10/08, stamp theo tick.
- `get_overview` vẫn trễ một phiên, nên vốn hoá của phiên vừa đóng là `null`.

Hệ quả cho adapter: `effective_at` của `market` lấy theo **đầu ngày phiên giờ VN**, để một phiên là một Snapshot dù provider ghi hai lần (live rồi consolidated) — `SnapshotStore` khoá theo `effective_at` và đọc theo `effective_at` mới nhất, nên stamp theo tick sẽ khiến dòng dở dang che mất dòng đã chốt suốt phần còn lại của ngày hôm sau. `bu`/`sd` bằng 0 khi có khối lượng khớp thì đọc là **chưa công bố**, không phải bằng 0.

Đây cũng là lý do thật của ngưỡng bảy ngày ở `SESSION_MAX_AGE_SECONDS`: một chu kỳ chạy trước lúc provider nối phiên sẽ lấy được phiên trước đó — hợp lệ chứ không phải hỏng.

### Đọc một phiên và đọc một chuỗi là hai luật khác nhau

Bổ sung khi làm #27. Luật "không tự rơi sang Cover Source" ở trên viết cho `SnapshotStore.latest()` — đọc **một** phiên, trả **một** con số. Ở đó lẫn nguồn là nguy hiểm: người đọc thấy một giá và không có cách nào biết nó vừa đổi nguồn.

`SnapshotStore.series()` đọc một dải phiên và **đọc cả hai nguồn sở hữu Capability đó**. Không phải nới lỏng luật cũ mà là một tình huống khác: lịch sử vốn dĩ là hai nguồn nối nhau — `Backfill` nạp phần sâu từ Cover Source, `Collector` ghi tiếp mỗi phiên từ Main Source — nên hỏi một nguồn là hỏi một nửa. Điều khiến việc này an toàn: **mỗi điểm mang `source` của chính nó ra tới wire**, đúng như đoạn "mối nối được ghi lại qua `Snapshot.metadata.source`" ở trên. Người đọc so một phiên 2019 với phiên tuần trước biết mình đang so hai phép đo.

Rủi ro còn lại không phải đơn vị — cả hai `Adapter` đã chuẩn hoá về VND — mà là **trường một nguồn không điền**. `VnstockMarketHistoryProvider` không có `total_value_vnd`, FiinQuant có. Một bar tuần bắc qua mối nối mà cộng phần có sẽ báo giá trị vài phiên thành giá trị cả tuần: một con số nhỏ hơn nhưng trông như tổng, đúng kiểu sai âm thầm mà phương án fallback động bị loại vì nó. Nên phép gộp **từ chối tổng thiếu**: thiếu một phiên thì trường đó là `null`, không phải một tổng nhỏ hơn.

Nếu sau này có thêm trường mà một nguồn không điền, luật vẫn đứng nguyên chỗ đó và không phải sửa gì.

## Considered Options

- **Fallback động giữa hai nguồn cho cùng một Capability.** Bị loại: hai nguồn lệch đơn vị — FiinQuant trả giá bằng VND (HPG 22.000), còn payload hiện tại của hệ thống trộn VND, triệu VND và tỷ VND tuỳ trường. Rơi nguồn giữa chừng sẽ tạo biểu đồ sai mà không ai phát hiện, và với một công cụ phân tích thì đó nguy hiểm hơn là thiếu dữ liệu.
- **Giữ nguyên ba Capability và ép P/E, P/B về vnstock.** Bị loại: vứt đi dữ liệu định giá đã có sẵn, chất lượng tốt, ở nguồn có hạn mức rộng hơn.

## Consequences

- `PRIMARY_SOURCE_BY_CAPABILITY` trong `providers/contracts.py` phải viết lại: bảng hiện tại gán `market` cho FiinQuant và cả `reference` lẫn `fundamental` cho vnstock, không khớp với năng lực đo được. Đã thay bằng `SOURCE_OWNERSHIP_BY_CAPABILITY` — mang cả Main lẫn Cover và bỏ từ "primary" mà `CONTEXT.md` liệt vào `_Avoid_`.
- Cover Source chỉ đọc được khi người gọi nêu tên nguồn. `SnapshotStore.latest()` mặc định ở Main Source và không tự rơi sang Cover, đúng với phương án fallback động đã bị loại ở trên.
- `FundamentalSnapshot` đang gộp `provider_pe`/`provider_pb` chung với lợi nhuận và vốn chủ. Hai nửa này giờ đến từ hai nguồn khác nhau nên phải tách thành hai snapshot riêng.
- Một mã trong Universe cần lấy từ **cả hai** nhà cung cấp mỗi chu kỳ, không phải một. Collector phải chịu được việc một nguồn hỏng mà nguồn kia vẫn ghi được.
- Nếu sau này nâng gói FiinQuant, báo cáo tài chính và reference có thể chuyển về FiinQuant; ADR này sẽ cần xem lại chứ không tự đúng.
