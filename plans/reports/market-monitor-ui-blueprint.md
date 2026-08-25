# Market Monitor UI blueprint

## Product and composition thesis

Market Monitor is an **Operate** surface for self-directed Vietnamese investors who need to establish, in order: market direction, breadth, money flow, sector leadership, and the securities carrying that evidence. It stays inside the existing Analyst's Instrument Panel: the 274px collapsible sidebar remains the only navigation rail, the center remains the working surface, and the existing right inspector remains the only detail plane.

The center is a **five-lens workspace, not a dashboard of everything**. `Tổng quan` gives one bounded answer to each market question and links to depth; the four specialist lenses replace, rather than stack beneath, those summaries. There is no second sidebar, nested card wall, global KPI strip, or permanently visible five-chart grid.

## Workspace hierarchy

### Desktop (>= 1024px)

Inside the existing `AppShell` center column, `BoardView` becomes a thin coordinator with three vertical layers:

1. Existing `TopBar` (unchanged shell chrome).
2. `MonitorNavigation`, sticky to the top of the board scroll region:
   - first row: five tabs — `Tổng quan`, `Độ rộng`, `Dòng tiền`, `Ngành`, `Cổ phiếu`;
   - second row: shared context controls — exchange (`Tất cả`, `HOSE`, `HNX`), horizon (`1 phiên`, `5 phiên`, `20 phiên` where meaningful), and `Đến ngày`/latest-session selector;
   - right edge: compact freshness/coverage summary, e.g. `Cập nhật 14:32 · 312/329 mã`, with a textual state label when not complete.
3. One scrollable active-lens body, max width 1560px, with 18px between major sections and 12–14px inside working groups.

The sticky block uses the panel/ground tonal ladder and one bottom hairline; no shadow unless it visually overlaps scrolled content. Lens tabs are neutral segmented controls. The active tab uses a raised neutral surface plus `aria-selected`; do not spend the filled amber action on ordinary navigation.

When the inspector opens, preserve the current shell behavior: it occupies the existing 408px right plane, can resize from 320px, and folds the left sidebar before reducing the center below a usable width. At 1024–1199px, allow secondary timestamps and long control labels to collapse, but do not hide controls or evidence state.

### Mobile (< 768px)

Keep the existing top bar, then use one sticky compact header:

- Row 1: a full-width labeled select/combobox for the five lenses (`Chế độ xem: Tổng quan`), not another hamburger or horizontal tab strip that clips.
- Row 2: horizontally scrollable context controls in document order: exchange, horizon, date. The ends use spacing, not fades that imply hidden content.
- Row 3 only when needed: a full-width freshness/coverage notice. Complete/current state may remain a compact line in row 2; partial, stale, disconnected, or unavailable must be visible without opening details.

The active lens is a single column. Tables become deliberate record rows, not squeezed desktop tables: symbol/sector and primary reading on line 1; supporting measures and state on line 2; disclosure chevron/action at the end. Preserve logical reading order and expose the same sort/filter controls through an inline collapsible control bar, never a side drawer.

The existing inspector becomes a modal bottom sheet for narrow screens: 92dvh maximum, visible drag handle plus title, close button, and internal scrolling. It overlays rather than shrinks the lens, traps focus while open, restores focus to the invoking row, closes on `Escape`, and does not mutate the selected lens or its scroll position. It is the only mobile detail surface.

## First viewport contract

After navigation/context (roughly the top 96–112px of the board region), the first viewport must answer these in this visual order:

1. **Direction:** index level, signed move, and trend regime in one market-pulse band.
2. **Breadth:** advancing / declining / unchanged and the most decision-relevant trend-breadth reading.
3. **Leadership:** leading and lagging sector, each with return, relative strength, and participation.
4. **Flow:** current foreign/signed-flow reading and whether usable realtime coverage is partial.
5. **Freshness:** always visible in the sticky context or an inline state notice, with evaluated/eligible counts.

On desktop, use a 12-column composition: pulse spans 5 columns, breadth 3, leadership 2, and flow 2 when room permits. These are unequal working blocks, not same-size metric cards. On mobile, preserve the order above and show one compact block per question. No block may contain more than the answer, one supporting comparison, its as-of/state line, and one drill-down action.

## Five lens compositions

### 1. Tổng quan — “What is the market doing?”

- **Pulse band:** VNINDEX/HNXINDEX as applicable; level, signed point/% change, above/below MA20/50/200 text, and as-of. Use mono tabular figures and explicit `Tăng/Giảm/Không đổi` text alongside market color.
- **Breadth summary:** advancing, declining, unchanged; A/D ratio; one small proportional bar with a textual equivalent. Link `Xem độ rộng` carries exchange/date context.
- **Leadership pair:** one leading and one lagging sector row showing selected-horizon return, relative strength, advancing share, and coverage. Link `Xem các ngành` preserves horizon.
- **Flow summary:** foreign net for the selected horizon plus active-flow/ADTV when available. If realtime covers only part of the cohort, label it `Realtime một phần · evaluated/eligible`; never blend it into a full-market claim.
- **Notable evidence:** a bounded list of at most 5 securities selected by the API response. Each row opens the existing symbol inspector. Do not append breadth history, full sector grid, rankings, and a stock board below this; specialist lenses own them.

