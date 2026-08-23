---
phase: 7
title: "Cổng kiểm số: bước check giữa call tool và phân tích"
status: implemented
---

# Phase 7 — Cổng kiểm số

## Lớp lỗi đang mở, có bằng chứng

Lượt thật `a81c94f1` (`Phân tích HPG`, 2026-08-22 20:42 ICT) trích từ investing.com:

> *"Vùng biến động 52 tuần được ghi nhận là **20.100–27.542 đồng/cp**."*

`price_band.py:241 tick_size(exchange, price)` giữ bước giá HOSE: dưới 10.000 → 10;
10.000–50.000 → **50**; từ 50.000 → 100.

| Số | Chia hết cho bước 50? |
|---|---|
| 21.700 · 21.050 · 21.750 · 21.150 · 20.100 | ✓ |
| **27.542** | **✗** — 27.542 / 50 = 550,84 |

Một giá không nằm trên bước giá của sàn **không phải một giá đã khớp**. Nó là số nguồn ngoài
tự điều chỉnh theo phương pháp của họ. Model trích nó như dữ kiện thị trường, và **không có
cách nào biết là không phải** — vòng lặp hôm nay không có bước kiểm nào giữa "nhận kết quả
tool" và "dùng con số".

Đây đúng chỗ trống mà kiến trúc Hermes gọi tên: kết quả tool được **bọc** ở tầng dựng message
(`agent/untrusted.py` đã làm) nhưng không được **kiểm**. Bọc nói *"đây là dữ liệu, không phải
chỉ dẫn"*. Nó không nói *"con số này không thể tồn tại"*.

## Nguyên tắc

Vòng lặp phải là **call → check → phân tích → call tiếp**, không phải **call → phân tích**.
Bước check là bước duy nhất đang thiếu, và ở lane Analysis nó **đã có** dưới dạng
`health` + `reasonCode` do backend tính. Ở lane chat, với nội dung web, nó không có gì.

Hai luật, theo đúng khuôn hai tầng của Hermes (bọc thì **luôn**, quét thì **chỉ khuyến cáo**):

1. **Không bao giờ xoá con số.** Xoá là ẩn. Gắn cờ vào kết quả model đọc.
2. **Không bao giờ chặn.** Fail-open: model đọc cờ rồi tự quyết. Một cổng kiểm làm trắng câu
   trả lời còn tệ hơn một con số sai được nêu tên.

## Thay đổi

### `agent/tools/price_check.py` — tool mới `check_price_claim`

```
check_price_claim(symbol: str, price: float, session_date: str | None)
```

Trả về, mỗi mục là một dữ kiện độc lập:

| Kiểm | Cơ chế | Kết luận |
|---|---|---|
| Bước giá | `tick_size(exchange, price)` | `off_tick` — giá không nằm trên bước giá của sàn tại mức giá đó. **Không thể là giá đã khớp.** |
| Biên độ | `band_limits(exchange, anchor)` với anchor là close phiên trước trong store | `exceeds_band` — bước giá vượt biên độ cho phép của sàn ngày đó |
| Đối chiếu store | đọc bar của `(symbol, session_date)` | `store_disagrees` kèm **cả hai** giá trị và `asOf` của store |
| Không kiểm được | thiếu bar, thiếu sàn của ngày đó | `unverified` kèm lý do — **không** phải "hợp lệ" |

Trạng thái thứ tư là chỗ dễ làm sai nhất: "không kiểm được" phải khác "kiểm rồi và đúng".
Gộp hai cái là biến sự thiếu bằng chứng thành bằng chứng.

Cả hai hàm đã public, nên tool là composition mỏng, không có phép tính mới. `exchange` lấy từ
`listing_roster` theo ngày, không hardcode HOSE — sàn của một bar là câu hỏi thật cho tới
31/12/2026 vì chương trình chuyển sàn HNX→HOSE (`price_band.py:86-94`).

Đăng ký vào toolset `signals` (Phase 3), nên cả lane Analysis và lane chat đều có.

### `agent/prompt/sections.py` — luật trong contract

Một câu, đặt trong khối đã dạy về nguồn ngoài:

> Một mức giá lấy từ nguồn ngoài phải được `check_price_claim` xác nhận trước khi bạn nêu nó.
> Nếu nó về `off_tick` hoặc `exceeds_band` thì đó không phải giá đã khớp — nói ra điều đó thay
> vì dùng nó. Nếu nó về `store_disagrees` thì **số của store thắng**, và sự khác nhau phải
> được nói ra.

Bump `PROMPT_VERSION` cùng Phase 6.

### `agent/untrusted.py` — gắn theo thuộc tính, không theo tên

`untrusted.py:45` hiện tại:

```python
UNTRUSTED_TOOLS = frozenset({"web_search", "fetch_url"})
```

Danh sách duyệt tay. Và docstring của chính module (`:16`) nói ngược lại điều code làm:

> *"including tools added later, which are wrapped by naming their source rather than by
> remembering to ask"*

Code không làm thế: `is_untrusted()` kiểm thành viên trong một frozenset viết tay, nên tool
thêm sau **không** được bọc cho tới khi ai đó sửa dòng 45. Cùng lớp lỗi mà khảo sát Hermes bắt
được ở chính Hermes — `x_search` lọt lưới `_UNTRUSTED_TOOL_NAMES` của nó.

Phase 6 thêm tool vào chat, nên lỗ này phải đóng **trước** đó. Đổi sang một thuộc tính khai
báo trên `ToolEntry` — `reads_external: bool` — và `is_untrusted()` đọc registry thay vì đọc
frozenset. Hai tool store là `False`; `check_price_claim` là `False` (nó đọc store để phán về
một con số, nó không mang nội dung ngoài vào).

