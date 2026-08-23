---
title: "Evidence-Adjudicating Loop: số liệu đúng, kiểm được, và một vòng lặp biết tự phán xử"
status: implemented
created: 2026-08-22
updated: 2026-08-23
branch: feat/evidence-adjudicating-loop
base: develop@1974c24
blocks: [260823-1744-investment-intelligence-eval-replay-harness]
---

# Evidence-Adjudicating Loop

Vòng lặp hôm nay là **call → phân tích**. Nó phải là **call → check → phân tích → call tiếp**.
Bước `check` là bước duy nhất đang thiếu, và nó thiếu ở cả hai lane vì hai lý do khác nhau.

## Bằng chứng, không phải giả định

Hai lượt thật, đo trên `stockmassive-api-1`, 2026-08-22:

**Lượt `a81c94f1`, prompt `Phân tích HPG`, 20:42 ICT** — `complete` sau 25.653 ms, **3 lời gọi
`web_search`**, 15 nguồn (investing.com, cafef, vietstock, một PDF broker, 3 video YouTube).

Nội dung khá tốt: doanh thu Q2/2026 55.557 tỷ, LNST 6.424 tỷ, biên gộp ~19%, Dung Quất 2, sự
kiện ~1,34 tỷ cổ phiếu bổ sung lưu hành, giá đóng 21.700 phiên 21/08.

Ba khiếm khuyết đo được:

1. **Không con số nào đến từ store.** Store có đúng phiên 21/08 đó, đã chuẩn hoá, đã ghim
   `price_basis`. Không được đọc — `agent/toolsets.py` cho chat đúng hai toolset `web` và
   `memory`.
2. **Không phép so sánh nào.** Không phân vị thanh khoản, không sụt giá so mức kỳ vọng, không
   xếp hạng động lượng. Bài tổng hợp tin, không phải phép đo. Và không tái lập: hỏi lại mai ra
   bộ nguồn khác.
3. **Một con số không thể tồn tại đã lọt qua.** Câu trả lời nêu vùng 52 tuần
   *"20.100–27.542"*. `price_band.py:241 tick_size()` giữ bước giá HOSE 50đ ở dải
   10.000–50.000; **27.542 / 50 = 550,84**. Một giá không nằm trên bước giá của sàn không phải
   giá đã khớp. Vòng lặp không có bước nào kiểm được điều đó.

**Lượt trước đó, prompt về vị thế HAG 45%** — model khuyên cụ thể *"chốt/bán từng phần để hạ
tỷ trọng về khoảng 20–30%"*, dù `sections.py` INVARIANTS nói *"Bạn không phải là người tư vấn
đầu tư"*. Ranh giới tư vấn trong thực tế lỏng hơn contract, và thêm số liệu thật sẽ làm lời
khuyên **nghe** đáng tin hơn mà không **trở nên** đáng tin hơn.

## Lane Analysis thiếu bước check theo cách khác

`alpha/generation.py:403-404`: `tools=()`, `tool_choice="none"`. Backend gói sẵn 15 figure rồi
đưa một lượt. Ở đây bước check **đã có** — `health` + `reasonCode` do backend tính — nhưng
model **không hành động được** trên nó, vì không có vòng lặp để đi tìm cái thay thế.

Tài sản không sản phẩm dữ liệu VN nào có: **36 mã Signal Issue** (`stocks/signals/issues.py`),
cả 36 đã có câu giải thích trao cho model (`alpha/reasons.py`). Mỗi mã nói *phải đọc lại thế
nào*, không chỉ nói thiếu gì:

> `LIMIT_LOCKED_WINDOW` — *"More than a fifth of the window was locked at a limit, so a
> range-based estimate over it is measuring the band rather than the market. A degradation
> with a name, not a refusal: the sessions are real and the number is computable, it is the
> reading of it that has to change."*

36 mã đó là 36 nhánh quyết định. One-shot không đi được nhánh nào.

## Outcome

1. Lane Analysis có vòng lặp có biên: gặp figure `refused`, model đi tìm cái thay thế dùng
   được thay vì kể quanh cái lỗ.
2. Lane chat đọc được store qua đúng hai tool đã dựng, và **số của store thắng số của web**
   khi hai bên khác nhau.
3. Một mức giá từ nguồn ngoài không tới được người đọc mà chưa qua kiểm bước giá + biên độ +
   đối chiếu store.
4. Mọi lượt hỏi và mọi kết quả được ghi lại, đủ để dựng lại đường đi.

## Constraints

- Không dependency mới. Không nguồn dữ liệu mới. Không đụng bảng giá.
- Giữ `prompt/contract.py::_assert_no_formatting_hole`; `render()` chỉ nhận typed value.
  Evidence đi qua **tool**, không qua prompt.
- Giữ bất biến sở hữu figure (`alpha/production.py`): *"There is no key in the payload where a
  fragment-supplied number could be rendered as a figure."*
