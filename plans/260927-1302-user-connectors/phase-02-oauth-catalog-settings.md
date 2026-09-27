# P2 — OAuth, catalog, Settings UI

## Requirements

OAuth 2.1 + PKCE (S256) for connectors whose catalog entry or discovery says so;
refresh under a row lock; disconnect deletes tokens. Catalog tab for every user;
Settings pane "Kết nối" to add, edit tool permissions, remove.

## Files

- `src/connectors/oauth.py`, router endpoints `/oauth/start`, `/oauth/callback`.
- Web: `apps/web/src/lib/connectors/*` (API client, types), `apps/web/src/components/connectors/*`
  (pane, table, detail, add dialog); one entry in `components/shell/settings-dialog.tsx`
  registered after the peer session's Settings rework lands.

## Steps

1. Discovery: `WWW-Authenticate` / RFC 9728 protected-resource metadata →
   RFC 8414 authorization-server metadata (every URL through `netguard`).
2. Client: catalog `oauth_client_id` if set, otherwise RFC 7591 dynamic
   registration; stored encrypted on the connector.
3. Start: PKCE verifier + `state` stored in `connector_oauth_state` (encrypted
   verifier, 10 min expiry); callback exchanges the code, stores tokens with an
   absolute `expires_at`, snapshots tools.
4. Refresh: `SELECT … FOR UPDATE` on the connector row, re-read, refresh only if
   still expiring, commit — two Turns never refresh the same token twice.
5. UI: table Connector / Loại / Xác thực / Trạng thái, tabs Của bạn / Khám phá,
   "Thêm" (custom URL shown only when the server says it is allowed), detail page
   with Ngắt kết nối and per-tool tri-state; write tools never offer Cho phép;
   custom read-only tools say the classification is the server's own claim.

## Validation

- `test_connectors_oauth.py`: full PKCE round trip against the fake auth server,
  refresh, concurrent refresh takes one exchange, disconnect removes tokens.
- Web vitest for the pane (add, edit permission, remove, locked write tool).

## Risk

Real providers differ in discovery details; the fake server follows the MCP
authorization spec. Real catalog entries need the owner (ask-before).
