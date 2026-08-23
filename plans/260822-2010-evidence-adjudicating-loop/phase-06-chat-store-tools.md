---
phase: 6
title: "Chat đọc store qua hai tool đã dựng"
status: implemented
---

# Phase 6 — Chat đọc store qua hai tool đã dựng

## Bằng chứng: một lượt thật, đo được

Lượt `a81c94f1-5f94-4f07-92fa-11c607de2324`, 2026-08-22 20:42 ICT, prompt `Phân tích HPG`,
`complete` sau 25.653 ms, **3 lời gọi `web_search`**, 15 nguồn.

Câu trả lời khá tốt về nội dung: doanh thu Q2/2026 55.557 tỷ, LNST 6.424 tỷ, biên gộp ~19%,
Dung Quất 2, sự kiện ~1,34 tỷ cổ phiếu bổ sung lưu hành, giá đóng 21.700 phiên 21/08.

Nhưng **không con số nào đến từ store.** Nguồn là investing.com, cafef, vietstock, một PDF
broker và 3 video YouTube. Store có đúng phiên 21/08 đó trong `stock_daily_ohlcv` và
`provider_snapshots`, đã chuẩn hoá, đã ghim `price_basis` — và không được đọc.

Hệ quả đo được, không phải suy đoán:

- **Không phép so sánh nào.** Không phân vị thanh khoản, không sụt giá so với mức kỳ vọng,
  không xếp hạng động lượng, không dòng tiền ngoại. Đó là bài tổng hợp tin, không phải phép đo.
- **Không tái lập.** Hỏi lại mai ra bộ nguồn khác, có thể ra số khác.
- **Một con số sai đã lọt qua** — xem Phase 7.

Lý do là `agent/toolsets.py`: chat chỉ có `web` và `memory`. Bất biến `1e7b936` là có chủ đích,
nhưng nó được viết khi **không có tool nào đọc store an toàn**. Sau Phase 3 thì có hai.

## Thay đổi

### `agent/toolsets.py`

Thêm `signals` vào tập toolset lane chat chọn. Không tool mới — đúng hai tool của Phase 3.

Nhưng chat khác lane Analysis ở một điểm bắt buộc: **không có `symbol` trong `ToolContext`**.
Lane Analysis biết mã vì Run khoá bởi `(symbol, trading_day)`; chat thì mã đến từ câu người
dùng gõ.

Nên chat cần chữ ký khác:

```
get_field(symbol: str, field_id: str)
```

`symbol` **được** là argument ở đây, và phải qua `validate_symbol` + kiểm tư cách Universe
(`stocks/universe.py`) — mã ngoài Universe trả một câu model đọc được, không raise. `trading_day`
vẫn **không** là argument: nó là phiên gần nhất đã đóng, lấy từ `trading_day.latest_trading_day`,
vì một argument cho phép model đọc một phiên chưa đóng.

Ghi vào docstring vì sao hai lane hai chữ ký: ở lane Analysis, một `symbol` argument là đường
để model đọc mã khác; ở chat, mã **là** yêu cầu của người dùng.

### `agent/prompt/sections.py` — HONESTY phải viết lại

`sections.py:100` hiện tại:

> *"Bạn KHÔNG đọc được bất cứ dữ liệu nào của hệ thống này. Không giá, không khối lượng, không
> báo cáo tài chính, không chỉ báo, không danh mục theo dõi, không kết quả phân tích."*

Sau Phase 6 câu đó **sai**. Để nguyên là dạy model nói dối về chính năng lực của nó.

Viết lại thành ranh giới đúng, không phải phủ định toàn bộ:

- Đọc được: các Signal Field đã đăng ký cho một mã trong Universe, ở phiên gần nhất đã đóng.
- Không đọc được: bảng giá người dùng đang xem, danh mục, tin tức, báo cáo tài chính thô.
- **Số của store thắng số của web khi hai bên khác nhau, và sự khác nhau phải được nói ra.**
- Vẫn không được bịa: con số không tra được trong lượt này thì không biết.

