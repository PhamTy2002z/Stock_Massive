"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { fetchFundCertificates, FundCertificatesResponse } from "@/lib/api"

const REFRESH_INTERVAL = 5 * 60 * 1000 // 5 minutes

interface UseFundCertificatesResult {
  data: FundCertificatesResponse | null
  isLoading: boolean
  error: Error | null
  refetch: () => void
  lastUpdated: Date | null
}

export function useFundCertificates(fundType?: string): UseFundCertificatesResult {
  const [data, setData] = useState<FundCertificatesResponse | null>(null)
  const [isLoading, setIsLoading] = useState(true)
  const [error, setError] = useState<Error | null>(null)
  const [lastUpdated, setLastUpdated] = useState<Date | null>(null)
  const isMountedRef = useRef(true)
  const intervalRef = useRef<NodeJS.Timeout | null>(null)

  const fetchData = useCallback(async () => {
    setIsLoading(true)
    setError(null)

    try {
      const result = await fetchFundCertificates(fundType)
      if (isMountedRef.current) {
        setData(result)
        setLastUpdated(new Date())
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err : new Error("Failed to fetch fund certificates"))
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false)
      }
    }
  }, [fundType])

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
