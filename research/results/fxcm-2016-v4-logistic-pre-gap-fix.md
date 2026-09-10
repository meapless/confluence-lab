# FXCM EURUSD 2016 — V4 Logistic Baseline (pre gap-safe settlement)

Status: **REJECTED_VALIDATION**

Audit status: **SUPERSEDED FOR CONFIRMATORY USE PENDING GAP-SAFE RERUN**

Preregistration: `research/hypotheses/v4-logistic-preregistration.md`

Workflow run: `34496407185`

Artifact digest: `sha256:4f55c78cf447bf387635ee0144ad0c410a585f91fcbd4148daf5d35fbc30d308`

Dataset fingerprint: `b0103c0a12a87210c8caf5061c1c6482c28ecc2139846dbe7e62eec6b5fd7991`

Dataset rows: `371,619`

## Frozen V4 protocol

```text
model = StandardScaler + LogisticRegression
C = 1.0
penalty = l2
solver = lbfgs
class_weight = None
expiries = [1, 2, 3, 5]
probability thresholds = [0.55, 0.575, 0.60, 0.625, 0.65]
development candidates = 20
OOF folds = 5
fixed payout = 0.82 (hypothetical)
```

The feature list and model settings were frozen before the 2016 evaluation.

## Selected development candidate

```text
expiry_bars = 5
probability_threshold = 0.575
trades = 3,828
non_tie_trades = 3,805
wins = 2,222
losses = 1,583
ties = 23
win_rate = 58.3968%
95% Wilson interval = [56.8230%, 59.9537%]
expectancy = +0.062445 per unit stake
total_pnl = +239.04 units
max_drawdown = 44.46 units
max_losing_streak = 22
```

Hypothetical 82% payout break-even win rate: `54.9451%`.

The development candidate cleared the preregistered development eligibility criteria.

## Validation

```text
trades = 1,557
non_tie_trades = 1,540
wins = 883
losses = 657
ties = 17
win_rate = 57.3377%
95% Wilson interval = [54.8522%, 59.7866%]
expectancy = +0.043070 per unit stake
total_pnl = +67.06 units
max_drawdown = 52.44 units
max_losing_streak = 16
```

The validation point estimate and hypothetical payout-adjusted expectancy were positive, but the preregistered gate required the **95% Wilson lower bound** to exceed the 82%-payout break-even win rate of `54.9451%`.

Observed validation Wilson lower bound: `54.8522%`.

Shortfall: approximately `0.0929` percentage points.

Therefore validation failed and the locked 2016 slice was **not opened**.

## Complete-search context

The report retained all 20 development cells. The selected 5-bar / 0.575 candidate had the highest eligible development Wilson lower bound (`56.8230%`). Several lower-confidence candidates had positive development expectancy, but no alternative was substituted after validation.

## Gap-safety audit note

This run occurred before Confluence Lab enforced contiguous timestamp horizons in the settlement engine and ML target generator. The earlier implementation advanced by available row number, so a short-expiry target near a weekend, market closure, or missing-candle gap could bridge the discontinuity.

The result remains preserved as historical evidence of what the pre-fix engine produced, but it must not be treated as the final V4 confirmatory result. V4 is to be rerun under the gap-safe protocol using the same frozen model/search rules.

## Decision

`REJECTED_VALIDATION` under the original engine, with locked test unopened.

No claim of a validated edge is supported. This is regular FXCM EUR/USD midpoint research using a hypothetical fixed payout, not Pocket Option/OTC evidence.
