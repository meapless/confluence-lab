# V5 Dukascopy 2015 Quote-Source Robustness — Protocol Amendment 1

Status: **FROZEN BEFORE ANY COMPLETE DUKASCOPY 2015 DATASET OR V5 SOURCE-TEST METRIC EXISTS**

Parent preregistration: `research/hypotheses/v5-dukascopy-2015-source-robustness-preregistration.md`

## Why this amendment exists

The original preregistration correctly specified the scientific source as Dukascopy raw bid/ask ticks reconstructed to midpoint 1-minute OHLC, but its implementation section incorrectly described the raw archive as one daily tick BI5 object.

Attempts 1–3 never produced a complete Dukascopy 2015 candle dataset, JSON report, primary V5 metric, or robustness metric:

- attempt 1: HTTP 503 execution failure;
- attempt 2: socket read timeout execution failure;
- attempt 3: HTTP 301 redirect-loop execution failure.

The attempt-3 root-cause audit established that the adapter was constructing a non-canonical daily tick path. Dukascopy raw ticks are stored as **hourly** BI5 objects under each UTC day, and the millisecond field inside each object is relative to that hour.

Because no V5 source-test outcome has been observed, this correction cannot be informed by trading performance.

## Corrected source construction

The evaluation source remains the full UTC calendar year 2015 and remains raw Dukascopy bid/ask ticks.

The corrected deterministic construction is:

1. request canonical hourly BI5 objects from `https://datafeed.dukascopy.com/datafeed`;
2. use path shape `SYMBOL/YYYY/MM0/DD/HHh_ticks.bi5`, with zero-indexed month;
3. retain each hourly object's UTC hour, URL, byte count, status and SHA-256 digest;
4. decode the BI5 millisecond offset relative to the object's UTC hour;
5. derive midpoint `(bid + ask) / 2` per tick;
6. resample each hourly tick object to UTC 1-minute OHLC;
7. discard ticks after that hourly object is resampled;
8. concatenate only 1-minute candles and validate/sort the final frame;
9. apply the same gap-safe label and settlement semantics already frozen for V5.

A missing hourly object may be classified as missing only on HTTP 404. Transient 429/5xx, URL-level failures and read timeouts receive bounded retries; exhausted failures abort the dataset instead of being silently skipped.

## Transport-only batching

A full year contains thousands of hourly objects. To make the canonical raw-tick route practical without changing source content:

- fetch concurrency is fixed at `max_workers = 4`;
- requests are grouped in chronological batches of `24` hours;
- batches preserve input order;
- a `0.25` second pause is used between batches;
- decoding/resampling remains object-by-object after fetch;
- the full year of raw ticks is never retained in memory.

Concurrency and batching affect transport only. They do not change timestamps, price construction, features, signals, labels, settlement, or evidence gates.

## Frozen scientific rules — unchanged

Everything below remains exactly as preregistered:

```text
training provider        FXCM 2014
training fingerprint     3588398a302084a360b8eea1cfce3676c68c61e4e5d62b6b9e45e32c0f133f71
model                     HistGradientBoostingClassifier
learning_rate             0.05
max_iter                  200
max_leaf_nodes            15
max_depth                 None
min_samples_leaf          100
l2_regularization         1.0
early_stopping            False
random_state              42
expiry_bars               3
entry_offset_bars         1
probability_threshold     0.625
fixed payout              0.82
allow overlap             True
cooldown                  0
require contiguous bars   True
minimum resolved trades   150
minimum expectancy        > 0
minimum Wilson lower      > 1/(1+0.82)
```

The existing post-pass robustness requirements are unchanged.

## No-rescue rule

No Dukascopy 2015 threshold, expiry, direction, month, session, volatility subgroup, feature selection, model parameter, or transport behavior may be chosen based on V5 trading outcomes. A complete corrected run receives the preregistered classification as-is.

This amendment corrects the source adapter so that the originally intended raw-tick experiment is actually executable; it does not redefine what constitutes success.
