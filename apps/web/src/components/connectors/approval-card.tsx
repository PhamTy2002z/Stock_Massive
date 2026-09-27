"use client"

import { useEffect, useId, useState } from "react"
import { ShieldQuestion } from "lucide-react"

import { AlphaRefusalError } from "@/lib/alpha"
import { answerApproval } from "@/lib/alpha-desk/api"
import type { ApprovalDecision, ApprovalRequest } from "@/lib/alpha-desk/types"
import { refusalMessage } from "@/lib/connectors/copy"
import { cn } from "@/lib/utils"

const DECISION_LABEL: Record<ApprovalDecision, string> = {
  allow_once: "Cho phép một lần",
  always: "Luôn cho phép",
  deny: "Từ chối",
}

/** Every card the running Turn is waiting on, oldest first. */
export function ApprovalCards({
  turnId,
  approvals,
}: {
  turnId: string
  approvals: ApprovalRequest[]
}) {
  if (approvals.length === 0) return null
  return (
    <div className="grid gap-2.5">
      {approvals.map((request) => (
        <ApprovalCard key={request.call_id} turnId={turnId} request={request} />
      ))}
    </div>
  )
}

/**
 * One connector call the Turn is holding until the reader answers.
 *
 * **The card leaves on `approval.resolved`, not on the press.** The POST only
 * hands the answer over; the stream says what became of it (including a
 * timeout or a connector switched off meanwhile), so after a press the buttons
 * go inert and the card says it is waiting rather than vanishing early.
 *
 * No button is the filled accent: nudging the reader toward "allow" is the one
 * thing an approval prompt must not do.
 */
export function ApprovalCard({ turnId, request }: { turnId: string; request: ApprovalRequest }) {
  const titleId = useId()
  const [sent, setSent] = useState<ApprovalDecision | null>(null)
  const [problem, setProblem] = useState<string | null>(null)
  const remaining = useSecondsLeft(request.expires_at)
  const expired = remaining !== null && remaining <= 0
  const inert = sent !== null || expired

  async function decide(decision: ApprovalDecision) {
    setSent(decision)
    setProblem(null)
    try {
      await answerApproval(turnId, request.call_id, decision)
    } catch (error) {
      if (error instanceof AlphaRefusalError && error.status === 404) {
        // Nothing waits any more; the stream's `approval.resolved` removes the card.
        setProblem("Yêu cầu này không còn chờ nữa.")
        return
      }
      setSent(null)
      setProblem(refusalMessage(error))
    }
  }

  const write = request.effect === "write"

  return (
    <section
      aria-labelledby={titleId}
      className="grid gap-2.5 rounded-card border border-border bg-surface-raised px-3.5 py-3"
    >
      <div className="flex items-start gap-2.5">
        <ShieldQuestion className="mt-0.5 size-4 shrink-0 text-ink-4" strokeWidth={1.7} aria-hidden />
        <div className="min-w-0 flex-1">
          <p id={titleId} className="text-row leading-[1.45] text-foreground">
            {request.connector || "Kết nối"} muốn chạy{" "}
            <span className="font-medium">{request.display}</span>
          </p>
          <p className="mt-0.5 flex flex-wrap items-center gap-x-2 text-meta text-ink-6">
            <span
              className={cn(
                "rounded-md border px-1.5 py-px text-micro font-medium",
                write ? "border-caution/45 text-caution" : "border-border text-ink-4",
              )}
            >
              {write ? "Ghi dữ liệu" : "Chỉ đọc"}
            </span>
            {remaining !== null && (
              <span>
                {expired ? "Đã hết hạn chờ" : <>Tự từ chối sau <span className="font-mono tabular-nums">{clock(remaining)}</span></>}
              </span>
            )}
          </p>
        </div>
      </div>

      {request.arguments_preview && (
        <pre
          aria-label="Tham số của lệnh gọi"
          className="scrollbar-thin max-h-[7.5rem] overflow-auto whitespace-pre-wrap break-all rounded-lg border border-hairline bg-surface-sunken px-2.5 py-2 font-mono text-micro leading-[1.5] text-ink-3"
        >
          {request.arguments_preview}
        </pre>
      )}

      <div className="flex flex-wrap gap-2">
        <DecisionButton disabled={inert} onClick={() => decide("allow_once")}>
          {DECISION_LABEL.allow_once}
        </DecisionButton>
        {request.can_always && (
          <DecisionButton disabled={inert} onClick={() => decide("always")}>
            {DECISION_LABEL.always}
          </DecisionButton>
        )}
        <DecisionButton disabled={inert} onClick={() => decide("deny")} quiet>
          {DECISION_LABEL.deny}
        </DecisionButton>
      </div>

      <p aria-live="polite" className="text-meta text-ink-5 empty:hidden">
        {problem ?? (sent ? `Đã chọn “${DECISION_LABEL[sent]}”. Đang chờ xác nhận…` : "")}
      </p>
    </section>
  )
}

function DecisionButton({
  children,
  onClick,
  disabled,
  quiet = false,
}: {
  children: string
  onClick: () => void
  disabled: boolean
  quiet?: boolean
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      className={cn(
        "h-8 rounded-[10px] px-3 text-control outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50",
        quiet
          ? "text-ink-4 hover:bg-foreground/[0.06] hover:text-foreground"
          : "border border-border text-ink-2 hover:bg-foreground/[0.06] hover:text-foreground",
      )}
    >
      {children}
    </button>
  )
}

/** Whole seconds until `expiresAt`, ticking once a second; null when there is no deadline. */
function useSecondsLeft(expiresAt: string | null): number | null {
  const deadline = expiresAt ? Date.parse(expiresAt) : Number.NaN
  const [now, setNow] = useState(() => Date.now())
  useEffect(() => {
    if (Number.isNaN(deadline)) return
    const timer = setInterval(() => setNow(Date.now()), 1000)
    return () => clearInterval(timer)
  }, [deadline])
  if (Number.isNaN(deadline)) return null
  return Math.max(0, Math.ceil((deadline - now) / 1000))
}

function clock(seconds: number): string {
  const minutes = Math.floor(seconds / 60)
  return `${minutes}:${String(seconds % 60).padStart(2, "0")}`
}