`sections.py:131` (*"Bạn có năm công cụ, và chỉ năm công cụ đó"*) thành bảy, và phải nói rõ
hai tool mới đọc **dữ liệu của hệ thống**, khác hẳn hai tool web đọc **thế giới bên ngoài**.

Bump `PROMPT_VERSION` `2.2.0` → `2.3.0`.

### Thứ tự trong câu trả lời

Contract phải yêu cầu tách hai khối, vì hai loại bằng chứng có tư cách khác nhau:

1. **Từ dữ liệu hệ thống** — figure kèm `asOf`, kèm `health`. Đây là phần tái lập được.
2. **Từ tin tức** — nhãn rõ là nguồn ngoài chưa đối chiếu.

Trộn hai khối là thứ làm người đọc không biết con số nào kiểm được.

## Ngân sách

Lane Turn, không phải lane Analysis. `TURN_INPUT_TOKENS = 100_000` nên hai tool store thêm
vào không chạm trần: một figure 730 byte, `list_fields` cả catalog ~2KB.

`MAX_EXTERNAL_TOOL_CALLS = 6` (`loop.py:275`) **không** áp cho hai tool mới — chúng đọc
Postgres nội bộ. Đây là chỗ trần phải tách theo lớp tool thay vì một `EXTERNAL_TOOLS`
frozenset, đúng như Phase 4 làm cho lane Analysis.

`MAX_TOOL_ROUNDS = 4` giữ nguyên ở lane chat: lượt HPG thật dùng **1 round** với 3 call song
song. Thêm hai tool store không đổi hình dạng đó.

## Validation

- Test: `get_field` với mã ngoài Universe trả câu model đọc được, không raise.
- Test: `get_field` không nhận `trading_day` trong schema.
- Test: prompt không còn câu "KHÔNG đọc được bất cứ dữ liệu nào"; `PROMPT_VERSION` đã bump.
- Test: một Turn dùng cả `web_search` và `get_field` → chỉ kết quả `web_search` bị bọc
  `<untrusted_tool_result>`, kết quả `get_field` thì không (Phase 3 đã đổi sang gắn theo
  thuộc tính).
- Đo lại đúng prompt `Phân tích HPG` và so với lượt `a81c94f1` ở trên.
- `make test` pass.

## Risk / rollback

Rollback là bỏ `signals` khỏi tập toolset chat — một dòng, và `toolsets.py` từ chối tên lạ nên
không có đường nào một Turn chọn được nó sau đó.

