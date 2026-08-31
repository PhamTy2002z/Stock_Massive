---
version: alpha
name: VisgniteAI
description: A precise, evidence-led instrument panel for Vietnamese market intelligence.
colors:
  ignition-amber: "hsl(30 91% 58%)"
  ignition-amber-day: "hsl(30 76% 36%)"
  cool-night: "hsl(210 6% 7%)"
  slate-panel: "hsl(220 6% 10%)"
  slate-raised: "hsl(220 5% 12%)"
  slate-sunken: "hsl(220 4% 13%)"
  slate-menu: "hsl(220 4% 14%)"
  slate-bubble: "hsl(210 5% 16%)"
  paper-ink: "hsl(0 0% 98%)"
  quiet-ink: "hsl(214 3% 56%)"
  day-paper: "hsl(220 12% 97%)"
  day-ink: "hsl(220 10% 10%)"
  market-green: "hsl(140 50% 50%)"
  market-red: "hsl(3 72% 60%)"
  ceiling-violet: "hsl(262 77% 75%)"
  reference-gold: "hsl(45 76% 62%)"
  floor-cyan: "hsl(187 59% 61%)"
typography:
  display:
    fontFamily: "Newsreader, Georgia, Times New Roman, serif"
    fontSize: 2.15rem
    fontWeight: 400
    lineHeight: 1.1
    letterSpacing: "-0.01em"
  body:
    fontFamily: "Inter, Helvetica Neue, Arial, system-ui, sans-serif"
    fontSize: 0.9375rem
    fontWeight: 400
  row:
    fontFamily: "Inter, Helvetica Neue, Arial, system-ui, sans-serif"
    fontSize: 0.9rem
    fontWeight: 400
    lineHeight: 1.3rem
  control:
    fontFamily: "Inter, Helvetica Neue, Arial, system-ui, sans-serif"
    fontSize: 0.86rem
    fontWeight: 500
    lineHeight: 1.25rem
  metadata:
    fontFamily: "Inter, Helvetica Neue, Arial, system-ui, sans-serif"
    fontSize: 0.8rem
    fontWeight: 400
    lineHeight: 1.15rem
  eyebrow:
    fontFamily: "Inter, Helvetica Neue, Arial, system-ui, sans-serif"
    fontSize: 0.7rem
    fontWeight: 600
    lineHeight: 1rem
    letterSpacing: "0.08em"
  figure:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: 0.8rem
    fontWeight: 400
  figure-sm:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: 1.05rem
    fontWeight: 600
  figure-md:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: 1.22rem
    fontWeight: 600
  figure-lg:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: 1.3rem
    fontWeight: 600
  ticker-chip:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: 12px
    fontWeight: 400
  media-symbol-md:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: 1.4rem
    fontWeight: 500
  media-symbol-lg:
    fontFamily: "JetBrains Mono, ui-monospace, monospace"
    fontSize: 2.4rem
    fontWeight: 500
rounded:
  sm: 6px
  md: 8px
  control: 10px
  card: 14px
  composer: 18px
  pill: 99px
spacing:
  micro: 4px
  compact: 6px
  control: 10px
  card: 14px
  section: 18px
  panel: 24px
components:
  button-primary:
    backgroundColor: "{colors.ignition-amber}"
    textColor: "{colors.cool-night}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "8px 16px"
    height: 36px
  button-primary-action:
    backgroundColor: "{colors.ignition-amber}"
    textColor: "{colors.cool-night}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "8px 14px"
    height: 40px
  button-outline:
    backgroundColor: transparent
    textColor: "{colors.paper-ink}"
    typography: "{typography.control}"
    rounded: "{rounded.control}"
    padding: "8px 16px"
    height: 36px
  icon-button:
    backgroundColor: transparent
    textColor: "{colors.quiet-ink}"
    rounded: "{rounded.md}"
    size: 30px
  card:
    backgroundColor: "{colors.slate-raised}"
    textColor: "{colors.paper-ink}"
    rounded: "{rounded.card}"
    padding: 14px
  composer:
    backgroundColor: "{colors.slate-sunken}"
    textColor: "{colors.paper-ink}"
    rounded: "{rounded.composer}"
    padding: "12px 14px 10px"
  nav-row:
    backgroundColor: transparent
    textColor: "{colors.paper-ink}"
    typography: "{typography.row}"
    rounded: "{rounded.md}"
    padding: "8px 10px"
---

# Design System: VisgniteAI

## Overview

**Creative North Star: "The Analyst's Instrument Panel"**

VisgniteAI is a precise, calm, serious workspace for people who need to inspect
evidence rather than be entertained by market motion. Its dark-first surface
feels like a purpose-built financial instrument: dense enough for comparison,
quiet enough for sustained reading, and explicit about where attention belongs.

The system is evidence-led in both information and appearance. Tonal hierarchy,
tabular figures, compact controls, and persistent contextual panels make the
interface feel operational. It rejects casino energy, neon-fintech spectacle,
generic AI glow, and decorative effects that compete with financial meaning.

**Key Characteristics:**

