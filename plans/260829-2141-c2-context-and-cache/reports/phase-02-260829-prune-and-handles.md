# Phase 02 — prune deterministic: đo được bao nhiêu, và trần ở đâu

**Ngày:** 2026-08-29 · **Corpus:** `context-replay-v1.json` (20 case, 129 call, 78 lượt gọi model)

## Kết quả

| | Baseline (phase 01) | Sau phase 02 | |
|---|---:|---:|---:|
| Constructed token | 797.722 | **687.269** | **−13,85%** |
| Median/Turn | 36.043 | 31.878 | −11,6% |
| `tool_results` | 343.890 | 234.097 | −31,9% |
| `study_headlines` | 2.560 | 1.900 | −25,8% |
| URL còn tới được trong text model đọc | — | **536/536** | **100%** |
| Câu hỏi của người dùng còn trong context | — | **20/20 case, mọi lượt** | **100%** |

Replay hai lượt → byte-identical. Sáu layer còn lại không đổi một token.

## Hai thứ được dựng

**Dedup theo phạm vi Turn cho `web_search`.** `context_text` là bản chiếu model
đọc; `result_text` vẫn là toàn văn tool trả về và là thứ trace ghi. Một trang hai
truy vấn cùng tìm ra chỉ đi tới model một lần. `fetch_url` **không** dedup theo
URL — cùng một trang đọc với hai `looking_for` trả hai đoạn khác nhau, và bỏ cái
thứ hai là vứt đúng thứ lượt gọi thứ hai sinh ra để lấy.

**Rung ageing chủ động.** `SELECTION_CALLS = 1` · `RESULT_CALLS = 2`. Một kết quả
giữ nguyên văn N lượt gọi *kể từ lượt đọc nó lần đầu*, rồi thành trace handle
mang query/URL của call cộng tối đa năm link. Đây **không** phải một rung của
thang phục hồi — nó là trạng thái thang bắt đầu từ đó. Context vừa vặn vẫn được
dựng mà không mang lại đoạn prose model đã thôi đọc từ hai lượt trước.

## Một lỗi đã suýt lọt, và test bắt được nó

Bản đầu tính tuổi là `round <= i - keep`, làm kết quả `web_search` của vòng 0
thành handle **ngay ở lượt gọi lẽ ra phải đọc nó**. Đó không phải prune, đó là
Turn chưa từng tìm kiếm. Nó cho ra "−19,8%" và con số đó là giả.
`test_a_result_is_never_a_handle_on_the_call_that_first_reads_it` giữ luật đúng:
tuổi đếm từ lượt đọc, `keep=1` nghĩa là *đã đọc một lần*.

## Trần của prune, và nó là số học

| Luật (dedup luôn bật) | Token | vs baseline | URL mất |
|---|---:|---:|---:|
| Dedup only | 789.215 | −1,1% | 0 |
| search giữ 2, khác giữ 3 | 759.114 | −4,8% | 0 |
| search giữ 2, khác giữ 2 | 746.163 | −6,5% | 0 |
| search giữ 1, khác giữ 3 | 700.220 | −12,2% | 0 |
| **search giữ 1, khác giữ 2 (đã chọn)** | **687.269** | **−13,8%** | **0** |
| search giữ 1, khác giữ 1 | 655.932 | −17,8% | 0 |

**−17,8% là trần cứng, không phải mức thiếu cố gắng.** `system_core` chiếm
**53,3%** context và prune không chạm được nó — nó là prompt, giống nhau ở mọi
lượt gọi, và thứ làm nó rẻ là **cache** chứ không phải cắt gọt. `tool_results`
là 43,1%. Cắt 20% tổng đòi cắt **46,4%** của tool_results; biến *mọi* kết quả
thành handle ngay sau đúng một lượt đọc chỉ cắt được 41% của nó. Vượt qua ngưỡng
đó là collapse một trang **trước khi model đọc nó lần nào** — đó không phải
prune.

Nên **gate "≥20% constructed token" của plan không đạt được trong ranh giới C2**.
Cùng hình dạng với tiêu chí citation của C1: một ngưỡng viết trước khi có phân bố.
Quyết định (2026-08-29): giữ luật `search 1 / khác 2` và **đặt lại bar từ phân
bố đã đo** ở phase 05 — đúng luật mở đầu của `golden/README.md`: không có ngưỡng
trước khi có phân bố.

## Bất biến còn nguyên

- Trace là toàn văn. `context_text` **không bao giờ** lên wire (`as_wire`), không
  vào `agent_message.content`, không vào SSE. Test giữ cả ba.
- Scanner vẫn chạy **đúng một lần** ở executor, trên toàn văn, trước khi chiếu.
  `messages.py` và `golden/context_replay.py` đều không nhắc `scan_for_threats`.
- Prune deterministic chạy **trước** summary và trước overflow retry — test khẳng
  định lượt retry mang handle chứ không mang summary.
- `wrap_result` vẫn bọc đúng thứ gửi model.
- Handle nói rõ nó là gì (`TRACE_HANDLE_PREFIX`) và **không** gợi ý một tool lấy
  lại — deployment này không có tool nào như vậy.
