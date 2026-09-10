# Research methodology

Confluence Lab is designed to make it difficult to accidentally manufacture a good-looking backtest.

## Core rules

1. **Signals are observed before entry.** The default engine enters on the next bar open, never on the same bar that completed the signal.
2. **Time-series splits are chronological.** Development, validation, and final test data are never randomly shuffled.
3. **Payout is part of the experiment.** Binary-style results are evaluated using the payout that would have applied at entry where that data exists.
4. **Win rate is not enough.** We also calculate expectancy, drawdown, streaks, sample size, and confidence intervals.
5. **Baselines are mandatory.** Complex strategies must beat random and simple rules on unseen data.
6. **Locked-test performance is not optimization data.** Once a configuration is selected, the final test set estimates generalization rather than tuning parameters.
7. **Synthetic data is labelled.** Generated fixtures are engineering tests, never evidence of trading profitability.
8. **OTC is not ordinary FX.** Pocket Option OTC observations must be collected and validated as broker-specific data rather than substituted with unrelated spot-FX history.

## Current execution model

With candle-only data, a signal on bar `t` enters at the **open of bar `t+1`**. An expiry of `N` bars settles at the close of the Nth bar starting from entry. This convention is intentionally conservative and avoids same-bar hindsight assumptions. Tick-level Pocket data can later support a more exact execution model.

## Binary payout economics

For a one-unit stake and decimal payout `p`:

- win P&L = `+p`
- loss P&L = `-1`
- break-even win rate = `1 / (1 + p)`

A strategy can therefore have a win rate above 50% and still have negative expectancy when payouts are low.