### 2. Độ rộng — “Is the move broad?”

- Start with advancing / declining / unchanged and A/D ratio as one comparison row.
- Main body is a two-part analysis plane: return-distribution buckets (CSS/SVG bars with count labels) and the A/D line over the available sessions (inline SVG plus a visible point/table summary).
- Follow with trend breadth (`Trên MA20`, `Trên MA50`, `Trên MA200`), then highs/lows (`20 phiên`, `252 phiên`) and advancing-volume share.
- Every percentage names its denominator through the shared coverage line; missing time-series points break the line and expose a reason, never interpolate silently.
- Clicking a distribution bucket routes to `Cổ phiếu` with the corresponding supported filter only; if the API has no matching stock filter, render the bucket as non-interactive.

### 3. Dòng tiền — “Where is money moving?”

- Header comparison: foreign net `1/5/20 phiên` and active-buy share, with the selected horizon emphasized neutrally.
- Main composition: inflow and outflow ranked lists on opposite sides at desktop, stacked on mobile. Rows show symbol, net value, flow/ADTV, price direction text/sign, source state, and open the symbol inspector.
- A separate `Đảo chiều` list follows only when returned by the API; absence is an explicit empty finding, not an empty panel.
- Optional price/flow quadrant is a compact CSS/SVG plot only when comparable rows have both axes; provide an adjacent accessible table and quadrant labels. Do not synthesize points from missing metrics.
- Realtime and EOD evidence remain visually and verbally distinct. `disconnected` realtime keeps historical foreign-flow content visible with a scoped notice explaining what is unavailable.

### 4. Ngành — “Which sectors lead?”

- Top control is a neutral horizon switch (`1`, `5`, `20 phiên`) tied to URL state.
- Primary view is a sortable sector comparison table on desktop and ranked sector rows on mobile: sector, horizon return, relative strength, advancing share, liquidity ratio, rotation label, and coverage.
- Above the table, one thin leader-to-laggard strip may summarize ordering; it supplements rather than replaces labels and values.
- Selecting a sector routes to `Cổ phiếu` with `sector_code`, exchange, horizon/date, and a visible removable sector filter. A secondary disclosure can open a compact sector detail within the same lens only if no new backend read is needed; it must not create another sidebar.
- Rotation is written as a label supplied/derived by the backend contract; color is optional support, never the classification itself.

### 5. Cổ phiếu — “Which stocks carry the evidence?”

- Begin with preset tabs mapped directly to the API `lens`: `Tổng hợp`, `Xu hướng`, `Dòng tiền`, `Định giá`. Presets change the column set; they do not create one mega-table.
- Inline controls: sector filter, supported sort field, direction, and a concise active-filter summary. Exchange/date remain in the shared context bar.
- Desktop table keeps `Mã` sticky left and the primary measure visible; each preset should target 5–7 visible columns:
  - Tổng hợp: symbol/name, sector, 1D/5D/20D return, liquidity ratio.
  - Xu hướng: symbol/name, 1D/5D/20D return, trend measures actually present in `metrics`.
  - Dòng tiền: symbol/name, foreign 20D, foreign/ADTV, active-flow/ADTV, price return.
  - Định giá: symbol/name, P/E, P/B, and percentile/sector comparison only when supplied.
- Treat `metrics` as contract-driven: a preset renders only named real metrics; unsupported/missing values are `—` plus a nearby or inspector-readable issue. Never infer a value or show zero as absence.
- Cursor pagination uses `Xem thêm`/next-page loading while retaining prior rows; preserve sort/filter state and per-lens scroll in keyed memory. Each row opens the existing symbol inspector without changing the lens URL.

## Evidence, loading, and failure states

Use one shared state vocabulary and presentation across lenses:

| State | Treatment | Content behavior |
|---|---|---|
| `complete` | Quiet metadata line: as-of, source count, `evaluated/eligible` | Full composition |
| `partial` | Persistent inline notice before affected content; exact evaluated/eligible and issue summary | Render valid values; mark affected metrics/rows |
| `stale` | `Dữ liệu cũ` label plus effective time and age/recovery action | Keep last valid evidence visible |
| `disconnected` | Scoped connection notice naming realtime as unavailable | Preserve EOD/historical content; no silent fallback claim |
| `unavailable` | Plain reason and recovery/constraint text in the owning section | No zero, blank chart, or fabricated placeholder |

- **Initial loading:** keep navigation/context usable; render structural skeletons with stable dimensions and one `role="status"` announcement. Do not pulse colored market figures.
- **Background refresh:** retain data, add a quiet `Đang cập nhật…` status near freshness; avoid whole-lens opacity changes.
- **Empty success:** state the applied exchange/filter/date and offer a scoped reset when applicable (`Xóa bộ lọc ngành`), not a generic “no data.”
- **Request error:** one lens-level notice names the failed read and offers `Thử lại`; navigation and cached neighboring lenses remain usable.
- **Metric absence:** render `—`; expose the server `issues` reason in visible supporting text for key metrics and in row detail/inspector for dense tables.
- **No illustrative values:** remove the current sample liquidity/foreign/contribution data from the monitor path. API-backed values or explicit unavailable states are the only permitted content.

