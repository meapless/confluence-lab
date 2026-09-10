# FXCM EURUSD 2017 — V3A CALL-only Range Replication

Status: **REJECTED_PRIMARY**

Preregistration: `research/hypotheses/v3a-call-only-range-preregistration.md`

Workflow run: `34494412081`

Artifact digest: `sha256:c7548a17fdfa330d0e7d82c6341deaffac0f01f8e60e43d52b00bf61b44e2c87`

Dataset fingerprint: `2ee9d530c34c74bec2ae3d56b1cd7fc45e5e1d37c8c59426b6f25c1f02edac03`

Dataset rows: `369,924`

## Frozen hypothesis

Exact V1 range-reversion configuration, CALL signals only:

```text
adx_max = 30.0
rsi_lower = 25.0
rsi_upper = 65.0
band_buffer_atr = 0.10
atr_pct_max = 0.70
expiry_bars = 5
entry_offset_bars = 1
fixed_payout = 0.82 (hypothetical)
```

No parameter search was performed on 2017.

## Primary result

```text
trades = 548
non_tie_trades = 541
wins = 311
losses = 230
ties = 7
win_rate = 57.4861%
95% Wilson interval = [53.2820%, 61.5848%]
expectancy = +0.045657 per unit stake
total_pnl = +25.02 units
max_drawdown = 22.72 units
max_losing_streak = 12
```

Hypothetical 82% payout break-even win rate: `54.9451%`.

The preregistered primary rule required the **95% Wilson lower bound** to exceed break-even. The observed lower bound was only `53.2820%`, therefore V3A fails regardless of the positive point estimate and P&L.

## Frozen robustness diagnostics

- 80% payout repricing: **positive**, expectancy `+0.03431`.
- One additional bar of entry delay (`entry_offset_bars=2`): **failed**, expectancy `-0.00931`, win rate `54.4280%`.
- Non-overlapping positions: **positive point estimate**, expectancy `+0.02805`, but Wilson lower bound only `51.1800%`.

## Decision

`REJECTED_PRIMARY`.

The 57.49% headline is not sufficient evidence. The confidence interval does not clear the economic break-even threshold and the edge does not survive a small entry-delay perturbation.

This is regular FXCM EUR/USD midpoint research using a hypothetical binary payout. It is not Pocket Option or OTC evidence and must not be marketed as expected trading performance.
