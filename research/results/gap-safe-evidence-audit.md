# Gap-Safe Settlement Evidence Audit — 2016–2019

Status: **COMPLETE**

Audit workflow run: `34514738521`

Pinned audit commit: `b4dc99810afbc3d91965afdfc8db11e97204f96e`

Gap-safe engine merge commit: `c42abcdcc46271707dcdf0c7e21c5e19a61f6375`

Preregistration: `research/hypotheses/gap-safe-protocol-audit.md`

## Why this audit was required

The original short-expiry settlement engine advanced by available row number. A nominal 1–5 bar outcome could therefore cross a weekend, market closure, or missing-candle interval and settle much later than the intended minute horizon. The same issue existed in the V4 ML label generator.

The corrected engine requires all timestamp steps from signal through next-bar entry and expiry to be contiguous at the inferred candle interval. Gap-crossing trades are excluded, and ML target rows whose label horizon crosses a gap are set to `NaN` for model fitting.

The audit reran the previously evidence-bearing FXCM studies with **no hypothesis or threshold retuning**. The only methodological change was gap-safe horizon eligibility.

## Overall conclusion

The defect was real and the corrected engine supersedes the pre-fix engine for future work. However, **the correction did not reverse any scientific decision in the audited studies**.

Every audited strategy/model remains rejected or unvalidated. No locked test that was previously sealed became eligible to open because of the fix. The 2018 V2 Sweep Reversal still demonstrates the same development/validation success followed by a negative locked result.

2015 remains untouched.

## Corrected evidence table

| Study | Corrected result | Evidence decision | Artifact digest |
|---|---|---|---|
| 2019 V1 Trend Pullback | No eligible positive-expectancy development candidate | Rejected before validation | `sha256:7f5545e0bee8fb379cff5efaee3da55b34de19b81408e545dc214461d0005253` |
| 2019 V1 Range Reversion | Dev 56.42%; validation 56.13%, Wilson low 53.28%, expectancy +0.02115 | Validation rejected; locked sealed | same 2019 V1 artifact |
| 2019 V1 Breakout | No eligible positive-expectancy development candidate | Rejected before validation | same 2019 V1 artifact |
| 2018 frozen Range replication | 6,447 trades; win 55.49%; Wilson low 54.27%; expectancy +0.00979 | Failed replication / fragile | `sha256:3c69dd29bbcc45b227972af6b318334d9905be31282ecf9d2676aa1da33253e9` |
| 2018 V2 Sweep Reversal | Dev 59.72%; validation 63.03%; locked 51.71%, expectancy -0.05742 | Locked failure | `sha256:5f735c4690e0f88a5d30f7080efd6cca3142ee345c46cc0dd0bd23380aa363e2` |
| 2017 V3A CALL-only Range | 541 trades; win 57.68%; Wilson low 53.45%; expectancy +0.04909 | Failed primary gate; delay fragile | `sha256:234ac28f6df6ede202d42b0ecfc3e3136a865eef19ed8a128fca5798cc942c9f` |
| 2017 V3B moderate-vol Sweep | 175 trades; win 48.28%; Wilson low 40.97%; expectancy -0.12069 | Rejected | `sha256:b08c8c39364af26f2dd9b9e04cdbfda40e0084fca3fb592c226d394402a1ac7a` |
| 2016 V4 Logistic | Same 5-bar / 0.575 candidate; dev 58.77%; validation 57.10%, Wilson low 54.58%, expectancy +0.03891 | Validation rejected; locked sealed | `sha256:2c1536f6b468e41fab97d0ba074070814fb3d49b3b72a97e1c65e6c9fabdda92` |

All win-rate confidence comparisons above use the hypothetical 82% payout break-even rate of approximately **54.9451%**.

## Before / after detail

### 2019 V1 Range Reversion

Pre-fix evidence had shown approximately:

```text
development win rate  ~56.52%
validation win rate   ~56.26%
validation Wilson low ~53.44%
```

