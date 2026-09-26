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

// jsdom draws nothing: `getContext("2d")` returns null, and a chart runtime
// that starts anyway paints on the next animation frame — after the test that
// rendered it has finished. The throw lands outside every catch in the tree as
// an uncaught exception, so the file passes and the run fails.
//
// A no-op context rather than a mocked chart library: the gap is the
// environment's, the same way `matchMedia` above is, and a component that draws
// should be reachable from any test without that test knowing which runtime it
// reaches for. Nothing here asserts anything about pixels — no test can, with
// no canvas — it only lets the runtime run to completion and be disposed.
//
// Every method answers with one shared object carrying the few shapes a
// renderer reads back: a text measurement, a gradient's `addColorStop`, an
// image's `data`. One object for all of them is blunt, and the alternative is
// naming thirty canvas methods and being wrong about the thirty-first.
const CANVAS_RESULT = Object.freeze({
  width: 0,
  actualBoundingBoxAscent: 0,
  actualBoundingBoxDescent: 0,
  addColorStop: () => {},
  data: new Uint8ClampedArray(4),
})

function stubCanvasContext(canvas: HTMLCanvasElement): CanvasRenderingContext2D {
  const written = new Map<string, unknown>()
  return new Proxy(
    {},
    {
      get(_target, key) {
        if (typeof key === "symbol") return undefined
        if (key === "canvas") return canvas
        if (written.has(key)) return written.get(key)
        return () => CANVAS_RESULT
      },
      set(_target, key, value) {
        if (typeof key === "string") written.set(key, value)
        return true
      },
    },
  ) as unknown as CanvasRenderingContext2D
}

if (typeof HTMLCanvasElement !== "undefined") {
  HTMLCanvasElement.prototype.getContext = function getContext(
    this: HTMLCanvasElement,
    contextId: string,
  ) {
    // Only the 2D context is answered. A runtime asking for WebGL is told there
    // is none, which is a thing browsers say too, and it falls back on its own.
    return contextId === "2d" ? stubCanvasContext(this) : null
  } as HTMLCanvasElement["getContext"]
}