Amber remains scarce: use it for the focus ring and at most one filled recovery/primary action per view. Positive/negative, ceiling/reference/floor, and neutral series colors retain market meaning only; every use has a sign, label, value, pattern/position, or explanation.

## Drill-down and inspector contract

- Lens summary links update the durable URL and push browser history. High-frequency filter/sort changes replace history. Back/forward restores lens, controls, and keyed scroll without closing unrelated shell context.
- Sector drill-down: `Ngành -> Cổ phiếu` adds `sector_code`; stock drill-down opens the existing inspector and does **not** navigate away.
- The symbol inspector extends its current symbol tab in this order: identity/current reading, trend, flow, valuation, then provenance. Sections use the monitor stock-detail response at the board's exchange/as-of context.
- Inspector provenance shows source, effective/as-of time, freshness, method version, quality state, and issues. A value and its evidence must remain visibly associated.
- Search and the existing `select-symbol` reducer action remain authoritative. Do not create separate monitor-selected-symbol state. Opening/closing/resizing the inspector must preserve active lens, URL filters, draft, sidebar, transcript, and lens scroll.
- On desktop, row activation leaves focus on the row while the inspector opens; a deliberate shortcut/button may move focus into the inspector. On mobile bottom sheet, move focus to the sheet heading/close control and restore it on close.

## Accessibility and keyboard implementation

- Desktop navigation is `role="tablist"`; tabs use `role="tab"`, `aria-selected`, `aria-controls`, roving `tabIndex`, Left/Right (or Home/End) movement, and activation that updates history. The active body is `role="tabpanel"` with an accessible name.
- Mobile lens control is a native `select` or a fully compliant labeled combobox. It exposes the same five choices and URL behavior as desktop.
- Context controls are grouped under `aria-label="Phạm vi thị trường"`. Visible labels remain available at compact widths; icon-only controls retain `title` and `aria-label`.
- Use semantic tables with `scope="col"`; sortable headers are buttons with `aria-sort`. Rows should contain a real button/link for detail rather than relying solely on a focusable `<tr>`.
- All drill-down actions work with Enter/Space. Escape closes the inspector/bottom sheet. The desktop resize separator keeps current Arrow, Shift+Arrow, Home, and End behavior.
- New content and refresh messages use a polite live region; request errors use `role="alert"`. Do not announce every changing price cell.
- CSS/SVG visuals have an accessible summary and table/list equivalent. SVGs are `aria-hidden` when redundant; otherwise provide a concise accessible name and descriptions of axes/units.
- Focus rings use the existing contrast-safe amber ring. Sticky headers must not cover focused rows (`scroll-margin-top` matching the sticky stack). Touch targets are at least 40px on mobile.
- Numerals use JetBrains Mono/tabular figures; Vietnamese labels use Inter with the Vietnamese subset. Body/metadata contrast meets 4.5:1; color never carries the only meaning.
- Honor `prefers-reduced-motion`; lens changes need no entrance choreography. Keep existing restrained row/bar motion only where it explains arrival and disable it under reduced motion.

## State ownership and implementation boundaries

- URL owns: `view=board`, lens, exchange, horizon/window, as-of, sector/filter, preset, sort, and direction. Lens changes push; filter/sort edits replace.
- Existing shell reducer owns: sidebar, inspector tab/width, selected symbol, overlays, draft, transcript context, and viewport. Preserve these contracts.
- Keyed in-memory state owns per-lens scroll and cursor-loaded pages; keys include lens plus canonical durable filter state.
- `BoardView` coordinates navigation, URL adapter, state boundary, and active lens only. Each lens owns one query hook/composition; shared monitor primitives own figures, coverage/provenance, charts, tables/rows, and state notices.
- Use existing Tailwind tokens, Lucide icons, CSS, and inline SVG. Add no chart library, no decorative shadow system, and no new shell navigation region.

## Acceptance checklist

- Desktop and mobile reach all five lenses with identical durable state and no second sidebar.
- The first `Tổng quan` viewport answers direction, breadth, leadership, flow, and freshness without becoming a mega-dashboard.
- Each specialist lens has one clear comparison task and routes deeper context rather than duplicating every metric.
- Partial/stale/disconnected/unavailable evidence remains explicit, scoped, and numerically honest.
- Stock selection reuses the existing inspector and reducer state; shell draft, conversation, sidebar, history, and scroll survive navigation.
- Keyboard, focus restoration, semantic tables/tabs, live announcements, textual chart equivalents, contrast, and reduced motion are testable from this contract.

## Open decisions

None. Metric labels and column availability must be resolved from the shipped API keys; builders must not invent unsupported mappings.
