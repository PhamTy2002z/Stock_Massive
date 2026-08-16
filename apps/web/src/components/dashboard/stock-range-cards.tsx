"use client"

import { RangeTrack as SharedRangeTrack } from "@/components/charts"
import { cn } from "@/lib/utils"

interface StockRangeCardsProps {
  price: number | null
  openPrice: number | null
  lowPrice: number | null
  highPrice: number | null
  low52Week: number | null
  high52Week: number | null
  volume: number | null
  /** Million VND, the unit /detail reports it in. */
  tradingValue: number | null
  avgVolume52Week: number | null
  className?: string
}

const decimal = (value: number, digits = 1) =>
  value.toLocaleString("vi-VN", {
    minimumFractionDigits: digits,
    maximumFractionDigits: digits,
  })

const whole = (value: number) => value.toLocaleString("vi-VN", { maximumFractionDigits: 0 })

/** Shares in millions, the unit the board itself quotes. */
function formatShares(value: number): string {
  if (value >= 1_000_000) return `${decimal(value / 1_000_000, 2)}M`
  if (value >= 1_000) return `${decimal(value / 1_000, 1)}K`
  return whole(value)
}

/** Trading value arrives in triệu đồng; traders read it in tỷ. */
function formatValue(valueInMillions: number): string {
  const billions = valueInMillions / 1_000
  if (billions >= 1_000) return `${decimal(billions / 1_000, 2)} nghìn tỷ`
  return `${whole(billions)} tỷ`
}

/** Where `value` sits inside [low, high], clamped so a stale quote can't overflow the track. */
function positionPct(value: number, low: number, high: number): number | null {
  if (!Number.isFinite(low) || !Number.isFinite(high) || high <= low) return null
  return Math.min(100, Math.max(0, ((value - low) / (high - low)) * 100))
}

function Card({
  title,
  children,
  className,
}: {
  title: string
  children: React.ReactNode
  className?: string
}) {
  return (
    <div className={cn("min-w-0 rounded-[18px] border border-border bg-card p-[18px]", className)}>
      <div className="text-[13px] font-semibold leading-[1.29] tracking-[-0.208px] text-muted-foreground">
        {title}
      </div>
      {children}
    </div>
  )
}

/**
 * Track with the current value marked against its low–high bounds.
 *
 * The drawing moved to `@/components/charts` so the Widget registry can reuse
 * it with a palette of its own (ADR-0012). The colours this card has always
 * used stay here, which is why it still renders exactly as it did.
 */
function RangeTrack({ percent }: { percent: number }) {
  return (
    <SharedRangeTrack
      percent={percent}
      className="mt-2.5"
      fillColor="hsl(var(--border))"
      trackColor="hsl(var(--hairline))"
      markerColor="hsl(var(--interactive))"
      markerRingColor="hsl(var(--card))"
    />
  )
}

function Caption({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-2.5 text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
      {children}
    </div>
  )
}

function Unavailable({ children }: { children: React.ReactNode }) {
  return (
    <div className="mt-2.5 text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
      {children}
    </div>
  )
}

/**
 * The three range readings that open the overview: where the price sits in the
 * session, where the session sits in the year, and whether today's liquidity is
 * normal. Each answers its question with a position on a track rather than a
 * number the reader has to compare in their head.
 */
