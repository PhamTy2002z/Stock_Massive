import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import { SurfaceEmptyState } from "@/components/shared/surface-empty-state"

// The dashboard chrome reads the signed-in user, so this page is per-request.
// Every other dashboard route is dynamic implicitly because it fetches data.
export const dynamic = "force-dynamic"

export default function ComparePage() {
  return (
    <DashboardLayoutClient>
      <SurfaceEmptyState
        question="Mã này đang khác gì so với nhóm của nó?"
        description="Chọn 2-5 mã để so sánh trên cùng khoảng thời gian và cùng đơn vị, cạnh sector và index."
        action={{ label: "Mở Stock 360", href: "/analytics/deep-dive" }}
        notYet="Bảng so sánh nhiều mã chưa được build. Hiện tại hãy bắt đầu từ một mã trong Stock 360."
      />
    </DashboardLayoutClient>
  )
}
