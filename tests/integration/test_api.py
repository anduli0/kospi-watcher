"""End-to-end API tests over the 7 Phase-1 endpoints (httpx ASGI transport)."""

from __future__ import annotations

from decimal import Decimal
from typing import Any

from httpx import AsyncClient


def _proposal_body(idempotency_key: str = "api-k-1", **overrides: Any) -> dict[str, Any]:
    body: dict[str, Any] = {
        "symbol": "069500",
        "instrument_type": "ETF",
        "side": "BUY",
        "order_type": "LIMIT",
        "quantity": 10,
        "limit_price": "35000",
        "strategy_id": "baseline-momentum-v0",
        "strategy_version": "0.1.0",
        "idempotency_key": idempotency_key,
    }
    body.update(overrides)
    return body


async def test_health_reports_backends_and_safety(client: AsyncClient) -> None:
    resp = await client.get("/health")
    assert resp.status_code == 200
    data = resp.json()
    assert data["status"] in ("ok", "degraded")
    assert data["database"]["backend"] == "sqlite"
    assert data["redis"]["backend"] == "fakeredis"
    assert data["live_trading_enabled"] is False
    assert data["trading_mode"] == "RESEARCH"


async def test_system_status(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/system/status")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_count"] == 21
    assert data["trading_mode"] == "RESEARCH"
    assert data["feature_flags"]["live_execution_implemented"] is False
    assert data["feature_flags"]["paper_execution_implemented"] is True
    assert data["agent_runtime"] == "mock"  # no key in tests


async def test_list_agents_returns_21(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/agents")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] == 21
    assert len(data["agents"]) == 21
    assert all(a["enabled"] for a in data["agents"])


async def test_agents_org_hierarchy(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/agents/org")
    assert resp.status_code == 200
    data = resp.json()
    assert data["agent_count"] == 21
    assert len(data["desks"]) == 6
    keys = {d["key"] for d in data["desks"]}
    assert keys == {"DATA_INTEGRITY", "MACRO", "FLOW_TECH", "FUNDAMENTAL", "RISK", "CHIEF"}
    assert data["tiers"] == ["VALIDATE", "ANALYZE", "SYNTHESIZE"]


async def test_prediction_run_latest_and_brief(client: AsyncClient) -> None:
    run = await client.post("/api/v1/prediction/run", json={"agent_name": "n/a", "universe": []})
    assert run.status_code == 200
    pred = run.json()
    assert len(pred["desk_views"]) == 6
    assert {s["symbol"] for s in pred["instrument_stances"]} == {
        "069500",
        "122630",
        "114800",
        "252670",
    }
    assert pred["generated_by"] == "mock"
    assert abs(sum(s["probability"] for s in pred["scenarios"]) - 1.0) < 1e-6

    latest = await client.get("/api/v1/prediction/latest")
    assert latest.status_code == 200
    assert latest.json()["prediction_id"] == pred["prediction_id"]

    brief = await client.get("/api/v1/brief")
    assert brief.status_code == 200
    body = brief.json()
    assert "곱버스" in body["brief"]
    assert len(body["stances"]) == 4


async def test_brief_404_before_any_run(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/brief")).status_code == 404
    assert (await client.get("/api/v1/prediction/latest")).status_code == 404


async def test_news_scrape_list_and_dates(client: AsyncClient) -> None:
    scrape = await client.post("/api/v1/news/scrape")
    assert scrape.status_code == 200
    assert scrape.json()["added"] >= 1  # mock provider yields items

    listing = await client.get("/api/v1/news?limit=10")
    assert listing.status_code == 200
    body = listing.json()
    assert body["count"] >= 1
    assert all("title" in it and "date_kst" in it for it in body["items"])

    dates = await client.get("/api/v1/news/dates")
    assert dates.status_code == 200
    assert len(dates.json()["dates"]) >= 1


async def test_market_quotes(client: AsyncClient) -> None:
    resp = await client.get("/api/v1/market/quotes?symbols=069500,USDKRW")
    assert resp.status_code == 200
    data = resp.json()
    assert data["provider"] == "mock"  # forced offline in tests
    syms = {q["symbol"] for q in data["quotes"]}
    assert syms == {"069500", "USDKRW"}


async def test_mock_run_known_and_unknown(client: AsyncClient) -> None:
    ok = await client.post(
        "/api/v1/agents/mock-run",
        json={"agent_name": "FX Agent", "universe": ["069500"]},
    )
    assert ok.status_code == 200
    assert ok.json()["status"] == "SUCCEEDED"

    missing = await client.post(
        "/api/v1/agents/mock-run", json={"agent_name": "Nope Agent"}
    )
    assert missing.status_code == 404


async def test_agents_run_uses_mock_runtime(client: AsyncClient) -> None:
    # /agents/run uses the configured runtime; with no key it is the mock.
    resp = await client.post(
        "/api/v1/agents/run", json={"agent_name": "FX Agent", "universe": ["069500"]}
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "SUCCEEDED"
    assert body["model_name"] == "mock-deterministic-v0"


async def test_order_proposal_validate_and_duplicate(client: AsyncClient) -> None:
    first = await client.post(
        "/api/v1/order-proposals/validate", json=_proposal_body("dup-key")
    )
    assert first.status_code == 200
    assert first.json()["valid"] is True

    second = await client.post(
        "/api/v1/order-proposals/validate", json=_proposal_body("dup-key")
    )
    assert second.status_code == 409


async def test_risk_evaluate_reject_and_approve(client: AsyncClient) -> None:
    closed = await client.post(
        "/api/v1/risk/evaluate",
        json={"proposal": _proposal_body("r-closed"), "market_open": False},
    )
    assert closed.status_code == 200
    assert closed.json()["status"] == "REJECTED"
    assert "MARKET_OPEN" in closed.json()["failed_checks"]

    approved = await client.post(
        "/api/v1/risk/evaluate",
        json={
            "proposal": _proposal_body("r-open"),
            "market_open": True,
            "last_price": "35000",
        },
    )
    assert approved.status_code == 200
    assert approved.json()["status"] == "APPROVED"


async def test_invalid_proposal_is_422(client: AsyncClient) -> None:
    # LIMIT order without a limit_price is rejected at the schema boundary.
    bad = _proposal_body("bad")
    bad.pop("limit_price")
    resp = await client.post("/api/v1/order-proposals/validate", json=bad)
    assert resp.status_code == 422


async def test_submit_order_refused_in_research_mode(client: AsyncClient) -> None:
    # Default test trading mode is RESEARCH -> execution is disabled (409).
    resp = await client.post(
        "/api/v1/orders",
        json={"proposal": _proposal_body("po-1"), "market_open": True},
    )
    assert resp.status_code == 409
    assert "RESEARCH" in resp.json()["detail"]


async def test_trading_read_endpoints_empty(client: AsyncClient) -> None:
    assert (await client.get("/api/v1/orders")).status_code == 200
    assert (await client.get("/api/v1/positions")).json() == []
    account = (await client.get("/api/v1/account")).json()
    assert account["account"] == "paper"
    assert account["position_count"] == 0
    assert Decimal(str(account["total_pnl"])) == Decimal("0")


async def test_audit_log_records_actions(client: AsyncClient) -> None:
    await client.post(
        "/api/v1/agents/mock-run", json={"agent_name": "FX Agent"}
    )
    resp = await client.get("/api/v1/audit-logs?limit=10")
    assert resp.status_code == 200
    data = resp.json()
    assert data["count"] >= 1
    assert any(item["action"] == "AGENT_RUN" for item in data["items"])
