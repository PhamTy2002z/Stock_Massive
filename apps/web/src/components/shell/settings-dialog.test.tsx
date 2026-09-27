// @vitest-environment jsdom
/**
 * What Settings offers, and that every row in it does what it says.
 *
 * *An allowance is drawn in the state it is actually in.* Loading, unlimited and
 * metered are three different facts, and an unlimited ceiling drawn as a full
 * meter would tell a reader they had run out of something they cannot.
 *
 * *A write sends what changed and nothing else.* The profile endpoint changes
 * only the keys it is sent, so a field that sent the whole profile would
 * overwrite a second field saved a moment earlier with its stale value.
 *
 * *A destructive action asks twice, in place.* One press arms it, the second
 * acts, and nothing is sent in between.
 */

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"

import type { AuthUser } from "@/hooks/use-auth"
import type { MemoryFactPage, Usage } from "@/lib/alpha-desk/types"
import { queryKeys } from "@/lib/query-keys"

const fetchUsage = vi.fn<() => Promise<Usage>>()
const listMemoryFacts = vi.fn<(offset?: number, limit?: number) => Promise<MemoryFactPage>>()
const deleteMemoryFact = vi.fn<(id: number) => Promise<void>>()
const deleteAllMemoryFacts = vi.fn<() => Promise<{ deleted: number }>>()
const deleteAllThreads = vi.fn<() => Promise<{ deleted: number }>>()
const updateProfileAction = vi.fn()
const changePasswordAction = vi.fn()
const logoutAllAction = vi.fn()
const logoutAction = vi.fn()
const newThread = vi.fn()

vi.mock("@/lib/alpha-desk/api", () => ({
  fetchUsage: () => fetchUsage(),
  listMemoryFacts: (offset?: number, limit?: number) => listMemoryFacts(offset, limit),
  deleteMemoryFact: (id: number) => deleteMemoryFact(id),
  deleteAllMemoryFacts: () => deleteAllMemoryFacts(),
  deleteAllThreads: () => deleteAllThreads(),
  listThreads: async () => ({ threads: [] }),
  fetchThread: async () => ({}),
}))
vi.mock("@/app/(auth)/account-actions", () => ({
  updateProfileAction: (patch: unknown) => updateProfileAction(patch),
  changePasswordAction: (input: unknown) => changePasswordAction(input),
  logoutAllAction: () => logoutAllAction(),
}))
vi.mock("@/app/(auth)/actions", () => ({ logoutAction: () => logoutAction() }))
vi.mock("./shell-state", async (importOriginal) => ({
  SIGNAL_DESK_PAUSED: (await importOriginal<typeof import("./shell-state")>()).SIGNAL_DESK_PAUSED,
  useShell: () => ({ dispatch: () => {} }),
}))
vi.mock("./desk-state", () => ({ useDesk: () => ({ newThread }) }))

import { readPreferences, writePreferences } from "@/lib/alpha-desk/preferences"

import { SettingsDialog } from "./settings-dialog"
import { SIGNAL_DESK_PAUSED } from "./shell-state"

const USER: AuthUser = {
  id: 1,
  email: "investor@example.com",
  full_name: "Investor",
  is_active: true,
  created_at: null,
  preferences: {
    nickname: null,
    investing_style: null,
    custom_instructions: null,
    memory_enabled: true,
  },
}

function allowance(used: number, limit: number | null, resetsAt: string | null = null) {
  return { used, limit, resets_at: resetsAt }
}

function usage(overrides: Partial<Usage> = {}): Usage {
  return {
    as_of: "2026-08-28T08:00:00Z",
    turns_today: allowance(0, 20),
    spend_today_micro_usd: allowance(0, 3_000_000),
    spend_rolling_30d_micro_usd: allowance(0, 15_000_000),
    ...overrides,
  }
}

function fact(id: number, title: string) {
  return {
    id,
    title,
    body: `Content: ${title}`,
    symbol: "VNM",
    source_url: "https://example.com/article",
    source_name: "Source",
    as_of: "2026-09-01T03:00:00Z",
    created_at: "2026-09-02T03:00:00Z",
  }
}

function open() {
  const client = new QueryClient({
    defaultOptions: { queries: { retry: false }, mutations: { retry: false } },
  })
  // Seeded as the session read would leave it, so `useAuth` answers at once.
  client.setQueryData(queryKeys.currentUser, USER)
  return render(
    <QueryClientProvider client={client}>
      <SettingsDialog />
    </QueryClientProvider>,
  )
}

/** Move the rail to a pane by its label, the way a reader does. */
function goTo(label: string) {
  fireEvent.click(screen.getByRole("button", { name: label }))
}

