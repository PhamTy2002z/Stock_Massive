# Portfolio Intelligence — danh sách chức năng UI

Ngày: 2026-08-23 · Nhánh: `develop` · Dùng để build UI

Bốn quyết định đã chốt và chúng chi phối mọi mục dưới đây:
**research-only** (không tỷ trọng mục tiêu, không mức vào/ra, không rebalance) ·
**nhập tay từng giao dịch** · **mở theo lớp** (field bar-only cho mọi mã,
percentile chỉ VN30) · **model chỉ thấy figure đã tính**.

Ký hiệu lớp — quyết định chức năng nào hiện số ngay và chức năng nào phải chờ dữ
liệu:

- **L1** — đúng với một phiên dữ liệu. Không bao giờ "chưa đủ mẫu".
- **L2** — cần mẫu. Có sàn phiên; dưới sàn thì `refused` + reason code.
- **L3** — scenario deterministic, có giả định nêu rõ.

---

## 0. Chỗ đặt trong shell

Sản phẩm là một màn hình. Portfolio là **view thứ năm**, không phải route.

| Việc | File | Thay đổi |
|---|---|---|
| Thêm view | `shell-state.tsx:29` | `ShellView = "chat" \| "board" \| "new" \| "news" \| "portfolio"` |
| Thêm tab inspector | `shell-state.tsx:32` | `InspectorTab = ... \| "portfolio"` |
| Render view | `app-shell.tsx:78` `MainView()` | thêm `if (state.view === "portfolio") return <PortfolioView />` |
| Overlay nhập giao dịch | `shell-state.tsx:34` | `Overlay = ... \| "transaction"` |
| Component chính | mới: `components/shell/view-portfolio.tsx` | lấy `view-board.tsx` làm khuôn |

### State mới cần thêm vào `ShellState`

```ts
/** Danh mục đang xem. Null khi user chưa có danh mục nào. */
portfolioId: number | null
/** Vị thế đang mở trong inspector, hoặc null. Symbol chứ không phải object:
 *  bảng vị thế đã sở hữu số liệu, bản sao ở đây sẽ lệch. */
portfolioPosition: string | null
/** Giao dịch đang sửa, hoặc null khi overlay đang ở chế độ thêm mới. */
editingTransaction: number | null
/** Kỳ đang xem trên chart và trên mọi số hiệu suất. */
period: "1M" | "3M" | "6M" | "1Y" | "YTD" | "ALL"
```

### Action mới

```ts
| { type: "portfolio"; id: number | null }
| { type: "open-position"; symbol: string }       // mở inspector tab portfolio
| { type: "edit-transaction"; id: number | null } // null = thêm mới
| { type: "period"; period: Period }
```

Ràng buộc giữ nguyên từ shell hiện tại: **đổi view không được làm mất câu đang gõ
dở** — `draft` sống ở shell state, không ở composer.

---

## 1. Sidebar — mục "Danh mục"

Đặt ngay trên hoặc dưới `WatchlistSection`. Cùng pattern: join hai resource ở
client, không nhờ backend trả shape của một màn hình.

| # | Chức năng | Lớp | Nội dung |
|---|---|---|---|
| 1.1 | Danh sách danh mục | L1 | tên · tổng giá trị · lãi/lỗ hôm nay (%). Nhấn → `dispatch({type:"portfolio", id})` + chuyển view |
| 1.2 | Nút tạo danh mục | — | inline như `WatchlistSection` mở form thêm mã: đặt tên, xác nhận |
| 1.3 | Danh mục đang chọn | — | một đường viền accent, đúng quy ước "the one accent stroke a selected row is allowed" |
| 1.4 | Số vị thế | L1 | `12 mã` dưới tên, `text-micro text-ink-6` |
| 1.5 | Trạng thái dữ liệu | — | dot màu như `STATE_DOT` của watchlist: xanh = đủ dữ liệu, vàng = một số chỉ số đang thiếu lịch sử, xám = chưa có giao dịch |

