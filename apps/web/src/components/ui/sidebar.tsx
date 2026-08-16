"use client"

import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva, type VariantProps } from "class-variance-authority"
import { PanelLeft } from "lucide-react"

import { useIsMobile } from "@/hooks/use-mobile"
import { cn } from "@/lib/utils"
import { Button } from "@/components/ui/button"
import { Input } from "@/components/ui/input"
import { Separator } from "@/components/ui/separator"
import {
  Sheet,
  SheetContent,
  SheetDescription,
  SheetHeader,
  SheetTitle,
} from "@/components/ui/sheet"
import { Skeleton } from "@/components/ui/skeleton"
import {
  Tooltip,
  TooltipContent,
  TooltipProvider,
  TooltipTrigger,
} from "@/components/ui/tooltip"

const SIDEBAR_COOKIE_NAME = "sidebar_state"
const SIDEBAR_COOKIE_MAX_AGE = 60 * 60 * 24 * 7
// 274px expanded / 60px rail — the VisgniteAI reference draws its sidebar at
// 274px, which is what the watchlist rows and the chat titles are laid out for.
const SIDEBAR_WIDTH = "17.125rem"
const SIDEBAR_WIDTH_MOBILE = "18rem"
const SIDEBAR_WIDTH_ICON = "3.75rem"
// How far down the viewport the sidebar starts. Layouts that put a full-width
// bar above the sidebar override --sidebar-top with its height.
const SIDEBAR_TOP = "0rem"
const SIDEBAR_KEYBOARD_SHORTCUT = "b"
// Opening reflows the content beside the rail, so it still waits for hover
// intent — but the intent is read from approaching the rail, not from landing on
// it, so the panel is already moving by the time the cursor reaches an icon.
// A cursor that crosses the zone faster than the delay cancels on the way out.
// Closing stays immediate — leaving is always deliberate.
const SIDEBAR_PEEK_IN_DELAY = 70
const SIDEBAR_PEEK_OUT_DELAY = 0
// How far outside the rail counts as approaching it, in px.
const SIDEBAR_PEEK_APPROACH = 32

type SidebarMode = "rail" | "pinned"

type SidebarContextProps = {
  state: "expanded" | "collapsed"
  mode: SidebarMode
  isPeeking: boolean
  open: boolean
  setOpen: (open: boolean) => void
  openMobile: boolean
  setOpenMobile: (open: boolean) => void
  isMobile: boolean
  canHover: boolean
  toggleSidebar: () => void
  schedulePeek: (next: boolean) => void
  startPeek: () => void
  endPeek: () => void
}

const SidebarContext = React.createContext<SidebarContextProps | null>(null)

function useSidebar() {
  const context = React.useContext(SidebarContext)
  if (!context) {
    throw new Error("useSidebar must be used within a SidebarProvider.")
  }

  return context
}

const SidebarProvider = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div"> & {
    defaultOpen?: boolean
    open?: boolean
    onOpenChange?: (open: boolean) => void
  }
