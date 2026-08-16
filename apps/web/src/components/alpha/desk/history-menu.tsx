"use client"

import { useState } from "react"
import { History, Plus } from "lucide-react"

import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu"
import { useThreads } from "@/hooks/use-threads"

/**
 * History / Related Analysis, as a compact popover.
 *
 * **Secondary retrieval, never primary navigation** (`docs/specs/0002` §2).
 * The default surface must not ask the user to choose a Thread before asking a
 * question, so this is a control they open when they deliberately go back to
 * earlier research — not a permanent list beside the conversation, and on a
 * narrow viewport not a second navigation level either.
 *
 * The list is fetched only while the menu is open. A Thread list nobody looked
 * at is a request nobody needed.
 */
export function HistoryMenu({
  currentThreadId,
  onOpenThread,
  onNewThread,
}: {
  currentThreadId: string | null
  onOpenThread: (threadId: string) => void
  onNewThread: () => void
}) {
  const [open, setOpen] = useState(false)
  const { data, isPending } = useThreads(open)

  return (
    <DropdownMenu open={open} onOpenChange={setOpen}>
      <DropdownMenuTrigger className="inline-flex items-center gap-1.5 rounded-lg border border-border px-2.5 py-1 text-meta text-ink-4 transition-colors hover:bg-foreground/[0.06] hover:text-foreground">
        <History className="h-3.5 w-3.5" />
        {/* The label goes first when the row runs out of room; the icon is what
            has to survive. */}
        <span className="hidden sm:inline">History</span>
      </DropdownMenuTrigger>

      <DropdownMenuContent align="end" className="max-h-80 w-72 overflow-y-auto">
        <DropdownMenuItem onSelect={onNewThread} className="gap-2 text-meta">
          <Plus className="h-3.5 w-3.5" />
          New thread
        </DropdownMenuItem>

        <DropdownMenuSeparator />
        <DropdownMenuLabel className="text-micro uppercase tracking-wide text-muted-foreground">Recent</DropdownMenuLabel>

        {isPending ? (
          <p className="px-2.5 py-2 text-meta text-muted-foreground">Loading…</p>
        ) : !data || data.threads.length === 0 ? (
          <p className="px-2.5 py-2 text-meta text-muted-foreground">
            No threads yet.
          </p>
        ) : (
          data.threads.map((thread) => (
            <DropdownMenuItem
              key={thread.id}
              onSelect={() => onOpenThread(thread.id)}
              className="flex-col items-start gap-0.5 text-meta"
              aria-current={thread.id === currentThreadId}
            >
              <span className="w-full truncate">
                {thread.title ?? "Untitled thread"}
              </span>
              {/* A Thread carries every symbol it touched and is owned by none
                  of them, so they are listed rather than reduced to one. */}
              {thread.symbols.length > 0 && (
                <span className="w-full truncate text-muted-foreground">
                  {thread.symbols.join(" · ")}
                </span>
              )}
            </DropdownMenuItem>
          ))
        )}
      </DropdownMenuContent>
    </DropdownMenu>
  )
}
