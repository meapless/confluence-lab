# Dukascopy EURUSD 2015 — V5 Source Robustness Attempt 4 Execution Failure

Status: **EXECUTION_FAILURE — NO TRADING RESULT PRODUCED**

Workflow run: `34569412210`

Job: `103168121902`

Workflow commit: `cf53438f62622dbe69bc564bf619a67e30149861`

Protocol: `v5-dukascopy-2015-source-robustness-2`

Protocol amendment: `research/hypotheses/v5-dukascopy-2015-source-robustness-protocol-amendment-1.md`

## What happened

Attempt 4 was the first source run using the corrected canonical hourly raw-tick archive. It passed the complete pre-access test gate (`126 passed`) and entered the frozen source-evaluation step at approximately `2026-09-11T06:19:44Z`.

The canonical hourly source build proceeded until approximately `2026-09-11T06:23:58Z`, when one hourly request exhausted the existing bounded transport-retry budget. The terminal exception was:

```text
urllib.error.URLError: <urlopen error timed out>
```

The report file had not yet been written, so artifact upload found no JSON report.

## Scientific interpretation

This is a source-acquisition execution failure, **not** a V5 source-robustness failure. No complete Dukascopy 2015 dataset, primary trading metric, or post-pass robustness metric was produced.

The frozen model, feature set, 3-bar expiry, 0.625 probability threshold, hypothetical 82% payout, overlap rule, gap-safe settlement, minimum sample requirement, expectancy gate and Wilson-confidence gate remain unchanged.

## Operational follow-up permitted

The canonical raw archive contains thousands of hourly objects. Aborting the whole year immediately when one object exhausts a short retry window wastes successfully retrieved data and causes subsequent attempts to repeat the same successful requests.

A transport-only completion strategy may therefore:

1. preserve successfully fetched/decoded source objects within the run;
2. defer objects that exhaust their local transport retries;
3. continue fetching other required objects;
4. retry only the deferred objects in later completion passes;
5. abort the study if any required non-404 object still cannot be acquired after the frozen completion-pass budget;
6. emit an explicit execution-status JSON artifact even on incomplete acquisition.

This cannot silently omit unavailable data and cannot inspect V5 trading outcomes before deciding which source objects to retry. It changes source-delivery reliability only, not the experiment's market-data definition or statistical hypothesis.
