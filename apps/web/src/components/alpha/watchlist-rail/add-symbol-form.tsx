"use client"

import { useState, type FormEvent } from "react"
import { Loader2, Plus } from "lucide-react"

import { cn } from "@/lib/utils"

/**
 * Adding a symbol, and reporting what the addition did.
 *
 * The notice is separate from the error on purpose. A refusal — outside the
 * Universe, Watchlist full — means the symbol is not there. A notice means the
 * symbol *is* there and something about its Analysis is worth saying: the
 * on-demand allowance is spent, or no session has closed yet. Rendering both as
 * "error" would tell a user their addition failed when it succeeded.
 */
export function AddSymbolForm({
  onAdd,
  isAdding,
  error,
  notice,
  className,
}: {
  onAdd: (symbol: string) => void
  isAdding?: boolean
  error?: string | null
  notice?: string | null
  className?: string
}) {
  const [symbol, setSymbol] = useState("")

  function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = symbol.trim().toUpperCase()
    if (!trimmed || isAdding) return
    onAdd(trimmed)
    setSymbol("")
  }

  return (
    <div className={cn("space-y-2", className)}>
      <form onSubmit={submit} className="flex items-center gap-2">
        <input
          value={symbol}
          onChange={(event) => setSymbol(event.target.value)}
          placeholder="Add symbol"
          aria-label="Add symbol"
          maxLength={32}
          className="h-9 min-w-0 flex-1 rounded-md border border-border/60 bg-background px-3 text-sm uppercase placeholder:normal-case placeholder:text-muted-foreground focus:outline-none focus:ring-1 focus:ring-ring"
        />
        <button
          type="submit"
          disabled={isAdding || !symbol.trim()}
          className="inline-flex h-9 items-center gap-1 rounded-md border border-border/60 px-3 text-sm hover:bg-muted disabled:opacity-50"
        >
          {isAdding ? (
            <Loader2 className="h-4 w-4 animate-spin" />
          ) : (
            <Plus className="h-4 w-4" />
          )}
          Add
        </button>
      </form>

      {error && (
        <p role="alert" className="text-xs text-red-600 dark:text-red-400">
          {error}
        </p>
      )}
      {notice && (
        <p role="status" className="text-xs text-amber-600 dark:text-amber-400">
          {notice}
        </p>
      )}
    </div>
  )
}
