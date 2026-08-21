---
phase: 6
title: "Ngân sách tool và thang guardrail"
status: complete
priority: P2
effort: "2-3d"
dependencies: [2, 5]
---

# Phase 6: Ngân sách tool và thang guardrail

## Overview

Hai việc: chống tràn context từ kết quả tool theo ba tầng, và thay bước nhảy
"allow → kết thúc Turn" bằng thang `allow → warn → block → halt` với halt rất muộn.

## Requirements

- Functional: kết quả tool lớn được giữ lại trên đĩa và thay bằng preview +
  tham chiếu, thay vì cắt cụt.
- Functional: gọi lặp một tool vô nghĩa được **cảnh báo** trước, chỉ halt khi lặp nhiều.
- Non-functional: controller guardrail không có tác dụng phụ — trả quyết định,
  runtime quyết biến nó thành gì.
- Non-functional: tool không rõ hình dạng mặc định coi là **có tác dụng phụ**
  (an toàn mặc định cho cái không biết).

## Architecture

### 6.1 Ba tầng chống tràn

Mẫu `tool_result_storage.py` của Hermes, nguyên văn: *"Defense against
context-window overflow operates at three levels."*

| Tầng | Cơ chế | Ta có gì |
|---|---|---|
| 1 | Mỗi tool tự cắt output trước khi trả | có — `MAX_TOOL_RESULT_BYTES` |
| 2 | Sau khi tool trả, vượt ngưỡng riêng của tool → lưu đầy đủ, trong context chỉ còn preview + đường dẫn | **chưa có** |
| 3 | Sau khi gom **mọi** kết quả tool của một lượt, tổng vượt trần → spill cái lớn nhất tới khi dưới trần | **chưa có** |

Tầng 3 là tầng ta thiếu quan trọng nhất: nhiều kết quả cỡ trung cộng lại tràn.

Phân giải ngưỡng theo khuôn `budget_config.py`: `pinned > config > registry >
default`. Ta đã có `data_ref` trong ý tưởng `docs/specs/0004` W1 — tầng 2 chính
là chỗ nó thuộc về.

Nơi lưu: ta không có sandbox, nên đơn giản hơn Hermes — lưu vào Postgres cạnh
`agent_tool_call.result`, hoặc một bảng phụ. **Không** dùng đĩa: worktree song
song và container ephemeral làm đường dẫn đĩa không đáng tin.

### 6.2 Thang guardrail

Mẫu `tool_guardrails.py`. Controller thuần, không tác dụng phụ:
*"Runtime code owns whether those decisions become warning guidance, synthetic
tool results, or controlled turn halts."*

Ngưỡng mặc định của Hermes — chú ý halt **rất** muộn:

| Điều kiện | Ngưỡng |
|---|---|
| Cùng một lời gọi y hệt thất bại | warn sau **2** |
| Cùng một tool thất bại | warn sau **3** |
| Tool idempotent không tạo tiến triển | warn sau **2** |
| Cùng một tool thất bại | **halt sau 8** |

Với `MAX_TOOL_ROUNDS = 4` của ta, halt-sau-8 không đạt được — nên ngưỡng phải
scale theo ngân sách round, không copy số. Đây là chỗ **không** được bắt chước số.

