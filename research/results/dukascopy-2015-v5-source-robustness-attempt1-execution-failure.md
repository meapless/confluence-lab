# Dukascopy EURUSD 2015 — V5 Source Robustness Attempt 1 Execution Failure

Status: **EXECUTION_FAILURE — NO TRADING RESULT PRODUCED**

Workflow run: `34567258684`

Job: `103161814594`

Commit: `6f4f2dbf58a1b339ca198cac7b7ae54037b0a043`

Preregistration: `research/hypotheses/v5-dukascopy-2015-source-robustness-preregistration.md`

## What happened

The one-shot quote-source robustness workflow passed its pre-access research test gate and then began the preregistered Dukascopy 2015 source evaluation.

Pre-access CI result:

```text
119 passed, 9 warnings
```

During daily BI5 retrieval, Dukascopy returned a transient HTTP `503 Service Unavailable`. The downloader intentionally raised non-404 HTTP failures rather than silently skipping source data, so the study stopped before a complete 2015 dataset or any trading-performance report was produced.

The relevant exception was:

```text
urllib.error.HTTPError: HTTP Error 503: Service Unavailable
```

No `dukascopy-eurusd-m1-2015-v5-source-robustness.json` artifact existed, and therefore no V5 source-test metrics were calculated or inspected.

## Scientific interpretation

This attempt is **not** a failed V5 trading hypothesis and must not be counted as `source_robustness_failed`.

It is an operational transport failure only.

However, because the source-evaluation step had begun, Dukascopy 2015 is no longer described as untouched/unaccessed for this study. The scientific protocol remains frozen from the preregistration and may not be changed in response to this execution failure.

## Allowed recovery

A retry is allowed only after a transport-layer resilience change that does not alter:

- the V5 model or hyperparameters;
- the FXCM 2014 training fingerprint requirement;
- the feature list;
- the 3-bar expiry;
- the 0.625 probability threshold;
- signal direction rules;
- gap-safe target/settlement rules;
- the hypothetical 82% primary payout;
- the primary evidence gate;
- the post-pass robustness requirements;
- the rule that exhausted network failures fail the study rather than silently skipping data.

The permitted engineering fix is bounded retry/backoff for transient HTTP/network failures such as 429/500/502/503/504. HTTP 404 may continue to be recorded as a missing source object. If retries are exhausted, the downloader must still raise and the study must remain incomplete.

## Audit policy

The next source-test attempt must reference this failed run and the transport-only code change in Git history. It must use the exact preregistered V5 candidate and classification rules.
