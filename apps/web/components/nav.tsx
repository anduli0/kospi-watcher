"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV = [
  { href: "/", label: "오늘" },
  { href: "/prediction", label: "예측" },
  { href: "/news", label: "뉴스" },
  { href: "/agents", label: "에이전트" },
  { href: "/trading", label: "트레이딩" },
  { href: "/system", label: "시스템" },
];

export function NavBar() {
  const path = usePathname();
  const active = (href: string) =>
    href === "/" ? path === "/" : path.startsWith(href);

  return (
    <header className="sticky top-0 z-40 border-b border-border/70 bg-background/70 backdrop-blur-xl">
      <div className="mx-auto flex h-14 max-w-6xl items-center gap-4 px-6">
        <Link href="/" className="flex items-center gap-2">
          <span className="grid h-7 w-7 place-items-center rounded-lg bg-gradient-to-br from-accent to-accent2 text-sm font-bold text-background">
            K
          </span>
          <span className="text-sm font-semibold tracking-tight">
            KOSPI<span className="text-muted">·</span>WATCHER
          </span>
        </Link>

        <nav className="ml-2 hidden items-center gap-1 md:flex">
          {NAV.map((n) => (
            <Link
              key={n.href}
              href={n.href}
              className={
                "rounded-lg px-3 py-1.5 text-sm transition-colors " +
                (active(n.href)
                  ? "bg-elevated text-foreground"
                  : "text-muted hover:bg-elevated/60 hover:text-foreground")
              }
            >
              {n.label}
            </Link>
          ))}
        </nav>

        <span className="ml-auto chip border-accent/30 bg-accent/10 text-accent">
          <span className="h-1.5 w-1.5 rounded-full bg-accent" /> RESEARCH
        </span>
      </div>

      {/* mobile nav */}
      <nav className="flex items-center gap-1 overflow-x-auto border-t border-border/60 px-4 py-1.5 md:hidden">
        {NAV.map((n) => (
          <Link
            key={n.href}
            href={n.href}
            className={
              "whitespace-nowrap rounded-lg px-2.5 py-1 text-xs " +
              (active(n.href) ? "bg-elevated text-foreground" : "text-muted")
            }
          >
            {n.label}
          </Link>
        ))}
      </nav>
    </header>
  );
}

export function SiteFooter() {
  return (
    <footer className="mt-16 border-t border-border/70 bg-surface/40">
      <div className="mx-auto max-w-6xl space-y-3 px-6 py-8 text-xs leading-relaxed text-muted">
        <p>
          <strong className="text-foreground/80">면책 고지(Disclaimer).</strong> 본 서비스는 정보
          제공을 목적으로 하며, 특정 종목·상품에 대한 투자 자문이나 매매 권유가 아닙니다. 모든 예측·국면
          판단·종목 스탠스는 알고리즘과 에이전트가 생성한 참고 자료이며, 정확성·완전성을 보증하지 않습니다.
          투자 판단과 그 결과에 대한 책임은 전적으로 이용자 본인에게 있습니다. 인버스·레버리지(곱버스)
          상품은 일일 리밸런싱에 따른 변동성 손실(데케이)과 원금 손실 위험이 큽니다.
        </p>
        <p>
          시세 데이터는 Yahoo Finance(실시간·키리스), 뉴스는 Google News 기준이며, 에이전트 분석은 현재
          모의(mock) 또는 LLM 런타임 결과입니다. 실거래·실계좌 연결은 제공하지 않으며, 트레이딩 화면은
          모의 체결(paper)만 지원합니다.
        </p>
        <div className="flex flex-wrap items-center justify-between gap-2 border-t border-border/60 pt-3">
          <span>© 2026 YellowScale · 안민규(Minkyu An). All rights reserved.</span>
          <span className="num text-[11px] text-muted/70">
            KOSPI-WATCHER · 21-agent research desk · v0.2
          </span>
        </div>
      </div>
    </footer>
  );
}
