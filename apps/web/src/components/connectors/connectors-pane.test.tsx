// @vitest-environment jsdom
/**
 * Settings › Connectors, against a stubbed `fetch` so each assertion is about
 * the request that actually leaves the browser: path, method and body.
 */

import { afterEach, describe, expect, it, vi } from "vitest"
import { QueryClient, QueryClientProvider } from "@tanstack/react-query"
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react"
import "@testing-library/jest-dom/vitest"

import { clearConnectorsPane, requestConnectorsPane } from "@/lib/connectors/open-pane"

import { ConnectorsPane } from "./connectors-pane"
import { connector, connectorsState, json, stubFetch, tool } from "./test-fixtures"

afterEach(() => {
  cleanup()
  clearConnectorsPane()
  vi.unstubAllGlobals()
  vi.restoreAllMocks()
})

function open() {
  const client = new QueryClient({ defaultOptions: { queries: { retry: false } } })
  return render(
    <QueryClientProvider client={client}>
      <ConnectorsPane />
    </QueryClientProvider>,
  )
}

describe("the table", () => {
  it("lists each connector with its kind, auth and status in words", async () => {
    stubFetch(
      connectorsState({
        connectors: [
          connector(),
          connector({ id: "c-2", name: "Calendar", source: "catalog", catalog_id: 3, auth_type: "oauth", status: "needs_auth" }),
        ],
      }),
      () => json({}),
    )
    open()

    const rows = await screen.findAllByRole("row")
    expect(within(rows[1]).getByText("Internal vault")).toBeInTheDocument()
    expect(within(rows[1]).getByText("Custom")).toBeInTheDocument()
    expect(within(rows[1]).getByText("Key")).toBeInTheDocument()
    expect(within(rows[1]).getByText("Connected")).toBeInTheDocument()
    expect(within(rows[2]).getByText("Catalog")).toBeInTheDocument()
    expect(within(rows[2]).getByText("OAuth")).toBeInTheDocument()
    expect(within(rows[2]).getByText("Needs sign-in")).toBeInTheDocument()
  })

  it("says plainly that the feature is off, and offers nothing to press", async () => {
    stubFetch(connectorsState({ enabled: false }), () => json({}))
    open()

    expect(await screen.findByText(/aren't enabled/)).toBeInTheDocument()
    expect(screen.queryByRole("button", { name: "Add" })).not.toBeInTheDocument()
  })
})

describe("adding", () => {
  it("adds a custom URL with a key, and opens the new connector", async () => {
    const added = connector({ id: "c-new", name: "Private server" })
    const calls = stubFetch(connectorsState(), () => json(added, 201))
    open()

    fireEvent.click(await screen.findByRole("button", { name: "Add" }))
    fireEvent.click(screen.getByRole("menuitem", { name: "Custom URL" }))
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Private server" } })
    fireEvent.change(screen.getByLabelText("MCP server URL"), {
      target: { value: "https://mcp.example.com/mcp" },
    })
    fireEvent.click(screen.getByRole("radio", { name: "Key" }))
    fireEvent.change(screen.getByLabelText("Key"), { target: { value: "s3cret" } })
    fireEvent.click(screen.getByRole("button", { name: "Add connector" }))

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0]).toEqual({
      method: "POST",
      path: "/connectors",
      body: {
        name: "Private server",
        url: "https://mcp.example.com/mcp",
        header_name: "Authorization",
        header_value: "s3cret",
      },
    })
    expect(await screen.findByRole("button", { name: "Your connectors" })).toBeInTheDocument()
  })

  it("does not offer a custom URL when this account may not add one", async () => {
    stubFetch(connectorsState({ custom_url_allowed: false }), () => json({}))
    open()

    fireEvent.click(await screen.findByRole("button", { name: "Add" }))
    expect(screen.getByRole("menuitem", { name: "From catalog" })).toBeInTheDocument()
    expect(screen.queryByRole("menuitem", { name: "Custom URL" })).not.toBeInTheDocument()
  })

  it("adds a catalog entry by its id", async () => {
    const entry = { id: 7, slug: "news", name: "Company news", description: "News", auth_type: "none" as const, trusted_data: false }
    const calls = stubFetch(connectorsState({ catalog: [entry] }), () =>
      json(connector({ id: "c-7", name: entry.name, source: "catalog", catalog_id: 7, auth_type: "none" }), 201),
    )
    open()

    fireEvent.click(await screen.findByRole("button", { name: "Add" }))
    fireEvent.click(screen.getByRole("menuitem", { name: "From catalog" }))
    fireEvent.click(await screen.findByRole("button", { name: "Add Company news" }))

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0]).toEqual({ method: "POST", path: "/connectors", body: { catalog_id: 7 } })
  })

  it("shows the refusal in words when the server refuses the URL", async () => {
    stubFetch(connectorsState(), () =>
      json({ detail: { reason: "url_refused", message: "private address" } }, 422),
    )
    open()

    fireEvent.click(await screen.findByRole("button", { name: "Add" }))
    fireEvent.click(screen.getByRole("menuitem", { name: "Custom URL" }))
    fireEvent.change(screen.getByLabelText("Name"), { target: { value: "Internal" } })
    fireEvent.change(screen.getByLabelText("MCP server URL"), { target: { value: "http://10.0.0.1/mcp" } })
    fireEvent.click(screen.getByRole("button", { name: "Add connector" }))

    expect(await screen.findByRole("alert")).toHaveTextContent("That server address was refused")
  })
})

