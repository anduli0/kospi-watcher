"use client";

import { useState } from "react";

import { api, type DeskView, type OrgDeskInfo } from "@/lib/api";
import {
  DirectionPill,
  ErrorNote,
  KIND_KO,
  LeanBar,
  Loading,
  PageHeader,
  RegimeBadge,
  StanceBadge,
  useApi,
} from "@/components/shell";

const TIER_KO: Record<string, string> = {
  VALIDATE: "검증",
  ANALYZE: "분석",
  SYNTHESIZE: "합성",
};

function DeskCard({ desk, view }: { desk: OrgDeskInfo; view?: DeskView }) {
  return (
    <div className="card">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold">{desk.title}</p>
          <p className="mt-0.5 font-mono text-[11px] text-muted">
            리드 {desk.lead} · {desk.members.length}명 · 가중치 {(desk.weight * 100).toFixed(0)}%
          </p>
        </div>
        {view && desk.key !== "CHIEF" && <DirectionPill direction={view.lean} />}
      </div>
      {view && desk.key !== "CHIEF" && (
        <div className="mt-2">
          <LeanBar score={view.score} />
          <p className="mt-1 font-mono text-[11px] text-muted">
            score {view.score.toFixed(2)} · 확신 {(view.conviction * 100).toFixed(0)}% · 응답{" "}
            {view.responded}/{view.member_count}
          </p>
        </div>
      )}
      <div className="mt-2 flex flex-wrap gap-1">
        {desk.members.map((m) => (
          <span
            key={m}
            className={
              "rounded border border-border bg-elevated px-1.5 py-0.5 text-[10px] " +
              (m === desk.lead ? "text-accent" : "text-muted")
            }
          >
            {m.replace(/ Agent$/, "")}
          </span>
        ))}
      </div>
      {view?.top_drivers?.[0] && (
        <p className="mt-2 text-[11px] leading-snug text-muted">“{view.top_drivers[0]}”</p>
      )}
    </div>
  );
}

export default function PredictionPage() {
  const org = useApi(() => api.agentsOrg());
  const pred = useApi(() => api.latestPrediction());
  const [generating, setGenerating] = useState(false);

  async function generate() {
    setGenerating(true);
    try {
      await api.runPrediction(["069500", "114800", "252670"]);
      pred.reload();
    } finally {
      setGenerating(false);
    }
  }

  const desks = org.data?.desks ?? [];
  const viewByKey = new Map((pred.data?.desk_views ?? []).map((v) => [v.desk, v]));
  const tier = (t: string) => desks.filter((d) => d.tier === t);
  const p = pred.data;

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <PageHeader title="예측 · 리서치 조직도" subtitle="21에이전트 → 5데스크 → 수석 계층 합성" />

      <div className="mt-6 flex flex-wrap items-center gap-3">
        <button
          onClick={generate}
          disabled={generating}
          className="rounded-md border border-accent/40 bg-accent/10 px-4 py-2 font-mono text-sm text-accent hover:bg-accent/20 disabled:opacity-40"
        >
          {generating ? "생성 중…" : "예측 생성/새로고침"}
        </button>
        {p && (
          <div className="flex flex-wrap items-center gap-2">
            <DirectionPill direction={p.direction} big />
            <RegimeBadge regime={p.regime} />
            <span className="font-mono text-xs text-muted">
              확신 {(p.confidence * 100).toFixed(0)}% · {p.generated_by}
            </span>
          </div>
        )}
      </div>

      {org.loading ? (
        <div className="mt-8">
          <Loading />
        </div>
      ) : org.error ? (
        <div className="mt-8">
          <ErrorNote error={org.error} />
        </div>
      ) : (
        <>
          {/* Hierarchical org chart: SYNTHESIZE -> ANALYZE -> VALIDATE */}
          <section className="mt-8 space-y-4">
            {(["SYNTHESIZE", "ANALYZE", "VALIDATE"] as const).map((t) => (
              <div key={t}>
                <div className="mb-2 flex items-center gap-2">
                  <span className="rounded bg-elevated px-2 py-0.5 font-mono text-[10px] uppercase tracking-wider text-muted">
                    {TIER_KO[t]} 티어
                  </span>
                  <div className="h-px flex-1 bg-border" />
                </div>
                <div
                  className={
                    t === "ANALYZE"
                      ? "grid gap-3 sm:grid-cols-2 lg:grid-cols-4"
                      : "grid gap-3"
                  }
                >
                  {tier(t).map((d) => (
                    <DeskCard key={d.key} desk={d} view={viewByKey.get(d.key)} />
                  ))}
                </div>
              </div>
            ))}
          </section>

          {!p ? (
            <p className="mt-6 text-sm text-muted">
              아직 예측이 없습니다. 위 버튼으로 생성하면 데스크별 신호와 종목 스탠스가 채워집니다.
            </p>
          ) : (
            <>
              {/* Instrument stances */}
              <section className="mt-8">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">
                  종목 스탠스 (롱 · 레버리지 · 인버스 · 곱버스)
                </h2>
                <div className="mt-3 card p-0">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-xs text-muted">
                        <th className="px-4 py-2 font-medium">종목</th>
                        <th className="px-4 py-2 font-medium">유형</th>
                        <th className="px-4 py-2 font-medium">스탠스</th>
                        <th className="px-4 py-2 font-medium">근거 / 위험</th>
                      </tr>
                    </thead>
                    <tbody>
                      {p.instrument_stances.map((s) => (
                        <tr key={s.symbol} className="border-b border-border/50 last:border-0">
                          <td className="px-4 py-2">
                            <span className="text-sm">{s.name}</span>
                            <span className="ml-2 font-mono text-[11px] text-muted">{s.symbol}</span>
                          </td>
                          <td className="px-4 py-2 font-mono text-xs text-muted">
                            {KIND_KO[s.kind] ?? s.kind}
                          </td>
                          <td className="px-4 py-2">
                            <StanceBadge label={s.label} />
                          </td>
                          <td className="px-4 py-2 text-xs text-muted">
                            {s.rationale}
                            {s.risk_note && (
                              <span className="mt-1 block text-warning">⚠ {s.risk_note}</span>
                            )}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* Scenarios */}
              <section className="mt-8">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">시나리오</h2>
                <div className="mt-3 grid gap-3 sm:grid-cols-3">
                  {p.scenarios.map((s) => (
                    <div key={s.name} className="card">
                      <div className="flex items-baseline justify-between">
                        <span className="text-sm font-medium">{s.name}</span>
                        <span className="font-mono text-lg font-semibold text-accent">
                          {(s.probability * 100).toFixed(0)}%
                        </span>
                      </div>
                      <p className="mt-2 text-xs text-muted">{s.thesis}</p>
                      <ul className="mt-2 space-y-1">
                        {s.triggers.map((t) => (
                          <li key={t} className="text-[11px] text-muted">
                            · {t}
                          </li>
                        ))}
                      </ul>
                    </div>
                  ))}
                </div>
              </section>

              {/* Brief */}
              <section className="mt-8 card">
                <h2 className="text-xs font-semibold uppercase tracking-wider text-muted">데일리 브리프</h2>
                <p className="mt-3 leading-7 text-foreground/90">{p.brief}</p>
              </section>
            </>
          )}
        </>
      )}
    </main>
  );
}
