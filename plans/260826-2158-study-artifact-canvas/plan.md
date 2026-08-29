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
| 01 | [Studies core + agent_artifact store](phase-01-studies-core-and-artifact-store.md) | A | — | **done** |
| 02 | [Intraday ingest vnstock 15m](phase-02-intraday-ingest-vnstock.md) | A | — | **done** |
| 03 | [Study intraday_liquidity_profile](phase-03-study-intraday-liquidity-profile.md) | A | 01, 02 | **done** |
| 04 | [Bundle `studies` + event canvas.ready](phase-04-agent-tools-and-canvas-ready-event.md) | A | 01, 03 | **done** |
| 05 | [Web canvas panel + widget registry v1](phase-05-web-canvas-panel-and-widget-registry.md) | A | **bước 0 (widgets trên fixture): chỉ cần 01-contracts — chạy song song 02–04**; wiring SSE: 04 | **done** |
| 06 | [get_series + composition render_canvas](phase-06-series-evidence-and-composition.md) | B | 05 | **done** |
| 07 | [Study entry_condition_review](phase-07-condition-review-study.md) | C | 06, 08a | **done** |
| 08a | [Spine daily market-wide `bar_daily`](phase-08-market-wide-daily-spine.md) | D | 02 | **done** |
| 08b | Luật price basis + xoá dòng fiinquant | D | 08a | **done** — giao ở `260828-2126-price-basis-and-signal-field-spine/` phase 02-08 (đóng 2026-08-29; 71.773 dòng đã xoá qua revision `a3f7e21b8d54`) |
| 09a | [Store BCTC quý + ratio + job quét](phase-09-financial-statement-store.md) | E | 08a | **done** |
| 09b | Signal Field `earnings.*` | E | 09a | **done** — giao ở `260828-2126-price-basis-and-signal-field-spine/` phase 09 (ba field `earnings.*`, registry 30 → 33) |
| 10 | [Study earnings_dislocation_screener](phase-10-earnings-screener.md) | E | 06, 08a, 09a | **done** |

Song song, không chặn code: **email `support@vnstocks.com` xin điều khoản
thương mại bằng văn bản** (R1 — chặn ngày launch). Việc của user, plan chỉ nhắc.

## Sửa lại spec khi thi công (2026-08-26, đo thật)

Phase 02 probe live `Quote(source="VCI")` trên STB (75 phiên) + SHS (70 phiên).
Ba chỗ spec trong plan lệch dữ liệu thật; code theo dữ liệu:

1. **ATC nằm ở bucket `14:45`, không phải `14:30`.** Đấu giá đóng cửa *chạy*
   14:30–14:45 nhưng không khớp gì tới lúc đóng, nên bucket `14:30` rỗng ở
   **mọi phiên đo được** và toàn bộ volume ATC — bucket lớn nhất phiên của
   phần lớn mã — mang nhãn `14:45`. Window viết theo giờ đấu giá sẽ **xoá
   sạch** volume ATC.
2. **Grid là union hai sàn.** HNX/UPCoM giao dịch liên tục từ `09:00`; HOSE
   khớp ATO vào bucket `09:15`. Grid gồm 17 bucket; mã HOSE không bao giờ có
   cột đầu, và đó không phải lỗ dữ liệu.
3. **Giá vnstock intraday là nghìn VND** (74.5); store dùng `price_unit: VND`
   (74900.0). Scale ×1000 một lần ở ingest.

Lệch thiết kế có chủ ý so với plan (ghi để phase sau không hiểu nhầm):

- **4 frame, không 3** — thêm frame `tiles` (table) vì `stat_tiles` phải vẽ từ
  một frame, không vẽ từ headline.
- `compute` dùng Python thuần + `statistics.median` trên row đã typed thay vì
  pandas; pandas vẫn dùng ở ingest. Ít một lần chuyển đổi hai chiều.
- Headline dùng `peakAvgAmount` (không `peakAvgVolume`) vì `metric` có thể là
  `value`.
- `StudyDefinition` khai thêm `frames` + `widgets` (tuple) để kiểm widget được
  **lúc import**, không đợi một câu hỏi thật.
- `agent_artifact.turn_id`/`thread_id` nullable — Study cũng chạy ngoài Turn
  (smoke, precompute sau này).
- `sessions` **kẹp** 10–60 thay vì refuse: `sessionsUsed` trong headline đã nói
  đúng số phiên thật đọc được, nên một vòng round-trip "60 là max" không mua
  thêm gì.

## Sửa lại spec khi thi công (2026-08-27, phase 04–06)

Bốn chỗ code đi khác plan, và lý do:

1. **`run_study` nhận tham số phẳng, không nhận `{name, params}`.** Strict mode
   viết lại mọi object với `additionalProperties: false`
   (`core/llm/protocol.py`), nên một `params` tự do thành object **không nhận
   được key nào**. Tham số của mọi Study nằm cạnh nhau trên một object;
   `_check_the_parameters_agree()` từ chối build khi hai Study hiểu khác nhau
   về một tên; handler chỉ chuyển cho Study đúng những key nó khai.
