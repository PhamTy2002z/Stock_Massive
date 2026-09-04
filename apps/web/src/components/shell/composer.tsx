"use client"

import { useEffect, useRef, type FormEvent, type KeyboardEvent } from "react"
import {
  Camera,
  ChevronDown,
  ChevronRight,
  Paperclip,
  Plus,
  Square,
  Wallet,
  X,
} from "lucide-react"

import { attachmentUrl } from "@/lib/alpha-desk/api"
import {
  ATTACHMENT_COPY,
  CANCELLING_LABEL,
  CAPTURE_COPY,
  SEND_LABEL,
  SIGNAL_DESK_COPY,
} from "@/lib/alpha-desk/copy"
import { cn } from "@/lib/utils"

import { AttachmentChip } from "./attachment-chip"
import { useDesk } from "./desk-state"
import { IconButton, Menu, MenuItem, MenuSeparator } from "./primitives"
import { useShell } from "./shell-state"

/**
 * The five-bar waveform on the send control.
 *
 * Hand-drawn rather than taken from the icon set: the design fixes each bar's
 * height, and the symmetry — tall in the middle, tapering either side — is the
 * whole of what makes it read as sound rather than as a bar chart. The nearest
 * packaged icon has different proportions, and matching a design by eye is how
 * two surfaces drift apart.
 */
function WaveformIcon() {
  return (
    <svg
      width="18"
      height="18"
      viewBox="0 0 24 24"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.9}
      strokeLinecap="round"
      aria-hidden="true"
    >
      <line x1="4.5" y1="10" x2="4.5" y2="14" />
      <line x1="8" y1="7.5" x2="8" y2="16.5" />
      <line x1="11.5" y1="5.5" x2="11.5" y2="18.5" />
      <line x1="15" y1="8.5" x2="15" y2="15.5" />
      <line x1="18.5" y1="10.5" x2="18.5" y2="13.5" />
    </svg>
  )
}

/** What a question is allowed to grow to before the field starts scrolling. */
const MAX_FIELD_HEIGHT_PX = 150

