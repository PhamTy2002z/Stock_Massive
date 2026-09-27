"use client"

import { useEffect, useRef, useState, type FormEvent, type ReactNode } from "react"
import { ChevronDown, Globe, LayoutGrid } from "lucide-react"

import { Menu, MenuItem } from "@/components/shell/primitives"
import {
  PillAction,
  Segmented,
  SettingsSection,
} from "@/components/settings/settings-primitives"
import { Tabs, TabsContent, TabsList, TabsTrigger } from "@/components/ui/tabs"
import { AUTH_LABEL, SOURCE_LABEL, STATUS_LABEL } from "@/lib/connectors/copy"
import { clearConnectorsPane, peekConnectorsPane } from "@/lib/connectors/open-pane"
import type { CatalogEntry, Connector, ConnectorsState } from "@/lib/connectors/types"
import { cn } from "@/lib/utils"

import { ConnectorDetail, FIELD_CLASS, SubmitPill } from "./connector-detail"
import { useConnectors } from "./use-connectors"

type Connectors = ReturnType<typeof useConnectors>
type View = { kind: "list" } | { kind: "detail"; id: string } | { kind: "custom" }
type Tab = "mine" | "discover"

const DESCRIPTION =
  "Attach remote MCP servers so VisgniteAI can use your tools when answering. Content fetched through a connector counts as an external, unverified source."

/**
 * Settings › Connectors: the reader's own remote MCP servers, and the catalog.
 *
 * One pane with three views — the table, one connector, the custom-URL form —
 * switched in place rather than stacked as dialogs over the Settings dialog.
 */
export function ConnectorsPane() {
  const connectors = useConnectors()
  // Read once, cleared after mount: see `open-pane.ts` for why not in render.
  const [request] = useState(peekConnectorsPane)
  useEffect(() => clearConnectorsPane(), [])

  const [view, setView] = useState<View>(
    request?.connectorId ? { kind: "detail", id: request.connectorId } : { kind: "list" },
  )
  const [tab, setTab] = useState<Tab>("mine")
  const { state } = connectors

  let body: ReactNode
  if (connectors.isPending) {
    body = <p className="text-control text-ink-6">Loading connectors…</p>
  } else if (connectors.isError || !state) {
    body = (
      <div className="flex items-center gap-3">
        <p className="text-control text-ink-4">Couldn't read the connector list.</p>
        <PillAction onClick={() => connectors.refetch()}>Retry</PillAction>
      </div>
    )
  } else if (!state.enabled) {
    body = (
      <p role="status" className="rounded-lg border border-border bg-foreground/[0.035] px-3 py-2.5 text-control text-ink-3">
        Connectors aren't enabled on this system. Once an administrator turns them on,
        you'll add and manage connectors here.
      </p>
    )
  } else {
    const open = view.kind === "detail" ? state.connectors.find((one) => one.id === view.id) : undefined
    if (open) {
      body = (
        <ConnectorDetail
          connector={open}
          connectors={connectors}
          onBack={() => setView({ kind: "list" })}
        />
      )
    } else if (view.kind === "custom") {
      body = (
        <CustomForm
          connectors={connectors}
          onCancel={() => setView({ kind: "list" })}
          onAdded={(connector) => setView({ kind: "detail", id: connector.id })}
        />
      )
    } else {
      body = (
        <ListView
          state={state}
          connectors={connectors}
          tab={tab}
          onTab={setTab}
          onOpen={(id) => setView({ kind: "detail", id })}
          onCustom={() => setView({ kind: "custom" })}
        />
      )
    }
  }

  return (
    <SettingsSection title="Connectors" description={DESCRIPTION}>
      {request?.outcome && (
        <p
          role="status"
          className={cn(
            "mb-4 rounded-lg border px-3 py-2 text-control",
            request.outcome === "connected"
              ? "border-border bg-foreground/[0.035] text-ink-2"
              : "border-negative/35 bg-negative/[0.06] text-ink-2",
          )}
        >
          {request.outcome === "connected"
            ? "Signed in — the connector is ready to use."
            : "Sign-in failed. Please try again."}
        </p>
      )}
      {connectors.error && (
        <p role="alert" className="mb-4 rounded-lg border border-negative/35 bg-negative/[0.06] px-3 py-2 text-control text-ink-2">
          {connectors.error}
        </p>
      )}
      {body}
    </SettingsSection>
  )
}

