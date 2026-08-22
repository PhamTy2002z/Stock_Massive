---
phase: 4
title: "Vòng lặp thay generate_fragment"
status: done
---

# Phase 4 — Vòng lặp thay `generate_fragment`

## Kết quả (2026-08-23)

Đã land. `src/alpha/analysis_loop.py::generate_fragment_in_loop()` trả
`LoopOutcome(fragment, envelope, rounds_used, calls, fetched_field_ids)`; `production.py`
chọn giữa nó và `generate_fragment` qua `ANALYSIS_EVIDENCE_LOOP_ENABLED` (mặc định **on**).
35 test trong `tests/test_analysis_loop.py` + 7 test cấp producer trong `test_real_producer.py`
(chạy trên Postgres thật, store thật). `make test` pass với đúng hai fail có sẵn.

**Số thật, không phải số đề xuất:**

| | plan | đã land | vì sao |
|---|---|---|---|
| round | 6 | 6 | — |
| output/round | không nêu | **380** | `6×380 + 700 = 2.980 ≤ 3.000`, assert lúc import |
| `ANALYSIS_INPUT_TOKENS` | 24.000 | 24.000 | — |
| `ANALYSIS_OUTPUT_TOKENS` | 3.000 | 3.000 | — |
| `ANALYSIS_COST_CEILING_USD` | "tính lại" | **0,015** | `24.000×$0,5/Mtok + 3.000×$1,0/Mtok`, bảng giá cấu hình thật |
| `ANALYSIS_COST_MICRO_USD` | — | **15.000** | cùng số, đơn vị ledger; có test so hai chỗ |
| `ANALYSIS_INPUT_PER_CALL` | — | **24.000** | trần một-lời-gọi nâng bằng trần cả-Analysis: cái chặn qua nhiều lời gọi là trần **chi phí** trên owner, không phải trần token mỗi lời |
| `ANALYSIS_OUTPUT_PER_CALL` | — | **3.000** | như trên |

Chi phí thật/tháng ở cohort 30 mã × 21 phiên: **$9,45** (plan đoán $9,70), vừa lane $10.

**Ngưỡng guardrail — đọc lại như plan yêu cầu, không chép của chat.** Base vẫn là 5/8 của
Hermes, không tới được bằng 4 round. Lane này: `warn 1 / block 2` cho lời gọi trùng khít,
`warn 2 / halt 4` cho cùng một tool, `no_progress 2`. Mọi rung **tới được** trong 6 round, và
có test khẳng định điều đó.

**Prompt: `LOOP_SYSTEM_PROMPT = SYSTEM_PROMPT + LOOP_CONTRACT`, `LOOP_PROMPT_VERSION = "v2"`.**
Khác plan một chỗ: `generation.PROMPT_VERSION` **giữ** `v1` thay vì bị bump. Lý do là quyết định
rollback của chính plan này — one-shot vẫn ship, và nếu `SYSTEM_PROMPT` mang thêm đoạn nói về
tool thì một Analysis one-shot sẽ được dán nhãn contract mà nó không hề chạy. `analysis_payload()`
nhận `prompt_version` làm tham số; mỗi shape tự dán nhãn của mình.

**Chi phí của "không gọi tool nào": 2 lời gọi, không phải 1.** Plan viết đúng như vậy
(`không có tool_call → sang lời gọi cuối`) và test cấp producer khẳng định **payload** bằng
one-shot từng byte ở `evidence`/`judgment`/`citedFieldIds` — chỉ số lời gọi là 2. Đã cân nhắc
gộp `response_format` vào lời gọi round 0 để về lại 1 lời gọi và **bỏ**: trộn structured output
với tool calling là đúng lớp hành vi gateway mà `generation.py` đã đo được là không tin cậy.

**Trace ghi từ `outcome.results` theo thứ tự model phát lệnh**, không qua `trace` hook của
executor: hook chạy đồng thời cho segment song song nên `seq` sẽ không còn là thứ tự của model.
`session.commit()` tường minh trong `_record_round` — `sync_session_factory` không tự commit,
và không có nó thì trace im lặng biến mất (đã bắt được bằng test cấp producer).

**`TurnBudget` không dùng.** Plan liệt kê nó ở bảng tái dùng, nhưng chính Phase 3 nói "không port
tầng spillover/truncate/dedup" — và rung ba của `TurnBudget` (`PER_TURN_MIN_CHARS = 16_000`) sẽ
**cắt** đúng những figure store mà Analysis vừa trả tiền để đọc (30 figure ≈ 22KB). Chỉ dùng
`trim_text` + `registry.get_max_result_size` cho từng kết quả, tức rung hai, đúng khuôn
"chặn một bug" của Phase 3.

## Seam: đúng một hàm

`alpha/production.py:203` gọi `_run_generation(envelope, ...)` → `generation.py:432
generate_fragment(client, envelope, *, model, run_id) -> AnalysisFragment`.

