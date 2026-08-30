---
phase: 10
title: "Bronze data breadth"
status: blocked
priority: P2
effort: "10h+"
dependencies: [2]
---

# Phase 10: Bronze data breadth

## Overview
**Conditional** — mở khi Vnstock trả lời văn bản 9 câu go/no-go
(`plans/reports/research-260829-2015-vnstock-bronze-full-power.md`) và user
quyết mua. Mở rộng **chiều rộng** dữ liệu qua `vnstock_data`: khối ngoại
(đang 0 dòng), BCTC sâu > 8 quý, ratio ngân hàng chuẩn, vĩ mô, sự kiện/cổ
đông. Mọi nguồn mới **chỉ** là một member enum `source` của `query` — tầng
compute/render không biết Bronze tồn tại.

## Requirements
- Functional:
  - Adapter `providers/vnstock_data.py` sau contract hiện có; `ProviderSource`
    vẫn một member `VNSTOCK` (source con ghi trong `source` text như
    `vnstock.VCI`).
  - Quota arbiter 4 cửa sổ (180/phút · 10.800/giờ · 50.000/ngày · 600.000/
    tháng) × hệ số an toàn 0,9; dùng chung process/container qua Redis (đã là
    cơ chế của `core/quota.py`); tier đọc từ env.
  - Nạp: `foreign_flow_daily` (bảng mới: symbol, trading_day, buy/sell value &
    volume, net) ≥ 250 phiên × 30 mã; `financial_scan_job` nới `periods` tối
    đa nguồn cho 30 mã declared (mục tiêu ≥ 20 quý); ratio taxonomy ngân hàng
    (NIM, CIR, NPL, CASA, LDR) vào `financial_ratio_snapshot` với `source`
    riêng; `macro_series` (bảng mới: series_id, date, value, unit, source);
    reference events/cổ đông vào `provider_snapshots` capability mới hoặc bảng
    riêng — quyết lúc thi công theo shape thật.
  - `query.source` += `foreign_flow, macro, events`; `foreign_flow_pressure.*`
    đọc `foreign_flow_daily` thay `realtime_events` → refusal
    `foreign_flow_not_stored` VCB 3 → 0 (sửa trong `signals/foreign_share_
    flow.py` — surface freeze, cần dòng amendment riêng khi mở phase).
  - Scheduler: job Bronze đăng ký cùng seam `backfill_daily`, **mặc định
    TẮT**, log WARNING khi stale.
- Non-functional: không đổi shape `bar_daily`/`BarDaily`; dependency mới
  (`vnstock_data`) **hỏi user** trước; key chỉ trong env, không log; device-id
  Docker/CI xác nhận trước khi cài trong container.

## Architecture
```
vnstock_data (Sponsor) → providers/vnstock_data.py → normalize → store (bảng theo capability)
                                                 ↑ core/quota.py (4 cửa sổ, Redis)
query(source=foreign_flow|macro|events) → frame  (không đổi compute/render)
```

## Related Code Files
- Create: `apps/api/src/stocks/providers/vnstock_data.py`, `src/stocks/
  foreign_flow_backfill.py`, `src/stocks/macro_backfill.py`, revision(s)
  `foreign_flow_daily`, `macro_series`
- Modify: `apps/api/src/core/quota.py:78-98` (4 cửa sổ), `src/core/config.py`
  (tier), `.env.example`, `docker-compose*.yml`, `requirements.txt` (sau khi
  hỏi), `src/stocks/financial/fetch.py` (periods), `financial_scan_job.py`,
  `src/stocks/signals/foreign_share_flow.py` (nguồn), `src/agent/tools/query.py`
  (enum), `src/alpha/models.py` (2 model), `Makefile` (3 target backfill)
- Tests: contract test bằng response thật đã được phép lưu (fixture), quota
  4 cửa sổ, `foreign_flow_pressure.*` phục vụ trên fixture

## Implementation Steps
0. Gate 0 của report Bronze: cài trong môi trường tách, smoke từng endpoint,
   ghi schema/unit/timezone/pagination thật; **backup DB** trước revision.
1. Hỏi user thêm dep; cài; adapter + contract tests.
2. Quota 4 cửa sổ + test bất đẳng thức từng cửa sổ (như `test_vnstock_quota.py`).
3. `foreign_flow_daily` + backfill 30 mã; `foreign_share_flow.py` đổi nguồn;
   đo VCB refusal.
4. BCTC sâu: nới periods, scan declared; đo số quý.
5. Ratio ngân hàng; nhãn vào `financial_statement_item`.
6. `macro_series` + backfill; `query.source=macro`.
7. Events/cổ đông theo shape thật.
8. Scheduler seam, mặc định tắt; docs Commands.

## Success Criteria
- [ ] `foreign_flow_not_stored` VCB 3 → 0; `foreign_flow_pressure.*` phục vụ 30 mã.
- [ ] 30 mã declared ≥ 20 quý BCTC; ratio ngân hàng có cho 4 ngân hàng Universe.
- [ ] `query(source=macro, series=[cpi_yoy, policy_rate])` trả frame.
- [ ] Quota: 0 lần vượt bất kỳ cửa sổ trong scan toàn thị trường (log đếm).
- [ ] Không thay đổi nào ở `studies/*` hay `apps/web` ngoài enum/label.

## Risk Assessment
- Device-id đổi khi rebuild container → khoá tài khoản; **không cài trong
  container** trước khi có xác nhận văn bản; chạy backfill từ host nếu cần.
- Quota tính theo page → scan toàn thị trường vượt ngày; arbiter đếm theo page
  khi nghi ngờ (cấu hình), đo thật rồi chốt.
- Licence: Bronze là dev — production vẫn Diamond + văn bản; plan này không
  đổi điều đó.

## Outcome — 2026-08-30

**Không mở được, và không viết code trước.** Phase này `Conditional` theo đúng
plan: cần Vnstock trả lời **bằng văn bản** 9 câu go/no-go
(`plans/reports/research-260829-2015-vnstock-bronze-full-power.md`, mục "Điều
kiện go/no-go" + mẫu tin nhắn đã soạn sẵn) và user quyết mua.

Hai câu trong chín câu quyết thiết kế, không phải quyết ngày bắt đầu:

- **Câu 3** — `get_all=True` tính một request hay từng page upstream, và quota
  có dùng chung giữa source/thiết bị/process không. Trả lời khác nhau ra hai
  arbiter khác nhau; viết trước là viết một cái rồi vứt.
- **Câu 4** — Docker rebuild / CI runner có bị tính là thiết bị mới không. Trả
  lời quyết backfill chạy ở host hay trong container, và đoán sai thì hậu quả là
  **khoá tài khoản**, không phải một lần chạy hỏng.

Không có bước nào của phase 10 độc lập với hai câu này, nên không có phần nào
làm trước được.