function ListView({
  state,
  connectors,
  tab,
  onTab,
  onOpen,
  onCustom,
}: {
  state: ConnectorsState
  connectors: Connectors
  tab: Tab
  onTab: (tab: Tab) => void
  onOpen: (id: string) => void
  onCustom: () => void
}) {
  return (
    <Tabs value={tab} onValueChange={(value) => onTab(value as Tab)}>
      <div className="flex items-center justify-between gap-3">
        <TabsList aria-label="Connector group">
          <TabsTrigger value="mine">Yours</TabsTrigger>
          <TabsTrigger value="discover">Discover</TabsTrigger>
        </TabsList>
        <AddMenu
          customAllowed={state.custom_url_allowed}
          onCatalog={() => onTab("discover")}
          onCustom={onCustom}
        />
      </div>
      <TabsContent value="mine">
        <ConnectorTable rows={state.connectors} onOpen={onOpen} />
      </TabsContent>
      <TabsContent value="discover">
        <CatalogList state={state} connectors={connectors} onAdded={onOpen} />
      </TabsContent>
    </Tabs>
  )
}

function AddMenu({
  customAllowed,
  onCatalog,
  onCustom,
}: {
  customAllowed: boolean
  onCatalog: () => void
  onCustom: () => void
}) {
  const [open, setOpen] = useState(false)
  const root = useRef<HTMLDivElement>(null)

  useEffect(() => {
    if (!open) return
    function onPointerDown(event: PointerEvent) {
      if (!root.current?.contains(event.target as Node)) setOpen(false)
    }
    document.addEventListener("pointerdown", onPointerDown)
    return () => document.removeEventListener("pointerdown", onPointerDown)
  }, [open])

  return (
    <div ref={root} className="relative">
      <button
        type="button"
        aria-haspopup="menu"
        aria-expanded={open}
        onClick={() => setOpen((value) => !value)}
        className="inline-flex h-9 items-center gap-1.5 rounded-[10px] border border-border px-3.5 text-control text-ink-2 outline-none transition-colors hover:bg-foreground/[0.06] focus-visible:ring-2 focus-visible:ring-ring"
      >
        Add
        <ChevronDown className="size-[13px] text-ink-6" strokeWidth={1.8} aria-hidden />
      </button>
      {open && (
        <Menu className="absolute right-0 top-[42px] min-w-[220px]">
          <MenuItem
            icon={<LayoutGrid className="size-[16px] text-ink-4" strokeWidth={1.6} />}
            onClick={() => {
              setOpen(false)
              onCatalog()
            }}
          >
            From catalog
          </MenuItem>
          {customAllowed && (
            <MenuItem
              icon={<Globe className="size-[16px] text-ink-4" strokeWidth={1.6} />}
              onClick={() => {
                setOpen(false)
                onCustom()
              }}
            >
              Custom URL
            </MenuItem>
          )}
        </Menu>
      )}
    </div>
  )
}

