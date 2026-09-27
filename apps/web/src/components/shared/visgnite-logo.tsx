import { cn } from "@/lib/utils"

/**
 * The VisgniteAI mark.
 *
 * "Vis" and "ignite" in one letter: the left stroke of a V in a quiet tone, the
 * right stroke a lightning bolt in the ink colour, meeting at one point. Both
 * follow `currentColor` (the stroke at half strength), so the mark reads on
 * the night and day themes alike and still says "V" at favicon size. It is
 * monochrome by design: the one chromatic thing in this system is the amber,
 * and the brand mark is deliberately not it.
 */
export function VisgniteMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="6 9 36 32"
      aria-hidden="true"
      className={cn("block shrink-0", className)}
    >
      <path
        d="M6 9 H15 L24.5 33 L21 41 Z"
        fill="currentColor"
        fillOpacity={0.5}
      />
      <path
        d="M33 9 H42 L34 24 H38.5 L21 41 L27 28 H22.5 Z"
        fill="currentColor"
      />
    </svg>
  )
}

/**
 * Mark plus wordmark, at the proportions the reference uses in the sidebar
 * head: a 22 × 20 mark, half an em of gap, and the name at 1.02rem with the
 * tracking pulled in.
 */
export function VisgniteWordmark({ className }: { className?: string }) {
  return (
    <span
      className={cn(
        "inline-flex items-center gap-[0.5em] text-[1.02rem] font-medium leading-none tracking-[-0.015em]",
        className
      )}
    >
      <VisgniteMark className="h-5 w-[22px]" />
      VisgniteAI
    </span>
  )
}
