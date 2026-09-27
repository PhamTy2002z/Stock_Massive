// @vitest-environment jsdom
/**
 * The desk against a Turn that is streaming: which Thread owns the controls,
 * where a first question goes, and which regions redraw on every word.
 */

import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, cleanup, render, waitFor } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import type { Thread, ThreadDetail } from "@/lib/alpha-desk/types"
import { queryKeys } from "@/lib/query-keys"

const api = vi.hoisted(() => ({
  cancelTurn: vi.fn(),
  createThread: vi.fn(),
  createTurn: vi.fn(),
  fetchThread: vi.fn(),
  fetchTurn: vi.fn(),
  flagMessage: vi.fn(),
  newTurnId: vi.fn(() => "turn-1"),
  turnStreamUrl: (id: string) => `/api/alpha-desk/turns/${id}/events`,
  uploadAttachment: vi.fn(),
}))
vi.mock("@/lib/alpha-desk/api", () => api)
vi.mock("@/lib/alpha-desk/answer-alert", () => ({ announceSettledTurn: vi.fn() }))
vi.mock("@/hooks/use-capabilities", () => ({ useCapabilities: () => ({ vision: true }) }))
vi.mock("next/navigation", () => ({
  useRouter: () => ({ replace: vi.fn() }),
  useSearchParams: () => new URLSearchParams(),
}))

import { DeskProvider, useDesk, useDeskTranscript } from "./desk-state"
import { ShellProvider } from "./shell-state"

class FakeEventSource {
  static instances: FakeEventSource[] = []
  listeners = new Map<string, Set<(event: MessageEvent<string>) => void>>()
  closed = false
  constructor(public url: string) {
    FakeEventSource.instances.push(this)
  }
  addEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    if (!this.listeners.has(type)) this.listeners.set(type, new Set())
    this.listeners.get(type)?.add(listener)
  }
  removeEventListener(type: string, listener: (event: MessageEvent<string>) => void) {
    this.listeners.get(type)?.delete(listener)
  }
  close() {
    this.closed = true
  }
  emit(type: string, data: unknown) {
    const event = { data: JSON.stringify(data) } as MessageEvent<string>
    for (const listener of this.listeners.get(type) ?? []) listener(event)
  }
}

function thread(id: string): Thread {
  return {
    id,
    title: null,
    symbols: [],
    pinned_at: null,
    created_at: "2026-09-27T08:00:00Z",
    updated_at: "2026-09-27T08:00:00Z",
  } as unknown as Thread
}

function detail(id: string, messages: ThreadDetail["messages"] = []): ThreadDetail {
  return { ...thread(id), messages }
}

let desk: ReturnType<typeof useDesk>
let controlRenders = 0
let transcriptRenders = 0

function ControlsProbe() {
  desk = useDesk()
  controlRenders += 1
  return null
}

function TranscriptProbe() {
  useDeskTranscript()
  transcriptRenders += 1
  return null
}

let queryClient: QueryClient

function mount() {
  queryClient = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={queryClient}>
      <ShellProvider>
        <DeskProvider>{children}</DeskProvider>
      </ShellProvider>
    </QueryClientProvider>
  )
  render(
    <>
      <ControlsProbe />
      <TranscriptProbe />
    </>,
    { wrapper },
  )
}

function deferred<T>() {
  let resolve!: (value: T) => void
  const promise = new Promise<T>((done) => {
    resolve = done
  })
  return { promise, resolve }
}

/** Open a Thread and start a Turn in it, streaming. */
async function runTurnIn(threadId: string) {
  act(() => desk.openThread(threadId))
  await act(async () => desk.submit("STB?"))
  await waitFor(() => expect(FakeEventSource.instances).toHaveLength(1))
  return FakeEventSource.instances[0]
}

