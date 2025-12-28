"use client"

import { useState, useEffect } from "react"
import { ChevronDown } from "lucide-react"
import {
  Collapsible,
  CollapsibleContent,
  CollapsibleTrigger,
} from "@/components/ui/collapsible"
import { cn } from "@/lib/utils"

interface CollapsibleSectionProps {
  id: string
  title: string
  children: React.ReactNode
  defaultOpen?: boolean
  className?: string
}

export function CollapsibleSection({
  id,
  title,
  children,
  defaultOpen = true,
  className,
}: CollapsibleSectionProps) {
  const storageKey = `section-collapsed-${id}`

  // Initialize with defaultOpen, then sync with localStorage in useEffect
  const [isOpen, setIsOpen] = useState(defaultOpen)
  const [hasMounted, setHasMounted] = useState(false)

  // Sync with localStorage after mount to avoid hydration mismatch
  useEffect(() => {
    try {
      const stored = localStorage.getItem(storageKey)
      if (stored !== null) {
        setIsOpen(stored === "true")
      }
    } catch {
      // localStorage unavailable (e.g., Safari private mode)
    }
    setHasMounted(true)
  }, [storageKey])

  // Persist to localStorage when state changes (after mount)
  useEffect(() => {
    if (hasMounted) {
      try {
        localStorage.setItem(storageKey, String(isOpen))
      } catch {
        // localStorage unavailable
      }
    }
  }, [isOpen, storageKey, hasMounted])

  return (
    <Collapsible open={isOpen} onOpenChange={setIsOpen} className={className}>
      <CollapsibleTrigger className="flex items-center justify-between w-full py-2 group">
        <h2 className="text-lg font-semibold text-foreground">{title}</h2>
        <ChevronDown
          className={cn(
            "h-4 w-4 text-muted-foreground transition-transform duration-200",
            isOpen && "rotate-180"
          )}
        />
      </CollapsibleTrigger>
      <CollapsibleContent className="data-[state=open]:animate-in data-[state=closed]:animate-out data-[state=closed]:fade-out-0 data-[state=open]:fade-in-0">
        {children}
      </CollapsibleContent>
    </Collapsible>
  )
}
