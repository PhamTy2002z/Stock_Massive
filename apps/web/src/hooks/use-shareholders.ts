"use client"

import { useState, useEffect, useCallback } from "react"
import { ShareholdersResponse, fetchShareholders } from "@/lib/api"

interface UseShareholdersResult {
  data: ShareholdersResponse | null
  isLoading: boolean
  error: Error | null
  refetch: () => void
}

export function useShareholders(symbol: string | null): UseShareholdersResult {
  const [data, setData] = useState<ShareholdersResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)

  const fetchData = useCallback(async () => {
    if (!symbol) {
      setData(null)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const result = await fetchShareholders(symbol)
      setData(result)
    } catch (err) {
      setError(err instanceof Error ? err : new Error("Failed to fetch shareholders"))
      setData(null)
    } finally {
      setIsLoading(false)
    }
  }, [symbol])

  useEffect(() => {
    const timeoutId = setTimeout(() => {
      fetchData()
    }, 300) // Debounce

    return () => clearTimeout(timeoutId)
  }, [fetchData])

  return { data, isLoading, error, refetch: fetchData }
}
