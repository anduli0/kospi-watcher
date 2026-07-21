"use client";

import { useState } from "react";

import { api, type OrderProposalInput, type RiskDecision } from "@/lib/api";
import { MockNotice, PageHeader, StatusPill } from "@/components/shell";

const ALLOWED = [
  { symbol: "069500", name: "KODEX 200" },
  { symbol: "102110", name: "TIGER 200" },
];

export default function RiskPage() {
  const [symbol, setSymbol] = useState("069500");
  const [quantity, setQuantity] = useState(10);
  const [limitPrice, setLimitPrice] = useState("35000");
  const [marketOpen, setMarketOpen] = useState(true);
  const [decision, setDecision] = useState<RiskDecision | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  async function evaluate() {
    setBusy(true);
    setError(null);
    setDecision(null);
    const proposal: OrderProposalInput = {
      symbol,
      instrument_type: "ETF",
      side: "BUY",
      order_type: "LIMIT",
      quantity,
      limit_price: limitPrice,
      strategy_id: "baseline-momentum-v0",
      strategy_version: "0.1.0",
      idempotency_key: `web-${symbol}-${Date.now()}`,
    };
    try {
      setDecision(await api.evaluateRisk(proposal, marketOpen, limitPrice));
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <PageHeader
        title="리스크 엔진"
        subtitle="결정론적 deny-by-default 리스크 평가 — 주문은 실행되지 않습니다"
      />
      <div className="mt-6">
        <MockNotice />
      </div>

      <section className="mt-8 grid gap-6 lg:grid-cols-[320px_1fr]">
        <div className="card space-y-4">
          <h2 className="section-label">주문 제안 (모의)</h2>
          <label className="block text-sm">
            <span className="text-muted">종목</span>
            <select
              value={symbol}
              onChange={(e) => setSymbol(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 font-mono text-sm"
            >
              {ALLOWED.map((a) => (
                <option key={a.symbol} value={a.symbol}>
                  {a.symbol} · {a.name}
                </option>
              ))}
              <option value="005930">005930 · 삼성전자 (미허용 — 거부 테스트)</option>
            </select>
          </label>
          <label className="block text-sm">
            <span className="text-muted">수량</span>
            <input
              type="number"
              min={1}
              value={quantity}
              onChange={(e) => setQuantity(Number(e.target.value))}
              className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 font-mono text-sm"
            />
          </label>
          <label className="block text-sm">
            <span className="text-muted">지정가 (KRW, Decimal)</span>
            <input
              value={limitPrice}
              onChange={(e) => setLimitPrice(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 font-mono text-sm"
            />
          </label>
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={marketOpen}
              onChange={(e) => setMarketOpen(e.target.checked)}
            />
            <span className="text-muted">장 개장 중(market_open)</span>
          </label>
          <button
            onClick={evaluate}
            disabled={busy}
            className="w-full rounded-xl border border-accent/40 bg-accent/10 px-3 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
          >
            {busy ? "평가 중…" : "리스크 평가"}
          </button>
        </div>

        <div className="card">
          <h2 className="section-label">결정</h2>
          {error ? (
            <p className="mt-3 font-mono text-xs text-danger break-all">{error}</p>
          ) : decision ? (
            <div className="mt-3 space-y-4">
              <div className="flex flex-wrap items-center gap-2">
                <StatusPill ok={decision.status === "APPROVED"}>{decision.status}</StatusPill>
                {decision.requires_human && (
                  <span className="rounded-full border border-warning/40 bg-warning/10 px-2.5 py-0.5 font-mono text-xs text-warning">
                    requires human
                  </span>
                )}
                <span className="text-xs text-muted">{decision.reason}</span>
              </div>
              <div className="overflow-x-auto rounded-md border border-border">
                <table className="w-full min-w-[28rem] text-sm">
                  <thead>
                    <tr className="border-b border-border text-left text-xs text-muted">
                      <th className="px-3 py-2 font-medium">Check</th>
                      <th className="px-3 py-2 font-medium">Result</th>
                      <th className="px-3 py-2 font-medium">Detail</th>
                    </tr>
                  </thead>
                  <tbody>
                    {decision.checks.map((c) => (
                      <tr key={c.code} className="border-b border-border/50 last:border-0">
                        <td className="px-3 py-1.5 font-mono text-xs">{c.code}</td>
                        <td className="px-3 py-1.5">
                          <span className={c.passed ? "text-accent" : "text-danger"}>
                            {c.passed ? "PASS" : "FAIL"}
                          </span>
                        </td>
                        <td className="px-3 py-1.5 text-xs text-muted">{c.detail}</td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </div>
          ) : (
            <p className="mt-3 text-sm text-muted">
              좌측에서 제안을 평가하세요. 22개 결정론적 체크가 실행되며, 하나라도 실패하면 거부됩니다.
            </p>
          )}
        </div>
      </section>
    </main>
  );
}
