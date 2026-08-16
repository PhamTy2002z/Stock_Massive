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
        "flex gap-2 rounded-md border border-amber-500/40 bg-amber-500/5 px-3 py-2 text-xs text-amber-700 dark:text-amber-400",
        className,
      )}
    >
      <ShieldAlert className="mt-0.5 h-3.5 w-3.5 shrink-0" />
      <div className="min-w-0 space-y-1">
        <p>{notice ? notice.text : MISSING}</p>
        {notice && notice.meanings.length > 0 && (
          <ul className="list-disc space-y-0.5 pl-4 text-amber-700/80 dark:text-amber-400/80">
            {notice.meanings.map((meaning) => (
              <li key={meaning}>{meaning}</li>
            ))}
          </ul>
        )}
      </div>
    </div>
  )
}
