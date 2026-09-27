// @vitest-environment jsdom
/** The composer's "+" › Kết nối flyout: what each row sends. */

import { afterEach, describe, expect, it, vi } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"

import { ShellProvider } from "@/components/shell/shell-state"
import { clearConnectorsPane, peekConnectorsPane } from "@/lib/connectors/open-pane"

import { ConnectorsMenu } from "./connectors-menu"
import { connector, connectorsState, json, stubFetch } from "./test-fixtures"

afterEach(() => {
  cleanup()
  clearConnectorsPane()
  vi.unstubAllGlobals()
})

function open() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ShellProvider>
        <ConnectorsMenu />
      </ShellProvider>
    </QueryClientProvider>,
  )
}

describe("the Kết nối flyout", () => {
  it("toggles a connector with a PATCH of enabled", async () => {
    const calls = stubFetch(connectorsState({ connectors: [connector()] }), () =>
      json(connector({ enabled: false })),
    )
    open()

    fireEvent.click(await screen.findByRole("menuitem", { name: "Kết nối" }))
    const row = screen.getByRole("menuitemcheckbox", { name: "Kho nội bộ" })
    expect(row).toHaveAttribute("aria-checked", "true")
    fireEvent.click(row)

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0]).toEqual({ method: "PATCH", path: "/connectors/c-1", body: { enabled: false } })
    await waitFor(() => expect(row).toHaveAttribute("aria-checked", "false"))
  })

  it("changes the tool access mode with a PUT of preferences, and marks the choice", async () => {
    const calls = stubFetch(connectorsState(), () => json({ tool_access: "preloaded" }))
    open()

    fireEvent.click(await screen.findByRole("menuitem", { name: "Kết nối" }))
    fireEvent.click(screen.getByRole("menuitem", { name: "Truy cập công cụ" }))
    const onDemand = screen.getByRole("menuitemradio", { name: /Nạp khi cần/ })
    const preloaded = screen.getByRole("menuitemradio", { name: /Nạp sẵn/ })
    expect(onDemand).toHaveAttribute("aria-checked", "true")
    expect(onDemand).toHaveTextContent("Ít phải nén hội thoại")
    fireEvent.click(preloaded)

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0]).toEqual({
      method: "PUT",
      path: "/connectors/preferences",
      body: { tool_access: "preloaded" },
    })
    await waitFor(() => expect(preloaded).toHaveAttribute("aria-checked", "true"))
  })

  it("asks Settings to open on the Kết nối pane", async () => {
    stubFetch(connectorsState(), () => json({}))
    open()

    fireEvent.click(await screen.findByRole("menuitem", { name: "Kết nối" }))
    fireEvent.click(screen.getByRole("menuitem", { name: "Quản lý kết nối" }))

    expect(peekConnectorsPane()).toEqual({ outcome: null, connectorId: null })
  })

  it("draws nothing while the feature is off", async () => {
    const calls = stubFetch(connectorsState({ enabled: false }), () => json({}))
    const view = open()

    await waitFor(() => expect(vi.mocked(fetch)).toHaveBeenCalled())
    expect(view.container).toBeEmptyDOMElement()
    expect(calls).toHaveLength(0)
  })
})
