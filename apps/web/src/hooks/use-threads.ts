"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"
import { toast } from "sonner"

import {
  clearHelpful,
  createThread,
  deleteThread,
  fetchThread,
  flagMessage,
  listThreads,
  markHelpful,
  unflagMessage,
  updateThread,
} from "@/lib/alpha-desk/api"
import type {
  FlagReason,
  MessageFlag,
  MessageHelpful,
  Thread,
  ThreadDetail,
} from "@/lib/alpha-desk/types"
import { queryKeys } from "@/lib/query-keys"

/**
 * The canonical half of the conversation.
 *
 * Threads and their messages are TanStack Query resources; the Turn in flight
 * is not (ADR-0013). Nothing here is polled: a Thread changes only when a Turn
 * this browser started ends, and `useLiveTurn` already invalidates it at the
 * terminal event. Polling on top of that would be a request a minute asking
 * whether something this tab did has happened yet.
 */

/** One Thread and its transcript. Disabled until a Thread has been opened. */
export function useThread(threadId: string | null) {
  return useQuery<ThreadDetail>({
    queryKey: queryKeys.thread(threadId ?? "none"),
    queryFn: () => fetchThread(threadId as string),
    enabled: threadId !== null,
    // A Thread is history. It is refetched when a Turn ends, not on a timer.
    staleTime: Infinity,
  })
}

/**
 * This user's Threads, for History / Related Analysis.
 *
 * Secondary retrieval, so it is fetched only when the surface asks: the default
 * screen never makes the user choose a Thread before asking a question, and a
 * list nobody opened is a request nobody needed.
 */
export function useThreads(enabled: boolean) {
  return useQuery<{ threads: Thread[] }>({
    queryKey: queryKeys.threads,
    queryFn: listThreads,
    enabled,
  })
}

/**
 * Open a Thread.
 *
 * Opened without a name, and never named from the client: the backend titles an
 * unnamed Thread from the question that opens it, in the same transaction that
 * commits the message. A title guessed here would be a second authority on the
 * name, and the deep-linked `?symbol=` case would carry a symbol-scoped name
 * into a conversation that is not scoped to a symbol at all.
 */
export function useCreateThread() {
  const queryClient = useQueryClient()
  return useMutation({
    mutationFn: () => createThread(null),
    onSuccess: (thread) => {
      queryClient.setQueryData(queryKeys.thread(thread.id), {
        ...thread,
        messages: [],
      } satisfies ThreadDetail)
      void queryClient.invalidateQueries({ queryKey: queryKeys.threads })
    },
  })
}

/**
 * Rename a Thread or pin it — the writes the sidebar's per-Thread menu makes.
 *
 * The answer is written straight into the cached list rather than refetched.
 * The response *is* the row the list holds, and the ordering the backend
 * applies is the thing that changed, so the list is re-sorted the same way it
 * arrives sorted: pinned group first, then by last touched.
 *
 * The open Thread's own cache entry is patched too, because the top bar names
 * it from there and a rename that left the header stale would look like it
 * failed.
 */
export function useUpdateThread() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: ({
      threadId,
      ...patch
    }: {
      threadId: string
      title?: string | null
      pinned?: boolean
    }) => updateThread(threadId, patch),
    onSuccess: (updated) => {
      queryClient.setQueryData<{ threads: Thread[] }>(queryKeys.threads, (cached) =>
        cached === undefined
          ? cached
          : {
              threads: sortThreads(
                cached.threads.map((row) => (row.id === updated.id ? updated : row)),
              ),
            },
      )
      queryClient.setQueryData<ThreadDetail>(queryKeys.thread(updated.id), (thread) =>
        thread === undefined ? thread : { ...thread, ...updated },
      )
    },
    // The list is written on success only, so a failure leaves the rail
    // showing the truth. What it did not do was say so: a rename that did not
    // take snapped back to the old title with no explanation, which reads as
    // the app having ignored the edit rather than as the request having
    // failed.
    onError: () => {
      toast.error("Không lưu được thay đổi cho hội thoại này.")
    },
  })
}

/**
 * Delete a Thread and its transcript.
 *
 * Not optimistic, and not reversible: the row is dropped from the list once the
 * backend has actually dropped it, because a Thread that vanished and came back
 * on a failed request would read as data loss rather than as an error.
 *
 * The Thread's own cache entry is removed rather than left behind — a stale
 * transcript under a deleted id is the thing a reopened tab would render.
 */
