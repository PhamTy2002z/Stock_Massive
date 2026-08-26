import type { Metadata } from "next";
import { Inter, JetBrains_Mono, Newsreader } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/providers/theme-provider";
import { QueryProvider } from "@/components/providers/query-provider";
import { QueryErrorBoundary } from "@/components/providers/query-error-boundary";
import { ConnectionGate } from "@/components/providers/connection-gate";
import { Toaster } from "@/components/ui/sonner";
import { AgentationToolbar } from "@/components/dev/agentation-toolbar";
import { CanvasFixtureToolbar } from "@/components/dev/canvas-fixture-toolbar";

/**
 * The body face, and the one every label in the product is set in.
 *
 * **Vietnamese is not optional in the subset.** Latin alone leaves the whole
 * U+1EA0–U+1EF9 range unsubsetted, so every word carrying a diacritic — which
 * in this product is most of them — falls back mid-sentence to the system sans.
 * The result reads as two typefaces fighting inside one label, which is exactly
 * the tell that a font was configured for an English product.
 */
const inter = Inter({
  subsets: ["latin", "vietnamese"],
  variable: "--font-inter",
  display: "swap",
});

/** Every figure a reader might compare against another figure. */
const jetBrainsMono = JetBrains_Mono({
  subsets: ["latin", "vietnamese"],
  variable: "--font-jetbrains-mono",
  display: "swap",
});

/**
 * The one serif in the system, and it says one thing: the greeting that opens
 * a new conversation.
 *
 * `opsz` is requested explicitly rather than left to the default instance. This
 * face is drawn for a range of sizes, and the greeting is set at roughly 2rem —
 * pinning a static cut would give it the thicker strokes and looser fit a
 * caption-sized optical master is drawn with, which is precisely the difference
 * between a display line and a heading.
 */
const newsreader = Newsreader({
  subsets: ["latin", "vietnamese"],
  axes: ["opsz"],
  variable: "--font-newsreader",
  display: "swap",
});

/**
 * `icons` is deliberately absent: `app/icon.svg`, `app/favicon.ico` and
 * `app/apple-icon.png` are Next's file conventions, so the link tags — type,
 * sizes and a content hash for cache busting — are emitted from the files
 * themselves. Declaring the same icons here would only add a second, unhashed
 * copy of each tag.
 */
export const metadata: Metadata = {
  title: "VisgniteAI",
  description: "Trợ lý phân tích chứng khoán Việt Nam — HOSE, HNX, UPCOM",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    /* The three faces are declared as variables on the root and consumed by
       Tailwind's own `sans` / `mono` / `serif` families, rather than one of them
       being pinned to `body` with a class. That way a component asking for
       `font-sans` and a component inheriting from the body resolve to the same
       stack — with a class on the body those two answers can differ. */
    <html
      lang="vi"
      suppressHydrationWarning
      className={`${inter.variable} ${jetBrainsMono.variable} ${newsreader.variable}`}
    >
      <body>
        {/* Night is the design, not a mode: the VisgniteAI reference is drawn
            on #101112 and every surface step above it is defined against that
            ground, so a first visit lands there. The light theme is the same
            system re-grounded on paper and stays a choice the user makes in
            the toggle — which is why enableSystem is still on. */}
        <ThemeProvider
          attribute="class"
          defaultTheme="dark"
          enableSystem
          disableTransitionOnChange
        >
          <QueryProvider>
            {/* Outside the error boundary on purpose: an unreachable API is a
                wait, not a fault, and the veil has to survive without the tree
                below it unmounting. */}
            <ConnectionGate>
              <QueryErrorBoundary>
                {children}
              </QueryErrorBoundary>
            </ConnectionGate>
            <Toaster />
          </QueryProvider>
        </ThemeProvider>
        {/* Devtool annotate UI cho AI coding agent — component tự no-op ở
            production build, xem `components/dev/agentation-toolbar.tsx`. */}
        <AgentationToolbar />
        {/* Every canvas widget drawn from the real artifact fixture, so the
            look of a chart can be worked on without a backend. Dev only —
            see `components/dev/canvas-fixture-toolbar.tsx`. */}
        <CanvasFixtureToolbar />
      </body>
    </html>
  );
}