- Cool, dark tonal surfaces with a coherent slate cast.
- One rationed amber accent for the most important action or selected state.
- Compact, comparison-friendly typography with a dedicated numeric face.
- Stable, single-viewport workspace with contextual panels instead of page churn.
- Restrained motion that explains arrival, progress, and spatial change.

## Colors

The palette is a cool night ladder with one ignition point and a separate,
conventional vocabulary for Vietnamese market data.

### Primary

- **Ignition Amber** (`hsl(30 91% 58%)`): the filled primary action, focus ring,
  and rare selected accent in the dark theme. Use dark ink on top.
- **Day Ignition Amber** (`hsl(30 76% 36%)`): the contrast-safe light-theme form
  of the same accent. Use white on top.

### Secondary

- **Market Green** (`hsl(140 50% 50%)`) and **Market Red**
  (`hsl(3 72% 60%)`): directional data only—never brand or general controls.
- **Ceiling Violet** (`hsl(262 77% 75%)`), **Reference Gold**
  (`hsl(45 76% 62%)`), and **Floor Cyan** (`hsl(187 59% 61%)`): the conventional
  Vietnamese price-board states.

### Neutral

- **Cool Night** (`hsl(210 6% 7%)`): the dark-theme page ground.
- **Slate Panel** (`hsl(220 6% 10%)`): sidebar and inspector chrome.
- **Slate Raised** (`hsl(220 5% 12%)`): content cards.
- **Slate Sunken** (`hsl(220 4% 13%)`): fields and nested surfaces.
- **Slate Menu** (`hsl(220 4% 14%)`): floating popovers.
- **Slate Bubble** (`hsl(210 5% 16%)`): secondary filled surfaces and user
  messages.
- **Paper Ink** (`hsl(0 0% 98%)`) to **Quiet Ink** (`hsl(214 3% 56%)`): the
  readable six-step dark-theme ink ladder.
- **Day Paper** (`hsl(220 12% 97%)`) and **Day Ink**
  (`hsl(220 10% 10%)`): the light-theme ground and primary ink.

### Named Rules

**The Rationed Amber Rule.** Allow roughly one filled amber control per view.
Amber is a scarce action signal, not decoration or body text.

**The Data Is Not Brand Rule.** Green, red, violet, gold, and cyan carry market
meaning. Never reuse them merely to make a control vivid,
and never rely on color alone to communicate the state.

## Typography

**Display Font:** Newsreader (with Georgia and Times New Roman fallbacks)
**Body Font:** Inter (with Helvetica Neue, Arial, and system fallbacks)
**Label/Mono Font:** JetBrains Mono (with `ui-monospace` fallback)

**Character:** Inter keeps Vietnamese interface copy compact and neutral;
JetBrains Mono makes figures stable down a column. Newsreader is a deliberately
rare human note used when the system greets or addresses the reader.

### Hierarchy

- **Display** (400, `clamp(1.6rem, 2.7vw, 2.15rem)`, 1.1): greetings and select
  editorial headlines only; auth headings may reach 2.3rem and news headlines
  46px.
- **Title** (400–500, 0.95–1.02rem, tight leading): surface titles, card titles,
  and the wordmark.
- **Body** (400, 15px): default prose and interface copy.
- **Row** (400, 0.9rem/1.3rem): navigation rows, table labels, and list content.
- **Control** (500, 0.86rem/1.25rem): buttons, tabs, and field labels.
- **Metadata** (400, 0.8rem/1.15rem): timestamps, hints, and supporting labels.
- **Eyebrow** (600, 0.7rem/1rem, 0.08em, uppercase): the quietest category label.
- **Figure** (JetBrains Mono with tabular numerals): prices, percentages,
  timestamps, codes, and any number intended for comparison.
- **Figure Small / Medium / Large** (JetBrains Mono Semibold, 1.05rem / 1.22rem /
  1.3rem): stepped emphasis for comparable market figures in cards and the
  inspector.
- **Ticker Chip** (JetBrains Mono, 12px): compact company symbols in article
  metadata and navigation chips.
- **Media Symbol** (JetBrains Mono, 1.4rem or 2.4rem): responsive ticker
  fallbacks used only when a news image is unavailable.

### Named Rules

**The Three Jobs Rule.** Newsreader addresses, Inter operates, and JetBrains Mono
compares. Do not trade roles for novelty.

**The Vietnamese Is Native Rule.** Every loaded face must include the Vietnamese
subset; mid-sentence fallback is a broken design, not a harmless optimization.

## Layout

The primary application is one viewport with three coordinated regions: a
274px collapsible sidebar, a fluid central workspace, and an optional resizable
inspector. The inspector defaults to 408px, never goes below 320px, and can
expand to 52% of the viewport up to 760px. The central conversation retains at
least 520px; opening the inspector folds the sidebar first when space is tight.

The page itself does not scroll. Each region owns its overflow so the composer,
navigation position, and contextual data remain stable. Main content uses
responsive, bounded containers—up to 1560px for broad market views and narrower
reading measures for conversations and articles. Repeated spacing favors dense
4–14px internal rhythms, 18px section separation, and 24px larger panel rhythm.

