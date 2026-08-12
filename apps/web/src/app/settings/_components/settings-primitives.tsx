"use client"

import * as React from "react"

import { cn } from "@/lib/utils"

/**
 * The settings surface is built from three pieces that repeat: a titled
 * section, a bordered panel, and a row whose label sits left and whose control
 * sits right. Elevation is carried by the surface step (--card over
 * --background), never by a shadow, so the panel ships flat with one hairline.
 */

export function SettingsSection({
  id,
  title,
  description,
  children,
}: {
  id: string
  title: string
  description?: string
  children: React.ReactNode
}) {
  return (
    /* Sections scroll inside their own column rather than the page, so the
       anchor only needs to clear its own top padding. */
    <section id={id} className="scroll-mt-8">
      <h2 className="text-[21px] font-semibold leading-[1.19] tracking-[-0.374px]">
        {title}
      </h2>
      {description ? (
        <p className="mt-1 text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
          {description}
        </p>
      ) : null}
      <div className="mt-4 space-y-6">{children}</div>
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
    <div className="overflow-hidden rounded-[18px] border border-[hsl(var(--hairline))] bg-card">
      {children}
      {footer ? (
        <div className="border-t border-[hsl(var(--hairline))] bg-muted/40 px-5 py-3.5">
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
        "flex flex-col gap-3 border-b border-[hsl(var(--hairline))] px-5 py-4 last:border-b-0 md:flex-row md:items-center md:justify-between md:gap-6",
        className
      )}
    >
      <div className="min-w-0 md:max-w-[46%]">
        <div className="text-[15px] font-semibold leading-[1.24] tracking-[-0.374px]">
          {label}
        </div>
        {description ? (
          <p className="mt-0.5 text-[13px] leading-[1.43] tracking-[-0.208px] text-muted-foreground">
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
    <div className="w-full truncate rounded-lg border border-border bg-background px-3 py-2 text-[13px] leading-[1.43] tracking-[-0.208px] tabular-nums text-muted-foreground md:w-[320px]">
      {value}
    </div>
  )
}
