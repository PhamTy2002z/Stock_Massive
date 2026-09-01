/**
 * Authenticated chat transport over the same-origin Next.js proxy.
 *
 * Network silence becomes `ApiUnavailableError` so `ConnectionGate` can wait
 * and retry. An answered refusal keeps its typed reason for the caller.
 */

import {
  ApiUnavailableError,
  connectionStatus,
  UPSTREAM_UNREACHABLE,
} from "./connection-status"

const ALPHA_BASE = "/api/alpha-desk"

export class AlphaRefusalError extends Error {
  constructor(
    public status: number,
    public reason: string | null,
    message: string,
  ) {
    super(message)
    this.name = "AlphaRefusalError"
  }
}

async function readRefusal(response: Response): Promise<AlphaRefusalError> {
  try {
    const body = await response.json()
    const detail = body?.detail
    if (detail && typeof detail === "object" && typeof detail.message === "string") {
      return new AlphaRefusalError(response.status, detail.reason ?? null, detail.message)
    }
    if (typeof detail === "string" && detail) {
      return new AlphaRefusalError(response.status, null, detail)
    }
  } catch {
    // Non-JSON failures fall back to the HTTP status line.
  }
  return new AlphaRefusalError(
    response.status,
    null,
    `Agent API error: ${response.statusText || response.status}`,
  )
}

async function sendAlpha(path: string, init?: RequestInit): Promise<Response> {
  const url = `${ALPHA_BASE}${path}`
  const isFormData = typeof FormData !== "undefined" && init?.body instanceof FormData
  let response: Response
  try {
    response = await fetch(url, {
      ...init,
      headers: isFormData
        ? { ...init?.headers }
        : { "Content-Type": "application/json", ...init?.headers },
      credentials: "same-origin",
    })
  } catch (cause) {
    connectionStatus.reportWaiting(url)
    throw new ApiUnavailableError(undefined, undefined, { cause })
  }

  if (response.ok) {
    connectionStatus.reportReady(url)
    return response
  }

  const refusal = await readRefusal(response)
  if (refusal.reason === UPSTREAM_UNREACHABLE) {
    connectionStatus.reportWaiting(url)
    throw new ApiUnavailableError(refusal.message, response.status)
  }

  connectionStatus.reportReady(url)
  throw refusal
}

export async function alphaFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await sendAlpha(path, init)
  return response.json() as Promise<T>
}

export async function alphaSend(path: string, init?: RequestInit): Promise<void> {
  await sendAlpha(path, init)
}
