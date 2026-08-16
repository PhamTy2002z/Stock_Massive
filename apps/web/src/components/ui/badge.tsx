import * as React from "react"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Badges are labels, not controls.
 *
 * The reference writes them at 0.74rem inside a 6px hairline box — the source
 * chips after a paragraph, the exchange tag beside a ticker. `default` is the
 * only filled one and it stays rare: a teal fill reads as an action, so a
 * badge that merely states a fact takes `outline` or `secondary`.
 */
const badgeVariants = cva(
  "inline-flex items-center gap-1 rounded-md border px-2 py-[0.1em] text-micro font-medium transition-colors focus:outline-none focus:ring-1 focus:ring-ring",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground hover:brightness-110",
        secondary:
          "border-transparent bg-foreground/[0.06] text-ink-4",
        destructive:
          "border-transparent bg-destructive text-destructive-foreground hover:brightness-110",
        outline: "border-border text-ink-4",
        /** A rising or falling figure, tinted rather than filled. */
        positive: "border-transparent bg-positive/[0.12] text-positive",
        negative: "border-transparent bg-negative/[0.12] text-negative",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

export interface BadgeProps
  extends React.HTMLAttributes<HTMLDivElement>,
    VariantProps<typeof badgeVariants> {}

function Badge({ className, variant, ...props }: BadgeProps) {
  return (
    <div className={cn(badgeVariants({ variant }), className)} {...props} />
  )
}

export { Badge, badgeVariants }
