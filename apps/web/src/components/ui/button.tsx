import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"

import { cn } from "@/lib/utils"

/**
 * Buttons, at the reference's own weights.
 *
 * `default` is the one filled control — amber with ink on top, brightened on
 * hover rather than dimmed, because on a near-black ground `bg-primary/90`
 * composites *towards* the page and the control looks like it switched off
 * when you touch it. The design rations this variant to roughly one per view.
 *
 * Everything else is a surface event: `outline` is a hairline over nothing,
 * `ghost` is nothing until hover, and both lift by a few percent of white
 * instead of taking a fill of their own.
 */
const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-[10px] text-control font-medium transition-[background-color,color,filter,border-color] duration-200 focus-visible:outline-none focus-visible:ring-1 focus-visible:ring-ring disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0",
  {
    variants: {
      variant: {
        default: "bg-primary text-primary-foreground hover:brightness-110",
        destructive:
          "bg-destructive text-destructive-foreground hover:brightness-110",
        outline:
          "border border-border bg-transparent text-ink-3 hover:bg-foreground/[0.06] hover:text-foreground",
        secondary:
          "bg-secondary text-secondary-foreground hover:bg-foreground/[0.09]",
        ghost: "text-ink-5 hover:bg-foreground/[0.06] hover:text-foreground",
        link: "text-interactive underline-offset-4 hover:underline",
      },
      size: {
        default: "h-9 px-4 py-2",
        sm: "h-8 px-3 text-micro",
        lg: "h-10 px-8 text-[0.92rem]",
        icon: "h-9 w-9",
        /** The 30px square the reference uses for header and composer icons. */
        "icon-sm": "h-[30px] w-[30px] rounded-lg [&_svg]:size-[17px]",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  asChild?: boolean
}

const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, ...props }, ref) => {
    const Comp = asChild ? Slot : "button"
    return (
      <Comp
        className={cn(buttonVariants({ variant, size, className }))}
        ref={ref}
        {...props}
      />
    )
  }
)
Button.displayName = "Button"

export { Button, buttonVariants }
