# Dukascopy EURUSD 2015 — V5 Source Robustness Attempt 3 Execution Failure

Status: **EXECUTION_FAILURE — NO TRADING RESULT PRODUCED**

Workflow run: `34568459430`

Job: `103165298679`

Workflow commit: `519623c3819ba3ad3e3b43245db6c2e5663efc4c`

## What happened

Attempt 3 passed the complete pre-access test gate (`124 passed`) and entered the preregistered frozen V5 source-evaluation step. The step ran from approximately `2026-09-11T06:05:35Z` until `2026-09-11T06:12:07Z`, then terminated while downloading the Dukascopy archive.

The terminal exception was:

```text
urllib.error.HTTPError: HTTP Error 301: The HTTP server returned a redirect error that would lead to an infinite loop.
The last 30x error message was:
Moved Permanently
```

The JSON report path did not exist afterward, so the artifact upload also failed with `No files were found`.

## Scientific interpretation

This run produced **no complete Dukascopy 2015 dataset and no V5 trading metrics**. It therefore cannot be classified as a source-robustness pass or failure.

No model parameter, feature, expiry, probability threshold, payout assumption, evidence gate, subgroup, or strategy rule was changed in response to this run.

## Root-cause audit triggered

The failure prompted an audit of the Dukascopy adapter itself. That audit found that the existing implementation constructed a day-level tick URL of the form:

```text
.../EURUSD/YYYY/MM/DD_ticks.bi5
```

whereas Dukascopy's canonical raw tick archive is organized as **hourly** BI5 objects under a day directory:

```text
.../EURUSD/YYYY/MM/DD/HHh_ticks.bi5
```

The tick record's millisecond field is relative to the hour, not an invented daily aggregate object. The source adapter must therefore be corrected before another source-robustness run is scientifically interpretable.

Because attempts 1–3 never produced a complete source dataset or any model metric, correcting this acquisition bug does not use observed trading outcomes to tune the candidate. The correction must nevertheless be documented and tested before the next attempt.
