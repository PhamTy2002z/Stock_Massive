---
phase: 1
title: "Baseline one-shot trên dữ liệu thật"
status: done-with-caveat
---

# Phase 1 — Baseline one-shot trên dữ liệu thật

## Kết quả (2026-08-22)

Đã đo. Report: [`plans/reports/baseline-oneshot-260822.md`](../reports/baseline-oneshot-260822.md).

Hai chỗ phase này đoán sai và số thật đã sửa:

- **Cờ đã bật từ trước.** `.env` nội bộ có `ALPHA_DESK_ENABLED=true`; store đã có 8 Analysis
  `ready` trên 2 Trading Day (2026-08-20, 08-21) và 10 run `failed` trước đó. Không có việc gì
  để bật.
- **Cửa 5 Trading Day chưa đạt: có 2.** Ba phiên còn lại là ba phiên thật phải chờ; không rút
  ngắn được, và tự sinh dữ liệu để lấp thì phá đúng cái phase này bảo vệ.

Cửa quyết định của phase này **không đóng plan**: `refused` chiếm **41,6 %** (57/137 figure).
Nhưng lý do của Phase 4 phải viết lại — **86 % refusal là cấu trúc** (`fundamental_not_stored`,
`unavailable`: BCTC chưa persist, trục news chưa dựng — cả hai trong `Non-goals`), không có đường
đi quanh. Giá trị đo được của vòng lặp nằm ở chỗ khác: **16 field trong catalog chưa bao giờ tới
được một Analysis nào**, vì Field Profile `v1` cố định chọn 11 field cho mọi mã mọi phiên.

## Lớp lỗi đang mở

`core/config.py:220`: `alpha_desk_enabled: bool = False`.

Lane Analysis **chưa từng chạy trên dữ liệu thật**. Nghĩa là mọi phát biểu về "chất lượng
phân tích hiện tại" — kể cả các phát biểu trong plan này — là suy từ code, không phải đo.
Dựng vòng lặp để cải thiện một thứ chưa ai thấy chạy là dựng mù: khi loop xong sẽ không có
mốc nào để nói nó tốt hơn ở đâu.

Phase này không viết logic mới. Nó lấy mốc.

## Thay đổi

### Bật lane trên môi trường nội bộ

Bật `ALPHA_DESK_ENABLED` cùng bảng giá LLM (`llm_pricing_version`,
`llm_price_batch_*`) — Budget Validation từ chối giá `0.0` và sẽ chặn startup, đó là hành vi
đúng, không phải lỗi cấu hình.

Cohort là hợp các Watchlist (`alpha/nightly.py`), cap 10 mã/user
(`alpha/watchlist.py::WATCHLIST_MAX_SYMBOLS`). Nội bộ vài user → ≤30 mã, nằm trong lane $10.

Cohort được chốt bởi **dữ liệu, không phải đồng hồ**: khoảnh khắc Market Snapshot đầu tiên
lập một Trading Day mới. `alpha/nightly.py` ghi rõ lý do — *"the Main Source appends the
session that just closed hours after the close, so 16:15 routinely comes away with
yesterday's session"*. Nên đừng chờ theo giờ; chờ theo `latest_trading_day` nhảy.

### Đo và ghi lại

Chạy ít nhất **5 Trading Day** liên tiếp, rồi ghi vào
`plans/reports/baseline-oneshot-<date>.md`:

| Số | Lấy từ đâu |
|---|---|
| Số Analysis `ready` / `failed`, chia theo `error_code` | `analysis_run` |
| Phân bố `verdict` | `analysis.verdict` |
| Với mỗi Analysis: bao nhiêu figure `ok` / `degraded` / `refused` | `analysis.payload` → `evidence` |
| `reasonCode` nào xuất hiện, tần suất | cùng nguồn |
| Bao nhiêu figure được `citedFieldIds` dẫn, trên tổng số `ok`+`degraded` | cùng nguồn |
| Token và giá thật mỗi Analysis | `llm_call_usage` theo `owner_type='analysis_run'` |

Hai con số cuối là mốc mà Phase 5 so vào.

Con số quan trọng nhất là **tần suất `reasonCode`**: nó nói mã issue nào thực sự xảy ra trên
Universe thật. Nếu `insufficient_history` chiếm phần lớn thì vòng lặp có nhiều việc để làm;
nếu gần như mọi figure là `ok` thì giá trị của substitution thấp hơn dự kiến và Phase 4 phải
được định lại giá trước khi thi công.

## Validation

- Budget Validation pass lúc startup (nếu fail: bảng giá chưa điền, không phải bug).
- Ít nhất 5 Trading Day có Analysis `ready`.
- Report tồn tại và mọi con số trong đó truy được về một query cụ thể.

## Risk / rollback

Rollback là tắt cờ. Không migration, không schema, không dữ liệu bị đổi.

Rủi ro thật là **quota vnstock**: cohort đầu tiên đọc cross-section cho percentile, và
`stocks/universe.py:31` cap Universe ở 100 mã. Nếu Snapshot của phiên đó chưa đủ thì Analysis
`failed` với `missing_market_snapshot` — đó là kết quả đúng, ghi lại rồi chạy lại phiên sau,
không phải nới quota.

## Kết quả có thể làm plan này dừng

Nếu baseline cho thấy `refused` gần như không xảy ra, giá trị của Phase 4 sụp. Lúc đó việc
đúng là dừng plan và chuyển sang mở rộng evidence plane (persist BCTC, axis news) —
`Non-goals` của plan này. Phase 1 là cổng đó, và nó được phép đóng plan.