/**
 * Where the user says something.
 *
 * One lifted card rather than a field with a button beside it: deep corners, a
 * hairline, a shadow deep enough to separate it from the transcript running
 * underneath, and every control *inside* the card. The field itself carries no
 * border — it would be a second box inside the first.
 *
 * **The card is deliberately larger than the sum of what is in it.** The field
 * is the one thing on the screen the reader has to act in rather than read, and
 * a box sized tightly to a single line of placeholder reads as a search input —
 * something you type a phrase into. The padding above the field and the air
 * between it and the control row are what make it read as somewhere a question
 * gets composed. The corner radius grew with it, in `tailwind.config.js`.
 *
 * The height is where that room comes from, never the width. Widening the card
 * pushes the first line of a question across the reader's whole field of view
 * and turns the prompt into a page; the opening screen keeps its narrower
 * column for exactly that reason.
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

  // One picker for the menu row and for ⌘U. The input is hidden rather than
  // styled because a file input cannot be restyled reliably across browsers,
  // and every real product opens a native picker from a button of its own.
  const picker = useRef<HTMLInputElement | null>(null)
  const attachRequests = state.attachRequests
  useEffect(() => {
    // Zero is the initial value, not a press.
    if (attachRequests === 0) return
    picker.current?.click()
  }, [attachRequests])

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
    // Enter while an IME is still composing belongs to the IME, not to us.
    //
    // This is a Vietnamese product and Vietnamese is very often typed through
    // one: Telex and VNI build "ườ" out of several keystrokes, and the Enter
    // that commits the syllable is the same Enter that sends. Submitting on it
    // sends a half-typed word and swallows the keystroke that would have
    // finished it. `isComposing` is exactly the flag that separates the two,
    // and it is false for a keyboard that never opens an IME at all — so the
    // ordinary path is unchanged.
    if (event.nativeEvent.isComposing) return
    if (event.key === "Enter" && !event.shiftKey) {
      event.preventDefault()
      submit(event)
    }
  }

  return (
    <form
      onSubmit={submit}
      className={cn(
        "composer-shell relative rounded-composer bg-surface-sunken px-4 pb-4 pt-6",
        variant === "docked" && "shadow-composer",
      )}
    >
      {state.contextSymbol && (
        <div className="flex items-center gap-2 pb-2.5">
          {/* Neutral rather than amber, and it used to be amber. The desk's own
              pill a few pixels away is now the selected state on this card, and
              the send button's note below states the rule this follows: two
              oranges in one card compete. Of the two selections the mode is the
              consequential one — it changes the whole layout — so the accent
              went to it and the lens kept the ticker in mono, which is what
              made it legible as a symbol in the first place. */}
          <span className="inline-flex items-center gap-1.5 rounded-lg border border-border bg-surface-bubble py-1 pl-2.5 pr-1 font-mono text-meta text-ink-2">
            {state.contextSymbol}
            <IconButton
              label="Bỏ ngữ cảnh phân tích"
              size="sm"
              onClick={() => dispatch({ type: "context-symbol", symbol: null })}
              className="size-[17px] rounded-[5px] text-ink-4 hover:bg-foreground/10 hover:text-foreground"
            >
              <X className="size-2.5" strokeWidth={2.4} />
            </IconButton>
          </span>
          <span className="min-w-0 truncate text-meta text-ink-6">
            đang là ngữ cảnh phân tích
          </span>
        </div>
      )}

      {/* Above the field, where the context pill sits, because both
          answer the same question: what is travelling with this question
          besides its words. */}
      {desk.attachments.length > 0 && (
        <div
          role="group"
          aria-label={ATTACHMENT_COPY.region}
          className="flex flex-wrap items-center gap-1.5 pb-2.5"
        >
          {desk.attachments.map((attachment) => (
            <AttachmentChip
              key={attachment.key}
              filename={attachment.filename}
              byteSize={attachment.byteSize}
              image={attachment.image}
              previewUrl={
                attachment.previewUrl ??
                (attachment.id !== null && attachment.image
                  ? attachmentUrl(attachment.id)
                  : undefined)
              }
              status={attachment.status}
              error={attachment.error}
              onRemove={() => desk.detach(attachment.key)}
            />
          ))}
          {/* Said once for the row, not once per picture. The files are still
              stored and still travel; this is about what the model will do with
              them, and saying nothing lets a reader read a generic answer as a
              wrong one. */}
          {!desk.visionEnabled && desk.attachments.some((entry) => entry.image) && (
            <span className="w-full text-micro text-ink-6">
              {ATTACHMENT_COPY.imagesNotRead}
            </span>
          )}
        </div>
      )}

      <input
        ref={picker}
        type="file"
        multiple
        accept="image/png,image/jpeg,image/webp,text/plain,text/csv,.txt,.csv"
        className="hidden"
        onChange={(event) => {
          const chosen = Array.from(event.target.files ?? [])
          desk.attach(chosen)
          // Cleared so choosing the same file twice in a row fires `change`
          // both times — without this the second pick is silent.
          event.target.value = ""
        }}
      />

      <textarea
        ref={field}
        value={text}
        onChange={(event) => {
          dispatch({ type: "draft", text: event.target.value })
          resize()
        }}
        onKeyDown={onKeyDown}
        rows={1}
        aria-label="Hỏi VisgniteAI"
        // Short enough to fit the desk's narrowest column on one line. The
        // longer sentence this used to ask ("…một ngành hay cả thị trường") is
        // 43 characters, which wants ~330px and had ~305px to sit in once the
        // desk narrowed the conversation — so it wrapped, and the second line
        // was clipped by a box measured for one. Naming two of the three scopes
        // says the same thing in the width that exists.
        placeholder={
          state.contextSymbol
            ? `Hỏi về ${state.contextSymbol}, hay mã nào khác…`
            : "Hỏi về một mã hay cả thị trường…"
        }
        className="composer-field block max-h-[150px] min-h-[28px] w-full resize-none border-0 bg-transparent p-0 pb-5 text-[0.92rem] leading-[1.5] text-foreground outline-none placeholder:text-ink-6"
      />

      <div className="flex items-center gap-1.5">
        <div className="relative flex shrink-0">
          {attachOpen && (
            <AttachMenu
              onPickFile={() => {
                dispatch({ type: "overlay", overlay: null })
                picker.current?.click()
              }}
              onCapture={() => {
                // The menu closes first: the browser's own picker takes over the
                // screen, and coming back to a menu still open reads as a press
                // that did not land.
                dispatch({ type: "overlay", overlay: null })
                desk.startCapture()
              }}
              supported={desk.captureSupported}
            />
          )}
          <IconButton
            label="Đính kèm"
            aria-expanded={attachOpen}
            aria-haspopup="menu"
            onClick={(event) => {
              event.stopPropagation()
              dispatch({ type: "overlay", overlay: attachOpen ? null : "attach" })
            }}
            className="composer-icon size-9"
          >
            <Plus className="size-[19px]" strokeWidth={1.6} />
          </IconButton>
        </div>

        <SignalDeskToggle />

        <div className="ml-auto flex shrink-0 items-center gap-1.5">
          {/* `composer-model` is a container query, not a breakpoint: the row
              has to lay out for the width of this card and the desk makes that
              card narrow on a wide display. See `globals.css`. */}
          <span className="composer-model items-center gap-1.5 rounded-lg px-2 py-1 text-control text-ink-3">
            Visgnite Pro
            <ChevronDown className="size-3 shrink-0 text-ink-6" strokeWidth={1.8} />
          </span>
          {desk.canCancel ? (
            <button
              type="button"
              onClick={desk.cancel}
              disabled={desk.isCancelling}
              className="inline-flex h-9 shrink-0 items-center gap-1.5 whitespace-nowrap rounded-[10px] border border-border px-3.5 text-control text-ink-3 transition-colors hover:bg-foreground/[0.06] hover:text-foreground disabled:opacity-50"
            >
              <Square className="size-3.5" />
              {desk.isCancelling ? CANCELLING_LABEL : "Dừng"}
            </button>
          ) : (
            <button
              type="submit"
              title={SEND_LABEL}
              disabled={!text.trim() || desk.isSubmitting}
              // Inverted rather than coloured: the design makes this the one
              // solid light shape on the whole surface, which is what picks it
              // out without the accent colour — that is spoken for by the
              // context chip a few pixels away, and two oranges in one
              // card compete. `bg-foreground` inverts with the theme, so the
              // button stays the opposite of its ground in light mode too.
              //
              // Three states, and the pressed one is the point: this is the
              // last thing the reader touches before waiting, so it has to
              // acknowledge the press itself rather than leave them wondering
              // whether it registered. Lift on hover, settle and darken on
              // press, and no pointer events at all while there is nothing to
              // send — a disabled control that still reacts reads as broken.
              className="composer-icon inline-flex size-9 shrink-0 items-center justify-center rounded-full bg-foreground text-background transition-[filter,transform] duration-150 hover:-translate-y-px hover:brightness-110 active:translate-y-0 active:brightness-90 disabled:pointer-events-none disabled:opacity-40 motion-reduce:transition-none motion-reduce:hover:translate-y-0"
            >
              <WaveformIcon />
              <span className="sr-only">{SEND_LABEL}</span>
            </button>
          )}
        </div>
      </div>
    </form>
  )
}

