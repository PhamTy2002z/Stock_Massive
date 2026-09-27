# P3 — Approvals, composer, tool access

## Requirements

In-Turn approval over SSE; composer submenu to toggle connectors and choose the
tool access mode; on-demand loading that keeps the cached prefix.

## Contract changes (server and web together)

- `CreateTurnRequest.client_capabilities: list["approvals"]` (default empty).
- SSE `approval.requested` `{call_id, connector, tool, display, effect, arguments_preview,
  can_always, expires_at}` and `approval.resolved` `{call_id, decision}`; snapshot
  restates pending approvals under `approvals`.
- `POST /api/alpha-desk/turns/{turn_id}/approvals/{call_id}` `{decision:
  allow_once|always|deny}` — owner only; `always` refused for locked tools.

## Steps

1. `connectors/approvals.py`: hub of futures keyed `(turn_id, call_id)`, resolves on
   answer, cancel, timeout (300 s), connector disabled/deleted.
2. Executor: `approve(calls)` pre-pass (called by the loop before the round
   timeout) and a grant check in `_dispatch`; writes that would be blocked by the
   escalation rule are not asked about.
3. Loop: pause accounting so waiting does not spend the lane deadline.
4. On-demand meta tools and executor unwrapping.
5. Web: approval card in the chat view, SSE handling, turn body capability,
   composer "+" › Kết nối submenu with toggles + Truy cập công cụ.

## Validation

- `test_connectors_approvals.py`: allow_once, always (persists allow), deny,
  timeout, no capability → immediate deny, two parallel approvals, connector
  disabled while waiting.
- `test_connectors_tool_access.py`: both modes run a tool; on-demand
  `identity_digest`/cache key unchanged before/after loading and across users.
- Web vitest: approval card sends the decision; composer toggle PATCHes.