beforeEach(() => {
  window.sessionStorage.clear()
  window.localStorage.clear()
  FakeEventSource.instances = []
  vi.stubGlobal("EventSource", FakeEventSource)
  controlRenders = 0
  transcriptRenders = 0
  api.fetchThread.mockImplementation((id: string) => Promise.resolve(detail(id)))
  api.createTurn.mockResolvedValue({ id: "turn-1", created: true })
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe("the Thread that owns the running Turn", () => {
  it("offers Stop only in the Thread the Turn is running in", async () => {
    mount()
    const stream = await runTurnIn("thread-1")
    expect(desk.canCancel).toBe(true)

    act(() => desk.openThread("thread-2"))
    expect(desk.canCancel).toBe(false)
    expect(stream.closed).toBe(false)

    act(() => desk.openThread("thread-1"))
    expect(desk.canCancel).toBe(true)
  })

  it("keeps a running Turn watched through a new conversation, and marks its Thread stale", async () => {
    mount()
    const stream = await runTurnIn("thread-1")
    await waitFor(() =>
      expect(queryClient.getQueryState(queryKeys.thread("thread-1"))?.status).toBe("success"),
    )

    act(() => desk.newThread())

    expect(desk.threadId).toBeNull()
    expect(desk.canCancel).toBe(false)
    expect(stream.closed).toBe(false)
    expect(queryClient.getQueryState(queryKeys.thread("thread-1"))?.isInvalidated).toBe(true)
  })
})

describe("the first question of a new Thread", () => {
  it("goes to the Thread its create returned, even after the reader opened another", async () => {
    const created = deferred<Thread>()
    api.createThread.mockReturnValue(created.promise)
    mount()

    act(() => desk.submit("STB?"))
    act(() => desk.openThread("thread-z"))
    await act(async () => created.resolve(thread("thread-created")))

    await waitFor(() => expect(api.createTurn).toHaveBeenCalledTimes(1))
    expect(api.createTurn.mock.calls[0][0].threadId).toBe("thread-created")
    // The reader stays where they went.
    expect(desk.threadId).toBe("thread-z")
  })
})

describe("a verdict that lands after the reader moved on", () => {
  it("patches the Thread it was made in", async () => {
    const message = {
      id: 7,
      seq: 2,
      role: "assistant",
      content: { text: "Trả lời." },
      flagged_reason: null,
      flagged_at: null,
      helpful_at: null,
    } as unknown as ThreadDetail["messages"][number]
    api.fetchThread.mockImplementation((id: string) =>
      Promise.resolve(detail(id, id === "thread-a" ? [message] : [])),
    )
    const flagged = deferred<{ message_id: number; flagged_reason: string; flagged_at: string }>()
    api.flagMessage.mockReturnValue(flagged.promise)
    mount()

    act(() => desk.openThread("thread-a"))
    await waitFor(() =>
      expect(queryClient.getQueryData<ThreadDetail>(queryKeys.thread("thread-a"))).toBeDefined(),
    )
    act(() => desk.flag(7, "wrong_figure"))
    act(() => desk.openThread("thread-b"))
    await act(async () =>
      flagged.resolve({ message_id: 7, flagged_reason: "wrong_figure", flagged_at: "now" }),
    )

    await waitFor(() =>
      expect(
        queryClient.getQueryData<ThreadDetail>(queryKeys.thread("thread-a"))?.messages[0]
          .flagged_reason,
      ).toBe("wrong_figure"),
    )
  })
})

describe("what redraws while an answer streams", () => {
  it("redraws the transcript on every event and the controls not at all", async () => {
    mount()
    const stream = await runTurnIn("thread-1")
    stream.emit("turn.snapshot", {
      version: 1,
      seq: 0,
      type: "turn.snapshot",
      turn_id: "turn-1",
      data: { status: "running", through_seq: 0, text: "" },
    })
    await act(async () => {})
    const controlsBefore = controlRenders
    const transcriptBefore = transcriptRenders

    for (let seq = 1; seq <= 20; seq += 1) {
      act(() =>
        stream.emit("content.delta", {
          version: 1,
          seq,
          type: "content.delta",
          turn_id: "turn-1",
          data: { text: `từ${seq} ` },
        }),
      )
    }

    expect(transcriptRenders - transcriptBefore).toBeGreaterThanOrEqual(20)
    expect(controlRenders - controlsBefore).toBe(0)
  })
})
