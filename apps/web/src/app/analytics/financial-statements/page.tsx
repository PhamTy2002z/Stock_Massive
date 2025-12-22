import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import { TopPerformersTable } from "@/components/dashboard/top-performers-table"

export default function TopPerformersPage() {
  return (
    <DashboardLayoutClient>
      <div className="flex flex-col gap-6">
        <div className="flex items-center justify-between">
          <div>
            <h1 className="text-2xl font-bold">Báo Cáo Tài Chính</h1>
            <p className="text-sm text-muted-foreground">
              Top 50 công ty có lợi nhuận cao nhất từ HOSE & HNX (theo quý)
            </p>
          </div>
        </div>
        <TopPerformersTable />
      </div>
    </DashboardLayoutClient>
  )
}