At narrower widths, labels and secondary stamps disappear before functional
controls. Multi-column content collapses, settings navigation becomes
horizontal, and contextual panels displace less important chrome instead of
crushing the main task.

## Elevation & Depth

Depth is primarily tonal. The ground, panel, raised, sunken, menu, and bubble
steps separate nested work without turning every boundary into a line. Cards
use one hairline and no shadow. Shadows appear only where a surface truly floats
or overlaps another working plane.

### Shadow Vocabulary

- **Menu** (`0 26px 60px rgba(0, 0, 0, 0.65)`): dropdowns and popovers.
- **Composer** (`0 20px 50px rgba(0, 0, 0, 0.45)`): the docked input over a
  scrolling transcript.
- **Panel** (`-30px 0 70px rgba(0, 0, 0, 0.5)`): the open right-hand inspector.
- **Modal** (`0 40px 90px rgba(0, 0, 0, 0.7)`): dialogs and blocking overlays.

### Named Rules

**The Tonal-First Rule.** Static content earns hierarchy through its surface
step and one hairline. Shadow is reserved for real overlap.

## Shapes

The form language is precise with softened instrument edges. Standard controls
use 8–10px corners; cards and menus use 14px; the composer and major dialogs use
18px; meters, state dots, avatars, and circular send controls are fully rounded.
Borders are cool, low-contrast hairlines. Repeated silhouettes remain stable
across states so interaction does not shift nearby content.

## Components

### Buttons

- **Shape:** 10px control radius, normally 36px high. High-emphasis actions at
  panel and view edges use the shared 40px `action` size; icon controls are 30px
  squares with an 8px radius.
- **Primary:** Ignition Amber with Cool Night ink, medium control type, and
  8px/16px padding. Brighten on hover instead of fading into the dark ground.
- **Hover / Focus:** 150–200ms state transitions; one- or two-pixel focus rings
  in the primary token. Disabled controls keep their geometry and reduce opacity.
- **Secondary / Ghost:** transparent or tonal surfaces with quiet ink; hover by
  lifting a few percent of foreground rather than introducing another hue.
- **Send:** a 34px circular inversion of foreground and background. It may lift
  by one pixel on hover and settles on press.

### Chips

- **Style:** compact rounded rectangles or pills with mono data where relevant.
  Context chips use a subtle amber tint, 30% amber hairline, and amber text.
- **State:** selected states may use the single permitted accent stroke; market
  state chips use text and labels alongside color.

### Cards / Containers

- **Corner Style:** 14px for primary cards; 12px for cards nested in panels.
- **Background:** Slate Raised on the page, Slate Sunken inside panels.
- **Shadow Strategy:** none at rest; use the tonal-first rule.
- **Border:** one cool hairline.
- **Internal Padding:** typically 14–16px; nested panel cards use 12px.

### Inputs / Fields

- **Style:** Slate Sunken fill, cool hairline, 10–11px radius, readable labels,
  and Quiet Ink placeholders. Textareas inside the composer have no second box.
- **Focus:** shift the border toward 50% amber and add a restrained amber ring.
- **Error / Disabled:** pair semantic color with explicit copy; disabled controls
  remain visible at reduced opacity rather than disappearing.

### Navigation

Navigation is compact, left-aligned, and icon-assisted. Rows use 0.9rem type,
8px corners, and an 8px/10px inset. Hover is a faint foreground wash. Active
segmented controls use a raised neutral surface; sidebar selection may use the
single accent stroke. On compact widths, secondary labels disappear before
icons or core controls.

### Figures and Evidence

Comparable figures always use JetBrains Mono and tabular numerals. Positive,
negative, reference, ceiling, and floor states use their named market colors,
but every important state also has a sign, label, value, or explanation. Missing
or refused data renders as an em dash with a human-readable reason, never zero.

### Composer

The composer is one 18px rounded, sunken card containing the text field and all
message controls. It can float above the transcript with the composer shadow.
The field grows to 150px before scrolling, preserves a draft across view changes,
and remains available while an answer arrives.

## Do's and Don'ts

### Do:

- **Do** use the cool tonal ladder to express nesting and hierarchy.
- **Do** reserve filled amber for the single most important action or selection.
- **Do** render comparable figures in mono with tabular numerals.
- **Do** preserve the Vietnamese market palette and accompany color with text.
- **Do** keep sidebar, draft, transcript, and inspector context stable as views
  change.
- **Do** disable nonessential motion under `prefers-reduced-motion`.

### Don't:

- **Don't** add casino-like glow, neon gradients, generic AI auroras, or ambient
  decoration that competes with evidence.
- **Don't** use green or red as brand colors, or amber for ordinary body text.
- **Don't** add shadows to static cards; shadows belong to floating surfaces.
- **Don't** introduce a fourth type role or use Newsreader for routine UI copy.
- **Don't** hide missing, stale, sample, or refused data behind color, hover, or
  an empty space.
- **Don't** navigate away merely to reveal context that belongs beside the
  user's current task.
