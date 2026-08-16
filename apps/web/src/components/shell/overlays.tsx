"use client"

import { useState } from "react"
import { Building2, Check, Lock, MessageSquare, Search, X } from "lucide-react"

import { useThreads } from "@/hooks/use-threads"
import { cn } from "@/lib/utils"

import { useDesk } from "./desk-state"
import { IconButton, SampleDataNote } from "./primitives"
import { threadTitle } from "./sidebar"
import { useShell } from "./shell-state"

/**
 * The two things that take over the screen, and the scrim they share.
 *
 * Both are dismissed by the same three gestures — the backdrop, the close
 * control, and Escape — and Escape is handled once for every overlay in the
 * shell's own key listener rather than here, so a dialog cannot forget it.
 */
export function Overlays() {
  const { state } = useShell()

  if (state.overlay === "palette") return <CommandPalette />
  if (state.overlay === "share") return <ShareDialog />
  return null
}

function Scrim({
  children,
  align = "center",
  label,
}: {
  children: React.ReactNode
  align?: "center" | "top"
  label: string
}) {
  const { dispatch } = useShell()

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label={label}
      onClick={() => dispatch({ type: "overlay", overlay: null })}
      className={cn(
        "fixed inset-0 z-[60] flex animate-vg-fade-in justify-center bg-[hsl(45_9%_4%/0.58)] p-5",
        align === "top" ? "items-start pt-[12vh]" : "items-center",
      )}
    >
      {children}
    </div>
  )
}

/**
 * Every conversation this account has, filtered as you type.
 *
 * Filtered in the browser rather than by the API: the Threads list is already
 * loaded for the sidebar, it is one request either way, and a server round trip
 * per keystroke would make the palette lag behind the typing it exists to keep
 * up with.
 */
function CommandPalette() {
  const { dispatch } = useShell()
  const desk = useDesk()
  const threads = useThreads(true)
  const [term, setTerm] = useState("")

  const query = term.trim().toLowerCase()
  const rows = (threads.data?.threads ?? [])
    .map((thread) => ({ thread, label: threadTitle(thread.title, thread.updated_at) }))
    .filter((row) => query === "" || row.label.toLowerCase().includes(query))

  function open(id: string) {
    desk.openThread(id)
    dispatch({ type: "view", view: "chat" })
    dispatch({ type: "overlay", overlay: null })
  }

  return (
    <Scrim align="top" label="Tìm hội thoại">
      <div
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-[620px] animate-vg-message-in overflow-hidden rounded-2xl border border-border bg-surface-sunken shadow-modal"
      >
        <div className="flex items-center gap-2.5 border-b border-border px-4 py-3.5">
          <Search className="size-[18px] shrink-0 text-ink-5" strokeWidth={1.6} />
          <input
            value={term}
            onChange={(event) => setTerm(event.target.value)}
            onKeyDown={(event) => {
              if (event.key === "Enter" && rows[0]) {
                event.preventDefault()
                open(rows[0].thread.id)
              }
            }}
            autoFocus
            aria-label="Tìm hội thoại"
            placeholder="Tìm hội thoại…"
            className="min-w-0 flex-1 border-0 bg-transparent text-[0.98rem] text-foreground outline-none placeholder:text-ink-6"
          />
          <IconButton
            label="Đóng"
            size="sm"
            onClick={() => dispatch({ type: "overlay", overlay: null })}
          >
            <X className="size-3.5" strokeWidth={1.8} />
          </IconButton>
        </div>

        <div className="scrollbar-thin max-h-[52vh] overflow-y-auto p-1.5">
          {rows.map((row, position) => (
            <button
              key={row.thread.id}
              type="button"
              onClick={() => open(row.thread.id)}
              className={cn(
                "flex w-full items-center gap-2.5 rounded-[9px] px-2.5 py-2.5 text-left text-row transition-colors hover:bg-foreground/[0.05]",
                position === 0 && "bg-surface-raised",
              )}
            >
              <MessageSquare className="size-[17px] shrink-0 text-ink-5" strokeWidth={1.5} />
              <span className="min-w-0 flex-1 truncate">{row.label}</span>
            </button>
          ))}

          {rows.length === 0 && (
            <p className="px-2.5 py-6 text-center text-row text-ink-6">
              {threads.isPending ? "Đang tải…" : "Không có hội thoại nào khớp."}
            </p>
          )}
        </div>
      </div>
    </Scrim>
  )
}

/**
 * Sharing a conversation.
 *
 * Drawn to the reference's shape, and honest about where it stops: no share
 * endpoint exists, so nothing here produces a link. The choice above is real
 * enough to express an intent and the action below says why it cannot yet act
 * on it — which is the only version of this dialog worth shipping before the
 * backend has an opinion about who may read a Thread.
 */
function ShareDialog() {
  const { dispatch } = useShell()
  const [scope, setScope] = useState<"private" | "team">("private")

  return (
    <Scrim label="Chia sẻ hội thoại">
      <div
        onClick={(event) => event.stopPropagation()}
        className="w-full max-w-[520px] animate-vg-message-in rounded-[18px] border border-border bg-surface-sunken p-6 shadow-modal"
      >
        <div className="flex items-start gap-4">
          <div>
            <h2 className="text-[1.28rem] font-normal tracking-[-0.015em] text-foreground">
              Chia sẻ hội thoại
            </h2>
            <p className="mt-1.5 text-row text-ink-4">
              Chỉ các tin nhắn đến thời điểm này được chia sẻ.
            </p>
          </div>
          <IconButton
            label="Đóng"
            onClick={() => dispatch({ type: "overlay", overlay: null })}
            className="ml-auto"
          >
            <X className="size-4" strokeWidth={1.8} />
          </IconButton>
        </div>

        <div className="mt-4 overflow-hidden rounded-card border border-border">
          <ScopeRow
            icon={<Lock className="size-[19px] shrink-0 text-ink-4" strokeWidth={1.6} />}
            title="Giữ riêng tư"
            description="Chỉ bạn truy cập được"
            selected={scope === "private"}
            onSelect={() => setScope("private")}
          />
          <span className="block h-px bg-border" />
          <ScopeRow
            icon={<Building2 className="size-[19px] shrink-0 text-ink-4" strokeWidth={1.6} />}
            title="Chia sẻ nội bộ"
            description="Mọi người trong tổ chức của bạn đều xem được"
            selected={scope === "team"}
            onSelect={() => setScope("team")}
          />
        </div>

        <div className="mt-4">
          <SampleDataNote>
            Chưa tạo được liên kết — API chưa có endpoint chia sẻ hội thoại.
          </SampleDataNote>
        </div>

        <div className="mt-4 flex justify-end">
          <button
            type="button"
            disabled
            className="rounded-[11px] bg-primary px-4 py-2.5 text-row font-medium text-primary-foreground opacity-50"
          >
            Tạo liên kết chia sẻ
          </button>
        </div>
      </div>
    </Scrim>
  )
}

function ScopeRow({
  icon,
  title,
  description,
  selected,
  onSelect,
}: {
  icon: React.ReactNode
  title: string
  description: string
  selected: boolean
  onSelect: () => void
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      onClick={onSelect}
      className="flex w-full items-center gap-3.5 px-4 py-3.5 text-left transition-colors hover:bg-foreground/[0.035]"
    >
      {icon}
      <div className="min-w-0">
        <div className="text-row text-foreground">{title}</div>
        <div className="mt-0.5 text-control text-ink-4">{description}</div>
      </div>
      {selected && <Check className="ml-auto size-[18px] shrink-0 text-primary" strokeWidth={2} />}
    </button>
  )
}
