# P1 — Backend core

## Requirements

Data model, encrypted credentials, SSRF-safe MCP client, per-Turn overlay with
Allow/Block permissions, untrusted wrapping, header-auth custom connectors behind
`CONNECTORS_CUSTOM_URL`.

## Files

- New `apps/api/src/connectors/{__init__,models,crypto,netguard,mcp_client,snapshot,policy,service,overlay,router}.py`
- New migration `apps/api/alembic/versions/<rev>_add_user_connectors.py`
- Edit `src/core/config.py` (settings), `src/main.py` (router), `src/agent/definitions.py`
  (`extra`), `src/agent/loop.py` + `src/agent/turns.py` (overlay into the Turn),
  `src/agent/evidence/grounding.py` (connector sources), `requirements.txt`.
- Tests: `tests/connectors/fake_mcp_server.py` (MCP SDK server over Streamable
  HTTP on a local uvicorn), `tests/test_connectors_*.py`.

## Settings

`CONNECTORS_ENABLED` (default false), `CONNECTORS_ENCRYPTION_KEYS` (comma list,
first encrypts, all decrypt), `CONNECTORS_CUSTOM_URL` (default false),
`CONNECTORS_CUSTOM_URL_USERS` (comma list of user ids; the profile must also be
`personal_internal`), `CONNECTORS_CALL_TIMEOUT_SECONDS` (20),
`CONNECTORS_MAX_RESULT_CHARS` (20 000).

## Steps

1. Models: `connector_catalog`, `user_connector`, `connector_oauth_state`,
   `user_connector_preference` (tool access mode). Policies and the tool snapshot
   are JSONB on `user_connector`. Delete cascades from `users`.
2. `crypto`: `MultiFernet` over the key list; `encrypt(dict) -> str`,
   `decrypt(str) -> dict`; `rotate(token)`; refuse to start connectors with no key.
3. `netguard`: `validate_connector_url` (https; public host; no credentials in
   URL) and `PinnedBackend` for httpcore2 — the first `connect_tcp` to a host
   resolves once, rejects any non-global address, and connects to that address
   only; every later connection of the same client reuses it (no second lookup).
   Redirects are off. `allow_private_hosts_for_tests()` is a context manager with
   no environment switch, and refuses under `deployment_profile == "production"`.
4. `mcp_client`: `list_tools(target)` and `call_tool(target, name, args)` over a
   fresh session (initialize + request), typed errors `ConnectorAuthError`
   (401/403), `ConnectorUnavailable`, `ConnectorProtocolError`.
5. `snapshot`: sanitise + dedupe wire names (hash suffix), cap 50, drop tools
   whose schema fails `assert_supported_schema` or whose description trips
   `threat_patterns`, record each drop with a reason; fingerprint = sha256 of the
   kept tools' name/description/schema/annotations.
6. `policy`: effect per tool (catalog: operator map; custom: annotations only
   tighten), default action, allowed actions; writes can only be `ask`/`deny`.
7. `overlay`: for one user at Turn start, enabled + connected connectors →
   `ResolvedTool`s (`UNTRUSTED`, `NETWORK`, `timeout`, `max_result_size_chars`,
   permission rules from policy; `deny` tools are left out of the schema). The
   handler returns the envelope `{connector, connector_name, tool, trusted_data,
   retrieved_at, content, is_error}`; non-text/oversized results are cut with a
   stated reason.
8. Loop/turns: `TurnRequest.connectors` (overlay resolved in `TurnService.create`),
   `resolve_tool_surface(..., extra=overlay.tools)`.
9. Grounding: `SourceKind.CONNECTOR`; trusted → structured; ledger gets every
   connector source.
10. Router: list catalog/mine, add custom (flag + allowlist), patch enabled /
    policies / header secret, refresh, delete (deletes credentials).

## Validation

- a: `test_connectors_overlay.py::test_other_users_never_see_a_connector`
- c: `test_connectors_netguard.py` (literal private IP, DNS to private, redirect,
  rebinding second lookup, production refuses the test override)
- d: `test_connectors_overlay.py::test_a_connector_read_blocks_remember_fact`
- g: `test_connectors_service.py::test_no_plaintext_secret_in_the_database`
- Integration: header auth round trip through the fake server; result wrapped.

## Risk / rollback

Everything is behind `CONNECTORS_ENABLED`; with it off the overlay is empty and
the surface is identical to today. Rollback = flag off; migration downgrade drops
only the new tables.
