"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

export interface SettingsNavGroup {
  heading: string
  items: { id: string; label: string }[]
}

/**
 * The left rail. It tracks the section in view rather than the last hash the
 * user clicked, so scrolling past a section moves the marker with it.
 */
export function SettingsNav({ groups }: { groups: SettingsNavGroup[] }) {
  const ids = React.useMemo(
    () => groups.flatMap((group) => group.items.map((item) => item.id)),
    [groups]
  )
  const [active, setActive] = React.useState(ids[0])

  React.useEffect(() => {
    const sections = ids
      .map((id) => document.getElementById(id))
      .filter((el): el is HTMLElement => el !== null)

    if (sections.length === 0) return

    // The band ends 60% up the viewport so a section counts as "current" once
    // its heading clears the header, not once it fills the screen.
    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries
          .filter((entry) => entry.isIntersecting)
          .sort((a, b) => a.boundingClientRect.top - b.boundingClientRect.top)[0]

        if (visible) setActive(visible.target.id)
      },
      { rootMargin: "-80px 0px -60% 0px", threshold: 0 }
    )

    sections.forEach((section) => observer.observe(section))
    return () => observer.disconnect()
  }, [ids])

  return (
    <nav aria-label="Mục cài đặt" className="w-full md:w-56 md:shrink-0">
      <div className="md:sticky md:top-24">
        <h1 className="px-3 text-[21px] font-semibold leading-[1.19] tracking-[-0.374px]">
          Cài đặt
        </h1>
        <div className="mt-6 space-y-6">
          {groups.map((group) => (
            <div key={group.heading}>
              <div className="px-3 text-[11px] font-semibold uppercase leading-[1.3] tracking-[0.06em] text-muted-foreground">
                {group.heading}
              </div>
              <ul className="mt-2 space-y-0.5">
                {group.items.map((item) => (
                  <li key={item.id}>
                    <a
                      href={`#${item.id}`}
                      aria-current={active === item.id ? "true" : undefined}
                      className={cn(
                        "block rounded-lg px-3 py-1.5 text-[13px] leading-[1.43] tracking-[-0.208px] transition-colors",
                        active === item.id
                          ? "bg-accent font-semibold text-accent-foreground"
                          : "text-muted-foreground hover:bg-accent/60 hover:text-foreground"
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
      </div>
    </nav>
  )
}
