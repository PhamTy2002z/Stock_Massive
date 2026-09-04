---
phase: 4
title: "Signal Desk Mode And Market Evidence In The Deep Pipeline"
status: todo
priority: P1
effort: "6h"
dependencies: [3]
---

# Phase 4: Signal Desk Mode And Market Evidence In The Deep Pipeline

## Context Links

- `apps/api/src/agent/evidence/ledger.py::validate_claim_ledger`
- `apps/api/src/agent/evidence/pipeline.py` — `PipelineStage`, `ResearchDraft`, `PLANNER_NOTE`, `RESEARCH_NOTE`, `failed_ledger`
- `apps/api/src/agent/loop.py:1370` (`deep_pipeline`), `:1211` (`self._toolsets`), `:416` (`CHAT_MODE`)
- `apps/api/src/agent/turns.py:483` — site duy nhất chọn lane
- `apps/api/src/agent/persistence.py:1514` — `create_turn(mode=...)` **đã tồn tại**
- `apps/api/src/agent/guardrails.py`, `apps/api/src/agent/lanes.py::DEEP`
- `apps/api/src/agent/schemas.py::CreateTurnRequest`

## Overview

Bản trước của phase này định viết `readiness.py`: typed `EvidenceNeed`,
`coverage_digest`, state machine `PLAN → CHECK → READY_*`, bộ đếm no-progress,
mười stop reason mới. Đọc code xong thì **gần như toàn bộ đã tồn tại dưới tên
khác**, và một layer thứ hai enforce cùng invariant là hai chỗ để một invariant
lệch nhau.

| Thứ plan gọi | Đã có trong code |
|---|---|
| Host readiness gate | `validate_claim_ledger` — recompute mọi verdict từ evidence, model label không có authority: numbers-on-page, temporal admissibility, primary/multi-source rule |
| Readiness state machine | `PipelineStage` PLANNING → RESEARCH → COUNTEREVIDENCE → VERIFICATION → COMPLETE, deterministic, model không tự khai `ready` |
| Typed evidence needs | `ResearchDraft.gaps` (schema `DRAFT_FORMAT` bắt buộc) + `ClaimLedger.gaps` gộp research + counter + verifier |
| `ready_refusal` / `insufficient_evidence` | `failed_ledger` + `_fail_deep_pipeline` — refusal có reason, settle terminal, render ledger |
| Duplicate-call reuse, failure ladder | `TurnGuardrails`: `call_signature` canonical args, `result_signature`, warn → block → halt |
| Bounds 10/20/1.800 | `lanes.DEEP`, với arithmetic invariant tự refuse ở `LaneProfile.__post_init__` |
| Mode persistence | `create_turn(mode=CHAT_MODE)` đã ghi mode vào idempotency payload chỉ khi khác default |

Còn lại đúng ba việc: **đưa `mode` từ request tới lane/toolset**, **cho deep
pipeline dùng được market data**, và **test rằng bound vẫn giữ khi surface có
tool thứ ba**.

## Đã cắt, và thêm lại khi nào

| Cắt | Lý do | Thêm khi |
|---|---|---|
| `evidence/readiness.py` | `validate_claim_ledger` đã là host gate; module thứ hai = hai định nghĩa "ready". | Không bao giờ dưới hình dạng này. |
| `coverage_digest` + course-correct counter | Chỉ bắt được case "query khác, kiến thức như cũ" — vốn đã bounded bởi 10 round / 20 call / 1.800s, terminate có reason. CLAUDE.md §4: bound để dừng có lý do, không để tiết kiệm tiền. | Corpus Phase 7 đo được số round lãng phí đáng kể. |
| `EvidenceNeed` typed (ID, kind, materiality, expected symbol/range) | `DRAFT_FORMAT` đã buộc claims có `material`/`unit`/`currency` và `gaps`; thêm một schema song song = hai nơi khai cùng thiếu sót. | Verifier cần route gap theo dataset để tự chọn tool. |
| Tri-state `continue`/`ready_answer`/`ready_refusal` | Stage machine đã quyết định; model chưa từng được phép khai `ready`. | Nếu pipeline chuyển sang vòng lặp mở — không thuộc plan này. |
| 10 stop reason mới | Terminal reason hiện có (`TURN_DEADLINE`, `CANCELLED_BY_USER`, `verification_*`, `draft_recovery_failed`, guardrail `halt`) đã phủ mọi exit. | Một exit thật không map được vào reason nào đang có. |
| `parts.py`, `turns.py` checkpoint readiness payload | Không còn readiness state để checkpoint. | Cùng lúc với mục trên. |

## Requirements

- `mode` là enum strict `chat | signal_desk`; thiếu `mode` = `chat`,
  byte-compatible với request cũ; mode lạ = 422.
- `CreateTurnRequest` là `extra="forbid"`: field này phải đổi **cùng commit**
  với web client, nếu không mọi Turn 422.
- `signal_desk` → lane `DEEP` (bỏ qua heuristic keyword) + toolset
  `(*CHAT_TOOLSETS, "market_data")`. `chat` giữ nguyên router và catalog hiện tại.
- Deep pipeline planning pass được phép một `get_market_data` cho series
  giá/khối lượng; snippet search không bao giờ thoả một claim cần row market.
- Bound `DEEP` không đổi: 10 round, 20 external call, 1.800s, ceiling LLM/cost
  hiện có. Không có tool nào được thêm capacity riêng.
