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
  DIRECTION_KO,
  DirectionPill,
  ErrorNote,
  KIND_KO,
  LeanBar,
  Loading,
  MonetaryPolicyCard,
  RegimeBadge,
  StanceBadge,
  TrendSignalCard,
  dirText,
  useApi,
} from "@/components/shell";

const TIER_KO: Record<string, string> = {
  VALIDATE: "검증",
  ANALYZE: "분석",
  SYNTHESIZE: "수석",
};

const stripAgent = (name: string) => name.replace(/ Agent$/, "");

/** A numbered, consistent heading so the page reads top-to-bottom in order. */
function SectionHeading({
  step,
  title,
  desc,
  right,
}: {
  step: number;
  title: string;
  desc?: string;
  right?: React.ReactNode;
}) {
  return (
    <div className="flex flex-wrap items-start justify-between gap-x-4 gap-y-1">
      <div className="flex items-baseline gap-2.5">
        <span className="num grid h-6 w-6 flex-none place-items-center rounded-full border border-accent/40 bg-accent/10 text-xs font-semibold text-accent">
          {step}
        </span>
        <div>
          <h2 className="text-lg font-semibold tracking-tight">{title}</h2>
          {desc && <p className="mt-0.5 text-sm leading-relaxed text-muted">{desc}</p>}
        </div>
      </div>
      {right}
    </div>
  );
}

