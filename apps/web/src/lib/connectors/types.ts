/**
 * The connectors resource as `/api/v1/connectors` puts it on the wire.
 *
 * Hand-written against `connectors/service.py` (`describe`, `describe_catalog`)
 * and snake_case for the same reason `alpha-desk/types.ts` is: one name per
 * field, the one that arrives. Nothing here can carry a credential — the
 * backend's `describe` has no field that could.
 */

export type ConnectorStatus = "connected" | "needs_auth" | "needs_reconsent" | "error"
export type ConnectorAuth = "none" | "header" | "oauth"
export type ToolEffect = "read" | "write"
export type ToolAction = "allow" | "ask" | "deny"
export type ToolAccess = "on_demand" | "preloaded"

export interface ConnectorTool {
  /** The server's own tool name. What the policy PUT is keyed by. */
  name: string
  /** `mcp__…`: the model's name for it. Never drawn — it means nothing to a reader. */
  wire: string
  title: string
  description: string
  effect: ToolEffect
  action: ToolAction
  /** The actions this tool may be set to. A write never offers `allow`. */
  allowed_actions: ToolAction[]
  /** A custom connector's read is the server's own claim, not a checked fact. */
  read_only_claimed_by_server: boolean
}

export interface DroppedTool {
  name: string
  reason: string
}

export interface PendingChange {
  added: string[]
  removed: string[]
  changed: string[]
  detected_at: string | null
}

export interface Connector {
  id: string
  slug: string
  name: string
  source: "catalog" | "custom"
  catalog_id: number | null
  url: string
  auth_type: ConnectorAuth
  status: ConnectorStatus
  enabled: boolean
  last_error: string | null
  breaker_open: boolean
  trusted_data: boolean
  tools: ConnectorTool[]
  dropped: DroppedTool[]
  /** How many tools were cut by the per-connector limit. */
  truncated: number
  pending: PendingChange | null
  snapshot_at: string | null
}

export interface CatalogEntry {
  id: number
  slug: string
  name: string
  description: string
  auth_type: ConnectorAuth
  trusted_data: boolean
}

export interface ConnectorsState {
  enabled: boolean
  custom_url_allowed: boolean
  tool_access: ToolAccess
  catalog: CatalogEntry[]
  connectors: Connector[]
}

export type AddConnectorInput =
  | { catalog_id: number; header_value?: string }
  | { name: string; url: string; header_name?: string; header_value?: string; oauth?: boolean }
