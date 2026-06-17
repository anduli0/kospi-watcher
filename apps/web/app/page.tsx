"use client";

import Link from "next/link";
import { useState } from "react";

import { api } from "@/lib/api";
import {
  DIRECTION_KO,
  ErrorNote,
  KIND_KO,
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

const TODAY = new Date().toISOString().slice(0, 10);

const BANNERS = [
  {
    href: "/prediction",
    title: "예측 상세",
    desc: "논의 과정 · 조직도 · 종목 스탠스",
    accent: "from-accent/20 to-accent/0",
  },
  {
    href: "/news",
    title: "뉴스 스크랩",
    desc: "일자별 한국 증시 뉴스 · 브리프 근거",
    accent: "from-accent2/20 to-accent2/0",
  },
  {
    href: "/trading",
    title: "페이퍼 트레이딩",
    desc: "모의 체결 · 계좌 · 주문 내역",
    accent: "from-warning/20 to-warning/0",
  },
];

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
  const notFound = pred.error?.includes("404");
  const priceFor = (symbol: string) =>
    quotes.data?.quotes.find((q) => q.symbol === symbol)?.price;

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-10">
      {/* Intro */}
      <p className="section-label">
        오늘의 코스피 예측 · 데일리 브리프 · <span className="num">{TODAY}</span>
      </p>

      {/* Live quote strip */}
      <div className="card flex flex-wrap items-center gap-x-6 gap-y-2 py-3.5">
        {quotes.data?.quotes.length ? (
          quotes.data.quotes.map((q) => (
            <div key={q.symbol} className="flex items-baseline gap-2">
              <span className="text-xs text-muted">{QUOTE_NAMES[q.symbol] ?? q.symbol}</span>
              <span className="num text-sm font-medium">{Number(q.price).toLocaleString()}</span>
            </div>
          ))
        ) : (
          <span className="text-xs text-muted">시세 불러오는 중…</span>
        )}
        <span className="num ml-auto text-[11px] text-muted/80">
          source: {quotes.data?.provider ?? "yahoo"} · 실시세
        </span>
      </div>

      {/* Hero prediction */}
      {pred.loading ? (
        <Loading />
      ) : !p ? (
        <section className="card flex flex-col items-start gap-3">
          <h2 className="text-xl font-semibold tracking-tight">오늘의 예측이 아직 없습니다</h2>
          <p className="max-w-2xl text-sm text-muted">
            21개 분석 에이전트를 5개 데스크로 계층 종합해 코스피 방향·국면·롱/인버스/곱버스 스탠스와
            데일리 브리프를 생성합니다.
          </p>
          <button
            onClick={generate}
            disabled={generating}
            className="rounded-xl border border-accent/40 bg-accent/10 px-4 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
          >
            {generating ? "생성 중…" : "오늘의 예측 생성"}
          </button>
          {pred.error && !notFound && <ErrorNote error={pred.error} />}
        </section>
      ) : (
        <section className="card">
          <div className="flex flex-wrap items-start gap-x-6 gap-y-2">
            <div>
              <p className="section-label">예측 대상</p>
              <p className="mt-1 text-sm font-medium">{p.subject}</p>
            </div>
            <div>
              <p className="section-label">기간</p>
              <p className="num mt-1 text-sm font-medium">{p.horizon_label}</p>
            </div>
            <button
              onClick={generate}
              disabled={generating}
              className="ml-auto rounded-xl border border-accent/40 bg-accent/10 px-3.5 py-1.5 text-xs font-semibold text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
            >
              {generating ? "생성 중…" : "예측 새로고침"}
            </button>
          </div>

          <div className="mt-6 flex flex-wrap items-end gap-x-8 gap-y-4">
            <div>
              <span className={`text-6xl font-bold leading-none tracking-tight ${dirText(p.direction)}`}>
                {DIRECTION_KO[p.direction]}
              </span>
            </div>
            <div className="pb-1">
              <p className="text-xs text-muted">확신도</p>
              <p className="num text-3xl font-semibold">{(p.confidence * 100).toFixed(0)}%</p>
            </div>
            <div className="pb-1.5">
              <RegimeBadge regime={p.regime} />
            </div>
          </div>

          <p className="mt-5 text-lg font-medium leading-snug">{p.headline}</p>
          <p className="num mt-3 text-[11px] text-muted/80">
            분석 {p.generated_by} · {p.agent_count}에이전트 · as of {p.as_of.slice(0, 16).replace("T", " ")}
          </p>
        </section>
      )}

      {/* Daily brief narrative */}
      {p && (
        <section className="card">
          <h2 className="section-label">데일리 브리프</h2>
          <p className="mt-3 whitespace-pre-line leading-7 text-foreground/90">{p.brief}</p>
          {p.news_refs.length > 0 && (
            <div className="mt-4 border-t border-border/60 pt-4">
              <p className="section-label">반영 뉴스</p>
              <div className="mt-2 flex flex-wrap gap-1.5">
                {p.news_refs.map((ref) => (
                  <span key={ref} className="chip text-muted">
                    {ref}
                  </span>
                ))}
              </div>
            </div>
          )}
        </section>
      )}

      {/* Instrument ladder */}
      {p && (
        <section className="card">
          <h2 className="section-label">포지셔닝 (롱 · 인버스 · 곱버스)</h2>
          <div className="mt-3 divide-y divide-border/50">
            {p.instrument_stances.map((s) => {
              const price = priceFor(s.symbol);
              return (
                <div key={s.symbol} className="flex items-center justify-between gap-3 py-2.5">
                  <div className="min-w-0">
                    <span className="text-sm">{s.name}</span>
                    <span className="num ml-2 text-[11px] text-muted">{KIND_KO[s.kind] ?? s.kind}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    {price && (
                      <span className="num text-xs text-muted">{Number(price).toLocaleString()}</span>
                    )}
                    <StanceBadge label={s.label} />
                  </div>
                </div>
              );
            })}
          </div>
        </section>
      )}

      {/* Banner navigation */}
      <section className="grid gap-4 sm:grid-cols-3">
        {BANNERS.map((b) => (
          <Link
            key={b.href}
            href={b.href}
            className={`card card-hover relative overflow-hidden bg-gradient-to-br ${b.accent}`}
          >
            <p className="text-base font-semibold tracking-tight">{b.title}</p>
            <p className="mt-1.5 text-sm text-muted">{b.desc}</p>
            <span className="mt-4 inline-flex items-center gap-1 text-sm font-medium text-accent">
              열기 <span aria-hidden>→</span>
            </span>
          </Link>
        ))}
      </section>
    </main>
  );
}
