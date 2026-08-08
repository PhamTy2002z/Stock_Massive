---
title: "Stock Massive sidebar hover implementation"
tags: [stock-massive, sidebar, frontend]
status: active
created: 2026-08-08
---

# Stock Massive sidebar hover implementation

This plan splits the desktop sidebar state migration and hover interaction into
two independently reviewable pull requests. PR-1 establishes the persistent
layout model. PR-2 adds transient hover peek behavior without changing content
layout width.

## Behavior model

The sidebar uses two independent attributes on desktop:

- `data-layout="rail|pinned"` controls the width reserved in page layout.
- `data-peek="true|false"` controls whether a rail temporarily renders the full
  panel over the page.

`rail` reserves `3rem`. `pinned` reserves `16rem`. A peeked rail still reserves
`3rem`, but its fixed panel renders at `16rem` above page content. Mobile keeps
the existing sheet behavior and doesn't use hover peek.

The canonical `sidebar_state` cookie stores `rail` or `pinned` for seven days.
On the first client reconciliation, legacy values migrate as follows:

- `open`, `true`, and `expanded` become `pinned`.
- `closed`, `false`, and `collapsed` become `rail`.
- Missing or invalid values use the provider default and are rewritten only
  after an explicit layout change.

The existing `open`, `setOpen`, `state`, and `data-state` contracts remain as
compatibility aliases until a separate cleanup is justified.

## PR-1: Persistent data layout

PR-1 changes state semantics without adding hover behavior.

### Scope

1. Add the `SidebarLayout` type and expose `layout` and `setLayout` from the
   sidebar context.
2. Derive the existing boolean and `expanded|collapsed` values from
   `pinned|rail` so current consumers and Tailwind selectors keep working.
3. Read and normalize `sidebar_state` after mount, including the legacy cookie
   mappings above.
4. Persist only canonical `rail|pinned` values after migration or user action.
5. Add `data-layout` to the provider wrapper and desktop sidebar peer.
6. Route the trigger, keyboard shortcut, brand control, and rail control through
   the canonical layout setter.
7. Keep desktop widths, animation duration, mobile sheet behavior, navigation,
   and authentication behavior unchanged.

### Files

- Modify `apps/web/src/components/ui/sidebar.tsx`.
- Modify `apps/web/src/components/layout/app-sidebar.tsx` only if its toggle
  consumer needs the new semantic API.

### Acceptance checklist

- [ ] A new session defaults to `pinned`.
- [ ] Toggling produces `data-layout="rail"` and
  `data-layout="pinned"` without changing current visuals.
- [ ] `sidebar_state=open` reloads as pinned and rewrites to `pinned`.
- [ ] `sidebar_state=closed` reloads as rail and rewrites to `rail`.
- [ ] Existing `true|false` cookies also migrate without losing preference.
- [ ] Invalid or missing cookie values do not throw or break hydration.
- [ ] `Cmd+B` or `Ctrl+B`, the brand control, and the sidebar rail still toggle.
- [ ] Mobile sheet open and close behavior is unchanged.
- [ ] `pnpm type-check` passes in `apps/web`.
- [ ] `pnpm build` passes in `apps/web`.

## PR-2: Transient data peek

PR-2 begins only after PR-1 review and merge. It adds desktop pointer and focus
interaction on top of the stable layout model.

### Scope

1. Add transient `peek` state that can become true only when the desktop layout
   is `rail`.
2. Set `data-peek="true|false"` on the provider wrapper and desktop sidebar
   peer.
3. Start peek 150 ms after pointer entry or focus entry on the rail/sidebar.
4. End peek 300 ms after pointer leave or focus leaves the sidebar subtree.
5. Cancel the opposite timer on every enter/leave transition and clear both
   timers on unmount, layout change, mobile transition, and explicit toggle.
6. Expand only the fixed sidebar panel while peeking; keep the layout spacer at
   rail width so dashboard content does not shift.
7. Let a click or keyboard toggle during peek persist `pinned` and clear peek.
8. Keep tooltips hidden while the full panel is visible and preserve existing
   menu, dropdown, and collapsible interactions.
9. Respect reduced motion and retain the current mobile sheet behavior.

### Files

- Modify `apps/web/src/components/ui/sidebar.tsx`.
- Modify `apps/web/src/components/layout/app-sidebar.tsx` only for controls that
  distinguish pinned and peeked presentation.

### Acceptance checklist

- [ ] A rail stays compact for pointer visits shorter than 150 ms.
- [ ] A rail peeks at full visual width after 150 ms without moving content.
- [ ] Leaving and returning within 300 ms cancels close without flicker.
- [ ] A completed leave closes peek after 300 ms.
- [ ] Rapid enter/leave sequences cannot fire stale timers.
- [ ] Pinned layout never enters peek state.
- [ ] Clicking or using the keyboard while peeked pins the sidebar and persists
  `sidebar_state=pinned`.
- [ ] Dropdowns, nested navigation, focus traversal, and tooltips remain usable.
- [ ] Mobile behavior and touch interactions remain unchanged.
- [ ] Reduced-motion users do not receive width/transform animation.
- [ ] `pnpm type-check` passes in `apps/web`.
- [ ] `pnpm build` passes in `apps/web`.

## Delivery order

1. Commit this plan to `main`.
2. Branch `feat/sidebar-hover-pr1` from the plan commit.
3. Implement, verify, push, and open PR-1 with command results in its
   description.
4. Stop after PR-1 and wait for review before creating or implementing PR-2.

## Risks and controls

- Hydration drift: keep the server/default render deterministic, then reconcile
  the cookie after mount.
- Layout shift: reserve width from `data-layout` only; PR-2 must never bind the
  spacer width to `data-peek`.
- Stale timers: store timer IDs in refs and clear them at every state boundary.
- Mobile regressions: gate cookie-driven hover behavior behind the existing
  desktop detection and leave `openMobile` independent.

## Security and privacy

The cookie contains only a presentation preference. It uses `path=/`, a
seven-day lifetime, and `SameSite=Lax`; it stores no identity, market data, or
authentication material.

## Unresolved questions

None.
