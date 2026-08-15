import { NextResponse, type NextRequest } from "next/server"

// Public routes - accessible without authentication
// All other routes are protected by default
const publicRoutes = ["/login", "/register"]

// Guest-only routes - redirect to home if already authenticated
const guestOnlyRoutes = ["/login", "/register"]

// Duplicated from lib/auth/session.ts: that module is server-only and importing
// it here would pull `next/headers` into the middleware runtime.
const REFRESH_TOKEN_COOKIE = "sm_refresh_token"

/**
 * Check if pathname matches any route in the list
 * Supports exact matches and prefix matches (e.g., "/login" matches "/login/help")
 */
function matchesRoute(pathname: string, routes: string[]): boolean {
  return routes.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`)
  )
}

/**
 * Route gate based on the presence of a refresh cookie.
 *
 * Presence is a cheap signal, not proof: the token is still verified by the API
 * on every request. Validating here would mean a network call on every
 * navigation, and a forged cookie buys nothing but a redirect to a page whose
 * data calls will 401 anyway.
 */
export function middleware(request: NextRequest) {
  const hasSession = !!request.cookies.get(REFRESH_TOKEN_COOKIE)?.value
  const pathname = request.nextUrl.pathname

  if (!matchesRoute(pathname, publicRoutes) && !hasSession) {
    const loginUrl = new URL("/login", request.url)
    loginUrl.searchParams.set("next", pathname + request.nextUrl.search)
    return NextResponse.redirect(loginUrl)
  }

  if (matchesRoute(pathname, guestOnlyRoutes) && hasSession) {
    return NextResponse.redirect(new URL("/", request.url))
  }

  return NextResponse.next()
}

export const config = {
  matcher: [
    /*
     * Match all request paths except for the ones starting with:
     * - api/auth (session endpoints must stay reachable while signed out)
     * - api/alpha-desk (a fetch cannot follow a login redirect; the handler
     *   authenticates and answers 401 instead)
     * - _next/static (static files)
     * - _next/image (image optimization files)
     * - favicon.ico (favicon file)
     * - public folder
     */
    "/((?!api/auth|api/alpha-desk|_next/static|_next/image|favicon.ico|.*\\.(?:svg|png|jpg|jpeg|gif|webp)$).*)",
  ],
}
