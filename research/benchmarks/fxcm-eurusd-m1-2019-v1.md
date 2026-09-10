# FXCM EUR/USD M1 2019 benchmark — v1

## Status

**No strategy family passed the validation gate. The locked strategy test slice remained unopened for every family.**

This run is preserved because it produced the first substantial near-miss in Confluence Lab and also exposed a matrix-selection policy gap that was fixed afterward.

## Provenance

- GitHub Actions run: `34490311010`
- Run commit: `a9b1a04f5722cf518eddde79c566621039923920`
- Artifact: `fxcm-eurusd-2019-benchmark`
- Artifact digest: `sha256:012746949f8e7076938eeb40a010665f38580d4dc31d97e2fb79dd2026573fc2`
- Provider: FXCM public candle archive
- Instrument: EUR/USD
- Timeframe: 1 minute
- Price construction: midpoint of FXCM bid/ask OHLC
- Rows: 368,191
- Coverage: 2019-01-06 22:01 UTC through 2020-01-03 21:59 UTC
- Dataset fingerprint: `284c064834f65b1ef6c042812c10730477c36499f404695238e19e1c41c5518b`
- Downloaded archive weeks: 52
- Missing archive week: week 1
- Per-file byte counts and SHA-256 hashes: `research/manifests/fxcm-eurusd-m1-2019-v1-source-files.csv`

The fixed 82% payout in this benchmark is a hypothetical binary-style economics assumption. This is **not Pocket Option or OTC data** and these results must not be represented as Pocket performance.

## Research gate

- Development: 60%
- Validation: 20%
- Locked test: 20%
- Development minimum trades: 200
- Validation minimum trades: 100
- Locked minimum trades: 100
- Search ranking objective: Wilson 95% lower bound
- Validation required positive expectancy
- Validation required Wilson lower bound above the 82%-payout break-even win rate, `54.9451%`

## Results

### Range Reversion — near miss, rejected

Development winner:

- 4,103 trades
- 56.5250% win rate
- 54.9876% Wilson lower bound
- +0.02819 expectancy per unit stake

Validation:

- 1,227 trades
- 56.2604% win rate
- 53.4358% Wilson lower bound
- +0.02337 expectancy per unit stake
- +28.68 hypothetical total P&L units

The point estimate remained above break-even, but the validation confidence bound did not. **Rejected. Locked test not opened.**

### Trend Pullback — rejected

The development candidate selected in this historical run had negative expectancy, which exposed a gap in the matrix search path: minimum development expectancy existed in the core optimizer but was not propagated through matrix selection.

- Development: 1,287 trades, 50.6452% win rate, -0.07540 expectancy
- Validation: 369 trades, 47.3973% win rate, -0.13588 expectancy
- **Rejected. Locked test not opened.**

### Breakout — rejected

The same matrix-selection caveat applies to this historical development winner.

- Development: 17,165 trades, 45.3564% win rate, -0.16946 expectancy
- Validation: 5,918 trades, 46.3715% win rate, -0.15187 expectancy
- **Rejected. Locked test not opened.**

## Methodology note discovered after the run

Commit `3b82c1b9b89b36e08a265a1a8f938a7b5d5841cc` propagated `min_expectancy` through matrix search. Commit `995d1e9626859eb35f8513d451c1a517f141bf1d` made positive development expectancy the default eligibility requirement for public fixed-payout benchmarks.

This means the Range Reversion result remains directly interpretable because its chosen development candidate already had positive expectancy. Trend Pullback and Breakout require a corrected-selector rerun before their best development candidates can be compared fairly.

## Conclusion

The 2019 data does **not** validate a tradable strategy. Range Reversion is the first family that showed enough persistence to justify new, independently preregistered follow-up research, but its uncertainty remains too large to claim an edge.
