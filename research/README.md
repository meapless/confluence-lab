# Confluence Lab research ledger

This directory is the evidence record for Confluence Lab. The goal is not to maximize backtest win rate; it is to discover whether any short-horizon directional hypothesis survives increasingly difficult attempts to falsify it.

Regular-FX benchmarks are **not Pocket Option or OTC evidence**. Fixed binary payouts used in these studies are hypothetical economics assumptions. No result here is a guarantee of future returns.

## Current evidence state

| Study | Data | Search / hypothesis | Development | Validation | Locked / replication | Final decision |
|---|---|---|---|---|---|---|
| Public MT5 engineering benchmark | EUR/USD M1, Mar–Apr 2025 | V1 Trend / Range / Breakout | searched | all candidates weak/unstable | locked not opened | **Rejected** |
| GetData engineering benchmark | EUR/USD M1, Jul–Sep 2026 | V1 Trend / Range / Breakout | searched | none cleared evidence gate | locked not opened | **Rejected** |
| FXCM 2019 v1 | EUR/USD M1, full 2019 | V1 families | Range positive; Trend/Breakout historical selector issue | Range 56.26% but Wilson low 53.44% | locked not opened | **Rejected / near miss** |
| FXCM 2019 corrected selector | same 2019 data | Trend / Breakout only | no positive-expectancy dev candidate | not run | locked not opened | **Rejected** |
| FXCM 2018 Range replication | EUR/USD M1, full 2018 | exact frozen 2019 Range candidate | no tuning | no tuning | 55.49%, Wilson low 54.27%; delay/payout fragile | **Failed replication** |
| FXCM 2018 V2 | same 2018 data, preregistered | HTF Pullback / Compression Breakout / Sweep Reversal | Sweep passed | Sweep 63.03%, Wilson low 56.34% | Sweep locked: 51.71%, expectancy -0.0574 | **Locked failure** |
| FXCM 2017 V3 CALL Range | EUR/USD M1, full 2017 | exact CALL-only hypothesis generated from 2018 diagnostic | no tuning | no tuning | pending at time of ledger creation | **Pending** |

## Important negative results

### V1 Trend Pullback

After matrix development eligibility was corrected to require positive expectancy, the full 2019 FXCM study contained **no eligible development candidate** across the preregistered Trend Pullback grid and expiries.

### V1 Breakout

Same outcome: **no eligible positive-expectancy development candidate** on FXCM 2019 under the corrected selector.

### V1 Range Reversion

This is the only V1 family that showed persistent positive point estimates:

- 2019 development: 56.52%, expectancy +0.0282;
- 2019 validation: 56.26%, expectancy +0.0234;
- validation Wilson lower: 53.44%, below 54.95% break-even at 82% payout;
- independent 2018 frozen replication: 55.49%, expectancy +0.00974;
- 2018 Wilson lower: 54.27%, again below break-even;
- +1 additional minute entry delay made expectancy negative;
- repricing the same 2018 outcomes at 80% payout made expectancy slightly negative.

Therefore it is **not validated**.

### V2 Sweep Reversal

This is the strongest example so far of why locked data matters:

- development: 59.62%, Wilson lower 55.56%, positive expectancy;
- validation: 63.03%, Wilson lower 56.34%, positive expectancy;
- locked test: **51.71%, negative expectancy**.

The strategy is rejected. The 2018 locked slice is now seen and may not be retuned to rescue it.

## Research rules

1. Hypotheses and search spaces should be frozen before independent evaluation.
2. Development searches require a meaningful minimum trade count and positive payout-adjusted expectancy.
3. Validation must be chronological and separate from development.
4. Locked data is opened only after validation passes its preregistered gate.
5. A locked pass is not sufficient for deployment; independent-period replication is still required.
6. Overlapping short-expiry trades are treated as a dependence risk and must be stress-tested with one-position-at-a-time execution.
7. Payout sensitivity and entry-delay sensitivity are mandatory for promising candidates.
8. Post-hoc subgroup discoveries are new hypotheses, not retroactive rescues.
9. Failed studies are preserved.
10. No Martingale or loss-chasing sizing is used to manufacture a favorable equity curve.

## Evidence files

- `benchmarks/` — human-readable decisions and experiment summaries.
- `hypotheses/` — preregistration documents created before independent tests.
- `manifests/` — source-file hashes and provenance used to reproduce datasets.

## Current next question

The only live hypothesis at the time this index was created is whether the post-hoc 2018 CALL-only Range Reversion asymmetry replicates without tuning on full-year FXCM 2017. If it fails, that line is closed. If it passes, it must still survive another untouched year and eventually broker-specific Pocket demo/payout data before it can support any product claim.
