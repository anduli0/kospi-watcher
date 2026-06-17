"use client";

import { api } from "@/lib/api";
import { ErrorNote, Loading, PageHeader, StatusPill, useApi } from "@/components/shell";

export default function SystemPage() {
  const status = useApi(() => api.systemStatus());
  const health = useApi(() => api.health());
  const audit = useApi(() => api.auditLogs(25));

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <PageHeader title="System" subtitle="버전 · 시각 · 기능 플래그 · 데이터 소스 · 감사 로그" />

      <section className="mt-8 grid gap-4 lg:grid-cols-2">
        <div className="card">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">Status</h2>
          {status.loading ? (
            <Loading />
          ) : status.error ? (
            <ErrorNote error={status.error} />
          ) : status.data ? (
            <dl className="mt-3 grid grid-cols-2 gap-y-2 text-sm">
              <dt className="text-muted">app</dt>
              <dd className="font-mono">{status.data.app} v{status.data.version}</dd>
              <dt className="text-muted">environment</dt>
              <dd className="font-mono">{status.data.environment}</dd>
              <dt className="text-muted">trading mode</dt>
              <dd className="font-mono">{status.data.trading_mode}</dd>
              <dt className="text-muted">agents</dt>
              <dd className="font-mono">{status.data.agent_count}</dd>
              <dt className="text-muted">UTC</dt>
              <dd className="font-mono text-xs">{status.data.server_time_utc.slice(0, 19)}</dd>
              <dt className="text-muted">KST</dt>
              <dd className="font-mono text-xs">{status.data.server_time_kst.slice(0, 19)}</dd>
            </dl>
          ) : null}
        </div>

        <div className="card">
          <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">Health & flags</h2>
          {health.data ? (
            <div className="mt-3 space-y-3 text-sm">
              <div className="flex items-center gap-2">
                <StatusPill ok={health.data.status === "ok"}>{health.data.status.toUpperCase()}</StatusPill>
                <span className="font-mono text-xs text-muted">
                  db {health.data.database.backend} · redis {health.data.redis.backend}
                </span>
              </div>
              <div className="flex flex-wrap gap-2">
                {status.data &&
                  Object.entries(status.data.feature_flags).map(([k, v]) => (
                    <span
                      key={k}
                      className={
                        "rounded-full border px-2.5 py-0.5 font-mono text-xs " +
                        (v
                          ? "border-accent/40 bg-accent/10 text-accent"
                          : "border-border bg-elevated text-muted")
                      }
                    >
                      {k}: {String(v)}
                    </span>
                  ))}
              </div>
            </div>
          ) : (
            <p className="mt-3 text-sm text-muted">—</p>
          )}
        </div>
      </section>

      <section className="mt-6">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">데이터 소스 (Phase 1: 미연결)</h2>
        <div className="mt-3 flex flex-wrap gap-2">
          {status.data?.data_sources.map((d) => (
            <span
              key={d.name}
              className="rounded-md border border-border bg-elevated px-3 py-1 font-mono text-xs text-muted"
            >
              {d.name}: {d.status}
            </span>
          ))}
        </div>
      </section>

      <section className="mt-8">
        <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">감사 로그 (append-only)</h2>
        <div className="mt-3 card p-0">
          {audit.loading ? (
            <div className="p-5">
              <Loading />
            </div>
          ) : audit.error ? (
            <div className="p-5">
              <ErrorNote error={audit.error} />
            </div>
          ) : audit.data && audit.data.items.length > 0 ? (
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted">
                  <th className="px-4 py-2 font-medium">#</th>
                  <th className="px-4 py-2 font-medium">Action</th>
                  <th className="px-4 py-2 font-medium">Entity</th>
                  <th className="px-4 py-2 font-medium">Summary</th>
                  <th className="px-4 py-2 font-medium">Time (UTC)</th>
                </tr>
              </thead>
              <tbody>
                {audit.data.items.map((row) => (
                  <tr key={row.id} className="border-b border-border/50 last:border-0">
                    <td className="px-4 py-2 font-mono text-xs text-muted">{row.id}</td>
                    <td className="px-4 py-2 font-mono text-xs text-accent">{row.action}</td>
                    <td className="px-4 py-2 font-mono text-xs text-muted">{row.entity_type}</td>
                    <td className="px-4 py-2 text-muted">{row.summary}</td>
                    <td className="px-4 py-2 font-mono text-xs text-muted">
                      {row.created_at.replace("T", " ").slice(0, 19)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          ) : (
            <p className="p-5 text-sm text-muted">아직 기록된 감사 로그가 없습니다.</p>
          )}
        </div>
      </section>
    </main>
  );
}
