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
