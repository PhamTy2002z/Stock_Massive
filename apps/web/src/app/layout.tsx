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
        {/* forcedTheme, not just defaultTheme: next-themes persists the chosen
            theme in localStorage, so every browser that ever loaded the old
            dark build keeps rendering dark no matter what the default says —
            and the app ships no theme switcher to escape with. The v3 design is
            light; drop forcedTheme if a switcher is ever added. */}
        <ThemeProvider
          attribute="class"
          defaultTheme="light"
          forcedTheme="light"
          enableSystem={false}
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