2. **Ingest on-demand qua tham số `warm` của runner, không phải mặc định.**
   `runner.run(..., warm=None)` giữ runner offline cho suite và smoke; lane chat
   truyền `warmup.warm`. Bảng requirement → hàm fetch ở `src/studies/warmup.py`;
   tên khai được nằm ở `contracts.KNOWN_REQUIREMENTS` để registry kiểm lúc
   import mà không kéo vnstock vào mọi import của `src.studies`.
3. **Danh sách canvas nằm trên `agent_message.content`, không join.** Chỉ id +
   title + blockCount — **không** spec, **không** frames. Cùng khuôn với
   `tool_calls` vốn đã nhân bản từ `agent_tool_call`, và transcript đọc được
   ngay trong lần đọc nó vẫn làm.
4. **`canvas.ready` do loop phát, không do handler.** Handler thuần (không cầm
   publisher); loop đọc `result.payload` qua `messages.canvas_of` đúng chỗ nó đã
   đọc `outcome_of`/`display_results`. `TurnPublisher` protocol gọi
   `canvas_ready` qua `getattr`, nên transport cũ vẫn chạy Turn có canvas.

### Ba lỗi phase 03 sửa cùng đợt này (audit `code-reviewer-260826-2255`)

- **`avg_share`/`avg_amount` chia theo số phiên trong cửa sổ**, không theo số
  phiên bucket *xuất hiện*. Trước đó một bucket khớp 1/30 phiên được tính như
  bucket bận nhất ngày, và `phaseSummary` cộng ra 1,25 trên dữ liệu thật.
  `median` cũng đệm 0 cho các phiên bucket vắng, cùng một lý do. Bucket vắng ở
  **mọi** phiên (09:00 của mã HOSE) vẫn bị loại khỏi thống kê — đó là khung giờ
  sàn không có, không phải khung giờ ế.
- **Spike đo được thay vì phá hoà theo đồng hồ.** `_spiking()` chỉ tính bucket
  **lớn hơn hẳn** giá trị lớn nhất nằm ngoài top 2; phiên hoà nhau ở mức cắt
  không cho ai điểm, phiên có ≤2 bucket cũng vậy. Trong chính fixture cũ,
  `09:15` được `30/30` và `09:30` được `9/30` dù volume hai bucket giống hệt
  nhau ở mọi phiên — giờ là `0/30`.
- **Bucket provider gửi trùng không còn abort transaction.** `ON CONFLICT DO
  UPDATE` từ chối statement có key trùng trong chính values của nó
  (`CardinalityViolation`, abort cả transaction). `_deduplicated()` giữ giá trị
  sau cùng trước khi dựng statement — lane chat chạy ingest và ghi artifact
  trong **một** session, nên lỗi này sẽ nuốt luôn câu trả lời.

Fixture đã sinh lại (`make contracts`); `peakShare`/`phaseSummary` không đổi,
`occurrence` của các bucket không phải đỉnh về `0/30`.

Ngoài ra: `get_series` kẹp **hai** trần — `MAX_SERIES_SESSIONS=120` cho bức
tranh và `MAX_WINDOW_READS=12.000` cho chi phí thật (`điểm × window`), nên một
field 273 phiên chỉ được ~44 điểm. `frame_id` địa chỉ hoá là `<artifactId>` cho
frame đơn và `<artifactId>#<tên>` cho frame của Study.

## Kết quả nghiệm thu phase 04–06

- `make test` (apps/api, host): **1060 pass** (baseline sau phase 03: 1025).
- `pnpm type-check` · `lint` · `test` (**435 pass**) · `build` tại apps/web: xanh.
- `pnpm test:e2e streaming.spec.ts canvas.spec.ts`: **6 pass** — gồm hai case
  canvas mới đi hết ba chặng (browser → Next → FastAPI thật).
- Bundle: route `/` giảm còn **82,2 kB** (First Load 214 kB) — recharts nằm sau
  `next/dynamic` của panel canvas, nên lane chat không trả phí chart lib.
- 12 tool: 8 cũ + `list_studies` · `run_study` · `get_series` · `render_canvas`.
  `PROMPT_VERSION` 2.4.0 → **2.6.0** (thêm tên tool vào prompt; catalog Study
  vẫn đến qua schema).

### Nợ để lại, đã đo

- `e2e/market-monitor.spec.ts` (2 case) **đỏ từ trước**: nó kiểm surface đã bị
  rip 2026-08-25. Nên xoá cùng PR dọn e2e, không thuộc phạm vi phase này.
- `e2e/desk.ts::CANONICAL_MARK` trỏ nút "Báo lỗi câu trả lời" không còn tồn tại
  (đổi thành "Chưa đúng" ở `dc35b37`) — đã sửa, vì nó làm hai case streaming đỏ
  và che mất cổng của chính phase 05.