function ConnectorTable({ rows, onOpen }: { rows: Connector[]; onOpen: (id: string) => void }) {
  if (rows.length === 0) {
    return (
      <p className="py-6 text-control text-ink-6">
        No connectors yet. Add one from Discover or with the Add button.
      </p>
    )
  }
  return (
    <table className="w-full table-fixed border-collapse text-left">
      <thead>
        <tr className="border-b border-hairline text-micro font-semibold uppercase tracking-[0.08em] text-ink-6">
          <th scope="col" className="w-[40%] py-2 font-semibold">Connector</th>
          <th scope="col" className="py-2 font-semibold">Kind</th>
          <th scope="col" className="py-2 font-semibold">Auth</th>
          <th scope="col" className="py-2 font-semibold">Status</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((row) => (
          <tr
            key={row.id}
            onClick={() => onOpen(row.id)}
            className="cursor-pointer border-b border-hairline text-row transition-colors last:border-b-0 hover:bg-foreground/[0.03]"
          >
            <td className="py-2.5 pr-3">
              <button
                type="button"
                onClick={(event) => {
                  event.stopPropagation()
                  onOpen(row.id)
                }}
                className="max-w-full truncate rounded text-left text-foreground outline-none focus-visible:ring-2 focus-visible:ring-ring"
              >
                {row.name}
              </button>
              {!row.enabled && <span className="ml-2 text-micro text-ink-6">Off</span>}
            </td>
            <td className="py-2.5 text-ink-4">{SOURCE_LABEL[row.source]}</td>
            <td className="py-2.5 text-ink-4">{AUTH_LABEL[row.auth_type]}</td>
            <td className={cn("py-2.5", row.status === "connected" ? "text-ink-3" : "text-caution")}>
              {STATUS_LABEL[row.status]}
            </td>
          </tr>
        ))}
      </tbody>
    </table>
  )
}

function CatalogList({
  state,
  connectors,
  onAdded,
}: {
  state: ConnectorsState
  connectors: Connectors
  onAdded: (id: string) => void
}) {
  if (state.catalog.length === 0) {
    return <p className="py-6 text-control text-ink-6">The catalog has no connectors yet.</p>
  }
  return (
    <ul className="grid gap-2.5">
      {state.catalog.map((entry) => (
        <CatalogItem
          key={entry.id}
          entry={entry}
          added={state.connectors.some((one) => one.catalog_id === entry.id)}
          connectors={connectors}
          onAdded={onAdded}
        />
      ))}
    </ul>
  )
}

function CatalogItem({
  entry,
  added,
  connectors,
  onAdded,
}: {
  entry: CatalogEntry
  added: boolean
  connectors: Connectors
  onAdded: (id: string) => void
}) {
  const [askingKey, setAskingKey] = useState(false)
  const [key, setKey] = useState("")
  const busy = connectors.busy === "add"

  async function add(headerValue?: string) {
    const connector = await connectors.add(
      headerValue ? { catalog_id: entry.id, header_value: headerValue } : { catalog_id: entry.id },
    )
    if (!connector) return
    if (connector.auth_type === "oauth" && connector.status === "needs_auth") {
      await connectors.signIn(connector.id)
      return
    }
    onAdded(connector.id)
  }

  return (
    <li className="rounded-card border border-border bg-surface-raised px-3.5 py-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-row font-medium text-foreground">{entry.name}</p>
          {entry.description && <p className="mt-0.5 text-meta text-ink-5">{entry.description}</p>}
          <p className="mt-1 text-micro text-ink-6">
            Auth: {AUTH_LABEL[entry.auth_type]}
            {entry.trusted_data ? " · Data from a vetted source" : ""}
          </p>
        </div>
        {added ? (
          <span className="shrink-0 text-meta text-ink-6">Added</span>
        ) : (
          <PillAction
            disabled={busy}
            onClick={() => (entry.auth_type === "header" ? setAskingKey(true) : add())}
          >
            Add {entry.name}
          </PillAction>
        )}
      </div>
      {askingKey && !added && (
        <form
          className="mt-3 flex flex-wrap items-center gap-2"
          onSubmit={(event) => {
            event.preventDefault()
            if (key.trim()) add(key.trim())
          }}
        >
          <input
            type="password"
            autoComplete="off"
            aria-label={`Access key for ${entry.name}`}
            placeholder="Access key"
            value={key}
            onChange={(event) => setKey(event.target.value)}
            className={cn(FIELD_CLASS, "md:w-[280px]")}
          />
          <SubmitPill disabled={busy || !key.trim()}>{busy ? "Adding…" : "Connect"}</SubmitPill>
        </form>
      )}
    </li>
  )
}

