"use client";

import { RefreshCw, Target, TrendingUp } from "lucide-react";

import { api, type AccuracyTrackReport } from "@/lib/api";
import { ErrorNote, Loading, PageHeader, useApi } from "@/components/shell";

function pct(v: number, d = 1): string {
  return `${v > 0 ? "+" : ""}${v.toFixed(d)}%`;
}

function Chart({ r }: { r: AccuracyTrackReport }) {
  const pts = r.points;
  if (pts.length < 2) return null;
  const W = 820;
  const H = 300;
  const padL = 46;
  const padR = 14;
  const padT = 14;
  const padB = 26;
  const vals = pts.flatMap((p) => [p.actual_cum_pct, p.model_cum_pct]);
  const vmin = Math.min(0, ...vals);
  const vmax = Math.max(...vals);
  const span = vmax - vmin || 1;
  const x = (i: number) => padL + (i / (pts.length - 1)) * (W - padL - padR);
  const y = (v: number) => H - padB - ((v - vmin) / span) * (H - padT - padB);
  const actualLine = pts.map((p, i) => `${x(i).toFixed(1)},${y(p.actual_cum_pct).toFixed(1)}`).join(" ");
  const modelLine = pts.map((p, i) => `${x(i).toFixed(1)},${y(p.model_cum_pct).toFixed(1)}`).join(" ");
  const misses = pts.map((p, i) => ({ p, i })).filter((o) => o.p.hit === false);
  const zeroY = y(0);

  return (
    <svg viewBox={`0 0 ${W} ${H}`} className="w-full" role="img" aria-label="예측 vs 실제 누적수익 시계열">
      <line x1={padL} y1={zeroY} x2={W - padR} y2={zeroY} className="stroke-current text-border" strokeWidth={1} strokeDasharray="3 3" />
      <polyline points={actualLine} className="fill-none stroke-current text-foreground" strokeWidth={1.8} strokeLinejoin="round" />
      <polyline points={modelLine} className="fill-none stroke-current text-accent2" strokeWidth={1.6} strokeDasharray="6 3" strokeLinejoin="round" />
      {misses.map((o) => (
        <circle key={o.i} cx={x(o.i)} cy={y(o.p.actual_cum_pct)} r={2.2} className="fill-current text-down" />
      ))}
      <text x={6} y={y(vmax) + 4} className="fill-current text-muted text-[10px]">{vmax.toFixed(0)}%</text>
      <text x={6} y={zeroY + 4} className="fill-current text-muted text-[10px]">0%</text>
      <text x={padL} y={H - 6} className="fill-current text-muted text-[10px]">{pts[0].date}</text>
      <text x={W - padR - 56} y={H - 6} className="fill-current text-muted text-[10px]">{pts[pts.length - 1].date}</text>
    </svg>
  );
}

function Stat({ label, value, tone }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg border border-border/60 bg-surface/60 p-3">
      <p className="text-[11px] text-muted">{label}</p>
      <p className={`num mt-1 text-lg font-bold ${tone ?? ""}`}>{value}</p>
    </div>
  );
}

