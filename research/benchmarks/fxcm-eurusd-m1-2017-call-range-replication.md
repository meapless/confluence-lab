# FXCM EUR/USD M1 2017 — preregistered CALL-only Range Reversion replication

## Decision

**FAILED REPLICATION. RESEARCH LINE CLOSED.**

The CALL-only hypothesis was generated from a post-hoc direction diagnostic in the failed 2018 Range Reversion replication, then preregistered before any full-year 2017 strategy evaluation. The exact rules were evaluated on FXCM EUR/USD M1 2017 with no parameter search.

The point estimate remained positive, but the preregistered 95% Wilson lower confidence bound did not clear the hypothetical 82%-payout break-even threshold. Ordinary bootstrap uncertainty also crossed zero, and the result was fragile to one additional minute of entry delay.

Per the preregistration, this direction-specific research line is closed rather than retuned on 2017.

## Provenance

- Preregistration: `research/hypotheses/v3-call-range-preregistration.md`
- GitHub Actions run: `34493491824`
- Run commit: `8958d52a5e36e9123aa48010248363bb7a556488`
- Artifact: `fxcm-eurusd-2017-call-range-replication`
- Artifact digest: `sha256:0072e109f1cf5d319f0b1eb3315b5135f8b1c896e4e683b2c518598a76bb5ece`
- Provider: FXCM public candle archive
- Instrument: EUR/USD
- Timeframe: 1 minute
- Price construction: FXCM bid/ask midpoint
- Rows: **369,924**
- Coverage: 2017-01-03 00:00 UTC through 2017-12-29 21:57 UTC
- Dataset fingerprint: `2ee9d530c34c74bec2ae3d56b1cd7fc45e5e1d37c8c59426b6f25c1f02edac03`
- Weekly files downloaded: 52
- Missing archive week: 53
- Per-file hashes: `research/manifests/fxcm-eurusd-m1-2017-call-range-source-files.csv`

Dataset diagnostics recorded zero duplicate timestamps and zero invalid OHLC rows. Nominal missing one-minute intervals were dominated by weekend-spanning closures; 767 missing intervals were classified as non-weekend gaps.

## Frozen configuration

Base Range Reversion rules:

- `adx_max = 30.0`
- `rsi_lower = 25.0`
- `rsi_upper = 65.0`
- `band_buffer_atr = 0.10`
- `atr_pct_max = 0.70`
- expiry = 5 one-minute bars
- entry offset = 1 bar
- fixed payout assumption = 0.82
- ties = refund

V3 direction rule:

- retain CALL (`+1`) signals only;
- convert every PUT (`-1`) signal to no-trade.

Break-even win rate at an 82% payout: **54.9451%**.

Preregistered primary pass rule:

1. at least 300 trades;
2. strictly positive expectancy;
3. 95% Wilson lower bound strictly above 54.9451%.

## Primary result

- trades: **548**
- wins: 311
- losses: 230
- ties: 7
- non-tie win rate: **57.4861%**
- Wilson 95% lower: **53.2820%**
- Wilson 95% upper: 61.5848%
- expectancy: **+0.045657** units/trade
- hypothetical total P&L: +25.02 units
- max drawdown: 22.72 units
- longest losing streak: 12
- longest winning streak: 11

The point estimate and expectancy were positive, but the Wilson lower bound remained below break-even. **Primary replication pass = false.**

## Preregistered secondary diagnostics

These diagnostics do not change the failed primary decision.

### Ordinary expectancy bootstrap

10,000 bootstrap simulations:

- observed expectancy: +0.045657
- 2.5th percentile: **-0.029234**
- median: +0.045328
- 97.5th percentile: +0.119891
- probability of positive expectancy: **0.8805**

The 95% bootstrap interval crosses zero, so the positive point estimate is not statistically robust under this diagnostic.

### One-position-at-a-time execution

- cooldown 0: 343 trades, 56.5089% win rate, Wilson lower 51.1800%, expectancy +0.02805
- cooldown 1: same effective result
- cooldown 2: 342 trades, 56.6766% win rate, Wilson lower 51.3402%, expectancy +0.03105

None clear the evidence threshold.

### Entry-delay sensitivity

- normal next-bar entry (`offset=1`): expectancy +0.045657
- one additional minute (`offset=2`): **expectancy -0.009307**, win rate 54.4280%
- two additional minutes (`offset=3`): expectancy +0.000985, approximately zero

The apparent edge does not tolerate a one-minute additional entry delay.

### Payout sensitivity

Same historical directional outcomes repriced at fixed payouts:

- 70% payout: expectancy **-0.022445**
- 80% payout: expectancy +0.034307
- 82% payout: expectancy +0.045657
- 90% payout: expectancy +0.091058

This remains materially dependent on payout quality.

### Monthly stability

Monthly expectancy was highly unstable. Positive months included January (+0.2807), July (+0.1974), August (+0.1681), September (+0.1785), and November (+0.2133), while notable negative months included:

- May: **-0.1956**
- June: **-0.0586**
- October: **-0.3000**
- December: **-0.1406**

This pattern is inconsistent with a stable year-round edge.

## Interpretation

The clean conclusion is narrower than the attractive 57.49% headline:

> The CALL-only Range Reversion hypothesis produced a positive point estimate on full-year FXCM 2017, but failed its preregistered confidence threshold, had an expectancy bootstrap interval crossing zero, showed large monthly instability, and lost its edge under a one-minute additional entry delay.

This is not replicated evidence of a robust strategy. The CALL-only Range Reversion line is therefore **closed** and will not be tuned on 2017.

No Pocket Option, OTC, live-trading, or future-return claim follows from this result.
