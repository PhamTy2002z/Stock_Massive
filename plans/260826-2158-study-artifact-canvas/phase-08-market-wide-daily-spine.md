# Phase 08 — Spine dữ liệu market-wide (nhóm D, trả nợ)

Phụ thuộc 02 (khuôn ingest). Một backfill giải bốn việc.

## Context — nợ đo được

`provider_snapshots` 2026-08-26: market 36.528 dòng + valuation 35.245 dòng
`source=fiinquant` (2021-08 → nay) — provider đã tuyên bố vi phạm ToS, code
đã rip, **dữ liệu chưa**. `market_index` = 0 dòng. `fundamental` 1.088/1.343
mã chỉ 1 snapshot. Phase 07 đã vá cục bộ cho mã được hỏi; phase này vá hệ
thống.

## Requirements

1. **Backfill daily OHLCV từ vnstock** (capability MARKET, source=vnstock):
   - `declared` 30 mã: full depth (~8 năm) — ghi đè thay dòng fiinquant.
   - `market` (~1.700 mã từ `Listing.all_symbols()`): **400 phiên** (52w +
     đệm) — đủ cho screener price-reaction phase 10, tránh 2,1M rows vô ích.
   - Chi phí: 1 request/mã (daily 1 call trả cả dải — probe VNINDEX 1.738
     dòng/1 call). ~1.730 requests ≈ 29 phút free key / 87 phút guest.
     Job resumable (checkpoint theo symbol), chạy được nhiều đợt.
2. **VN-Index daily** → capability MARKET_INDEX (enum đã có, bảng
   provider_snapshots dùng chung). Mở lại trục relative-return.
3. **Listing roster + ICB**: `all_symbols()` + `symbols_by_exchange()` +
   `industries_icb()` → `listing_roster` (bảng đã có) — exchange, icb_code,
   icb_name. Peer group thật cho phase 09/10.
4. **Universe hai nửa** (khuôn phase-10 restore map cũ): `Universe.declared`
   (30 mã, full signal) + `Universe.market` (roster listed, signal tối
   thiểu). `get_field` giữ luật declared-only cho field khai vậy.
5. **Xoá dòng fiinquant** sau khi verify: đối chiếu ngẫu nhiên 50 (symbol,
   day) vnstock-vs-fiinquant (lệch >0,5% → dừng, điều tra); backup; DELETE
   theo `payload->metadata->>'source'`; VACUUM. Downgrade = restore backup.

## Files

- `src/stocks/providers/vnstock_daily.py` — fetch + normalize về payload
  schema_version hiện hành (đọc `contracts.py` + payload mẫu trước khi viết)
- `src/stocks/backfill_daily.py` — job checkpoint/resume, CLI entry
  (`python -m src.stocks.backfill_daily --scope declared|market|index`)
- `src/stocks/universe.py` — hai nửa; giữ chữ ký `build_universe(session)`
- Alembic: KHÔNG bảng mới (dùng provider_snapshots + listing_roster)
- Tests: normalize (fixture response thật) · checkpoint resume · universe
  hai nửa · so khớp vnstock-fiinquant trên fixture

## Steps

1. Backup DB (bắt buộc — có DELETE).
2. Fetcher + normalize + tests.
3. Backfill declared → verify 50 cặp → backfill index → roster/ICB.
4. Backfill market 400 phiên (chạy nền, checkpoint).
5. Universe hai nửa + tests get_field luật declared-only.
6. DELETE fiinquant rows → chạy lại toàn bộ signal smoke (25 field trên 3 mã)
   khẳng định serving không gãy.

## Validation

- Acceptance #6 plan.md: cửa sổ phục vụ không còn `source=fiinquant`;
  `trading_day.latest_trading_day` vẫn đúng; VNINDEX đọc được ≥5 năm.
- `make test` xanh; signal smoke 25 field không đổi health ngoài dự kiến.

## Risk & rollback

- Lệch giá vnstock vs fiinquant (adjusted khác nhau): ngưỡng 0,5% + điều tra
  thủ công trước DELETE — không xoá khi chưa giải thích được lệch.
- DB phình (~700k rows mới): chấp nhận, đo kích thước trước/sau, ghi vào
  report phase.
- Rollback: restore backup pre-phase; job idempotent nên chạy lại an toàn.