- Untrusted tool text không đổi được policy, permission hay tool surface.
- Recovery giữ đúng một strict-format repair mỗi draft (`draft_recovery_messages`).

## File Inventory

| Action | File | Purpose |
|---|---|---|
| Modify | `apps/api/src/agent/schemas.py` | `mode: Literal["chat","signal_desk"] = "chat"` trên `CreateTurnRequest`. |
| Modify | `apps/api/src/agent/turns.py` | Truyền `mode` vào `create_turn` (param đã có) và chọn lane ở site duy nhất `:483`. |
| Modify | `apps/api/src/agent/service.py` | Truyền toolset selection vào `AgentLoop(toolsets=...)` (ctor param đã có). |
| Modify | `apps/api/src/agent/evidence/pipeline.py` | Biến thể `PLANNER_NOTE`/`RESEARCH_NOTE` cho signal_desk: cho phép một market call, giữ nguyên counter pass. |
| Modify | `apps/api/src/agent/router.py` | Nhận `mode` từ body, không suy từ text. |
| Modify | `apps/web/src/lib/alpha-desk/*` (client gửi Turn) | Gửi `mode` — cùng commit với schema. |
| Modify | `apps/api/tests/test_agent_transport.py` | Default/omitted/invalid mode; replay contract. |
| Modify | `apps/api/tests/test_agent_loop.py` | signal_desk → DEEP + surface có `get_market_data`; chat thì không. |
| Modify | `apps/api/tests/test_agent_evidence_pipeline.py` | Planning note biến thể; market gap không bị snippet thoả. |

Không file mới. Không bảng mới. Không state machine thứ hai.

## Implementation Steps

1. Freeze transcript chat light/deep hiện tại làm baseline; thêm schema test:
   omitted mode byte-compatible, mode lạ = 422.
2. Thêm `mode` vào `CreateTurnRequest` + router + client trong **một commit**.
3. `turns.py`: `mode == "signal_desk"` → `(DEEP, "mode:signal_desk")`; log
   reason như hiện tại. Không sửa `route_reason` — signal_desk không phải
   heuristic.
4. `service.py`: toolset selection theo mode; chat vẫn `CHAT_TOOLSETS`.
5. Biến thể planning/research note cho signal_desk: nêu rõ số giá/khối lượng
   phải đến từ `get_market_data`, snippet chỉ để discovery. Không đổi
   `DRAFT_FORMAT`.
6. Test: mọi ceiling vẫn giữ với ba tool trong surface; cancel/deadline/
   permission-denied/provider-unavailable vẫn settle terminal có reason.
7. Chạy lại suite evidence/untrusted/cancellation của Phase 6 để chứng minh
   truth contract và three-pass không đổi.

## Test Matrix

| Scenario | Expected |
|---|---|
| Request không có `mode` | Hành vi hiện tại, byte-compatible, không mode trong idempotency payload. |
| `mode` lạ | 422, không tạo Turn. |
| `mode=signal_desk` | Lane `DEEP`, reason `mode:signal_desk`, surface có `get_market_data`. |
| `mode=chat` | Catalog và lane hiện tại, không có tool market. |
| Gap giá/khối lượng | Chỉ `get_market_data` thoả; snippet để `gaps`. |
| Market claim thiếu evidence | `validate_claim_ledger` hạ verdict; không có đường nào lên `VERIFIED`. |
| Exact call lặp thất bại | Ladder warn → block → halt hiện có; không external call sau halt. |
| Round / call / deadline ceiling | Không vượt 10 / 20 / 1.800; reason persisted. |
| Cancel giữa batch | Call đã settle giữ thứ tự, call chưa dispatch bị cancel, Turn terminal. |
| Verifier fail | `failed_ledger` render, Turn `COMPLETE` với gap là reason. |

## Verification Commands

```bash
cd apps/api && pytest -q tests/test_agent_transport.py tests/test_agent_loop.py tests/test_agent_evidence_pipeline.py tests/test_agent_guardrails.py tests/test_agent_turn_lifecycle.py
python -m compileall -q apps/api/src apps/api/tests
pnpm --dir apps/web type-check
git diff --check
```

## Success Criteria

- [ ] Request cũ (không `mode`) chạy y như trước, chứng minh bằng transcript
      baseline.
- [ ] `signal_desk` là đường duy nhất tới toolset market; chat không chạm được.
- [ ] Mọi Turn test terminate với reason ổn định; không path nào lên round thứ
      11 hay external call thứ 21.
- [ ] Không file `readiness.py`, không digest, không state machine thứ hai
      trong diff.
- [ ] Suite evidence/untrusted/cancellation của Phase 6 xanh.

## Risks And Rollback

**`extra="forbid"` phá mọi Turn:** schema và client lệch commit. Chặn bằng test
transport chạy trước khi client đổi; rollback là revert cả hai cùng lúc.

**Planning note quá cứng:** model tiêu round vào market call không cần thiết.
Đo bằng corpus Phase 7, sửa note — không sửa bound.

**Ledger quá nghiêm với số market:** xem Phase 3 Ledger Findings; hệ quả đúng
là `SINGLE_SOURCE`, không phải nới `_PRIMARY_CLASSES`. Nếu answer refuse quá
nhiều thì đó là deviation về truth contract, dừng và hỏi owner.

Rollback toàn phase: gỡ `mode` khỏi schema/client và toolset selection; deep
pipeline trở lại web-only, không mất capability nào đang có.
