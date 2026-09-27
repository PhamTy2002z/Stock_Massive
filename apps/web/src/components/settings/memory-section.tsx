"use client"

import { useInfiniteQuery, useMutation, useQueryClient, type InfiniteData } from "@tanstack/react-query"
import { Trash2 } from "lucide-react"
import { toast } from "sonner"

import { safeHref } from "@/components/alpha/message/source-list"
import { IconButton } from "@/components/shell/primitives"
import { useAuth, useUpdateProfile } from "@/hooks/use-auth"
import { deleteAllMemoryFacts, deleteMemoryFact, listMemoryFacts } from "@/lib/alpha-desk/api"
import type { MemoryFact, MemoryFactPage } from "@/lib/alpha-desk/types"
import { formatVietnamDate } from "@/lib/market-session"
import { queryKeys } from "@/lib/query-keys"

import { ConfirmAction, PillAction, SettingsRow, SettingsSection, Toggle } from "./settings-primitives"

/** How many notes one page asks for. */
const PAGE_SIZE = 50

type Pages = InfiniteData<MemoryFactPage, number>

/** How many notes the cache already holds, which is also where the next page starts. */
function loaded(pages: MemoryFactPage[]): number {
  return pages.reduce((sum, page) => sum + page.items.length, 0)
}

/**
 * The notes, paged by offset.
 *
 * The next offset is the count already held rather than `pages × PAGE_SIZE`:
 * a note deleted here is removed from the cache and from the server at once,
 * so both sides shift by one and the next page starts at the right note.
 */
function useMemoryFacts() {
  return useInfiniteQuery({
    queryKey: queryKeys.memoryFacts,
    queryFn: ({ pageParam }) => listMemoryFacts(pageParam, PAGE_SIZE),
    initialPageParam: 0,
    getNextPageParam: (last, pages) => {
      const held = loaded(pages)
      return held < last.total ? held : undefined
    },
  })
}

function MemoryToggle() {
  const { user } = useAuth()
  const update = useUpdateProfile({ optimistic: true })
  const enabled = user?.preferences.memory_enabled ?? true

  return (
    <SettingsRow
      label="Allow memory"
      description="When off, the system won't save new facts or look up what it already remembers. Existing facts are kept."
    >
      <Toggle
        label="Allow memory"
        checked={enabled}
        disabled={!user || update.isPending}
        onChange={(next) => update.mutate({ preferences: { memory_enabled: next } })}
      />
    </SettingsRow>
  )
}

function FactRow({ fact, onDelete, deleting }: { fact: MemoryFact; onDelete: () => void; deleting: boolean }) {
  const asOf = formatVietnamDate(fact.as_of)
  const kept = formatVietnamDate(fact.created_at)
  // The backend already refuses non-http(s) sources; checking again here keeps
  // a `javascript:` URL from ever reaching an `href` if that ever regresses.
  const sourceHref = fact.source_url ? safeHref(fact.source_url) : null

  return (
    <li className="flex min-h-[56px] items-start gap-4 border-b border-hairline py-3.5 last:border-b-0">
      <div className="min-w-0 flex-1">
        <div className="text-row text-foreground">{fact.title}</div>
        <p className="mt-0.5 line-clamp-2 text-control text-ink-5 [text-wrap:pretty]">{fact.body}</p>
        <p className="mt-1 flex flex-wrap items-center gap-x-2 gap-y-0.5 text-meta text-ink-6">
          {fact.symbol ? <span className="font-mono text-ink-4">{fact.symbol}</span> : null}
          {fact.source_name ? (
            sourceHref ? (
              <a
                href={sourceHref}
                target="_blank"
                rel="noopener noreferrer"
                className="rounded-sm underline decoration-hairline underline-offset-2 outline-none hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
              >
                {fact.source_name}
              </a>
            ) : (
              <span>{fact.source_name}</span>
            )
          ) : null}
          {asOf ? <span>As of {asOf}</span> : null}
          {kept ? <span>Remembered on {kept}</span> : null}
        </p>
      </div>
      <IconButton
        label="Delete memory"
        disabled={deleting}
        onClick={onDelete}
        className="size-8"
      >
        <Trash2 className="size-4" strokeWidth={1.7} />
      </IconButton>
    </li>
  )
}