- `scripts/smoke_canvas.py` + `make smoke-canvas` đã có; **chưa chạy** vì tốn
  model call thật. Perf budget của plan chưa được đo.
- Audit phase 01–03 còn các mục **chưa** sửa:
  `_round` dùng ROUND_HALF_EVEN nên `_round(0.5)` ra `0`; volume `NaN` kèm giá
  hợp lệ ném `ValueError` trần; lỗ hổng ở giữa cửa sổ không được nạp lại và
  `health` vẫn báo `normal`; mã có ít phiên hơn số hỏi thì lần nào cũng refetch
  cả năm; `reads.latest_closed_session` không có caller.

## Kết quả nghiệm thu phase 01–03

- `make test` (apps/api, host): **1024 pass** (baseline trước phase 01: 940).
- `pnpm type-check` · `lint` · `test` (**406 pass**) · `build` tại apps/web: xanh.
- Alembic: một head `c2e94a7b1f30`; `downgrade -1` → `upgrade head` sạch cho cả
  hai revision mới.
- Smoke ingest thật: `ensure_bars('STB', sessions=30)` → 3.985 dòng / 250 phiên
  (15,94 bucket/phiên ≈ 16 của HOSE); chạy lần hai: **row count không đổi**.
- Smoke study thật trên STB 30 phiên: `peakWindow=14:45`, share 0,1307,
  occurrence 14/30, `phaseSummary.pm=0,5788`. Đỉnh thuộc {14:45, 14:00, 14:15}
  — đúng tập probe đã đo trước khi code.
- Backup trước migration: `backups/pre-agent-artifact-260826.sql.gz` (5,8M).

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

## Quyết định 2026-08-27 — vì sao 08 tách hai và 07 đi sau nó

Đo trước khi thi công: `bars.py::_basis_of` chỉ serve window **toàn `raw`**, và
vnstock **không có** giá chưa điều chỉnh cho thị trường VN (probe bản đang cài:
chỉ connector `fmp` có `adj_type`). Dòng `raw` duy nhất trong store là 36.528
dòng **fiinquant** — nguồn đã tuyên bố vi phạm ToS. Ba hệ quả:

1. **07 không tự ingest daily được** theo cách plan viết ("ghi
   `provider_snapshots` để tái dùng reader `signals/bars.py`") — reader từ chối
   mọi dòng vnstock. Nên 07 đi **sau** 08a và chỉ đọc store.
2. **08 tách hai.** 08a dựng `bar_daily` (bảng typed mới, ghi `price_basis`
   thành cột) — không đụng đường đọc của signals, blast radius bằng 0. 08b là
   quyết định đổi luật basis của core rồi mới xoá fiinquant; nó đổi con số 25
   Signal Field báo ra nên không đi kèm một backfill.
3. **Acceptance #6 chưa đạt sau 08a** — nêu thẳng thay vì đánh dấu done.

Hai số đo đổi cách chia việc: provider chặn **~2.000 dòng/call** (lấp ngược từ
`end`; STB và VNINDEX cùng trả 1.997 dòng từ 2018-08-29), và thị trường có
**1.523 mã STOCK listed** (HSX 405 · HNX 299 · UPCOM 819), không phải ~1.700 —
`all_symbols()` 1.751 gồm cả bond, CW, ETF, future.

## Rủi ro cấp plan

- **R1 licence** — không chặn dev, chặn launch. Theo dõi ngoài plan.
- **R2 provenance FiinQuant** — phase 07 dùng giá gần đây: tự vá bằng
  backfill daily 52w cho declared trong chính phase đó; xoá triệt để ở 08.
- **R3 vnstock không SLA** — mọi ingest idempotent + retry; store phục vụ.
- **R5 mapping BCTC theo ngành** — cô lập trong phase 09, có golden test
  per-industry-template trước khi screener (10) được tin.

## Plan chạy song song — điểm giao duy nhất

`plans/260827-2325-evidence-led-chat-surface/` (UX + harness cho lane chat) chạy
song song từ 2026-08-27 và **chặn ở đúng một chỗ**: phase 08 của nó thêm 3 cột
additive trên `agent_thread` và **không được tạo alembic revision trước khi
phase 09a ở đây merge** — `alembic heads` phải trả một dòng.

Plan đó không đụng `src/stocks/*`, không đụng `src/studies/*`, không bump
`PROMPT_VERSION`, và không đổi cấu trúc vòng tool của `loop.py` (chỉ đổi trần qua
tham số ở phase 09 của nó). Hai chỗ nó **đọc** kết quả của plan này: `bar_daily`
+ `bar_intraday_15m.observed_at` cho độ mới dữ liệu, và `Provenance{as_of, health,
sessions_used}` làm vốn từ cho tóm tắt bằng chứng — nên vốn từ đó không được đổi
tên mà không nói.

Test giữ luật của plan này (`frames` không reachable trong transcript,
`test_agent_study_tools.py:155,178`) là **cổng cứng** của phase 10 bên đó.
