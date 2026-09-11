# FXCM EURUSD 2015 — V5 Frozen Independent Replication

Status: **REPLICATED_AND_ROBUST_REGULAR_FX_CANDIDATE**

Authoritative workflow run: `34566625579`

Authoritative commit: `c5b4f4b6e7170d7fb5d522b26cf83e9ed8582542`

Authoritative artifact: `fxcm-eurusd-2015-v5-frozen-replication`

Artifact ID: `10186273292`

Artifact digest: `sha256:e566606c52a758d6186859d3ff79ceee71430604097cae1c3b0c172af701080b`

Preregistration: `research/hypotheses/v5-2015-replication-preregistration.md`

Parent 2014 result: `research/results/fxcm-2014-v5-histgb.md`

## Decision

The exact V5 candidate selected on 2014 and frozen before any 2015 access **passed the preregistered independent 2015 replication gate and every preregistered robustness requirement**.

This is the first Confluence Lab candidate to complete the following evidence chain on regular FXCM EUR/USD data:

```text
2014 development search
        -> 2014 validation pass
        -> 2014 locked-test pass
        -> 2014 payout/delay/non-overlap/bootstrap robustness
        -> model + expiry + threshold frozen before 2015 access
        -> full-year 2015 independent replication pass
        -> 2015 payout/delay/non-overlap/bootstrap robustness pass
```

The result is evidence for a reproducible **regular-FX research candidate under hypothetical binary-style payout assumptions**. It is not Pocket Option/OTC evidence and does not establish a guaranteed future win rate or guaranteed profitability.

## Reproducibility environment

The authoritative Actions job used:

```text
Ubuntu             24.04.5 LTS
Python             3.12.14
confluence-lab     0.5.0
numpy              2.5.3
pandas             3.0.5
scikit-learn       1.9.1
scipy              1.18.1
pyarrow            25.0.1
```

The pre-access test gate completed with **110 passed** tests before the frozen replication script was allowed to run.

## Frozen candidate

No 2015 hyperparameter, feature, expiry or probability-threshold search occurred.

```text
model                  HistGradientBoostingClassifier
learning_rate          0.05
max_iter               200
max_leaf_nodes         15
max_depth              None
min_samples_leaf       100
l2_regularization      1.0
early_stopping         False
random_state           42

expiry_bars            3
entry_offset_bars       1
probability_threshold   0.625
CALL                    P(up) >= 0.625
PUT                     P(up) <= 0.375
NO TRADE                otherwise
fixed payout scenario   0.82
allow overlap           True
cooldown                0
require contiguous bars True
```

The feature vector was the exact frozen V4/V5 `ML_FEATURE_COLUMNS`; no feature selection or new interactions were added for 2015.

## 2014 training provenance verification

The preregistration required the 2014 training history to match the authoritative V5 source fingerprint before the final model could be fit and before 2015 could be accessed.

```text
expected 2014 fingerprint
3588398a302084a360b8eea1cfce3676c68c61e4e5d62b6b9e45e32c0f133f71

observed 2014 fingerprint
3588398a302084a360b8eea1cfce3676c68c61e4e5d62b6b9e45e32c0f133f71

fingerprint verified   YES
2014 rows              368,878
valid labeled rows     349,962
class DOWN rows        175,528
class UP rows          174,434
```

The final V5 model was fit once on all feature-valid, gap-safe labeled 2014 observations only after this provenance check passed.

## 2015 replication dataset

Source: FXCM public EUR/USD M1 candle archive, midpoint derived from bid/ask OHLC.

```text
rows                    369,856
start                    2015-01-04 22:00:00 UTC
end                      2015-12-31 18:02:00 UTC
weekly files downloaded 52
missing archive weeks   [53]
duplicate timestamps    0
invalid OHLC rows        0
non-weekend missing min 971
gap-safe settlement      enabled
```

Dataset fingerprint:

`54b07d270522f0433d45dd2f3be9f6943b7b149fbebf585d5490778fe42ad3ec`

The authoritative JSON artifact retains each downloaded weekly file URL, byte size and SHA-256 hash.

## Primary independent replication

Preregistered gate at hypothetical 82% payout:

1. at least 150 resolved non-tie trades;
2. expectancy strictly greater than zero;
3. 95% Wilson lower bound strictly greater than `1 / 1.82 = 54.9451%`.

Observed result:

```text
trades                  4,076
resolved non-ties       4,050
wins                    2,466
losses                  1,584
ties                    26
win rate                60.8889%
95% Wilson lower        59.3763%
95% Wilson upper        62.3808%
break-even win rate     54.9451%
expectancy / trade      +0.107488 units
total P&L               +438.12 units
max drawdown            17.58 units
max losing streak       13
max winning streak      17
```

**Primary replication gate: PASS.**

The Wilson lower bound exceeds the hypothetical 82%-payout break-even rate by approximately **4.43 percentage points**.

## Payout robustness

The same settled 2015 outcomes were repriced without changing any signal:

| Fixed payout | Break-even WR | Observed WR | Expectancy/trade | Total P&L | Result |
|---|---:|---:|---:|---:|---|
| 80% | 55.5556% | 60.8889% | +0.095388 | +388.80 | PASS |
| 82% | 54.9451% | 60.8889% | +0.107488 | +438.12 | PASS |
| 90% | 52.6316% | 60.8889% | +0.155888 | +635.40 | PASS |

Preregistered 80%-payout positive-expectancy requirement: **PASS**.

## Additional entry-delay robustness

The frozen model and 0.625 threshold were evaluated with one additional entry bar (`entry_offset_bars=2`) without retraining.

```text
trades                  4,069
resolved                4,038
win rate                58.9648%
95% Wilson lower        57.4398%
expectancy / trade      +0.072603
total P&L               +295.42
max drawdown            32.64
```

Full preregistered evidence gate: **PASS**.

## Non-overlapping execution robustness

The primary one-bar entry rule was rerun with overlapping positions disabled and no cooldown.

```text
trades                  2,563
resolved                2,547
win rate                60.2277%
95% Wilson lower        58.3129%
expectancy / trade      +0.095544
total P&L               +244.88
max drawdown            12.66
```

Full preregistered evidence gate: **PASS**.

## Dependence-aware bootstrap

5,000 moving-block bootstrap simulations were run at each preregistered block size.

| Block size | 2.5% EV | Median EV | 97.5% EV | P(EV > 0) | Result |
|---|---:|---:|---:|---:|---|
| 5 | +0.075716 | +0.107117 | +0.138008 | 100% | PASS |
| 10 | +0.075293 | +0.107699 | +0.137608 | 100% | PASS |
| 20 | +0.075450 | +0.106180 | +0.137275 | 100% | PASS |

All three lower confidence bounds are strictly positive: **PASS**.

For descriptive comparison, the ordinary 5,000-simulation bootstrap produced a 2.5% expectancy bound of **+0.079357** and `P(EV > 0) = 100%` in the resamples.

## Direction diagnostics

These were permitted only because the primary replication passed. They are descriptive and do not modify the frozen candidate.

```text
CALL
resolved                1,654
win rate                59.7944%
Wilson lower            57.4114%
expectancy              +0.087940
P&L                     +145.98

PUT
resolved                2,396
win rate                61.6444%
Wilson lower            59.6802%
expectancy              +0.120919
P&L                     +292.14
```

Both directions were positive without applying any direction filter.

## Calendar-month diagnostics

All 12 calendar months had positive point-estimate expectancy under the hypothetical 82% payout. Monthly win rates ranged from approximately **58.28% to 64.62%** and monthly point-estimate expectancy ranged from approximately **+0.0602 to +0.1749 units/trade**.

These monthly slices are descriptive. Individual monthly Wilson intervals are not used as independent passes/fails and no month is removed from the primary replication.

## Final preregistered classification

Every required post-primary check passed:

```text
primary independent replication gate          PASS
80% payout expectancy > 0                     PASS
additional-entry-delay evidence gate          PASS
non-overlapping execution evidence gate       PASS
block bootstrap size 5 lower EV > 0           PASS
block bootstrap size 10 lower EV > 0          PASS
block bootstrap size 20 lower EV > 0          PASS
```

Classification:

**`replicated_and_robust_regular_fx_candidate`**

## What this result establishes

The project now has evidence that a fixed nonlinear model learned on 2014 regular EUR/USD data can produce a selective short-horizon signal whose performance remained statistically and economically positive in a completely independent 2015 regular-FX year under the stated hypothetical fixed-payout model.

The independent-year result is materially stronger than a tuned backtest because:

- 2015 was preregistered before access;
- model hyperparameters were frozen;
- feature list was frozen;
- expiry and confidence threshold were frozen;
- the model was trained only on 2014;
- no 2015 development or validation search occurred;
- the 2015 result survived payout, execution-delay, overlap and serial-dependence stress tests.

## What this result does **not** establish

This result does **not** prove:

- Pocket Option OTC prices behave like regular EUR/USD;
- Pocket fills/timestamps match FXCM midpoint candles;
- historical or live Pocket payouts are 82%;
- the model will preserve a 60.9% future win rate;
- future profitability is guaranteed;
- the result is appropriate to market as guaranteed or near-guaranteed income.

The 82% payout is a hypothetical research assumption. Pocket-specific expectancy requires contemporaneous Pocket payout observations.

## Evidence policy after this result

2015 is now permanently **seen** and must never again be used as a fresh replication year for a modified V5 hypothesis.

Do not tune V5 based on 2015 direction, month, confidence, volatility or session diagnostics and then describe another 2015 evaluation as independent.

The appropriate next evidence steps are:

1. preserve this exact candidate and result;
2. perform cross-source replication on regular EUR/USD without tuning where useful;
3. accumulate broker-observed Pocket regular/OTC candles plus timestamped payout observations;
4. test any Pocket application chronologically with payout-aware economics;
5. run a prospective demo forward test using an append-only candidate/outcome ledger;
6. only after prospective evidence consider any live-use or public performance claim.

The objective remains falsification first: this replicated regular-FX result earns further testing, not certainty.