Gap-safe rerun:

```text
development trades        4,033
development win rate      56.4206%
development Wilson low    54.8700%
development expectancy    +0.026343

validation trades         1,200
validation win rate       56.1329%
validation Wilson low     53.2789%
validation expectancy     +0.021150
locked test               NOT OPENED
```

The exact same Range parameter set remained selected:

```text
ADX max          30
RSI lower        25
RSI upper        65
band buffer ATR  0.10
ATR pct max      0.70
expiry           5 bars
```

Trend Pullback and Breakout again produced no eligible development candidate after the corrected positive-expectancy selector.

### 2018 frozen Range replication

Pre-fix:

```text
trades       6,498
win rate     ~55.49%
Wilson low   ~54.27%
expectancy   +0.00974
```

Gap-safe:

```text
trades       6,447
wins         3,527
losses       2,829
ties         91
win rate     55.4909%
Wilson low   54.2661%
expectancy   +0.009794
```

The fix removed 51 invalid gap-crossing outcomes but did not materially change the estimate. The 80% payout repricing remains slightly negative and one additional bar of entry delay remains negative.

The previously noted CALL-only post-hoc slice also weakened under correction: its Wilson lower bound is approximately 54.78%, below the 54.95% break-even requirement. In any case that direction-specific idea was separately preregistered as V3A and failed on 2017.

### 2018 V2 Sweep Reversal

Gap-safe rerun:

```text
development   59.72% win rate, positive expectancy
validation    63.03% win rate, Wilson low 56.34%
locked        51.71% win rate
locked EV     -0.05742
locked P&L    -13.78 units
```

This is substantively unchanged. The candidate legitimately clears development and validation, then fails the locked slice. The result remains the clearest example in the project of why a strong validation percentage is not sufficient evidence.

### 2017 V3A CALL-only Range

Pre-fix:

```text
548 trades
57.49% win rate
Wilson low 53.28%
expectancy +0.0457
```

Gap-safe:

```text
541 trades
534 resolved
57.6779% win rate
Wilson low 53.4472%
expectancy +0.049094
```

Only seven trades disappeared and the scientific decision is unchanged. One additional entry bar still produces negative expectancy.

### 2017 V3B moderate-volatility Sweep

The corrected result is effectively unchanged:

```text
175 trades
174 resolved
48.2759% win rate
Wilson low 40.9688%
expectancy -0.120686
total P&L -21.12 units
```

The post-hoc 2018 volatility pattern still fails decisively in its fresh 2017 replication.

### 2016 V4 Logistic Regression

Pre-fix V4 selected 5 bars / threshold 0.575 and failed validation narrowly:

```text
validation win rate    57.3377%
validation Wilson low  54.8522%
validation expectancy  +0.04307
```

Gap-safe rerun selects the same candidate but is slightly weaker at validation:

```text
development trades       3,857
development win rate     58.7728%
development Wilson low   57.2059%
development expectancy   +0.069178

validation trades        1,507
validation win rate      57.1046%
validation Wilson low    54.5781%
validation expectancy    +0.038912
locked test              NOT OPENED
```

The locked slice remains sealed because 54.5781% is below the 54.9451% evidence threshold.

## Methodological decision

From this audit forward:

1. `require_contiguous_bars=True` is the default settlement policy.
2. Short-expiry ML targets crossing a candle gap are invalid training labels.
3. Pre-gap-fix figures remain historical audit records but are superseded for future model decisions.
4. A correction rerun does **not** make previously seen years fresh again.
5. 2016–2019 remain seen data.
6. 2015 remains reserved for a no-tuning replication only if a later preregistered candidate earns access to it.
7. Regular FXCM results remain general-market research, not Pocket Option/OTC evidence.

## Audit outcome

**No currently tested V1–V4 strategy or model has earned validated-edge status.**

The correction increased confidence in the *research process*, not in any strategy. That is the intended outcome of a reproducibility audit.