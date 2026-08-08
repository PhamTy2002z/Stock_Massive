"use client"

import { fetchCashFlow } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { createFinancialStatementHook } from "./create-financial-statement-hook"

/**
 * Hook for cash flow - requires valid symbol.
 * Consumer must validate symbol before rendering.
 */
export const useCashFlow = createFinancialStatementHook(
  queryKeys.cashFlow,
  fetchCashFlow
)
