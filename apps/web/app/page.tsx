import Link from "next/link";

const SITE_MAP: { n: number; title: string; desc: string }[] = [
  { n: 1, title: "오늘", desc: "지수·환율·수급·주도주·국면·전망" },
  { n: 2, title: "실시간 시장 국면", desc: "9개 레짐 분류" },
  { n: 3, title: "거시·국제정세", desc: "한국/미국/중국·환율·정세" },
  { n: 4, title: "수급·기술적 분석", desc: "투자자·프로그램·변동성" },
  { n: 5, title: "섹터", desc: "수익률·수급·밸류·정책수혜" },
  { n: 6, title: "종목", desc: "실적·공시·논거·무효화조건" },
  { n: 7, title: "구조적 성장 산업", desc: "AI·전력·원전·방산·조선" },
  { n: 8, title: "트레이딩 랩", desc: "전략·백테스트·신호·제안" },
  { n: 9, title: "계좌와 체결", desc: "잔고·손익·주문·Kill Switch" },
  { n: 10, title: "관리자", desc: "데이터·에이전트·리스크·Audit" },
];

const PHASE1_PAGES = [
  { href: "/dashboard", label: "Dashboard" },
  { href: "/agents", label: "Agents" },
  { href: "/risk", label: "Risk" },
  { href: "/trading", label: "Paper Trading" },
  { href: "/system", label: "System" },
];

export default function Home() {
  return (
    <main className="mx-auto max-w-6xl px-6 py-12">
      <header className="flex flex-wrap items-center justify-between gap-4">
        <div>
          <h1 className="font-mono text-2xl font-semibold tracking-tight">
            KOSPI-WATCHER
          </h1>
          <p className="mt-1 text-sm text-muted">
            한국 증시 분석 · 리스크 통제형 트레이딩 리서치 플랫폼
          </p>
        </div>
        <div className="flex items-center gap-2">
          <span className="rounded-full border border-border bg-elevated px-3 py-1 font-mono text-xs text-muted">
            MODE: RESEARCH
          </span>
          <span className="rounded-full border border-danger/40 bg-danger/10 px-3 py-1 font-mono text-xs font-semibold text-danger">
            ● LIVE TRADING DISABLED
          </span>
        </div>
      </header>

      <section className="mt-8 rounded-lg border border-warning/30 bg-warning/10 p-4 text-sm text-warning">
        <strong className="font-semibold">MOCK DATA — NOT REAL MARKET DATA.</strong>{" "}
        이 단계(Phase 0/1)의 모든 시장·금융 수치는 모의 데이터이며 실제 시세가 아닙니다.
        실거래·실계좌 연결은 구현되어 있지 않습니다.
      </section>

      <section className="mt-10">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">
          Phase 1 — 구현된 화면
        </h2>
        <nav className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
          {PHASE1_PAGES.map((p) => (
            <Link
              key={p.href}
              href={p.href}
              className="card transition-colors hover:border-accent/60 hover:bg-elevated"
            >
              <span className="font-mono text-sm font-medium">{p.label}</span>
            </Link>
          ))}
        </nav>
      </section>

      <section className="mt-10">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">
          최종 정보 구조 (목표 — Phase 2+)
        </h2>
        <ul className="mt-3 grid gap-3 sm:grid-cols-2">
          {SITE_MAP.map((s) => (
            <li key={s.n} className="card flex items-start gap-3 opacity-80">
              <span className="font-mono text-sm text-accent">{String(s.n).padStart(2, "0")}</span>
              <span>
                <span className="block text-sm font-medium">{s.title}</span>
                <span className="block text-xs text-muted">{s.desc}</span>
              </span>
            </li>
          ))}
        </ul>
      </section>

      <footer className="mt-12 border-t border-border pt-6 text-xs text-muted">
        KOSPI-WATCHER · LLM 에이전트는 분석만 수행하며 주문 권한이 없습니다. 모든 주문은
        deterministic Risk Engine 승인을 거칩니다.
      </footer>
    </main>
  );
}