- Giữ thứ tự công bố của A2: Analysis ghi trước, run flip `ready` sau.
- Fail-open ở mọi cổng: được phép chậm, ồn, kèm cờ — không được phép làm trắng câu trả lời.
- Ngân sách: cohort nội bộ ≤30 mã → loop tốn ~$9,70/tháng khi prompt cache tắt, vừa lane $10.
  `llm_prompt_cache_control_enabled` là việc trước-prod. Lane chat không chạm trần
  (`TURN_INPUT_TOKENS = 100_000`; một figure 730 byte).

## Non-goals

Axis news · persist BCTC · đổi nguồn sang FiinQuant/SSI · forward-return ledger ·
subagent/MoA · memory xuyên phiên · planner/graph · MCP · cổng giấy phép nguồn.

Ba cái là **quyết định**, không phải bỏ quên:

**Reject-list guardrail: 0 dòng code, đã cưỡng chế sẵn.** `stocks/signals/fields.py:25-27`:
*"The tool layer serializes registered fields only, which is why an unregistered computation
needs no prohibition — it simply has no route to a model."* Cả 10 phương pháp mà
`docs/research/quant-methods-eod-vn.md` loại (cointegration, HMM regime, skew/kurtosis trên
daily return, RSI làm signal, √252 Sharpe, full Kelly, intraday, full-sample normalisation,
GARCH, short-term reversal) đều **không gọi được**.

**Forward-return ledger: hoãn vì chưa đo được.** `alpha_desk_enabled = False` — chưa có verdict
nào để chấm, và chấm cần ≥20 phiên (sàn T+2). Nó là bar thứ hai.

**Kiểm số chỉ phủ giá.** Không có bước giá hay biên độ nào cho doanh thu, lợi nhuận, biên gộp
— kiểm chúng cần BCTC đã lưu, mà store chưa lưu. Phase 7 đóng đúng một lớp.

## Acceptance criteria

1. ✅ Mọi Analysis do loop sinh có trace đầy đủ: hỏi gì, nhận gì, thứ tự nào.
2. ✅ Substitution rate query được từ trace — `analysis_reads.substitution_rate`, và
   `GET /api/v1/ops/analysis-loop`.
3. ✅ Một mức giá không nằm trên bước giá của sàn trả `off_tick`, kèm câu giải thích nêu bước
   giá. Đo trên fixture HOSE với đúng con số `27542` của lượt `a81c94f1`.
4. ⏳ **Chưa nghiệm thu.** Contract đã yêu cầu tách hai khối và lane chat đã có đường đọc store,
   nhưng chạy lại `Phân tích HPG` là một phép đo trên deployment có store đầy — không phải một
   test. Việc kế tiếp.
5. ✅ Không Analysis nào rỗng; không Turn nào bị cổng kiểm làm trắng. `check_price_claim` không
   xoá số và không chặn; mọi nhánh không kiểm được trả `unverified` kèm lý do.
6. ✅ `make test`: 2422 pass, 2 fail đều **không** thuộc thay đổi này — xem dưới. Cổng web không
   bị chạm (không file nào trong `apps/web`).

**Hai fail còn lại, cả hai có trước nhánh này:**

- `test_deployment_topology.py::test_the_topology_is_written_down_where_the_next_reader_will_look`
  — đòi `docs/streaming-topology.md`, đã bị xoá cùng `docs/` ở `b352417`. Ghi trong CLAUDE.md.
- `test_agent_loop.py::test_the_round_ceiling_is_the_constant_and_the_last_call_answers` —
  thừa hưởng từ base `develop@1974c24`: ở đó một câu trả lời rỗng kết thúc Turn là `incomplete`,
  và commit `6bfaccd` trên `develop` (plan `260822-1908`) mới sửa hành vi đó. Rebase lên
  `develop` là cách đóng nó, đúng như mục **Rủi ro đã biết** của plan này đã nói.

## Phase

| # | Phase | Vùng | Chặn bởi | Trạng thái |
|---|---|---|---|---|
| 1 | [Baseline one-shot trên dữ liệu thật](phase-01-baseline.md) | cờ config, script đo | — | ✅ đo xong, 2/5 phiên |
| 2 | [Trace: bảng `analysis_tool_call`](phase-02-trace-table.md) | `alpha/models.py`, 1 migration | — | ✅ |
| 3 | [Hai tool store-only](phase-03-store-tools.md) | `agent/tools/signals.py`, `registry`, `toolsets`, `envelope` | — | ✅ |
| 4 | [Vòng lặp thay `generate_fragment`](phase-04-analysis-loop.md) | `alpha/analysis_loop.py`, `production.py`, `core/llm/budget`+`admission` | 2, 3 | ✅ |
| 5 | [Substitution rate](phase-05-substitution-rate.md) | `alpha/analysis_reads.py`, `loop_ops_router.py` | 2, 4 | ✅ |
| 6 | [Chat đọc store](phase-06-chat-store-tools.md) | `toolsets.py`, `prompt/sections.py`, `tools/signals.py`, `loop.py` | 3, 7 | ✅ |
| 7 | [Cổng kiểm số](phase-07-figure-plausibility-gate.md) | `agent/tools/price_check.py`, `untrusted.py`, `registry`, `ops` | 3 | ✅ |

