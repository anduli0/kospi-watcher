"use client";

import { useState } from "react";

import { api, type AgentRun } from "@/lib/api";
import { ErrorNote, Loading, MockNotice, PageHeader, StatusPill, useApi } from "@/components/shell";

export default function AgentsPage() {
  const agents = useApi(() => api.listAgents());
  const [run, setRun] = useState<AgentRun | null>(null);
  const [running, setRunning] = useState<string | null>(null);
  const [runError, setRunError] = useState<string | null>(null);

  async function mockRun(name: string) {
    setRunning(name);
    setRunError(null);
    setRun(null);
    try {
      setRun(await api.mockRun(name, ["069500", "102110"]));
    } catch (e) {
      setRunError(String(e));
    } finally {
      setRunning(null);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <PageHeader title="에이전트" subtitle="21개 분석 에이전트 — 분석만 수행, 주문 권한 없음" />
      <div className="mt-6">
        <MockNotice />
      </div>

      {agents.loading ? (
        <div className="mt-8">
          <Loading />
        </div>
      ) : agents.error ? (
        <div className="mt-8">
          <ErrorNote error={agents.error} />
        </div>
      ) : agents.data ? (
        <>
          <p className="mt-8 text-xs text-muted">
            총 <span className="font-mono text-accent">{agents.data.count}</span>개 에이전트
          </p>
          <div className="mt-3 grid gap-3 sm:grid-cols-2">
            {agents.data.agents.map((a) => (
              <div key={a.name} className="card">
                <div className="flex items-start justify-between gap-3">
                  <div>
                    <p className="text-sm font-medium">{a.name}</p>
                    <p className="mt-0.5 font-mono text-xs text-muted">
                      {a.category} · v{a.version}
                    </p>
                  </div>
                  <button
                    onClick={() => mockRun(a.name)}
                    disabled={running !== null}
                    className="shrink-0 rounded-md border border-accent/40 bg-accent/10 px-2.5 py-1 font-mono text-xs text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
                  >
                    {running === a.name ? "…" : "mock-run"}
                  </button>
                </div>
                <p className="mt-2 text-xs text-muted">{a.summary}</p>
              </div>
            ))}
          </div>
        </>
      ) : null}

      {(run || runError) && (
        <section className="mt-8">
          <h2 className="section-label">Mock run 결과</h2>
          <div className="mt-3 card">
            {runError ? (
              <p className="font-mono text-xs text-danger break-all">{runError}</p>
            ) : run ? (
              <div className="space-y-3">
                <div className="flex items-center gap-2">
                  <StatusPill ok={run.status === "SUCCEEDED"}>{run.status}</StatusPill>
                  <span className="font-mono text-sm">{run.agent_name}</span>
                  <span className="font-mono text-xs text-muted">{run.model_name}</span>
                </div>
                {run.findings.map((f, i) => (
                  <div key={i} className="rounded-md border border-border bg-elevated p-3 text-sm">
                    <div className="flex flex-wrap items-center gap-2 font-mono text-xs">
                      <span className="text-accent">{f.direction}</span>
                      <span className="text-muted">impact {f.impact}</span>
                      <span className="text-muted">horizon {f.horizon}</span>
                      <span className="text-muted">conf {(f.confidence * 100).toFixed(0)}%</span>
                      <span className="text-muted">data {f.data_quality}</span>
                    </div>
                    <p className="mt-2">{f.thesis}</p>
                    {f.invalidation_conditions.length > 0 && (
                      <p className="mt-2 text-xs text-warning">
                        무효화 조건: {f.invalidation_conditions.join("; ")}
                      </p>
                    )}
                  </div>
                ))}
              </div>
            ) : null}
          </div>
        </section>
      )}
    </main>
  );
}
