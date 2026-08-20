"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * The settings surface is built from three pieces that repeat: a titled
 * section, a bordered panel, and a row whose label sits left and whose control
 * sits right. Elevation is carried by the surface step (the panel one stop
 * above the dialog it sits in), never by a shadow, so the panel ships flat with
 * one hairline.
 */

export function SettingsSection({
  title,
  description,
  children,
}: {
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    /* One section is on screen at a time — the dialog's rail switches between
       them rather than scrolling past them — so the heading is the pane's own
       title, not an anchor to jump to. */
    <section className="animate-vg-row-in">
      <h2 className="text-[1.45rem] font-semibold leading-[1.19] tracking-[-0.02em]">
        {title}
      </h2>
      {description ? (
        <p className="mt-2 text-meta text-ink-4">
          {description}
        </p>
      ) : null}
      <div className="mt-5 space-y-6">{children}</div>
    </section>
  )
}

export function SettingsPanel({
  children,
  footer,
}: {
  children: React.ReactNode
  footer?: React.ReactNode
}) {
  return (
    <div className="overflow-hidden rounded-card border border-hairline bg-card">
      {children}
      {footer ? (
        <div className="border-t border-hairline bg-foreground/[0.025] px-5 py-3">
          {footer}
        </div>
      ) : null}
    </div>
  )
}

export function SettingsRow({
  label,
  description,
  children,
  className,
}: {
  label: string
  description?: string
  children?: React.ReactNode
  className?: string
}) {
  return (
    <div
      className={cn(
        // Below md the control drops under its label rather than fighting it
        // for a share of a phone-width row.
        "flex flex-col gap-3 border-b border-hairline px-5 py-4 last:border-b-0 md:flex-row md:items-center md:justify-between md:gap-6",
        className
      )}
    >
      <div className="min-w-0 md:max-w-[280px]">
        <div className="text-[0.95rem] font-medium">
          {label}
        </div>
        {description ? (
          <p className="mt-0.5 text-meta text-ink-6">
            {description}
          </p>
        ) : null}
      </div>
      {children ? <div className="min-w-0 md:shrink-0">{children}</div> : null}
    </div>
  )
}

/**
 * Read-only value in a field-shaped shell — it looks like the input it would be
 * if the field were editable, but it is deliberately not one.
 */
export function ReadOnlyField({ value }: { value: string }) {
  return (
    <div className="w-full truncate rounded-lg border border-hairline bg-background px-3 py-2 text-meta tabular-nums text-ink-4 md:w-[250px]">
      {value}
    </div>
  )
}
