"use client"

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query"

import {
  createThread,
  fetchThread,
  flagMessage,
  listThreads,
  unflagMessage,
} from "@/lib/alpha-desk/api"
import type {
  FlagReason,
  MessageFlag,
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
 * Free-roaming and untitled: a Thread is never owned by a symbol, and titling
 * it from the first question would make the deep-linked `?symbol=` case look
 * like a symbol-scoped conversation, which is exactly what it is not.
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

  return { flag, unflag }
}
