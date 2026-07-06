# ADR-029 — Trend-anchor recalibration: bull-default + strict bear confirmation

Date: 2026-07-06 · Status: accepted (supersedes the rule inside ADR-025; the
anchor/backtest architecture of ADR-025 is unchanged)

## Context

The prediction's primary directional driver is the deterministic `trend_core`
(ADR-025): price vs the 100-day SMA, gated by 60-day momentum agreement,
abstaining on conflict. Measured over 29 years of ^KS11 (7,276 sessions,
walk-forward), that symmetric rule showed persistent weaknesses: worst-regime
composite skill −11.5%p (6-fold min), 14% of days with no call, and bear calls
whose overall D20 hit rate (45.1%) was dragged below 50% by false alarms in
range-bound markets — even though the same bear calls scored well inside true
bear regimes (2008: 0.57, 2022: 0.61).

## Experiment

~530 past-only candidate rules (symmetric MA/momentum grids, dual-MA crosses,
momentum-only, vote ensembles, Donchian channels, bull-default families) were
evaluated with an anti-overfit protocol:

* **Selection**: ^KS11 history *excluding the last 750 sessions*, 3→6
  contiguous folds; score = the **minimum** fold composite
  (skill_D5 + 2·skill_D20 + skill_D60)/4 — must survive every regime.
* **Validation (held out)**: the last 750 sessions of ^KS11 **and** the full
  ^KQ11 (KOSDAQ) series.
* **Acceptance gates**: better worst-fold than the incumbent; no loss on the
  held-out windows; D20 hit ≥ 0.50 inside the 2008 GFC and 2022 bear windows
  (a watcher that can't call a real bear is useless); D20 coverage ≥ 0.85.

Two structural findings drove the redesign: (1) KOSPI's upward drift makes
*bullish-by-default* the right prior; (2) bear calls only pay under strict
regime confirmation, and chasing weakness >10% below the 100-day line is
negative-value (mean-reversion zone).

## Decision — the recalibrated `trend_core`

**Bullish by default.** **Bearish only when ALL hold:**

1. price is 3%+ below the 100-day SMA (clear breach), and
2. 60-day momentum is negative, and
3. SMA50 < SMA200 (trend structure broken), and
4. the breach is *not* deeper than 10% (deep oversold → weak default long
   labelled "급락 구간 — 과매도 반등 우위", never a fresh bear call).

Strength: trend/momentum-scaled as before for confirmed calls; a fixed weak
0.15 for unconfirmed default-long days (so the Chief tilt and the confidence
bonus stay honest). NEUTRAL now only means "insufficient history" (warmup
200 sessions, up from 100); consumers (`backtest`, `accuracy_track`) import
`TREND_WARMUP`, and the fetch windows grew accordingly (trend 2y, accuracy 3y,
backtest 10y — note Yahoo's `range=max` is broken for these indices).

62/243 of the strict-bear family passed all gates; the chosen point sits on a
broad parameter plateau (neighbouring variants perform nearly identically),
which is the main defence against overfitting.

## Measured results (winner vs incumbent)

| Metric | old | new |
|---|---|---|
| worst 6-fold composite (selection) | −11.5%p | **−3.4%p** |
| held-out 3y D5 hit | 53.4% | **57.7%** |
| held-out 3y D20 hit | 59.6% | **63.2%** |
| 29y D5 / D20 / D60 hit | 52.0 / 52.8 / 55.9% | **55.3 / 55.9 / 60.0%** |
| KOSDAQ (cross-market) composite | −2.1%p | **−1.0%p** |
| 2008 / 2022 bear-window D20 hit | 0.57 / 0.61 | 0.53 / 0.58 (gate ≥ 0.50) |
| coverage (has a call) | 86% | **100%** |

Honest framing unchanged: skill vs the post-hoc always-majority base rate
remains slightly negative (−0.7%p from −4%p) — the anchor's job is regime
alignment, not oracle-beating; hit rates and worst-regime behavior are what
improved. The self-improvement loop (ADR-027) rescales automatically: the
realized D5 hit rate feeds `confidence_target`.

## Consequences

* Every day now has a directional anchor (no more 추세 중립 gaps), with weak
  conviction honestly labelled on default-long days.
* Bear calls are rarer but regime-confirmed; the house view stops fighting
  box-market chop and stops chasing crash bottoms.
* Warmup grew to 200 sessions — any consumer feeding shorter series gets
  NEUTRAL (and the mock/offline series were lengthened to compensate).
