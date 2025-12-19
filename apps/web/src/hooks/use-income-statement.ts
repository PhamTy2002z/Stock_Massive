"use client"

import { useCallback, useEffect, useRef, useState } from "react"
import {
  fetchIncomeStatement,
  IncomeStatementResponse,
  PeriodType,
} from "@/lib/api"

const SYMBOL_PATTERN = /^[A-Z0-9]{1,10}$/

interface UseIncomeStatementResult {
  data: IncomeStatementResponse | null
  isLoading: boolean
  error: Error | null
  refetch: () => void
}

export function useIncomeStatement(
  symbol: string | null,
  period: PeriodType = "quarter",
  limit: number = 4
): UseIncomeStatementResult {
  const [data, setData] = useState<IncomeStatementResponse | null>(null)
  const [isLoading, setIsLoading] = useState(false)
  const [error, setError] = useState<Error | null>(null)
  const isMountedRef = useRef(true)

  const fetchData = useCallback(
    async (sym: string) => {
      if (!SYMBOL_PATTERN.test(sym)) {
        setError(new Error("Invalid stock symbol format"))
        setData(null)
        return
      }

      setIsLoading(true)
      setError(null)

      try {
        const result = await fetchIncomeStatement(sym, period, limit)
        if (isMountedRef.current) {
          setData(result)
        }
      } catch (err) {
        if (isMountedRef.current) {
          setError(
            err instanceof Error
              ? err
              : new Error("Failed to fetch income statement")
          )
          setData(null)
        }
      } finally {
        if (isMountedRef.current) {
          setIsLoading(false)
        }
      }
    },
    [period, limit]
  )

  useEffect(() => {
    isMountedRef.current = true

    if (!symbol) {
      setData(null)
      return
    }

    const timeoutId = setTimeout(() => {
      fetchData(symbol)
    }, 300)

    return () => {
      clearTimeout(timeoutId)
      isMountedRef.current = false
    }
  }, [symbol, period, limit, fetchData])

  const refetch = useCallback(() => {
    if (symbol) {
      fetchData(symbol)
    }
  }, [symbol, fetchData])

  return { data, isLoading, error, refetch }
}
