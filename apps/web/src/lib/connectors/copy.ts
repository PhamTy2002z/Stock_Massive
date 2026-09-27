/**
 * The words the connectors surfaces say, in one place.
 *
 * The backend's refusals carry a stable `reason` and an English sentence meant
 * for logs; the reader is shown the English line keyed by the reason, and the
 * backend's sentence only for a reason this client does not know yet.
 */

import { AlphaRefusalError } from "@/lib/alpha"
import { ApiUnavailableError } from "@/lib/connection-status"

import type { ConnectorAuth, ConnectorStatus, ToolAccess, ToolAction } from "./types"

export const STATUS_LABEL: Record<ConnectorStatus, string> = {
  connected: "Connected",
  needs_auth: "Needs sign-in",
  needs_reconsent: "Needs confirmation",
  error: "Error",
}

export const AUTH_LABEL: Record<ConnectorAuth, string> = {
  none: "None",
  header: "Key",
  oauth: "OAuth",
}

export const SOURCE_LABEL = { catalog: "Catalog", custom: "Custom" } as const

export const ACTION_LABEL: Record<ToolAction, string> = {
  allow: "Allow",
  ask: "Needs approval",
  deny: "Block",
}

export const TOOL_ACCESS_COPY: Record<ToolAccess, { label: string; hint: string }> = {
  on_demand: {
    label: "Load on demand",
    hint: "Compacts the conversation less often, since tools aren't preloaded",
  },
  preloaded: {
    label: "Preload",
    hint: "Compacts the conversation more often, since tools are already loaded",
  },
}

export const WRITE_NEEDS_APPROVAL = "A write tool always needs approval"
export const SERVER_CLAIMED_READ_ONLY = "The server declares itself read-only — this is not verified"
export const TOOL_LIMIT = 50

const REFUSAL: Record<string, string> = {
  connectors_disabled: "Connectors aren't enabled on this system.",
  custom_url_not_allowed: "This account isn't allowed to add a custom URL.",
  url_refused: "That server address was refused. Only a public, safe address works.",
  header_refused: "This header name can't carry a key.",
  credential_required: "This connector needs an access key.",
  name_required: "Please name this connector.",
  write_needs_approval: `${WRITE_NEEDS_APPROVAL}.`,
  not_header_auth: "This connector doesn't use a key.",
  not_oauth: "This connector doesn't sign in with OAuth.",
  approve_once_only: "This tool can only be approved one call at a time.",
}

/** What to tell the reader about a failed connectors call. */
export function refusalMessage(error: unknown): string {
  if (error instanceof ApiUnavailableError) return "The system isn't responding. Try again shortly."
  if (error instanceof AlphaRefusalError) {
    const known = error.reason ? REFUSAL[error.reason] : undefined
    if (known) return known
    if (error.status === 404) return "This connector no longer exists."
    return `Couldn't complete that: ${error.message}`
  }
  return "Couldn't complete that. Please try again."
}

/** A dropped tool's reason, in words. `suspicious_text:…` and `unsupported_schema: …` carry details. */
export function droppedReason(reason: string): string {
  if (reason === "no_name") return "No name"
  if (reason === "duplicate_name") return "Duplicate name of another tool"
  if (reason === "over_tool_limit") return `Over the ${TOOL_LIMIT}-tool limit`
  if (reason.startsWith("suspicious_text")) return "Description contains suspicious content, so it wasn't loaded"
  if (reason.startsWith("unsupported_schema")) return "This tool's parameters aren't supported"
  return "Not usable"
}