describe("one connector", () => {
  const withTools = () =>
    connector({
      tools: [
        tool(),
        tool({
          name: "create_note",
          wire: "mcp__vault__create_note",
          title: "",
          effect: "write",
          action: "ask",
          allowed_actions: ["ask", "deny"],
        }),
        tool({ name: "list_tags", title: "List tags", read_only_claimed_by_server: true }),
      ],
    })

  function openDetail() {
    requestConnectorsPane({ outcome: null, connectorId: "c-1" })
    open()
  }

  it("sends a PUT with the chosen action for one tool", async () => {
    const calls = stubFetch(connectorsState({ connectors: [withTools()] }), () => json(withTools()))
    openDetail()

    const group = await screen.findByRole("radiogroup", { name: "Permission for Find notes" })
    fireEvent.click(within(group).getByRole("radio", { name: "Block" }))

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0]).toEqual({
      method: "PUT",
      path: "/connectors/c-1/tools/search_notes",
      body: { action: "deny" },
    })
  })

  it("never lets a write tool be set to Allow, and says why", async () => {
    stubFetch(connectorsState({ connectors: [withTools()] }), () => json(withTools()))
    openDetail()

    // No title: the row falls back to the tool's own name, never the wire name.
    const group = await screen.findByRole("radiogroup", { name: "Permission for create_note" })
    expect(within(group).getByRole("radio", { name: "Allow" })).toBeDisabled()
    expect(within(group).getByRole("radio", { name: "Needs approval" })).toBeEnabled()
    expect(group).toHaveAccessibleDescription("A write tool always needs approval")
    expect(screen.queryByText(/mcp__/)).not.toBeInTheDocument()
    expect(screen.getByRole("region", { name: "Write tools" })).toHaveTextContent("1")
    expect(screen.getByText(/The server declares itself read-only/)).toBeInTheDocument()
  })

  it("applies one action to a whole group, skipping tools that already have it", async () => {
    const calls = stubFetch(connectorsState({ connectors: [withTools()] }), () => json(withTools()))
    openDetail()

    fireEvent.change(await screen.findByLabelText("Set the permission for all read-only tools"), {
      target: { value: "ask" },
    })

    await waitFor(() => expect(calls).toHaveLength(2))
    expect(calls.map((call) => call.path)).toEqual([
      "/connectors/c-1/tools/search_notes",
      "/connectors/c-1/tools/list_tags",
    ])
  })

  it("disconnects only after an in-app confirmation, with a DELETE", async () => {
    const confirm = vi.spyOn(window, "confirm")
    const calls = stubFetch(connectorsState({ connectors: [withTools()] }), () => new Response(null, { status: 204 }))
    openDetail()

    fireEvent.click(await screen.findByRole("button", { name: "Disconnect" }))
    expect(calls).toHaveLength(0)
    const dialog = screen.getByRole("alertdialog")
    fireEvent.click(within(dialog).getByRole("button", { name: "Confirm disconnect" }))

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0]).toMatchObject({ method: "DELETE", path: "/connectors/c-1" })
    expect(confirm).not.toHaveBeenCalled()
    // Back on the table, which no longer lists it.
    expect(await screen.findByText(/No connectors yet/)).toBeInTheDocument()
  })

  it("shows a changed tool list and accepts it", async () => {
    const changed = withTools()
    changed.pending = { added: ["export_csv"], removed: ["list_tags"], changed: [], detected_at: null }
    changed.status = "needs_reconsent"
    changed.truncated = 3
    changed.dropped = [{ name: "evil", reason: "suspicious_text:instruction" }]
    const calls = stubFetch(connectorsState({ connectors: [changed] }), () => json(withTools()))
    openDetail()

    expect(await screen.findByText(/export_csv/)).toBeInTheDocument()
    expect(screen.getByText(/3 more tools over the 50-tool-per-connector/)).toBeInTheDocument()
    expect(screen.getByText(/suspicious content/)).toBeInTheDocument()
    fireEvent.click(screen.getByRole("button", { name: "Confirm changes" }))

    await waitFor(() => expect(calls).toHaveLength(1))
    expect(calls[0]).toMatchObject({ method: "POST", path: "/connectors/c-1/accept" })
  })

  it("reports an OAuth return that failed", async () => {
    stubFetch(connectorsState({ connectors: [withTools()] }), () => json({}))
    requestConnectorsPane({ outcome: "failed", connectorId: "c-1" })
    open()

    expect(await screen.findByText("Sign-in failed. Please try again.")).toBeInTheDocument()
  })
})
