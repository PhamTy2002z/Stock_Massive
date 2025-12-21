import { createServerClient } from "@supabase/ssr"
import { NextResponse, type NextRequest } from "next/server"

// Public routes - accessible without authentication
// All other routes are protected by default
const publicRoutes = ["/login", "/register", "/auth/callback"]

// Guest-only routes - redirect to home if already authenticated
const guestOnlyRoutes = ["/login", "/register"]

/**
 * Check if pathname matches any route in the list
 * Supports exact matches and prefix matches (e.g., "/auth/callback" matches "/auth/callback?code=...")
 */
function matchesRoute(pathname: string, routes: string[]): boolean {
  return routes.some(
    (route) => pathname === route || pathname.startsWith(`${route}/`)
  )
}

export async function updateSession(request: NextRequest) {
  let supabaseResponse = NextResponse.next({
    request,
  })

  const supabase = createServerClient(
    process.env.NEXT_PUBLIC_SUPABASE_URL!,
    process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY!,
    {
      cookies: {
        getAll() {
          return request.cookies.getAll()
        },
        setAll(cookiesToSet) {
          cookiesToSet.forEach(({ name, value }) =>
            request.cookies.set(name, value)
          )
          supabaseResponse = NextResponse.next({
            request,
          })
          cookiesToSet.forEach(({ name, value, options }) =>
            supabaseResponse.cookies.set(name, value, options)
          )
        },
      },
    }
  )

  // Refresh session if expired - required for Server Components
  const {
    data: { user },
  } = await supabase.auth.getUser()

  const pathname = request.nextUrl.pathname

  const isPublicRoute = matchesRoute(pathname, publicRoutes)
  const isGuestOnlyRoute = matchesRoute(pathname, guestOnlyRoutes)

  // Protect all routes by default - redirect to login if not authenticated
  if (!isPublicRoute && !user) {
    const loginUrl = new URL("/login", request.url)
    loginUrl.searchParams.set("next", pathname + request.nextUrl.search)
    return NextResponse.redirect(loginUrl)
  }

  // Guest-only routes - redirect to home if already authenticated
  if (isGuestOnlyRoute && user) {
    return NextResponse.redirect(new URL("/", request.url))
  }

  return supabaseResponse
}
