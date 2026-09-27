"use client"

import * as React from "react"
import { useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import { useDesk } from "@/components/shell/desk-state"
import { deleteAllThreads, fetchThread, listMemoryFacts, listThreads } from "@/lib/alpha-desk/api"
import type { MemoryFact, ThreadDetail } from "@/lib/alpha-desk/types"
import { queryKeys } from "@/lib/query-keys"

import { ConfirmAction, PillAction, SettingsRow, SettingsSection } from "./settings-primitives"

/** How many transcripts the export reads at once. */
const EXPORT_CONCURRENCY = 3

/** Run `task` over `items` with at most `limit` in flight, keeping input order. */
async function mapLimited<T, R>(
  items: T[],
  limit: number,
  task: (item: T) => Promise<R>,
): Promise<R[]> {
  const results = new Array<R>(items.length)
  let next = 0
  const worker = async () => {
    while (next < items.length) {
      const index = next++
      results[index] = await task(items[index])
    }
  }
  await Promise.all(Array.from({ length: Math.min(limit, items.length) }, worker))
  return results
}

async function allMemoryFacts(): Promise<MemoryFact[]> {
  const facts: MemoryFact[] = []
  for (;;) {
    const page = await listMemoryFacts(facts.length, 50)
    facts.push(...page.items)
    if (page.items.length === 0 || facts.length >= page.total) return facts
  }
}

/** Today in Vietnam as YYYY-MM-DD, for the file name. */
function vietnamToday(): string {
  // `en-CA` formats a date as ISO order, which is the whole reason it is used.
  return new Intl.DateTimeFormat("en-CA", { timeZone: "Asia/Ho_Chi_Minh" }).format(new Date())
}

function download(name: string, contents: string): void {
  const url = URL.createObjectURL(new Blob([contents], { type: "application/json" }))
  const link = document.createElement("a")
  link.href = url
  link.download = name
  document.body.appendChild(link)
  link.click()
  link.remove()
  // Revoked on the next turn of the loop: the click has handed the URL to the
  // download by then, and holding the blob longer only holds memory.
  setTimeout(() => URL.revokeObjectURL(url), 0)
}

/**
 * Every conversation with its transcript, and every remembered note, as one
 * JSON file — assembled here from the same reads the workspace makes, so the
 * export says exactly what the product shows.
 */
function ExportRow() {
  const [progress, setProgress] = React.useState<{ done: number; total: number } | null>(null)

  const run = async () => {
    setProgress({ done: 0, total: 0 })
    try {
      const { threads } = await listThreads()
      setProgress({ done: 0, total: threads.length })
      let done = 0
      const transcripts: ThreadDetail[] = await mapLimited(
        threads,
        EXPORT_CONCURRENCY,
        async (thread) => {
          const detail = await fetchThread(thread.id)
          done += 1
          setProgress({ done, total: threads.length })
          return detail
        },
      )
      const memory = await allMemoryFacts()
      download(
        `visgnite-data-${vietnamToday()}.json`,
        JSON.stringify(
          { exported_at: new Date().toISOString(), threads: transcripts, memory_facts: memory },
          null,
          2,
        ),
      )
      toast.success("Data exported")
    } catch {
      toast.error("Couldn't export the data. Please try again.")
    } finally {
      setProgress(null)
    }
  }

  return (
    <SettingsRow
      label="Export data"
      description="Download a JSON file with every conversation, its content, and your remembered facts."
    >
      <PillAction disabled={progress !== null} onClick={() => void run()}>
        {progress === null
          ? "Export"
          : progress.total === 0
            ? "Exporting…"
            : `Exporting ${progress.done}/${progress.total}…`}
      </PillAction>
    </SettingsRow>
  )
}

/**
 * The conversation history, and what the reader may do with it.
 *
 * Deleting one conversation lives on each thread's own menu in the sidebar,
 * which is where a reader deleting one thing looks for it; this pane holds the
 * whole-history actions.
 */
export function DataSection() {
  const queryClient = useQueryClient()
  const desk = useDesk()

  const deleteEverything = async () => {
    try {
      const { deleted } = await deleteAllThreads()
      queryClient.setQueryData(queryKeys.threads, { threads: [] })
      queryClient.removeQueries({ queryKey: ["thread"] })
      // The conversation on screen went with the rest, the same way the
      // sidebar handles deleting the open one.
      desk.newThread()
      toast.success(`Deleted ${deleted} conversations`)
    } catch {
      toast.error("Couldn't delete the conversations. Please try again.")
    } finally {
      void queryClient.invalidateQueries({ queryKey: queryKeys.threads })
    }
  }

  return (
    <SettingsSection title="Data">
      <ExportRow />
      <SettingsRow
        label="Delete all conversations"
        description="This can't be undone. To delete one conversation, open its menu in the sidebar."
      >
        <ConfirmAction
          confirmLabel="Confirm delete"
          pendingLabel="Deleting…"
          onConfirm={deleteEverything}
        >
          Delete all
        </ConfirmAction>
      </SettingsRow>
    </SettingsSection>
  )
}
