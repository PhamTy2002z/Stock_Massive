"use client"

import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { VolumeSpikePieChart } from "../volume-spike-pie-chart"
import {
  LazyVolumeSpikeChart,
  LazyVolumeSpikeTreemap,
  LazyVolumeSpikeComposedChart,
} from "../charts-lazy"
import type { IndustryVolumeSpikeGroup } from "@/lib/api"

// Chart cards (bar / pie / treemap / composed) with tab switching
export function SpikeChartTabs({ industries }: { industries: IndustryVolumeSpikeGroup[] }) {
  return (
    <Tabs defaultValue="bar" className="w-full">
      <TabsList className="grid w-full grid-cols-3 md:grid-cols-4 lg:w-auto lg:inline-grid">
        <TabsTrigger value="bar" className="text-xs sm:text-sm">
          Cột ngang
        </TabsTrigger>
        <TabsTrigger value="pie" className="text-xs sm:text-sm">
          Tròn
        </TabsTrigger>
        <TabsTrigger value="treemap" className="text-xs sm:text-sm hidden md:inline-flex">
          Phân cấp
        </TabsTrigger>
        <TabsTrigger value="composed" className="text-xs sm:text-sm">
          KL vs Giá
        </TabsTrigger>
      </TabsList>

      <TabsContent value="bar" className="mt-4">
        <LazyVolumeSpikeChart industries={industries} />
      </TabsContent>

      <TabsContent value="pie" className="mt-4">
        <VolumeSpikePieChart industries={industries} />
      </TabsContent>

      <TabsContent value="treemap" className="mt-4">
        <LazyVolumeSpikeTreemap industries={industries} />
      </TabsContent>

      <TabsContent value="composed" className="mt-4">
        <LazyVolumeSpikeComposedChart industries={industries} />
      </TabsContent>
    </Tabs>
  )
}
