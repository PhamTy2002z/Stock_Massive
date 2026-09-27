/**
 * The connectors resource, over the same-origin proxy (`/api/alpha-desk/connectors`).
 *
 * Every route answers with the whole connector as it now stands, so a caller
 * replaces its copy rather than patching one field of it.
 */

import { alphaFetch, alphaSend } from "@/lib/alpha"

import type {
  AddConnectorInput,
  Connector,
  ConnectorsState,
  ToolAccess,
  ToolAction,
} from "./types"

const one = (id: string) => `/connectors/${encodeURIComponent(id)}`

export function fetchConnectors(): Promise<ConnectorsState> {
  return alphaFetch<ConnectorsState>("/connectors")
}

export function addConnector(input: AddConnectorInput): Promise<Connector> {
  return alphaFetch<Connector>("/connectors", { method: "POST", body: JSON.stringify(input) })
}

/** Only the keys present are sent; the backend reads which fields arrived. */
export function updateConnector(
  id: string,
  patch: { enabled?: boolean; header_value?: string },
): Promise<Connector> {
  return alphaFetch<Connector>(one(id), { method: "PATCH", body: JSON.stringify(patch) })
}

export function setToolAction(id: string, toolName: string, action: ToolAction): Promise<Connector> {
  return alphaFetch<Connector>(`${one(id)}/tools/${encodeURIComponent(toolName)}`, {
    method: "PUT",
    body: JSON.stringify({ action }),
  })
}

export function refreshConnector(id: string): Promise<Connector> {
  return alphaFetch<Connector>(`${one(id)}/refresh`, { method: "POST" })
}

/** Take the server's changed tool list as the one this connector now offers. */
export function acceptConnectorChanges(id: string): Promise<Connector> {
  return alphaFetch<Connector>(`${one(id)}/accept`, { method: "POST" })
}

export function deleteConnector(id: string): Promise<void> {
  return alphaSend(one(id), { method: "DELETE" })
}

export function setToolAccess(toolAccess: ToolAccess): Promise<{ tool_access: ToolAccess }> {
  return alphaFetch<{ tool_access: ToolAccess }>("/connectors/preferences", {
    method: "PUT",
    body: JSON.stringify({ tool_access: toolAccess }),
  })
}

export function startConnectorOAuth(id: string): Promise<{ authorize_url: string }> {
  return alphaFetch<{ authorize_url: string }>(`${one(id)}/oauth/start`, { method: "POST" })
}

/**
 * Where the browser may be sent to sign in, or null.
 *
 * The URL came from a server the reader typed in, relayed by the API. Only an
 * http(s) address is followed: `javascript:` or `data:` handed to
 * `location.assign` would run in this origin with the reader's session.
 */
export function safeAuthorizeUrl(raw: unknown): string | null {
  if (typeof raw !== "string") return null
  try {
    const url = new URL(raw)
    return url.protocol === "https:" || url.protocol === "http:" ? url.toString() : null
  } catch {
    return null
  }
}
