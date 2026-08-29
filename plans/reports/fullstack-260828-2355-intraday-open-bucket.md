# Bucket đang mở không được ghi vào kho

## File đã đổi

| File | Nội dung |
|---|---|
| `apps/api/src/stocks/intraday/ingest.py` | Lọc bucket chưa đóng; thêm `now` inject được; docstring lên "năm điều" |
| `apps/api/tests/stocks/intraday/test_ingest.py` | 3 case mới + helper `_bucket_times` |
| `apps/api/src/studies/volume_at_price.py` | `_bucket_label` → `_covered_through`, trả **giờ kết thúc** bucket cuối |
| `apps/api/tests/studies/test_volume_at_price.py` | Sửa 1 assert, thêm 1 case (ATC 14:45 → "tính tới 15:00") |
| `apps/api/src/alpha/reasons.py` | Đúng một câu: `SESSION_NOT_INGESTED` |
| `apps/web/src/lib/signal-issues.ts` | Đúng một câu: `session_not_ingested` |

## Luật lọc

`_still_filling(bucket_start, now)` trong `ingest.py`:

```
bucket_start + BUCKET_MINUTES(15') + SETTLE_GRACE(60s) > now  →  bỏ
```

- `SETTLE_GRACE = timedelta(seconds=60)`, hằng module, có trong `__all__`.
- Bucket bị bỏ đếm riêng ở `IngestOutcome.buckets_underway` (mặc định `0`),
  **không** cộng vào `padding_dropped`: padding là khung giờ sẽ không bao giờ là
  phiên, còn cái này là bucket sẽ có ở lần warm sau.
- `ensure_bars(..., now: datetime | None = None)`. `now` là đồng hồ duy nhất của
  lệnh gọi: `today` mặc định lấy `now.date()`, cut-off lấy từ nó, `observed_at`
  đóng dấu bằng nó. Production không truyền gì.
- Không đụng `_start_from`: warm fetch vẫn bắt đầu từ phiên lưu cuối, nên bucket
  bị giữ lại quay về ở lần warm kế tiếp mà không cần backfill.

`volume_at_price._covered_through(bar)` = `bucket_start + 15'`. Bucket 13:30 →
"Phiên chưa đóng, tính tới 13:45"; bucket ATC 14:45 → "tính tới 15:00", trùng
đúng `SESSION_SETTLED_AT`.

## Câu reason

- `reasons.py` (tiếng Anh, câu cho model): "The session being asked about is not
  in the store: it may not have opened yet, its bars may not have arrived, or the
  market may not be trading that day. Nothing was answered from an earlier
  session under its name."
- `signal-issues.ts` (tiếng Việt, câu cho người đọc): "Chưa có dữ liệu giao dịch
  của phiên được hỏi — phiên chưa mở, dữ liệu chưa về, hoặc ngày đó không giao
  dịch".

Chỉ sửa đúng một dòng ở mỗi file; test đồng bộ hai đầu là
`apps/web/src/lib/signal-issues.test.ts` (đọc thẳng enum trong `issues.py`).

## Lệnh test + kết quả

| Lệnh | Kết quả |
|---|---|
| `make test` (apps/api) | 1400 passed |
| `pnpm vitest run src/lib/signal-issues.test.ts` | 5 passed |
| `pnpm test` (apps/web) | 59 file / 736 passed |
| `pnpm type-check` | pass |
| `pnpm lint` | pass |

Không nới test nào. Không thêm dependency.

## Ghi nhận

Cửa sổ 60 giây từ 09:30:00 đến 09:31:00: `volume_at_price` bắt đầu kỳ vọng có
phiên hôm nay lúc `FIRST_BUCKET_SETTLED_AT = 09:30`, nhưng bucket 09:15 chỉ được
ghi từ 09:31 (09:30 + đệm). Trong đúng một phút đó Study từ chối với
`session_not_ingested` thay vì trả bức tranh một bucket. Câu reason mới đọc đúng
cho tình huống này ("dữ liệu chưa về"), nên không sửa thêm — nới `FIRST_BUCKET_
SETTLED_AT` hay đệm là quyết định riêng, ngoài phạm vi việc này.
