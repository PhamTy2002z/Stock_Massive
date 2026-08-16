import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * A field is a sunken surface, not a bordered hole.
 *
 * The reference fills its inputs one step *below* the panel they sit on and
 * draws a hairline around that — which is why this takes `bg-surface-sunken`
 * rather than the transparent background shadcn ships. On a near-black ground
 * a transparent field is invisible until it is focused.
 */
const Input = React.forwardRef<HTMLInputElement, React.ComponentProps<"input">>(
  ({ className, type, ...props }, ref) => {
    return (
      <input
        type={type}
        className={cn(
          "flex h-9 w-full rounded-[10px] border border-border bg-surface-sunken px-3 py-1 text-control text-foreground transition-colors file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground placeholder:text-muted-foreground focus-visible:border-primary/40 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring/60 disabled:cursor-not-allowed disabled:opacity-50",
          className
        )}
        ref={ref}
        {...props}
      />
    )
  }
)
Input.displayName = "Input"

export { Input }
