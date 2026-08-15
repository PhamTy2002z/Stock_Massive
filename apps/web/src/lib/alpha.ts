/**
 * The Alpha Desk client: the Watchlist rail, and the Analyses behind it.
 *
 * Same-origin against the Next route handler rather than against FastAPI
 * directly, because the session lives in httpOnly cookies the browser cannot
 * read. That is also why this file does not reuse `fetchApi` from `./api`:
 * those routes are public market data on the API's own origin, these carry a
 * user.
 *
 * A refusal arrives as `{ detail: { reason, message } }` — a stable code the
 * interface branches on and a Vietnamese sentence it shows. Both are kept:
 * flattening them into one string forces every caller to parse prose, and the
 * prose is exactly the part allowed to change.
 */

const ALPHA_BASE = "/api/alpha-desk"

/** Whether a symbol is still analysed, which is a question about the Universe. */
export type WatchlistState = "active" | "unsupported"

/**
 * What the rail shows for one symbol against the session it is labelled with.
 *
 * `ready` is a fact about the Analysis; `pending`, `producing` and `failed`
 * come from the run; `unsupported` comes from the Universe and overrides the
 * rest — nothing new is produced for it, so `pending` would promise an Analysis
 * that is never coming.
 */
export type AnalysisState = "ready" | "pending" | "producing" | "failed" | "unsupported"

/** What the on-demand lane did when a symbol was added. */
export type OnDemandOutcome =
  | "created"
  | "already_analysed"
  | "already_queued"
  | "allowance_exhausted"
  | "no_snapshotted_session"

export interface AnalysisSummary {
  symbol: string
  /** The session this Analysis is for, never the day it was written. */
  trading_day: string
  verdict: string
  /** Several values are in circulation across days; there is one row per pair. */
  schema_version: number
  created_at: string
}

export interface AnalysisDetail extends AnalysisSummary {
  payload: Record<string, unknown>
}

export interface AnalysisHistory {
  symbol: string
  entries: AnalysisSummary[]
  /** How far back this window reaches. A browsing depth, not a retention rule. */
  depth: number
  /** Whether anything lies past the bound — the edge, rather than an empty scroll. */
  older_exist: boolean
}

export interface RunFailure {
  code: string | null
  message: string | null
  attempts: number
  max_attempts: number
  /** The ceiling is reached: offer no retry that would do nothing. */
  exhausted: boolean
}

export interface RailEntry {
  symbol: string
  state: AnalysisState
  added_at: string
  /** The newest Analysis that exists, whatever session it is for. */
  latest: AnalysisSummary | null
  failure: RunFailure | null
  unread: boolean
  last_seen_analysis_date: string | null
}

export interface Rail {
  cap: number
  /** Active entries only; `unsupported` ones are listed and not counted. */
  count: number
  /** The session the rail is showing. Null only when nothing has closed yet. */
  trading_day: string | null
  entries: RailEntry[]
}

export interface OnDemandResult {
  outcome: OnDemandOutcome
  trading_day: string | null
  remaining: number
  allowance: number
  message: string | null
}

export interface WatchlistItem {
  symbol: string
  state: WatchlistState
  added_at: string
}

export interface WatchlistView {
  cap: number
  count: number
  entries: WatchlistItem[]
}

export interface WatchlistAddition extends WatchlistView {
  on_demand: OnDemandResult
}

export interface RetryResult {
  symbol: string
  trading_day: string
  status: "pending" | "producing" | "ready" | "failed"
  attempts: number
  max_attempts: number
  locked: boolean
  error_code: string | null
  error_message: string | null
}

export interface AnalysisOpened {
  symbol: string
  last_seen_analysis_date: string
}

/**
 * A request Alpha Desk refused, carrying the code and the sentence separately.
 *
 * `reason` is null when the failure was not one of Alpha Desk's own — a proxy
 * error, a 500 — so a caller branching on reasons cannot mistake an outage for
 * a rule.
 */
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
    // Not JSON; fall through to the status line.
  }
  return new AlphaRefusalError(
    response.status,
    null,
    `Alpha Desk error: ${response.statusText || response.status}`,
  )
}

async function alphaFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const response = await fetch(`${ALPHA_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...init?.headers },
    credentials: "same-origin",
  })

  if (!response.ok) throw await readRefusal(response)
  return response.json() as Promise<T>
}

/** The whole rail in one request: the session, the cap, and every symbol's state. */
export function fetchRail(): Promise<Rail> {
  return alphaFetch<Rail>("/watchlist/rail")
}

/** Start watching a symbol. The response says what it cost to produce, if anything. */
export function addWatchlistSymbol(symbol: string): Promise<WatchlistAddition> {
  return alphaFetch<WatchlistAddition>("/watchlist", {
    method: "POST",
    body: JSON.stringify({ symbol }),
  })
}

/** Stop watching a symbol. Nothing else is deleted — no Analysis, no Thread. */
export function removeWatchlistSymbol(symbol: string): Promise<WatchlistView> {
  return alphaFetch<WatchlistView>(`/watchlist/${encodeURIComponent(symbol)}`, {
    method: "DELETE",
  })
}

/** One Analysis in full, or a refusal naming the pair that has none. */
export function fetchAnalysis(symbol: string, tradingDay: string): Promise<AnalysisDetail> {
  return alphaFetch<AnalysisDetail>(
    `/analyses/${encodeURIComponent(symbol)}/${encodeURIComponent(tradingDay)}`,
  )
}

/** One symbol's recent Analyses, newest first, bounded by the API. */
export function fetchAnalysisHistory(symbol: string): Promise<AnalysisHistory> {
  return alphaFetch<AnalysisHistory>(`/analyses/${encodeURIComponent(symbol)}`)
}

/**
 * Report that the user opened this Analysis.
 *
 * The only thing that advances their last-seen date, and deliberately an
 * explicit act: doing it on a list request would clear every badge at once.
 */
export function markAnalysisOpened(
  symbol: string,
  tradingDay: string,
): Promise<AnalysisOpened> {
  return alphaFetch<AnalysisOpened>(
    `/analyses/${encodeURIComponent(symbol)}/${encodeURIComponent(tradingDay)}/opened`,
    { method: "POST" },
  )
}

/** Ask for another attempt at a session that failed. It queues; it does not produce. */
export function retryAnalysis(symbol: string, tradingDay: string): Promise<RetryResult> {
  return alphaFetch<RetryResult>(
    `/analyses/${encodeURIComponent(symbol)}/${encodeURIComponent(tradingDay)}/retry`,
    { method: "POST" },
  )
}
