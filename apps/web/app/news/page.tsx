"use client";

import { useMemo, useState } from "react";

import { api, type NewsItem, type ScrapeResponse } from "@/lib/api";
import { ErrorNote, Loading, PageHeader, useApi } from "@/components/shell";

/** HH:MM in KST from an ISO timestamp. */
function timeKst(iso: string): string {
  try {
    return new Date(iso).toLocaleTimeString("ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
      timeZone: "Asia/Seoul",
    });
  } catch {
    return iso.slice(11, 16);
  }
}

/** Group items by date_kst, preserving (already newest-first) order of first appearance. */
function groupByDate(items: NewsItem[]): [string, NewsItem[]][] {
  const map = new Map<string, NewsItem[]>();
  for (const it of items) {
    const list = map.get(it.date_kst);
    if (list) list.push(it);
    else map.set(it.date_kst, [it]);
  }
  return [...map.entries()];
}

export default function NewsPage() {
  const [activeDate, setActiveDate] = useState<string | null>(null);
  const dates = useApi(() => api.newsDates());
  const news = useApi(() => api.news(activeDate ?? undefined), [activeDate]);

  const [scraping, setScraping] = useState(false);
  const [scrapeResult, setScrapeResult] = useState<ScrapeResponse | null>(null);
  const [scrapeError, setScrapeError] = useState<string | null>(null);

  async function scrape() {
    setScraping(true);
    setScrapeError(null);
    setScrapeResult(null);
    try {
      const res = await api.scrapeNews();
      setScrapeResult(res);
      dates.reload();
      news.reload();
    } catch (e) {
      setScrapeError(String(e));
    } finally {
      setScraping(false);
    }
  }

  const items = news.data?.items ?? [];
  const grouped = useMemo(() => groupByDate(news.data?.items ?? []), [news.data]);
  const retentionDays = dates.data?.dates.length ?? 0;

  return (
    <main className="mx-auto max-w-6xl space-y-8 px-6 py-10">
      <PageHeader
        title="뉴스 스크랩"
        subtitle="일자별 한국 증시 뉴스 · 데일리 브리프 근거 · 오래된 뉴스는 자동 삭제"
      />

      {/* Action bar */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={scrape}
          disabled={scraping}
          className="rounded-xl border border-accent/40 bg-accent/10 px-4 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
        >
          {scraping ? "스크랩 중…" : "뉴스 스크랩 실행"}
        </button>
        {scrapeResult && (
          <span className="num text-xs text-muted">
            +{scrapeResult.added}건 추가 · {scrapeResult.pruned}건 정리 · 수집 {scrapeResult.fetched}건
          </span>
        )}
        {retentionDays > 0 && (
          <span className="num ml-auto text-[11px] text-muted/80">
            최근 {retentionDays}일 보존, 이전 항목 자동 삭제
          </span>
        )}
      </div>

      {scrapeError && <ErrorNote error={scrapeError} />}

      <div className="grid gap-6 lg:grid-cols-[220px_1fr]">
        {/* Date filter rail */}
        <aside className="space-y-2">
          <p className="section-label">일자</p>
          <div className="flex flex-wrap gap-2 lg:flex-col">
            <button
              onClick={() => setActiveDate(null)}
              className={
                "flex items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left text-sm transition-colors " +
                (activeDate === null
                  ? "border-accent/40 bg-accent/10 text-accent"
                  : "border-border bg-surface/60 text-muted hover:bg-elevated/60")
              }
            >
              <span>전체 (최근)</span>
            </button>
            {dates.data?.dates.map((d) => (
              <button
                key={d.date}
                onClick={() => setActiveDate(d.date)}
                className={
                  "flex items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left text-sm transition-colors " +
                  (activeDate === d.date
                    ? "border-accent/40 bg-accent/10 text-accent"
                    : "border-border bg-surface/60 text-foreground/80 hover:bg-elevated/60")
                }
              >
                <span className="num">{d.date}</span>
                <span className="num text-xs text-muted">{d.count}</span>
              </button>
            ))}
          </div>
        </aside>

        {/* Items grouped by date */}
        <section className="space-y-6">
          {news.loading ? (
            <Loading />
          ) : news.error ? (
            <ErrorNote error={news.error} />
          ) : items.length === 0 ? (
            <div className="card flex flex-col items-start gap-3">
              <h2 className="text-lg font-semibold tracking-tight">표시할 뉴스가 없습니다</h2>
              <p className="text-sm text-muted">
                위의 “뉴스 스크랩 실행”을 눌러 일자별 한국 증시 뉴스를 수집하세요.
              </p>
              <button
                onClick={scrape}
                disabled={scraping}
                className="rounded-xl border border-accent/40 bg-accent/10 px-4 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
              >
                {scraping ? "스크랩 중…" : "뉴스 스크랩을 실행하세요"}
              </button>
            </div>
          ) : (
            grouped.map(([date, group]) => (
              <div key={date} className="space-y-3">
                <div className="flex items-center gap-3">
                  <h2 className="num text-sm font-semibold tracking-tight">{date}</h2>
                  <div className="h-px flex-1 bg-border" />
                  <span className="num text-xs text-muted">{group.length}건</span>
                </div>
                <div className="space-y-2">
                  {group.map((it) => (
                    <a
                      key={it.id}
                      href={it.url}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="card card-hover block py-3.5"
                    >
                      <div className="flex items-start justify-between gap-3">
                        <p className="text-sm font-medium leading-snug text-foreground/95">{it.title}</p>
                        <span className="num shrink-0 text-xs text-muted">{timeKst(it.published_at)}</span>
                      </div>
                      <div className="mt-2 flex flex-wrap items-center gap-2">
                        <span className="text-xs text-muted">{it.source}</span>
                        <span className="chip text-muted">{it.topic}</span>
                      </div>
                    </a>
                  ))}
                </div>
              </div>
            ))
          )}
        </section>
      </div>
    </main>
  );
}
