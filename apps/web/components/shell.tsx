"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { Landmark, LineChart as LineChartIcon, Target } from "lucide-react";

import {
  ApiError,
  type BacktestReport,
  type MonetaryPolicySignal,
  type TrendSignal,
} from "@/lib/api";

export function MockNotice() {
  return (
    <div className="rounded-lg border border-warning/30 bg-warning/10 p-3 text-xs text-warning">
      <strong className="font-semibold">MOCK DATA — NOT REAL MARKET DATA.</strong>{" "}
      이 단계의 모든 수치는 모의 데이터이며 실제 시세가 아닙니다. 실거래·실계좌 연결은 없습니다.
    </div>
  );
}

export function PageHeader({ title, subtitle }: { title: string; subtitle?: string }) {
  return (
    <header>
      <h1 className="text-3xl font-semibold tracking-tight">{title}</h1>
      {subtitle ? <p className="mt-2 max-w-2xl text-sm text-muted">{subtitle}</p> : null}
    </header>
  );
}

export function StatusPill({ ok, children }: { ok: boolean; children: React.ReactNode }) {
  return (
    <span
      className={
        "rounded-full px-2.5 py-0.5 font-mono text-xs font-semibold " +
        (ok
          ? "border border-accent/40 bg-accent/10 text-accent"
          : "border border-danger/40 bg-danger/10 text-danger")
      }
    >
      {children}
    </span>
  );
}

type AsyncState<T> = {
  data: T | null;
  error: string | null;
  loading: boolean;
  /** True while waiting to auto-retry after a connection error. */
  retrying: boolean;
};

const MAX_AUTO_RETRIES = 5;

/**
 * Tiny client-side loader with self-healing.
 *
 * On a *connection* error (the backend unreachable, status 0) it keeps the page
 * alive and automatically retries with exponential backoff — so when the API
 * comes back (e.g. after its self-healing restart) the data fills in on its own,
 * with no red error and no manual refresh. HTTP errors (404, 5xx) surface
 * immediately and are not auto-retried. `reload()` always resets the cycle.
 */
