/**
 * Where a sign-in may send the reader afterwards: a path on this origin, or `/`.
 *
 * Lives outside `actions.ts` because a `"use server"` module may only export
 * async actions, and every export there is a callable endpoint.
 *
 * A prefix check alone is not enough. Browsers follow the WHATWG URL parser,
 * which treats `\` as `/` in a special scheme, so `/\evil.example` resolves to
 * `//evil.example` — another host. Resolving against a placeholder origin and
 * requiring the result to stay on it asks the same parser the browser will use.
 * Backslashes and control characters are refused outright rather than trusted
 * to normalise the same way in every client.
 */
const INTERNAL_ORIGIN = "http://internal.invalid"

// eslint-disable-next-line no-control-regex -- control characters are exactly what this refuses
const UNSAFE_CHARACTERS = /[\\\u0000-\u001f\u007f]/

export function safeRedirectPath(next?: string | null): string {
  if (!next || !next.startsWith("/") || UNSAFE_CHARACTERS.test(next)) {
    return "/"
  }

  let resolved: URL
  try {
    resolved = new URL(next, INTERNAL_ORIGIN)
  } catch {
    return "/"
  }

  if (resolved.origin !== INTERNAL_ORIGIN || !resolved.pathname.startsWith("/")) {
    return "/"
  }
  // The normalised form, so what is redirected to is exactly what was checked.
  return `${resolved.pathname}${resolved.search}${resolved.hash}`
}
