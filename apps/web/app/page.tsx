"use client";

import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api";
import {
  DIRECTION_KO,
  ErrorNote,
  KIND_KO,
  LeanBar,
  Loading,
  RegimeBadge,
  StanceBadge,
  dirText,
  useApi,
} from "@/components/shell";

const QUOTE_NAMES: Record<string, string> = {
  KOSPI: "코스피",
  USDKRW: "원/달러",
  "069500": "KODEX 200",
  "114800": "KODEX 인버스",
  "252670": "곱버스 2X",
};

export default function Home() {
  const pred = useApi(() => api.latestPrediction());
  const quotes = useApi(() => api.marketQuotes(["KOSPI", "USDKRW", "069500", "114800", "252670"]));
  const [generating, setGenerating] = useState(false);

  async function generate() {
    setGenerating(true);
    try {
      await api.runPrediction(["069500", "114800", "252670"]);
      pred.reload();
    } finally {
      setGenerating(false);
    }
  }

  const p = pred.data;

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <header className="flex flex-wrap items-start justify-between gap-4">
        <div>
          <h1 className="font-mono text-2xl font-semibold tracking-tight">KOSPI-WATCHER</h1>
          <p className="mt-1 text-sm text-muted">한국 증시 예측 · 데일리 브리프 · 21에이전트 리서치 데스크</p>
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <span className="rounded-full border border-border bg-elevated px-3 py-1 font-mono text-xs text-muted">
            오늘 {new Date().toISOString().slice(0, 10)}
          </span>
          <button
            onClick={generate}
            disabled={generating}
            className="rounded-full border border-accent/40 bg-accent/10 px-3 py-1 font-mono text-xs font-semibold text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
          >
            {generating ? "생성 중…" : "예측 새로고침"}
          </button>
        </div>
      </header>

      {/* Live quotes strip */}
      <div className="mt-5 flex flex-wrap gap-3 rounded-lg border border-border bg-surface px-4 py-3">
        {quotes.data?.quotes.length ? (
          quotes.data.quotes.map((q) => (
            <div key={q.symbol} className="flex items-baseline gap-2">
              <span className="text-xs text-muted">{QUOTE_NAMES[q.symbol] ?? q.symbol}</span>
              <span className="font-mono text-sm">{Number(q.price).toLocaleString()}</span>
            </div>
          ))
        ) : (
          <span className="text-xs text-muted">시세 불러오는 중…</span>
        )}
        <span className="ml-auto font-mono text-[11px] text-muted">
          source: {quotes.data?.provider ?? "—"} · 실시세
        </span>
      </div>

      {pred.loading ? (
        <div className="mt-8">
          <Loading />
        </div>
      ) : !p ? (
        <section className="mt-8 card flex flex-col items-start gap-3">
          <h2 className="text-lg font-semibold">오늘의 예측이 아직 없습니다</h2>
          <p className="text-sm text-muted">
            21개 분석 에이전트를 5개 데스크로 계층 종합해 코스피 방향·국면·롱/인버스/곱버스 스탠스와
            데일리 브리프를 생성합니다.
          </p>
          <button
            onClick={generate}
            disabled={generating}
            className="rounded-md border border-accent/40 bg-accent/10 px-4 py-2 font-mono text-sm text-accent hover:bg-accent/20 disabled:opacity-40"
          >
            {generating ? "생성 중…" : "오늘의 예측 생성"}
          </button>
          {pred.error && !pred.error.includes("404") && <ErrorNote error={pred.error} />}
        </section>
      ) : (
        <>
          {/* Hero prediction */}
          <section className="mt-8 grid gap-4 lg:grid-cols-[1.4fr_1fr]">
            <div className="card">
              <div className="flex flex-wrap items-center gap-3">
                <span className="text-xs uppercase tracking-wider text-muted">하우스 뷰</span>
                <RegimeBadge regime={p.regime} />
                <span className="ml-auto font-mono text-[11px] text-muted">
                  분석: {p.generated_by} · {p.agent_count}에이전트
                </span>
              </div>
              <div className="mt-3 flex items-end gap-4">
                <span className={`font-mono text-5xl font-bold leading-none ${dirText(p.direction)}`}>
                  {DIRECTION_KO[p.direction]}
                </span>
                <div className="pb-1">
                  <div className="text-xs text-muted">확신도</div>
                  <div className="font-mono text-2xl font-semibold">{(p.confidence * 100).toFixed(0)}%</div>
                </div>
              </div>
              <p className="mt-3 text-sm font-medium">{p.headline}</p>
            </div>

            {/* Instrument ladder */}
            <div className="card">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">
                포지셔닝 (롱 · 인버스 · 곱버스)
              </h2>
              <div className="mt-3 space-y-2">
                {p.instrument_stances.map((s) => (
                  <div key={s.symbol} className="flex items-center justify-between gap-2">
                    <div>
                      <span className="text-sm">{s.name}</span>
                      <span className="ml-2 font-mono text-[11px] text-muted">{KIND_KO[s.kind] ?? s.kind}</span>
                    </div>
                    <StanceBadge label={s.label} />
                  </div>
                ))}
              </div>
            </div>
          </section>

          {/* Daily brief narrative */}
          <section className="mt-6 card">
            <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">데일리 브리프</h2>
            <p className="mt-3 leading-7 text-foreground/90">{p.brief}</p>
          </section>

          {/* Desk leans + scenarios */}
          <section className="mt-6 grid gap-4 lg:grid-cols-2">
            <div className="card">
              <div className="flex items-center justify-between">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">데스크 신호</h2>
                <Link href="/prediction" className="text-xs text-muted hover:text-accent">
                  조직도·상세 →
                </Link>
              </div>
              <div className="mt-3 space-y-2.5">
                {p.desk_views
                  .filter((d) => d.desk !== "CHIEF")
                  .map((d) => (
                    <div key={d.desk} className="flex items-center gap-3">
                      <span className="w-28 shrink-0 text-xs">{d.title}</span>
                      <LeanBar score={d.score} />
                      <span className={`w-10 shrink-0 text-right font-mono text-xs ${dirText(d.lean)}`}>
                        {DIRECTION_KO[d.lean]}
                      </span>
                    </div>
                  ))}
              </div>
            </div>

            <div className="card">
              <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">시나리오</h2>
              <div className="mt-3 space-y-3">
                {p.scenarios.map((s) => (
                  <div key={s.name}>
                    <div className="flex items-center justify-between text-sm">
                      <span>{s.name}</span>
                      <span className="font-mono text-muted">{(s.probability * 100).toFixed(0)}%</span>
                    </div>
                    <div className="mt-1 h-1.5 w-full rounded-full bg-elevated">
                      <div
                        className="h-1.5 rounded-full bg-accent/70"
                        style={{ width: `${s.probability * 100}%` }}
                      />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </section>
        </>
      )}

      {/* Nav */}
      <section className="mt-10">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">바로가기</h2>
        <nav className="mt-3 grid grid-cols-2 gap-3 sm:grid-cols-5">
          {[
            { href: "/prediction", label: "예측·조직도" },
            { href: "/agents", label: "에이전트" },
            { href: "/system", label: "시스템" },
            { href: "/trading", label: "페이퍼 트레이딩" },
            { href: "/risk", label: "리스크 엔진" },
          ].map((x) => (
            <Link
              key={x.href}
              href={x.href}
              className="card text-center transition-colors hover:border-accent/60 hover:bg-elevated"
            >
              <span className="font-mono text-sm font-medium">{x.label}</span>
            </Link>
          ))}
        </nav>
      </section>

      <footer className="mt-12 border-t border-border pt-6 text-xs text-muted">
        시세는 실시간(Yahoo), 에이전트 분석은 현재 런타임({pred.data?.generated_by ?? "mock"}). LLM 에이전트는
        분석만 수행하며 주문 권한이 없습니다. 모든 주문은 deterministic Risk Engine 승인을 거칩니다.
      </footer>
    </main>
  );
}
