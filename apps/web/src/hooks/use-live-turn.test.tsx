// @vitest-environment jsdom
/**
 * The live Turn's recovery paths, against a stream that stops speaking and an
 * API that is down for a while.
 */

import type { ReactNode } from "react"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { act, renderHook } from "@testing-library/react"
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"

import { AlphaRefusalError } from "@/lib/alpha"
import { ApiUnavailableError } from "@/lib/connection-status"
import type { Turn } from "@/lib/alpha-desk/types"

const api = vi.hoisted(() => ({
  cancelTurn: vi.fn(),
  createTurn: vi.fn(),
  fetchTurn: vi.fn(),
  newTurnId: vi.fn(() => "turn-new"),
  turnStreamUrl: (id: string) => `/api/alpha-desk/turns/${id}/events`,
}))
vi.mock("@/lib/alpha-desk/api", () => api)
vi.mock("@/lib/alpha-desk/answer-alert", () => ({ announceSettledTurn: vi.fn() }))

import { probeBackoffMs, useLiveTurn } from "./use-live-turn"

/** An `EventSource` the test drives by hand. */
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
  emit(type: string, data?: unknown) {
    const event = { data: JSON.stringify(data) } as MessageEvent<string>
    for (const listener of this.listeners.get(type) ?? []) listener(event)
  }
}

function openStreams(): FakeEventSource[] {
  return FakeEventSource.instances.filter((source) => !source.closed)
}

function turn(status: Turn["status"], id = "turn-1"): Turn {
  return {
    id,
    thread_id: "thread-1",
    status,
    terminal_reason: status === "cancelled" ? "cancelled_by_user" : null,
    request_message_id: 1,
    response_message_id: status === "running" ? null : 2,
    retry_of_turn_id: null,
    last_event_seq: 0,
    cancel_requested: false,
    started_at: "2026-09-27T08:00:00Z",
    finished_at: null,
  }
}

function mount(threadId: string | null = "thread-1") {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  const wrapper = ({ children }: { children: ReactNode }) => (
    <QueryClientProvider client={client}>{children}</QueryClientProvider>
  )
  return renderHook(({ thread }) => useLiveTurn(thread), {
    wrapper,
    initialProps: { thread: threadId },
  })
}

beforeEach(() => {
  vi.useFakeTimers()
  FakeEventSource.instances = []
  vi.stubGlobal("EventSource", FakeEventSource)
})

afterEach(() => {
  vi.useRealTimers()
  vi.unstubAllGlobals()
  vi.clearAllMocks()
})

describe("the probe backoff", () => {
  it("widens from two seconds and stops widening at thirty", () => {
    expect([0, 1, 2, 3, 4, 5, 9].map(probeBackoffMs)).toEqual([
      2000, 4000, 8000, 16000, 30000, 30000, 30000,
    ])
  })
})

describe("a stream that stops speaking", () => {
  it("keeps asking while the API is down, then settles on the Turn's real ending", async () => {
    api.fetchTurn
      .mockRejectedValueOnce(new ApiUnavailableError(undefined, undefined))
      .mockRejectedValueOnce(new AlphaRefusalError(401, null, "Not authenticated"))
      .mockResolvedValueOnce(turn("complete"))
    const { result } = mount()
    act(() => result.current.attach("turn-1", "thread-1"))
    const [stream] = openStreams()

    act(() => stream.emit("error"))
    await act(() => vi.advanceTimersByTimeAsync(4000)) // first probe: unreachable
    expect(api.fetchTurn).toHaveBeenCalledTimes(1)
    expect(result.current.state.phase).toBe("starting")

    await act(() => vi.advanceTimersByTimeAsync(2000)) // second: 401
    expect(api.fetchTurn).toHaveBeenCalledTimes(2)
    await act(() => vi.advanceTimersByTimeAsync(3999)) // backoff widened to 4s
    expect(api.fetchTurn).toHaveBeenCalledTimes(2)
    await act(() => vi.advanceTimersByTimeAsync(1))
    expect(api.fetchTurn).toHaveBeenCalledTimes(3)

    expect(result.current.state.phase).toBe("completed")
    expect(result.current.state.messageId).toBe(2)
  })

  it("reopens the stream when the probe finds the Turn still running", async () => {
    api.fetchTurn.mockResolvedValueOnce(turn("running"))
    const { result } = mount()
    act(() => result.current.attach("turn-1", "thread-1"))
    const [first] = openStreams()

    act(() => first.emit("error"))
    await act(() => vi.advanceTimersByTimeAsync(4000))

    expect(first.closed).toBe(true)
    expect(openStreams()).toHaveLength(1)
    expect(openStreams()[0]).not.toBe(first)
  })

  it("stops asking once the stream speaks again", async () => {
    api.fetchTurn.mockRejectedValue(new ApiUnavailableError(undefined, undefined))
    const { result } = mount()
    act(() => result.current.attach("turn-1", "thread-1"))
    const [stream] = openStreams()

    act(() => stream.emit("error"))
    await act(() => vi.advanceTimersByTimeAsync(4000))
    expect(api.fetchTurn).toHaveBeenCalledTimes(1)
    act(() =>
      stream.emit("content.delta", {
        version: 1,
        seq: 1,
        type: "content.delta",
        turn_id: "turn-1",
        data: { text: "một" },
      }),
    )
    await act(() => vi.advanceTimersByTimeAsync(60_000))
    expect(api.fetchTurn).toHaveBeenCalledTimes(1)
  })

  it("stops asking when the hook resets", async () => {
    api.fetchTurn.mockRejectedValue(new ApiUnavailableError(undefined, undefined))
    const { result } = mount()
    act(() => result.current.attach("turn-1", "thread-1"))
    act(() => openStreams()[0].emit("error"))
    await act(() => vi.advanceTimersByTimeAsync(4000))
    act(() => result.current.reset())
    await act(() => vi.advanceTimersByTimeAsync(60_000))
    expect(api.fetchTurn).toHaveBeenCalledTimes(1)
  })
})

