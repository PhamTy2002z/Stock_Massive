"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

export interface SettingsNavGroup {
  heading: string
  items: { id: string; label: string }[]
}

/**
 * The settings rail: a panel flush against the app sidebar, running the full
 * height of the content box and scrolling on its own.
 *
 * It tracks the section in view rather than the last hash the user clicked, so
 * scrolling past a section moves the marker with it.
 */
export function SettingsNav({
  groups,
  scrollRef,
}: {
  groups: SettingsNavGroup[]
  /** The column the sections scroll inside — the observer's root. */
  scrollRef: React.RefObject<HTMLElement | null>
}) {
  const ids = React.useMemo(
    () => groups.flatMap((group) => group.items.map((item) => item.id)),
    [groups]
  )
  const [active, setActive] = React.useState(ids[0])

  React.useEffect(() => {
    const root = scrollRef.current
    const sections = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null)

    if (!root || sections.length === 0) return

    // Scoped to the scrolling column, not the viewport: the page itself never
    // scrolls here, so a viewport-rooted observer would see nothing move. The
    // band ends 60% down so a section counts as current once its heading
    // reaches the top, not once it fills the column.
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]

        if (visible) setActive(visible.target.id)
      },
      { root, rootMargin: "0px 0px -60% 0px", threshold: 0 }
    )

    sections.forEach((section) => observer.observe(section))
    return () => observer.disconnect()
  }, [ids, scrollRef])

  return (
    <nav
      aria-label="Mục cài đặt"
      className="hidden w-64 shrink-0 flex-col overflow-y-auto border-r border-border bg-sidebar md:flex"
    >
      <div className="border-b border-border px-5 py-5">
        <h1 className="text-[17px] font-semibold leading-[1.24] tracking-[-0.374px]">
          Cài đặt
        </h1>
      </div>

      <div className="flex-1 py-2">
        {groups.map((group) => (
          <div
            key={group.heading}
            className="border-b border-border px-3 py-4 last:border-b-0"
          >
            <div className="px-2 text-[11px] font-medium uppercase leading-[1.3] tracking-[0.08em] text-muted-foreground">
              {group.heading}
            </div>
            <ul className="mt-2 space-y-0.5">
              {group.items.map((item) => (
                <li key={item.id}>
                  <a
                    href={`#${item.id}`}
                    aria-current={active === item.id ? "true" : undefined}
                    className={cn(
                      "block rounded-md px-2 py-1.5 text-[13px] leading-[1.43] tracking-[-0.208px] transition-colors",
                      active === item.id
                        ? "bg-accent font-medium text-accent-foreground"
                        : "text-muted-foreground hover:bg-accent/50 hover:text-foreground"
                    )}
                  >
                    {item.label}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        ))}
      </div>
    </nav>
  )
}
