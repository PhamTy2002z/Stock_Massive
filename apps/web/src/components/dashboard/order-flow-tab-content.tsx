"use client"

import { RefreshCw, TrendingDown, TrendingUp } from "lucide-react"
import { useIntradayOrderStats } from "@/hooks/use-intraday-order-stats"
import { formatSessionDate } from "@/lib/format"
import { cn } from "@/lib/utils"

interface OrderFlowTabContentProps {
  symbol: string
  className?: string
}

const decimal = (value: number, digits = 1) =>
  value.toLocaleString("vi-VN", { minimumFractionDigits: digits, maximumFractionDigits: digits })

const shares = (value: number) =>
  value >= 1_000_000
    ? `${decimal(value / 1_000_000, 2)}M`
    : `${decimal(value / 1_000, 1)}K`

function Card({ children, className }: { children: React.ReactNode; className?: string }) {
  return (
    <div className={cn("min-w-0 rounded-[18px] border border-border bg-card p-[18px]", className)}>
      {children}
    </div>
  )
}

/** One measure split into its buy and sell halves. */
function Split({
  label,
  buy,
  sell,
  unit,
}: {
  label: string
  buy: number
  sell: number
  unit: (value: number) => string
}) {
  const total = buy + sell
  const buyPct = total > 0 ? (buy / total) * 100 : 50
  const sellPct = 100 - buyPct

  return (
    <div className="mt-4">
      <div className="flex items-baseline justify-between gap-3 text-[13px] leading-[1.43] tracking-[-0.208px]">
        <span className="text-muted-foreground">{label}</span>
        <span className="tabular-nums">
          <span className="text-positive">Mua {decimal(buyPct)}%</span>{" "}
          <span className="text-muted-foreground">vs</span>{" "}
          <span className="text-negative">Bán {decimal(sellPct)}%</span>
        </span>
      </div>
      <div className="mt-2 flex h-2.5 gap-[3px]">
        <span style={{ flex: buy || 1 }} className="rounded-full bg-positive" />
        <span style={{ flex: sell || 1 }} className="rounded-full bg-negative" />
      </div>
      <div className="mt-1.5 text-[13px] leading-[1.43] tracking-[-0.208px] tabular-nums text-muted-foreground">
        {unit(buy)} / {unit(sell)}
      </div>
    </div>
  )
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="flex min-w-0 flex-col gap-0.5">
      <span className="text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
        {label}
      </span>
      <span
        className={cn(
          "text-[17px] font-semibold leading-[1.35] tracking-[-0.374px] tabular-nums",
          tone
        )}
      >
        {value}
      </span>
    </div>
  )
}

/**
 * Who pushed harder today, read two ways: share of matched volume and share of
 * orders. The gap between them is the point — the same volume from fewer orders
 * means bigger tickets behind it, which one bar alone would hide.
 */
