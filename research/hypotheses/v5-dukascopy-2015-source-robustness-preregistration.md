# V5 Dukascopy 2015 Quote-Source Robustness — Preregistration

Status: **PREREGISTERED BEFORE ANY DUKASCOPY 2015 DATA IS ACCESSED FOR THIS STUDY**

## Purpose

V5 has passed a no-tuning independent-year replication on FXCM EUR/USD 2015 after being selected and locked on FXCM 2014.

This study asks a different question:

> Does the exact frozen V5 model remain positive when the 2015 market path is reconstructed from an independently maintained Dukascopy tick/quote feed instead of FXCM candles?

This is **quote-source robustness**, not a second independent temporal replication. Calendar year 2015 has already been seen through the authoritative FXCM replication and must not be described as fresh time-domain evidence.

## Frozen training source

The model is fit exactly as in the authoritative V5 2015 replication:

- training provider: FXCM public candle archive;
- symbol: EURUSD;
- training year: 2014;
- required training fingerprint: `3588398a302084a360b8eea1cfce3676c68c61e4e5d62b6b9e45e32c0f133f71`;
- fit on all feature-valid, gap-safe labeled 2014 rows;
- no training on Dukascopy data.

If the FXCM 2014 fingerprint does not match exactly, stop before accessing Dukascopy 2015.

## Frozen model

No model search is allowed.

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
```

Use the exact existing `ML_FEATURE_COLUMNS`.

## Frozen signal/execution rule

```text
expiry_bars             3
entry_offset_bars       1
probability_threshold   0.625
CALL                     P(up) >= 0.625
PUT                      P(up) <= 0.375
NO TRADE                 otherwise
fixed payout scenario   0.82
allow overlap            True
cooldown                 0
require contiguous bars  True
```

No threshold, expiry, direction, session, month, volatility or feature filter may be changed based on Dukascopy 2015.

## Evaluation source

Provider: Dukascopy historical BI5 tick feed.

Interval: full calendar year 2015 UTC, requested as `[2015-01-01T00:00:00Z, 2016-01-01T00:00:00Z)`.

Construction:

1. download each daily BI5 object independently;
2. retain each raw object's URL, byte count and SHA-256 digest;
3. decode bid/ask ticks;
4. derive midpoint `(bid + ask) / 2` per tick;
5. resample midpoint ticks to UTC 1-minute OHLC;
6. process one day at a time so a full year of ticks is never retained in memory;
7. concatenate only daily 1-minute candles;
8. run normal dataset diagnostics;
9. use gap-safe signal/entry/expiry eligibility.

HTTP 404 days are retained in provenance as missing source objects. Other HTTP/network failures must fail the study rather than silently skip data.

## Primary quote-source robustness gate

The frozen candidate passes this source test iff the Dukascopy 2015 evaluation has all of:

1. at least **150 resolved non-tie trades**;
2. payout-adjusted expectancy at hypothetical 82% payout strictly greater than `0`;
3. 95% Wilson lower confidence bound strictly greater than the 82%-payout break-even rate:
   `1 / (1 + 0.82) = 54.9450549%`.

If the primary gate fails, classify:

`source_robustness_failed`

and do not tune/rescue using Dukascopy 2015 subgroups.

If it passes, classify at minimum:

`source_robustness_passed`

and the same post-pass stress tests below may be reported.

## Allowed post-pass robustness diagnostics

Only after the primary gate passes:

- reprice same outcomes at 80%, 82%, 90%; 80% expectancy must remain positive for the stronger classification;
- additional-entry-delay (`entry_offset_bars=2`) must have >=150 resolved, positive expectancy, and Wilson lower >54.9451%;
- non-overlapping execution must have >=150 resolved, positive expectancy, and Wilson lower >54.9451%;
- moving-block expectancy bootstrap with 5,000 simulations at block sizes 5, 10 and 20; every 2.5% bound must be >0;
- direction and month may be shown descriptively only.

If primary passes but any required post-pass robustness condition fails:

`source_robustness_passed_but_fragile`

If every required post-pass condition passes:

`source_robustness_passed_and_robust`

## Optional cross-provider agreement diagnostics

Because FXCM 2015 is already seen, it may be re-downloaded only for descriptive provider-comparison metrics after the Dukascopy primary result is fixed. Allowed descriptive measures include:

- minute timestamp overlap;
- absolute/relative OHLC deviation on shared timestamps;
- frozen-model signal count by provider;
- exact signal-direction agreement on common timestamps.

These metrics cannot change the Dukascopy primary classification.

## Interpretation boundary

Passing would strengthen evidence that V5 is not merely exploiting FXCM-specific candle construction or quote artifacts.

It would still **not** establish Pocket Option/OTC performance. Pocket-specific evidence requires Pocket-observed prices and contemporaneous payout observations, followed by prospective demo testing.
