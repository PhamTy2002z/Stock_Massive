# Phase 01 — Mở freeze và chốt nền

Plan: `plans/260828-2126-price-basis-and-signal-field-spine/`
Nhánh: `feat/study-canvas-runtime` · 2026-08-28

## Nền xanh — mốc mọi phase sau so vào

Đo trên host, DB container `stockmassive-db-1`.

| Cổng | Kết quả | Ghi chú |
|---|---|---|
| `make test` (apps/api) | ✅ **1305 passed**, 35,35 s | plan ghi 1284; con số đã tăng, mốc thật là 1305 |
| `pnpm type-check` (apps/web) | ✅ | |
| `pnpm lint` (apps/web) | ✅ sạch | |
| `pnpm test` (apps/web) | ✅ **645 passed / 52 file**, 15,08 s | plan ghi 616/50 |
| `pnpm build` (apps/web) | ✅ 9/9 static page, First Load JS chung 103 kB | `/` = 227 kB |

`pnpm dev` được dừng (PID 77136) trước khi build và khởi động lại sau (PID
92256) — đúng phản ứng đã ghi trong Risk Assessment.

## Amendment freeze

`CLAUDE.md` §"Hard freeze ngoài `src/agent/*`" nhận một khối **Mở thêm
2026-08-28** với bảng tám surface kèm giới hạn từng cái, và câu chốt *"Bảng này
**là** ranh giới"*. Phần vẫn freeze được viết lại cho đúng phần còn lại:
`realtime/*`, `providers/normalize.py`, `models.py` ngoài bảng mới.

Tám surface: `trading_day.py` · `signals/{sessions,bars}.py` ·
`signals/corporate_actions.py` · `signals/{price_band,market_behavior}.py` ·
`signals/{registry,serving,issues,cross_sectional,foreign_flow,fields}.py` ·
`providers/{contracts,store}.py` · `schemas/snapshot.py` ·
`signals/earnings.py` (mới, cho Phase 09).

So với bảng trong phase file, đã thêm `signals/fields.py` vào nhóm Phase 04:
trường `projection` sống trên `SignalField`, nên file đó bị sửa và phải nằm
trong bảng thay vì được nới thầm lúc thi công.

## `docs/roadmap.md` §S0

Kiểm trước khi sửa, đúng như bước 5 yêu cầu:

- Dòng tiêu đề đã là `**Current / đang đóng**` → không đụng.
- Checklist "Contract test cố định *frames không vào message* ở tầng
  transcript" → **đã tick**, có bằng chứng:
  `tests/test_agent_study_tools.py::test_the_frames_are_absent_from_the_messages_a_turn_would_send`
  và `::test_the_frames_stay_out_of_a_signal_desk_turn_too`.
- Checklist "Đóng nhánh `feat/study-canvas-runtime`" → **để nguyên**. Cổng đã
  xanh nhưng nhánh chưa đóng, và plan `260826-2158-study-artifact-canvas/`
  còn hai mục 08b/09b trỏ sang plan này.

## Commit

Working tree đi từ 244 mục (`-uall`) về 0 file code, qua sáu commit:

| Commit | Nội dung |
|---|---|
| `fc5b520` | `feat(db)` — ba alembic revision `d4a71c9e5b82`, `e6b3d90c41af`, `f8c2d4a96e17` + `stocks/models.py` + `alpha/models.py` |
| `b1c169c` | `feat(stocks)` — `vnstock_daily.py`, `backfill_daily.py`, `financial/*`, roster + universe market half |
| `4ed903f` | `feat(studies)` — condition review, earnings dislocation, hai reads, contract regenerated |
| `7006aaa` | `feat(agent)` — bundle `studies`, `TurnMode=signal_desk`, `usage.py`, Makefile/scripts rename |
| `093efc7` | `feat(web)` — surface Signal Desk, rename `components/canvas/*` → `components/signal-desk/*` |
| (docs) | `CLAUDE.md`, `docs/roadmap.md`, plans + reports |

Ba revision đi **commit đầu tiên** cùng model của chúng — plan yêu cầu chúng đi
riêng và đi trước; gộp model vào cùng commit vì một revision không có model là
một schema không tái tạo được từ code, mà tái tạo được chính là lý do bước này
tồn tại (Phase 08 restore vào DB tạm).

## Hai thứ dọn thêm, ngoài checklist

1. **`.claude/agent-memory/`** — scratch của subagent, chưa bị ignore. Thêm vào
   `.gitignore`; không commit.
2. **`apps/web/next-env.d.ts`** trỏ `./.next-verify/types/routes.d.ts` — dấu vết
   một lần chạy E2E với `E2E_NEXT_DIST_DIR`. Trả về `./.next/...`; đây là file
   Next tự sinh, không phải thay đổi cố ý.

## Việc còn nợ, phát hiện khi chạy

- **`Makefile` còn năm target `eval-*`** trỏ `python -m src.eval`, mà `src/eval`
  đã bị rip 2026-08-22. Chúng chết. Không thuộc tám surface của plan này nên
  không đụng; ghi ra để không ai tưởng chúng chạy được.
- **Phase 04 có một success criterion chưa đạt được ở Phase 04.**
  `adtv_percentile` trả số cần `SessionSnapshot.total_value_vnd`, mà `bar_daily`
  **không có cột traded value** (`models.py` nói thẳng: *"There is no
  traded-value column"*). Suy diễn `close × volume` là Phase 05. Sau Phase 04,
  `adtv_percentile` không còn bị **projection** khoá, nhưng vẫn refuse vì thiếu
  input. Criterion cần đọc là "projection không còn là lý do từ chối"; số thật
  đến ở Phase 05.

## Bốn quyết định chốt với user 2026-08-28 22:3x

Chúng chi phối Phase 02–03, ghi ở đây vì phase sau đọc report này:

1. **Lịch giao dịch định nghĩa trên `series='index'` (VNINDEX).** Đo lại: hai
   phương án (index vs Universe-30) cho **kết quả giống hệt** — cùng 3.991
   phiên, 0 ngày lệch hai chiều.
2. **Giữ `bar_daily` tươi bằng Makefile target + cron ngoài app**, kèm chốt chặn
   cuối tuần/tương lai ở biên ingest và cảnh báo khi `max(observed_at)` quá cũ.
3. **Golden test Phase 03 = bất biến tỉ lệ trong suite + báo cáo lệch thật ngoài
   suite.** Dung sai tuyệt đối bằng 0 là bất khả thi giữa hai phương pháp adjust
   khác nhau; field tính theo mức VND (`macd_12_26_vnd`) khai rõ là **đổi**.
4. **R7: dựng lại nhánh STORE của `check_price_claim`** trên giá đã điều chỉnh,
   có dung sai, và **chỉ khi** không có corporate action ex-date nào giữa phiên
   đó và hôm nay. Nhánh BAND vẫn mất — nó cần giá tham chiếu thô.

## Success Criteria

- [x] `CLAUDE.md` liệt kê đủ tám surface kèm giới hạn
- [x] Năm cổng xanh, con số ghi lại làm mốc
- [x] `git status --porcelain` rỗng; ba alembic revision đã vào git
- [x] `docs/roadmap.md` §S0 đúng trạng thái (kiểm trước khi sửa)