export function OrderFlowTabContent({ symbol, className }: OrderFlowTabContentProps) {
  const { data, isLoading, isError, error, refetch, isFetching } = useIntradayOrderStats(symbol)

  if (isLoading) {
    return <div className="h-[420px] animate-pulse rounded-[18px] border border-border bg-card" />
  }

  if (isError || !data) {
    return (
      <Card className={className}>
        <div className="text-[17px] font-semibold leading-[1.24] tracking-[-0.374px]">
          Chưa có dữ liệu dòng lệnh
        </div>
        <p className="mt-1 text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
          {error instanceof Error
            ? error.message
            : `Phiên gần nhất của ${symbol} chưa được thu thập.`}
        </p>
      </Card>
    )
  }

  const buyDominant = data.net_volume >= 0
  const volumeTotal = data.buy_volume + data.sell_volume
  const buyVolumePct = volumeTotal > 0 ? (data.buy_volume / volumeTotal) * 100 : 0
  const orderTotal = data.buy_orders + data.sell_orders
  const buyOrderPct = orderTotal > 0 ? (data.buy_orders / orderTotal) * 100 : 0

  const avgBuySize = data.buy_orders > 0 ? data.buy_volume / data.buy_orders : 0
  const avgSellSize = data.sell_orders > 0 ? data.sell_volume / data.sell_orders : 0
  const sizeGap = avgSellSize > 0 ? ((avgBuySize - avgSellSize) / avgSellSize) * 100 : 0

  const Trend = buyDominant ? TrendingUp : TrendingDown
  const sessionDate = formatSessionDate(data.date ?? undefined)
  const updated = data.last_updated
    ? new Date(data.last_updated).toLocaleTimeString("vi-VN", {
        hour: "2-digit",
        minute: "2-digit",
        second: "2-digit",
      })
    : null

  return (
    <div className={cn("flex min-w-0 flex-col gap-4", className)}>
      {/* The verdict, stated in words before any bar has to be decoded. */}
      <div className="min-w-0 rounded-[18px] bg-[#272729] p-[18px] text-white">
        <div className="flex flex-wrap items-center gap-3">
          <span
            className={cn(
              "flex items-center gap-[7px] rounded-full px-[11px] py-1 text-[13px] font-semibold leading-[1.29] tracking-[-0.208px]",
              buyDominant
                ? "bg-[rgba(55,196,106,0.16)] text-[#37c46a]"
                : "bg-[rgba(255,105,97,0.16)] text-[#ff6961]"
            )}
          >
            <Trend aria-hidden className="size-3.5" />
            {buyDominant ? "Lực mua áp đảo" : "Lực bán áp đảo"}
          </span>
          <span className="text-[13px] leading-[1.43] tracking-[-0.208px] text-[#cccccc]">
            {sessionDate ? `Phiên ${sessionDate}` : "Phiên gần nhất"}
            {updated ? ` · cập nhật ${updated}` : ""}
          </span>
        </div>
        <p className="mt-3 text-pretty text-[17px] leading-[1.5] tracking-[-0.374px]">
          Bên mua chiếm{" "}
          <strong className={cn("font-semibold", buyDominant && "text-[#37c46a]")}>
            {decimal(buyVolumePct)}% khối lượng
          </strong>{" "}
          nhưng <strong className="font-semibold">{decimal(buyOrderPct)}% số lệnh</strong>
          {avgSellSize > 0 && (
            <>
              {" "}
              — mỗi lệnh mua {sizeGap >= 0 ? "lớn hơn" : "nhỏ hơn"} lệnh bán khoảng{" "}
              <strong className="font-semibold">{decimal(Math.abs(sizeGap), 0)}%</strong>
            </>
          )}
          . Khối lượng ròng{" "}
          <strong
            className={cn("font-semibold", buyDominant ? "text-[#37c46a]" : "text-[#ff6961]")}
          >
            {buyDominant ? "+" : "−"}
            {shares(Math.abs(data.net_volume))} CP
          </strong>
          .
        </p>
      </div>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <span className="text-[17px] font-semibold leading-[1.24] tracking-[-0.374px]">
            Mua và bán trên hai thước đo
          </span>
          <button
            type="button"
            onClick={() => void refetch()}
            disabled={isFetching}
            title="Làm mới"
            className="flex size-9 items-center justify-center rounded-full text-interactive transition-[background-color,transform] duration-150 hover:bg-muted active:scale-95 disabled:cursor-progress"
          >
            <RefreshCw className={cn("size-4", isFetching && "animate-spin")} />
            <span className="sr-only">Làm mới dòng lệnh</span>
          </button>
        </div>

        <Split
          label="Theo khối lượng khớp"
          buy={data.buy_volume}
          sell={data.sell_volume}
          unit={(v) => `${shares(v)} CP`}
        />
        <Split
          label="Theo số lệnh"
          buy={data.buy_orders}
          sell={data.sell_orders}
          unit={(v) => `${v.toLocaleString("vi-VN")} lệnh`}
        />

        <div className="mt-[18px] grid grid-cols-[repeat(auto-fit,minmax(150px,1fr))] gap-3.5 border-t border-[hsl(var(--hairline))] pt-4">
          <Stat
            label="Số lệnh mua / bán"
            value={`${data.buy_orders.toLocaleString("vi-VN")} / ${data.sell_orders.toLocaleString("vi-VN")}`}
          />
          <Stat
            label="Quy mô lệnh mua / bán"
            value={`${Math.round(avgBuySize).toLocaleString("vi-VN")} / ${Math.round(avgSellSize).toLocaleString("vi-VN")} CP`}
          />
          <Stat
            label="Khối lượng ròng"
            value={`${buyDominant ? "+" : "−"}${shares(Math.abs(data.net_volume))} CP`}
            tone={buyDominant ? "text-positive" : "text-negative"}
          />
          <Stat
            label="ATO / ATC"
            value={`${shares(data.ato_volume)} / ${shares(data.atc_volume)}`}
          />
        </div>
      </Card>
    </div>
  )
}
