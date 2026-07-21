"use client";

import Link from "next/link";

import { api } from "@/lib/api";
import {
  ErrorNote,
  Loading,
  MockNotice,
  PageHeader,
  StatusPill,
  useApi,
} from "@/components/shell";

export default function DashboardPage() {
  const health = useApi(() => api.health());
  const status = useApi(() => api.systemStatus());
  const audit = useApi(() => api.auditLogs(8));

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <PageHeader title="대시보드" subtitle="시스템 상태 · 에이전트 · 최근 감사 로그" />
      <div className="mt-6">
        <MockNotice />
      </div>

      <section className="mt-8 grid gap-4 sm:grid-cols-3">
        <div className="card">
          <h2 className="section-label">Health</h2>
          {health.loading ? (
            <Loading />
          ) : health.error ? (
            <p className="mt-2 text-sm text-danger">unreachable</p>
          ) : health.data ? (
            <div className="mt-2 space-y-2">
              <StatusPill ok={health.data.status === "ok"}>{health.data.status.toUpperCase()}</StatusPill>
              <p className="font-mono text-xs text-muted">
                db: {health.data.database.backend} · redis: {health.data.redis.backend}
              </p>
            </div>
          ) : null}
        </div>

        <div className="card">
          <h2 className="section-label">Agents</h2>
          {status.data ? (
            <p className="mt-2 font-mono text-3xl font-semibold text-accent">
              {status.data.agent_count}
            </p>
          ) : (
            <p className="mt-2 text-sm text-muted">—</p>
          )}
          <Link href="/agents" className="mt-1 inline-block text-xs text-muted hover:text-accent">
            에이전트 보기 →
          </Link>
        </div>

        <div className="card">
          <h2 className="section-label">Trading mode</h2>
          <p className="mt-2 font-mono text-lg font-semibold">{status.data?.trading_mode ?? "—"}</p>
          <p className="mt-1 text-xs text-danger">live execution not implemented</p>
        </div>
      </section>

      <section className="mt-8">
        <div className="flex items-center justify-between">
          <h2 className="section-label">최근 감사 로그</h2>
          <Link href="/system" className="text-xs text-muted hover:text-accent">
            전체 →
          </Link>
        </div>
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
            <div className="overflow-x-auto">
            <table className="w-full min-w-[32rem] text-sm">
              <thead>
                <tr className="border-b border-border text-left text-xs text-muted">
                  <th className="px-4 py-2 font-medium">Action</th>
                  <th className="px-4 py-2 font-medium">Summary</th>
                  <th className="px-4 py-2 font-medium">Time (UTC)</th>
                </tr>
              </thead>
              <tbody>
                {audit.data.items.map((row) => (
                  <tr key={row.id} className="border-b border-border/50 last:border-0">
                    <td className="px-4 py-2 font-mono text-xs text-accent">{row.action}</td>
                    <td className="px-4 py-2 text-muted">{row.summary}</td>
                    <td className="px-4 py-2 font-mono text-xs text-muted">
                      {new Date(row.created_at).toISOString().replace("T", " ").slice(0, 19)}
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
            </div>
          ) : (
            <p className="p-5 text-sm text-muted">아직 기록된 감사 로그가 없습니다.</p>
          )}
        </div>
      </section>
    </main>
  );
}
