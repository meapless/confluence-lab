# V5 — Frozen 2015 Independent Replication

Status: **PREREGISTERED BEFORE ANY 2015 DATA IS ACCESSED**

Parent result: `research/results/fxcm-2014-v5-histgb.md`

Authoritative 2014 V5 artifact digest: `sha256:5a6fd64025188d4093459e4cefe8ed968990cf42c3ab1214ec8ee370b13e20b9`

Authoritative 2014 dataset fingerprint: `3588398a302084a360b8eea1cfce3676c68c61e4e5d62b6b9e45e32c0f133f71`

## Purpose

V5 is the first Confluence Lab model to clear its preregistered development, validation, locked-test, payout, execution-delay, non-overlap and dependence-aware bootstrap checks on regular FXCM EUR/USD data.

This study asks one question only:

**Does that exact candidate replicate on an independent full year that has not been used for model or threshold development?**

No 2015 observation may be used to alter the model, feature list, expiry, probability threshold, payout assumption, or pass/fail criteria.

## Training source

Training data: **FXCM EUR/USD M1, full 2014**.

Before fitting, the downloaded 2014 dataset fingerprint must exactly equal:

`3588398a302084a360b8eea1cfce3676c68c61e4e5d62b6b9e45e32c0f133f71`

If the fingerprint differs, the replication must stop and report a provenance mismatch rather than silently training on changed history.

The final replication model is fit on all 2014 rows that:

- have the frozen V5 feature vector fully available; and
- have a valid gap-safe 3-bar direction target.

Tie, out-of-bounds and gap-crossing targets remain invalid for fitting. No resampling or class weighting is added.

## Frozen feature set

Use the exact existing `ML_FEATURE_COLUMNS` from V4/V5. No feature selection, feature addition, interaction engineering, or normalization change is permitted.

## Frozen model

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

No hyperparameter search or calibration is permitted.

## Frozen trading decision

```text
expiry_bars            = 3
entry_offset_bars       = 1
probability_threshold   = 0.625
CALL                    if P(up) >= 0.625
PUT                     if P(up) <= 0.375
NO TRADE                otherwise
fixed payout scenario   = 0.82
stake                    = 1 unit
allow overlap            = True for primary replication
cooldown                 = 0
require contiguous bars  = True
```

## Replication source

Evaluation data: **FXCM EUR/USD M1, full 2015**.

2015 is treated as a single independent replication set. There is no development/validation/locked subdivision and no candidate selection on 2015.

For consistency with prior validation/locked evaluation, features are built from the 2015 frame itself. Early rows lacking the frozen trailing feature history are simply ineligible for prediction; no parameter is changed to recover them.

The 2015 dataset fingerprint, weekly source SHA-256 hashes, missing-week list and diagnostics must be recorded in the result.

## Primary replication gate

The frozen candidate passes the primary 2015 replication only if all of the following hold on the full 2015 prediction set:

1. at least **150 resolved non-tie trades**;
2. payout-adjusted expectancy at hypothetical 82% payout is strictly greater than zero;
3. the 95% Wilson lower bound for win rate is strictly greater than `1 / (1 + 0.82)` = approximately **54.9451%**.

If the primary gate fails:

- classification = `rejected_replication`;
- no robustness subgroup analysis is permitted;
- the V5 replication line is closed on 2015;
- no direction, month, session, volatility or confidence subset may be used to rescue it.

## Robustness after primary replication pass only

If—and only if—the primary 2015 gate passes, calculate the following on the frozen 2015 candidate.

### 1. Payout sensitivity

Reprice the same settled outcomes at:

```text
80%
82%
90%
```

The robustness requirement is that expectancy at **80% payout remains > 0**.

### 2. Additional entry delay

Evaluate the same model and threshold with:

```text
entry_offset_bars = 2
expiry_bars = 3
```

Delay robustness requires:

- at least 150 resolved trades;
- expectancy > 0 at 82%;
- Wilson lower bound > 54.9451%.

### 3. Non-overlapping execution

Evaluate the primary 1-bar entry rule with:

```text
allow_overlapping_positions = False
cooldown_bars = 0
```

Non-overlap robustness requires:

- at least 150 resolved trades;
- expectancy > 0 at 82%;
- Wilson lower bound > 54.9451%.

### 4. Dependence-aware expectancy bootstrap

Run 5,000 moving-block bootstrap simulations at each fixed block size:

```text
5
10
20
```

The robustness requirement is that the 2.5th-percentile expectancy is strictly > 0 for **all three** block sizes.

An ordinary 5,000-simulation bootstrap may also be reported as descriptive context but does not replace the moving-block requirements.

### 5. Direction and month

Direction and calendar-month performance may be reported **only after the primary replication passes**. They are descriptive diagnostics and cannot alter the candidate or final replication classification.

## Classification

After the one-shot 2015 evaluation:

- `rejected_replication` — primary replication gate fails.
- `replicated_primary_but_fragile` — primary gate passes but one or more preregistered robustness requirements fail.
- `replicated_and_robust_regular_fx_candidate` — primary gate and every robustness requirement above pass.

No additional 2015 test is permitted after any of these classifications merely to improve the result.

## Interpretation limits

Even `replicated_and_robust_regular_fx_candidate` means only that a frozen statistical candidate survived an independent regular-FX year under the stated hypothetical payout economics.

It does **not** establish:

- Pocket Option/OTC performance;
- broker-execution equivalence;
- future profitability;
- a guaranteed win rate;
- permission to market the model as guaranteed or near-guaranteed income.

Pocket-specific evidence requires broker-observed Pocket candles, contemporaneous payout observations, the same chronological research discipline, and prospective demo forward testing.