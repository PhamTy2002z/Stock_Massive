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
  title: "VisgniteAI",
  description: "Trợ lý phân tích chứng khoán Việt Nam — HOSE, HNX, UPCOM",
  icons: {
    icon: "/visgnite-mark.svg",
    apple: "/visgnite-mark.svg",
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
        {/* Night is the design, not a mode: the VisgniteAI reference is drawn
            on #191815 and every surface step above it is defined against that
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
      </body>
    </html>
  );
}
