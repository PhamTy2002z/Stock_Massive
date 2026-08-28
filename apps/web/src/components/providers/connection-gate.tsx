"use client"

import { useQueryClient } from "@tanstack/react-query"
import { Loader2 } from "lucide-react"
import { useEffect, useState, useSyncExternalStore } from "react"
import { toast } from "sonner"

import { FailureState } from "@/components/ui/failure-state"
import { getApiBaseUrl } from "@/lib/api"
import { connectionStatus, healthUrlFrom } from "@/lib/connection-status"
import { describeFailure } from "@/lib/failure"

/** How often to ask whether the API is back. Restarts take a second or two. */
const PROBE_INTERVAL_MS = 3000
/**
 * How long a wait may stay wordless before it owes the reader an explanation.
 *
 * A restart is over in a second or two, and narrating that would be noise. Past
 * twenty seconds it is no longer a blip: the spinner has become a screen with
 * no exit, and "it is still trying" is information the reader needs in order to
 * decide whether to keep waiting or go and check their own connection.
 */
const PROLONGED_AFTER_MS = 20_000
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
 * when the probe finds the API answering the stale views refetch in place. A
 * successful application request then lifts the veil; `/health` alone cannot
 * prove that the endpoint which originally failed has recovered.
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
  const waiting = state === "waiting"
  const [prolonged, setProlonged] = useState(false)

  useEffect(() => {
    if (!waiting) {
      setProlonged(false)
      return
    }
    const timer = setTimeout(() => setProlonged(true), PROLONGED_AFTER_MS)
    return () => clearTimeout(timer)
  }, [waiting])

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
        // The health endpoint can be healthy while an application endpoint is
        // still rate-limited or failing. Let a successful retried request call
        // reportReady() so the waiting veil cannot flicker every probe cycle.
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
          className="fixed inset-0 z-50 flex items-center justify-center bg-background/40 px-6 backdrop-blur-[1px]"
        >
          {prolonged ? (
            // The probe keeps running underneath this — the veil still lifts by
            // itself the moment the API answers. What changes is that the
            // reader is no longer looking at an unlabelled spinner with nothing
            // to press.
            <div className="max-w-[34rem] rounded-card border border-hairline bg-surface-raised px-5 py-4">
              <FailureState
                failure={describeFailure(new TypeError("offline"))}
                density="region"
                onRetry={() => void queryClient.refetchQueries({ type: "active" })}
                className="py-0"
              />
            </div>
          ) : (
            <>
              <span className="sr-only">Đang chờ hệ thống phản hồi</span>
              <Loader2 className="h-6 w-6 animate-spin text-muted-foreground" aria-hidden />
            </>
          )}
        </div>
      )}
    </>
  )
}