Phase 1–3 độc lập về file. **Phase 7 phải xong trước Phase 6**: Phase 6 thêm tool vào chat, và
`untrusted.py:45` đang gắn nhãn untrusted bằng frozenset viết tay — Phase 7 đổi nó sang thuộc
tính khai báo trước khi có tool mới đi qua.

`agent/loop.py` **không bị chạm ở phase nào** — xem quyết định trong Phase 4. Nhánh này vì thế
không xung đột với plan `260822-1908` đang viết lại chính file đó.

## Bằng chứng thật đã thay bằng chứng suy luận (2026-08-22)

Phase 1 đã đo trên store: [`plans/reports/baseline-oneshot-260822.md`](../reports/baseline-oneshot-260822.md).
Ba con số đổi cách đọc plan này:

1. **`refused` 41,6 %** (57/137 figure trên 8 Analysis) — cửa của Phase 1 không đóng plan.
2. **86 % refusal là cấu trúc**, không có đường đi quanh: BCTC chưa persist, trục news rỗng
   16/16. Phase 4 **không** được bán mình bằng "đi quanh chỗ trống".
3. **16/30 field trong catalog chưa bao giờ tới được một Analysis nào**, vì Field Profile `v1`
   chọn cố định 11 field cho mọi mã mọi phiên. Đây là giá trị đo được của vòng lặp, và Phase 4
   phải được viết theo hình dạng đó.

Ba mốc để Phase 5 so vào: **47,7 % figure dùng được không được dẫn** (`price_zone.ordinary_range_pct`
— *core evidence* — 0/8 lượt), **1 call · 5 043 input · 492 output token mỗi Analysis**, **~15,6 s**.

## Rủi ro đã biết

**Base `develop@1974c24` không có plan `260822-1908` (agent-core fail-open).** Ở base này
`guardrails.py:86-87` vẫn là ngưỡng Hermes cũ (`block_after=5`, `halt_after=8`) — thang
warn-only, không tới được bằng 4 round. Khi fail-open land lên `develop` thì rebase, và Phase 4
phải đọc lại ngưỡng thật trước khi đặt ngưỡng riêng cho lane Analysis.

**Đánh đổi trung tâm: reproducible → auditable.** `alpha/envelope.py`: *"an Analysis rebuilt
tomorrow from the same store has to say the same thing"*; `alpha/generation.py` định nghĩa
determinism là *"fixed inputs, fixed control flow"*. Vòng lặp phá `fixed control flow`. Cái mua
lại là trace (Phase 2). Quyết định kiến trúc đã được chấp nhận tường minh.

**Phase 6 đảo một quyết định đã ghi.** `1e7b936`: *"a general assistant that reads none of our
data"*. Lý do đảo: quyết định đó viết khi chưa có đường đọc store nào mang theo `health` và
`asOf`; Phase 3 tạo ra đường đó. Lý do phải nằm trong commit message, không chỉ trong plan.

**Contract không cưỡng chế được.** Model có thể nêu một mức giá mà không gọi `check_price_claim`.
Phase 7 **đo** tỷ lệ tuân thủ thay vì giả định, và chỉ dựng backstop quét văn bản nếu tỷ lệ
thấp. Dựng trước là dựng hàng rào cho một lớp lỗi chưa đo tần suất — đúng bài học meta của bộ
khảo sát Hermes.

**`spec 0003` không còn tồn tại.** Code tham chiếu 35 lần; `docs/specs/` đã xoá ở `b352417`.
Phase 4 đổi ngữ nghĩa `fieldProfileVersion` mà không có bản ghi hợp đồng nào để amend — ghi vào
docstring của `field_profile.py`.

## Câu hỏi chưa giải quyết

1. ~~**Ranh giới tư vấn.**~~ **Đã chốt ở Phase 6**, trong `INVARIANTS`: được nêu các mức và hệ
   quả, không ra chỉ thị hành động cho một vị thế cụ thể. Không "bán đi", không "chốt một
   phần", không tỷ trọng mục tiêu, không mức vào/ra. Lý do ghi trong prompt: số liệu thật làm
   lời khuyên *nghe* đáng tin hơn mà không *trở nên* đáng tin hơn.
2. ~~**Store vs web khi khác nhau.**~~ **Đã chốt ở Phase 6**: số của store thắng, và sự khác
   nhau **phải được nói ra**. Store là số đã chuẩn hoá, đã ghim ngày và tra lại được; một trang
   web là phương pháp của người khác. Luật nằm trong `HONESTY` và trong luật
   `check_price_claim` của `UNTRUSTED`.
3. `generation.py:175` nói *"a Vietnamese equities Analysis"* nhưng **không ghim ngôn ngữ
   output** và schema không có field ngôn ngữ. Còn mở — Phase 4 đã land mà không ghim.
