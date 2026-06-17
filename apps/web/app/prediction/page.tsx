"use client";

import { useState } from "react";

import {
  api,
  type AgentPosition,
  type DeskDeliberation,
  type DeskView,
  type OrgDeskInfo,
} from "@/lib/api";
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
  SYNTHESIZE: "수석",
};

const stripAgent = (name: string) => name.replace(/ Agent$/, "");

function DeskCard({ desk, view }: { desk: OrgDeskInfo; view?: DeskView }) {
  return (
    <div className="card">
      <div className="flex items-start justify-between gap-2">
        <div>
          <p className="text-sm font-semibold">{desk.title}</p>
          <p className="num mt-0.5 text-[11px] text-muted">
            리드 {desk.lead} · {desk.members.length}명 · 가중치 {(desk.weight * 100).toFixed(0)}%
          </p>
        </div>
        {view && desk.key !== "CHIEF" && <DirectionPill direction={view.lean} />}
      </div>
      {view && desk.key !== "CHIEF" && (
        <div className="mt-2">
          <LeanBar score={view.score} />
          <p className="num mt-1 text-[11px] text-muted">
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
            {stripAgent(m)}
          </span>
        ))}
      </div>
      {view?.top_drivers?.[0] && (
        <p className="mt-2 text-[11px] leading-snug text-muted">“{view.top_drivers[0]}”</p>
      )}
    </div>
  );
}

function PositionRow({ pos, dissenting }: { pos: AgentPosition; dissenting: boolean }) {
  return (
    <div
      className={
        "flex flex-wrap items-center gap-2 rounded-xl border px-3 py-2 " +
        (dissenting ? "border-warning/40 bg-warning/5" : "border-border/60 bg-elevated/40")
      }
    >
      <span className="text-sm font-medium">{stripAgent(pos.agent)}</span>
      {pos.is_lead && (
        <span className="chip border-accent/40 bg-accent/10 text-accent">리드</span>
      )}
      {dissenting && (
        <span className="chip border-warning/40 bg-warning/10 text-warning">이견</span>
      )}
      <DirectionPill direction={pos.direction} />
      <span className="num text-xs text-muted">{(pos.confidence * 100).toFixed(0)}%</span>
      {pos.note && <span className="w-full text-xs text-muted sm:w-auto sm:flex-1">{pos.note}</span>}
    </div>
  );
}

