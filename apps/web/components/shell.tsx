"use client";

import Link from "next/link";
import { useCallback, useEffect, useState } from "react";

import { ApiError } from "@/lib/api";

/** RESEARCH-mode / live-disabled banner shown on every page. */
export function SafetyBanner() {
  return (
    <div className="flex flex-wrap items-center gap-2">
      <span className="rounded-full border border-border bg-elevated px-3 py-1 font-mono text-xs text-muted">
        MODE: RESEARCH
      </span>
      <span className="rounded-full border border-danger/40 bg-danger/10 px-3 py-1 font-mono text-xs font-semibold text-danger">
        ● LIVE TRADING DISABLED
      </span>
    </div>
  );
}

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
    <header className="flex flex-wrap items-start justify-between gap-4">
      <div>
        <Link href="/" className="font-mono text-xs text-muted hover:text-accent">
          ← KOSPI-WATCHER
        </Link>
        <h1 className="mt-1 font-mono text-2xl font-semibold tracking-tight">{title}</h1>
        {subtitle ? <p className="mt-1 text-sm text-muted">{subtitle}</p> : null}
      </div>
      <SafetyBanner />
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

type AsyncState<T> = { data: T | null; error: string | null; loading: boolean };

/** Tiny client-side loader. Keeps `next build` static (fetch happens on mount). */
export function useApi<T>(fn: () => Promise<T>, deps: unknown[] = []): AsyncState<T> & {
  reload: () => void;
} {
  const [state, setState] = useState<AsyncState<T>>({
    data: null,
    error: null,
    loading: true,
  });

  const run = useCallback(() => {
    setState((s) => ({ ...s, loading: true, error: null }));
    fn()
      .then((data) => setState({ data, error: null, loading: false }))
      .catch((e: unknown) =>
        setState({
          data: null,
          loading: false,
          error: e instanceof ApiError ? e.message : String(e),
        }),
      );
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, deps);

  useEffect(run, [run]);
  return { ...state, reload: run };
}

export function ErrorNote({ error }: { error: string }) {
  return (
    <div className="rounded-lg border border-danger/40 bg-danger/10 p-4 text-sm text-danger">
      <p className="font-semibold">API 연결 실패</p>
      <p className="mt-1 font-mono text-xs break-all">{error}</p>
      <p className="mt-2 text-xs text-muted">
        백엔드가 실행 중인지 확인하세요: <span className="kbd">uvicorn main:app --app-dir apps/api --port 8000</span>
      </p>
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
