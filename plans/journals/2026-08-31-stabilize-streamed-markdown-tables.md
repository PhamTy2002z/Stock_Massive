---
title: Stabilize streamed markdown tables
date: 2026-08-31
summary: Kept streamed table cells mounted so word-fade animations do not restart on every reveal commit.
---

# Stabilize streamed markdown tables

## What happened

A streamed GFM table visibly flashed whenever later answer text arrived. The reveal pacer reparses Markdown on each committed prefix, while `Markdown` created new inline React component types for `th` and `td` on every render. React therefore remounted every table cell and restarted each word's `vg-chunk` fade animation.

## Decision

Keep the existing row-paced reveal and animation. Move the table header and cell renderers to stable module-level components so already revealed DOM nodes survive later Markdown renders.

## Evidence

- The focused DOM-identity regression failed consistently before the fix and passed after it.
- The focused Markdown/message suite passes 27 tests, including TSV/code copy and GFM numeric alignment.
- The full frontend suite passes 430 tests; lint, typecheck, and the production compile complete successfully.
- A Playwright acceptance through FastAPI, the Next proxy, and Chromium confirms the revealed table node remains mounted while later prose streams.
- The same browser acceptance confirms horizontal-only table rules, a tonal code surface, and internal table scrolling without document overflow at 375px.

## Follow-up polish

Tables now use editorial horizontal hairlines, tabular figures, preserved GFM alignment and a readable scrolling width. Code and ASCII blocks use a rounded raised surface. Each surface has one quiet copy action with success and failure feedback; no language badges, filenames or extra toolbar chrome were added.

## Next steps

None for this fix. Pre-existing unrelated warnings remain outside its scope.

> Historical work record — not durable authority. Prefer docs/specs/ADRs for current decisions.
