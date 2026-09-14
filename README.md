# Confluence Lab

Evidence-driven quantitative research for short-horizon, payout-aware trading hypotheses.

Confluence Lab is being built as a **research laboratory first**, not as a signal-selling interface. Its job is to collect reproducible market data, define causal features and strategies, backtest binary-style outcomes correctly, reject weak ideas aggressively, preserve negative findings, and only promote candidates that survive chronological validation, locked tests, robustness checks, and independent replication.

> **Important:** this repository contains research code and historical experiments. It does not guarantee future profitability, does not establish that Pocket Option/OTC behaves like regular FX, and does not justify advertising a fixed win rate.

## Current evidence status

The strongest result in the repository is the frozen **V5 HistGradientBoosting regular-FX candidate**.

- trained on FXCM EUR/USD M1 data from 2014;
- frozen before 2015 was accessed;
- 3-bar expiry;
- one-bar entry offset;
- probability threshold `0.625` for CALL and `0.375` for PUT;
- hypothetical fixed binary payout of `0.82`;
- gap-safe targets and settlement;
- no 2015 tuning.

On the independent FXCM 2015 replication it produced:

- 4,050 resolved non-tie trades;
- 60.8889% win rate;
- 59.3763% 95% Wilson lower bound;
- +0.107488 hypothetical units of expectancy per resolved trade at 82% payout;
- positive expectancy at 80% payout;
- positive delayed-entry and non-overlapping execution stress tests;
- positive lower confidence bounds in moving-block bootstrap tests.

See [`research/results/fxcm-2015-v5-replication.md`](research/results/fxcm-2015-v5-replication.md) for the authoritative evidence and limitations.

This is currently classified as a **replicated and robust regular-FX research candidate**, not as Pocket Option evidence.

## Evidence ladder

```text
hypothesis
    ↓
development search
    ↓
chronological validation
    ↓
locked unseen test
    ↓
payout / delay / overlap / bootstrap robustness
    ↓
freeze model + features + threshold + expiry
    ↓
independent temporal replication
    ↓
independent quote-source robustness
    ↓
broker-observed Pocket data + contemporaneous payouts
    ↓
prospective demo forward testing
    ↓
only then consider practical/live use
```

A failed stage is preserved as evidence. The project deliberately avoids retuning against failed locked or replication periods and then presenting the same period as fresh evidence.

## Research engine

The Python package currently includes:

- payout-aware binary settlement and break-even math;
- gap-safe expiry targets and settlement;
- chronological development / validation / locked-test splits;
- walk-forward validation;
- Wilson confidence intervals;
- ordinary and moving-block expectancy bootstrap analysis;
- payout, entry-delay, overlap and cooldown stress testing;
- indicators and causal feature generation;
- higher-timeframe features using only completed bars;
- rule-based strategy families;
- matrix search with validation gates;
- logistic-regression and HistGradientBoosting ML research pipelines;
- experiment/result provenance and dataset fingerprints;
- FXCM historical data ingestion;
- Dukascopy raw BI5 tick ingestion with source-object SHA-256 provenance;
- research-only Pocket candle and payout capture;
- Pocket snapshot consolidation with conflict detection;
- append-only prospective candidate/outcome ledgers.

## Pocket data boundary

Pocket-specific research is intentionally separated from independent regular-FX research.

The Pocket collector:

- reads session credentials from the local environment;
- does not expose trade execution methods in Confluence Lab;
- stores candles separately from payout observations;
- does not backfill a current payout onto historical candles;
- aligns payouts backward-only when building payout-aware research datasets;
- deduplicates overlapping snapshots;
- fails closed if overlapping historical candle snapshots disagree.

See [`docs/POCKET_DATA.md`](docs/POCKET_DATA.md).

## Installation

```bash
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
python -m pip install -e ".[dev]"
pytest
```

Supported CI environments currently include Python 3.11 and 3.12.

## Main commands

### Run a single research search

```bash
confluence-search path/to/dataset.parquet
```

### Run a strategy matrix

```bash
confluence-matrix-search path/to/dataset.parquet
```

### Fetch independent FX research data

```bash
confluence-fetch-fx EURUSD \
  --start 2025-01-01T00:00:00Z \
  --end 2026-01-01T00:00:00Z \
  --timeframe 1min
```

### Capture one Pocket research snapshot

Set the Pocket session value in your local environment rather than committing or pasting it into the repository.

```bash
export POCKET_SSID="..."

confluence-pocket-capture EURUSD_otc \
  --period-seconds 60 \
  --duration-seconds 3600
```

### Run a bounded Pocket observer

```bash
confluence-pocket-watch \
  EURUSD_otc GBPUSD_otc USDJPY_otc \
  --period-seconds 60 \
  --interval-seconds 60 \
  --duration-hours 6 \
  --snapshot-every 15 \
  --snapshot-duration-seconds 3600
```

### Consolidate Pocket observations

```bash
confluence-pocket-consolidate \
  --asset EURUSD_otc \
  --period-seconds 60
```

## Repository layout

```text
.github/workflows/   reproducible CI and preregistered experiment runs
src/confluence_lab/  research engine and data adapters
tests/               correctness and leakage-regression tests
scripts/             frozen experiment runners
research/hypotheses/ preregistrations and protocol amendments
research/results/    authoritative positive and negative findings
docs/                methodology and operating guides
benchmark-results/   machine-readable benchmark outputs kept when appropriate
```

## Research rules

1. **No lookahead.** Features may only use information available at signal time.
2. **Next-bar execution by default.** A completed signal candle cannot also provide its own entry price.
3. **Respect market gaps.** Expiry labels and settlement may not jump across missing bars as if time were continuous.
4. **Tune only on development data.** Validation and locked data are not search surfaces.
5. **Keep the locked set sealed until validation passes.**
6. **Freeze before replication.** Model, features, expiry and threshold must be fixed before a replication period/source is opened.
7. **Preserve negative findings.** Failed candidates remain in `research/results/`.
8. **Do not rescue a failure with post-hoc subgroups.** A subgroup observation can become a new preregistered hypothesis, not a rewrite of the original result.
9. **Use actual payout observations for Pocket economics.** A current payout must never be assumed to apply historically.
10. **No Martingale assumptions or guaranteed-return claims.**

For more detail, see:

- [`docs/RESEARCH_METHODOLOGY.md`](docs/RESEARCH_METHODOLOGY.md)
- [`docs/RESEARCH_WORKFLOW.md`](docs/RESEARCH_WORKFLOW.md)
- [`docs/POCKET_DATA.md`](docs/POCKET_DATA.md)

## Current frontier

The regular-FX V5 candidate has passed an independent FXCM temporal replication. The active next evidence step is an **untuned Dukascopy 2015 quote-source robustness study** using the exact frozen V5 candidate. After cross-source robustness, the project should prioritize broker-observed Pocket candles/payouts and prospective demo forward testing rather than further tuning the already-seen FXCM years.
