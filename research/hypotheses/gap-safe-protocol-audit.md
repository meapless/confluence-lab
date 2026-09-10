# Gap-Safe Settlement Protocol Audit

Status: **PREREGISTERED BEFORE CORRECTED-RUN OUTCOMES**

Engine correction merged in commit `c42abcdcc46271707dcdf0c7e21c5e19a61f6375`.

## Reason for the audit

The original backtester and V4 target generator advanced short-expiry horizons by available row number. On datasets containing weekend closures or missing candles, an intended 1–5 minute horizon could therefore cross a discontinuity and settle hours or days later.

The corrected engine requires every timestamp step from signal through entry and expiry to match the inferred candle interval. Gap-crossing trades are excluded. The V4 training target is also `NaN` for gap-crossing horizons so the model cannot learn from impossible short-expiry outcomes.

## Audit principle

This correction is **not permission to retune prior hypotheses**.

For every rerun below:

- same source and year;
- same strategy family or fixed hypothesis;
- same parameter grid, if a grid existed;
- same expiries;
- same hypothetical fixed payout;
- same development / validation / locked-test split;
- same minimum trade counts;
- same search objective;
- same confidence and expectancy gates;
- no threshold or feature changes based on the previous outcome.

The only methodological change is gap-safe time-contiguity enforcement.

## Rerun set

### 2019 V1 families

Run `scripts/run_fxcm_2019_benchmark.py` on all registered V1 families using the corrected selector and gap-safe settlement. This re-audits Trend Pullback, Range Reversion and Breakout. The original Range near-miss must not receive preferential tuning.

### 2018 frozen V1 Range replication

Run the exact frozen 2019 Range candidate through `scripts/run_fxcm_2018_range_replication.py` unchanged.

### 2018 V2 preregistered search

Run `scripts/run_fxcm_2018_v2_benchmark.py` unchanged. If candidate selection changes because gap-crossing trades were removed, the corrected development search result governs. Validation and locked access remain subject to the existing gates.

### 2017 V3A

Run the exact CALL-only Range Reversion replication through `scripts/run_fxcm_2017_call_only_range_replication.py` unchanged.

### 2017 V3B

Run the exact moderate-volatility Sweep Reversal replication through `scripts/run_fxcm_2017_moderate_vol_sweep_replication.py` unchanged.

### 2016 V4 logistic baseline

Run `scripts/run_fxcm_2016_v4_logistic.py` with the same frozen feature list, model, four expiries and five confidence thresholds. Gap-safe targets and settlement are now mandatory. The pre-fix V4 result is preserved separately and is not used to alter the corrected run.

## Interpretation

A corrected result can strengthen or weaken an old point estimate, but it does not reset previously seen data into a new independent holdout. These reruns are **methodological audits**, not fresh replications.

If a previously failed strategy passes only after the correction, it remains hypothesis-generating unless it subsequently survives an untouched period. If a previous pass/near-miss weakens, the corrected result supersedes it for future research decisions.

2015 remains untouched. It will not be opened merely because this audit changes a historical result.

## Reporting

Every corrected artifact must use a distinct `gap-safe` name and retain source provenance. Human-readable summaries should explicitly compare the corrected result with the corresponding pre-fix result where available.

No regular-FX result in this audit is Pocket Option/OTC evidence. The 82% payout remains a hypothetical economics assumption.