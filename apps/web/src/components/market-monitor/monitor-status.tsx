"use client"

import { createContext, useContext, useEffect, useMemo, useState } from "react"

import type { MonitorMeta } from "@/lib/market-monitor/api"

interface MonitorStatus {
  meta: MonitorMeta | null
  updating: boolean
}

const StatusContext = createContext<{
  status: MonitorStatus
  setStatus: (status: MonitorStatus) => void
} | null>(null)

export function MonitorStatusProvider({ children }: { children: React.ReactNode }) {
  const [status, setStatus] = useState<MonitorStatus>({ meta: null, updating: false })
  const value = useMemo(() => ({ status, setStatus }), [status])
  return <StatusContext.Provider value={value}>{children}</StatusContext.Provider>
}

export function useMonitorStatus(): MonitorStatus {
  return useContext(StatusContext)?.status ?? { meta: null, updating: false }
}

export function useReportMonitorStatus(meta: MonitorMeta | undefined, updating: boolean): void {
  const setStatus = useContext(StatusContext)?.setStatus
  useEffect(() => {
    if (!setStatus) return
    setStatus({ meta: meta ?? null, updating })
    return () => setStatus({ meta: null, updating: false })
  }, [setStatus, meta, updating])
}
