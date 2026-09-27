/**
 * Every sentence the conversation surface says on the system's behalf.
 *
 * In one file because each of them is a promise about what the user is *not*
 * shown: a Turn that stopped early must carry a sentence and never its stable
 * code, the same way the rail maps a `Signal Issue` code to prose. Spread
 * across the components that render them, that rule would be enforced by
 * whoever happened to write the JSX.
 *
 * The whole interface is English: chrome and narration alike. Only the
 * answer text the backend writes keeps the language it was written in.
 */

import type { FlagReason } from "./types"

/**
 * What the list of tool calls says: its own label, and one word per outcome.
 *
 * The sentence describing a call is the backend's `summary`, because only the
 * side that made the call knows what it was for. What is left here is the
 * chrome around it — which is why there are three words and not three
 * templates.
 */
export const TOOL_CALL_COPY = {
  label: "Tools used", running: "Running…", ok: "Done", error: "Error",
  // A call written down before its effect ran, and one a permission rule
  // refused. Two more states, and each says something the other four cannot: a
  // pending call has not started yet, and a denied one never will.
  pending: "Queued", denied: "Not allowed",
} as const

/**
 * What a failed call says, when the reason is not that anything failed.
 *
 * Keyed by the backend's stable `error` code. Every entry here shares one
 * property: the call was refused by our own ceilings and never dispatched, so
 * nothing outside this deployment was even asked. Calling that "Error" tells the
 * reader to retry a search engine that is working perfectly well.
 *
 * A code with no entry keeps `TOOL_CALL_COPY.error`, which is the right default:
 * everything not listed here — a tool that threw, a page that would not load, a
 * name no tool answers to — really is a failure.
 */
const REFUSED_CALL_LABELS: Record<string, string> = {
  external_budget_exhausted: "Lookup limit reached", round_fanout_exceeded: "Not run", halted_turn: "Stopped",
  // Nothing ran and nothing will: the route is closed rather than broken, so the
  // word must not invite a retry.
  permission_denied: "Not allowed",
  // The source did not answer within the call's bound; it is not a broken page.
  tool_call_timeout: "Timed out",
}

/** The word shown beside a call that did not succeed. */
export function toolCallErrorLabel(error: string | null): string {
  if (error === null) return TOOL_CALL_COPY.error
  return REFUSED_CALL_LABELS[error] ?? TOOL_CALL_COPY.error
}

/**
 * The words around one question card.
 *
 * The prompt, the options and the skip label are the backend's — a card is
 * written where the question is decided, and a client that composed any of them
 * would be asking something other than what was meant. What is here is the
 * frame: what the card is, and what each settled state means now that pressing
 * it is over. `skip` is a fallback for a stored card that carries no label of
 * its own, never a rewording of one that does.
 */
export const QUESTION_COPY = {
  region: "A question for you",
  skip: "Skip",
  answered: "You chose",
  skipped: "You skipped this — the rest runs on the default assumption.",
  superseded: "You asked a follow-up, so this question no longer needs an answer.",
  failed: "Couldn't save this choice. Please try again.",
} as const