Nếu chốt v1 chỉ một danh mục/người dùng thì 1.1 và 1.2 thu về một dòng duy nhất.
Đây là quyết định còn để ngỏ và nó đổi schema, nên quyết trước khi build.

---

## 2. View `portfolio` — cột chính

Thứ tự từ trên xuống là thứ tự người dùng hỏi: *tôi đang có gì → nó đi thế nào →
từng mã ra sao → nó tập trung tới đâu → nó rủi ro tới đâu → tôi ra được không →
nếu thị trường xấu thì sao*.

### 2.1 Dải KPI đầu trang — L1

Sáu số, `Card` + `Figure`, `tabular-nums`. Không số nào ở đây được phép refuse.

| # | Chỉ số | Ghi chú hiển thị |
|---|---|---|
| 2.1.1 | Tổng giá trị thị trường | VND, phiên đóng gần nhất; kèm as-of |
| 2.1.2 | Tổng vốn đã bỏ ra | VND, từ ledger |
| 2.1.3 | Lãi/lỗ chưa thực hiện | VND + %, `deltaClass()` |
| 2.1.4 | Lãi/lỗ đã thực hiện | VND, luỹ kế từ ledger |
| 2.1.5 | Cổ tức đã nhận | VND, luỹ kế |
| 2.1.6 | Thay đổi phiên gần nhất | VND + %, `signedPercent()` |

Mọi ô mang **as-of của phiên** ở chân card. Nếu phiên gần nhất cũ hơn hôm nay,
nói ra ngày đó — không hiện "hôm nay".

### 2.2 Chart hiệu suất — L1 (đường), L2 (drawdown)

| # | Chức năng | Lớp | Ghi chú |
|---|---|---|---|
| 2.2.1 | Đường giá trị danh mục theo thời gian | L1 | tính từ ledger + giá đóng phiên |
| 2.2.2 | Đường TWR của danh mục | L1 | % luỹ kế, đây là đường so được với benchmark |
| 2.2.3 | Đường VNINDEX chồng lên | L1 | cùng gốc 0%, `--chart-5` |
| 2.2.4 | Chuyển kỳ | — | 1M · 3M · 6M · 1Y · YTD · ALL, pill row |
| 2.2.5 | Dải drawdown dưới chart | L2 | vùng âm dưới đỉnh cũ; **ẩn kèm câu giải thích** khi lịch sử < 250 phiên |
| 2.2.6 | Đánh dấu ngày có giao dịch | L1 | tick nhỏ trên trục; hover hiện mua/bán |
| 2.2.7 | Đánh dấu ex-date quyền | L1 | tick khác màu; hover hiện loại quyền. Đây là chỗ `price_basis` mixed phải nói ra |
| 2.2.8 | Cảnh báo chuỗi có lỗ hổng | — | nếu chuỗi phiên bị thiếu ngày, nói ra thay vì nối thẳng hai điểm cách nhau bảy tháng |

**Cần chart library.** Hiện chỉ có `Sparkline` SVG viết tay
(`inspector.tsx:699`, viewBox 320×100) — không đủ cho trục thời gian, hai đường
chồng nhau, tooltip và marker. Đây là dependency mới cần đồng ý.

### 2.3 Bảng vị thế — L1

Khuôn: `view-board.tsx` — `<table>`, `Th`/`Td`, `PER_PAGE`, `BoardRow`.

