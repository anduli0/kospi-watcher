"use client";

/**
 * SyncBanner — the site's self-update strip.
 *
 * Shows when the data was last refreshed and which engine analyses it
 * (내 클로드 구독 vs 기본 모드), lets the user trigger a refresh, and — the key
 * bit — auto-triggers one when the page opens on stale data, so a phone visit
 * refreshes the whole site by itself. The server enforces single-flight and a
 * cooldown, so this is always safe to call.
 */

import { useCallback, useEffect, useRef, useState } from "react";
import { Cloud, RefreshCw, Sparkles } from "lucide-react";

import { IS_STATIC, api, type SyncStatus } from "@/lib/api";

const POLL_MS = 5000;

function kstTime(iso: string | null): string {
  if (!iso) return "아직 없음";
  return new Date(iso).toLocaleString("ko-KR", {
    timeZone: "Asia/Seoul",
    month: "numeric",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

function agoText(iso: string | null): string {
  if (!iso) return "";
  const mins = Math.max(0, Math.round((Date.now() - new Date(iso).getTime()) / 60000));
  if (mins < 1) return "방금";
  if (mins < 60) return `${mins}분 전`;
  const hours = Math.floor(mins / 60);
  if (hours < 24) return `${hours}시간 전`;
  return `${Math.floor(hours / 24)}일 전`;
}

export function engineLabel(runtime: string): string {
  if (runtime === "claude_cli") return "내 클로드로 분석";
  if (runtime === "llm") return "클로드 API 분석";
  return "기본 분석 모드";
}

/**
 * Read-only banner for the always-on cloud (GitHub Pages) build. There is no
 * live backend to trigger, so it just shows the engine + when GitHub Actions
 * last rebuilt the site. No polling, no buttons.
 */
function StaticSyncBanner() {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  useEffect(() => {
    let alive = true;
    api
      .syncStatus()
      .then((s) => alive && setStatus(s))
      .catch(() => {});
    return () => {
      alive = false;
    };
  }, []);
  if (!status) return null;
  const live = status.runtime !== "mock";
  return (
    <div className="card flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
      <span
        className={`chip ${
          live
            ? "border-accent/40 bg-accent/10 text-accent"
            : "border-border/60 bg-elevated/40 text-muted"
        }`}
      >
        <Sparkles className="mr-1 inline h-3 w-3" aria-hidden />
        {engineLabel(status.runtime)}
      </span>
      <span className="text-sm text-muted">
        마지막 업데이트{" "}
        <span className="num text-foreground/90">{kstTime(status.last_prediction_at)}</span>
        {status.last_prediction_at && (
          <span className="num"> · {agoText(status.last_prediction_at)}</span>
        )}
      </span>
      <span className="ml-auto inline-flex items-center gap-1.5 chip border-accent2/30 bg-accent2/10 text-accent2">
        <Cloud className="h-3.5 w-3.5" aria-hidden />
        클라우드에서 매일 자동 업데이트 (PC 없이 상시 가동)
      </span>
    </div>
  );
}

export function SyncBanner({ onSynced }: { onSynced?: () => void }) {
  // IS_STATIC is a build-time constant, so this branch is stable per build.
  return IS_STATIC ? <StaticSyncBanner /> : <LiveSyncBanner onSynced={onSynced} />;
}

function LiveSyncBanner({ onSynced }: { onSynced?: () => void }) {
  const [status, setStatus] = useState<SyncStatus | null>(null);
  const [starting, setStarting] = useState(false);
  const autoFired = useRef(false);
  const wasRunning = useRef(false);
  const onSyncedRef = useRef(onSynced);
  onSyncedRef.current = onSynced;

  const poll = useCallback(async () => {
    try {
      const s = await api.syncStatus();
      // A run just finished successfully -> tell the page to reload its data.
      if (wasRunning.current && !s.running && s.ok) onSyncedRef.current?.();
      wasRunning.current = s.running;
      setStatus(s);
      return s;
    } catch {
      return null;
    }
  }, []);

  const start = useCallback(async () => {
    setStarting(true);
    try {
      await api.syncRun();
      await poll();
    } finally {
      setStarting(false);
    }
  }, [poll]);

  useEffect(() => {
    let alive = true;
    (async () => {
      const s = await poll();
      // Self-update: opening the site on stale data kicks a refresh (once).
      if (alive && s && s.stale && !s.running && s.cooldown_seconds === 0 && !autoFired.current) {
        autoFired.current = true;
        await start();
      }
    })();
    const timer = setInterval(poll, POLL_MS);
    return () => {
      alive = false;
      clearInterval(timer);
    };
  }, [poll, start]);

  if (!status) return null;

  const live = status.runtime !== "mock";
  const cooldownMin = Math.ceil(status.cooldown_seconds / 60);
  const busy = status.running || starting;

  return (
    <div className="card flex flex-wrap items-center gap-x-4 gap-y-2 py-3">
      <span
        className={`chip ${
          live
            ? "border-accent/40 bg-accent/10 text-accent"
            : "border-border/60 bg-elevated/40 text-muted"
        }`}
      >
        <Sparkles className="mr-1 inline h-3 w-3" aria-hidden />
        {engineLabel(status.runtime)}
      </span>

      {busy ? (
        <span className="flex items-center gap-2 text-sm text-foreground/90">
          <span className="relative flex h-2.5 w-2.5">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-accent opacity-60" />
            <span className="relative inline-flex h-2.5 w-2.5 rounded-full bg-accent" />
          </span>
          새로 분석하는 중{status.stage_ko ? ` — ${status.stage_ko}` : ""}… 잠시만요
        </span>
      ) : (
        <span className="text-sm text-muted">
          마지막 업데이트{" "}
          <span className="num text-foreground/90">{kstTime(status.last_prediction_at)}</span>
          {status.last_prediction_at && (
            <span className="num"> · {agoText(status.last_prediction_at)}</span>
          )}
        </span>
      )}

      {!busy && status.ok === false && status.error && (
        <span className="text-xs text-warning">직전 업데이트 실패 — 다시 시도할 수 있어요</span>
      )}

      <button
        onClick={start}
        disabled={busy || status.cooldown_seconds > 0}
        className="ml-auto inline-flex items-center gap-1.5 rounded-xl border border-accent/40 bg-accent/10 px-3.5 py-1.5 text-xs font-semibold text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
      >
        <RefreshCw className={`h-3.5 w-3.5 ${busy ? "animate-spin" : ""}`} aria-hidden />
        {busy
          ? "업데이트 중…"
          : status.cooldown_seconds > 0
            ? `${cooldownMin}분 후 다시 가능`
            : "지금 업데이트"}
      </button>
    </div>
  );
}