type AuthChoice = "none" | "header" | "oauth"

function CustomForm({
  connectors,
  onCancel,
  onAdded,
}: {
  connectors: Connectors
  onCancel: () => void
  onAdded: (connector: Connector) => void
}) {
  const [name, setName] = useState("")
  const [url, setUrl] = useState("")
  const [auth, setAuth] = useState<AuthChoice>("none")
  const [headerName, setHeaderName] = useState("Authorization")
  const [headerValue, setHeaderValue] = useState("")
  const [problem, setProblem] = useState<string | null>(null)
  const busy = connectors.busy === "add" || connectors.busy?.startsWith("oauth:")

  async function submit(event: FormEvent) {
    event.preventDefault()
    const trimmedUrl = url.trim()
    if (!name.trim()) return setProblem("Please name this connector.")
    if (!/^https?:\/\/\S+$/i.test(trimmedUrl)) return setProblem("The URL must be a full address starting with https://.")
    if (auth === "header" && (!headerName.trim() || !headerValue.trim())) {
      return setProblem("Please enter a header name and a key.")
    }
    setProblem(null)
    const connector = await connectors.add({
      name: name.trim(),
      url: trimmedUrl,
      ...(auth === "header" ? { header_name: headerName.trim(), header_value: headerValue.trim() } : {}),
      ...(auth === "oauth" ? { oauth: true } : {}),
    })
    if (!connector) return
    if (connector.auth_type === "oauth" && connector.status === "needs_auth") {
      await connectors.signIn(connector.id)
      return
    }
    onAdded(connector)
  }

  return (
    <form onSubmit={submit} aria-label="Add a connector with a custom URL" className="grid gap-4 animate-vg-row-in">
      <h3 className="text-[1rem] font-medium">Add with a custom URL</h3>
      <p className="-mt-2 text-control text-ink-6">
        Only add a server you trust. A custom server's tools declare themselves read-only or
        write; the system can't verify that.
      </p>
      <Field label="Name">
        <input value={name} onChange={(event) => setName(event.target.value)} maxLength={120} className={FIELD_CLASS} placeholder="For example: Internal data" />
      </Field>
      <Field label="MCP server URL">
        <input
          value={url}
          onChange={(event) => setUrl(event.target.value)}
          inputMode="url"
          maxLength={2000}
          className={cn(FIELD_CLASS, "font-mono")}
          placeholder="https://mcp.example.com/mcp"
        />
      </Field>
      <div>
        <span className="mb-1.5 block text-control text-ink-3">Auth</span>
        <Segmented<AuthChoice>
          label="Auth"
          selected={auth}
          onSelect={setAuth}
          options={[
            { value: "none", label: "None" },
            { value: "header", label: "Key" },
            { value: "oauth", label: "OAuth" },
          ]}
        />
      </div>
      {auth === "header" && (
        <div className="grid gap-3 md:grid-cols-2">
          <Field label="Header name">
            <input value={headerName} onChange={(event) => setHeaderName(event.target.value)} maxLength={64} className={cn(FIELD_CLASS, "font-mono")} />
          </Field>
          <Field label="Key">
            <input type="password" autoComplete="off" value={headerValue} onChange={(event) => setHeaderValue(event.target.value)} className={FIELD_CLASS} />
          </Field>
        </div>
      )}
      {problem && (
        <p role="alert" className="text-control text-negative">
          {problem}
        </p>
      )}
      <div className="flex gap-2">
        <PillAction onClick={onCancel}>Cancel</PillAction>
        <SubmitPill disabled={Boolean(busy)}>{busy ? "Adding…" : "Add connector"}</SubmitPill>
      </div>
    </form>
  )
}

function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <label className="grid gap-1.5 text-control text-ink-3">
      {label}
      {children}
    </label>
  )
}
