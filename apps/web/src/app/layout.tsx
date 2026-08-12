import type { Metadata } from "next";
import { Inter, JetBrains_Mono } from "next/font/google";
import "./globals.css";
import { ThemeProvider } from "@/components/providers/theme-provider";
import { QueryProvider } from "@/components/providers/query-provider";
import { QueryErrorBoundary } from "@/components/providers/query-error-boundary";
import { ConnectionGate } from "@/components/providers/connection-gate";
import { Toaster } from "@/components/ui/sonner";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
});

const jetBrainsMono = JetBrains_Mono({
  subsets: ["latin", "vietnamese"],
  variable: "--font-jetbrains-mono",
});

export const metadata: Metadata = {
  title: "Stock Massive",
  description: "Stock analysis platform with real-time charting",
  icons: {
    icon: "/logo.png",
    apple: "/logo.png",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="vi" suppressHydrationWarning>
      <body className={`${inter.className} ${jetBrainsMono.variable}`}>
        {/* forcedTheme is gone now that ThemeToggle ships: it was only ever
            there because a browser holding a stale "dark" in localStorage had
            no way back to the light v3 design. There is a way back now, and
            dark is a designed surface rather than a leftover.

            defaultTheme stays "light" rather than "system" so a first visit
            still lands on the light design; "system" is a choice the user
            makes in the toggle, which is why enableSystem is on. */}
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
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
      </body>
    </html>
  );
}
