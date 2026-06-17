"use client";

import { useEffect, useState } from "react";

import { api, type OrderProposalInput, type SubmitOrderResponse } from "@/lib/api";
import { ErrorNote, Loading, MockNotice, PageHeader, StatusPill, useApi } from "@/components/shell";

const ALLOWED = [
  { symbol: "069500", name: "KODEX 200" },
  { symbol: "102110", name: "TIGER 200" },
];

export default function TradingPage() {
  const orders = useApi(() => api.listOrders(20));
  const account = useApi(() => api.account());

  const [symbol, setSymbol] = useState("069500");
  const [quantity, setQuantity] = useState(1);
  const [limitPrice, setLimitPrice] = useState("");
  const [result, setResult] = useState<SubmitOrderResponse | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);

  // Prefill the limit price with a live quote.
  useEffect(() => {
    let active = true;
    api
      .marketQuotes([symbol])
      .then((r) => {
        const q = r.quotes.find((x) => x.symbol === symbol);
        if (active && q) setLimitPrice(String(Math.round(Number(q.price))));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [symbol]);

  async function submit() {
    setBusy(true);
    setError(null);
    setResult(null);
    const proposal: OrderProposalInput = {
      symbol,
      instrument_type: "ETF",
      side: "BUY",
      order_type: "LIMIT",
      quantity,
      limit_price: limitPrice,
      strategy_id: "baseline-momentum-v0",
      strategy_version: "0.1.0",
      idempotency_key: `web-trade-${symbol}-${Date.now()}`,
    };
    try {
      setResult(await api.submitOrder(proposal, true, limitPrice));
      orders.reload();
      account.reload();
    } catch (e) {
      setError(String(e));
    } finally {
      setBusy(false);
    }
  }

  return (
    <main className="mx-auto max-w-6xl px-6 py-10">
      <PageHeader
        title="페이퍼 트레이딩"
        subtitle="모의 체결 — 실거래·실계좌 아님. RESEARCH 모드에서는 실행이 비활성화됩니다."
      />
      <div className="mt-6">
        <MockNotice />
      </div>

      <section className="mt-8 grid gap-6 lg:grid-cols-[320px_1fr]">
        <div className="card space-y-4">
          <h2 className="section-label">주문 (paper)</h2>
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
            <span className="text-muted">지정가 (실시세 prefill)</span>
            <input
              value={limitPrice}
              onChange={(e) => setLimitPrice(e.target.value)}
              className="mt-1 w-full rounded-md border border-border bg-elevated px-3 py-2 font-mono text-sm"
            />
          </label>
          <button
            onClick={submit}
            disabled={busy}
            className="w-full rounded-xl border border-accent/40 bg-accent/10 px-3 py-2 text-sm font-semibold text-accent transition-colors hover:bg-accent/20 disabled:opacity-40"
          >
            {busy ? "제출 중…" : "매수 주문 (BUY)"}
          </button>

          {error && (
            <div className="rounded-md border border-warning/40 bg-warning/10 p-3 text-xs text-warning">
              {error.includes("409")
                ? "실행 비활성화: TRADING_MODE=RESEARCH. 모의 체결을 보려면 서버를 TRADING_MODE=PAPER로 실행하세요."
                : error}
            </div>
          )}
          {result && (
            <div className="rounded-md border border-border bg-elevated p-3 text-sm">
              <div className="flex items-center gap-2">
                <StatusPill ok={result.status === "FILLED"}>{result.status}</StatusPill>
                <span className="text-xs text-muted">{result.message}</span>
              </div>
              {result.fill && (
                <p className="mt-2 font-mono text-xs">
                  체결 {result.fill.quantity} @ {result.fill.price}
                </p>
              )}
            </div>
          )}
        </div>

        <div className="space-y-6">
          <div className="card">
            <h2 className="section-label">계좌 (paper)</h2>
            {account.loading ? (
              <Loading />
            ) : account.error ? (
              <ErrorNote error={account.error} />
            ) : account.data ? (
              <dl className="mt-3 grid grid-cols-2 gap-y-2 text-sm sm:grid-cols-4">
                <div>
                  <dt className="text-xs text-muted">realized</dt>
                  <dd className="font-mono">{account.data.realized_pnl}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">unrealized</dt>
                  <dd className="font-mono">{account.data.unrealized_pnl}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">total PnL</dt>
                  <dd className="font-mono text-accent">{account.data.total_pnl}</dd>
                </div>
                <div>
                  <dt className="text-xs text-muted">positions</dt>
                  <dd className="font-mono">{account.data.position_count}</dd>
                </div>
              </dl>
            ) : null}
            {account.data && account.data.positions.length > 0 && (
              <table className="mt-4 w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted">
                    <th className="px-2 py-1.5 font-medium">Symbol</th>
                    <th className="px-2 py-1.5 font-medium">Qty</th>
                    <th className="px-2 py-1.5 font-medium">Avg cost</th>
                    <th className="px-2 py-1.5 font-medium">Mark</th>
                    <th className="px-2 py-1.5 font-medium">Unrealized</th>
                  </tr>
                </thead>
                <tbody>
                  {account.data.positions.map((p) => (
                    <tr key={p.symbol} className="border-b border-border/50 last:border-0">
                      <td className="px-2 py-1.5 font-mono">{p.symbol}</td>
                      <td className="px-2 py-1.5 font-mono">{p.quantity}</td>
                      <td className="px-2 py-1.5 font-mono">{p.avg_cost}</td>
                      <td className="px-2 py-1.5 font-mono text-muted">{p.mark_price ?? "—"}</td>
                      <td className="px-2 py-1.5 font-mono">{p.unrealized_pnl ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            )}
          </div>

          <div className="card p-0">
            <h2 className="px-5 pt-5 text-xs font-semibold uppercase tracking-wider text-muted">주문 내역</h2>
            {orders.loading ? (
              <div className="p-5">
                <Loading />
              </div>
            ) : orders.error ? (
              <div className="p-5">
                <ErrorNote error={orders.error} />
              </div>
            ) : orders.data && orders.data.orders.length > 0 ? (
              <table className="mt-3 w-full text-sm">
                <thead>
                  <tr className="border-b border-border text-left text-xs text-muted">
                    <th className="px-4 py-2 font-medium">Symbol</th>
                    <th className="px-4 py-2 font-medium">Side</th>
                    <th className="px-4 py-2 font-medium">Qty</th>
                    <th className="px-4 py-2 font-medium">Status</th>
                    <th className="px-4 py-2 font-medium">Avg fill</th>
                  </tr>
                </thead>
                <tbody>
                  {orders.data.orders.map((o) => (
                    <tr key={o.id} className="border-b border-border/50 last:border-0">
                      <td className="px-4 py-2 font-mono">{o.symbol}</td>
                      <td className="px-4 py-2 font-mono">{o.side}</td>
                      <td className="px-4 py-2 font-mono">{o.quantity}</td>
                      <td className="px-4 py-2">
                        <span
                          className={
                            o.status === "FILLED"
                              ? "text-accent"
                              : o.status === "RISK_REJECTED"
                                ? "text-danger"
                                : "text-muted"
                          }
                        >
                          {o.status}
                        </span>
                      </td>
                      <td className="px-4 py-2 font-mono text-muted">{o.avg_fill_price ?? "—"}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            ) : (
              <p className="p-5 text-sm text-muted">아직 주문이 없습니다.</p>
            )}
          </div>
        </div>
      </section>
    </main>
  );
}
