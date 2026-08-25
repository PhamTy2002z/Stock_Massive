"use client"

import { useEffect, useRef } from "react"

import { BreadthLens } from "@/components/market-monitor/breadth-lens"
import { FlowLens } from "@/components/market-monitor/flow-lens"
import { MonitorNavigation } from "@/components/market-monitor/monitor-navigation"
import { OverviewLens } from "@/components/market-monitor/overview-lens"
import { SectorLens } from "@/components/market-monitor/sector-lens"
import { StocksLens } from "@/components/market-monitor/stocks-lens"
import { MonitorStatusProvider } from "@/components/market-monitor/monitor-status"
import {
  recalledMonitorScroll,
  rememberMonitorScroll,
  monitorScrollKey,
  useMarketMonitorUrlState,
} from "@/lib/market-monitor/url-state"

import { useShell } from "./shell-state"

/** One URL-addressable market workspace; specialist lenses replace one another. */
export function BoardView() {
  const { dispatch } = useShell()
  const url = useMarketMonitorUrlState()
  const scrollRef = useRef<HTMLDivElement>(null)
  const scrollKey = monitorScrollKey(url.state)
  const previousKey = useRef(scrollKey)

  useEffect(() => {
    const scroller = scrollRef.current
    if (!scroller) return
    if (previousKey.current !== scrollKey) {
      previousKey.current = scrollKey
      scroller.scrollTop = recalledMonitorScroll(url.state)
    }
  }, [scrollKey, url.state])

  return (
    <MonitorStatusProvider>
      <div
        className="flex min-h-0 flex-1 flex-col"
        onClick={() => dispatch({ type: "overlay", overlay: null })}
      >
        <MonitorNavigation url={url} />
        <div
          ref={scrollRef}
          onScroll={(event) => rememberMonitorScroll(url.state, event.currentTarget.scrollTop)}
          className="scrollbar-thin min-h-0 flex-1 overflow-y-auto px-3.5 pb-8 pt-[18px] sm:px-5"
        >
          <div className="mx-auto max-w-[1560px] scroll-mt-28">
          {url.state.lens === "overview" ? (
            <OverviewLens url={url} />
          ) : url.state.lens === "breadth" ? (
            <BreadthLens url={url} />
          ) : url.state.lens === "flow" ? (
            <FlowLens url={url} />
          ) : url.state.lens === "sectors" ? (
            <SectorLens url={url} />
          ) : (
            <StocksLens url={url} />
          )}
          </div>
        </div>
      </div>
    </MonitorStatusProvider>
  )
}
