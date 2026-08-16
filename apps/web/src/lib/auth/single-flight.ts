/**
 * One in-flight call for however many callers ask at once.
 *
 * The refresh token rotates: exchanging it invalidates it. Alpha Desk makes
 * that concrete — two tabs subscribing to the same Turn can meet the same
 * expired access token in the same instant, and without this each would
 * exchange the same refresh token. The first wins, the second is handed a token
 * the API has already retired, and its `401` clears the cookies and signs the
 * user out mid-conversation.
 *
 * Its own module, and its own test, because the property is easy to state and
 * easy to break: a rewrite that awaits anything before assigning the promise
 * reopens the race without changing the shape of the code.
 *
 * **Process-local**, which is the whole of the guarantee and worth saying out
 * loud: two Next instances behind a load balancer would still race. That is
 * acceptable at this size, and fixing it needs a shared lock rather than a
 * bigger variable.
 */
export function singleFlight<T>(work: () => Promise<T>): () => Promise<T> {
  let inFlight: Promise<T> | null = null

  return () => {
    if (inFlight) return inFlight
    // Assigned before anything is awaited. A caller that arrives in the same
    // tick finds the promise rather than an empty slot.
    inFlight = work().finally(() => {
      inFlight = null
    })
    return inFlight
  }
}