describe("stopping a Turn", () => {
  it("settles from the cancel response when the Turn had already ended", async () => {
    api.cancelTurn.mockResolvedValue(turn("cancelled"))
    const { result } = mount()
    act(() => result.current.attach("turn-1", "thread-1"))

    await act(() => result.current.cancel())

    expect(result.current.state.phase).toBe("cancelled")
    expect(openStreams()).toHaveLength(0)
  })

  it("waits for the stream when the cancel was only requested", async () => {
    api.cancelTurn.mockResolvedValue({ ...turn("running"), cancel_requested: true })
    const { result } = mount()
    act(() => result.current.attach("turn-1", "thread-1"))

    await act(() => result.current.cancel())

    expect(result.current.state.phase).toBe("cancelling")
  })
})

describe("a create whose answer was lost", () => {
  it("attaches to the Turn the lost request committed instead of creating another", async () => {
    api.createTurn.mockRejectedValueOnce(new ApiUnavailableError(undefined, undefined))
    api.fetchTurn.mockResolvedValueOnce(turn("running", "turn-new"))
    const { result } = mount()

    let sent!: Promise<void>
    act(() => {
      sent = result.current.send({ text: "STB?" })
    })
    await act(() => vi.advanceTimersByTimeAsync(1000))
    await act(() => sent)

    expect(api.createTurn).toHaveBeenCalledTimes(1)
    expect(api.fetchTurn).toHaveBeenCalledWith("turn-new")
    expect(result.current.refusal).toBeNull()
    expect(result.current.state.subscribable).toBe(true)
  })

  it("creates again under the same id when the Turn is not there", async () => {
    api.createTurn
      .mockRejectedValueOnce(new TypeError("Failed to fetch"))
      .mockResolvedValueOnce({ ...turn("admitted", "turn-new"), created: true })
    api.fetchTurn.mockRejectedValueOnce(new AlphaRefusalError(404, null, "Turn not found"))
    const { result } = mount()

    let sent!: Promise<void>
    act(() => {
      sent = result.current.send({ text: "STB?" })
    })
    await act(() => vi.advanceTimersByTimeAsync(1000))
    await act(() => sent)

    expect(api.createTurn).toHaveBeenCalledTimes(2)
    expect(api.createTurn.mock.calls[1][0].turnId).toBe("turn-new")
    expect(result.current.refusal).toBeNull()
  })

  it("gives up after its retries and says so", async () => {
    api.createTurn.mockRejectedValue(new ApiUnavailableError(undefined, undefined))
    api.fetchTurn.mockRejectedValue(new ApiUnavailableError(undefined, undefined))
    const { result } = mount()

    let sent!: Promise<void>
    act(() => {
      sent = result.current.send({ text: "STB?" })
    })
    await act(() => vi.advanceTimersByTimeAsync(10_000))
    await act(() => sent)

    expect(api.createTurn).toHaveBeenCalledTimes(3)
    expect(result.current.refusal).toBeInstanceOf(ApiUnavailableError)
    expect(result.current.state.phase).toBe("idle")
  })

  it("does not retry a refusal", async () => {
    api.createTurn.mockRejectedValue(new AlphaRefusalError(429, "user_active_turn", "busy"))
    const { result } = mount()

    await act(() => result.current.send({ text: "STB?" }))

    expect(api.createTurn).toHaveBeenCalledTimes(1)
    expect(api.fetchTurn).not.toHaveBeenCalled()
  })
})

describe("a question asked in another Thread while a Turn runs", () => {
  it("puts the running Turn back when the account's one slot refuses the new one", async () => {
    api.createTurn.mockRejectedValue(new AlphaRefusalError(429, "user_active_turn", "busy"))
    const { result, rerender } = mount("thread-1")
    act(() => result.current.attach("turn-1", "thread-1"))
    rerender({ thread: "thread-2" })

    await act(() => result.current.send({ text: "VCB?" }))

    expect(result.current.refusal?.message).toBe("busy")
    expect(result.current.state.turnId).toBe("turn-1")
    expect(result.current.state.threadId).toBe("thread-1")
    expect(openStreams()).toHaveLength(1)
    expect(openStreams()[0].url).toContain("turn-1")
  })

  it("sends the first question of a new Thread to the Thread it names", async () => {
    api.createTurn.mockResolvedValue({ ...turn("admitted", "turn-new"), created: true })
    const { result } = mount("thread-open")

    await act(() => result.current.send({ text: "STB?", threadId: "thread-created" }))

    expect(api.createTurn.mock.calls[0][0].threadId).toBe("thread-created")
    expect(result.current.state.threadId).toBe("thread-created")
  })
})