const TERMINAL_REASONS: Record<string, string> = {
  cancelled_by_user: "You stopped this turn.",
  shutdown: "The system restarted, so this turn stopped partway.",
  interrupted_restart: "The system restarted, so this turn stopped partway.",
  turn_deadline: "This turn ran past its time limit and stopped.",
  turn_failed: "This turn ran into a problem and stopped.",
  llm_call_timeout: "The model didn't respond in time, so this turn stopped.",
  answer_truncated: "The answer was cut off because it exceeded the length limit for one turn.",
  empty_answer:
    "The model route returned no answer for this turn. Try asking again.",
  deadline_expired: "Couldn't reach the model route in time, so this turn stopped.",
  gateway_timeout: "The model route didn't respond, so this turn stopped.",
  route_rate_limited:
    "The model route has used up its call allowance, so this turn stopped. Wait for the quota to reset, then try again.",
  route_error: "The model route returned an error, so this turn stopped.",
  context_overflow:
    "The conversation is longer than the model route accepts, so this turn stopped. Try starting a new thread.",
  output_cap_exceeded:
    "This turn needed more answer space than the model route allows, so it stopped. Try a narrower question.",
  content_policy_blocked: "The model route declined this question, so this turn stopped.",
  model_unavailable:
    "The model route no longer serves the configured model, so this turn stopped.",
  schema_rejected: "The model route didn't accept the tool catalog, so this turn stopped.",
  auth_unavailable: "Couldn't connect to the model route, so this turn stopped.",
  tool_timeout: "A tool ran past its time limit, so this turn stopped.",
  model_refusal: "The model declined to answer this question.",
  user_input_too_large: "The question exceeds the length limit for one turn.",
}

const UNNAMED_REASON = "This turn stopped before it finished."

/** The sentence for a stable reason. Never the code, whatever the code is. */
export function terminalSentence(reason: string | null): string {
  return (reason && TERMINAL_REASONS[reason]) || UNNAMED_REASON
}

/**
 * Everything the Signal Desk says, and the one thing it deliberately does not.
 *
 * The workspace's name is a proper noun the client chose, so it is not
 * translated and not paraphrased: the pill in the composer, the pane it opens
 * and the tab a picture files itself under are one feature, and a reader who
 * met it under three names would count three.
 *
 * **There is no "Save".** The design draws a save control beside the export one,
 * and there is no endpoint behind it — the sidebar's own "Saved reports" still
 * says "Coming soon". A button that swallowed the press would promise a reader
 * their work was kept, which is the one failure this surface cannot recover
 * from, so the control is absent rather than inert.
 */
export const SIGNAL_DESK_COPY = {
  /** The feature, wherever it is named. */
  name: "Signal Desk",
  /**
   * What the pane says while the desk is on and nothing has been drawn yet.
   *
   * Four parts rather than one sentence, and still no button: the composer is
   * the call to action three hundred pixels to the left, and a second one here
   * would send the reader looking for a control already under their hands. What
   * the empty pane owes them instead is *what will appear* — which is why the
   * shape of a board is drawn above the words, unlabelled and inert.
   *
   * `emptyStatus` is the one line that reports rather than explains: the desk
   * being on is a state the reader switched into, and it is the fact they will
   * check first if nothing arrives.
   */
  emptyStatus: "Signal Desk is on",
  emptyTitle: "Your analysis board will appear here",
  emptyBody:
    "Ask about a ticker, a sector or the whole market — each answer builds a board with figures, sources and export.",
  /**
   * The Universe, said where a reader is about to name a symbol.
   *
   * The count is written out rather than fetched. It is a deployment's own
   * declared Universe — thirty symbols, stated in the backend — and a figure
   * that arrived over the network would show a blank or a wrong number for the
   * first few hundred milliseconds of exactly the screen that exists to set an
   * expectation.
   *
   * No link under it. The design draws one to a list of the thirty, and there is
   * no page, popover or endpoint on this side that holds them — a link to
   * nothing teaches the reader that the product's links do not work, which
   * costs more than the list would have given them.
   */
  emptyUniverseHint: "Currently covers the 30 VN30 tickers — more coming.",
  /** What the pane says with the desk off and no picture in the conversation. */
  noDeskView: "No Signal Desk in this conversation yet.",
  /**
   * The pane while a Signal Desk Turn is still running.
   *
   * It reports rather than reassures. The previous answer's chart is not shown
   * behind this — a picture standing under a new question reads as an answer to
   * it — so the line has to say plainly that one is being worked out.
   */
  chartWorking: "Building the chart from evidence…",
  /**
   * The pane when the answer settled without a chart.
   *
   * One line, and no reason. The reason is a ledger of gaps and it is already
   * written in full in the column to the left; restating it here would be the
   * same explanation in two places, drifting apart at the first edit.
   */
  chartAbsent: "This answer has no chart with enough evidence.",
  /** The pane when the chart could not be drawn at all. */
  chartFailed: "Couldn't build a chart for this answer.",
  /**
   * The line under the chart: how many sources it rests on, and as of when.
   *
   * A count rather than the ids. The ids are the audit trail and they live in
   * the ledger; what a reader glancing at a picture needs is that it *has* one
   * and how old it is.
   */
  chartProvenance: (sources: number, asOf: string) =>
    `${sources} ${sources === 1 ? "source" : "sources"} · as of ${asOf.slice(0, 16).replace("T", " ")}`,
  chatMode: "Chat",
  toggle: "Signal Desk",
  sources: "Sources",
  deskEmptyHeadline: "Signal on your Desk",
  blockNoData: "No figures for this section yet.",
  blockAsTable: "Shown as a table — this one couldn't be charted.",
} as const


