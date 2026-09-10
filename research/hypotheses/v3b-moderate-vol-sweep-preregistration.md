# V3B Preregistration — Moderate-Volatility Sweep Reversal

Status: **PREREGISTERED BEFORE INSPECTION OF ANY 2017 STRATEGY RESULT**

## Origin and contamination status

The V2 Sweep Reversal family was selected on 2018 development data, passed its 2018 validation gate, and then failed the 2018 locked test. A post-hoc diagnostic of that already-failed candidate was explicitly labeled `NOT_EVIDENCE`.

One fixed subgroup pattern was unusually consistent across all three 2018 slices: signals occurring when the trailing 100-bar ATR percentile was in the second fixed quartile (`> 0.25` and `<= 0.50`). This subgroup had positive payout-adjusted expectancy in development, validation, and locked-test slices. The sample sizes were small and the subgroup was discovered after inspecting the failed locked result.

Therefore this observation is **not evidence**. V3B tests it once, without tuning, on a fresh year.

## Fresh confirmatory dataset

- Provider: FXCM public candle archive
- Symbol: EURUSD
- Timeframe: 1 minute
- Year: **2017**
- Price construction: midpoint of FXCM bid/ask OHLC
- Timestamps: UTC

No V3B outcome on 2017 has been inspected before this preregistration. The V3A 2017 job may execute concurrently, but its result must not be inspected or used to alter V3B before V3B's configuration is frozen in Git.

## Frozen base strategy

Exact V2 Sweep Reversal winner from 2018:

```text
lookback = 20
wick_min = 0.65
rsi_edge = 65.0
overshoot_atr = 0.0
liquid_core_only = false
```

## Frozen additional context rule

At the signal timestamp, keep a Sweep Reversal signal only when:

```text
atr_percentile_100 > 0.25
AND
atr_percentile_100 <= 0.50
```

`atr_percentile_100` is the trailing-only 100-bar percentile rank already defined by Confluence Lab. The boundaries are copied exactly from the fixed diagnostic Q2 bucket; they are not to be optimized.

Both CALL and PUT directions remain eligible.

## Frozen execution

```text
expiry_bars = 2
entry_offset_bars = 1
fixed_payout = 0.82  # hypothetical regular-FX benchmark economics
stake = 1.0
allow_overlapping_positions = true
cooldown_bars = 0
tie_policy = refund
```

Break-even win rate at 82% payout:

```text
1 / (1 + 0.82) = 0.54945054945
```

## Primary pass rule

V3B passes only if all conditions hold on the complete 2017 dataset:

1. at least 120 settled non-tie trades;
2. payout-adjusted expectancy at 82% is > 0;
3. 95% Wilson lower confidence bound for win rate is > 0.54945054945.

No direction, month, UTC window, HTF state, or narrower volatility bucket may substitute for failure of this primary rule.

## Frozen robustness diagnostics

Secondary diagnostics cannot rescue primary failure:

1. 80% payout repricing expectancy > 0 → `payout_robust_80`.
2. `entry_offset_bars = 2` expectancy > 0 → `entry_delay_robust`.
3. non-overlapping positions expectancy > 0 → `non_overlap_robust`.
4. moving-block bootstrap expectancy lower 95% bound > 0 at block sizes 5, 10, and 20 → three separate dependence-robustness flags.
5. calendar-month performance is reported without selecting months.
6. CALL and PUT performance are reported diagnostically but cannot redefine the hypothesis after the result.

## Decision policy

- Primary fail → `rejected_primary`.
- Primary pass with any of payout/delay/non-overlap robustness failing → `replicated_but_fragile`.
- Primary pass plus payout/delay/non-overlap pass, but one or more block-bootstrap lower bounds <= 0 → `replicated_but_dependence_sensitive`.
- Primary pass plus all frozen robustness checks → `replicated_and_robust_regular_fx_candidate`.

Even a complete pass is regular-FX research only. It is not Pocket Option/OTC evidence and is not a guarantee of future returns.
