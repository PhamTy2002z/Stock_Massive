---
phase: 3
title: "Cacheable Domain Body And Identity"
status: complete
priority: P1
effort: "7h"
dependencies: [2]
---

# Phase 3: Cacheable Domain Body And Identity

## Context Links

- `plans/260829-1435-c5-domain-pack/phase-05-load-body-on-tool-path.md`
- `apps/api/src/agent/prompt/contract.py::cache_key`
- `apps/api/src/agent/domain/pack.py::DomainPack.identity`
- `apps/api/src/agent/definitions.py::ResolvedToolSurface.identity_digest`

## Overview

Đưa body pack khỏi tail note vào stable prefix ngay sau core. Giữ nguyên ba
trigger C5, prose và sticky lifetime; cache identity có runtime caller thật.

## Requirements

- Functional: system content theo thứ tự `core → optional domain body → runtime`;
  body bật giữa Turn xuất hiện từ call kế tiếp và dính tới cuối Turn.
- Functional: core/body là byte-stable prefixes; runtime date/name ở sau chúng.
- Functional: identity = model + prompt version/hash + resolved surface digest +
  pack identity; không có user, thread, date, mode hoặc question.
- Functional: `cache_key()` được dùng trong runtime request/replay metadata,
  không giả vờ điều khiển provider content-addressed cache.
- Non-functional: giữ `llm_prompt_cache_control_enabled=False`; không gửi
  `prompt_cache_key` field chưa được route chứng minh.
- Non-functional: token reservation đúng sau khi body chuyển vào constructed context.

## Architecture

Mở rộng typed system-message input để `_system_message()` ghép core, optional
cached extension và runtime suffix mà `Message.segments` vẫn concatenate đúng
`content`. Khi body vào context, xoá đường append/reserve riêng ở `_call`.
`AgentLoop` đã có `surface.identity_digest`; ghép nó với `active_pack().identity`
và prompt contract thành identity auditable trong `CompletionRequest.metadata`.

Automatic provider cache key vẫn là bytes đầu request. Khác pack có body bytes
khác nên không cross-hit sai; core giống nhau có thể share an toàn.

## Related Code Files

- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/messages.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/loop.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/src/agent/prompt/contract.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/src/core/llm/protocol.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_loop.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_prompt.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_agent_domain_pack.py`
- Modify: `/Users/typham/Dev/Stock_Massive/apps/api/tests/test_llm_route_resilience.py`

## Implementation Steps

1. Viết transcript tests cho no-domain, signal-desk, history trigger và tool-path trigger.
2. Thêm typed optional body vào `Transcript`/system builder; không string-search boundary.
3. Xoá body tail message và duplicated reservation khỏi `_construct`/`_call`.
4. Tính runtime cache identity sau `resolve_tool_surface`; attach metadata mọi call.
5. Bump `PROMPT_VERSION` theo convention vì wire order đổi, dù prose không đổi.
6. Test two packs/two surfaces tạo identity khác; runtime values không vào key.
7. Replay Phase 1 để xác nhận body token count không đổi ngoài vị trí/layer.

## Success Criteria

- [x] Body chỉ có khi trigger bật, đúng một lần, từ call kế tiếp tới cuối Turn.
- [x] Body đứng trước runtime/user/tool messages trong actual wire content.
- [x] Không body token nào vừa nằm constructed context vừa bị reserve lần hai.
- [x] Pack prose/surface đổi làm identity đổi; date/name/question không làm đổi.
- [x] `cache_control` vẫn off và transport wire không nhận field mới.
- [x] C5 domain-pack transcript tests xanh nguyên (25 pass).

## Evidence

`reports/phase-03-260829-cacheable-head.md`. Replay: 687.269 → **687.145**
token, và toàn bộ −124 nằm ở `domain_body` — bốn token overhead của một message
× 31 lượt gọi từng mang body riêng. Mọi layer khác không đổi một token, tức đây
là phép dời chỗ chứ không phải phép cắt. `PROMPT_VERSION` 3.0.0 → 3.1.0.
`make test` 1739 pass.

## Risk Assessment

**Instruction precedence đổi:** signal là Golden đọc web/store giảm sau reorder.
Response: rollback body placement, giữ identity/measurement, replan prompt order.

**Prefix không stable:** signal là cùng pack/surface sinh hai identity hoặc bytes
khác nhau. Response: fail import/test; không enable/configure cache workaround.

## Security Considerations

Cache identity không mang tenant/user data. Runtime values luôn sau stable blocks;
không cho conversation content vào system prefix hoặc cache metadata.

## Rollback

Trả body về tail note và reservation cũ, revert prompt version; phase 1–2 vẫn
độc lập và tiếp tục dùng được.
