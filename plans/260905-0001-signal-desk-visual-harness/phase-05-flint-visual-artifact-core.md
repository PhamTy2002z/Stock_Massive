---
phase: 5
title: "Flint Visual Artifact Core"
status: todo
priority: P1
effort: "10h"
dependencies: [2, 4]
---

# Phase 5: Flint Visual Artifact Core

## Context Links

- Phase 2 Findings + fixture đã export trong `apps/web/src/components/signal-desk/flint-contract.test.ts`
- `apps/api/src/agent/turns.py::assistant_message` — pattern "key chỉ ghi khi có" của `question`
- `apps/api/src/agent/evidence/pipeline.py::evidence_from_calls` — pattern đọc `state.calls`
- `apps/api/src/agent/parts.py` — vì sao part là allowlist, content-light, không tới model
- `apps/web/src/lib/alpha-desk/types.ts` — union `"part.progress" | "part.question"`
- `apps/web/src/lib/alpha-desk/read-content.ts::readQuestion`

## Overview

Một part `visual` durable cùng assistant message, **host assemble hoàn toàn
deterministic từ các `get_market_data` call đã thành công**. Browser validate/
compile qua package Flint đã pin và render bằng ECharts.

Không artifact table, không artifact endpoint, không Board DSL, không widget,
không server-side chart compiler.

## Model không đề xuất chart

Bản trước cho model gửi `VisualDraft` (chart kind + field mapping + evidence
refs) rồi host refuse literal data, allowlist chart type, và cho một strict
repair nếu draft sai. Với **một** dataset (`ohlcv`) và **một** hình dạng chart
mà Phase 2 chứng minh compile được, tầng đó không quyết định gì:

| Input của Turn | Assembly (deterministic) |
|---|---|
| 1 market call thành công | Candlestick + volume — đúng fixture Phase 2 |
| ≥ 2 market call cùng interval và unit | Multi-series line, thứ tự theo thứ tự call |
| 0 market call thành công | Không có part `visual` |

Cắt được: `VisualDraft` schema, refusal "model gửi literal data" (không có
payload model nên không có gì để refuse), allowlist chart type, strict-format
repair, và một lượt LLM mỗi Turn.

**Thêm lại khi:** có dataset hoặc hình dạng chart thứ ba mà host không suy ra
được từ shape của call. Lúc đó model chọn *kind*, host vẫn giữ toàn quyền về
data — không bao giờ nhận số từ model.

## Visual Part Contract

```json
{
  "version": 1,
  "renderer": "flint-echarts",
  "flintVersion": "<pinned>",
  "asOf": "<timezone-aware ISO-8601>",
  "assembly": "<official ChartAssemblyInput>",
  "evidenceIds": ["..."],
  "sourceCallIds": ["..."]
}
```

**Không `status`, không `reason`.** Theo đúng pattern `question` trong
`assistant_message`: key chỉ được ghi khi có thật, absent chứ không null — nhờ
đó message viết trước khi visual tồn tại vẫn byte-identical, và client hỏi *có
chart không* bằng chính key. Turn không đủ bằng chứng cho chart thì không có
part; lý do đã nằm trong ledger gaps ở cột chat, và một enum `unavailable` chỉ
để nhân đôi lời giải thích đó.

**Không `contentSha256`.** Payload persisted là immutable JSON; replay
determinism chứng minh bằng so sánh chính payload đó, hash không thêm fact nào.

`visual` là sibling part, không vào transcript gửi lại model.

## Data Ownership

```text
host:    chọn shape từ market call + rows đã normalize + caps + provenance
Flint:   validate + compile assembly
ECharts: render compiled output
```

Host được dựng input cho Flint; không được sửa thứ Flint đã compile. Mutation
hợp pháp duy nhất sau normalization là chọn field và sắp thứ tự row theo đúng
contract input mà Flint tài liệu hoá.

## Requirements

- Part chỉ tồn tại cho Turn `signal_desk` đạt `PipelineStage.COMPLETE` với
  ledger đã qua `validate_claim_ledger`. Market-only material claim là
  `SINGLE_SOURCE` theo thiết kế (Phase 3), nên gate nhận `SINGLE_SOURCE` trở
  lên — không nhận `UNSUPPORTED` hay `TEMPORALLY_INVALID`.
- Mỗi value trong assembly truy ra được `agent_tool_call` id + evidence ID +
  unit + `as_of`. Không giá trị nào không có nguồn.
- Reopen Thread không gọi lại model/tool: part đọc từ message content.
- Frontend gọi Flint validate/compile mỗi lần render; ECharts option chỉ tồn
  tại trong memory.
- Pin `flint-chart` + ECharts đúng version Phase 2; source và template của
  package byte-unmodified.
- Theme/behavior mặc định của Flint giữ nguyên. CSS host chỉ set kích thước và
  padding của khung panel, không traverse hay rewrite compiled option.
- Caps series/rows/points/label chars/serialized bytes khai một lần, test ở
  biên và quá biên. Đây là trust boundary tới browser — không cắt.

## File Inventory