| Cột | Lớp | Nội dung |
|---|---|---|
| Mã + tên | L1 | `Figure` in đậm + tên truncate, như `BoardRow` |
| Số lượng | L1 | cổ phiếu |
| Giá vốn BQ | L1 | VND/cp, **đã điều chỉnh quyền** |
| Giá hiện tại | L1 | VND, `deltaClass` theo % phiên |
| Giá trị | L1 | VND |
| Tỷ trọng | L1 | % + `Bar` mini để mắt so được |
| Lãi/lỗ | L1 | VND + %, `deltaClass` |
| Đóng góp | L1 | `w_i × r_i` — mã này đóng bao nhiêu vào biến động kỳ này |
| Phiên để thoát | L1 | giá trị vị thế / ADTV 20 phiên |
| Cờ trạng thái | L1 | chip nhỏ: `đang limit-lock` · `ngoài Universe` · `room ngoại đầy` · `thiếu lịch sử` |

Tương tác:

| # | Chức năng |
|---|---|
| 2.3.1 | Nhấn dòng → mở inspector tab `portfolio` cho vị thế đó (§5) |
| 2.3.2 | Sắp xếp theo mọi cột số |
| 2.3.3 | Nút thêm giao dịch trên đầu bảng → overlay §4 |
| 2.3.4 | Menu ngữ cảnh mỗi dòng: thêm giao dịch cho mã này · xem lịch sử giao dịch · thêm vào watchlist · hỏi AI về vị thế này |
| 2.3.5 | Phân trang khi > 15 dòng, y như board |
| 2.3.6 | Hàng tổng cố định ở chân bảng: tổng giá trị, tổng tỷ trọng 100%, tổng lãi/lỗ |

Cờ `ngoài Universe` là chỗ quyết định "mở theo lớp" hiện ra: mã đó vẫn có giá,
vẫn có biến động và drawdown, nhưng **không có percentile** — và bảng phải nói ra
sự khác biệt đó chứ không để ô trống.

### 2.4 Panel cấu trúc danh mục — L1

| # | Chức năng | Nội dung |
|---|---|---|
| 2.4.1 | Vòng phân bổ theo mã | donut, `--chart-1..5` cuộn vòng; nhóm phần đuôi thành "khác" |
| 2.4.2 | Phân bổ theo ngành ICB | thanh ngang xếp giảm dần, dùng `Bar` |
| 2.4.3 | Phân bổ theo sàn | HOSE/HNX/UPCOM — quan trọng vì biên độ mỗi sàn khác nhau |
| 2.4.4 | HHI + số vị thế hiệu dụng | một số + một câu: "12 mã nhưng tập trung như 4,3 mã" |
| 2.4.5 | Ba vị thế lớn nhất chiếm bao nhiêu | % — câu người dùng hỏi nhiều nhất về tập trung |
| 2.4.6 | Tiền chưa đầu tư | nếu ledger có nạp/rút thì hiện; nếu không thì bỏ cột này |

### 2.5 Panel rủi ro — L2, đây là panel phải trung thực nhất

Mọi dòng ở đây dùng `FigureRow` (`components/alpha/analysis/figure-row.tsx`) —
không viết component mới. Nó đã mang đủ: value, unit, kind, source,
interpretation, as-of, số phiên đã dùng, cửa sổ, badge health, câu reason, và
`—` khi refused.

| # | Chỉ số | Sàn | Kèm theo |
|---|---|---|---|
| 2.5.1 | Biến động danh mục (annualized) | 60 phiên | khoảng tin cậy |
| 2.5.2 | Max drawdown | 250 | so với `E[MDD] ≈ 1,25σ√T` — cho drawdown một bối cảnh thay vì kịch tính |
| 2.5.3 | Drawdown hiện tại + số phiên dưới đỉnh | 250 | |
| 2.5.4 | Beta vs VNINDEX | 250 | `δ̂` shrinkage |
| 2.5.5 | Tương quan trung bình trong danh mục | ~300 | `δ̂`; `δ̂` gần 1 chính là câu "dữ liệu không đỡ được ma trận này" |
| 2.5.6 | Đóng góp rủi ro từng vị thế | như 2.5.5 | thanh ngang; **đây là thứ thay chỗ của optimizer** và nó chỉ đọc hiện trạng |
| 2.5.7 | Sharpe / Sortino | 250 để tính | **bắt buộc hiện CI**. Ở dữ liệu thực tế CI thường chứa 0 — và đó là câu phải hiện, không phải con số |
| 2.5.8 | VaR / CVaR historical | 250 tối thiểu | phải hiện N; dưới 500 nói rõ suy luận yếu |

