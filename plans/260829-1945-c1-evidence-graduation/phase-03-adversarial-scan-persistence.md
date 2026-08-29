---
phase: 3
title: "Adversarial scan persistence"
status: done
priority: P1
effort: "5h"
dependencies: [1]
---

# Phase 3: Adversarial scan persistence

## Context Links

- `apps/api/src/agent/executor.py` — scan once after external result
- `apps/api/src/agent/messages.py::TurnToolCall.as_wire`
- `apps/api/src/agent/turns.py::assistant_message`
- `apps/api/golden/run.py::read_case`
- `apps/api/tests/test_threat_patterns.py`

## Overview

Chứng minh scanner không chỉ đúng ở unit level: hostile external text được quét
đúng một lần, verdict không vào model text, được persist và đọc lại/counted.

## Requirements

- Functional: deterministic hostile payload đi qua real registry + executor +
  loop/wire/persistence path; không inject sẵn verdict vào fixture.
- Functional: reopen thread và `golden.run.read_case` đều thấy cùng `scan`.
- Functional: benign payload `low`; scanner exception/timeout `unknown`; cả ba
  không chặn answer.
- Security: matched spans/attacker text không đi trong `scan`; model transcript
  chỉ nhận wrapped result, không nhận risk metadata.
- Non-functional: không trộn synthetic attack vào `web_first.json`; security
  lane riêng để web-quality corpus vẫn đo web thật.

## Architecture

```text
external handler → ToolExecutor.scan_for_threats (once)
                 → ToolResult.scan
                 → TurnToolCall.as_wire
                 → agent_message.content JSONB
                 → history reopen / golden.read_case

model transcript ← shown_result only; never scan metadata
```

## Related Code Files

- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_tool_executor.py` — real scan call count/verdict.
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_untrusted_results.py` — transcript isolation.
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_persistence_paths.py` — persist/reopen integration.
- Create: `/Users/typham/Dev/Stock_Massive/apps/api/tests/golden/test_run.py` — `read_case` scan projection from persisted message and trace.
- Conditional modify only after a red test proves a gap: `executor.py`,
  `messages.py`, `turns.py`, `events.py`, `golden/run.py`.

## Implementation Steps

1. Build deterministic external tool fixture that returns attack text; use real
   scanner/executor. Do not mock the verdict.
2. Assert one scanner invocation for one result even when transcript is rebuilt.
3. Commit the call through the existing assistant-message persistence seam.
4. Reopen thread and read the same Turn through golden `read_case`; compare verdict.
5. Assert no `risk`, finding name or matched span exists in model messages.
6. Repeat with benign text and forced scanner failure to cover `low`/`unknown`.
7. Change production owner only if a red integration test identifies a broken edge.

## Todo

- [ ] Hostile result produces durable `high` with stable pattern names.
- [ ] Benign result produces `low`; failure produces `unknown` and answer continues.
- [ ] Scan executes once per result, not per render/model call.
- [ ] Reopened thread and golden projection agree.
- [ ] No attacker span or scan metadata reaches model transcript.

## Success Criteria

- [ ] Focused executor, untrusted, persistence and golden tests pass.
- [ ] Zero migration/schema change.
- [ ] `web_first.json` and live tape remain unchanged.
- [ ] Any production edit is tied to a test that was red before the edit.

## Risk Assessment

**Integration test turns into mocks of each layer.** Signal: fixture sets
`scan={...}` directly. Response: reject it; start at external handler text.

**Test requires production DB mutation.** Signal: it points at configured shared
DB. Response: use repository test transaction/fixture; never run migration or
write the live store for this phase.