/**
 * The three questions the desk offers before it has been asked anything.
 *
 * Written to the shape of question the desk is for — one figure, in context,
 * with its sources — because the point of the row is to teach that shape. The
 * empty column is the only place a reader has to learn it from.
 *
 * They are offered into the field **unsent**. Two of them name a symbol, and
 * which symbols exist is a deployment's Universe rather than something this
 * bundle can know — so the reader gets the sentence with the ticker selected to
 * change, which is the same contract every other offered question follows
 * (`shell-state`, `ask`). Sending on the press would spend a Turn on whichever
 * ticker happened to be written here.
 *
 * Neither starter asks whether to buy or sell. The lane's prompt states levels
 * and consequences and declines instructions for a position, so a starter that
 * asks for one would be teaching the reader to ask for a refusal.
 */
export const SIGNAL_DESK_STARTERS = [
  "Which hours of the session does VCB's liquidity concentrate in?",
  "Where is VCB in its 52-week range, and which way is quarterly profit heading?",
  "Which tickers grew quarterly profit strongly while the price hasn't followed?",
] as const

/**
 * What the send control is called.
 *
 * It is never drawn as text — the button is an arrow — so this is what a screen
 * reader announces and what the tooltip says. Both need to be the same word,
 * which is why it is named once here rather than typed twice at the button.
 */
export const SEND_LABEL = "Send"

/**
 * What the stop control says once it has been pressed.
 *
 * Shared by the composer and status line so both places describe one state in
 * the same words.
 */
export const CANCELLING_LABEL = "Stopping…"

/**
 * Everything the attachment path says, including every way it says no.
 *
 * The refusals are named by the reason the backend sends rather than by status
 * code, and each one names the action left to take. A reader who sees "413" has
 * been told what happened to the request; a reader who sees "this file is larger
 * than 4 MB" has been told what to do next.
 *
 * `unknown` exists because a refusal this build has never heard of is still a
 * refusal, and a blank space beside a file that did not upload is the one
 * outcome with no reading at all.
 */
export const ATTACHMENT_COPY = {
  add: "Add file or image",
  addHint: "⌘U",
  /** On the button that takes one chip back off the question. */
  remove: (filename: string) => `Remove ${filename}`,
  uploading: "Uploading…",
  failed: "Upload failed",
  /** Read by a screen reader for the row of chips above the field. */
  region: "Attachments for this question",
  /**
   * Said once, beside the chips, when the route cannot read pictures.
   *
   * The file still uploads and still travels — this is a fact about what the
   * model will be able to do with it, not a refusal. Saying nothing would let a
   * reader attach a chart and read a generic answer as a wrong answer.
   */
  imagesNotRead: "This session's model can't read images yet — the image is still saved with the question.",
  refusals: {
    file_too_large: "This file is larger than allowed. Choose a smaller file.",
    media_type_not_allowed: "Only PNG, JPEG and WebP images and .txt, .csv text files are accepted.",
    empty_file: "This file is empty.",
    quota_rows: "You've stored too many files. Remove a few old ones and try again.",
    quota_bytes: "Your file storage is full. Remove a few old files and try again.",
    turn_image_budget: "These images are too large to send with one question. Remove one.",
    unknown: "Couldn't upload this file. Please try again.",
  },
} as const

