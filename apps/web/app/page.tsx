"use client";

import Link from "next/link";
import { useState } from "react";
import {
  BarChart3,
  LineChart,
  Newspaper,
  Sparkles,
  Target,
  type LucideIcon,
} from "lucide-react";

import { api } from "@/lib/api";
import { SyncBanner } from "@/components/sync";
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

const BANNERS: {
  href: string;
  title: string;
  desc: string;
  accent: string;
  Icon: LucideIcon;
}[] = [
  {
    href: "/prediction",
    title: "예측 상세",
    desc: "논의 과정 · 조직도 · 종목 스탠스",
    accent: "from-accent/20 to-accent/0",
    Icon: LineChart,
  },
  {
    href: "/market",
    title: "시장 흐름",
    desc: "섹터 등락 · 외국인·기관·개인 수급",
    accent: "from-up/20 to-up/0",
    Icon: BarChart3,
  },
  {
    href: "/news",
    title: "뉴스 스크랩",
    desc: "일자별 한국 증시 뉴스 · 브리프 근거",
    accent: "from-accent2/20 to-accent2/0",
    Icon: Newspaper,
  },
  {
    href: "/analysis",
    title: "포지션 분석",
    desc: "매수·매도 판단 · 단·중·장기 가격 시나리오",
    accent: "from-warning/20 to-warning/0",
    Icon: Target,
  },
  {
    href: "/stocks",
    title: "종목 추천",
    desc: "국장 개별주 · 단·중·장기 Top 픽",
    accent: "from-up/20 to-up/0",
    Icon: Sparkles,
  },
];

export default function Home() {
  const pred = useApi(() => api.latestPrediction());
  const brief = useApi(() => api.newsBrief());
  const quotes = useApi(() => api.marketQuotes(["KOSPI", "USDKRW", "069500", "114800", "252670"]));
  const [generating, setGenerating] = useState(false);

  // Ask the server for a full refresh (news → prediction → brief); the
  // SyncBanner tracks progress and reloads the page data when it lands.
  async function generate() {
    setGenerating(true);
    try {
      await api.syncRun();
    } finally {
      setGenerating(false);
    }
  }

  function reloadAll() {
    pred.reload();
    brief.reload();
    quotes.reload();
  }

  const p = pred.data;
  const b = brief.data;
  const notFound = pred.error?.includes("404");
  const priceFor = (symbol: string) =>
    quotes.data?.quotes.find((q) => q.symbol === symbol)?.price;

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-10">
      {/* Intro */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="section-label">
          예측 리포트 · 뉴스 데일리 브리프 · <span className="num">{TODAY}</span>
        </p>
        <span className="chip border-accent2/30 bg-accent2/10 text-accent2">
          매일 08:00 자동 업데이트 · 접속 시 자동 갱신
        </span>
      </div>

      {/* Self-update strip: engine badge + last update + progress + button */}
      <SyncBanner onSynced={reloadAll} />

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
            분석 {p.generated_by === "claude_cli" ? "내 클로드" : p.generated_by} · {p.agent_count}에이전트 · as of{" "}
            {p.as_of.slice(0, 16).replace("T", " ")}
          </p>
        </section>
      )}

      {/* Prediction report summary (the forecast narrative) */}
      {p && (
        <section className="card">
          <h2 className="section-label">예측 리포트 요약</h2>
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
          <Link
            href="/prediction"
            className="mt-4 inline-flex text-sm font-medium text-accent hover:underline"
          >
            예측 상세 · 논의 과정 보기 →
          </Link>
        </section>
      )}

      {/* News daily brief (the news roundup — distinct from the forecast) */}
      <section className="card">
        <div className="flex items-center justify-between gap-2">
          <h2 className="section-label">뉴스 데일리 브리프 (뉴스 종합 요약)</h2>
          {b && <span className="num text-[11px] text-muted/80">{b.item_count}건 · {b.date}</span>}
        </div>
        {brief.loading ? (
          <Loading />
        ) : b ? (
          <>
            <p className="mt-3 whitespace-pre-line leading-7 text-foreground/90">{b.summary}</p>
            <div className="mt-4 grid gap-3 sm:grid-cols-2">
              {b.themes.slice(0, 4).map((t) => (
                <div key={t.topic} className="rounded-xl border border-border/60 bg-elevated/40 p-3">
                  <p className="text-xs font-semibold text-accent2">
                    {t.topic} <span className="num text-muted">· {t.count}건</span>
                  </p>
                  <ul className="mt-1.5 space-y-1">
                    {t.headlines.slice(0, 2).map((h) => (
                      <li key={h.url} className="truncate text-xs text-muted">
                        · {h.title}
                      </li>
                    ))}
                  </ul>
                </div>
              ))}
            </div>
            <Link
              href="/news"
              className="mt-4 inline-flex text-sm font-medium text-accent hover:underline"
            >
              전체 뉴스 · 일자별 보기 →
            </Link>
          </>
        ) : (
          <p className="mt-3 text-sm text-muted">
            아직 생성된 뉴스 브리프가 없습니다. <Link href="/news" className="text-accent hover:underline">뉴스 페이지</Link>에서
            스크랩 후 생성하거나, 매일 08:00 자동 생성됩니다.
          </p>
        )}
      </section>

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
      <section className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
        {BANNERS.map((b) => (
          <Link
            key={b.href}
            href={b.href}
            className={`card card-hover relative overflow-hidden bg-gradient-to-br ${b.accent}`}
          >
            <b.Icon className="h-5 w-5 text-foreground/70" aria-hidden />
            <p className="mt-3 text-base font-semibold tracking-tight">{b.title}</p>
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
