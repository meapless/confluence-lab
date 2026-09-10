# Confluence Lab Research Workflow

## Purpose

Confluence Lab is a research system for short-horizon, payout-aware trading hypotheses. It is designed to make false confidence harder: development search, validation, locked testing, walk-forward analysis and experiment provenance are separated intentionally.

It does not guarantee profitability and it must never manufacture performance numbers.

## 1. Install

Use Python 3.11 or 3.12.

```bash
python -m venv .venv
```

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

macOS/Linux:

```bash
source .venv/bin/activate
python -m pip install --upgrade pip
pip install -e ".[dev]"
pytest
```

## 2. Dataset contract

Minimum required columns:

- `timestamp`
- `open`
- `high`
- `low`
- `close`

Optional research columns include:

- `volume`
- `spread_mean`
- `asset`
- `market_type`
- `source`
- `payout`

Timestamps are normalized to UTC. Duplicate timestamps and impossible OHLC rows are rejected. Gaps are diagnosed and included in dataset provenance.

## 3. Independent regular-FX data

Dukascopy is the initial independent regular-FX source.

Example:

```bash
confluence-fetch-fx EURUSD \
  --start 2025-01-01T00:00:00Z \
  --end 2026-01-01T00:00:00Z \
  --timeframe 1min
```

The command stores candles plus a metadata sidecar containing the dataset fingerprint and diagnostics. The default output is Parquet. CSV may be requested explicitly by giving an `--output` path ending in `.csv`.

Dukascopy data does **not** contain Pocket Option historical payouts. Do not invent a historical payout column. For independent FX experiments, use explicit fixed-payout scenarios such as 0.75, 0.80, 0.85, 0.90 and 0.92.

## 4. Pocket research snapshots

The Pocket adapter is intentionally data-only. Confluence Lab does not expose buy/sell methods.

The adapter currently expects a compatible `BinaryOptionsToolsAsync` installation in the research environment. Keep Pocket connectivity optional and isolated from the research engine.

Set the Pocket session value only in your local shell environment:

Windows PowerShell:

```powershell
$env:POCKET_SSID="<your-session-value>"
```

macOS/Linux:

```bash
export POCKET_SSID="<your-session-value>"
```

Then capture research data:

```bash
confluence-pocket-capture EURUSD_otc \
  --period-seconds 60 \
  --duration-seconds 86400
```

Never commit the session value. It is not written to metadata.

### Critical payout rule

`get_payout()` returns a current payout observation. That value is logged with its observation timestamp. It is **not** copied backward across historical candles.

Historical expectancy using Pocket payouts is only valid when the payout at or near each historical entry time was actually observed and retained.

## 5. Single execution-setting research

A basic strategy-grid run:

```bash
confluence-search data.csv \
  --expiry-bars 3 \
  --fixed-payout 0.90 \
  --payout-column none
```

For datasets that contain trustworthy timestamped payout values, pass the appropriate payout column instead.

## 6. Large execution matrix

The default matrix searches:

- 288 Trend Pullback parameter combinations
- 4 expiries: 1, 2, 3 and 5 bars
- 5 payout-floor variants: any, 0.75, 0.80, 0.85 and 0.90

That is **5,760 development configurations per dataset**.

```bash
confluence-matrix-search pocket-history.parquet \
  --payout-column payout
```

For independent FX data without historical payout observations, use fixed-payout scenarios and disable the payout column.

## 7. Research gates

The pipeline is chronological:

1. Development
2. Validation
3. Locked test

Parameter search occurs only on development data.

The selected development candidate is evaluated once on validation. If validation does not clear its trade-count and expectancy gate, the locked test is not run.

Possible statuses:

- `no_development_candidate`
- `rejected_validation`
- `insufficient_locked_test`
- `tested`

`tested` means the candidate cleared validation and the locked-test sample met the configured minimum trade count. It does **not** mean profitable, safe or future-proof.

## 8. Locked-test discipline

A locked test is evidence, not another tuning surface.

If a strategy fails the locked test, do not adjust parameters based on that failure and call the same locked data fresh again. A changed hypothesis requires a new strategy version and, for strong claims, new untouched holdout data or prospective forward observations.

## 9. Walk-forward validation

Walk-forward validation repeatedly optimizes on a historical train window and evaluates only the following test window. Training always ends before the evaluated period starts.

Use it to examine:

- parameter stability
- regime dependence
- performance decay
- candidate frequency
- drawdown stability

## 10. Monte Carlo

Monte Carlo bootstraps observed trade P&L to estimate distributions of:

- final P&L
- drawdown
- profitability frequency under resampling

It is a robustness diagnostic, not a forecast or guarantee.

## 11. Experiment registry

Research reports are appended to `experiments/registry.jsonl` through a SHA-256 hash chain. If an older line is edited, verification fails and new records are refused until the integrity problem is resolved.

The registry records dataset fingerprints so a result can be associated with the exact input data used.

## 12. Interpretation rules

Do not promote a strategy because one split has a high win rate.

At minimum inspect:

- number of resolved trades
- win-rate confidence interval
- payout-adjusted expectancy
- maximum drawdown
- maximum losing streak
- development vs validation vs locked-test behavior
- walk-forward stability
- performance by time and market regime
- sensitivity to expiry and payout
- prospective forward-test agreement

A narrow, stable edge with many observations is more valuable than a spectacular percentage from a tiny or tuned sample.