Quy tắc hiển thị cho cả panel:

- Refused thì hiện `—` **kèm câu lý do**, không hiện `0`, không ẩn dòng. Lý do
  đã được dịch sẵn ở `lib/signal-issues.ts`; UI không bao giờ in reason code thô.
- Không đặt bất cứ thứ gì trong panel này sau một cú nhấn để mở. Một figure
  degraded là bằng chứng về sự trung thực; bằng chứng phải hover mới thấy là
  bằng chứng đang bị giấu.
- Khi **cả** panel refuse vì lịch sử ngắn, hiện một khối giải thích duy nhất ở
  đầu panel thay vì tám dòng `—` giống nhau — dùng `SampleDataNote` làm khuôn
  giọng điệu.

### 2.6 Panel thanh khoản và trạng thái giao dịch — L1

| # | Chức năng |
|---|---|
| 2.6.1 | Số phiên để thoát toàn bộ danh mục ở 20% ADTV |
| 2.6.2 | Vị thế khó thoát nhất — xếp hạng theo giá trị/ADTV |
| 2.6.3 | Mã đang limit-lock hôm nay, đánh dấu rõ **không giao dịch được** |
| 2.6.4 | Khoảng cách tới trần/sàn từng mã — `text-ceiling` / `text-floor` |
| 2.6.5 | Room ngoại còn lại của từng mã |
| 2.6.6 | Nhắc T+2: bán hôm nay thì tiền về chiều T+2 |

### 2.7 Panel kịch bản — L3

Không gắn probability. Mỗi kịch bản nêu giả định của nó ngay cạnh kết quả.

| # | Chức năng | Nội dung |
|---|---|---|
| 2.7.1 | Shock đồng loạt | slider −5% / −10% / −20% → danh mục mất bao nhiêu VND, có tính bước giá và biên độ mỗi sàn |
| 2.7.2 | Sensitivity một vị thế | "nếu mã lớn nhất mất X%" → ảnh hưởng tổng |
| 2.7.3 | Historical replay | chọn một đoạn quá khứ → áp đúng return đã xảy ra của chính các mã đang nắm |
| 2.7.4 | Thanh khoản xấu đi | ADTV giảm một nửa → số phiên để thoát tăng lên bao nhiêu |
| 2.7.5 | Nhãn "không giao dịch được" | khi kịch bản đụng mã đang limit-lock, không được tính như thể khớp ở giá đóng cửa |

### 2.8 Dải "Hỏi AI về danh mục" — cuối trang

Khuôn có sẵn: `AskAboutSession` (`view-board.tsx:517`) — `dispatch({type:"ask"})`
**fill composer và để người dùng tự bấm gửi**, không gửi thay họ. Giữ đúng hành vi
đó.

Ba câu gợi ý, sinh từ chính số liệu đang hiện:

- "Danh mục của tôi đang tập trung ở đâu và điều đó có ý nghĩa gì?"
- "Vì sao danh mục tôi giảm mạnh hơn VN-INDEX phiên nay?"
- "Nếu thị trường giảm 10% thì danh mục tôi chịu ảnh hưởng thế nào?"

---

## 3. Trạng thái rỗng và trạng thái chờ

