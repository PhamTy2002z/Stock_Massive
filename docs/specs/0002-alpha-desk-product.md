# Product specification — Alpha Desk

The user-facing half of **Intelligent Quant**. It turns the decisions closed on the
Wayfinder map ([issue #16](https://github.com/PhamTy2002z/Stock_Massive/issues/16))
into buildable product behaviour: the flows, the Watchlist rail, the
Analysis artifact, and the loop a user actually repeats.

The architecture that serves it is
[`0003-intelligent-quant-architecture.md`](0003-intelligent-quant-architecture.md).
Decisions that are hard to reverse live in `docs/adr/0007` … `0016`; this spec states
what is built, and points at the ADR when a reader will want the argument.

Terms in **bold** are glossary terms and always carry their `CONTEXT.md` meaning.

## 1. What Alpha Desk is

**Alpha Desk** is the first sidebar tab of the existing app. It is an agent surface —
a tool-calling loop with streamed answers, persisted **Threads**, and generated
**Widgets** — sitting above a deterministic nightly **Analysis** pipeline.

Two sentences fix the product:

> **An Analysis is an artifact, not a page.** The existing sidebar is for looking up
> numbers; Alpha Desk is for asking what to do about them.

> **This is not a chatbot.** Any reduction of it to "prompt in, text out" has misread
> the destination.

### What it does not touch

- Every existing page stays exactly as it is. `apps/web` gains one route plus the
  Next Route Handler proxy of ADR-0013.
- **Alpha Desk never redraws a chart Stock 360 already owns** — OHLCV, candlesticks,
  volume, valuation history, price ranges, peer valuation. It carries the verdict, the
  price zone, and the decisive figures, then deep-links to
  `/analytics/deep-dive?symbol=`. One number lives in one place (ADR-0012).
- No global assistant dock on the other tabs in v1. Deep-linking `?symbol=` from other
  pages buys most of that value.
- `fetchApi` in `src/lib/api.ts` is unchanged. Retro-fitting auth onto the app's
  existing hooks is its own effort.

### The two facts a new reader gets wrong

- **The Watchlist does not exist in the web app today.**
  `src/app/(dashboard)/watchlist/` is empty scaffolding. The Watchlist UI is greenfield
  and lives *inside* Alpha Desk as a symbol rail, not as its own sidebar tab. It exists
  because the nightly Analysis needs to know which symbols to run — it is Alpha Desk's
  input.
- **The Watchlist is not the agent's gate.** The agent answers on **any Universe
  symbol**; it refuses only symbols outside the **Universe**. The Watchlist decides
  which symbols are re-analysed nightly and which appear on the rail — nothing more.
  Gating the agent on it would make a user spend one of ten slots to ask one question,
  against a Universe of a hundred.

## 2. Information architecture

**Symbol-first for information, conversation-first for interaction.**

- The **Watchlist** is the durable set of symbols the user chose for nightly
  production, and it is a compact persistent dock or strip — never a competing
  full-height rail.
- The **active symbol** organises its latest Analysis, its Analysis history, and
  related research. It is a workspace *lens*, not a persistence key.
- **Chat owns the main canvas** and almost all available width. Switching symbols
  changes the Analysis context without forcing a new Thread.
- A **Thread** is free-roaming and carries the set of symbols it touched. It is never
  owned by one symbol.

**Threads are secondary retrieval, not primary navigation.** They live under
*History / Related Analysis* and become prominent only when the user deliberately
returns to earlier research. The default surface never asks the user to choose a Thread
before asking a question. Recent Threads may appear in a compact popover or history
panel, and symbol-scoped related Threads inside the active symbol's history, but
neither becomes a permanent desktop rail.

### The shell seam

There is no route-group layout today; each page wraps `DashboardLayout` itself and
`<main>` is `flex-1 overflow-auto p-6`. A full-height agent panel uses
`DashboardLayout`'s bleed behaviour plus an inner `h-full min-h-0` tree whose
conversation owns its own scroll container. The desktop header actions need progressive
collapse on narrow viewports.

## 3. The Watchlist rail

### Cap and mutation

- **Ten symbols per user**, shown permanently as a count (`7/10`). Unlike the Universe
  cap — a collector safety valve that never reaches the interface — users collide with
  this one every time they add a symbol, so hiding it until it is full turns the first
  collision into a surprise error.
- An **Analysis** is keyed by `(symbol, trading_day)` and shared system-wide, so **a
  freed slot is immediately reusable with no mutation rate limit**: removing FPT and
  re-adding it the same day re-reads the existing Analysis at zero cost.
- **Removing a symbol deletes nothing.** The rail lists only current symbols, but old
  Threads and links stay alive and the agent can still read those Analyses. Removal is
  a statement about what keeps being analysed, not about history.
- Adding is restricted to symbols currently in the **Universe**; anything else is
  refused with the reason named.
- The accepted trade-off, stated in the glossary: **an Analysis is not personalised.**

### Five states, and `failed` never renders empty

`ready` · `pending` · `producing` · `failed` · `unsupported`

- **`failed` shows the most recent Analysis** plus a label — *"chưa có Analysis cho
  phiên 12/08"* — and a retry. An empty cell tells the user there is nothing to see
  when a month of history exists.
- **Retry** may be triggered by any user with that symbol on their Watchlist;
  production is idempotent per `(symbol, trading_day)`, so two people retrying is one
  run. Capped at **three attempts per symbol per session**, then locked until the next
  session. The third failure surfaces a human-readable reason — *"no session data for
  FPT"*, *"LLM route did not respond"* — never a stack trace.
- **`unsupported`** is one state covering both a real delisting and an operator
  trimming the Universe, because v1 cannot tell them apart and does not pretend to. The
  symbol stays on the rail, its history stays readable, no new Analysis is produced, it
  **does not count against the cap**, and there is an explicit remove button. A symbol
  restored to the Universe **revives automatically**; if that pushes the Watchlist over
  ten, the overflow stands and *adding* is blocked until the user trims — the system
  never picks which symbol to evict.

Auto-removal was rejected: it destroys a user's choice because of an operator's config
change, converting a reversible change into data loss.

### What "today" means on the rail

- **Trading Day** is data-defined — the latest day for which an EOD **Snapshot**
  exists. The rail shows that day, labelled with its date (*"phiên 08/08"*), **never
  "today"**.
- Non-trading days produce nothing and show no extra chrome, just the dated label.
- **One system-level status line**, not per symbol, appears only when today is a
  weekday **and** 16:15 ICT has passed **and** no Snapshot exists for today:
  *"Dữ liệu phiên 12/08 chưa về."* Weekends and holidays show no line.
  The accepted cost of having no holiday calendar is that this informational line fires
  once on a public holiday — one redundant sentence, rather than an Analysis labelled
  with a session that never happened.

### How a user learns today's Analysis is ready

**No external channel in v1.** The rail polls, following the TanStack Query pattern
already used by `JobProgressBar`, and an unread badge counts symbols with a new
Analysis. `last_seen_analysis_date` is per user per symbol and advances **only when
that specific Analysis is opened** — not on app open, which would clear the badge for
all ten symbols at once and make the indicator meaningless exactly when it has work to
do.

Email needs SMTP credentials and web push needs VAPID keys plus a service worker: both
are new infrastructure for an unmeasured problem with a handful of internal users who
all open the app in the evening. If someone is later observed missing Analyses, email
is the cheapest next step and the badge already persists the data it needs.

### History depth

Analyses are kept indefinitely. The rail browses the **last 90 sessions**; anything
deeper is reached through the agent's `get_analysis(symbol, date)`.

## 4. The core loop

1. **Evening.** The user opens Alpha Desk. The rail shows ten symbols against the
   latest Trading Day, with a badge on those whose Analysis they have not opened.
2. **Read.** Opening one renders the Analysis inline in the transcript as a bounded
   artifact. Opening it advances that symbol's `last_seen_analysis_date`.
3. **Ask.** The user asks about what they just read, or about any other Universe
   symbol. The answer streams as complete blocks, with a collapsed activity line while
   tools run, and at most one **Widget**.
4. **Expand or leave.** The artifact expands to full width for the briefing treatment,
   or the deep link hands off to Stock 360 for any chart Alpha Desk does not own.
5. **Adjust.** Adding a symbol produces an on-demand Analysis for the latest
   **Snapshotted** session; removing one frees a slot immediately.

Two lanes feed step 1: the nightly batch over the **union of all Watchlists**, and
on-demand production when a symbol is added. On-demand **always** produces for the
latest `trading_day` that already has a Snapshot, with no exceptions — adding FPT at
10:00 yields an Analysis for yesterday's session, clearly labelled, and from 16:15 the
next day the symbol joins the batch normally. Any exception would mint an artifact
labelled with a session that has not closed, which cannot be diffed against the
official one that evening.

A user may create at most **three new on-demand Analyses per Trading Day**. Adding a
symbol whose Analysis already exists costs nothing and does not consume the allowance;
above it, the addition still succeeds and its Analysis waits for the next nightly
cohort.

**A new user's Watchlist is genuinely empty — no seeding.** Every seeded symbol is an
Analysis produced that night for a holding nobody chose.

## 5. The Analysis artifact

An Analysis renders **inline in the transcript** and expands to full width. It is never
a page.

### Two treatments

- **Inline — bounded height.** A pinned verdict and price-zone band, with the four
  fixed-order axes as **tabs**. The industry-selected lead axis opens first. Bounded
  because a Thread may hold ten of these.
- **Expanded — the briefing.** Verdict, thesis, price-zone band, then all four axes
  and their decisive figures in fixed order.

### The fixed template

Section set and order are invariant: `technical → fundamental → money_flow → news`.
Exactly one axis is `lead`; the others are `support` or `context`.

The model may choose `emphasis`, `emphasisReason`, the lead tab, and which
industry-specific registered fields occupy each axis's slots. It may **not** choose
section order, section membership, or layout. Model-chosen paragraph order was
prototyped and rejected: "fixed template" means the reader's eye learns one shape.

Emphasis is therefore visible as *which tab opens* and *how much space an axis gets* —
never as a reordering. Worked examples from the prototype fixtures: a bank leads
`fundamental`; a developer leads `money_flow` because it is the only axis over its
calibrated threshold and the only number that arrived today; a retailer leads
`technical` and carries an honest hole where a 273-session momentum window crosses a
price-basis seam.

### What the artifact carries

Backend-owned envelope: the price zone, the four sections with their figures and
health, `windowHealth`, the news block, the **Risk Notice**, `citedFieldIds`, and the
audit metadata. Model-owned fragment: `verdict`, `verdictLine`, `thesis`,
`citedFieldIds`, and per axis `emphasis`, `emphasisReason`, `read`.

`verdict` is a **single value** — `accumulate | hold | reduce | avoid | watch` — never
a structure, because the rail reads it as an extracted column to show one word for ten
symbols.

Per figure the artifact shows: label, value, unit, `kind`, `source`, the sanctioned
`interpretation`, an `asOf` staleness stamp, and `health` with a mandatory reason when
it is not `ok`.

### The price zone is a number, not a target

The zone is a registered field computed in code — this symbol's ordinary daily range —
and it reads that way. The verdict is the model's judgment and rests only on registered
fields (ADR-0010). The **only inline graphic is the price-zone band**; everything else
deep-links.

### Honesty states are first-class

`degraded`, `insufficient_history`, and `refused` fields stay visible with their reason
rendered directly — not hidden in a tooltip, not deferred to the expanded view. A
refused field shows `value: null` and its reason, may be read as evidence of what the
system could not see, and **can never support the verdict**.

### Language split

Application chrome and registered field labels are **English**, matching the rest of
the app. Model narration and human-readable health reasons are **Vietnamese**.

### Citations

The inline artifact shows the **citation count**; the expanded and audit views expose
the exact registered field ids. The stored payload always carries the complete
`citedFieldIds` list.

## 6. The conversation surface

### How an answer reads

- **Conclusion first**, in two to four concise bullets, in the user's language with
  Vietnamese as the default.
- Facts, interpretation, reference actions, and risks are visibly separate. Units and
  `as_of` sit next to material figures.
- Formulas, method names, and implementation detail appear only on demand, under
  **View details** and an expandable **Sources & methods** surface.
- *"I don't know"* and *"the data is insufficient"* are valid answers.
- No certainty claims, and no personalised allocation, leverage, or position sizing —
  the system does not know the user's assets, horizon, or loss tolerance. It may state
  an analytical stance (*wait for zone X*, *avoid chasing*), and it may compute an
  explicitly-assumption-bearing scenario when the user supplies the assumptions.

### Streaming, as the user perceives it

Content arrives as **complete blocks** — a paragraph, a bullet group, a finished table
— with a light 150–200 ms reveal. **There is no typewriter effect.** A reopened Thread
or a reconnect renders everything already present at once, with no staged replay.
Reduced-motion removes the transition.

While tools run, a **collapsed activity trail** shows the work as a short list of
steps: the phases already finished, then the one in flight — *Searching…*, *Reading
data…*, *Analyzing…*, *Preparing visual…*, each expandable to a compact user-facing
summary of the semantic operation. A finished step stays on screen in the past tense;
only the step in flight is announced to assistive technology. Consecutive repeats of
one phase are one step.

The trail is **never a raw trace, and never a tool name, symbol, argument, or
result** — the publisher sends a phase and only a phase, so the vocabulary on screen
is those four words whatever the Turn actually called. The full detail stays in the
**Tool Call Trace** as an audit surface. The trail is what *this tab watched happen*:
a reconnect keeps the steps it saw, and a tab that joined a Turn late shows none
rather than inventing the ones it missed.

The harness must feel like it is *working*, not hung: the first block or activity line
arrives well before completion, and a heartbeat keeps a quiet path observable.

### Widgets

At most **one Widget per answer** by default; a second requires an explicit request. A
single value stays text. A Widget appears only when a visual makes a comparison,
ranking, trend, or relative position easier to understand than words, and it always
carries a plain-language *"what this means"* line plus its data date. Reopening a
Thread re-renders the same fixed historical slice — never today's numbers. The four v1
forms and their accessibility contract are in ADR-0012.

### A pending on-demand Analysis

Never blocks the composer. The user keeps talking while it runs, durable-looking steps
show progress, and the **previous Analysis stays reachable** rather than being replaced
by emptiness.

### Cancellation and failure

Cancel is immediate in the UI (*Cancelling…*, button disabled) and keeps every block
already received. A Turn that stops early — budget, deadline, shutdown — keeps its
useful content and adds a short status plus retry; **the UI never replaces useful
content with a full-screen error.** Retry starts a new Turn; the old one stays
immutable. A network reconnection is not a retry.

## 7. Entry points

### First run

No Watchlist, no Thread. The empty state makes two things explicit:

- the user may discuss **any Universe symbol**, while only Watchlist symbols receive
  nightly production;
- the scope boundary, in user language — *four-axis analysis for Watchlist symbols; no
  ad-hoc computation* (ADR-0011). The catalog itself is not published; a refusal
  teaches the detail at the moment it matters.

### Deep link

Arriving with `?symbol=HPG` from Stock 360 carries the symbol into context as the
active lens and opens a new free-roaming Thread. **It never silently adds HPG to the
Watchlist.**

### Refusals

A symbol outside the Universe gets a polite refusal plus up to three same-industry
Universe suggestions, computed by query. A request for a computation that does not
exist gets a refusal that **lists what is available** plus the nearest answerable
question.

## 8. Narrow viewports

Mobile *web* only; the native app is out of scope.

- The symbol dock scrolls or collapses horizontally rather than the layout being
  replaced. The interaction model survives unchanged.
- *History / Related Analysis* collapses into an on-demand surface. It does not become
  a second permanent navigation level.
- Artifact expansion is a modal overlay, not a forced desktop width.
- A Widget uses the available width and may become a list or table rather than forcing
  horizontal scrolling or an illegible chart.
- Header actions collapse progressively.

## 9. What the user never sees

| Never shown | Why |
| --- | --- |
| The Universe cap of 100 | An operational safety valve, not a quota sold to users (ADR-0001) |
| USD amounts, budgets, reservations | Users see state and reset time; operations sees money (ADR-0014) |
| Raw Tool Call Traces, tool names, arguments | The activity line is semantic; the trace is an audit surface (ADR-0013) |
| Prompt text, hidden reasoning, credentials | Non-overridable invariant of the System Prompt Contract (ADR-0015) |
| A `Signal Issue` code, verbatim | Codes map to short Vietnamese sentences in one place |
| A number that could not be proven | An unprovable block is never displayed and flagged later (ADR-0015) |

## 10. Out of scope for v1

Each of these is a closed decision, not an omission.

- Rebuilding `apps/web` around chat — the original premise, superseded.
- Long-term per-user memory (risk appetite, holdings, habits). V1 memory is
  thread context plus tool access to past Analyses.
- General web search beyond the cleared per-symbol news sources — the largest injection
  surface in the system, and legally exposed.
- A global assistant dock on the other tabs.
- Ad-hoc code execution (ADR-0011).
- Billing and package tiers. V1 is internal: login, Watchlist, a hard-coded cap.
- Symbols outside the Universe.
- Intraday or real-time re-analysis. An Analysis is a daily artifact.
- Mobile app.
- A dispute workflow. What v1 *does* ship is one action — **flag a message**, carrying the
  message and a reason label (wrong figure / overreach / wrongly refused / other). It
  opens no ticket and starts no process; its value is that a confirmed failure becomes a
  new Eval Case (ADR-0016). Replay means someone re-reading the evidence, and the product
  should not imply otherwise.
- Notifications of any kind. Polling plus the unread badge, per §3.

## 11. Definition of done

Alpha Desk is shippable when all of the following hold.

1. A user can add up to ten Universe symbols, see a truthful state per symbol against
   the data-defined **Trading Day**, and never see an empty cell where history exists.
2. Two users watching one symbol read exactly one Analysis for that Trading Day, and a
   removed-then-re-added symbol produces no second one.
3. An Analysis renders inline as the bounded artifact and expands to the briefing, with
   `degraded` and `refused` fields visible and their reasons rendered.
4. A Turn survives a page reload, a route change, and a network drop, and only an
   explicit cancel ends it.
5. An answer's material figures each resolve to a registered field from the same Turn;
   nothing unprovable is ever displayed.
6. The **Risk Notice** is present on every completed and useful incomplete assistant
   message, attached by the backend.
7. No user request reaches a **Provider Source** except through the `search_news` lane.
8. **One passing `gate` run of the Eval Battery** (ADR-0016). This is part of done, not
   a follow-up.
9. The repository gates pass: `make test` in `apps/api`, and `pnpm type-check`,
   `pnpm lint`, `pnpm test`, `pnpm build` in `apps/web`.

## 12. Open product questions

Genuinely undecided, and none of them blocks a build session from starting.

1. **Whether the previous Analysis is promoted inline during a pending on-demand run**,
   rather than shown as a compact link. Decide from usability observation, not in
   advance.
2. **The decommission plan** for anything in the current web app that Alpha Desk makes
   redundant. Not phrasable until the artifact and the harness are real enough to show
   the overlap.

## Primary sources

The two prototypes are primary sources and are **not** merged into `develop`; the
selected behaviour is re-implemented as production code with tests.

- `prototype/analysis-artifact` — commits `1fb7e6d`, `374aebc`. Four artifact shapes;
  inline **D** plus expanded **A** selected.
- `prototype/alpha-desk-harness` — commits `b6d2d51`, `e59b2ad`, `05b1b00`. Three
  harness shapes over six states; **B**'s information architecture plus **C**'s
  interaction model selected.
