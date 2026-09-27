import { splitSources } from "./figure-markers"
import type { ToolCall } from "./types"

/** One source an answer rested on, as the sources pill and panel show it. */
export interface AnswerSource {
  /** Who published it: a hostname for a page, a provider's name for a figure. */
  publisher: string
  title: string
  /** Where a click goes; `null` only when there is nowhere honest to send it. */
  url: string | null
  /**
   * The host a click actually lands on, read from `url`.
   *
   * Shown beside the publisher because the publisher is a label the answer
   * wrote: "Vietcap — …" can sit on a link to any domain, and the host is the
   * part of the row an injected page cannot choose.
   */
  host: string | null
  /** What its icon is drawn from: a hostname when there is one. */
  mark: string
  /**
   * Whether `mark` may be sent to the favicon proxy.
   *
   * Only for a host this Turn's own tool results recorded. A link that appears
   * only in the answer's text was written by the model, possibly under a page's
   * injection, and asking the proxy for its icon would make the backend resolve
   * and call a host the text chose — with nobody clicking anything. Its DNS
   * labels alone can carry whatever the model was told to leak. Such a row
   * keeps its letters and makes no request.
   */
  favicon: boolean
}

/**
 * Every source behind an answer, once each, in the order a reader meets them.
 *
 * The sources the answer cites come first, then the pages its searches turned
 * up. A figure from a provider feed has no page of its own, so it links to the
 * provider's page for the ticker instead (`providerLink`).
 */
export function answerSources(text: string, toolCalls: ToolCall[]): AnswerSource[] {
  const sources: AnswerSource[] = []
  const seen = new Set<string>()
  const add = (source: AnswerSource) => {
    const key = source.url ?? `${source.publisher} — ${source.title}`
    if (seen.has(key)) return
    seen.add(key)
    sources.push(source)
  }

  // Hosts the backend itself reached for this Turn: the only ones a cited link
  // may borrow a favicon from.
  const recorded = new Set<string>()
  for (const call of toolCalls) {
    for (const result of call.results) {
      const host = hostname(result.url || null)
      if (host) recorded.add(host)
      if (result.source) recorded.add(result.source.toLowerCase())
    }
  }

  for (const cited of splitSources(text).sources) {
    const [publisher, ...rest] = cited.label.split(" — ")
    const title = rest.join(" — ") || publisher
    const url = cited.url ?? providerLink(publisher, title)
    const citedHost = hostname(cited.url)
    add({
      publisher,
      title,
      url,
      host: hostname(url),
      mark: citedHost ?? publisher,
      favicon: citedHost !== null && recorded.has(citedHost),
    })
  }
  for (const call of toolCalls) {
    for (const result of call.results) {
      add({
        publisher: result.source,
        title: result.title || result.source,
        url: result.url || null,
        host: hostname(result.url || null),
        mark: result.source,
        favicon: true,
      })
    }
  }
  return sources
}

/** A provider's public page for the ticker a figure's title names. */
function providerLink(publisher: string, title: string): string | null {
  const ticker = /^([A-Z0-9]{3,5}) ·/.exec(title)?.[1]
  if (publisher === "Vietcap") {
    return ticker
      ? `https://trading.vietcap.com.vn/iq/company?ticker=${ticker}`
      : "https://www.vietcap.com.vn/"
  }
  // ponytail: homepage only, KBS has no ticker page we could confirm.
  if (publisher === "KB Securities") return "https://www.kbsec.com.vn/"
  return null
}

function hostname(url: string | null): string | null {
  if (!url) return null
  try {
    return new URL(url).hostname
  } catch {
    return null
  }
}