>(
  (
    {
      defaultOpen = true,
      open: openProp,
      onOpenChange: setOpenProp,
      className,
      style,
      children,
      ...props
    },
    ref
  ) => {
    const isMobile = useIsMobile()
    const [openMobile, setOpenMobile] = React.useState(false)

    // This is the internal state of the sidebar.
    // We use openProp and setOpenProp for control from outside the component.
    const [_open, _setOpen] = React.useState(defaultOpen)
    const open = openProp ?? _open
    const setOpen = React.useCallback(
      (value: boolean | ((value: boolean) => boolean)) => {
        const openState = typeof value === "function" ? value(open) : value
        if (setOpenProp) {
          setOpenProp(openState)
        } else {
          _setOpen(openState)
        }

        // Only the pinned/rail choice is persisted. Peek is transient by design.
        document.cookie = `${SIDEBAR_COOKIE_NAME}=${
          openState ? "pinned" : "rail"
        }; path=/; max-age=${SIDEBAR_COOKIE_MAX_AGE}`
      },
      [setOpenProp, open]
    )

    // Transient hover/focus expansion. Never persisted, never pushes layout.
    const [isPeeking, setIsPeeking] = React.useState(false)
    const peekTimerRef = React.useRef<ReturnType<typeof setTimeout> | null>(null)
    // What the pending timer is about to set. A repeated request for the same
    // target must not restart the countdown, or a pointer that keeps moving
    // inside the approach zone would push the opening back on every event and
    // the panel would only open once the cursor stopped.
    const pendingPeekRef = React.useRef<boolean | null>(null)
    const pointerDownRef = React.useRef(false)
    const [canHover, setCanHover] = React.useState(false)

    const clearPeekTimer = React.useCallback(() => {
      if (peekTimerRef.current) {
        clearTimeout(peekTimerRef.current)
        peekTimerRef.current = null
      }
      pendingPeekRef.current = null
    }, [])

    // Hover-expand is a pointer affordance only. Touch devices tap the rail.
    React.useEffect(() => {
      const mql = window.matchMedia("(hover: hover) and (pointer: fine)")
      const update = () => setCanHover(mql.matches)
      update()
      mql.addEventListener("change", update)
      return () => mql.removeEventListener("change", update)
    }, [])

    // A held pointer button means the user is dragging or brushing a chart range.
    // Expanding mid-gesture is the worst failure mode of this pattern, so suppress it.
    React.useEffect(() => {
      const onDown = () => {
        pointerDownRef.current = true
        clearPeekTimer()
      }
      const onUp = () => {
        pointerDownRef.current = false
      }

      window.addEventListener("pointerdown", onDown, true)
      window.addEventListener("pointerup", onUp, true)
      window.addEventListener("pointercancel", onUp, true)
      return () => {
        window.removeEventListener("pointerdown", onDown, true)
        window.removeEventListener("pointerup", onUp, true)
        window.removeEventListener("pointercancel", onUp, true)
      }
    }, [clearPeekTimer])

    React.useEffect(() => clearPeekTimer, [clearPeekTimer])

    const schedulePeek = React.useCallback(
      (next: boolean) => {
        if (peekTimerRef.current && pendingPeekRef.current === next) return
        clearPeekTimer()
        if (next && (!canHover || pointerDownRef.current)) return

        const delay = next ? SIDEBAR_PEEK_IN_DELAY : SIDEBAR_PEEK_OUT_DELAY
        // A zero delay must not go through setTimeout: deferring a tick is the
        // difference between "attached to the cursor" and "slightly late".
        if (delay === 0) {
          setIsPeeking(next)
          return
        }

        pendingPeekRef.current = next
        peekTimerRef.current = setTimeout(() => {
          peekTimerRef.current = null
          pendingPeekRef.current = null
          setIsPeeking(next)
        }, delay)
      },
      [canHover, clearPeekTimer]
    )

    // Keyboard focus expands immediately — a delay there reads as an unresponsive app.
    const startPeek = React.useCallback(() => {
      clearPeekTimer()
      setIsPeeking(true)
    }, [clearPeekTimer])

    const endPeek = React.useCallback(() => {
      clearPeekTimer()
      setIsPeeking(false)
    }, [clearPeekTimer])

    // Opens the mobile sheet. Desktop has no pin control, so there is nothing to
    // toggle there — hover drives the rail, and a shortcut that silently pinned
    // the sidebar open would leave no visible way back.
    const toggleSidebar = React.useCallback(() => {
      if (!isMobile) return
      setOpenMobile((open) => !open)
    }, [isMobile, setOpenMobile])

    // Adds a keyboard shortcut to toggle the sidebar.
    React.useEffect(() => {
      const handleKeyDown = (event: KeyboardEvent) => {
        if (
          event.key === SIDEBAR_KEYBOARD_SHORTCUT &&
          (event.metaKey || event.ctrlKey)
        ) {
          event.preventDefault()
          toggleSidebar()
        }
      }

      window.addEventListener("keydown", handleKeyDown)
      return () => window.removeEventListener("keydown", handleKeyDown)
    }, [toggleSidebar])

    // Escape collapses a peeked panel without touching the pinned preference.
    React.useEffect(() => {
      if (!isPeeking) return
      const handleEscape = (event: KeyboardEvent) => {
        if (event.key === "Escape") endPeek()
      }
      window.addEventListener("keydown", handleEscape)
      return () => window.removeEventListener("keydown", handleEscape)
    }, [isPeeking, endPeek])

    const mode: SidebarMode = open ? "pinned" : "rail"

    // We add a state so that we can do data-state="expanded" or "collapsed".
    // This makes it easier to style the sidebar with Tailwind classes.
    // A peeked rail counts as expanded so labels fade in inside the overlay.
    const state = open || isPeeking ? "expanded" : "collapsed"

    const contextValue = React.useMemo<SidebarContextProps>(
      () => ({
        state,
        mode,
        isPeeking,
        open,
        setOpen,
        isMobile,
        canHover,
        openMobile,
        setOpenMobile,
        toggleSidebar,
        schedulePeek,
        startPeek,
        endPeek,
      }),
      [
        state,
        mode,
        isPeeking,
        open,
        setOpen,
        isMobile,
        canHover,
        openMobile,
        setOpenMobile,
        toggleSidebar,
        schedulePeek,
        startPeek,
        endPeek,
      ]
    )

    return (
      <SidebarContext.Provider value={contextValue}>
        <TooltipProvider delayDuration={0}>
          <div
            data-sidebar-state={state}
            style={
              {
                "--sidebar-width": SIDEBAR_WIDTH,
                "--sidebar-width-icon": SIDEBAR_WIDTH_ICON,
                "--sidebar-top": SIDEBAR_TOP,
                ...style,
              } as React.CSSProperties
            }
            className={cn(
              "group/sidebar-wrapper flex min-h-svh w-full has-[[data-variant=inset]]:bg-sidebar",
              className
            )}
            ref={ref}
            {...props}
          >
            {children}
          </div>
        </TooltipProvider>
      </SidebarContext.Provider>
    )
  }
)
SidebarProvider.displayName = "SidebarProvider"

