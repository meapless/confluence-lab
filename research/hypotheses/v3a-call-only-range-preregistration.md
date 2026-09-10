# V3A Preregistration — CALL-only Range Reversion Replication

Status: **PREREGISTERED BEFORE ANY 2017 STRATEGY EVALUATION**

## Origin

The V1 2019 range-reversion family produced the only legitimate positive-development candidate among the original strategy families. Its exact frozen configuration was then replicated without tuning on FXCM EUR/USD 2018 and failed the preregistered full-strategy confidence criterion.

The 2018 post-hoc direction diagnostic showed an asymmetry: CALL outcomes were materially stronger than PUT outcomes. Because that direction split was inspected after the primary replication result, it is **not evidence**. V3A exists to test that observation on a fresh year without tuning.

## Fresh confirmatory dataset

- Provider: FXCM public candle archive
- Symbol: EURUSD
- Timeframe: 1 minute
- Year: **2017**
- Price construction: midpoint of FXCM bid/ask OHLC
- Timestamps: UTC according to FXCM archive documentation
- 2017 has not previously been used for strategy selection, parameter tuning, validation, or locked-test outcome inspection in Confluence Lab. A single historical week was used only to verify the FXCM parser/schema.

## Frozen strategy

Base family: `range_reversion`

Parameters are copied exactly from the 2019 V1 candidate:

```text
adx_max = 30.0
rsi_lower = 25.0
rsi_upper = 65.0
band_buffer_atr = 0.10
atr_pct_max = 0.70
```

Direction rule:

```text
KEEP CALL (+1) signals only.
DROP all PUT (-1) signals.
```

No parameter search is permitted.

## Frozen execution

```text
expiry_bars = 5
entry_offset_bars = 1
fixed_payout = 0.82  # hypothetical binary-style economics assumption
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

V3A passes the fresh-year replication only if **all** conditions hold on the complete 2017 dataset:

1. at least 400 settled non-tie trades;
2. payout-adjusted expectancy at 82% is > 0;
3. the 95% Wilson lower confidence bound for win rate is > 0.54945054945.

No subgroup may substitute for failure of this primary rule.

## Frozen robustness diagnostics

These diagnostics are secondary and cannot rescue a failed primary result:

1. Reprice the same outcomes at 80% payout; expectancy should remain > 0 to earn a `payout_robust_80` flag.
2. Re-run with `entry_offset_bars = 2`; expectancy should remain > 0 to earn an `entry_delay_robust` flag.
3. Re-run with overlapping positions disabled; expectancy should remain > 0 to earn a `non_overlap_robust` flag.
4. Report calendar-month stability without selecting months.

## Decision policy

- Primary fail → hypothesis rejected as confirmatory evidence, regardless of attractive months or subgroups.
- Primary pass but robustness weak → classify as `replicated_but_fragile`.
- Primary pass plus all three robustness flags → classify as `replicated_and_robust_regular_fx_candidate`.

Even the strongest classification is **not Pocket Option/OTC evidence** and is not a guarantee of future returns. It would only justify additional independent-year testing and eventual Pocket-specific prospective research.