export function useDeleteThread() {
  const queryClient = useQueryClient()

  return useMutation({
    mutationFn: (threadId: string) => deleteThread(threadId),
    onSuccess: (_answer, threadId) => {
      queryClient.setQueryData<{ threads: Thread[] }>(queryKeys.threads, (cached) =>
        cached === undefined
          ? cached
          : { threads: cached.threads.filter((row) => row.id !== threadId) },
      )
      queryClient.removeQueries({ queryKey: queryKeys.thread(threadId) })
    },
    // A delete that failed leaves the row exactly where it was, which is the
    // correct list and a silent one: the reader pressed delete and the thread
    // stayed, with nothing to distinguish a refused request from a control
    // that does not work.
    onError: () => {
      toast.error("Không xoá được hội thoại này.")
    },
  })
}

/**
 * The order the API answers in, applied to a list this client just changed.
 *
 * A copy of the backend's ordering, and the only one: it exists so that pinning
 * moves a row *now* rather than on the next fetch. Everywhere else the list is
 * rendered in the order it arrived.
 */
function sortThreads(threads: Thread[]): Thread[] {
  return [...threads].sort((left, right) => {
    if (left.pinned_at !== right.pinned_at) {
      if (left.pinned_at === null) return 1
      if (right.pinned_at === null) return -1
      return right.pinned_at.localeCompare(left.pinned_at)
    }
    return right.updated_at.localeCompare(left.updated_at)
  })
}

/**
 * Flag one assistant message, or clear the flag again.
 *
 * The answer is patched into the cached Thread rather than invalidating it. A
 * flag changes exactly two columns on one message, and refetching the whole
 * transcript to learn them would pull an evening's reading back over the wire
 * for a pair of fields the response already carries.
 *
 * **Not optimistic.** The pair only exists once the backend wrote it, and a
 * flag that appeared instantly and then vanished on a 401 would tell the reader
 * their objection was recorded when it was not. The write is a single small
 * request; the honest ordering costs nothing worth having.
 */
export function useFlagMessage(threadId: string | null) {
  const queryClient = useQueryClient()

  function applyToThread(flag: MessageFlag): void {
    if (threadId === null) return
    queryClient.setQueryData<ThreadDetail>(queryKeys.thread(threadId), (thread) =>
      thread === undefined
        ? thread
        : {
            ...thread,
            messages: thread.messages.map((message) =>
              message.id === flag.message_id
                ? {
                    ...message,
                    flagged_reason: flag.flagged_reason,
                    flagged_at: flag.flagged_at,
                  }
                : message,
            ),
          },
    )
  }

  const flag = useMutation({
    mutationFn: ({ messageId, reason }: { messageId: number; reason: FlagReason }) =>
      flagMessage(messageId, reason),
    onSuccess: applyToThread,
  })

  const unflag = useMutation({
    mutationFn: (messageId: number) => unflagMessage(messageId),
    onSuccess: applyToThread,
  })

  /**
   * Which message's last write was rejected, if any.
   *
   * Read from the mutation's own `variables` rather than tracked in state,
   * because those *are* the failed call's arguments and a second copy could
   * disagree with them. One id rather than a set: a rejected write is answered
   * by pressing again, and the answer to the previous failure is whatever the
   * next attempt does.
   */
  const failedMessageId = flag.isError
    ? flag.variables.messageId
    : unflag.isError
      ? unflag.variables
      : null

  return { flag, unflag, failedMessageId }
}

/**
 * Mark one assistant message helpful, or take the mark back.
 *
 * The same shape as `useFlagMessage` and for the same reasons: the answer is
 * patched into the cached Thread rather than invalidating it, and the write is
 * **not optimistic** — a mark that appeared instantly and then vanished on a
 * 401 would tell the reader their approval was recorded when it was not.
 *
 * The patch touches `helpful_at` alone. The flag on the same message is left
 * exactly as it was, because the store keeps both: an answer that was useful
 * and got one figure wrong is both, and the UI showing one at a time is a fact
 * about pressing buttons rather than about the record.
 */
export function useHelpfulMessage(threadId: string | null) {
  const queryClient = useQueryClient()

  function applyToThread(mark: MessageHelpful): void {
    if (threadId === null) return
    queryClient.setQueryData<ThreadDetail>(queryKeys.thread(threadId), (thread) =>
      thread === undefined
        ? thread
        : {
            ...thread,
            messages: thread.messages.map((message) =>
              message.id === mark.message_id
                ? { ...message, helpful_at: mark.helpful_at }
                : message,
            ),
          },
    )
  }

  const mark = useMutation({
    mutationFn: (messageId: number) => markHelpful(messageId),
    onSuccess: applyToThread,
  })

  const unmark = useMutation({
    mutationFn: (messageId: number) => clearHelpful(messageId),
    onSuccess: applyToThread,
  })

  return { mark, unmark }
}