export function StockRangeCards({
  price,
  openPrice,
  lowPrice,
  highPrice,
  low52Week,
  high52Week,
  volume,
  tradingValue,
  avgVolume52Week,
  className,
}: StockRangeCardsProps) {
  const sessionPct =
    price !== null && lowPrice !== null && highPrice !== null
      ? positionPct(price, lowPrice, highPrice)
      : null
  const sessionSwing =
    lowPrice !== null && highPrice !== null && lowPrice > 0
      ? ((highPrice - lowPrice) / lowPrice) * 100
      : null

  const yearPct =
    price !== null && low52Week !== null && high52Week !== null
      ? positionPct(price, low52Week, high52Week)
      : null
  const belowHigh =
    price !== null && high52Week !== null && high52Week > 0
      ? ((high52Week - price) / high52Week) * 100
      : null

  const volumeVsAvg =
    volume !== null && avgVolume52Week !== null && avgVolume52Week > 0
      ? (volume / avgVolume52Week) * 100
      : null

  return (
    <div
      className={cn(
        "grid min-w-0 grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-4",
        className
      )}
    >
      <Card title="Biên độ trong phiên">
        {sessionPct === null ? (
          <Unavailable>Chưa có giá thấp/cao của phiên</Unavailable>
        ) : (
          <>
            <div className="mt-2.5 flex items-baseline justify-between gap-3 text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums">
              <span className="text-negative">{whole(lowPrice as number)}</span>
              {openPrice !== null && (
                <span className="text-[13px] text-muted-foreground">
                  Mở cửa {whole(openPrice)}
                </span>
              )}
              <span className="text-positive">{whole(highPrice as number)}</span>
            </div>
            <RangeTrack percent={sessionPct} />
            {sessionSwing !== null && (
              <Caption>
                Dao động {decimal(sessionSwing, 2)}%
                {sessionPct >= 80
                  ? " · đóng gần đỉnh phiên"
                  : sessionPct <= 20
                    ? " · đóng gần đáy phiên"
                    : ""}
              </Caption>
            )}
          </>
        )}
      </Card>

      <Card title="Vùng giá 52 tuần">
        {yearPct === null ? (
          <Unavailable>Chưa có vùng giá 52 tuần</Unavailable>
        ) : (
          <>
            <div className="mt-2.5 flex items-baseline justify-between gap-3 text-[15px] leading-[1.47] tracking-[-0.374px] tabular-nums">
              <span>{whole(low52Week as number)}</span>
              <span className="text-[13px] text-muted-foreground">
                Hiện tại {whole(price as number)}
              </span>
              <span>{whole(high52Week as number)}</span>
            </div>
            <RangeTrack percent={yearPct} />
            {belowHigh !== null && (
              <Caption>Thấp hơn đỉnh 52T {decimal(belowHigh, 1)}%</Caption>
            )}
          </>
        )}
      </Card>

      <Card title="Thanh khoản phiên">
        {volume === null ? (
          <Unavailable>Chưa có khối lượng khớp</Unavailable>
        ) : (
          <>
            <div className="mt-2 flex items-baseline gap-2">
              <span className="text-2xl font-semibold leading-[1.2] tracking-[-0.374px] tabular-nums">
                {formatShares(volume)}
              </span>
              <span className="text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
                cổ phiếu{tradingValue !== null ? ` · ${formatValue(tradingValue)}` : ""}
              </span>
            </div>
            {volumeVsAvg !== null && (
              <>
                {/* Filled share of the 52-week average, capped so an unusually
                    heavy session still reads as "full bar plus a number". */}
                <div className="mt-3 flex h-1.5 gap-[3px]">
                  <span
                    style={{ flex: Math.min(100, volumeVsAvg) }}
                    className="rounded-full bg-interactive"
                  />
                  <span
                    style={{ flex: Math.max(0, 100 - volumeVsAvg) }}
                    className="rounded-full bg-[hsl(var(--hairline))]"
                  />
                </div>
                <Caption>
                  Bằng {decimal(volumeVsAvg, 0)}% khối lượng bình quân 52T (
                  {formatShares(avgVolume52Week as number)})
                </Caption>
              </>
            )}
          </>
        )}
      </Card>
    </div>
  )
}

export function StockRangeCardsSkeleton({ className }: { className?: string }) {
  return (
    <div
      className={cn(
        "grid min-w-0 grid-cols-[repeat(auto-fit,minmax(240px,1fr))] gap-4",
        className
      )}
    >
      {[0, 1, 2].map((i) => (
        <div
          key={i}
          className="h-[132px] animate-pulse rounded-[18px] border border-border bg-card"
        />
      ))}
    </div>
  )
}