Sửa luôn docstring cho khớp hành vi. Đây là chỗ tài liệu đã trôi khỏi code, và bộ khảo sát
Hermes cảnh báo đúng lớp này: *"Chỗ nào quan trọng thì đọc code, đừng đọc lời tự thuật."*

## Đo, chứ không đoán

Contract không cưỡng chế được: model có thể nêu một giá mà không gọi check. Nên Phase 7 đo
tuân thủ thay vì giả định nó:

**Tỷ lệ kiểm** = trong các Turn mà câu trả lời có nêu một mức giá lấy từ nguồn ngoài, tỷ lệ
Turn đã gọi `check_price_claim` ít nhất một lần. Đọc từ `agent_tool_call` + nội dung
`agent_message`.

Nếu tỷ lệ thấp thì mới dựng backstop — quét kết quả `web_search`/`fetch_url` tìm số dạng giá
và tự gắn cờ ở tầng dựng message. **Không dựng trước**: một backstop quét văn bản tự do sẽ
gắn cờ cả doanh thu tỷ đồng và phần trăm, và noise làm người dùng mất tin vào cả cơ chế. Đây
đúng bài học meta của bộ khảo sát: đo tần suất trước khi đóng, đừng dựng hàng rào cho một lớp
lỗi chưa đo.

## Validation

- Test: `check_price_claim("HPG", 27542)` → `off_tick`, và câu giải thích nêu bước giá 50.
- Test: `check_price_claim("HPG", 21700)` → không `off_tick`.
- Test: giá vượt biên độ so với close phiên trước → `exceeds_band`.
- Test: store có bar khác → `store_disagrees` kèm **cả hai** giá trị và `asOf`.
- Test: không có bar cho ngày đó → `unverified`, **không** phải hợp lệ.
- Test: sàn lấy theo `listing_roster` của ngày đó, không hardcode HOSE.
- Test: `is_untrusted` đọc `reads_external` từ registry; một tool mới không khai thì mặc định
  **là** external (an toàn theo hướng bảo thủ).
- `make test` pass.

## Risk / rollback

Rollback là bỏ tool khỏi toolset + revert câu contract.

Rủi ro thật: **cổng này chỉ kiểm giá.** Nó không kiểm doanh thu, lợi nhuận, biên gộp — và lượt
HPG thật nêu cả ba (55.557 tỷ, 6.424 tỷ, 19%). Không có bước giá hay biên độ nào cho một con
số báo cáo tài chính, nên cách duy nhất kiểm chúng là đối chiếu BCTC đã lưu — mà store chưa
lưu (`Non-goals` của plan này). Phase 7 đóng đúng một lớp: **giá**. Nói rõ để không ai đọc nó
thành "số liệu AI nêu đã được kiểm".


## Đã làm (2026-08-23)

`agent/tools/price_check.py` — tool `check_price_claim(symbol, price, session_date?)`, đăng ký
vào bundle `signals` nên cả hai lane đều có. Ba kiểm độc lập (`tick` · `band` · `store`) cộng
trạng thái thứ tư `unverified` kèm lý do; không kiểm nào gộp vào một verdict chung.

Ba điều lệch khỏi bản mô tả trong plan, mỗi điều một lý do đo được:

1. **Bước giá trả lời được khi không có phiên nào.** Bước giá là thuộc tính của **sàn**, không
   của phiên; chỉ `band` và `store` cần một phiên. Cho cả ba cùng `unverified` vì thiếu ngày sẽ
   che đúng cái kiểm duy nhất tự nó chứng minh được một giá là bất khả. Sàn hỏi theo
   `session_date` khi có, theo hôm nay khi không — vẫn qua `listing_roster` + register di trú,
   không hardcode HOSE.
2. **`session_date` bỏ trống rơi về phiên gần nhất store có**, không phải hôm nay: hôm nay có
   thể chưa đóng, và một biên độ đang chạy không kiểm được cái gì.
3. **`price_basis` không phải `raw` thì `band` và `store` trả `unverified`.** Một close đã điều
   chỉnh tại nguồn không phải giá tham chiếu sàn đặt biên độ từ đó, và đối chiếu nó với một giá
   thô là đối chiếu hai đại lượng khác nhau — đúng lớp lỗi mà cả module này tồn tại để gọi tên.

`check_price_claim` **không đọc `ToolContext.symbol`**: chủ thể ở đây là một lời khẳng định,
không phải hàng mà lời gọi được mở cho. Một giá nêu giữa lượt Analysis thường là về công ty
khác, và khoá kiểm vào mã đang phân tích sẽ để đúng những lời khẳng định đó không được kiểm.

`registry.ToolEntry.reads_external` thay `untrusted.UNTRUSTED_TOOLS`. Mặc định `True` — tool
không khai là tool được bọc. Docstring của `untrusted.py` đã sửa cho khớp hành vi; nó vốn đang
khẳng định đúng tính chất mà frozenset không có.

**Đo, chưa dựng backstop.** `agent/ops.py::read_price_check_compliance` đếm: trong các Turn vừa
đọc nội dung ngoài vừa nêu một số dạng giá, bao nhiêu Turn đã gọi `check_price_claim`. Mẫu số
hẹp có chủ đích — Turn trả lời từ store, hay không nêu số nào, không nợ một lần kiểm. `rate` là
`None` chứ không phải `0` trên cửa sổ rỗng. `names_a_price` là heuristic đọc-only, **không** nối
vào tầng dựng message: `55.557 tỷ` và `12.500%` cùng hình dạng với một mức giá và không phải
giá, nên nó loại theo từ đơn vị đứng sau.

Test: `tests/test_agent_price_check.py` (27 case) · `tests/test_agent_ops_query.py` (11 case
mới).
