"use client"

import { fetchBalanceSheet } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { createFinancialStatementHook } from "./create-financial-statement-hook"

/**
 * Hook for balance sheet - requires valid symbol.
 * Consumer must validate symbol before rendering.
 */
export const useBalanceSheet = createFinancialStatementHook(
  queryKeys.balanceSheet,
  fetchBalanceSheet
)
