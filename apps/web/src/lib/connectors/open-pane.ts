/**
 * Opening Settings on the Connectors pane, from somewhere that is not Settings.
 *
 * Two callers: the composer's "Manage connectors" and the page the OAuth sign-in
 * comes back to (`?connector=<id>&connector_status=connected|failed`). The
 * Settings dialog keeps its selected pane in its own state, so the request is
 * left here for it to read when it mounts — read without consuming in render
 * (a StrictMode double render must see the same answer) and cleared by the pane
 * in an effect.
 */

export interface PaneRequest {
  /** How the OAuth sign-in ended, when this request came back from one. */
  outcome: "connected" | "failed" | null
  connectorId: string | null
}

let requested: PaneRequest | null = null

export function requestConnectorsPane(
  request: PaneRequest = { outcome: null, connectorId: null },
): void {
  requested = request
}

export function peekConnectorsPane(): PaneRequest | null {
  return requested
}

export function clearConnectorsPane(): void {
  requested = null
}

const RETURN_KEYS = ["connector", "connector_status", "connector_reason"]

/** The OAuth return in a query string, or null when this page load is not one. */
export function readOAuthReturn(search: string): PaneRequest | null {
  const params = new URLSearchParams(search)
  const status = params.get("connector_status")
  if (status !== "connected" && status !== "failed") return null
  return { outcome: status, connectorId: params.get("connector") || null }
}

/** The same address without the OAuth return's keys, so a reload does not replay it. */
export function stripOAuthReturn(href: string): string {
  const url = new URL(href)
  for (const key of RETURN_KEYS) url.searchParams.delete(key)
  return `${url.pathname}${url.search}${url.hash}`
}
