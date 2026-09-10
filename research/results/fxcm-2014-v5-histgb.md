# FXCM EURUSD 2014 — V5 HistGradientBoosting

Status: **PASSED_LOCKED — REQUIRES INDEPENDENT 2015 REPLICATION**

Authoritative workflow run: `34516011788`

Authoritative commit: `c0ffd891e1e7e034f4021488a434095b9f4fbc97`

Artifact digest: `sha256:5a6fd64025188d4093459e4cefe8ed968990cf42c3ab1214ec8ee370b13e20b9`

Dataset fingerprint: `3588398a302084a360b8eea1cfce3676c68c61e4e5d62b6b9e45e32c0f133f71`

Dataset rows: `368,878`

Preregistration: `research/hypotheses/v5-histgradientboosting-preregistration.md`

Protocol note: workflow run `34515712020` is separately marked discarded without outcome inspection because its reporting helper could calculate post-hoc robustness after a failed locked test. The primary protocol settings were unchanged; only run `34516011788` is interpreted here.

## Fixed model

```text
HistGradientBoostingClassifier
learning_rate      = 0.05
max_iter           = 200
max_leaf_nodes     = 15
max_depth          = None
min_samples_leaf   = 100
l2_regularization  = 1.0
early_stopping     = False
random_state       = 42
```

The model reused the exact causal V4 feature universe. There was no model-hyperparameter search.

Development search was limited to:

```text
expiry bars              [1, 2, 3, 5]
probability thresholds   [0.55, 0.575, 0.60, 0.625, 0.65]
total cells              20
OOF folds                5, expanding time series with expiry-aware purge gap
hypothetical payout      0.82
```

All short-expiry targets and trades used gap-safe settlement.

## Selected development candidate

```text
expiry                    3 bars
probability threshold     0.625
trades                    5,204
resolved                  5,096
wins                      3,044
losses                    2,052
ties                      108
win rate                  59.7331%
95% Wilson interval       [58.3798%, 61.0718%]
expectancy                +0.085334 per unit stake
total P&L                 +444.08 units
max drawdown              42.16 units
max losing streak         13
```

The complete 20-cell development table was retained in the machine-readable artifact. No alternative candidate was substituted after seeing validation.

## Validation

The frozen development-fitted model, expiry and threshold were used for prediction only.

```text
trades                    915
resolved                  905
wins                      572
losses                    333
ties                      10
win rate                  63.2044%
95% Wilson interval       [60.0128%, 66.2844%]
expectancy                +0.148678
total P&L                 +136.04 units
max drawdown              22.86 units
max losing streak         11
```

The 82%-payout break-even win rate is approximately `54.9451%`. Validation cleared the preregistered sample, expectancy, and Wilson-lower gates, so the locked 2014 slice was legitimately opened.

## Locked test

```text
trades                    1,124
resolved                  1,116
wins                      666
losses                    450
ties                      8
win rate                  59.6774%
95% Wilson interval       [56.7709%, 62.5175%]
expectancy                +0.085516
total P&L                 +96.12 units
max drawdown              35.50 units
max losing streak         9
```

The locked test clears the preregistered primary gate.

## Allowed post-pass robustness

### Payout sensitivity

```text
80% payout  expectancy +0.073665   total +82.80
82% payout  expectancy +0.085516   total +96.12
90% payout  expectancy +0.132918   total +149.40
```

### Additional entry delay

One additional bar of entry delay:

```text
1,113 resolved trades
58.9398% win rate
Wilson low 56.0237%
expectancy +0.072186
```

This remains above the 82%-payout break-even confidence threshold.

### Non-overlapping execution

```text
753 resolved trades
60.0266% win rate
Wilson low 56.4855%
expectancy +0.091632
```

### Moving-block bootstrap expectancy

```text
block 5   2.5th percentile +0.022934   P(EV > 0) 99.58%
block 10  2.5th percentile +0.020018   P(EV > 0) 99.38%
block 20  2.5th percentile +0.015000   P(EV > 0) 99.20%
```

The ordinary bootstrap 2.5th percentile was `+0.033701`.

### Direction and month diagnostics

Overall locked performance was positive in both CALL and PUT directions by point estimate. The PUT subgroup had stronger confidence support; the CALL subgroup's Wilson lower bound alone was below the 82%-payout break-even threshold. This is descriptive only and **does not authorize a direction filter** for replication.

Monthly locked performance decayed from October through December. December remained positive by point estimate but its standalone Wilson lower bound was below break-even. No month filter is permitted for the replication.

## Decision

V5 has earned **candidate** status on regular FXCM EUR/USD because it passed development, validation, locked testing and the preregistered post-pass robustness diagnostics.

It has **not** earned replicated-edge status yet.

The exact model family/hyperparameters, 3-bar expiry, 0.625 probability threshold, feature list and gap-safe settlement must now be frozen for the preregistered one-shot 2015 replication. No 2014-derived direction, month, payout, or other subgroup filter may be added.

This is not Pocket Option/OTC evidence. The 82% payout is hypothetical and no future return or fixed win rate is guaranteed.