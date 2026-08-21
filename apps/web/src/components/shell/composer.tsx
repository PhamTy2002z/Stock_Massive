"use client"

import { useEffect, useRef, type FormEvent, type KeyboardEvent } from "react"
import {
  ArrowUp,
  Camera,
  ChevronDown,
  ChevronRight,
  Globe,
  Grid2x2,
  LayoutList,
  Mic,
  Paperclip,
  Plus,
  Search,
  Square,
  Wallet,
  X,
} from "lucide-react"

import { CANCELLING_LABEL } from "@/lib/alpha-desk/copy"
import { cn } from "@/lib/utils"

import { useDesk } from "./desk-state"
import { IconButton, Menu, MenuItem, MenuSeparator } from "./primitives"
import { useShell } from "./shell-state"

/** What a question is allowed to grow to before the field starts scrolling. */
const MAX_FIELD_HEIGHT_PX = 150

/**
 * Where the user says something.
 *
 * One lifted card rather than a field with a button beside it: 18px corners, a
 * hairline, a shadow deep enough to separate it from the transcript running
 * underneath, and every control *inside* the card. The field itself carries no
 * border — it would be a second box inside the first.
 *
 * The field is **never disabled by anything happening elsewhere**. A Turn in
 * flight does not lock it: composing the next question while an answer arrives
 * is the ordinary way anyone uses a conversation. What changes is the control
 * beside it — while a Turn runs it is Stop, and a pressed Stop is immediate.
 */
export function Composer({ variant = "docked" }: { variant?: "docked" | "opening" }) {
  const desk = useDesk()
  const { state, dispatch } = useShell()
  const text = state.draft
  const field = useRef<HTMLTextAreaElement>(null)

  const attachOpen = state.overlay === "attach"

  function resize() {
    const element = field.current
    if (!element) return
    // Measured from a collapsed height, or the box only ever grows: scrollHeight
    // of an already-tall element reports the height it was given.
    element.style.height = "auto"
    element.style.height = `${Math.min(element.scrollHeight, MAX_FIELD_HEIGHT_PX)}px`
  }

  // A question offered by another panel arrives as text this field did not
  // type. Taking focus is the whole point of offering it — the user is meant to
  // read it, edit it if they like, and press send themselves.
  useEffect(() => {
    const element = field.current
    if (!element || text === "" || document.activeElement === element) return
    element.focus()
    element.setSelectionRange(text.length, text.length)
    resize()
    // Only when the offer arrives; every later keystroke is already focused.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [text === ""])

  function submit(event: FormEvent) {
    event.preventDefault()
    const trimmed = text.trim()
    if (!trimmed || desk.canCancel || desk.isSubmitting) return
    desk.submit(trimmed)
    dispatch({ type: "draft", text: "" })
    if (field.current) field.current.style.height = "auto"
    // Asking from the opening screen is what turns it into a conversation.
    if (state.view !== "chat") dispatch({ type: "view", view: "chat" })
  }

  function onKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      submit(event)
    }
  }

  return (
    <form
      onSubmit={submit}
      className={cn(
        "relative rounded-composer border border-border bg-surface-sunken px-3.5 pb-2.5 pt-3",
        variant === "docked" && "shadow-composer",
      )}
    >
      {state.contextSymbol && (
        <div className="flex items-center gap-2 pb-2.5">
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-primary/30 bg-primary/[0.09] py-1 pl-2.5 pr-1 font-mono text-meta text-primary">
            {state.contextSymbol}
            <IconButton
              label="Bỏ ngữ cảnh phân tích"
              size="sm"
              onClick={() => dispatch({ type: "context-symbol", symbol: null })}
              className="size-[17px] rounded-[5px] text-primary hover:bg-primary/20 hover:text-primary"
            >
              <X className="size-2.5" strokeWidth={2.4} />
            </IconButton>
          </span>
          <span className="min-w-0 truncate text-meta text-ink-6">
            đang là ngữ cảnh phân tích
          </span>
        </div>
      )}

      <textarea
        ref={field}
        value={text}
        onChange={(event) => {
          dispatch({ type: "draft", text: event.target.value })
          resize()
        }}
        onKeyDown={onKeyDown}
        rows={1}
        aria-label="Ask Alpha Desk"
        placeholder={
          state.contextSymbol
            ? `Hỏi về ${state.contextSymbol}, hay bất kỳ mã nào…`
            : "Hỏi về một mã, một ngành hay cả thị trường…"
        }
        className="block max-h-[150px] min-h-[26px] w-full resize-none border-0 bg-transparent p-0 pb-2 text-[0.98rem] leading-[1.5] text-foreground outline-none placeholder:text-ink-6"
      />

      <div className="flex items-center gap-1.5">
        <div className="relative flex">
          {attachOpen && <AttachMenu />}
          <IconButton
            label="Đính kèm"
            aria-expanded={attachOpen}
            aria-haspopup="menu"
            onClick={(event) => {
              event.stopPropagation()
              dispatch({ type: "overlay", overlay: attachOpen ? null : "attach" })
            }}
          >
            <Plus className="size-[18px]" strokeWidth={1.6} />
          </IconButton>
        </div>

        <div className="ml-auto flex items-center gap-1.5">
          <span className="hidden items-center gap-1.5 rounded-lg px-2 py-1 text-control text-ink-3 md:flex">
            Visgnite Pro
            <ChevronDown className="size-3 text-ink-6" strokeWidth={1.8} />
          </span>
          <IconButton label="Nhập bằng giọng nói" disabled>
            <Mic className="size-[17px]" strokeWidth={1.6} />
          </IconButton>

          {desk.canCancel ? (
            <button
              type="button"
              onClick={desk.cancel}
              disabled={desk.isCancelling}
              className="inline-flex h-8 shrink-0 items-center gap-1.5 rounded-[10px] border border-border px-3 text-control text-ink-3 transition-colors hover:bg-foreground/[0.06] hover:text-foreground disabled:opacity-50"
            >
              <Square className="size-3.5" />
              {desk.isCancelling ? CANCELLING_LABEL : "Stop"}
            </button>
          ) : (
            <button
              type="submit"
              disabled={!text.trim() || desk.isSubmitting}
              className="inline-flex size-8 shrink-0 items-center justify-center rounded-[10px] bg-primary text-primary-foreground transition-[filter,transform] hover:-translate-y-px hover:brightness-110 disabled:pointer-events-none disabled:opacity-40"
            >
              <ArrowUp className="size-[17px]" strokeWidth={2} />
              <span className="sr-only">Send</span>
            </button>
          )}
        </div>
      </div>
    </form>
  )
}

