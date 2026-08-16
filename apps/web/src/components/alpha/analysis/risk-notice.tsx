/**
 * The Risk Notice the Analysis artifact carries, and why it is written here.
 *
 * An Analysis is one of the things this artifact must carry (`docs/specs/0002`
 * §5), and a notice the model was asked to write is a notice the model can
 * forget, hedge or paraphrase away — so it is the renderer's, exactly as it is
 * for an assistant message.
 *
 * **It is not in the payload.** The stored Analysis is `audit`, `evidence`,
 * `judgment` and `citedFieldIds` (spec 0003 §8.6–§8.9): the pipeline owns the
 * evidence, not the rendering contract. The message path gets its notice from
 * `assemble_message`, and there is no equivalent hook on a nightly artifact, so
 * the surface supplies it.
 *
 * A second copy of a sentence is a second sentence as soon as one is edited, so
 * `risk-notice.test.ts` reads `apps/api/src/agent/manifest.py` and refuses to
 * pass if this text or this version drifts from the backend's. One place, kept
 * one place by a test rather than by memory.
 */

"use client"

import { ShieldAlert } from "lucide-react"

import { cn } from "@/lib/utils"
import { CHROME } from "./copy"

export const RISK_NOTICE_VERSION = "1.0.0"

export const RISK_NOTICE_TEXT =
  "Nội dung này phục vụ phân tích và tham khảo, không phải tư vấn đầu tư cá " +
  "nhân hay cam kết lợi nhuận. Dữ liệu có thể chậm, thiếu hoặc thay đổi; bạn " +
  "tự chịu trách nhiệm cho quyết định của mình."

/**
 * The Risk Notice, rendered by the renderer.
 *
 * Unconditional: there is no prop and no branch that can omit it. Both
 * treatments mount it, because an Analysis carries one in both — a notice the
 * reader only meets after expanding is a notice most readers never meet.
 */
export function ArtifactRiskNotice({ className }: { className?: string }) {
  return (
    <div
      role="note"
      aria-label={CHROME.riskNotice}
      className={cn(
        "flex gap-2 rounded-md border border-caution/40 bg-caution/5 px-2 py-1.5 text-[11px] text-caution",
        className,
      )}
    >
      <ShieldAlert className="mt-0.5 h-3 w-3 shrink-0" />
      <p>{RISK_NOTICE_TEXT}</p>
    </div>
  )
}
