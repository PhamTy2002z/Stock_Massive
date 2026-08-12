"use client"

/**
 * PROTOTYPE — throwaway. Issue #21.
 *
 * The thread the artifact lives inside. Shared by every variant on purpose:
 * the transcript is the *context* being judged against, not the design under
 * test. Only the artifact slot changes between variants.
 *
 * Deliberately real about the surroundings: a user turn above, a streamed
 * assistant sentence introducing the artifact, and a follow-up turn below — so
 * a variant that eats the whole viewport is visibly a problem rather than an
 * abstraction.
 */

import type { AnalysisArtifact } from "./fixtures"

export function ThreadShell({
  artifact,
  children,
}: {
  artifact: AnalysisArtifact
  children: React.ReactNode
}) {
  return (
    <div className="flex h-full min-h-0 flex-col">
      <div className="min-h-0 flex-1 overflow-auto">
        <div className="mx-auto w-full max-w-[52rem] px-6 py-8">
          <div className="mb-2 text-[11px] font-medium uppercase tracking-wider text-muted-foreground">
            Thread · {artifact.symbol} · phiên {artifact.tradingDay}
          </div>

          <UserTurn>Phân tích {artifact.symbol} hôm nay giúp tôi.</UserTurn>

          <AssistantText>
            Đây là bản Analysis của <strong>{artifact.symbol}</strong> cho phiên{" "}
            {artifact.tradingDay}, chạy tự động sau khi có Snapshot EOD.
          </AssistantText>

          {/* The artifact slot. Variants own everything inside, including width. */}
          <div className="my-4">{children}</div>

          <AssistantText>
            Bạn muốn tôi so trục nào với các mã cùng ngành trong Watchlist không?
          </AssistantText>

          <UserTurn>Cho tôi xem dòng ngoại 30 phiên của mã này.</UserTurn>

          <AssistantText muted>
            <span className="inline-flex items-center gap-2">
              <span className="h-1.5 w-1.5 animate-pulse rounded-full bg-primary" />
              đang gọi <code className="text-[11px]">foreign_flow_pressure</code>…
            </span>
          </AssistantText>
        </div>
      </div>

      <div className="shrink-0 border-t border-border bg-card px-6 py-3">
        <div className="mx-auto flex w-full max-w-[52rem] items-center gap-2 rounded-lg border border-input px-3 py-2">
          <span className="flex-1 text-sm text-muted-foreground">
            Hỏi tiếp về {artifact.symbol}…
          </span>
          <span className="rounded-md bg-primary px-2.5 py-1 text-xs font-semibold text-primary-foreground">
            Gửi
          </span>
        </div>
      </div>
    </div>
  )
}

function UserTurn({ children }: { children: React.ReactNode }) {
  return (
    <div className="mb-4 flex justify-end">
      <div className="max-w-[80%] rounded-2xl rounded-br-md bg-secondary px-3.5 py-2 text-sm text-foreground">
        {children}
      </div>
    </div>
  )
}

function AssistantText({
  children,
  muted,
}: {
  children: React.ReactNode
  muted?: boolean
}) {
  return (
    <div
      className={`mb-4 text-sm leading-relaxed ${
        muted ? "text-muted-foreground" : "text-foreground"
      }`}
    >
      {children}
    </div>
  )
}
