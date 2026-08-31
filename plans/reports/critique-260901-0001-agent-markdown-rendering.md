⚠️ DEGRADED: single-context (sub-agents declined by user)

# Agent Markdown rendering critique

Target: `apps/web/src/components/alpha/message/markdown.tsx`

## Design health score

| # | Heuristic | Score | Key issue |
|---|---|---:|---|
| 1 | Visibility of system status | 4 | Copy success is immediate; streamed content remains stable. |
| 2 | Match system / real world | 4 | Tables, numeric alignment and code surfaces follow familiar reading conventions. |
| 3 | User control and freedom | 3 | Keyboard scrolling and local copy are available; no undo is relevant here. |
| 4 | Consistency and standards | 4 | Uses the existing tonal ladder, type ramp and copy-feedback language. |
| 5 | Error prevention | 4 | Raw HTML stays disabled; clipboard refusal is handled. |
| 6 | Recognition rather than recall | 3 | Copy is a standard icon with title and accessible name, but remains intentionally quiet. |
| 7 | Flexibility and efficiency | 4 | Tables copy as TSV; code and ASCII copy as plain text. |
| 8 | Aesthetic and minimalist design | 4 | Horizontal hairlines replace the dense cell grid; no badges or toolbars were added. |
| 9 | Error recovery | 3 | Clipboard denial produces an error toast; manual selection remains possible. |
| 10 | Help and documentation | n/a | This is a reading surface, not a workflow requiring embedded help. |
| **Total** | | **33/36** | **Excellent** |

## Design specificity verdict

The final surface feels authored for VisgniteAI rather than copied from a generic chat UI: compact editorial tables, tabular figures, cool tonal depth, mono code and rationed controls fit the product's analyst-instrument-panel language. The initial deterministic scan and the final scan both returned zero findings; the quality gap was visual and interaction-level, not a detectable markup anti-pattern.

## Overall impression

The original renderer was semantically sound and security-conscious, but tables looked like a dense spreadsheet and streamed cell remounts restarted word animations. The revised renderer is calmer, more scannable and materially more useful without adding persistent metadata.

## What is working

- Stable module-level Markdown renderers keep revealed table nodes mounted while later prose arrives.
- Table hierarchy now relies on spacing and horizontal hairlines; GFM numeric alignment is preserved.
- Code and ASCII diagrams use one rounded tonal surface with a local copy action and keyboard scrolling.

## Priority issues addressed

- **P1 — Streaming flicker:** fixed renderer identity and covered it at DOM and browser levels.
- **P1 — Dense table grid:** replaced full cell borders with horizontal hairlines and clearer row rhythm.
- **P1 — Weak code/ASCII affordance:** added a dedicated tonal surface and copy feedback.
- **P2 — Narrow viewport compression:** tables retain a readable minimum width and scroll internally without widening the document.
- **P2 — Financial alignment:** right/center GFM alignment is preserved for quantitative columns.

## Cognitive load and emotional journey

Each data surface exposes one secondary action. There are no language badges, filenames, row menus or persistent labels to compete with the answer. Stable streaming removes the most disruptive reading valley; success feedback reassures without interrupting the research flow.

## Persona red flags

- **Active investor:** resolved — changing prose no longer flashes the table being compared.
- **Research analyst:** resolved — quantitative alignment and TSV/plain-text copy reduce cleanup work.
- **Narrow-screen reader:** Markdown now scrolls internally, though the existing application shell still leaves a very narrow transcript at 375px; shell responsiveness is outside this change.

## Minor observations

- Native title text keeps the always-visible copy icons visually quiet while preserving discoverability.
- The existing build still emits unrelated warnings about `duration-[180ms]` and the missing Next ESLint plugin.

## Run notes

- Slug: `apps-web-src-components-alpha-message-markdown-tsx`.
- Ignore list: none.
- Assessment independence: sequential single-context; design assessment completed before detector execution.
- CLI detector: clean before and after implementation.
- Browser evidence: real FastAPI → Next production → Chromium; desktop and 375px screenshots inspected, plus computed-style assertions.
- Overlay injection: skipped; no user-visible detector overlay was claimed. Playwright screenshots and DOM/computed-style checks were the fallback signal.
- Live server: only Playwright-managed E2E servers; stopped cleanly.
- Temporary screenshots: moved to Trash after inspection.
- Snapshot/trend: `.impeccable/critique` write skipped to respect the repository rule that Markdown belongs under `plans/` or `docs/`; no prior trend existed.

Questions skipped: the user already requested implementation of all scoped priority findings.
