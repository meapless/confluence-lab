# Confluence Lab V2 preregistration

Recorded before the first V2 evaluation on FXCM 2018 EUR/USD M1.

## Scope and interpretation

All work in this protocol uses **regular FX EUR/USD market data**, not Pocket Option or OTC data. A fixed 82% payout is a hypothetical binary-style economics assumption for comparing directional outcomes. Nothing in this study should be represented as expected Pocket performance or future profit.

The 2019 FXCM benchmark has already been observed. Therefore 2019 is considered **seen research context** and is not eligible to serve as independent confirmation for the V2 hypotheses below.

## Economic threshold

At an 82% payout, the simple no-tie break-even win rate is:

`1 / (1 + 0.82) = 54.9451%`

For fixed-payout studies, point-estimate win rate alone is insufficient. Validation must have positive payout-adjusted expectancy and its 95% Wilson lower confidence bound must exceed 54.9451% before a locked test is opened.

---

# Track A — fixed Range Reversion replication

The first 2019 long-history benchmark produced a near-miss in Range Reversion. Its selected parameters are now frozen and will be evaluated on an **independent full 2018 FXCM year without any parameter search**.

Frozen configuration:

- family: `range_reversion`
- `adx_max = 30.0`
- `rsi_lower = 25.0`
- `rsi_upper = 65.0`
- `band_buffer_atr = 0.10`
- `atr_pct_max = 0.70`
- expiry: 5 one-minute bars
- entry offset: 1 bar
- payout assumption: 0.82
- tie policy: refund
- stake: 1 unit

Primary replication evidence:

- full-year trade count
- win/loss/tie counts
- payout-adjusted expectancy
- 95% Wilson interval on non-tie win rate
- maximum drawdown in unit-stake P&L
- longest losing streak

Replication pass criterion:

1. at least 500 trades;
2. positive expectancy;
3. Wilson 95% lower bound > 54.9451%.

No parameter may be changed after seeing the 2018 result. If it fails, it is recorded as a failed replication.

Secondary stress diagnostics, which do not change the primary pass/fail decision:

- CALL and PUT performance separately;
- non-overlapping positions;
- non-overlapping positions with 1- and 2-bar cooldowns;
- entry delay sensitivity;
- hypothetical payout sensitivity.

---

# Track B — V2 family search on untouched 2018 data

The first V2 family search will use FXCM EUR/USD M1 2018. Within that year, data is split chronologically:

- development: 60%
- validation: 20%
- locked test: 20%

The locked slice may not be inspected for a family unless its selected development candidate passes validation.

Development candidate eligibility:

- at least 200 development trades;
- positive expectancy under the 82% payout assumption;
- candidates ranked by Wilson 95% lower bound, not raw win rate.

Validation gate:

- at least 100 validation trades;
- positive expectancy;
- Wilson 95% lower bound > 54.9451%.

Locked evidence minimum:

- at least 100 locked trades;
- positive expectancy;
- Wilson 95% lower bound > 54.9451% to call the locked result an evidence pass.

A locked pass is still only a research result. Any surviving candidate must later pass execution, overlap, payout, calendar and independent-year stress tests.

## V2-1 — Higher-timeframe-aligned pullback

Hypothesis: a 1-minute pullback-recovery signal may be more reliable when its direction agrees with a **previously completed** 5-minute or 15-minute trend rather than using only 1-minute indicators.

Independent evidence components:

- base-timeframe trend and pullback location;
- momentum recovery;
- completed higher-timeframe trend;
- volatility ceiling.

Frozen search grid:

- `htf_minutes`: 5, 15
- `adx_min`: 15, 20, 25
- `ema_distance_atr`: 0.25, 0.50, 0.75
- `rsi_trigger`: 50, 55
- `atr_pct_max`: 0.75, 0.90

Grid size: **72** parameter sets.

## V2-2 — Volatility-compression breakout

Hypothesis: breakouts may have better continuation odds when preceded by unusually narrow Bollinger width, accompanied by current ATR expansion, and aligned with a previously completed HTF trend.

Leakage controls:

- compression is measured on the previous bar;
- breakout boundaries are rolling highs/lows shifted one bar;
- HTF direction comes only from the prior completed 5m/15m candle.

Frozen search grid:

- `htf_minutes`: 5, 15
- `lookback`: 20, 30
- `compression_max`: 0.20, 0.35 percentile
- `body_min`: 0.50, 0.65
- `atr_expansion_min`: 1.0, 1.2 for ATR(5)/ATR(50)

Grid size: **32** parameter sets.

## V2-3 — Failed-breakout / sweep reversal

Hypothesis: a candle that trades beyond a prior range extreme but closes back inside with a large rejection wick may have short-horizon reversal information, especially when momentum is already extended.

Leakage controls:

- prior range high/low is shifted one bar;
- ATR overshoot reference is shifted one bar;
- entry remains next-bar open.

Frozen search grid:

- `lookback`: 20, 30, 50
- `wick_min`: 0.50, 0.65
- `rsi_edge`: 60, 65
- `overshoot_atr`: 0.00, 0.10
- `liquid_core_only`: false, true

`liquid_core_only=true` means fixed UTC hours 07:00 through 16:59. This is intentionally called a UTC liquidity window rather than a London/New York session label because daylight-saving boundaries are not being modeled here.

Grid size: **48** parameter sets.

## Total V2 search budget

V2 parameter sets: `72 + 32 + 48 = 152`.

With four preregistered expiries (1, 2, 3, 5 bars), maximum development evaluations are `152 × 4 = 608`.

This search budget is deliberately far smaller than the V1 catalog to reduce multiple-testing pressure.

---

# After a candidate survives

A V2 candidate that passes its locked 2018 slice will not immediately become a signal product. It must be frozen and subjected to:

- one-position-at-a-time execution;
- cooldown sensitivity;
- +1 and +2 bar entry-delay sensitivity;
- lower payout assumptions;
- direction-separated performance;
- calendar-period stability;
- bootstrap confidence interval for payout-adjusted expectancy;
- Monte Carlo trade-order diagnostics;
- at least one additional independent FX year;
- eventually Pocket-specific demo data with contemporaneous broker payouts.

No Martingale or loss-chasing position sizing is part of this protocol.