| Action | File | Purpose |
|---|---|---|
| Create | `apps/api/src/agent/visual.py` | Chọn shape, bind evidence/call id, dựng assembly, caps. |
| Modify | `apps/api/src/agent/loop.py` | Sau khi verification pass validate ledger, dựng visual và mang trên draft/outcome. |
| Modify | `apps/api/src/agent/turns.py` | `assistant_message(..., visual=None)`: ghi key chỉ khi có. |
| Modify | `apps/api/src/agent/persistence.py` | Chỉ khi signature terminal transaction hiện tại đòi. |
| Create | `apps/api/tests/test_agent_visual.py` | Shape selection, binding, caps, replay, absent-key. |
| Modify | `apps/api/tests/test_agent_turn_lifecycle.py` | Checkpoint/terminal/restart persistence. |
| Modify | `apps/web/package.json`, `apps/web/pnpm-lock.yaml` | Pin Flint + ECharts. |
| Create | `apps/web/src/lib/flint/compile-visual.ts` | Một hàm validate/compile; Phase 6 và Phase 7 đều dùng. |
| Create | `apps/web/src/lib/flint/compile-visual.test.ts` | Compile fixture Phase 2, reject payload malformed. |
| Modify | `apps/web/src/lib/alpha-desk/types.ts` | Thêm `"part.visual"` vào union + type `VisualPart`. |
| Modify | `apps/web/src/lib/alpha-desk/read-content.ts` | `readVisual` theo pattern `readQuestion`: trả `null` khi không đọc được. |

Không sửa `evidence/pipeline.py`: `visual.py` đọc `state.calls` trực tiếp, đúng
pattern `evidence_from_calls`.

Không sửa `transcript.ts`: nó chỉ đọc key nó biết (`content.question`), nên key
lạ bị bỏ qua sẵn. Một test chứng minh điều đó, không phải một thay đổi code.

Không migration: `agent_message.content` và `agent_turn.draft_content` đã là
đường persistence JSON versioned cho typed part. Schema `agent_artifact` đã
retired, không map lại.

## Implementation Steps

1. Pin package; compile fixture Phase 2 trong một web unit test trước tiên.
2. Test backend đỏ trước: mọi value trong assembly phải map về một field của
   market call có tên; không có call thì không có key `visual`.
3. Viết `visual.py`: chọn shape theo số call, hydrate rows từ result đã
   normalize, gắn evidence/call id + unit + `as_of`, áp caps.
4. Mang visual qua checkpoint/outcome/message ở mọi đường terminal, complete,
   incomplete, cancelled, restart — không orphan tool call. Giữ nó ngoài
   transcript dựng cho model.
5. `compile-visual.ts`: một hàm, gọi public API của Flint, trả compile output
   hoặc một error ổn định; không mutate input/output.
6. Test: version sai, thiếu evidence, quá nhiều point, payload persisted hỏng —
   tất cả degrade thành "không có chart", không crash transcript.
7. Chạy fixture qua backend assembly → persisted JSON → web parser → Flint
   compile, so field semantic với output Phase 2.
8. `rg` chứng minh: không nơi nào persist/post-process ECharts option, không
   file nào dưới Flint source bị đổi.

## Test Matrix

| Scenario | Expected |
|---|---|
| Một market call ohlcv | Candlestick + volume; Flint compile thành công. |
| Hai call cùng interval/unit | Multi-series line, thứ tự deterministic. |
| Hai call lệch interval hoặc unit | Không có part; ledger gaps giải thích ở chat. |
| Không có market call | Không có key `visual` ở mọi lifecycle stage. |
| Ledger `UNSUPPORTED`/`TEMPORALLY_INVALID` | Không có part. |
| Thiếu call id / evidence id | Không có part; không có value nào không nguồn. |
| Vượt cap row/byte | Refusal deterministic trước khi persist và trước browser. |
| Refresh/restart | Cùng assembly, không gọi tool/model. |
| Chat mode | Không có key `visual`. |
| Visual lịch sử hỏng | Parser trả `null`, transcript vẫn render. |

## Verification Commands

```bash
cd apps/api && pytest -q tests/test_agent_visual.py tests/test_agent_turn_lifecycle.py tests/test_agent_persistence_paths.py tests/test_agent_evidence_renderer.py
pnpm --dir apps/web test -- src/lib/flint/compile-visual.test.ts src/lib/alpha-desk
pnpm --dir apps/web type-check
python -m compileall -q apps/api/src apps/api/tests
rg -n 'echarts.*option|compiledOption|setOption' apps/api apps/web/src
git diff --check
```

`setOption` chỉ được xuất hiện ở đúng một lời gọi render chính thức; mọi store,
serializer hay mutation của object đó là fail phase.

## Success Criteria

- [ ] Fixture đi từ backend tới browser, compile bằng Flint chính thức, giữ
      đúng giá trị có evidence.
- [ ] Zero số trong assembly do model viết — vì model không gửi số nào.
- [ ] Zero ECharts option được persist hoặc post-process.
- [ ] Refresh/restart deterministic, không thêm network/model work.
- [ ] Chat và evidence behavior sống nguyên khi visual vắng mặt.

## Risks And Rollback

**Flint input đổi:** compile test đã pin fail trước khi deploy; upgrade là một
quyết định migrate fixture, không phải viết compiler fallback.

**Message payload quá lớn:** hạ cap row, hoặc aggregate server-side từ evidence
tường minh. Không thêm artifact service khi chưa đo được nhu cầu. Rollback: gỡ
field visual optional + web dependency, mọi text/evidence còn nguyên.

**Host chọn shape sai ý người đọc:** đây là hệ quả của việc cắt model draft.
Phase 7 corpus đo; nếu sai nhiều thì thêm model chọn *kind* (không bao giờ
chọn *data*) theo mục "Thêm lại khi" ở trên.
