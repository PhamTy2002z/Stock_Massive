"use client"

import { fetchIncomeStatement } from "@/lib/api"
import { queryKeys } from "@/lib/query-keys"
import { createFinancialStatementHook } from "./create-financial-statement-hook"

/**
 * Hook for income statement - requires valid symbol.
 * Consumer must validate symbol before rendering.
 */
export const useIncomeStatement = createFinancialStatementHook(
  queryKeys.incomeStatement,
  fetchIncomeStatement
)