export default function AccuracyPage() {
  const track = useApi<AccuracyTrackReport>(() => api.accuracyTrack());
  const r = track.data;
  const s = r?.score;
  const skillTone = s ? (s.skill >= 0.02 ? "text-up" : s.skill <= -0.02 ? "text-down" : "text-muted") : "";

  return (
    <main className="mx-auto max-w-6xl space-y-6 px-6 py-10">
      <PageHeader
        title="예측 정확도 · 추적"
        subtitle="이 프로그램의 예측을 과거 전 구간에 재현(replay)해 실제 결과와 비교·채점하고, 그 오차로 도출한 보정을 다음 예측에 자동 반영합니다."
      />

      {track.loading ? (
        <div className="card">
          <Loading />
          <p className="mt-2 text-xs text-muted">과거 시세를 수집해 예측을 재현·채점 중입니다…</p>
        </div>
      ) : track.error ? (
        <ErrorNote error={track.error} />
      ) : r && s ? (
        <>
          {/* Time-series chart */}
          <section className="card">
            <div className="flex flex-wrap items-center gap-2">
              <TrendingUp className="h-5 w-5 text-accent" aria-hidden />
              <h2 className="text-lg font-semibold tracking-tight">예측 vs 실제 (누적수익)</h2>
              <span className="num ml-auto text-[11px] text-muted/80">
                {r.symbol} · {r.window_days}거래일 · D{r.horizon_days} · {r.source === "yahoo" ? "실데이터" : "mock"}
              </span>
            </div>
            <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs">
              <span className="inline-flex items-center gap-1.5">
                <span className="h-0.5 w-5 bg-foreground" /> 실제 (지수 매수보유)
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-0.5 w-5 border-t-2 border-dashed border-accent2" /> 모델 (예측 방향 추종)
              </span>
              <span className="inline-flex items-center gap-1.5">
                <span className="h-2 w-2 rounded-full bg-down" /> 방향 오답
              </span>
            </div>
            <div className="mt-3">
              <Chart r={r} />
            </div>
            <p className="mt-2 text-[11px] leading-relaxed text-muted">
              두 선이 겹치면 모델이 시장 추세를 정확히 따라간 것(상승장에서 강세 유지 = 매수보유와 동일).
              하락 국면에서 모델이 방어로 돌면 두 선이 갈라집니다. 빨간 점은 방향이 틀린 시점입니다.
            </p>
          </section>

          {/* Scorecard */}
          <section className="card">
            <div className="flex items-center gap-2">
              <Target className="h-5 w-5 text-accent" aria-hidden />
              <h2 className="text-lg font-semibold tracking-tight">채점표</h2>
              <span className="num ml-auto text-[11px] text-muted/80">표본 {s.samples}회 (D{r.horizon_days})</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-4">
              <Stat label="방향 적중률" value={`${(s.hit_rate * 100).toFixed(1)}%`} />
              <Stat label="기저율(항상 다수)" value={`${(s.base_rate * 100).toFixed(1)}%`} />
              <Stat label="스킬(적중−기저)" value={pct(s.skill * 100, 1) + "p"} tone={skillTone} />
              <Stat
                label="상승/하락 예측 적중"
                value={`${s.bull_hit !== null ? (s.bull_hit * 100).toFixed(0) + "%" : "—"} / ${s.bear_hit !== null ? (s.bear_hit * 100).toFixed(0) + "%" : "N/A"}`}
              />
              <Stat label="누적 실제(매수보유)" value={pct(s.final_actual_cum_pct)} tone="text-up" />
              <Stat label="누적 모델(예측추종)" value={pct(s.final_model_cum_pct)} tone="text-accent2" />
              <Stat label="상승/하락 예측 횟수" value={`${s.bull_samples} / ${s.bear_samples}`} />
              <Stat label="방향 제시 비율" value={`${(s.coverage * 100).toFixed(0)}%`} />
            </div>
            <p className="mt-3 text-[11px] leading-relaxed text-muted">{r.interpretation}</p>
          </section>

          {/* Auto-feedback calibration */}
          <section className="card border-accent/30">
            <div className="flex flex-wrap items-center gap-2">
              <RefreshCw className="h-5 w-5 text-accent" aria-hidden />
              <h2 className="text-lg font-semibold tracking-tight">자동 피드백 보정</h2>
              <span className="rounded-full border border-accent/40 bg-accent/10 px-2.5 py-0.5 text-xs font-bold text-accent">
                등급 {r.calibration.grade}
              </span>
              <span className="chip ml-auto border-up/30 bg-up/10 text-up">다음 예측에 자동 반영됨</span>
            </div>
            <div className="mt-3 grid grid-cols-2 gap-2 sm:grid-cols-2">
              <Stat
                label="방향 보정 (하우스 점수 가산)"
                value={`${r.calibration.direction_bias >= 0 ? "+" : ""}${r.calibration.direction_bias.toFixed(3)}`}
                tone={r.calibration.direction_bias > 0 ? "text-up" : r.calibration.direction_bias < 0 ? "text-down" : "text-muted"}
              />
              <Stat
                label="확신도 목표 (실현 적중률 정합)"
                value={r.calibration.confidence_target > 0 ? `${(r.calibration.confidence_target * 100).toFixed(0)}%` : "—"}
              />
              <Stat
                label="방향별 확신도 앵커 (상승콜/하락콜)"
                value={`${r.calibration.bull_target ? (r.calibration.bull_target * 100).toFixed(0) + "%" : "—"} / ${r.calibration.bear_target ? (r.calibration.bear_target * 100).toFixed(0) + "%" : "—"}`}
              />
            </div>
            <p className="mt-3 text-xs leading-relaxed text-foreground/90">{r.calibration.basis}</p>
            <p className="mt-2 text-[11px] leading-relaxed text-muted">
              채점 → 보정 도출 → 다음 예측에 반영 → 재채점의 루프로, 오차를 줄이는 방향으로 예측이 자동 개선됩니다.
              모델·백테스트와 동일한 신호(trend_core)를 채점하므로, 측정한 정확도가 곧 실제 사용되는 예측의 정확도입니다.
            </p>
          </section>
        </>
      ) : null}
    </main>
  );
}
