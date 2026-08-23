# Prompt cache trên route cliproxy — đo trực tiếp

Ngày đo: 2026-08-23. Route `http://host.docker.internal:8317/v1`, model
`gpt-5.6-luna` (workload BATCH). Đo qua chính `transport.py` của app, nên số này
là số production sẽ thấy. Mọi phép đo tiêu token thật; ngân sách đang unmetered.

Câu hỏi: có nên bật `llm_prompt_cache_control_enabled` không, và vì sao lane
Analysis báo 0% cached trong khi lane Turn báo 57,6%.

## 1. Cache đã chạy — tự động, không cần `cache_control`

```
cache_control=False
  1st (prefix lạnh)   in=2953  cached=   0
  2nd (cùng prefix)   in= 137  cached=2816
  3rd (cùng prefix)   in= 137  cached=2816

cache_control=True
  1st                 in= 137  cached=2816
  2nd                 in= 137  cached=2816
  3rd                 in= 137  cached=2816
```

Route **nhận** request mang `cache_control` (không 400) và **không đổi gì**. Đây
là route OpenAI-shaped: cache là hành vi tự động của nhà cung cấp, báo về ở
`prompt_tokens_details.cached_tokens`, và `transport.py:603` đã đọc đúng field đó.

**Kết luận: giữ `llm_prompt_cache_control_enabled=False`.** Bật lên không mua
được gì, chỉ thêm một field của Anthropic vào một request hình dạng OpenAI.

## 2. Ledger xác nhận trên traffic thật

| owner | model | call | uncached | cached | % cached |
|---|---|---|---|---|---|
| Turn | `gpt-5.6-terra` | 442 | 1.490.188 | 2.023.424 | **57,6 %** |
| Turn | `gpt-5.6-luna` | 71 | 118.252 | 61.440 | 34,2 % |
| Turn | `claude-opus-5` | 9 | 43.228 | 51.855 | 54,5 % |
| **Analysis** | `gpt-5.6-luna` | 8 | 40.345 | 0 | **0 %** |
| Probe | mọi model | 398 | ~114k | 0 | 0 % |

`cache_write_tokens = 0` ở mọi dòng — nhất quán với việc không có cache tường
minh kiểu Anthropic nào đang xảy ra.

## 3. Cache bám ĐẦU prompt

Cùng một block chung, đổi chỗ với phần riêng theo mã:

| xếp | uncached | cached |
|---|---|---|
| block chung trước, mã sau | 141 | **2.816** (95,2 %) |
| mã trước, block chung sau | 2.957 | **0** |

Ba mã khác nhau đều hit khi block chung đứng trước. Nên cache **dùng chung được
xuyên mã** — miễn phần ổn định dẫn đầu.

## 4. Ngưỡng tối thiểu ≈ 2048 token, bước 128

```
actual 1883 → 0        actual 2065 → 1792
actual 1014 → 0        actual 2247 → 1792
actual 1281 → 0        actual 2597 → 1792
actual 1715 → 0        actual 2415 → 0      (xem §5)
```

Mọi giá trị `cached` đo được đều là bội của 128 (1792 = 14×128,
2816 = 22×128). Dưới ~1900 token thì không bao giờ cache.

## 5. Hit là best-effort, KHÔNG tin được theo từng call

Tám call liên tiếp, cùng một prefix 2416 token:

```
call 0 miss · call 1 HIT · call 2 miss · call 3 miss
call 4 miss · call 5 miss · call 6 HIT · call 7 HIT
→ 3/8
```

Đây là proxy, gần như chắc chắn đang phân tải qua nhiều instance/key upstream,
mỗi cái có cache riêng. Điều đó giải thích luôn vì sao lane Turn ra 57,6% chứ
không phải ~95%.

**Hệ quả thiết kế: cache chỉ được tính vào ngân sách theo *tổng*, không theo
từng call.** Không có chỗ nào được giả định một call cụ thể sẽ hit.

## 6. Vì sao lane Analysis là 0%

Không phải lỗi cache, và không phải lỗi thứ tự — thứ tự **đã đúng**:
`generation.py:387` đặt `SYSTEM_PROMPT` trước, envelope sau.

Nguyên nhân là kích thước: `SYSTEM_PROMPT` dài **1.744 ký tự ≈ 436 token**, dưới
xa ngưỡng ~2048. Prefix ổn định của lane này chưa đủ dài để cache được, chạy bao
nhiêu lần cũng vậy.

## 7. Sửa lại kết luận trước đó

- **Khảo sát Hermes #4** (`cache_key()` có nhưng không `cache_control` nào được
  set → "trả giá đầy đủ mỗi Turn") — nửa đầu đúng, **suy luận sai** với route
  này. Lane Turn đang được cache 57,6% mà không cần `cache_control` nào.
- **Bản đề xuất kiến trúc §5** ("cache là đòn bẩy lớn nhất, đã dựng xong, chỉ
  chờ bật một cờ") — **sai**. Không có cờ nào cần bật; cache đã chạy ở chỗ nó
  chạy được, và chỗ nó không chạy được là do prefix quá ngắn, không do cấu hình.
- **Baseline `phase-01` ("vòng lặp 4 round sẽ nhân input lên ~4× trước cache")**
  — quá bi quan với route này. Round 2 trở đi của một Analysis mang theo toàn bộ
  message của round 1, tức đã vượt ngưỡng 2048, nên sẽ cache **best-effort**
  (~40–60% theo số của lane Turn), không phải 0%.

## 8. Việc nên làm và không nên làm

**Không nên:** bật `llm_prompt_cache_control_enabled`. Không nên nhồi
`SYSTEM_PROMPT` cho dài quá 2048 token chỉ để chạm ngưỡng cache — đó là trả thêm
token trên đường miss để mua một cái hit best-effort, và làm phình prompt vì lợi
ích của cache chứ không vì lợi ích của câu trả lời.

**Nên:** khi loop Analysis chạy thật, đo lại `cached_read_tokens` theo
`owner_id` để biết round 2+ hit bao nhiêu. Đó là con số duy nhất còn thiếu, và
nó chỉ xuất hiện trên traffic thật.

## Câu chưa giải quyết

1. Tỷ lệ hit của round 2+ trong một Analysis là bao nhiêu? Chưa có loop thật chạy.
2. Proxy phân tải qua bao nhiêu instance? Nếu ghim được session về một instance
   thì hit rate lên gần 95% — nhưng đó là việc của cấu hình proxy, không phải của
   repo này.
3. Giá production thật: `LLM_PRICING_VERSION=2026-08-dev-cliproxy` ($0,5/$1,0 per
   Mtok) là giá dev. Mọi con số USD trong các báo cáo trước đều theo giá này.
