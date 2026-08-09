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

## Considered Options

- **Fallback động giữa hai nguồn cho cùng một Capability.** Bị loại: hai nguồn lệch đơn vị — FiinQuant trả giá bằng VND (HPG 22.000), còn payload hiện tại của hệ thống trộn VND, triệu VND và tỷ VND tuỳ trường. Rơi nguồn giữa chừng sẽ tạo biểu đồ sai mà không ai phát hiện, và với một công cụ phân tích thì đó nguy hiểm hơn là thiếu dữ liệu.
- **Giữ nguyên ba Capability và ép P/E, P/B về vnstock.** Bị loại: vứt đi dữ liệu định giá đã có sẵn, chất lượng tốt, ở nguồn có hạn mức rộng hơn.

## Consequences

- `PRIMARY_SOURCE_BY_CAPABILITY` trong `providers/contracts.py` phải viết lại: bảng hiện tại gán `market` cho FiinQuant và cả `reference` lẫn `fundamental` cho vnstock, không khớp với năng lực đo được.
- `FundamentalSnapshot` đang gộp `provider_pe`/`provider_pb` chung với lợi nhuận và vốn chủ. Hai nửa này giờ đến từ hai nguồn khác nhau nên phải tách thành hai snapshot riêng.
- Một mã trong Universe cần lấy từ **cả hai** nhà cung cấp mỗi chu kỳ, không phải một. Collector phải chịu được việc một nguồn hỏng mà nguồn kia vẫn ghi được.
- Nếu sau này nâng gói FiinQuant, báo cáo tài chính và reference có thể chuyển về FiinQuant; ADR này sẽ cần xem lại chứ không tự đúng.