const Sidebar = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div"> & {
    side?: "left" | "right"
    variant?: "sidebar" | "floating" | "inset"
    collapsible?: "offcanvas" | "icon" | "none"
  }
>(
  (
    {
      side = "left",
      variant = "sidebar",
      collapsible = "offcanvas",
      className,
      children,
      ...props
    },
    ref
  ) => {
    const {
      isMobile,
      state,
      mode,
      isPeeking,
      openMobile,
      setOpenMobile,
      schedulePeek,
      startPeek,
      endPeek,
    } = useSidebar()

    // Hover-expand only makes sense for the icon rail. Pinned and offcanvas opt out.
    const peekEnabled = collapsible === "icon" && mode === "rail"

    const panelRef = React.useRef<HTMLDivElement | null>(null)
    const insideApproachRef = React.useRef(false)

    // Reading intent from the pointer rather than from the panel's own
    // mouseenter buys the animation a head start: crossing into the band beside
    // the rail already schedules the open, so the width is settling as the
    // cursor arrives. A pointer listener does this without an overlay element,
    // which would otherwise sit over the content and swallow clicks along the
    // rail's edge. It runs only while collapsed and bails on the first
    // coordinate check, so the cost outside the band is one comparison.
    React.useEffect(() => {
      if (!peekEnabled || isPeeking) return

      insideApproachRef.current = false

      const handlePointerMove = (event: PointerEvent) => {
        const panel = panelRef.current
        if (!panel) return

        const rect = panel.getBoundingClientRect()
        const withinBand =
          event.clientY >= rect.top &&
          event.clientY <= rect.bottom &&
          (side === "left"
            ? event.clientX <= rect.right + SIDEBAR_PEEK_APPROACH
            : event.clientX >= rect.left - SIDEBAR_PEEK_APPROACH)

        if (withinBand === insideApproachRef.current) return
        insideApproachRef.current = withinBand
        // Leaving the band before the delay elapses cancels the pending open,
        // so a cursor merely passing by never moves the layout.
        if (withinBand) schedulePeek(true)
        else endPeek()
      }

      window.addEventListener("pointermove", handlePointerMove, { passive: true })
      return () =>
        window.removeEventListener("pointermove", handlePointerMove)
    }, [peekEnabled, isPeeking, side, schedulePeek, endPeek])

    const handleMouseEnter = React.useCallback(() => {
      if (peekEnabled) schedulePeek(true)
    }, [peekEnabled, schedulePeek])

    const handleMouseLeave = React.useCallback(() => {
      if (peekEnabled) schedulePeek(false)
    }, [peekEnabled, schedulePeek])

    const handleFocusCapture = React.useCallback(() => {
      if (peekEnabled) startPeek()
    }, [peekEnabled, startPeek])

    const handleBlurCapture = React.useCallback(
      (event: React.FocusEvent<HTMLDivElement>) => {
        if (!peekEnabled) return
        // Ignore focus moves that stay inside the panel.
        if (event.currentTarget.contains(event.relatedTarget as Node | null)) return
        endPeek()
      },
      [peekEnabled, endPeek]
    )

    if (collapsible === "none") {
      return (
        <div
          className={cn(
            "flex h-full w-[--sidebar-width] flex-col bg-sidebar text-sidebar-foreground",
            className
          )}
          ref={ref}
          {...props}
        >
          {children}
        </div>
      )
    }

    if (isMobile) {
      return (
        <Sheet open={openMobile} onOpenChange={setOpenMobile} {...props}>
          <SheetContent
            data-sidebar="sidebar"
            data-mobile="true"
            className="w-[--sidebar-width] bg-sidebar p-0 text-sidebar-foreground [&>button]:hidden"
            style={
              {
                "--sidebar-width": SIDEBAR_WIDTH_MOBILE,
              } as React.CSSProperties
            }
            side={side}
          >
            <SheetHeader className="sr-only">
              <SheetTitle>Sidebar</SheetTitle>
              <SheetDescription>Displays the mobile sidebar.</SheetDescription>
            </SheetHeader>
            <div className="flex h-full w-full flex-col">{children}</div>
          </SheetContent>
        </Sheet>
      )
    }

    return (
      <div
        ref={ref}
        className={cn(
          "group peer hidden text-sidebar-foreground md:block",
          "shrink-0 transition-[width] duration-[220ms] ease-sidebar will-change-[width]",
          // Width tracks the peek as well as the mode, so hovering the rail
          // reflows the content beside it instead of floating over it.
          mode === "pinned" || isPeeking
            ? "w-[--sidebar-width]"
            : "w-[--sidebar-width-icon]",
          collapsible === "offcanvas" && mode === "rail" && "w-0"
        )}
        data-state={state}
        data-mode={mode}
        data-peek={isPeeking ? "true" : "false"}
        data-collapsible={state === "collapsed" ? collapsible : ""}
        data-variant={variant}
        data-side={side}
      >
        {/* This is what handles the sidebar gap on desktop */}
        <div
          className={cn(
            "relative h-[calc(100svh-var(--sidebar-top))] w-full bg-transparent",
            "group-data-[side=right]:rotate-180"
          )}
        />
        <div
          ref={panelRef}
          onMouseEnter={handleMouseEnter}
          onMouseLeave={handleMouseLeave}
          onFocusCapture={handleFocusCapture}
          onBlurCapture={handleBlurCapture}
          className={cn(
            "fixed bottom-0 top-[--sidebar-top] hidden md:flex flex-col",
            "transition-[left,right,width] duration-[220ms] ease-sidebar will-change-[width,left,right]",
            "overflow-hidden",
            // Peek opens to the full sidebar width — same as pinned, and the
            // spacer above matches it so the two animate as one edge.
            mode === "pinned" || isPeeking
              ? "w-[--sidebar-width]"
              : "w-[--sidebar-width-icon]",
            // The panel now pushes rather than floats, so it needs no elevation
            // over the content — only over the page background.
            "z-10",
            side === "left"
              ? cn(
                  "left-0",
                  collapsible === "offcanvas" && mode === "rail" && "left-[calc(var(--sidebar-width)*-1)]"
                )
              : cn(
                  "right-0",
                  collapsible === "offcanvas" && mode === "rail" && "right-[calc(var(--sidebar-width)*-1)]"
                ),
            // Adjust the padding for floating and inset variants.
            variant === "floating" || variant === "inset"
              ? cn(
                  "p-2",
                  state === "collapsed" && collapsible === "icon" && "w-[calc(var(--sidebar-width-icon)_+_theme(spacing.4)_+2px)]"
                )
              : cn(
                  "group-data-[side=left]:border-r group-data-[side=right]:border-l"
                ),
            className
          )}
          {...props}
        >
          <div
            data-sidebar="sidebar"
            className="flex h-full w-full flex-col bg-sidebar transform-gpu group-data-[variant=floating]:rounded-lg group-data-[variant=floating]:border group-data-[variant=floating]:border-sidebar-border group-data-[variant=floating]:shadow"
          >
            {children}
          </div>
        </div>
      </div>
    )
  }
)
Sidebar.displayName = "Sidebar"

