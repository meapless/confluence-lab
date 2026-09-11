# Dukascopy EURUSD 2015 — V5 Source Robustness Attempt 2 Execution Failure

Status: **EXECUTION_FAILURE — NO TRADING RESULT PRODUCED**

Workflow run: `34567563016`

Job: `103162686998`

Commit: `b9cad1be316c30b12ccf35327f3eebdd6b4d2754`

Attempt 1 record: `research/results/dukascopy-2015-v5-source-robustness-attempt1-execution-failure.md`

Preregistration: `research/hypotheses/v5-dukascopy-2015-source-robustness-preregistration.md`

## What happened

Attempt 2 included the tested bounded retry/backoff policy for transient HTTP 429/500/502/503/504 responses. The scientific V5 model and evaluation protocol were unchanged.

The workflow again passed the complete pre-access test gate:

```text
122 passed, 9 warnings
```

The Dukascopy source step then ran for approximately three minutes before a redirected HTTPS response timed out while reading a daily BI5 object:

```text
TimeoutError: The read operation timed out
```

The timeout propagated from `urllib.request.urlopen()` through `_open_bi5_once()`. At this point the retry wrapper handled `HTTPError` and `URLError`, but Python's socket/SSL read timeout surfaced as `TimeoutError`, so it bypassed the retry branch.

No complete Dukascopy 2015 candle dataset was constructed. No source-test metrics were produced or inspected. No JSON result artifact existed.

## Scientific interpretation

This remains an **operational transport failure**, not `source_robustness_failed` and not evidence for or against V5.

Dukascopy 2015 is already considered accessed by this study because attempts 1 and 2 entered the source-evaluation step. The frozen scientific protocol may not be modified in response to these transport failures.

## Allowed recovery

A subsequent attempt may extend the existing bounded transport retry policy to include `TimeoutError` from response reads and may lengthen the per-request network timeout. These are transport-only changes.

The following remain frozen:

- exact FXCM 2014 training fingerprint;
- HistGradientBoosting model specification;
- feature list;
- expiry = 3 bars;
- threshold = 0.625;
- entry offset = 1 bar;
- CALL/PUT/NO-TRADE mapping;
- gap-safe label and settlement rules;
- hypothetical primary payout = 82%;
- primary evidence gate;
- all post-pass robustness requirements;
- no silent skipping of exhausted network failures.

If the bounded retry budget is exhausted, the study must still stop incomplete rather than omit the affected source day.
