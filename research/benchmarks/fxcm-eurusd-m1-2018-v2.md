# FXCM EUR/USD M1 2018 — preregistered V2 benchmark

## Decision

**NO V2 STRATEGY FAMILY PASSED LOCKED EVIDENCE.**

This study was preregistered before the first V2 evaluation on 2018 data. Two families failed to produce an eligible development candidate. The third, Sweep Reversal, passed both development and validation, legitimately opened the locked test, and then failed badly on the locked slice.

That locked failure is preserved as the final decision. The 2018 V2 data must now be treated as seen and must not be retuned to rescue the candidate.

## Provenance

- Preregistration: `research/hypotheses/v2-preregistration.md`
- GitHub Actions run: `34492557465`
- Run commit: `06c98c898746eaafb075f79ae8887d5e8d1e8a40`
- Artifact: `fxcm-eurusd-2018-v2-benchmark`
- Artifact digest: `sha256:386eac432db8a51e4395fff13cab8648593ed191fba2b0c83c57cf2bfcd241d0`
- Provider: FXCM public candle archive
- Instrument: EUR/USD
- Timeframe: 1 minute
- Price construction: FXCM bid/ask midpoint
- Rows: 374,660
- Dataset fingerprint: `a47a385e39d8eec507dc69106d86a11ba947e3399d8687dca1df8249397b3b7b`
- Missing weeks: none
- Source-file hashes are identical to the independently downloaded replication run and are preserved in `research/manifests/fxcm-eurusd-m1-2018-range-replication-source-files.csv`.

## Preregistered research policy

At the hypothetical 82% payout, break-even win rate is **54.9451%**.

- development: 60%
- validation: 20%
- locked test: 20%
- development candidate minimum: 200 trades and strictly positive expectancy
- development ranking: Wilson 95% lower bound
- validation minimum: 100 trades, positive expectancy, Wilson lower > 54.9451%
- locked evidence minimum: 100 trades, positive expectancy, Wilson lower > 54.9451%
- expiries searched: 1, 2, 3, 5 bars
- V2 parameter sets: 152
- total development configurations evaluated: **608**

## V2-1 — Higher-timeframe-aligned pullback

**Status: `no_development_candidate`**

Across the preregistered grid and expiries, no configuration simultaneously produced at least 200 development trades and positive expectancy. Validation was therefore not run and the locked test remained unopened.

## V2-2 — Volatility-compression breakout

**Status: `no_development_candidate`**

No preregistered development configuration met the minimum positive-expectancy evidence requirements. Validation was not run and the locked test remained unopened.

## V2-3 — Sweep Reversal

This family produced the strongest apparent signal seen so far in Confluence Lab before the locked test.

### Development winner

Frozen after development selection:

- `lookback = 20`
- `wick_min = 0.65`
- `rsi_edge = 65.0`
- `overshoot_atr = 0.0`
- `liquid_core_only = false`
- expiry = **2 bars**
- entry offset = 1 bar
- hypothetical payout = 0.82

Development performance:

- trades: **590**
- wins: 344
- losses: 233
- ties: 13
- win rate: **59.6187%**
- Wilson 95% lower: **55.5643%**
- expectancy: **+0.08319** units/trade
- hypothetical total P&L: +49.08 units
- max drawdown: 11.88 units

This was an eligible development candidate.

### Validation

- trades: **212**
- wins: 133
- losses: 78
- ties: 1
- win rate: **63.0332%**
- Wilson 95% lower: **56.3412%**
- expectancy: **+0.14651** units/trade
- hypothetical total P&L: +31.06 units
- max drawdown: 7.0 units

Validation passed every preregistered gate, so opening the locked slice was permitted.

### Locked test

- trades: **240**
- wins: 121
- losses: 113
- ties: 6
- win rate: **51.7094%**
- Wilson 95% lower: **45.3311%**
- expectancy: **-0.05742** units/trade
- hypothetical total P&L: **-13.78 units**
- max drawdown: 24.48 units

**Locked evidence pass: false.**

## Interpretation

Sweep Reversal is a useful demonstration of why Confluence Lab uses a truly locked holdout. If the research process had stopped after validation, the strategy could easily have been described as a 63% validation system with a confidence bound above break-even. The untouched final slice showed that conclusion was not robust.

The correct result is therefore:

> Sweep Reversal produced a strong development/validation pattern on the earlier 80% of FXCM 2018, but failed the untouched final 20% with negative expectancy. It is rejected as V2 evidence.

No parameter adjustment will be performed on the 2018 locked failure. Any future version must be a substantively new hypothesis and tested on data not used to invent or tune it.

## V2 conclusion

- `htf_aligned_pullback`: no development candidate
- `compression_breakout`: no development candidate
- `sweep_reversal`: validation pass, locked failure

**No V2 family is validated.**
