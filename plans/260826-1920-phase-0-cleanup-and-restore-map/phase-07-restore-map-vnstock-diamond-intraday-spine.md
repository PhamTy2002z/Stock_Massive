---
title: "Phase 7: Restore map — vnstock Diamond intraday spine"
status: reference-only
---

# Phase 7: Restore map — vnstock Diamond intraday spine

## Overview

**Reference-only — không thi công trong plan này.** Ghi phạm vi công việc
cần thiết khi restore backend intraday để phục vụ brief `docs/Text.txt`
(Intraday Liquidity Canvas cho STB, heatmap 30 phiên, bucket 5m/15m).

## Brief origin

`docs/Text.txt` line 1-166 (Intraday Liquidity Analysis mockup):
- 30 phiên gần nhất
- Bucket 5m / 15m
- Volume + value theo bucket
- Chuẩn hoá theo tổng thanh khoản phiên (`liquidity_share`)
- Spike frequency
- ATO / sáng / trước trưa / chiều / ATC bucket labels
- Heatmap 30 x 9 bucket (`░ ▒ ▓ █`)
- Top liquidity windows ranking
- Price reaction by bucket (drill-down)

## Data cần

- Intraday bar 5m + 15m cho 30 phiên gần nhất, mỗi mã Universe (sau khi mở rộng)
- Tag bucket theo session phase (ATO/AM/lunch break/PM/ATC)
- Aggregate volume + value + tick count trong bucket
- Liquidity share = bucket_volume / session_total_volume
- Price open/close trong bucket cho price reaction

## Nguồn thay DNSE

- **vnstock Bronze** giai đoạn dev (180 req/phút, `pd.read_csv` / helpers) → poll intraday bar từ vnstock
- **vnstock Diamond** khi lên prod (600 req/phút, licence phân phối < 500 user)
- Không stream, chỉ poll — mỗi 60s cho mã đang có người xem; batch mỗi 5 phút cho background

## Module cần restore (từ `v-with-market-surfaces` tag)

- `src/stocks/realtime/spine.py` — schedule + poll
- `src/stocks/realtime/aggregation.py` — bucket 5m/15m aggregation
- `src/stocks/realtime/bar_projection.py` — bar view
- `src/stocks/realtime/metric_projection.py` — spike + liquidity share metric
- `src/stocks/realtime/service.py` — read API
- `src/stocks/realtime/reconciliation.py` — reconcile Bronze ↔ Diamond
- `src/stocks/session_window.py` — bucket labels (ATO/AM/lunch/PM/ATC)
- `src/stocks/series_view.py` — series view helpers
- `src/stocks/intraday_collector.py` — cron job entry
- Table `bar_intraday_5m`, `bar_intraday_15m`, `session_metric_bucket` (chưa drop, còn trong DB — chỉ reconnect)

## Module PHẢI KHÔNG restore

- `src/stocks/realtime/dnse/*` (đã rip Phase 2)
- `src/stocks/realtime/ingress.py` (DNSE-specific)
- `src/stocks/realtime/coordinator.py` (DNSE-specific)
- `src/stocks/realtime/spine.py` **phần** subscribe pattern (giữ lại phần bar aggregation)

## Config setting mới

- `vnstock_licence_tier: "bronze" | "diamond"`
- `vnstock_api_key: SecretStr`
- `vnstock_poll_interval_seconds: int` (default 60)
- `vnstock_batch_poll_interval_seconds: int` (default 300)

## Signal fields mới cần đăng ký

- `intraday_bucket_volume` — dict{bucket_label -> volume}
- `intraday_bucket_liquidity_share` — dict{bucket_label -> percent}
- `intraday_spike_frequency` — dict{bucket_label -> N sessions with spike / total}
- `top_liquidity_window` — bucket_label với spike cao nhất
- `intraday_price_reaction` — dict{bucket_label -> avg return}

## Việc PHẢI KHÔNG làm ở phase này

- Không build canvas React component
- Không build agent tool `render_canvas`
- Không đụng CLAUDE.md tuyên bố "hard freeze"

## Placeholder success criteria

Khi lần restore này được kích hoạt (plan riêng), success có nghĩa:
- Poll vnstock Bronze/Diamond thành công, respect quota
- `bar_intraday_5m` populate cho 30 mã Universe trong 30 phiên gần nhất
- Signal fields mới liệt kê trong `list_fields`
- Reconcile Bronze ↔ Diamond ≤ 0.5% divergence
