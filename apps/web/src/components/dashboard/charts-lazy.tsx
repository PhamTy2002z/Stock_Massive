"use client"

import dynamic from "next/dynamic"
import { VolumeSpikeChartSkeleton } from "./volume-spike-chart"
import { VolumeSpikeTreemapSkeleton } from "./volume-spike-treemap"
import { VolumeSpikeComposedChartSkeleton } from "./volume-spike-composed-chart"

// Lazy load VolumeSpikeChart (contains Recharts BarChart)
export const LazyVolumeSpikeChart = dynamic(
  () => import("./volume-spike-chart").then((mod) => mod.VolumeSpikeChart),
  {
    ssr: false,
    loading: () => <VolumeSpikeChartSkeleton />,
  }
)

// Lazy load VolumeSpikeTreemap (contains Recharts Treemap)
export const LazyVolumeSpikeTreemap = dynamic(
  () => import("./volume-spike-treemap").then((mod) => mod.VolumeSpikeTreemap),
  {
    ssr: false,
    loading: () => <VolumeSpikeTreemapSkeleton />,
  }
)

// Lazy load VolumeSpikeComposedChart (contains Recharts ComposedChart)
export const LazyVolumeSpikeComposedChart = dynamic(
  () => import("./volume-spike-composed-chart").then((mod) => mod.VolumeSpikeComposedChart),
  {
    ssr: false,
    loading: () => <VolumeSpikeComposedChartSkeleton />,
  }
)
