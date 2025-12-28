"use client"

import { useIsFetching } from "@tanstack/react-query"

/**
 * Global loading indicator that shows a progress bar at the top of the viewport
 * when any React Query is fetching data
 */
export function GlobalLoadingIndicator() {
  const isFetching = useIsFetching()

  if (!isFetching) return null

  return (
    <div className="fixed top-0 left-0 right-0 h-0.5 z-50 overflow-hidden bg-primary/20">
      <div
        className="h-full w-1/3 bg-primary"
        style={{
          animation: "global-loading 1s ease-in-out infinite",
        }}
      />
      <style jsx>{`
        @keyframes global-loading {
          0% {
            transform: translateX(-100%);
          }
          50% {
            transform: translateX(150%);
          }
          100% {
            transform: translateX(400%);
          }
        }
      `}</style>
    </div>
  )
}