beforeEach(() => {
  vi.clearAllMocks()
  fetchUsage.mockResolvedValue(usage())
  listMemoryFacts.mockResolvedValue({ items: [], total: 0 })
  updateProfileAction.mockImplementation(async (patch: { full_name?: string; preferences?: object }) => ({
    ok: true,
    value: {
      ...USER,
      ...(patch.full_name ? { full_name: patch.full_name } : {}),
      preferences: { ...USER.preferences, ...patch.preferences },
    },
  }))
})

afterEach(() => {
  cleanup()
  vi.unstubAllGlobals()
  delete document.documentElement.dataset.motion
})

describe("the rail", () => {
  it("offers every pane", () => {
    open()

    for (const label of ["General", "Account", "Memory", "Privacy", "Usage"]) {
      expect(screen.getByRole("button", { name: label })).toBeInTheDocument()
    }
  })

  it("finds a pane by a row inside it", () => {
    open()

    fireEvent.change(screen.getByLabelText("Search settings"), { target: { value: "password" } })

    const rail = screen.getByRole("navigation", { name: "Settings sections" })
    const labels = Array.from(rail.querySelectorAll("button")).map((button) => button.textContent)
    expect(labels).toEqual(["Account"])
  })

  it("filters to nothing rather than showing a stale pane", () => {
    open()

    fireEvent.change(screen.getByLabelText("Search settings"), {
      target: { value: "no such setting" },
    })

    expect(screen.getByText("No matches.")).toBeInTheDocument()
  })

  it("draws no row that promises something unbuilt", async () => {
    open()

    for (const label of ["General", "Account", "Memory", "Privacy"]) {
      goTo(label)
      expect(screen.queryByText("Coming soon")).toBeNull()
    }
    goTo("General")
    // The chart cannot follow a swapped palette, so the row is not offered.
    expect(screen.queryByText("Up/down colors")).toBeNull()
  })
})

describe("the allowance", () => {
  it("draws a metered ceiling with what is left", async () => {
    fetchUsage.mockResolvedValue(usage({ turns_today: allowance(7, 20) }))
    open()
    goTo("Usage")

    const meter = await screen.findByRole("meter", { name: /Questions today/ })

    expect(meter).toHaveAttribute("aria-valuenow", "7")
    expect(meter).toHaveAttribute("aria-valuemax", "20")
    expect(screen.getByText("13 left")).toBeInTheDocument()
  })

  it("says unlimited rather than drawing a meter against nothing", async () => {
    fetchUsage.mockResolvedValue(usage({ turns_today: allowance(41, null) }))
    open()
    goTo("Usage")

    expect(await screen.findByText("41 · unlimited")).toBeInTheDocument()
    expect(screen.queryByRole("meter", { name: /Questions today/ })).toBeNull()
  })

  it("says when a spent allowance frees rather than only that it is spent", async () => {
    fetchUsage.mockResolvedValue(
      usage({ turns_today: allowance(20, 20, "2026-08-28T17:00:00Z") }),
    )
    open()
    goTo("Usage")

    // 17:00Z is midnight in Ho Chi Minh City, which is the reset the API means.
    expect(await screen.findByText(/Used up · opens again/)).toBeInTheDocument()
  })

  it("does not round a real charge down to nothing", async () => {
    fetchUsage.mockResolvedValue({
      ...usage(),
      spend_today_micro_usd: allowance(4_000, 3_000_000),
    })
    open()
    goTo("Usage")

    expect(await screen.findByText(/<\$0\.01/)).toBeInTheDocument()
  })

  it("offers a retry rather than an empty panel when the read fails", async () => {
    fetchUsage.mockRejectedValue(new Error("upstream is down"))
    open()
    goTo("Usage")

    expect(await screen.findByRole("button", { name: "Retry" })).toBeInTheDocument()
  })
})

describe("motion", () => {
  it("stills the document when the reader chooses Reduced, and releases it again", () => {
    open()

    fireEvent.click(screen.getByRole("radio", { name: "Reduced" }))
    expect(document.documentElement.dataset.motion).toBe("reduced")
    expect(readPreferences().motion).toBe("reduced")

    fireEvent.click(within(screen.getByRole("radiogroup", { name: "Motion" })).getByRole("radio", { name: "System" }))
    expect(document.documentElement.hasAttribute("data-motion")).toBe(false)
    expect(readPreferences().motion).toBe("system")
  })
})

