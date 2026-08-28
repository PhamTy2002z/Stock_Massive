---
phase: 4
title: "Projection cho 30 field + refusal đúng input"
status: done
priority: P1
effort: "1d"
dependencies: [3]
---

# Phase 04: Projection cho 30 field + refusal đúng input

> **Sửa 2026-08-28 sau red-team.** Bản đầu (a) chỉ gán projection cho 24/30 field,
> bỏ sót `liquidity_profile.adtv_shares` hoàn toàn; (b) đẩy `adtv_percentile` sang
> VOLUME, khoá nó vào `RANKING_UNAVAILABLE` vĩnh viễn; (c) tự chế mã
> `source_retired` trùng ba mã đã có và trái luật CLAUDE.md.

## Overview

Hai việc. Một: cổng `_basis_of` đang chặn cả field mà phép tính không chạm giá.
Hai: bảy field mất input vĩnh viễn cần refusal **trỏ đúng input thiếu**.

## Requirements

- Functional: **cả 30 field** khai projection tường minh.
- Functional: 2 field không làm số học trên giá đi projection VOLUME và trả số.
- Functional: 7 field mất nguồn trả **ba mã refusal đã có**, không mã mới.
- Non-functional: không field nào trả số khi input của nó không tồn tại.

## Architecture

### Bảng projection — cả 30, không phải 24

`_basis_of` chỉ chạy khi `projection is PRICE` (`bars.py:680`), nhưng
`serve_field` (`serving.py:66`) và `serve_cross_section` (`:196-206`) **không bao
giờ** truyền projection — mặc định PRICE (`bars.py:495,571`).

| # | Field | Projection |
|---|---|---|
| 1 | `volatility_regime.gk_variance_robust_z` | PRICE |
| 2 | `realized_volatility.yang_zhang_annualized_pct` | PRICE |
| 3 | `price_zone.ordinary_range_pct` | PRICE |
| 4-7 | `drawdown_stats.{max_drawdown_pct, current_drawdown_pct, days_underwater, mdd_over_expected}` | PRICE |
| 8-9 | `risk_adjusted.{sharpe_annualized, sortino_annualized}` | PRICE |
| 10 | `liquidity_profile.adtv_vnd` | **PRICE** |
| 11 | `liquidity_profile.adtv_shares` | **VOLUME** |
| 12 | `liquidity_profile.amihud_illiq` | **PRICE** |
| 13 | `liquidity_profile.adtv_percentile` | **PRICE** |
| 14 | `band_pressure.limit_days_in_window` | PRICE |
| 15-16 | `mean_reversion.{trailing_z, half_life_sessions}` | PRICE |
| 17 | `momentum_rank.percentile_12_2` | PRICE |
| 18 | `trend_signal.total_return_12m_pct` | PRICE |
| 19 | `relative_strength.beta_vs_market_index` | PRICE (giữ `UNAVAILABLE`) |
| 20-22 | `factor_percentiles.{earnings_yield, book_yield, size}_percentile` | PRICE (refuse sớm) |
| 23 | `factor_percentiles.roe_percentile` | **VOLUME** |
| 24-26 | `foreign_flow_pressure.*` | PRICE (refuse sớm) |
| 27 | `company_profile.foreign_room_pct` | PRICE (refuse sớm) |
| 28-30 | `indicator_pack.{rsi_14, macd_12_26_vnd, bollinger_percent_b_20}` | PRICE |

**20 PRICE · 2 VOLUME · 8 refuse sớm** (7 mất nguồn + 1 `UNAVAILABLE`). Tổng 30.

**Ba chỗ bản đầu gán sai, và vì sao:**

- `adtv_percentile` **phải PRICE**. `WindowHealth.adtv` chỉ được tính khi
  `projection is PRICE and series.has_peer_cross_section` (`bars.py:757-765`), và
  `adtv_percentile_reading` (`market_behavior.py:295-297`) không đọc gì khác. Đẩy
  sang VOLUME là khoá `RANKING_UNAVAILABLE` vĩnh viễn — rồi implementer hoặc lùi
  về PRICE (tái lập đúng cái refusal phase này định gỡ) hoặc nhân bản phép quét
  peer trong `market_behavior.py`, thứ docstring `:284-289` cấm thẳng.
- `adtv_vnd`, `amihud_illiq` **phải PRICE**: sau Phase 05 chúng làm số học trên
  `close`. Lý do "hệ số per-bar triệt tiêu" của nhóm VOLUME không áp cho chúng.
- `adtv_shares` bản đầu **quên hẳn** — nó chỉ đọc `volume`, đúng VOLUME.

`volatility_regime.gk_variance_robust_z` là ca đáng ghi lý do: phép tính
**intra-bar** (`volatility.py:87-89`, chỉ `log(high/low)` và `log(close/open)`) nên
basis-invariant, nhưng nó có phụ `limit_lock_days` (`registry.py:195`) đến từ máy
band → giữ PRICE.

### Bảy field mất nguồn — dùng mã đã có

CLAUDE.md: *"Mã refusal phải trỏ đúng input thiếu."* Một mã `source_retired` đặt
tên cho **chuỗi cung**, không cho input — và "nguồn đã ngừng" đúng với mọi lần gỡ
nguồn tương lai, nên nó sẽ thành thùng rác. Ba mã đã có trỏ đúng:

