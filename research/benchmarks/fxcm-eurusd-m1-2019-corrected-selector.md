# FXCM EUR/USD M1 2019 — corrected development selector

## Decision

The corrected matrix selector found **no eligible development candidate** for either Trend Pullback or Breakout.

This rerun exists to correct the development-ranking issue discovered after the original 2019 benchmark. The original validation lock was never compromised: both families had already been rejected before the locked slice. The correction changes only which development candidates are allowed to rank.

## Provenance

- GitHub Actions run: `34491959055`
- Run commit: `8229e92c3973ab6c3a341215cd3e2de0ca550fd3`
- Artifact: `fxcm-eurusd-2019-corrected-selector`
- Artifact digest: `sha256:faab83e389f74135771e44e5c18081b70530e41fb62aeca8311ea436a40a22a0`
- Dataset rows: 368,191
- Dataset fingerprint: `284c064834f65b1ef6c042812c10730477c36499f404695238e19e1c41c5518b`
- Same FXCM 2019 data as `research/benchmarks/fxcm-eurusd-m1-2019-v1.md`

## Corrected eligibility

A development candidate must satisfy all of the following before its Wilson score can rank:

- at least 200 trades;
- strictly positive payout-adjusted expectancy under the hypothetical 82% payout;
- then rank by Wilson 95% lower bound.

## Results

### Trend Pullback

- parameter sets: 288
- expiries: 4
- development configurations considered: 1,152
- eligible positive-expectancy candidate: **none**
- status: `no_development_candidate`
- validation: not run
- locked test: not opened

### Breakout

- parameter sets: 192
- expiries: 4
- development configurations considered: 768
- eligible positive-expectancy candidate: **none**
- status: `no_development_candidate`
- validation: not run
- locked test: not opened

## Interpretation

The negative-expectancy development winners in the historical v1 report should not be treated as meaningful candidate strategies. Under the corrected selector, neither family produces even a development-stage candidate worth validation on this full FXCM year.

The V1 research state is therefore:

- `trend_pullback`: no eligible 2019 development candidate;
- `breakout`: no eligible 2019 development candidate;
- `range_reversion`: positive 2019 development/validation point estimates, failed 2019 confidence gate, then failed independent 2018 replication confidence gate and showed material delay/payout fragility.

No V1 family is validated.