function DeskDeliberationCard({ d }: { d: DeskDeliberation }) {
  const dissentSet = new Set(d.dissent);
  return (
    <div className="card">
      <div className="flex flex-wrap items-center gap-3">
        <h3 className="text-base font-semibold tracking-tight">{d.title}</h3>
        <DirectionPill direction={d.consensus} />
        <span className="num text-xs text-muted">합의도 {(d.agreement * 100).toFixed(0)}%</span>
      </div>
      {d.lead_note && <p className="mt-2 text-sm text-muted">{d.lead_note}</p>}
      <div className="mt-3 space-y-2">
        {d.positions.map((pos) => (
          <PositionRow key={pos.agent} pos={pos} dissenting={dissentSet.has(pos.agent)} />
        ))}
      </div>
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
  const delib = p?.deliberation ?? null;

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-10">
      <PageHeader
        title="예측 · 리서치 조직도"
        subtitle="21에이전트 → 5데스크 → 수석 계층 합성. 데스크 신호, 에이전트 논의 과정, 종목 스탠스, 시나리오까지 한눈에."
      />

      {/* Prediction summary */}
      <div className="flex flex-wrap items-end gap-x-8 gap-y-3">
        {p && (
          <>
            <div>
              <p className="section-label">예측 대상</p>
              <p className="mt-1 text-sm font-medium">{p.subject}</p>
            </div>
            <div>
              <p className="section-label">기간</p>
              <p className="num mt-1 text-sm font-medium">{p.horizon_label}</p>
            </div>
            <div className="flex flex-wrap items-center gap-2 pb-0.5">
              <DirectionPill direction={p.direction} big />
              <RegimeBadge regime={p.regime} />
              <span className="num text-xs text-muted">확신 {(p.confidence * 100).toFixed(0)}%</span>
            </div>
          </>
        )}
        <button
          onClick={generate}
          disabled={generating}
          className="ml-auto rounded-xl border border-accent/40 bg-accent/10 px-4 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
        >
          {generating ? "생성 중…" : "예측 생성/새로고침"}
        </button>
      </div>

      {org.loading ? (
        <Loading />
      ) : org.error ? (
        <ErrorNote error={org.error} />
      ) : (
        <>
          {/* Hierarchical org chart: SYNTHESIZE -> ANALYZE -> VALIDATE */}
          <section className="space-y-4">
            <h2 className="section-label">리서치 조직도</h2>
            {(["SYNTHESIZE", "ANALYZE", "VALIDATE"] as const).map((t) => (
              <div key={t}>
                <div className="mb-2 flex items-center gap-2">
                  <span className="num rounded bg-elevated px-2 py-0.5 text-[10px] uppercase tracking-wider text-muted">
                    {TIER_KO[t]} 티어
                  </span>
                  <div className="h-px flex-1 bg-border" />
                </div>
                <div className={t === "ANALYZE" ? "grid gap-3 sm:grid-cols-2 lg:grid-cols-4" : "grid gap-3"}>
                  {tier(t).map((d) => (
                    <DeskCard key={d.key} desk={d} view={viewByKey.get(d.key)} />
                  ))}
                </div>
              </div>
            ))}
          </section>

          {!p ? (
            <p className="text-sm text-muted">
              아직 예측이 없습니다. 위 버튼으로 생성하면 데스크별 신호와 논의 과정, 종목 스탠스가 채워집니다.
            </p>
          ) : (
            <>
              {/* Deliberation: how the agents debated and reconciled */}
              {delib && (
                <section className="space-y-4">
                  <div>
                    <h2 className="text-2xl font-semibold tracking-tight">에이전트 논의 과정</h2>
                    <p className="mt-1 text-sm text-muted">
                      각 데스크 내부의 합의·이견과 수석의 최종 조정 과정입니다.
                    </p>
                  </div>

                  <div className="space-y-4">
                    {delib.desks.map((d) => (
                      <DeskDeliberationCard key={d.desk} d={d} />
                    ))}
                  </div>

                  {/* Chief reconciliation */}
                  <div className="card border-accent/30">
                    <div className="flex flex-wrap items-center gap-3">
                      <h3 className="text-base font-semibold tracking-tight">수석 종합 (Chief)</h3>
                      <DirectionPill direction={delib.chief.overall} big />
                    </div>
                    {delib.chief.note && <p className="mt-2 text-sm leading-7 text-foreground/90">{delib.chief.note}</p>}
                    <div className="mt-4 grid gap-4 sm:grid-cols-2">
                      <div className="rounded-xl border border-up/30 bg-up/5 p-3">
                        <p className="text-xs font-semibold text-up">지지 데스크</p>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {delib.chief.aligned_desks.length ? (
                            delib.chief.aligned_desks.map((k) => (
                              <span key={k} className="chip text-foreground/80">
                                {k}
                              </span>
                            ))
                          ) : (
                            <span className="text-xs text-muted">없음</span>
                          )}
                        </div>
                      </div>
                      <div className="rounded-xl border border-warning/30 bg-warning/5 p-3">
                        <p className="text-xs font-semibold text-warning">이견 데스크</p>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {delib.chief.conflicted_desks.length ? (
                            delib.chief.conflicted_desks.map((k) => (
                              <span key={k} className="chip text-foreground/80">
                                {k}
                              </span>
                            ))
                          ) : (
                            <span className="text-xs text-muted">없음</span>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                </section>
              )}

              {/* Instrument stances */}
              <section>
                <h2 className="section-label">종목 스탠스 (롱 · 레버리지 · 인버스 · 곱버스)</h2>
                <div className="card mt-3 p-0">
                  <table className="w-full text-sm">
                    <thead>
                      <tr className="border-b border-border text-left text-xs text-muted">
                        <th className="px-4 py-2.5 font-medium">종목</th>
                        <th className="px-4 py-2.5 font-medium">유형</th>
                        <th className="px-4 py-2.5 font-medium">스탠스</th>
                        <th className="px-4 py-2.5 font-medium">근거 / 위험</th>
                      </tr>
                    </thead>
                    <tbody>
                      {p.instrument_stances.map((s) => (
                        <tr key={s.symbol} className="border-b border-border/50 last:border-0">
                          <td className="px-4 py-3">
                            <span className="text-sm">{s.name}</span>
                            <span className="num ml-2 text-[11px] text-muted">{s.symbol}</span>
                          </td>
                          <td className="num px-4 py-3 text-xs text-muted">{KIND_KO[s.kind] ?? s.kind}</td>
                          <td className="px-4 py-3">
                            <StanceBadge label={s.label} />
                          </td>
                          <td className="px-4 py-3 text-xs text-muted">
                            {s.rationale}
                            {s.risk_note && <span className="mt-1 block text-warning">⚠ {s.risk_note}</span>}
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              </section>

              {/* Scenarios */}
              <section>
                <h2 className="section-label">시나리오</h2>
                <div className="mt-3 grid gap-3 sm:grid-cols-3">
                  {p.scenarios.map((s) => (
                    <div key={s.name} className="card">
                      <div className="flex items-baseline justify-between">
                        <span className="text-sm font-medium">{s.name}</span>
                        <span className="num text-lg font-semibold text-accent">
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
              <section className="card">
                <h2 className="section-label">데일리 브리프</h2>
                <p className="mt-3 whitespace-pre-line leading-7 text-foreground/90">{p.brief}</p>
              </section>
            </>
          )}
        </>
      )}
    </main>
  );
}