describe("notifications", () => {
  it("stays off when the browser refuses permission, and says so", async () => {
    const requestPermission = vi.fn().mockResolvedValue("denied")
    vi.stubGlobal("Notification", { permission: "default", requestPermission })
    open()

    const toggle = screen.getByRole("switch", { name: "Notify when an answer is ready" })
    await waitFor(() => expect(toggle).not.toBeDisabled())
    fireEvent.click(toggle)

    expect(await screen.findByText(/blocking notifications/)).toBeInTheDocument()
    expect(requestPermission).toHaveBeenCalledTimes(1)
    expect(toggle).toHaveAttribute("aria-checked", "false")
    expect(readPreferences().notifyOnAnswer).toBe(false)
  })

  it("turns on once the browser grants permission", async () => {
    vi.stubGlobal("Notification", {
      permission: "default",
      requestPermission: vi.fn().mockResolvedValue("granted"),
    })
    open()

    const toggle = screen.getByRole("switch", { name: "Notify when an answer is ready" })
    await waitFor(() => expect(toggle).not.toBeDisabled())
    fireEvent.click(toggle)

    await waitFor(() => expect(toggle).toHaveAttribute("aria-checked", "true"))
    expect(readPreferences().notifyOnAnswer).toBe(true)
  })
})

describe("the profile", () => {
  it("saves the name on blur, sending that key alone", async () => {
    open()
    goTo("Account")

    const name = screen.getByRole("textbox", { name: "Full name" })
    fireEvent.change(name, { target: { value: "  Jane Smith  " } })
    fireEvent.blur(name)

    await waitFor(() => expect(updateProfileAction).toHaveBeenCalledTimes(1))
    expect(updateProfileAction).toHaveBeenCalledWith({ full_name: "Jane Smith" })
  })

  it("sends nothing when the field is left as it was, or emptied", () => {
    open()
    goTo("Account")

    const name = screen.getByRole("textbox", { name: "Full name" })
    fireEvent.blur(name)
    fireEvent.change(name, { target: { value: "   " } })
    fireEvent.blur(name)

    expect(updateProfileAction).not.toHaveBeenCalled()
    expect(name).toHaveValue("Investor")
  })

  it("puts the saved name back when the write is refused", async () => {
    updateProfileAction.mockResolvedValue({ ok: false, status: 422, error: "invalid" })
    open()
    goTo("Account")

    const name = screen.getByRole("textbox", { name: "Full name" })
    fireEvent.change(name, { target: { value: "New name" } })
    fireEvent.keyDown(name, { key: "Enter" })

    await waitFor(() => expect(name).toHaveValue("Investor"))
  })

  it("sends only the investing style when it changes", async () => {
    open()
    goTo("Account")

    fireEvent.change(screen.getByRole("combobox", { name: "Investing style" }), {
      target: { value: "growth" },
    })

    await waitFor(() =>
      expect(updateProfileAction).toHaveBeenCalledWith({
        preferences: { investing_style: "growth" },
      }),
    )
  })

  it("offers Save only once the instructions change, and sends only them", async () => {
    open()
    goTo("Account")

    expect(screen.queryByRole("button", { name: "Save" })).toBeNull()
    fireEvent.change(screen.getByRole("textbox", { name: "Custom instructions" }), {
      target: { value: "Be concise." },
    })
    expect(screen.getByText("11/1500")).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Save" }))

    await waitFor(() =>
      expect(updateProfileAction).toHaveBeenCalledWith({
        preferences: { custom_instructions: "Be concise." },
      }),
    )
  })
})

describe("security", () => {
  it("keeps the account's real email readable on the pane that holds it", () => {
    open()
    goTo("Account")

    const pane = screen.getByRole("region", { name: "Account" })
    expect(within(pane).getByText("investor@example.com")).toBeInTheDocument()
  })

  it("checks a password change before sending it", () => {
    open()
    goTo("Account")

    fireEvent.click(screen.getByRole("button", { name: "Change password" }))
    fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "old-12345" } })
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "new-12345" } })
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "diff-123" } })
    fireEvent.click(screen.getByRole("button", { name: "Change password" }))

    expect(screen.getByText("The passwords don't match.")).toBeInTheDocument()
    expect(changePasswordAction).not.toHaveBeenCalled()
  })

  it("says the current password is wrong when the API says so", async () => {
    changePasswordAction.mockResolvedValue({ ok: false, status: 400, error: "Current password is incorrect" })
    open()
    goTo("Account")

    fireEvent.click(screen.getByRole("button", { name: "Change password" }))
    fireEvent.change(screen.getByLabelText("Current password"), { target: { value: "wrong-12345" } })
    fireEvent.change(screen.getByLabelText("New password"), { target: { value: "new-12345" } })
    fireEvent.change(screen.getByLabelText("Confirm new password"), { target: { value: "new-12345" } })
    fireEvent.click(screen.getByRole("button", { name: "Change password" }))

    expect(await screen.findByText("That current password is incorrect")).toBeInTheDocument()
    expect(changePasswordAction).toHaveBeenCalledWith({
      current_password: "wrong-12345",
      new_password: "new-12345",
    })
  })

  it("signs out everywhere only on the second press, then signs this browser out", async () => {
    logoutAllAction.mockResolvedValue({ ok: true, value: undefined })
    open()
    goTo("Account")

    fireEvent.click(screen.getByRole("button", { name: "Sign out" }))
    expect(logoutAllAction).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole("button", { name: "Confirm sign out" }))
    await waitFor(() => expect(logoutAllAction).toHaveBeenCalledTimes(1))
    await waitFor(() => expect(logoutAction).toHaveBeenCalledTimes(1))
  })
})

