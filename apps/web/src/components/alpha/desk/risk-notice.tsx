"use client"

import { ShieldAlert } from "lucide-react"

import type { RiskNotice } from "@/lib/alpha-desk/types"
import { cn } from "@/lib/utils"

/**
 * The Risk Notice, rendered by the renderer.
 *
 * It is attached by the backend to every completed and usefully incomplete
 * assistant message, and it is displayed as its own element for one reason: a
 * notice the model was asked to write is a notice the model can forget, hedge
 * or paraphrase away. **Model prose cannot satisfy this** (`docs/specs/0002`
 * §11.6), so the component takes the stored value and shows it.
 *
 * The fallback is deliberately the renderer's own voice rather than a copy of
 * the canonical text. A stored message with no notice reached the transcript
 * through some path that bypassed `assemble_message`, and printing the real
 * wording there would claim the backend attached something it did not.
 *
 * `notice.meanings` is not rendered. It carries the four `RiskMeaning` enum
 * values (`apps/api/src/agent/manifest.py`) that a *translation* is checked
 * against, so that verifying a locale needs a set comparison rather than a
 * reader. They are machine labels — `analytical_purpose`, `no_personal_advice`
 * — and showing them puts identifiers on screen under a notice whose whole job
 * is to be read.
 */
const MISSING =
  "Chưa đọc được Risk Notice cho câu trả lời này. Nội dung không phải khuyến nghị đầu tư."

export function RiskNoticePanel({
  notice,
  className,
}: {
  notice: RiskNotice | null
  className?: string
}) {
  return (
    <div
      role="note"
      aria-label="Risk notice"
      className={cn(
        "flex gap-2 rounded-card border border-caution/35 bg-caution/[0.06] px-3.5 py-2.5 text-meta text-caution",
        className,
      )}
    >
      <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <div className="min-w-0">
        <p>{notice ? notice.text : MISSING}</p>
      </div>
    </div>
  )
}
