import { DashboardLayoutClient } from "@/components/layout/dashboard-layout-client"
import { SurfaceEmptyState } from "@/components/shared/surface-empty-state"

// The dashboard chrome reads the signed-in user, so this page is per-request.
// Every other dashboard route is dynamic implicitly because it fetches data.
export const dynamic = "force-dynamic"

export default function WorkspacesPage() {
  return (
    <DashboardLayoutClient>
      <SurfaceEmptyState
        question="Bạn muốn mở lại phân tích nào?"
        description="Workspace lưu đúng view, nhóm, filter và khoảng thời gian bạn đang xem, để mở lại hoặc chia sẻ nguyên trạng."
        action={{ label: "Xem Market Map", href: "/" }}
        notYet="Lưu workspace chưa được build. Chưa có gì để mở lại."
      />
    </DashboardLayoutClient>
  )
}
