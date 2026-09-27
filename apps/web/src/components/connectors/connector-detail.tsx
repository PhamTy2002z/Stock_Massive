"use client"

import { useId, useState, type FormEvent, type ReactNode } from "react"
import { ArrowLeft } from "lucide-react"

import { PillAction, Toggle } from "@/components/settings/settings-primitives"
import {
  ACTION_LABEL,
  AUTH_LABEL,
  SERVER_CLAIMED_READ_ONLY,
  SOURCE_LABEL,
  STATUS_LABEL,
  TOOL_LIMIT,
  WRITE_NEEDS_APPROVAL,
  droppedReason,
} from "@/lib/connectors/copy"
import type { Connector, ConnectorTool, ToolAction } from "@/lib/connectors/types"
import { cn } from "@/lib/utils"

import type { useConnectors } from "./use-connectors"

type Connectors = ReturnType<typeof useConnectors>

const ACTIONS: ToolAction[] = ["allow", "ask", "deny"]

export const FIELD_CLASS =
  "w-full rounded-[10px] border border-border bg-surface-sunken px-3 py-2 text-control text-foreground outline-none transition-colors placeholder:text-ink-6 focus:border-primary/50"

/** `PillAction`'s shape for a form's submit, which `PillAction` (always `type="button"`) cannot be. */
export function SubmitPill({ disabled, children }: { disabled: boolean; children: ReactNode }) {
  return (
    <button
      type="submit"
      disabled={disabled}
      className="shrink-0 whitespace-nowrap rounded-pill border border-border px-[0.95rem] py-[0.42rem] text-control text-ink-2 outline-none transition-colors hover:bg-accent hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed disabled:opacity-50"
    >
      {children}
    </button>
  )
}

/**
 * One connector: what it is, whether it runs, and what each of its tools may do.
 *
 * Names on screen are the server's tool `title` or `name`, never the `mcp__…`
 * wire name or the slug — those are the model's handles, not the reader's.
 */
