import { Suspense } from "react"

import { AppShell } from "@/components/shell/app-shell"

/**
 * The product, at one address.
 *
 * The surface reads the signed-in account's Threads, so there is
 * nothing to prerender: a build-time snapshot would ship somebody else's.
 */
export const dynamic = "force-dynamic"

export default function HomePage() {
  return (
    // `useSearchParams` reads the `?symbol=` deep link, and Next requires a
    // boundary around any component that does.
    <Suspense>
      <AppShell />
    </Suspense>
  )
}