const SidebarTrigger = React.forwardRef<
  React.ElementRef<typeof Button>,
  React.ComponentProps<typeof Button>
>(({ className, onClick, ...props }, ref) => {
  const { toggleSidebar } = useSidebar()

  return (
    <Button
      ref={ref}
      data-sidebar="trigger"
      variant="ghost"
      size="icon"
      className={cn("h-7 w-7", className)}
      onClick={(event) => {
        onClick?.(event)
        toggleSidebar()
      }}
      {...props}
    >
      <PanelLeft />
      <span className="sr-only">Toggle Sidebar</span>
    </Button>
  )
})
SidebarTrigger.displayName = "SidebarTrigger"

const SidebarRail = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<"button">
>(({ className, ...props }, ref) => {
  const { toggleSidebar } = useSidebar()

  return (
    <button
      ref={ref}
      data-sidebar="rail"
      aria-label="Toggle Sidebar"
      tabIndex={-1}
      onClick={toggleSidebar}
      title="Toggle Sidebar"
      className={cn(
        "absolute inset-y-0 z-20 hidden w-4 -translate-x-1/2 transition-all ease-linear after:absolute after:inset-y-0 after:left-1/2 after:w-[2px] hover:after:bg-sidebar-border group-data-[side=left]:-right-4 group-data-[side=right]:left-0 sm:flex",
        "[[data-side=left]_&]:cursor-w-resize [[data-side=right]_&]:cursor-e-resize",
        "[[data-side=left][data-state=collapsed]_&]:cursor-e-resize [[data-side=right][data-state=collapsed]_&]:cursor-w-resize",
        "group-data-[collapsible=offcanvas]:translate-x-0 group-data-[collapsible=offcanvas]:after:left-full group-data-[collapsible=offcanvas]:hover:bg-sidebar",
        "[[data-side=left][data-collapsible=offcanvas]_&]:-right-2",
        "[[data-side=right][data-collapsible=offcanvas]_&]:-left-2",
        className
      )}
      {...props}
    />
  )
})
SidebarRail.displayName = "SidebarRail"