export function ConnectorDetail({
  connector,
  connectors,
  onBack,
}: {
  connector: Connector
  connectors: Connectors
  onBack: () => void
}) {
  const [confirming, setConfirming] = useState(false)
  const [editingKey, setEditingKey] = useState(false)
  const { busy } = connectors
  const reads = connector.tools.filter((tool) => tool.effect === "read")
  const writes = connector.tools.filter((tool) => tool.effect === "write")
  // The over-limit ones are said once as a count; the rest are listed with why.
  const dropped = connector.dropped.filter((item) => item.reason !== "over_tool_limit")

  async function disconnect() {
    if (await connectors.remove(connector.id)) onBack()
  }

  return (
    <div className="animate-vg-row-in">
      <button
        type="button"
        onClick={onBack}
        className="-ml-1 inline-flex items-center gap-1.5 rounded-lg px-1 py-0.5 text-control text-ink-4 outline-none transition-colors hover:text-foreground focus-visible:ring-2 focus-visible:ring-ring"
      >
        <ArrowLeft className="size-[15px]" strokeWidth={1.7} aria-hidden />
        Your connectors
      </button>

      <div className="mt-4 flex flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <h3 className="truncate text-[1.1rem] font-semibold leading-[1.3]">{connector.name}</h3>
          <p className="mt-1 text-meta text-ink-6">
            {SOURCE_LABEL[connector.source]} · Auth: {AUTH_LABEL[connector.auth_type]} ·{" "}
            <span className={connector.status === "connected" ? "text-ink-3" : "text-caution"}>
              {STATUS_LABEL[connector.status]}
            </span>
          </p>
          <p className="mt-0.5 truncate font-mono text-micro text-ink-6">{connector.url}</p>
        </div>
        <PillAction tone="danger" onClick={() => setConfirming(true)}>
          Disconnect
        </PillAction>
      </div>

      {confirming && (
        <div
          role="alertdialog"
          aria-label={`Disconnect ${connector.name}`}
          className="mt-4 rounded-card border border-negative/35 bg-negative/[0.06] px-3.5 py-3"
        >
          <p className="text-row text-foreground">
            Disconnect {connector.name}? Its key, sign-in session and saved tool permissions will be deleted.
          </p>
          <div className="mt-3 flex gap-2">
            <PillAction onClick={() => setConfirming(false)}>Cancel</PillAction>
            <PillAction
              tone="danger"
              disabled={busy === `remove:${connector.id}`}
              onClick={disconnect}
            >
              {busy === `remove:${connector.id}` ? "Disconnecting…" : "Confirm disconnect"}
            </PillAction>
          </div>
        </div>
      )}

      <div className="mt-5 flex flex-wrap items-center gap-x-6 gap-y-3 border-y border-hairline py-4">
        <label className="flex items-center gap-2.5 text-control text-ink-3">
          <Toggle
            label="Use this connector in a question"
            checked={connector.enabled}
            disabled={busy === `enabled:${connector.id}`}
            onChange={(next) => connectors.setEnabled(connector.id, next)}
          />
          {connector.enabled ? "On" : "Off"}
        </label>
        <div className="flex flex-wrap gap-2">
          <PillAction
            disabled={busy === `refresh:${connector.id}`}
            onClick={() => connectors.refresh(connector.id)}
          >
            {busy === `refresh:${connector.id}` ? "Refreshing…" : "Refresh"}
          </PillAction>
          {connector.auth_type === "oauth" && (
            <PillAction
              disabled={busy === `oauth:${connector.id}`}
              onClick={() => connectors.signIn(connector.id)}
            >
              Sign in again
            </PillAction>
          )}
          {connector.auth_type === "header" && (
            <PillAction onClick={() => setEditingKey((open) => !open)}>Update key</PillAction>
          )}
        </div>
      </div>

      {editingKey && (
        <KeyForm
          busy={busy === `header:${connector.id}`}
          onCancel={() => setEditingKey(false)}
          onSave={async (value) => {
            if ((await connectors.setHeader(connector.id, value)) !== undefined) setEditingKey(false)
          }}
        />
      )}

      <StatusNotes connector={connector} />

      {connector.pending && (
        <section
          aria-label="Tool list changed"
          className="mt-4 rounded-card border border-caution/45 bg-caution/[0.08] px-3.5 py-3"
        >
          <p className="text-row font-medium text-foreground">The server changed its tool list</p>
          <p className="mt-0.5 text-meta text-ink-4">Review it, then confirm to use the new list.</p>
          <ChangeList label="Added" names={connector.pending.added} />
          <ChangeList label="Changed" names={connector.pending.changed} />
          <ChangeList label="Removed" names={connector.pending.removed} />
          <div className="mt-3">
            <PillAction
              disabled={busy === `accept:${connector.id}`}
              onClick={() => connectors.accept(connector.id)}
            >
              {busy === `accept:${connector.id}` ? "Confirming…" : "Confirm changes"}
            </PillAction>
          </div>
        </section>
      )}

      <h4 className="mt-7 text-[0.95rem] font-medium">Tool permissions</h4>
      <p className="mt-1 text-control text-ink-6">
        Allow: runs right away. Needs approval: asks you in the conversation before it runs. Block: never runs.
      </p>

      {connector.tools.length === 0 && (
        <p className="mt-3 text-control text-ink-6">The server hasn't offered any tools yet.</p>
      )}
      <ToolGroup title="Read-only tools" tools={reads} connector={connector} connectors={connectors} />
      <ToolGroup title="Write tools" tools={writes} connector={connector} connectors={connectors} />

      {(connector.truncated > 0 || dropped.length > 0) && (
        <section aria-label="Tools not loaded" className="mt-6 text-control text-ink-4">
          {connector.truncated > 0 && (
            <p>
              The server has {connector.truncated} more tools over the {TOOL_LIMIT}-tool-per-connector
              limit, so they weren't loaded.
            </p>
          )}
          {dropped.length > 0 && (
            <>
              <p className="mt-2">Couldn't load {dropped.length} tools:</p>
              <ul className="mt-1 space-y-0.5">
                {dropped.map((item, index) => (
                  <li key={`${item.name}-${index}`} className="text-meta text-ink-6">
                    <span className="text-ink-4">{item.name || "(no name)"}</span> —{" "}
                    {droppedReason(item.reason)}
                  </li>
                ))}
              </ul>
            </>
          )}
        </section>
      )}
    </div>
  )
}

function StatusNotes({ connector }: { connector: Connector }) {
  const notes: string[] = []
  if (connector.status === "needs_auth") {
    notes.push(
      connector.auth_type === "oauth"
        ? "The sign-in session has expired or been revoked. Please sign in again."
        : "The server refused the current key. Please update the key.",
    )
  }
  if (connector.status === "error" && connector.last_error) {
    notes.push(`Last error: ${connector.last_error}`)
  }
  if (connector.breaker_open) {
    notes.push("The server has been failing repeatedly, so calls are paused; the system will retry later.")
  }
  if (notes.length === 0) return null
  return (
    <div role="status" className="mt-4 space-y-1 rounded-lg border border-border bg-foreground/[0.035] px-3 py-2 text-meta text-ink-3">
      {notes.map((note) => (
        <p key={note}>{note}</p>
      ))}
    </div>
  )
}

function ChangeList({ label, names }: { label: string; names: string[] }) {
  if (names.length === 0) return null
  return (
    <p className="mt-1.5 text-meta text-ink-3">
      <span className="font-medium text-ink-2">
        {label} ({names.length}):
      </span>{" "}
      {names.join(", ")}
    </p>
  )
}

