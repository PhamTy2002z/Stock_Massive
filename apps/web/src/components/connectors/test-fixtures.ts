import { vi } from "vitest"

import type { Connector, ConnectorsState, ConnectorTool } from "@/lib/connectors/types"

/** A tool as `describe` puts it on the wire. */
export function tool(overrides: Partial<ConnectorTool> = {}): ConnectorTool {
  return {
    name: "search_notes",
    wire: "mcp__vault__search_notes",
    title: "Find notes",
    description: "Search internal notes",
    effect: "read",
    action: "allow",
    allowed_actions: ["allow", "ask", "deny"],
    read_only_claimed_by_server: false,
    ...overrides,
  }
}

export function connector(overrides: Partial<Connector> = {}): Connector {
  return {
    id: "c-1",
    slug: "vault",
    name: "Internal vault",
    source: "custom",
    catalog_id: null,
    url: "https://mcp.example.com/mcp",
    auth_type: "header",
    status: "connected",
    enabled: true,
    last_error: null,
    breaker_open: false,
    trusted_data: false,
    tools: [],
    dropped: [],
    truncated: 0,
    pending: null,
    snapshot_at: null,
    ...overrides,
  }
}

export function connectorsState(overrides: Partial<ConnectorsState> = {}): ConnectorsState {
  return {
    enabled: true,
    custom_url_allowed: true,
    tool_access: "on_demand",
    catalog: [],
    connectors: [],
    ...overrides,
  }
}

export function json(payload: unknown, status = 200): Response {
  return new Response(JSON.stringify(payload), {
    status,
    headers: { "Content-Type": "application/json" },
  })
}

/**
 * `fetch`, answered by method and path, recording what was sent.
 *
 * `GET /connectors` answers `state`; every other call goes to `write`.
 */
export function stubFetch(state: ConnectorsState, write: (method: string, path: string, body: unknown) => Response) {
  const calls: { method: string; path: string; body: unknown }[] = []
  const mock = vi.fn(async (url: string, init?: RequestInit) => {
    const method = init?.method ?? "GET"
    const path = url.replace("/api/alpha-desk", "")
    const body = typeof init?.body === "string" ? JSON.parse(init.body) : undefined
    if (method === "GET" && path === "/connectors") return json(state)
    calls.push({ method, path, body })
    return write(method, path, body)
  })
  vi.stubGlobal("fetch", mock)
  return calls
}