/** One desk's signal — the digestible middle layer between the 21 agents and the house view. */
function DeskSignalCard({
  desk,
  view,
  houseDirection,
}: {
  desk: OrgDeskInfo;
  view?: DeskView;
  houseDirection?: string;
}) {
  const aligned = view && houseDirection && view.lean === houseDirection;
  const dissent =
    view && houseDirection && view.lean !== "NEUTRAL" && view.lean !== houseDirection;
  return (
    <div className="card p-4">
      <div className="flex items-start justify-between gap-2">
        <div className="min-w-0">
          <div className="flex items-center gap-1.5">
            <span className="num rounded bg-elevated px-1.5 py-0.5 text-[10px] font-medium tracking-wider text-muted">
              {TIER_KO[desk.tier] ?? desk.tier}
            </span>
            <p className="truncate text-sm font-semibold">{desk.title}</p>
          </div>
          <p className="num mt-1 text-[11px] text-muted">
            리드 {stripAgent(desk.lead)} · {desk.members.length}명 · 영향력 {(desk.weight * 100).toFixed(0)}%
          </p>
        </div>
        {view && <DirectionPill direction={view.lean} />}
      </div>

      {view ? (
        <>
          <div className="mt-3">
            <LeanBar score={view.score} />
            <div className="mt-1.5 flex items-center justify-between">
              <span className="num text-[11px] text-muted">확신 {(view.conviction * 100).toFixed(0)}%</span>
              {aligned && (
                <span className="text-[10px] font-semibold text-up">수석 결론과 일치</span>
              )}
              {dissent && (
                <span className="text-[10px] font-semibold text-warning">수석과 이견</span>
              )}
              {view.lean === "NEUTRAL" && (
                <span className="text-[10px] font-semibold text-muted">중립</span>
              )}
            </div>
          </div>
          {view.top_drivers?.[0] && (
            <p className="mt-2.5 border-t border-border/50 pt-2.5 text-[11px] leading-snug text-muted">
              “{view.top_drivers[0]}”
            </p>
          )}
        </>
      ) : (
        <p className="mt-3 text-[11px] text-muted">예측 생성 후 신호가 채워집니다.</p>
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
      {pos.is_lead && <span className="chip border-accent/40 bg-accent/10 text-accent">리드</span>}
      {dissenting && <span className="chip border-warning/40 bg-warning/10 text-warning">이견</span>}
      <DirectionPill direction={pos.direction} />
      <span className="num text-xs text-muted">{(pos.confidence * 100).toFixed(0)}%</span>
      {pos.note && <span className="w-full text-xs text-muted sm:w-auto sm:flex-1">{pos.note}</span>}
    </div>
  );
}

function DeskDeliberationCard({ d }: { d: DeskDeliberation }) {
  const dissentSet = new Set(d.dissent);
  return (
    <div className="rounded-xl border border-border/70 bg-surface/60 p-4">
      <div className="flex flex-wrap items-center gap-3">
        <h4 className="text-sm font-semibold tracking-tight">{d.title}</h4>
        <DirectionPill direction={d.consensus} />
        <span className="num text-xs text-muted">내부 합의도 {(d.agreement * 100).toFixed(0)}%</span>
      </div>
      {d.lead_note && (
        <p className="mt-2 text-sm leading-relaxed text-muted">
          <span className="text-foreground/70">리드 정리 — </span>
          {d.lead_note}
        </p>
      )}
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
  const analysisDesks = desks.filter((d) => d.key !== "CHIEF");
  const viewByKey = new Map((pred.data?.desk_views ?? []).map((v) => [v.desk, v]));
  const p = pred.data;
  const delib = p?.deliberation ?? null;
  const connError = pred.error?.startsWith("API unreachable") ?? false;
  const scenarios = p ? [...p.scenarios].sort((a, b) => b.probability - a.probability) : [];

  const refreshBtn = (
    <button
      onClick={generate}
      disabled={generating}
      className="rounded-xl border border-accent/40 bg-accent/10 px-3.5 py-1.5 text-xs font-semibold text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
    >
      {generating ? "생성 중…" : "예측 새로고침"}
    </button>
  );

  return (
    <main className="mx-auto max-w-5xl space-y-10 px-6 py-10">
      {/* Context strip */}
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="section-label">예측 리포트 · 코스피200 지수</p>
        <span className="chip border-accent2/30 bg-accent2/10 text-accent2">매일 08:00 자동 갱신</span>
      </div>

      {/* ── Hero: the answer, first and biggest ───────────────────────── */}
      {pred.loading ? (
        <Loading />
      ) : connError ? (
        <section className="card">
          <ErrorNote error={pred.error!} retrying={pred.retrying} onRetry={pred.reload} />
        </section>
      ) : !p ? (
        <section className="card flex flex-col items-start gap-3">
          <h1 className="text-2xl font-semibold tracking-tight">아직 생성된 예측이 없습니다</h1>
          <p className="max-w-2xl text-sm leading-relaxed text-muted">
            21개 분석 에이전트를 5개 데스크로 모아 수석이 종합하면, 코스피 방향·국면·종목
            포지션과 그 근거가 한 화면에 채워집니다.
          </p>
          <button
            onClick={generate}
            disabled={generating}
            className="rounded-xl border border-accent/40 bg-accent/10 px-4 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
          >
            {generating ? "생성 중…" : "오늘의 예측 생성"}
          </button>
        </section>
      ) : (
        <section className="card">
          <div className="flex flex-wrap items-start justify-between gap-3">
            <div>
              <p className="section-label">예측 대상</p>
              <p className="mt-1 text-sm font-medium">{p.subject}</p>
              <p className="num mt-0.5 text-xs text-muted">전망 기간 · {p.horizon_label}</p>
            </div>
            {refreshBtn}
          </div>

          {/* The verdict — large and unmissable */}
          <div className="mt-6 flex flex-wrap items-end gap-x-8 gap-y-4">
            <div>
              <p className="text-xs text-muted">코스피200 방향</p>
              <span className={`text-6xl font-bold leading-none tracking-tight ${dirText(p.direction)}`}>
                {DIRECTION_KO[p.direction]}
              </span>
            </div>
            <div className="pb-1">
              <p className="text-xs text-muted">확신도</p>
              <p className="num text-3xl font-semibold">{(p.confidence * 100).toFixed(0)}%</p>
            </div>
            <div className="pb-1.5">
              <RegimeBadge regime={p.regime} />
            </div>
          </div>

          <p className="mt-5 text-lg font-medium leading-snug">{p.headline}</p>

          {/* Plain-language legend so the numbers above aren't jargon */}
          <p className="mt-3 text-xs leading-relaxed text-muted">
            <b className="font-semibold text-foreground/80">방향</b>은 향후 {p.horizon_label}{" "}
            동안 예상되는 흐름, <b className="font-semibold text-foreground/80">확신도</b>는 모델이
            그 방향에 두는 신뢰 수준, <b className="font-semibold text-foreground/80">국면</b>은
            현재 시장 레짐입니다.
          </p>

          <p className="num mt-4 border-t border-border/50 pt-3 text-[11px] text-muted/80">
            분석 {p.generated_by} · {p.agent_count}개 에이전트 · 기준{" "}
            {p.as_of.slice(0, 16).replace("T", " ")}
          </p>
        </section>
      )}

      {/* Everything below depends on a prediction existing */}
      {p && (
        <>
          {/* ── 1. Key drivers ───────────────────────────────────────── */}
          {(p.trend_signal || p.monetary_policy) && (
            <section className="space-y-3">
              <SectionHeading
                step={1}
                title="핵심 근거"
                desc="방향을 좌우한 두 가지 결정적 입력. 가격 추세가 주 앵커, 통화정책이 위험 기울기를 더합니다."
              />
              <div className="grid gap-3 lg:grid-cols-2">
                {p.trend_signal && <TrendSignalCard ts={p.trend_signal} />}
                {p.monetary_policy && <MonetaryPolicyCard mp={p.monetary_policy} />}
              </div>
            </section>
          )}

          {/* ── 2. The narrative report ──────────────────────────────── */}
          <section className="space-y-3">
            <SectionHeading
              step={2}
              title="예측 리포트"
              desc="위 결론을 한 편의 글로 풀어낸 종합 설명입니다."
            />
            <div className="card">
              <p className="whitespace-pre-line leading-7 text-foreground/90">{p.brief}</p>
              {p.news_refs.length > 0 && (
                <div className="mt-4 border-t border-border/60 pt-4">
                  <p className="section-label">반영한 뉴스</p>
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {p.news_refs.map((ref) => (
                      <span key={ref} className="chip text-muted">
                        {ref}
                      </span>
                    ))}
                  </div>
                </div>
              )}
            </div>
          </section>

          {/* ── 3. Instrument positioning ────────────────────────────── */}
          <section className="space-y-3">
            <SectionHeading
              step={3}
              title="종목 포지셔닝"
              desc="지수 전망을 ETF별 포지션으로 옮긴 것입니다. 비중확대=적극, 중립=관망, 비중축소·회피=피하기. 참고용이며 주문 권한은 없습니다."
            />
            <div className="card p-0">
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
                    <tr key={s.symbol} className="border-b border-border/50 align-top last:border-0">
                      <td className="px-4 py-3">
                        <span className="text-sm font-medium">{s.name}</span>
                        <span className="num ml-2 text-[11px] text-muted">{s.symbol}</span>
                      </td>
                      <td className="num px-4 py-3 text-xs text-muted">{KIND_KO[s.kind] ?? s.kind}</td>
                      <td className="px-4 py-3">
                        <StanceBadge label={s.label} />
                      </td>
                      <td className="px-4 py-3 text-xs leading-relaxed text-muted">
                        {s.rationale}
                        {s.risk_note && <span className="mt-1 block text-warning">⚠ {s.risk_note}</span>}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </section>

          {/* ── 4. Scenarios ─────────────────────────────────────────── */}
          <section className="space-y-3">
            <SectionHeading
              step={4}
              title="시나리오"
              desc="앞으로 벌어질 수 있는 전개를 발생 확률이 높은 순서로 정리했습니다."
            />
            <div className="grid gap-3 sm:grid-cols-3">
              {scenarios.map((s) => {
                const pct = Math.round(s.probability * 100);
                return (
                  <div key={s.name} className="card flex flex-col">
                    <div className="flex items-baseline justify-between gap-2">
                      <span className="text-sm font-semibold">{s.name}</span>
                      <span className="num text-xl font-bold text-accent">{pct}%</span>
                    </div>
                    <div className="mt-2 h-1.5 w-full overflow-hidden rounded-full bg-elevated">
                      <div className="h-full rounded-full bg-accent" style={{ width: `${pct}%` }} />
                    </div>
                    <p className="mt-3 text-xs leading-relaxed text-muted">{s.thesis}</p>
                    {s.triggers.length > 0 && (
                      <div className="mt-3 border-t border-border/50 pt-2.5">
                        <p className="text-[10px] font-semibold uppercase tracking-wider text-muted/70">
                          촉발 조건
                        </p>
                        <ul className="mt-1 space-y-1">
                          {s.triggers.map((t) => (
                            <li key={t} className="text-[11px] leading-snug text-muted">
                              · {t}
                            </li>
                          ))}
                        </ul>
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          </section>

          {/* ── 5. How it was decided (process — collapsible depth) ───── */}
          <section className="space-y-3">
            <SectionHeading
              step={5}
              title="분석 과정"
              desc="21개 에이전트가 5개 데스크로 모여 수석이 최종 조율하기까지의 흐름입니다."
            />

            {org.loading ? (
              <Loading />
            ) : org.error ? (
              <ErrorNote error={org.error} retrying={org.retrying} onRetry={org.reload} />
            ) : (
              <>
                {/* Desk-level signals: the digestible middle layer */}
                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
                  {analysisDesks.map((d) => (
                    <DeskSignalCard
                      key={d.key}
                      desk={d}
                      view={viewByKey.get(d.key)}
                      houseDirection={p.direction}
                    />
                  ))}
                </div>

                {/* Full agent-by-agent thread, tucked away to avoid clutter */}
                {delib && (
                  <details className="group rounded-2xl border border-border bg-surface/60 p-4 backdrop-blur-sm">
                    <summary className="flex cursor-pointer list-none items-center justify-between gap-2 [&::-webkit-details-marker]:hidden">
                      <span className="text-sm font-semibold">
                        에이전트별 논의 전체 보기 · 데스크 내부 합의와 이견
                      </span>
                      <span className="text-muted transition-transform group-open:rotate-180" aria-hidden>
                        ▾
                      </span>
                    </summary>

                    <div className="mt-4 space-y-3">
                      {delib.desks.map((d) => (
                        <DeskDeliberationCard key={d.desk} d={d} />
                      ))}

                      {/* Chief reconciliation */}
                      <div className="rounded-xl border border-accent/30 bg-accent/5 p-4">
                        <div className="flex flex-wrap items-center gap-3">
                          <h4 className="text-sm font-semibold tracking-tight">수석 종합 (Chief)</h4>
                          <DirectionPill direction={delib.chief.overall} big />
                        </div>
                        {delib.chief.note && (
                          <p className="mt-2 text-sm leading-7 text-foreground/90">{delib.chief.note}</p>
                        )}
                        <div className="mt-4 grid gap-3 sm:grid-cols-2">
                          <div className="rounded-xl border border-up/30 bg-up/5 p-3">
                            <p className="text-xs font-semibold text-up">결론을 지지한 데스크</p>
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
                            <p className="text-xs font-semibold text-warning">이견을 낸 데스크</p>
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
                    </div>
                  </details>
                )}
              </>
            )}
          </section>
        </>
      )}
    </main>
  );
}
