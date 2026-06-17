import type { Metadata } from "next";

import { NavBar, SiteFooter } from "@/components/nav";
import "./globals.css";

export const metadata: Metadata = {
  title: "KOSPI-WATCHER · 한국 증시 예측 & 데일리 브리프",
  description:
    "21-agent research desk: KOSPI prediction, regime, long/inverse/leveraged stances, and a daily brief.",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="ko">
      <head>
        <link rel="preconnect" href="https://cdn.jsdelivr.net" crossOrigin="anonymous" />
        <link
          rel="stylesheet"
          href="https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/dist/web/variable/pretendardvariable-dynamic-subset.css"
        />
      </head>
      <body className="min-h-screen font-sans antialiased">
        <NavBar />
        <div className="min-h-[calc(100vh-3.5rem)]">{children}</div>
        <SiteFooter />
      </body>
    </html>
  );
}
