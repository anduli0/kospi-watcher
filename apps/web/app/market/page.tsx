"use client";

import { Activity, Building2, Globe, TrendingDown, TrendingUp, User } from "lucide-react";

import { api, type InvestorFlow, type MarketAnalysis, type SectorMove } from "@/lib/api";
import { ErrorNote, Loading, PageHeader, useApi } from "@/components/shell";

/** Korea convention: up = red, down = blue. */
function toneClass(v: number): string {
  return v > 0 ? "text-up" : v < 0 ? "text-down" : "text-muted";
}
function barClass(v: number): string {
  return v > 0 ? "bg-up" : v < 0 ? "bg-down" : "bg-muted";
}
function pct(v: string | null): string {
  if (v === null) return "—";
  const n = Number(v);
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
}
function eok(v: string): string {
  const n = Math.round(Number(v));
  return `${n > 0 ? "+" : ""}${n.toLocaleString()}억`;
}

function SectorRow({ s, maxAbs }: { s: SectorMove; maxAbs: number }) {
  const v = Number(s.change_pct);
  const widthPct = maxAbs > 0 ? (Math.abs(v) / maxAbs) * 50 : 0; // half-width diverging
  return (
    <div className="flex items-center gap-3 py-2">
      <span className="w-20 shrink-0 text-sm">{s.name}</span>
      <div className="relative h-2.5 flex-1 rounded-full bg-elevated">
        <div className="absolute left-1/2 top-0 h-2.5 w-px -translate-x-1/2 bg-border" />
        <div
          className={`absolute top-0 h-2.5 rounded-full ${barClass(v)}`}
          style={
            v >= 0
              ? { left: "50%", width: `${widthPct}%` }
              : { right: "50%", width: `${widthPct}%` }
          }
        />
      </div>
      <span className={`num w-16 shrink-0 text-right text-sm font-semibold ${toneClass(v)}`}>
        {pct(s.change_pct)}
      </span>
    </div>
  );
}

const FLOW_ICON: Record<string, typeof Globe> = {
  FOREIGN: Globe,
  INSTITUTION: Building2,
  INDIVIDUAL: User,
};

function FlowCard({ f }: { f: InvestorFlow }) {
  const Icon = FLOW_ICON[f.investor] ?? User;
  const today = Number(f.net_today);
  const trendMax = Math.max(1, ...f.trend.map((t) => Math.abs(Number(t.net))));
  return (
    <div className="rounded-xl border border-border/70 bg-elevated/40 p-4">
      <div className="flex items-center gap-2">
        <Icon className="h-4 w-4 text-muted" aria-hidden />
        <span className="text-sm font-semibold">{f.label}</span>
        <span className={`num ml-auto text-xs font-semibold ${toneClass(today)}`}>
          {today > 0 ? "순매수" : today < 0 ? "순매도" : "중립"}
        </span>
      </div>
      <p className={`num mt-2 text-2xl font-bold ${toneClass(today)}`}>{eok(f.net_today)}</p>
      <p className="num mt-0.5 text-[11px] text-muted">5일 누적 {eok(f.net_5d)}</p>
      {/* 5-day mini trend (diverging bars around a zero line) */}
      <div className="mt-3 flex h-12 items-center gap-1.5">
        {f.trend.map((t) => {
          const n = Number(t.net);
          const h = (Math.abs(n) / trendMax) * 100;
          return (
            <div key={t.date} className="flex flex-1 flex-col items-center" title={`${t.date}: ${eok(t.net)}`}>
              <div className="flex h-10 w-full flex-col justify-center">
                <div className="flex h-5 items-end justify-center">
                  {n > 0 && <div className={`w-2.5 rounded-t-sm ${barClass(n)}`} style={{ height: `${h}%` }} />}
                </div>
                <div className="flex h-5 items-start justify-center">
                  {n < 0 && <div className={`w-2.5 rounded-b-sm ${barClass(n)}`} style={{ height: `${h}%` }} />}
                </div>
              </div>
            </div>
          );
        })}
      </div>
      <p className="num mt-1 text-center text-[10px] text-muted/70">최근 5거래일</p>
    </div>
  );
}

