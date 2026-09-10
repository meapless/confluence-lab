# V3 preregistration — CALL-only Range Reversion replication

Recorded after the 2018 frozen Range Reversion replication and before evaluating the V3 hypothesis on full-year FXCM 2017 EUR/USD M1 data.

## Why this hypothesis exists

The frozen all-direction Range Reversion candidate failed its preregistered 2018 replication because the full-strategy 95% Wilson lower confidence bound did not clear the hypothetical 82%-payout break-even win rate.

A preregistered secondary direction diagnostic showed a post-hoc asymmetry:

- CALL subset: 508 trades, 59.3939% win rate, Wilson lower 55.0114%, expectancy +0.07890;
- PUT subset: 5,990 trades, 55.1607% win rate, Wilson lower 53.8899%, expectancy +0.00387.

Because direction filtering was not the original primary hypothesis, the CALL-only result **cannot rescue the failed 2018 study**. It is treated here as a newly generated hypothesis requiring independent testing.

## Independence note

FXCM 2017 was previously used only for an engineering smoke test of one weekly archive file and parser behavior. No Range Reversion performance, CALL-only performance, parameter search, or full-year outcome was inspected. The V3 trading rules below are fixed before any full-year 2017 strategy evaluation.

## Frozen strategy

Start with the exact Range Reversion rules originally selected from 2019:

- `adx_max = 30.0`
- `rsi_lower = 25.0`
- `rsi_upper = 65.0`
- `band_buffer_atr = 0.10`
- `atr_pct_max = 0.70`
- expiry = 5 one-minute bars
- entry offset = 1 bar
- hypothetical fixed payout = 0.82
- ties = refund

**New V3 rule:** retain CALL (`+1`) signals only; all PUT (`-1`) signals become no-trade.

No thresholds, expiry, or direction rules may be changed after observing 2017.

## Primary 2017 test

The primary execution model matches the observed 2018 diagnostic so this is a direct replication of that newly generated hypothesis:

- overlapping positions allowed;
- stake = 1 unit;
- next-bar-open entry;
- five-bar expiry.

Pass criteria:

1. at least **300 trades**;
2. strictly positive payout-adjusted expectancy at 82%;
3. 95% Wilson lower confidence bound on non-tie win rate strictly above `1/(1+0.82) = 54.9451%`.

All three are required.

## Preregistered robustness diagnostics

These do not change the primary pass/fail result, but a primary pass will not be considered deployment-ready unless robustness is also convincing.

- one-position-at-a-time, cooldown 0;
- non-overlap with cooldown 1 and 2;
- entry offsets 2 and 3 (one/two additional one-minute delays);
- hypothetical payout repricing at 70%, 80%, 82%, and 90%;
- monthly performance stability;
- bootstrap confidence interval for payout-adjusted expectancy.

## Sequential decision

- If the primary 2017 test **fails**, abandon the CALL-only Range Reversion line unless a substantively different hypothesis is generated from independent reasoning; do not retune on 2017.
- If it **passes**, freeze it again and test one more untouched FX year before any Pocket-specific inference.

This remains regular-FX research, not Pocket Option/OTC evidence and not a guarantee of future returns.