function KeyForm({
  busy,
  onSave,
  onCancel,
}: {
  busy: boolean
  onSave: (value: string) => void
  onCancel: () => void
}) {
  const [value, setValue] = useState("")
  function submit(event: FormEvent) {
    event.preventDefault()
    if (value.trim()) onSave(value.trim())
  }
  return (
    <form onSubmit={submit} className="mt-4 flex flex-wrap items-center gap-2">
      <input
        type="password"
        autoComplete="off"
        aria-label="New access key"
        placeholder="New access key"
        value={value}
        onChange={(event) => setValue(event.target.value)}
        className={cn(FIELD_CLASS, "md:w-[280px]")}
      />
      <PillAction onClick={onCancel}>Cancel</PillAction>
      <SubmitPill disabled={busy || !value.trim()}>{busy ? "Saving…" : "Save key"}</SubmitPill>
    </form>
  )
}

function ToolGroup({
  title,
  tools,
  connector,
  connectors,
}: {
  title: string
  tools: ConnectorTool[]
  connector: Connector
  connectors: Connectors
}) {
  const bulkId = useId()
  if (tools.length === 0) return null
  const groupBusy = connectors.busy === `group:${connector.id}`
  const writes = tools[0].effect === "write"

  return (
    <section aria-label={title} className="mt-5">
      <div className="flex flex-wrap items-center justify-between gap-2 border-b border-hairline pb-2">
        <h5 className="text-control font-medium text-ink-2">
          {title} <span className="font-mono text-ink-6">{tools.length}</span>
        </h5>
        <label htmlFor={bulkId} className="sr-only">
          Set the permission for all {title.toLowerCase()}
        </label>
        <select
          id={bulkId}
          value=""
          disabled={groupBusy}
          onChange={(event) => {
            const action = event.target.value as ToolAction
            if (action) connectors.setGroup(connector.id, tools, action)
          }}
          className="rounded-[8px] border border-border bg-surface-sunken px-2 py-1 text-meta text-ink-3 outline-none focus:border-primary/50"
        >
          <option value="">{groupBusy ? "Applying…" : "Set for all…"}</option>
          {ACTIONS.map((action) => (
            <option key={action} value={action} disabled={writes && action === "allow"}>
              {ACTION_LABEL[action]} all
            </option>
          ))}
        </select>
      </div>
      <ul>
        {tools.map((tool) => (
          <ToolRow key={tool.name} tool={tool} connector={connector} connectors={connectors} />
        ))}
      </ul>
    </section>
  )
}

function ToolRow({
  tool,
  connector,
  connectors,
}: {
  tool: ConnectorTool
  connector: Connector
  connectors: Connectors
}) {
  const noteId = useId()
  const display = tool.title || tool.name
  const busy =
    connectors.busy === `tool:${connector.id}:${tool.name}` ||
    connectors.busy === `group:${connector.id}`
  const lockedAllow = !tool.allowed_actions.includes("allow")

  return (
    <li className="flex flex-col gap-2 border-b border-hairline py-3 last:border-b-0 md:flex-row md:items-center md:justify-between md:gap-6">
      <div className="min-w-0">
        <p className="text-row text-foreground">{display}</p>
        {tool.description && (
          <p className="mt-0.5 line-clamp-2 text-meta text-ink-6">{tool.description}</p>
        )}
        <p id={noteId} className="mt-0.5 text-micro text-ink-5">
          {tool.effect === "write" && lockedAllow ? WRITE_NEEDS_APPROVAL : null}
          {tool.read_only_claimed_by_server ? SERVER_CLAIMED_READ_ONLY : null}
        </p>
      </div>
      <div
        role="radiogroup"
        aria-label={`Permission for ${display}`}
        aria-describedby={noteId}
        aria-busy={busy || undefined}
        className="flex shrink-0 gap-0.5 self-start rounded-[11px] border border-hairline bg-surface-sunken p-[3px] md:self-auto"
      >
        {ACTIONS.map((action) => {
          const selected = tool.action === action
          const allowed = tool.allowed_actions.includes(action)
          return (
            <button
              key={action}
              type="button"
              role="radio"
              aria-checked={selected}
              disabled={!allowed || busy}
              title={!allowed && action === "allow" ? WRITE_NEEDS_APPROVAL : undefined}
              onClick={() => {
                if (!selected) connectors.setTool(connector.id, tool.name, action)
              }}
              className={cn(
                "rounded-[8px] px-2.5 py-1 text-meta outline-none transition-colors focus-visible:ring-2 focus-visible:ring-ring disabled:cursor-not-allowed",
                selected
                  ? "bg-surface-menu text-foreground shadow-sm"
                  : "text-ink-5 hover:text-foreground disabled:hover:text-ink-5",
                !allowed && "opacity-40",
              )}
            >
              {ACTION_LABEL[action]}
            </button>
          )
        })}
      </div>
    </li>
  )
}
