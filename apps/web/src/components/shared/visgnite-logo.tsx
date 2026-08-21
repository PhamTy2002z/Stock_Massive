import { cn } from "@/lib/utils"

/**
 * The VisgniteAI mark.
 *
 * A bolt cut from a 31.5 × 48.5 box, filled with the reference's own metallic
 * ramp and notched twice in flat white so the shape still reads at 13px in the
 * sidebar. It is monochrome by design: the one chromatic thing in this system
 * is the amber, and the brand mark is deliberately not it.
 *
 * The gradient id is fixed rather than generated. Every instance paints the
 * identical ramp, so two marks on one page resolving to the same `<defs>` is
 * the correct outcome — and a fixed id keeps this a server component, which a
 * `useId` would not.
 */
export function VisgniteMark({ className }: { className?: string }) {
  return (
    <svg
      viewBox="0 0 31.5 48.5"
      aria-hidden="true"
      className={cn("block shrink-0", className)}
    >
      <defs>
        <linearGradient
          id="visgnite-mark-ramp"
          gradientUnits="userSpaceOnUse"
          x1="8"
          y1="0"
          x2="34.1"
          y2="28.9"
        >
          <stop offset="0" stopColor="#9e9e9e" />
          <stop offset=".28" stopColor="#a6a6a6" />
          <stop offset=".34" stopColor="#a3a3a3" />
          <stop offset=".40" stopColor="#3a3a3a" />
          <stop offset=".55" stopColor="#414141" />
          <stop offset=".60" stopColor="#7a7a7a" />
          <stop offset=".68" stopColor="#8e8e8e" />
          <stop offset=".80" stopColor="#a9a9a9" />
          <stop offset=".95" stopColor="#c4c4c4" />
          <stop offset="1" stopColor="#cccccc" />
        </linearGradient>
      </defs>
      <path
        d="M21.5 0 L21.5 19.5 L31.5 19.5 L31.5 29 L10 48.5 L10 28.5 L0.5 28.5 L0.5 18.5 Z"
        fill="url(#visgnite-mark-ramp)"
      />
      <rect x="0.5" y="18.5" width="9" height="10" fill="#fdfdfd" />
      <rect x="22" y="19.5" width="9.5" height="9.5" fill="#fdfdfd" />
    </svg>
  )
}

/**
 * Mark plus wordmark, at the proportions the reference uses in the sidebar
 * head: a 13 × 20 mark, half an em of gap, and the name at 1.02rem with the
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
      <VisgniteMark className="h-5 w-[13px]" />
      VisgniteAI
    </span>
  )
}
