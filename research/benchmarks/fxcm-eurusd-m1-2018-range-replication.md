# FXCM EUR/USD M1 2018 — frozen Range Reversion replication

## Decision

**FAILED REPLICATION.**

The exact Range Reversion candidate selected from the 2019 FXCM study was frozen before this test and evaluated on the full independent 2018 FXCM EUR/USD M1 year with no parameter search.

It remained slightly positive at the hypothetical 82% payout, but the preregistered 95% Wilson lower confidence bound did not clear break-even. The result is therefore not accepted as replicated evidence.

## Provenance

- Preregistration: `research/hypotheses/v2-preregistration.md`
- GitHub Actions run: `34492500922`
- Run commit: `e213e9f9217dc6ad920a47a3f1650e27a3f71bb5`
- Artifact: `fxcm-eurusd-2018-range-replication`
- Artifact digest: `sha256:1465e88aa3e14d9a0465ead58c93424bae2b09edc47d50736cbcc97eada040d8`
- Provider: FXCM public candle archive
- Instrument: EUR/USD
- Timeframe: 1 minute
- Price construction: bid/ask midpoint
- Rows: 374,660
- Coverage: 2018-01-01 22:00 UTC through 2019-01-04 21:59 UTC
- Dataset fingerprint: `a47a385e39d8eec507dc69106d86a11ba947e3399d8687dca1df8249397b3b7b`
- Weekly files downloaded: 53
- Missing weeks: none
- Per-file hashes: `research/manifests/fxcm-eurusd-m1-2018-range-replication-source-files.csv`

Dataset diagnostics recorded 155,260 nominal missing one-minute intervals, of which 150,100 were in weekend-spanning gaps and 5,160 were non-weekend missing intervals. There were zero duplicate timestamps and zero invalid OHLC rows.

## Frozen configuration

- family: `range_reversion`
- `adx_max = 30.0`
- `rsi_lower = 25.0`
- `rsi_upper = 65.0`
- `band_buffer_atr = 0.10`
- `atr_pct_max = 0.70`
- expiry: 5 bars
- entry offset: 1 bar
- fixed payout assumption: 0.82
- ties: refund
- overlapping positions: allowed for primary replication

Break-even win rate at an 82% payout: **54.9451%**.

Preregistered pass rule:

1. at least 500 trades;
2. positive expectancy;
3. 95% Wilson lower bound above 54.9451%.

## Primary result

- trades: **6,498**
- wins: 3,554
- losses: 2,851
- ties: 93
- non-tie win rate: **55.4879%**
- Wilson 95% interval: **54.2679% to 56.7014%**
- expectancy: **+0.009738** units per trade
- hypothetical total P&L: +63.28 units
- max drawdown: 88.12 units
- longest losing streak: 16

The point estimate was above break-even, but the Wilson lower bound was not. **Primary replication pass = false.**

## Secondary robustness diagnostics

These were preregistered as diagnostics only and do not change the failed primary decision.

### Direction split

CALL:

- 508 trades
- 59.3939% win rate
- Wilson lower: **55.0114%**
- expectancy: +0.07890

PUT:

- 5,990 trades
- 55.1607% win rate
- Wilson lower: 53.8899%
- expectancy: +0.00387

The CALL-only result is interesting, but it is **post-hoc relative to the original candidate**. It may motivate a separately preregistered future hypothesis; it cannot be used to rescue this failed replication.

### Overlap stress

One position at a time remained slightly positive, but uncertainty still crossed break-even:

- cooldown 0: 3,414 trades, 55.2976%, expectancy +0.00632, Wilson lower 53.6114%
- cooldown 1: 3,327 trades, 55.5250%, expectancy +0.01039, Wilson lower 53.8179%
- cooldown 2: 3,262 trades, 55.6489%, expectancy +0.01262, Wilson lower 53.9254%

None cleared the evidence threshold.

### Entry-delay sensitivity

- normal next-bar entry (`offset=1`): expectancy +0.00974
- one additional bar delay (`offset=2`): **expectancy -0.01086**, 54.3397% win rate
- two additional bars (`offset=3`): **expectancy -0.02611**, 53.4942% win rate

This is a material fragility warning: the observed edge did not tolerate even one additional one-minute entry delay.

### Payout sensitivity

Same historical outcomes repriced at fixed payouts:

- 70% payout: expectancy **-0.05589**
- 80% payout: expectancy **-0.00120**
- 82% payout: expectancy +0.00974
- 90% payout: expectancy +0.05349

The candidate is therefore highly dependent on payout quality. It is slightly negative even at an 80% payout.

## Research interpretation

The 2018 result supports a narrower statement than “the strategy works”:

> The frozen 2019 Range Reversion rules produced a small positive point estimate on an independent 2018 FX year, but the evidence did not clear the preregistered confidence threshold and was fragile to payout compression and modest entry delay.

Accordingly, the candidate remains **unvalidated**. No live-trading or Pocket-specific performance claim follows from this result.
