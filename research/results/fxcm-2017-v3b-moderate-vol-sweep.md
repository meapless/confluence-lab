# FXCM EURUSD 2017 — V3B Moderate-Volatility Sweep Reversal

Status: **REJECTED_PRIMARY**

Preregistration: `research/hypotheses/v3b-moderate-vol-sweep-preregistration.md`

Workflow run: `34495210254`

Artifact digest: `sha256:192e988d46c1107cdf7b090a7722e63f141b395e5ca238db6d6b9fc528841cfd`

Dataset fingerprint: `2ee9d530c34c74bec2ae3d56b1cd7fc45e5e1d37c8c59426b6f25c1f02edac03`

Dataset rows: `369,924`

## Frozen hypothesis

Exact 2018 V2 Sweep Reversal winner, restricted to the post-hoc fixed moderate-volatility bucket:

```text
lookback = 20
wick_min = 0.65
rsi_edge = 65.0
overshoot_atr = 0.0
liquid_core_only = false
atr_percentile_100 > 0.25
atr_percentile_100 <= 0.50
expiry_bars = 2
entry_offset_bars = 1
fixed_payout = 0.82 (hypothetical)
```

No parameter search or subgroup selection was performed on 2017.

## Primary result

```text
trades = 175
non_tie_trades = 174
wins = 84
losses = 90
ties = 1
win_rate = 48.2759%
95% Wilson interval = [40.9688%, 55.6574%]
expectancy = -0.120686 per unit stake
total_pnl = -21.12 units
max_drawdown = 29.90 units
max_losing_streak = 9
```

Hypothetical 82% payout break-even win rate: `54.9451%`.

The preregistered primary rule required at least 120 non-tie trades, positive expectancy, and a 95% Wilson lower bound above break-even. Sample size cleared the minimum, but both economic and statistical criteria failed materially.

## Frozen robustness diagnostics

- 80% payout repricing: **failed**, expectancy `-0.13029`.
- One additional bar of entry delay: **failed**, expectancy `-0.03646`.
- Non-overlapping positions: **failed**, expectancy unchanged at `-0.12069` because these selected signals did not materially overlap under the frozen expiry.
- Moving-block bootstrap, block size 5: **failed**, lower 95% expectancy `-0.2824`, probability positive `2.76%`.
- Moving-block bootstrap, block size 10: **failed**, lower 95% expectancy `-0.27669`, probability positive `1.20%`.
- Moving-block bootstrap, block size 20: **failed**, lower 95% expectancy `-0.2512`, probability positive `1.36%`.
- CALL subset: 46.84% win rate, expectancy `-0.14759`.
- PUT subset: 49.47% win rate, expectancy `-0.09854`.

## Decision

`REJECTED_PRIMARY`.

The fixed moderate-volatility subgroup that appeared attractive in post-hoc 2018 diagnostics did not reproduce on the fresh 2017 year. It should not be refined against 2017 and should not be used as evidence of an edge.

This is regular FXCM EUR/USD midpoint research using a hypothetical binary payout. It is not Pocket Option or OTC evidence and must not be marketed as expected trading performance.
