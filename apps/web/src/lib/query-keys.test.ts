import { describe, expect, it } from "vitest"
import { queryKeys } from "./query-keys"

describe("queryKeys", () => {
  it("scopes per-stock keys under the stock prefix so symbol invalidation works", () => {
    const prefix = queryKeys.stock("VCB")
    const perStock = [
      queryKeys.stockDetail("VCB"),
      queryKeys.incomeStatement("VCB", "quarter", 8),
      queryKeys.balanceSheet("VCB", "year", 5),
      queryKeys.cashFlow("VCB", "quarter", 8),
      queryKeys.foreignSnapshot("VCB"),
      queryKeys.intradayOrderStats("VCB"),
      queryKeys.healthScore("VCB"),
    ]

    for (const key of perStock) {
      expect(key.slice(0, prefix.length)).toEqual(prefix)
    }
  })

  it("keeps distinct suffixes per financial statement", () => {
    expect(queryKeys.incomeStatement("VCB", "quarter", 8)).toEqual(["stock", "VCB", "income", "quarter", 8])
    expect(queryKeys.balanceSheet("VCB", "quarter", 8)).toEqual(["stock", "VCB", "balance", "quarter", 8])
    expect(queryKeys.cashFlow("VCB", "quarter", 8)).toEqual(["stock", "VCB", "cashFlow", "quarter", 8])
  })

  it("varies the key with every parameter", () => {
    expect(queryKeys.incomeStatement("VCB", "quarter", 8)).not.toEqual(
      queryKeys.incomeStatement("VCB", "year", 8),
    )
    expect(queryKeys.volumeAnalysis("VCB", 20)).not.toEqual(queryKeys.volumeAnalysis("VCB", 60))
    expect(queryKeys.stockSearch("vcb", 20)).not.toEqual(queryKeys.stockSearch("vcb", 10))
  })

  it("keeps global keys out of the stock namespace", () => {
    expect(queryKeys.jobsStatus).toEqual(["jobs", "status"])
    expect(queryKeys.marketIndices).toEqual(["market", "indices"])
  })
})