const SidebarInset = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"main">
>(({ className, ...props }, ref) => {
  return (
    <main
      ref={ref}
      className={cn(
        "relative flex min-h-[calc(100svh-var(--sidebar-top))] flex-1 flex-col bg-background overflow-hidden",
        // Inset variant specific styles
        "peer-data-[variant=inset]:min-h-[calc(100svh-theme(spacing.4))] md:peer-data-[variant=inset]:m-2 md:peer-data-[state=collapsed]:peer-data-[variant=inset]:ml-2 md:peer-data-[variant=inset]:ml-0 md:peer-data-[variant=inset]:rounded-xl md:peer-data-[variant=inset]:shadow",
        className
      )}
      {...props}
    />
  )
})
SidebarInset.displayName = "SidebarInset"

const SidebarInput = React.forwardRef<
  React.ElementRef<typeof Input>,
  React.ComponentProps<typeof Input>
>(({ className, ...props }, ref) => {
  return (
    <Input
      ref={ref}
      data-sidebar="input"
      className={cn(
        "h-8 w-full bg-background shadow-none focus-visible:ring-2 focus-visible:ring-sidebar-ring",
        className
      )}
      {...props}
    />
  )
})
SidebarInput.displayName = "SidebarInput"

const SidebarHeader = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div">
>(({ className, ...props }, ref) => {
  return (
    <div
      ref={ref}
      data-sidebar="header"
      className={cn("flex flex-col gap-2 px-[10px] pb-2.5 pt-4 group-data-[collapsible=icon]:px-2", className)}
      {...props}
    />
  )
})
SidebarHeader.displayName = "SidebarHeader"

const SidebarFooter = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div">
>(({ className, ...props }, ref) => {
  return (
    <div
      ref={ref}
      data-sidebar="footer"
      className={cn("flex flex-col gap-2 border-t border-sidebar-border p-2 group-data-[collapsible=icon]:p-1", className)}
      {...props}
    />
  )
})
SidebarFooter.displayName = "SidebarFooter"

const SidebarSeparator = React.forwardRef<
  React.ElementRef<typeof Separator>,
  React.ComponentProps<typeof Separator>
>(({ className, ...props }, ref) => {
  return (
    <Separator
      ref={ref}
      data-sidebar="separator"
      className={cn("mx-2 w-auto bg-sidebar-border", className)}
      {...props}
    />
  )
})
SidebarSeparator.displayName = "SidebarSeparator"

const SidebarContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div">
>(({ className, ...props }, ref) => {
  return (
    <div
      ref={ref}
      data-sidebar="content"
      className={cn(
        "flex min-h-0 flex-1 flex-col gap-2 overflow-auto group-data-[collapsible=icon]:overflow-hidden",
        className
      )}
      {...props}
    />
  )
})
SidebarContent.displayName = "SidebarContent"

