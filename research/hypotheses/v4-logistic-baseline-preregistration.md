# V4 Preregistration — Causal Logistic Probability Baseline

Status: **PREREGISTERED BEFORE ANY 2016 V4 MODEL OUTCOME IS INSPECTED**

## Purpose

V1–V3 hand-written rule families did not survive the project’s confirmatory standards. V4 changes the research method rather than continuing to tune indicator thresholds: use one simple, interpretable supervised classifier to estimate the probability of an upward expiry from a fixed causal feature set.

The model is intentionally Logistic Regression. More complex learners are prohibited in V4. They may only become a later hypothesis if this baseline establishes a useful comparison.

## Dataset

Discovery/validation/locked-test year:

- Provider: FXCM public candle archive
- Symbol: EURUSD
- Timeframe: 1 minute
- Year: **2016**
- Price: midpoint of FXCM bid/ask OHLC
- Timestamps: UTC

Chronological split:

```text
development = first 60%
validation  = next 20%
locked test = final 20%
```

2015 is reserved as a fresh independent replication year if a 2016 candidate passes the locked test. Do not inspect or optimize a V4 strategy on 2015 before a 2016 candidate is frozen.

## Settlement convention

For a feature row at base bar `t`:

```text
entry = open of t + 1
exit  = close of t + expiry_bars
tie   = entry == exit
```

This is the same next-bar execution convention used by the Confluence Lab backtester.

Targets:

```text
up   -> 1
down -> 0
tie/out-of-bounds -> missing training label
```

Tie rows may be omitted from **model fitting**, but must not be excluded from prediction or backtest eligibility using future knowledge.

## Fixed feature set

Use exactly the feature list defined by `confluence_lab.ml.ML_FEATURE_COLUMNS` at preregistration:

```text
return_1
return_3
return_5
body_atr
range_atr
upper_wick_ratio
lower_wick_ratio
ema_spread_atr
ema20_slope_atr
ema50_slope_atr
distance_ema20_atr
rsi_14
macd_hist_atr
adx_14
atr_percentile_100
bb_position
atr_ratio_5_50
bb_width_percentile_200
range_position_20
htf_5_trend
htf_15_trend
htf_5_return_1
htf_15_return_1
utc_hour_sin
utc_hour_cos
utc_weekday_sin
utc_weekday_cos
```

All higher-timeframe inputs must come only from the previous completed HTF bar. No future candle, future payout, or current incomplete HTF bar may enter a feature.

## Fixed model

```text
Pipeline:
  StandardScaler
  LogisticRegression

LogisticRegression:
  C = 1.0
  penalty = l2
  solver = lbfgs
  max_iter = 1000
  class_weight = None
```

No coefficient-based feature deletion, feature selection, PCA, polynomial features, interactions, calibration model, alternative regularization, or hyperparameter search is allowed in V4.

## Development probability generation

Threshold selection must use expanding-window **out-of-fold** development probabilities, not probabilities from observations used to fit that fold.

```text
n_splits = 5
purge gap = entry_offset_bars + expiry_bars - 1
```

The purge prevents a training target from reaching into the following test fold’s time region.

## Frozen candidate space

Expiry candidates:

```text
1, 2, 3, 5 bars
```

Probability thresholds:

```text
0.550
0.575
0.600
0.625
0.650
```

Signal rule for threshold `q`:

```text
P(up) >= q       -> CALL
P(up) <= 1 - q   -> PUT
otherwise        -> NO TRADE
```

Total permitted development candidate combinations:

```text
4 expiries x 5 thresholds = 20
```

No other threshold or expiry may be added after 2016 development results are inspected.

## Development selection rule

Hypothetical payout for the regular-FX benchmark:

```text
82%
break-even = 1 / 1.82 = 54.945054945%
```

A development OOF candidate is eligible only if:

1. at least 300 settled trades;
2. expectancy at 82% payout > 0.

Among eligible candidates, select the one with the highest 95% Wilson lower bound. Ties are resolved deterministically by lower expiry, then higher probability threshold.

If no candidate is eligible, V4 status is `no_development_candidate` and validation/locked test are not used for strategy rescue.

## Model refit after development selection

After selecting exactly one `(expiry, threshold)` pair, fit the same fixed pipeline once on all feature-valid, labeled development rows for that expiry.

Do not fit on validation or locked-test labels.

## Validation gate

Predict validation probabilities using the development-fitted model and frozen threshold.

The locked test may be opened only when validation has:

1. at least 150 settled non-tie trades;
2. expectancy > 0 at hypothetical 82% payout;
3. 95% Wilson lower bound > 54.945054945%.

Failure yields `rejected_validation`. Do not tune the model or threshold against the failed validation slice and call the same protocol fresh.

## Locked-test evidence rule

If validation passes, evaluate once on the final 20% 2016 locked slice using the unchanged development-fitted model and threshold.

A V4 locked candidate passes only if:

1. at least 150 settled non-tie trades;
2. expectancy > 0;
3. 95% Wilson lower bound > break-even.

## Secondary robustness

A locked-test pass is still not enough for a trading claim. For a candidate that reaches the locked test, report without changing the primary result:

- 80% payout repricing;
- `entry_offset_bars=2` using the same model and probability threshold, with features observed at the original decision bar;
- non-overlapping-position settlement;
- CALL and PUT separately;
- monthly stability;
- ordinary bootstrap expectancy;
- moving-block bootstrap expectancy at block sizes 5, 10 and 20.

These checks cannot rescue primary failure.

## Independent replication

Only if the 2016 locked-test rule passes may the exact feature set, model, expiry and probability threshold be frozen and evaluated on **2015** as a no-tuning replication.

A 2015 replication must be preregistered before its outcome is inspected.

## Interpretation

This study uses regular FXCM EUR/USD prices with a hypothetical 82% binary-style payout. It is not Pocket Option or OTC evidence.

A pass would justify further research, including independent replication and Pocket-specific prospective data. It would not imply guaranteed returns or a promised future win rate.