| # | Trạng thái | Hiển thị |
|---|---|---|
| 3.1 | Chưa có danh mục | một khối mời tạo, nêu rõ nhập tay và vì sao (cost basis đúng qua các đợt chia) |
| 3.2 | Có danh mục, chưa có giao dịch | form nhập giao dịch đầu tiên ngay tại chỗ, không bắt đi qua overlay |
| 3.3 | Có giao dịch, chưa đủ lịch sử | L1 hiện đầy đủ; panel rủi ro hiện một khối giải thích duy nhất, nói rõ cần bao nhiêu phiên và đang có bao nhiêu |
| 3.4 | Đang tải | text `Đang tải…` như board, không skeleton nhảy |
| 3.5 | Phiên gần nhất cũ | banner nói rõ ngày của phiên đang dùng |
| 3.6 | Có mã ngoài Universe | ghi chú một dòng: những mã nào không có percentile, và vì sao đó không phải nhận xét về doanh nghiệp |

---

## 4. Overlay nhập/sửa giao dịch

Overlay chứ không phải trang. Đây là đường duy nhất dữ liệu vào hệ thống, nên nó
phải nhanh và không mất dữ liệu khi nhập sai.

| # | Chức năng | Ghi chú |
|---|---|---|
| 4.1 | Chọn loại | Mua · Bán · Cổ tức tiền · Cổ tức cổ phiếu · Thưởng · Chia tách · Nạp tiền · Rút tiền |
| 4.2 | Ô mã | tái dùng `SymbolSearch` của inspector; cảnh báo mềm nếu ngoài Universe, **không chặn** |
| 4.3 | Ngày giao dịch | date picker; chặn ngày tương lai và ngày không phải phiên |
| 4.4 | Số lượng | cổ phiếu |
| 4.5 | Giá | VND/cp; gợi ý giá đóng phiên đó và cảnh báo nếu ngoài biên độ ngày đó |
| 4.6 | Phí + thuế | tách hai ô; mặc định từ settings |
| 4.7 | Ghi chú | tự do, một dòng |
| 4.8 | Xem trước tác động | ngay trong overlay: sau giao dịch này tỷ trọng và giá vốn thành bao nhiêu |
| 4.9 | Nhập nhiều dòng liên tiếp | lưu rồi giữ overlay mở với ô mã đã xoá — nhập 20 giao dịch không phải mở lại 20 lần |
| 4.10 | Sửa / xoá giao dịch | từ danh sách lịch sử; xoá thì tính lại toàn bộ chuỗi, không xoá mềm |
| 4.11 | Cảnh báo bán quá số đang có | chặn cứng, kèm số đang có tại ngày đó |
| 4.12 | Nhắc quyền chưa nhập | nếu store có ex-date đã confirmed cho mã đang giữ mà ledger không có dòng tương ứng — đây là nguồn sai cost basis phổ biến nhất |

### 4b. Danh sách lịch sử giao dịch

Bảng riêng, mở từ menu dòng vị thế hoặc từ nút trên đầu bảng: ngày · loại · mã ·
số lượng · giá · phí · giá trị · ghi chú · sửa/xoá. Lọc theo mã và theo kỳ.

---

## 5. Inspector — tab `portfolio`

Cùng cơ chế điều kiện như tab `sources` và `news`: chỉ hiện khi có chủ đề. Ở đây
chủ đề là một vị thế đang mở (`state.portfolioPosition !== null`).

| # | Chức năng | Lớp |
|---|---|---|
| 5.1 | Đầu tab: mã, tên, sàn, giá hiện tại | L1 |
| 5.2 | Vị thế của tôi: số lượng, giá vốn, giá trị, tỷ trọng, lãi/lỗ | L1 |
| 5.3 | Lịch sử giao dịch của mã này | L1 |
| 5.4 | Cổ tức đã nhận từ mã này | L1 |
| 5.5 | Sparkline giá — tái dùng component có sẵn | L1 |
| 5.6 | Signal Field của mã, dùng `FigureRow` | L1/L2 |
| 5.7 | Trạng thái biên độ hôm nay + room ngoại | L1 |
| 5.8 | Đóng góp của mã vào rủi ro danh mục | L2 |
| 5.9 | Nút "Hỏi AI về vị thế này" | — |
| 5.10 | Nút thêm giao dịch cho mã này | — |

