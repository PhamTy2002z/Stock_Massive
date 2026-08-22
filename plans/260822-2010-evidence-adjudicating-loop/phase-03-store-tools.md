---
phase: 3
title: "Hai tool store-only"
status: pending
---

# Phase 3 — Hai tool store-only

## Lớp lỗi đang mở

`agent/toolsets.py:38-50` có đúng hai toolset — `web` và `memory` — và không tool nào đọc
store. Đó là bất biến có chủ đích của `1e7b936` (*"a general assistant that reads none of our
data"*) và **plan này không đổi nó**: toolset mới chỉ lane Analysis chọn, chat không thấy.

Cái phải xây là bề mặt để model *hỏi* evidence plane. Đường đọc đã có, đúng một cửa:
`stocks/signals/serving.py::serve_field(session, symbol, field, *, end=None, peers=None)`.

## Hình dạng tool result: đã tồn tại, không phát minh lại

`alpha/envelope.py:162-175` đã là format model đánh giá được:

```json
{"fieldId": "...", "label": "...", "value": null, "unit": "ratio", "kind": "estimator",
 "source": "...", "interpretation": "...", "health": "refused",
 "reasonCode": "insufficient_history", "reason": "The store holds fewer sessions than...",
 "asOf": null, "sessionsUsed": 41, "windowDays": 250, "extras": {}}
```

Đo thật: **730 byte/figure**; toàn bộ 30 field trong `REGISTRY` (`registry.py:1171`) là
~22KB ≈ 5.500 token. Đó là worst case tuyệt đối — model xin bằng hết mọi thứ hệ thống biết
tính.

Hệ quả thiết kế: **không port tầng spillover/truncate/dedup của Hermes.** Nó dựng cho cửa sổ
250k ký tự terminal; ở đây không kết quả nào cần spill. `max_result_size_chars` đặt ở mức
chặn một bug (ví dụ 32_000), không phải mức quản lý ngân sách.

## Hai tool

### `list_fields(axis: str | None) -> catalog`

Đọc `REGISTRY`, trả mỗi field: `fieldId`, `label`, `unit`, `kind`, `minSessions`.

**Không trả `interpretation`.** Nó chiếm ~60% byte của một figure (đo được: 227–663 ký tự,
median 433). Catalog không kèm interpretation còn ~2KB cho cả 30 field; interpretation chỉ đi
cùng field mà model thực sự xin.

`minSessions` là thứ làm vòng lặp có nghĩa: gặp `insufficient_history` ở một field cần 250
phiên, model thấy ngay field nào cần ít hơn.

### `get_field(field_id: str) -> figure`

Trả đúng `as_wire()` của một figure.

**Không có tham số `symbol`, không có `trading_day`, không có `peers`.** Cả ba là fact tin
cậy, không phải argument. `agent/registry.py:73-79` đã nói chính xác vì sao:

> *"Never part of a tool schema: the model must not be able to name a user or a thread it does
> not own, so identity arrives here and arguments arrive from the model, and the two are never
> merged."*

Cùng lý lẽ áp cho mã và phiên: một Analysis được khoá bởi `(symbol, trading_day)`, và một
argument cho phép model đổi mã là một đường để nó đọc mã khác hoặc một phiên chưa đóng.
`peers` cũng backend-owned — cross-section đến từ `measure_cross_sections`, không từ model.

## Thay đổi

### `agent/registry.py` — `ToolContext`

Thêm hai field optional: `symbol: str | None = None`, `trading_day: date | None = None`.
Và `user_id: int | None = None`.

`user_id` thành optional là thay đổi duy nhất chạm code dùng chung, và nó **trung thực hơn**
hiện trạng: một Analysis được chia sẻ toàn hệ, khoá bởi `(symbol, trading_day)`, không thuộc
user nào (`alpha/watchlist.py` — *"An Analysis is keyed by `(symbol, trading_day)` and shared
system-wide, so it never belonged to this row in the first place"*). Handler nào cần user thì
từ chối khi không có, cùng khuôn `requires_env` khai báo điều kiện của mình. Ba tool memory
là những handler đó, và lane Analysis không chọn toolset `memory` nên chúng không bao giờ gặp
`None` lúc chạy.

### `agent/tools/signals.py` — mới

Hai handler, `is_async=False` (`serve_field` nhận `Session` đồng bộ; executor tự chuyển
handler blocking ra khỏi event loop). Session mở tại chỗ qua `get_sync_db`, đúng khuôn
`alpha/production.py:167` (`open_session = session_factory or get_sync_db`) — session không
phải "trusted fact" nên không đi vào `ToolContext`.

`check_fn`: cả hai tool khả dụng vô điều kiện — không credential, không cờ tính năng, chỉ
Postgres. Nên `check_fn=None`.

### `agent/toolsets.py`

```python
"signals": {
    "description": "Read one registered Signal Field for the symbol under analysis.",
    "tools": ("list_fields", "get_field"),
}
```

Không thêm vào `CORE_TOOLS` (đang rỗng có chủ đích). Không `includes` từ `web`/`memory`.

## Validation

- Test: `get_field` với một `field_id` không đăng ký trả lỗi model đọc được, không raise.
- Test: schema của `get_field` **không** chứa `symbol`/`trading_day`/`peers`.
- Test: một field `refused` trả `health`/`reasonCode`/`reason` đầy đủ, `value: null`.
- Test: `list_fields` không trả khoá `interpretation`.
- Test: toolset `signals` không nằm trong tập toolset mà chat chọn.
- `make test` pass.

## Risk / rollback

Rollback là bỏ toolset khỏi `TOOLSETS` — `agent/toolsets.py` từ chối tên lạ nên không có
đường nào một Turn chọn được nó sau khi xoá.

Rủi ro thật: `user_id: int | None` làm yếu type ở chỗ dùng chung. Nếu review không chấp nhận,
đường thay thế là một `ToolContext` thứ hai cho lane Analysis — đắt hơn (hai loại context cho
một `Handler` signature) nhưng không chạm chat. Quyết định này nên được xác nhận trước khi
viết code.
