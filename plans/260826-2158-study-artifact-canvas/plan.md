# Plan: Study → Artifact → Canvas

Nguồn quyết định: `plans/reports/proposal-260826-2107-ai-core-dynamic-canvas.md`
(đề xuất đã được user duyệt 2026-08-26) + 4 câu trả lời chốt:

1. **Issue #34 đảo có phạm vi** — canvas panel nhiều widget; transcript giữ
   text-trước, ≤1 widget inline. Giữ mọi luật khác của #34 (typed registry có
   version, as-of đóng băng, degrade thay vì crash, dãy số không qua model).
2. **Chart lib: recharts** (^3.x) + SVG tự vẽ cho `session_heatmap`,
   `range_strip`. User giao quyết theo chất lượng — đã chốt, không hỏi lại.
3. **Case 3 = Condition Review** — không verdict chỉ thị, không nhãn PREFERRED.
4. **Phạm vi: chi tiết cả A–E** (10 phase files dưới).

## Nguyên tắc xuyên suốt

- Model chọn Study + điền params + diễn giải. **Engine tính, artifact giữ số,
  registry vẽ.** `frames` không bao giờ vào context model.
- Mọi thêm tool đi qua `registry`/`toolsets`/`definitions` — không hardcode
  trong `loop.py`. Catalog Study đến qua schema tool, không qua prompt.
- Ingest idempotent, store là nguồn phục vụ; canvas không gọi provider trực
  tiếp (vnstock không SLA — R3).
- vnstock đi qua `vnstock.api.{quote,financial,listing}` (đường mới), bọc bằng
  `safe_vnstock_call`.
- Trước mọi migration/bulk-update: backup DB (`pg_dump` vào `backups/`,
  không commit).

## Trạng thái & phases

| # | Phase | Nhóm | Phụ thuộc | Trạng thái |
|---|---|---|---|---|
| 01 | [Studies core + agent_artifact store](phase-01-studies-core-and-artifact-store.md) | A | — | pending |
| 02 | [Intraday ingest vnstock 15m](phase-02-intraday-ingest-vnstock.md) | A | — | pending |
| 03 | [Study intraday_liquidity_profile](phase-03-study-intraday-liquidity-profile.md) | A | 01, 02 | pending |
| 04 | [Bundle `studies` + event canvas.ready](phase-04-agent-tools-and-canvas-ready-event.md) | A | 01, 03 | pending |
| 05 | [Web canvas panel + widget registry v1](phase-05-web-canvas-panel-and-widget-registry.md) | A | **bước 0 (widgets trên fixture): chỉ cần 01-contracts — chạy song song 02–04**; wiring SSE: 04 | pending |
| 06 | [get_series + composition render_canvas](phase-06-series-evidence-and-composition.md) | B | 05 | pending |
| 07 | [Study entry_condition_review](phase-07-condition-review-study.md) | C | 06 | pending |
| 08 | [Spine dữ liệu market-wide (trả nợ FiinQuant)](phase-08-market-wide-daily-spine.md) | D | 02 | pending |
| 09 | [Store BCTC quý market-wide](phase-09-financial-statement-store.md) | E | 08 | pending |
| 10 | [Study earnings_dislocation_screener](phase-10-earnings-screener.md) | E | 06, 09 | pending |

Song song, không chặn code: **email `support@vnstocks.com` xin điều khoản
thương mại bằng văn bản** (R1 — chặn ngày launch). Việc của user, plan chỉ nhắc.

## Phát hiện sửa lại restore map

`phase-07` cũ của restore map nói bảng `bar_intraday_5m/15m`,
`session_metric_bucket` "còn trong DB — chỉ reconnect". **Sai** — kiểm
`pg_tables` 2026-08-26: không tồn tại. Phase 02 tạo bảng mới qua alembic
revision (additive, downgrade = drop được phép vì bảng mới).

## Branch & freeze

- Branch: `feat/study-canvas` cắt từ `refactor/harness-first` (rip-out lớn
  dùng branch riêng theo quy ước CLAUDE.md).
- Phase 01 amend CLAUDE.md: ghi quyết định canvas dynamic đã chốt, mở freeze
  cho `src/studies/*` (mới), `src/stocks/intraday/*` (mới), bundle `studies`
  trong `src/agent/`, và surface canvas trong `apps/web`. Freeze phần còn lại
  của `src/stocks/*` giữ nguyên tới Phase 08.

## Acceptance criteria toàn plan (đo, không cảm)

1. Câu hỏi tiếng Việt về thanh khoản trong phiên của mã declared → canvas
   4 block, số khớp `intraday_liquidity_profile` tính lại độc lập.
2. `frames` không xuất hiện trong bất kỳ message nào gửi model — kiểm bằng
   test đọc transcript.
3. Mở lại thread render đúng slice cũ, `asOf` không đổi.
4. Widget version không biết → `data_table` fallback, transcript không crash.
5. Study thứ hai (phase 07) thêm được **không sửa `loop.py`, không sửa prompt
   contract, không bump PROMPT_VERSION** (bump ở phase 07 là do luật framing,
   không do cơ chế Study).
6. Sau phase 08: `provider_snapshots` capability MARKET/VALUATION cho cửa sổ
   phục vụ không còn dòng `source=fiinquant`; VN-Index daily có dữ liệu.
7. Mỗi phase xanh: `make test` (apps/api, host) + `pnpm type-check && pnpm
   lint && pnpm test && pnpm build` (apps/web).

## Perf budget (bổ sung audit 2026-08-26 22:15)

Nguồn: `plans/reports/audit-260826-2215-study-canvas-bottlenecks.md` (N1–N12,
đã vá vào từng phase). Acceptance thêm:

| Mốc | Target P50 |
|---|---|
| Câu hỏi → `canvas.ready` (store ấm / ingest lạnh 1 mã) | ≤ 8s / ≤ 12s |
| `canvas.ready` → skeleton hiển thị | ≤ 1s |
| Fetch artifact → widgets interactive | ≤ 2,5s |
| Tool-choice smoke 5 câu chuẩn | `run_study` đúng params ≥ 4/5 |

Đo bằng `scripts/smoke_canvas.py` (phase 04). Tiền đề chưa đo: latency route
LLM (luna qua proxy) — đo trước khi cam kết 8s là đạt được.

## Rủi ro cấp plan

- **R1 licence** — không chặn dev, chặn launch. Theo dõi ngoài plan.
- **R2 provenance FiinQuant** — phase 07 dùng giá gần đây: tự vá bằng
  backfill daily 52w cho declared trong chính phase đó; xoá triệt để ở 08.
- **R3 vnstock không SLA** — mọi ingest idempotent + retry; store phục vụ.
- **R5 mapping BCTC theo ngành** — cô lập trong phase 09, có golden test
  per-industry-template trước khi screener (10) được tin.