/**
 * What the screen capture says.
 *
 * The preview step has its own words because it is the one gate on a real
 * privacy risk: `getDisplayMedia` hands back everything the reader agreed to
 * share, which can include a tab, a message, an inbox. Once it is sent it is
 * sent, so the copy has to make "look before you attach" the obvious reading.
 */
export const CAPTURE_COPY = {
  /** The menu row. Not "capture price board" — it captures anything. */
  row: "Capture screen",
  /** The preview dialog's accessible name. */
  title: "Review capture",
  explain: "Review before attaching. This image will be sent to the model.",
  accept: "Attach",
  discard: "Discard",
  /** Said on the row when the browser cannot capture at all. */
  unsupported: "This browser doesn't support screen capture.",
  /** The capture came back empty — a stream with no frame in it. */
  failed: "Capture failed. Please try again.",
} as const

/** The message for one refusal reason, falling back to the honest generic one. */
export function attachmentRefusal(reason: string | null | undefined): string {
  const table: Record<string, string> = ATTACHMENT_COPY.refusals
  return table[reason ?? ""] ?? ATTACHMENT_COPY.refusals.unknown
}

/**
 * What flagging a message says, and — the load-bearing half — what it does not.
 *
 * V1 has **no dispute workflow**. One action carries a
 * `message_id` and a reason label; it opens no ticket, notifies nobody and
 * suspends no account. So the acknowledgement states what was recorded and
 * stops there. A sentence like *"we will get back to you"* would be a promise the
 * system has no mechanism to keep, and the reader would be waiting for a reply
 * that is never coming — which is worse than an action that admits its limit.
 *
 * What the flag is actually for is said plainly instead: it is read when the
 * answers are reviewed. That is true — a flag confirmed as a genuine failure is
 * a defect somebody reads the transcript for — and it promises this reader
 * nothing.
 *
 * The four labels are the reader's vocabulary rather than the column's, so they
 * describe what went wrong in the answer and never name a mechanism: nobody
 * flags an answer for a validator's verdict, they flag it because the number is
 * wrong.
 */
export const FLAG_REASON_LABELS: Record<FlagReason, string> = {
  wrong_figure: "Wrong figure",
  overreach: "Conclusion goes beyond the data",
  wrongly_refused: "Wrongly refused to answer",
  other: "Other reason",
}

/**
 * The reasons this surface offers, in the order it offers them.
 *
 * Derived from the labels rather than listed a second time: the vocabulary is
 * already spelled once in `FlagReason` and once by the backend on the column it
 * validates, and a third in-app copy is a third place the four can disagree.
 * Key order is insertion order, so the record above is also the running order.
 */
export const FLAG_REASONS = Object.keys(FLAG_REASON_LABELS) as FlagReason[]

export const FLAG_COPY = {
  /** The control itself. Deliberately quiet: it sits under an answer, not in it. */
  action: "Report a problem with this answer",
  prompt: "What's wrong?",
  /**
   * Said once the pair is written. It records, and it promises nothing —
   * no ticket number, no reply, no deadline.
   */
  acknowledged:
    "Flag recorded. It's read when answer quality is reviewed, and it doesn't open a support request.",
  remove: "Remove flag",
  /**
   * Said when the write itself failed.
   *
   * The counterpart to the acknowledgement, and the reason the flag is never
   * shown optimistically: a mark that appeared and then quietly vanished would
   * tell the reader their objection was recorded when it was not. Silence here
   * is the same lie, so a rejected write says so.
   */
  failed: "Couldn't save the flag. Please try again.",
} as const
