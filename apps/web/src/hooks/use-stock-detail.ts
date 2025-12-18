"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import { fetchStockDetail, StockDetail } from "@/lib/api"

// Valid stock symbol pattern: 1-10 uppercase letters/numbers
const SYMBOL_PATTERN = /^[A-Z0-9]{1,10}$/

interface UseStockDetailResult {
  data: StockDetail | null
  isLoading: boolean
  error: Error | null
  refetch: () => void
}

export function useStockDetail(symbol: string | null): UseStockDetailResult {
  const [data, setData] = useState<StockDetail | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const isMountedRef = useRef(true)

  const fetchData = useCallback(async (sym: string) => {
    // Validate symbol format
    if (!SYMBOL_PATTERN.test(sym)) {
      setError(new Error("Invalid stock symbol format"))
      setData(null)
      return
    }

    setIsLoading(true)
    setError(null)

    try {
      const result = await fetchStockDetail(sym)
      if (isMountedRef.current) {
        setData(result)
      }
    } catch (err) {
      if (isMountedRef.current) {
        setError(err instanceof Error ? err : new Error("Failed to fetch stock detail"))
        setData(null)
      }
    } finally {
      if (isMountedRef.current) {
        setIsLoading(false)
      }
    }
  }, [])

  useEffect(() => {
    isMountedRef.current = true

    if (!symbol) {
      setData(null)
      return
    }

    // Debounce: wait 300ms before fetching
    const timeoutId = setTimeout(() => {
      fetchData(symbol)
    }, 300)

    return () => {
      clearTimeout(timeoutId)
      isMountedRef.current = false
    }
  }, [symbol, fetchData])

  const refetch = useCallback(() => {
    if (symbol) {
      fetchData(symbol)
    }
  }, [symbol, fetchData])

  return { data, isLoading, error, refetch }
}
