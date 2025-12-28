"use client"

import { useMarketOverview } from "@/hooks/use-market-overview"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"

export function TopMovers() {
  const { data } = useMarketOverview()

  return (
    <Card>
      <CardHeader className="pb-2">
        <CardTitle className="text-base">Top Bien dong</CardTitle>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {/* Gainers */}
          <div>
            <h4 className="text-sm font-medium text-green-500 mb-2">
              Tang manh
            </h4>
            <div className="space-y-1">
              {data.top_gainers.map((item) => (
                <div key={item.symbol} className="flex justify-between text-sm">
                  <span className="font-mono">{item.symbol}</span>
                  <span className="text-green-500">
                    +{item.change_pct.toFixed(2)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
          {/* Losers */}
          <div>
            <h4 className="text-sm font-medium text-red-500 mb-2">
              Giam manh
            </h4>
            <div className="space-y-1">
              {data.top_losers.map((item) => (
                <div key={item.symbol} className="flex justify-between text-sm">
                  <span className="font-mono">{item.symbol}</span>
                  <span className="text-red-500">
                    {item.change_pct.toFixed(2)}%
                  </span>
                </div>
              ))}
            </div>
          </div>
        </div>
      </CardContent>
    </Card>
  )
}