| Field | Mã | Vị trí |
|---|---|---|
| `factor_percentiles.{earnings_yield, book_yield, size}_percentile` | `MARKET_CAP_ABSENT` | `issues.py:232` |
| `foreign_flow_pressure.*` (3) | `FOREIGN_FLOW_NOT_STORED` | `issues.py:183` |
| `company_profile.foreign_room_pct` | `FOREIGN_ROOM_NOT_STORED` | `issues.py:190` |

Cả ba đã có câu ở `alpha/reasons.py` và `signal-issues.ts`, và test đồng bộ hai
bên đã tồn tại. **Không thêm mã, không thêm câu.**

Nếu cần diễn đạt tính **vĩnh viễn** (khác với "tạm thời thiếu"), đó là thuộc tính
của declaration — theo tiền lệ `requires_foreign_share_flow` trên `SignalField`
(`fields.py:399-460`) — không phải một mã refusal cạnh tranh.

Ghi chú độ phủ: `market_cap_vnd` đã null ở **99,48%** dòng FiinQuant
(36.338/36.528). Ba field `factor_percentiles` gần như đã chết từ trước; xoá
FiinQuant không đổi gì cho chúng. Nói đúng thế trong phase report, đừng ghi
"mới mất nguồn".

`relative_strength.beta_vs_market_index` giữ `UNAVAILABLE` (`cross_sectional.py:316-325`)
— estimator chưa viết. Đừng đổi lý do từ chối.

### `registry_version()` không bump tay

`registry.py:1233-1256`: hash SHA-256 **dẫn xuất**, phủ đúng sáu declaration
(`name, unit, sign, claim, source, interpretation`). `projection` **không** nằm
trong đó — nên phase này đổi *field nào trả số* mà không đổi định danh registry,
và Evidence Manifest không phân biệt được câu trả lời trước/sau Phase 04.

**Quyết một trong hai, ghi ra:** đưa `projection` vào digest, hoặc viết rõ vì sao
một thay đổi hành vi phục vụ được phép để định danh registry đứng yên.

## Related Code Files

- Modify: `apps/api/src/stocks/signals/registry.py` (projection cho 30 field)
- Modify: `apps/api/src/stocks/signals/serving.py:66,196,201` — truyền projection
  cho **cả** `prepare_bars` và `prepare_bars_context`, nếu không
  `bars.py:612-613` raise `ValueError` trần (500, không phải refusal)
- Modify: `apps/api/src/stocks/signals/{cross_sectional,foreign_flow}.py` (refuse sớm)
- Modify: `apps/api/src/stocks/signals/fields.py` (trường `projection` trên `SignalField`)
- Read: `apps/api/src/stocks/signals/issues.py:183,190,232`
- Tests: `apps/api/tests/` + **`tests/studies/`** (5 module studies import
  `SignalIssue`; `entry_condition_review.py:258` rẽ nhánh trên `MIXED_PRICE_BASIS`)
- Cũng cập nhật: `tests/test_signal_registry.py` (2 chỗ dựng `SignalField`)

## Implementation Steps

1. Thêm `projection` vào `SignalField`; điền cho **cả 30** field theo bảng trên.
   `SignalField` fail-loud khi thiếu declaration, nên bỏ sót sẽ vỡ lúc import —
   đó là hành vi mong muốn.
2. `serve_field` / `serve_cross_section` truyền projection xuống **cả hai** hàm.
3. Bảy field mất nguồn: trả ba mã đã có, **trước** khi chạm bars.
4. Quyết chuyện `registry_version()`; ghi vào phase report.
5. Test: 2 field VOLUME trả số trên window `adjusted_at_source`; 7 field trả đúng
   mã của mình (không phải `INSUFFICIENT_HISTORY` mượn tạm); 20 field PRICE vẫn
   trả số (đã đạt ở Phase 03, khẳng định lại để bắt hồi quy).
6. Chạy `tests/studies/` — plan này **có** đụng plan Study qua `issues.py`.
7. Kiểm mắt trên web: 7 field hiện câu giải thích, không khối trắng.

## Success Criteria

- [ ] Cả 30 field khai projection; import không vỡ
- [ ] 2 field VOLUME trả số trên window `adjusted_at_source`
- [ ] `adtv_percentile` trả số (không `RANKING_UNAVAILABLE`)
- [ ] 7 field mất nguồn trả đúng ba mã có sẵn; **0 mã refusal mới**
- [ ] `beta_vs_market_index` vẫn `UNAVAILABLE`
- [ ] Quyết định về `registry_version()` ghi ra
- [ ] `make test` + `tests/studies/` + bốn cổng web xanh

## Risk Assessment

- **Gán nhầm projection.** Cho VOLUME một field có đọc mức giá = bỏ qua cổng
  basis cho đúng cái nó phải chặn. *Tín hiệu:* số của field đó đổi khi window
  chứa corporate action. *Phản ứng:* bảng trên đến từ đọc code từng field; field
  nào còn lăn tăn thì để PRICE — chặn nhầm hơn cho qua nhầm.
- **`ValueError` trần trên đường cross-section.** *Tín hiệu:* 500 thay vì refusal.
  *Phản ứng:* bước 2 truyền cả hai chỗ, đó là lý do nó là một bước riêng.
- **Phase này và Phase 05, 06 cùng sửa `registry.py` và `market_behavior.py`.**
  *Tín hiệu:* conflict merge trong vùng nhạy. *Phản ứng:* 04 → 05 → 06 nối tiếp,
  không song song. Đã sửa ở plan.md.