Khi không có vị thế nào đang mở nhưng view đang là portfolio, tab hiện **tóm tắt
cấp danh mục**: KPI, HHI, ba vị thế lớn nhất — để inspector không rỗng khi người
dùng vừa mở view.

---

## 6. Hỏi đáp AI trong danh mục

Đây là phần trả lời "user tương tác với AI ra sao". Không có surface chat thứ hai
— vẫn là `ChatView` và `Composer` hiện có, chỉ thêm ngữ cảnh.

| # | Chức năng | Ghi chú |
|---|---|---|
| 6.1 | Chip ngữ cảnh danh mục trên composer | giống `contextSymbol` đang có: khi đang ở view portfolio, composer mang ngữ cảnh danh mục. Bỏ được bằng một cú nhấn |
| 6.2 | Từ bảng vị thế hỏi về một mã | `dispatch({type:"ask"})` fill sẵn câu, người dùng bấm gửi |
| 6.3 | Rail bằng chứng trong câu trả lời | tool call portfolio hiện như tool call hiện tại, có nhãn riêng: "Không có số" / "Ngoài phạm vi" đã có sẵn vốn từ |
| 6.4 | Figure trong câu trả lời truy được về nguồn | mọi số trong câu trả lời phải có một tool call tương ứng trong trace |
| 6.5 | Tab "Nguồn" cho câu trả lời về danh mục | tái dùng `sources` tab; với portfolio thì nguồn là field + as-of, không phải URL |
| 6.6 | Câu trả lời nói rõ giới hạn | khi người dùng hỏi về giao dịch cụ thể ("lô mua tháng 3 của tôi"), AI **không** trả lời được vì chỉ thấy figure đã tính — và phải nói ra điều đó, không đoán |
| 6.7 | Khi người dùng hỏi thẳng "nên làm gì" | trả lời rằng quyết định là của họ, rồi đưa mức và hệ quả. Đây là luật prompt hiện tại, và nó phải chặt hơn khi có số liệu thật về vị thế thật |
| 6.8 | Không có nút nào sinh chỉ thị | không "gợi ý tái cân bằng", không "tỷ trọng đề xuất". Nút không tồn tại thì không có gì để trôi |

### Cái AI đọc được và không đọc được — phải nói ra trên UI

Prompt hiện tại nói thẳng "Bạn KHÔNG đọc được... danh mục theo dõi của họ". Sau
thay đổi này, câu đó đổi — và UI nên có một chỗ nói rõ ranh giới mới: AI đọc
được các con số cấp danh mục đã tính, **không** đọc được sổ giao dịch. Đặt trong
settings hoặc trong một popover cạnh chip ngữ cảnh.

---

## 7. Settings — mục "Danh mục"

| # | Chức năng |
|---|---|
| 7.1 | Phí giao dịch mặc định (%) và thuế bán (%) |
| 7.2 | Benchmark mặc định — VNINDEX hoặc VN30 |
| 7.3 | Kỳ mặc định của chart |
| 7.4 | Xoá danh mục, có xác nhận gõ tên |
| 7.5 | Xuất giao dịch ra CSV — người dùng lấy lại được dữ liệu họ nhập |
| 7.6 | Câu giải thích AI đọc được gì về danh mục |

---

## 8. Component: cái tái dùng, cái phải viết mới

### Tái dùng nguyên, không sửa

