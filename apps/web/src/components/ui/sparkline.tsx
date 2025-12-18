"use client"

import * as React from "react"
import { cn } from "@/lib/utils"

interface SparklineProps {
  data: number[]
  width?: number
  height?: number
  strokeWidth?: number
  className?: string
  positive?: boolean
}

export function Sparkline({
  data,
  width = 80,
  height = 32,
  strokeWidth = 1.5,
  className,
  positive = true,
}: SparklineProps) {
  if (!data || data.length < 2) {
    return null
  }

  const min = Math.min(...data)
  const max = Math.max(...data)
  const range = max - min || 1

  // Padding to prevent clipping
  const padding = 2
  const chartWidth = width - padding * 2
  const chartHeight = height - padding * 2

  // Generate SVG path
  const points = data.map((value, index) => {
    const x = padding + (index / (data.length - 1)) * chartWidth
    const y = padding + chartHeight - ((value - min) / range) * chartHeight
    return `${x},${y}`
  })

  const pathD = `M ${points.join(" L ")}`

  // Gradient fill path (area under the line)
  const areaPathD = `${pathD} L ${width - padding},${height - padding} L ${padding},${height - padding} Z`

  const strokeColor = positive ? "#22C55E" : "#EF4444"
  const gradientId = React.useId()

  return (
    <svg
      width={width}
      height={height}
      viewBox={`0 0 ${width} ${height}`}
      className={cn("overflow-visible", className)}
    >
      <defs>
        <linearGradient id={gradientId} x1="0%" y1="0%" x2="0%" y2="100%">
          <stop
            offset="0%"
            stopColor={strokeColor}
            stopOpacity={0.2}
          />
          <stop
            offset="100%"
            stopColor={strokeColor}
            stopOpacity={0}
          />
        </linearGradient>
      </defs>
      {/* Area fill */}
      <path
        d={areaPathD}
        fill={`url(#${gradientId})`}
      />
      {/* Line */}
      <path
        d={pathD}
        fill="none"
        stroke={strokeColor}
        strokeWidth={strokeWidth}
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}
