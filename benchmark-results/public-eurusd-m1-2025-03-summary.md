# Public EUR/USD M1 benchmark — March/April 2025

## Purpose

This is an **engineering/research benchmark**, not a Pocket Option result and not evidence of future profitability. It uses third-party regular EUR/USD MetaTrader 5 data and a hypothetical fixed 82% binary payout solely to test Confluence Lab's research pipeline on real market prices.

## Provenance

- Source repository: `shubhamlodha21/MetaTrader-5-Data-Downloader`
- Pinned source commit: `79733c68c5d26490efd4b85b31c5c2c17a907423`
- Source blob SHA: `b2f840067011782c6dcdd1ce7a5c036efa711fac`
- Source file: `EURUSD_1_Minute_2025-03-04_to_2025-04-03.csv`
- Downloaded bytes: `1,900,741`
- Download SHA-256: `62b2b93110e9d2eac49b14ffaa0382d45ea759a7de33150891a7a4823d6ff1f2`
- Normalized dataset fingerprint: `2ec2dd10c39e327bd21d762219c4035e381c3e291446c2d241eabf0cb0b2ead9`
- Rows: `31,708`
- Span: `2025-03-03 18:30 UTC` through `2025-04-02 18:30 UTC`
- Duplicate timestamps: `0`
- Invalid OHLC rows: `0`

The generic gap detector reported 11,493 missing one-minute intervals. That count includes normal FX market closures/weekends and should **not** be interpreted as 11,493 corrupted bars. A later diagnostics revision will separate scheduled closures from suspicious gaps.

## Economics assumption

Hypothetical fixed payout: **82%**.

Break-even resolved-trade win rate:

`1 / (1 + 0.82) = 54.9451%`

This payout was **not observed from Pocket Option** and must never be represented as historical Pocket payout data.

## Search policy

- 60% chronological development slice
- 20% chronological validation slice
- 20% locked test slice
- Development objective: 95% Wilson lower bound
- Minimum development sample: 30 trades
- Validation required at least 30 trades and positive payout-adjusted expectancy
- Locked test was only available after validation passed
- Three strategy families
- Expiries: 1, 2, 3, 5 bars
- Total development configurations evaluated: **3,072**

## Result

### Trend Pullback — REJECTED ON VALIDATION

Best development candidate:

- expiry: 1 bar
- trades: 97
- resolved win rate: **63.44%**
- 95% Wilson lower bound: **53.30%**
- expectancy per unit risk: **+0.1482**
- total hypothetical P&L: **+14.38**

Even in development, its conservative Wilson lower bound did not clear the 54.95% break-even threshold.

Validation:

- trades: 32
- resolved win rate: **41.38%**
- 95% Wilson interval: **25.51%–59.26%**
- expectancy per unit risk: **−0.22375**
- total hypothetical P&L: **−7.16**

**Decision: reject. Locked test was not opened.**

### Range Reversion — REJECTED ON VALIDATION

Best development candidate:

- expiry: 5 bars
- trades: 532
- resolved win rate: **54.65%**
- 95% Wilson lower bound: **50.34%**
- expectancy per unit risk: **−0.00519**

Validation:

- trades: 158
- resolved win rate: **52.98%**
- expectancy per unit risk: **−0.03418**
- total hypothetical P&L: **−5.40**

**Decision: reject. Locked test was not opened.**

### Breakout — REJECTED ON VALIDATION

Best development candidate:

- expiry: 1 bar
- trades: 1,575
- resolved win rate: **52.52%**
- 95% Wilson lower bound: **50.02%**
- expectancy per unit risk: **−0.04265**

Validation:

- trades: 539
- resolved win rate: **51.18%**
- expectancy per unit risk: **−0.06456**
- total hypothetical P&L: **−34.80**

**Decision: reject. Locked test was not opened.**

## Baseline sanity check

Always-CALL, always-PUT and seeded-random baselines clustered near 50% resolved accuracy and had negative 82%-payout expectancy on the locked slice, as expected.

The superficially strongest locked baseline was the fixed RSI reversal with a five-bar expiry:

- trades: 143
- resolved win rate: **56.34%**
- expectancy: **+0.02517**
- 95% Wilson lower bound: **48.12%**

That lower bound is far below 54.95%, so this is **not evidence of an edge**. It is retained as a useful example of why a positive small-sample result is not enough.

## Conclusion

The first real-price experiment found **no validated strategy**. This is a successful research outcome because the pipeline prevented a 63.44% development result from being cherry-picked and marketed after it collapsed on validation.

Next steps are to: (1) improve market-closure-aware gap diagnostics, (2) use a much longer independent regular-FX history, (3) add stricter validation evidence gates, and (4) separately accumulate Pocket/OTC candles and contemporaneous payout observations before making any Pocket-specific claim.
