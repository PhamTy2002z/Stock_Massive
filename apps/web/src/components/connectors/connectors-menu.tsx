"use client"

import { useState, type ReactNode } from "react"
import { Check, ChevronRight, Plug, Settings2, SlidersHorizontal } from "lucide-react"

import { Menu, MenuItem, MenuSeparator } from "@/components/shell/primitives"
import { useShell } from "@/components/shell/shell-state"
import { TOOL_ACCESS_COPY } from "@/lib/connectors/copy"
import { requestConnectorsPane } from "@/lib/connectors/open-pane"
import type { ToolAccess } from "@/lib/connectors/types"
import { cn } from "@/lib/utils"

import { useConnectors } from "./use-connectors"

const MODES: ToolAccess[] = ["on_demand", "preloaded"]

/**
 * The composer's "+" › Connectors row and its flyout.
 *
 * Draws nothing until the feature is on for this deployment: a row that opened
 * onto "not enabled" would be a promise, and the Settings pane already says it.
 * A toggle here changes the connector itself, so it takes effect from the next
 * Turn — the running one resolved its tools when it started.
 */
export function ConnectorsMenu() {
  const connectors = useConnectors()
  const { dispatch } = useShell()
  const [open, setOpen] = useState<"none" | "connectors" | "access">("none")
  const { state } = connectors
  if (!state?.enabled) return null

  return (
    <div className="relative">
      <SubmenuTrigger
        icon={<Plug className="size-[17px] text-ink-4" strokeWidth={1.6} />}
        expanded={open !== "none"}
        onClick={() => setOpen(open === "none" ? "connectors" : "none")}
      >
        Connectors
      </SubmenuTrigger>
      {open !== "none" && (
        <Menu className="absolute bottom-0 left-full ml-2 w-[280px]">
          <MenuItem
            icon={<Settings2 className="size-[16px] text-ink-4" strokeWidth={1.6} />}
            onClick={() => {
              requestConnectorsPane()
              dispatch({ type: "overlay", overlay: "settings" })
            }}
          >
            Manage connectors
          </MenuItem>
          {state.connectors.length > 0 && <MenuSeparator />}
          {state.connectors.map((connector) => (
            <button
              key={connector.id}
              type="button"
              role="menuitemcheckbox"
              aria-checked={connector.enabled}
              disabled={connectors.busy === `enabled:${connector.id}`}
              onClick={() => connectors.setEnabled(connector.id, !connector.enabled)}
              className="flex w-full items-center gap-2.5 rounded-[9px] px-2.5 py-2 text-left text-row text-ink-2 outline-none transition-colors hover:bg-foreground/[0.06] focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
            >
              <span className="min-w-0 flex-1 truncate">{connector.name}</span>
              {/* The switch is drawn, not a control of its own: the row is the control. */}
              <span
                aria-hidden
                className={cn(
                  "relative block h-[18px] w-[30px] shrink-0 rounded-pill transition-colors",
                  connector.enabled ? "bg-primary" : "bg-foreground/[0.14]",
                )}
              >
                <span
                  className={cn(
                    "absolute top-[3px] size-3 rounded-full bg-ink-1 transition-[left]",
                    connector.enabled ? "left-[15px]" : "left-[3px]",
                  )}
                />
              </span>
            </button>
          ))}
          <MenuSeparator />
          <div className="relative">
            <SubmenuTrigger
              icon={<SlidersHorizontal className="size-[16px] text-ink-4" strokeWidth={1.6} />}
              expanded={open === "access"}
              onClick={() => setOpen(open === "access" ? "connectors" : "access")}
            >
              Tool access
            </SubmenuTrigger>
            {open === "access" && (
              <Menu className="absolute bottom-0 left-full ml-2 w-[280px]">
                {MODES.map((mode) => (
                  <button
                    key={mode}
                    type="button"
                    role="menuitemradio"
                    aria-checked={state.tool_access === mode}
                    disabled={connectors.busy === "access"}
                    onClick={() => {
                      if (state.tool_access !== mode) connectors.setAccess(mode)
                    }}
                    className="flex w-full items-start gap-2.5 rounded-[9px] px-2.5 py-2 text-left outline-none transition-colors hover:bg-foreground/[0.06] focus-visible:ring-2 focus-visible:ring-ring disabled:opacity-60"
                  >
                    <span className="min-w-0 flex-1">
                      <span className="block text-row text-ink-2">{TOOL_ACCESS_COPY[mode].label}</span>
                      <span className="mt-0.5 block text-micro leading-[1.4] text-ink-6">
                        {TOOL_ACCESS_COPY[mode].hint}
                      </span>
                    </span>
                    <Check
                      aria-hidden
                      className={cn(
                        "mt-0.5 size-4 shrink-0 text-ink-2",
                        state.tool_access === mode ? "opacity-100" : "opacity-0",
                      )}
                    />
                  </button>
                ))}
              </Menu>
            )}
          </div>
          <p className="px-2.5 pb-1 pt-1.5 text-micro text-ink-6">
            The change takes effect from the next question.
          </p>
          {connectors.error && (
            <p role="alert" className="px-2.5 pb-1 text-micro text-destructive">
              {connectors.error}
            </p>
          )}
        </Menu>
      )}
    </div>
  )
}

/** A menu row that opens a flyout: `MenuItem`'s look, with the popup state announced. */
function SubmenuTrigger({
  icon,
  expanded,
  onClick,
  children,
}: {
  icon: ReactNode
  expanded: boolean
  onClick: () => void
  children: ReactNode
}) {
  return (
    <button
      type="button"
      role="menuitem"
      aria-haspopup="menu"
      aria-expanded={expanded}
      onClick={onClick}
      className="flex w-full items-center gap-2.5 rounded-[9px] px-2.5 py-2 text-left text-row text-ink-2 outline-none transition-colors hover:bg-foreground/[0.06] focus-visible:ring-2 focus-visible:ring-ring"
    >
      {icon}
      <span className="min-w-0 flex-1 truncate">{children}</span>
      <ChevronRight className="size-4 shrink-0 text-ink-6" aria-hidden />
    </button>
  )
}