Đó là toàn bộ chỗ phải đổi. Lifecycle (`analysis_run.py`), dispatcher, thứ tự công bố,
admission, `AnalysisDraft` — không chạm gì. `produce()` vẫn trả `AnalysisDraft`.

Một thay đổi hợp đồng tại seam: loop **mở rộng** envelope, nên nó phải trả về cả envelope đã
mở rộng, vì `analysis_payload(envelope, fragment, ...)` render từ envelope. Chữ ký thành
`-> tuple[AnalysisFragment, EvidenceEnvelope]`.

## Quyết định: KHÔNG tham số hoá `AgentLoop`

Tôi đã đề xuất "tham số hoá `agent/loop.py` đúng 4 chỗ". Đọc kỹ thì sai, và đây là lý do.

`AgentLoop._run` nhận `TurnRequest` (thread_id, request_message_id, user_id, runtime), publish
qua `TurnPublisher`, `_save` vào transcript, dựng context bằng `render(request.runtime)` là
contract của chat. Một Analysis Run không có thread, không có message, không có ai đang xem
stream — `generation.py:404` chọn `stream=False` có lý do ghi rõ: *"Nothing in the nightly lane
consumes tokens as they arrive."*

Dùng `AgentLoop` sẽ phải bịa một thread và một message. Đó đúng thứ repo này từ chối.

Vậy: **một loop riêng ở `alpha/analysis_loop.py`, tái dùng các bộ phận, không tái dùng
orchestrator.** Tái dùng nguyên trạng:

| Bộ phận | Ở đâu | Vì sao đáng tái dùng |
|---|---|---|
| `ToolExecutor` | `agent/executor.py` | fail-open: *"a tool failure is a result"*; plan_segments; trace hook |
| `TurnGuardrails` | `agent/guardrails.py` | thang `allow → warn → block → halt`, `thresholds` đã là tham số |
| `TurnBudget` | `agent/budget.py` | trần kết quả theo context window, cursor |
| `ReservedLLMClient` + `spend_for` | `core/llm/`, `generation.py:415` | admission bắt buộc về cấu trúc |
| `FRAGMENT_FORMAT` + 6 luật semantic + `_citations` | `generation.py` | hợp đồng dẫn nguồn — **không viết lại** |

Lợi ích phụ và nó lớn: `agent/loop.py` **không bị chạm**, nên nhánh này không xung đột với
plan `260822-1908` đang viết lại chính file đó.

## Vòng lặp

Seed là envelope hiện tại (`build_envelope`) — 15 figure, gồm `price_zone` là core evidence
bắt buộc. Model bắt đầu với evidence lõi trong tay và chỉ tiêu round cho **thay thế và chiều
sâu**. Nếu nó không gọi tool nào, kết quả bằng đúng hành vi hôm nay.

```
round 0..N-1:  call(model, messages, tools=signals, tool_choice="auto")
               ├─ không có tool_call  → sang lời gọi cuối
               └─ có tool_call        → executor.run() → append tool results
                                        → ghi analysis_tool_call
round N:       call(model, messages, tools=(), tool_choice="none",
                    response_format=FRAGMENT_FORMAT)   → fragment
               → validate bằng 6 luật của generation.py
               → invalid: đúng MỘT regeneration, nếu admission còn tiền
```

Lời gọi cuối là chỗ `generation.py` hôm nay đang làm, không đổi gì: temperature 0, strict
structured output, `tools=()`.

**Fail-open**: hết round mà chưa có fragment hợp lệ thì thất bại theo tên đã có
(`invalid_model_output` trong `producer.py::FAILURE_CODES`), **không** thêm mã mới. Một
Analysis không bao giờ được publish rỗng.

## Ngân sách — số học phải đổi tường minh

`core/llm/budget.py:36-38` hiện tại:

```
ANALYSIS_INPUT_TOKENS = 6_000
ANALYSIS_OUTPUT_TOKENS = 1_500
ANALYSIS_COST_CEILING_USD = 0.0045
```

Docstring gọi chúng là *"the contract, not the route"* — đổi là đổi lời hứa của sản phẩm, nên
phải có số.

Đo (6 round, model xin ~12 field, figure 730 byte):

| | token | so với one-shot |
|---|---|---|
| one-shot hôm nay | 7.500 | 1,00× |
| loop, prompt cache **tắt** | 25.705 (23.005 in / 2.700 out) | 3,43× |
| loop, prompt cache **bật** | 6.252 in hiệu dụng | 0,83× |

80% input của loop là prefix lặp lại (system prompt + tool schema + kết quả đã tích luỹ, gửi
lại mỗi round). Nên **vòng lặp làm prompt cache đáng tiền hơn one-shot**, không kém đi.