const SidebarGroup = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div">
>(({ className, ...props }, ref) => {
  return (
    <div
      ref={ref}
      data-sidebar="group"
      className={cn("relative flex w-full min-w-0 flex-col p-2", className)}
      {...props}
    />
  )
})
SidebarGroup.displayName = "SidebarGroup"

const SidebarGroupLabel = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div"> & { asChild?: boolean }
>(({ className, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "div"

  return (
    <Comp
      ref={ref}
      data-sidebar="group-label"
      className={cn(
        "flex h-8 shrink-0 items-center rounded-md px-2 text-xs font-medium text-sidebar-foreground/70 outline-none ring-sidebar-ring transition-[margin,opacity] duration-200 ease-linear focus-visible:ring-2 [&>svg]:size-4 [&>svg]:shrink-0",
        "group-data-[collapsible=icon]:-mt-8 group-data-[collapsible=icon]:opacity-0",
        className
      )}
      {...props}
    />
  )
})
SidebarGroupLabel.displayName = "SidebarGroupLabel"

const SidebarGroupAction = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<"button"> & { asChild?: boolean }
>(({ className, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"

  return (
    <Comp
      ref={ref}
      data-sidebar="group-action"
      className={cn(
        "absolute right-3 top-3.5 flex aspect-square w-5 items-center justify-center rounded-md p-0 text-sidebar-foreground outline-none ring-sidebar-ring transition-[opacity,transform] duration-100 ease-sidebar hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 [&>svg]:size-4 [&>svg]:shrink-0",
        // Increases the hit area of the button on mobile.
        "after:absolute after:-inset-2 after:md:hidden",
        "group-data-[collapsible=icon]:opacity-0 group-data-[collapsible=icon]:scale-95 group-data-[collapsible=icon]:pointer-events-none",
        className
      )}
      {...props}
    />
  )
})
SidebarGroupAction.displayName = "SidebarGroupAction"

const SidebarGroupContent = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div">
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    data-sidebar="group-content"
    className={cn("w-full text-sm", className)}
    {...props}
  />
))
SidebarGroupContent.displayName = "SidebarGroupContent"

const SidebarMenu = React.forwardRef<
  HTMLUListElement,
  React.ComponentProps<"ul">
>(({ className, ...props }, ref) => (
  <ul
    ref={ref}
    data-sidebar="menu"
    className={cn("flex w-full min-w-0 flex-col gap-1", className)}
    {...props}
  />
))
SidebarMenu.displayName = "SidebarMenu"

const SidebarMenuItem = React.forwardRef<
  HTMLLIElement,
  React.ComponentProps<"li">
>(({ className, ...props }, ref) => (
  <li
    ref={ref}
    data-sidebar="menu-item"
    className={cn("group/menu-item relative", className)}
    {...props}
  />
))
SidebarMenuItem.displayName = "SidebarMenuItem"