describe("memory", () => {
  it("lists what was remembered, with its source and dates", async () => {
    listMemoryFacts.mockResolvedValue({ items: [fact(7, "VNM dividend")], total: 1 })
    open()
    goTo("Memory")

    expect(await screen.findByText("VNM dividend")).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Remembered (1)" })).toBeInTheDocument()
    const source = screen.getByRole("link", { name: "Source" })
    expect(source).toHaveAttribute("rel", "noopener noreferrer")
    expect(source).toHaveAttribute("target", "_blank")
    expect(screen.getByText("As of 01/09/2026")).toBeInTheDocument()
  })

  it("deletes one note through the API and drops it from the list", async () => {
    listMemoryFacts.mockResolvedValue({ items: [fact(7, "VNM dividend"), fact(8, "Foreign room")], total: 2 })
    deleteMemoryFact.mockResolvedValue(undefined)
    open()
    goTo("Memory")

    await screen.findByText("VNM dividend")
    fireEvent.click(screen.getAllByRole("button", { name: "Delete memory" })[0])

    await waitFor(() => expect(screen.queryByText("VNM dividend")).toBeNull())
    expect(deleteMemoryFact).toHaveBeenCalledWith(7)
    expect(screen.getByText("Foreign room")).toBeInTheDocument()
    expect(screen.getByRole("heading", { name: "Remembered (1)" })).toBeInTheDocument()
  })

  it("says so when there is nothing remembered", async () => {
    open()
    goTo("Memory")

    expect(await screen.findByText(/No memories yet/)).toBeInTheDocument()
  })

  it("asks twice before forgetting everything", async () => {
    listMemoryFacts.mockResolvedValue({ items: [fact(7, "VNM dividend")], total: 1 })
    deleteAllMemoryFacts.mockResolvedValue({ deleted: 1 })
    open()
    goTo("Memory")
    await screen.findByText("VNM dividend")

    fireEvent.click(screen.getByRole("button", { name: "Delete all" }))
    expect(deleteAllMemoryFacts).not.toHaveBeenCalled()

    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }))
    await waitFor(() => expect(deleteAllMemoryFacts).toHaveBeenCalledTimes(1))
    expect(await screen.findByText(/No memories yet/)).toBeInTheDocument()
  })

  it("can be taken back between the two presses", async () => {
    listMemoryFacts.mockResolvedValue({ items: [fact(7, "VNM dividend")], total: 1 })
    open()
    goTo("Memory")
    await screen.findByText("VNM dividend")

    fireEvent.click(screen.getByRole("button", { name: "Delete all" }))
    fireEvent.click(screen.getByRole("button", { name: "Cancel" }))

    expect(screen.getByRole("button", { name: "Delete all" })).toBeInTheDocument()
    expect(deleteAllMemoryFacts).not.toHaveBeenCalled()
  })

  it("switches memory off on the account", async () => {
    open()
    goTo("Memory")

    fireEvent.click(screen.getByRole("switch", { name: "Allow memory" }))

    await waitFor(() =>
      expect(updateProfileAction).toHaveBeenCalledWith({ preferences: { memory_enabled: false } }),
    )
  })
})

describe("the history", () => {
  it("deletes every conversation on the second press and opens a fresh one", async () => {
    deleteAllThreads.mockResolvedValue({ deleted: 4 })
    open()
    goTo("Privacy")

    fireEvent.click(screen.getByRole("button", { name: "Delete all" }))
    expect(deleteAllThreads).not.toHaveBeenCalled()
    fireEvent.click(screen.getByRole("button", { name: "Confirm delete" }))

    await waitFor(() => expect(newThread).toHaveBeenCalledTimes(1))
    expect(deleteAllThreads).toHaveBeenCalledTimes(1)
  })
})

const DEFAULT_DESK = "Signal Desk is the default mode"

describe("how a new conversation opens", () => {
  it.runIf(SIGNAL_DESK_PAUSED)("is not offered while the desk is paused", () => {
    open()

    expect(screen.queryByRole("heading", { name: "Conversation" })).toBeNull()
  })

  it.skipIf(SIGNAL_DESK_PAUSED)("writes the default without touching anything else", async () => {
    writePreferences({ signalDeskByDefault: false, chatWidth: 640 })
    open()

    fireEvent.click(screen.getByRole("switch", { name: DEFAULT_DESK }))

    await waitFor(() => expect(readPreferences().signalDeskByDefault).toBe(true))
    expect(readPreferences().chatWidth).toBe(640)
  })
})
