"use client"

import { useMarketOverview } from "@/hooks/use-market-overview"
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card"
import { cn } from "@/lib/utils"

function formatBillion(value: number): string {
  const billions = value / 1e9
  return `${billions >= 0 ? "+" : ""}${billions.toFixed(1)} ty`
}

export function ForeignFlow() {
  const { data } = useMarketOverview()
  const { net_buy, net_sell, total_net_value } = data.foreign_flow

  return (
    <Card>
      <CardHeader className="pb-2">
        <div className="flex justify-between items-center">
          <CardTitle className="text-base">Giao dich NDNN</CardTitle>
          <span
            className={cn(
              "text-sm font-medium",
              total_net_value >= 0 ? "text-green-500" : "text-red-500"
            )}
          >
            Net: {formatBillion(total_net_value)}
          </span>
        </div>
      </CardHeader>
      <CardContent>
        <div className="grid grid-cols-2 gap-4">
          {/* Net Buy */}
          <div>
            <h4 className="text-sm font-medium text-green-500 mb-2">
              Mua rong
            </h4>
            <div className="space-y-1">
              {net_buy.slice(0, 5).map((item) => (
                <div key={item.symbol} className="flex justify-between text-sm">
                  <span className="font-mono">{item.symbol}</span>
                  <span className="text-green-500">
                    {formatBillion(item.net_value)}
                  </span>
                </div>
              ))}
            </div>
          </div>
          {/* Net Sell */}
          <div>
            <h4 className="text-sm font-medium text-red-500 mb-2">Ban rong</h4>
            <div className="space-y-1">
              {net_sell.slice(0, 5).map((item) => (
                <div key={item.symbol} className="flex justify-between text-sm">
                  <span className="font-mono">{item.symbol}</span>
                  <span className="text-red-500">
                    {formatBillion(Math.abs(item.net_value))}
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
