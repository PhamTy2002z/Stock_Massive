"use client"

/**
 * The last boundary: the root layout itself failed.
 *
 * This one replaces the document, so it has to carry its own `html` and `body`
 * — the layout that would normally provide them is the thing that broke. That
 * also means the font variables and the theme class are gone, which is why the
 * ground colour is written here as a literal: this file cannot assume the
 * design system loaded.
 *
 * Deliberately not built from `FailureState`. That component reaches for the
 * mark, the serif face and the Button, and every one of those is a chance for a
 * second error inside the handler for the first. The last boundary is the one
 * place where fewer moving parts beats a consistent surface.
 */

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string }
  reset: () => void
}) {
  return (
    <html lang="en">
      <body
        style={{
          margin: 0,
          minHeight: "100dvh",
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          justifyContent: "center",
          gap: "0.75rem",
          padding: "0 1.5rem",
          textAlign: "center",
          background: "#101112",
          color: "#fafafa",
          fontFamily:
            "Inter, 'Helvetica Neue', Arial, system-ui, sans-serif",
        }}
      >
        <h1 style={{ margin: 0, fontSize: "1.5rem", fontWeight: 500 }}>
          VisgniteAI failed to start
        </h1>
        <p
          style={{
            margin: 0,
            maxWidth: "34rem",
            fontSize: "0.9rem",
            lineHeight: 1.55,
            color: "#a1a4a8",
          }}
        >
          The interface hit an error at its outermost layer, so no screen could
          be built. Trying again is usually enough; if it still fails, reload the page.
        </p>
        <button
          type="button"
          onClick={reset}
          style={{
            marginTop: "0.5rem",
            height: 40,
            padding: "0 1rem",
            borderRadius: 10,
            border: "none",
            cursor: "pointer",
            background: "#f59331",
            color: "#101112",
            fontSize: "0.86rem",
            fontWeight: 500,
          }}
        >
          Try again
        </button>
        {error.digest !== undefined && (
          <p style={{ margin: 0, fontSize: "0.75rem", color: "#8c8f93" }}>
            Error code: {error.digest}
          </p>
        )}
      </body>
    </html>
  )
}