Hai frozenset cần phân loại tool của ta: idempotent (đọc store, web_search,
fetch_url, recall_facts) vs có tác dụng phụ (remember_fact, và mọi tool MCP/
không rõ — theo `tool_result_classification.py`: *"Unknown/plugin/MCP tools stay
effect-capable by default."*)

### 6.3 Gợi ý phục hồi trong lỗi tool

Mẫu `terminal_hints.py`: khi tool lỗi, stderr thô làm model đi sai hướng. Họ đào
tần suất từ DB sản xuất (*"a 250k-terminal-result window"*) rồi map hình dạng lỗi
phổ biến sang **một** câu gợi ý hành động kế tiếp.

Ta đã có `refusal_reason` trong `tools/catalog.py`. Nới nó mang gợi ý: refuse vì
Window Health thì nói rõ tool nào có cửa sổ ngắn hơn phục vụ được.

Quy tắc thiết kế của họ đáng giữ: chỉ khi lỗi; tối đa **một** gợi ý, khớp đầu
tiên thắng; chỉ quét đầu output; gợi ý nói **hành động kế tiếp**, không phải bài
chẩn đoán; hàm thuần, không I/O.

## Related Code Files

- Modify: `apps/api/src/agent/tools/catalog.py` — ngưỡng mỗi tool, gợi ý phục hồi
- Create: `apps/api/src/agent/tools/spillover.py` — tầng 2 + 3
- Create: `apps/api/src/agent/guardrails.py` — controller thuần, thang quyết định
- Modify: `apps/api/src/agent/loop.py` — gọi guardrail, áp quyết định
- Modify: `apps/api/src/agent/persistence.py` — lưu kết quả tool đầy đủ
- Modify: `apps/api/alembic/versions/` — migration cho bảng/cột spillover
- Modify: `apps/api/tests/test_agent_tool_catalog.py`, `test_agent_tool_suite.py`

## Implementation Steps

1. **Backup DB trước migration** (luật bắt buộc của repo).
2. Migration: chỗ lưu kết quả tool đầy đủ.
3. Tầng 2: vượt ngưỡng riêng → lưu, thay bằng preview + `data_ref`.
4. Tầng 3: tổng mỗi lượt vượt trần → spill cái lớn nhất trước.
5. Controller guardrail thuần + test bảng quyết định.
6. Nối vào `loop.py`: warn thành guidance trong message tổng hợp (dùng lại cơ chế
   nudge Phase 2), halt thành terminal.
7. Ngưỡng scale theo `MAX_TOOL_ROUNDS`, không copy số của Hermes.
8. Gợi ý phục hồi trong `refusal_reason`.
9. `make test`. **Eval Report** — phase này chạm tool catalog và
   `tool_catalog_version`, nên phải đóng băng lại Eval Fixture.

## Success Criteria

- [x] DB đã backup trước migration (cả DB Docker và DB host mà test dùng)
- [x] Kết quả tool lớn: context chỉ còn preview + `spilled_ref`, bản đầy đủ truy được
- [x] Tổng kết quả một lượt vượt trần → spill, Turn không tràn context
- [x] Controller guardrail không có tác dụng phụ (test: gọi 100 lần, không state ngoài)
- [x] Tool không rõ hình dạng mặc định là có-tác-dụng-phụ (test)
- [x] Ngưỡng halt scale theo `MAX_TOOL_ROUNDS`, có test cho biên (4 round và 2/8 round)
- [x] Gợi ý hành động trong kết quả bị từ chối, tối đa một, bảng đóng
- [x] `tool_catalog_version` **không** đổi → Eval Fixture **không** phải đóng băng lại
- [x] `make test` xanh (2.755 passed)
- [ ] Eval Report — nợ, gộp vào gate run Phase 8

## Risk Assessment

**Rủi ro**: spill làm model mất dữ liệu nó cần, trả lời tệ hơn. **Tín hiệu**:
`answer_kinds.analysis` giảm sau phase này. **Phản ứng**: nâng ngưỡng tầng 2;
preview phải mang đủ hình dạng để model biết có gì trong `data_ref`.

**Rủi ro**: migration trên bảng `agent_tool_call` đang có dữ liệu. **Phản ứng**:
backup trước; cột mới nullable, thuần cộng thêm.

**Rủi ro**: copy ngưỡng 8 của Hermes vào hệ có 4 round → halt không bao giờ chạm,
guardrail thành vô dụng. **Tín hiệu**: `halt` count = 0 mãi. **Phản ứng**: ngưỡng
phải là hàm của `MAX_TOOL_ROUNDS` ngay từ đầu, không phải hằng số.

**Assumption có thể vỡ**: giả định tràn context do kết quả tool là vấn đề thật.
Nếu ops cho thấy `ContextOverflow` (Phase 1 phân loại) gần bằng 0, tầng 2/3 là
giải pháp cho vấn đề không tồn tại — khi đó **hoãn** phase này và làm Phase 7 trước.

## Rollback

Cờ tắt spillover; cột migration nullable nên giữ được. Guardrail có cờ riêng.

---

## Kết quả thực hiện (2026-08-21)

**Status: Complete.** `ADR-0024` ghi quyết định. Migration `a4c71d9e5b28`.

### Bằng chứng đo được trước khi chọn ngưỡng

Truy vấn trực tiếp store dev (60 ngày traces, 30 ngày turns):

| Đo | Giá trị |
|---|---|
| Kết quả tool lớn nhất từng trả về | **2.267 byte** (`web_search`), trần mỗi tool là 4.096 |
| Trung bình một kết quả | ~1.200 byte |
| Turn "béo" nhất | 61 KB / 62 call / 4 round |
| `context_overflow` trong 30 ngày | **0** |

Đây chính là "assumption có thể vỡ" mà plan nêu: tràn context **chưa** là vấn đề đo
được. Quyết định: **không hoãn phase**, nhưng đặt ngưỡng **trên** mọi kết quả đã đo
thay vì ở nửa trần như mẫu Hermes:

- tầng 2 mặc định = 3/4 trần mỗi tool (3.072 byte) → hôm nay không bắn cho tool nào
  đã đo; nó bắn cho hai ca **không** có trong lịch sử đó: tool phình payload (12 quý
  statement là hình dạng W1 vừa mở ra) và tool MCP (không khai báo gì, hình dạng
  chưa ai đọc);
- tầng 3 trần lượt = 1/4 ngân sách constructed-context (~24 KB) → Turn béo nhất
  (~15 KB/round) vẫn không chạm.

Ghi rõ trong ADR-0024 rằng đây là **guard vũ trang trên mức traffic đã đo**, không
phải bản sửa cho một lỗi đã thấy.

### Sáu quyết định phải lấy khác plan

1. **`spilled_ref`, không phải `data_ref`.** `data_ref` đã bị chiếm: `get_price_series`
   trả Data Reference ở key đó và `widgets.py` resolve nó. Ghi spill descriptor vào đó
   biến mọi widget bind vào series bị spill thành `wrong_binding`. `data_ref` và
   `registered_fields` vào `PRESERVED_KEYS` — cắt `registered_fields` là mất một
   citation qua `unknown_field_path`.
2. **Spill chỉ áp lên bản transcript.** Bản đầy đủ đã nằm ở `agent_tool_call.result`.
   Model chỉ citate được cái nó thấy, nên `TraceIndex` resolve trên cùng bản preview —
   nhất quán, không có đường citate vào phần nó không thấy.
3. **Trail chiếu trước, spill sau.** `progress.sources_of` đọc kết quả tool; đảo thứ tự
   làm danh sách nguồn dưới câu trả lời ngắn đi theo một ngân sách context người đọc
   không thấy.
4. **Ngưỡng mỗi tool khai báo ở registration** (`ToolSpec.result_budget_bytes`), không
   phải bảng trong `spillover.py`. Sáu tool khai báo full trần (payload *là* câu trả
   lời): `web_search`, `fetch_url`, `screen_universe`, `search_news`, `get_analysis`,
   `get_financials` (periods vừa là câu trả lời vừa là binding của widget quý).
5. **Retry vẫn của `ToolAttempts`.** Call *thất bại* **không** đưa vào history của
   ladder: hai guard cùng đếm một sự kiện thì lần retry thứ hai mà policy cho phép bị
   guardrail chặn. Bắt được đúng bằng test có sẵn (`capped_at_two_attempts` tụt xuống 1).
6. **Trùng trong cùng một lượt bị block thẳng**, không đi theo rung. Các rung nói về
   "model hỏi lại sau khi đã đọc câu trả lời"; trong một lượt chưa ai đọc gì —
   round phát ra nguyên khối. Call đầu chạy, các bản sao được nó trả lời.
   Ngoại lệ: halt do **history của Turn** thì vẫn halt.

### Halt là kết thúc *tool loop*, không phải kết thúc Turn

Plan nói "halt thành terminal". Đã làm khác và tốt hơn: `state.tools_halted` làm
`final = True` ở vòng sau, nên call kế tiếp là call trả lời với `tool_choice="none"`
trên bằng chứng đã có. Đúng thứ câu guidance yêu cầu, và không lấy đi câu trả lời
người đọc đã được nợ.

### Migration

`a4c71d9e5b28`: hai cột nullable trên `agent_tool_call`.
- `tool_call_id` — cột này lấp một khoảng trống có trước phase: `Citation.call_id` là
  id route, mà trace **không** lưu id đó, nên một citation không join được về row giữ
  kết quả nó dẫn. Nay join được.
- `spilled_bytes` — để ngưỡng tinh chỉnh được theo số đo thay vì theo phán đoán.

Backup trước khi chạy: DB Docker (`stockmassive`, 6.8 MB) **và** DB host trên
localhost:5432 mà `make test` thực sự dùng (81 KB) — hai DB khác nhau, đúng như
memory `local-postgres-shadows-docker` cảnh báo. Container `api` đang chạy không
thấy file migration mới trong bind mount, phải chạy qua `docker compose run --rm`.

### Còn nợ / mở

- **Không có bộ đếm halt trong ops query.** Tín hiệu plan nêu ("halt count = 0 mãi")
  hiện chỉ nằm ở structured log: một Turn bị halt vẫn `complete`, nên đếm nó cần một
  bản ghi per-Turn mà schema chưa có. Thêm vào là sửa truy vấn cố định của `ADR-0016`
  → để lại cho phase đọc báo cáo đó (Phase 8).
- `over_ceiling=True` (lượt vẫn quá trần sau khi đã spill hết) hiện chỉ ghi log; chưa
  có hành động. Đúng thiết kế: chưa đo được ca đó bao giờ.

### Review findings đã sửa (code-reviewer, 2026-08-21)

**H1 — thang fruitless halt oan cả một lượt (sửa).** `_fruitlessness` đếm **theo tool,
bỏ qua arguments**, và mọi Structured Refusal đều là `progressed=False`. Với 4 round,
`halt_repeats = 3`, nên ba lần refuse của một tool làm **call thứ tư — arguments chưa
ai thử — thành HALT**, và vì lúc đó một HALT huỷ cả round nên mọi call bên cạnh (kể cả
sang tool khác) bị bỏ luôn. Ca thật: web down → 3 `web_unavailable` → round sau model
gọi `web_search(q4)` **và** `get_price_series(FPT)` → cả hai không chạy, Turn trả lời
bằng không có gì trong khi store vẫn sống. Cũng đạt được bằng 3 `not_in_universe` trên
một câu so sánh 4 mã.

Sửa hai nửa: (a) route fruitless **chỉ warn, không bao giờ halt** — đúng như docstring
của chính nó nói ("never blocks"), vì "không tiến triển" đọc từ refusal và refusal đến
theo chùm bình thường; (b) HALT **từ chối chính call đó, không huỷ round** —
`RoundJudgement.refused` = BLOCK ∪ HALT, `tools_halted` làm round sau thành final. Có
test cho cả hai, kể cả test chứng minh không lượng refusal nào halt được một call chưa
từng gọi (thử ở 2/4/8 round).

**H2 — rung 3 lách bảng ngưỡng mỗi tool (sửa).** `spill_round` gọi
`spill_result(threshold=size - overshoot)` — ngưỡng **pinned**, nên nó bỏ qua toàn bộ
`per_tool`. Vì rung 3 sắp lớn-trước, đúng những tool khai báo full trần là những tool
nó với tới đầu tiên: một round béo sẽ cắt `get_financials.periods` xuống 3 quý và ghim
descriptor của widget vào 3 quý đó mãi mãi. Sửa: sàn = **giá trị đã khai báo**
(`declared_for`), không phải `threshold_for` — sau rung 2 mọi kết quả đã ≤ ngưỡng của
nó, lấy `threshold_for` làm sàn thì rung 3 không còn gì để nhường. Round vẫn không vừa
thì báo `over_ceiling` chứ không cắt xuyên qua khai báo. Hai test mới: tool khai báo
không bị cắt / tool không khai báo vẫn bị cắt.

**L1** — `GUARDRAIL_NOTE_CHARS` trừ `MESSAGE_OVERHEAD_TOKENS`: note dài tối đa từng
tốn 164 token trên chỗ đặt 160.

**L2** — comment cột `spilled_bytes` nói sai giá trị nó lưu (lưu kích thước **toàn
bộ**, không phải phần model không thấy).

**L3** — bảng "preview không bao giờ bỏ" trong ADR-0024 thiếu `unavailable`, `tool`,
`tool_call_id`.

**L4** — biến mất theo H1: call bị halt nay có kết quả trong transcript.

**L5** (rung 3 là O(n²·rung) serialise JSON) — không sửa: chỉ chạy trên round đã quá
trần, và ADR đã ghi là ghi chú.

### Trả lời ba câu hỏi mở của review

1. **`run_python` là effect-capable?** Giữ. Executor networkless (`ADR-0019`) nhưng
   *hình dạng* thứ chạy trong đó là code model viết — module này không đọc được nó, và
   "không biết" là đúng ca mà luật mặc-định-có-tác-dụng-phụ tồn tại để quyết.
2. **`replay_financials` không áp lại refusal Universe?** Cố ý, và nhất quán với
   `replay_field` đang có: một widget đã lưu là **bản ghi lịch sử**, `ADR-0012` nói
   Thread mở lại phải render đúng slice cũ. Áp Universe hôm nay lên câu trả lời tháng
   trước là để cohort hiện tại xoá một bảng đã đúng lúc nó được viết.
3. **Đoạn Voice/ngôn ngữ trong Contract 1.9.0?** **Không thuộc phase này.** Nó xuất
   hiện trong working tree từ một session khác đang làm việc về ngôn ngữ + suggestions
   (`suggestions.py` cùng lúc đổi `MAX_SUGGESTIONS` 5 → 2). Nó đang đi nhờ bản bump
   1.9.0 của phase này mà chưa có ADR/plan nào ghi. Chủ sản phẩm cần quyết: ghi nó vào
   một record riêng, hay tách khỏi commit này.