function SkeletonRows() {
  return (
    <ul aria-label="Loading memory" aria-busy="true">
      {[0, 1, 2].map((row) => (
        <li key={row} className="border-b border-hairline py-3.5 last:border-b-0">
          <div className="h-3.5 w-2/5 animate-pulse rounded bg-foreground/[0.07] motion-reduce:animate-none" />
          <div className="mt-2 h-3 w-4/5 animate-pulse rounded bg-foreground/[0.05] motion-reduce:animate-none" />
        </li>
      ))}
    </ul>
  )
}

/**
 * What the assistant was asked to keep, and the switch that stops it keeping more.
 *
 * `memory_enabled` lives on the account, not this browser: saving and looking
 * up notes is the assistant's work on the server, so that is where the switch
 * has to be read.
 */
export function MemorySection() {
  const queryClient = useQueryClient()
  const facts = useMemoryFacts()
  const pages = facts.data?.pages ?? []
  const items = pages.flatMap((page) => page.items)
  const total = pages.length > 0 ? pages[pages.length - 1].total : 0

  const remove = useMutation({
    mutationFn: (factId: number) => deleteMemoryFact(factId),
    onSuccess: (_answer, factId) => {
      queryClient.setQueryData<Pages>(queryKeys.memoryFacts, (cached) =>
        cached === undefined
          ? cached
          : {
              ...cached,
              pages: cached.pages.map((page) => ({
                items: page.items.filter((fact) => fact.id !== factId),
                total: Math.max(0, page.total - 1),
              })),
            },
      )
    },
    onError: () => toast.error("Couldn't delete that memory. Please try again."),
  })

  const clearAll = async () => {
    try {
      const { deleted } = await deleteAllMemoryFacts()
      queryClient.setQueryData<Pages>(queryKeys.memoryFacts, {
        pages: [{ items: [], total: 0 }],
        pageParams: [0],
      })
      toast.success(`Deleted ${deleted} memories`)
    } catch {
      toast.error("Couldn't clear memory. Please try again.")
    }
  }

  return (
    <>
      <SettingsSection title="Memory">
        <MemoryToggle />
      </SettingsSection>

      <SettingsSection title={facts.isSuccess ? `Remembered (${total})` : "Remembered"}>
        {facts.isPending ? (
          <SkeletonRows />
        ) : facts.isError && items.length === 0 ? (
          <SettingsRow
            label="Couldn't load memory"
            description="Memory lives on the server; the next try may be able to read it."
          >
            <PillAction onClick={() => void facts.refetch()} disabled={facts.isFetching}>
              {facts.isFetching ? "Retrying…" : "Retry"}
            </PillAction>
          </SettingsRow>
        ) : items.length === 0 ? (
          <p className="border-b border-hairline py-3.5 text-control text-ink-5">
            No memories yet. When you ask the system to remember something, it will appear here.
          </p>
        ) : (
          <ul aria-label="Remembered facts">
            {items.map((fact) => (
              <FactRow
                key={fact.id}
                fact={fact}
                deleting={remove.isPending && remove.variables === fact.id}
                onDelete={() => remove.mutate(fact.id)}
              />
            ))}
          </ul>
        )}

        {facts.hasNextPage ? (
          <div className="border-b border-hairline py-3.5">
            <PillAction
              onClick={() => void facts.fetchNextPage()}
              disabled={facts.isFetchingNextPage}
            >
              {facts.isFetchingNextPage
                ? "Loading…"
                : facts.isFetchNextPageError
                  ? "Couldn't load · Retry"
                  : "Show more"}
            </PillAction>
          </div>
        ) : null}

        <SettingsRow
          label="Delete all memory"
          description="Permanently deletes every memory. This can't be undone."
        >
          <ConfirmAction
            confirmLabel="Confirm delete"
            pendingLabel="Deleting…"
            disabled={!facts.isSuccess || total === 0}
            onConfirm={clearAll}
          >
            Delete all
          </ConfirmAction>
        </SettingsRow>
      </SettingsSection>
    </>
  )
}
