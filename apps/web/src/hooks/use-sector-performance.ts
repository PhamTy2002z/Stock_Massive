"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { fetchSectorPerformance, SectorPerformanceResponse } from "@/lib/api"

const REFRESH_INTERVAL = 5 * 60 * 1000 // 5 minutes

interface UseSectorPerformanceResult {
  data: SectorPerformanceResponse | null
  isLoading: boolean
  error: Error | null
  refetch: () => void
  lastUpdated: Date | null
}

export function useSectorPerformance(): UseSectorPerformanceResult {
  const [data, setData] = useState<SectorPerformanceResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const isMountedRef = useRef(true)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const result = await fetchSectorPerformance()
      if (isMountedRef.current) {
        setData(result)
        setLastUpdated(new Date())
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err : new Error("Failed to fetch sector performance"))
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    isMountedRef.current = true

    // Initial fetch
    fetchData()

    // Set up auto-refresh
    intervalRef.current = setInterval(fetchData, REFRESH_INTERVAL)

    return () => {
      isMountedRef.current = false
      if (intervalRef.current) {
        clearInterval(intervalRef.current)
      }
    }
  }, [fetchData])

  const refetch = useCallback(() => {
    fetchData()
  }, [fetchData])

  return { data, isLoading, error, refetch, lastUpdated }
}
