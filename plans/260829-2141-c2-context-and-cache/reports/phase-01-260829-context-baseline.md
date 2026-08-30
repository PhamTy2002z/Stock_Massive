# Phase 01 — baseline context, đo được, chấm lại được không cần model

**Ngày:** 2026-08-29 · **Corpus:** `web-first-v1-final.json` (20 case, run 2026-08-29 11:13 UTC)
**Artifact replay:** `apps/api/golden/artifacts/context-replay-v1.json` (`golden.context-replay@1`)

## Cái được dựng

Một `ContextComposition` tám layer trên mọi `ConstructedContext`, và
`composition.total` **là** `estimated_tokens` — không phải một phép đo thứ hai
có thể lệch. Layer chia bằng cách quy nạp từng message: mỗi message được tính
đúng một lần, phần text của nó cắt thành các đoạn liền nhau phủ kín, và làm
tròn áp lên tiền tố cộng dồn nên các phần cộng lại đúng bằng tổng.

Reservation của `loop._call` (body pack + ba system note) đi qua **một** hàm
`_appended`, và `_construct` đọc lại chính hàm đó để trừ ceiling. Trước đây là
hai biểu thức chép tay. Giờ `SpendRequest.input_tokens == composition.total`
theo cấu tạo, không theo một assert chạy được hay không.

## Đối chiếu với ledger — replay có đúng cái đã xảy ra không

| | Ledger (`llm_call_usage`, 20 Turn) | Replay |
|---|---|---|
| Số lời gọi model | **78** | **78** |
| Token input đã reserve | **800.628** | **797.722** |
| Lệch | | **0,36%** |

0,36% có tên và có địa chỉ: **13 call bị từ chối trước khi dispatch**
(`MAX_EXTERNAL_TOOL_CALLS` cạn). Chúng vẫn nằm trong context — model đã xin gọi
và được cho biết chúng không chạy — nhưng câu `guidance` của guardrail đi trong
message và **không được persist ở đâu cả**. Đó là hằng số cố định theo lý do, nên
nó thiếu **cùng một lượng** trong mọi replay của mọi corpus và **triệt tiêu trong
một phép hiệu**. Report in ra `refused_calls` để chỗ hụt này được đọc, không phải
được phát hiện.

## Baseline: token đi đâu

**797.722 token dựng / 20 Turn · median 36.043/Turn · min 12.044 · max 70.974**

| Layer | Token | Tỷ trọng |
|---|---:|---:|
| `system_core` | 425.022 | **53,3%** |
| `tool_results` | 343.890 | **43,1%** |
| `domain_body` | 21.235 | 2,7% |
| `user_intent` | 2.729 | 0,3% |
| `study_headlines` | 2.560 | 0,3% |
| `system_dynamic` | 2.286 | 0,3% |
| `history` | 0 | 0% |
| `attachments` | 0 | 0% |

Ba điều đọc được ngay, và cả ba định hình phase sau:

1. **`system_core` là layer lớn nhất, và prune không chạm được nó.** 5.449
   token × 78 call. Nó không nhỏ đi được bằng cắt gọt — nó chỉ rẻ đi bằng
   **cache**. Đó là lý do phase 03–04 tồn tại, và là lý do một phép đo prune đơn
   thuần không thể chạm 20% nếu chỉ nhắm vào `tool_results`: cắt 43% đi một nửa
   mới được 21,5% tổng.
2. **`history` bằng 0 và điều đó đúng.** Corpus golden là 20 thread một Turn.
   Nghĩa là mọi thứ phase 02 tiết kiệm phải đến từ `tool_results` **trong cùng
   một Turn** — dedup giữa các call và trace handle — chứ không từ Turn cũ.
3. **`domain_body` 21.235 token đang nằm ở đuôi mỗi call.** Nó là 2,7% hôm nay
   và trả giá đầy đủ mỗi lần; phase 03 chuyển nó lên ngay sau core.

## Chi phí theo lượt gọi

| Lượt | n | median | max |
|---|---:|---:|---:|
| 0 (chưa có tool) | 20 | 5.501 | 5.513 |
| 1 | 20 | 7.860 | 10.953 |
| 2 | 19 | 11.644 | 18.546 |
| 3 | 13 | 13.973 | 19.452 |
| 4 | 6 | 17.397 | 19.999 |

Lượt 0 gần như là hằng số (5.501 ± 12) — nó **là** prompt. Từ lượt 1 trở đi mọi
thứ tăng lên là kết quả tool cộng dồn.

## Cache tự động: đã chạy sẵn, và đáng kể

Cùng 78 call đó, đọc từ `llm_call_usage`:

| | Token |
|---|---:|
| Fresh input | **489.106** |
| Cached read | **492.032** |
| Cache write | **0** |
| Tổng prompt thật | **981.138** |

**50,1% prompt đã được đọc từ cache** với `llm_prompt_cache_control_enabled=False`.
Route ghi cached read mà không ghi cache write. Con số này là input của phase 04
và nó nói trước một điều: quyết định "giữ `cache_control` tắt" đã đúng, và việc
cần làm ở phase 03 là làm cho **prefix ổn định hơn**, không phải bật cờ.

Ước lượng của harness (797.722) thấp hơn prompt thật (981.138) **18,7%** —
`CHARS_PER_TOKEN = 3` không đủ bi quan cho tiếng Việt trộn JSON. Không sửa ở
phase này: replay là **mẫu số của một phép hiệu**, và một mẫu số lệch cố định
không ảnh hưởng tới phần trăm giảm. Ghi lại để không ai đọc 797.722 như tiền.

## Tính xác định

`make golden-context-replay` chạy hai lần → **byte-identical**. Không network,
không model, không đồng hồ: ngày trong prompt được ghim ở `REPLAY_DATE`.

## Cái corpus có và không có

Có: câu hỏi, tên tool, arguments, **toàn văn** kết quả, danh sách kết quả hiển
thị (đọc từ `agent_message.content`, không từ `sources` đã dedup của artifact —
lấy từ đó là đã vô tình làm trước chính việc phase 02 đo).

Không có: account của runner, owner id, route, key. Corpus **có** chứa văn bản
trang web đã đọc, và trong đó có một địa chỉ email nằm trong byline một bài báo
công khai. Không xoá: đó là byte model đã đọc, và xoá nó là làm sai chính phép
đo. Tape `web-tape-final.json` cạnh nó đã chứa cùng văn bản đó, cùng lý do.

## Trạng thái

- [x] Layer sum bằng total ở mọi rung của thang trim — test giữ
- [x] Replay 20 case không network/model, byte-identical hai lượt
- [x] Baseline có phân bố theo layer **và** theo lượt gọi
- [x] Golden artifact tách fresh / cached read / cache write; `input_tokens` giữ nguyên tên và nguyên cột nên artifact cũ vẫn so được
- [x] Corpus không mang định danh của deployment này
- [x] `make test` 1711 pass · 0 file production đổi hành vi
