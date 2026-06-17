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
