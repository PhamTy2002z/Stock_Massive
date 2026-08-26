# Phase 02 — Intraday ingest vnstock 15m

Nhóm A. Không phụ thuộc phase nào (chạy song song 01 được).

## Context — hai sự thật đo được quyết định thiết kế

1. vnstock trả **lịch sử** intraday: `Quote(symbol, source="VCI")
   .history(start, end, interval="15m")` → STB 6.644 dòng / 70 phiên /
   2,14 s / 1 request, tier guest (OBSERVED 2026-08-26). Không có cold start,
   không cần Bronze. Trần cứng: 15m tới 1 năm lùi từ hiện tại.
2. Restore map cũ nói bảng intraday "còn trong DB — chỉ reconnect". **Sai**:
   `pg_tables` không có. Phase này tạo bảng mới.

Bẫy: grid trả 96 bucket/ngày (24h); phiên VN chỉ ~17 bucket thật. Không lọc
→ thống kê pha loãng 5,6×.

## Requirements

- Bảng `bar_intraday_15m` mới, ingest idempotent (chạy lại không nhân đôi).
- Session window VN: ATO 09:00–09:15 · sáng 09:15–11:30 · nghỉ trưa (loại) ·
  chiều 13:00–14:30 · ATC 14:30–14:45. Bucket label = giờ bắt đầu +
  phase tag (`ato|am|pm|atc`).
- Dùng `vnstock.api.quote.Quote` (đường mới), bọc `safe_vnstock_call`
  (đã có `src/core/vnstock_wrapper.py` — mở rộng, không thay).
- Provenance mỗi dòng: `source='vnstock'`, `observed_at`.
- On-demand + đầy dần: lần đầu hỏi một mã → backfill 1 năm; các lần sau chỉ
  kéo từ bar cuối cùng đã có (delta).

## Files

| File | Việc |
|---|---|
| `src/stocks/intraday/__init__.py` | package mới (thư mục `stocks/realtime` cũ KHÔNG đụng) |
| `src/stocks/intraday/session_window.py` | lọc + gắn nhãn bucket; thuần, không I/O |
| `src/stocks/intraday/ingest.py` | `ensure_bars(session, symbol, *, sessions: int) -> IngestOutcome` — kéo delta, upsert |
| `src/stocks/intraday/reads.py` | `bars_for(session, symbol, sessions) -> tuple[Bar15m, ...]` — API đọc cho studies |
| `src/stocks/models.py` | model `BarIntraday15m` |
| `alembic/versions/<new>` | tạo bảng |
| `tests/stocks/intraday/*` | session window (bảng vàng bucket), idempotency (gọi 2 lần), delta logic — provider mock, không gọi mạng trong test |

## Schema

`bar_intraday_15m`: `symbol text · bucket_start timestamptz · trading_day date
· phase text · open/high/low/close numeric · volume bigint · source text ·
observed_at timestamptz` — PK `(symbol, bucket_start)`.

## Steps

1. Backup DB → alembic revision → upgrade.
2. `session_window.py` với bảng bucket cố định + test vàng (một phiên thật
   của STB làm fixture).
3. `ingest.py`: upsert `ON CONFLICT (symbol, bucket_start) DO UPDATE` (bar
   cuối phiên có thể được provider sửa); loại bucket ngoài session window
   **trước khi** ghi.
4. `reads.py` trả đúng N phiên gần nhất **đã đóng** (loại phiên hôm nay nếu
   chưa qua ATC — khớp luật "phiên gần nhất đã đóng" của lane chat).
5. Rate-limit ý thức: 1 mã = 1 request; `ensure_bars` cho nhiều mã đi tuần tự
   qua wrapper (retry + backoff đã có).
6. Import pandas/vnstock ở module load (container start), không import lười
   trong handler — tránh trả giá import lạnh vào call đầu tiên (audit N11).

## Validation

- Test unit xanh (mock provider).
- Smoke thật trên host/container: `ensure_bars('STB', sessions=30)` → đếm
  `select count(*), count(distinct trading_day)` ≈ 17 bucket × ≥30 phiên;
  chạy lần 2 → row count không đổi.

## Risk & rollback

- vnstock đổi shape trả về (R3): ingest validate cột bắt buộc, thiếu → raise
  typed error, không ghi rác. Rollback: downgrade revision (bảng mới).
