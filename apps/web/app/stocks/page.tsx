"use client";

import { useState } from "react";
import {
  Calendar,
  CalendarClock,
  CalendarRange,
  ChevronDown,
  Flame,
  Newspaper,
} from "lucide-react";

import {
  api,
  type HorizonRecommendation,
  type StockPick,
  type StockRecommendationReport,
} from "@/lib/api";
import {
  DIRECTION_KO,
  ErrorNote,
  Loading,
  PageHeader,
  RegimeBadge,
  dirText,
  useApi,
} from "@/components/shell";

const HORIZON_ICON: Record<string, typeof Calendar> = {
  SHORT: Calendar,
  MID: CalendarClock,
  LONG: CalendarRange,
};

const STANCE_KO: Record<string, string> = {
  HAWKISH: "매파(긴축)",
  DOVISH: "비둘기(완화)",
  NEUTRAL: "중립",
};

function convictionTone(c: string): string {
  return c === "적극매수"
    ? "border-up/50 bg-up/15 text-up"
    : c === "매수"
      ? "border-up/30 bg-up/5 text-up"
      : "border-border bg-elevated text-muted";
}

function PickRow({ p }: { p: StockPick }) {
  const [open, setOpen] = useState(false);
  const mom = p.momentum_pct !== null ? Number(p.momentum_pct) : null;
  const stretch = p.stretch_pct !== null ? Number(p.stretch_pct) : null;
  return (
    <div className="border-b border-border/40 last:border-0">
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        className="flex w-full gap-3 py-3 text-left transition-colors hover:bg-elevated/30"
      >
        <div className="num grid h-7 w-7 shrink-0 place-items-center rounded-lg bg-elevated text-sm font-bold text-muted">
          {p.rank}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-x-2 gap-y-1">
            <span className="text-sm font-semibold">{p.name}</span>
            <span className="num text-[11px] text-muted">{p.code}</span>
            <span className="text-[11px] text-muted">· {p.sector}</span>
            {p.overheated && (
              <span className="chip border-warning/40 bg-warning/10 text-warning">
                <Flame className="h-3 w-3" aria-hidden /> 과열
              </span>
            )}
            {p.news_catalyst && (
              <span className="chip border-accent2/30 bg-accent2/10 text-accent2">
                <Newspaper className="h-3 w-3" aria-hidden /> 뉴스
              </span>
            )}
            <span
              className={`ml-auto rounded-full border px-2.5 py-0.5 text-xs font-bold ${convictionTone(p.conviction)}`}
            >
              {p.conviction}
            </span>
            <ChevronDown
              className={`h-4 w-4 text-muted transition-transform ${open ? "rotate-180" : ""}`}
              aria-hidden
            />
          </div>
          <div className="mt-1 flex flex-wrap items-center gap-x-3 gap-y-1 text-[11px]">
            {p.price !== null && (
              <span className="num text-muted">{Number(p.price).toLocaleString()}원</span>
            )}
            {mom !== null && (
              <span className={`num font-semibold ${dirText(mom > 0 ? "BULLISH" : mom < 0 ? "BEARISH" : "NEUTRAL")}`}>
                모멘텀 {mom > 0 ? "+" : ""}{mom.toFixed(1)}%
              </span>
            )}
            <span className="flex flex-wrap gap-1">
              {p.themes.slice(0, 3).map((t) => (
                <span key={t} className="rounded bg-elevated px-1.5 py-0.5 text-[10px] text-muted">
                  {t}
                </span>
              ))}
            </span>
          </div>
          <p className="mt-1.5 text-xs leading-relaxed text-muted">{p.drivers.join(" · ")}</p>
        </div>
      </button>
      {open && (
        <div className="ml-10 mb-3 rounded-lg border border-border/50 bg-elevated/40 p-3">
          <p className="text-xs font-semibold text-foreground/80">추천 근거 (상세)</p>
          <p className="mt-1.5 text-xs leading-relaxed text-foreground/90">{p.detail}</p>
          <div className="mt-2.5 flex flex-wrap gap-x-4 gap-y-1 text-[11px] text-muted">
            <span className="num">모델 점수 {p.score.toFixed(2)}</span>
            {stretch !== null && (
              <span className={`num ${stretch >= 35 ? "text-warning" : ""}`}>
                120일선 이격 {stretch > 0 ? "+" : ""}{stretch.toFixed(1)}%
              </span>
            )}
            <span className="num">테마: {p.themes.join(" · ")}</span>
          </div>
          {p.news_catalyst && (
            <p className="mt-2 truncate text-[11px] text-accent2/80">📰 {p.news_catalyst}</p>
          )}
        </div>
      )}
    </div>
  );
}

function HorizonSection({ h }: { h: HorizonRecommendation }) {
  const Icon = HORIZON_ICON[h.horizon] ?? Calendar;
  return (
    <section className="card">
      <div className="flex items-center gap-2">
        <Icon className="h-5 w-5 text-accent" aria-hidden />
        <h2 className="text-lg font-semibold tracking-tight">{h.label}</h2>
        <Flame className="ml-auto h-4 w-4 text-up/70" aria-hidden />
        <span className="text-[11px] text-muted">Top {h.picks.length}</span>
      </div>
      <p className="mt-1 text-xs leading-relaxed text-muted">{h.approach}</p>
      <div className="mt-2">
        {h.picks.map((p) => (
          <PickRow key={p.code} p={p} />
        ))}
      </div>
    </section>
  );
}

export default function StocksPage() {
  const rec = useApi<StockRecommendationReport>(() => api.stockRecommendations());
  const r = rec.data;

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-10">
      <PageHeader
        title="종목 추천"
        subtitle="국장 전체에서 — 시총 상위 약 300개 종목을 전수 분석해 단기·중기·장기 Top 픽을 선별합니다. 가격 모멘텀·섹터·하우스 뷰·금리(BOK)·뉴스를 결합한 모델 추천."
      />

      {rec.loading ? (
        <div className="card">
          <Loading />
          <p className="mt-2 text-xs text-muted">시총 상위 약 300개 종목의 실시세를 수집·분석 중입니다 (10여 초)…</p>
        </div>
      ) : rec.error ? (
        <ErrorNote error={rec.error} />
      ) : r ? (
        <>
          {/* House context strip */}
          <section className="card">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <span className="section-label">반영된 시장 컨텍스트</span>
              <span className={`text-lg font-bold ${dirText(r.house_direction)}`}>
                {DIRECTION_KO[r.house_direction] ?? r.house_direction}
              </span>
              <RegimeBadge regime={r.house_regime} />
              <span className="chip border-warning/30 bg-warning/10 text-warning">
                BOK {STANCE_KO[r.monetary_stance] ?? r.monetary_stance}
              </span>
              <span className="num ml-auto text-[11px] text-muted/80">
                {r.universe_size}종목 · 시세 {r.price_source === "yahoo" ? "실시간" : "mock"} · {r.as_of.slice(0, 16).replace("T", " ")}
              </span>
            </div>
          </section>

          {/* Three horizons */}
          {r.horizons.map((h) => (
            <HorizonSection key={h.horizon} h={h} />
          ))}

          {/* Disclaimer */}
          <p className="rounded-lg border border-warning/20 bg-warning/5 p-3 text-[11px] leading-relaxed text-muted">
            <strong className="text-warning/90">투자 유의.</strong> {r.disclaimer}
          </p>
        </>
      ) : null}
    </main>
  );
}