Đặt trần theo trường hợp cache tắt: `ANALYSIS_INPUT_TOKENS = 24_000`,
`ANALYSIS_OUTPUT_TOKENS = 3_000`, và `ANALYSIS_COST_CEILING_USD` tính lại từ bảng giá thật.
Lane vẫn $10 nên Budget Validation vẫn cộng đúng envelope $45; ở ≤30 mã nội bộ, chi phí
~$9,70/tháng.

`llm_prompt_cache_control_enabled` là việc **trước-prod**: đặt cờ → chạy Capability Probe →
chỉ giữ nếu check `prompt_cache_control` xanh. Ở 100 mã nó là khác biệt giữa $11,34 và
$32,34/tháng.

## Trần round và thang guardrail

Trần chat là **một phép tính**, không phải một con số — `loop.py:147-151`: `MAX_TOOL_ROUNDS +
1` lời gọi ở `DEFAULT_MAX_OUTPUT_TOKENS` mỗi lời, đối chiếu `TURN_OUTPUT_TOTAL`. Lane Analysis
có mẫu số khác nên phải có phép tính riêng, viết vào docstring.

Đề xuất 6 round + 1 lời gọi cuối, khớp `ANALYSIS_OUTPUT_TOKENS = 3_000`.

`GuardrailThresholds` riêng cho lane, và ngưỡng phải **tới được** bằng 6 round — đây đúng lớp
lỗi Phase 2 của plan `260822-1908` đang sửa cho chat. **Tại base `develop@1974c24`,
`guardrails.py:86-87` vẫn là 5/8 của Hermes.** Đọc lại ngưỡng thật sau khi rebase trước khi
đặt số cho lane này; đừng chép số của chat.

Không có `EXTERNAL_TOOLS` ở lane này: hai tool đều đọc Postgres nội bộ, không tốn quota
vnstock, không ra ngoài deployment. Trần external của chat (`loop.py:275`, 6 call) **không**
áp — đó là trần cho tool tốn tiền, và ở đây không có tool nào như vậy.

## Contract prompt cho lane Analysis

`SYSTEM_PROMPT` hiện tại (`generation.py:174-208`) viết cho one-shot: *"The user message is the
complete evidence envelope"*. Với loop thì envelope không còn complete — nó là seed.

Thêm vào contract, không thay:

- Envelope là điểm bắt đầu, không phải toàn bộ; `list_fields` cho biết còn gì.
- Figure `refused` mang `reasonCode` **và** `reason`; việc phải làm là tìm cái thay thế dùng
  được, không phải kể quanh nó. `minSessions` trong catalog là chỗ nhìn.
- Vẫn chỉ được cite figure `ok`/`degraded`; figure `refused` mãi mãi không chống được verdict.
- Không xin lại một field đã trả `refused` cùng lý do — đó là round bị mất, và guardrail
  `no_progress` sẽ đếm nó.

Giữ `PROMPT_VERSION` là hợp đồng: bump `v1` → `v2`.

## `fieldProfileVersion` đổi nghĩa

Hôm nay nó nghĩa "đúng các field này". Với loop, hai Analysis cùng `fieldProfileVersion` có
thể mang bộ figure khác nhau — nó thành "catalog phiên bản này khả dụng, seed là profile này".

`alpha/field_profile.py:20-27` nói lý do bản cũ tồn tại: *"a profile that silently dropped them
would make two Analyses carrying the same `fieldProfileVersion` mean two different things, and
nothing downstream could tell."* Với loop, chính điều đó xảy ra **có chủ đích** — và cái nói
được sự khác biệt là trace của Phase 2. Ghi vào docstring; `spec 0003` không còn để amend.

`MAX_FIELDS_PER_AXIS = 6` **giữ nguyên**: nó bound seed, và model với tới phần còn lại qua
tool.

## Validation

- Test: model không gọi tool nào → kết quả bằng one-shot hôm nay (hồi quy).
- Test: seed có một figure `refused`, model xin field khác, fragment cite field mới → envelope
  trả về chứa cả hai, payload render cả hai.
- Test: model xin một field không đăng ký → nhận lỗi đọc được, loop tiếp tục.
- Test: hết round chưa có fragment hợp lệ → `invalid_model_output`, không publish.
- Test: mọi lời gọi model đều qua reservation cùng `owner=(analysis_run, run_id)`; ceiling giữ
  qua cả 3 attempt của cặp `(symbol, trading_day)`.
- Test: `analysis_tool_call` có đúng số row bằng số call, `round_index`/`seq` liên tục.
- `make test` pass.

## Risk / rollback

Rollback là một cờ chọn producer: `analysis_producer` nhận producer làm tham số
(`producer.py` — *"a producer arrives as an argument"*), nên one-shot và loop cùng tồn tại và
đổi qua config, không cần revert code.

Rủi ro lớn nhất **không** phải kỹ thuật: nếu Phase 1 cho thấy `refused` hiếm, loop tiêu 3,43×
token để làm một việc gần như không xảy ra. Phase 1 là cổng và nó được phép đóng Phase 4.