/**
 * The mode the composer is in, as two named segments.
 *
 * A mode the reader enters, which is why it sits in the control row and not in
 * a menu: turning it on inverts the layout there and then — the conversation
 * narrows to its column, the workspace opens beside it — with or without a
 * picture in hand. Nothing about asking changes. The chat in the narrow column
 * is the same chat, and a question that draws nothing is answered exactly as it
 * was.
 *
 * **It was a switch and it is a segmented control now.** One pill that was
 * either lit or unlit put the whole burden of the mode on a colour: a reader
 * meeting it for the first time could see that something was on, and had no way
 * to learn what was off. Two segments name both halves, so the choice is
 * legible before it is made — and the design system already had the pattern
 * written down for exactly this, down to what the selected one looks like.
 *
 * **The selected segment is a raised neutral surface, not a filled accent.**
 * That is the system's own rule for segmented controls, and it is the right one
 * here: the lift says "this is the segment you are in" without spending the
 * page's one filled colour on a control that is not an action. The amber comes
 * back as *text* on the selected Signal Desk segment only — the accent marks
 * the consequential mode, and marks nothing at all while the reader is simply
 * chatting.
 *
 * **Two states, and no third.** The feature is free for everyone in this
 * release, so there is no locked state, no upgrade path and no popover
 * explaining a limit that does not exist.
 *
 * The decision is read from `useDesk` and written back through one function, so
 * an entitlement check later has exactly one edge to attach to.
 */