| Component | Ở đâu | Dùng cho |
|---|---|---|
| `Card`, `PanelCard`, `Eyebrow`, `Figure`, `Bar`, `QuietLine`, `SampleDataNote` | `shell/primitives.tsx` | mọi panel |
| `deltaClass`, `signedPercent`, `price` | `shell/primitives.tsx` | mọi số có dấu |
| `FigureRow` | `alpha/analysis/figure-row.tsx` | **toàn bộ panel rủi ro** |
| `Th`, `Td`, `PageButton` | `shell/view-board.tsx` | bảng vị thế |
| `Sparkline` | `shell/inspector.tsx:699` | inspector vị thế |
| `SymbolSearch` | `shell/inspector.tsx` | ô mã trong overlay giao dịch |
| `STATE_DOT`, `stateSentence` | `shell/analysis-state.ts` | dot trạng thái ở sidebar |
| `formatFieldValue`, `unitLabel` | `lib/units.ts` | mọi field |
| `signal-issues.ts` | `lib/` | dịch reason code sang câu |
| `AskAboutSession` | `shell/view-board.tsx:517` | khuôn cho dải hỏi AI |

### Phải viết mới

| Component | Ghi chú |
|---|---|
| `view-portfolio.tsx` | lấy `view-board.tsx` làm khuôn |
| `portfolio-section.tsx` | sidebar, khuôn `watchlist-section.tsx` |
| `transaction-dialog.tsx` | overlay, khuôn `settings-dialog.tsx` |
| `portfolio-tab.tsx` | inspector tab |
| `equity-curve.tsx` | **cần chart library** |
| `allocation-donut.tsx` | **cần chart library** hoặc SVG tự vẽ |
| `drawdown-strip.tsx` | **cần chart library** |
| `scenario-panel.tsx` | slider + số, không cần chart |

---

## 9. Endpoint UI cần

Tên chỉ mang tính mô tả hình dạng; router mỏng + service giữ logic theo quy ước
`src/stocks/<domain>/`.

| Method | Đường | Trả về |
|---|---|---|
| GET | `/portfolios` | danh sách + tổng giá trị + lãi/lỗ phiên |
| POST | `/portfolios` | tạo |
| PATCH · DELETE | `/portfolios/{id}` | đổi tên · xoá |
| GET | `/portfolios/{id}/holdings` | vị thế phái sinh từ ledger, kèm giá và cờ trạng thái |
| GET | `/portfolios/{id}/summary` | dải KPI L1 |
| GET | `/portfolios/{id}/performance?period=` | chuỗi giá trị + TWR + benchmark + marker giao dịch/ex-date |
| GET | `/portfolios/{id}/structure` | phân bổ theo mã/ngành/sàn + HHI |
| GET | `/portfolios/{id}/risk` | field L2, **mỗi field mang health + reason + as-of + số phiên** |
| GET | `/portfolios/{id}/liquidity` | phiên để thoát, limit-lock, biên độ, room |
| POST | `/portfolios/{id}/scenario` | L3, nhận giả định trả kết quả |
| GET · POST | `/portfolios/{id}/transactions` | lịch sử · thêm |
| PATCH · DELETE | `/portfolios/{id}/transactions/{txId}` | sửa · xoá |
| GET | `/portfolios/{id}/transactions/export` | CSV |

`/risk` phải trả **cùng shape** với field của Analysis để `FigureRow` dùng lại
được không cần adapter. Nếu shape lệch thì sẽ có hai vốn từ health trên một sản
phẩm.

---

## 10. Việc còn để ngỏ, chặn phần nào

| Việc | Chặn |
|---|---|
| Chart library nào | 2.2, 2.4.1, 2.5 phần biểu đồ |
| Multi-portfolio hay một danh mục | §1, và `portfolio_id` trong schema |
| ~~Độ sâu lịch sử~~ | **Đã giải, 2026-08-24.** `provider_snapshots` có 2.527 phiên/mã; 28/30 mã Universe ≥970 phiên. **L2 có số thật.** Nhưng TCX và VPL (mã mới) sẽ `refused` — nên §2.5 phải xử lý được **trạng thái hỗn hợp**: một phần danh mục có số, một phần không, trong cùng một panel. Khối giải thích chung ở §3.3 chỉ dùng khi *cả* panel refuse, không phải mặc định |
| Lane nào nhường phần trong envelope $45 | §6 |
