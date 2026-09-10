# V5 — Fixed HistGradientBoosting Baseline

Status: **PREREGISTERED BEFORE ANY 2014 OUTCOME IS ACCESSED**

## Purpose

V1–V4 did not produce a validated edge under the research gates. V5 tests whether a modest nonlinear classifier can extract useful interactions from the **same causal feature set** without widening the feature universe or conducting a model-hyperparameter search.

This is a new model-family hypothesis, not a rescue/tuning pass over the previously seen 2016–2019 outcomes.

## Data chronology

- Discovery / development / validation / locked-test year: **FXCM EUR/USD M1, 2014**.
- 2015 remains **untouched** unless V5 passes its locked 2014 gate.
- 2016–2019 are already seen and must not be used as V5 confirmation data.
- Pocket Option/OTC data is a separate future evidence stream and must not be inferred from FXCM results.

## Fixed feature set

Use the exact `ML_FEATURE_COLUMNS` already defined for V4. No feature selection, feature expansion, or post-hoc removal is permitted in V5.

Features remain causal and include price returns, ATR-normalized candle/EMA/momentum structure, RSI, ADX, volatility/location context, completed 5m/15m context, and cyclical UTC calendar encodings.

## Gap-safe target and settlement

Use the corrected gap-safe engine merged before this preregistration.

An expiry label or trade is invalid if any timestamp step from signal through next-bar entry and expiry crosses a missing candle interval, market closure, or weekend discontinuity.

Gap-crossing target rows are `NaN` for fitting. They are not removed from prediction eligibility based on their future outcome.

## Fixed model

One model configuration only:

```text
sklearn.ensemble.HistGradientBoostingClassifier
learning_rate = 0.05
max_iter = 200
max_leaf_nodes = 15
max_depth = None
min_samples_leaf = 100
l2_regularization = 1.0
early_stopping = False
random_state = 42
```

No hyperparameter optimization is allowed on 2014.

Scaling is not required for this tree-based model.

## Development protocol

Chronological split of the 2014 year:

```text
60% development
20% validation
20% locked test
```

For development, generate probabilities through **5-fold expanding-window out-of-fold prediction** using `TimeSeriesSplit` with a purge gap equal to the expiry label horizon.

Search only:

```text
expiry bars = [1, 2, 3, 5]
probability threshold = [0.55, 0.575, 0.60, 0.625, 0.65]
```

Total development cells: **20**.

A probability `p >= threshold` emits CALL. A probability `p <= 1 - threshold` emits PUT. Values in between emit NO TRADE.

## Development eligibility and selection

A development cell is eligible only if:

- at least **300 trades** are generated;
- payout-adjusted expectancy at hypothetical 82% payout is strictly positive.

Among eligible cells choose the highest 95% Wilson lower bound.

Tie-breaks, in order:

1. lower expiry;
2. higher confidence threshold.

The complete 20-cell development search must be retained in the report even if no candidate is eligible.

## Validation gate

Freeze model family, hyperparameters, expiry and confidence threshold after development.

The selected development-fitted model is used for **prediction only** on validation. No validation fitting, threshold search, calibration or feature change is permitted.

Validation passes only if:

- at least **150 resolved non-tie trades**;
- expectancy at hypothetical 82% payout > 0;
- 95% Wilson lower bound > `1 / (1 + 0.82)` = approximately **54.9451%**.

If validation fails, the locked 2014 slice remains unopened.

## Locked-test gate

If and only if validation passes, evaluate the frozen candidate once on the locked 2014 slice.

Locked evidence passes only if:

- at least **150 resolved non-tie trades**;
- expectancy > 0 at hypothetical 82% payout;
- 95% Wilson lower bound > 54.9451%.

A locked pass still does not establish a Pocket edge or guarantee future profitability.

## Robustness after locked pass

Only after a locked pass, calculate:

- 80%, 82%, 90% payout sensitivity;
- one additional bar of entry delay;
- non-overlapping execution;
- moving-block bootstrap expectancy using block sizes 5, 10 and 20;
- performance by direction and calendar month.

These diagnostics may reject a fragile candidate but may not be used to modify it and retry the same locked slice.

## 2015 replication policy

Only if the 2014 locked test passes:

1. keep feature list, model hyperparameters, expiry and threshold frozen;
2. refit the same model specification on all feature-valid, labeled **2014** observations;
3. evaluate once on untouched **2015** data with no search;
4. require the same sample-size, expectancy and Wilson-lower evidence gate;
5. apply robustness diagnostics without retuning.

If the 2015 replication fails, V5 is rejected as non-replicated evidence.

## Interpretation

The 82% payout is hypothetical. FXCM midpoint candles are regular-FX research data, not Pocket Option/OTC prices. Passing this study would justify continued investigation only; it would not justify claims of guaranteed returns, a fixed future win rate, or Pocket-specific performance.