function SignalDeskToggle() {
  const desk = useDesk()
  return (
    <div
      role="radiogroup"
      aria-label="Chế độ trả lời"
      className="inline-flex h-9 shrink-0 items-center gap-0.5 rounded-[11px] bg-foreground/[0.05] p-0.5"
    >
      <ModeSegment
        selected={!desk.signalDesk}
        onSelect={() => desk.setSignalDesk(false)}
        label={SIGNAL_DESK_COPY.chatMode}
      />
      <ModeSegment
        selected={desk.signalDesk}
        onSelect={() => desk.setSignalDesk(true)}
        accent
        label={SIGNAL_DESK_COPY.toggle}
      />
    </div>
  )
}

/**
 * One segment of the mode control.
 *
 * `radio` rather than a pressed button: these are two values of one setting, and
 * the difference matters to anything not looking at the screen — a radio group
 * announces "one of two" and reads the unselected label out, which is precisely
 * the information the old single switch could not carry.
 */
function ModeSegment({
  selected,
  onSelect,
  label,
  accent = false,
  busy = false,
}: {
  selected: boolean
  onSelect: () => void
  label: string
  /** Whether this segment carries the accent while it is the selected one. */
  accent?: boolean
  busy?: boolean
}) {
  return (
    <button
      type="button"
      role="radio"
      aria-checked={selected}
      aria-busy={busy || undefined}
      // Only the selected segment is in the tab order, which is how a radio
      // group behaves everywhere else: one stop, then the arrow keys.
      tabIndex={selected ? 0 : -1}
      onClick={onSelect}
      className={cn(
        "composer-mode-segment inline-flex h-8 items-center whitespace-nowrap rounded-[9px] px-3 text-control transition-colors",
        "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 focus-visible:ring-offset-surface-sunken",
        selected
          ? cn("bg-surface-bubble", accent ? "text-primary" : "text-foreground")
          : "text-ink-5 hover:text-ink-2",
        busy && "animate-pulse motion-reduce:animate-none",
      )}
    >
      {label}
    </button>
  )
}

/**
 * The attach menu.
 *
 * Row one works. It uploads the file when it is chosen rather than when Send is
 * pressed, so the reader watches the progress while they are still writing and
 * the Turn itself carries a short list of ids.
 *
 * The rest still need something the backend does not expose. They stay inert
 * and keep the badge — a control that swallowed the press would be worse than
 * one that says it is not ready.
 */
export function AttachMenu({
  onPickFile,
  onCapture,
  supported,
}: {
  onPickFile: () => void
  onCapture: () => void
  /** Whether this browser can capture a screen. */
  supported: boolean
}) {
  return (
    <Menu className="absolute bottom-[44px] left-0 min-w-[250px]">
      <MenuItem
        icon={<Paperclip className="size-[17px] text-ink-4" strokeWidth={1.6} />}
        hint={ATTACHMENT_COPY.addHint}
        onClick={onPickFile}
      >
        {ATTACHMENT_COPY.add}
      </MenuItem>
      {/* Not "chụp màn hình bảng giá": it captures whatever the reader picks,
          and a name narrower than the behaviour is a name that misleads. When
          the browser cannot capture at all the row keeps its badge rather than
          becoming a control that swallows the press. */}
      <MenuItem
        icon={<Camera className="size-[17px] text-ink-4" strokeWidth={1.6} />}
        onClick={supported ? onCapture : undefined}
        disabled={!supported}
      >
        {CAPTURE_COPY.row}
      </MenuItem>
      <MenuSeparator />
      <MenuItem
        icon={<Wallet className="size-[17px] text-ink-4" strokeWidth={1.6} />}
        trailing={<ChevronRight className="size-4 shrink-0 text-ink-6" />}
        disabled
      >
        Thêm vào danh mục
      </MenuItem>
      {/* Two rows are deliberately absent from this menu.
          One was a calque of a competitor's feature name for work this product
          does under its own: the desk is a switch in the control row.
          The other was "Tra tin tức thị trường", and it is gone because the
          capability is already on. `web_search` and `fetch_url` are in the chat
          lane's toolset on every Turn, so a badge reading "Sắp ra mắt" over them
          was a false statement, and a switch for something already running is a
          switch that misleads. Where the reader sees what was looked up is the
          Sources panel, not a control here. */}
    </Menu>
  )
}