**Đây là đảo một quyết định đã ghi** (`1e7b936`: *"a general assistant that reads none of our
data"*). Lý do đảo phải nằm trong commit message, không chỉ trong plan này: quyết định đó
được viết khi không có đường đọc store nào có `health` và `asOf` đi kèm; Phase 3 tạo ra đường
đó.

Rủi ro thật: chat trở thành bề mặt tư vấn đầu tư. Lượt HAG thật (`Tôi đang giữ 45% HAG giá
12k...`) cho thấy model **đã** khuyên cụ thể — *"chốt/bán từng phần để hạ tỷ trọng về khoảng
20–30%"* — dù `INVARIANTS` nói nó không phải người tư vấn đầu tư. Thêm số liệu thật vào sẽ làm
lời khuyên đó **nghe** đáng tin hơn mà không **trở nên** đáng tin hơn. Ranh giới tư vấn là
quyết định sản phẩm còn mở, và nó nên được chốt trong Phase 6 chứ không để trôi.


## Đã làm (2026-08-23)

`CHAT_TOOLSETS = ("web", "memory", "signals")`. Cổng import cũ — dòng từ chối `signals` — bị bỏ
**có chủ đích**, và lý do nằm trong docstring của `toolsets.py` và trong commit, không chỉ ở
đây. Cái còn giữ là: selection vẫn được **viết ra**, nên bundle thứ tư thêm mai không tới được
hội thoại cho tới khi tuple này gọi tên nó.

**Một registration, hai chữ ký.** `registry` chỉ cho một tên thuộc một toolset, nên không có
đường nào hai lane có hai schema cho cùng tên `get_field`. Cách giải: schema có `symbol` là
thuộc tính **optional**, và handler phân giải theo thứ tự — `ToolContext.symbol` có thì nó
thắng, và một argument nêu mã **khác** bị từ chối. Kết quả là ranh giới lane Analysis giờ được
**cưỡng chế bởi handler** thay vì chỉ được *không nhắc tới* trong schema, tức là chặt hơn bản
plan mô tả: một schema là điều model được *bảo*, không phải điều harness *làm*.

`trading_day` vẫn không phải argument ở lane nào. Lane chat lấy phiên gần nhất đã đóng từ
`latest_trading_day`; mã ngoài Universe, mã sai hình dạng, store chưa có phiên nào — cả ba trả
`{"error": "cannot_read", "detail": ...}`, **không** raise, và **không** mang `fieldId` nên
`analysis_loop._figure_in` không thể gấp một lời từ chối thành figure.

`PROMPT_VERSION` `2.2.0` → `2.3.0`. Ba khối đổi:

- **HONESTY** viết lại từ "không đọc được bất cứ dữ liệu nào" thành ranh giới đúng: đọc được
  Signal Field cho mã trong Universe ở phiên gần nhất đã đóng; không đọc được bảng giá, danh
  mục, tin tức, BCTC thô. Thêm luật **số của store thắng số của web** và sự khác nhau phải nói
  ra — đây là câu trả lời cho câu hỏi mở số 2 của plan.
- **TOOLS** năm → **tám**, chia ba loại (đọc thế giới ngoài · đọc dữ liệu hệ thống này · đọc
  chính người dùng). Loại là điều quan trọng nhất về một tool, và một danh sách phẳng tám dòng
  sẽ dạy model rằng chúng thay thế được cho nhau.
- **UNTRUSTED** nhận luật `check_price_claim` của Phase 7, câu nói rõ cổng đó **chỉ phủ giá**,
  và yêu cầu tách hai khối bằng chứng trong câu trả lời.

**Ranh giới tư vấn — câu hỏi mở số 1, đã chốt.** `INVARIANTS` giờ nói cụ thể: được nêu **các
mức và hệ quả** (tỷ trọng tập trung tới đâu, giá cách vùng nào bao xa, lỗ giả định cỡ nào,
thanh khoản đủ ra trong bao lâu); **không** ra chỉ thị hành động cho một vị thế cụ thể — không
"bán đi", không "chốt một phần", không tỷ trọng mục tiêu, không mức vào/ra. Người dùng hỏi
thẳng thì nói quyết định là của họ rồi đưa mức và hệ quả. Lý do ghi ngay trong prompt: số liệu
thật làm lời khuyên *nghe* đáng tin hơn mà không *trở nên* đáng tin hơn, nên ranh giới chặt lại
khi đọc được store, không lỏng ra.

**Trần external tách theo lớp tool.** `loop.py::EXTERNAL_TOOLS` frozenset bị bỏ;
`MAX_EXTERNAL_TOOL_CALLS` giờ chỉ tính các tool có `registry.reads_external` bật. Ba tool
`signals` đọc Postgres trong deployment — tính chúng vào một trần tồn tại vì search tốn tiền và
trang web là của người khác sẽ tiêu hạn mức web cho bằng chứng không có tính chất nào trong hai.
`MAX_TOOL_ROUNDS = 4` giữ nguyên.

Test: `tests/test_agent_signal_tools.py` (+9 case cho hai chữ ký), `tests/test_agent_prompt.py`
(+1, và `unverified`/`Universe` rời khỏi `VANISHED_VOCABULARY` kèm lý do),
`tests/test_agent_loop.py` (+2: store read không bị tính vào trần external, và trong một Turn
dùng cả hai loại thì chỉ kết quả web bị bọc).

**Chưa làm: đo lại `Phân tích HPG` thật.** Cần một lượt thật trên deployment có store đầy, so
với lượt `a81c94f1`. Đó là phép đo, không phải code, và nó là việc kế tiếp.
