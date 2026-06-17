"""The deterministic, deny-by-default Risk Engine.

No LLM, no I/O, no broker access — pure rules over an ``OrderProposal`` plus a
``RiskContext``. Checks that require live infrastructure not present in Phase 1
return a clearly labelled ``[PLACEHOLDER]`` pass and MUST be implemented before
any LIVE mode is enabled (see TRADING_SAFETY.md). They never gate-open a real
order because live execution is not implemented in this phase.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime
from decimal import Decimal

from kospi_watcher.domain.enums import (
    RiskCheckCode,
    RiskDecisionStatus,
    TradingMode,
)
from kospi_watcher.domain.risk.schemas import (
    OrderProposal,
    RiskCheckResult,
    RiskDecision,
    RiskLimits,
)
from kospi_watcher.domain.time import now_utc

_PLACEHOLDER = (
    "[PLACEHOLDER] structural check, not evaluated in Phase 1 (mock); "
    "implement before LIVE"
)


@dataclass(frozen=True)
class RiskContext:
    """Runtime state the engine evaluates a proposal against."""

    as_of: datetime
    trading_mode: TradingMode = TradingMode.RESEARCH
    market_open: bool | None = None
    last_price: Decimal | None = None
    position_notional: Decimal = Decimal("0")
    gross_exposure: Decimal = Decimal("0")
    daily_realized_loss: Decimal = Decimal("0")
    open_orders: int = 0
    daily_trade_count: int = 0
    seen_idempotency_keys: frozenset[str] = field(default_factory=frozenset)


class RiskEngine:
    def __init__(self, limits: RiskLimits) -> None:
        self.limits = limits

    @staticmethod
    def _r(code: RiskCheckCode, passed: bool, detail: str) -> RiskCheckResult:
        return RiskCheckResult(code=code, passed=passed, detail=detail)

    def evaluate(
        self, proposal: OrderProposal, context: RiskContext | None = None
    ) -> RiskDecision:
        ctx = context or RiskContext(as_of=now_utc())
        lim = self.limits
        checks: list[RiskCheckResult] = []

        # 1. Instrument allow-list (deny-by-default).
        checks.append(
            self._r(
                RiskCheckCode.INSTRUMENT_ALLOWED,
                proposal.symbol in lim.allowed_instruments,
                f"{proposal.symbol} "
                f"{'is' if proposal.symbol in lim.allowed_instruments else 'is NOT'}"
                " in allowed_instruments",
            )
        )
        # 2. Strategy allow-list.
        checks.append(
            self._r(
                RiskCheckCode.STRATEGY_ALLOWED,
                proposal.strategy_id in lim.allowed_strategies,
                f"strategy {proposal.strategy_id} "
                f"{'allowed' if proposal.strategy_id in lim.allowed_strategies else 'NOT allowed'}",
            )
        )
        # 3. Market open.
        market_open = lim.market_open if ctx.market_open is None else ctx.market_open
        checks.append(
            self._r(RiskCheckCode.MARKET_OPEN, market_open, f"market_open={market_open}")
        )
        # 4. Data freshness (placeholder).
        checks.append(self._r(RiskCheckCode.DATA_FRESHNESS, True, _PLACEHOLDER))
        # 5. Quote freshness — require a quote to size/deviation-check the order.
        has_quote = ctx.last_price is not None
        checks.append(
            self._r(
                RiskCheckCode.QUOTE_FRESHNESS,
                has_quote,
                "quote present" if has_quote else "no quote available (last_price is None)",
            )
        )
        # 6. Price deviation vs last quote (only meaningful for priced orders).
        price = proposal.effective_price
        if price is not None and ctx.last_price is not None and ctx.last_price > 0:
            deviation = abs(price - ctx.last_price) / ctx.last_price * Decimal("100")
            ok = deviation <= lim.price_deviation_pct
            checks.append(
                self._r(
                    RiskCheckCode.PRICE_DEVIATION,
                    ok,
                    f"deviation={deviation:.2f}% limit={lim.price_deviation_pct}%",
                )
            )
        else:
            checks.append(
                self._r(
                    RiskCheckCode.PRICE_DEVIATION,
                    price is None,
                    "no limit price (market order); deviation N/A"
                    if price is None
                    else "cannot evaluate deviation without a quote",
                )
            )
        # 7. Max order notional + abnormal quantity.
        if price is not None:
            notional = Decimal(proposal.quantity) * price
            ok = notional <= lim.max_order_notional and proposal.quantity <= lim.max_order_quantity
            checks.append(
                self._r(
                    RiskCheckCode.MAX_ORDER_NOTIONAL,
                    ok,
                    f"notional={notional} qty={proposal.quantity} "
                    f"(limits: notional<={lim.max_order_notional}, "
                    f"qty<={lim.max_order_quantity})",
                )
            )
        else:
            notional = Decimal("0")
            checks.append(
                self._r(
                    RiskCheckCode.MAX_ORDER_NOTIONAL,
                    False,
                    "cannot size order without a price",
                )
            )
        # 8. Max position notional.
        checks.append(
            self._r(
                RiskCheckCode.MAX_POSITION,
                ctx.position_notional + notional <= lim.max_position_notional,
                f"position+order={ctx.position_notional + notional} <= {lim.max_position_notional}",
            )
        )
        # 9. Max gross exposure.
        checks.append(
            self._r(
                RiskCheckCode.MAX_GROSS_EXPOSURE,
                ctx.gross_exposure + notional <= lim.max_gross_exposure,
                f"gross+order={ctx.gross_exposure + notional} <= {lim.max_gross_exposure}",
            )
        )
        # 10. Daily loss limit.
        checks.append(
            self._r(
                RiskCheckCode.DAILY_LOSS_LIMIT,
                ctx.daily_realized_loss <= lim.daily_loss_limit,
                f"daily_loss={ctx.daily_realized_loss} <= {lim.daily_loss_limit}",
            )
        )
        # 11-12. Drawdown / strategy loss (placeholders).
        checks.append(self._r(RiskCheckCode.MAX_DRAWDOWN, True, _PLACEHOLDER))
        checks.append(self._r(RiskCheckCode.STRATEGY_LOSS_LIMIT, True, _PLACEHOLDER))
        # 13. Daily trade count.
        checks.append(
            self._r(
                RiskCheckCode.DAILY_TRADE_COUNT,
                ctx.daily_trade_count < lim.daily_trade_count,
                f"trades_today={ctx.daily_trade_count} < {lim.daily_trade_count}",
            )
        )
        # 14. Slippage (placeholder).
        checks.append(self._r(RiskCheckCode.SLIPPAGE_LIMIT, True, _PLACEHOLDER))
        # 15. Open order count.
        checks.append(
            self._r(
                RiskCheckCode.OPEN_ORDER_COUNT,
                ctx.open_orders < lim.max_open_orders,
                f"open_orders={ctx.open_orders} < {lim.max_open_orders}",
            )
        )
        # 16. Reconciliation state (placeholder — assumed OK in mock).
        checks.append(self._r(RiskCheckCode.RECONCILIATION_STATE, True, _PLACEHOLDER))
        # 17. Duplicate order (idempotency).
        is_dup = proposal.idempotency_key in ctx.seen_idempotency_keys
        checks.append(
            self._r(
                RiskCheckCode.DUPLICATE_ORDER,
                not is_dup,
                "duplicate idempotency_key" if is_dup else "idempotency_key is new",
            )
        )
        # 18-22. Remaining live-data checks (placeholders).
        for code in (
            RiskCheckCode.VOLATILITY_SPIKE,
            RiskCheckCode.API_FAILURE,
            RiskCheckCode.DATA_RELIABILITY,
            RiskCheckCode.ETF_DISCOUNT_PREMIUM,
            RiskCheckCode.INAV_ANOMALY,
        ):
            checks.append(self._r(code, True, _PLACEHOLDER))

        failed = [c.code for c in checks if not c.passed]
        approved = not failed
        status = RiskDecisionStatus.APPROVED if approved else RiskDecisionStatus.REJECTED
        # GUARDED_LIVE always defers an approved order to a human (never auto-sends).
        requires_human = approved and ctx.trading_mode is TradingMode.GUARDED_LIVE
        reason = (
            "all implemented risk checks passed"
            if approved
            else "rejected by: " + ", ".join(code.value for code in failed)
        )
        return RiskDecision(
            decision_id=uuid.uuid4().hex,
            proposal_id=proposal.proposal_id,
            status=status,
            created_at=now_utc(),
            checks=checks,
            failed_checks=failed,
            reason=reason,
            requires_human=requires_human,
        )