export default function MarketPage() {
  const analysis = useApi<MarketAnalysis>(() => api.marketAnalysis());
  const a = analysis.data;
  const idx = a?.index_change_pct !== null && a?.index_change_pct !== undefined ? Number(a.index_change_pct) : null;
  const maxAbs = a ? Math.max(1, ...a.sectors.map((s) => Math.abs(Number(s.change_pct)))) : 1;

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-10">
      <PageHeader
        title="시장 흐름"
        subtitle="코스피를 움직인 주요 산업 섹터와 외국인·기관·개인 수급 추이"
      />

      {analysis.loading ? (
        <Loading />
      ) : analysis.error ? (
        <ErrorNote error={analysis.error} />
      ) : a ? (
        <>
          {/* Index + narrative */}
          <section className="card">
            <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
              <div>
                <p className="section-label">코스피 (KOSPI)</p>
                <div className="mt-1 flex items-end gap-3">
                  <span className="num text-4xl font-bold leading-none">
                    {a.index_price ? Number(a.index_price).toLocaleString() : "—"}
                  </span>
                  {idx !== null && (
                    <span
                      className={`num inline-flex items-center gap-1 pb-0.5 text-lg font-semibold ${toneClass(idx)}`}
                    >
                      {idx > 0 ? <TrendingUp className="h-4 w-4" /> : idx < 0 ? <TrendingDown className="h-4 w-4" /> : null}
                      {pct(a.index_change_pct)}
                    </span>
                  )}
                </div>
              </div>
              <div className="ml-auto flex flex-wrap items-center gap-1.5">
                <span className="chip border-accent/30 bg-accent/10 text-accent">
                  섹터: {a.sector_source === "yahoo" ? "Yahoo 실시간" : "오프라인(mock)"}
                </span>
                <span className="chip border-warning/30 bg-warning/10 text-warning">
                  수급: 대표값(예시) · 실데이터 연동 전
                </span>
              </div>
            </div>
            <p className="mt-5 flex items-start gap-2 leading-7 text-foreground/90">
              <Activity className="mt-1 h-4 w-4 shrink-0 text-muted" aria-hidden />
              <span>{a.narrative}</span>
            </p>
          </section>

          {/* Sector board */}
          <section className="card">
            <div className="flex items-center justify-between">
              <h2 className="section-label">섹터별 등락 (KODEX 산업 ETF)</h2>
              <span className="num text-[11px] text-muted/70">강세 ▲ 빨강 · 약세 ▼ 파랑</span>
            </div>
            <div className="mt-3 divide-y divide-border/40">
              {a.sectors.map((s) => (
                <SectorRow key={s.key} s={s} maxAbs={maxAbs} />
              ))}
            </div>
          </section>

          {/* Investor flows */}
          <section className="card">
            <div className="flex items-center justify-between">
              <h2 className="section-label">투자자별 수급 (외국인 · 기관 · 개인)</h2>
              <span className="num text-[11px] text-muted/70">+순매수 · −순매도 (억원)</span>
            </div>
            <div className="mt-4 grid gap-3 sm:grid-cols-3">
              {a.flows.map((f) => (
                <FlowCard key={f.investor} f={f} />
              ))}
            </div>
            <p className="mt-4 rounded-lg border border-warning/20 bg-warning/5 p-3 text-[11px] leading-relaxed text-muted">
              <strong className="text-warning/90">수급 데이터 고지.</strong> 외국인·기관·개인 순매수 수치는
              지수 흐름과 정합하도록 산출한 <strong>대표값(예시)</strong>이며, 실제 KRX 집계가 아닙니다. 추후
              KRX/pykrx 실데이터 연동 시 자동 대체됩니다. 섹터 등락은 Yahoo 실시간(키리스) 기준입니다.
            </p>
          </section>
        </>
      ) : null}
    </main>
  );
}
