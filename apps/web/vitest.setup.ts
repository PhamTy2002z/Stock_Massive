import { beforeEach } from "vitest"

import "@testing-library/jest-dom/vitest"

// jsdom implements no media queries at all, and `useIsMobile` asks for one on
// mount. A desktop-sized stub rather than a per-file mock: a component that
// reads the viewport should be reachable from any test without that test having
// to know it does, and a test about narrow viewports overrides `useIsMobile`
// itself.
if (typeof window !== "undefined" && typeof window.matchMedia !== "function") {
  window.matchMedia = (query: string): MediaQueryList =>
    ({
      matches: false,
      media: query,
      onchange: null,
      addListener: () => {},
      removeListener: () => {},
      addEventListener: () => {},
      removeEventListener: () => {},
      dispatchEvent: () => false,
    }) as unknown as MediaQueryList
}

// Web storage is per-origin, and jsdom gives a whole test file one origin — so
// a preference written by one test is still there for the next one. That was
// harmless while only `desk-session` used it and cleared its own key; it stopped
// being harmless once the shell began remembering the layout, where a width
// dragged in one test silently became the starting width of the one after it.
//
// Cleared here rather than per file for the same reason the DOM is: a test
// should not have to know which storage the component it renders reaches for.
beforeEach(() => {
  if (typeof window === "undefined") return
  try {
    window.localStorage.clear()
    window.sessionStorage.clear()
  } catch {
    // A jsdom instance configured without storage. Nothing to reset.
  }
})
