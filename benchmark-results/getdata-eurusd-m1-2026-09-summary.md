# Public EUR/USD M1 benchmark — July to September 2026

## Purpose

This is an **engineering/research benchmark**, not a Pocket Option result and not evidence of future profitability. It uses a pinned, independently maintained regular EUR/USD one-minute sample and a hypothetical fixed 82% binary payout solely to test Confluence Lab on real market prices.

## Provenance

- Source: GetData EURUSD 1m evaluation sample
- Repository: `getdata-finance/eurusd-1m-ohlcv-forex-historical-data`
- Pinned source commit: `c8526b6d1b7e629ff2fcf9eb585820c2e83ea4e1`
- Source blob SHA: `7d56b0010bafb83e86cf3f27239337a723728187`
- File: `EURUSD_1m.csv`
- License: MIT
- Downloaded bytes: `5,221,554`
- Download SHA-256: `fc46937d44c2bfdb1ece4c14f0767505fac58790dfed35827bb0cb0dad881a86`
- Normalized dataset fingerprint: `848e11ede6437a98456ee0eb1514255810e4954831e4e147a4a41c6fbaae432e`
- Rows: `55,440`
- Span: `2026-07-14 08:28 UTC` through `2026-09-04 20:59 UTC`
- Duplicate timestamps: `0`
- Invalid OHLC rows: `0`

### Gap diagnostics

- Raw missing one-minute intervals: `20,192`
- Gap events: `16`
- Largest gap: `2 days 00:05:00`
- Weekend-spanning gap events: `7`
- Missing intervals inside weekend-spanning gaps: `20,167`
- Non-weekend missing intervals: **25**

This is much more informative than treating every closed-market minute as corrupted data. Weekend-spanning counts remain visible for audit, while only 25 missing intervals fall outside those gaps.

## Economics assumption

Hypothetical fixed payout: **82%**.

Break-even resolved-trade win rate: **54.9451%**.

The payout is not observed Pocket Option history and must never be described as Pocket performance.

## Research policy

- 60% chronological development
- 20% chronological validation
- 20% locked test
- Development ranking: 95% Wilson lower bound
- Minimum development sample: 30 trades
- Validation minimum: 30 trades
- Validation must have positive payout-adjusted expectancy
- **Validation's 95% Wilson lower bound must also exceed 54.9451% before the locked test is opened**
- Locked evidence requires positive expectancy and Wilson lower bound above break-even
- Expiries: 1, 2, 3, 5 bars
- Total development configurations evaluated: **3,072**

## Results

### Trend Pullback — REJECTED ON VALIDATION

Best development candidate:

- expiry: 5 bars
- trades: 65
- resolved win rate: **63.08%**
- Wilson lower bound: **50.92%**
- expectancy: **+0.1480** per unit risk

Validation:

- trades: 16
- resolved win rate: **37.50%**
- Wilson interval: **18.48%–61.36%**
- expectancy: **−0.3175**
- total hypothetical P&L: **−5.08**

It also failed the minimum 30-trade validation sample.

**Decision: reject. Locked test was not opened.**

### Range Reversion — REJECTED ON EVIDENCE STRENGTH

Best development candidate:

- expiry: 5 bars
- trades: 91
- resolved win rate: **63.64%**
- Wilson lower bound: **53.21%**
- expectancy: **+0.15297**

Validation:

- trades: 30
- wins: 16
- losses: 13
- ties: 1
- resolved win rate: **55.17%**
- Wilson interval: **37.55%–71.59%**
- expectancy: **+0.0040**
- total hypothetical P&L: **+0.12**

The point estimate barely exceeds the 54.9451% break-even rate, but the 95% lower bound is only 37.55%. This is nowhere near enough evidence to claim an edge.

**Decision: reject. Locked test was not opened.**

This case is a useful example of why positive P&L and a >break-even point estimate are insufficient when the sample is small.

### Breakout — REJECTED

Best development candidate:

- expiry: 1 bar
- trades: 1,197
- resolved win rate: **50.72%**
- Wilson lower bound: **47.79%**
- expectancy: **−0.07175**

Validation:

- trades: 368
- resolved win rate: **50.44%**
- Wilson lower bound: **45.16%**
- expectancy: **−0.07598**
- total hypothetical P&L: **−27.96**

**Decision: reject. Locked test was not opened.**

## Baselines

None of the fixed baseline/expiry combinations produced positive locked-slice expectancy in this benchmark. Always-CALL, always-PUT and seeded-random remained around chance and negative at an 82% payout, which is the expected sanity-check behavior.

## Cross-benchmark conclusion

This independent July–September 2026 source supports the same broad conclusion as the March/April 2025 MT5 benchmark: the current hand-designed Trend Pullback, Range Reversion and Breakout families do **not** have validated evidence of an edge.

The correct next action is not to reveal either locked set and keep tuning against it. The failed strategy versions and parameters remain part of the research record. New hypotheses should be developed using broader/different development histories and then receive fresh validation/locked periods.
