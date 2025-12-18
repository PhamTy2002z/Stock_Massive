import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "Stock Massive",
  description: "Stock analysis platform with real-time charting",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en">
      <body>{children}</body>
    </html>
  );
}
