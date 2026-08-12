"use client"

import { useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { usePathname } from "next/navigation"
import { useEffect, useSyncExternalStore } from "react"
import { toast } from "sonner"

import { getApiBaseUrl } from "@/lib/api"
import { connectionStatus, healthUrlFrom } from "@/lib/connection-status"

/** How often to ask whether the API is back. Restarts take a second or two. */
const PROBE_INTERVAL_MS = 3000
const TOAST_ID = "connection-waiting"

/**
 * Veils the page while the API is unreachable, and lifts by itself.
 *
 * A restarting container, an exhausted rate limit and a dropped connection are
 * all states the system leaves on its own within seconds. Surfacing them as
 * errors handed the user a `Failed to fetch` and a broken-looking screen for a
 * problem that had already fixed itself by the time they read it.
 *
 * So the page is dimmed rather than replaced: what was on screen stays
 * readable underneath, no route unmounts, no query cache is thrown away, and
 * when the probe finds the API answering the veil lifts and the stale views
 * refetch in place.
 */
export function ConnectionGate({ children }: { children: React.ReactNode }) {
  const queryClient = useQueryClient()
  const state = useSyncExternalStore(
    connectionStatus.subscribe,
    () => connectionStatus.get(),
    // The server renders the optimistic state: it has no failed request to go
    // on, and a veil in the HTML would flash on every first paint.
    () => "ready" as const
  )
  // PROTOTYPE-BRANCH ONLY (issue #21). A throwaway route runs on fixtures and
  // needs no API, but the surrounding chrome — header search, JobProgressBar —
  // still calls one, so an absent backend veiled the mockup itself. Drop this
  // when the branch is folded back.
  const pathname = usePathname()
  const isPrototype = pathname?.startsWith("/prototypes") ?? false

  const waiting = state === "waiting" && !isPrototype

  useEffect(() => {
    if (!waiting) {
      toast.dismiss(TOAST_ID)
      return
    }

    toast.loading("Đang chờ hệ thống phản hồi…", {
      id: TOAST_ID,
      description: "Dữ liệu sẽ tự hiện lại, bạn không cần tải lại trang.",
      duration: Infinity,
    })

    const healthUrl = healthUrlFrom(getApiBaseUrl())
    let cancelled = false

    const probe = async () => {
      try {
        const response = await fetch(healthUrl, { cache: "no-store" })
        if (cancelled || !response.ok) return
        connectionStatus.reportReady()
        // The veil hid views holding data from before the outage; refetching
        // is what makes lifting it mean anything.
        void queryClient.refetchQueries({ type: "active" })
      } catch {
        // Still down. The interval asks again.
      }
    }

    const timer = setInterval(probe, PROBE_INTERVAL_MS)
    return () => {
      cancelled = true
      clearInterval(timer)
      toast.dismiss(TOAST_ID)
    }
  }, [waiting, queryClient])

  return (
    <>
      <div
        aria-busy={waiting}
        className={
          waiting
            ? "pointer-events-none blur-[2px] saturate-50 transition-[filter] duration-300"
            : "transition-[filter] duration-300"
        }
      >
        {children}
      </div>
      {waiting && (
        <div
          role="status"
          aria-live="polite"
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/40 backdrop-blur-[1px]"
        >
          <span className="sr-only">Đang chờ hệ thống phản hồi</span>
          <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-hidden />
        </div>
      )}
    </>
  )
}