const sidebarMenuButtonVariants = cva(
  "peer/menu-button flex w-full items-center gap-[0.7rem] overflow-hidden rounded-lg px-[0.6rem] py-[0.55rem] text-left text-row outline-none ring-sidebar-ring transition-all duration-[180ms] ease-sidebar hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 active:bg-sidebar-accent active:text-sidebar-accent-foreground disabled:pointer-events-none disabled:opacity-50 group-has-[[data-sidebar=menu-action]]/menu-item:pr-8 aria-disabled:pointer-events-none aria-disabled:opacity-50 data-[active=true]:bg-sidebar-accent data-[active=true]:font-medium data-[active=true]:text-sidebar-accent-foreground data-[state=open]:hover:bg-sidebar-accent data-[state=open]:hover:text-sidebar-accent-foreground [&>span:last-child]:truncate [&>svg]:size-[17px] [&>svg]:shrink-0 [&>svg]:transition-transform [&>svg]:duration-200",
  {
    variants: {
      variant: {
        default: "hover:bg-sidebar-accent hover:text-sidebar-accent-foreground",
        outline:
          "bg-background shadow-[0_0_0_1px_hsl(var(--sidebar-border))] hover:bg-sidebar-accent hover:text-sidebar-accent-foreground hover:shadow-[0_0_0_1px_hsl(var(--sidebar-accent))]",
      },
      size: {
        default: "min-h-9 text-row group-data-[collapsible=icon]:!size-9 group-data-[collapsible=icon]:!p-2",
        sm: "h-7 text-xs group-data-[collapsible=icon]:!size-7 group-data-[collapsible=icon]:!p-1.5",
        lg: "h-12 text-sm group-data-[collapsible=icon]:!size-10 group-data-[collapsible=icon]:!p-1 group-data-[collapsible=icon]:justify-center",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

const SidebarMenuButton = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<"button"> & {
    asChild?: boolean
    isActive?: boolean
    tooltip?: string | React.ComponentProps<typeof TooltipContent>
  } & VariantProps<typeof sidebarMenuButtonVariants>
>(
  (
    {
      asChild = false,
      isActive = false,
      variant = "default",
      size = "default",
      tooltip,
      className,
      ...props
    },
    ref
  ) => {
    const Comp = asChild ? Slot : "button"
    const { isMobile, state, mode, canHover } = useSidebar()

    const button = (
      <Comp
        ref={ref}
        data-sidebar="menu-button"
        data-size={size}
        data-active={isActive}
        className={cn(sidebarMenuButtonVariants({ variant, size }), className)}
        {...props}
      />
    )

    // On a hover-capable rail the same mouseenter that would open the tooltip
    // also starts the peek. The tooltip wins the race by its zero delay, so it
    // paints for the ~120ms before the panel opens and then disappears — read as
    // a flash, not a label. The expanded panel shows the real text anyway.
    const railPeeksOnHover = canHover && mode === "rail"

    if (!tooltip || railPeeksOnHover) {
      return button
    }

    if (typeof tooltip === "string") {
      tooltip = {
        children: tooltip,
      }
    }

    return (
      <Tooltip>
        <TooltipTrigger asChild>{button}</TooltipTrigger>
        <TooltipContent
          side="right"
          align="center"
          hidden={state !== "collapsed" || isMobile}
          {...tooltip}
        />
      </Tooltip>
    )
  }
)
SidebarMenuButton.displayName = "SidebarMenuButton"

const SidebarMenuAction = React.forwardRef<
  HTMLButtonElement,
  React.ComponentProps<"button"> & {
    asChild?: boolean
    showOnHover?: boolean
  }
>(({ className, asChild = false, showOnHover = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"

  return (
    <Comp
      ref={ref}
      data-sidebar="menu-action"
      className={cn(
        "absolute right-1 top-1.5 flex aspect-square w-5 items-center justify-center rounded-md p-0 text-sidebar-foreground outline-none ring-sidebar-ring transition-[opacity,transform] duration-100 ease-sidebar hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 peer-hover/menu-button:text-sidebar-accent-foreground [&>svg]:size-4 [&>svg]:shrink-0",
        // Increases the hit area of the button on mobile.
        "after:absolute after:-inset-2 after:md:hidden",
        "peer-data-[size=sm]/menu-button:top-1",
        "peer-data-[size=default]/menu-button:top-1.5",
        "peer-data-[size=lg]/menu-button:top-2.5",
        "group-data-[collapsible=icon]:opacity-0 group-data-[collapsible=icon]:scale-95 group-data-[collapsible=icon]:pointer-events-none",
        showOnHover &&
          "group-focus-within/menu-item:opacity-100 group-hover/menu-item:opacity-100 data-[state=open]:opacity-100 peer-data-[active=true]/menu-button:text-sidebar-accent-foreground md:opacity-0",
        className
      )}
      {...props}
    />
  )
})
SidebarMenuAction.displayName = "SidebarMenuAction"

const SidebarMenuBadge = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div">
>(({ className, ...props }, ref) => (
  <div
    ref={ref}
    data-sidebar="menu-badge"
    className={cn(
      "pointer-events-none absolute right-1 flex h-5 min-w-5 select-none items-center justify-center rounded-md px-1 text-xs font-medium tabular-nums text-sidebar-foreground transition-[opacity,transform] duration-100 ease-sidebar",
      "peer-hover/menu-button:text-sidebar-accent-foreground peer-data-[active=true]/menu-button:text-sidebar-accent-foreground",
      "peer-data-[size=sm]/menu-button:top-1",
      "peer-data-[size=default]/menu-button:top-1.5",
      "peer-data-[size=lg]/menu-button:top-2.5",
      "group-data-[collapsible=icon]:opacity-0 group-data-[collapsible=icon]:scale-95",
      className
    )}
    {...props}
  />
))
SidebarMenuBadge.displayName = "SidebarMenuBadge"

// Fixed widths to avoid hydration mismatch from Math.random()
const SKELETON_WIDTHS = ["60%", "75%", "50%", "85%", "70%"]

const SidebarMenuSkeleton = React.forwardRef<
  HTMLDivElement,
  React.ComponentProps<"div"> & {
    showIcon?: boolean
    index?: number
  }
>(({ className, showIcon = false, index = 0, ...props }, ref) => {
  // Use deterministic width based on index to avoid hydration mismatch
  const width = SKELETON_WIDTHS[index % SKELETON_WIDTHS.length]

  return (
    <div
      ref={ref}
      data-sidebar="menu-skeleton"
      className={cn("flex h-8 items-center gap-2 rounded-md px-2", className)}
      {...props}
    >
      {showIcon && (
        <Skeleton
          className="size-4 rounded-md"
          data-sidebar="menu-skeleton-icon"
        />
      )}
      <Skeleton
        className="h-4 max-w-[--skeleton-width] flex-1"
        data-sidebar="menu-skeleton-text"
        style={
          {
            "--skeleton-width": width,
          } as React.CSSProperties
        }
      />
    </div>
  )
})
SidebarMenuSkeleton.displayName = "SidebarMenuSkeleton"

const SidebarMenuSub = React.forwardRef<
  HTMLUListElement,
  React.ComponentProps<"ul">
>(({ className, ...props }, ref) => (
  <ul
    ref={ref}
    data-sidebar="menu-sub"
    className={cn(
      "mx-3.5 flex min-w-0 translate-x-px flex-col gap-1 border-l border-sidebar-border px-2.5 py-0.5",
      "transition-[opacity,max-height,transform] duration-100 ease-sidebar origin-top",
      "group-data-[collapsible=icon]:opacity-0 group-data-[collapsible=icon]:max-h-0 group-data-[collapsible=icon]:scale-y-0 group-data-[collapsible=icon]:pointer-events-none",
      className
    )}
    {...props}
  />
))
SidebarMenuSub.displayName = "SidebarMenuSub"

const SidebarMenuSubItem = React.forwardRef<
  HTMLLIElement,
  React.ComponentProps<"li">
>(({ ...props }, ref) => <li ref={ref} {...props} />)
SidebarMenuSubItem.displayName = "SidebarMenuSubItem"

const SidebarMenuSubButton = React.forwardRef<
  HTMLAnchorElement,
  React.ComponentProps<"a"> & {
    asChild?: boolean
    size?: "sm" | "md"
    isActive?: boolean
  }
>(({ asChild = false, size = "md", isActive, className, ...props }, ref) => {
  const Comp = asChild ? Slot : "a"

  return (
    <Comp
      ref={ref}
      data-sidebar="menu-sub-button"
      data-size={size}
      data-active={isActive}
      className={cn(
        "flex h-7 min-w-0 -translate-x-px items-center gap-2 overflow-hidden rounded-md px-2 text-sidebar-foreground outline-none ring-sidebar-ring hover:bg-sidebar-accent hover:text-sidebar-accent-foreground focus-visible:ring-2 active:bg-sidebar-accent active:text-sidebar-accent-foreground disabled:pointer-events-none disabled:opacity-50 aria-disabled:pointer-events-none aria-disabled:opacity-50 [&>span:last-child]:truncate [&>svg]:size-4 [&>svg]:shrink-0 [&>svg]:text-sidebar-accent-foreground",
        "transition-[opacity,transform] duration-100 ease-sidebar",
        "data-[active=true]:bg-sidebar-accent data-[active=true]:text-sidebar-accent-foreground",
        "group-data-[collapsible=icon]:opacity-0 group-data-[collapsible=icon]:scale-95 group-data-[collapsible=icon]:pointer-events-none",
        size === "sm" && "text-xs",
        size === "md" && "text-sm",
        className
      )}
      {...props}
    />
  )
})
SidebarMenuSubButton.displayName = "SidebarMenuSubButton"

export {
  Sidebar,
  SidebarContent,
  SidebarFooter,
  SidebarGroup,
  SidebarGroupAction,
  SidebarGroupContent,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarInput,
  SidebarInset,
  SidebarMenu,
  SidebarMenuAction,
  SidebarMenuBadge,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSkeleton,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
  SidebarProvider,
  SidebarRail,
  SidebarSeparator,
  SidebarTrigger,
  useSidebar,
}
