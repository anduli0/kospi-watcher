import type { Metadata } from "next";
import "./globals.css";

export const metadata: Metadata = {
  title: "KOSPI-WATCHER",
  description:
    "Korean equity market analysis and risk-controlled trading research platform.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