/**
 * The attach menu.
 *
 * Every row here needs something the backend does not expose: there is no
 * upload endpoint, no portfolio resource, no analysis-template store, no
 * connector registry, and the news toggle is a property of the agent's tool
 * catalog rather than a per-message switch. Drawn to the reference's shape and
 * inert throughout — a control that swallowed the press would be worse than one
 * that says it is not ready.
 */
function AttachMenu() {
  return (
    <Menu className="absolute bottom-[38px] left-0 min-w-[250px]">
      <MenuItem icon={<Paperclip className="size-[17px] text-ink-4" strokeWidth={1.6} />} hint="⌘U" disabled>
        Thêm tệp hoặc ảnh
      </MenuItem>
      <MenuItem icon={<Camera className="size-[17px] text-ink-4" strokeWidth={1.6} />} disabled>
        Chụp màn hình bảng giá
      </MenuItem>
      <MenuItem
        icon={<Wallet className="size-[17px] text-ink-4" strokeWidth={1.6} />}
        trailing={<ChevronRight className="size-4 shrink-0 text-ink-6" />}
        disabled
      >
        Thêm vào danh mục
      </MenuItem>
      <MenuSeparator />
      <MenuItem
        icon={<LayoutList className="size-[17px] text-ink-4" strokeWidth={1.6} />}
        trailing={<ChevronRight className="size-4 shrink-0 text-ink-6" />}
        disabled
      >
        Mẫu phân tích
      </MenuItem>
      <MenuItem
        icon={<Grid2x2 className="size-[17px] text-ink-4" strokeWidth={1.6} />}
        trailing={<ChevronRight className="size-4 shrink-0 text-ink-6" />}
        disabled
      >
        Nguồn dữ liệu kết nối
      </MenuItem>
      <MenuSeparator />
      <MenuItem icon={<Search className="size-[17px] text-ink-4" strokeWidth={1.6} />} disabled>
        Nghiên cứu sâu
      </MenuItem>
      <MenuItem icon={<Globe className="size-[17px] text-ink-4" strokeWidth={1.6} />} disabled>
        Tra tin tức thị trường
      </MenuItem>
    </Menu>
  )
}
