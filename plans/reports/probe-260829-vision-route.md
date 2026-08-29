# Probe: does the route read images

- Ngày chạy: **2026-08-29** giờ VN (script in `2026-08-28` vì container chạy UTC)
- Model: `gpt-5.6-terra`
- Route: `http://host.docker.internal:8317/v1`

| Lượt | `prompt_cache_control` | Dải màu chờ | Kết quả | `usage.input_tokens` |
|---|---|---|---|---|
| `one-image` | off | blue green red | PASS | 1277 |
| `cache-control` | on | blue green red | PASS | 1277 |
| `two-images` | off | blue magenta green · red magenta cyan | PASS | 2207 |

Chi phí một ảnh ≈ **930** token (hiệu `input_tokens` giữa lượt hai ảnh và lượt một ảnh, cùng cache off).
Đây là số chốt `IMAGE_TOKENS` ở `core/llm/protocol.py` và trần bytes của phase 05.
Phần cố định của request là `1277 − 930 = 347` token.

## Câu trả lời nguyên văn

### `one-image`

```
{'text': 'blue green red', 'finish_reason': 'stop', 'usage.input_tokens': 1277}
```

### `cache-control`

```
{'text': 'blue green red', 'finish_reason': 'stop', 'usage.input_tokens': 1277}
```

### `two-images`

```
{'text': 'blue magenta green\nred magenta cyan', 'finish_reason': 'stop', 'usage.input_tokens': 2207}
```

## Kết luận cho cổng chặn

**PASS.** Fork "route không đọc được ảnh" ở phase 04 **không kích hoạt**; phase
05→10 chạy nguyên phạm vi. `LLM_VISION_ENABLED=true` và
`LLM_VISION_MEASURED_MODEL=gpt-5.6-terra` đã đặt trong `.env` (không commit).

Lượt `cache-control` là lượt đáng giá nhất: nó chứng minh
`_mark_tail_breakpoints` sau sửa của phase 03 đặt marker lên block **text** cạnh
ảnh, và route vẫn nhận. Trước sửa, marker rơi lên block ảnh — một hình dạng mà
unit test của `as_wire` vẫn xanh.

## Phát hiện phụ — cách dựng ảnh test, và vì sao bản đầu sai

Bản đầu của script vẽ bốn chữ số bằng một font bitmap 3×5 tự viết. Ảnh hợp lệ và
**người đọc được** (đã xem tận mắt). Model trả lời:

> *"A plain white rectangular image with no visible objects, text, markings, or
> other details."*

rồi bịa ra bốn chữ số — đúng bằng câu nó trả lời khi **không** có ảnh nào (lượt
đối chứng "no-image" trả `'42'`). Đã loại trừ hai nghi phạm:

| Nghi phạm | Phép thử | Kết quả |
|---|---|---|
| PNG greyscale (colour type 0) | vẽ lại y hệt bằng colour type 2 | vẫn "blank white" |
| Encoder tự viết | nạp bằng Pillow rồi lưu lại, gửi bytes của Pillow | vẫn đọc sai |
| Route không chở ảnh | ảnh một màu ngẫu nhiên trong 6 màu | **đọc đúng** (`Cyan`, `Blue`) |
| Model không đọc được chữ | chữ số render bằng font thật của Pillow | **đọc đúng `2662`** |

Nên: route chở ảnh tốt và model đọc **chữ khử răng cưa** chính xác; thứ nó không
đọc được là hình khối pixel tự chế. Script chốt lại dùng **dải màu dọc** —
tín hiệu đã đo là sống sót — ba dải rút từ sáu màu, tính cả thứ tự: một đáp án
trong 216, và phải đọc được *vị trí* mới trả lời đúng thứ tự.

Hệ quả cho phase 06: injection qua ảnh là mối lo **có thật**. Model đọc chữ trong
screenshot chính xác, nên một dòng chỉ thị nằm trong ảnh là chữ nó đọc được.
