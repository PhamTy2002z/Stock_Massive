# User connectors (remote MCP)

Status: in progress · Branch: `feat/user-connectors` (worktree
`/Users/typham/Dev/worktrees/Stock_Massive-user-connectors`) · Proposal and owner
decisions: [proposal.md](proposal.md).

## Fixed values (placeholders in the brief)

- `N` = **50** tools per connector (`MAX_TOOLS_PER_CONNECTOR`); the rest are listed
  as truncated on the UI.
- Approval wait = **300 s**, then deny. Trial = **5** questions on dev.
- Tool wire name `mcp__<connector>__<tool>`, ≤ 64 chars, `[A-Za-z0-9_]`; a collision
  after sanitising/cutting gets a `_<6 hex sha1>` suffix, never an overwrite.

## Phases

| Phase | File | Gate |
|---|---|---|
| P1 Backend core | [phase-01](phase-01-backend-core.md) | a, c, d, g tests pass; header-auth connector calls a tool on the fake MCP server; result wrapped untrusted |
| P2 OAuth, catalog, Settings UI | [phase-02](phase-02-oauth-catalog-settings.md) | PKCE connect → refresh → disconnect on the fake server; Settings adds, edits permissions, removes |
| P3 Approvals, composer, tool access | [phase-03](phase-03-approvals-composer-tool-access.md) | b via allow_once / always / deny+timeout; composer toggle applies next Turn; both load modes run; on-demand keeps the cached prefix |
| P4 Change detection, breaker | [phase-04](phase-04-change-detection-breaker.md) | e and f pass; breaker opens after repeated failure, 401/403 park immediately |
| Trial | — | 5 dev questions graded from Turn logs (permissions, labels, ledger, isolation) |

## Architecture (one paragraph per seam)

- **Package** `apps/api/src/connectors/`: `models`, `crypto` (MultiFernet),
  `netguard` (SSRF + IP pinning for httpx2), `mcp_client` (MCP SDK 2.0
  `ClientSession` over `streamable_http_client` with our pinned client),
  `snapshot` (sanitise, cap, validate, scan, fingerprint), `policy`, `oauth`,
  `service`, `overlay` (per-Turn `ResolvedTool`s), `approvals` (in-process hub),
  `router` (`/api/connectors`).
- **Surface:** `definitions.resolve_tool_surface(toolsets, extra=..., hidden=...)`.
  Base resolution and its cache stay as they are; overlay tools are merged after
  the base, so a user with no enabled connector gets the byte-identical surface and
  prompt-cache key. Overlay tools are built as `ResolvedTool` directly, never
  through `register()`, so the global registry and its ASK-only-for-writes rule are
  untouched.
- **On-demand mode:** two fixed meta tools (`search_connector_tools`,
  `call_connector_tool`) go into the schema; connector schemas arrive as tool
  *results* (end of the conversation), so the `tools` array and prefix never
  change inside a Turn. The executor unwraps `call_connector_tool` into the hidden
  inner tool and applies its own permission, approval and validation.
- **Approvals:** the loop runs an approval pre-pass for a batch *before* the
  round timeout starts; each ASK call gets its own future keyed by
  `(turn_id, call_id)`. Waiting time is excluded from the lane deadline. No
  `approvals` in the Turn body's `client_capabilities` → deny at once.
- **Untrusted:** every overlay tool is `ContentTrust.UNTRUSTED`,
  `ToolAccess.NETWORK`; reads set `untrusted_content_seen`, so `remember_fact` and
  every write after it are refused by the existing escalation rule (kept as is:
  a connector write only runs in a Turn that has not read outside content).
- **Grounding:** connector results carry a host-built envelope
  (`connector`, `tool`, `trusted_data`, `retrieved_at`, `content`); grounding
  treats `trusted_data=true` as structured evidence and every other connector
  source as `SourceKind.CONNECTOR`, whose matches stay `unverified`
  (`reason=untrusted_connector`) and do not trigger the repair round. Every
  connector source is written to the ledger.

## Constraints kept

Prompt-injection layers, host-built chart numbers, the figure check on every lane,
the cached prefix, and the existing suite (baseline 1507 passed). Dev migration
runs on a **clone** of the dev DB (`stockmassive_connectors`), because the main
tree's API runs `alembic upgrade head` at boot and would refuse an unknown head.

## Ask before

Merge to `main`; migration on a DB with real data; adding a real catalog entry or
setting `trusted_data=true`; anything in the proposal's non-goals.
