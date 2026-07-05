"use client";

import { Minus, TrendingDown, TrendingUp } from "lucide-react";

import {
  api,
  type BacktestReport,
  type HorizonProjection,
  type InstrumentAnalysisReport,
  type InstrumentOutlook,
  type PositionVerdict,
} from "@/lib/api";
import {
  BacktestCard,
  DIRECTION_KO,
  ErrorNote,
  KIND_KO,
  Loading,
  MonetaryPolicyCard,
  PageHeader,
  RegimeBadge,
  TrendSignalCard,
  dirText,
  useApi,
} from "@/components/shell";

/** Korea convention: 매수(상승 기대)=red, 매도=blue, 중립=muted. */
function verdictTone(v: PositionVerdict): string {
  return v === "BUY"
    ? "border-up/40 bg-up/10 text-up"
    : v === "SELL"
      ? "border-down/40 bg-down/10 text-down"
      : "border-border bg-elevated text-muted";
}

function won(v: string | null): string {
  return v === null ? "—" : `${Number(v).toLocaleString()}`;
}

function pctText(v: string): string {
  const n = Number(v);
  return `${n > 0 ? "+" : ""}${n.toFixed(2)}%`;
}

function DirIcon({ direction }: { direction: string }) {
  if (direction === "BULLISH") return <TrendingUp className="h-3.5 w-3.5 text-up" />;
  if (direction === "BEARISH") return <TrendingDown className="h-3.5 w-3.5 text-down" />;
  return <Minus className="h-3.5 w-3.5 text-muted" />;
}

function ProjectionCard({ p }: { p: HorizonProjection }) {
  const ret = Number(p.expected_return_pct);
  return (
    <div className="rounded-xl border border-border/60 bg-elevated/40 p-3">
      <div className="flex items-center justify-between">
        <span className="text-xs font-semibold text-foreground/80">{p.label}</span>
        <span className={`num inline-flex items-center gap-1 text-xs font-semibold ${dirText(p.direction)}`}>
          <DirIcon direction={p.direction} />
          {pctText(p.expected_return_pct)}
        </span>
      </div>
      <p className="num mt-2 text-base font-semibold">
        {won(p.target_low)} <span className="text-muted">~</span> {won(p.target_high)}
      </p>
      <p className="num text-[11px] text-muted">기준 {won(p.target_base)}원</p>
      <p className="mt-2 text-[11px] leading-relaxed text-muted">{p.rationale}</p>
      {/* subtle position of the expected return within the projected band */}
      <div className="mt-2 h-1 w-full rounded-full bg-elevated">
        <div
          className={`h-1 rounded-full ${ret > 0 ? "bg-up" : ret < 0 ? "bg-down" : "bg-muted"}`}
          style={{ width: `${Math.min(100, Math.abs(ret) * 4 + 6)}%` }}
        />
      </div>
    </div>
  );
}

function InstrumentCard({ ins }: { ins: InstrumentOutlook }) {
  return (
    <section className="card">
      <div className="flex flex-wrap items-center gap-x-3 gap-y-2">
        <h2 className="text-lg font-semibold tracking-tight">{ins.name}</h2>
        <span className="num text-[11px] text-muted">{KIND_KO[ins.kind] ?? ins.kind}</span>
        <span className="num text-[11px] text-muted">· {ins.symbol}</span>
        <div className="ml-auto flex items-center gap-3">
          {ins.current_price && (
            <span className="num text-sm">
              현재가 <span className="font-semibold">{Number(ins.current_price).toLocaleString()}원</span>
            </span>
          )}
          <span
            className={`rounded-full border px-3 py-1 text-sm font-bold ${verdictTone(ins.verdict)}`}
          >
            {ins.verdict_label}
          </span>
        </div>
      </div>

      <p className="mt-3 text-sm leading-relaxed text-foreground/90">{ins.summary}</p>
      {ins.risk_note && (
        <p className="mt-2 rounded-lg border border-warning/20 bg-warning/5 p-2.5 text-[11px] leading-relaxed text-warning/90">
          ⚠ {ins.risk_note}
        </p>
      )}

      <div className="mt-4 grid gap-3 sm:grid-cols-3">
        {ins.projections.map((p) => (
          <ProjectionCard key={p.horizon} p={p} />
        ))}
      </div>
    </section>
  );
}

export default function AnalysisPage() {
  const report = useApi<InstrumentAnalysisReport>(() => api.instrumentAnalysis());
  const backtest = useApi<BacktestReport>(() => api.backtest());
  const r = report.data;

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-10">
      <PageHeader
        title="포지션 분석"
        subtitle="KODEX200 · 레버리지 · 인버스 · 곱버스 — 포지션 판단과 단·중·장기 가격 시나리오"
      />

      {report.loading ? (
        <Loading />
      ) : report.error ? (
        <ErrorNote error={report.error} />
      ) : r ? (
        <>
          {/* House view */}
          <section className="card">
            <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
              <span className="section-label">하우스 뷰</span>
              <span className={`text-2xl font-bold tracking-tight ${dirText(r.direction)}`}>
                {DIRECTION_KO[r.direction] ?? r.direction}
              </span>
              <span className="num text-sm text-muted">확신도 {Math.round(r.confidence * 100)}%</span>
              <RegimeBadge regime={r.regime} />
              <span className="num ml-auto text-[11px] text-muted/80">
                {r.subject} · 분석 {r.generated_by} · 시세 {r.price_source} · {r.as_of.slice(0, 16).replace("T", " ")}
              </span>
            </div>
            <p className="mt-3 text-sm leading-relaxed text-foreground/90">{r.house_summary}</p>
          </section>

          {/* Price-trend anchor — the primary directional driver */}
          {r.trend_signal && <TrendSignalCard ts={r.trend_signal} />}

          {/* BOK monetary policy — a core macro risk tilt */}
          {r.monetary_policy && <MonetaryPolicyCard mp={r.monetary_policy} />}

          {/* Accuracy backtest of the trend anchor */}
          {backtest.data && <BacktestCard b={backtest.data} />}

          {/* Per-instrument analysis */}
          {r.instruments.map((ins) => (
            <InstrumentCard key={ins.symbol} ins={ins} />
          ))}

          {/* Disclaimer */}
          <p className="rounded-lg border border-border/60 bg-elevated/30 p-3 text-[11px] leading-relaxed text-muted">
            <strong className="text-foreground/70">분석 고지.</strong> {r.disclaimer} 본 화면은 모의
            체결·실거래 기능이 없는 <strong>분석 전용</strong>입니다.
          </p>
        </>
      ) : null}
    </main>
  );
}