export function useApi<T>(fn: () => Promise<T>, deps: unknown[] = []): AsyncState<T> & {
  reload: () => void;
} {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    error: null,
    loading: true,
    retrying: false,
  });

  const timer = useRef<ReturnType<typeof setTimeout> | undefined>(undefined);
  const attempt = useRef(0);
  const alive = useRef(true);

  const run = useCallback(() => {
    if (timer.current) clearTimeout(timer.current);
    setState((s) => ({ ...s, loading: true, error: null, retrying: false }));
    fn()
      .then((data) => {
        if (!alive.current) return;
        attempt.current = 0;
        setState({ data, error: null, loading: false, retrying: false });
      })
      .catch((e: unknown) => {
        if (!alive.current) return;
        const message = e instanceof ApiError ? e.message : String(e);
        const isConnection = e instanceof ApiError && e.status === 0;
        if (isConnection && attempt.current < MAX_AUTO_RETRIES) {
          attempt.current += 1;
          const delay = Math.min(8000, 1000 * 2 ** (attempt.current - 1)); // 1→8s
          setState({ data: null, error: message, loading: false, retrying: true });
          timer.current = setTimeout(run, delay);
        } else {
          setState({ data: null, error: message, loading: false, retrying: false });
        }
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(() => {
    alive.current = true;
    run();
    return () => {
      alive.current = false;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [run]);

  return {
    ...state,
    reload: () => {
      attempt.current = 0;
      run();
    },
  };
}

export function ErrorNote({
  error,
  retrying = false,
  onRetry,
}: {
  error: string;
  /** When true, the loader is auto-retrying — show a calmer "reconnecting" state. */
  retrying?: boolean;
  onRetry?: () => void;
}) {
  const connection = error.startsWith("API unreachable");

  // Connection blips are transient and auto-heal — keep them calm, not alarming.
  if (connection) {
    return (
      <div className="rounded-lg border border-warning/30 bg-warning/10 p-4 text-sm">
        <div className="flex items-center gap-2 text-warning">
          {retrying && (
            <span className="h-3.5 w-3.5 animate-spin rounded-full border-2 border-warning/40 border-t-warning" />
          )}
          <p className="font-semibold">
            {retrying ? "백엔드에 다시 연결하는 중…" : "백엔드에 연결할 수 없습니다"}
          </p>
        </div>
        <p className="mt-1.5 text-xs text-muted">
          {retrying
            ? "API가 재시작 중일 수 있습니다. 연결되면 자동으로 화면이 채워집니다."
            : "API가 실행 중인지 확인하세요. 준비되면 자동으로 다시 시도합니다."}
        </p>
        {onRetry && (
          <button
            onClick={onRetry}
            className="mt-3 rounded-lg border border-warning/40 bg-warning/10 px-3 py-1.5 text-xs font-semibold text-warning transition-colors hover:bg-warning/20"
          >
            지금 다시 시도
          </button>
        )}
      </div>
    );
  }

  return (
    <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm text-danger">
      <p className="font-semibold">요청을 처리하지 못했습니다</p>
      <p className="mt-1 font-mono text-xs break-all">{error}</p>
      {onRetry && (
        <button
          onClick={onRetry}
          className="mt-3 rounded-lg border border-danger/40 bg-danger/10 px-3 py-1.5 text-xs font-semibold text-danger transition-colors hover:bg-danger/20"
        >
          다시 시도
        </button>
      )}
    </div>
  );
}

export function Loading() {
  return <p className="text-sm text-muted">불러오는 중…</p>;
}

// --- Domain labels & colors (Korea convention: up=red, down=blue) ---

export const DIRECTION_KO: Record<string, string> = {
  BULLISH: "강세",
  BEARISH: "약세",
  NEUTRAL: "중립",
};

export const REGIME_KO: Record<string, string> = {
  RISK_ON_STRONG: "강한 위험선호",
  RISK_ON_FRAGILE: "취약한 위험선호",
  LIQUIDITY_RALLY: "유동성 랠리",
  EARNINGS_RALLY: "실적 랠리",
  SIDEWAYS_LOW_VOL: "저변동성 횡보",
  SIDEWAYS_HIGH_VOL: "고변동성 횡보",
  RISK_OFF: "위험회피",
  CRISIS: "위기",
  DATA_UNCERTAIN: "데이터 불확실",
};

export const STANCE_KO: Record<string, string> = {
  OVERWEIGHT: "비중확대",
  NEUTRAL: "중립",
  UNDERWEIGHT: "비중축소",
  AVOID: "회피",
};

export const KIND_KO: Record<string, string> = {
  LONG_1X: "롱 (1x)",
  LONG_2X: "레버리지 (2x)",
  INVERSE_1X: "인버스 (-1x)",
  INVERSE_2X: "곱버스 (-2x)",
};

/** Text color for a market direction (강세=red, 약세=blue, 중립=muted). */
export function dirText(direction: string): string {
  return direction === "BULLISH"
    ? "text-up"
    : direction === "BEARISH"
      ? "text-down"
      : "text-muted";
}

export function DirectionPill({ direction, big = false }: { direction: string; big?: boolean }) {
  const tone =
    direction === "BULLISH"
      ? "border-up/40 bg-up/10 text-up"
      : direction === "BEARISH"
        ? "border-down/40 bg-down/10 text-down"
        : "border-border bg-elevated text-muted";
  return (
    <span
      className={`inline-flex items-center gap-1 rounded-full border font-semibold ${tone} ${
        big ? "px-3 py-1 text-sm" : "px-2 py-0.5 text-xs"
      }`}
    >
      {direction === "BULLISH" ? "▲" : direction === "BEARISH" ? "▼" : "■"}{" "}
      {DIRECTION_KO[direction] ?? direction}
    </span>
  );
}

export function RegimeBadge({ regime }: { regime: string }) {
  const danger = regime === "CRISIS" || regime === "RISK_OFF" || regime === "DATA_UNCERTAIN";
  return (
    <span
      className={
        "rounded-full border px-3 py-1 font-mono text-xs font-semibold " +
        (danger
          ? "border-danger/40 bg-danger/10 text-danger"
          : "border-accent/40 bg-accent/10 text-accent")
      }
    >
      {REGIME_KO[regime] ?? regime}
    </span>
  );
}

export function StanceBadge({ label }: { label: string }) {
  const tone =
    label === "OVERWEIGHT"
      ? "border-accent/40 bg-accent/10 text-accent"
      : label === "AVOID"
        ? "border-danger/40 bg-danger/10 text-danger"
        : label === "UNDERWEIGHT"
          ? "border-warning/40 bg-warning/10 text-warning"
          : "border-border bg-elevated text-muted";
  return (
    <span className={`rounded-md border px-2 py-0.5 font-mono text-xs font-semibold ${tone}`}>
      {STANCE_KO[label] ?? label}
    </span>
  );
}

const POLICY_STANCE_KO: Record<string, string> = {
  HAWKISH: "매파(긴축)",
  DOVISH: "비둘기(완화)",
  NEUTRAL: "중립/관망",
};
const POLICY_SOURCE_KO: Record<string, string> = {
  config: "사용자 지정",
  news: "BOK 뉴스 분석",
  mock: "모의",
};

/** BOK monetary-policy signal card. Colored by equity implication (매파→약세→파랑). */
export function MonetaryPolicyCard({ mp }: { mp: MonetaryPolicySignal }) {
  const tone = dirText(mp.equity_bias); // bullish=red, bearish=blue, neutral=muted
  const border =
    mp.equity_bias === "BULLISH"
      ? "border-up/40 bg-up/5"
      : mp.equity_bias === "BEARISH"
        ? "border-down/40 bg-down/5"
        : "border-border/70 bg-elevated/40";
  const n = Math.abs(mp.expected_hikes_2026);
  const move = mp.stance === "HAWKISH" ? "인상" : mp.stance === "DOVISH" ? "인하" : "";
  return (
    <div className={`rounded-xl border p-4 ${border}`}>
      <div className="flex items-center gap-2">
        <Landmark className="h-4 w-4 text-muted" aria-hidden />
        <span className="text-sm font-semibold">한국은행 통화정책 (BOK)</span>
        <span className={`ml-auto rounded-full border border-current/30 px-2.5 py-0.5 text-xs font-bold ${tone}`}>
          {POLICY_STANCE_KO[mp.stance] ?? mp.stance}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        {n > 0 && (
          <span className="num">
            2026년 ~{n}회 {move} 전망
          </span>
        )}
        <span className={`num font-semibold ${tone}`}>
          코스피 {DIRECTION_KO[mp.equity_bias] ?? mp.equity_bias} 압력
        </span>
        <span className="num text-muted">확신도 {Math.round(mp.confidence * 100)}%</span>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted">{mp.rationale}</p>
      {mp.drivers.length > 0 && (
        <div className="mt-2 flex flex-wrap gap-1.5">
          {mp.drivers.slice(0, 3).map((d) => (
            <span key={d} className="chip text-[11px] text-muted">
              {d.length > 38 ? d.slice(0, 37) + "…" : d}
            </span>
          ))}
        </div>
      )}
      <p className="num mt-2 text-[10px] text-muted/70">
        출처: {POLICY_SOURCE_KO[mp.source] ?? mp.source} · 핵심 거시 변수
      </p>
    </div>
  );
}

/** Price-trend anchor card (primary directional driver of the prediction). */
export function TrendSignalCard({ ts }: { ts: TrendSignal }) {
  const tone = dirText(ts.direction);
  const border =
    ts.direction === "BULLISH"
      ? "border-up/40 bg-up/5"
      : ts.direction === "BEARISH"
        ? "border-down/40 bg-down/5"
        : "border-border/70 bg-elevated/40";
  return (
    <div className={`rounded-xl border p-4 ${border}`}>
      <div className="flex items-center gap-2">
        <LineChartIcon className="h-4 w-4 text-muted" aria-hidden />
        <span className="text-sm font-semibold">가격 추세 (주 앵커)</span>
        <span className={`ml-auto rounded-full border border-current/30 px-2.5 py-0.5 text-xs font-bold ${tone}`}>
          {DIRECTION_KO[ts.direction] ?? ts.direction}
        </span>
      </div>
      <div className="mt-2 flex flex-wrap items-center gap-x-4 gap-y-1 text-sm">
        {ts.price !== null && (
          <span className="num">현재가 {Number(ts.price).toLocaleString()}</span>
        )}
        {ts.sma100 !== null && (
          <span className="num text-muted">100일선 {Number(ts.sma100).toLocaleString()}</span>
        )}
        {ts.mom60_pct !== null && (
          <span className={`num font-semibold ${dirText(Number(ts.mom60_pct) > 0 ? "BULLISH" : Number(ts.mom60_pct) < 0 ? "BEARISH" : "NEUTRAL")}`}>
            60일 모멘텀 {Number(ts.mom60_pct) > 0 ? "+" : ""}{ts.mom60_pct}%
          </span>
        )}
        <span className="num text-muted">강도 {Math.round(ts.strength * 100)}%</span>
      </div>
      <p className="mt-2 text-xs leading-relaxed text-muted">{ts.note}</p>
      <p className="num mt-2 text-[10px] text-muted/70">
        출처: {ts.source === "yahoo" ? "Yahoo 일봉 실데이터" : ts.source === "mock" ? "오프라인 mock" : "데이터 없음"} · 100일 SMA + 60일 모멘텀
      </p>
    </div>
  );
}

/** Accuracy backtest summary card (directional skill vs base rate). */
export function BacktestCard({ b }: { b: BacktestReport }) {
  const skillPct = b.primary_skill * 100;
  const skillTone =
    skillPct >= 2 ? "text-up" : skillPct <= -2 ? "text-down" : "text-muted";
  return (
    <div className="rounded-xl border border-border/70 bg-elevated/40 p-4">
      <div className="flex flex-wrap items-center gap-2">
        <Target className="h-4 w-4 text-muted" aria-hidden />
        <span className="text-sm font-semibold">방향 예측 정확도 (백테스트)</span>
        <span className="num ml-auto text-[11px] text-muted/80">
          {b.symbol} · {b.source === "yahoo" ? "실데이터" : "mock"} · {b.n_days}일 · out-of-sample {Math.round(b.test_fraction * 100)}%
        </span>
      </div>
      <div className="mt-3 grid grid-cols-1 gap-2 sm:grid-cols-3">
        {b.test.map((h) => {
          const sk = h.skill * 100;
          const tone = sk >= 2 ? "text-up" : sk <= -2 ? "text-down" : "text-muted";
          return (
            <div key={h.horizon_days} className="rounded-lg border border-border/60 bg-surface/60 p-3">
              <p className="text-[11px] text-muted">{h.label}</p>
              <p className="num mt-1 text-lg font-bold">{(h.hit_rate * 100).toFixed(1)}%</p>
              <p className="num text-[11px] text-muted">기저율 {(h.base_rate * 100).toFixed(1)}%</p>
              <p className={`num text-[11px] font-semibold ${tone}`}>
                스킬 {sk >= 0 ? "+" : ""}{sk.toFixed(1)}%p
              </p>
            </div>
          );
        })}
      </div>
      <p className={`num mt-3 text-xs font-semibold ${skillTone}`}>
        주 horizon(D{b.primary_horizon_days}) 적중률 {(b.primary_hit_rate * 100).toFixed(1)}% · 기저율 {(b.primary_base_rate * 100).toFixed(1)}% · 스킬 {skillPct >= 0 ? "+" : ""}{skillPct.toFixed(1)}%p
      </p>
      <p className="mt-2 text-[11px] leading-relaxed text-muted">{b.interpretation}</p>
    </div>
  );
}

/** A signed conviction bar centered at 0: 약세(blue) ← → 강세(red). */
export function LeanBar({ score }: { score: number }) {
  const pct = Math.max(-1, Math.min(1, score)) * 50; // -50..50
  const left = pct >= 0 ? 50 : 50 + pct;
  const width = Math.abs(pct);
  const color = score > 0.05 ? "bg-up" : score < -0.05 ? "bg-down" : "bg-muted";
  return (
    <div className="relative h-2 w-full rounded-full bg-elevated">
      <div className="absolute left-1/2 top-0 h-2 w-px -translate-x-1/2 bg-border" />
      <div
        className={`absolute top-0 h-2 rounded-full ${color}`}
        style={{ left: `${left}%`, width: `${width}%` }}
      />
    </div>
  );
}
