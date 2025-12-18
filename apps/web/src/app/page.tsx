import { DashboardLayout } from "@/components/layout"
import { MarketIndices } from "@/components/dashboard"

export default function Home() {
  return (
    <DashboardLayout>
      <div className="flex flex-col gap-6">
        {/* Market Indices Section */}
        <section>
          <h2 className="text-lg font-semibold text-foreground mb-4">
            Chỉ số thị trường
          </h2>
          <MarketIndices />
        </section>
      </div>
    </DashboardLayout>
  )
}
