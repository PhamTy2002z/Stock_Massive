/**
 * Reading a Widget's data back, through the message that stores its descriptor.
 *
 * The request names a message and a descriptor id, and never a descriptor: the
 * only slice this can fetch is one already attached to an answer the caller
 * owns. That is what makes "a reopened Thread renders the same historical
 * slice" a property of the URL rather than of anybody's care — there is no
 * parameter here through which today could be asked for.
 *
 * Same-origin against the Next route handler for the reason `lib/alpha.ts`
 * gives: the session lives in httpOnly cookies the browser cannot read.
 */

import type { WidgetData, WidgetSpec } from "./types"

const BASE = "/api/alpha-desk/widgets"

export class WidgetDataUnavailable extends Error {
  constructor(readonly status: number) {
    super(`Widget data could not be read (${status})`)
    this.name = "WidgetDataUnavailable"
  }
}

/**
 * Bind a resolver to one message, ready to hand to a slot.
 *
 * Curried rather than taking the message id per call because a slot resolves
 * exactly one descriptor and should not be in a position to ask for another
 * message's.
 */
export function widgetResolverFor(
  messageId: number,
  fetcher: typeof fetch = fetch
): (spec: WidgetSpec) => Promise<WidgetData> {
  return async (spec: WidgetSpec) => {
    const response = await fetcher(
      `${BASE}/${messageId}/${encodeURIComponent(spec.descriptor_id)}`,
      { credentials: "same-origin" }
    )
    if (!response.ok) throw new WidgetDataUnavailable(response.status)
    return (await response.json()) as WidgetData
  }
}
